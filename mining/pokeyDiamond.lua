if not turtle then
    error("Requires a Turtle")
    return
end

local tArgs = { ... }
if #tArgs ~= 1 then
    local programName = arg[0] or fs.getName(shell.getRunningProgram())
    print("Usage: " .. programName .. " <radius>")
    return
end

local radius = tonumber(tArgs[1])
if not radius or radius < 1 then
    print("Radius must be positive")
    return
end

shell.run("mining/pokey.lua", tostring(radius), "-39", "-59", "15", "vanilla_ores")
