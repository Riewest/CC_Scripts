local squid = {}


local genericPackage = ";/DIR/?;/DIR/?.lua;/DIR/?/init.lua"
package.path = package.path .. genericPackage:gsub("%DIR", "squid")

squid.turtle = require("turtle")
squid.util = require("util")

function squid.testSquid()
    print("testSquid")
end

return squid