#!/bin/bash
APP_DIR="/userdata/system/batocera-movie-player"
[ "$(sed -n 's/^sounds_enabled=//p' "$APP_DIR/settings.conf" 2>/dev/null)" = "true" ] || exit 0
name="${1:-confirm}"
[ "$name" = "warning" ] || name="confirm"
mpv --no-video --really-quiet --volume=24 --audio-display=no -- "$APP_DIR/$name.wav" >/dev/null 2>&1 &
