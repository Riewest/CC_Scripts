-- bamboo.lua
term.clear()
term.setCursorPos(1,1)
print("Spinning endlessly, fueled by bamboo dreams.")

-- Delay between spins (seconds)
local SPIN_DELAY = 0.5

-- Check if any slots are full
local function isInventoryFull()
  for i = 1, 16 do
    if turtle.getItemCount(i) == 0 then
      return false
    end
  end
  return true
end

-- Try to dump items down
local function dumpItemsDown()
  for i = 1, 16 do
    turtle.select(i)
    turtle.dropDown()
  end
  turtle.select(1)
end

-- Wait until there's space below
local function waitForSpace()
  while isInventoryFull() do
    print("Inventory full. Waiting for space...")
    dumpItemsDown()
    sleep(10)
  end
end

-- Main loop
while true do
  waitForSpace()

  -- Try to dig bamboo in front
  turtle.dig()

  -- Turn and repeat
  turtle.turnRight()
  sleep(SPIN_DELAY)

  -- Dump bamboo if we have any
  dumpItemsDown()
end
