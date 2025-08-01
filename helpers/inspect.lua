-- Attempt to inspect the block in front
local success, data = turtle.inspect()

local FILE = "info.data"

-- Open a file called test.lua for writing
local file = fs.open(FILE, "w")

-- Write the result to the file
if success then
    file.write("-- Inspected Block:\n")
    file.write("data = ")
    file.write(textutils.serialize(data))
else
    file.write("No block detected.")
end

file.close()

shell.run("edit", FILE)

fs.delete(FILE)

