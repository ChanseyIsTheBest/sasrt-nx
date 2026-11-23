#!/usr/bin/env python3
"""Who calls a host function in a console profile: stacks whose leaf is in a matching section, by their next frames
(non-waiting busy stacks only: the 'stack' lines minus 'wait' lines are not separated, so leaf filter is used).
python callers_of.py PROFILE MAP "regex of leaf section" [depth=3] [from_report=10]"""
import bisect, collections, re, sys
sys.path.insert(0, r'D:/sonic transformed/sasrt-nx/tools')
import switch_hot_functions as shf
PROF, MAP, PAT = sys.argv[1:4]
DEPTH = int(sys.argv[4]) if len(sys.argv) > 4 else 3
FROM = int(sys.argv[5]) if len(sys.argv) > 5 else 10
secs = sorted(shf.load_map(MAP)); starts = [s[0] for s in secs]
def name(a):
    i = bisect.bisect_right(starts, a) - 1
    if i >= 0 and a < secs[i][1]:
        return secs[i][2]
    return '?%x' % a
leafre = re.compile(PAT)
THREAD = re.compile(r'^-- thread (\d+) "(.*?)"')
SAMPLES = re.compile(r'^\s+(\d+) samples')
STACK = re.compile(r'^\s+([\d.]+)%\s+stack (.*)$')
rep = 0; thread = ''; n = 0
agg = collections.Counter(); bythread = collections.Counter(); leafs = collections.Counter()
for line in open(PROF, encoding='utf-8', errors='replace'):
    if line.startswith('==== '):
        rep += 1; continue
    if rep <= FROM: continue
    m = THREAD.match(line)
    if m: thread = m.group(2); continue
    m = SAMPLES.match(line)
    if m: n = int(m.group(1)); continue
    m = STACK.match(line)
    if m:
        frames = [int(x.split('+0x')[1], 16) for x in m.group(2).split(' <- ') if x.startswith('image+0x')]
        if not frames: continue
        leaf = name(frames[0])
        if not leafre.search(leaf): continue
        cnt = float(m.group(1)) * n / 100.0
        key = ' <- '.join(name(f)[:70] for f in frames[1:1 + DEPTH])
        agg[(leaf[:40], key)] += cnt; bythread[thread] += cnt; leafs[leaf[:60]] += cnt
print('leaves:'); [print('  %7.1f  %s' % (c, l)) for l, c in leafs.most_common(10)]
print('threads:'); [print('  %7.1f  %s' % (c, t)) for t, c in bythread.most_common(10)]
print('callers:')
for (l, k), c in agg.most_common(30):
    print('  %7.1f  %s <- %s' % (c, l, k))
