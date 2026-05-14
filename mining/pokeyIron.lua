local getRadius = require("mining/pokeyHelper")
local radius = getRadius()
shell.run("mining/pokey.lua", tostring(radius), "24", "4", "15", "vanilla_ores")
