local ws_url = "ws://192.168.50.201:8765"

local function gather_inventories()
    local inventories = {}
    for _, inv in pairs({ peripheral.find("inventory") }) do
        local name = peripheral.getName(inv)
        local items = {}
        for slot, item in pairs(inv.list()) do
            local detail = inv.getItemDetail(slot)
            if detail then
                detail.slot = slot
                table.insert(items, detail)
            end
        end
        table.insert(inventories, {
            peripheral = name,
            items = items
        })
    end
    return inventories
end


local ws, err = http.websocket(ws_url)
if not ws then
    print("Failed to connect: " .. tostring(err))
    return
end

print("Connected! Waiting for server commands...")

while true do
    local msg = ws.receive()
    if not msg then
        print("Connection closed")
        break
    end
    print("msg recv:", msg)
    if msg == "request_inventory" then
        local data = gather_inventories()
        local json = textutils.serializeJSON(data)
        ws.send(json)
    else
        print("Received unknown command: " .. msg)
    end
end

ws.close()
