cluster_name = "ae2:quartz_cluster"

function checkCluster(inspect, dig, get_dust)
    b, info = inspect()

    if get_dust or info.name == cluster_name then
        dig()
    end
end

while true do
    turtle.turnLeft()
    checkCluster(turtle.inspect, turtle.dig, true)
    turtle.turnRight()
    turtle.turnRight()
    checkCluster(turtle.inspect, turtle.dig)
    turtle.turnLeft()
    checkCluster(turtle.inspectUp,turtle.digUp)
    checkCluster(turtle.inspectDown,turtle.digDown)
    sleep(8)
end
