-- This is just a showcase of how you could use the wsrelay libary
--
local WS = require("wsrelay")
local ip = "wss://wsrelay.suicidesquid.net"
local player = "riewest"
local channel = "tracker/" .. player

local PING_RATE = 3 -- Seconds
local relay = WS.WSRelay.new(ip, channel)

local function recieveLocation(packet)
    local loc = packet.data
    print(loc.x, loc.y, loc.z)
end

local function transmitLocation()
    local raw_x, raw_y, raw_z = gps.locate()
    local location = {
        x = math.floor(raw_x),
        y = math.floor(raw_y) -1,
        z = math.floor(raw_z)
    }
    relay:send(location)
end


local function main()
    if pocket then
        while true do
            transmitLocation()
            sleep(PING_RATE)
        end
    else
        relay:listen(recieveLocation)
    end
    sleep(2)
end

relay:runMainSafely(main)