#!/bin/bash
if [ "${1:-}" != "--visible" ] && command -v xterm >/dev/null 2>&1; then
  exec xterm -fullscreen -e bash "$0" --visible
fi

APP_DIR="/userdata/system/batocera-movie-player"
MOVIE_DIR="/userdata/roms/movies"
CORE_DATA="/userdata/system/.local/share/zaparoo"
LAUNCHER="$CORE_DATA/launchers/BatoceraMoviePlayer.toml"
LOG="/userdata/system/logs/movie-player-diagnostics.log"
SETTINGS="/userdata/system/configs/emulationstation/es_settings.cfg"
MOVIES_THEME="/userdata/roms/movies/theme.xml"
PASS=0
FAIL=0

find_zaparoo() {
  if command -v zaparoo >/dev/null 2>&1; then
    command -v zaparoo
  elif [ -x /userdata/system/zaparoo ]; then
    printf '%s\n' /userdata/system/zaparoo
  elif [ -x /userdata/system/zaparoo/zaparoo ]; then
    printf '%s\n' /userdata/system/zaparoo/zaparoo
  fi
}

check() {
  label="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    printf '[PASS] %s\n' "$label" | tee -a "$LOG"
    PASS=$((PASS + 1))
  else
    printf '[FAIL] %s\n' "$label" | tee -a "$LOG"
    FAIL=$((FAIL + 1))
  fi
}

: > "$LOG"
echo "MOVIE PLAYER STATUS" | tee -a "$LOG"
echo "===================" | tee -a "$LOG"
echo "Installed version: $(cat "$APP_DIR/VERSION" 2>/dev/null || echo missing)" | tee -a "$LOG"

ZAPAROO="$(find_zaparoo)"
if [ -n "$ZAPAROO" ]; then
  CORE_VERSION="$("$ZAPAROO" -version 2>&1 | head -n 1 || true)"
else
  CORE_VERSION="not found"
fi
echo "Zaparoo Core: $CORE_VERSION" | tee -a "$LOG"

MOVIE_COUNT="$(find "$MOVIE_DIR" -type f \( -iname '*.mp4' -o -iname '*.mkv' -o -iname '*.avi' -o -iname '*.mov' -o -iname '*.m4v' -o -iname '*.webm' -o -iname '*.mpeg' -o -iname '*.mpg' -o -iname '*.ts' -o -iname '*.m2ts' -o -iname '*.wmv' -o -iname '*.vob' \) 2>/dev/null | wc -l)"
echo "Movies found: $MOVIE_COUNT" | tee -a "$LOG"
echo "Progress records: $(find "$APP_DIR/progress" -name '*.json' 2>/dev/null | wc -l)" | tee -a "$LOG"
echo | tee -a "$LOG"

check "MPV installed" command -v mpv
check "Zaparoo Core installed" test -n "$ZAPAROO"
check "Single movie folder exists" test -d "$MOVIE_DIR"
check "At least one movie exists" test "$MOVIE_COUNT" -gt 0
check "Movies system installed" test -f /userdata/system/configs/emulationstation/es_systems_movies.cfg
check "Custom launcher installed" test -f "$LAUNCHER"
check "Launcher scans /userdata/roms/movies" grep -Fq 'media_dirs = ["/userdata/roms/movies"]' "$LAUNCHER"
check "Launcher uses Movie system" grep -Fq 'system = "Movie"' "$LAUNCHER"
check "Session manager installed" test -x "$APP_DIR/movie-session.py"
check "Launch client installed" test -x "$APP_DIR/movie-client.py"
check "Session manager is running" test -S /tmp/batocera-movie-player/session.sock
check "Movies menu uses verified launch bridge" grep -Fq 'zaparoo-launch.py' /userdata/system/configs/emulationstation/es_systems_movies.cfg
check "Authoritative Movies theme installed" test -f "$MOVIES_THEME"
check "Exact beta15 ROM theme location" test -f /userdata/roms/movies/theme.xml
check "Movies library forced to detailed panels" grep -Fq 'name="movies.defaultView" value="detailed"' "$SETTINGS"
check "Movies theme contains title list" grep -Fq '<textlist name="gamelist">' "$MOVIES_THEME"
check "Movies theme contains framed poster" grep -Fq 'name="e_poster_frame"' "$MOVIES_THEME"
check "Beta15 Movies layout installed" grep -q '<customView name="Icons,Tiles,Carousel,Boxes,Content"' "$MOVIES_THEME"
check "Beta15 title-list renderer installed" grep -q '<imagegrid name="gamegrid">' "$MOVIES_THEME"
check "Obsolete cloned theme removed" test ! -d /userdata/themes/movie-player-carbon
check "Zaparoo uses session client" grep -Fq 'movie-client.py' "$LAUNCHER"
check "Controller input devices detected" sh -c 'ls /dev/input/event* >/dev/null 2>&1'

echo | tee -a "$LOG"
if [ "$FAIL" -eq 0 ]; then
  echo "LOCAL RESULT: READY" | tee -a "$LOG"
  echo "Phone step: Settings > Manage Media > Update media database." | tee -a "$LOG"
  echo "Then search for system: Movie" | tee -a "$LOG"
else
  echo "LOCAL RESULT: $FAIL item(s) need attention" | tee -a "$LOG"
fi
echo | tee -a "$LOG"
echo "Current Media check:" | tee -a "$LOG"
if [ -n "$ZAPAROO" ]; then
  "$ZAPAROO" -api media.active 2>&1 | tee -a "$LOG" || true
fi
echo | tee -a "$LOG"
echo "Report saved to: $LOG" | tee -a "$LOG"
echo "Install log: /userdata/system/logs/movie-player-install.log" | tee -a "$LOG"
echo "Session log: /userdata/system/logs/batocera-movie-player.log" | tee -a "$LOG"
echo "Test log: /userdata/system/logs/movie-zaparoo-test.log" | tee -a "$LOG"
read -r -p "Press Enter to close."
