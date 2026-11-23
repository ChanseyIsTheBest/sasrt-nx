# sasrt-nx (2026-11-20): the render thread's (mask 0x2) samples in one function, by instruction, with its disassembly
# (no line tables needed): the hot stretches of a function such as FastDrawLocked.
#   python rt_pcs.py PROFILE ELF MAP FUNC_SUBSTRING [stretches] [context]
import bisect
import collections
import re
import subprocess
import sys

sys.path.insert(0, r'D:/sonic transformed/sasrt-nx/tools')
import switch_hot_functions as shf  # noqa: E402

prof, elf, mp, want = sys.argv[1:5]
stretches = int(sys.argv[5]) if len(sys.argv) > 5 else 12
ctx = int(sys.argv[6]) if len(sys.argv) > 6 else 6
OBJDUMP = r'C:/devkitPro/devkitA64/bin/aarch64-none-elf-objdump.exe'
syms = shf.load_map(mp)
cands = [s for s in syms if want in s[2]]
if not cands:
    sys.exit('no function matches %r' % want)
cands.sort(key=lambda s: s[1] - s[0], reverse=True)
start, end, name = cands[0][:3]
print('%s: %08x-%08x (%d bytes)' % (name[:120], start, end, end - start))

pcs = collections.Counter()
busy = 0
keep = on = False
for l in open(prof, encoding='utf-8', errors='replace'):
    m = re.match(r'^==== [\d.]+ s \| mode: \S+ \| game ([\d.]+) fps \| CPU total (\d+)%', l)
    if m:
        keep = int(m[2]) >= 200
        on = False
        continue
    if not keep:
        continue
    m = re.match(r'^-- thread \d+ "([^"]*)": CPU [\d.]+% \| priority \S+, preferred core -?\d+, mask (0x[0-9a-f]+)', l)
    if m:
        on = m[2] == '0x2'
        continue
    if not on:
        continue
    m = re.match(r'\s+[\d.]+%\s+pc image\+0x([0-9a-f]+) x(\d+)', l)
    if m:
        a, n = int(m[1], 16), int(m[2])
        busy += n
        if start <= a < end:
            pcs[a] += n
inside = sum(pcs.values())
print('render thread busy samples %d; in the function %d (%.1f%%)' % (busy, inside, 100.0 * inside / max(busy, 1)))
dis = subprocess.run([OBJDUMP, '-d', '--no-show-raw-insn', '--start-address=0x%x' % start, '--stop-address=0x%x' % end,
                      elf], capture_output=True, text=True).stdout.split('\n')
insns = []
for l in dis:
    m = re.match(r'\s+([0-9a-f]+):\s+(.*)$', l)
    if m:
        insns.append((int(m[1], 16), m[2].strip()))
index = {a: i for i, (a, _) in enumerate(insns)}
# stretches: windows of 2*ctx+1 instructions around the hottest, taken greedily
taken = set()
rows = []
for a, n in pcs.most_common():
    i = index.get(a)
    if i is None or i in taken:
        continue
    lo, hi = max(0, i - ctx), min(len(insns), i + ctx + 1)
    total = sum(pcs.get(insns[j][0], 0) for j in range(lo, hi) if j not in taken)
    rows.append((total, lo, hi))
    taken.update(range(lo, hi))
    if len(rows) >= stretches:
        break
for total, lo, hi in sorted(rows, reverse=True):
    print('\n--- %d samples (%.2f%% of the thread) at +0x%x' % (total, 100.0 * total / max(busy, 1), insns[lo][0] - start))
    for j in range(lo, hi):
        a, t = insns[j]
        n = pcs.get(a, 0)
        print('%6s  %08x  +%-5x %s' % (n or '', a, a - start, t[:110]))
