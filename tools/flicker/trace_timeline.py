"""The '[trace]' lines of a log (sasrt_renut_diag_trace) as a timeline: one block per window dump, the threads named
by what they do (game: Swap; worker: begin-cb; render: render-frame-done), times in ms from the dump's start, and the
scene pass's camera (c133.w) beside each recording's end.
    python tools/flicker/trace_timeline.py <log> [dump index] [max lines]"""
import re
import sys

log = sys.argv[1]
want = int(sys.argv[2]) if len(sys.argv) > 2 else 0
limit = int(sys.argv[3]) if len(sys.argv) > 3 else 400
HEAD = re.compile(r'\[trace\] (\d+) events from (\d+) to (\d+) us')
EV = re.compile(r'\[trace\] (\d+) t(\d+) ([a-z0-9-]+) ?(.*)$')
dumps = []
cur = None
for line in open(log, encoding='utf-8', errors='replace'):
    m = HEAD.search(line)
    if m:
        cur = []
        dumps.append(cur)
        continue
    m = EV.search(line)
    if m and cur is not None:
        cur.append((int(m.group(1)), m.group(2), m.group(3), m.group(4).strip()))
print('%d dumps' % len(dumps))
if not dumps:
    sys.exit()
ev = sorted(dumps[want])
names = {}
for t, th, kind, rest in ev:
    if kind == 'swap':
        names.setdefault(th, 'GAME')
    elif kind == 'begin-cb':
        names.setdefault(th, 'WORKER')
    elif kind == 'render-frame-done':
        names.setdefault(th, 'RENDER')
t0 = ev[0][0]
shown = 0
for t, th, kind, rest in ev:
    if kind in ('callback-insert', 'callback-run') and shown > limit // 2:
        continue
    print('%9.2f %-7s %-18s %s' % ((t - t0) / 1000.0, names.get(th, th), kind, rest))
    shown += 1
    if shown >= limit:
        break
