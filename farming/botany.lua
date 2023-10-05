local args = {...}
local NO_INPUT = "XXXXXXXXXXXX"
local INPUT_INV_NAME = args[1] or NO_INPUT
local OUTPUT_INV = nil

local SEED_SLOT = 2
local SOIL_SLOT = 1
local MINUTE = 60
local SLEEP_TIME = 2 * MINUTE 

local VALID_OUTPUTS = {
    "chest",
    "barrel",
    "interface",
    "backpack"
}

local SOIL_NAME_PATTERNS = {
    "farmland",
    "dirt",
    "soil"
}

function find_output()
    local possible_outputs = { peripheral.find("inventory", function(name, p)
        return (string.find(name, "chest") or string.find(name, "barrel") or string.find(name, "interface") or string.find(name, "backpack")) and not string.find(name, INPUT_INV_NAME)
    end) }
    local first_output = possible_outputs[1]
    if not first_output then
        error("Unable to find a valid output inventory")
    end
    OUTPUT_INV = first_output
end

function process_slot(to_inv, from_inv, from_slot)
    to_inv.pullItems(peripheral.getName(from_inv), from_slot)
end

function is_soil(item_name)
    local soil_check = false
    for _, pattern in pairs(SOIL_NAME_PATTERNS) do
        soil_check = string.find(item_name, pattern)
        if soil_check then break end
    end
    return soil_check
end

function find_soil(input_inv)
    local inputs = input_inv.list()
    for slot, item in pairs(inputs) do
        if is_soil(item.name) then
            return slot, item.count
        end
    end
end

function find_seed(input_inv)
    local inputs = input_inv.list()
    for slot, item in pairs(inputs) do
        if not is_soil(item.name) then
            return slot, item.count
        end
    end
end

function process_inputs(empty_pots)
    if INPUT_INV_NAME == NO_INPUT then return end
    local input_inv = peripheral.wrap(INPUT_INV_NAME)
    local seed_slot, seed_count = find_seed(input_inv)
    local soil_slot, soil_count = find_soil(input_inv)
    local empty_pot_count = #empty_pots
    for _, pot in pairs(empty_pots) do
        if not seed_count or not soil_count then
            break
        end
        if not pot.getItemDetail(SEED_SLOT) then
            pot.pullItems(peripheral.getName(input_inv), seed_slot, 1, SEED_SLOT)
            seed_count = seed_count - 1
            empty_pot_count = empty_pot_count - 1
        end
        if not pot.getItemDetail(SOIL_SLOT) then
            pot.pullItems(peripheral.getName(input_inv), soil_slot, 1, SOIL_SLOT)
            soil_count = soil_count - 1
        end
        if seed_count <= 0 then
            seed_slot, seed_count = find_seed(input_inv)
        end
        if soil_count <= 0 then
            soil_slot, soil_count = find_soil(input_inv)
        end
    end
    return empty_pot_count
end

function process_pot(pot)
    local contents = pot.list()
    contents[SEED_SLOT] = nil
    contents[SOIL_SLOT] = nil
    local seed = pot.getItemDetail(SEED_SLOT)
    local has_seed = false 
    if seed then has_seed = true end
    for from_slot,v in pairs(contents) do
        pcall(process_slot, OUTPUT_INV, pot, from_slot)
    end
    return has_seed
end

function process_pots(botany_pots)
    
    local empty_pots = {}
    for _, pot in pairs(botany_pots) do
        if not process_pot(pot) then
            table.insert(empty_pots, pot)
        end
    end
    return process_inputs(empty_pots)
end

--ADD EVENT LOOKING FOR BUTTON PRESS TO FORCE START
--add list of valid outputs (add backpack) 
--autocycle through all the pots (10 min divide by pot number or something)



function main()
    find_output()
    local botany_pots = {peripheral.find("botanypots:botany_pot")}
    term.clear()
    term.setCursorPos(1,1)
    print("\"Mars will come to fear my botany powers\"")
    print("    - Mark Watney")
    print("")
    print("Input Inv:", INPUT_INV_NAME)
    print("Output Inv:", peripheral.getName(OUTPUT_INV))
    print("Maintaining:",#botany_pots,"pots.")
    print("Empty Pots:","?")
    print("Seconds Between:", SLEEP_TIME)
    while true do
        local empty_pot_count = process_pots(botany_pots)
        term.setCursorPos(1,7)
        term.clearLine()
        print("Empty Pots:",empty_pot_count)
        sleep(SLEEP_TIME)
    end
end

main()