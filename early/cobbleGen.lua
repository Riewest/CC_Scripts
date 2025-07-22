-- cobble_miner.lua

-- === Configurable functions ===
local digFunc = turtle.digUp
local dropFunc = turtle.drop
local inspectFunc = turtle.inspectUp

-- === Constants ===
local cobbleSlot = 1
local waitTime = 1 -- seconds

-- === Startup Info ===
term.clear()
term.setCursorPos(1,1)
print("Expecting cobblestone ABOVE the turtle.")
print("Expecting inventory (e.g., hopper) IN FRONT of the turtle.")
print("Starting cobble mining loop...")

-- === Optional: define what counts as cobblestone ===
local function isCobblestone(detail)
    return detail and detail.name == "minecraft:cobblestone"
end

while true do
    turtle.select(cobbleSlot)

    -- Inspect and dig cobble if present
    local success, data = inspectFunc()
    if success and isCobblestone(data) then
        digFunc()
    end

    -- Drop items forward into hopper
    while turtle.getItemCount(cobbleSlot) > 0 do
        if not dropFunc() then
            print("Waiting: inventory full...")
            sleep(waitTime)
        end
    end

    sleep(0.1)
end
