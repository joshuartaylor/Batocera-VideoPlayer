#!/bin/bash
set -u

APP_DIR="/userdata/system/batocera-movie-player"
SAVED_DATA="/userdata/system/batocera-movie-player-saved-data"
PORTS_DIR="/userdata/roms/ports"

mkdir -p "$SAVED_DATA/progress" "$SAVED_DATA/watch_later"
cp -a "$APP_DIR/progress/." "$SAVED_DATA/progress/" 2>/dev/null || true
cp -a "$APP_DIR/watch_later/." "$SAVED_DATA/watch_later/" 2>/dev/null || true
[ -f "$APP_DIR/settings.conf" ] && cp "$APP_DIR/settings.conf" "$SAVED_DATA/settings.conf"

if [ -f /tmp/batocera-movie-player/session.pid ]; then
  SESSION_PID="$(cat /tmp/batocera-movie-player/session.pid 2>/dev/null || true)"
  case "$SESSION_PID" in ''|*[!0-9]*) ;; *) kill "$SESSION_PID" 2>/dev/null || true ;; esac
  sleep 1
fi

rm -f /userdata/system/.local/share/zaparoo/launchers/BatoceraMoviePlayer.toml
rm -f /userdata/system/configs/emulationstation/es_systems_movies.cfg
rm -f "$PORTS_DIR/Movie Player Setup.sh"
rm -f "$PORTS_DIR/Show Scan Card Screen.sh"
rm -f "$PORTS_DIR/Refresh Movie Library.sh"
rm -f "$PORTS_DIR/Repair Movie Library - Only If Needed.sh"
rm -f "$PORTS_DIR/Movie Player Version.sh"
rm -f "$PORTS_DIR/Movie Player Diagnostics.sh"
rm -f "$PORTS_DIR/Test First Movie with Zaparoo.sh"
rm -f "$PORTS_DIR/Repair Zaparoo Movies.sh"
rm -f "$PORTS_DIR/Collect Movie Player Logs.sh"

# Restore the theme that was active before Movie Player installed its exact
# Carbon clone, but never override a theme the user selected afterward.
python3 - <<'PY'
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
app = Path('/userdata/system/batocera-movie-player')
settings = Path('/userdata/system/configs/emulationstation/es_settings.cfg')
saved = app / 'ORIGINAL_THEMESET'
saved_view = app / 'ORIGINAL_MOVIES_DEFAULT_VIEW'
if settings.is_file():
    tree = ET.parse(settings)
    root = tree.getroot()
    changed = False
    node = next((n for n in root.findall('string') if n.get('name') == 'ThemeSet'), None)
    if saved.is_file() and node is not None and node.get('value') == 'movie-player-carbon':
        node.set('value', saved.read_text(encoding='utf-8').strip() or 'carbon')
        changed = True
    view = next((n for n in root.findall('string') if n.get('name') == 'movies.defaultView'), None)
    if saved_view.is_file() and view is not None and view.get('value') == 'detailed':
        old_view = saved_view.read_text(encoding='utf-8').strip()
        if old_view == '__MISSING__':
            root.remove(view)
        else:
            view.set('value', old_view)
        changed = True
    if changed:
        tree.write(settings, encoding='utf-8', xml_declaration=True)
shutil.rmtree('/userdata/themes/movie-player-carbon', ignore_errors=True)
PY
rm -rf "$APP_DIR"

echo "Batocera Movie Player was removed."
echo "Movies and posters remain in /userdata/roms/movies."
echo "Settings and playback progress were preserved in $SAVED_DATA."
read -r -p "Press Enter to close."
