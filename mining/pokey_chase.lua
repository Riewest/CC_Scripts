---------------------------------
--- Arguments
---------------------------------
if not turtle then
    error("Requires a Turtle")
    return
end

local tArgs = { ... }
if #tArgs ~= 1 then
    local programName = arg[0] or fs.getName(shell.getRunningProgram())
    print("Usage: " .. programName .. " <diameter>")
    return
end

-- Mine in a quarry pattern until we hit something we can't dig
local size = tonumber(tArgs[1])
if size < 1 then
    print("Excavate diameter must be positive")
    return
end

---------------------------------
--- Imports and Globals
---------------------------------

package.path = package.path .. ";/?;/?.lua;/?/init.lua;/squid/?;/squid/?.lua;/squid/turtle/?.lua;/squid/?/init.lua"

local INS = require("INS")
local MINING = require("mining")

-- will instantiate in the startup function
local nav
local pokehole_map
local chest_direction
local hole_height
local returnAndEmpty

-- The Root Poke Hole to calculate all others in the world :)
local ROOT_COORD = vector.new(0,0,0)
local DISTANCE_BETWEEN = 4 --Empty blocks between holes
local DIST_MOD = DISTANCE_BETWEEN + 1
local HOLE_BOTTOM = -59 -- Should be bedrock safe
local MIN_HOLE_FUEL = 50
local MIN_STARTING_FUEL = 500
local HOLES_BETWEEN_UNLOADS = 3

-- Used in the map generation to make sure we always do the correct square in front of the turtle
local XZ_MAP_MOD ={}
XZ_MAP_MOD[INS.Directions.NORTH] = {x=1 , z=-1}
XZ_MAP_MOD[INS.Directions.EAST]  = {x=1 , z=1}
XZ_MAP_MOD[INS.Directions.SOUTH] = {x=-1 , z=1}
XZ_MAP_MOD[INS.Directions.WEST]  = {x=-1 , z=-1}

local MAP_DIR = "/POKEY"
local MAP_FILE_BASE = "pokehole_map.json"
local STARTUP_DIR = "/startup"
local STARUP_FILE = "_pokey.lua"
local STARTUP_FILEPATH = string.format("%s/%s", STARTUP_DIR, STARUP_FILE)


---------------------------------
--- Static Functions
---------------------------------

local function copyVector(v)
    return vector.new(v.x, v.y, v.z)
end

-- Returns true if the coord should be mined
local function isPokeHole(coord)
    coord.x = coord.x + ROOT_COORD.x
    coord.z = coord.z - ROOT_COORD.z
    local x_mod = coord.x % DIST_MOD
    local x_z_comp = (x_mod == 0) and 0 or (DIST_MOD - x_mod)
    local x_z_mod = (coord.x + coord.z) % DIST_MOD
    return x_z_mod == x_z_comp
end

-- Function to reverse a table
local function reverseTable(t)
    local reversedTable = {}
    local n = #t
    for i = n, 1, -1 do
        table.insert(reversedTable, t[i])
    end
    return reversedTable
end

-- Function to append table2 to table1
local function appendTables(table1, table2)
    for _, value in ipairs(table2) do
        table.insert(table1, value)
    end
end

---------------------------------
--- Pokehole Map Class
---------------------------------

-- Define the class
PokeholeMap = {
    size = nil,
    start_coord = nil,
    holes = {},
    current_hole = nil
}
PokeholeMap.__index = PokeholeMap

-- Constructor
function PokeholeMap.new(size)
    local self = setmetatable({}, PokeholeMap)
    self.size = size
    self.start_coord = nav.home_coord
    
    -- Create a unique file to name this pokehole run
    self.map_filepath = string.lower(string.format("%s/%s_%s_%s_%s_%s" .. MAP_FILE_BASE,MAP_DIR, size, nav:getDisplayDir(nav.home_direction), self.start_coord.x, self.start_coord.y, self.start_coord.z))

    self:load()

    return self
end

function PokeholeMap:save()
    local ins_json = fs.open(self.map_filepath, "w")
    ins_json.write(textutils.serializeJSON(self.holes))
    ins_json.close()
end

function PokeholeMap:load()
    local holes_loaded
    if fs.exists(self.map_filepath) then
        local holes_json = fs.open(self.map_filepath, "r")
        if holes_json then
            holes_loaded = {}
            local raw_holes_loaded = textutils.unserializeJSON(holes_json.readAll())
            for _, raw_hole in pairs(raw_holes_loaded) do
                table.insert(holes_loaded, vector.new(raw_hole.x, raw_hole.y, raw_hole.z))
            end
        end
    end
    if holes_loaded then
        self.holes = holes_loaded
    else
        self:generate()
    end
end

-- Define a function to calculate the distance between two vectors
local function distance(vector1, vector2)
    local dx = vector1.x - vector2.x
    local dy = vector1.y - vector2.y
    local dz = vector1.z - vector2.z
    return math.sqrt(dx*dx + dy*dy + dz*dz)
end

-- Sort the table of vectors based on their distance to the previous vector
local function sortVectorsByDistance(previousVector, vectors)
    local sortedVectors = {}
    while #vectors > 0 do
        local closestVector
        local minDistance = math.huge
        for i, vector in ipairs(vectors) do
            local d = distance(previousVector, vector)
            if d < minDistance then
                closestVector = vector
                minDistance = d
            end
        end
        table.insert(sortedVectors, closestVector)
        previousVector = closestVector
        for i, vector in ipairs(vectors) do
            if vector == closestVector then
                table.remove(vectors, i)
                break
            end
        end
    end
    return sortedVectors
end

-- Define a custom sorting function
local function customSort(a, b)
    return distance(a, nav.home_coord) < distance(b, nav.home_coord)
end

-- Function to generate pokehole map
function PokeholeMap:generate()
    print("Generating pokehole map...")
    -- depending on which direction the turtle is facing need to change whether we are subtracting/adding
    local map_mod = XZ_MAP_MOD[nav.home_direction]
    local pokehole_map = {}

    local reverse = false
    for x_diff=0, self.size - 1 do
        local x = self.start_coord.x + (x_diff * map_mod.x)
        local z_map = {}
        for z_diff=0, self.size-1 do
            local z = self.start_coord.z + (z_diff * map_mod.z)
            local check_coord = vector.new(x, self.start_coord.y, z)
            if isPokeHole(check_coord) then
                table.insert(z_map, check_coord)
            end
        end

        if reverse then
            z_map = reverseTable(z_map)
        end
        reverse = not reverse
        appendTables(pokehole_map, z_map)
    end
    self.holes = pokehole_map

    -- Sort the table of vectors
    -- local sortedHoles = sortVectorsByDistance(nav.home_coord, self.holes)
    -- self.holes = sortedHoles

    self:save()
end

function PokeholeMap:completed()
    return (not self.holes or #self.holes <= 0)
end

function PokeholeMap:nextHole()
    if self.current_hole then
        table.remove(self.holes, 1)
    end
    self.current_hole = self.holes[1]
    self:save()
    if self.current_hole then
        return self.current_hole
    else
        print("No More Holes")
        fs.delete(self.map_filepath)
    end
end

function PokeholeMap:estimateFuel(hole_count)
    local fuel_estimate = 0

    -- Calculate fuel for holes
    local remaining_holes = #self.holes
    hole_count = hole_count or remaining_holes
    if hole_count > MIN_HOLE_FUEL then
        hole_count = MIN_HOLE_FUEL
    end
    fuel_estimate = fuel_estimate + (hole_count * (hole_height + 12))
    
    --Calculate return from bottom and top of every hole. This should ensure plenty of fuel.
    for holeNum = 1,#self.holes do
        if holeNum % 4 == 0 then
            local thisHole = self.holes[holeNum]
            local thisHoleBottom = vector.new(thisHole.x, HOLE_BOTTOM, thisHole.z)
            local manhattanVectorFromTop = self.start_coord:sub(thisHole)
            local manhattanVectorFromBottom = self.start_coord:sub(thisHoleBottom)
            fuel_estimate = fuel_estimate + math.abs(manhattanVectorFromTop.x) + math.abs(manhattanVectorFromTop.y) + math.abs(manhattanVectorFromTop.z)
            fuel_estimate = fuel_estimate + math.abs(manhattanVectorFromBottom.x) + math.abs(manhattanVectorFromBottom.y) + math.abs(manhattanVectorFromBottom.z)
        end
    end
    if fuel_estimate > turtle.getFuelLimit() then -- this is probably fine to keep in the event that somehow a MIN_HOLE_FUEL estimate exceeds the turtle's max capacity
        return turtle.getFuelLimit()
    else
        print("Fuel Est: "..fuel_estimate)
        return fuel_estimate
    end
end


---------------------------------
--- Main Loop/Functions
---------------------------------
local function refuel(amount)
    local fuelLevel = turtle.getFuelLevel()
    if fuelLevel == "unlimited" then
        return true
    end

    local needed = amount
    if turtle.getFuelLevel() < needed then
        for n = 1, 16 do
            if turtle.getItemCount(n) > 0 then
                turtle.select(n)
                if turtle.refuel(1) then
                    while turtle.getItemCount(n) > 0 and turtle.getFuelLevel() < turtle.getFuelLimit() do -- turtle.getFuelLevel() < needed
                        turtle.refuel(1)
                    end
                    if turtle.getFuelLevel() >= needed then
                        turtle.select(1)
                        return true
                    end
                end
            end
        end
        turtle.select(1)
        return false
    end

    return true
end

local function fuelCheck(minFuel, startup_check)
    if not refuel(minFuel) then
        if startup_check then
            returnAndEmpty() -- Go home if we don't have enough fuel
        end
        term.clear()
        term.setCursorPos(1, 1)
        print("FUEL REQUIRED")
        print(" Current Fuel:  " .. turtle.getFuelLevel())
        print("Required Fuel:  " .. minFuel)

        while not refuel(minFuel) do
            term.setCursorPos(1, 2)
            print(" Current Fuel:  " .. turtle.getFuelLevel())
            os.pullEvent("turtle_inventory")
        end
    end
end

local function empty()
    print("Emptying inventory")
    for slot = 1, 16 do
        if turtle.getItemDetail(slot) then
            turtle.select(slot)
            turtle.drop()
        end
    end
end

function returnAndEmpty()
    local saved_location = copyVector(nav.current_coord)
    nav:goTo(nav.home_coord, chest_direction)
    fuelCheck(pokehole_map:estimateFuel())
    empty()
    if not pokehole_map:completed() then
        nav:goTo(saved_location)
    else
        nav:goHome()
    end
end

local function createStartupFile()
    local startup_line = string.format("shell.run(\"%s %s\")", shell.getRunningProgram(), table.concat(tArgs, " "))
    print("Creating Startup file")
    local startup_file = fs.open(STARTUP_FILEPATH, "w")
    startup_file.write(startup_line)
    startup_file.close()
end

local function removeStartupFile()
    fs.delete(STARTUP_FILEPATH)
end

local function startup()
    fuelCheck(MIN_STARTING_FUEL)
    -- Initialize INS/nav object
    nav = INS.INS:new()

    hole_height = nav.home_coord.y - HOLE_BOTTOM

    chest_direction = INS.reverseDirection(nav.home_direction)
    -- Generate/Load PokeHole Map (Based on nav.home_coord and size)
    pokehole_map = PokeholeMap.new(size)

    fuelCheck(pokehole_map:estimateFuel(),true)
    -- This will do a fuel check as well
    -- Might as well have the turtle clean its inv

    createStartupFile()
end

local function checkInventory()
    if turtle.getItemDetail(16) then
        MINING.purgeInventory()
        if turtle.getItemDetail(16) then
            returnAndEmpty()
        end
    end
end

local function scan()
    turtle.select(1)
    if nav.direction == chest_direction and nav.current_coord:equals(nav.home_coord)  then
        return
    end
    MINING.scanDig()
    checkInventory()
end

local function scanLayer()
    checkInventory()
    nav:turnRight(4, scan)
end

local function bedrockPlunger()
    nav:down(5,scanLayer)
    while nav.current_coord.y ~= HOLE_BOTTOM do
        nav:up()
    end
end

local function doPokehole()
    scanLayer()
    if nav.current_coord.y == HOLE_BOTTOM then
        bedrockPlunger()
        nav:up(hole_height, scanLayer)
        MINING.scanDig("Up")
    else
        MINING.scanDig("Up")
        nav:down(hole_height, scanLayer)
        bedrockPlunger()
    end
end

local function minePokeHoles()
    local holesSinceLastUnload = 0

    -- Process Each Hole
    pokehole_map:nextHole()
    while pokehole_map.current_hole do
        local travelTo = copyVector(pokehole_map.current_hole)
        -- Figure out if I'm closer to the bottom or top (AKA "Am I high")
        travelTo.y = (math.abs(nav.current_coord.y - nav.home_coord.y) < math.abs(nav.current_coord.y - HOLE_BOTTOM)) and nav.home_coord.y or HOLE_BOTTOM

        -- Travel to the top or bottom of next pokehole
        if nav.current_coord.y == HOLE_BOTTOM then
            nav:goTo(travelTo,nil,function ()
                MINING.scanDig("Down")
            end)
        else
            nav:goTo(travelTo,nil,function ()
                MINING.scanDig("Up")
            end)
        end

        doPokehole()
        holesSinceLastUnload = holesSinceLastUnload + 1
        pokehole_map:nextHole()
        if holesSinceLastUnload > HOLES_BETWEEN_UNLOADS and nav.current_coord.y ~= HOLE_BOTTOM then
            holesSinceLastUnload = 0
            MINING.purgeInventory()
            returnAndEmpty()
        end
    end
end

local function cleanup()
    nav:clean()
    removeStartupFile()
end

local function main()
    local start_time = os.clock()
    
    -- Do the work
    minePokeHoles()
    -- End Back at the start
    returnAndEmpty()
    -- Cleanup
    cleanup()
    local end_time = os.clock()
    local duration = end_time - start_time
    print("Duration:",duration)
end


-- Initialize objects
startup()
parallel.waitForAny(
    main, 
    function ()
        nav:pingLoc()
    end
)



-- TODO
-- JUST RANDOM TEST CODE BELOW
-- Will clean up after development

-- local function testChunk()
--     -- Define the constant values
--     local y = 64
--     local min = 0
--     local max = 15

--     -- Initialize the list to store coordinates
--     local coordinates = {}
--     local file = fs.open("x_lines.txt", "w")
--     -- file.writeLine("0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5")

--     -- Loop through x and z coordinates
--     for x = min, max do
--         local x_str = ""
--         for z = min, max do
--             -- Add coordinates to the list as vectors
            
--             local coord = vector.new(x, y, z)
--             table.insert(coordinates, coord)
--             if isPokeHole(coord) then
--                 x_str = x_str .. "X "
--             else
--                 x_str = x_str .. "O "
--             end
--         end
        
--         file.writeLine(x_str)
--     end
-- end


-- testChunk()


