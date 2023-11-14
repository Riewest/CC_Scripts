local chat = require("chat_box")
local expect = require "cc.expect"
local expect, field, range = expect.expect, expect.field, expect.range

local Player = {}
Player.DEFAULT_SETTINGS = {
    itemFilters = {}
}
Player.__index = Player

function Player:new(inv)
    local self = setmetatable({}, Player)
    self.name = inv.getOwner()
    self.inv = inv --This is a wrapped inventoryManager
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

function Player:cleanInv()
    print("Cleaning:", self.name)
    local inventory = self.inv.list()
    for i = #inventory, 1, -1 do
        local item = inventory[i]
        print("", item.slot, item.name)
        -- self.inv.removeItemFromPlayerNBT("up", v.count, v.slot)
        if not self.settings.itemFilters[item.name] then
            self.inv.removeItemFromPlayerNBT("up", item.count, nil, {fromSlot=item.slot})
        end
    end
end

function Player:addItemFilter(item)
    expect(1, item, "string")
    self.settings.itemFilters[item] = true
    self:saveSettings()
    chat.box.sendMessageToPlayer(string.format("Added Item Filter: %s", item), self.name)
end

function Player:removeItemFilter(item)
    expect(1, item, "string")
    if self.settings.itemFilters[item] then
        self.settings.itemFilters[item] = nil
    end
    self:saveSettings()
    chat.box.sendMessageToPlayer(string.format("Removed Item Filter: %s", item), self.name)
end


local players = {}
peripheral.find("inventoryManager", function(name, manager)
    local owner = manager.getOwner()
    players[owner] = Player:new(manager)
end)


local cleanCMD = chat.Command.new("clean", function (username, message, uuid, isHidden)
    local player = players[username]
    if player and getmetatable(player) == Player then
        player:cleanInv()
    end
end)

local filterCategory = chat.Category.new("filter")
filterCategory:addCommand(chat.Command.new("add", function (username, message, uuid, isHidden)
    local player = players[username]
    if player and getmetatable(player) == Player then
        local newFilters = chat.stringSplit(message)
        if newFilters[1] == "hand" then
            local currentItem = player.inv.getItemInHand()
            if currentItem then
                newFilters[1] = currentItem.name
            end
        end
        for k,item in ipairs(newFilters) do
            player:addItemFilter(item)
        end
    end
end))

filterCategory:addCommand(chat.Command.new("rm", function (username, message, uuid, isHidden)
    local player = players[username]
    if player and getmetatable(player) == Player then
        local newFilters = chat.stringSplit(message)
        if newFilters[1] == "hand" then
            local currentItem = player.inv.getItemInHand()
            if currentItem then
                newFilters[1] = currentItem.name
            end
        end
        for k,item in ipairs(newFilters) do
            player:removeItemFilter(item)
        end
    end
end))


local invProcessor = chat.Processor.new("Inventory Processor", "inv", cleanCMD, filterCategory)
invProcessor:listen()




-- TEST AREA
local function saveInvJson(inv)
    local filepath = inv.getOwner() .. "_inv.json"
    local playerSettings = fs.open(filepath, "w")
    playerSettings.write(textutils.serializeJSON(inv.list()))
    playerSettings.close()
end

saveInvJson(peripheral.wrap("left"))