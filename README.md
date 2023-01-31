# CC_Scripts

A common place for my computercraft scripts. Use the [sgit](sgit.lua) script to download all scripts to a computercraft computer

<!-- TODO: Upload sgit to pastebin when stable and insert code here -->
## Setup Computer/Turtle
Run the following
```lua
pastebin get HuSsRvQw sgit.lua
sgit
-- Optionally run: sgit DIFFERENT_BRANCH
```

## Info
- ### [./squid](squid/)
  This is a common library for alot of the scripts in here and where new common code should be added. One of the more useful things in this library is the `squid.turtle.gps.goTo()` function which will allow the turtle to move to the given destination.

  **Important: If you are loading this library from a separate sub directory you need to add the root dir to the package.path. See example below.**
  ```lua
  -- Adds the root dir "/" to the lua path and loads squid
  package.path = ";/?;/?.lua;/?/init.lua" .. package.path
  local squid = require("squid")
  ```

  Example Imports:
  ```lua
  local squid = require("squid") -- Access to everything in the squid library
  squid.util.findModem() -- Example Usage


  local sturtle = require("squid/turtle") -- Access to everything in the turtle sub directory
  sturtle.inv.findEmptySlot() -- Example Usage


  local mygps = require("squid/turtle/gps") -- Access to only the turtle gps functions
  mygps.gpsInit() -- Should be called when a turtle is turned on
  local newLocation = vector.new(10,66,10)
  local travelHeight = newLocation.y + 5
  mygps.goTo(newLocation, travelHeight, "south") -- Travel to the above coords and face south when it gets there
  ```

- ### [./helpers](helpers/) 
  Useful one off scripts (example: gps-deploy)

- ### [./ae2](ae2/) 
  Programs for use with AppliedEnergistics2 mod

- ### [./pastebins](pastebins/) 
  Programs that also need to be kept up to date on pastebin

- ### [./tests](tests/) 
  Programs that are ran to test another's program functionality or show things are working as they should
