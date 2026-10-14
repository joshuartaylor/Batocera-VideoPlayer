#!/usr/bin/python3
"""Thin Zaparoo/EmulationStation client for the persistent movie session."""
import fcntl, json, os, shlex, socket, subprocess, sys, time
from pathlib import Path

APP = Path('/userdata/system/batocera-movie-player')
SOCKET = Path('/tmp/batocera-movie-player/session.sock')
RAW_MEDIA = sys.argv[1] if len(sys.argv) > 1 else ''
# Older/custom EmulationStation substitutions can leave shell escapes as
# literal backslashes inside an already quoted argument. Decode only when the
# original value is not a real file, preserving legitimate backslashes.
if RAW_MEDIA and not os.path.isfile(RAW_MEDIA) and '\\' in RAW_MEDIA:
    try:
        decoded = shlex.split(RAW_MEDIA)
        if len(decoded) == 1:
            RAW_MEDIA = decoded[0]
    except ValueError:
        pass
MEDIA = os.path.realpath(RAW_MEDIA) if RAW_MEDIA else ''


def request(payload):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(None)
        client.connect(str(SOCKET))
        client.sendall((json.dumps(payload) + '\n').encode())
        data = b''
        while not data.endswith(b'\n'):
            part = client.recv(4096)
            if not part: break
            data += part
    return json.loads(data.decode())


def ensure_manager():
    Path('/tmp/batocera-movie-player').mkdir(parents=True, exist_ok=True)
    with open('/tmp/batocera-movie-player/manager-start.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            if request({'action': 'status'}).get('ok'): return
        except (OSError, ValueError): pass
        subprocess.Popen(['/usr/bin/python3', str(APP/'movie-session.py')],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        for _ in range(60):
            try:
                if request({'action': 'status'}).get('ok'): return
            except (OSError, ValueError): time.sleep(0.05)
    raise SystemExit('Movie session manager did not start')


if not MEDIA or not os.path.isfile(MEDIA):
    raise SystemExit(f'Movie not found: {MEDIA}')
ensure_manager()
reply = request({'action': 'play', 'media': MEDIA})
if not reply.get('ok'):
    raise SystemExit(reply.get('error', 'Movie did not start'))
# The launcher is deliberately backgrounded. The session manager owns the one
# persistent MPV process; this short client only submits a replacement request.
# Letting Core track this client as a blocking player creates a delayed
# media-stopped event that can erase the next movie's ActiveMedia record.
