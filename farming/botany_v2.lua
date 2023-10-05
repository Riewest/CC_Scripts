local args = {...}
local NO_INPUT_ARG = "NO INPUT"
local NO_OUTPUT_ARG = "NO OUTPUT"
local BOTANY_POT_PATTERN = "botany_pot"
local INPUT_INV_NAME = args[1] or NO_INPUT_ARG
local OUTPUT_INV_NAME = args[2] or NO_OUTPUT_ARG
local INPUT_Y = 4
local OUTPUT_Y = 5
local MAINTAINED_POTS_Y = 6
local EMPTY_POT_Y = 7
local HARVESTING_Y = 8
local ACTIVITY_Y = 10


local SEED_SLOT = 2
local SOIL_SLOT = 1
local MINUTE = 60
local LOOP_TIME = 10
local sleep_time = 0

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

local VALID_KEY_NAMES = {
    "up",
    "down",
    "enter",
    "r"
}

function selectIO(args_input,args_output)
    local function iCheck(i,array_len)
        if i < 1 then
            return 1
        else
            if i > array_len then
                return array_len
            else 
                return i
            end
        end
    end

    if args_input == NO_INPUT_ARG then
        local i = 1
        local input_selected = false
        local potentialIO = getNonPots()
        print("  Input Inv:", potentialIO[i])
        while not input_selected do
            local key = wait_for_IO_select()
            --print("Pressed Key: ",key)
            if key == "down" then
                i=i+1
                i = iCheck(i,#potentialIO)
            else
                if key == "up" then
                    i=i-1
                    i = iCheck(i,#potentialIO)
                else
                    if key == "enter" then
                        INPUT_INV_NAME = potentialIO[i]
                        input_selected = true
                    else
                        if key == "r" then
                            potentialIO = getNonPots()
                            i=1
                        else
                            print("invalid key")
                        end
                    end
                end
            end
            reprintLine(INPUT_Y,"  Input Inv: "..potentialIO[i])
        end
    else

    end

    if args_output == NO_OUTPUT_ARG then
        local i = 1
        local output_selected = false
        local potentialIO = getNonPots()
        print(" Output Inv:", potentialIO[i])
        while not output_selected do
            local key = wait_for_IO_select()
            --print("Pressed Key: ",key)
            if key == "down" then
                i=i+1
                i = iCheck(i,#potentialIO)
            else
                if key == "up" then
                    i=i-1
                    i = iCheck(i,#potentialIO)
                else
                    if key == "enter" then
                        OUTPUT_INV_NAME = potentialIO[i]
                        output_selected = true
                    else
                        if key == "r" then
                            potentialIO = getNonPots()
                            i=1
                        else
                            print("invalid key")
                        end
                    end
                end
            end
            reprintLine(OUTPUT_Y," Output Inv: "..potentialIO[i])
        end
    else

    end
end

function getNonPots()
    local potentialIO = {}
    peripheral.find("inventory", function(name, modem)
        if not string.find(name, BOTANY_POT_PATTERN) then
            table.insert(potentialIO, name)
        end
    end)
    return potentialIO
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
        pcall(process_slot, OUTPUT_INV_NAME, pot, from_slot)
    end
    return has_seed
end

function process_pots(botany_pots,sleep_time)
    
    local empty_pots = {}
    for _, pot in pairs(botany_pots) do
        if not process_pot(pot) then
            table.insert(empty_pots, pot)
        end
    end
    return process_inputs(empty_pots)
end

function wait_for_IO_select()
    local _, key
    repeat
        _, key = os.pullEvent("key")
    until arrayContains(VALID_KEY_NAMES, keys.getName(key))
    --print(keys.getName(key))
    return keys.getName(key)
end

function arrayContains(array, v)
    --print(v)
    for i = 1, #array do
        --print(array[i])
        if array[i] == v then
            return true
        end
    end
    return false
end

function reprintLine(line,string)
    term.setCursorPos(1,line)
    term.clearLine()
    print(string)
end

function getPerPotSleepTime(potCount)
    local loop_seconds = LOOP_TIME * MINUTE
    local perPot = loop_seconds / potCount
    if perPot < .25 then 
        return .25
    else
        return perPot
    end
end

--ADD EVENT LOOKING FOR BUTTON PRESS TO FORCE START
--add list of valid outputs (add backpack) 
--autocycle through all the pots (10 min divide by pot number or something)


function main()
    term.clear()
    term.setCursorPos(1,1)
    print("\"Mars will come to fear my botany powers\"")
    print("    - Mark Watney")
    print("")
    selectIO(INPUT_INV_NAME,OUTPUT_INV_NAME)
    print("Maintaining:","?","pots")
    print("      Empty:","?","pots")
    print("  Loop Time:",LOOP_TIME,"minutes")
    while true do
        local botany_pots = {peripheral.find("botanypots:botany_pot")}
        reprintLine(MAINTAINED_POTS_Y,"Maintaining: "..#botany_pots.." pots")
        sleep_time = getPerPotSleepTime(#botany_pots)
        local empty_pot_count = process_pots(botany_pots,sleep_time)
        reprintLine(EMPTY_POT_Y,"    Empty: "..empty_pot_count.." pots")
    end
end

main()