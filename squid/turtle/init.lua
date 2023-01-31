local genericPackage = ";/DIR/?;/DIR/?.lua;/DIR/?/init.lua"
package.path = package.path .. genericPackage:gsub("%DIR", "squid/turtle")

local turtle = {}

turtle.inv = require("squid/turtle/inventory")
turtle.mv = require("squid/turtle/movement")
turtle.gps = require("squid/turtle/gps")

return turtle
