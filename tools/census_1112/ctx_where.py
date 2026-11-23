# sasrt-nx (2026-11-12, calling-convention stage 2 sizing): where the ctx loads/stores of the console profile sit:
# right before a call (hand-over), right after one (reload), at entry, before a return (write-back) or in the body;
# and for calls, what kind of callee (a closed copy f_/n_, a real guest call sub_/__imp__, a host function).
import sys, re, bisect, collections, subprocess
sys.path.insert(0, 'D:/sonic transformed/sasrt-nx/tools')
import switch_hot_functions as shf
PROF, MAP, ELF = sys.argv[1:4]
FROM = 2
OBJ = 'C:/devkitPro/devkitA64/bin/aarch64-none-elf-objdump.exe'
secs = sorted(shf.load_map(MAP)); starts = [s[0] for s in secs]
guest = re.compile(r'(^|\.)sub_[0-9A-F]{8}$|_ZN5banjo3hot10n_|_ZN5sasrt3hot10n_|_ZN5banjo4hand')
PC = re.compile(r'^\s+[\d.]+%\s+pc image\+0x([0-9a-f]+) x(\d+)')
pcs = collections.Counter(); rep = 0; total = 0
for line in open(PROF, encoding='utf-8', errors='replace'):
    if line.startswith('==== '): rep += 1; continue
    m = PC.match(line)
    if m and rep > FROM:
        pcs[int(m.group(1), 16)] += int(m.group(2)); total += int(m.group(2))
byfunc = collections.defaultdict(collections.Counter)
for a, n in pcs.items():
    i = bisect.bisect_right(starts, a) - 1
    if i >= 0 and a < secs[i][1] and guest.search(secs[i][2]):
        byfunc[i][a] += n
INS = re.compile(r'^\s*([0-9a-f]+):\s+(\S+)\s*(.*)$')
MEM = re.compile(r'^(ldr|str|ldp|stp|ldur|stur|ldrb|strb|ldrh|strh|ldrsw|ldrsb|ldrsh|ldnp|stnp)$')
MOVX0 = re.compile(r'^mov$')
CT = re.compile(r'^(bl|blr|br|ret|b)$')
W = 40
where = collections.Counter(); callee_kind = collections.Counter(); per_func = collections.defaultdict(collections.Counter)
regs_by_where = collections.defaultdict(collections.Counter)
ctx_n = 0
order = sorted(byfunc, key=lambda i: -sum(byfunc[i].values()))


def kind_of(target):
    if re.search(r'f_[0-9A-F]{8}|n_[0-9A-F]{8}|_ZN5banjo3hot|_ZN5sasrt3hot', target):
        return 'copy'
    if re.search(r'sub_[0-9A-F]{8}', target):
        return 'guest'
    return 'host'


for i in order:
    n_f = sum(byfunc[i].values())
    if n_f < 3: break
    start, end, name = secs[i][0], secs[i][1], secs[i][2]
    out = subprocess.run([OBJ, '-d', '--no-show-raw-insn', '--start-address=0x%x' % start, '--stop-address=0x%x' % end, ELF],
                         capture_output=True, text=True, errors='replace').stdout.splitlines()
    ins = []
    for l in out:
        m = INS.match(l)
        if m and not m.group(2).endswith('>:'):
            ins.append((int(m.group(1), 16), m.group(2), m.group(3)))
    ctxregs = {'x0'}
    for a, mn, ops in ins[:80]:
        if mn == 'mov' and re.match(r'^(x\d+), x0\s*$', ops):
            ctxregs.add(ops.split(',')[0])
    first_bl = next((k for k, (a, mn, ops) in enumerate(ins) if mn in ('bl', 'blr')), len(ins))
    # x0 holds ctx from the entry until the first instruction that writes x0 / w0 or a call (layout order): after
    # that an access through x0 is guest memory or anything else. The prologue's copies (callee-saved) stay.
    x0_end = len(ins)
    for k, (a, mn, ops) in enumerate(ins):
        if mn in ('bl', 'blr') or (re.match(r'^(x0|w0)', ops) and not mn.startswith(('st', 'cmp', 'tst', 'cb', 'tb', 'ccmp', 'b.', 'br', 'ret', 'prfm'))):
            x0_end = k
            break
    for k, (a, mn, ops) in enumerate(ins):
        n = byfunc[i].get(a, 0)
        if not n or not MEM.match(mn):
            continue
        bm = re.search(r'\[(x\d+|sp)(?:, #(-?\d+|0x[0-9a-f]+))?\]', ops)
        if not (bm and bm.group(1) in ctxregs):
            continue
        if bm.group(1) == 'x0' and k > x0_end:
            continue
        ctx_n += n
        off = int(bm.group(2), 0) if bm.group(2) else 0
        reg = ('r' if off < 256 else 'spr' if off < 336 else 'f' if off < 592 else 'v' if off < 2640 else 'o')
        nxt = next(((j, ins[j]) for j in range(k + 1, min(len(ins), k + W)) if CT.match(ins[j][1])), None)
        prv = next(((j, ins[j]) for j in range(k - 1, max(-1, k - W), -1) if CT.match(ins[j][1])), None)
        st = mn.startswith('st')
        if nxt and nxt[1][1] in ('bl', 'blr') and st:
            w = 'store before call'
            callee_kind[('before', kind_of(nxt[1][2]) if nxt[1][1] == 'bl' else 'indirect-host')] += n
        elif prv and prv[1][1] in ('bl', 'blr') and not st:
            w = 'load after call'
            callee_kind[('after', kind_of(prv[1][2]) if prv[1][1] == 'bl' else 'indirect-host')] += n
        elif k < first_bl and k < 96 and not st:
            w = 'load at entry'
        elif nxt and nxt[1][1] == 'ret' and st:
            w = 'store at exit'
        elif nxt and nxt[1][1] == 'b' and st and kind_of(nxt[1][2]) != 'host':
            w = 'store before tail call'
        else:
            w = ('store' if st else 'load') + ' in body'
        where[w] += n
        regs_by_where[w][reg] += n
        per_func[name][w] += n
print('ctx samples %d of %d (%.1f %%)' % (ctx_n, total, 100.0 * ctx_n / total))
for w, n in where.most_common():
    print('  %-24s %5d  %4.1f %%   %s' % (w, n, 100.0 * n / ctx_n, dict(regs_by_where[w])))
print('callee kinds:', sorted(callee_kind.items(), key=lambda x: -x[1]))
for name, c in sorted(per_func.items(), key=lambda x: -sum(x[1].values()))[:15]:
    print('  %4d %-60s %s' % (sum(c.values()), name[-60:], dict(c.most_common(4))))
