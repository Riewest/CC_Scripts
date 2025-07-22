-- === Configurable functions ===
local digFunc = turtle.digUp
local dropFunc = turtle.drop
local inspectFunc = turtle.inspectUp

-- === Constants ===
local cobbleSlot = 1
local waitTime = 1 -- seconds
local displayY = 4  -- Line number to display BPS

-- === Startup Info ===
term.clear()
term.setCursorPos(1, 1)
print("Expecting cobblestone ABOVE.")
print("Expecting inventory IN FRONT.")
print("Starting cobble mining loop...")

-- === Utility ===
local function isCobblestone(detail)
    return detail and detail.name == "minecraft:cobblestone"
end

-- === Metrics ===
local blockCount = 0
local startTime = os.clock()

-- === Main Loop ===
while true do
    turtle.select(cobbleSlot)

    -- Try to dig cobble
    local success, data = inspectFunc()
    if success and isCobblestone(data) then
        if digFunc() then
            blockCount = blockCount + 1
        end
    end

    -- Drop into inventory
    while turtle.getItemCount(cobbleSlot) > 0 do
        if not dropFunc() then
            term.setCursorPos(1, displayY)
            print("Inventory full... waiting   ")
            sleep(waitTime)
        else
            break
        end
    end

    -- Display rate
    local elapsed = os.clock() - startTime
    local rate = elapsed > 0 and (blockCount / elapsed) or 0
    term.setCursorPos(1, displayY)
    print(string.format("Blocks mined: %d (%.2f BPS)   ", blockCount, rate))

    sleep(0.5)
end
