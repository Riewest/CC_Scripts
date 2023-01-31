-------------------------------
--Name: squid/turtle/gps
--Version: 1.0.0
--Description: Provides a goTo method to fly to a given gps coord
--By: SuicideSquid
-------------------------------
--Library Requirements
local mv = require("squid/turtle/movement")
local inv = require("squid/turtle/inventory")

--Variables
local defaultTravelHeight = 85
local Directions = {}
local invDirections = {}
local locateTime = 5
Directions.north = 0
Directions.east = 1
Directions.south = 2
Directions.west = 3
invDirections[0] = "north"
invDirections[1] = "east"
invDirections[2] = "south"
invDirections[3] = "west"
local GPS_settings = "settings/GPS_settings"



--------------------
--LOCATION METHODS
--------------------

--Gets the direction the
--turtle is facing
local function getFacing()
	settings.load(GPS_settings)
	local setting = "facing"
	data = settings.get(setting,false)
	if not data then print("NO GPS FACING SAVE") return false end
	return tonumber(data)
end

--Saves the direction the
--turtle is facing
local function setFacing(direction)
	settings.load(GPS_settings)
	local setting = "facing"
	settings.set(setting,tostring(direction))
	return settings.save(GPS_settings)
end

--Detects which direction the
--turtle is facing by moving on block
--on its horizontal plane
--Should always be run on turtle start
--as it saves the facing direction in a file
local function detectFacing()
	local me = vector.new(gps.locate(locateTime))
	if not me then print("NO GPS SIGNAL") return false end

	local foundSlot = inv.findEmptySlot(true)
	local dug = mv.forceMove()
	local newLoc = vector.new(gps.locate(locateTime))
	local dug2 = mv.forceMove(1, mv.directions.back)
	if foundSlot and (dug or dug2) then turtle.dropDown() end

	local result = me:sub(newLoc)
	local x = result.x
	local z = result.z
	local newFacing = nil
	if x > 0 then
		newFacing = Directions.west
	elseif x < 0 then
		newFacing = Directions.east
	end
	if z > 0 then
		newFacing = Directions.north
	elseif z < 0 then
		newFacing = Directions.south
	end
	if newFacing then
		setFacing(newFacing)
	end
end

--Turns the turtle towards
--the passed direction
--"north", "south", "east", "west"
local function turnTowards(direction)
	if not direction then print("NO DIRECTION TO TURN TO") return end
	direction = string.lower(direction)
	local facing = getFacing()
	local wantToFace = Directions[direction]
	local turns = facing - wantToFace
	if turns == 0 then return end
	if turns > 0 then
		for i = 1, turns do
			turtle.turnLeft()
		end
	else
		for i = 1, math.abs(turns) do
			turtle.turnRight()
		end
	end
	setFacing(wantToFace)
end


--Moves the turtle on its vertical
--axis by the specified amount
local function changeY(moveAmount)
	if moveAmount > 0 then
		mv.forceMove(moveAmount, mv.directions.up)
	elseif moveAmount < 0 then
		mv.forceMove(math.abs(moveAmount), mv.directions.down)
	end	
end


--Goes to the passed vectors
--location in the world. If specified
--will travel at a certain y height
--will also face a direction if specified
local function goTo(location, yLevel, face)
	if not location then print("NO LOCATION TO GOTO") return end
	yLevel = yLevel or defaultTravelHeight
	local turnTo
	if not face then
		turnTo = invDirections[getFacing()]
	else
		turnTo = face
	end
	local me = vector.new(gps.locate(locateTime))
	local travel = location:sub(me)
	local yChange = yLevel - me.y
	if travel.x == 0 and travel.z == 0 then
		turnTowards(turnTo)
		return
	end
	changeY(yChange)
	local x = travel.x
	local z = travel.z
	
	if x > 0 then
		turnTowards("east")
	elseif x < 0 then
		turnTowards("west")
	end
	mv.forceMove(math.abs(x))
	
	if z > 0 then
		turnTowards("south")
	elseif z < 0 then
		turnTowards("north")
	end
	mv.forceMove(math.abs(z))
	
	yChange = (0 - yChange) + travel.y
	changeY(yChange)
	turnTowards(turnTo)
end



local function gpsInit()
	print("Initilializing Squid GPS...")
	detectFacing()
	print("Squid GPS Initialized")
end

return {goTo = goTo, getFacing = getFacing, gpsInit = gpsInit}