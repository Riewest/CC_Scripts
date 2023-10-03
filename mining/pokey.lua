---------------------------------------------------------------
-- Efficient Chunk Mining v3
-- Written by LogicEngineer
-- Started 02/27/20 in Minecraft version 1.12.2
---------------------------------------------------------------
 
local args = {...}
local turnQueue
local startingHeight
local minHeight
local pos
local rPos
local fuelEstimate = 0
local pingFrequency = 180
local forward = "forward"
local up = "up"
local down = "down"
local left = "left"
local right = "right"
local moved
local chestSlot  = 16
local cobbleSlot = 1
local fuelSlot = 2
local flatBedrock = false
local chestType 
local spinCount = 1
local chunkStartLoc
 
function GPSLostSleepCycle()
    pos = vector.new(gps.locate(5))
    while not pos.x do 
        sleep(pingFrequency)
    end
end
 
function GPSLocate(timeout)
    pos = vector.new(gps.locate(timeout))
    if not pos.x then 
        print("Cannot find GPS network! Stopping work unitl GPS network can be located.")
        GPSLostSleepCycle()
    else
        rPos = RoundVectorComsToInt(pos)
        return rPos
    end
    return false
end
 
function GetHeight()
    rPos = GPSLocate(5)
    return  rPos.y
end 
 
function GetMinHeight(bedrock)
    bedrock = bedrock or "regular"
    if bedrock == "flat" then
        return (2)
    else
        if bedrock == "debug" then
            return (65)
        else
            return (5)
        end
    end
end
 
function AmIHigh() --420 BlazeIt?
    if GetHeight() >= startingHeight-((startingHeight-minHeight)/2) then
        return true
    else
        return false
    end
end
 
function SpinAround()
    turtle.turnLeft()
    turtle.turnLeft()
    return
end
 
function TrackSpin()
    spinCount = spinCount + 1
    if spinCount == 0 then
        spinCount = 4
    end
    if spinCount == 5 then
        spinCount = 1
    end
end
 
function CorrectDirection(current)
    print(current)
    if current == 4 then
        turtle.turnLeft()
    else
        if current == 3 then
            SpinAround()
        else
            if current == 2 then
                turtle.turnRight()
            else
                return
            end
        end
    end
    return
end
 
function ForceMove(distance, direction)
    for i=1, distance do 
        while not moved do
            if direction == down then
                turtle.digDown()
                if turtle.down() then 
                    moved = true
                end
            else 
                if direction == up then
                    turtle.digUp()
                    if turtle.up() then 
                        moved = true
                    end
                else
                    if direction == forward then
                        turtle.dig()
                        if turtle.forward() then 
                            moved = true
                        end
                    else 
                        return false
                    end
                end
            end
        end
        moved = false
    end
    return
end
 
function RoundVectorComsToInt(vec)
    return vec:round()
    --    return vector.new(math.floor(vec.x+0.5),math.floor(vec.y+0.5),math.floor(vec.z+0.5))
end
 
function IsInt(num)
    return num==math.floor(num)
end
 
function Turn21() -- Time to party?
    if turnQueue == right then
        turtle.turnRight()
        ForceMove(1,forward)
        turtle.turnRight()
        turnQueue = left
    else
        turtle.turnLeft()
        ForceMove(1,forward)
        turtle.turnLeft()
        turnQueue = right
    end
end
 
function FuelCheck()
    fuelEstimate = 16*16+52*startingHeight
    print("Current Fuel:", turtle.getFuelLevel())
        print("Estimated Fuel:", fuelEstimate)
    if (fuelEstimate) >= turtle.getFuelLevel() then
        print("Need more fuel for requested chunkmine.")
        turtle.select(fuelSlot)
        while turtle.getFuelLevel() < fuelEstimate do 
            turtle.refuel(5)
        end
--      return false
    end
    return true
end
 
function WaitForChest()
    while not ChestCheck() do
        sleep(10)
    end
    return
end
 
function ChestCheck()
    local detail = turtle.getItemDetail(chestSlot)
    if detail then
        if detail.name == "enderstorage:ender_storage" then 
            return "ender"
        elseif detail.name == "enderchests:ender_chest" then
            return "ender"
        else
            if detail.name == "minecraft:chest" then
                return "vanilla"
            else
                return false
            end
        end
    end
    return false
end
 
function DropSide(slotNum, side)
    turtle.select(slotNum)
    side = string.lower(side)
    local success = false
    if side == "front" then
      success = turtle.drop()
    elseif side == "top" then
      success = turtle.dropUp()
    elseif side == "bottom" then
      success = turtle.dropDown()
    else
      success = turtle.drop()
    end
    return success
  end
  
function EmptyInv(slotsToEmpty, side)
    local count
    local oldSlot = turtle.getSelectedSlot()
    if not side then
      side = "back"
    end
    if not slotsToEmpty then
      count = 16
    else
      count = table.getn(slotsToEmpty)
    end
    for i = 1, count do
      DropSide(slotsToEmpty[i], side)
    end
    turtle.select(oldSlot)
  end
  
function DoChest()
    if chestType == "vanilla" then
        ChestCheck()
    end
    turtle.select(chestSlot)
    while not turtle.placeUp() do
        turtle.digUp()
        sleep(.5)
    end
    local slotsToEmpty = { 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15}
    EmptyInv(slotsToEmpty, "top")
    turtle.select(chestSlot)
    if chestType == "ender" then
        turtle.digUp()
    end
end
 
function CheckOre()
    local success, block = turtle.inspect()
    if not success then return false end
    local name = string.lower(block.name)
    return (string.match(name, "ore"))
end
 
function Scan()
    for i=1, 4 do
        if CheckOre() then
            turtle.dig()
        end
    end
end
 
function PokeHole(updown)
    spinCount = 1
    for i=1, (startingHeight-minHeight) do
        SpinScan()
        ForceMove(1,updown)
        if updown == down and i == 2 then
            turtle.select(cobbleSlot)
            turtle.placeUp()
        end
    end
    SpinScan()
    if updown == up then
        turtle.select(cobbleSlot)
        turtle.placeDown()
    end
    print("Correcting facing direction.")
    CorrectDirection(spinCount)
    if chestType == "vanilla" then
        if updown == "up" then 
            DoChest()
        end
    else
        DoChest()
    end
end
 
function SpinScan()
    for j=1, 3 do
        Scan()
        turtle.turnRight()
    end
    Scan()
    TrackSpin()
end
 
function DigIfShould()
    if ShouldIDigHere() then
        if AmIHigh() then 
            PokeHole(down)
        else 
            PokeHole(up)
        end
    end
    return
end
 
function ShouldIDigHere()
    GPSLocate()
    if IsInt(rPos.x/5) and IsInt(rPos.z/5) then
        return true
    else
        if IsInt((rPos.x-2)/5) and IsInt((rPos.z-1)/5) then
            return true
        else
            if IsInt((rPos.x+1)/5) and IsInt((rPos.z-2)/5) then
                return true
            else
                if IsInt((rPos.x-1)/5) and IsInt((rPos.z+2)/5) then
                    return true
                else
                    if IsInt((rPos.x+2)/5) and IsInt((rPos.z+1)/5) then
                        return true
                    else
                      return false
                    end
                end
            end
        end
    end
end
 
function ProcessChunk()
    local debugCheck = 15
    if args[2] == "debug" then 
        debugCheck = 1
    end
    for i=1, debugCheck do
        for j=1, 15 do
            DigIfShould()
            ForceMove(1,forward)
        end
        DigIfShould()
        Turn21()
    end
    for i=1, 15 do 
        DigIfShould()
        ForceMove(1,forward)
    end
    DigIfShould()
    SpinAround()
    if not AmIHigh() then
        for i=1, (startingHeight-minHeight) do
            ForceMove(1,up)
        end
        DoChest()
        turtle.select(cobbleSlot)
        turtle.placeDown()
    end
    return
end
 
function CheckArgs()
    if not args[1] then 
        print("ERROR: Need turtle start location!")
        return false
    else
        chunkStartLoc = args[1]
    end
    return true
end
 
function HeightInit()
    startingHeight = GetHeight()
    print("Starting Height:", startingHeight)
    minHeight = GetMinHeight(args[2])
    print("Minimum Height:", minHeight)
end
 
function Main()
    if not CheckArgs() then 
        return
    end
 
    chestType = ChestCheck()
    while not (chestType) do
        term.clear()
        term.setCursorPos(1,1)
        print("No chest in slot 16!")
        print("Waiting for chest...")
        chestType = ChestCheck()
        sleep(5)
    end
    
    HeightInit()
 
    if not FuelCheck() then 
        return
    end
 
    if chunkStartLoc == left then 
        turnQueue = right
    else
        turnQueue = left
    end
 
    ProcessChunk()
 
end
 
Main()