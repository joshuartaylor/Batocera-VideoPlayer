#!/usr/bin/python3
"""Record MPV resume progress for Continue Watching and watched markers."""
import hashlib, json, os, socket, sys, time
from pathlib import Path

socket_path = sys.argv[1]
media_path = os.path.realpath(sys.argv[2])
state_dir = Path('/userdata/system/batocera-movie-player/progress')
state_dir.mkdir(parents=True, exist_ok=True)
state_file = state_dir / (hashlib.sha256(media_path.encode()).hexdigest() + '.json')

def prop(name):
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(1)
            client.connect(socket_path)
            client.sendall((json.dumps({'command': ['get_property', name], 'request_id': 1}) + '\n').encode())
            data = b''
            while b'\n' not in data:
                data += client.recv(4096)
            return json.loads(data.split(b'\n', 1)[0]).get('data')
    except (OSError, ValueError, json.JSONDecodeError):
        return None

def save():
    position, duration = prop('time-pos'), prop('duration')
    if not isinstance(position, (int, float)) or not isinstance(duration, (int, float)) or duration <= 0:
        return
    percent = max(0.0, min(1.0, position / duration))
    data = {'path': media_path, 'position': round(position, 1), 'duration': round(duration, 1),
            'percent': round(percent, 4), 'watched': percent >= 0.90, 'updated': int(time.time())}
    temporary = state_file.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, indent=2), encoding='utf-8')
    temporary.replace(state_file)

while not os.path.exists(socket_path):
    time.sleep(0.1)
while True:
    save()
    time.sleep(5)
