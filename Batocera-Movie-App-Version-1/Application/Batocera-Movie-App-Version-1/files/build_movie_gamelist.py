#!/usr/bin/python3
"""Build a poster-friendly Batocera gamelist for the visible Movies system."""
import html, json, os, re, shutil, subprocess, sys, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else '/userdata/roms/movies')
root.mkdir(parents=True, exist_ok=True)
images = root / 'images'; images.mkdir(exist_ok=True)
generated_images = images / '.generated'; generated_images.mkdir(exist_ok=True)
settings = Path('/userdata/system/batocera-movie-player/settings.conf')
cache_file = root / '.tmdb-cache.json'
extensions = {'.mkv','.mp4','.m4v','.avi','.mov','.mpeg','.mpg','.ts','.m2ts','.webm','.wmv','.flv','.ogv','.vob','.3gp'}
movies = sorted((p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in extensions), key=lambda p: str(p).lower())
progress_dir = Path('/userdata/system/batocera-movie-player/progress')
progress_by_path = {}
if progress_dir.exists():
    for record in progress_dir.glob('*.json'):
        try:
            state = json.loads(record.read_text(encoding='utf-8'))
            progress_by_path[os.path.realpath(state['path'])] = state
        except (OSError, KeyError, ValueError, json.JSONDecodeError):
            pass

# Preserve Batocera-owned user choices and history across poster refreshes.
preserved_by_path = {}
gamelist_path = root / 'gamelist.xml'
if gamelist_path.exists():
    try:
        old_root = ET.parse(gamelist_path).getroot()
        for old_game in old_root.findall('game'):
            old_path = old_game.findtext('path', '')
            if not old_path:
                continue
            resolved = Path(old_path)
            if not resolved.is_absolute():
                resolved = root / old_path.removeprefix('./')
            preserved_by_path[os.path.realpath(resolved)] = {
                tag: old_game.findtext(tag)
                for tag in ('name', 'favorite', 'playcount', 'lastplayed', 'gametime',
                            'kidgame', 'hidden', 'adult', 'lang', 'region')
                if old_game.findtext(tag) is not None
            }
    except (OSError, ET.ParseError):
        pass

def setting(key):
    if settings.exists():
        for line in settings.read_text(encoding='utf-8', errors='ignore').splitlines():
            if line.startswith(key + '='): return line.split('=', 1)[1].strip()
    return ''

tmdb_key = setting('tmdb_api_key')
free_poster_lookup = setting('free_poster_lookup').lower() not in ('0', 'false', 'no', 'off')
try: cache = json.loads(cache_file.read_text(encoding='utf-8')) if cache_file.exists() else {}
except Exception: cache = {}

def identity(path):
    raw = re.sub(r'[._]+', ' ', path.stem)
    match = re.search(r'(?<!\d)((?:19|20)\d{2})(?!\d)', raw)
    year = match.group(1) if match else ''
    title = re.sub(r'\b(?:19|20)\d{2}\b.*$', '', raw).strip(' -_()[]')
    title = re.sub(r'\b(?:1080p|720p|2160p|bluray|brrip|webrip|web-dl|dvdrip|x26[45]|hevc)\b.*$', '', title, flags=re.I)
    return re.sub(r'\s+', ' ', title).strip() or path.stem, year

def unmarked_title(value):
    """Remove only Movie Player's generated watch-progress prefix."""
    return re.sub(r'^(?:✓\s+|▶\s+\d+%\s+)', '', value or '').strip()

def tmdb_json(endpoint, params):
    query, headers = dict(params), {'User-Agent': 'Batocera-Movie-Player/0.21'}
    if tmdb_key.startswith('eyJ'): headers['Authorization'] = 'Bearer ' + tmdb_key
    else: query['api_key'] = tmdb_key
    url = 'https://api.themoviedb.org/3/' + endpoint + '?' + urllib.parse.urlencode(query)
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=12) as response:
        return json.load(response)

def metadata(title, year):
    if not tmdb_key: return {}
    key = title.lower() + '|' + year
    if key in cache: return cache[key]
    try:
        params = {'query': title, 'include_adult': 'false'}
        if year: params['year'] = year
        results = tmdb_json('search/movie', params).get('results', [])
        result = results[0] if results else {}
        data = {'poster_path': result.get('poster_path') or '', 'overview': result.get('overview') or '',
                'release_date': result.get('release_date') or '', 'rating': result.get('vote_average') or 0}
        cache[key] = data
        return data
    except Exception as exc:
        print(f'Poster lookup skipped for {title}: {exc}')
        return {}

def download(url, target):
    try:
        request = urllib.request.Request(url, headers={'User-Agent': 'Batocera-Movie-Player/0.21'})
        with urllib.request.urlopen(request, timeout=15) as response, target.open('wb') as output: shutil.copyfileobj(response, output)
        return target.exists() and target.stat().st_size > 0
    except Exception:
        target.unlink(missing_ok=True); return False

def apple_catalog_poster(title, year, target):
    """Fetch a best-effort, no-account poster from Apple's public movie API."""
    if not free_poster_lookup or not shutil.which('ffmpeg'):
        return False
    cache_key = 'apple-movie|' + title.lower() + '|' + year
    cached = cache.get(cache_key)
    if cached is False:
        return False
    try:
        source = cached if isinstance(cached, str) else ''
        if not source:
            params = urllib.parse.urlencode({
                'term': title, 'country': 'US', 'media': 'movie',
                'entity': 'movie', 'limit': '15',
            })
            request = urllib.request.Request(
                'https://itunes.apple.com/search?' + params,
                headers={'User-Agent': 'Batocera-Movie-Player/2.2 (JRT3D.com)'})
            with urllib.request.urlopen(request, timeout=12) as response:
                results = json.load(response).get('results', [])
            normalize = lambda value: re.sub(r'[^a-z0-9]+', ' ', value.lower()).strip()
            exact = [item for item in results
                     if normalize(item.get('trackName', '')) == normalize(title)
                     and item.get('artworkUrl100')]
            if exact:
                def year_distance(item):
                    released = (item.get('releaseDate') or '')[:4]
                    if not year or not released.isdigit():
                        return 0
                    return abs(int(released) - int(year))
                best = min(exact, key=year_distance)
                source = best.get('artworkUrl100', '').replace('http://', 'https://', 1)
                # Apple artwork URLs encode their output dimensions in the path.
                # Ask for poster proportions; fall back to the original URL below.
                source = re.sub(r'\d+x\d+(?=bb\.)', '1000x1500', source)
            cache[cache_key] = source or False
        if not source:
            return False
        temporary = target.with_suffix('.apple-image')
        if not download(source, temporary):
            # Some catalog entries do not accept a larger artwork request.
            smaller = re.sub(r'1000x1500(?=bb\.)', '100x100', source)
            if smaller == source or not download(smaller, temporary):
                return False
        result = subprocess.run(
            ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', str(temporary),
             '-frames:v', '1', '-q:v', '2', str(target)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        temporary.unlink(missing_ok=True)
        return result.returncode == 0 and target.exists() and target.stat().st_size > 0
    except Exception as exc:
        print(f'Free Apple movie-poster lookup skipped for {title}: {exc}')
        return False

def manual_poster(movie):
    candidates = []
    folders = (movie.parent, root / 'custom-posters', root / 'images', root / 'thumbnails')
    # Exact same-name files are checked first so they override older generated
    # "-poster.jpg" files left by pre-beta27 installations.
    suffixes = ('.jpg', '.jpeg', '.png', '.webp', '.bmp',
                '-poster.jpg', '-poster.jpeg', '-poster.png', '-poster.webp', '-poster.bmp',
                '-thumbnail.jpg', '-thumbnail.jpeg', '-thumbnail.png', '-thumbnail.webp', '-thumbnail.bmp',
                )
    for folder in folders:
        for suffix in suffixes:
            candidates.append(folder / (movie.stem + suffix))
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None

def thumbnail(movie, target):
    if target.exists() or not shutil.which('ffmpeg'): return target.exists()
    common = ['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(movie),'-frames:v','1','-vf',
              'scale=480:270:force_original_aspect_ratio=decrease,pad=480:270:(ow-iw)/2:(oh-ih)/2:black',str(target)]
    for seek in ('20','2'):
        subprocess.run(common[:5] + ['-ss', seek] + common[5:], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if target.exists() and target.stat().st_size > 0: return True
    return False

game_list, poster_count = ET.Element('gameList'), 0
for movie in movies:
    relative = movie.relative_to(root)
    safe = re.sub(r'[^A-Za-z0-9._-]+', '_', str(relative.with_suffix('')))
    poster = generated_images / (safe + '-poster.jpg')
    thumb = generated_images / (safe + '-thumb.jpg')
    title, year = identity(movie)
    # beta27/28 briefly tested Wikipedia. Remove its cache marker and any
    # corresponding generated image once so Apple can make a clean attempt.
    legacy_wikipedia_key = 'wikipedia|' + title.lower() + '|' + year
    if legacy_wikipedia_key in cache:
        cache.pop(legacy_wikipedia_key, None)
        poster.unlink(missing_ok=True)
    state = progress_by_path.get(os.path.realpath(movie), {})
    percent = float(state.get('percent') or 0)
    watched = bool(state.get('watched'))
    continuing = 0.03 <= percent < 0.90
    # A user-supplied image is checked first on every refresh and therefore
    # permanently overrides any previously downloaded scraper artwork.
    custom_artwork = manual_poster(movie)
    data = metadata(title, year)
    has_poster = bool(custom_artwork) or poster.exists()
    if not has_poster and data.get('poster_path'):
        has_poster = download('https://image.tmdb.org/t/p/w500' + data['poster_path'], poster)
    if not has_poster:
        has_poster = apple_catalog_poster(title, year, poster)
    artwork = custom_artwork or (poster if has_poster else thumb)
    has_artwork = bool(custom_artwork) or has_poster or thumbnail(movie, thumb)
    poster_count += int(bool(custom_artwork) or has_poster)
    game = ET.SubElement(game_list, 'game')
    ET.SubElement(game, 'path').text = './' + relative.as_posix()
    marker = '✓  ' if watched else (f'▶ {round(percent * 100):d}%  ' if continuing else '')
    automatic_name = title + (f' ({year})' if year else '')
    preserved = preserved_by_path.get(os.path.realpath(movie), {})
    previous_name = unmarked_title(preserved.pop('name', ''))
    # Batocera stores intentional metadata edits in gamelist.xml. Keep a
    # same-path edited title, while a renamed file correctly receives its new
    # filename-derived title because its path no longer matches the old entry.
    display_name = previous_name if previous_name and previous_name != automatic_name else automatic_name
    ET.SubElement(game, 'name').text = marker + display_name
    if has_artwork: ET.SubElement(game, 'image').text = './' + artwork.relative_to(root).as_posix()
    status = 'WATCHED\n\n' if watched else (f'CONTINUE WATCHING — {round(percent * 100):d}% COMPLETE\n\n' if continuing else '')
    ET.SubElement(game, 'desc').text = status + (data.get('overview') or 'Play fullscreen with Batocera Movie Player. Zaparoo compatible.')
    if watched or continuing:
        ET.SubElement(game, 'genre').text = 'Watched' if watched else 'Continue Watching'
        updated = int(state.get('updated') or 0)
        if updated and 'lastplayed' not in preserved:
            ET.SubElement(game, 'lastplayed').text = time.strftime('%Y%m%dT%H%M%S', time.localtime(updated))
    for tag, value in preserved.items():
        ET.SubElement(game, tag).text = value
    if watched and 'playcount' not in preserved:
        ET.SubElement(game, 'playcount').text = '1'
    release = data.get('release_date', '')
    if release: ET.SubElement(game, 'releasedate').text = release.replace('-', '') + 'T000000'
    rating = data.get('rating') or 0
    if rating: ET.SubElement(game, 'rating').text = f'{float(rating) / 10:.2f}'
    group = '0' if continuing else ('2' if watched else '1')
    ET.SubElement(game, 'sortname').text = group + ' ' + display_name

tree = ET.ElementTree(game_list); ET.indent(tree, space='  ')
tree.write(root / 'gamelist.xml', encoding='utf-8', xml_declaration=True)

# The standalone theater theme cannot inherit extended system counters from an
# arbitrary installed theme, so generate a small guaranteed statistics strip.
games = game_list.findall('game')
favorite_count = sum(((g.findtext('favorite') or '').lower() == 'true') for g in games)
played_count = 0
for game in games:
    try:
        played_count += int(game.findtext('playcount', '0') or 0) > 0
    except ValueError:
        pass
stats = f'{len(games)} MOVIES     {favorite_count} FAVORITES     {played_count} PLAYED'
stats_svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 80">
  <text x="600" y="52" text-anchor="middle" font-family="sans-serif" font-size="34" font-weight="bold" fill="#a0a0a0">{html.escape(stats)}</text>
</svg>\n'''
(root / 'movies-stats.svg').write_text(stats_svg, encoding='utf-8')
cache_file.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding='utf-8')
print(f'Movie library refreshed: {len(movies)} movie(s), {poster_count} poster(s)')
if not tmdb_key: print('No-account poster mode: manual art first, then free Apple movie artwork when available.')

# On the real Batocera library, refresh only Zaparoo's Movie system and then
# remove the missing row left by a renamed/deleted file. Run independently so
# Game Lists and the installer never freeze while Core indexes in background.
if root.resolve() == Path('/userdata/roms/movies'):
    zaparoo_refresh = Path(__file__).with_name('zaparoo_media_refresh.py')
    if zaparoo_refresh.is_file():
        subprocess.Popen(
            ['/usr/bin/python3', str(zaparoo_refresh)],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True)
