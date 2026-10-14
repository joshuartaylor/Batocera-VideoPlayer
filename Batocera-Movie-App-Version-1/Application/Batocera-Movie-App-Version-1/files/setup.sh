#!/bin/bash
CONFIG="/userdata/system/batocera-movie-player/settings.conf"

set_value() {
  key="$1" value="$2"
  if grep -q "^${key}=" "$CONFIG"; then
    sed -i "s/^${key}=.*/${key}=${value}/" "$CONFIG"
  else
    printf '%s=%s\n' "$key" "$value" >> "$CONFIG"
  fi
}

while true; do
  choice="$(dialog --stdout --title "Batocera Movie Player" --menu "Choose a setting" 18 72 6 \
    volume "Set default volume" \
    safe "Toggle child / elderly safe mode" \
    sounds "Toggle confirmation sounds" \
    ending "Choose what happens when a movie ends" \
    posters "Set TMDB key for movie posters" \
    diagnostics "Open the one-button status screen" \
    exit "Save and exit")" || exit 0
  case "$choice" in
    volume)
      value="$(dialog --stdout --inputbox "Default volume (0-100)" 9 45 "$(sed -n 's/^default_volume=//p' "$CONFIG")")" || continue
      case "$value" in ''|*[!0-9]*) ;; *) [ "$value" -le 100 ] && set_value default_volume "$value" ;; esac ;;
    safe)
      current="$(sed -n 's/^safe_mode=//p' "$CONFIG")"
      [ "$current" = "true" ] && set_value safe_mode false || set_value safe_mode true ;;
    sounds)
      current="$(sed -n 's/^sounds_enabled=//p' "$CONFIG")"
      [ "$current" = "true" ] && set_value sounds_enabled false || set_value sounds_enabled true ;;
    ending)
      value="$(dialog --stdout --menu "After the movie ends" 14 60 3 waiting "Return to Batocera" replay "Replay the movie" hold "Hold the final frame")" || continue
      set_value end_behavior "$value" ;;
    posters)
      current="$(sed -n 's/^tmdb_api_key=//p' "$CONFIG")"
      value="$(dialog --stdout --insecure --passwordbox "Enter a free TMDB API key or Read Access Token.\n\nGet one from themoviedb.org, then choose GAME SETTINGS > UPDATE GAME LISTS. The Ports repair tool is only a fallback." 15 74 "$current")" || continue
      set_value tmdb_api_key "$value" ;;
    diagnostics) /userdata/roms/ports/Movie\ Player\ Diagnostics.sh ;;
    exit) exit 0 ;;
  esac
done
