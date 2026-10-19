local configPath = "/aicontrol/config"
local clientPath = "/aicontrol/client.lua"
local logPath = "/aicontrol/log"

local function log(message)
    if not fs.exists("/aicontrol") then fs.makeDir("/aicontrol") end
    local handle = fs.open(logPath, "a")
    if handle then
        handle.writeLine(os.date("!%Y-%m-%dT%H:%M:%SZ") .. " " .. tostring(message))
        handle.close()
    end
end

local function readConfig()
    if not fs.exists(configPath) then error("missing /aicontrol/config") end
    local handle = fs.open(configPath, "r")
    local value = textutils.unserializeJSON(handle.readAll())
    handle.close()
    if type(value) ~= "table" or not value.server_url or not value.device_id then
        error("invalid /aicontrol/config")
    end
    return value
end

local function request(url)
    local response, reason = http.get(url, nil, true)
    if not response then return nil, reason end
    local body = response.readAll()
    response.close()
    return body
end

local function isSafeRelativePath(path)
    if type(path) ~= "string" or path == "" or path:sub(1, 1) == "/" then return false end
    if path:find("[^%w%._/%-]") then return false end
    for segment in path:gmatch("[^/]+") do
        if segment == "." or segment == ".." then return false end
    end
    return true
end

local function updateFiles(config)
    local manifestBody, reason = request(config.server_url .. "/client/manifest.json")
    if not manifestBody then error("manifest download failed: " .. tostring(reason)) end
    local manifest = textutils.unserializeJSON(manifestBody)
    if type(manifest) ~= "table" or type(manifest.files) ~= "table" then
        error("server returned an invalid client manifest")
    end

    local changed = false
    for relativePath in pairs(manifest.files) do
        if not isSafeRelativePath(relativePath) then error("unsafe path in client manifest") end
        local body, fileError = request(config.server_url .. "/client/" .. relativePath)
        if not body then error("client file download failed: " .. tostring(fileError)) end
        local target = relativePath == "startup.lua" and "/startup.lua" or ("/aicontrol/" .. relativePath)
        local old = nil
        if fs.exists(target) then
            local handle = fs.open(target, "r")
            old = handle.readAll()
            handle.close()
        end
        if old ~= body then
            local temporary = target .. ".new"
            local handle = fs.open(temporary, "w")
            if not handle then error("cannot write update file " .. target) end
            handle.write(body)
            handle.close()
            if fs.exists(target) then fs.delete(target) end
            fs.move(temporary, target)
            changed = true
        end
    end
    config.client_version = manifest.version or config.client_version
    local handle = fs.open(configPath, "w")
    handle.write(textutils.serializeJSON(config))
    handle.close()
    return changed
end

local ok, config = pcall(readConfig)
if not ok then
    log("configuration error: " .. tostring(config))
    printError("AI Control: " .. tostring(config))
    return
end

local updateOk, updated = pcall(updateFiles, config)
if not updateOk then log("update failed: " .. tostring(updated)) end
if not fs.exists(clientPath) then
    log("client file is missing")
    printError("AI Control client is missing")
    return
end

local runOk, runError = pcall(shell.run, clientPath)
if not runOk then
    log("client stopped: " .. tostring(runError))
    printError("AI Control stopped: " .. tostring(runError))
end
