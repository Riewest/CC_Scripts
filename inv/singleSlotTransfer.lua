local args = {...}
local slot_num = tonumber(args[1]) or 1
local from_inv_name = args[2] or "left"
local to_inv_name = args[3] or "right"
print(slot_num, from_inv_name, "->", to_inv_name)

function help()
    print("USAGE: transfer [slotNum] [fromSide] [toSide]")
    print(" -slotNum defaults to 1")
    print(" -fromSide defaults to left")
    print(" -toSide defaults to right")
    print("")
    print("If you want to specify toSide")
    print("then you must give slotNum,fromSide")
    print("   Accepts valid computer sides")
end

function invError(message)
    print("")
    print("Error!")
    shell.run("peripherals")
    print("")
    error(message)
end

function preCheck()
    if not peripheral.isPresent(from_inv_name) then
        invError(from_inv_name .. " Inventory Not Found!")
    end
    if not peripheral.isPresent(to_inv_name) then
        invError(to_inv_name .. " Inventory Not Found!")
    end
end

function main()
    preCheck()
    local from_inv = peripheral.wrap(from_inv_name)
    local to_inv = peripheral.wrap(to_inv_name)
    local from_size = from_inv.size()
    local to_size = to_inv.size()
    while true do
        local item = from_inv.getItemDetail(slot_num)
        if item and item.count > 0 then
            to_inv.pullItems(peripheral.getName(from_inv), slot_num)
        end
    end
end

if string.find(string.lower(from_inv_name), "help") then
    help()
else
    main()
end
