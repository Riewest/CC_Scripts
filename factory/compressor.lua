-- === Configuration ===
local crafterSide = "top" -- Crafter is on this side
local chestSide = "left"  -- Chest is on this side
local pulseTime = 0.05

term.clear()
term.setCursorPos(1,1)

-- === Valid nugget items (add more if needed) ===
local validNuggets = {
    ["minecraft:iron_nugget"] = true,
    ["minecraft:gold_nugget"] = true,
    ["minecraft:copper_nugget"] = true,
    ["create:copper_nugget"] = true,
    ["create:zinc_nugget"] = true,
    ["create:brass_nugget"] = true
}

-- === Setup peripherals ===
local chest = peripheral.wrap(chestSide)
local crafter = peripheral.wrap(crafterSide)

if not chest or not chest.list then error("Chest not found on side: " .. chestSide) end
if not crafter or not crafter.pullItems then error("Crafter not found on side: " .. crafterSide) end

-- === Crafting Tracking ===
local totalCrafts = 0
local lastCrafted = "None"

-- === Helper Functions ===
local function findNuggets()
    local nuggets = {}
    for slot, item in pairs(chest.list()) do
        if validNuggets[item.name] then
            if not nuggets[item.name] then
                nuggets[item.name] = {}
            end
            table.insert(nuggets[item.name], {slot = slot, count = item.count})
        end
    end
    return nuggets
end

local function moveNineNuggets(nuggetName, sources)
    local moved = 0
    for _, src in ipairs(sources) do
        local toMove = math.min(9 - moved, src.count)
        for i = 1, toMove do
            chest.pushItems(crafterSide, src.slot, 1, moved + 1)
            moved = moved + 1
            if moved >= 9 then return true end
        end
    end
    return false
end

local function pulseCrafter()
    redstone.setOutput(crafterSide, true)
    sleep(pulseTime)
    redstone.setOutput(crafterSide, false)
end

local function updateStats(nuggetName)
    totalCrafts = totalCrafts + 1
    lastCrafted = nuggetName
end

local function drawStats()
    term.setCursorPos(1, 1)
    term.clearLine()
    term.write("Total Crafts: " .. totalCrafts)

    term.setCursorPos(1, 2)
    term.clearLine()
    term.write("Last: " .. lastCrafted)
end

-- === Main Loop ===
while true do
    local nuggets = findNuggets()
    local crafted = false
    for name, sources in pairs(nuggets) do
        local total = 0
        for _, s in ipairs(sources) do total = total + s.count end

        if total >= 9 then
            if moveNineNuggets(name, sources) then
                pulseCrafter()
                updateStats(name)
                crafted = true
            end
            break -- one craft per loop
        end
    end

    drawStats()
    if not crafted then
        sleep(1)
    else
        sleep(.1)
    end
end
