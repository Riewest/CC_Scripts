local args = {...}

local validBuildingBlocks = {
    ["minecraft:cobblestone"] = true,
    ["minecraft:cobbled_deepslate"] = true,
    ["minecraft:netherrack"] = true,
    ["minecraft:nether_bricks"] = true,
}
local validBuildingSlabs = {
    ["minecraft:cobblestone_slab"] = true,
    ["minecraft:cobbled_deepslate_slab"] = true,
    ["minecraft:nether_brick_slab"] = true
}

local block_type = "block"
local MIN_FUEL = 1200

local function isSpawner(block)
    return block.name == "minecraft:spawner"
end

local function refuelIfNeeded(minFuel)
    if turtle.getFuelLevel() == "unlimited" then return true end
    if turtle.getFuelLevel() >= minFuel then return true end

    print("FUEL REQUIRED")
    print("Current Fuel: " .. turtle.getFuelLevel())
    print("Required Fuel: " .. minFuel)

    print("Waiting for fuel...")
    while turtle.getFuelLevel() < minFuel do
        turtle.refuel()
        sleep(1)
    end

    print("Fuel check passed.")
    return true
end

local function searchForSpawner()
    term.clear()
    term.setCursorPos(1, 1)

    if not refuelIfNeeded(MIN_FUEL) then
        print("Insufficient fuel. Aborting.")
        return false
    end

    while true do
        -- Inspect block in front
        local success, block = turtle.inspect()
        if success and isSpawner(block) then
            return true
        end
        
        -- Try to move forward
        if turtle.forward() then
            -- keep searching
        else
            -- blocked, try moving up
            if turtle.up() then
                -- keep searching at new level
            else
                print("Can't move up. Search failed.")
                return false
            end
        end
    end
end

local function rt()
    turtle.turnRight()
end
local function lt()
    turtle.turnLeft()
end

local function du()
    turtle.digUp()
end
local function dd()
    turtle.digDown()
end
local function dud()
    turtle.digUp()
    turtle.digDown()
end

local function up(distance)
    distance = distance or 1
    for i=1,distance do
        while not turtle.up() do
            turtle.attackUp()
            turtle.digUp()
        end
    end
end
local function dn(distance)
    distance = distance or 1
    for i=1,distance do
        while not turtle.down() do
            turtle.attackDown()
            turtle.digDown()
        end
    end
end
local function fd(distance)
    distance = distance or 1
    for i=1,distance do
        while not turtle.forward() do
            turtle.attack()
            turtle.dig()
        end
    end
end
local function fddud(distance)
    distance = distance or 1
    for i=1,distance do
        while not turtle.forward() do
            turtle.attack()
            turtle.dig()
        end
        turtle.digUp()
        turtle.digDown()
    end
end

local function bk(distance)
    distance = distance or 1
    for i=1,distance do
        if not turtle.back() then
            while not turtle.back() do
                lt()
                lt()
                fd()
                lt()
                lt()
                
            end
        end
    end
end

-- Clears a 3-block tall area starting at turtle's current position, facing forward
local function clearArea(x, z)
    for row = 1, z do
        fddud(x - 1) -- Clear this row (minus 1 because we already occupy the first column)

        -- At end of row, decide if we should snake to next row
        if row < z then
            if row % 2 == 1 then
                rt()
                fddud(1)
                rt()
            else
                lt()
                fddud(1)
                lt()
            end
        end
    end
end


local function findValidBlock()
    local searchTable = {}
    if block_type == "block" then
        searchTable = validBuildingBlocks
    else
        searchTable = validBuildingSlabs
    end
    for slot = 1, 16 do
        local detail = turtle.getItemDetail(slot)
        if detail and searchTable[detail.name] then
            turtle.select(slot)
            return true
        end
    end
    return false
end

local function pbd()
    findValidBlock()
    local detail = turtle.getItemDetail()
    if not detail or (not validBuildingBlocks[detail.name] and not validBuildingSlabs[detail.name]) then
        if not findValidBlock() then
            print("No valid building block found!")
            return false
        end
    end
    for i=1,5 do
        if turtle.detectDown() or turtle.placeDown() then
            return true
        end
       sleep(1)
    end
    -- Placement failed and nothing to attack
    return false
end

local function pbu()
    findValidBlock()
    local detail = turtle.getItemDetail()
    if not detail or (not validBuildingBlocks[detail.name] and not validBuildingSlabs[detail.name]) then
        if not findValidBlock() then
            print("No valid building block found!")
            return false
        end
    end
    for i=1,5 do
        if turtle.detectUp() or turtle.placeUp() then
            return true
        end
        sleep(1)
    end
    -- Placement failed and nothing to attack
    return false
end

local function fdpbd(distance)
    distance = distance or 1
    for i = 1,distance do
        fd()
        pbd()
    end
end

local function buildArea(xSize, zSize)
    local direction = "right"

    for z = 1, zSize do
        for x = 1, xSize do
            pbd()
            if x < xSize then
                fd(1)
            end
        end

        -- Move to the next row if not on the last one
        if z < zSize then
            if direction == "right" then
                rt()
                fd(1)
                rt()
                direction = "left"
            else
                lt()
                fd(1)
                lt()
                direction = "right"
            end
        end
    end
end

-- Builds snaking rows of blocks with a 1-block gap between rows
local function buildRows(rowCount, colCount,dir)
    dir = dir or "d"
    local direction = "right"
    
    for row = 1, rowCount do
        for col = 1, colCount do
            if dir == "d" then
                pbd()
            else
                pbu()
            end
            if col < colCount then
                fd(1)
            end
        end

        if row < rowCount then
            -- Move to the next row with 1-block gap
            if direction == "right" then
                rt()
                fd(2)  -- 1 block to step over + 1 block gap
                rt()
                direction = "left"
            else
                lt()
                fd(2)
                lt()
                direction = "right"
            end
        end
    end
end

local function clearOutSpawner()
    lt()
    lt()
    fd(4)
    rt()
    fd(4)
    rt()
    up()
    clearArea(11,4)
    lt()
    fddud()
    lt()
    fddud(4)
    fd()
    du()
    fddud(5)
    rt()
    fddud(4)
    rt()
    clearArea(11,4)
    dn(3)
    rt()
    fddud(3)
    rt()
    clearArea(11,9)
end

local function placeBottomSlabs()
    block_type = "slab"
    dn(2)
    lt()
    fd()
    lt()
    buildRows(4,11,"up")
    rt()
    fd()
    pbu()
    fd(2)
    pbu()
    fd(2)
    pbu()
    rt()
    fd(10)
    rt()
    pbu()
    fd(2)
    pbu()
    fd(2)
    pbu()
    block_type = "block"
    fd(2)
    rt()
    up(2)
    fd()
end

local function placelayerOne()
    placeBottomSlabs()
    buildRows(5,9)
    fdpbd(2)
    lt()
    fdpbd()
    fd(5)
    fdpbd(2)
    lt()
    fdpbd()
    bk()
    rt()
    fdpbd()
    lt()
    fdpbd(12)
    lt()
    fdpbd()
    lt()
    fdpbd()
    bk()
    rt()
    fdpbd(8)
    lt()
    fdpbd()
    bk()
    rt()
    fdpbd()
    lt()
    fdpbd(12)


end

local function placeLayerTwo()
    up()
    lt()
    fd()
    lt()
    fd()
    lt()
    lt()
    bk()
    fdpbd(2)
    lt()
    fdpbd(2)
    fd(3)
    fdpbd(3)
    lt()
    fdpbd()
    bk()
    rt()
    fdpbd()
    lt()
    fdpbd(12)
    lt()
    fdpbd()
    lt()
    fdpbd()
    bk()
    rt()
    fdpbd(8)
    lt()
    fdpbd()
    bk()
    rt()
    fdpbd()
    lt()
    fdpbd(12)
    bk()
    lt()
    fd()
    lt()
    fd()
    buildRows(5,9)

end

local function placeLayerThree()
    fd()
    lt()
    fd()
    up()
    lt()
    block_type = "slab"
    buildRows(4,11)
    rt()
    fdpbd()
    fd()
    fdpbd()
    fd()
    fdpbd()
    rt()
    fd(10)
    rt()
    bk()
    fdpbd()
    fd()
    fdpbd()
    fd()
    fdpbd()
    lt()
    block_type = "block"
    fdpbd()
    rt()
    fdpbd(3)
    rt()
    fdpbd(12)
    rt()
    fdpbd(10)
    rt()
    fdpbd(12)
    rt()
    fdpbd(3)
    block_type = "slab"
    fdpbd(3)
end

local function placeLayerFour()
    block_type = "block"
    fd(2)
    rt()
    fd()
    up()
    buildRows(4,11)
    rt()
    fdpbd()
    fd()
    fdpbd()
    fd()
    fdpbd()
    rt()
    fd(10)
    rt()
    bk()
    fdpbd()
    fd()
    fdpbd()
    fd()
    fdpbd()
    lt()
    fdpbd()
    rt()
    fdpbd(3)
    rt()
    fdpbd(12)
    rt()
    fdpbd(10)
    rt()
    fdpbd(12)
    rt()
    fdpbd(3)
    fdpbd(3)
end

local function placeLayerSixFix()
    bk()
    rt()
    fd(5)
    fdpbd()
    fd(6)
    rt()
    fd(5)
    rt()
end

local function placeRoof()
    up()
    buildArea(13,11)
    lt()
    fd(5)
    lt()
    fd(13)
    dn(7)
end

local function main()
    term.clear()
    term.setCursorPos(1,1)

    if #args > 0 then
        print("Simple Blaze Farm Requirements:")
        print("-------------------------------")
        print("~8 stack blocks, ~2 stack slabs")
        print("1200 Fuel")
        print("")
        print("Valid Materials:")
        print("cobblestone, cobbled_deepslate")
        print("netherrack, nether brick")
        print("")
        print("Place on the ground inline with and facing the spawner. Try not to activate the spawner. Wait ~20 minutes.")
        return
    end

    if searchForSpawner() then
        clearOutSpawner()
        placelayerOne()
        placeLayerTwo()
        placeLayerThree()
        placeLayerFour()
        placeLayerFour()
        placeLayerFour()
        placeLayerSixFix()
        placeRoof()
        print("Enjoy your simple blaze farm!")
    else
        print("Spawner not found.")
    end
end

main()


