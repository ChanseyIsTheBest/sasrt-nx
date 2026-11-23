"""Write chosen frames of a raw capture side by side (or as a grid) at full size.

  python frames.py <capture.rgba> <out.png> <i,j,k,...> [cols=2] [scale=1.0] [crop x0,y0,x1,y1]
"""
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

raw, out = sys.argv[1], sys.argv[2]
idx = [int(v) for v in sys.argv[3].split(',')]
cols = int(sys.argv[4]) if len(sys.argv) > 4 else 2
scale = float(sys.argv[5]) if len(sys.argv) > 5 else 1.0
crop = [int(v) for v in sys.argv[6].split(',')] if len(sys.argv) > 6 else None
w, h, fps, n = open(raw[:-5] + '.txt').read().split()
w, h, n = int(w), int(h), int(n)
frames = np.memmap(raw, np.uint8, 'r').reshape(-1, h, w, 4)[:n]
font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 16)
tiles = []
for i in idx:
    a = np.asarray(frames[i, :, :, :3])
    if crop:
        a = a[crop[1]:crop[3], crop[0]:crop[2]]
    im = Image.fromarray(a)
    if scale != 1.0:
        im = im.resize((int(im.width * scale), int(im.height * scale)), Image.NEAREST if scale > 1 else Image.BILINEAR)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 60, 20], fill=(0, 0, 0))
    d.text((4, 2), str(i), fill=(255, 255, 0), font=font)
    tiles.append(im)
tw, th = tiles[0].size
rows = (len(tiles) + cols - 1) // cols
sheet = Image.new('RGB', (cols * tw, rows * th), (0, 0, 0))
for k, im in enumerate(tiles):
    sheet.paste(im, ((k % cols) * tw, (k // cols) * th))
sheet.save(out)
print(out, sheet.size)
