term.clear()
term.setCursorPos(1,1)
print("\"Mars will come to fear my botany powers\"")
print("    - Mark Watney")


local OUTPUT_INV = nil

local SEED_SLOT = 2
local SOIL_SLOT = 1
local MINUTE = 60
local SLEEP_TIME = 2 * MINUTE 

function find_output()
    local possible_outputs = { peripheral.find("inventory", function(name, p) 
        return string.find(name, "chest") or string.find(name, "barrel") or string.find(name, "interface")
    end) }
    local first_output = possible_outputs[1]
    if not first_output then
        error("Unable to find a valid output inventory")
    end
    OUTPUT_INV = first_output
end

function process_slot(to_inv, from_inv, from_slot)
    to_inv.pullItems(peripheral.getName(from_inv), from_slot)
end

function process_pot(pot)
    local contents = pot.list()
    contents[SEED_SLOT] = nil
    contents[SOIL_SLOT] = nil

    for from_slot,v in pairs(contents) do
        pcall(process_slot, OUTPUT_INV, pot, from_slot)
    end
end

function process_pots()
    local botany_pots = {peripheral.find("botanypots:botany_pot")}
    for _, pot in pairs(botany_pots) do
        process_pot(pot)
    end
end


function main()
    find_output()
    print("")
    print("Output Inv:", peripheral.getName(OUTPUT_INV))
    print("Seconds Between:", SLEEP_TIME)
    while true do
        pcall(process_pots)
        sleep(SLEEP_TIME)
    end
end

main()