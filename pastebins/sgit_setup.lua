-- Author: Chase Riewestahl
-- Date: 1/29/2023
-- Description: Downloads sgit.lua from my github repo and pulls in the main branch unless overridden
-- Usage: "sgit OPTIONAL_BRANCH" if no branch is passed defaults to "main"
-- Note: "Keep up to date on pastebin https://pastebin.com/HuSsRvQw"

local args = {...}
local githubName = "Riewest"
local repositoryName = "CC_Scripts" -- The repository must be public for this script to work
local branch = args[1] or "main"

local filepath = "sgit.lua"

local rawHeaders = {
    ["cache-control"] = "max-age=1",
}                
local rawUrl = string.format("https://raw.githubusercontent.com/%s/%s/%s/%s", githubName, repositoryName, branch, filepath)
print("Attempting Download of: " .. rawUrl)
local rawRequest = http.get(rawUrl, rawHeaders)
if rawRequest then
    local content = rawRequest.readAll() -- Read all lines in the lua file

    local scriptFile = fs.open(filepath, "w")

    scriptFile.write(content)

    scriptFile.close()

    print("File: " .. filepath .. " downloaded successfully")
else
    print("File: " .. filepath .. " not found")
end


local setup_command = "sgit " .. branch
shell.run(setup_command)