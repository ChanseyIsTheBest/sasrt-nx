# sasrt-nx (2026-11-20): where the render thread (the core-1 thread, mask 0x2) spends its samples in a console profile's
# race windows (CPU total >= 200 %), by function (the NRO's map).
#   python rt_funcs.py PROFILE MAP [top]
import bisect
import collections
import re
import sys

sys.path.insert(0, r'D:/sonic transformed/sasrt-nx/tools')
import switch_hot_functions as shf  # noqa: E402
load_map = shf.load_map

prof, mp = sys.argv[1:3]
top = int(sys.argv[3]) if len(sys.argv) > 3 else 40
syms = load_map(mp)
starts = [s[0] for s in syms]


def name(a):
    i = bisect.bisect_right(starts, a) - 1
    return syms[i][2] if i >= 0 and a < syms[i][1] else '?'


funcs = collections.Counter()
total = waiting = windows = 0
keep = on = False
for l in open(prof, encoding='utf-8', errors='replace'):
    m = re.match(r'^==== [\d.]+ s \| mode: \S+ \| game ([\d.]+) fps \| CPU total (\d+)%', l)
    if m:
        keep = int(m[2]) >= 200
        windows += keep
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
    m = re.match(r'\s+(\d+) samples, (\d+)% waiting in the kernel', l)
    if m:
        total += int(m[1])
        waiting += int(m[1]) * int(m[2]) / 100.0
        continue
    m = re.match(r'\s+[\d.]+%\s+pc image\+0x([0-9a-f]+) x(\d+)', l)
    if m:
        funcs[name(int(m[1], 16))] += int(m[2])
busy = sum(funcs.values())
print('%d race windows; render thread samples %d (%.0f%% waiting in the kernel), busy pcs %d' % (
    windows, total, 100.0 * waiting / max(total, 1), busy))
for f, n in funcs.most_common(top):
    print('%5.1f%%  %s' % (100.0 * n / busy, f[:150]))
