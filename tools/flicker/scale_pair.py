"""Per near-band shading draw (ps 9041): its |c16| (view -> atlas u of the near cascade) beside half the |c138| of the
casters of the recording its atlas (t2) came from, and of the recordings before and after. Same game frame: equal.
    python scale_pair.py <log>"""
import math
import re
import sys

log = sys.argv[1]
CREG = re.compile(r' c(\d+)\*? \(([^)]*)\)')
CAST = re.compile(r'shadow caster: frame (\d+) draw \d+ vs (\w{4}).*?own tag buf \w+ rec (\d+) swaps b(\d+) e(\d+) s(\d+):(.*)$')
LV = re.compile(r'light volume: frame (\d+) draw (\d+) \(\w+\) vs [0-9A-F]{16} ps ([0-9A-F]{4})[0-9A-F]{12} .*?own tag buf \w+ rec (\d+) swaps b(\d+) e(\d+) s(\d+):(.*)$')
TAG2 = re.compile(r't2 va [^|]*?tag buf \w+ rec (\d+)')


def nrm(v):
    return math.sqrt(sum(x * x for x in v[:3]))


casters = {}
draws = []
for line in open(log, encoding='utf-8', errors='replace'):
    m = CAST.search(line)
    if m:
        regs = {int(r): [float(x) for x in v.split()] for r, v in CREG.findall(m.group(7))}
        if 138 in regs:
            casters.setdefault(int(m.group(3)), (nrm(regs[138]) / 2, nrm(regs[139]) / 2, regs[138][3], regs[139][3]))
        continue
    m = LV.search(line)
    if m and m.group(3) == '9041':
        regs = {int(r): [float(x) for x in v.split()] for r, v in CREG.findall(m.group(8))}
        t = TAG2.search(line)
        if 16 in regs:
            draws.append((int(m.group(1)), int(m.group(2)), int(m.group(4)), int(t.group(1)) if t else None, nrm(regs[16]), nrm(regs[17]), regs[16][3], regs[17][3]))
seen = set()
bad = 0
print('frame draw  mask.rec atlas.rec  |c16|      caster(atlas.rec)/2  ratio     caster(rec-1)  caster(rec+1)')
for fr, d, rec, arec, n16, n17, w16, w17 in draws:
    key = (rec, round(n16, 6))
    if key in seen:
        continue
    seen.add(key)
    c = casters.get(arec)
    cm = casters.get(arec - 1) if arec else None
    cp = casters.get(arec + 1) if arec else None
    ratio = n16 / c[0] if c else float('nan')
    flag = '' if c and abs(ratio - 1) < 2e-3 else '  <-- MISMATCH' if c else '  (no caster line)'
    if c and abs(ratio - 1) >= 2e-3:
        bad += 1
    print('f%-6d %2d  %6d %6s  %.6f  %s  %s  %s  %s%s' % (
        fr, d, rec, arec, n16, '%.6f' % c[0] if c else '   -    ', '%.5f' % ratio if c else '   -   ',
        '%.6f' % cm[0] if cm else '   -    ', '%.6f' % cp[0] if cp else '   -    ', flag))
print('%d near-band draws (distinct), %d mismatched' % (len(seen), bad))
