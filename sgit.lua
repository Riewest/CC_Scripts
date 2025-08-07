-- Author: Chase Riewestahl
-- Date: 1/29/2023
-- Description: Downloads all the .lua files from a github repository maintaining the directory structure
-- Usage: "sgit OPTIONAL_BRANCH" if no branch is passed defaults to "main"

local args = {...}
local githubName = "Riewest"
local repositoryName = "CC_Scripts" -- The repository must be public for this script to work
local branch = args[1] or "main"

local debug = false
local debugDir = "Debug"

local LOG_LEVELS = {}
LOG_LEVELS.info = 0 -- print minimal info to console
LOG_LEVELS.debug = 1 -- print every log to console

local logLevel = LOG_LEVELS.info -- Only applies to console output
local logFileEnabled = true -- All log messages will appear in log file if enabled no matter the loglevel
local logFile = "sgit.log"
local logDir = "logs"
local logPath = string.format("%s/%s", logDir, logFile)


local counterName = "ccscripts"
local httpEndpoint = "https://riecount.suicidesquid.net/count?name=" .. counterName
local postData = ""
local count
local label = "Squid_"

local response = http.post(httpEndpoint, postData)

if response then
    local body = response.readAll()
    response.close()
    local ok, data = pcall(textutils.unserializeJSON, body)
    if ok and type(data) == "table" and type(data.count) == "number" then
        count = data.count
    else
        count = os.getComputerID()
    end
else
    count = os.getComputerID()
end
label = label .. count

print("Setting Label:",label)
os.setComputerLabel(label)



local rawHeaders = {
    ["cache-control"] = "max-age=1",
}

local treeApiHeaders = {
    ["Accept"] = "application/vnd.github+json",
    ["X-GitHub-Api-Version"] = "2022-11-28"
}

if logFileEnabled then
    logFile = fs.open(logPath, "w")
end

if debug then
    debugFile = fs.open(debugDir .. "/debug.txt", "w") -- Debug file
end

local function log(message, level)
    level = level or LOG_LEVELS.info
    if level <= logLevel then
        print(message)
    end
    if logFileEnabled then
        logFile.writeLine(message)
    end
end

local treeRequestUrl = string.format("https://api.github.com/repos/%s/%s/git/trees/%s?recursive=true", githubName, repositoryName, branch)
log("Tree Request URL: " .. treeRequestUrl)
local treeRequest = http.get(treeRequestUrl, headers)

if treeRequest then
    treeJson = treeRequest.readAll()
    repoTree = textutils.unserializeJSON(treeJson, { parse_null = true })
    
    if debug then
        local debugRepoRequest = fs.open(debugDir .. "/repoTree.json", "w")
        debugRepoRequest.write(treeJson)
        debugRepoRequest.close()
    end

    if repoTree["tree"] then
        for k, v in pairs(repoTree["tree"]) do
            local filepath = v["path"]
            if string.find(filepath, ".lua") then
                fileName = fs.getName(filepath)
                fileDir  = fs.getDir(filepath)
                if fileDir and fileDir ~= "" and not fs.exists(fileDir) then
                    fs.makeDir(fileDir)
                end
                
                local rawUrl = string.format("https://raw.githubusercontent.com/%s/%s/%s/%s", githubName, repositoryName, branch, filepath)
                log("Attempting Download of: " .. rawUrl, LOG_LEVELS.debug)
                local rawRequest = http.get(rawUrl, rawHeaders)
                if rawRequest then
                    local content = rawRequest.readAll() -- Read all lines in the lua file
    
                    local scriptFile = fs.open(filepath, "w")
    
                    scriptFile.write(content)
    
                    scriptFile.close()
    
                    log("File: " .. filepath .. " downloaded successfully")
                else
                    log("File: " .. filepath .. " not found")
                end
            end
        end
    else
        local err_msg = "No Files Found"
        log(err_msg)
        error(err_msg)
    end
else
    local err_msg = "Bad Tree Request"
    log(err_msg)
    error(err_msg)
end

local testCommand = "tests/sgit_test"
if args[1] then
    testCommand = testCommand .. " " .. args[1]
end
log("Running Test Command: " .. testCommand, LOG_LEVELS.debug)
shell.run(testCommand)

if logFileEnabled then
    logFile.close()
end

if debug then
    debugFile.close()
end
