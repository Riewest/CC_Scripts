local args = {...}
local from_inv_name = args[1] or "left"
local to_inv_name = args[2] or "right"
local slots_per_thread = tonumber(args[3]) or 5 
local createStartup = args[4] or "-n" -- set this to "-s" to install startup file automatically


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

function getSlotRanges()
    local from_inv = peripheral.wrap(from_inv_name)
    local from_size = from_inv.size()
    local slotRanges = {}
    local numFullRange = math.floor(from_size / slots_per_thread)
    local leftover = from_size % slots_per_thread
    local slot = 1
    for i=slot, from_size - leftover, slots_per_thread do
        local range = {}
        range.start_slot = i
        range.end_slot = i + slots_per_thread - 1
        table.insert(slotRanges, range)
        slot = i + slots_per_thread
    end
    if leftover > 0 then
        local range = {}
        range.start_slot = slot
        range.end_slot = slot + leftover - 1
        table.insert(slotRanges, range)
    end
    return slotRanges
end

function main()
    preCheck()
    installStartup()
    local from_inv = peripheral.wrap(from_inv_name)
    local slotRanges = getSlotRanges()
    local transferShells = {}
    for _, range in pairs(slotRanges) do
        local id = multishell.launch({}, "/inv/slotRangeTransfer.lua", tostring(range.start_slot), tostring(range.end_slot), from_inv_name, to_inv_name)
        multishell.setTitle(id, tostring(range.start_slot).."->"..tostring(range.end_slot))
        table.insert(transferShells, id)
    end
end


if string.find(string.lower(from_inv_name), "help") then
    help()
else
    main()
end