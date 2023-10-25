-- Import the Machine class from Machine.lua
local mlib = require("machine")

-- A few example filter functions for slots.
-- The inv and the machine will be wrapped
local function roundRobinInputs(inv, slot, item, machine)
    local move_count = 8
    return true, move_count
end

local function roundRobinFuel(inv, slot, item, machine)
    local move_count = 1
    return true, move_count
end

LootFabSchema = mlib.Schema.new("Furnace Processor", "furnace")
LootFabSchema:addOutputSlots(3)
LootFabSchema:addInputSlots(1, roundRobinInputs)
LootFabSchema:addExtraSlots(2, roundRobinFuel)
local furnaces = mlib.Processor:new("Furnace Processor", LootFabSchema)
furnaces:setProcessTime(.5) -- Allowing this to run a bit faster than default
furnaces:run() -- Kicks off the processing loop