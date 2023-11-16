-- local args = {...}
-- local PREFIX = "scc"

local expect = require "cc.expect"
local expect, field, range = expect.expect, expect.field, expect.range

-- Find the first chatbox peripheral
local box = peripheral.find("chatBox")

local function stringSplit (inputstr, sep)
    if sep == nil then
            sep = "%s"
    end
    local t={}
    for str in string.gmatch(inputstr, "([^"..sep.."]+)") do
            table.insert(t, str)
    end
    return t
end

local function trimWhitespace(inputstr)
    return inputstr:match("^%s*(.-)%s*$")
end

local function helpTextBuilder(command, description, message)
    local bmessage = message or {}
    table.insert(bmessage, {
        {
            text = "\n" .. command .. "\n",
            underlined = true,
            color = "aqua",
            clickEvent = {
                action = "suggest_command",
                value = command
            },
            hoverEvent = {
                action = "show_text",
                contents = {text = "Click to Run"}
            }
        },
        {
            text = "   " .. description,
            color = "white",
            underlined = false
        }
    })
    return bmessage
end



local Command = {}
Command.__index = Command

function Command.new(command, help, chat_function)
    local self = setmetatable({}, Command)
    expect(1, command, "string")
    expect(2, command, "string")
    expect(3, chat_function, "function")
    self.command = command
    self.help = help
    self.chat_function = chat_function
    return self
end

function Command:getCommand()
    return self.command
end

function Command:executeFunction(...)
    local chatArgs = {...}
    return self.chat_function(table.unpack(chatArgs))
end

function Command:getHelp()
    return self.help
end


local Category = {}
Category.__index = Category

function Category.new(category)
    local self = setmetatable({}, Category)
    expect(1, category, "string")
    self.category = category
    self.commands = {}
    return self
end

function Category:getcategory()
    return self.category
end

function Category:addCommand(command)
    expect(1, command, "table")
    if not getmetatable(command) == Command then
        error("Given table was not a Command object!")
    end
    self.commands[command:getCommand()] = command
end

function Category:getCommand(command)
    return self.commands[command]
end
function Category:getCommands()
    return self.commands
end


local Processor = {}
Processor.__index = Processor

function Processor.new(name, prefix, ...)
    local self = setmetatable({}, Processor)
    expect(1, name, "string")
    expect(2, prefix, "string")
    self.name = name
    self.prefix = prefix
    self.categories = {}
    local topLevelCat = Category.new("")
    local ProcessorArgs = {...}
    for k,v in ipairs(ProcessorArgs) do
        expect(3, v, "table") --Check that the variable args coming in are still tables/commands/categories
        if getmetatable(v) == Command then
            topLevelCat:addCommand(v)
        elseif getmetatable(v) == Category then
            self.categories[v:getcategory()] = v
        else
            error("Given table was not a Command/Category object!")
        end
    end
    self.categories[""] = topLevelCat
    return self
end

function Processor:sendHelpMessage(message, username)
       
    local json = textutils.serialiseJSON(message)
    box.sendFormattedMessage(json, username)
end

function Processor:processMessage(username, message, uuid, isHidden)
    local trimmed_msg = trimWhitespace(message)
    
    local command_components = stringSplit(trimmed_msg)

    if command_components[1] ~= self.prefix then
        return
    end
    table.remove(command_components, 1)

    local found_category = self.categories[""] --default to TopLevelCategory

    if self.categories[command_components[1]] then
        found_category = self.categories[command_components[1]]
        table.remove(command_components, 1)
    end

    local found_command = found_category:getCommand(command_components[1])
    if found_command then
        table.remove(command_components, 1)
        if command_components[1] == "help" then
            local help_text = found_command:getHelp()
            local command_txt = string.format("$%s %s %s", self.prefix, found_category:getcategory(), found_command:getCommand())
            local cmd_help_message = helpTextBuilder(command_txt, help_text)
            self:sendHelpMessage(cmd_help_message, username)
            return
        end
        local cmd_message = table.concat(command_components, " ")
        found_command:executeFunction(username, cmd_message, uuid, isHidden)
    elseif command_components[1] == "help" then
        local cat_help_message = {}
        for command_name,command in pairs(found_category:getCommands()) do
            local help_text = command:getHelp()
            local command_txt = string.format("$%s %s %s", self.prefix, found_category:getcategory(), command_name)
            cat_help_message = helpTextBuilder(command_txt, help_text, cat_help_message)
        end
        if found_category:getcategory() == "" then
            for cat,v in pairs(self.categories) do
                local help_text = "See Category Help"
                local command_txt = string.format("$%s %s help", self.prefix, cat)
                cat_help_message = helpTextBuilder(command_txt, help_text, cat_help_message)
            end
        end
        self:sendHelpMessage(cat_help_message, username)
    end
end

function Processor:listen()
    while true do
        local event, username, message, uuid, isHidden = os.pullEvent("chat")
        local lower_message = string.lower(message)
        if isHidden and string.find(lower_message, self.prefix) then
            self:processMessage(username, lower_message, uuid, isHidden)
        end
    end
end

return {
    box = box,
    Processor = Processor,
    Category = Category,
    Command = Command,
    stringSplit = stringSplit
}



-- TESTING AREA
-- local t1 = ChatCommand.new("t1", function ()
--     print("This is my t1 command")
-- end)

-- local c1 = ChatCategory.new("c1")
-- c1:addCommand(ChatCommand.new("t2", function ()
--     print("This is my c1, t2 command")
-- end))


-- local cp = ChatProcessor.new("test processor", "scc", t1, c1)
-- cp:listen()