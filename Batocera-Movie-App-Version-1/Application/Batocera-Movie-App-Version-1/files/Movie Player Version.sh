#!/bin/bash
if [ "${1:-}" != "--visible" ] && command -v xterm >/dev/null 2>&1; then
  exec xterm -fullscreen -e bash "$0" --visible
fi

VERSION_FILE="/userdata/system/batocera-movie-player/VERSION"
VERSION="unknown"
[ -f "$VERSION_FILE" ] && VERSION="$(cat "$VERSION_FILE")"

if command -v dialog >/dev/null 2>&1; then
  dialog --title "Batocera Movie App" --msgbox "INSTALLED VERSION\n\nVersion ${VERSION}\n\nCreated by Joshua R. Taylor\nJRT3D.com • 2026\nDeveloped with assistance from ChatGPT" 17 68
else
  echo
  echo "========================================"
  echo " BATOCERA MOVIE APP VERSION: ${VERSION}"
  echo "========================================"
  echo " Created by Joshua R. Taylor - JRT3D.com - 2026"
  echo " Developed with assistance from ChatGPT"
  echo
  read -r -p "Press Enter to close."
fi
