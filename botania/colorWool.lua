local place_ = "left"
local break_ = "right"
local color_1 = "bottom"


function rsOn(side)
    redstone.setOutput(side, true)
end
function rsOff(side)
    redstone.setOutput(side, false)
end

rsOff(place_)
rsOff(break_)
rsOff(color_1)
rsOff(color_2)
sleep(.05)

local toggle = true
function cycle()
while true do

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
    toggle = not toggle
end
end

--while true do
    cycle()
--end
