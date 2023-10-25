local expect = require "cc.expect"
local completion = require "cc.completion"
local expect, field, range = expect.expect, expect.field, expect.range

YES_NO_CHOICE = {"yes", "no"}


-- Merge table2 into table1
local function mergeTables(table1, table2)
    for key, value in pairs(table2) do
        table1[key] = value
    end
end

local function parsePeripheralName(p)
    if type(p) == "table" then
        p = peripheral.getName(p)
    end
    -- Match mod
    local mod = p:match("([^:]+)")
    
    -- Match name
    local name = p:match(":(.-)_%d")
    
    -- Match number
    local number = p:match("(%d+)$")
    return mod, name, number
end

local function move_from(fromInvName, fromSlot, toInv, toSlot, count)
    local fromInv = peripheral.wrap(fromInvName)
    fromInv.pushItems(peripheral.getName(toInv), fromSlot, count, toSlot)
end

local function getItem(invName, slot_info, machine)
    local inv = peripheral.wrap(invName)
    local items = inv.list()
    for slot, item in pairs(items) do
        if item then
            local moveItem, moveCount = slot_info.filter_func(inv, slot, item, machine)
            if moveItem then -- Run the filter function if it exists, pass in the inv, slot and item variables
                item.slot = slot -- Injects the slot into the item table because thats useful
                return item, moveCount
            end
        end
    end
end

local function slotHasItem(p, slot)
    return p.getItemDetail(slot)
end

local function defaultFilter(inv, slot, item)
    return true, nil
end

local function reprintLine(line,...)
    local x,y = term.getCursorPos()
    local print_string = table.concat(arg, " ")
    term.setCursorPos(1,line)
    term.clearLine()
    print(print_string)
    term.setCursorPos(x,y)
end

local function getNonMachineInvs(machine_id)
    local inventories = {}
    peripheral.find("inventory", function(name, modem)
        if not string.find(name, machine_id) then
            table.insert(inventories, name)
        end
    end)
    return inventories
end

local function validateInventory(name, allow_nil)
    local present = (type(name) == "string" and peripheral.isPresent(name))
    if allow_nil then
        present = present or type(name) == "nil"
    end
    return present
end

local function tableContains(table, check_value)
    for _,value in pairs(table) do
        if value == check_value then
            return true
        end
    end
    return false
end

local function promptChoice(prompt, table, match)
    write(prompt)
    local x,y = term.getCursorPos()
    local choice = ""
    if match then
        while not tableContains(table,choice) do
            term.setCursorPos(x,y)
            choice = read(nil, table, function(text) return completion.choice(text, table) end)
            choice = string.lower(choice)
        end
    else
        term.setCursorPos(x,y)
        choice = read(nil, table, function(text) return completion.choice(text, table) end)
        choice = string.lower(choice)
    end
    return choice
end


local Schema = {}
Schema.__index = Schema

function Schema.new(name, machine_id, peripheral_type)
    local self = setmetatable({}, Schema)
    expect(1, name, "string")
    expect(2, machine_id, "string")
    expect(3, peripheral_type, "string", "nil")
    self.schema_name = name
    self.machine_id = machine_id
    self.peripheral_type = peripheral_type or "inventory"
    self.output_slots = nil
    self.input_slots = nil
    self.extra_slots = nil
    return self
end

function Schema:validate()
    print("Validating Schema...")
    expect("schema_name", self.schema_name, "string")
    expect("machine_id", self.machine_id, "string")
    expect("peripheral_type", self.peripheral_type, "string")
    print("Valid Machine Schema")
    sleep(2)
end

function Schema:getDisplayName()
    return self.machine_id
end

function Schema:addSlots(key, slots, filter_func)
    expect(1, key, "string")
    expect(2, slots, "number", "table")
    expect(3, filter_func, "function", "nil")
    if type(slots) == "number" then
        range(slots, 1, 1000)
        slots = {slots}
    end
    local verbose_slots = self[key] or {}
    for k,slot_num in pairs(slots) do
        local slot = {
            number = slot_num,
            filter_func = filter_func or defaultFilter
        }
        verbose_slots[slot_num] = slot
    end
    self[key] = verbose_slots
end

function Schema:addOutputSlots(...)
    self:addSlots("output_slots", ...)
end

function Schema:addInputSlots(...)
    self:addSlots("input_slots", ...)
end

function Schema:addExtraSlots(...)
    self:addSlots("extra_slots", ...)
end

-- Printing Slots is mostly for debug purposes
function Schema:printSlots(key)
    if self[key] then
        for k,v in pairs(self[key]) do
            print(key, k, v.number, v.filter_func)
        end 
    end
end
function Schema:printOutputSlots()
    self:printSlots("output_slots")
end
function Schema:printInputSlots()
    self:printSlots("input_slots")
end

function Schema:printExtraSlots()
    self:printSlots("extra_slots")
end

local Processor = {}
Processor.DEFAULT_SETTINGS = {
    output_inv = nil,
    input_inv = nil,
    extra_inv = nil
}
Processor.__index = Processor

function Processor:new(name, schema)
    local self = setmetatable({}, Processor)
    expect(1, name, "string")
    expect(2, schema, "table")
    self.name = name
    self.schema = schema
    self.machines = {}
    self.process_time = 1
    self.configured = false
    self.settings = Processor.DEFAULT_SETTINGS
    self:init()
    return self
end

function Processor:getSettingsFilepath()
    local dir = "machines/settings"
    local filename = self.schema.machine_id
    local filepath = string.format("%s/%s", dir, filename)
    return dir, filename, filepath
end

function Processor:saveSettings()
    local dir, filename, filepath = self:getSettingsFilepath()
    fs.makeDir(dir)
    local processorSettings = fs.open(filepath, "w")
    processorSettings.write(textutils.serializeJSON(self.settings))
    processorSettings.close()
    self.configured = true
end

function Processor:loadSettings()
    local dir, filename, filepath = self:getSettingsFilepath()
    local processorSettings = fs.open(filepath, "r")
    if processorSettings then
        local savedSettings = textutils.unserializeJSON(processorSettings.readAll())
        processorSettings.close()
        self.settings = savedSettings
        self.configured = true
    end
end

function Processor:init()
    self.schema:validate()
    self:loadSettings() -- load in any saved settings
    self:setupInventories()
    self:findMachines()
end

function Processor:setupInventories()
    term.clear()
    term.setCursorPos(1,1)
    if not self.configured then
        while not self:validateInventories() do
            print("Invalid or Missing Inventories")
            print("Proceeding With Setup...")

            self:setupOutput()
            self:setupInput()
            self:setupExtra()
        end
        self:saveSettings()
    end

end

function Processor:validateInventories()
    local output_valid = validateInventory(self.settings.output_inv)
    local input_valid = validateInventory(self.settings.input_inv)
    local extra_valid = validateInventory(self.settings.extra_inv, true)
    local one_valid = input_valid or output_valid
    local valid_if_set = extra_valid and one_valid
    return valid_if_set
end

function Processor:setProcessTime(process_time)
    expect(1, process_time, "number")
    range(process_time, -1, 3600)
    self.process_time = process_time
end

function Processor:findMachines()
    self.machines = { peripheral.find(self.schema.peripheral_type, function(n, p)
        return string.match(n, self.schema.machine_id)
    end) }
end

function Processor:setupInventory(inv_key)
    local prompt = string.format("Need an '%s' (yes/no): ", inv_key)
    if promptChoice(prompt, YES_NO_CHOICE, true) == "yes" then
        prompt = string.format("Select or Connect %s: ", inv_key)
        local potentialIO = getNonMachineInvs(self.schema.machine_id)
        local choice = promptChoice(prompt, potentialIO, true)
        print("")
        print("Choice:", choice)
        self.settings[inv_key] = choice
    end
end

function Processor:setupOutput()
    self:setupInventory("output_inv")
end
function Processor:setupInput()
    self:setupInventory("input_inv")
end
function Processor:setupExtra()
    self:setupInventory("extra_inv")
end

function Processor:setOutputInv(output_inv)
    self.settings.output_inv = output_inv
end

function Processor:setInputInv(input_inv)
    self.settings.input_inv = input_inv
end

function Processor:setExtraInv(extra_inv)
    self.settings.extra_inv = extra_inv
end

function Processor:staticPrint()
    term.clear()
    reprintLine(1, "Program Info:")
    reprintLine(2, "  Name:        ", self.schema.schema_name)
    reprintLine(3, "  Count:       ", #self.machines)
    reprintLine(5, "  Input Inv:   ", self.settings.input_inv)
    reprintLine(6, "  Output Inv:  ", self.settings.output_inv)
    reprintLine(7, "  Extra Inv:   ", self.settings.extra_inv)
end

function Processor:printSingleMachine(machine)
    local mod, name, number = parsePeripheralName(machine)
    local tend_line = string.format(" Tending To:    %s %s", name, number)
    reprintLine(9, tend_line)
end

function Processor:processSlots(machine, inv_key, slots_key)
    local invName = self.settings[inv_key]
    local slots = self.schema[slots_key]
    if invName and slots then
        for slot_num, slot_info in pairs(slots) do
            local slotItem, moveCount = getItem(invName, slot_info, machine)
            if slotItem then
                move_from(invName, slotItem.slot, machine, slot_num, moveCount)
            end
        end
    end
end

function Processor:processExtraSlots(machine)
    -- Only process extra_slots if there is an inventory/slot defined
    self:processSlots(machine, "extra_inv", "extra_slots")
end
function Processor:processInputSlots(machine)
    -- Only process extra_slots if there is an inventory/slot defined
    self:processSlots(machine, "input_inv", "input_slots")
end
function Processor:processOutputSlots(machine)
    local invName = self.settings.output_inv
    local slots = self.schema.output_slots
    if invName and slots then
        for slot_num, slot_info in pairs(slots) do
            if slotHasItem(machine, slot_num) then
                machine.pushItems(invName,slot_num)
            end
        end
    end
end

function Processor:processSingleMachine(machine)
    self:printSingleMachine(machine)
    self:processInputSlots(machine)
    self:processExtraSlots(machine)
    self:processOutputSlots(machine)
end

function Processor:processMachines()
    for _, machine in pairs(self.machines) do
        self:processSingleMachine(machine)
        sleep(self.process_time)
    end
end



function Processor:run()
    self:staticPrint()
    while true do
        self:processMachines()
    end
end

function Processor:printInvs()
    print("Invs (O,I,E):", self.settings.output_inv, self.settings.input_inv, self.settings.extra_inv)
end

function Processor:getMachineCount()
    return #self.machines
end


-- These are the things that can be included (required) by other lua files
return {
    Processor = Processor,
    Schema = Schema
}
