-- tunnel.lua
-- Usage: tunnel <width> <length>

local tArgs = { ... }
local LENGTH = tonumber(tArgs[1])
local WIDTH = 3
local HEIGHT = WIDTH
print(LENGTH, "x", WIDTH, "x", HEIGHT)

local nextTurn = turtle.turnRight
local turnTable = {
    [turtle.turnRight] = turtle.turnLeft,
    [turtle.turnLeft] = turtle.turnRight
}

-- === Safe movement ===
local function tryForward()
    while not turtle.forward() do
      turtle.dig()
      sleep(0.1)
    end
end

local function doColumn()
    tryForward()
    while turtle.digUp() do sleep(0.1) end
    turtle.digDown()
end

local function doSlice()
    doColumn()
    nextTurn()
    nextTurn = turnTable[nextTurn]
    doColumn()
    doColumn()
    nextTurn()
end


for i = 1, LENGTH do
    doSlice()
end


if LENGTH % 2 == 1 then
    turtle.turnLeft()
    tryForward()
    tryForward()
    turtle.turnRight()
end