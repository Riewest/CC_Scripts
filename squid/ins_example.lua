package.path = package.path .. ";/?;/?.lua;/?/init.lua;/squid/?;/squid/?.lua;/squid/?/init.lua"
local INS = require("INS")
local nav = INS.INS:new()


parallel.waitForAny(
    function ()
        INS.runExample(nav)
    end, 
    function ()
        nav:pingLoc()
    end
)