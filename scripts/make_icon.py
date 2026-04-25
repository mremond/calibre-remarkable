#!/usr/bin/env python3
"""Generate a reMarkable-style plugin icon at images/icon.png."""

import os
from PIL import Image, ImageDraw

SIZE = 128
OUT = os.path.join(os.path.dirname(__file__), '..', 'images', 'icon.png')

BG = (0, 0, 0, 0)
BEZEL = (40, 40, 40, 255)
SCREEN = (245, 242, 232, 255)
LINE = (70, 70, 70, 255)
METAL_LIGHT = (210, 210, 212, 255)
METAL_DARK = (150, 150, 154, 255)
STYLUS_BODY = (30, 30, 30, 255)
STYLUS_TIP = (200, 200, 200, 255)


def rounded_rect(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill,
                           outline=outline, width=width)


def main():
    img = Image.new('RGBA', (SIZE, SIZE), BG)
    d = ImageDraw.Draw(img)

    # Tablet body (portrait, rM2-style: wider left bezel, thin elsewhere).
    body_left, body_top, body_right, body_bottom = 18, 8, 92, 120
    rounded_rect(d, (body_left, body_top, body_right, body_bottom),
                 radius=8, fill=BEZEL)

    # E-ink screen — wider gap on the left to make room for the metal strip.
    left_bezel = 12
    inset = 5
    screen_box = (body_left + left_bezel, body_top + inset,
                  body_right - inset, body_bottom - inset)
    rounded_rect(d, screen_box, radius=2, fill=SCREEN)

    # Brushed-aluminum strip along the left edge (rM2 hallmark).
    strip_left = body_left + 3
    strip_right = body_left + left_bezel - 3
    strip_top = body_top + 10
    strip_bottom = body_bottom - 10
    # Vertical gradient bands to suggest brushed metal.
    bands = strip_bottom - strip_top
    for i in range(bands):
        t = i / max(bands - 1, 1)
        # Smooth light→dark→light shimmer.
        shimmer = abs(0.5 - t) * 2
        r = int(METAL_LIGHT[0] * (1 - shimmer) + METAL_DARK[0] * shimmer)
        g = int(METAL_LIGHT[1] * (1 - shimmer) + METAL_DARK[1] * shimmer)
        b = int(METAL_LIGHT[2] * (1 - shimmer) + METAL_DARK[2] * shimmer)
        d.line([(strip_left, strip_top + i), (strip_right, strip_top + i)],
               fill=(r, g, b, 255), width=1)

    # Hand-written-style notes on the screen.
    sx0, sy0, sx1, sy1 = screen_box
    sw = sx1 - sx0
    rows = [
        (0.18, [(0.10, 0.78)]),
        (0.30, [(0.10, 0.62)]),
        (0.42, [(0.10, 0.85)]),
        (0.54, [(0.10, 0.55)]),
        (0.66, [(0.10, 0.72)]),
        (0.78, [(0.10, 0.45)]),
    ]
    for ry, segs in rows:
        y = sy0 + (sy1 - sy0) * ry
        for fx0, fx1 in segs:
            d.line([(sx0 + sw * fx0, y), (sx0 + sw * fx1, y)],
                   fill=LINE, width=2)

    # Stylus diagonally on the right side (Marker-like).
    stylus = Image.new('RGBA', (SIZE, SIZE), BG)
    sd = ImageDraw.Draw(stylus)
    sd.rounded_rectangle((58, 6, 68, 96), radius=4, fill=STYLUS_BODY)
    sd.polygon([(58, 96), (68, 96), (63, 108)], fill=STYLUS_TIP)
    sd.rectangle((58, 28, 68, 32), fill=(90, 90, 90, 255))
    stylus = stylus.rotate(-18, resample=Image.BICUBIC, center=(63, 60))
    img.alpha_composite(stylus)

    img.save(OUT, format='PNG', optimize=True)
    print(f'wrote {OUT} ({img.size[0]}x{img.size[1]})')


if __name__ == '__main__':
    main()
