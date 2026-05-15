-- This is just a showcase of how you could use the wsrelay libary
--
local WS = require("wscontrol")
local telemetry = require("telemetry")
local PROTOCOLS = require("protocols")
local logger = require("logger")

local log = logger.new("squidbot", { level = logger.DEBUG, file = "squidbot.log" })
local ip = "ws://127.0.0.1:8766"
local channel = "squidbot"

local PING_RATE = 5 -- Seconds

local controller_ws = WS.WSControl.new(ip, channel, telemetry.telemetryParams())


local function transmitTelemetry()
    log:info("Starting telemetry transmission...")
    while true do
        controller_ws:send(telemetry.getComputerState(), PROTOCOLS.TELEMETRY)
        sleep(PING_RATE)
    end
end


local function runCommand(packet)
    local func, err = load(packet.data, "command", "t", _ENV)
        log:debug("Received command: %s", packet.data)
        if func then
            local success, result = pcall(func)
            if success then
                log:debug("command executed successfully")
                controller_ws:send({ type = "result", result = result }, PROTOCOLS.COMMAND_SUCCESS)
            else
                log:error("command runtime error: %s", result)
                controller_ws:send({ type = "error", error = result }, PROTOCOLS.COMMAND_ERROR)
            end
        else
            log:error("command compile error: %s", err)
            controller_ws:send({ type = "error", error = err }, PROTOCOLS.COMMAND_ERROR)
        end
end


local function recieve(packet)
    if packet.protocol == PROTOCOLS.COMMAND then
        runCommand(packet)
    end
end

local function startListening()
    controller_ws:listen(recieve)
end


local function main()
    parallel.waitForAll(
        transmitTelemetry,
        startListening
    )
    sleep(2)
end

controller_ws:runMainSafely(main)