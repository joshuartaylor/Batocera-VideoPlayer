#!/usr/bin/python3
"""Generate deterministic 1080p accessibility status screens."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'files'
W, H = 1920, 1080
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'


def font(size, bold=False):
    return ImageFont.truetype(BOLD if bold else FONT, size)


def centered(draw, y, text, size, color, bold=False, stroke=0):
    draw.text((W // 2, y), text, font=font(size, bold), fill=color,
              anchor='mm', align='center', stroke_width=stroke,
              stroke_fill='#101018')


def background():
    image = Image.new('RGB', (W, H))
    pixels = image.load()
    for y in range(H):
        for x in range(W):
            t = (x / W + y / H) / 2
            pixels[x, y] = (int(20 + 24*t), int(10 + 18*t), int(55 + 45*t))
    draw = ImageDraw.Draw(image, 'RGBA')
    for y in range(540, 1080, 110):
        draw.line((0, y, W, y), fill=(45, 226, 230, 90), width=4)
    for x in (160, 480, 720, 1200, 1440, 1760):
        draw.line((960, 540, x, 1080), fill=(45, 226, 230, 90), width=4)
    return image


def loading_game(stage):
    image = background(); draw = ImageDraw.Draw(image, 'RGBA')
    centered(draw, 280, 'LOADING GAME', 132, '#ffffff', True, 10)
    centered(draw, 400, 'PLEASE WAIT — THE SYSTEM IS WORKING', 46, '#ffdb59', True)
    draw.rounded_rectangle((300, 500, 1620, 630), radius=65,
                           fill='#080817', outline='#ffffff', width=8)
    colors = ('#ff2d8d', '#ffb72c', '#2de2e6')
    segment_width = 400
    for index, color in enumerate(colors):
        left = 335 + index * 425
        draw.rounded_rectangle((left, 535, left + segment_width, 595), radius=30,
                               fill=color if index < stage else '#343448',
                               outline='#ffffff' if index < stage else '#686878', width=3)
    labels = ('MOVIE STOPPED', 'BATOCERA STARTING', 'GAME LAUNCHING')
    for x, label in zip((535, 960, 1385), labels):
        draw.text((x, 690), label, font=font(30, True), fill='#ffffff', anchor='mm')
    centered(draw, 900, 'Do not press buttons or restart the system.', 34, '#bdefff')
    centered(draw, 1000, 'BATOCERA MOVIE PLAYER  •  JRT3D.COM', 24, '#9a9aaa')
    image.save(OUT / f'game-loading-{stage}.png', optimize=True)


for current_stage in (1, 2, 3):
    loading_game(current_stage)
