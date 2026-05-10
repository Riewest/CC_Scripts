-- logger.lua
-- Logging module with level filtering, colored terminal output, and file output.
--
-- Usage:
--   local logger = require("logger")
--   local log = logger.new("squidbot")          -- named logger, file defaults to "squidbot.log"
--   local log = logger.new("squidbot", {
--       level    = logger.WARN,                 -- minimum level to output (default: DEBUG)
--       file     = "logs/squidbot.log",         -- log file path (default: "<name>.log")
--       toFile   = true,                        -- write to file (default: true)
--       toScreen = true,                        -- print to terminal (default: true)
--   })
--
--   log:debug("entered main loop")
--   log:info("connected to %s", ip)
--   log:warn("packet dropped")
--   log:error("connection failed: %s", err)

local logger = {}

-- Log levels
logger.DEBUG = 1
logger.INFO  = 2
logger.WARN  = 3
logger.ERROR = 4

local LEVEL_NAMES = { [1] = "DEBUG", [2] = "INFO", [3] = "WARN", [4] = "ERROR" }

-- Terminal colours per level (falls back gracefully if colours unsupported)
local LEVEL_COLOURS = {
    [1] = colours.lightGrey,
    [2] = colours.white,
    [3] = colours.yellow,
    [4] = colours.red,
}

local function timestamp()
    -- Returns a HH:MM:SS string using the in-game clock (real-time fallback via os.clock)
    local t = os.time("utc") -- seconds since epoch when running on a real server; os.time() otherwise
    if type(t) == "number" and t > 86400 then
        -- Real epoch: format it
        local h = math.floor(t / 3600) % 24
        local m = math.floor(t / 60)   % 60
        local s = t % 60
        return string.format("%02d:%02d:%02d", h, m, s)
    end
    -- Fallback: os.clock gives seconds since computer start
    local c = math.floor(os.clock())
    return string.format("%02d:%02d:%02d", math.floor(c/3600) % 24, math.floor(c/60) % 60, c % 60)
end

local function writeToFile(path, line)
    local f = fs.open(path, "a")
    if f then
        f.writeLine(line)
        f.close()
    end
end

-- Logger instance metatable
local LoggerMeta = {}
LoggerMeta.__index = LoggerMeta

function LoggerMeta:_log(level, fmt, ...)
    if level < self.level then return end

    local msg    = select("#", ...) > 0 and string.format(fmt, ...) or tostring(fmt)
    local entry  = string.format("[%s][%s][%s] %s", timestamp(), LEVEL_NAMES[level], self.name, msg)

    if self.toScreen then
        if term.isColour() then
            term.setTextColour(LEVEL_COLOURS[level] or colours.white)
        end
        print(entry)
        if term.isColour() then
            term.setTextColour(colours.white)
        end
    end

    if self.toFile then
        writeToFile(self.file, entry)
    end
end

function LoggerMeta:debug(fmt, ...) self:_log(logger.DEBUG, fmt, ...) end
function LoggerMeta:info (fmt, ...) self:_log(logger.INFO,  fmt, ...) end
function LoggerMeta:warn (fmt, ...) self:_log(logger.WARN,  fmt, ...) end
function LoggerMeta:error(fmt, ...) self:_log(logger.ERROR, fmt, ...) end

--- Create a new logger instance.
-- @param name    string  A label shown in every log line.
-- @param opts    table   Optional settings (level, file, toFile, toScreen).
function logger.new(name, opts)
    opts = opts or {}
    local instance = {
        name     = name or "app",
        level    = opts.level    or logger.DEBUG,
        file     = opts.file     or (name .. ".log"),
        toFile   = opts.toFile   ~= false,   -- default true
        toScreen = opts.toScreen ~= false,   -- default true
    }
    return setmetatable(instance, LoggerMeta)
end

return logger
