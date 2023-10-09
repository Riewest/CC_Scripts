local machine = require("machine")
local function prediction_filter(inv, slot, item)
    return string.match(item.name, "matrix")
end
local function model_filter(inv, slot, item)
    return string.match(item.name, "data_model")
end

local function main()
    local output_inv = "minecraft:barrel_5"
    local extra_input_inv = "minecraft:barrel_4"
    local input_inv = "minecraft:barrel_3"
    machine.set_inventories(input_inv, output_inv, extra_input_inv)
    machine.create_machine_schema({3,4}, "sim_chamber")
    machine.create_input_item_schema(2, 1, prediction_filter)
    machine.create_extra_item_schema(1, 1, model_filter)
    machine.main()
end

main()