"""Per dumped frame group (stream order: scene depth, mask, atlas, lit), the near-band shading draw (ps 9041) redone in
software with the group's own constants and atlas and the scene depth of the previous, its own and the next group.
Printed per pairing: the model's dark share of the valid pixels inside the cascade, and the median margin
((1 - stored) - receiver; lit >= 0, acne < 0). The console's own dark share after that draw (pass 0) for reference.
    python depth_pair.py <log> <dump dir> <window>"""
import os
import re
import sys
from collections import defaultdict

import numpy as np

log, d, win = sys.argv[1], sys.argv[2], int(sys.argv[3])
LINE = re.compile(r'light volume: frame (\d+) draw \d+ \(\w+\) vs ([0-9A-F]{16}) ps ([0-9A-F]{16})(.*)$')
CREG = re.compile(r' c(\d+)\*? \(([^)]*)\)')
shading = defaultdict(list)
sphere = {}
for line in open(log, encoding='utf-8', errors='replace'):
    m = LINE.search(line)
    if not m:
        continue
    fr, vs, ps, rest = int(m.group(1)), m.group(2), m.group(3), m.group(4)
    regs = {int(r): np.array([float(x) for x in v.split()]) for r, v in CREG.findall(rest)}
    if ps == '0' * 16:
        if vs.startswith('98B5') and fr not in sphere and 0 in regs and 3 in regs:
            sphere[fr] = regs
    elif ps.startswith('9041') and 16 in regs:
        shading[fr].append(regs)
PAT = re.compile(r'w(\d+)_f(\d+)_(\d+)_(\w+?)_([0-9A-F]{8})_x0_y0_(\d+)x(\d+)_fmt(\d+)\.bin')
items = []
passes = defaultdict(dict)
for f in os.listdir(d):
    m = PAT.match(f)
    if not m or int(m.group(1)) != win:
        continue
    if m.group(4) == 'pass':
        passes[int(m.group(2))][int(m.group(5), 16)] = os.path.join(d, f)
    else:
        items.append((int(m.group(3)), int(m.group(2)), m.group(5), os.path.join(d, f)))
items.sort()
groups = []
cur = {}
for ser, fr, addr, p in items:
    if addr == 'B5640B28' and cur:
        groups.append(cur)
        cur = {}
    cur[addr] = (fr, p)
if cur:
    groups.append(cur)
H, W = 544, 1152
py, px = np.mgrid[0:H, 0:W]
ndc_x = (px + 0.5) / W * 2 - 1
ndc_y = 1 - (py + 0.5) / H * 2
depths = [np.fromfile(g['B5640B28'][1], np.float32).reshape(H, W) if 'B5640B28' in g else None for g in groups]


def model(c, s, z, atlas):
    R = abs(s[3][2])
    P00, P11 = s[0][0] / R, s[1][1] / R
    dist = np.where(z > 1e-6, 0.25 / np.maximum(z, 1e-6), 1e9)
    Px, Py, Pz = ndc_x / P00 * dist, ndc_y / P11 * dist, -dist
    lu = c[16][0] * Px + c[16][1] * Py + c[16][2] * Pz + c[16][3]
    lv = c[17][0] * Px + c[17][1] * Py + c[17][2] * Pz + c[17][3]
    recv = c[18][0] * Px + c[18][1] * Py + c[18][2] * Pz + c[18][3]
    bias = np.exp2(c[13][2] * np.log2(np.maximum(np.abs(Pz), 1e-6))) * c[13][0] + c[13][1]
    recv = recv - bias
    tx, ty = lu * 1024.0 - 0.5, lv * 3072.0 - 0.5
    x0, y0 = np.floor(tx).astype(np.int64), np.floor(ty).astype(np.int64)
    inside = (x0 >= 0) & (x0 < 1023) & (y0 >= 0) & (y0 < 1023) & (z > 1e-6)  # the near cascade's rows
    x0c, y0c = np.clip(x0, 0, 1022), np.clip(y0, 0, 3070)
    margin = (1.0 - atlas[y0c, x0c]) - recv
    if not inside.any():
        return float('nan'), float('nan'), 0
    # exact alignment: lit ground stores its own depth, so margin == bias; the misfit is median |margin - bias|
    off = np.abs(margin - bias)[inside]
    return float((margin[inside] < 0).mean()), float(np.median(off)), int(inside.sum())


VERDICT = {}
print('window %d: %d groups' % (win, len(groups)))
print('group label   console-pass0-dark | depth from: prev (dark share, median |margin - bias| x1e-5) | own | next')
for i, g in enumerate(groups):
    if 'B5640E28' not in g or 'B5640EA8' not in g:
        continue
    label = g['B5640E28'][0]
    if label not in shading or label not in sphere:
        print('  %d f%d: no constants' % (i, label))
        continue
    c, s = shading[label][0], sphere[label]
    atlas = np.fromfile(g['B5640EA8'][1], np.float32).reshape(3072, 1024)
    p0 = passes.get(label, {}).get(0)
    cons = (np.fromfile(p0, np.uint8).reshape(H, W, 4)[:, :, 0] < 128).mean() if p0 else float('nan')
    parts = []
    fits = []
    for j in (i - 1, i, i + 1):
        if 0 <= j < len(groups) and depths[j] is not None:
            dk, mg, n = model(c, s, depths[j], atlas)
            parts.append('%s %.3f %6.1f' % ('prev' if j < i else 'own ' if j == i else 'next', dk, mg * 1e5))
            fits.append((mg, 'prev' if j < i else 'own' if j == i else 'next'))
        else:
            parts.append('%s   -' % ('prev' if j < i else 'own ' if j == i else 'next'))
    best = min(fits)[1] if fits else '-'
    VERDICT[best] = VERDICT.get(best, 0) + 1
    print('  %2d f%-6d %.3f | %s  -> %s' % (i, label, cons, ' | '.join(parts), best))
print('best fit: %s' % VERDICT)
