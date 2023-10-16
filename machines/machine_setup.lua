local completion = require "cc.completion"

local WELCOME_MESSAGE = "Welcome to Machine Setup..."
local PROMPT_MESSAGE = "Please follow the prompts..."
local MACHINE_SELECT_MESSAGE = "What machine would you like to setup a schema for?"
local STARTUP_PATH = "startup.lua"
local machineBeingSetupName = ""
local wrappedMachine
local machineSlotsSetup = {}
local LINE_ONE = 1
local LINE_TWO = 2

local slot_types = {
    "input",
    "output",
    "ignore"
}

local args = {...}
local input_inv_name = args[1] or NO_INPUT_ARG
local output_inv_name = args[2] or NO_OUTPUT_ARG
local sleep_time = 0

--assume empty slots are outputs?

function selectMachine()
    local potentialMachines = getAllInventories()
    if #potentialMachines < 1 then
        print("No peripherals connected. Please connect a machine and try again.")
        exit()
    end
    clearLineAndSlowWrite(LINE_ONE,MACHINE_SELECT_MESSAGE)
    sleep(1)
    clearLineAndSlowWrite(LINE_TWO,"Machine: ")
    return getUserChoiceFromTable(potentialMachines)
end

function setupMachineSlots(machine)
    local slot_data = {}
    local x,y = term.getCursorPos()

    for slot_number=1,machine.size() do
        local slot_type = ""
        local filter_string = ""
        --clearLines(y,y+5)
        term.setCursorPos(x,y)
        local item_data = machine.getItemDetail(slot_number)
        if item_data then
            print("Slot #: "..slot_number..", Containing: "..item_data.displayName)
            write("Slot Type: ")
            slot_type = getUserChoiceFromTable(slot_types,true)
            --print("DEBUG: "..slot_type)
            if slot_type == "input" then
                write("Filter string: ")
                filter_string = getUserChoiceFromTable({item_data.name})
            else
                write("Not Filtering: "..slot_number)
            end
        end
        table.insert(slot_data,slot_number,{slot_type = slot_type,filter_string = filter_string})
    end
    return slot_data
end

function getUserChoiceFromTable(table,match_table)
    local x,y = term.getCursorPos()
    local choice = ""
    if match_table then
        while not tableContains(table,choice) do
            term.setCursorPos(x,y)
            choice = read(nil, table, function(text) return completion.choice(text, table) end)
        end
    else
        while choice == "" do
            term.setCursorPos(x,y)
            choice = read(nil, table, function(text) return completion.choice(text, table) end)
        end
    end
    return choice
end

function tableContains(table, check_value)
    for _,value in pairs(table) do
        if value == check_value then 
            return true
        end
    end
    return false
end

function nextLine()
    print()
end

function clearLines(a,b)
    if a > b then
        for i=b,a do
            clearLine(i)
        end
    else
        for i=a,b do
            clearLine(i)
        end
    end
end

function clearLine(line)
    term.setCursorPos(1,line)
    term.clearLine()
end

function clearLineAndSlowWrite(line,string)
    term.setCursorPos(1,line)
    term.clearLine()
    write(string)
end

-- function getNonMachineInventories()
--     local potentialIO = {}
--     peripheral.find("inventory", function(name, modem)
--         if not string.find(name, BOTANY_POT_PATTERN) then
--             table.insert(potentialIO, name)
--         end
--     end)
--     return potentialIO
-- end

function getAllInventories()
    local allInventtories = {}
    peripheral.find("inventory", function(name, modem)
        table.insert(allInventtories, name)end)
    return allInventtories
end

function welcome()
    term.setCursorBlink(true)
    term.clear()
    clearLineAndSlowWrite(LINE_ONE,WELCOME_MESSAGE)
    sleep(1)
end

function main()
    welcome()
    machineBeingSetupName = selectMachine()
    -- print("DEBUG: "..machineBeingSetupName)
    wrappedMachine = peripheral.wrap(machineBeingSetupName)
    machineSlotsSetup = setupMachineSlots(wrappedMachine)

    for slot,slot_data in pairs(machineSlotsSetup) do
        print("Slot: "..slot)
        print(slot_data["slot_type"])
        print(slot_data["filter_string"])
    end
end

main()