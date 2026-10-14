#!/usr/bin/python3
"""Consolidate legacy movie storage into /userdata/roms/movies safely."""
import hashlib
import os
import shutil
from pathlib import Path

old = Path('/userdata/movies')
new = Path('/userdata/roms/movies')

def same_file(a, b):
    if a.stat().st_size != b.stat().st_size:
        return False
    def digest(path):
        h = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                h.update(block)
        return h.digest()
    return digest(a) == digest(b)

# Early packages sometimes made the canonical ROM folder a symlink to the old
# folder. Replace it with a real directory before moving the library.
if new.is_symlink():
    source = new.resolve()
    staging = new.with_name('movies-migration-staging')
    staging.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        for item in source.iterdir():
            shutil.move(str(item), str(staging / item.name))
    new.unlink()
    staging.rename(new)
else:
    new.mkdir(parents=True, exist_ok=True)

if old.is_symlink():
    old.unlink()
elif old.is_dir() and old.resolve() != new.resolve():
    conflicts = new / '_legacy_import'
    for item in list(old.iterdir()):
        target = new / item.name
        if not target.exists():
            shutil.move(str(item), str(target))
        elif item.is_file() and target.is_file() and same_file(item, target):
            item.unlink()
        else:
            conflicts.mkdir(exist_ok=True)
            alternate = conflicts / item.name
            number = 2
            while alternate.exists():
                alternate = conflicts / f'{item.stem}-{number}{item.suffix}'
                number += 1
            shutil.move(str(item), str(alternate))
    try:
        old.rmdir()
    except OSError:
        pass

print('Movie library: /userdata/roms/movies')
print('Legacy movie content was consolidated without creating a duplicate path.')
