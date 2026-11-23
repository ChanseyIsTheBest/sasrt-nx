# sasrt-nx (2026-11-21): sasrt_renut_diag_view_dump's files (view_dump/d<dump>_v<view>_<what>_<w>x<h>_m<mode>.bin) to
# PNGs, and a sheet per dump: one row per view, its images side by side (each scaled to 288 high), plus numbers.
#   python view_dump.py DIR [OUT]
#   mode 11: 4 bytes a texel, the first channel's float bits (depth): shown 0..1 (white = 1) and as its own range;
#   mode 12: unorm8 x 4 (RGB shown, alpha as its own image); mode 13: four floats (each channel by its range).
import glob
import os
import re
import sys

import numpy as np
from PIL import Image, ImageDraw

src = sys.argv[1]
out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(src, 'png')
os.makedirs(out, exist_ok=True)
NAME = re.compile(r'd(\d+)_v(\d)_(.+)_(\d+)x(\d+)_m(\d+)\.bin$')


def to8(a, lo=None, hi=None):
    a = np.nan_to_num(a.astype(np.float64), nan=0.0, posinf=0.0, neginf=0.0)
    lo = np.min(a) if lo is None else lo
    hi = np.max(a) if hi is None else hi
    return (np.clip((a - lo) / max(hi - lo, 1e-12), 0, 1) * 255).astype(np.uint8)


sheets = {}
for path in sorted(glob.glob(os.path.join(src, '*.bin'))):
    m = NAME.search(os.path.basename(path))
    if not m:
        continue
    dump, view, what, w, h, mode = int(m[1]), int(m[2]), m[3], int(m[4]), int(m[5]), int(m[6])
    raw = np.fromfile(path, dtype=np.uint8)
    base = os.path.join(out, os.path.basename(path)[:-4])
    imgs = []
    if mode == 11:
        f = raw.view(np.float32).reshape(h, w)
        fin = f[np.isfinite(f)]
        stats = 'min %.5f max %.5f mean %.5f; <=0 %.1f%% >=1 %.1f%%' % (
            fin.min(), fin.max(), fin.mean(), 100 * np.mean(fin <= 0), 100 * np.mean(fin >= 1))
        # rows in thirds: the far (top) part of a view against the near (bottom)
        thirds = ' | '.join('%.4f' % f[i * h // 3:(i + 1) * h // 3].mean() for i in range(3))
        print('d%d v%d %-22s %4dx%-4d %s; mean by thirds top->bottom %s' % (dump, view, what, w, h, stats, thirds))
        imgs.append(('0..1', Image.fromarray(to8(f, 0.0, 1.0))))
        imgs.append(('range', Image.fromarray(to8(f))))
    elif mode == 12:
        a = raw.reshape(h, w, 4)
        print('d%d v%d %-22s %4dx%-4d rgba means %s; thirds (rgb mean) top->bottom %s' % (
            dump, view, what, w, h, ' '.join('%.1f' % a[..., c].mean() for c in range(4)),
            ' | '.join('%.1f' % a[i * h // 3:(i + 1) * h // 3, :, :3].mean() for i in range(3))))
        imgs.append(('rgb', Image.fromarray(a[..., :3].copy())))
        imgs.append(('a', Image.fromarray(a[..., 3].copy())))
    elif mode == 13:
        f = raw.view(np.float32).reshape(h, w, 4)
        print('d%d v%d %-22s %4dx%-4d channel ranges %s' % (dump, view, what, w, h, ' '.join(
            '[%.4f %.4f]' % (np.nanmin(f[..., c]), np.nanmax(f[..., c])) for c in range(4))))
        imgs.append(('rgb', Image.fromarray(np.stack([to8(f[..., c]) for c in range(3)], -1))))
        imgs.append(('a', Image.fromarray(to8(f[..., 3]))))
    for tag, im in imgs:
        im.save('%s_%s.png' % (base, tag))
        sheets.setdefault(dump, {}).setdefault(view, []).append(('%s %s' % (what, tag), im))

for dump, views in sheets.items():
    row_h = 288
    rows = []
    for view in sorted(views):
        tiles = []
        for label, im in views[view]:
            s = row_h / im.height
            t = im.convert('RGB').resize((max(1, int(im.width * s)), row_h))
            ImageDraw.Draw(t).text((4, 4), 'v%d %s' % (view, label), fill=(255, 0, 255))
            tiles.append(t)
        width = sum(t.width for t in tiles) + 4 * len(tiles)
        row = Image.new('RGB', (width, row_h), (40, 40, 40))
        x = 0
        for t in tiles:
            row.paste(t, (x, 0))
            x += t.width + 4
        rows.append(row)
    sheet = Image.new('RGB', (max(r.width for r in rows), sum(r.height + 4 for r in rows)), (20, 20, 20))
    y = 0
    for r in rows:
        sheet.paste(r, (0, y))
        y += r.height + 4
    p = os.path.join(out, 'sheet_d%d.jpg' % dump)
    sheet.save(p, quality=88)
    print('sheet', p, sheet.size)
