local expect = require "cc.expect"
local completion = require "cc.completion"
local expect, field, range = expect.expect, expect.field, expect.range

local schema_created = false
local machine_schema = {
    INPUT_SLOT = nil,
    INPUT_MIN_STACK = nil,
    INPUT_FILTER_FUNC = nil,
    OUTPUT_SLOTS = nil,
    EXTRA_SLOT = nil,
    EXTRA_MIN_STACK = nil,
    EXTRA_FILTER_FUNC = nil,
    ID_STR = nil, -- Used for doing "string.match" on the peripheral names when finding machines
    PERIPHERAL_TYPE = "inventory", -- Used as first parameter in "peripheral.find"
    PROCESS_TIME = 1 -- Sleep time after processing a machine
}

local machines = {}
local potentialIO = {}
local output_inv = nil
local input_inv = nil
local extra_input_inv = nil

local current_extra_stack = nil
local current_input_stack = nil

local parallel_var = nil

local function reprintLine(line,...)
    local x,y = term.getCursorPos()
    local print_string = table.concat(arg, " ")
    term.setCursorPos(1,line)
    term.clearLine()
    print(print_string)
    term.setCursorPos(x,y)
end

local function print_static_program_info()
    term.clear()
    reprintLine(1, "Program Info:")
    reprintLine(2, "  Machine Type:", machine_schema.ID_STR)
    reprintLine(3, "  Count:       ", #machines )
    reprintLine(5, "  Input Inv:   ", peripheral.getName(input_inv))
    reprintLine(6, "  Output Inv:  ", peripheral.getName(output_inv))
    reprintLine(7, "  Extra Inv:   ", peripheral.getName(extra_input_inv))

end

local function print_dynamic_program_info()
    
end

local function print_current_machine_info(machine)
    local machine_name = peripheral.getName(machine)
    --reprintLine(7,machine_name)
    reprintLine(9," Tending To:    "..string.sub(machine_name,17,string.len(machine_name)))
end


local function check_valid_schema()
    if not schema_created then
        error("No Schema Created!\nBe Sure to call: create_machine_schema(...)")
    end
    expect("INPUT_SLOT", machine_schema.INPUT_SLOT, "number")
    expect("OUTPUT_SLOTS", machine_schema.OUTPUT_SLOTS, "table")
    expect("EXTRA_SLOT", machine_schema.EXTRA_SLOT, "number", "nil")
    expect("ID_STR", machine_schema.ID_STR, "string")
    expect("PERIPHERAL_TYPE", machine_schema.PERIPHERAL_TYPE, "string", "nil")
    expect("PROCESS_TIME", machine_schema.PROCESS_TIME, "number")
    print("Valid Machine Schema")
end

local function create_machine_schema(outputSlots, id_string, peripheral_type)
    expect(1, outputSlots, "number", "table")
    expect(3, id_string, "string")
    expect(4, peripheral_type, "string", "nil")
    if type(outputSlots) == "number" then
        range(outputSlots, 1, 1000)
        outputSlots = {outputSlots}
    end
    machine_schema.OUTPUT_SLOTS = outputSlots
    machine_schema.ID_STR = id_string
    machine_schema.PERIPHERAL_TYPE = peripheral_type or machine_schema.PERIPHERAL_TYPE
    schema_created = true
end

local function create_input_item_schema(slot, minStack, filter_func)
    expect(1, slot, "number")
    expect(2, minStack, "number", "nil")
    expect(3, filter_func, "function", "nil")
    range(slot, 1, 1000)
    machine_schema.INPUT_SLOT = slot
    machine_schema.INPUT_MIN_STACK = minStack
    machine_schema.INPUT_FILTER_FUNC = filter_func
end

local function create_extra_item_schema(slot, minStack, filter_func)
    expect(1, slot, "number")
    expect(2, minStack, "number", "nil")
    expect(3, filter_func, "function", "nil")
    range(slot, 1, 1000)
    machine_schema.EXTRA_SLOT = slot
    machine_schema.EXTRA_MIN_STACK = minStack
    machine_schema.EXTRA_FILTER_FUNC = filter_func
end

local function set_process_time(process_time)
    expect(1, process_time, "number")
    range(process_time, 0.05, 1000)
    machine_schema.PROCESS_TIME = process_time
end

local function print_machines()
    for count, machine in pairs(machines) do
        print(count, peripheral.getName(machine))
    end
end

local function print_machine_schema()
    for k, v in pairs(machines) do
        print(k, v)
    end
end

local function find_machines()
    machines = { peripheral.find(machine_schema.PERIPHERAL_TYPE, function(n, p)
        return string.match(n, machine_schema.ID_STR)
    end) }
end

local function move_from(fromInv, fromSlot, toInv, toSlot, count)
    fromInv.pushItems(peripheral.getName(toInv), fromSlot, count, toSlot)
end

local function slotHasItem(p, slot)
    return p.getItemDetail(slot)
end

local function get_next_item(inv, minCount, filter_func)
    local items = inv.list()
    for slot, item in pairs(items) do
        if item and item.count >= minCount then
            if (filter_func and filter_func(inv, slot, item)) or not filter_func then -- Run the filter function if it exists, pass in the inv, slot and item variables
                item.slot = slot -- Injects the slot into the item table because thats useful
                return item
            end
        end
    end
end

local function get_input_item()
    local minCount = machine_schema.INPUT_MIN_STACK or 1
    current_input_stack = get_next_item(input_inv, minCount, machine_schema.INPUT_FILTER_FUNC)
    if current_input_stack and current_input_stack.count >= minCount then
        local returnItem = current_input_stack
        current_input_stack.count = returnItem.count - minCount
        return returnItem
    end
end

local function get_extra_item()
    local minCount = machine_schema.EXTRA_MIN_STACK or 1
    current_extra_stack = get_next_item(extra_input_inv, minCount, machine_schema.EXTRA_FILTER_FUNC)
    if current_extra_stack and current_extra_stack.count >= minCount then
        local returnItem = current_extra_stack
        current_extra_stack.count = returnItem.count - minCount
        return returnItem
    end
end

local function process_output(machine)
    for _, slot in pairs(machine_schema.OUTPUT_SLOTS) do
        if slotHasItem(machine, slot) then
            move_from(machine, slot, output_inv, nil, nil)
        end
    end
end


local function process_machine(machine)
    -- Process OutputSlots
    process_output(machine)

    -- Process ExtraSlot (If there is one)
    if machine_schema.EXTRA_SLOT and not slotHasItem(machine, machine_schema.EXTRA_SLOT) then
        local extra_item = get_extra_item()
        if extra_item then
            move_from(extra_input_inv, extra_item.slot, machine, machine_schema.EXTRA_SLOT, machine_schema.EXTRA_MIN_STACK)    
        end
    end

    -- Process inputSlot
    local input_item = get_input_item()
    if input_item then
        move_from(input_inv, input_item.slot, machine, machine_schema.INPUT_SLOT, machine_schema.INPUT_MIN_STACK)
    end
end


local function process_machines()
    for _, machine in pairs(machines) do
        print_current_machine_info(machine)
        process_machine(machine)
        sleep(machine_schema.PROCESS_TIME)
    end
end

local function getNonMachineInvs(machine_id)
    local inventories = {}
    peripheral.find("inventory", function(name, modem)
        if not string.find(name, machine_id) then
            table.insert(inventories, name)
        end
    end)
    return inventories
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
    parallel_var = choice
    --return choice
end

function tableContains(table, check_value)
    for _,value in pairs(table) do
        if value == check_value then 
            return true
        end
    end
    return false
end

local function set_inventories(inputInvName, outputInvName, extraInputInvName)
    expect(1, inputInvName, "string")
    expect(2, outputInvName, "string")
    expect(3, extraInputInvName, "string", "nil")
    output_inv = peripheral.wrap(outputInvName)
    extra_input_inv = nil
    if extraInputInvName then
        extra_input_inv = peripheral.wrap(extraInputInvName)
    end
    input_inv = peripheral.wrap(inputInvName)
end

local function getPeripheralAttach()
    local machine_id = machine_schema.ID_STR
    local event = nil
    local side = machine_id
    while string.find(side, machine_id) do
        event, side = os.pullEvent("peripheral")
    end
    write(side)
    table.insert(potentialIO,side)
    parallel_var = side
end

local function validateSettings(settingsNameTable)
    for _,name in pairs(settingsNameTable) do

        if not peripheral.isPresent(name) then
            reprintLine(18,"Missing Inventories! Please set them up again.")
            return false
        end
    end
    return true
end

local function setupInventorySettings()
    local schema_settings_path = machine_schema.ID_STR..".settings"
    local schema_input_setting = machine_schema.ID_STR..".input"
    local schema_output_setting = machine_schema.ID_STR..".output"
    local schema_extra_setting = machine_schema.ID_STR..".extra"
    local inputInvName = nil
    local outputInvName = nil
    local extraInputInvName = nil
    
    reprintLine(1,"Press Enter to begin setup...")
    while true do 
        local event,key,is_held = os.pullEvent("key")
        if key == keys.enter then
            reprintLine(1,"Select or Connect Inventories:")
            break
        end
    end
    potentialIO = getNonMachineInvs(machine_schema.ID_STR)
    write("Input:  ")
    parallel.waitForAny(function() getUserChoiceFromTable(potentialIO,true) end,function() getPeripheralAttach() print("") end)
    --print(parallel_var)
    inputInvName = parallel_var
    write("Output: ")
    parallel.waitForAny(function() getUserChoiceFromTable(potentialIO,true) end,function() getPeripheralAttach() print("") end)
    --print(parallel_var)
    outputInvName = parallel_var
    write("Extra:  ")
    parallel.waitForAny(function() getUserChoiceFromTable(potentialIO) end,function() getPeripheralAttach() print("") end)
    --print(parallel_var)
    extraInputInvName = parallel_var
    --print(inputInvName,outputInvName,extraInputInvName)
    settings.clear()
    settings.define(schema_input_setting)
    settings.define(schema_output_setting)
    settings.define(schema_extra_setting)
    settings.set(schema_input_setting,inputInvName)
    settings.set(schema_output_setting,outputInvName)
    settings.set(schema_extra_setting,extraInputInvName)
    settings.save(schema_settings_path)
    settings.load(schema_settings_path)
end

local function find_inventories()
    local schema_settings_path = machine_schema.ID_STR..".settings"
    local schema_input_setting = machine_schema.ID_STR..".input"
    local schema_output_setting = machine_schema.ID_STR..".output"
    local schema_extra_setting = machine_schema.ID_STR..".extra"
    
    settings.load(schema_settings_path)
    local inputInvName = settings.get(schema_input_setting)
    local outputInvName = settings.get(schema_output_setting)
    local extraInputInvName = settings.get(schema_extra_setting)
    -- print(inputInvName,outputInvName)
    if not inputInvName or not outputInvName then 
        -- print("deleting schema settings file.")
        fs.delete(schema_settings_path)
    end
    while not (settings.load(schema_settings_path) and validateSettings({inputInvName,outputInvName,extraInputInvName})) do
        setupInventorySettings()
        inputInvName = settings.get(schema_input_setting)
        outputInvName = settings.get(schema_output_setting)
        extraInputInvName = settings.get(schema_extra_setting)
    end

    return inputInvName,outputInvName,extraInputInvName
end

local function startup()
    check_valid_schema()
    set_inventories(find_inventories())
    find_machines()
end

local function main()
    term.setCursorPos(1,1)
    term.clear()
    startup()
    print_static_program_info()
    while true do
        process_machines()
    end
end

local public = {
    main = main,
    create_machine_schema = create_machine_schema,
    create_extra_item_schema = create_extra_item_schema,
    create_input_item_schema = create_input_item_schema,
    print_machine_schema = print_machine_schema,
    print_machines = print_machines,
    set_inventories = set_inventories,
    set_process_time = set_process_time
}

return public