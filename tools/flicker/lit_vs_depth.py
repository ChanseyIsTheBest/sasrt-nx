"""Per dumped frame group (stream order: scene depth, mask, atlas, lit), which scene depth (previous, own, next group)
has the lit image's edges: the correlation of edge maps (gradient magnitudes, top 10 % as edges).
    python lit_vs_depth.py <dump dir> <window>"""
import os
import re
import sys

import numpy as np

d, win = sys.argv[1], int(sys.argv[2])
PAT = re.compile(r'w(\d+)_f(\d+)_(\d+)_(\w+?)_([0-9A-F]{8})_x0_y0_(\d+)x(\d+)_fmt(\d+)\.bin')
items = []
for f in os.listdir(d):
    m = PAT.match(f)
    if m and int(m.group(1)) == win and m.group(4) != 'pass':
        items.append((int(m.group(3)), int(m.group(2)), m.group(5), os.path.join(d, f)))
items.sort()
groups, cur = [], {}
for ser, fr, addr, p in items:
    if addr == 'B5640B28' and cur:
        groups.append(cur)
        cur = {}
    cur[addr] = (fr, ser, p)
if cur:
    groups.append(cur)
H, W = 544, 1152


def edges(a):
    gy, gx = np.gradient(a.astype(np.float64))
    g = np.hypot(gx, gy)
    return g > np.percentile(g, 90)


dep = []
for g in groups:
    if 'B5640B28' in g:
        z = np.fromfile(g['B5640B28'][2], np.float32).reshape(H, W)
        dep.append(edges(np.log(np.maximum(z, 1e-6))))
    else:
        dep.append(None)


def agree(a, b):
    return (a & b).sum() / max(1, (a | b).sum())


print('window %d' % win)
for i, g in enumerate(groups):
    if 'B5642E28' not in g:
        continue
    lit = np.fromfile(g['B5642E28'][2], np.uint8).reshape(H, W, 4)[:, :, :3].astype(np.float64).mean(axis=2)
    le = edges(lit)
    s = []
    for j, name in ((i - 1, 'prev'), (i, 'own'), (i + 1, 'next')):
        s.append('%s %.3f' % (name, agree(le, dep[j])) if 0 <= j < len(dep) and dep[j] is not None else '%s   -  ' % name)
    best = max(((agree(le, dep[j]) if 0 <= j < len(dep) and dep[j] is not None else -1), n) for j, n in ((i - 1, 'prev'), (i, 'own'), (i + 1, 'next')))[1]
    mask = g.get('B5640E28', (0, 0))[0]
    print('  group %d mask f%d lit #%d: edge overlap with depth %s  -> %s' % (i, mask, g['B5642E28'][1], ' | '.join(s), best))
