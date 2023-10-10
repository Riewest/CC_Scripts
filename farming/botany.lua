local completion = require "cc.completion"

local STARTUP_PATH = "startup.lua"
local NO_INPUT_ARG = "NO INPUT"
local NO_OUTPUT_ARG = "NO OUTPUT"
local BOTANY_POT_PATTERN = "botany_pot"
local INPUT_Y = 4
local OUTPUT_Y = 5
local MAINTAINED_POTS_Y = 6
local EMPTY_POT_Y = 7
local TENDING_Y = 10
local CROP_Y = 11
local SOIL_Y = 12
local CROP_COUNT_Y = 14
local INFO_Y = 18
local STARTUP_SCRIPT_CHOICE_X = 33
local SEED_SLOT = 2
local SOIL_SLOT = 1
local MINUTE = 60
local LOOP_TIME = 10

local args = {...}
local input_inv_name = args[1] or NO_INPUT_ARG
local output_inv_name = args[2] or NO_OUTPUT_ARG
local sleep_time = 0

local SOIL_NAME_PATTERNS = {
    "farmland",
    "dirt",
    "soil"
}

function selectIO()
    local potentialIO = getNonPots()
    write("  Input Inv:")
    while input_inv_name == NO_INPUT_ARG or input_inv_name == "" or string.lower(input_inv_name) == "r"do
        term.setCursorPos(14,INPUT_Y)
        input_inv_name = read(nil, potentialIO, function(text) return completion.choice(text, potentialIO) end)
    end
        reprintLine(INPUT_Y,"  Input Inv: "..input_inv_name)
    for i=1, #potentialIO do
        if potentialIO[i] == input_inv_name then
            table.remove(potentialIO,i)
            break
        end
    end
    write(" Output Inv:")
    while output_inv_name == NO_OUTPUT_ARG or output_inv_name == "" do
        term.setCursorPos(14,OUTPUT_Y)
        output_inv_name = read(nil, potentialIO, function(text) return completion.choice(text, potentialIO) end)
    end
        reprintLine(OUTPUT_Y," Output Inv: "..output_inv_name)
    createStartup(input_inv_name, output_inv_name)
end

function createStartup(...)
    local options = {"yes", "no"}
    local choice = ""
    local x,y = term.getCursorPos()
    term.setCursorPos(1,INFO_Y)
    write("Create Startup Script? (yes/no) ")
    while choice == "" do 
        term.setCursorPos(STARTUP_SCRIPT_CHOICE_X,INFO_Y)
        choice = read(nil, options, function(text) return completion.choice(text, options) end, nil)
    end
        if string.lower(choice) == "yes" then
        reprintLine(INFO_Y,"Creating Startup...")
        local startup_file = fs.open("startup.lua", "w")
        local script_path = shell.getRunningProgram()
        local startup_args = table.concat(arg, "\",\"")
        startup_file.write("shell.run(\""..script_path.."\",\""..startup_args.."\")")
        startup_file.close()
        reprintLine(INFO_Y,"Startup Script Created.")
    else
        reprintLine(INFO_Y,"Startup Script Skipped.")
    end
    term.setCursorPos(x,y)
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
    return to_inv.pullItems(peripheral.getName(from_inv), from_slot)
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
            return slot
        end
    end
    return nil
end

function find_seed(input_inv)
    local inputs = input_inv.list()
    for slot, item in pairs(inputs) do
        if not is_soil(item.name) then
            return slot
        end
    end
    return nil
end

function process_empty_pot(pot)
    if input_inv_name == NO_INPUT then return end
    local input_inv = peripheral.wrap(input_inv_name)
    local seed_slot = find_seed(input_inv)
    local soil_slot = find_soil(input_inv)
    if not seed_slot or not soil_slot then
        return false
    end
    if not pot.getItemDetail(SEED_SLOT) then
        if 0 == pot.pullItems(peripheral.getName(input_inv), seed_slot, 1, SEED_SLOT) then
            return false
        end
    end
    if not pot.getItemDetail(SOIL_SLOT) then
        if 0 == pot.pullItems(peripheral.getName(input_inv), soil_slot, 1, SOIL_SLOT) then
            return false
        end
    end
    return true
end

function process_pot(pot)
    local contents = pot.list()
    contents[SEED_SLOT] = nil
    contents[SOIL_SLOT] = nil
    local crop_count = 0
    local output_inv = peripheral.wrap(output_inv_name)
    local crop = pot.getItemDetail(SEED_SLOT)
    local soil = pot.getItemDetail(SOIL_SLOT)
    local has_seed = false 
    local crop_name = "empty"
    local soil_name = "empty"
    if crop then 
        has_seed = true
        crop_name = removeModName(crop.name)
        soil_name = removeModName(soil.name)
    end
    for from_slot,v in pairs(contents) do
        local _,count = pcall(process_slot, output_inv, pot, from_slot)
        crop_count = crop_count + count
    end
    return has_seed,crop_name,soil_name,crop_count
end

function removeModName(full_name)
    local i,b = string.find(full_name,":")
    return string.sub(full_name,i+1,string.len(full_name))
end

function process_pots(botany_pots,sleep_time)
    local empty_pot_count = 0
    local cycle_crop_count = 0
    for _, pot in pairs(botany_pots) do
        local pot_name = peripheral.getName(pot)
        local successful_process, crop_name, soil_name, pot_crop_count = process_pot(pot)
        cycle_crop_count = cycle_crop_count + pot_crop_count
        reprintLine(TENDING_Y," Tending To: "..string.sub(pot_name,19,string.len(pot_name)))
        if not successful_process then
            if not process_empty_pot(pot) then 
                empty_pot_count = empty_pot_count + 1
            end
        end
        reprintLine(CROP_Y,"       Crop: "..crop_name)
        reprintLine(SOIL_Y,"       Soil: "..soil_name)
        sleep(sleep_time)
    end
    return empty_pot_count,cycle_crop_count
end

function arrayContains(array, v)
    for i = 1, #array do
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
    if perPot < .2 then 
        return .2
    else 
        if perPot > 15 then 
            return 15 
        end
        return perPot
    end
end

function findCPM(crop_count,total_pot_count)
    return crop_count / (total_pot_count * sleep_time / MINUTE)
end

--ADD MONITOR OUTPUTS
--Tending too add seed and trim
-- handle add and remove pots with events 

function main()
    term.clear()
    term.setCursorPos(1,1)
    local botany_pots = {peripheral.find("botanypots:botany_pot")}
    local total_pot_count = #botany_pots
    sleep_time = math.floor(getPerPotSleepTime(total_pot_count))
    print("\"Mars will come to fear my botany powers\"")
    print("    - Mark Watney")
    print("")
    if not fs.exists(STARTUP_PATH) or input_inv_name == NO_INPUT_ARG then 
        selectIO() 
    else
        reprintLine(INPUT_Y,"  Input Inv: "..input_inv_name)
        reprintLine(OUTPUT_Y," Output Inv: "..output_inv_name)
    end
    print("Maintaining:","?","pots")
    print("      Empty:","?","pots")
    print("  Tend Time:",sleep_time,"seconds")
    while true do
        --rework this first line
        reprintLine(MAINTAINED_POTS_Y,"Maintaining: "..#botany_pots.." pots")
        local empty_pot_count,cycle_crop_count = process_pots(botany_pots,sleep_time)
        reprintLine(EMPTY_POT_Y,"      Empty: "..empty_pot_count.." pots")
        reprintLine(CROP_COUNT_Y,"        C/M: "..math.floor(findCPM(cycle_crop_count,total_pot_count)))
    end
end

main()