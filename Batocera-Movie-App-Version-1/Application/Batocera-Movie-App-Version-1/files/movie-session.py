#!/usr/bin/python3
"""Single-owner Batocera movie session.

One process owns MPV, EmulationStation, controller input, media replacement and
recovery. Launch clients may come and go without affecting playback.
"""
import json
import os
import signal
import socket
import socketserver
import subprocess
import threading
import time
import re
import urllib.error
import urllib.request
from pathlib import Path

APP = Path('/userdata/system/batocera-movie-player')
RUNTIME = Path('/tmp/batocera-movie-player')
SESSION_SOCKET = RUNTIME / 'session.sock'
MPV_SOCKET = RUNTIME / 'mpv.sock'
PID_FILE = RUNTIME / 'session.pid'
LOG_PATH = Path('/userdata/system/logs/batocera-movie-player.log')
CORE_LOG = Path('/userdata/system/.local/share/zaparoo/logs/core.log')
ES_API = 'http://localhost:1234'
HANDOFF_MARKER = RUNTIME / 'game-handoff'
MOVIE_SWITCH_MARKER = RUNTIME / 'movie-switch'
MOVIE_ROOT = Path('/userdata/roms/movies')
LIBRARY_EXTENSIONS = {
    '.mkv', '.mp4', '.m4v', '.avi', '.mov', '.mpeg', '.mpg', '.ts', '.m2ts',
    '.webm', '.wmv', '.flv', '.ogv', '.vob', '.3gp',
    '.jpg', '.jpeg', '.png', '.webp', '.bmp',
}


def process_is_running(name, proc_root=Path('/proc')):
    """Match a real executable argv[0], without Linux's 15-char comm limit."""
    try:
        entries = proc_root.iterdir()
    except OSError:
        return False
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            argv0 = (entry / 'cmdline').read_bytes().split(b'\0', 1)[0]
            executable = os.path.basename(os.fsdecode(argv0))
        except (OSError, UnicodeError):
            continue
        if executable == name:
            return True
    return False


class State:
    def __init__(self):
        self.lock = threading.RLock()
        self.changed = threading.Condition(self.lock)
        self.mpv = None
        self.bridge = None
        self.progress = None
        self.token = 0
        self.media = ''
        self.es_owned = False
        self.game_handoff = False
        self.last_movie_end = 0.0
        self.movie_prelaunch = 0
        self.log_stream = None

    def log(self, message):
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open('a', encoding='utf-8') as stream:
            stream.write(f'{time.strftime("%F %T")} SESSION {message}\n')

    @staticmethod
    def setting(name, default):
        config = APP / 'settings.conf'
        try:
            for line in config.read_text(encoding='utf-8').splitlines():
                if line.startswith(name + '='):
                    return line.split('=', 1)[1].strip() or default
        except OSError:
            pass
        return default

    @staticmethod
    def es_running():
        # pgrep's process-name field is limited to 15 characters on Linux;
        # "emulationstation" is 16 and cannot be matched reliably with -x.
        # Inspect argv[0] so the init script is not mistaken for the frontend.
        return process_is_running('emulationstation')

    @staticmethod
    def start_es_async():
        subprocess.Popen(['/etc/init.d/S31emulationstation', 'start'],
                         stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
                         start_new_session=True)

    def stop_es(self):
        if not self.es_running():
            self.es_owned = True
            return
        self.log('Stopping EmulationStation once for movie session')
        try:
            subprocess.run(['/etc/init.d/S31emulationstation', 'stop'], timeout=8,
                           stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        except subprocess.TimeoutExpired:
            self.log('EmulationStation stop timed out; continuing with movie display guard')
        for _ in range(50):
            if not self.es_running():
                break
            time.sleep(0.05)
        self.es_owned = True

    def prehide_for_movie_scan(self, media):
        """Hide ES at Core announcement time, before the scanned input can draw a menu."""
        with self.lock:
            if ((self.mpv and self.mpv.poll() is None) or self.game_handoff):
                return
            self.movie_prelaunch += 1
            prelaunch = self.movie_prelaunch
            token = self.token
            self.log(f'Pre-hiding EmulationStation for scanned movie: {media}')
            self.stop_es()
        threading.Thread(target=self.restore_failed_movie_prelaunch,
                         args=(prelaunch, token), daemon=True).start()

    def restore_failed_movie_prelaunch(self, prelaunch, token):
        """Return the frontend if Core announced a movie that never reached MPV."""
        time.sleep(10.0)
        with self.lock:
            should_restore = (
                self.movie_prelaunch == prelaunch and
                self.token == token and
                not (self.mpv and self.mpv.poll() is None) and
                not self.game_handoff and self.es_owned
            )
        if should_restore:
            self.log('Scanned movie did not start within 10 seconds; restoring EmulationStation')
            self.restore_es()

    def start_es_and_wait(self):
        """Start EmulationStation and leave enough time for its launch API."""
        # Starting ES can wait for the display currently owned by MPV. Keep
        # that init action asynchronous so loading never freezes at stage one.
        self.start_es_async()
        for _ in range(50):
            if self.es_running():
                # A visible process appears before EmulationStation's HTTP
                # launch endpoint is ready.  Zaparoo must not release its
                # pending game until this settling period has elapsed.
                time.sleep(1.5)
                return True
            time.sleep(0.1)
        swissknife = '/usr/bin/batocera-es-swissknife'
        if os.path.exists(swissknife):
            subprocess.Popen([swissknife, '--restart'], stdout=subprocess.DEVNULL,
                             stderr=subprocess.STDOUT, start_new_session=True)
        time.sleep(1.5)
        return self.es_running()

    def restore_es(self):
        if not self.es_owned:
            return
        self.es_owned = False
        self.log('Restoring EmulationStation directly to Movies after final exit')
        # Temporarily ask ES to start on Movies, then restore the user's original
        # startup preference after ES has read the file.
        settings_path = Path('/userdata/system/configs/emulationstation/es_settings.cfg')
        original_startup = None
        startup_existed = False
        if settings_path.exists():
            try:
                text = settings_path.read_text(encoding='utf-8')
                pattern = r'<string\s+name="StartupSystem"\s+value="([^"]*)"\s*/>'
                match = re.search(pattern, text)
                if match:
                    startup_existed = True
                    original_startup = match.group(1)
                replacement = '<string name="StartupSystem" value="movies" />'
                if match:
                    text = re.sub(pattern, replacement, text, count=1)
                elif '</config>' in text:
                    text = text.replace('</config>', f'  {replacement}\n</config>', 1)
                settings_path.write_text(text, encoding='utf-8')
            except (OSError, UnicodeError):
                original_startup = None
                startup_existed = False

        def restore_startup_only():
            # Read the live file after ES starts. A stale whole-file restore
            # previously rolled ThemeSet back after every movie exit.
            try:
                current = settings_path.read_text(encoding='utf-8')
                pattern = r'<string\s+name="StartupSystem"\s+value="[^"]*"\s*/>'
                if startup_existed:
                    replacement = f'<string name="StartupSystem" value="{original_startup}" />'
                    current = re.sub(pattern, replacement, current, count=1)
                else:
                    current = re.sub(r'\s*<string\s+name="StartupSystem"\s+value="movies"\s*/>', '', current, count=1)
                settings_path.write_text(current, encoding='utf-8')
            except (OSError, UnicodeError):
                pass
        self.start_es_and_wait()
        restore_startup_only()

    def prepare_game_handoff(self):
        """Bring ES up before releasing a movie that Zaparoo is preempting."""
        with self.lock:
            if not self.mpv or self.mpv.poll() is not None:
                return
            self.game_handoff = True
            HANDOFF_MARKER.touch()
            self.mpv_command(['set', 'pause', 'yes'])
            self.show_game_stage(1, 'STARTING BATOCERA')
            if self.es_owned:
                self.log('Zaparoo game handoff: starting EmulationStation before movie exit')
                self.es_owned = False
                self.start_es_async()
            self.log('Zaparoo game handoff: frontend start requested asynchronously')

    def show_game_stage(self, stage, label, minimum=0.65):
        """Advance the real progress artwork and keep it readable."""
        if self.mpv and self.mpv.poll() is None:
            self.mpv_command(['loadfile', str(APP / f'game-loading-{stage}.png'), 'replace'])
            self.mpv_command(['show-text', f'STEP {stage} OF 3  •  {label}', 30000])
            time.sleep(minimum)

    def release_game_handoff(self):
        """Close the loading movie only when the replacement can be launched."""
        with self.lock:
            if self.mpv and self.mpv.poll() is None:
                self.mpv_command(['show-text', 'GAME READY\nLAUNCHING NOW', 2000])
                time.sleep(0.25)
                self.mpv_command(['quit'])
                for _ in range(60):
                    if self.mpv.poll() is not None:
                        break
                    time.sleep(0.05)
            try: HANDOFF_MARKER.unlink()
            except FileNotFoundError: pass

    @staticmethod
    def mpv_command(command, attempts=20):
        payload = (json.dumps({'command': command}) + '\n').encode()
        for _ in range(attempts):
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                    client.settimeout(0.3)
                    client.connect(str(MPV_SOCKET))
                    client.sendall(payload)
                    return True
            except OSError:
                time.sleep(0.05)
        return False

    def stop_helper(self, name):
        proc = getattr(self, name)
        if proc and proc.poll() is None:
            proc.terminate()
            try: proc.wait(timeout=1)
            except subprocess.TimeoutExpired: proc.kill()
        setattr(self, name, None)

    def start_progress(self, media):
        self.stop_helper('progress')
        self.progress = subprocess.Popen(
            ['/usr/bin/python3', str(APP/'progress_tracker.py'), str(MPV_SOCKET), media],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def start_bridge(self):
        """Give the active movie one fresh controller/keyboard state machine."""
        self.stop_helper('bridge')
        self.bridge = subprocess.Popen(
            ['/usr/bin/python3', str(APP/'controller_bridge.py'), str(MPV_SOCKET)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def reset_replacement_controls(self):
        """Make a replaced movie behave like a clean first launch.

        MPV intentionally stays alive for fast movie-to-movie scans.  Without
        this reset it also keeps pause, mute, volume and picture-filter state
        from the previous title, while the controller bridge keeps its local
        fit/zoom/prompt state.  Reset both halves without disturbing the proven
        persistent-player or Zaparoo lifecycle.
        """
        volume = self.setting('default_volume', '80')
        aspect_mode = self.setting('aspect_mode', 'fit').lower()
        panscan = '1.0' if aspect_mode == 'fill' else '0.0'
        commands = [
            ['set', 'pause', 'no'],
            ['set', 'mute', 'no'],
            ['set', 'volume', volume],
            ['vf', 'remove', '@movie-picture'],
            ['set', 'panscan', panscan],
            ['set', 'video-scale-x', '1.0'],
            ['set', 'video-scale-y', '1.0'],
            ['set', 'video-pan-x', '0.0'],
            ['set', 'video-pan-y', '0.0'],
            ['set', 'video-zoom', '0.0'],
        ]
        for command in commands:
            self.mpv_command(command)
        self.start_bridge()
        self.log(f'Reset replacement controls: pause=no mute=no volume={volume} aspect={aspect_mode}')

    def play(self, media):
        media = os.path.realpath(media)
        if not os.path.isfile(media):
            raise FileNotFoundError(media)
        with self.lock:
            self.token += 1
            token = self.token
            self.media = media
            if self.mpv and self.mpv.poll() is None:
                # A movie-to-movie scan must retain exclusive ownership of the
                # display. Core may briefly bring ES back while replacing its
                # launcher record, so close it again before changing media.
                if self.es_running() and not self.game_handoff:
                    self.log('Movie replacement found EmulationStation active; hiding frontend again')
                    self.stop_es()
                self.log(f'Replacing active media in same MPV process: {media}')
                if not self.mpv_command(['loadfile', media, 'replace']):
                    raise RuntimeError('active MPV socket did not accept replacement')
                # Allow MPV to apply the queued load before resetting properties
                # that otherwise survive across loadfile/replace.
                time.sleep(0.08)
                self.reset_replacement_controls()
                self.start_progress(media)
                threading.Thread(target=self.clear_movie_switch_after,
                                 daemon=True).start()
                self.changed.notify_all()
                return token

            self.game_handoff = False
            try: HANDOFF_MARKER.unlink()
            except FileNotFoundError: pass
            # Preserve beta15's proven display order: EmulationStation must
            # release the display before MPV is created.
            self.stop_es()
            try: MPV_SOCKET.unlink()
            except FileNotFoundError: pass
            self.log_stream = LOG_PATH.open('a', encoding='utf-8')
            volume = self.setting('default_volume', '80')
            end_behavior = self.setting('end_behavior', 'waiting')
            aspect_mode = self.setting('aspect_mode', 'fit').lower()
            panscan = '1.0' if aspect_mode == 'fill' else '0.0'
            args = [
                'mpv', '--fullscreen', '--ontop', '--no-border', '--force-window=yes',
                '--no-input-default-bindings', f'--input-ipc-server={MPV_SOCKET}',
                '--image-display-duration=inf',
                f'--input-conf={APP / "mpv-input.conf"}', '--osd-level=1',
                f'--volume={volume}',
                '--keepaspect=yes', '--video-unscaled=no', '--video-zoom=0',
                f'--panscan={panscan}',
                '--save-position-on-quit',
                f'--watch-later-directory={APP / "watch_later"}',
                '--sub-auto=fuzzy', '--audio-file-auto=fuzzy', '--', media,
            ]
            if end_behavior == 'replay': args.insert(-2, '--loop-file=inf')
            if end_behavior == 'hold': args.insert(-2, '--keep-open=yes')
            self.mpv = subprocess.Popen(args, stdout=self.log_stream,
                                        stderr=subprocess.STDOUT, start_new_session=True)
            for _ in range(20):
                if MPV_SOCKET.exists():
                    break
                time.sleep(0.05)
            self.start_bridge()
            self.start_progress(media)
            threading.Thread(target=self.clear_movie_switch_after,
                             daemon=True).start()
            threading.Thread(target=self.monitor, args=(self.mpv,), daemon=True).start()
            threading.Thread(target=self.keep_es_hidden, args=(self.mpv,), daemon=True).start()
            self.changed.notify_all()
            return token

    def keep_es_hidden(self, watched):
        """Prevent Core lifecycle events from reopening ES over a movie."""
        while watched.poll() is None:
            time.sleep(0.2)
            with self.lock:
                should_hide = (self.mpv is watched and not self.game_handoff)
            if should_hide and self.es_running():
                # Recheck after a short debounce so a legitimate game handoff
                # always wins ownership before we stop the frontend.
                time.sleep(0.1)
                with self.lock:
                    should_hide = (self.mpv is watched and not self.game_handoff)
                if should_hide and self.es_running():
                    self.log('Frontend guard stopped EmulationStation reopened during movie playback')
                    self.stop_es()

    @staticmethod
    def clear_movie_switch_after():
        # Keep the protection through Core's delayed old-launcher exit event.
        try: marker_time = MOVIE_SWITCH_MARKER.stat().st_mtime_ns
        except FileNotFoundError: return
        time.sleep(3.0)
        try:
            if MOVIE_SWITCH_MARKER.stat().st_mtime_ns == marker_time:
                MOVIE_SWITCH_MARKER.unlink()
        except FileNotFoundError: pass

    def monitor(self, watched):
        result = watched.wait()
        restore_needed = False
        ended_token = 0
        with self.lock:
            if self.mpv is not watched:
                return
            self.log(f'MPV ended with code {result}')
            self.last_movie_end = time.monotonic()
            ended_token = self.token
            self.stop_helper('bridge')
            self.stop_helper('progress')
            self.mpv = None
            self.media = ''
            try: MPV_SOCKET.unlink()
            except FileNotFoundError: pass
            if self.log_stream:
                self.log_stream.close(); self.log_stream = None
            self.changed.notify_all()
            if self.game_handoff:
                self.log('Movie released to pending Zaparoo game launch')
                self.game_handoff = False
            else:
                # Do not hold the session lock while restoring the frontend.
                # A replacement scan closes Core's old launcher first; the new
                # movie must get a chance to claim the session before ES returns.
                restore_needed = True
        if restore_needed:
            threading.Thread(target=self.restore_after_quiet,
                             args=(ended_token,), daemon=True).start()

    def restore_after_quiet(self, ended_token):
        """Restore ES only after proving this was a genuine final exit."""
        time.sleep(1.5)
        with self.lock:
            if (self.token != ended_token or
                    (self.mpv and self.mpv.poll() is None) or
                    self.game_handoff or MOVIE_SWITCH_MARKER.exists()):
                self.log('Skipped frontend restore because another media launch is pending')
                return
        self.restore_es()

    def wait_token(self, token):
        with self.changed:
            while self.token == token and self.mpv and self.mpv.poll() is None:
                self.changed.wait(timeout=2)
            return {'active': bool(self.mpv and self.mpv.poll() is None),
                    'token': self.token, 'media': self.media}

    def shutdown(self):
        with self.lock:
            if self.mpv and self.mpv.poll() is None:
                self.mpv_command(['quit'])


STATE = State()


def watch_zaparoo_launches():
    """Prepare ES as soon as Core announces a non-movie replacement launch."""
    stream = None
    inode = None
    while True:
        try:
            stat = CORE_LOG.stat()
            if stream is None or inode != stat.st_ino:
                if stream:
                    stream.close()
                stream = CORE_LOG.open('r', encoding='utf-8', errors='replace')
                stream.seek(0, os.SEEK_END)
                inode = stat.st_ino
            line = stream.readline()
            if not line:
                time.sleep(0.05)
                continue
            game_path = extract_launch_path(line)
            if not game_path:
                continue
            lower_path = game_path.lower()
            if lower_path.startswith('/userdata/roms/movies/'):
                MOVIE_SWITCH_MARKER.touch()
                STATE.log(f'Zaparoo movie replacement announced: {game_path}')
                STATE.prehide_for_movie_scan(game_path)
                continue
            movie_active = bool(STATE.mpv and STATE.mpv.poll() is None)
            recent_movie_exit = time.monotonic() - STATE.last_movie_end < 30.0
            if movie_active or recent_movie_exit or STATE.es_owned:
                STATE.log(f'Zaparoo non-movie launch detected during movie handoff: {line.strip()[-300:]}')
                if movie_active:
                    STATE.prepare_game_handoff()
                else:
                    # The synthetic movie-exit event can arrive just before
                    # Core writes the new game path. Preserve and replay that
                    # pending launch even though MPV has already disappeared.
                    HANDOFF_MARKER.touch()
                verify_or_replay_game(game_path)
        except (OSError, ValueError):
            if stream:
                stream.close(); stream = None
            time.sleep(0.25)


def extract_launch_path(line):
    """Extract Core's exact ROM path from either JSON or plain-text logging."""
    message = line
    try:
        record = json.loads(line)
        if isinstance(record, dict):
            message = next((value for value in record.values()
                            if isinstance(value, str) and 'launch media:' in value.lower()), '')
    except (ValueError, TypeError):
        pass
    match = re.search(r'launch media:\s*(/userdata/roms/.+)$', message, re.IGNORECASE)
    return match.group(1).strip() if match else ''


def es_api(path, body=None, timeout=1.0):
    data = body.encode('utf-8') if body is not None else None
    request = urllib.request.Request(ES_API + path, data=data)
    if data is not None:
        request.add_header('Content-Type', 'text/plain')
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode('utf-8', errors='replace')


def verify_or_replay_game(game_path):
    """Hand the display to ES, then replay Core's game request exactly once."""
    STATE.show_game_stage(2, 'STARTING GAME SYSTEM')

    # First allow ES to expose its real HTTP API behind the still-visible
    # loading window. Never infer readiness from a similarly named shell script.
    ready = False
    for _ in range(50):
        try:
            es_api('/runningGame', timeout=0.35)
            ready = True
            break
        except (OSError, urllib.error.URLError):
            time.sleep(0.1)

    if ready:
        # Core may already have completed the launch during startup.
        try:
            payload = es_api('/runningGame', timeout=0.5)
            if 'NO GAME RUNNING' not in payload.upper():
                STATE.log(f'Game handoff already completed by Core: {game_path}')
                STATE.show_game_stage(3, 'GAME ACCEPTED')
                STATE.release_game_handoff()
                return
        except (OSError, urllib.error.URLError):
            pass

    # Stage three is always shown before MPV releases the display. If ES could
    # not expose its API while MPV was fullscreen, release first and wait again;
    # this explicitly breaks the display/API circular dependency.
    STATE.show_game_stage(3, 'HANDING OFF DISPLAY')
    if not ready:
        STATE.release_game_handoff()
        for _ in range(150):
            try:
                es_api('/runningGame', timeout=0.35)
                ready = True
                break
            except (OSError, urllib.error.URLError):
                time.sleep(0.1)
        if not ready:
            STATE.log(f'Initial EmulationStation start never exposed its API for {game_path}')
            STATE.log('Restarting the frontend while preserving the pending game path')
            ready = restart_es_until_api()
            if not ready:
                STATE.log(f'GAME HANDOFF FAILED: API unavailable after clean restart for {game_path}')
                clear_failed_game_handoff()
                return
            STATE.log(f'Frontend API recovered; continuing pending game launch: {game_path}')

    # Submit and then verify the state change. An HTTP response only proves the
    # menu accepted the request; it does not prove the emulator actually began.
    # If ES remains alive and says NO GAME RUNNING, retry the exact path once.
    for attempt in (1, 2):
        result = {'error': None}
        finished = threading.Event()

        def request_launch():
            try:
                es_api('/launch', body=game_path, timeout=35.0)
            except (OSError, urllib.error.URLError) as exc:
                result['error'] = exc
            finally:
                finished.set()

        threading.Thread(target=request_launch, daemon=True).start()
        if attempt == 1 and STATE.mpv and STATE.mpv.poll() is None:
            time.sleep(0.65)
            STATE.release_game_handoff()
        finished.wait(36.0)

        no_game_replies = 0
        api_missing = 0
        for _ in range(50):
            try:
                payload = es_api('/runningGame', timeout=0.35)
                if 'NO GAME RUNNING' not in payload.upper():
                    STATE.log(f'GAME HANDOFF VERIFIED on attempt {attempt}: {payload.strip()}')
                    return
                no_game_replies += 1
            except (OSError, urllib.error.URLError):
                # Batocera normally suspends ES once an emulator owns the
                # display. Repeated API disappearance after /launch is success,
                # not a reason to restart ES and kill the newly started game.
                api_missing += 1
                if api_missing >= 5 and no_game_replies == 0:
                    STATE.log(f'GAME HANDOFF VERIFIED by frontend suspension on attempt {attempt}')
                    return
            time.sleep(0.1)

        detail = result['error'] if result['error'] is not None else 'menu still reports NO GAME RUNNING'
        STATE.log(f'Game launch attempt {attempt} did not start emulator: {detail}')
        if attempt == 1:
            time.sleep(1.0)

    STATE.log(f'GAME HANDOFF FAILED AFTER VERIFIED RETRY: {game_path}')
    # Leave the now-functional Batocera menu visible. Do not restart it and do
    # not turn a recoverable launch failure into a black-screen loop.
    clear_failed_game_handoff()


def clear_failed_game_handoff():
    """Release every movie-owned state so a later game scan remains usable."""
    with STATE.lock:
        STATE.game_handoff = False
        STATE.es_owned = False
        STATE.last_movie_end = 0.0
    for marker in (HANDOFF_MARKER, MOVIE_SWITCH_MARKER):
        try:
            marker.unlink()
        except FileNotFoundError:
            pass
    STATE.log('Failed game handoff state cleared; future game scans unlocked')


def recover_frontend():
    """Never leave a failed handoff trapped on a black display."""
    STATE.log('Recovering EmulationStation after failed game handoff')
    if restart_es_until_api():
        return
    swissknife = '/usr/bin/batocera-es-swissknife'
    if os.path.exists(swissknife):
        subprocess.run([swissknife, '--restart'], stdout=subprocess.DEVNULL,
                       stderr=subprocess.STDOUT)


def restart_es_until_api():
    """Cleanly restart ES and verify its HTTP API, not merely its process."""
    try:
        subprocess.run(['/etc/init.d/S31emulationstation', 'stop'], timeout=8,
                       stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    except subprocess.TimeoutExpired:
        STATE.log('EmulationStation stop timed out during API recovery')
    for _ in range(50):
        if not STATE.es_running():
            break
        time.sleep(0.1)
    subprocess.Popen(['/etc/init.d/S31emulationstation', 'start'],
                     stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
                     start_new_session=True)
    for _ in range(150):
        try:
            es_api('/runningGame', timeout=0.35)
            STATE.log('EmulationStation API verified after clean restart')
            return True
        except (OSError, urllib.error.URLError):
            time.sleep(0.1)
    return False


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            request = json.loads(self.rfile.readline().decode())
            action = request.get('action')
            if action == 'play':
                token = STATE.play(request.get('media', ''))
                response = {'ok': True, 'token': token}
            elif action == 'wait':
                response = {'ok': True, **STATE.wait_token(int(request.get('token', 0)))}
            elif action == 'status':
                response = {'ok': True, 'token': STATE.token, 'media': STATE.media,
                            'active': bool(STATE.mpv and STATE.mpv.poll() is None)}
            elif action == 'game_handoff':
                STATE.prepare_game_handoff(); response = {'ok': True}
            elif action == 'shutdown':
                STATE.shutdown(); response = {'ok': True}
            else:
                response = {'ok': False, 'error': 'unknown action'}
        except Exception as exc:
            STATE.log(f'ERROR {type(exc).__name__}: {exc}')
            response = {'ok': False, 'error': str(exc)}
        self.wfile.write((json.dumps(response) + '\n').encode())


class Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True


def movie_library_signature():
    """Cheap change fingerprint for movies and user-supplied artwork."""
    signature = []
    if not MOVIE_ROOT.exists():
        return signature
    for path in MOVIE_ROOT.rglob('*'):
        if not path.is_file() or path.suffix.lower() not in LIBRARY_EXTENSIONS:
            continue
        try:
            stat = path.stat()
            signature.append((str(path.relative_to(MOVIE_ROOT)), stat.st_size,
                              stat.st_mtime_ns))
        except OSError:
            continue
    return sorted(signature)


def watch_movie_library():
    """Keep gamelist.xml ready for Batocera's standard Update Game Lists action."""
    previous = movie_library_signature()
    while True:
        time.sleep(1)
        current = movie_library_signature()
        if current == previous:
            continue
        # One short debounce pass avoids rebuilding halfway through a network copy.
        time.sleep(1)
        current = movie_library_signature()
        STATE.log('Movie or poster change detected; refreshing movie library')
        result = subprocess.run(
            ['/usr/bin/python3', str(APP / 'build_movie_gamelist.py'), str(MOVIE_ROOT)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        summary = (result.stdout or '').strip().replace('\n', ' | ')
        STATE.log(f'Automatic movie refresh exit={result.returncode}: {summary}')
        previous = movie_library_signature()


def main():
    RUNTIME.mkdir(parents=True, exist_ok=True)
    try: SESSION_SOCKET.unlink()
    except FileNotFoundError: pass
    PID_FILE.write_text(str(os.getpid()), encoding='utf-8')
    def terminate(*_):
        STATE.shutdown()
        if STATE.mpv:
            try: STATE.mpv.wait(timeout=5)
            except subprocess.TimeoutExpired: STATE.mpv.kill()
        STATE.restore_es()
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, terminate)
    threading.Thread(target=watch_zaparoo_launches, daemon=True).start()
    threading.Thread(target=watch_movie_library, daemon=True).start()
    try:
        with Server(str(SESSION_SOCKET), Handler) as server:
            os.chmod(SESSION_SOCKET, 0o666)
            STATE.log('Session manager ready')
            server.serve_forever(poll_interval=0.2)
    finally:
        try: SESSION_SOCKET.unlink()
        except FileNotFoundError: pass
        try: PID_FILE.unlink()
        except FileNotFoundError: pass


if __name__ == '__main__':
    main()
