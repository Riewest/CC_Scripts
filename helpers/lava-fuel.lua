-- lava_fuel.lua

-- CONFIG
local BUCKET_SLOT = 1

-- Get square size from args
local tArgs = { ... }
local size = tonumber(tArgs[1])
if not size or size < 1 then
  print("Usage: lava_fuel <size>")
  return
end

-- Heading: 0 = north, 1 = east, 2 = south, 3 = west
local x, y = 0, 0
local heading = 0  -- We'll assume 0 is the direction the turtle is initially facing after stepping forward

-- Helpers to update position/heading
local function updateForward()
  if heading == 0 then y = y + 1
  elseif heading == 1 then x = x + 1
  elseif heading == 2 then y = y - 1
  elseif heading == 3 then x = x - 1 end
end

local function turnLeft()
  turtle.turnLeft()
  heading = (heading - 1) % 4
end

local function turnRight()
  turtle.turnRight()
  heading = (heading + 1) % 4
end

local function forward()
  while not turtle.forward() do
    turtle.dig()
    sleep(0.2)
  end
  updateForward()
end

-- Refuel logic using lava below
local function refuelFromLavaBelow()
  turtle.select(BUCKET_SLOT)
  turtle.placeDown()
  if not turtle.refuel(1) then
    print("Refuel failed at ("..x..","..y..").")
  end
end

-- Move one step backward (with position tracking)
local function back()
  if turtle.back() then
    if heading == 0 then y = y - 1
    elseif heading == 1 then x = x - 1
    elseif heading == 2 then y = y + 1
    elseif heading == 3 then x = x + 1 end
    return true
  end
  return false
end

-- Face a specific direction (0=north, 1=east, etc.)
local function face(dir)
  while heading ~= dir do
    turnRight()
  end
end

-- Traverse NxN square
local function traverseSquare(n)
  for row = 1, n do
    for col = 1, n do
      refuelFromLavaBelow()
      if col < n then forward() end
    end
    if row < n then
      if row % 2 == 1 then
        turnRight()
        forward()
        turnRight()
      else
        turnLeft()
        forward()
        turnLeft()
      end
    end
  end
end

-- Return to original position and face original direction (assumed to be heading = 0)
local function returnToStart()
  -- Move back to (0,0)
  if x ~= 0 then
    if x > 0 then face(3) else face(1) end
    for _ = 1, math.abs(x) do forward() end
  end

  if y ~= 0 then
    if y > 0 then face(2) else face(0) end
    for _ = 1, math.abs(y) do forward() end
  end

  -- Face back to original direction (north)
  face(0)
end

-- === Main ===

forward() -- Move into square
traverseSquare(size)
returnToStart()
