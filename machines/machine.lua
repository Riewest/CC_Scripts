local expect = require "cc.expect"
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
    PERIPHERAL_TYPE = "inventory" -- Used as first parameter in "peripheral.find"
}

local machines = {}
local output_inv = nil
local input_inv = nil
local extra_input_inv = nil

local current_extra_stack = nil
local current_input_stack = nil

local function print_program_info()
    term.clear()
    term.setCursorPos(1,1)
    print("Program Info:")
    term.setCursorPos(1,2)
    print("  Machine Type:", machine_schema.ID_STR)
    term.setCursorPos(1,3)
    print("  Count:", #machines )
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
    if not current_input_stack then
        current_input_stack = get_next_item(input_inv, minCount, machine_schema.INPUT_FILTER_FUNC)
    else
        local input_stack = input_inv.getItemDetail(current_input_stack.slot)
        if not input_stack or (input_stack and input_stack.count < minCount) then
            current_input_stack = get_next_item(input_inv, minCount, machine_schema.INPUT_FILTER_FUNC)
        end
    end
    if current_input_stack and current_input_stack.count >= minCount then
        local returnItem = current_input_stack
        current_input_stack.count = returnItem.count - minCount
        return returnItem
    end
end

local function get_extra_item()
    local minCount = machine_schema.EXTRA_MIN_STACK or 1
    if not current_extra_stack then
        current_extra_stack = get_next_item(extra_input_inv, minCount, machine_schema.EXTRA_FILTER_FUNC)
    else
        local extra_stack = extra_input_inv.getItemDetail(current_extra_stack.slot)
        if not extra_stack or (extra_stack and extra_stack.count < minCount) then
            current_extra_stack = get_next_item(extra_input_inv, minCount, machine_schema.EXTRA_FILTER_FUNC)
        end
    end
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
        process_machine(machine)
    end
end

local function set_inventories(inputInvName, outputInvName, extraInputInvName)
    expect(1, inputInvName, "string")
    expect(2, outputInvName, "string")
    expect(3, extraInputInvName, "string", "nil")
    output_inv = peripheral.wrap(outputInvName)
    extra_input_inv = peripheral.wrap(extraInputInvName)
    input_inv = peripheral.wrap(inputInvName)
end

local function startup()
    check_valid_schema()
    find_machines()
end

local function main()
    startup()
    print_program_info()
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
    set_inventories = set_inventories
}

return public