#!/usr/bin/python3
"""Activate the frozen Movies theme once per installed version.

Batocera runs custom.sh after EmulationStation has already loaded its settings.
Writing ThemeSet at that point cannot change the live interface and ES may later
write its old choice back. Perform one controlled frontend restart on the first
boot after an update, while no movie is playing, then leave it untouched.
"""
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

APP = Path('/userdata/system/batocera-movie-player')
MARKER = APP / 'THEME_ACTIVATED_VERSION'
LOG = Path('/userdata/system/logs/movie-player-install.log')
MOVIES_THEME = Path('/userdata/roms/movies/theme.xml')


def note(message):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open('a', encoding='utf-8') as stream:
        stream.write(f'{time.strftime("%F %T")} THEME ACTIVATE {message}\n')


def theme_is_already_live():
    """Return true when ES necessarily loaded the installed theme this boot."""
    try:
        installed = MOVIES_THEME.read_text(encoding='utf-8')
        return ('<customView name="Icons,Tiles,Carousel,Boxes,Content"' in installed and
                '<imagegrid name="gamegrid">' in installed and
                'name="e_list_panel"' in installed and
                'name="e_poster_frame"' in installed)
    except (OSError, ET.ParseError, UnicodeError):
        return False


def main():
    version = (APP / 'VERSION').read_text(encoding='utf-8').strip()
    if MARKER.is_file() and MARKER.read_text(encoding='utf-8').strip() == version:
        return 0

    # Normal fast path: install.sh wrote the settings before this reboot, so ES
    # has already loaded the correct theme. Do not copy Carbon or restart ES.
    if theme_is_already_live():
        MARKER.write_text(version + '\n', encoding='utf-8')
        note(f'fast activation confirmed for {version}; frontend restart skipped')
        return 0

    note(f'first boot activation beginning for {version}')
    try:
        subprocess.run(['/etc/init.d/S31emulationstation', 'stop'], timeout=12,
                       stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    except (OSError, subprocess.TimeoutExpired) as exc:
        note(f'frontend stop warning: {exc}')

    result = subprocess.run(['/usr/bin/python3', str(APP / 'install_movies_theme.py')],
                            stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    if result.returncode != 0:
        note('theme installer failed; starting frontend without activation marker')

    subprocess.Popen(['/etc/init.d/S31emulationstation', 'start'],
                     stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
                     start_new_session=True)
    for _ in range(150):
        running = subprocess.run(['pgrep', '-f', '^/usr/bin/emulationstation([[:space:]]|$)'],
                                 stdout=subprocess.DEVNULL).returncode == 0
        if running:
            break
        time.sleep(0.1)

    if result.returncode == 0:
        MARKER.write_text(version + '\n', encoding='utf-8')
        note(f'approved Movies theme activated for {version}')
        return 0
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
