local server_url = "http://192.168.50.201:5000/upload_inventory"
local inventories = {}

-- Find all attached inventories
for _, inv in pairs({ peripheral.find("inventory") }) do
    local name = peripheral.getName(inv)
    local items = {}

    for slot, item in pairs(inv.list()) do
        local detail = inv.getItemDetail(slot)
        if detail then
            detail.slot = slot  -- Include slot number in the payload
            table.insert(items, detail)
        end
    end

    table.insert(inventories, {
        peripheral = name,
        items = items
    })
end

-- Send JSON data to the Flask server
if http then
    local res = http.post(server_url, textutils.serializeJSON(inventories), {
        ["Content-Type"] = "application/json"
    })

    if res then
        print("Server responded: " .. res.readAll())
        res.close()
    else
        print("Failed to send data to server.")
    end
else
    print("HTTP API is disabled.")
end
