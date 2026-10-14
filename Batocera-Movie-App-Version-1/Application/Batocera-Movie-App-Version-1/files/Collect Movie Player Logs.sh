#!/bin/bash
if [ "${1:-}" != "--visible" ] && command -v xterm >/dev/null 2>&1; then
  exec xterm -fullscreen -e bash "$0" --visible
fi

TEXT_DEST="/userdata/Movie-Player-Diagnostics.txt"
ZIP_DEST="/userdata/Movie-Player-Logs.zip"
LOG_DIR="/userdata/system/logs"
APP_DIR="/userdata/system/batocera-movie-player"
SETTINGS="/userdata/system/configs/emulationstation/es_settings.cfg"

rm -f "$TEXT_DEST" "$ZIP_DEST"
: > "$TEXT_DEST" || {
  dialog --title "LOG EXPORT FAILED" --msgbox "Batocera could not write to the main SHARE folder.\n\nTarget: $TEXT_DEST" 12 72 2>/dev/null || true
  exit 1
}

section() {
  printf '\n\n===== %s =====\n' "$1" >> "$TEXT_DEST"
}

section "SUMMARY"
printf 'Generated: %s\n' "$(date '+%F %T %Z')" >> "$TEXT_DEST"
printf 'Installed version: %s\n' "$(cat "$APP_DIR/VERSION" 2>/dev/null || echo MISSING)" >> "$TEXT_DEST"
printf 'Free space:\n' >> "$TEXT_DEST"
df -h /userdata >> "$TEXT_DEST" 2>&1 || true

section "THEME STATUS"
grep -E 'name="ThemeSet"|name="ThemeConfiguration"|name="GamelistViewStyle"|name="movies.defaultView"' "$SETTINGS" >> "$TEXT_DEST" 2>&1 || true
printf '\nInstalled Carbon candidates:\n' >> "$TEXT_DEST"
find /usr/share/emulationstation/themes /etc/emulationstation/themes /userdata/themes \
  -maxdepth 1 -type d -iname '*carbon*' -print >> "$TEXT_DEST" 2>&1 || true
printf '\nMovie theme files:\n' >> "$TEXT_DEST"
find /userdata/themes/es-theme-carbon-movie-player/movies /userdata/roms/movies \
  -maxdepth 1 -type f \( -name 'theme.xml' -o -name 'movies-logo.png' -o -name 'movie-poster-frame.png' \) \
  -ls >> "$TEXT_DEST" 2>&1 || true
if [ -f /userdata/themes/es-theme-carbon-movie-player/movies/theme.xml ]; then
  printf '\nCarbon Movies theme.xml:\n' >> "$TEXT_DEST"
  sed -n '1,220p' /userdata/themes/es-theme-carbon-movie-player/movies/theme.xml >> "$TEXT_DEST" 2>&1
fi

section "LIVE MPV GEOMETRY"
/usr/bin/python3 - >> "$TEXT_DEST" 2>&1 <<'PY'
import json, socket
path = '/tmp/batocera-movie-player/mpv.sock'
names = ('video-params/aspect', 'video-params/w', 'video-params/h',
         'osd-dimensions/aspect', 'osd-width', 'osd-height',
         'video-zoom', 'video-scale-x', 'video-scale-y',
         'panscan', 'keepaspect', 'video-unscaled')
for number, name in enumerate(names, 1):
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(1)
            client.connect(path)
            client.sendall((json.dumps({'command':['get_property', name], 'request_id':number})+'\n').encode())
            data = b''
            while b'\n' not in data:
                block = client.recv(4096)
                if not block: break
                data += block
            reply = next((json.loads(line) for line in data.splitlines()
                          if json.loads(line).get('request_id') == number), {})
            print(f'{name}: data={reply.get("data")!r} error={reply.get("error")!r}')
    except Exception as error:
        print(f'{name}: QUERY FAILED: {error}')
PY

for file in \
  "$LOG_DIR/movie-player-install.log" \
  "$LOG_DIR/movie-controller.log" \
  "$LOG_DIR/batocera-movie-player.log" \
  "$LOG_DIR/movie-zaparoo-launch.log" \
  "/userdata/system/.local/share/zaparoo/logs/core.log"; do
  [ -f "$file" ] || continue
  section "$(basename "$file")"
  tail -n 800 "$file" >> "$TEXT_DEST" 2>&1
done

sync
if [ ! -s "$TEXT_DEST" ]; then
  dialog --title "LOG EXPORT FAILED" --msgbox "The diagnostic file was created but is empty.\n\nTarget: $TEXT_DEST" 12 72 2>/dev/null || true
  exit 1
fi

FINAL="$TEXT_DEST"
if command -v zip >/dev/null 2>&1 && zip -j "$ZIP_DEST" "$TEXT_DEST" >/dev/null 2>&1 && [ -s "$ZIP_DEST" ]; then
  FINAL="$ZIP_DEST"
fi

MESSAGE="EXPORT SUCCESSFUL\n\nMain SHARE folder:\n\n$(basename "$FINAL")\n\nIf the ZIP is unavailable, send:\n$(basename "$TEXT_DEST")"
if command -v dialog >/dev/null 2>&1; then
  dialog --title "MOVIE PLAYER LOGS" --msgbox "$MESSAGE" 17 72
else
  printf '%b\n' "$MESSAGE"
  read -r -p "Press Enter to close."
fi
