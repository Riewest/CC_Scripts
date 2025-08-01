local completion = require "cc.completion"
-- Define constants for direction
local Directions = {}
Directions.NORTH = 0
Directions.EAST = 1
Directions.SOUTH = 2
Directions.WEST = 3
local DirectionLookup = {}
DirectionLookup[0] = "NORTH"
DirectionLookup[1] = "EAST"
DirectionLookup[2] = "SOUTH"
DirectionLookup[3] = "WEST"
local DirectionMod = {}
DirectionMod[0] = -1
DirectionMod[1] = 1
DirectionMod[2] = 1
DirectionMod[3] = -1
local AxisLookup = {}
AxisLookup.NORTH = "z"
AxisLookup.EAST = "x"
AxisLookup.SOUTH = "z"
AxisLookup.WEST = "x"
AxisLookup.UP = "y"
AxisLookup.DOWN = "y"

local BEDROCK_LEVEL = -60

local GPS_DIR = "/GPS"
local INS_FILE = "INS.json"
local INS_FILEPATH = string.format("%s/%s", GPS_DIR, INS_FILE)


-- Static function that gets called by the constructor to make sure things are setup
local function initINS()
    fs.makeDir(GPS_DIR)
end

local function tableContains(table, check_value)
    for _,value in pairs(table) do
        if value == check_value then
            return true
        end
    end
    return false
end

local function get_keys(t)
    local keys={}
    for key,_ in pairs(t) do
      table.insert(keys, key)
    end
    return keys
  end

local function promptChoice(prompt, table, match)
    local x,y = term.getCursorPos()
    local choice = nil
    if match then
        while not tableContains(table,choice) do
            term.setCursorPos(x,y)
            term.clearLine()
            write(prompt)
            choice = read(nil, table, function(text) return completion.choice(text, table) end)
        end
    else
        term.setCursorPos(x,y)
        term.clearLine()
        write(prompt)
        choice = read(nil, table, function(text) return completion.choice(text, table) end)
    end
    return choice
end

local function promptInteger(prompt)
    local x,y = term.getCursorPos()
    local input_int = nil
    while not input_int do
        term.setCursorPos(x,y)
        term.clearLine()
        write(prompt)
        local input_str = read()
        input_int = tonumber(input_str)
    end
    return input_int
end

local function promptLoad()
    term.clear()
    term.setCursorPos(1,1)
    print("What Direction Am I Facing?")
    print("NORTH, EAST, SOUTH, WEST")
    local str_direction = promptChoice("Facing: ", get_keys(Directions), true)
    print("Use F3 'Looking At' For the Next Inputs")
    local x = promptInteger("X: ")
    local y = promptInteger("Y: ")
    local z = promptInteger("Z: ")
    local ins_load = {}
    ins_load.current_coord = vector.new(x,y,z)
    ins_load.direction = Directions[str_direction]
    return ins_load
end

-- Static function for loading INS
local function fileLoad()
    local ins_json = fs.open(INS_FILEPATH, "r")
    local ins_load = {}
    ins_load.first_load = true
    if ins_json then
        ins_load = textutils.unserializeJSON(ins_json.readAll())
        ins_json.close()
        local coord_loaded = vector.new(ins_load.current_coord.x, ins_load.current_coord.y, ins_load.current_coord.z)
        local home_loaded = vector.new(ins_load.home_coord.x, ins_load.home_coord.y, ins_load.home_coord.z)
        ins_load.current_coord = coord_loaded
        ins_load.home_coord = home_loaded
        ins_load.first_load = false
    end
    return ins_load
end

local function gpsLoad()
    local success = false
    local function fmove()
        turtle.dig()
        return turtle.forward()
    end
    while not success do
        local needUp = true
        local first_coord = vector.new(gps.locate(GPS_TIMEOUT))
        if not first_coord then return false end
        for try = 1,4 do
            if fmove() then
                needUp = false
                break
            else
                turtle.turnRight()
            end
        end
        if not needUp then
            local second_coord = vector.new(gps.locate(GPS_TIMEOUT))

            local result = first_coord:sub(second_coord)
            local x = result.x
            local z = result.z
            local new_direction = nil
            if x > 0 then
                new_direction = Directions.WEST
            elseif x < 0 then
                new_direction = Directions.EAST
            end
            if z > 0 then
                new_direction = Directions.NORTH
            elseif z < 0 then
                new_direction = Directions.SOUTH
            end
            turtle.turnRight()
            turtle.turnRight()
            fmove()
            turtle.turnRight()
            turtle.turnRight()
            return {
                current_coord = first_coord,
                direction = new_direction
            }
        else
            turtle.digUp()
            turtle.up()
        end
    end
end

local function loadINS()
    term.clear()
    term.setCursorPos(1,1)
    print("Loading INS...")

    -- Primary key/values wiil overwrite secondary if the same key exists
    local function mergeTables(primary, secondary)
        for k,v in pairs(primary) do
            secondary[k] = v
        end
        return secondary
    end

    local loaded_ins = fileLoad() --This can return an empty table if no ins file exists
    
    loaded_ins.gps_available = (gps.locate(GPS_TIMEOUT) ~= nil and true or false) -- Initial Check For GPS
    if loaded_ins.gps_available then
        local gps_ins = gpsLoad()
        loaded_ins = mergeTables(gps_ins, loaded_ins)
    end

    local valid = true
    local function invalidate()
        while true do
            local event, key, is_held = os.pullEvent("key")
            if key == keys.space or key == keys.enter then
                valid = (key ~= keys.space)
                return
            end
        end
    end 

    local function continue()
        local x,y = term.getCursorPos()
        local timer = 10
        for i=timer, 1, -1 do
            term.setCursorPos(x,y)
            term.clearLine()
            print("Continuing in " .. tostring(i))
            sleep(1)
        end
    end

    if not loaded_ins.gps_available and fs.exists(INS_FILEPATH) then
        print(INS_FILEPATH .. " detected")
        print("Press 'spacebar' to invalidate")
        print("Press 'enter' to keep")
        parallel.waitForAny(invalidate, continue)
        sleep(.1)
    end

    if not valid or not loaded_ins.current_coord then
        local prompt_ins = promptLoad()
        loaded_ins.home_coord = nil
        loaded_ins.home_direction = nil
        loaded_ins.first_load = true
        loaded_ins = mergeTables(prompt_ins, loaded_ins)
    end

    if not loaded_ins.home_coord or not loaded_ins.home_direction then
        loaded_ins.home_coord = vector.new(loaded_ins.current_coord.x, loaded_ins.current_coord.y, loaded_ins.current_coord.z)
        loaded_ins.home_direction = loaded_ins.direction
    end

    return loaded_ins
end

local function reverseDirection(d)
    return (d + 2 % 4)
end


-- Define class
local INS = {
    current_coord = nil,
    home_coord = nil,
    direction = nil,
    home_direction = nil
}

-- Constructor
function INS:new(force_move)
    initINS()
    local obj = loadINS()
    setmetatable(obj, self)
    self.__index = self
    obj.force_move = force_move or true
    obj:save()
    return obj
end


function INS:save()
    local save_data = {}
    save_data.current_coord = self.current_coord
    save_data.direction = self.direction
    save_data.home_coord = self.home_coord
    save_data.home_direction = self.home_direction

    local ins_json = fs.open(INS_FILEPATH, "w")
    ins_json.write(textutils.serializeJSON(save_data))
    ins_json.close()
end

function INS:gpsFix()
    local x, y, z = gps.locate(GPS_TIMEOUT)
    if x and y and z then
        self.current_coord = vector.new(x, y, z)
        self:save()
    end
end

function INS:gpsFixFace()
    -- print("Getting facing direction...")
    local success = false
    while not success do
        local needUp = true
        local first_coord = vector.new(gps.locate(GPS_TIMEOUT))
        if not first_coord then return false end
        for try = 1,4 do
            if self:forward() then
                needUp = false
                break
            else
                self:turnRight()
            end
        end
        if not needUp then
            local second_coord = vector.new(gps.locate(GPS_TIMEOUT))
        
            local result = first_coord:sub(second_coord)
            local x = result.x
            local z = result.z
            local new_direction = nil
            if x > 0 then
                new_direction = Directions.WEST
            elseif x < 0 then
                new_direction = Directions.EAST
            end
            if z > 0 then
                new_direction = Directions.NORTH
            elseif z < 0 then
                new_direction = Directions.SOUTH
            end
            if new_direction then
                self.direction = new_direction
                self:save()
            end
            self:turnRight(2)
            self:forward()
            self:turnRight(2)
        else
            self:up()
        end
    end
end


-- function INS:move(moveFunc, digFunc, coordKey, coordChange, distance, action)
--     distance = distance or 1
--     for m = 1, distance do
--         while not moveFunc() do
--             if self.force_move then
--                 digFunc()
--             end
--         end
--         self.current_coord[coordKey] = self.current_coord[coordKey] + coordChange
--         self:save()
--         if action then
--             action()
--         end
--     end
-- end

function INS:move(moveFunc, digFunc, coordKey, coordChange, distance, action)
    distance = distance or 1
    for m = 1, distance do
        local success = false
        for attempt = 1, 10 do
            if moveFunc() then
                success = true
                break
            elseif self.force_move and digFunc then
                digFunc()
            end
        end
        if not success then
            -- print("Failed to move after 10 attempts.")
            return false
        end
        self.current_coord[coordKey] = self.current_coord[coordKey] + coordChange
        self:save()
        if action then
            action()
        end
    end
    return true
end

-- Method to move up
function INS:up(distance, action)
    return self:move(turtle.up, turtle.digUp, "y", 1, distance, action)
end

-- Method to move down
function INS:down(distance, action)
    return self:move(turtle.down, turtle.digDown, "y", -1, distance, action)
end

-- Method to move forward
function INS:forward(distance, action)
    local coordKey, coordVal
    if self.direction == Directions.EAST then
        coordKey, coordVal = "x", 1
    elseif self.direction == Directions.WEST then
        coordKey, coordVal = "x", -1
    elseif self.direction == Directions.NORTH then
        coordKey, coordVal = "z", -1
    elseif self.direction == Directions.SOUTH then
        coordKey, coordVal = "z", 1
    end
    return self:move(turtle.forward, turtle.dig, coordKey, coordVal, distance, action)
end


function INS:turn(turnFunc, turnVal, amount, action)
    amount = amount or 1
    for i = 1, amount do
        turnFunc()
        self.direction = (self.direction + turnVal) % 4
        self:save()
        if action then
            action()
        end
    end
end

function INS:turnRight(amount, action)
    self:turn(turtle.turnRight, 1, amount, action)
end

function INS:turnLeft(amount, action)
    self:turn(turtle.turnLeft, -1, amount, action)
end

-- Turn to a cardinal direction
-- (Needs to passed the correct direction const from above)
function INS:turnDir(direction)
    local turn_ammount = (direction - self.direction) % 4
    if turn_ammount > 2 then
        self:turnLeft(4 - turn_ammount)
    else
        self:turnRight(turn_ammount)
    end
end

function INS:goTo(coord, direction, action)
    if not coord then
        return false -- Return false if no coord given
    end

    while self.current_coord.y <= BEDROCK_LEVEL do
        self:up()
    end

    local travel = coord:sub(self.current_coord)

    -- Travel X change First
    if travel.x > 0 then
        self:turnDir(Directions.EAST)
    elseif travel.x < 0 then
        self:turnDir(Directions.WEST)
    end
    self:forward(math.abs(travel.x),action)

    -- Travel Z change Second
    if travel.z > 0 then
        self:turnDir(Directions.SOUTH)
    elseif travel.z < 0 then
        self:turnDir(Directions.NORTH)
    end
    self:forward(math.abs(travel.z),action)
    
    -- Travel Y change Third
    if travel.y > 0 then
        self:up(travel.y)
    elseif travel.y < 0 then
        self:down(math.abs(travel.y))
    end

    direction = direction or self.direction
    self:turnDir(direction)
    return true
end

function INS:getDirMod(dir)
    dir = dir or self.direction
    return DirectionMod[dir]
end

-- Allow programs to set a new home coord/direciton if they want to
function INS:setHome(home_coord, home_direction)
    self.home_coord = home_coord or self.current_coord
    self.home_direction = home_direction or self.direction
    self:save()
end

function INS:goHome()
    self:goTo(self.home_coord, self.home_direction)
end

function INS:isFirstLoad()
    return self.first_load
end

function INS:clean()
    if fs.exists(INS_FILEPATH) then
        fs.delete(INS_FILEPATH)
    end
end

function INS:getDisplayCoord()
    return string.format("%s, %s, %s", self.current_coord.x, self.current_coord.y, self.current_coord.z)
end

function INS:getDisplayDir(dir)
    dir = dir or self.direction
    return DirectionLookup[dir]
end

function INS:getAxis(dir)
    dir = dir or self.direction
    return AxisLookup[DirectionLookup[dir]]
end

function INS:printLoc()
    print(self:getDisplayCoord(), self:getDisplayDir())
end


-- Example usage:
local function runExample()
    
    -- Add two lines to the top of the file to include this
    -- package.path = package.path .. ";/?;/?.lua;/?/init.lua;/squid/?;/squid/?.lua;/squid/?/init.lua"
    -- local INS = require("INS") 

    -- First thing any program using INS should do is make an INS object
    -- This will load the coords from file, gps, or prompt
    -- If this is a first load then the home_coord/direction will default to current location
    local nav = INS:new()
    nav:printLoc()

    -- If INS was loaded from file (or gps & file) then this will be considered the "first run" of any program
    if nav:isFirstLoad() then
        print("Doing my first run code here")
        -- You can override the home coord/direction
        -- nav:setHome(new_coord, new_direction)
    end

    -- There are normal turtle.MOVEFUNC options available but you can pass in optional amounts and action func per move
    nav:forward(5)
    nav:up(2)

    -- you can travel to a specific coordinate
    -- local test_coord = vector.new(-75, -51, 40)
    -- nav:goTo(test_coord, Directions.WEST)

    -- You can go back to the home coord/direction
    -- Some programs might want to overwrite this because it doesn't
    --  do it with any aproach context (i.e. could break things coming from a certain side)
    nav:goHome()

    -- The last thing the program should do is call clean so that the next run of the program is still considered a "first run"
    nav:clean()
end


return {
    INS = INS,
    Directions = Directions,
    reverseDirection = reverseDirection,
    runExample = runExample
}

