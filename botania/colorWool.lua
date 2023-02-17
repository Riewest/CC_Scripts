local place_ = "left"
local break_ = "right"
local color_1 = "bottom"
local redstone_input = "top"

function rsOn(side)
    redstone.setOutput(side, true)
end
function rsOff(side)
    redstone.setOutput(side, false)
end

rsOff(place_)
rsOff(break_)
rsOff(color_1)
sleep(.05)

function cycle()
while true do
    while redstone.getInput(redstone_input) do        
        term.clear()
        term.setCursorPos(1,1)
        print("Shutdown with redstone signal...")
        sleep(5)
    end
    term.clear()
    term.setCursorPos(1,1)
    rsOn(place_)
    sleep(.05)
    rsOn(color_1)
    sleep(.1)
    rsOn(break_)
    sleep(.05)
    rsOff(place_)
    rsOff(break_)
    rsOff(color_1)
    sleep(.05)
end
end

--while true do
    cycle()
--end
