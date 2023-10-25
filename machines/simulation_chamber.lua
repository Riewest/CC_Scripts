local mlib = require("machine")
local function matrix_filter(inv, slot, item)
    return string.match(item.name, "matrix")
end
local function model_filter(inv, slot, item)
    return string.match(item.name, "data_model")
end

-- Spin up an instance of the loot fabricator schema in a new tab
local new_require_builder = require "cc.require"
local env = setmetatable({}, { __index = _ENV })
env.require, env.package = new_require_builder.make(env, "/machines")
local lootfab = multishell.launch(env, "/machines/loot_fabricator.lua")
multishell.setTitle(lootfab, "LootFab")



LootFabSchema = mlib.Schema.new("Simulation Chambers", "sim_chamber")
local output_slots = {3,4}
LootFabSchema:addOutputSlots(output_slots)
LootFabSchema:addInputSlots(2, matrix_filter)
LootFabSchema:addExtraSlots(1, model_filter)
local SimChamberProcessor = mlib.Processor:new("Simulation Chambers", LootFabSchema)
SimChamberProcessor:setProcessTime(.25) -- Allowing this to run a bit faster than default
SimChamberProcessor:run() -- Kicks off the processing loop



