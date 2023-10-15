local prediction_output = "minecraft:barrel_5"
local model_input_inv = "minecraft:barrel_4"
local input_inv = "minecraft:barrel_3"

local simchamber = require("machine")
local function matrix_filter(inv, slot, item)
    return string.match(item.name, "matrix")
end
local function model_filter(inv, slot, item)
    return string.match(item.name, "data_model")
end

local function simchamber_main()
    local output_slots = {3,4}
    simchamber.set_inventories(input_inv, prediction_output, model_input_inv)
    simchamber.create_machine_schema(output_slots, "sim_chamber")
    simchamber.create_input_item_schema(2, nil, matrix_filter)
    simchamber.create_extra_item_schema(1, 1, model_filter)
    simchamber.main()
end

local new_require_builder = require "cc.require"
local env = setmetatable({}, { __index = _ENV })
env.require, env.package = new_require_builder.make(env, "/machines")

local lootfab = multishell.launch(env, "/machines/loot_fabricator.lua")
multishell.setTitle(lootfab, "LootFab")
simchamber_main()