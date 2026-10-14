#!/usr/bin/python3
"""Minimal, dependency-free Linux gamepad bridge for Batocera's MPV player."""

import glob
import json
import math
import os
import socket
import struct
import sys
import threading
import time
from selectors import DefaultSelector, EVENT_READ

SOCKET_PATH = sys.argv[1]
SESSION_SOCKET = "/tmp/batocera-movie-player/session.sock"
HANDOFF_MARKER = "/tmp/batocera-movie-player/game-handoff"
MOVIE_SWITCH_MARKER = "/tmp/batocera-movie-player/movie-switch"
EVENT = struct.Struct("llHHi")
EV_KEY = 1
EV_ABS = 3

# Linux gamepad codes used by standard Xbox/PlayStation/Switch-style pads.
BTN_SOUTH, BTN_EAST, BTN_NORTH, BTN_WEST = 304, 305, 307, 308
BTN_TL, BTN_TR, BTN_TL2, BTN_TR2 = 310, 311, 312, 313
BTN_SELECT, BTN_START = 314, 315
BTN_THUMBL, BTN_THUMBR = 317, 318
DPAD_UP, DPAD_DOWN, DPAD_LEFT, DPAD_RIGHT = 544, 545, 546, 547
ABS_HAT0X, ABS_HAT0Y = 16, 17

# Linux keyboard event codes. Reading them here makes physical keyboards and
# Zaparoo's virtual keyboard use the same reliable MPV IPC path as controllers.
KEY_ESC, KEY_ENTER, KEY_SPACE = 1, 28, 57
KEY_Q, KEY_R, KEY_I, KEY_O = 16, 19, 23, 24
KEY_A, KEY_S, KEY_F = 30, 31, 33
KEY_Z, KEY_X, KEY_C, KEY_N, KEY_M = 44, 45, 46, 49, 50
KEY_LEFTSHIFT, KEY_RIGHTSHIFT = 42, 54
KEY_UP, KEY_PAGEUP, KEY_LEFT = 103, 104, 105
KEY_RIGHT, KEY_DOWN, KEY_PAGEDOWN = 106, 108, 109

pressed = set()
last_action = {}
LOG_PATH = "/userdata/system/logs/movie-controller.log"

# Standard Linux codes plus older/generic USB-pad button codes. Some Batocera
# controllers expose both interfaces, so actions (not raw codes) are deduped.
PAUSE_CODES = {BTN_SOUTH, 288, 256}
STOP_CODES = {BTN_EAST, 289, 257}
FIT_CODES = {BTN_NORTH, 290, 258}
ZOOM_CODES = {BTN_WEST, 291, 259}
INFO_CODES = set()
fill_enabled = False
zoom_step = 0
restart_prompt = False
restart_prompt_deadline = 0.0
restart_prompt_was_paused = False


def log_event(message):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as log:
            log.write(f"{time.strftime('%F %T')} {message}\n")
    except OSError:
        pass


def property_value(name, fallback=None):
    """Read one live MPV property through IPC, returning fallback on old VOs."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(0.5)
            client.connect(SOCKET_PATH)
            request_id = int(time.monotonic_ns() & 0x7fffffff)
            message = {"command": ["get_property", name], "request_id": request_id}
            client.sendall((json.dumps(message) + "\n").encode())
            response = b""
            while b"\n" not in response:
                block = client.recv(4096)
                if not block:
                    break
                response += block
            for line in response.splitlines():
                reply = json.loads(line.decode())
                if reply.get("request_id") == request_id and reply.get("error") == "success":
                    return reply.get("data", fallback)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        pass
    return fallback


def fill_zoom_amount():
    """Calculate the exact center-crop zoom for the active video and window."""
    video_aspect = property_value("video-params/aspect", 4 / 3)
    window_aspect = property_value("osd-dimensions/aspect", 16 / 9)
    try:
        video_aspect = float(video_aspect)
        window_aspect = float(window_aspect)
        if video_aspect <= 0 or window_aspect <= 0:
            raise ValueError
        ratio = max(video_aspect / window_aspect, window_aspect / video_aspect)
        # A number of older 4:3 transfers are encoded as 16:9 frames with the
        # pillarbox bars baked into the pixels. MPV reports these as 16:9, so an
        # automatic ratio calculation would incorrectly produce no crop.
        if ratio < 1.03:
            ratio = 4 / 3
        log_event(f"fill geometry video_aspect={video_aspect:.4f} window_aspect={window_aspect:.4f} scale={ratio:.4f}")
        return round(ratio, 4)
    except (TypeError, ValueError, ZeroDivisionError):
        log_event("fill geometry query failed; using 1.3333 pillarbox crop")
        return 4 / 3


def reset_picture_filter():
    command(["vf", "remove", "@movie-picture"])


def apply_zoom_filter(scale):
    """Zoom decoded pixels, independent of Batocera's video-output driver."""
    reset_picture_filter()
    command(["set", "panscan", "0.0"])
    command(["set", "video-scale-x", "1.0"])
    command(["set", "video-scale-y", "1.0"])
    command(["set", "video-pan-x", "0.0"])
    command(["set", "video-pan-y", "0.0"])
    command(["set", "video-zoom", "0.0"])
    if scale > 1.001:
        command(["vf", "add", f"@movie-picture:crop=iw/{scale:.4f}:ih/{scale:.4f}"])
    actual = property_value("vf", "unavailable")
    log_event(f"picture zoom requested={scale:.4f} actual_filter={actual}")


def apply_fill_filter():
    """Center-crop the decoded source to the display ratio."""
    reset_picture_filter()
    width = property_value("video-params/w", 0)
    height = property_value("video-params/h", 0)
    target = property_value("osd-dimensions/aspect", 16 / 9)
    try:
        width, height, target = int(width), int(height), float(target)
        if width <= 0 or height <= 0 or target <= 0:
            raise ValueError
        source = width / height
        if source < target:
            crop_w, crop_h = width, max(2, int(width / target))
        elif source > target:
            crop_w, crop_h = max(2, int(height * target)), height
        else:
            # Handle 4:3 content stored with black pillars inside a 16:9 frame.
            crop_w = max(2, int(width * 0.75))
            crop_h = max(2, int(crop_w / target))
        crop_w -= crop_w % 2
        crop_h -= crop_h % 2
    except (TypeError, ValueError, ZeroDivisionError):
        crop_w, crop_h = 1440, 810
    command(["set", "video-zoom", "0.0"])
    command(["vf", "add", f"@movie-picture:crop={crop_w}:{crop_h}"])
    actual = property_value("vf", "unavailable")
    log_event(f"picture fill crop={crop_w}x{crop_h} actual_filter={actual}")


def toggle_fit_fill():
    global fill_enabled, zoom_step
    fill_enabled = not fill_enabled
    zoom_step = 0
    if fill_enabled:
        apply_fill_filter()
    else:
        reset_picture_filter()
    label = "PICTURE: FILL" if fill_enabled else "PICTURE: FIT"
    command(["show-text", label, 1800])


def cycle_zoom():
    global fill_enabled, zoom_step
    zoom_step = (zoom_step + 1) % 4
    fill_enabled = False
    scales = (1.0, 1.15, 1.30, 1.50)
    apply_zoom_filter(scales[zoom_step])
    label = "OFF" if zoom_step == 0 else f"{round(scales[zoom_step] * 100)}%"
    command(["show-text", f"ZOOM: {label}", 1800])


def command(payload):
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(0.25)
            client.connect(SOCKET_PATH)
            client.sendall((json.dumps({"command": payload}) + "\n").encode())
    except OSError:
        pass


def game_handoff():
    """Tell the session that Batocera's system-exit means a game is pending."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(4.0)
            client.connect(SESSION_SOCKET)
            client.sendall(b'{"action":"game_handoff"}\n')
            while not client.recv(256).endswith(b"\n"):
                pass
    except OSError as exc:
        log_event(f"game handoff request failed: {exc}")


def restart_movie():
    command(["seek", 0, "absolute+exact"])
    command(["set", "pause", "no"])
    command(["show-text", "RESTARTED FROM BEGINNING", 2200])
    log_event("movie restarted from beginning")


def open_restart_prompt():
    global restart_prompt, restart_prompt_deadline, restart_prompt_was_paused
    restart_prompt_was_paused = bool(property_value("pause", False))
    restart_prompt = True
    restart_prompt_deadline = time.monotonic() + 12.0
    command(["set", "pause", "yes"])
    command(["show-text", "RESTART MOVIE FROM BEGINNING?\n\nA = YES     B = CANCEL", 12000])
    log_event("restart confirmation opened")


def close_restart_prompt(resume=True, message="RESTART CANCELLED"):
    global restart_prompt, restart_prompt_deadline
    was_paused = restart_prompt_was_paused
    restart_prompt = False
    restart_prompt_deadline = 0.0
    if resume and not was_paused:
        command(["set", "pause", "no"])
    if message:
        command(["show-text", message, 1200])


def confirm_restart_prompt():
    close_restart_prompt(resume=False, message="")
    restart_movie()


def cancel_restart_prompt():
    close_restart_prompt(resume=True)
    log_event("restart confirmation cancelled")


def deferred_stop():
    """Allow Core's pending replacement marker to win the exit-event race."""
    if not rate_limit("deferred-stop", 0.6):
        return
    time.sleep(0.8)
    if os.path.exists(HANDOFF_MARKER):
        command(["set", "pause", "yes"])
        command(["show-text", "LOADING GAME...\nPLEASE WAIT", 30000])
    elif os.path.exists(MOVIE_SWITCH_MARKER):
        # Core closes its old launcher record during a movie-to-movie scan.
        # The persistent MPV process must stay alive for the incoming replace.
        log_event("ignored synthetic exit during movie replacement")
    else:
        command(["run", "touch", "/tmp/batocera-movie-player/manual_exit"])
        command(["quit"])


def rate_limit(name, seconds=0.12):
    now = time.monotonic()
    if now - last_action.get(name, 0) < seconds:
        return False
    last_action[name] = now
    return True


def act(code):
    if code in PAUSE_CODES and rate_limit("pause", 0.25):
        command(["cycle", "pause"])
    elif code in FIT_CODES and rate_limit("fit", 0.25):
        toggle_fit_fill()
    elif code in ZOOM_CODES and rate_limit("zoom", 0.25):
        cycle_zoom()
    elif code in INFO_CODES and rate_limit("info", 0.25):
        command(["show-text", "${media-title}  •  ${time-pos} / ${duration}", 3000])
    elif code == BTN_START and rate_limit("pause", 0.25):
        command(["cycle", "pause"])
    elif code == BTN_SELECT and rate_limit("restart-prompt", 0.5):
        open_restart_prompt()
    elif code == BTN_THUMBL and rate_limit("restart", 0.5):
        restart_movie()
    elif code in (DPAD_LEFT,):
        command(["seek", -10, "relative"])
    elif code in (DPAD_RIGHT,):
        command(["seek", 10, "relative"])
    elif code == DPAD_UP:
        command(["add", "volume", 5])
    elif code == DPAD_DOWN:
        command(["add", "volume", -5])
    elif code in (BTN_TL, BTN_TL2):
        command(["seek", -60, "relative"])
    elif code in (BTN_TR, BTN_TR2):
        command(["seek", 60, "relative"])
    # Physical keyboard and Zaparoo virtual-key events use MPV's socket instead
    # of window focus. mpv-input.conf intentionally contains no duplicate keys.
    elif code in (KEY_SPACE, KEY_ENTER) and rate_limit("pause", 0.35):
        command(["cycle", "pause"])
        command(["show-text", "PLAY / PAUSE", 1200])
    elif code in (KEY_ESC, KEY_Q, KEY_X) and rate_limit("stop", 0.35):
        threading.Thread(target=deferred_stop, daemon=True).start()
    elif code == KEY_LEFT and rate_limit("key-left", 0.2):
        command(["seek", -10, "relative"])
        command(["show-text", "BACK 10 SECONDS", 1200])
    elif code == KEY_RIGHT and rate_limit("key-right", 0.2):
        command(["seek", 10, "relative"])
        command(["show-text", "FORWARD 10 SECONDS", 1200])
    elif code == KEY_PAGEUP and rate_limit("key-pageup", 0.2):
        command(["seek", -60, "relative"])
    elif code == KEY_PAGEDOWN and rate_limit("key-pagedown", 0.2):
        command(["seek", 60, "relative"])
    elif code == KEY_UP and rate_limit("key-up", 0.15):
        command(["add", "volume", 5])
    elif code == KEY_DOWN and rate_limit("key-down", 0.15):
        command(["add", "volume", -5])
    elif code == KEY_I and rate_limit("key-info", 0.35):
        command(["show-text", "${media-title}  •  ${time-pos} / ${duration}", 3000])
    elif code == KEY_O and rate_limit("key-progress", 0.35):
        command(["show-progress"])
    elif code == KEY_R and rate_limit("key-restart", 0.35):
        restart_movie()
    elif code == KEY_S and rate_limit("key-subs", 0.35):
        command(["cycle", "sub-visibility"])
    elif code == KEY_N and rate_limit("key-next-sub", 0.35):
        command(["cycle", "sub"])
    elif code == KEY_A and rate_limit("key-audio", 0.35):
        command(["cycle", "audio"])
    elif code == KEY_C and rate_limit("key-chapter", 0.35):
        direction = -1 if KEY_LEFTSHIFT in pressed or KEY_RIGHTSHIFT in pressed else 1
        command(["add", "chapter", direction])
    elif code == KEY_M and rate_limit("key-mute", 0.35):
        command(["cycle", "mute"])
    elif code == KEY_F and rate_limit("key-fit", 0.35):
        toggle_fit_fill()
    elif code == KEY_Z and rate_limit("key-zoom", 0.35):
        cycle_zoom()


selector = DefaultSelector()
for path in glob.glob("/dev/input/event*"):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        selector.register(fd, EVENT_READ)
    except OSError:
        pass

while not os.path.exists(SOCKET_PATH):
    time.sleep(0.05)

while True:
    for key, _ in selector.select(timeout=1):
        try:
            data = os.read(key.fd, EVENT.size * 32)
        except OSError:
            continue
        for offset in range(0, len(data) - EVENT.size + 1, EVENT.size):
            _, _, event_type, code, value = EVENT.unpack_from(data, offset)
            if event_type == EV_KEY:
                if value:
                    pressed.add(code)
                    if restart_prompt and code in PAUSE_CODES and value == 1:
                        confirm_restart_prompt()
                    elif restart_prompt and code in STOP_CODES and value == 1:
                        cancel_restart_prompt()
                    elif code in STOP_CODES and value == 1:
                        command(["run", "touch", "/tmp/batocera-movie-player/manual_exit"])
                        command(["quit"])
                    elif code == BTN_SOUTH and BTN_SELECT in pressed and value == 1:
                        restart_movie()
                    elif code in (BTN_SELECT, BTN_START) and {BTN_SELECT, BTN_START} <= pressed:
                        # Batocera hotkeygen emits Select+Start when Zaparoo is
                        # preempting the movie for another system.  Starting ES
                        # before quitting MPV prevents the pending game launch
                        # from being lost at the menu.  A normal B exit remains
                        # the ordinary return-to-Movies path above.
                        if rate_limit("game-handoff", 1.0):
                            if restart_prompt:
                                close_restart_prompt(resume=False, message="")
                            game_handoff()
                    elif value == 1:
                        try:
                            with open(LOG_PATH, "a", encoding="utf-8") as log:
                                log.write(f"{time.strftime('%F %T')} key code={code}\n")
                        except OSError:
                            pass
                        act(code)
                else:
                    pressed.discard(code)
            elif event_type == EV_ABS:
                if code == ABS_HAT0X and value and rate_limit("hatx"):
                    act(DPAD_RIGHT if value > 0 else DPAD_LEFT)
                elif code == ABS_HAT0Y and value and rate_limit("haty"):
                    act(DPAD_DOWN if value > 0 else DPAD_UP)
    if restart_prompt and time.monotonic() >= restart_prompt_deadline:
        cancel_restart_prompt()
