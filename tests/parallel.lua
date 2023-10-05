local function tick()
    while true do
        os.sleep(1)
        print("Tick")
    end
end
local function wait_for_q()
    repeat
        local _, key = os.pullEvent("key")
    until key == keys.q
    print("Q was pressed!")
end

parallel.waitForAny(tick, wait_for_q)
print("Everything done!")