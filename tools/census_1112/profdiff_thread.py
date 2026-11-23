# Per-function samples per race frame for one thread, over several console runs (each with its own build's map).
#   profdiff_thread.py THREAD RUN_DIR [RUN_DIR ...] [--top N]
# A run dir holds rex_profile_*.log (the newest is used) and sasrt.map. Race reports: process CPU >= 150 % and the game
# at >= 15 fps (as the A/B summary). Keys: one per guest function (its copy, in-place symbol or generated form), else the
# host symbol without clone suffixes. Columns: samples per 100 race frames, then the last run's change against the first.
import bisect, collections, glob, os, re, sys
sys.path.insert(0, 'D:/sonic transformed/sasrt-nx/tools')
import switch_hot_functions as shf

PC = re.compile(r'^\s+[\d.]+%\s+pc image\+0x([0-9a-f]+) x(\d+)')
HEAD = re.compile(r'([\d.]+) s \| mode: \w+ \| game ([\d.]+) fps \| CPU total (\d+)%')
THREAD = re.compile(r'^-- thread \d+ "([^"]*)": CPU ([\d.]+)% \| priority (0x[0-9A-Fa-f]+), preferred core (-?\d+), mask (0x[0-9A-Fa-f]+)')


def key_of(name):
    g = re.search(r'(?:sub_|n_)([0-9A-F]{8})', name)
    if g:
        return 'guest ' + g.group(1)
    k = re.sub(r'^hot\.', '', name)
    return re.sub(r'\.(isra|constprop|part|cold|lto_priv)\.\d+', '', k)[-70:]


def load(run, thread):
    prof = sorted(glob.glob(os.path.join(run, 'rex_profile_*.log')))[-1]
    secs = sorted(shf.load_map(os.path.join(run, 'sasrt.map')))
    starts = [s[0] for s in secs]
    by = collections.Counter()
    frames = 0.0
    text = open(prof, encoding='utf-8', errors='replace').read()
    for block in text.split('\n==== ')[1:]:
        h = HEAD.match(block)
        if not h or int(h[3]) < 150 or float(h[2]) < 15:
            continue
        frames += float(h[1]) * float(h[2])
        cur = None
        for line in block.split('\n'):
            m = THREAD.match(line)
            if m:
                name = m[1]
                if name == '?' and m[5].lower() == '0x2':
                    name = 'render thread (core 1)'
                cur = name
                continue
            if cur is None or not cur.startswith(thread):
                continue
            p = PC.match(line)
            if p:
                a = int(p.group(1), 16)
                i = bisect.bisect_right(starts, a) - 1
                name = secs[i][2] if i >= 0 and a < secs[i][1] else '?'
                by[key_of(name)] += int(p.group(2))
    return {k: v * 100.0 / frames for k, v in by.items()}, frames


def main():
    args = sys.argv[1:]
    top = 30
    if '--top' in args:
        i = args.index('--top')
        top = int(args[i + 1])
        del args[i:i + 2]
    thread, runs = args[0], args[1:]
    data = [load(r, thread) for r in runs]
    tot = [sum(d.values()) for d, _ in data]
    print('%-46s' % ('samples / 100 frames, ' + thread[:20]) + ''.join('%11s' % os.path.basename(r) for r in runs) + '  last-first')
    print('%-46s' % 'total' + ''.join('%11.0f' % t for t in tot) + '  %+9.0f' % (tot[-1] - tot[0]))
    keys = set().union(*[d.keys() for d, _ in data])
    rows = sorted(keys, key=lambda k: -abs(data[-1][0].get(k, 0) - data[0][0].get(k, 0)))
    for k in rows[:top]:
        print('%-46s' % k[:46] + ''.join('%11.1f' % d.get(k, 0) for d, _ in data) + '  %+9.1f' % (data[-1][0].get(k, 0) - data[0][0].get(k, 0)))


main()
