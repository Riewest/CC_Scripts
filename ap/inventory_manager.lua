local chat = require("chat_box")
local expect = require "cc.expect"
local expect, field, range = expect.expect, expect.field, expect.range

local AUTO_CLEAN_INTERVAL = 5

local HOTBAR_SLOTS = {}
HOTBAR_SLOTS["0"] = true
HOTBAR_SLOTS["1"] = true
HOTBAR_SLOTS["2"] = true
HOTBAR_SLOTS["3"] = true
HOTBAR_SLOTS["4"] = true
HOTBAR_SLOTS["5"] = true
HOTBAR_SLOTS["6"] = true
HOTBAR_SLOTS["7"] = true
HOTBAR_SLOTS["8"] = true

local Player = {}
Player.DEFAULT_SETTINGS = {
    itemFilters = {},
    slots = HOTBAR_SLOTS
}
Player.__index = Player

function Player:new(inv)
    local self = setmetatable({}, Player)
    self.name = inv.getOwner()
    self.inv = inv --This is a wrapped inventoryManager
    self.auto_clean = false
    self.settings = Player.DEFAULT_SETTINGS
    self:init()
    return self
end

function Player:getSettingsFilepath()
    local dir = "players/settings"
    local filename = self.name .. ".json"
    local filepath = string.format("%s/%s", dir, filename)
    return dir, filename, filepath
end

function Player:saveSettings()
    local dir, filename, filepath = self:getSettingsFilepath()
    fs.makeDir(dir)
    local playerSettings = fs.open(filepath, "w")
    playerSettings.write(textutils.serializeJSON(self.settings))
    playerSettings.close()
    self.configured = true
end

function Player:loadSettings()
    local dir, filename, filepath = self:getSettingsFilepath()
    local playerSettings = fs.open(filepath, "r")
    if playerSettings then
        local savedSettings = textutils.unserializeJSON(playerSettings.readAll())
        playerSettings.close()
        self.settings = savedSettings
        self.configured = true
    end
end

function Player:init()
    self:loadSettings() -- load in any saved settings
end

function Player:sendMessage(message)
    expect(1, message, "string", "table")
    if type(message) == "string" then
        message = {
            {text = message}
        }
    end
    local json = textutils.serializeJSON(message)
    chat.box.sendFormattedMessage(json, self.name)
end

function Player:cleanInv()
    print("Cleaning:", self.name)
    local inventory = self.inv.list()
    for i = #inventory, 1, -1 do
        local item = inventory[i]
        if not self.settings.itemFilters[item.name] and not self.settings.slots[tostring(item.slot)] then
            self.inv.removeItemFromPlayerNBT("up", item.count, nil, {fromSlot=item.slot})
        end
    end
end

function Player:printHand()
    local item = self.inv.getItemInHand()
    if item then
        local message = {
            {text = "Name: "},
            {
                text = item.name,
                underlined = true,
                color = "aqua",
                clickEvent = {
                    action = "copy_to_clipboard",
                    value = item.name
                },
                hoverEvent = {
                    action = "show_text",
                    contents = {text = "Copy to Clipboard"}
                }
            }
        }
        self:sendMessage(message)
    end
end

function Player:addItemFilter(item)
    expect(1, item, "string")
    self.settings.itemFilters[item] = true
    self:saveSettings()
end

function Player:removeItemFilter(item)
    expect(1, item, "string")
    if self.settings.itemFilters[item] then
        self.settings.itemFilters[item] = nil
    end
    self:saveSettings()
end

function Player:addSlotFilter(slot)
    expect(1, slot, "string")
    self.settings.slots[slot] = true
    self:saveSettings()
end

function Player:removeSlotFilter(slot)
    expect(1, slot, "string")
    if self.settings.slots[slot] then
        self.settings.slots[slot] = nil
    end
    self:saveSettings()
end


local players = {}
peripheral.find("inventoryManager", function(name, manager)
    local owner = manager.getOwner()
    players[owner] = Player:new(manager)
end)


local cleanCMD = chat.Command.new("clean", "Will remove all non filtered items/slots from your inventory",
  function (username, message, uuid, isHidden)
    local player = players[username]
    if player and getmetatable(player) == Player then
        player:cleanInv()
    end
end)

local autoCMD = chat.Command.new("auto", "Will toggle auto inventory cleaning",
  function (username, message, uuid, isHidden)
    local player = players[username]
    if player and getmetatable(player) == Player then
        player.auto_clean = not player.auto_clean
        if player.auto_clean then
            player:sendMessage("Auto Clean Activated")
        else
            player:sendMessage("Auto Clean Deactivated")
        end
    end
end)

local handCMD = chat.Command.new("hand", "Returns a message with the current held item information",
  function (username, message, uuid, isHidden)
    local player = players[username]
    if player and getmetatable(player) == Player then
        player:printHand()
    end
end)

local filterCategory = chat.Category.new("filter")
filterCategory:addCommand(chat.Command.new("add", "Add 1 or multiple item filters (if 'hand' is given it will filter what you are holding)",
  function (username, message, uuid, isHidden)
    local player = players[username]
    if player and getmetatable(player) == Player then
        local newFilters = chat.stringSplit(message)
        if newFilters[1] == "hand" then
            local currentItem = player.inv.getItemInHand()
            if currentItem then
                newFilters[1] = currentItem.name
            end
        end

        local add_message = {
            {text = "Removed Item Filters:", color = "gold"}
        }
        for k,item in ipairs(newFilters) do
            player:addItemFilter(item)
            table.insert(add_message, {
                text = " " .. item
            })
        end
        player:sendMessage(add_message)
    end
end))

filterCategory:addCommand(chat.Command.new("rm", "Remove 1 or multiple item filters (if 'hand' is given it will use what you are holding)",
  function (username, message, uuid, isHidden)
    local player = players[username]
    if player and getmetatable(player) == Player then
        local newFilters = chat.stringSplit(message)
        if newFilters[1] == "hand" then
            local currentItem = player.inv.getItemInHand()
            if currentItem then
                newFilters[1] = currentItem.name
            end
        end

        local rm_message = {
            {text = "Removed Item Filters:", color = "gold"}
        }
        for k,item in ipairs(newFilters) do
            player:removeItemFilter(item)
            table.insert(rm_message, {
                text = " " .. item
            })
        end
        player:sendMessage(rm_message)
    end
end))

local slotsCategory = chat.Category.new("slots")
slotsCategory:addCommand(chat.Command.new("show", "Returns a message showing what the slot numbers are",
  function (username, message, uuid, isHidden)
    local player = players[username]
    if player and getmetatable(player) == Player then
        local slot_str = ""
        for i = 0, 35 do
            if player.settings.slots[tostring(i)] then
                slot_str = slot_str .. "x"
            else
                slot_str = slot_str .. "o"
            end
        end


        local nl = "\n"
        local slot_message = {
            { text = nl },
            { text = "SLOTS INFO         " .. nl, color = "gold" },
            { text =  string.sub(slot_str, 10, 18) .. " 9 > 17" .. nl, color = "aqua"},
            { text =  string.sub(slot_str, 19, 27) .. " 18 > 26" .. nl, color = "aqua"},
            { text =  string.sub(slot_str, 28, 36) .. " 27 > 35" .. nl, color = "aqua"},
            { text =  string.sub(slot_str, 1, 9) .. "  0 > 8 " .. nl, color = "green"},
            { text = nl }
        }

        player:sendMessage(slot_message)
    end
  end))

slotsCategory:addCommand(chat.Command.new("add", "Add 1 or multiple slot filters (if 'minecraft:item' is given it remove all slots with that item)",
  function (username, message, uuid, isHidden)
    local player = players[username]
    if player and getmetatable(player) == Player then
        local newFilters = chat.stringSplit(message)

        -- This if block handles if the user passes in an item as a way to process multiple slots
        if string.find(newFilters[1], ":") then
            local filter_item = newFilters[1]
            newFilters = {}
            for i, item in ipairs(player.inv.getItems()) do
                if item.name == filter_item then
                    table.insert(newFilters, tostring(item.slot))
                end
            end
        end

        local add_message = {
            {text = "Added Slots:", color = "gold"}
        }
        for k,slot in ipairs(newFilters) do
            if tonumber(slot) ~= nil then -- make sure its a number in string format
                player:addSlotFilter(slot)
                table.insert(add_message, {
                    text = " " .. slot
                })
            end
        end
        player:sendMessage(add_message)
    end
end))

slotsCategory:addCommand(chat.Command.new("rm", "Remove 1 or multiple slot filters (if 'minecraft:item' is given it remove all slots with that item)",
  function (username, message, uuid, isHidden)
    local player = players[username]
    if player and getmetatable(player) == Player then
        local newFilters = chat.stringSplit(message)

        -- This if block handles if the user passes in an item as a way to process multiple slots
        if string.find(newFilters[1], ":") then
            local filter_item = newFilters[1]
            newFilters = {}
            for i, item in ipairs(player.inv.getItems()) do
                if item.name == filter_item then
                    table.insert(newFilters, tostring(item.slot))
                end
            end
        end

        local rm_message = {
            {text = "Removed Slots:", color = "gold"}
        }
        for k,slot in ipairs(newFilters) do
            if tonumber(slot) ~= nil then -- make sure its a number in string format
                player:removeSlotFilter(slot)
                table.insert(rm_message, {
                    text = " " .. slot
                })
            end
        end
        player:sendMessage(rm_message)
    end
end))



local invProcessor = chat.Processor.new("Inventory Processor", "inv", cleanCMD, handCMD, autoCMD, filterCategory, slotsCategory)


local function listen()
    invProcessor:listen()
end

local function autoClean()
    while true do
        for k, player in pairs(players) do
            if player.auto_clean then
                player:cleanInv()
            end
        end
        sleep(AUTO_CLEAN_INTERVAL)
    end
end

parallel.waitForAll(listen, autoClean)

-- TEST AREA
-- local function saveInvJson(inv)
--     local filepath = inv.getOwner() .. "_inv.json"
--     local playerSettings = fs.open(filepath, "w")
--     playerSettings.write(textutils.serializeJSON(inv.list()))
--     playerSettings.close()
-- end

-- saveInvJson(peripheral.wrap("left"))