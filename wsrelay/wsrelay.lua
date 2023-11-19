local expect = require "cc.expect"
local expect, field, range = expect.expect, expect.field, expect.range

local DEFAULT_PROTOCOL = "default"

local WSRelay = {}
WSRelay.__index = WSRelay

function WSRelay.new(ip, channel)
    local self = setmetatable({}, WSRelay)
    expect(1, ip, "string")
    expect(2, channel, "string")
    self.ip = ip
    self.channel = channel
    self.wsip = string.format("%s/%s", ip, channel)
    local headers = {["computer_id"] = tostring(os.getComputerID())}
    self.ws = assert(http.websocket(self.wsip, headers))
    return self
end

function WSRelay:close()
    self.ws.close()
end

function WSRelay:listen(process_func)
    expect(1, process_func, "function")
    while true do
        local raw_packet, binary_bool = self.ws.receive()
        if raw_packet then
            local packet = textutils.unserializeJSON(raw_packet)
            process_func(packet)
        end
    end
end

function WSRelay:send(data, protocol)
    protocol = protocol or DEFAULT_PROTOCOL
    expect(1, data, "table", "string")
    expect(2, protocol, "string")
    local packet = {
        protocol = protocol,
        computer_id = os.getComputerID(),
        data = data
    }
    self.ws.send(textutils.serializeJSON(packet))
end

-- PASS IN YOUR MAIN FUNCTION HERE SO THAT THE WEBSOCKET CAN BE CLOSED SAFELY
function WSRelay:runMainSafely(main)
    xpcall(main,function (err)
        self.ws.close()
        error(err)
    end)
    self:close()
end


return {
    WSRelay = WSRelay
}