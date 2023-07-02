local clusters = {"ae2:quartz_cluster", "minecraft:amethyst_cluster"}
local sleep_time = 10
local dropSide = "back" -- Set to nil for no dropping


package.path = package.path .. ";/?;/?.lua;/?/init.lua"
st = require("squid/turtle")

function checkCluster(inspect, dig, get_dust)
    has_block, info = inspect()
    if has_block then
        for k, cluster_name in pairs(clusters) do
            if info.name == cluster_name then
                dig()
            end
        end
    end
end

while true do
    turtle.turnLeft()
    checkCluster(turtle.inspect, turtle.dig)
    st.mv.spin()
    checkCluster(turtle.inspect, turtle.dig)
    turtle.turnLeft()
    checkCluster(turtle.inspectUp,turtle.digUp)
    checkCluster(turtle.inspectDown,turtle.digDown)
    if dropSide then
        st.inv.emptyAllInv(dropSide)
    end
    sleep(sleep_time)
end
