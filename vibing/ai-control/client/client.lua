local CONFIG_PATH = "/aicontrol/config"
local LOG_PATH = "/aicontrol/log"
local CLIENT_VERSION = "0.1.0"
local OUTPUT_TRUNCATION_MARKER = "\n...[output truncated]"
local RETURN_TRUNCATION_MARKER = "...[return values truncated]"
local HOOK_YIELD = {}
local EVENT_YIELD = {}
local MAX_HOOK_INSTRUCTIONS = 10000
local MAX_CAPTURE_BYTES = 1048576

local config
local socket
local maxMessageBytes = 131072
local heartbeatInterval = 30
local nextMessageId = 0
local activeExecutionId
local interruptRequested = false
local pendingInterruptIds = {}
local pendingExecutions = {}

local function log(message)
    if not fs.exists("/aicontrol") then fs.makeDir("/aicontrol") end
    local handle = fs.open(LOG_PATH, "a")
    if handle then
        handle.writeLine(os.date("!%Y-%m-%dT%H:%M:%SZ") .. " " .. tostring(message))
        handle.close()
    end
end

local function loadConfig()
    local handle = fs.open(CONFIG_PATH, "r")
    if not handle then error("missing /aicontrol/config") end
    local value = textutils.unserializeJSON(handle.readAll())
    handle.close()
    if type(value) ~= "table" or type(value.server_url) ~= "string" or type(value.device_id) ~= "string" then
        error("invalid device configuration")
    end
    return value
end

local function saveConfig()
    local handle = fs.open(CONFIG_PATH, "w")
    if not handle then error("cannot write device configuration") end
    handle.write(textutils.serializeJSON(config))
    handle.close()
end

local function isSafeRelativePath(path)
    if type(path) ~= "string" or path == "" or path:sub(1, 1) == "/" then return false end
    if path:find("[^%w%._/%-]") then return false end
    for segment in path:gmatch("[^/]+") do
        if segment == "." or segment == ".." then return false end
    end
    return true
end

local function encode(message)
    return textutils.serializeJSON(message)
end

local function nextId(prefix)
    nextMessageId = nextMessageId + 1
    return prefix .. "-" .. tostring(os.epoch("utc")) .. "-" .. tostring(nextMessageId)
end

local function utf8Prefix(value, maxBytes)
    local finish = math.min(#value, maxBytes)
    while finish > 0 do
        local nextByte = value:byte(finish + 1)
        if not nextByte or nextByte < 128 or nextByte > 191 then break end
        finish = finish - 1
    end
    return value:sub(1, finish)
end

local function splitUtf8(value, maxBytes)
    local parts = {}
    local start = 1
    while start <= #value do
        local finish = math.min(#value, start + maxBytes - 1)
        while finish >= start do
            local nextByte = value:byte(finish + 1)
            if not nextByte or nextByte < 128 or nextByte > 191 then break end
            finish = finish - 1
        end
        if finish < start then error("frame limit cannot fit a UTF-8 code point") end
        parts[#parts + 1] = value:sub(start, finish)
        start = finish + 1
    end
    return parts
end

local function sendRaw(message)
    if not socket then return false end
    local ok, result, reason = pcall(socket.send, encode(message))
    if not ok then
        log("websocket send failed: " .. tostring(result))
        return false
    end
    if result == false then
        log("websocket send failed: " .. tostring(reason))
        return false
    end
    return true
end

local function sendMessage(message)
    local serialized = encode(message)
    if #serialized <= maxMessageBytes then
        if not socket then return false end
        local ok, result, reason = pcall(socket.send, serialized)
        if not ok or result == false then
            log("websocket send failed: " .. tostring(ok and reason or result))
            return false
        end
        return true
    end

    local chunkId = message.id or nextId("chunk")
    local pieceSize = math.max(1, math.floor(maxMessageBytes / 2))
    while pieceSize > 0 do
        local parts = splitUtf8(serialized, pieceSize)
        local chunks = {}
        local fits = true
        for index, payload in ipairs(parts) do
            local chunk = {
                v = 1,
                type = "chunk",
                id = chunkId,
                chunk = { index = index - 1, total = #parts },
                data = { message_type = message.type, payload = payload },
            }
            if #encode(chunk) > maxMessageBytes then
                fits = false
                break
            end
            chunks[#chunks + 1] = chunk
        end
        if fits then
            for _, chunk in ipairs(chunks) do
                if not sendRaw(chunk) then return false end
            end
            return true
        end
        if pieceSize == 1 then break end
        pieceSize = math.max(1, math.floor(pieceSize / 2))
    end
    log("configured websocket frame limit is too small for chunk envelope")
    return false
end

local function envelope(kind, data, id, replyTo)
    return { v = 1, type = kind, id = id, reply_to = replyTo, data = data }
end

local function safeString(value)
    if type(value) == "string" then return value end
    if value == nil then return "nil" end
    local ok, result = pcall(textutils.serialize, value)
    if ok and result then return result end
    return tostring(value)
end

local function appendCapture(buffer, text)
    if buffer.bytes >= MAX_CAPTURE_BYTES then
        buffer.truncated = true
        return
    end
    local piece = utf8Prefix(text, MAX_CAPTURE_BYTES - buffer.bytes)
    buffer.parts[#buffer.parts + 1] = piece
    buffer.bytes = buffer.bytes + #piece
    if #piece < #text then buffer.truncated = true end
end

local function sanitize(value, seen, depth)
    local valueType = type(value)
    if valueType == "nil" then return textutils.json_null or false end
    if valueType == "boolean" or valueType == "string" then return value end
    if valueType == "number" then
        if value ~= value or value == math.huge or value == -math.huge then
            return { ["$number"] = tostring(value) }
        end
        return value
    end
    if valueType ~= "table" then return tostring(value) end
    if depth > 8 then return "...[nested value truncated]" end
    if seen[value] then return "...[circular reference]" end
    seen[value] = true

    local maxIndex = 0
    local numericCount = 0
    local onlyArrayKeys = true
    for key in pairs(value) do
        if type(key) == "number" and key >= 1 and key % 1 == 0 then
            maxIndex = math.max(maxIndex, key)
            numericCount = numericCount + 1
        else
            onlyArrayKeys = false
        end
    end
    local result
    if onlyArrayKeys and numericCount == maxIndex then
        result = {}
        for index = 1, maxIndex do
            result[index] = sanitize(value[index], seen, depth + 1)
        end
    else
        result = {}
        for key, item in pairs(value) do
            if type(key) == "string" then
                result[key] = sanitize(item, seen, depth + 1)
            end
        end
    end
    seen[value] = nil
    return result
end

local function safeJson(value)
    return sanitize(value, {}, 0)
end

local function serializeResult(message)
    local ok, result = pcall(encode, message)
    if not ok then return nil end
    return result
end

local function truncateResult(message)
    local limit = math.max(256, maxMessageBytes - 512)
    local serialized = serializeResult(message)
    if serialized and #serialized <= limit then return message end

    local originalOutput = message.data.output or ""
    while #originalOutput > 0 do
        local target = math.floor(#originalOutput * 0.75)
        originalOutput = utf8Prefix(originalOutput, target)
        message.data.output = originalOutput .. OUTPUT_TRUNCATION_MARKER
        serialized = serializeResult(message)
        if serialized and #serialized <= limit then return message end
    end
    message.data.output = OUTPUT_TRUNCATION_MARKER

    local values = message.data.return_values or {}
    while #values > 0 do
        values[#values] = nil
        if #values > 0 then
            values[#values] = RETURN_TRUNCATION_MARKER
        else
            values[1] = RETURN_TRUNCATION_MARKER
        end
        message.data.return_values = values
        serialized = serializeResult(message)
        if serialized and #serialized <= limit then return message end
        values[#values] = nil
    end

    message.data.return_values = { RETURN_TRUNCATION_MARKER }
    if message.data.traceback then message.data.traceback = utf8Prefix(message.data.traceback, 512) end
    if message.data.error then message.data.error = utf8Prefix(message.data.error, 256) end
    serialized = serializeResult(message)
    if serialized and #serialized <= maxMessageBytes then return message end
    message.data.output = OUTPUT_TRUNCATION_MARKER
    message.data.return_values = {}
    message.data.traceback = nil
    message.data.error = "Result exceeded the configured message limit"
    return message
end

local function nowMs()
    if os.epoch then return os.epoch("utc") end
    return math.floor(os.clock() * 1000)
end

local function sendExecutionResult(execId, ok, values, output, message, traceback, duration)
    local response = envelope("exec_result", {
        ok = ok,
        return_values = values or {},
        output = output or "",
        error = message,
        traceback = traceback,
        duration_ms = duration,
    }, nil, execId)
    sendMessage(truncateResult(response))
end

local function eventReply(messageId, interrupted, explanation)
    if not messageId then return end
    sendMessage(envelope("event", {
        name = "interrupt_result",
        args = { interrupted, explanation },
    }, nextId("interrupt"), messageId))
end

local function cancelQueuedExecutions(reason)
    local queued = pendingExecutions
    pendingExecutions = {}
    for _, message in ipairs(queued) do
        sendExecutionResult(
            message.id,
            false,
            {},
            "",
            reason,
            "Execution was cancelled before it started.",
            0
        )
    end
    return #queued
end

local function copyTable(source, excluded)
    local result = {}
    for key, value in pairs(source) do
        if not excluded or not excluded[key] then result[key] = value end
    end
    return result
end

local function outputEnvironment(capture)
    local environment = copyTable(_ENV, { debug = true })
    local realPrint = print
    local realWrite = write
    environment.error = error
    environment.print = function(...)
        local values = {}
        for index = 1, select("#", ...) do
            values[index] = safeString(select(index, ...))
        end
        appendCapture(capture, table.concat(values, "\t") .. "\n")
        realPrint(...)
    end
    environment.write = function(...)
        local values = {}
        for index = 1, select("#", ...) do
            values[index] = safeString(select(index, ...))
        end
        appendCapture(capture, table.concat(values))
        realWrite(...)
    end

    if type(os) == "table" then
        environment.os = copyTable(os)
        environment.os.pullEvent = function(filter)
            local event = table.pack(coroutine.yield(EVENT_YIELD, filter))
            if event[1] == "terminate" then error("Terminated", 0) end
            return table.unpack(event, 1, event.n)
        end
        environment.os.pullEventRaw = function(filter)
            local event = table.pack(coroutine.yield(EVENT_YIELD, filter))
            return table.unpack(event, 1, event.n)
        end
    end
    return environment
end

local function runProgram(message)
    local data = message.data
    activeExecutionId = message.id
    interruptRequested = false
    local capture = { parts = {}, bytes = 0, truncated = false }
    local started = nowMs()
    sendMessage(envelope("exec_started", { name = data.name, started_at = tostring(started) }, nil, message.id))

    local environment = outputEnvironment(capture)
    local fn, compileError = load(data.code, "=" .. (data.name or "remote"), "t", environment)
    if not fn then
        local output = table.concat(capture.parts)
        if capture.truncated then output = output .. OUTPUT_TRUNCATION_MARKER end
        sendExecutionResult(
            message.id,
            false,
            {},
            output,
            tostring(compileError),
            debug.traceback(tostring(compileError), 2),
            nowMs() - started
        )
        activeExecutionId = nil
        return
    end

    local function errorHandler(err)
        local errorText = tostring(err)
        return { message = errorText, traceback = debug.traceback(errorText, 2) }
    end
    local program = coroutine.create(function()
        return xpcall(function() return table.pack(fn()) end, errorHandler)
    end)
    local hookInstalled = false
    if debug and debug.sethook then
        hookInstalled = pcall(debug.sethook, program, function()
            coroutine.yield(HOOK_YIELD)
        end, "", MAX_HOOK_INSTRUCTIONS)
    end

    local resumeArgs = {}
    local success, packedOrError, yieldedFilter = coroutine.resume(program, table.unpack(resumeArgs))
    local interrupted = false
    local programError
    local programTraceback
    local timedOut = false
    local returnValues = {}
    while success and coroutine.status(program) ~= "dead" do
        if interruptRequested then
            interrupted = true
            break
        end
        if packedOrError == HOOK_YIELD then
            if nowMs() - started >= data.timeout_ms then
                timedOut = true
                break
            end
            os.queueEvent("aicontrol_program_tick")
            os.pullEvent("aicontrol_program_tick")
            resumeArgs = {}
        elseif packedOrError == EVENT_YIELD then
            local event = table.pack(os.pullEventRaw(yieldedFilter))
            resumeArgs = { table.unpack(event, 1, event.n) }
        else
            programError = "Remote program yielded an unsupported value"
            programTraceback = debug.traceback(program, programError)
            break
        end
        success, packedOrError, yieldedFilter = coroutine.resume(program, table.unpack(resumeArgs))
    end
    if not success then
        programError = tostring(packedOrError)
        programTraceback = debug.traceback(program, programError)
    elseif not interrupted and coroutine.status(program) == "dead" then
        if packedOrError then
            local packedReturns = yieldedFilter
            for index = 1, packedReturns.n do
                returnValues[index] = safeJson(packedReturns[index])
            end
        else
            local failure = yieldedFilter
            programError = failure.message
            programTraceback = failure.traceback
        end
    end

    if hookInstalled then pcall(debug.sethook, program, nil) end
    local output = table.concat(capture.parts)
    if capture.truncated then output = output .. OUTPUT_TRUNCATION_MARKER end
    if interrupted then
        programError = "Interrupted"
        programTraceback = "Execution interrupted. An in-flight turtle API call cannot be aborted; interruption takes effect at the next Lua instruction yield."
    elseif timedOut then
        programError = "Execution timed out"
        programTraceback = "Execution exceeded its " .. tostring(data.timeout_ms) .. " ms timeout and was stopped at a Lua instruction yield."
    end
    sendExecutionResult(
        message.id,
        programError == nil and not interrupted,
        returnValues,
        output,
        programError,
        programTraceback,
        nowMs() - started
    )
    activeExecutionId = nil
    interruptRequested = false
    for _, interrupt in ipairs(pendingInterruptIds) do
        local explanation
        if interrupt.emergency then
            explanation = "Emergency stop halted active execution and cancelled "
                .. tostring(interrupt.cancelled_count)
                .. " queued program(s)"
        else
            explanation = interrupted and "Program stopped" or "Program had already completed"
        end
        eventReply(interrupt.id, interrupted, explanation)
    end
    pendingInterruptIds = {}
end

local function handleIncoming(message)
    if message.type == "exec" then
        runProgram(message)
    elseif message.type == "interrupt" then
        local emergency = message.data and message.data.reason == "emergency"
        local cancelledCount = emergency and cancelQueuedExecutions("Cancelled by emergency stop") or 0
        if activeExecutionId then
            interruptRequested = true
            pendingInterruptIds[#pendingInterruptIds + 1] = {
                id = message.id,
                emergency = emergency,
                cancelled_count = cancelledCount,
            }
        else
            local explanation = emergency
                and ("Emergency stop cleared " .. tostring(cancelledCount) .. " queued program(s)")
                or "No program is currently running"
            eventReply(message.id, false, explanation)
        end
    elseif message.type == "update_client" then
        local ok, reason = pcall(function()
            if message.data.files then
                for relativePath, contents in pairs(message.data.files) do
                    if not isSafeRelativePath(relativePath) then error("unsafe path in update") end
                    local target = relativePath == "startup.lua" and "/startup.lua" or ("/aicontrol/" .. relativePath)
                    local temporary = target .. ".new"
                    local handle = fs.open(temporary, "w")
                    if not handle then error("cannot write " .. target) end
                    handle.write(contents)
                    handle.close()
                    if fs.exists(target) then fs.delete(target) end
                    fs.move(temporary, target)
                end
            else
                local response, downloadError = http.get(message.data.url, nil, true)
                if not response then error(downloadError or "update download failed") end
                local manifest = textutils.unserializeJSON(response.readAll())
                response.close()
                if type(manifest) ~= "table" or type(manifest.files) ~= "table" then
                    error("update URL did not return a files manifest")
                end
                for relativePath, fileUrl in pairs(manifest.files) do
                    if not isSafeRelativePath(relativePath) or type(fileUrl) ~= "string" then
                        error("invalid path or URL in update manifest")
                    end
                    local fileResponse, fileError = http.get(fileUrl, nil, true)
                    if not fileResponse then error(fileError or ("cannot download " .. relativePath)) end
                    local contents = fileResponse.readAll()
                    fileResponse.close()
                    local target = relativePath == "startup.lua" and "/startup.lua" or ("/aicontrol/" .. relativePath)
                    local temporary = target .. ".new"
                    local handle = fs.open(temporary, "w")
                    if not handle then error("cannot write " .. target) end
                    handle.write(contents)
                    handle.close()
                    if fs.exists(target) then fs.delete(target) end
                    fs.move(temporary, target)
                end
                message.data.version = manifest.version or message.data.version
            end
            config.client_version = message.data.version
            saveConfig()
        end)
        if ok then os.reboot() else log("client update failed: " .. tostring(reason)) end
    elseif message.type == "config" then
        for key, value in pairs(message.data.settings) do
            if key == "heartbeat_interval_s" and type(value) == "number" and value > 0 then
                heartbeatInterval = value
            end
        end
    elseif message.type == "term_input" then
        os.queueEvent("char", message.data.text)
    end
end

local function sendTelemetry()
    local kind = (turtle and "turtle") or (pocket and "pocket") or "computer"
    local values = {
        device_id = config.device_id,
        label = config.label or os.getComputerLabel() or tostring(os.getComputerID()),
        kind = kind,
        advanced = term.isColor and term.isColor() or false,
        version = CLIENT_VERSION,
        uptime = os.clock(),
        day = os.day and os.day() or nil,
        time = os.time and os.time() or nil,
        peripherals = {},
    }

    if turtle then
        values.fuel = turtle.getFuelLevel()
        values.fuel_limit = turtle.getFuelLimit()
        values.selected_slot = turtle.getSelectedSlot()
        values.inventory = {}
        for slot = 1, 16 do
            local ok, detail = pcall(turtle.getItemDetail, slot)
            if ok and detail then
                detail.slot = slot
                values.inventory[#values.inventory + 1] = detail
            end
        end
        for side, method in pairs({ left = "getEquippedLeft", right = "getEquippedRight" }) do
            if turtle[method] then
                local ok, equipped = pcall(turtle[method])
                if ok then values["equipped_" .. side] = equipped end
            end
        end
    end

    if peripheral and peripheral.getNames then
        for _, name in ipairs(peripheral.getNames()) do
            local ok, peripheralType = pcall(peripheral.getType, name)
            values.peripherals[#values.peripherals + 1] = {
                name = name,
                type = ok and peripheralType or "unknown",
            }
        end
    end

    if fs.exists("/squid/INS.lua") and fs.exists("/GPS/INS.json") then
        local ok, position = pcall(function()
            local handle = fs.open("/GPS/INS.json", "r")
            local result = textutils.unserializeJSON(handle.readAll())
            handle.close()
            return result and result.current_coord
        end)
        if ok and position then values.position = position end
    elseif gps and gps.locate then
        local ok, x, y, z = pcall(gps.locate, 1)
        if ok and x and y and z then values.position = { x = x, y = y, z = z } end
    end

    sendMessage(envelope("telemetry", { values = values, timestamp = tostring(nowMs()) }, nextId("telemetry")))
end

local function isSocketTimeout(reason)
    local normalized = tostring(reason or ""):lower():gsub("%s+", "")
    return normalized:find("timeout", 1, true) ~= nil
        or normalized:find("timedout", 1, true) ~= nil
end

local function readerLoop()
    while true do
        local raw, reason = socket.receive(0.5)
        if raw then
            local ok, message = pcall(textutils.unserializeJSON, raw)
            if ok and type(message) == "table" and message.v == 1 then
                if message.type == "hello_ack" then
                    maxMessageBytes = message.data.max_message_bytes or maxMessageBytes
                    heartbeatInterval = message.data.heartbeat_interval_s or heartbeatInterval
                    if message.data.device_secret then
                        config.device_secret = message.data.device_secret
                        config.pairing_code = nil
                        saveConfig()
                    end
                    if not message.data.accept then error(message.data.reason or "server rejected client") end
                    sendTelemetry()
                elseif message.type == "interrupt" then
                    local emergency = message.data and message.data.reason == "emergency"
                    local cancelledCount = emergency and cancelQueuedExecutions("Cancelled by emergency stop") or 0
                    if activeExecutionId then
                        interruptRequested = true
                        pendingInterruptIds[#pendingInterruptIds + 1] = {
                            id = message.id,
                            emergency = emergency,
                            cancelled_count = cancelledCount,
                        }
                    else
                        local explanation = emergency
                            and ("Emergency stop cleared " .. tostring(cancelledCount) .. " queued program(s)")
                            or "No program is currently running"
                        eventReply(message.id, false, explanation)
                    end
                elseif message.type == "exec" then
                    pendingExecutions[#pendingExecutions + 1] = message
                    os.queueEvent("aicontrol_message")
                else
                    os.queueEvent("aicontrol_message", message)
                end
            elseif not ok then
                log("ignored invalid server JSON")
            end
        elseif reason and not isSocketTimeout(reason) then
            log("websocket reader ended: " .. tostring(reason))
            return
        end
    end
end

local function heartbeatLoop()
    while true do
        sleep(heartbeatInterval)
        if not sendMessage(envelope("heartbeat", { timestamp = tostring(nowMs()) }, nextId("heartbeat"))) then
            log("heartbeat send failed")
            return
        end
        sendTelemetry()
    end
end

local function executionLoop()
    while true do
        local message = table.remove(pendingExecutions, 1)
        if not message then
            os.pullEvent("aicontrol_message")
            message = table.remove(pendingExecutions, 1)
        end
        if message then
            local ok, reason = pcall(handleIncoming, message)
            if not ok then
                log("message handler failed: " .. tostring(reason))
                sendMessage(envelope("error", {
                    code = "client_handler_error",
                    message = tostring(reason),
                }, nextId("error")))
            end
        end
    end
end

local function runConnection()
    local wsUrl = config.server_url:gsub("^https://", "wss://"):gsub("^http://", "ws://")
    log("connecting to " .. wsUrl .. "/ws/computer")
    local connected, result, reason = pcall(http.websocket, wsUrl .. "/ws/computer")
    if not connected or not result then error("websocket connect failed: " .. tostring(connected and reason or result)) end
    socket = result
    log("websocket connected; sending hello")
    local hello = envelope("hello", {
        device_id = config.device_id,
        secret = config.device_secret or config.pairing_code,
        kind = (turtle and "turtle") or (pocket and "pocket") or "computer",
        label = config.label or os.getComputerLabel() or tostring(os.getComputerID()),
        cc_version = _HOST and _HOST.version,
        client_version = CLIENT_VERSION,
        capabilities = { "terminal", "filesystem", "peripherals", "interrupt" },
    }, nextId("hello"))
    if not sendMessage(hello) then error("unable to send hello") end

    local raw, receiveError = socket.receive(5)
    if not raw then error("server closed before hello acknowledgement: " .. tostring(receiveError)) end
    local ack = textutils.unserializeJSON(raw)
    if type(ack) ~= "table" or ack.type ~= "hello_ack" or not ack.data.accept then
        error(type(ack) == "table" and ack.data and ack.data.reason or "invalid hello acknowledgement")
    end
    log("server accepted hello")
    maxMessageBytes = ack.data.max_message_bytes or maxMessageBytes
    heartbeatInterval = ack.data.heartbeat_interval_s or heartbeatInterval
    if ack.data.device_secret then
        config.device_secret = ack.data.device_secret
        config.pairing_code = nil
        saveConfig()
    end
    sendTelemetry()
    local completedLoop = parallel.waitForAny(readerLoop, heartbeatLoop, executionLoop)
    log("connection worker " .. tostring(completedLoop) .. " ended; reconnecting")
    socket.close()
    socket = nil
    return true
end

local function main()
    local delay = 1
    while true do
        local ok, connected = pcall(runConnection)
        if not ok then
            log("connection stopped: " .. tostring(connected))
        elseif connected then
            delay = 1
            log("connection was established; retry backoff reset")
        end
        if socket then pcall(socket.close); socket = nil end
        log("retrying in " .. tostring(delay) .. " seconds")
        sleep(delay)
        delay = math.min(delay * 2, 60)
    end
end

local ok, reason = pcall(function()
    config = loadConfig()
    main()
end)
if not ok then
    log("fatal client error: " .. tostring(reason))
    printError("AI Control: " .. tostring(reason))
end
