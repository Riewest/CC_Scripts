local args = {...}
local branch = args[1] .. " " or ""
print(string.format("sgit %sran successfully", branch))