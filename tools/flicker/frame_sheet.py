"""Per frame group in stream order (depth, mask, atlas, lit): the lit image, the mask, and the atlas's three cascades
(R32F, 1024x3072, darker = nearer the light), one row per frame; plus atlas statistics.
    python frame_sheet.py <dump dir> <window> <out.png>"""
import os
import re
import sys

import numpy as np
from PIL import Image, ImageDraw

d, win, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
PAT = re.compile(r'w(\d+)_f(\d+)_(\d+)_(\w+?)_([0-9A-F]{8})_x0_y0_(\d+)x(\d+)_fmt(\d+)\.bin')
items = []
for f in os.listdir(d):
    m = PAT.match(f)
    if m and int(m.group(1)) == win and m.group(4) != 'pass':
        items.append((int(m.group(3)), int(m.group(2)), m.group(4), m.group(5), os.path.join(d, f)))
items.sort()
groups = []
cur = {}
for ser, fr, kind, addr, p in items:
    if addr == 'B5640B28' and cur:
        groups.append(cur)
        cur = {}
    cur[addr] = (fr, ser, p)
if cur:
    groups.append(cur)
tw, th = 384, 181
rows = []
for g in groups:
    row = Image.new('RGB', (tw * 2 + 3 * 120, th))
    label = []
    if 'B5642E28' in g:
        a = np.fromfile(g['B5642E28'][2], np.uint8).reshape(544, 1152, 4)
        row.paste(Image.fromarray(a[:, :, [2, 1, 0]]).resize((tw, th)), (0, 0))
        label.append('lit #%d' % g['B5642E28'][1])
    if 'B5640E28' in g:
        a = np.fromfile(g['B5640E28'][2], np.uint8).reshape(544, 1152, 4)[:, :, 0]
        row.paste(Image.fromarray(a).convert('RGB').resize((tw, th)), (tw, 0))
        label.append('mask f%d #%d dark %.2f' % (g['B5640E28'][0], g['B5640E28'][1], (a < 128).mean()))
    if 'B5640EA8' in g:
        at = np.fromfile(g['B5640EA8'][2], np.float32).reshape(3072, 1024)
        stats = []
        for k in range(3):
            c = at[k * 1024:(k + 1) * 1024]
            v = c[c < 0.9999]
            lo, hi = (np.percentile(v, 2), np.percentile(v, 98)) if v.size else (0, 1)
            img = np.clip((c - lo) / max(hi - lo, 1e-6) * 255, 0, 255).astype(np.uint8)
            img[c >= 0.9999] = 255
            row.paste(Image.fromarray(img).convert('RGB').resize((120, th)), (tw * 2 + k * 120, 0))
            stats.append('%.3f' % ((c < 0.9999).mean()))
        label.append('atlas #%d covered %s' % (g['B5640EA8'][1], '/'.join(stats)))
    ImageDraw.Draw(row).text((4, 4), ' | '.join(label), fill=(255, 255, 0))
    rows.append(row)
    print(' | '.join(label))
sheet = Image.new('RGB', (rows[0].width, th * len(rows)))
for i, r in enumerate(rows):
    sheet.paste(r, (0, i * th))
sheet.save(out)
