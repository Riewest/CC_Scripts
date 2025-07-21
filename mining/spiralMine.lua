-- test
local args = {...}
local length = tonumber(args[1]) or -1 -- defaults to huge

local fuelChest = 16
local fuelStackSize = 64
local minFuelLevel = 100
local returnChest = 15

-- DROP items that match tag (e.g., "minecraft:cobblestone")
local dropTags = {
    "c:cobblestones",
    "c:stones",
    "c:netherracks",
    "c:sands",
    "c:sandstone/blocks"
}
-- Drop items with these exact names
local dropItems = {
    "minecraft:clay_ball",
    "minecraft:flint",
    "minecraft:torch",
    "minecraft:gravel"
}

local function returnItems()
    turtle.select(returnChest)
    -- Ensure area above is clear
    while turtle.digUp() do sleep(0.1) end
    turtle.placeUp()
    sleep(0.1)

    for i = 1, 14 do
        turtle.select(i)
        local retry = 0
        while turtle.getItemCount() > 0 do
            if turtle.dropUp() then
                retry = 0 -- reset on success
            else
                retry = retry + 1
                if retry > 5 then
                    error("Failed to deposit item from slot " .. i .. " — inventory above may be full.")
                end
                sleep(1)
            end
        end
    end

    turtle.select(returnChest)
    turtle.digUp()
    turtle.select(1)
end





local function shouldDrop(item)
    if not item then return false end

    -- Check exact item names
    for _, name in ipairs(dropItems) do
        if item.name == name then
            return true
        end
    end

    -- Check tags
    if item.tags then
        for tagName, _ in pairs(item.tags) do
            for _, dropTag in ipairs(dropTags) do
                if tagName == dropTag then
                    return true
                end
            end
        end
    end

    return false
end

local function checkInv(force_return)
    for i = 1, 14 do
        local item = turtle.getItemDetail(i, true)
        if item and shouldDrop(item) then
            turtle.select(i)
            turtle.dropDown()
        end
    end

    -- Drop off if nearing full
    if force_return or turtle.getItemCount(13) > 0 or turtle.getItemCount(14) > 0 then
        returnItems()
    end
end

local function refuel()
    checkInv(true)
    turtle.select(fuelChest)
    -- Make sure the area is clear to place fuelChest
    while turtle.digUp() do
        sleep(.1)
    end
    turtle.placeUp()
    sleep(.1)
    turtle.select(1)
    while turtle.getFuelLevel() <= minFuelLevel do
        turtle.suckUp(fuelStackSize - turtle.getItemCount())
        turtle.refuel()
    end
    turtle.dropUp()
    turtle.select(fuelChest)
    turtle.digUp()
    turtle.select(1)
end

local function moveDig(moveFunc, digFunc)
    while not moveFunc() do
        digFunc()
        sleep(.05)
    end
end

Spiral = {}
Spiral.__index = Spiral
local dir, filename = "SPIRAL_MINE", "spiral.json"
local filepath = dir .. "/" .. filename
-- Task constructor
function Spiral:new(currentSideLength, currentSidePos, isTail)
    local o = {}
    o.isTail = isTail or false
    o.sideLength = currentSideLength or 0
    o.sidePos = currentSidePos or 0
    setmetatable(o, Spiral)
    o = o:load()
    return o
end

function Spiral:incrementPosition()
    checkInv()
    if turtle.getFuelLevel() <= minFuelLevel then -- Fuel Check
        refuel()
    end
    moveDig(turtle.forward, turtle.dig)
    turtle.digUp()
    turtle.digDown()
    self.sidePos = self.sidePos + 1
    self:save()
end

function Spiral:doSide()
    for i = self.sidePos, self.sideLength do
        print(i, self.sideLength)
        self:incrementPosition()
    end
    turtle.turnRight()
    self:nextLen()
    checkInv(true)
end

function Spiral:nextLen()
    if self.isTail then
        self.sideLength = self.sideLength + 1
    end
    self.isTail = not self.isTail
    self.sidePos = 0
    self:save()
    return self.sideLength
end

function Spiral:save()
    fs.makeDir(dir)
    local spiralFile = fs.open(filepath, "w")
    spiralFile.write(textutils.serializeJSON(self))
    spiralFile.close()
end

function Spiral:load()
    local spiralFile = fs.open(filepath, "r")
    if spiralFile then
        local savedSchedule = textutils.unserializeJSON(spiralFile.readAll())
        spiralFile.close()
        setmetatable(savedSchedule, Spiral)
        return savedSchedule
    end
    return self
end

local function main()
    if length < 1 then
        length = 30000000 -- Basically infinite
    end
    local mySpiral = Spiral:new()
    for i = 1, length do
        mySpiral:doSide()
        sleep(.05)
    end
    checkInv(true)
end

main()
