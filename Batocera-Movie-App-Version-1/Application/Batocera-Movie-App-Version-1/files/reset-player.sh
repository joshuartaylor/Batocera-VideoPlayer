#!/bin/bash
RUNTIME_DIR="/tmp/batocera-movie-player"
for file in "$RUNTIME_DIR/mpv.pid" "$RUNTIME_DIR/waiting.pid"; do
  [ -f "$file" ] || continue
  pid="$(cat "$file" 2>/dev/null || true)"
  case "$pid" in ''|*[!0-9]*) ;; *) kill "$pid" 2>/dev/null || true ;; esac
done
mkdir -p "$RUNTIME_DIR"
mpv --fullscreen --ontop --no-border --no-input-default-bindings --input-conf=/userdata/system/batocera-movie-player/mpv-input.conf --loop-file=inf --image-display-duration=inf -- /userdata/system/batocera-movie-player/waiting.png >/dev/null 2>&1 &
echo $! > "$RUNTIME_DIR/waiting.pid"
