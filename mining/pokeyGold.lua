local getRadius = require("mining/pokeyHelper")
local radius = getRadius()
shell.run("mining/pokey.lua", tostring(radius), "-6", "-26", "15", "vanilla_ores")