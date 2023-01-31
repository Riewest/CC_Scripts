local stm = require("squid/turtle/movement")

local inv = {}

function inv.findEmptySlot(select)
    select = select or false
    for i=1, 16 do
        if turtle.getItemCount(i) <= 0 then
            if select then
                turtle.select(i)
                return i
            end
        end
    end
    return false
end

--Drops all the items in slotNum
--to the indicated side
function inv.dropSide(slotNum, side)
    turtle.select(slotNum)
    side = string.lower(side)
    success = false
    if side == "front" then
        success = turtle.drop()
    elseif side == "top" then
        success = turtle.dropUp()
    elseif side == "bottom" then
        success = turtle.dropDown()
    else
        success = turtle.drop()
    end
    return success
end


--Empty's the slots passed in through
--the array.
function inv.emptyInv(slotsToEmpty, side)
    oldSlot = turtle.getSelectedSlot()
    side = side or "back"
    stm.rotate(side)
    for k, slotNum in pairs(slotsToEmpty) do
        inv.dropSide(slotNum, side)
    end
    stm.reverseRotate(side)
    turtle.select(oldSlot)
end


--Empty's the entire inventory
-- to the passed side
function inv.emptyAllInv(side)
    local slots = {}
    for i = 1, 16 do
        table.insert(slots, i)
    end
    inv.emptyInv(slots, side)
end

return inv