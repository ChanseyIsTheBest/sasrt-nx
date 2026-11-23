"""Per window: each frame's final shadow mask (B5640E28, channel 0) against its neighbours. mask-odd: how much more
the frame differs from both neighbours than they differ from each other (a one-frame flicker scores high); dark:
share of shadowed pixels. Also a contact sheet per window.
    python mask_score.py <dump dir> <out dir>"""
import os
import re
import sys

import numpy as np
from PIL import Image, ImageDraw

d, outd = sys.argv[1], sys.argv[2]
os.makedirs(outd, exist_ok=True)
PAT = re.compile(r'w(\d+)_f(\d+)_(\d+)_colour_B5640E28_x0_y0_1152x544_fmt20\.bin')
win = {}
for f in os.listdir(d):
    m = PAT.match(f)
    if m and os.path.getsize(os.path.join(d, f)) == 1152 * 544 * 4:
        win.setdefault(int(m.group(1)), []).append((int(m.group(2)), int(m.group(3)), os.path.join(d, f)))
rows = []
for w in sorted(win):
    items = sorted(win[w], key=lambda t: t[1])  # stream order
    masks = [np.fromfile(p, np.uint8).reshape(544, 1152, 4)[:, :, 0].astype(np.float32) for _, _, p in items]
    print('== window %d: %d frames' % (w, len(items)))
    for i, (fr, ser, p) in enumerate(items):
        s = 'f%-6d #%-4d dark %.3f' % (fr, ser, (masks[i] < 128).mean())
        if 0 < i < len(items) - 1:
            odd = np.abs(masks[i] - masks[i - 1]).mean() + np.abs(masks[i] - masks[i + 1]).mean() - 2 * np.abs(masks[i - 1] - masks[i + 1]).mean()
            s += ' odd %+6.1f' % odd
            rows.append((odd, w, fr))
        else:
            s += ' odd      -'
        if i > 0:
            s += ' d-prev %.1f' % np.abs(masks[i] - masks[i - 1]).mean()
        print('  ', s)
    tw, th = 384, 181
    sheet = Image.new('L', (tw * 4, th * ((len(items) + 3) // 4)))
    for i, (fr, ser, p) in enumerate(items):
        t = Image.fromarray(masks[i].astype(np.uint8)).resize((tw, th))
        ImageDraw.Draw(t).text((4, 4), 'f%d #%d' % (fr, ser), fill=255)
        sheet.paste(t, ((i % 4) * tw, (i // 4) * th))
    sheet.save(os.path.join(outd, 'w%02d_masks.png' % w))
rows.sort(reverse=True)
print('highest odd scores:', ', '.join('w%d f%d %+.1f' % (w, fr, o) for o, w, fr in rows[:12]))
