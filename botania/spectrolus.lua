local args = {...}
local from_inv_name = args[1] or "left"
local to_inv_name = args[2] or "right"
local redstone_input = args[3] or "top"
local sleep_time = tonumber(args[4]) or 0


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

function preCheck()
    if not peripheral.isPresent(from_inv_name) then
        invError(from_inv_name .. " Inventory Not Found!")
    end
    if not peripheral.isPresent(to_inv_name) then
        invError(to_inv_name .. " Inventory Not Found!")
    end
end

function main()
    preCheck()
    local from_inv = peripheral.wrap(from_inv_name)
    local to_inv = peripheral.wrap(to_inv_name)
    local from_size = from_inv.size()
    local to_size = to_inv.size()
    while true do
        while redstone.getInput(redstone_input) do        
            term.clear()
            term.setCursorPos(1,1)
            print("Shutdown with redstone signal...")
            sleep(5)
        end
        term.clear()
        term.setCursorPos(1,1)
        print("Active...")
        for i=1,16 do
            local item = from_inv.getItemDetail(i)
            while item.count < 2 do
                term.clear()
                term.setCursorPos(1,1)
                print("Waiting for "..item.displayName.." in slot "..i..".")
                sleep(5)
                item = from_inv.getItemDetail(i)
                term.clear()
            end
            to_inv.pullItems(peripheral.getName(from_inv),i,1)
            sleep(sleep_time)
        end
    end
end

if string.find(string.lower(from_inv_name), "help") then
    help()
else
    main()
end
