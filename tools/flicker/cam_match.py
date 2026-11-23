"""Which scene-pass camera the shading uses, from the log alone (sasrt_renut_diag_depth_writers + light_volumes -1).
Per frame label F in the dump windows: the game thread's casters' near-cascade row c138 (world -> light clip x), the
near-band shading draw's c16 (view -> atlas u), and the scene passes' camera rotations R (rows c131-c133: world ->
view) of the runs replayed at F-1, F and F+1. If the shading's view is the scene's, c16.xyz = 0.5 * c138.xyz * R^T (a
rotation of c138 into view space): the cosine between c16.xyz and that prediction is 1 for the matching camera.
    python tools/flicker/cam_match.py <log>"""
import math
import re
import sys
from collections import defaultdict

log = sys.argv[1]
CREG = re.compile(r' c(\d+)\*? \(([^)]*)\)')
CAST = re.compile(r'shadow caster: frame (\d+) .*?(c138 \([^)]*\))')
LV = re.compile(r'light volume: frame (\d+) draw \d+ \(\w+\) vs [0-9A-F]+ ps 9041')
SP = re.compile(r'scene pass: frame (\d+) rec (\d+) ')
casters, shading, scene = {}, {}, {}
for line in open(log, encoding='utf-8', errors='replace'):
    m = SP.search(line)
    if m:
        regs = {int(r): [float(x) for x in v.split()] for r, v in CREG.findall(line)}
        if 131 in regs and 133 in regs and 136 in regs and abs(regs[136][2] + 1) < 0.01:
            scene.setdefault(int(m.group(1)), regs)
        continue
    m = CAST.search(line)
    if m:
        regs = {int(r): [float(x) for x in v.split()] for r, v in CREG.findall(line)}
        if 138 in regs:
            casters.setdefault(int(m.group(1)), regs)
        continue
    m = LV.search(line)
    if m:
        regs = {int(r): [float(x) for x in v.split()] for r, v in CREG.findall(line)}
        if 16 in regs:
            shading.setdefault(int(m.group(1)), regs)


def norm(v):
    return math.sqrt(sum(x * x for x in v))


def cos(a, b):
    return sum(x * y for x, y in zip(a, b)) / max(1e-12, norm(a) * norm(b))


def predict(c138, sc):
    R = [sc[131][:3], sc[132][:3], sc[133][:3]]  # world -> view rows
    # view -> world is R^T; c16 . P_view = 0.5 * c138 . (R^T P_view) => c16.xyz = 0.5 * R c138.xyz
    return [0.5 * sum(R[i][k] * c138[k] for k in range(3)) for i in range(3)]


frames = sorted(set(shading) & set(casters))
verdict = defaultdict(int)
print('frame   cos(c16, predicted with the scene camera replayed at F-1 / F / F+1)   angle in mrad (F-1 / F / F+1)')
for f in frames:
    c16 = shading[f][16][:3]
    c138 = casters[f][138][:3]
    out = []
    best = None
    for d, name in ((-1, 'F-1'), (0, 'F'), (1, 'F+1')):
        sc = scene.get(f + d)
        if not sc:
            out.append('   -   ')
            continue
        c = cos(c16, predict(c138, sc))
        ang = math.acos(max(-1.0, min(1.0, c))) * 1000
        out.append('%7.3f' % ang)
        if best is None or ang < best[0]:
            best = (ang, name)
    if best:
        verdict[best[1]] += 1
    print('f%-6d %s  -> %s' % (f, ' / '.join(out), best[1] if best else '-'))
print('closest:', dict(verdict))
