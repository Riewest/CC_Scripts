local prediction_input = "minecraft:barrel_5"
local loot_output = "minecraft:barrel_6"

local lootfab = require("machine")
local function prediction_filter(inv, slot, item)
    return string.match(item.name, ":prediction")
end


local function loot_main()
    local output_slots = {2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17}
    lootfab.set_inventories(prediction_input, loot_output)
    lootfab.create_machine_schema(output_slots, "loot_fabricator")
    lootfab.create_input_item_schema(1, nil, prediction_filter)
    lootfab.set_process_time(.75)
    lootfab.main()
end


loot_main()