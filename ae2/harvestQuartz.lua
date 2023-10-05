local clusters = {"ae2:quartz_cluster", "minecraft:amethyst_cluster"}
local sleep_time = 10
local function checkCluster(inspect, dig)
    local has_block, info = inspect()
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
    if peripheral.hasType("front", "inventory") then
        for i=1,16 do
            turtle.select(i)
            turtle.drop()
        end
    else
        checkCluster(turtle.inspect, turtle.dig)
        checkCluster(turtle.inspectUp,turtle.digUp)
        checkCluster(turtle.inspectDown,turtle.digDown)
    end
    sleep(sleep_time)
end