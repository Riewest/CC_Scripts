local mv = {}

-----------------------------
-- Variables
-----------------------------
local directions = {}
directions.up = "up"
directions.down = "down"
directions.forward = "forward"
directions.back = "back"
mv.directions = directions

-----------------------------
-- Movement
-----------------------------
function mv.spin()
    turtle.turnLeft()
    turtle.turnLeft()
end

--- distance = blocks to moveAmount
--- direction = directions array above
--- f = pass the handle to a function that should be called with every movement (i.e turtle.dig )
function mv.forceMove(distance, direction, f)
    distance = distance or 1
    direction = direction or directions.forward
    local dug = false
    if direction == directions.back then
        mv.spin()
    end
	for i=1, distance do
        local moved = false
		while not moved do
			if direction == directions.down then
				dug = turtle.digDown()
				moved = turtle.down()
            elseif direction == directions.up then
				dug = turtle.digUp()
				moved = turtle.up()
			elseif direction == directions.forward or direction == directions.back then
				dug = turtle.dig()
				moved = turtle.forward() 
			end
		end
        if f and type(f) == "function" then
            f()
        end
    end
    if direction == directions.back then
        mv.spin()
    end
    return dug
end


--Turns the turtle to the passed side
function mv.rotate(side)
    if not side then
        return
    elseif side == "back" then
        mv.spin()
    elseif side == "left" then
        turtle.turnLeft()
    elseif side == "right" then
        turtle.turnRight()
    end
end

   
--Turns the turtle opposite the 
-- passed side
function mv.reverseRotate(side)
    if not side then
        return
    elseif side == "back" then
        mv.spin()
    elseif side == "left" then
        turtle.turnRight()
    elseif side == "right" then
        turtle.turnLeft()
    end
end


return mv