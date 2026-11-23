# sasrt-nx (2026-11-20): two runs compared by their 10 s "[renut] 10.x s:" lines in the race (draws a frame >= MIN):
# fps, render thread busy ms a frame, draws a frame, render thread us a draw, GPU ms a frame.
#   python cmp_runs.py LOG_A LOG_B [min_draws]
import re
import statistics
import sys

LINE = re.compile(r'\[renut\] 10\.\d s: (\d+) game frames \(([\d.]+) fps\), render thread busy ([\d.]+) ms a frame '
                  r'\(\d+ frames\), GPU ([\d.]+) ms a frame \(\d+ frames\); (\d+) draws')
min_draws = float(sys.argv[3]) if len(sys.argv) > 3 else 2000


def rows(log):
    out = []
    for line in open(log, encoding='utf-8', errors='replace'):
        m = LINE.search(line)
        if not m:
            continue
        frames, fps, rt, gpu, draws = int(m[1]), float(m[2]), float(m[3]), float(m[4]), int(m[5])
        dpf = draws / max(frames, 1)
        if dpf >= min_draws:
            out.append((fps, rt, dpf, 1000.0 * rt / dpf, gpu))
    return out


res = {}
for log in sys.argv[1:3]:
    r = rows(log)
    res[log] = r
    if not r:
        print(log, 'no race windows')
        continue
    cols = list(zip(*r))
    print('%-60s %d windows: fps %.2f  render %.2f ms  draws %.0f  %.2f us a draw  GPU %.2f ms' % (
        log[-60:], len(r), *(statistics.mean(c) for c in cols)))
    print('   us a draw by window: ' + ' '.join('%.2f' % x for x in cols[3]))
a, b = (res[l] for l in sys.argv[1:3])
if a and b:
    ua, ub = statistics.mean(x[3] for x in a), statistics.mean(x[3] for x in b)
    ra, rb = statistics.mean(x[1] for x in a), statistics.mean(x[1] for x in b)
    print('B vs A: us a draw %+.1f %%, render thread ms a frame %+.1f %%' % (100 * (ub - ua) / ua, 100 * (rb - ra) / ra))
