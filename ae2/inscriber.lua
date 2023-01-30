MOD_ID = "ae2"
-- TEST

local SLOTS = {}
SLOTS.top = 1
SLOTS.bottom = 2
SLOTS.middle = 3
SLOTS.output = 4

local PRESSES = {}
PRESSES.logic = MOD_ID .. ":logic_processor_press"
PRESSES.engineering = MOD_ID .. ":engineering_processor_press"
PRESSES.calculation = MOD_ID .. ":calculation_processor_press"
PRESSES.silicon = MOD_ID .. ":silicon_press"
local COMBINATION = "combine"

local MIDDLE_INPUTS = {}
MIDDLE_INPUTS.logic = "minecraft:gold_ingot"
MIDDLE_INPUTS.engineering = "minecraft:diamond"
MIDDLE_INPUTS.calculation = MOD_ID .. ":certus_quartz_crystal"
MIDDLE_INPUTS.silicon = "ae2:silicon" --MAKE THIS MORE ROBUST FOR SILICON TYPES
MIDDLE_INPUTS.combine = "minecraft:redstone"

local CIRCUITS = {}
CIRCUITS.logic = MOD_ID .. ":printed_logic_processor"
CIRCUITS.engineering = MOD_ID .. ":printed_engineering_processor"
CIRCUITS.calculation = MOD_ID .. ":printed_calculation_processor"

local SILICON = MOD_ID .. ":printed_silicon"

local inventory = nil
local inscribers = {}

function hasMethod(p, method)
    local methods = peripheral.getMethods(p)
    for k,v in pairs(methods) do
        if v == method then
            return true
        end
    end
    return false
end

function hasItem(item, i)
    local slots = peripheral.call(i, "list")
    for num, itemInfo in pairs(slots) do
        if item == itemInfo.name then
            return num
        end
    end
    return false
end

function determineInscriber(inscriber)
    for k, v in pairs(PRESSES) do
        local slot = hasItem(v, inscriber)
        if slot then
            return k, slot
        end
    end
    return COMBINATION, false
end

function findInscribers()
    local inscribers = {}
    print("Looking For Inscribers...")
    for _, v in pairs( peripheral.getNames() ) do
          if string.find(v, "inscriber") then
            local t, press_slot = determineInscriber(v)
            local inscriber = {}
            inscriber.name = v
            inscriber.type =  t
            inscriber.press_slot = press_slot
            inscribers[t] = inscriber
            print("Found Inscriber!") 
            print("Name:", inscriber.name, "Type:", inscriber.type, "Slot:", inscriber.press_slot)
          end
    end
    return inscribers
end

function findInventory()
    print("Looking For Inventory...")
    for _, v in pairs( peripheral.getNames() ) do
        if hasMethod(v, "size") and peripheral.call(v, "size") > 10 then
            print("Found Inventory!")
            return v
        end
    end
    print("No Inventory Found!")
end

function moveItem(fromInv, fromSlot, toInv, toSlot )
    local inv = peripheral.wrap(fromInv)
    inv.pushItems(toInv, fromSlot, nil, toSlot)
end


function genericPress(inscriber)
    local item = MIDDLE_INPUTS[inscriber.type]
    local i_slot = hasItem(item, inventory)
    if i_slot then
        moveItem(inventory, i_slot, inscriber.name, SLOTS.middle)
    end
end

function processSilicon()
    if inscribers[COMBINATION] then
        local i_slot = hasItem(SILICON, inventory)
        if i_slot then
            moveItem(inventory, i_slot, inscribers[COMBINATION].name, SLOTS.bottom)
        elseif inscribers.silicon then
                moveItem(inscribers.silicon.name, SLOTS.output, inscribers[COMBINATION].name, SLOTS.bottom)
        end
    end
end

function processInputs()
    for k, inscriber in pairs(inscribers) do
        genericPress(inscriber)
        if inscribers[COMBINATION] then
            if k ~= COMBINATION then
                if k ~= "silicon" then
                    moveItem(inscriber.name, SLOTS.output, inscribers[COMBINATION].name, SLOTS.top)
                end
            end
        else
            moveItem(inscriber.name, SLOTS.output, inventory)
        end
    end
end

function processOutput()
    if inscribers[COMBINATION] then
        moveItem(inscribers[COMBINATION].name, SLOTS.output, inventory)
    end
end

function processExtras()
    if inscribers[COMBINATION] then
        for k, v in pairs(CIRCUITS) do
            local i_slot = hasItem(v, inventory)
            if i_slot then
                moveItem(inventory, i_slot, inscribers[COMBINATION].name, SLOTS.top)
            end
        end
    end
end

function startup()
    print("Initializing...")
    inscribers = findInscribers()
    inventory = findInventory()
end


function main()
    startup()
    while true do
        processExtras()
        processOutput()
        processSilicon()
        processInputs()
        sleep(.1)
    end
end

function errorHandler(err)
    print("Error:", err)
    print("Rebooting in 5 seconds")
    sleep(5)
    os.reboot()
end


xpcall(main, errorHandler)