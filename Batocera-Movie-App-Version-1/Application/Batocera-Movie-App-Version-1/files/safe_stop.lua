local settings = "/userdata/system/batocera-movie-player/settings.conf"
local last_stop = 0
local utils = require 'mp.utils'

local function sound(name)
    utils.subprocess_detached({args={"/userdata/system/batocera-movie-player/feedback.sh", name}})
end

local function safe_mode()
    local file = io.open(settings, "r")
    if not file then return false end
    for line in file:lines() do
        if line == "safe_mode=true" then file:close(); return true end
    end
    file:close()
    return false
end

mp.register_script_message("safe-stop", function()
    if not safe_mode() then
        os.execute("touch /tmp/batocera-movie-player/manual_exit")
        mp.command("quit")
        return
    end
    local now = mp.get_time()
    if now - last_stop <= 5 then
        sound("confirm")
        os.execute("touch /tmp/batocera-movie-player/manual_exit")
        mp.osd_message("STOPPING MOVIE", 1.2)
        mp.add_timeout(0.3, function() mp.command("quit") end)
    else
        last_stop = now
        sound("warning")
        mp.osd_message("SCAN STOP AGAIN TO EXIT", 5)
    end
end)
