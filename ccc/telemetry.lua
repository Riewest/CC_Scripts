local function hasTool(left, right, pattern)
    local function matches(tool)
        return tool ~= nil and string.find(tool.name, pattern, 1, true) ~= nil
    end
    return matches(left) or matches(right)
end

local function getComputerState()
    local state = {
        id = os.getComputerID(),
        label = os.getComputerLabel(),
        cc_version = os.version(),
        uptime = os.clock(),
        day = os.day(),
        time = os.time(),
        is_turtle = turtle ~= nil,
        is_pocket = pocket ~= nil,
        peripherals = {},
    }

    local w, h = term.getSize()
    state.terminal = { width = w, height = h }

    for _, name in ipairs(peripheral.getNames()) do
        state.peripherals[name] = peripheral.getType(name)
    end

    if turtle then
        local left  = turtle.getEquippedLeft()
        local right = turtle.getEquippedRight()
        state.turtle = {
            fuel_level    = turtle.getFuelLevel(),
            fuel_limit    = turtle.getFuelLimit(),
            selected_slot = turtle.getSelectedSlot(),
            left_tool     = left,
            right_tool    = right,
            is_crafty     = hasTool(left, right, "crafting_table"),
            is_felling    = hasTool(left, right, "_axe"),
            is_farming    = hasTool(left, right, "_hoe"),
            is_mining     = hasTool(left, right, "pickaxe"),
            is_digging    = hasTool(left, right, "shovel"),
            is_melee      = hasTool(left, right, "sword"),
            is_ender      = hasTool(left, right, "wireless_modem_advanced"),
            is_wireless   = hasTool(left, right, "wireless_modem"),
            inventory     = (function()
                local inv = {}
                for slot = 1, 16 do
                    inv[slot] = turtle.getItemDetail(slot)
                end
                return inv
            end)(),
        }
    end

    return state
end

local function getComputerStateJSON()
    return textutils.serializeJSON(getComputerState())
end

local function saveStateToFile(filepath)
    filepath = filepath or "telemetry.json"
    local file = fs.open(filepath, "w")
    file.write(getComputerStateJSON())
    file.close()
end

return {
    getComputerState = getComputerState,
    getComputerStateJSON = getComputerStateJSON,
    saveStateToFile = saveStateToFile,
    sendTelemetry = sendTelemetry,
}
