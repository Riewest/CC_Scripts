local args = {...}
local from_inv_name = args[1] or "left"
local to_inv_name = args[2] or "right"
local createStartup = args[3] or "-n" -- set this to "-s" to install startup file automatically


local function installStartup()
    if string.find(string.lower(createStartup), "-s") then
        local startupFile = fs.open("startup.lua", "w")
        local startupCommand = string.format("shell.run(\"/inv/fastTransfer\", \"%s\", \"%s\")", from_inv_name, to_inv_name)
        startupFile.write(startupCommand)
        startupFile.close()
    end
end

function preCheck()
    if not peripheral.isPresent(from_inv_name) then
        invError(from_inv_name .. " Inventory Not Found!")
    end
    if not peripheral.isPresent(to_inv_name) then
        invError(to_inv_name .. " Inventory Not Found!")
    end
end


function help()
    print("USAGE: transfer [fromSide] [toSide]")
    print(" -fromSide defaults to left")
    print(" -toSide defaults to right")
    print("")
    print("If you want to specify toSide")
    print("then you must give the from side")
    print("   Accepts valid computer sides")
end

function invError(message)
    print("")
    print("Error!")
    shell.run("peripherals")
    print("")
    error(message)
end



function main()
    preCheck()
    installStartup()
    local from_inv = peripheral.wrap(from_inv_name)
    local from_size = from_inv.size()
    local transferShells = {}
    for i=1, from_size do
        local id = multishell.launch({}, "/inv/singleSlotTransfer.lua", tostring(i), from_inv_name, to_inv_name)
        multishell.setTitle(id, "Slot: "..tostring(i))
        table.insert(transferShells, id)
    end
end

if string.find(string.lower(from_inv_name), "help") then
    help()
else
    main()
end