local args = {...}
local from_inv_name = args[1] or "left"
local to_inv_name = args[2] or "right"
local sleep_cycle = tonumber(args[3]) or 0
local START_DELAY = 4
local sleep_display = tostring(sleep_cycle).." sec"

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
    print(message)
    --error(message)
end

function preCheck()
    if not peripheral.isPresent(from_inv_name) then
        invError(from_inv_name .. " Inventory Not Found!")
    end
    if not peripheral.isPresent(to_inv_name) then
        invError(to_inv_name .. " Inventory Not Found!")
    end
end

function process_slot(to_inv, from_inv, from_slot)
    to_inv.pullItems(peripheral.getName(from_inv), from_slot)
end

function process_invs()
    if peripheral.isPresent(to_inv_name) and peripheral.isPresent(from_inv_name) then
        local from_inv = peripheral.wrap(from_inv_name)
        local to_inv = peripheral.wrap(to_inv_name)
        for from_slot,v in pairs(from_inv.list()) do
            pcall(process_slot, to_inv, from_inv, from_slot)
        end
    end
end

function main()
    preCheck()
    print("Startup Delay", START_DELAY)
    sleep(START_DELAY)
    term.clear()
    term.setCursorPos(1,1)
    print("Transfering items:")
    print(from_inv_name,"-->",to_inv_name)
    print("Time:",sleep_display)
    while true do
        pcall(process_invs)
        sleep(sleep_cycle)
    end
end

function errorHandler(err)
    print("Error:", err)
    print("Rebooting in 5 seconds")
    sleep(5)
    os.reboot()
end

if string.find(string.lower(from_inv_name), "help") then
    help()
else
    xpcall(main, errorHandler)
end

