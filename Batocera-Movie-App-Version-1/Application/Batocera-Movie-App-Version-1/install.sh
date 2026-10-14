#!/bin/bash
set -u

APP_DIR="/userdata/system/batocera-movie-player"
ZAPAROO_DATA="/userdata/system/.local/share/zaparoo"
LAUNCHER_DIR="$ZAPAROO_DATA/launchers"
MOVIE_DIR="/userdata/roms/movies"
PORTS_DIR="/userdata/roms/ports"
ES_CONFIG_DIR="/userdata/system/configs/emulationstation"
SOURCE_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
VERSION="$(cat "$SOURCE_DIR/VERSION" 2>/dev/null || echo unknown)"
INSTALL_LOG="/userdata/system/logs/movie-player-install.log"

find_zaparoo() {
  if command -v zaparoo >/dev/null 2>&1; then
    command -v zaparoo
  elif [ -x /userdata/system/zaparoo ]; then
    printf '%s\n' /userdata/system/zaparoo
  elif [ -x /userdata/system/zaparoo/zaparoo ]; then
    printf '%s\n' /userdata/system/zaparoo/zaparoo
  fi
}

show_message() {
  local title="$1" message="$2"
  if command -v dialog >/dev/null 2>&1; then
    dialog --title "$title" --msgbox "$message" 20 72
  else
    echo
    echo "$title"
    echo "$message"
    echo
  fi
}

mkdir -p "$(dirname "$INSTALL_LOG")"
: > "$INSTALL_LOG"
exec > >(tee -a "$INSTALL_LOG") 2>&1

echo "Batocera Movie Player v${VERSION} clean installer"
echo

if ! command -v mpv >/dev/null 2>&1; then
  show_message "INSTALLATION STOPPED" "MPV was not found. This package is intended for Batocera 42."
  exit 1
fi

ZAPAROO="$(find_zaparoo)"
if [ -z "$ZAPAROO" ]; then
  show_message "INSTALLATION STOPPED" "Zaparoo Core was not found.\n\nInstall Zaparoo Core from Batocera's Content Downloader, then run this installer again."
  exit 1
fi

CORE_VERSION="$("$ZAPAROO" -version 2>&1 | head -n 1 || true)"
echo "Zaparoo Core: ${CORE_VERSION:-version unknown}"

mkdir -p "$APP_DIR/scripts" "$APP_DIR/progress" "$APP_DIR/watch_later"
mkdir -p "$LAUNCHER_DIR" "$MOVIE_DIR" "$MOVIE_DIR/custom-posters"
mkdir -p "$MOVIE_DIR/images" "$MOVIE_DIR/thumbnails" "$PORTS_DIR" "$ES_CONFIG_DIR"

# Stop earlier transient playback processes before replacing their code.
for pid_file in /tmp/batocera-movie-player/session.pid /tmp/batocera-movie-player/mpv.pid /tmp/batocera-movie-player/mpv-child.pid; do
  [ -f "$pid_file" ] || continue
  old_pid="$(cat "$pid_file" 2>/dev/null || true)"
  case "$old_pid" in
    ''|*[!0-9]*) ;;
    *) kill "$old_pid" 2>/dev/null || true
       for _ in 1 2 3 4 5 6 7 8 9 10; do kill -0 "$old_pid" 2>/dev/null || break; sleep 0.1; done
       kill -9 "$old_pid" 2>/dev/null || true ;;
  esac
done

SAVED_DATA="/userdata/system/batocera-movie-player-saved-data"
if [ -d "$SAVED_DATA" ]; then
  cp -a "$SAVED_DATA/progress/." "$APP_DIR/progress/" 2>/dev/null || true
  cp -a "$SAVED_DATA/watch_later/." "$APP_DIR/watch_later/" 2>/dev/null || true
  [ -f "$SAVED_DATA/settings.conf" ] && cp "$SAVED_DATA/settings.conf" "$APP_DIR/settings.conf"
fi

# Consolidate any genuine legacy movie folder. This never creates a second
# search path and never deletes a conflicting file without a SHA-256 match.
cp "$SOURCE_DIR/files/migrate_movies.py" "$APP_DIR/migrate_movies.py"
/usr/bin/python3 "$APP_DIR/migrate_movies.py"

copy_app_file() {
  cp "$SOURCE_DIR/files/$1" "$APP_DIR/$1"
}

copy_app_file movie-player.sh
copy_app_file movie-session.py
copy_app_file movie-client.py
copy_app_file controller_bridge.py
copy_app_file progress_tracker.py
copy_app_file mpv-input.conf
copy_app_file playlist_builder.py
copy_app_file setup.sh
copy_app_file reset-player.sh
copy_app_file waiting.png
copy_app_file game-loading-1.png
copy_app_file game-loading-2.png
copy_app_file game-loading-3.png
copy_app_file confirm.wav
copy_app_file warning.wav
copy_app_file feedback.sh
copy_app_file BatoceraMoviePlayer.toml
copy_app_file es_systems_movies.cfg
copy_app_file build_movie_gamelist.py
copy_app_file configure_zaparoo.py
copy_app_file zaparoo_media_refresh.py
copy_app_file zaparoo-launch.py
copy_app_file install_movies_theme.py
copy_app_file activate_movies_theme.py
copy_app_file install_autostart.py
copy_app_file movies-logo.png
copy_app_file movies-theme.xml
copy_app_file movies-background.png
copy_app_file movies-theater-background.png
copy_app_file movie-poster-frame.png
copy_app_file movies-panel.svg
copy_app_file movies-carousel-rules.svg
copy_app_file MANUAL-POSTERS.txt
# Remove obsolete competing theme and installer-art files from earlier betas.
rm -f "$APP_DIR/install_carbon_movies_theme.py" "$APP_DIR/movies-carbon-theme.xml" "$APP_DIR/sync_system_theme.py" "$APP_DIR/jrt3d-ascii.txt" "$APP_DIR/jrt3d-installer.png"
cp "$SOURCE_DIR/files/safe_stop.lua" "$APP_DIR/scripts/safe_stop.lua"
printf '%s\n' "$VERSION" > "$APP_DIR/VERSION"

if [ ! -f "$APP_DIR/settings.conf" ]; then
  cp "$SOURCE_DIR/files/settings.conf" "$APP_DIR/settings.conf"
fi

# One authoritative launcher and one authoritative movie path.
cp "$SOURCE_DIR/files/BatoceraMoviePlayer.toml" "$LAUNCHER_DIR/BatoceraMoviePlayer.toml"
cp "$SOURCE_DIR/files/es_systems_movies.cfg" "$ES_CONFIG_DIR/es_systems_movies.cfg"
# The user's working Zaparoo network/pairing configuration is never modified.

# Install the visible Movies-system assets.
cp "$SOURCE_DIR/files/movies-logo.png" "$MOVIE_DIR/movies-logo.png"
cp "$SOURCE_DIR/files/movies-background.png" "$MOVIE_DIR/movies-background.png"
cp "$SOURCE_DIR/files/movies-theater-background.png" "$MOVIE_DIR/movies-theater-background.png"
cp "$SOURCE_DIR/files/movie-poster-frame.png" "$MOVIE_DIR/movie-poster-frame.png"
cp "$SOURCE_DIR/files/movies-panel.svg" "$MOVIE_DIR/movies-panel.svg"
cp "$SOURCE_DIR/files/movies-carousel-rules.svg" "$MOVIE_DIR/movies-carousel-rules.svg"
cp "$SOURCE_DIR/files/MANUAL-POSTERS.txt" "$MOVIE_DIR/MANUAL-POSTERS.txt"
# Bind one Movies overlay to stock Carbon. F1 and EmulationStation are left
# completely alone during installation. The same verified theme operation is
# repeated by the managed startup block before future sessions, preventing the
# frontend from restoring a stale view without ever blanking the F1 desktop.
if /usr/bin/python3 "$APP_DIR/install_movies_theme.py"; then
  echo "Movies theme: exact beta15 ROM-folder override verified"
  THEME_STATUS="PASSED"
else
  show_message "INSTALLATION STOPPED" "The stock Batocera Carbon theme was not found.\n\nMovies was not given a fallback theme because public beta must install consistently."
  exit 1
fi

# Install maintenance entries. The repair tool is a clearly labelled fallback;
# ordinary movie changes are handled automatically and shown by Update Game Lists.
cp "$SOURCE_DIR/files/Movie Player Setup.sh" "$PORTS_DIR/Movie Player Setup.sh"
rm -f "$PORTS_DIR/Refresh Movie Library.sh"
cp "$SOURCE_DIR/files/Repair Movie Library - Only If Needed.sh" "$PORTS_DIR/Repair Movie Library - Only If Needed.sh"
cp "$SOURCE_DIR/files/Movie Player Version.sh" "$PORTS_DIR/Movie Player Version.sh"
cp "$SOURCE_DIR/files/Movie Player Diagnostics.sh" "$PORTS_DIR/Movie Player Diagnostics.sh"
cp "$SOURCE_DIR/files/Collect Movie Player Logs.sh" "$PORTS_DIR/Collect Movie Player Logs.sh"
rm -f "$PORTS_DIR/Repair Zaparoo Movies.sh"
rm -f "$PORTS_DIR/Movie Player Waiting Screen.sh"
rm -f "$PORTS_DIR/Show Scan Card Screen.sh"
rm -f "$PORTS_DIR/Test First Movie with Zaparoo.sh"

chmod +x "$APP_DIR/movie-player.sh" "$APP_DIR/controller_bridge.py"
chmod +x "$APP_DIR/movie-session.py" "$APP_DIR/movie-client.py"
chmod +x "$APP_DIR/progress_tracker.py" "$APP_DIR/playlist_builder.py"
chmod +x "$APP_DIR/build_movie_gamelist.py" "$APP_DIR/configure_zaparoo.py"
chmod +x "$APP_DIR/zaparoo_media_refresh.py"
chmod +x "$APP_DIR/zaparoo-launch.py" "$APP_DIR/migrate_movies.py"
chmod +x "$APP_DIR/install_movies_theme.py"
chmod +x "$APP_DIR/activate_movies_theme.py"
chmod +x "$APP_DIR/install_autostart.py"
chmod +x "$APP_DIR/setup.sh" "$APP_DIR/reset-player.sh" "$APP_DIR/feedback.sh"
chmod +x "$PORTS_DIR/Movie Player Setup.sh"
chmod +x "$PORTS_DIR/Repair Movie Library - Only If Needed.sh" "$PORTS_DIR/Movie Player Version.sh"
chmod +x "$PORTS_DIR/Movie Player Diagnostics.sh"
chmod +x "$PORTS_DIR/Collect Movie Player Logs.sh"

/usr/bin/python3 "$APP_DIR/build_movie_gamelist.py" "$MOVIE_DIR" || true
/usr/bin/python3 "$APP_DIR/install_autostart.py"

# Keep the lightweight session manager ready so the first card scan can remove
# EmulationStation immediately instead of displaying its side menu during startup.
nohup /usr/bin/python3 "$APP_DIR/movie-session.py" </dev/null >/dev/null 2>&1 &
for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
  [ -S /tmp/batocera-movie-player/session.sock ] && break
  sleep 0.05
done
if [ ! -S /tmp/batocera-movie-player/session.sock ]; then
  show_message "INSTALLATION STOPPED" "The movie session manager did not start. No test should be attempted.\n\nOpen Ports - Collect Movie Player Logs."
  exit 1
fi

PHONE_STATUS="PRESERVED - NOT CHANGED"

MOVIE_COUNT="$(find -L "$MOVIE_DIR" -type f \( -iname '*.mp4' -o -iname '*.mkv' -o -iname '*.avi' -o -iname '*.mov' -o -iname '*.m4v' -o -iname '*.webm' -o -iname '*.mpeg' -o -iname '*.mpg' -o -iname '*.ts' -o -iname '*.m2ts' -o -iname '*.wmv' -o -iname '*.vob' \) 2>/dev/null | wc -l)"

SUCCESS_MESSAGE="BATOCERA MOVIE APP VERSION ${VERSION}

INSTALLATION SUCCESSFUL

THEME CHECK: ${THEME_STATUS}
Movies found: ${MOVIE_COUNT}
Zaparoo: ${CORE_VERSION:-version unknown}
Phone access: ${PHONE_STATUS}

Nothing will restart or reboot automatically.

Choose CLOSE INSTALLER to return to the F1 file manager.
When you are ready, close F1 normally yourself.

Created by Joshua R. Taylor
JRT3D.com • 2026
Developed with assistance from ChatGPT"

# This foreground window deliberately waits forever for the user. It neither
# restarts EmulationStation nor closes F1. Running dialog inside its own xterm
# makes the success result visible even when install.sh was double-clicked.
if command -v xterm >/dev/null 2>&1 && command -v dialog >/dev/null 2>&1 && [ -n "${DISPLAY:-}" ]; then
  xterm -T "Batocera Movie App Version ${VERSION} - Installed" -geometry 92x30 \
    -e sh -c 'dialog --title "$1" --ok-label "CLOSE INSTALLER" --msgbox "$2" 25 84; exit 0' \
    sh "INSTALLATION SUCCESSFUL" "$SUCCESS_MESSAGE"
else
  show_message "INSTALLATION SUCCESSFUL" "$SUCCESS_MESSAGE"
fi

echo
echo "Installation complete: Batocera Movie App Version ${VERSION}"
echo "Movie library: $MOVIE_DIR"
echo "Installer log: $INSTALL_LOG"
echo
echo "Installation confirmed. Batocera is running; installer closed normally."
exit 0
