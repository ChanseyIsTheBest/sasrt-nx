#!/usr/bin/env python3
"""sasrt-nx (2026-11-11, machine-copy idea 46, part 1): the guest globals the localized copies load at a known address
(a D-form load whose base register a `lis` / `addi` line set: the constants tools/ro_constants.py follows) that lie in
the image's writable data. tools/ro_constants.py folds such loads when the data is read-only; these could be frozen
(part 2: a copy with the value built in, behind an entry check) if the game writes them once. With --write this writes
the census list app/generated/hot/frozen_census.inc ({address, size} per global), which the console's census
(app/src/cpu/banjo_hot_guest.cpp, sasrt_cpu_frozen_census) samples during a race. Every running form f_* of a header
is read (each closure member has its own, between the original statements' forms o_*); a register is forgotten at
any write of it, at a call and at a brace, as tools/ro_constants.py does on a straight line.

  python tools/frozen_census.py [--write]      (post_codegen.py runs it with --write after the copies are made)
"""
import collections
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import ro_constants as rc  # noqa: E402

SET = re.compile(r'^\t(l{0,2}_?r\d+)\.s64 = (-?\d+);$')
ADD = re.compile(r'^\t(l{0,2}_?r\d+)\.s64 = (l{0,2}_?r\d+)\.s64 \+ (-?\d+);$')
LOAD = re.compile(r'REX_LOAD_D_(U8|U16|U32|U64|F32|F64)\((l{0,2}_?r\d+)\.u32, (-?\d+)\)')
ORI = re.compile(r'^\t(l{0,2}_?r\d+)\.u64 = (l{0,2}_?r\d+)\.u64 \| (\d+);$')
WRITE = re.compile(r'\b(l{0,2}_?r\d+)(?:\.[us]\d+)? = ')
FORM = re.compile(r'^(?:\[\[[^\]]*\]\] )?(?:static )?(?:inline )?void ([fo])_\w+\(PPCContext& __restrict ctx.*\) \{$')
SIZE = {'U8': 1, 'U16': 2, 'U32': 4, 'U64': 8, 'F32': 4, 'F64': 8}


def main():
    image = open(os.path.join(ROOT, 'out', 'default_image.bin'), 'rb').read()
    ranges, base = rc.read_only_ranges(image)
    pch = open(os.path.join(ROOT, 'app', 'generated', 'default', 'sasrt_pch.h'), encoding='utf-8').read()
    code_lo = int(re.search(r'#define REX_CODE_BASE (0x[0-9A-Fa-f]+)', pch).group(1), 16)
    code_hi = code_lo + int(re.search(r'#define REX_CODE_SIZE (0x[0-9A-Fa-f]+)', pch).group(1), 16)
    samples = {}
    for line in open(os.path.join(ROOT, 'app', 'src', 'cpu', 'hot', 'localized_bulk.txt'), errors='replace'):
        m = re.match(r'([0-9A-F]{8}) (\d+) console samples', line)
        if m:
            samples[m.group(1)] = int(m.group(2))
    kind, per, addrs, sizes = collections.Counter(), collections.Counter(), collections.Counter(), {}
    for path in glob.glob(os.path.join(ROOT, 'app', 'generated', 'hot', 'n_*.h')):
        root = re.search(r'n_([0-9A-F]{8})', path).group(1)
        lines = open(path, errors='replace').read().splitlines()
        known = {}
        form = None  # 'f' inside a running form, 'o' inside an original statements' form (batch 2's audit, finding 9)
        for line in lines:
            m = FORM.match(line)
            if m:
                form = m.group(1)
                known.clear()
                continue
            if line == '}':
                form = None
            if form != 'f' or not line.startswith('\t'):
                known.clear()  # a label, a function's edge, or not a running form: a straight line ends
                continue
            if '{' in line or '}' in line or '(ctx, base' in line or 'REX_CALL' in line or 'REX_LOOP_' in line \
                    or 'REX_LR_' in line or line.startswith('\t\t'):
                known.clear()  # finding 10: structured lines, calls and macro writes forget everything
            m = SET.match(line)
            if m:
                known[m.group(1)] = int(m.group(2)) & 0xFFFFFFFF
                continue
            m = ADD.match(line)
            if m and m.group(2) in known:
                known[m.group(1)] = (known[m.group(2)] + int(m.group(3))) & 0xFFFFFFFF
                continue
            m = ORI.match(line)
            if m and m.group(2) in known:
                known[m.group(1)] = (known[m.group(2)] | int(m.group(3))) & 0xFFFFFFFF
                continue
            for t, r, off in LOAD.findall(line):
                if r not in known:
                    continue
                a = (known[r] + int(off)) & 0xFFFFFFFF
                inside = base <= a < base + len(image)
                if inside and any(s <= a < e for s, e in ranges):
                    kind['read-only'] += 1
                elif code_lo <= a < code_hi:
                    kind['code'] += 1
                elif inside:
                    kind['writable image data'] += 1
                    per[root] += 1
                    addrs[a] += 1
                    sizes[a] = max(sizes.get(a, 0), SIZE[t])
                else:
                    kind['outside the image'] += 1
            for r in WRITE.findall(line):
                known.pop(r, None)
    print('frozen_census: known-address loads in the copies:', dict(kind))
    print('frozen_census: writable data: %d loads in %d copies (%d console samples), %d globals' % (
        sum(per.values()), len(per), sum(samples.get(r, 0) for r in per), len(addrs)))
    if '--write' not in sys.argv:
        return
    out = os.path.join(ROOT, 'app', 'generated', 'hot', 'frozen_census.inc')
    text = ('// GENERATED by tools/frozen_census.py (machine-copy idea 46): the writable guest globals the copies load at a\n'
            '// known address, {address, size}; app/src/cpu/banjo_frozen_census.cpp samples them (sasrt_cpu_frozen_census).\n'
            + ''.join('{0x%08Xu, %du},\n' % (a, sizes[a]) for a in sorted(addrs)))
    old = open(out, encoding='utf-8').read() if os.path.exists(out) else None
    if old != text:
        with open(out, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
    print('frozen_census: %d globals in %s%s' % (len(addrs), out, ' (unchanged)' if old == text else ''))


if __name__ == '__main__':
    main()
