local WS = require("wsrelay")
local args = {...}
local ip = "wss://wsrelay.suicidesquid.net"
local channel = "cc"

local function printTable(t)
    for k, v in pairs(t) do
        print(k,v)
    end
end

local function saveToJson(packet)
    local filepath = "relay_data.json"
    local playerSettings = fs.open(filepath, "a")
    playerSettings.write(textutils.serializeJSON(packet.data))
    playerSettings.close()
end

local relay = WS.WSRelay.new(ip, channel)

local function main()
    if args[1] == "send" then
        for i = 1, 100 do
            relay:send(tostring(i))
        end
    else
        relay:listen(saveToJson)
    end
    sleep(2)
end

relay:runMainSafely(main)
