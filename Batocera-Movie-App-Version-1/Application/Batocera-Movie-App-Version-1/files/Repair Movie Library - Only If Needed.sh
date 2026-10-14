#!/bin/bash
# Manual fallback. Normal movie/poster changes are detected automatically and
# become visible after GAME SETTINGS > UPDATE GAME LISTS.
LOG="/userdata/system/logs/movie-library-repair.log"
if /usr/bin/python3 /userdata/system/batocera-movie-player/build_movie_gamelist.py /userdata/roms/movies >"$LOG" 2>&1; then
  MESSAGE="REPAIR SUCCESSFUL\n\nThe Batocera movie library was rebuilt and its Zaparoo Movie refresh was started automatically.\n\nNEXT:\n1. GAME SETTINGS > UPDATE GAME LISTS\n2. Wait for Zaparoo indexing to finish.\n3. Search Movie again.\n\nA metadata scrape is only needed for changed poster or description information."
  dialog --title "MOVIE LIBRARY REPAIR" --msgbox "$MESSAGE" 20 78 2>/dev/null || true
else
  MESSAGE="REPAIR FAILED\n\nNo player or theme files were changed.\n\nDetails:\n$LOG"
  dialog --title "MOVIE LIBRARY REPAIR" --msgbox "$MESSAGE" 14 72 2>/dev/null || true
fi
