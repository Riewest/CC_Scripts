--A collection of mining focused functions to import

local TAG_BLACKLIST = {
    "c:stones",
    "minecraft:dirt",
    "c:gravels",
    "c:cobblestones",
    "c:chests",
    "minecraft:features_cannot_replace",
    "computercraft:turtle"
}

local function isBlacklisted(tag_table)
    for j = 1,#TAG_BLACKLIST do
        if tag_table[TAG_BLACKLIST[j]] then
            return true
        end
    end
    return false
end

local function scanDig(direction)
    direction = direction or ""
    local block,block_data = turtle["inspect"..direction]()
    if block and not isBlacklisted(block_data["tags"]) then
        turtle["dig"..direction]()
        turtle["suck"..direction]()
    end
end

local function purgeInventory()
    local first_slot
    for slot = 1,16 do
        local item_data = turtle.getItemDetail(slot,true)
        if item_data and isBlacklisted(item_data["tags"]) then
            if not first_slot then
                first_slot = slot
            end
            turtle.select(slot)
            turtle.dropDown()
        end
    end
    if first_slot and first_slot ~= 16 then
        turtle.select(16)
        turtle.transferTo(first_slot)
    end
end

purgeInventory()

return {
    purgeInventory = purgeInventory,
    scanDig = scanDig
}