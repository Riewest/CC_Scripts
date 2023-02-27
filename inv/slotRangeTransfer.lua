local args = {...}
local start_slot = tonumber(args[1]) or 1
local end_slot = tonumber(args[2]) or 1
local from_inv_name = args[3] or "left"
local to_inv_name = args[4] or "right"

local START_DELAY = 4

print(start_slot, "->", end_slot, "in", from_inv_name, "->", to_inv_name)

function invError(message)
    print("")
    print("Error!")
    shell.run("peripherals")
    print("")
    error(message)
end

function preCheck()
    if end_slot < start_slot then
        error("End Slot (" .. tostring(end_slot) .. ") is less than Start Slot (" .. tostring(start_slot) .. ")")
    end
    if not peripheral.isPresent(from_inv_name) then
        invError(from_inv_name .. " Inventory Not Found!")
    end
    if not peripheral.isPresent(to_inv_name) then
        invError(to_inv_name .. " Inventory Not Found!")
    end
end

function process_slot(to_inv, from_inv, from_slot)
    to_inv.pullItems(peripheral.getName(from_inv), from_slot)
end

function process_invs()
    local from_inv = peripheral.wrap(from_inv_name)
    local to_inv = peripheral.wrap(to_inv_name)
    for from_slot=start_slot, end_slot do
        local item = from_inv.getItemDetail(from_slot)
        if item and item.count > 0 then
            pcall(process_slot, to_inv, from_inv, from_slot)
        end
    end
end

function main()
    preCheck()
    print("Startup Delay", START_DELAY)
    sleep(START_DELAY)  --Allows control t to kill program on startup
    print("Continuing")
    while true do
        pcall(process_invs)
    end
end

main()
