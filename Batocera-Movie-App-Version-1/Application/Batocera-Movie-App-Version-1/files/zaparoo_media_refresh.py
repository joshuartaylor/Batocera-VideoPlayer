#!/usr/bin/python3
"""Selectively refresh Movie in Zaparoo and remove stale renamed paths."""
import fcntl
import json
import sys
import time
import urllib.request
from pathlib import Path

API = 'http://127.0.0.1:7497/api/v0.1'
LOCK = Path('/tmp/batocera-movie-player/zaparoo-media-refresh.lock')
LOG = Path('/userdata/system/logs/movie-zaparoo-refresh.log')


def rpc(method, params=None, timeout=10):
    payload = {'jsonrpc': '2.0', 'id': 'movie-player-refresh', 'method': method}
    if params is not None:
        payload['params'] = params
    request = urllib.request.Request(
        API, data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.load(response)
    if result.get('error'):
        raise RuntimeError(result['error'].get('message') or str(result['error']))
    return result.get('result')


def wait_until_idle(timeout=240):
    deadline = time.monotonic() + timeout
    saw_indexing = False
    idle_checks = 0
    while time.monotonic() < deadline:
        state = (rpc('media') or {}).get('database', {})
        indexing = bool(state.get('indexing'))
        saw_indexing = saw_indexing or indexing
        if not indexing and (saw_indexing or time.monotonic() > deadline - timeout + 5):
            idle_checks += 1
            if idle_checks >= 3:
                return
        else:
            idle_checks = 0
        time.sleep(0.5)
    raise TimeoutError('Movie indexing did not finish within four minutes')


def refresh():
    # A selective index updates only Movie and marks the renamed path missing.
    for attempt in range(120):
        try:
            rpc('media.generate', {'systems': ['Movie'], 'fuzzySystem': True})
            break
        except RuntimeError as exc:
            # Never cancel phone-started indexing/scraping. Wait and retry the
            # selective Movie request when Core becomes available.
            message = str(exc).lower()
            # "optim" intentionally covers both US "optimization" and the
            # British "optimisation" wording returned by Zaparoo Core 2.16.1.
            if not any(word in message for word in ('progress', 'index', 'busy', 'scrap', 'optim')):
                raise
            if attempt == 119:
                raise TimeoutError('Zaparoo remained busy for two minutes')
            time.sleep(1)
    wait_until_idle()
    result = rpc('media.clean.orphans') or {}
    return int(result.get('deleted') or 0)


def main():
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open('w') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        try:
            deleted = refresh()
            message = f'Zaparoo Movie refresh complete; stale paths removed: {deleted}'
            LOG.write_text(message + '\n', encoding='utf-8')
            print(message)
            return 0
        except Exception as exc:
            message = f'Zaparoo Movie refresh failed: {type(exc).__name__}: {exc}'
            LOG.write_text(message + '\n', encoding='utf-8')
            print(message, file=sys.stderr)
            return 1


if __name__ == '__main__':
    raise SystemExit(main())
