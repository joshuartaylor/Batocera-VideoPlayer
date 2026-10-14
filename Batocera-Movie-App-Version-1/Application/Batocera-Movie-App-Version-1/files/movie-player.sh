#!/bin/bash
set -u

MEDIA_PATH="${1:-}"
PLAY_MODE="${2:-resume}"
LAUNCH_SOURCE="${3:-zaparoo}"
APP_DIR="/userdata/system/batocera-movie-player"
RUNTIME_DIR="/tmp/batocera-movie-player"
SOCKET_PATH="$RUNTIME_DIR/mpv.sock"
PID_FILE="$RUNTIME_DIR/mpv.pid"
MPV_CHILD_PID_FILE="$RUNTIME_DIR/mpv-child.pid"
WAITING_PID_FILE="$RUNTIME_DIR/waiting.pid"
MANUAL_EXIT_FILE="$RUNTIME_DIR/manual_exit"
ACTIVE_INSTANCE_FILE="$RUNTIME_DIR/active-instance"
SETTINGS_FILE="$APP_DIR/settings.conf"
LOG_FILE="/userdata/system/logs/batocera-movie-player.log"
ES_STOPPED_BY_PLAYER=0

stop_pid_file() {
  local file="$1" pid
  [ -f "$file" ] || return 0
  pid="$(cat "$file" 2>/dev/null || true)"
  case "$pid" in
    ''|*[!0-9]*) ;;
    *)
      kill "$pid" 2>/dev/null || true
      for _ in 1 2 3 4 5 6 7 8 9 10; do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.1
      done
      kill -9 "$pid" 2>/dev/null || true
      ;;
  esac
  rm -f "$file"
}

restore_emulationstation() {
  [ "$ES_STOPPED_BY_PLAYER" -eq 1 ] || return 0
  ES_STOPPED_BY_PLAYER=0
  printf '%s Scheduling EmulationStation restore after launcher shutdown\n' "$(date '+%F %T')" >> "$LOG_FILE"
  # Core uses a blocking launcher and may terminate children while closing it.
  # Start ES later in a new session so it cannot be killed with this wrapper.
  RESTORE_COMMAND='sleep 3; printf "%s Starting EmulationStation after movie exit\n" "$(date "+%F %T")" >> /userdata/system/logs/movie-es-restart.log; /etc/init.d/S31emulationstation start >> /userdata/system/logs/movie-es-restart.log 2>&1; sleep 3; if ! pgrep -f "[e]mulationstation" >/dev/null 2>&1 && command -v batocera-es-swissknife >/dev/null 2>&1; then batocera-es-swissknife --restart >> /userdata/system/logs/movie-es-restart.log 2>&1; fi'
  if command -v setsid >/dev/null 2>&1; then
    setsid -f sh -c "$RESTORE_COMMAND" </dev/null >/dev/null 2>&1
  else
    nohup sh -c "$RESTORE_COMMAND" </dev/null >/dev/null 2>&1 &
  fi
}

setting() {
  local key="$1" default="$2" value
  value="$(sed -n "s/^${key}=//p" "$SETTINGS_FILE" 2>/dev/null | tail -n 1)"
  printf '%s' "${value:-$default}"
}

if [ -z "$MEDIA_PATH" ] || [ ! -f "$MEDIA_PATH" ]; then
  echo "Movie not found: $MEDIA_PATH" >&2
  printf '%s Movie not found: %s\n' "$(date '+%F %T')" "$MEDIA_PATH" >> "$LOG_FILE"
  exit 2
fi

printf '%s Launching: %s\n' "$(date '+%F %T')" "$MEDIA_PATH" >> "$LOG_FILE"

mkdir -p "$RUNTIME_DIR"
rm -f "$MANUAL_EXIT_FILE"

if [ "$(setting safe_mode false)" = "true" ] && [ -f "$RUNTIME_DIR/last_launch" ]; then
  NOW="$(date +%s)"
  LAST="$(cat "$RUNTIME_DIR/last_launch" 2>/dev/null || echo 0)"
  if [ $((NOW - LAST)) -lt 2 ]; then
    exit 0
  fi
fi
date +%s > "$RUNTIME_DIR/last_launch"

# Claim playback ownership before touching the previous player. Only the newest
# scanned movie is allowed to restore EmulationStation when it eventually exits.
INSTANCE_ID="$$-$(date +%s)"
OLD_WRAPPER=""
if [ -f "$PID_FILE" ]; then
  OLD_WRAPPER="$(cat "$PID_FILE" 2>/dev/null || true)"
  case "$OLD_WRAPPER" in
    ''|*[!0-9]*) OLD_WRAPPER="" ;;
    *) kill -0 "$OLD_WRAPPER" 2>/dev/null || OLD_WRAPPER="" ;;
  esac
fi
printf '%s' "$INSTANCE_ID" > "$ACTIVE_INSTANCE_FILE"

cleanup() {
  if [ -n "${MPV_PID:-}" ]; then kill "$MPV_PID" 2>/dev/null || true; fi
  if [ -n "${BRIDGE_PID:-}" ]; then kill "$BRIDGE_PID" 2>/dev/null || true; fi
  if [ -n "${PROGRESS_PID:-}" ]; then kill "$PROGRESS_PID" 2>/dev/null || true; fi

  # A replaced movie must never tear down the new player's socket or restart ES.
  if [ -f "$ACTIVE_INSTANCE_FILE" ] && [ "$(cat "$ACTIVE_INSTANCE_FILE" 2>/dev/null)" = "$INSTANCE_ID" ]; then
    rm -f "$SOCKET_PATH" "$MPV_CHILD_PID_FILE" "$PID_FILE" "$ACTIVE_INSTANCE_FILE"
    restore_emulationstation
  fi
}
trap cleanup EXIT INT TERM

# When another card is scanned, take ownership from the old wrapper without
# running its cleanup trap. Its cleanup is what previously restarted Batocera
# over the newly selected movie.
if [ -n "$OLD_WRAPPER" ] && [ "$OLD_WRAPPER" != "$$" ]; then
  ES_STOPPED_BY_PLAYER=1
  printf '%s Replacing active movie wrapper %s without restarting ES\n' "$(date '+%F %T')" "$OLD_WRAPPER" >> "$LOG_FILE"
  kill "$OLD_WRAPPER" 2>/dev/null || true
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    kill -0 "$OLD_WRAPPER" 2>/dev/null || break
    sleep 0.05
  done
  kill -9 "$OLD_WRAPPER" 2>/dev/null || true
  stop_pid_file "$MPV_CHILD_PID_FILE"
fi
echo "$$" > "$PID_FILE"

# Card scans must remove EmulationStation immediately, before library cleanup,
# controller startup, or MPV preparation can leave time for the left menu to draw.
if [ "$LAUNCH_SOURCE" != "menu" ] && pgrep -f '[e]mulationstation' >/dev/null 2>&1; then
  printf '%s Immediately stopping EmulationStation for card playback\n' "$(date '+%F %T')" >> "$LOG_FILE"
  ES_STOPPED_BY_PLAYER=1
  /etc/init.d/S31emulationstation stop >> "$LOG_FILE" 2>&1 || true
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
    pgrep -f '[e]mulationstation' >/dev/null 2>&1 || break
    sleep 0.05
  done
fi

# Remove orphaned movie-player MPV processes left by an interrupted Core launch.
# Limit this strictly to MPV commands containing our one movie-library path.
for proc in /proc/[0-9]*; do
  [ -r "$proc/cmdline" ] || continue
  CMDLINE="$(tr '\0' ' ' < "$proc/cmdline" 2>/dev/null || true)"
  case "$CMDLINE" in
    *mpv*"/userdata/roms/movies/"*) kill "${proc##*/}" 2>/dev/null || true ;;
  esac
done

if [ -f "$WAITING_PID_FILE" ]; then
  WAITING_PID="$(cat "$WAITING_PID_FILE" 2>/dev/null || true)"
  case "$WAITING_PID" in
    ''|*[!0-9]*) ;;
    *) kill "$WAITING_PID" 2>/dev/null || true
       for _ in 1 2 3 4 5; do kill -0 "$WAITING_PID" 2>/dev/null || break; sleep 0.1; done ;;
  esac
  rm -f "$WAITING_PID_FILE"
fi

rm -f "$SOCKET_PATH"
: > /userdata/system/logs/movie-controller.log

printf '%s Launch source: %s\n' "$(date '+%F %T')" "$LAUNCH_SOURCE" >> "$LOG_FILE"

export DISPLAY="${DISPLAY:-:0.0}"

/usr/bin/python3 "$APP_DIR/controller_bridge.py" "$SOCKET_PATH" &
BRIDGE_PID=$!
/usr/bin/python3 "$APP_DIR/progress_tracker.py" "$SOCKET_PATH" "$MEDIA_PATH" &
PROGRESS_PID=$!

END_BEHAVIOR="$(setting end_behavior waiting)"
DEFAULT_VOLUME="$(setting default_volume 80)"
START_ARGS=()
if [ "$PLAY_MODE" = "fresh" ]; then
  START_ARGS=(--start=0 --no-resume-playback)
fi

PLAY_ARGS=(-- "$MEDIA_PATH")
if [ "$END_BEHAVIOR" = "next" ]; then
  PLAYLIST="$RUNTIME_DIR/movies.m3u"
  /usr/bin/python3 "$APP_DIR/playlist_builder.py" "$MEDIA_PATH" "$PLAYLIST"
  PLAY_ARGS=("--playlist=$PLAYLIST")
fi

KEEP_OPEN="no"
LOOP_FILE="no"
[ "$END_BEHAVIOR" = "hold" ] && KEEP_OPEN="yes"
[ "$END_BEHAVIOR" = "replay" ] && LOOP_FILE="inf"

mpv \
  --fullscreen \
  --ontop \
  --no-border \
  --force-window=yes \
  --keepaspect=yes \
  --video-unscaled=no \
  --video-zoom=0 \
  --panscan=0 \
  --keep-open="$KEEP_OPEN" \
  --loop-file="$LOOP_FILE" \
  --osd-level=1 \
  --input-ipc-server="$SOCKET_PATH" \
  --input-conf="$APP_DIR/mpv-input.conf" \
  --script="$APP_DIR/scripts/safe_stop.lua" \
  --volume="$DEFAULT_VOLUME" \
  --save-position-on-quit \
  --watch-later-directory=/userdata/system/batocera-movie-player/watch_later \
  --sub-auto=fuzzy \
  --audio-file-auto=fuzzy \
  "${START_ARGS[@]}" "${PLAY_ARGS[@]}" >> "$LOG_FILE" 2>&1 &
MPV_PID=$!
echo "$MPV_PID" > "$MPV_CHILD_PID_FILE"
wait "$MPV_PID"
RESULT=$?
rm -f "$MPV_CHILD_PID_FILE"

if [ "$RESULT" -ne 0 ]; then
  touch "$MANUAL_EXIT_FILE"
  printf '%s MPV failed with exit code %s\n' "$(date '+%F %T')" "$RESULT" >> "$LOG_FILE"
  if command -v xterm >/dev/null 2>&1; then
    xterm -fullscreen -e bash -c 'echo; echo "MOVIE COULD NOT START"; echo; echo "The last playback messages are:"; echo; tail -n 30 /userdata/system/logs/batocera-movie-player.log; echo; read -r -p "Press Enter to return to Batocera."'
  fi
fi

# Return to the Movies list after playback. A separate waiting-screen MPV would
# compete with EmulationStation for the display on Batocera 42.
rm -f "$MANUAL_EXIT_FILE"
exit "$RESULT"
