#!/usr/bin/python3
"""Launch an EmulationStation movie through Core, with guaranteed playback.

Core receives the first request so Current Media/Write Playing can work. If
that handoff does not activate the player promptly, the proven local client
takes over automatically. A Core bookkeeping failure must never prevent a
movie selected in Batocera from playing.
"""
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

raw_movie = sys.argv[1] if len(sys.argv) > 1 else ''
# EmulationStation may pass its shell-escaped ROM substitution inside quotes,
# leaving literal backslashes before spaces. Decode that form while preserving
# ordinary paths received from Zaparoo Core.
if '\\' in raw_movie:
    try:
        decoded = shlex.split(raw_movie)
        if len(decoded) == 1:
            raw_movie = decoded[0]
    except ValueError:
        pass
movie = os.path.realpath(raw_movie) if raw_movie else ''
runtime = Path('/tmp/batocera-movie-player')
session_socket = runtime / 'session.sock'
log_file = Path('/userdata/system/logs/movie-zaparoo-launch.log')


def write_log(message):
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open('a', encoding='utf-8') as stream:
        stream.write(f'{time.strftime("%F %T")} {message}\n')


def find_core():
    candidates = [
        shutil.which('zaparoo'),
        '/userdata/system/zaparoo',
        '/userdata/system/zaparoo/zaparoo',
    ]
    return next((item for item in candidates if item and os.access(item, os.X_OK)), None)


def player_started():
    try:
        import socket
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(0.25)
            client.connect(str(session_socket))
            client.sendall(b'{"action":"status"}\n')
            data = b''
            while not data.endswith(b'\n'):
                part = client.recv(4096)
                if not part:
                    break
                data += part
        return bool(json.loads(data.decode()).get('active'))
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def visible_error(reason):
    write_log(f'FAILED: {reason}')
    message = (
        'MOVIE WAS NOT STARTED BY ZAPAROO\n\n'
        f'{reason}\n\n'
        'Open Ports - Movie Player Diagnostics for the next step.'
    )
    if shutil.which('xterm'):
        subprocess.run(['xterm', '-fullscreen', '-e', 'bash', '-c',
                        'printf "%s\n" "$1"; read -r -p "Press Enter to close."', 'bash', message])
    elif shutil.which('dialog'):
        subprocess.run(['dialog', '--title', 'Movie Player', '--msgbox', message, '16', '70'])
    else:
        print(message, file=sys.stderr)


def direct_fallback(reason):
    """Start the same persistent player directly and verify it became active."""
    client = Path('/userdata/system/batocera-movie-player/movie-client.py')
    write_log(f'CORE HANDOFF FALLBACK: {reason}')
    try:
        process = subprocess.Popen(['/usr/bin/python3', str(client), movie],
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.PIPE, text=True)
    except OSError as exc:
        visible_error(f'Direct player could not start: {exc}')
        raise SystemExit(6)
    for _ in range(80):
        if player_started():
            write_log('SUCCESS: Direct fallback activated the persistent player')
            # Keep EmulationStation's launcher lifecycle attached until the
            # movie exits, exactly as movie-client.py does for Core.
            raise SystemExit(process.wait())
        if process.poll() is not None:
            error = (process.stderr.read() if process.stderr else '').strip()
            visible_error(error or 'Direct player exited before MPV became active.')
            raise SystemExit(7)
        time.sleep(0.1)
    process.terminate()
    visible_error('Direct player timed out before MPV became active.')
    raise SystemExit(8)


if not movie or not os.path.isfile(movie):
    visible_error(f'Movie file was not found: {movie}')
    raise SystemExit(2)

core = find_core()
if not core:
    direct_fallback('Zaparoo Core executable was not found')

# Advanced launch arguments follow the path. Quote and escape the path exactly
# as ZapScript requires so spaces, brackets, parentheses and ampersands remain
# part of the filename instead of corrupting Core's launcher selection.
escaped_movie = movie.replace('\\', '\\\\').replace('"', '\\"')
script = f'**launch:"{escaped_movie}"?system=Movie&launcher=BatoceraMoviePlayer'
write_log(f'Starting launch test for: {movie}')
write_log(f'Core executable: {core}')
write_log(f'ZapScript: {script}')
attempts = [('-run', script), ('-launch', script)]
accepted = False
last_error = ''
for flag, value in attempts:
    write_log(f'Trying Core command: {flag}')
    try:
        request = subprocess.Popen([core, flag, value], stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True)
    except OSError as exc:
        last_error = str(exc)
        write_log(f'{flag} could not start: {last_error}')
        continue

    for _ in range(60):
        if player_started():
            write_log(f'SUCCESS: Player started through {flag}')
            raise SystemExit(0)
        result_code = request.poll()
        if result_code is not None:
            break
        time.sleep(0.1)

    result_code = request.poll()
    if result_code is None:
        request.terminate()
        accepted = True
        write_log(f'{flag} is still processing; waiting for player')
        break

    stdout, stderr = request.communicate()
    output = (stdout + stderr).strip()
    if output:
        write_log(f'{flag} response: {output}')
    if result_code == 0:
        accepted = True
        write_log(f'{flag} was accepted by Core')
        break
    last_error = output or f'{flag} returned exit code {result_code}'
    write_log(f'{flag} was rejected: {last_error}')

if not accepted:
    direct_fallback(f'Core rejected the launch request: {last_error}')

for _ in range(60):
    if player_started():
        write_log('SUCCESS: BatoceraMoviePlayer process is active')
        raise SystemExit(0)
    time.sleep(0.1)

direct_fallback('Core accepted the request, but its launcher did not activate the player')
