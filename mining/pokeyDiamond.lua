local getRadius = require("mining/pokeyHelper")
local radius = getRadius()
shell.run("mining/pokey.lua", tostring(radius), "-39", "-59", "15", "vanilla_ores")