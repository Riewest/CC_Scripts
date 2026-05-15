local function isTurtle()
    return turtle ~= nil
end

local function isPocket()
    return pocket ~= nil
end

local function isAdvanced()
    return term.isColour()
end

local function hasTool(pattern)
    if not isTurtle() then return false end
    local left  = turtle.getEquippedLeft()
    local right = turtle.getEquippedRight()
    local function matches(tool)
        return tool ~= nil and string.find(tool.name, pattern, 1, true) ~= nil
    end
    return matches(left) or matches(right)
end

local function isMining()
    return hasTool("pickaxe")
end

local function isCrafty()
    return hasTool("crafting_table")
end

local function isFelling()
    return hasTool("_axe")
end

local function isFarming()
    return hasTool("_hoe")
end

local function isDigging()
    return hasTool("shovel")
end

local function isMelee()
    return hasTool("sword")
end

local function isEnder()
    return hasTool("wireless_modem_advanced")
end

local function isWireless()
    return hasTool("wireless_modem")
end

local function getLabel()
    return os.getComputerLabel() or ("Unnamed Computer #" .. tostring(os.getComputerID()))
end

local STATUS_FILE = "/.status"
local STATUSES = require("status")

local function setStatus(status)
    if not STATUSES[status:upper()] then
        error("telemetry: invalid status: " .. tostring(status), 2)
    end
    local ok, err = pcall(function()
        local file = fs.open(STATUS_FILE, "w")
        file.write(textutils.serializeJSON(status))
        file.close()
    end)
    if not ok then
        printError("telemetry: failed to write status: " .. tostring(err))
    end
end

local function getStatus()
    if not fs.exists(STATUS_FILE) then return nil end
    local ok, result = pcall(function()
        local file = fs.open(STATUS_FILE, "r")
        local raw = file.readAll()
        file.close()
        return textutils.unserializeJSON(raw)
    end)
    if ok then return result else return nil end
end

local function clearStatus()
    if fs.exists(STATUS_FILE) then
        fs.delete(STATUS_FILE)
    end
end


local function getComputerState()
    local state = {
        id = os.getComputerID(),
        label = getLabel(),
        cc_version = os.version(),
        uptime = os.clock(),
        day = os.day(),
        time = os.time(),
        is_turtle = isTurtle(),
        is_pocket = isPocket(),
        is_advanced = isAdvanced(),
        peripherals = {},
        status = getStatus(),
    }

    local w, h = term.getSize()
    state.terminal = { width = w, height = h }

    for _, name in ipairs(peripheral.getNames()) do
        state.peripherals[name] = peripheral.getType(name)
    end

    if isTurtle() then
        local left  = turtle.getEquippedLeft()
        local right = turtle.getEquippedRight()
        state.turtle = {
            fuel_level    = turtle.getFuelLevel(),
            fuel_limit    = turtle.getFuelLimit(),
            selected_slot = turtle.getSelectedSlot(),
            left_tool     = left,
            right_tool    = right,
            is_crafty     = isCrafty(),
            is_felling    = isFelling(),
            is_farming    = isFarming(),
            is_mining     = isMining(),
            is_digging    = isDigging(),
            is_melee      = isMelee(),
            is_ender      = isEnder(),
            is_wireless   = isWireless(),
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


local function telemetryParams()
    return {
        computerID = os.getComputerID(),
        computerLabel = getLabel(),
        status = getStatus(),
        isMining = isMining(),
        isCrafty = isCrafty(),
        isFelling = isFelling(),
        isFarming = isFarming(),
        isDigging = isDigging(),
        isMelee = isMelee(),
        isEnder = isEnder(),
        isWireless = isWireless(),
        isAdvanced = isAdvanced(),
        isTurtle = isTurtle(),
        isPocket = isPocket()
    }
end

return {
    getComputerState = getComputerState,
    getComputerStateJSON = getComputerStateJSON,
    saveStateToFile = saveStateToFile,
    telemetryParams = telemetryParams,
    setStatus = setStatus,
    getStatus = getStatus,
    clearStatus = clearStatus,
    isMining = isMining,
    isCrafty = isCrafty,
    isFelling = isFelling,
    isFarming = isFarming,
    isDigging = isDigging,
    isMelee = isMelee,
    isEnder = isEnder,
    isWireless = isWireless,
    isAdvanced = isAdvanced,
    isTurtle = isTurtle,
    isPocket = isPocket,
}
