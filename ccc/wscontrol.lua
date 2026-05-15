local expect = require "cc.expect"
local expect, field, range = expect.expect, expect.field, expect.range

local DEFAULT_PROTOCOL = "default"

local WSControl = {}
WSControl.__index = WSControl

function buildParamsString(params)
    local paramParts = {}
    for k, v in pairs(params) do
        table.insert(paramParts, string.format("%s=%s", k, tostring(v)))
    end
    return table.concat(paramParts, "&")
end

function WSControl.new(ip, channel, params)
    local self = setmetatable({}, WSControl)
    local params = params or {}
    expect(1, ip, "string")
    expect(2, channel, "string")
    expect(3, params, "table")
    self.ip = ip
    self.channel = channel
    self.params = params
    self.wsip = string.format("%s/%s?%s", ip, channel, buildParamsString(params))
    local headers = {["computer_id"] = tostring(os.getComputerID())}
    self.ws = assert(http.websocket(self.wsip, headers))
    return self
end

function WSControl:close()
    self.ws.close()
end

function WSControl:listen(process_func)
    expect(1, process_func, "function")
    while true do
        local raw_packet, binary_bool = self.ws.receive()
        if raw_packet then
            local packet = textutils.unserializeJSON(raw_packet)
            process_func(packet)
        end
    end
end

function WSControl:send(data, protocol)
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
function WSControl:runMainSafely(main)
    xpcall(main,function (err)
        self.ws.close()
        error(err)
    end)
    self:close()
end


return {
    WSControl = WSControl
}