local machine = require("machine")
local function test_filter(inv, slot, item)
    return string.match(item.name, "planks")
end

local function main()
    machine.create_machine_schema(3, "furnace")
    machine.create_input_item_schema(1, 1)
    machine.create_extra_item_schema(2, 1)
    --machine.create_extra_item_schema(2, 1, test_filter)
    machine.print_machine_schema()
    machine.main()
    machine.print_machines()
end

main()