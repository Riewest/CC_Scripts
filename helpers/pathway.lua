package.path = package.path .. ";/?;/?.lua;/?/init.lua;/squid/?;/squid/?.lua;/squid/turtle/?.lua;/squid/?/init.lua"
local args = {...}
local INS = require("INS")
-- local MINING = require("mining")

local nav = INS.INS:new()

-- Select the first slot that contains a block
function getBallastSlot()
    for slot = 1, 16 do
        local item = turtle.getItemDetail(slot)
        if item and item.name:find("minecraft:") and not item.name:find("_bucket") then
            turtle.select(slot)
            return item.count
        end
    end
    return false -- No block found
end

local function buildWalls()
    nav:turnRight()
    getBallastSlot()
    turtle.place()
    nav:turnRight()
    nav:turnRight()
    getBallastSlot()
    turtle.place()
    nav:turnRight()
end

local function buildPath()
    nav:up()
    while turtle.digUp() do
        sleep(0.1)
    end
    buildWalls()
    getBallastSlot()
    turtle.placeUp()
    nav:down()
    buildWalls()
    turtle.digDown()
    getBallastSlot()
    turtle.placeDown()
end

local function main()

    local x = args[1]
    local y = args[2]
    local z = args[3]
    term.clear()
    term.setCursorPos(1, 1)
    print("No coordinate given via arguments.")
    print("What is the end coordinate of the path?")
    x = x or INS.promptInteger("X: ")
    y = y or INS.promptInteger("Y: ")
    z = z or INS.promptInteger("Z: ")
    local finish_coord = vector.new(x, y, z)

    print("Starting:", nav:getDisplayCoord())
    print("Ending:", nav:getDisplayCoord(finish_coord))

    nav:goTo(finish_coord, nil, buildPath)

    -- Cleanup after yourself
    nav:clean()
end

parallel.waitForAny(main, function()
    nav:pingLoc()
end)
