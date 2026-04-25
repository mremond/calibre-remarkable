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
STYLUS_BODY = (30, 30, 30, 255)
STYLUS_TIP = (200, 200, 200, 255)


def rounded_rect(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill,
                           outline=outline, width=width)


def main():
    img = Image.new('RGBA', (SIZE, SIZE), BG)
    d = ImageDraw.Draw(img)

    # Tablet body (portrait, thin bezels) — leave room on the right for stylus.
    body_left, body_top, body_right, body_bottom = 18, 8, 92, 120
    rounded_rect(d, (body_left, body_top, body_right, body_bottom),
                 radius=8, fill=BEZEL)

    # E-ink screen inset.
    inset = 5
    screen_box = (body_left + inset, body_top + inset,
                  body_right - inset, body_bottom - inset - 6)
    rounded_rect(d, screen_box, radius=2, fill=SCREEN)

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

    # Home button indicator at bottom bezel.
    d.ellipse((54, 110, 60, 116), fill=SCREEN)

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
