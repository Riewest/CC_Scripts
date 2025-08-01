-- Attempt to inspect the block in front
local success, data = turtle.inspect()

-- Open a file called test.lua for writing
local file = fs.open("info.lua", "w")

-- Write the result to the file
if success then
    file.write("Inspected block:\n")
    file.write(textutils.serialize(data))
else
    file.write("No block detected.")
end

file.close()

shell.run("edit info.lua")

fs.delete("info.lua")

