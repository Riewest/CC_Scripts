local mlib = require("machine")
local function prediction_filter(inv, slot, item)
    return string.match(item.name, ":prediction")
end

LootFabSchema = mlib.Schema.new("Loot Fabricators", "loot_fabricator")
local output_slots = {2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17}
LootFabSchema:addOutputSlots(output_slots)
LootFabSchema:addInputSlots(1, prediction_filter)
local LootFabProcessor = mlib.Processor:new("Loot Fabricators", LootFabSchema)
LootFabProcessor:setProcessTime(.5) -- Allowing this to run a bit faster than default
LootFabProcessor:run() -- Kicks off the processing loop