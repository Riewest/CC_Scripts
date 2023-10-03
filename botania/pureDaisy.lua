local valid_inputs = {
    "minecraft:oak_log",
    "minecraft:spruce_log",
    "minecraft:birch_log",
    "minecraft:jungle_log",
    "minecraft:acacia_log",
    "minecraft:dark_oak_log",
    "minecraft:mangrove_log",
    "minecraft:stripped_oak_log",
    "minecraft:stripped_spruce_log",
    "minecraft:stripped_birch_log",
    "minecraft:stripped_jungle_log",
    "minecraft:stripped_acacia_log",
    "minecraft:stripped_dark_oak_log",
    "minecraft:stripped_mangrove_log",
    "minecraft:stone"
}
local livingWood = "botania:livingwood_log"
local livingRock = "botania:livingrock"
local args = {...}

local invTop
local invBottom
local invSlots = 0
local foundInput = false

local daisySpots = args[1] or 4

local function isOutput(data)
    if data.name == livingRock or data.name == livingWood then
        return true
    else
        return false
    end
end

local function handleOutput()
    local data = turtle.getItemDetail()
    if isOutput(data) then
        turtle.dropDown()
        return true
    else
        return false
    end
end

local function findInput(inv)
    local b,s = turtle.suckUp()
    return b
end

local function emptyExtraSlots()
    for slot=daisySpots+1,16 do 
        turtle.select(slot)
        turtle.dropDown()
    end
    turtle.select(1)
end

local function process()
    for spot=1,daisySpots do
        turtle.select(spot)
        local block,block_data = turtle.inspect()
        if block then
            if isOutput(block_data) then
                turtle.dig()
            end
        end
        if turtle.getItemCount() > 0 then
            if handleOutput() then 
                if findInput(invTop) then
                    turtle.place()
                end
            else
                turtle.place()
            end
        else
            findInput(invTop)
        end 
        turtle.turnRight()
    end
    for i=1,4-daisySpots do
        turtle.turnRight()
    end
    emptyExtraSlots()
    foundInput = false
end

local function main()
    invTop = peripheral.wrap("top")
    invBottom = peripheral.wrap("bottom")
    if invTop and invBottom then
        term.clear()
        term.setCursorPos(1,1)
        print("Pure Daisying...")
        print("Spots: "..daisySpots)
        while true do
            process()
            sleep(30)
        end
    else
        print("One or more inventories is missing!")
        return
    end
end

main()