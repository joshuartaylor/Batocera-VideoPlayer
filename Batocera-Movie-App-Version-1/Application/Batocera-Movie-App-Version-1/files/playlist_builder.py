#!/usr/bin/python3
import pathlib, sys

current = pathlib.Path(sys.argv[1]).resolve()
output = pathlib.Path(sys.argv[2])
extensions = {'.mkv','.mp4','.m4v','.avi','.mov','.mpeg','.mpg','.ts','.m2ts','.webm','.wmv','.flv','.ogv','.vob','.3gp'}
movies = sorted((p.resolve() for p in current.parent.iterdir() if p.suffix.lower() in extensions), key=lambda p: p.name.lower())
if current in movies:
    index = movies.index(current)
    movies = movies[index:] + movies[:index]
output.write_text('#EXTM3U\n' + '\n'.join(str(p) for p in movies) + '\n', encoding='utf-8')

