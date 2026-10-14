#!/usr/bin/python3
"""Clean legacy entries and restore phone access on the private LAN.

Movie Player v2.0.1 removed an older marked block which, on some installations,
also contained Zaparoo's service.allowed_ips value. Core then fell back to
localhost-only API access and the phone app could no longer connect. Preserve
the complete config, remove only the marked legacy block, and ensure the
service accepts private-network clients. A backup is kept beside the active
config before any change.
"""
from pathlib import Path
import re

begin = '# BEGIN BATOCERA MOVIE PLAYER'
end = '# END BATOCERA MOVIE PLAYER'
private_lan = (
    'allowed_ips = ["127.0.0.1", "10.0.0.0/8", "172.16.0.0/12", '
    '"192.168.0.0/16", "::1", "fe80::/10", "fc00::/7"]'
)
paths = [
    Path('/userdata/system/.config/zaparoo/config.toml'),
    Path('/userdata/system/.local/share/zaparoo/config.toml'),
]

for config in paths:
    if not config.exists():
        continue
    text = config.read_text(encoding='utf-8')
    original = text
    while begin in text:
        start = text.index(begin)
        finish = text.find(end, start)
        text = text[:start] if finish < 0 else text[:start] + text[finish + len(end):]
    # Core may write this array on one line or several lines.
    allowed_pattern = re.compile(
        r'(?ms)^[ \t]*allowed_ips[ \t]*=[ \t]*\[[^\]]*\][ \t]*(?:#[^\n]*)?$'
    )
    if allowed_pattern.search(text):
        text = allowed_pattern.sub(private_lan, text, count=1)
    else:
        service_header = re.search(r'(?m)^\s*\[service\]\s*(?:#.*)?$', text)
        if service_header:
            insert_at = service_header.end()
            text = text[:insert_at] + '\n' + private_lan + text[insert_at:]
        else:
            text = text.rstrip() + '\n\n[service]\n' + private_lan + '\n'

    if text != original:
        backup = config.with_name(config.name + '.before-movie-player-v2.0.2')
        if not backup.exists():
            backup.write_text(original, encoding='utf-8')
        config.write_text(text.strip() + '\n', encoding='utf-8')
        print(f'Restored private-LAN phone access in {config}')
    else:
        print(f'Private-LAN phone access already configured in {config}')
