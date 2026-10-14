import importlib.util
import hashlib
import re
import subprocess
import tempfile
import threading
import time
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('movie_session', ROOT/'files/movie-session.py')
session = importlib.util.module_from_spec(spec)
spec.loader.exec_module(session)
theme_spec = importlib.util.spec_from_file_location(
    'install_movies_theme', ROOT/'files/install_movies_theme.py')
theme_installer = importlib.util.module_from_spec(theme_spec)
theme_spec.loader.exec_module(theme_installer)
refresh_spec = importlib.util.spec_from_file_location(
    'zaparoo_media_refresh', ROOT/'files/zaparoo_media_refresh.py')
zaparoo_refresh = importlib.util.module_from_spec(refresh_spec)
refresh_spec.loader.exec_module(zaparoo_refresh)


class PosterFormatTests(unittest.TestCase):
    def test_manual_posters_support_webp_in_all_naming_styles(self):
        builder = (ROOT / 'files/build_movie_gamelist.py').read_text()
        for suffix in ('-poster.webp', '-thumbnail.webp', '.webp'):
            self.assertIn(repr(suffix), builder)
        self.assertIn('JPG, JPEG, PNG, WEBP and BMP',
                      (ROOT / 'files/MANUAL-POSTERS.txt').read_text())


class ProcessDetectionTests(unittest.TestCase):
    def test_zaparoo_waits_through_british_optimisation_message(self):
        calls = []
        def fake_rpc(method, params=None, timeout=10):
            calls.append(method)
            if method == 'media.generate' and calls.count('media.generate') == 1:
                raise RuntimeError('background optimisation is in progress')
            if method == 'media.clean.orphans':
                return {'deleted': 1}
            return None
        with patch.object(zaparoo_refresh, 'rpc', side_effect=fake_rpc), \
             patch.object(zaparoo_refresh, 'wait_until_idle'), \
             patch.object(zaparoo_refresh.time, 'sleep') as sleep:
            self.assertEqual(zaparoo_refresh.refresh(), 1)
        self.assertEqual(calls.count('media.generate'), 2)
        sleep.assert_called_once_with(1)

    def test_zaparoo_rename_refresh_indexes_movie_then_cleans_orphans(self):
        calls = []
        def fake_rpc(method, params=None, timeout=10):
            calls.append((method, params))
            if method == 'media.clean.orphans':
                return {'deleted': 1}
            return None
        with patch.object(zaparoo_refresh, 'rpc', side_effect=fake_rpc), \
             patch.object(zaparoo_refresh, 'wait_until_idle') as wait:
            self.assertEqual(zaparoo_refresh.refresh(), 1)
        self.assertEqual(calls[0], ('media.generate', {
            'systems': ['Movie'], 'fuzzySystem': True}))
        wait.assert_called_once_with()
        self.assertEqual(calls[-1], ('media.clean.orphans', None))

    def test_detects_full_emulationstation_argv_without_comm_truncation(self):
        with tempfile.TemporaryDirectory() as directory:
            proc = Path(directory)
            (proc / '123').mkdir()
            (proc / '123' / 'cmdline').write_bytes(
                b'/usr/bin/emulationstation\0--home\0')
            self.assertTrue(session.process_is_running('emulationstation', proc))

    def test_does_not_mistake_init_script_for_frontend(self):
        with tempfile.TemporaryDirectory() as directory:
            proc = Path(directory)
            (proc / '456').mkdir()
            (proc / '456' / 'cmdline').write_bytes(
                b'/etc/init.d/S31emulationstation\0start\0')
            self.assertFalse(session.process_is_running('emulationstation', proc))

    def test_movie_claims_display_before_starting_mpv(self):
        manager = (ROOT / 'files/movie-session.py').read_text()
        play = manager[manager.index('    def play(self, media):'):
                       manager.index('    def keep_es_hidden', manager.index('    def play(self, media):'))]
        self.assertLess(play.index('self.stop_es()'),
                        play.index('self.mpv = subprocess.Popen(args'))
        self.assertNotIn("pgrep', '-x', 'emulationstation", manager)

    def test_beta15_theme_is_deployed_at_rom_folder_and_clone_is_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = root/'app'; app.mkdir()
            target = root/'roms/movies/theme.xml'
            carbon = root/'carbon/theme.xml'; carbon.parent.mkdir()
            carbon.write_text('<theme><formatVersion>7</formatVersion></theme>')
            (app/'movies-theme.xml').write_bytes((ROOT/'files/movies-theme.xml').read_bytes())
            settings = root/'es_settings.cfg'
            settings.write_text('<?xml version="1.0"?><config><string name="ThemeSet" value="movie-player-carbon"/><string name="movies.defaultView" value="detailed"/></config>')
            (app/'ORIGINAL_THEMESET').write_text('carbon\n')
            (app/'ORIGINAL_MOVIES_DEFAULT_VIEW').write_text('__MISSING__\n')
            clone = root/'themes/movie-player-carbon'; clone.mkdir(parents=True)
            with patch.object(theme_installer, 'APP', app), \
                 patch.object(theme_installer, 'TARGET', target), \
                 patch.object(theme_installer, 'LOG', root/'install.log'), \
                 patch.object(theme_installer, 'SETTINGS', settings), \
                 patch.object(theme_installer, 'OLD_CLONE', clone), \
                 patch.object(theme_installer, 'SAVED_THEME', app/'ORIGINAL_THEMESET'), \
                 patch.object(theme_installer, 'SAVED_VIEW', app/'ORIGINAL_MOVIES_DEFAULT_VIEW'), \
                 patch.object(theme_installer, 'find_carbon', return_value=carbon.resolve()):
                self.assertEqual(theme_installer.main(), 0)
            self.assertTrue(target.is_file())
            self.assertIn(str(carbon.resolve()), target.read_text())
            self.assertFalse(clone.exists())
            tree = theme_installer.ET.parse(settings)
            values = {n.get('name'): n.get('value') for n in tree.getroot().findall('string')}
            self.assertEqual(values.get('ThemeSet'), 'carbon')
            self.assertEqual(values.get('movies.defaultView'), 'detailed')

    def test_standard_update_game_lists_is_the_only_routine_user_step(self):
        manager = (ROOT / 'files/movie-session.py').read_text()
        installer = (ROOT / 'install.sh').read_text()
        manual = (ROOT / 'files/MANUAL-POSTERS.txt').read_text()
        self.assertIn('def watch_movie_library():', manager)
        self.assertIn("threading.Thread(target=watch_movie_library", manager)
        self.assertIn('install_autostart.py', installer)
        self.assertIn('Game Settings > Update Game Lists', manual)
        self.assertNotIn('Then run:\n  Ports > Refresh Movie Library', manual)

    def test_title_edits_and_renames_have_distinct_refresh_rules(self):
        builder = (ROOT / 'files/build_movie_gamelist.py').read_text()
        installer = (ROOT / 'install.sh').read_text()
        repair = (ROOT / 'files/Repair Movie Library - Only If Needed.sh').read_text()
        self.assertIn("for tag in ('name', 'favorite'", builder)
        self.assertIn("previous_name = unmarked_title(preserved.pop('name', ''))", builder)
        self.assertIn('display_name = previous_name if previous_name', builder)
        self.assertIn("ET.SubElement(game, 'sortname').text = group + ' ' + display_name", builder)
        self.assertNotIn('files/Refresh Movie Library.sh', installer)
        self.assertIn('Repair Movie Library - Only If Needed.sh', installer)
        self.assertIn('Zaparoo Movie refresh was started automatically', repair)
        self.assertIn('zaparoo_media_refresh.py', builder)

    def test_manual_title_survives_then_real_file_rename_replaces_path(self):
        with tempfile.TemporaryDirectory() as directory:
            movies = Path(directory)
            original = movies / 'Christmas_Story.mp4'
            original.touch()
            gamelist = ET.Element('gameList')
            game = ET.SubElement(gamelist, 'game')
            ET.SubElement(game, 'path').text = './Christmas_Story.mp4'
            ET.SubElement(game, 'name').text = 'My Family Christmas Movie'
            ET.ElementTree(gamelist).write(movies / 'gamelist.xml', encoding='utf-8')
            env = dict(__import__('os').environ)
            env['PATH'] = '/directory-with-no-ffmpeg'
            command = ['/usr/bin/python3', str(ROOT / 'files/build_movie_gamelist.py'), str(movies)]
            subprocess.run(command, check=True, env=env, capture_output=True, text=True)
            first = ET.parse(movies / 'gamelist.xml').getroot().find('game')
            self.assertEqual(first.findtext('name'), 'My Family Christmas Movie')

            renamed = movies / 'A_Cristmas_Story.mp4'
            original.rename(renamed)
            subprocess.run(command, check=True, env=env, capture_output=True, text=True)
            games = ET.parse(movies / 'gamelist.xml').getroot().findall('game')
            self.assertEqual(len(games), 1)
            self.assertEqual(games[0].findtext('path'), './A_Cristmas_Story.mp4')
            self.assertEqual(games[0].findtext('name'), 'A Cristmas Story')

    def test_free_no_account_poster_fallback_and_manual_override(self):
        builder = (ROOT / 'files/build_movie_gamelist.py').read_text()
        self.assertIn('def apple_catalog_poster(', builder)
        self.assertIn('https://itunes.apple.com/search?', builder)
        self.assertNotIn('wikipedia_poster', builder.lower())
        self.assertNotIn('wikipedia.org', builder.lower())
        self.assertIn("legacy_wikipedia_key = 'wikipedia|'", builder)
        self.assertIn('poster.unlink(missing_ok=True)', builder)
        self.assertIn("generated_images = images / '.generated'", builder)
        self.assertLess(builder.index("suffixes = ('.jpg'"),
                        builder.index("'-poster.jpg'"))
        self.assertLess(builder.index('custom_artwork = manual_poster(movie)'),
                        builder.index('has_poster = bool(custom_artwork)'))


class FakeProc:
    next_pid = 5000
    def __init__(self, args):
        self.args = args
        self.pid = FakeProc.next_pid; FakeProc.next_pid += 1
        self.done = threading.Event()
        self.code = None
    def poll(self): return self.code
    def wait(self, timeout=None):
        if not self.done.wait(timeout):
            raise session.subprocess.TimeoutExpired(self.args, timeout)
        return self.code
    def terminate(self): self.finish(-15)
    def kill(self): self.finish(-9)
    def finish(self, code=0): self.code = code; self.done.set()


class SessionLifecycleTests(unittest.TestCase):
    def test_persistent_player_uses_background_core_lifecycle(self):
        client = (ROOT/'files/movie-client.py').read_text()
        launcher = (ROOT/'files/BatoceraMoviePlayer.toml').read_text()
        self.assertIn('lifecycle = "background"', launcher)
        self.assertNotIn("status = request({'action': 'status'})", client)
        self.assertNotIn("if not status.get('active')", client)
        self.assertNotIn("request({'action': 'wait', 'token': reply['token']})", client)
        self.assertNotIn("request({'action': 'wait_media'", client)

    def test_second_movie_reuses_mpv_and_final_exit_restores_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp)/'first.mp4'; first.write_bytes(b'1')
            second = Path(tmp)/'second.mkv'; second.write_bytes(b'2')
            created = []
            def fake_popen(args, **kwargs):
                proc = FakeProc(args); created.append(proc); return proc
            state = session.State()
            state.log = lambda *_: None
            state.stop_es = lambda: setattr(state, 'es_owned', True)
            state.es_running = lambda: False
            restores = []
            state.restore_es = lambda: restores.append('restored')
            commands = []
            state.mpv_command = lambda command, attempts=20: commands.append(command) or True
            with patch.object(session, 'LOG_PATH', Path(tmp)/'player.log'), \
                 patch.object(session.subprocess, 'Popen', side_effect=fake_popen):
                token1 = state.play(str(first))
                mpv = state.mpv
                token2 = state.play(str(second))
                self.assertEqual(token2, token1 + 1)
                self.assertIs(state.mpv, mpv)
                self.assertIn(['loadfile', str(second), 'replace'], commands)
                self.assertIn(['set', 'pause', 'no'], commands)
                self.assertIn(['set', 'mute', 'no'], commands)
                self.assertIn(['vf', 'remove', '@movie-picture'], commands)
                self.assertIn(['set', 'video-zoom', '0.0'], commands)
                self.assertEqual(sum(p.args[0] == 'mpv' for p in created), 1)
                bridges = [p for p in created if isinstance(p.args, list) and
                           p.args and str(p.args[0]).endswith('python3') and
                           any(str(arg).endswith('controller_bridge.py') for arg in p.args)]
                self.assertEqual(len(bridges), 2)
                self.assertIs(state.bridge, bridges[-1])
                self.assertIsNot(bridges[0], bridges[-1])
                self.assertEqual(restores, [])
                mpv.finish(0)
                for _ in range(250):
                    if restores: break
                    time.sleep(0.01)
                self.assertEqual(restores, ['restored'])

    def test_all_launch_routes_use_single_client(self):
        launcher = (ROOT/'files/BatoceraMoviePlayer.toml').read_text()
        system = (ROOT/'files/es_systems_movies.cfg').read_text()
        self.assertIn('movie-client.py', launcher)
        self.assertIn('zaparoo-launch.py', system)
        self.assertIn('%ROM_RAW%', system)
        self.assertNotIn('&quot;%ROM%&quot;', system)

    def test_update_preserves_working_zaparoo_connection(self):
        installer = (ROOT/'install.sh').read_text()
        self.assertNotIn('/usr/bin/python3 "$APP_DIR/configure_zaparoo.py"', installer)
        self.assertNotIn('-service restart', installer)
        self.assertNotIn('-service reload', installer)
        self.assertIn('PRESERVED - NOT CHANGED', installer)

    def test_core_handoff_has_verified_direct_fallback(self):
        handoff = (ROOT/'files/zaparoo-launch.py').read_text()
        self.assertIn('def direct_fallback', handoff)
        self.assertIn("movie-client.py", handoff)
        self.assertIn("direct_fallback('Core accepted the request", handoff)

    def test_movies_installs_authoritative_beta15_system_theme(self):
        installer = (ROOT/'install.sh').read_text()
        theme = (ROOT/'files/movies-theme.xml').read_text()
        binder = (ROOT/'files/install_movies_theme.py').read_text()
        self.assertNotIn('configure_movie_theme.py', installer)
        self.assertNotIn('/sync_system_theme.py" || true', installer)
        self.assertIn('/usr/bin/python3 "$APP_DIR/install_movies_theme.py"', installer)
        self.assertIn('<include>__CARBON_THEME__</include>', theme)
        self.assertIn("return candidate.resolve()", binder)
        self.assertIn("TARGET = Path('/userdata/roms/movies/theme.xml')", binder)
        self.assertIn("deployed = source.replace('__CARBON_THEME__', str(carbon))", binder)
        self.assertIn("TARGET.write_text(deployed", binder)
        self.assertIn("SAVED_VIEW = APP / 'ORIGINAL_MOVIES_DEFAULT_VIEW'", binder)
        self.assertIn("OLD_CLONE = Path('/userdata/themes/movie-player-carbon')", binder)
        self.assertIn('shutil.rmtree(OLD_CLONE)', binder)
        self.assertIn("theme.set('value', original or 'carbon')", binder)
        self.assertIn("view.set('value', 'detailed')", binder)
        self.assertIn("'<customView name=\"Icons,Tiles,Carousel,Boxes,Content\"'", binder)
        self.assertIn("'<imagegrid name=\"gamegrid\">'", binder)
        self.assertIn('ET.parse(TARGET)', binder)
        self.assertIn("'name=\"e_poster_frame\"'", binder)
        self.assertNotIn('/etc/init.d/S31emulationstation stop', installer)
        self.assertNotIn('/etc/init.d/S31emulationstation start', installer)
        self.assertNotIn("RETURN_COMMAND='sleep 2;", installer)
        self.assertIn('movies-theater-background.png', theme)
        self.assertIn('<image name="logo"><path>./movies-logo.png</path>', theme)
        self.assertIn('<image name="e_list_panel"', theme)
        self.assertIn('<image name="e_art_panel"', theme)
        self.assertIn('<theme defaultView="detailed">', theme)
        for name in ('backgroundMachines', 'backgroundvideo', 'randomImage',
                     'box', 'videobox', 'ControllerOverlay'):
            self.assertIn(f'name="{name}"', theme)
        self.assertIn('<video name="md_video"><visible>true</visible>', theme)

    def test_large_poster_and_text_stay_inside_right_panel(self):
        theme = (ROOT/'files/movies-theme.xml').read_text()
        self.assertIn('<maxSize>0.255 0.480</maxSize>', theme)
        self.assertIn('<maxSize>0.320 0.570</maxSize>', theme)
        self.assertIn('<text name="md_name"><pos>0.515 0.770</pos>', theme)
        self.assertIn('<text name="md_description"><pos>0.525 0.845</pos><size>0.41 0.075</size>', theme)
        self.assertIn('<customView name="Icons,Tiles,Carousel,Boxes,Content"', theme)

    def test_unknown_movie_metadata_is_not_displayed(self):
        theme = (ROOT/'files/movies-theme.xml').read_text()
        self.assertIn('<datetime name="md_releasedate"><visible>false</visible></datetime>', theme)
        self.assertIn('<text name="md_genre"><visible>false</visible></text>', theme)
        self.assertIn('<text name="md_playcount"><visible>false</visible></text>', theme)
        self.assertIn('<text name="e_movies_facts" extra="true"><visible>false</visible></text>', theme)
        self.assertNotIn('Played: {game:playcount}', theme)
        self.assertIn('<imagegrid name="gamegrid">', theme)
        self.assertIn('<textlist name="gamelist">', theme)

    def test_working_main_carousel_is_locked(self):
        theme = (ROOT/'files/movies-theme.xml').read_text()
        block = re.search(r'  <view name="system">.*?  </view>', theme, re.S)
        self.assertIsNotNone(block)
        digest = hashlib.sha256(block.group(0).encode()).hexdigest()
        self.assertEqual(digest, '4afc047343ac1f69f641b814b7a4db20af3bdae7630640625989e6ec8651323c')

    def test_working_movies_library_view_is_locked_separately(self):
        theme = (ROOT/'files/movies-theme.xml').read_text()
        block = re.search(r'  <view name="detailed">.*?  </view>', theme, re.S)
        self.assertIsNotNone(block)
        digest = hashlib.sha256(block.group(0).encode()).hexdigest()
        self.assertEqual(digest, '8c0c53b5762491997d4fa6a3e875530691f29b0fb184d4d9621fb2acfe09ac47')

    def test_beta15_approved_visuals_are_frozen(self):
        expected = {
            'movies-theme.xml': '89057eeffe0799febb47ca73a2d28578dec7335a00cd6368d5a87c5bb1dd1d75',
            'movies-logo.png': 'e91b71e0922bcaf4c583481fa41a1a390633bea3f0b17a2b89946f47e14a216d',
            'movies-theater-background.png': 'a01a736537cb0803fa4913270e468ff8b6d84cda893ea18280db1f73d18ae940',
            'movie-poster-frame.png': 'bef97d12cca5aa5175cd28f9f31f316dc0d4f638dda614d34027c195ce764dab',
            'movies-panel.svg': 'ce352327e4d8bd4b91a12b11562ae3f186f90b977dc6f4ca517814678102dd2b',
            'movies-carousel-rules.svg': 'f13fc763632d33793742c0ebb21cd425885983104a8d560eaf51cbae5e3cdff5',
        }
        for filename, digest in expected.items():
            self.assertEqual(hashlib.sha256((ROOT/'files'/filename).read_bytes()).hexdigest(), digest)

    def test_game_handoff_is_distinct_from_b_exit(self):
        bridge = (ROOT/'files/controller_bridge.py').read_text()
        manager = (ROOT/'files/movie-session.py').read_text()
        self.assertIn('game_handoff()', bridge)
        self.assertIn('if code in STOP_CODES and value == 1', bridge)
        self.assertIn("elif action == 'game_handoff'", manager)
        self.assertIn('self.start_es_and_wait()', manager)
        self.assertIn("self.mpv_command(['quit'])", manager)
        self.assertIn('def watch_zaparoo_launches():', manager)
        self.assertIn('def extract_launch_path(line):', manager)
        self.assertIn("es_api('/launch', body=game_path", manager)
        self.assertIn("if 'NO GAME RUNNING' not in payload.upper()", manager)
        self.assertIn('verify_or_replay_game(game_path)', manager)

    def test_movie_playback_keeps_frontend_hidden(self):
        manager = (ROOT/'files/movie-session.py').read_text()
        self.assertIn('def keep_es_hidden(self, watched):', manager)
        self.assertIn('and not self.game_handoff', manager)
        self.assertIn('Frontend guard stopped EmulationStation reopened during movie playback', manager)
        self.assertIn('target=self.keep_es_hidden', manager)
        self.assertIn('def restore_after_quiet(self, ended_token):', manager)
        self.assertIn('MOVIE_SWITCH_MARKER.touch()', manager)
        self.assertIn('Skipped frontend restore because another media launch is pending', manager)

    def test_movie_scan_hides_frontend_before_player_request(self):
        manager = (ROOT/'files/movie-session.py').read_text()
        movie_branch = manager[manager.index("if lower_path.startswith('/userdata/roms/movies/')"):
                               manager.index('movie_active = bool', manager.index("if lower_path.startswith('/userdata/roms/movies/')"))]
        self.assertIn('STATE.prehide_for_movie_scan(game_path)', movie_branch)
        self.assertIn('def restore_failed_movie_prelaunch(self, prelaunch, token):', manager)
        self.assertIn('Scanned movie did not start within 10 seconds; restoring EmulationStation', manager)

    def test_failed_movie_prelaunch_restores_but_successful_playback_does_not(self):
        class ActiveProc:
            def poll(self): return None
        state = session.State()
        state.log = lambda *_: None
        state.es_owned = True
        restored = []
        state.restore_es = lambda: restored.append('restored')
        with patch.object(session.time, 'sleep', return_value=None):
            state.restore_failed_movie_prelaunch(0, 0)
            self.assertEqual(restored, ['restored'])
            restored.clear()
            state.mpv = ActiveProc()
            state.restore_failed_movie_prelaunch(0, 0)
            self.assertEqual(restored, [])

    def test_game_handoff_never_blocks_on_es_start(self):
        manager = (ROOT/'files/movie-session.py').read_text()
        self.assertIn('def start_es_async():', manager)
        self.assertIn("subprocess.Popen(['/etc/init.d/S31emulationstation', 'start']", manager)
        self.assertIn("return process_is_running('emulationstation')", manager)
        self.assertNotIn("['pgrep', '-x', 'emulationstation']", manager)

    def test_game_handoff_releases_display_then_launches_when_api_was_blocked(self):
        calls = []
        class HandoffState:
            mpv = None
            def show_game_stage(self, stage, label): calls.append(('stage', stage, label))
            def release_game_handoff(self): calls.append(('release',))
            def log(self, message): calls.append(('log', message))
        checks = {'count': 0}
        def fake_api(path, body=None, timeout=1.0):
            if path == '/runningGame':
                checks['count'] += 1
                if checks['count'] <= 50:
                    raise session.urllib.error.URLError('display still owned')
                if any(call[0] == 'launch' for call in calls):
                    return body or '/userdata/roms/nes/Test Game.zip'
                return 'NO GAME RUNNING'
            calls.append(('launch', body))
            return 'OK'
        with patch.object(session, 'STATE', HandoffState()), \
             patch.object(session, 'es_api', side_effect=fake_api), \
             patch.object(session.time, 'sleep', return_value=None):
            session.verify_or_replay_game('/userdata/roms/nes/Test Game.zip')
        self.assertEqual(calls[0], ('stage', 2, 'STARTING GAME SYSTEM'))
        self.assertIn(('stage', 3, 'HANDING OFF DISPLAY'), calls)
        self.assertLess(calls.index(('release',)),
                        calls.index(('launch', '/userdata/roms/nes/Test Game.zip')))

    def test_api_recovery_continues_pending_game_instead_of_stopping_at_menu(self):
        calls = []
        recovered = {'value': False}
        class HandoffState:
            mpv = None
            def show_game_stage(self, stage, label): calls.append(('stage', stage, label))
            def release_game_handoff(self): calls.append(('release',))
            def log(self, message): calls.append(('log', message))
        def fake_api(path, body=None, timeout=1.0):
            if path == '/runningGame' and not recovered['value']:
                raise session.urllib.error.URLError('API wedged until clean restart')
            if path == '/launch':
                calls.append(('launch', body))
                return 'OK'
            if any(call[0] == 'launch' for call in calls):
                return '/userdata/roms/megadrive/Twin Cobra (USA).md'
            return 'NO GAME RUNNING'
        def fake_restart():
            recovered['value'] = True
            calls.append(('restart-api',))
            return True
        with patch.object(session, 'STATE', HandoffState()), \
             patch.object(session, 'es_api', side_effect=fake_api), \
             patch.object(session, 'restart_es_until_api', side_effect=fake_restart), \
             patch.object(session.time, 'sleep', return_value=None):
            session.verify_or_replay_game('/userdata/roms/megadrive/Twin Cobra (USA).md')
        self.assertIn(('restart-api',), calls)
        self.assertIn(('launch', '/userdata/roms/megadrive/Twin Cobra (USA).md'), calls)
        self.assertLess(calls.index(('restart-api',)),
                        calls.index(('launch', '/userdata/roms/megadrive/Twin Cobra (USA).md')))

    def test_game_handoff_retries_when_menu_reports_no_game_running(self):
        launches = []
        class HandoffState:
            mpv = None
            def show_game_stage(self, *_): pass
            def release_game_handoff(self): pass
            def log(self, *_): pass
        checks = {'after_launch': 0}
        def fake_api(path, body=None, timeout=1.0):
            if path == '/launch':
                launches.append(body)
                return 'OK'
            if launches:
                checks['after_launch'] += 1
                if len(launches) == 2 and checks['after_launch'] > 50:
                    return '/userdata/roms/nes/Test Game.zip'
            return 'NO GAME RUNNING'
        with patch.object(session, 'STATE', HandoffState()), \
             patch.object(session, 'es_api', side_effect=fake_api), \
             patch.object(session.time, 'sleep', return_value=None):
            session.verify_or_replay_game('/userdata/roms/nes/Test Game.zip')
        self.assertEqual(launches, ['/userdata/roms/nes/Test Game.zip'] * 2)

    def test_frozen_theme_gets_one_time_live_activation(self):
        installer = (ROOT/'install.sh').read_text()
        autostart = (ROOT/'files/install_autostart.py').read_text()
        activator = (ROOT/'files/activate_movies_theme.py').read_text()
        self.assertIn('copy_app_file activate_movies_theme.py', installer)
        self.assertIn('activate_movies_theme.py', autostart)
        self.assertIn("MARKER = APP / 'THEME_ACTIVATED_VERSION'", activator)
        self.assertIn("S31emulationstation', 'stop'", activator)
        self.assertIn("S31emulationstation', 'start'", activator)
        self.assertIn('def theme_is_already_live():', activator)
        self.assertIn('frontend restart skipped', activator)
        self.assertLess(activator.index('if theme_is_already_live():'),
                        activator.index("S31emulationstation', 'stop'"))

    def test_game_path_extraction_preserves_spaces(self):
        plain = '2026 INFO launch media: /userdata/roms/ps2/My Game (USA).iso'
        structured = '{"level":"info","message":"launch media: /userdata/roms/snes/Super Game.sfc"}'
        self.assertEqual(session.extract_launch_path(plain), '/userdata/roms/ps2/My Game (USA).iso')
        self.assertEqual(session.extract_launch_path(structured), '/userdata/roms/snes/Super Game.sfc')

    def test_failed_game_handoff_recovers_frontend(self):
        manager = (ROOT/'files/movie-session.py').read_text()
        self.assertIn('def recover_frontend():', manager)
        self.assertIn("STATE.log('Recovering EmulationStation", manager)
        self.assertIn('ready = restart_es_until_api()', manager)
        self.assertIn('continuing pending game launch', manager)
        self.assertIn('def restart_es_until_api():', manager)
        self.assertIn("es_api('/runningGame', timeout=0.35)", manager)
        self.assertIn("STATE.log('EmulationStation API verified after clean restart')", manager)
        self.assertIn("HANDOFF_MARKER.touch()", manager)
        self.assertIn("str(APP / f'game-loading-{stage}.png')", manager)
        self.assertIn('STATE.release_game_handoff()', manager)

    def test_public_beta_installer_has_no_jrt3d_splash(self):
        installer = (ROOT/'install.sh').read_text()
        banner = ROOT/'files/jrt3d-installer.png'
        self.assertNotIn('show_jrt3d_brand', installer)
        self.assertNotIn('copy_app_file jrt3d-installer.png', installer)
        self.assertFalse(banner.exists())

    def test_installer_reports_verified_theme_status(self):
        installer = (ROOT/'install.sh').read_text()
        self.assertIn('THEME_STATUS="PASSED"', installer)
        self.assertIn('THEME CHECK: ${THEME_STATUS}', installer)

    def test_x_fit_fill_and_y_zoom_use_explicit_properties(self):
        bridge = (ROOT/'files/controller_bridge.py').read_text()
        self.assertIn('FIT_CODES = {BTN_NORTH, 290, 258}', bridge)
        self.assertIn('ZOOM_CODES = {BTN_WEST, 291, 259}', bridge)
        self.assertIn('["set", "panscan"', bridge)
        self.assertIn('@movie-picture:crop=iw/', bridge)
        self.assertIn('@movie-picture:crop={crop_w}:{crop_h}', bridge)
        self.assertIn('video-params/aspect', bridge)
        self.assertIn('osd-dimensions/aspect', bridge)
        self.assertIn('(1.0, 1.15, 1.30, 1.50)', bridge)
        self.assertIn('["set", "video-scale-x", "1.0"]', bridge)
        self.assertIn('["set", "video-scale-y", "1.0"]', bridge)
        self.assertIn('actual = property_value("vf"', bridge)
        self.assertIn('ratio = 4 / 3', bridge)
        self.assertIn('["set", "video-zoom", "0.0"]', bridge)
        player = (ROOT/'files/movie-player.sh').read_text()
        self.assertIn('--keepaspect=yes', player)
        self.assertIn('--video-unscaled=no', player)

    def test_approved_picture_controls_are_locked(self):
        bridge = (ROOT/'files/controller_bridge.py').read_text()
        block = bridge[bridge.index('def reset_picture_filter():'):bridge.index('\ndef command(payload):')]
        self.assertEqual(hashlib.sha256(block.encode()).hexdigest(),
                         '8a5c1655752e4fe896fa0f2b57171e4df7fd05819745a12ee9a591afb808285a')

    def test_installer_waits_in_f1_for_explicit_close_without_restart(self):
        installer = (ROOT/'install.sh').read_text()
        self.assertIn('Nothing will restart or reboot automatically.', installer)
        self.assertIn('Choose CLOSE INSTALLER to return to the F1 file manager.', installer)
        self.assertIn('--ok-label "CLOSE INSTALLER"', installer)
        self.assertIn('xterm -T "Batocera Movie App Version ${VERSION} - Installed"', installer)
        self.assertNotIn('mpv --fullscreen --ontop', installer)
        self.assertNotIn('SUCCESS_PID', installer)

    def test_public_credit_is_in_installer_not_everyday_movies_theme(self):
        installer = (ROOT/'install.sh').read_text()
        theme = (ROOT/'files/movies-theme.xml').read_text()
        version_screen = (ROOT/'files/Movie Player Version.sh').read_text()
        self.assertIn('Created by Joshua R. Taylor', installer)
        self.assertIn('JRT3D.com', installer)
        self.assertIn('Created by Joshua R. Taylor', version_screen)
        self.assertNotIn('Joshua R. Taylor', theme)
        self.assertNotIn('JRT3D.com', theme)
        self.assertNotIn('restore_es_after_install', installer)
        self.assertNotIn('batocera-es-swissknife --restart', installer)
        self.assertNotIn('/etc/init.d/S31emulationstation', installer)
        self.assertNotIn('setsid -f sh -c "$RETURN_COMMAND"', installer)
        self.assertNotIn('read -r -p "Press Enter to close."', installer)

    def test_restart_from_beginning_has_keyboard_and_controller_paths(self):
        bridge = (ROOT/'files/controller_bridge.py').read_text()
        readme = (ROOT/'README.txt').read_text()
        self.assertIn('def restart_movie():', bridge)
        self.assertIn('["seek", 0, "absolute+exact"]', bridge)
        self.assertIn('["set", "pause", "no"]', bridge)
        self.assertIn('RESTARTED FROM BEGINNING', bridge)
        self.assertIn('code == BTN_THUMBL', bridge)
        self.assertIn('code == BTN_SELECT and rate_limit("restart-prompt"', bridge)
        self.assertIn('RESTART MOVIE FROM BEGINNING?', bridge)
        self.assertIn('A = YES     B = CANCEL', bridge)
        self.assertIn('confirm_restart_prompt()', bridge)
        self.assertIn('cancel_restart_prompt()', bridge)
        self.assertIn('code == BTN_SOUTH and BTN_SELECT in pressed', bridge)
        self.assertIn('code == KEY_R', bridge)
        self.assertIn('Controller L3 / keyboard R', readme)

    def test_game_handoff_survives_synthetic_exit_race_and_stays_visible(self):
        manager = (ROOT/'files/movie-session.py').read_text()
        self.assertIn("str(APP / f'game-loading-{stage}.png')", manager)
        self.assertIn("self.show_game_stage(1, 'STARTING BATOCERA')", manager)
        self.assertIn("STATE.show_game_stage(2, 'STARTING GAME SYSTEM')", manager)
        self.assertIn("STATE.show_game_stage(3, 'HANDING OFF DISPLAY')", manager)
        self.assertIn('recent_movie_exit = time.monotonic() - STATE.last_movie_end < 30.0', manager)
        self.assertIn('if movie_active or recent_movie_exit or STATE.es_owned:', manager)
        self.assertIn("f'STEP {stage} OF 3", manager)
        replay = manager[manager.index('def request_launch():'):
                         manager.index('\ndef recover_frontend')]
        self.assertLess(replay.index('threading.Thread(target=request_launch'),
                        replay.index('STATE.release_game_handoff()'))
        self.assertLess(replay.index('STATE.release_game_handoff()'),
                        replay.index('finished.wait(36.0)'))
        for stage in (1, 2, 3):
            self.assertTrue((ROOT/f'files/game-loading-{stage}.png').is_file())

    def test_complex_zaparoo_paths_are_quoted_for_current_media(self):
        handoff = (ROOT/'files/zaparoo-launch.py').read_text()
        self.assertIn('**launch:"{escaped_movie}"?system=Movie', handoff)

    def test_poster_and_frame_preserve_ratio_above_panel(self):
        theme = (ROOT/'files/movies-theme.xml').read_text()
        self.assertIn('<maxSize>0.320 0.570</maxSize><zIndex>31</zIndex>', theme)
        self.assertNotIn('e_poster_mat', theme)
        self.assertIn('<maxSize>0.255 0.480</maxSize><showSnapshotNoVideo>true</showSnapshotNoVideo>', theme)
        self.assertIn('<image name="md_image"><visible>true</visible>', theme)
        self.assertIn('<size>0.49 0.735</size><zIndex>20</zIndex>', theme)
        self.assertIn('<text name="md_description"><pos>0.525 0.845</pos>', theme)

    def test_carbon_owns_help_bar_style(self):
        installer = (ROOT/'install.sh').read_text()
        theme = (ROOT/'files/movies-theme.xml').read_text()
        self.assertIn('movies-theme.xml', installer)
        self.assertNotIn('<helpsystem name="help">', theme)
        self.assertNotIn('<iconColor>', theme)
        self.assertNotIn('<textColor>', theme)

    def test_old_carbon_installer_is_not_installed_or_executed(self):
        installer = (ROOT/'install.sh').read_text()
        self.assertNotIn('copy_app_file install_carbon_movies_theme.py', installer)
        self.assertNotIn('copy_app_file movies-carbon-theme.xml', installer)
        self.assertNotIn('copy_app_file sync_system_theme.py', installer)
        self.assertNotIn('if /usr/bin/python3 "$APP_DIR/install_carbon_movies_theme.py"', installer)
        self.assertIn('rm -f "$APP_DIR/install_carbon_movies_theme.py"', installer)

    def test_movie_exit_never_restores_stale_full_settings(self):
        session_source = (ROOT/'files/movie-session.py').read_text()
        self.assertNotIn('write_bytes(original_settings)', session_source)
        self.assertIn('restore_startup_only', session_source)
        self.assertIn('Read the live file after ES starts', session_source)

    def test_log_export_always_has_plain_text_fallback_and_live_geometry(self):
        collector = (ROOT/'files/Collect Movie Player Logs.sh').read_text()
        self.assertIn('/userdata/Movie-Player-Diagnostics.txt', collector)
        self.assertIn('EXPORT SUCCESSFUL', collector)
        self.assertIn('LOG EXPORT FAILED', collector)
        self.assertIn("'video-params/aspect'", collector)
        self.assertIn("'osd-dimensions/aspect'", collector)
        self.assertIn("'video-zoom'", collector)
        self.assertIn('name="ThemeSet"', collector)
        self.assertIn('name="movies.defaultView"', collector)

    def test_system_carousel_and_statistics_are_inherited_from_carbon(self):
        theme = (ROOT/'files/movies-theme.xml').read_text()
        builder = (ROOT/'files/build_movie_gamelist.py').read_text()
        self.assertNotIn('name="e_movies_carousel_rules"', theme)
        self.assertIn('<customView name="Icons,Tiles,Carousel,Boxes,Content"', theme)
        self.assertNotIn('<text name="systemInfo">', theme)
        self.assertIn('<include>__CARBON_THEME__</include>', theme)
        self.assertIn('FAVORITES', builder)
        self.assertIn('PLAYED', builder)

    def test_movies_logo_is_approved_movies_artwork(self):
        logo = (ROOT/'files/movies-logo.png').read_bytes()
        self.assertEqual(
            hashlib.sha256(logo).hexdigest(),
            'e91b71e0922bcaf4c583481fa41a1a390633bea3f0b17a2b89946f47e14a216d',
        )

    def test_refresh_preserves_batocera_user_metadata(self):
        builder = (ROOT/'files/build_movie_gamelist.py').read_text()
        for tag in ('favorite', 'playcount', 'lastplayed', 'gametime'):
            self.assertIn("'" + tag + "'", builder)

    def test_controls_have_one_owner_and_virtual_exit_has_race_guard(self):
        bridge = (ROOT/'files/controller_bridge.py').read_text()
        mpv_conf = (ROOT/'files/mpv-input.conf').read_text()
        self.assertIn('KEY_SPACE, KEY_ENTER', bridge)
        self.assertNotIn('cycle pause', mpv_conf)
        self.assertNotIn('HOLD B', bridge)
        self.assertIn('if code in STOP_CODES and value == 1', bridge)
        self.assertIn('def deferred_stop():', bridge)
        self.assertIn('time.sleep(0.8)', bridge)
        self.assertIn('threading.Thread(target=deferred_stop', bridge)


if __name__ == '__main__': unittest.main()
