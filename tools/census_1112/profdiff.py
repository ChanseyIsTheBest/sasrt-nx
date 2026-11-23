# Per-function sample difference between two console profiles (each with its own build's map).
#   profdiff.py PROF_A MAP_A PROF_B MAP_B [N]
import bisect, collections, re, sys
sys.path.insert(0, 'D:/sonic transformed/sasrt-nx/tools')
import switch_hot_functions as shf

AGG = False
PC = re.compile(r'^\s+[\d.]+%\s+pc image\+0x([0-9a-f]+) x(\d+)')


def load(prof, mp):
    secs = sorted(shf.load_map(mp))
    starts = [s[0] for s in secs]
    by = collections.Counter()
    tot = 0
    rep = 0
    for line in open(prof, encoding='utf-8', errors='replace'):
        if line.startswith('==== '):
            rep += 1
            continue
        m = PC.match(line)
        if m and rep > 2:
            a = int(m.group(1), 16)
            n = int(m.group(2))
            tot += n
            i = bisect.bisect_right(starts, a) - 1
            name = secs[i][2] if i >= 0 and a < secs[i][1] else '?'
            # one key per guest function: the copy, its in-place symbol or the generated one
            g = re.search(r'(?:sub_|n_)([0-9A-F]{8})', name)
            if g:
                key = 'guest ' + g.group(1) if not AGG else 'GUEST (all)'
            else:
                key = re.sub(r'^hot\.|\.(isra|constprop|part|cold|lto_priv)\.\d+', '', name)
                key = re.sub(r'\.(isra|constprop|part|cold|lto_priv)\.\d+', '', key)[-70:]
                if AGG:
                    key = 'HOST (all)'
            by[key] += n
    return by, tot


a, ta = load(sys.argv[1], sys.argv[2])
b, tb = load(sys.argv[3], sys.argv[4])
N = int(sys.argv[5]) if len(sys.argv) > 5 else 30
print('samples: A %d, B %d' % (ta, tb))
keys = set(a) | set(b)
# per-sample-share difference, scaled to B's total
rows = sorted(((b[k] - a[k] * tb / ta, k) for k in keys), reverse=True)
print('B gained most:')
for d, k in rows[:N]:
    print('  %+7.1f  %5d -> %5d  %s' % (d, a[k], b[k], k))
print('B lost most:')
for d, k in rows[-12:]:
    print('  %+7.1f  %5d -> %5d  %s' % (d, a[k], b[k], k))
