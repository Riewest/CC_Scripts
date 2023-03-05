local SETTINGS_FILE = "furnace.settings"

local SLOTS = {}
SLOTS.input = 1
SLOTS.fuel = 2
SLOTS.output = 3

local FUELS = {}
FUELS["minecraft:planks"] = {
    burnTime = 1.5,
    minStack = 2
}
FUELS["forge:rods/wooden"] = {
    burnTime = 0.5,
    minStack = 2
}
FUELS["minecraft:saplings"] = {
    burnTime = 0.5,
    minStack = 2
}
FUELS["minecraft:coals"] = {
    burnTime = 8,
    minStack = 1,
    namespace = "minecraft:"
}
FUELS["forge:coal_coke"] = {
    burnTime = 16,
    minStack = 1,
}

local INV_INFO = {}
INV_INFO.input = {
    type = " INPUT",
    display_line = 3,
    setting = "furnace_input_inv",
    wrapped = nil
}
INV_INFO.output = {
    type = "OUTPUT",
    display_line = 4,
    setting = "furnace_output_inv",
    wrapped = nil
}
INV_INFO.fuel = {
    type = "  FUEL",
    display_line = 5,
    setting = "furnace_fuel_inv",
    wrapped = nil
}

local FCDL = 7 --furnace count display line
local CODL = 9 --Current Operation display_line

local inventories = {}
local furnaces = {}

local FURNACE = "furnace"
local INVENTORY = "inventory"

function congfigureInventory(inv_in)
    --print(inv_in.type,inv_in.setting,inv_in.wrapped)
    checkInventoryList()
    local inv_name = settings.get(inv_in.setting)
    if (inv_name and peripheral.isPresent(inv_name) and not alreadyUsedInv(inv_name)) then --setting exists and peripheral is present
        printOnLine(inv_in.type..": "..inv_name,inv_in.display_line)
    else -- setting does not exist or peripheral is missing
        inv_name = findNewInventory(inv_in)
        settings.set(inv_in.setting, inv_name)
    end
    inventories[#inventories + 1] = inv_name
    inv_in.name = inv_name
    inv_in.wrapped = peripheral.wrap(inv_name)
    settings.save(SETTINGS_FILE)
end

function findNewInventory(inv_in) --make generic function that takes in filter param?
    local new_inv = nil
    printOnLine(inv_in.type.. ": Please connect an inventory...",inv_in.display_line)
    while not new_inv do
        local _, per_name = os.pullEvent("peripheral")
        if peripheral.hasType(per_name, INVENTORY) and not string.match(per_name, FURNACE) and not alreadyUsedInv(per_name) then
            new_inv = per_name
        end
    end
    printOnLine(inv_in.type .. ": "..new_inv,inv_in.display_line)
    return new_inv
end

function printOnLine(message,line)
    cPosX,cPosY = term.getCursorPos()
    term.setCursorPos(1,line)
    term.clearLine()
    print(message)
    term.setCursorPos(cPosX,cPosY)
end

function checkInventoryList()
    for k,v in pairs(inventories) do
        if not peripheral.isPresent(v) then
            table.remove(inventories,k)
        end
    end
end

function findFurnaces()
    printOnLine("Looking For Furnaces...",FCDL)
    while #furnaces < 1 do
        furnaces = { peripheral.find(INVENTORY, function(n, p)
            return string.match(n, FURNACE)
        end) }
        if #furnaces > 0 then
            printOnLine("FURNACE(S): "..#furnaces,FCDL)
            return furnaces
        end
        printOnLine("Please connect a furnace...",FCDL)
        sleep(2)
    end
end

function alreadyUsedInv(potential_inv)
    for _, v in pairs(inventories) do
        if v == potential_inv then
            return true
        end
    end
end

function findNextFuel()
    for slot, item in pairs(INV_INFO.fuel.wrapped.list()) do
        local fuel_data = slotHasFuelTag(INV_INFO.fuel.wrapped, slot)
        --print(fuel_data,tag)
        if (fuel_data and fuel_data.minStack <= item.count) and ((fuel_data.namespace and string.match(item.name, fuel_data.namespace)) or not fuel_data.namespace) then
            return slot, fuel_data
        end
    end
end

function slotHasFuelTag(inv, slot)
    local itemDetail = inv.getItemDetail(slot)
    for tag, _ in pairs(itemDetail.tags) do
        local fuel_data = FUELS[tag]
        if fuel_data then
            return fuel_data
        end
    end
end

function moveItem(fromInv, fromSlot, toInv, toSlot, count)
    fromInv.pushItems(peripheral.getName(toInv), fromSlot, count, toSlot)
end

function fuelFurnaces()
    printOnLine("Fueling Furnaces",CODL)
    if INV_INFO.fuel.wrapped and peripheral.isPresent(peripheral.getName(INV_INFO.fuel.wrapped)) then
        for _, furnace in pairs(furnaces) do
            if not slotHasItem(furnace, SLOTS.fuel) then
                local slot, fuel_data = findNextFuel()
                --print(slot, fuel_data)
                if slot and fuel_data then
                    moveItem(INV_INFO.fuel.wrapped, slot, furnace, SLOTS.fuel, fuel_data.minStack)
                end
            end
        end
    else
        congfigureInventory(INV_INFO.fuel)
    end
end

function slotHasItem(furnace, slot)
    return furnace.getItemDetail(slot)
end

function processInputs()
    printOnLine("Processing Inputs",CODL)
    if INV_INFO.input.wrapped and peripheral.isPresent(peripheral.getName(INV_INFO.input.wrapped)) then --
        local inputs = INV_INFO.input.wrapped.list()
        if inputs then
            for _, furnace in pairs(furnaces) do
                for slot, item in pairs(inputs) do
                    if not slotHasItem(furnace, SLOTS.input) and slotHasItem(furnace, SLOTS.fuel) then
                        local fuel_data = slotHasFuelTag(furnace, SLOTS.fuel)
                        local item_count = fuel_data.minStack * fuel_data.burnTime
                        if item.count >= item_count then
                            moveItem(INV_INFO.input.wrapped, slot, furnace, SLOTS.input, item_count)
                            break
                        end
                    end
                end
            end
        end
    else
        congfigureInventory(INV_INFO.input)
    end
end

function processOutputs()
    printOnLine("Processing Outputs",CODL)
    if INV_INFO.output.wrapped and peripheral.isPresent(peripheral.getName(INV_INFO.output.wrapped)) then
        for _, furnace in pairs(furnaces) do
            if slotHasItem(furnace, SLOTS.output) then
                moveItem(furnace, SLOTS.output, INV_INFO.output.wrapped, nil, nil)
            end
        end
    else
        congfigureInventory(INV_INFO.output)
    end
end

function startup()
    settings.load(SETTINGS_FILE)
    term.clear()
    term.setCursorPos(1, 1)
    print("         ***   Furnace Handler 9000   ***         ") -- make this a fancy print? . .. ...
    print("")
    sleep(.5)
    congfigureInventory(INV_INFO.input)
    congfigureInventory(INV_INFO.output)
    congfigureInventory(INV_INFO.fuel)
    furnaces = findFurnaces()
end

function main()
    startup()
    while true do
        processOutputs()
        fuelFurnaces()
        processInputs()
        sleep(0)
    end
end

function errorHandler(err)
    print("Error:", err)
    print("Rebooting in 5 seconds")
    sleep(5)
    os.reboot()
end

main()
-- xpcall(main, errorHandler)
