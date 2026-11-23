"""Contact sheet of a raw capture (captures/*.rgba + .txt): every <step>th frame with its index, as a grid.

  python tools/capture_sheet.py <capture.rgba> <out.png> [step=10] [cols=6] [tile width=320] [first=0] [last=-1]
"""
import re
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

raw, out = sys.argv[1], sys.argv[2]
step = int(sys.argv[3]) if len(sys.argv) > 3 else 10
cols = int(sys.argv[4]) if len(sys.argv) > 4 else 6
tw = int(sys.argv[5]) if len(sys.argv) > 5 else 320
first = int(sys.argv[6]) if len(sys.argv) > 6 else 0
last = int(sys.argv[7]) if len(sys.argv) > 7 else -1
w, h, fps, n = open(raw[:-5] + '.txt').read().split()
w, h, n = int(w), int(h), int(n)
frames = np.memmap(raw, np.uint8, 'r').reshape(-1, h, w, 4)[:n]
if last < 0 or last > n:
    last = n
idx = list(range(first, last, step))
th = tw * h // w
rows = (len(idx) + cols - 1) // cols
sheet = Image.new('RGB', (cols * tw, rows * th), (0, 0, 0))
font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 14)
for k, i in enumerate(idx):
    im = Image.fromarray(np.asarray(frames[i, :, :, :3])).resize((tw, th), Image.BILINEAR)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 52, 17], fill=(0, 0, 0))
    d.text((3, 1), str(i), fill=(255, 255, 0), font=font)
    sheet.paste(im, ((k % cols) * tw, (k // cols) * th))
sheet.save(out)
print(out, len(idx), 'tiles', sheet.size)
