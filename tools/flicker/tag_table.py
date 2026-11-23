"""Per mask pass (its first shading draw per frame label): the draw's own replay tag (recording, swap counts at Begin /
End / submission) beside the tags of the scene depth (t0) and the atlas (t2) it samples; the differences in swaps
say which recording lags which. Also the casters' own tags per frame.
    python tag_table.py <log>"""
import re
import sys

log = sys.argv[1]
OWN = re.compile(r'light volume: frame (\d+) draw \d+ \(\w+\) vs [0-9A-F]{16} ps ([0-9A-F]{4})[0-9A-F]{12} .*?own tag buf ([0-9A-F]+) rec (\d+) swaps b(\d+) e(\d+) s(\d+):(.*)$')
SLOT = re.compile(r'^t(\d) va ')
HOST = re.compile(r'host ([0-9A-F]+) ')
TAG = re.compile(r'tag buf ([0-9A-F]+) rec (\d+) swaps b(\d+) e(\d+) s(\d+)')
CAST = re.compile(r'shadow caster: frame (\d+) draw \d+ vs ([0-9A-F]{4}).*?own tag buf ([0-9A-F]+) rec (\d+) swaps b(\d+) e(\d+) s(\d+)')
seen = set()
casters = {}
print('frame  mask draw: own rec b/e/s | depth t0: rec b/e/s | atlas t2: rec b/e/s | mask.rec-atlas.rec | casters: rec b/e/s')
for line in open(log, encoding='utf-8', errors='replace'):
    m = CAST.search(line)
    if m:
        casters.setdefault(int(m.group(1)), (m.group(4), m.group(5), m.group(6), m.group(7)))
        continue
    m = OWN.search(line)
    if not m:
        continue
    fr, ps = int(m.group(1)), m.group(2)
    if fr in seen or ps == '0000':  # the first draw with a pixel shader: the shading draws bind the textures
        continue
    seen.add(fr)
    own = (m.group(4), m.group(5), m.group(6), m.group(7))
    tex = {}
    for piece in m.group(8).split(' | '):
        piece = piece.strip()
        sl = SLOT.match(piece)
        if not sl:
            continue
        h = HOST.search(piece)
        t = TAG.search(piece)
        tex[int(sl.group(1))] = (h.group(1) if h else '?', t.groups() if t else None)
    def fmt(k):
        if k not in tex:
            return '-'
        h, t = tex[k]
        return '%s rec %s %s/%s/%s' % (h, t[1], t[2], t[3], t[4]) if t else '%s untagged' % h
    delta = ''
    if 2 in tex and tex[2][1]:
        delta = str(int(own[0]) - int(tex[2][1][1]))
    c = casters.get(fr)
    print('f%d  ps %s own rec %s %s/%s/%s | %s | %s | %s | %s' % (
        fr, ps, own[0], own[1], own[2], own[3], fmt(0), fmt(2), delta, ('rec %s %s/%s/%s' % c) if c else '-'))
