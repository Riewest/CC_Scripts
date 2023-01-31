local cluster_name = "ae2:quartz_cluster"
local sleep_time = 10
local dropSide = "back" -- Set to nil for no dropping


package.path = package.path .. ";/?;/?.lua;/?/init.lua"
st = require("squid/turtle")

function checkCluster(inspect, dig, get_dust)
    b, info = inspect()

    if get_dust or info.name == cluster_name then
        dig()
    end
end

while true do
    turtle.turnLeft()
    checkCluster(turtle.inspect, turtle.dig, true)
    st.mv.spin()
    checkCluster(turtle.inspect, turtle.dig)
    turtle.turnLeft()
    checkCluster(turtle.inspectUp,turtle.digUp)
    checkCluster(turtle.inspectDown,turtle.digDown)
    if dropSide then
        st.inv.emptyAllInv(dropSide)
    end
    sleep(10)
end