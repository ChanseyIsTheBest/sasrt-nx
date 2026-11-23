"""The k-th shading draw of a mask pass redone in software from the dumped inputs, scored against the console's own
result (the pixels that draw darkened: pass k minus pass k-1). The cascade row is taken from the draw's own matrix
scale (|c16.xyz|: ~0.027 near row 0, ~0.008 middle row 1, ~0.0013 far row 2). Two atlas-v mappings are tried: 'atlas'
(v over the whole 3072 rows) and 'row' (v over the cascade's own 1024 rows). The atlas may be taken from another
label (cross-pairing) with atlas=<label>.
    python soft_match2.py <log> <shadow_dump> <label> <k> [atlas=<label>] [depth=<serial>]"""
import os
import re
import sys
from collections import defaultdict

import numpy as np

log, d = sys.argv[1], sys.argv[2]
label, k = int(sys.argv[3]), int(sys.argv[4])
atlas_label, depth_serial, consts_label = label, None, label
for a in sys.argv[5:]:
    if a.startswith('atlas='):
        atlas_label = int(a[6:])
    if a.startswith('depth='):
        depth_serial = a[6:]
    if a.startswith('consts='):
        consts_label = int(a[7:])
LINE = re.compile(r'light volume: frame (\d+) draw \d+ \(\w+\) vs ([0-9A-F]{16}) ps ([0-9A-F]{16})(.*)$')
CREG = re.compile(r' c(\d+)\*? \(([^)]*)\)')
shading = defaultdict(list)
sphere = {}
for line in open(log, encoding='utf-8', errors='replace'):
    m = LINE.search(line)
    if not m:
        continue
    fr, vs, ps, rest = int(m.group(1)), m.group(2), m.group(3), m.group(4)
    if fr != consts_label:
        continue
    regs = {int(r): np.array([float(x) for x in v.split()]) for r, v in CREG.findall(rest)}
    if ps == '0' * 16:
        if vs.startswith('98B5') and fr not in sphere and 0 in regs and 3 in regs:
            sphere[fr] = regs
    else:
        shading[fr].append((ps[:4], regs))
files = sorted(os.listdir(d))


def find(pattern, shape, dtype=np.float32):
    for f in files:
        if re.match(pattern, f):
            return np.fromfile(os.path.join(d, f), dtype).reshape(shape)
    return None


def pass_file(lb, kk):
    a = find(r'w\d+_f%d_\d+_pass_%08X_' % (lb, kk), (544, 1152, 4), np.uint8)
    return a[:, :, 0] if a is not None else None


H, W = 544, 1152
ps, c = shading[consts_label][k]
s = sphere[consts_label]
if depth_serial:
    z = find(r'w\d+_f\d+_%s_depth_B5640B28_' % depth_serial, (H, W))
else:
    z = find(r'w\d+_f%d_\d+_depth_B5640B28_' % label, (H, W))
atlas = find(r'w\d+_f%d_\d+_late_B5640EA8_' % atlas_label, (3072, 1024))
after = pass_file(label, k)
before = pass_file(label, k - 1) if k > 0 else np.full((H, W), 255, np.uint8)
print('label %d draw %d ps %s: inputs depth %s atlas(f%d) %s passes %s/%s' % (label, k, ps, z is not None, atlas_label, atlas is not None, before is not None, after is not None))
scale16 = float(np.linalg.norm(c[16][:3]))
row = 0 if scale16 > 0.015 else (1 if scale16 > 0.004 else 2)
print('  |c16| %.5f -> cascade row %d; c14 %s; c23 %s; c24 %s' % (scale16, row, c[14], c.get(23), c.get(24)))
console = (after < 128) & ~(before < 128)
print('  console: this draw darkened %d pixels' % int(console.sum()))
py, px = np.mgrid[0:H, 0:W]
ndc_x = (px + 0.5) / W * 2 - 1
ndc_y = 1 - (py + 0.5) / H * 2
R = abs(s[3][2])
P00, P11 = s[0][0] / R, s[1][1] / R
dist = np.where(z > 1e-6, 0.25 / np.maximum(z, 1e-6), 1e9)
Px, Py, Pz = ndc_x / P00 * dist, ndc_y / P11 * dist, -dist
lu = c[16][0] * Px + c[16][1] * Py + c[16][2] * Pz + c[16][3]
lv = c[17][0] * Px + c[17][1] * Py + c[17][2] * Pz + c[17][3]
recv = c[18][0] * Px + c[18][1] * Py + c[18][2] * Pz + c[18][3]
bias = np.exp2(c[13][2] * np.log2(np.maximum(np.abs(Pz), 1e-6))) * c[13][0] + c[13][1]
recv = recv - bias
valid = z > 1e-6
for mode in ('atlas', 'row'):
    tx = lu * 1024.0 - 0.5
    ty = (lv * 3072.0 - 0.5) if mode == 'atlas' else (lv * 1024.0 - 0.5 + 1024.0 * row)
    x0 = np.floor(tx).astype(np.int64)
    y0 = np.floor(ty).astype(np.int64)
    fx, fy = tx - x0, ty - y0
    inside = (x0 >= 0) & (x0 < 1023) & (y0 >= 0) & (y0 < 3071) & valid
    x0c, y0c = np.clip(x0, 0, 1022), np.clip(y0, 0, 3070)
    lit = lambda st: ((1.0 - st) >= recv).astype(np.float32)
    a = (lit(atlas[y0c, x0c]) * (1 - fx) + lit(atlas[y0c, x0c + 1]) * fx) * (1 - fy) + \
        (lit(atlas[y0c + 1, x0c]) * (1 - fx) + lit(atlas[y0c + 1, x0c + 1]) * fx) * fy
    dark = (a < 0.5) & inside
    # scored only where the console drew: inside its darkened set (hits) and the model's dark pixels within the draw's
    # shell, taken as the pixels the console touched (dark) plus its lit neighbours we cannot see: report hit rate and
    # the model's dark share over the console's dark set and over the whole valid image
    hit = (dark & console).sum() / max(1, console.sum())
    lu_in = ((lu >= 0) & (lu <= 1) & (lv >= 0) & (lv <= 1) & console).sum() / max(1, console.sum())
    # the wedge region of w4 (x >= 640, 180 <= y < 380) within the first shell (distance < 25)
    wedge = (px >= 640) & (py >= 180) & (py < 380) & valid & (dist < 25)
    margin = (1.0 - atlas[y0c, x0c]) - recv  # lit when >= 0
    print('  mode %-5s: model dark at %.3f of the console-darkened pixels (uv inside 0..1 there: %.3f); model dark share of all valid pixels %.3f; wedge region (%d px in the shell): model dark %.3f, margin (1-stored)-recv median %+.5f' % (
        mode, hit, lu_in, dark[valid].mean(), int(wedge.sum()), dark[wedge].mean() if wedge.any() else float('nan'),
        float(np.median(margin[wedge])) if wedge.any() else float('nan')))
