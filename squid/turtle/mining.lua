--A collection of mining focused functions to import

local FILTERS = {
    default = {
        mode = "blacklist",
        tags = {
            "sculk_replaceable_world_gen",
            "c:stones",
            "minecraft:dirt",
            "c:gravels",
            "c:cobblestones",
            "c:chests",
            "minecraft:features_cannot_replace",
            "minecraft:flowers",
            "minecraft:wall_post_override",
            "minecraft:stairs",
            "minecraft:slabs",
            "minecraft:trapdoors",
            "computercraft:turtle"
        },
        names = {}
    },
    vanilla_ores = {
        mode = "whitelist",
        tags = {
            "minecraft:coal_ores",
            "minecraft:iron_ores",
            "minecraft:copper_ores",
            "minecraft:gold_ores",
            "minecraft:redstone_ores",
            "minecraft:emerald_ores",
            "minecraft:lapis_ores",
            "minecraft:diamond_ores",
            "minecraft:nether_gold_ores",
            "minecraft:quartz_ores"
        },
        names = {
            "minecraft:coal",
            "minecraft:raw_iron",
            "minecraft:raw_copper",
            "minecraft:raw_gold",
            "minecraft:redstone",
            "minecraft:emerald",
            "minecraft:lapis_lazuli",
            "minecraft:diamond",
            "minecraft:quartz",
            "minecraft:gold_nugget",
            "minecraft:ancient_debris"
        }
    }
}

local current_filter_name = "default"
local current_filter = FILTERS[current_filter_name]
local current_tag_lookup = {}
local current_name_lookup = {}

local function rebuildLookups(filter)
    current_tag_lookup = {}
    for _, tag_name in ipairs(filter.tags) do
        current_tag_lookup[tag_name] = true
    end

    current_name_lookup = {}
    for _, item_name in ipairs(filter.names or {}) do
        current_name_lookup[item_name] = true
    end
end

local function setFilter(filter_name)
    filter_name = filter_name or "default"
    if not FILTERS[filter_name] then
        error("Unknown mining filter: " .. tostring(filter_name))
    end

    current_filter_name = filter_name
    current_filter = FILTERS[filter_name]
    rebuildLookups(current_filter)
end

local function tagMatches(tag_table)
    if not tag_table then
        return false
    end

    for tag_name, _ in pairs(tag_table) do
        if current_tag_lookup[tag_name] then
            return true
        end
    end
    return false
end

local function nameMatches(item_name)
    return item_name and current_name_lookup[item_name] or false
end

local function shouldKeep(item_data)
    local has_match = tagMatches(item_data and item_data["tags"]) or nameMatches(item_data and item_data["name"])
    if current_filter.mode == "whitelist" then
        return has_match
    end
    return not has_match
end

local function scanDig(direction)
    direction = direction or ""
    local block, block_data = turtle["inspect" .. direction]()
    if block and shouldKeep(block_data) then
        turtle["dig" .. direction]()
        turtle["suck" .. direction]()
    end
end

local function purgeInventory()
    local first_slot
    for slot = 1,16 do
        local item_data = turtle.getItemDetail(slot, true)
        if item_data and not shouldKeep(item_data) then
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

setFilter("default")
purgeInventory()

local exports = {}
exports.FILTERS = FILTERS
exports.getFilterName = function()
    return current_filter_name
end
exports.purgeInventory = purgeInventory
exports.scanDig = scanDig
exports.setFilter = setFilter

return exports
