#!/usr/bin/env python3
"""sasrt-nx (2026-11-12, docs/cpu-moonshots-1112.md idea 2): stack round trips in the generated code: a load from an
r1-relative slot whose bytes were all written in the same straight-line block by stores of another width or another
register file (the 360 has no moves between general, float and vector registers, so MSVC goes through memory; the A57
cannot forward several narrow stores into one wide load). Weighted by a console profile's samples per function.

  python tools/stack_roundtrip_census.py GEN PROFILE MAP
"""
import collections
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import switch_hot_functions as shf  # noqa: E402

GEN, PROF, MAP = sys.argv[1:4]
HEAD = re.compile(r'^DEFINE_REX_FUNC\((?:__imp__)?sub_([0-9A-F]{8})\) \{$')
COMMENT = re.compile(r'^\t// (\S+)[ \t]*(.*)$')
LABEL = re.compile(r'^loc_[0-9A-F]{8}:')
STORE_W = {'stw': 4, 'stfs': 4, 'stfd': 8, 'std': 8, 'sth': 2, 'stb': 1, 'stvx': 16, 'stvx128': 16, 'stfiwx': 4}
LOAD_W = {'lwz': 4, 'lfs': 4, 'lfd': 8, 'ld': 8, 'lhz': 2, 'lha': 2, 'lbz': 1, 'lvx': 16, 'lvx128': 16, 'lwa': 4,
          'lvlx': 16, 'lvlx128': 16, 'lvewx': 4, 'lvewx128': 4}
FILE = lambda mn: 'v' if 'v' in mn[:3] else ('f' if mn.startswith(('lf', 'stf')) else 'r')

# samples per function address (sub_X and n_X forms)
secs = sorted(shf.load_map(MAP))
starts = [s[0] for s in secs]
import bisect
PC = re.compile(r'^\s+[\d.]+%\s+pc image\+0x([0-9a-f]+) x(\d+)')
fs = collections.Counter()
rep = 0
for line in open(PROF, encoding='utf-8', errors='replace'):
    if line.startswith('==== '):
        rep += 1
        continue
    m = PC.match(line)
    if m and rep > 2:
        a = int(m.group(1), 16)
        i = bisect.bisect_right(starts, a) - 1
        if i >= 0 and a < secs[i][1]:
            n = re.search(r'sub_([0-9A-F]{8})', secs[i][2])
            if n:
                fs[n.group(1)] += int(m.group(2))
total = sum(fs.values())

sites = collections.Counter()
kinds = collections.Counter()
weighted = 0.0
per_func = collections.Counter()
for path in sorted(glob.glob(os.path.join(GEN, '*_recomp.*.cpp'))):
    cur = None
    slots = {}   # offset -> (width, file) of bytes written in this block (by byte)
    base = {}    # register -> offset from r1 (r1 itself 0)
    for line in open(path, encoding='utf-8', errors='replace'):
        line = line.rstrip('\n')
        h = HEAD.match(line)
        if h:
            cur = h.group(1)
            slots, base = {}, {'r1': 0}
            continue
        if cur is None:
            continue
        if LABEL.match(line) or 'goto ' in line or 'return;' in line or '(ctx, base)' in line:
            slots, base = {}, {'r1': 0}      # a block border or a call: start again
            if line == '}':
                cur = None
            continue
        m = COMMENT.match(line)
        if not m:
            continue
        mn, ops = m.group(1).rstrip('.'), [o.strip() for o in m.group(2).split(',')] if m.group(2).strip() else []
        if mn == 'addi' and len(ops) == 3 and ops[1] in base:
            base[ops[0]] = base[ops[1]] + int(ops[2])
            continue
        if mn == 'mr' and len(ops) == 2 and ops[1] in base:
            base[ops[0]] = base[ops[1]]
            continue
        addr = None
        if mn in STORE_W or mn in LOAD_W:
            if len(ops) >= 2:
                d = re.match(r'^(-?\d+)\((r\d+)\)$', ops[1])
                if d and d.group(2) in base:
                    addr = base[d.group(2)] + int(d.group(1))
                elif len(ops) == 3 and ops[1] in ('r0', '0') and ops[2] in base:   # X-form: 0, rB
                    addr = base[ops[2]]
        if mn in STORE_W:
            if addr is None:
                if not (len(ops) >= 2 and re.match(r'^-?\d+\(r1\)$', ops[1] or '')):
                    pass
                continue
            w = STORE_W[mn]
            for k in range(w):
                slots[addr + k] = (w, FILE(mn))
            continue
        if mn in LOAD_W and addr is not None:
            w = LOAD_W[mn]
            a0 = addr & ~15 if mn.startswith('lvx') else addr
            covered = [slots.get(a0 + k) for k in range(w)]
            if all(covered):
                widths = {c[0] for c in covered}
                files = {c[1] for c in covered}
                if widths != {w} or files != {FILE(mn)}:
                    sites[cur] += 1
                    kinds['%s<-%s' % (mn, '+'.join(sorted('%d%s' % c for c in set(covered))))] += 1
        # any other write to a base register forgets it
        if ops and re.match(r'^r\d+$', ops[0]) and ops[0] in base and ops[0] != 'r1' and mn not in STORE_W:
            base.pop(ops[0], None)

hot = [(fs[f], n, f) for f, n in sites.items() if fs[f]]
hot.sort(reverse=True)
print('stack round trips: %d sites in %d functions; in functions with console samples: %d sites, %d functions '
      'holding %.1f %% of all mapped guest samples' % (sum(sites.values()), len(sites), sum(n for _, n, _ in hot),
                                                       len(hot), 100.0 * sum(s for s, _, _ in hot) / max(1, total)))
print('kinds:', kinds.most_common(10))
for s, n, f in hot[:15]:
    print('  sub_%s  %d samples  %d round trips' % (f, s, n))
