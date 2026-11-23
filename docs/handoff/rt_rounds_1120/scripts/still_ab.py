# sasrt-nx (2026-11-20): an in-run A/B's pairs by target: render thread us a draw on vs off, only pairs in the race
# (both halves at least MIN_DRAWS draws a frame) whose draw counts are within TOL of each other; the mean, the spread
# and each pair's difference.
#   python still_ab.py LOG[,LOG...] [min_draws] [tol]
import collections
import re
import statistics
import sys

logs = sys.argv[1].split(',')
min_draws = float(sys.argv[2]) if len(sys.argv) > 2 else 2000
tol = float(sys.argv[3]) if len(sys.argv) > 3 else 0.10
HALF = r'([\d.]+) fps, render thread ([\d.]+) ms a frame, GPU ([\d.]+) ms a frame \((\d+) s\)(?:, CPU ([\d.]+) ms a frame \(all threads\))?, (\d+) draws a frame, render thread ([\d.]+) us a draw'
LINE = re.compile(r'\[renut A/B\] (.*?) \(target (\d+)[^)]*\): on ' + HALF + '; off ' + HALF)
pairs = collections.defaultdict(list)
names = {}
for log in logs:
    for line in open(log, encoding='utf-8', errors='replace'):
        m = LINE.search(line)
        if not m:
            continue
        t = int(m[2])
        names[t] = m[1][:70]
        on_d, on_us, off_d, off_us = float(m[8]), float(m[9]), float(m[15]), float(m[16])
        on_cpu, off_cpu = m[7], m[14]
        if min(on_d, off_d) < min_draws or abs(on_d - off_d) > tol * max(on_d, off_d):
            continue
        pairs[t].append((100.0 * (on_us - off_us) / off_us, on_d, off_d,
                         (100.0 * (float(on_cpu) - float(off_cpu)) / float(off_cpu)) if on_cpu and off_cpu else None))
for t in sorted(pairs):
    d = [p[0] for p in pairs[t]]
    mean = statistics.mean(d)
    sd = statistics.stdev(d) if len(d) > 1 else float('nan')
    se = sd / len(d) ** 0.5 if len(d) > 1 else float('nan')
    cpu = [p[3] for p in pairs[t] if p[3] is not None]
    print('%3d  %-62s n=%d  mean %+5.2f %%  (se %4.2f)  pairs: %s%s' % (
        t, names[t], len(d), mean, se, ' '.join('%+.1f' % x for x in d),
        ('  | CPU all threads %+.1f %%' % statistics.mean(cpu)) if cpu else ''))
