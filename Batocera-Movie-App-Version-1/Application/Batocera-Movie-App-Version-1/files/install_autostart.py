#!/usr/bin/python3
"""Install one managed Batocera boot block without replacing user custom.sh."""
import re
from pathlib import Path

target = Path('/userdata/system/custom.sh')
begin = '# BEGIN BATOCERA MOVIE PLAYER (managed)'
end = '# END BATOCERA MOVIE PLAYER (managed)'
block = f'''{begin}
if [ "$1" = "start" ]; then
  /usr/bin/python3 /userdata/system/batocera-movie-player/activate_movies_theme.py >> /userdata/system/logs/movie-player-install.log 2>&1 || true
  if ! [ -S /tmp/batocera-movie-player/session.sock ]; then
    nohup /usr/bin/python3 /userdata/system/batocera-movie-player/movie-session.py </dev/null >/dev/null 2>&1 &
  fi
fi
{end}'''

existing = target.read_text(encoding='utf-8', errors='ignore') if target.exists() else '#!/bin/bash\n'
existing = re.sub(re.escape(begin) + r'.*?' + re.escape(end) + r'\n?', '', existing,
                  flags=re.DOTALL).rstrip()
if not existing.startswith('#!'):
    existing = '#!/bin/bash\n' + existing
target.write_text(existing + '\n\n' + block + '\n', encoding='utf-8')
target.chmod(target.stat().st_mode | 0o111)
print('Automatic movie-library refresh: installed for Batocera startup')
