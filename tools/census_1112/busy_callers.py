import bisect, collections, re, sys
sys.path.insert(0, r'D:/sonic transformed/sasrt-nx/tools')
import switch_hot_functions as shf
PROF, MAP, PAT = sys.argv[1:4]
DEPTH = int(sys.argv[4]) if len(sys.argv) > 4 else 3
secs = sorted(shf.load_map(MAP)); starts = [s[0] for s in secs]
def name(a):
    i = bisect.bisect_right(starts, a) - 1
    return secs[i][2] if i >= 0 and a < secs[i][1] else '?%x' % a
leafre = re.compile(PAT)
THREAD = re.compile(r'^-- thread (\d+) "(.*?)"')
SAMPLES = re.compile(r'^\s+(\d+) samples')
LINE = re.compile(r'^\s+([\d.]+)%\s+(stack|wait) (.*)$')
rep = 0; thread = ''; n = 0
agg = collections.Counter(); per_thread = collections.Counter()
cur = {}
def flush():
    for k5, (st, wt, full) in cur.items():
        busy = st - wt
        if busy <= 0.01: continue
        frames = full
        leaf = name(frames[0])
        if not leafre.search(leaf): continue
        key = leaf[:30] + ' <- ' + ' <- '.join(name(f)[:60] for f in frames[1:1 + DEPTH])
        agg[key] += busy; per_thread[thread] += busy
for line in open(PROF, encoding='utf-8', errors='replace'):
    if line.startswith('==== '):
        flush(); cur = {}; rep += 1; continue
    if rep <= 10: continue
    m = THREAD.match(line)
    if m:
        flush(); cur = {}; thread = m.group(2); continue
    m = SAMPLES.match(line)
    if m: n = int(m.group(1)); continue
    m = LINE.match(line)
    if m:
        frames = [int(x.split('+0x')[1], 16) for x in m.group(3).split(' <- ') if x.startswith('image+0x')]
        if not frames: continue
        k5 = tuple(frames[:5]); cnt = float(m.group(1)) * n / 100.0
        st, wt, full = cur.get(k5, (0.0, 0.0, frames))
        if m.group(2) == 'stack': st += cnt; full = frames if len(frames) > len(full) else full
        else: wt += cnt
        cur[k5] = (st, wt, full)
flush()
print('threads:'); [print('  %7.1f  %s' % (c, t)) for t, c in per_thread.most_common(8)]
for k, c in agg.most_common(25): print('  %7.1f  %s' % (c, k))
