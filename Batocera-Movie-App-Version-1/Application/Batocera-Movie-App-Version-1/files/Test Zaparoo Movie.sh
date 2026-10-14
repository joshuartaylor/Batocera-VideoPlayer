#!/bin/bash
if [ "${1:-}" != "--visible" ] && command -v xterm >/dev/null 2>&1; then
  exec xterm -fullscreen -e bash "$0" --visible
fi

MOVIE_DIR="/userdata/roms/movies"
APP_DIR="/userdata/system/batocera-movie-player"
TEST_LOG="/userdata/system/logs/movie-zaparoo-test.log"

mkdir -p "$(dirname "$TEST_LOG")"
{
  echo
  echo "========================================"
  echo "$(date '+%F %T') ZAPAROO MOVIE TEST"
  echo "========================================"
} | tee -a "$TEST_LOG"

MOVIE=""
while IFS= read -r -d '' candidate; do
  MOVIE="$candidate"
  break
done < <(find "$MOVIE_DIR" -type f \( -iname '*.mp4' -o -iname '*.mkv' -o -iname '*.avi' -o -iname '*.mov' -o -iname '*.m4v' -o -iname '*.webm' -o -iname '*.mpeg' -o -iname '*.mpg' -o -iname '*.ts' -o -iname '*.m2ts' -o -iname '*.wmv' -o -iname '*.vob' \) -print0 2>/dev/null)

if [ -z "$MOVIE" ]; then
  echo "FAILED: No movie was found in $MOVIE_DIR" | tee -a "$TEST_LOG"
  if command -v dialog >/dev/null 2>&1; then
    dialog --title "Zaparoo Movie Test" --msgbox "NO MOVIES FOUND\n\nPut at least one movie in:\n/userdata/roms/movies" 13 62
  else
    echo "NO MOVIES FOUND"
    read -r -p "Press Enter to close."
  fi
  exit 1
fi

echo "Selected movie: $MOVIE" | tee -a "$TEST_LOG"
if command -v dialog >/dev/null 2>&1; then
  dialog --title "Zaparoo Movie Test" --yesno "This will launch the first movie through Zaparoo Core:\n\n$(basename "$MOVIE")\n\nAfter it starts, open Current Media on your phone. Continue?" 16 70 || exit 0
fi

echo "Sending movie to Zaparoo Core..." | tee -a "$TEST_LOG"
/usr/bin/python3 "$APP_DIR/zaparoo-launch.py" "$MOVIE"
RESULT=$?
echo "Test finished with result code: $RESULT" | tee -a "$TEST_LOG"
if [ "$RESULT" -ne 0 ]; then
  echo
  echo "MOVIE DID NOT START"
  echo
  echo "The exact failure is saved in:"
  echo "$TEST_LOG"
  echo "/userdata/system/logs/movie-zaparoo-launch.log"
  echo
  read -r -p "Press Enter to close."
fi
exit "$RESULT"
