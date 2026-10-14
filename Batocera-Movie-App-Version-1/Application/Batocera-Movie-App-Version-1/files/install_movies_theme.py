#!/usr/bin/python3
"""Install the exact beta15 Movies override over Batocera's stock Carbon."""
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

APP = Path('/userdata/system/batocera-movie-player')
TARGET = Path('/userdata/roms/movies/theme.xml')
LOG = Path('/userdata/system/logs/movie-player-install.log')
SETTINGS = Path('/userdata/system/configs/emulationstation/es_settings.cfg')
OLD_CLONE = Path('/userdata/themes/movie-player-carbon')
SAVED_THEME = APP / 'ORIGINAL_THEMESET'
SAVED_VIEW = APP / 'ORIGINAL_MOVIES_DEFAULT_VIEW'


def note(message):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open('a', encoding='utf-8') as stream:
        stream.write(message + '\n')


def find_carbon():
    roots = (Path('/usr/share/emulationstation/themes'),
             Path('/etc/emulationstation/themes'), Path('/userdata/themes'))
    names = ('es-theme-carbon', 'carbon', 'Carbon', 'theme-carbon')
    for root in roots:
        for name in names:
            candidate = root / name / 'theme.xml'
            if candidate.is_file() and OLD_CLONE not in candidate.parents:
                return candidate.resolve()
    return None


def restore_pre_clone_settings():
    """Undo beta16+ ThemeSet forcing without changing unrelated settings."""
    if not SETTINGS.is_file():
        return
    tree = ET.parse(SETTINGS)
    root = tree.getroot()
    theme = next((n for n in root.findall('string')
                  if n.get('name') == 'ThemeSet'), None)
    if theme is not None and theme.get('value') == 'movie-player-carbon':
        original = (SAVED_THEME.read_text(encoding='utf-8').strip()
                    if SAVED_THEME.is_file() else 'carbon')
        theme.set('value', original or 'carbon')

    # Isolated library-view choice: Carbon's global grid preference can
    # otherwise override this theme's defaultView and bring thumbnails back.
    # This per-system value does not affect the locked main-menu system view or
    # any other Batocera system.
    view = next((n for n in root.findall('string')
                 if n.get('name') == 'movies.defaultView'), None)
    if view is None:
        view = ET.SubElement(root, 'string', {'name': 'movies.defaultView'})
    view.set('value', 'detailed')
    tree.write(SETTINGS, encoding='utf-8', xml_declaration=True)


def main():
    carbon = find_carbon()
    if not carbon:
        note('THEME FAILED: stock Carbon theme.xml was not found')
        return 1
    try:
        source = (APP / 'movies-theme.xml').read_text(encoding='utf-8')
        if source.count('__CARBON_THEME__') != 1:
            raise RuntimeError('invalid beta15 Movies theme template')
        deployed = source.replace('__CARBON_THEME__', str(carbon))
        TARGET.parent.mkdir(parents=True, exist_ok=True)
        TARGET.write_text(deployed, encoding='utf-8')
        ET.parse(TARGET)
        required = (str(carbon), 'defaultView="detailed"',
                    'movies-theater-background.png', 'movies-logo.png',
                    'name="e_list_panel"', 'name="e_art_panel"',
                    'name="e_poster_frame"', 'name="md_image"',
                    '<customView name="Icons,Tiles,Carousel,Boxes,Content"',
                    '<imagegrid name="gamegrid">',
                    'name="e_movies_selected_poster"')
        installed = TARGET.read_text(encoding='utf-8')
        if '__CARBON_THEME__' in installed or any(x not in installed for x in required):
            raise RuntimeError('installed beta15 Movies override failed verification')
        restore_pre_clone_settings()
        if OLD_CLONE.exists():
            shutil.rmtree(OLD_CLONE)
    except Exception as exc:
        note(f'THEME FAILED: {exc}')
        return 1
    note(f'Exact beta15 Movies override installed at {TARGET}; Carbon={carbon}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
