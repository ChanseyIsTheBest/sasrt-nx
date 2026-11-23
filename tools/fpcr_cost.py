#!/usr/bin/env python3
"""sasrt-nx (2026-11-12, moonshot idea 1): console samples on flush-mode switches: samples whose PC is an `msr fpcr`
or one of the two instructions after it (the write's stall shows there), per function, from a profile and the same
build's map and ELF.  python tools/fpcr_cost.py PROFILE MAP ELF"""
import bisect, collections, re, subprocess, sys
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import switch_hot_functions as shf
PROF, MAP, ELF = sys.argv[1:4]
OBJ = 'C:/devkitPro/devkitA64/bin/aarch64-none-elf-objdump.exe'
secs = sorted(shf.load_map(MAP)); starts = [s[0] for s in secs]
PC = re.compile(r'^\s+[\d.]+%\s+pc image\+0x([0-9a-f]+) x(\d+)')
pcs = collections.Counter(); rep = 0; total = 0
for line in open(PROF, encoding='utf-8', errors='replace'):
    if line.startswith('==== '): rep += 1; continue
    m = PC.match(line)
    if m and rep > 2:
        pcs[int(m.group(1), 16)] += int(m.group(2)); total += int(m.group(2))
byf = collections.defaultdict(collections.Counter)
for a, n in pcs.items():
    i = bisect.bisect_right(starts, a) - 1
    if i >= 0 and a < secs[i][1]: byf[i][a] += n
hit = 0; per = collections.Counter(); msrs = 0
for i in sorted(byf, key=lambda k: -sum(byf[k].values()))[:500]:
    if sum(byf[i].values()) < 3: break
    s, e, name = secs[i][0], secs[i][1], secs[i][2]
    out = subprocess.run([OBJ, '-d', '--no-show-raw-insn', '--start-address=0x%x' % s, '--stop-address=0x%x' % e, ELF],
                         capture_output=True, text=True, errors='replace').stdout.splitlines()
    ins = [(int(m.group(1), 16), m.group(2)) for m in (re.match(r'^\s*([0-9a-f]+):\s+(.*)$', l) for l in out) if m]
    for k, (a, t) in enumerate(ins):
        if t.startswith('msr') and 'fpcr' in t:
            msrs += 1
            n = sum(byf[i].get(ins[q][0], 0) for q in range(k, min(k + 3, len(ins))))
            hit += n; per[name] += n
print('samples: %d; on an msr fpcr or the two instructions after it: %d (%.2f %% of all), %d such writes in the '
      'analysed functions' % (total, hit, 100.0 * hit / total, msrs))
for name, n in per.most_common(12): print('  %4d  %s' % (n, name[:100]))
