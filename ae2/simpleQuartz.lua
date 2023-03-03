local cluster_name = "ae2:quartz_cluster"
local cluster_name_2 = "minecraft:amethyst_cluster"
local accelerator = "ae2:quartz_growth_accelerator"
local sleep_time = 10
local dropSide = "back" -- Set to nil for no dropping

function checkCluster(inspect, dig, get_dust)
    local b, info = inspect()

    if get_dust or info.name == cluster_name or info.name == cluster_name_2 then
        dig()
    end
end

function findAccelerator()
    for i=1,4 do
        local b, info = turtle.inspect()
        if info.name == accelerator then
            return true
        end
        turtle.turnLeft()
    end
    return false
end

while findAccelerator() do
    turtle.turnLeft()
    checkCluster(turtle.inspect, turtle.dig, true)
    turtle.turnLeft()
    turtle.turnLeft()
    checkCluster(turtle.inspect, turtle.dig)
    turtle.turnRight()
    checkCluster(turtle.inspectUp,turtle.digUp)
    checkCluster(turtle.inspectDown,turtle.digDown)
    if dropSide then
        for i=1,16 do
            turtle.select(i)
            turtle.drop()
        end
    end
    sleep(10)
end