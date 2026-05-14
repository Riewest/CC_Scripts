local getRadius = require("mining/pokeyHelper")
local radius = getRadius()
shell.run("mining/pokey.lua", tostring(radius), "55", "35", "15", "vanilla_ores")
