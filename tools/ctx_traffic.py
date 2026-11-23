# sasrt-nx (2026-11-12): what share of the guest code's console samples are loads/stores through the ctx pointer
# (the calling-convention moonshot's ceiling). Guest code = sections named sub_XXXXXXXX (in-place copies, generated code)
# or the copies' n_... forms and hand natives. ctx register per function: x0 at entry and any register a prologue
# `mov xN, x0` copies it to (first 60 instructions).
import sys, re, bisect, collections, subprocess
sys.path.insert(0, 'D:/sonic transformed/sasrt-nx/tools')
import switch_hot_functions as shf
PROF, MAP, ELF = sys.argv[1:4]
FROM = int(sys.argv[4]) if len(sys.argv) > 4 else 2
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
gtot = sum(sum(c.values()) for c in byfunc.values())
print('samples: all %d, guest code %d (%.1f %%), guest functions %d' % (total, gtot, 100.0 * gtot / total, len(byfunc)))
MEM = re.compile(r'^\s*([0-9a-f]+):\s+(ldr|str|ldp|stp|ldur|stur|ldrb|strb|ldrh|strh|ldrsw|ldrsb|ldrsh|ldnp|stnp)\s+(.*)$')
MOVX0 = re.compile(r'^\s*[0-9a-f]+:\s+mov\s+(x\d+), x0\s*$')
CLS = collections.Counter(); PERF = collections.Counter(); VRC = collections.Counter(); GRC = collections.Counter(); ctx_n = 0; mem_n = 0; done = 0; covered = 0
order = sorted(byfunc, key=lambda i: -sum(byfunc[i].values()))
for i in order:
    n_f = sum(byfunc[i].values())
    if n_f < 3: break
    start, end, name = secs[i][0], secs[i][1], secs[i][2]
    out = subprocess.run([OBJ, '-d', '--no-show-raw-insn', '--start-address=0x%x' % start, '--stop-address=0x%x' % end, ELF],
                         capture_output=True, text=True, errors='replace').stdout.splitlines()
    ctxregs = {'x0'}
    for l in out[:80]:
        m = MOVX0.match(l)
        if m: ctxregs.add(m.group(1))
    # sasrt-nx (2026-11-12, fix): x0 holds ctx only until the first instruction (in layout order) that writes x0 / w0
    # or a call; after that an access through x0 is guest memory or anything else (the first version counted those:
    # 9.7 % of SASRT's process samples instead of 7.9 %). The prologue's copies (callee-saved registers) stay.
    x0_live = True
    INS = re.compile(r'^\s*[0-9a-f]+:\s+(\S+)\s*(.*)$')
    for l in out:
        im = INS.match(l)
        m = MEM.match(l)
        if m:
            a = int(m.group(1), 16); n = byfunc[i].get(a, 0)
            ops = m.group(3)
            bm = re.search(r'\[(x\d+|sp)(?:, #(-?\d+|0x[0-9a-f]+))?\]', ops)
        if im and x0_live:
            mn_, ops_ = im.group(1), im.group(2)
            if mn_ in ('bl', 'blr') or (re.match(r'^(x0|w0)', ops_) and not mn_.startswith(
                    ('st', 'cmp', 'tst', 'cb', 'tb', 'ccmp', 'b.', 'br', 'ret', 'prfm'))):
                x0_live_next = False
            else:
                x0_live_next = True
        else:
            x0_live_next = x0_live
        if not m:
            x0_live = x0_live_next
            continue
        here_x0 = x0_live
        x0_live = x0_live_next
        if not n: continue
        mem_n += n
        if bm and bm.group(1) in ctxregs and (bm.group(1) != 'x0' or here_x0):
            ctx_n += n
            off = int(bm.group(2), 0) if bm.group(2) else 0
            kind = ('GPR' if off < 256 else 'lr/ctr/xer/msr' if off < 292 else 'CR' if off < 324 else 'fpscr/vscr' if off < 336
                    else 'FPR' if off < 592 else 'VR' if off < 2640 else 'other')
            st = m.group(2).startswith('st')
            CLS[(kind, 'store' if st else 'load')] += n
            PERF[name] += n
            if kind == 'VR':
                v = (off - 592) // 16
                vc = 'v0-1' if v < 2 else 'v2-13 args' if v < 14 else 'v14-31' if v < 32 else 'v32-63' if v < 64 else 'v64-127'
                VRC[(vc, 'store' if st else 'load')] += n
            if kind == 'GPR':
                order_ = ['r3','r0','r1','r2'] + ['r%d' % k for k in range(4, 32)]
                r = order_[off // 8] if off // 8 < 32 else '?'
                k_ = int(r[1:])
                gc = 'r3-r10 args' if 3 <= k_ <= 10 else 'r0/r11/r12' if k_ in (0, 11, 12) else 'r1/r2/r13' if k_ in (1, 2, 13) else 'r14-r31'
                GRC[(gc, 'store' if st else 'load')] += n
    covered += n_f; done += 1
print('analysed %d functions holding %d guest samples (%.1f %% of guest)' % (done, covered, 100.0 * covered / gtot))
print('samples on loads/stores: %d (%.1f %% of analysed); through ctx: %d (%.1f %% of analysed guest samples)' % (
    mem_n, 100.0 * mem_n / covered, ctx_n, 100.0 * ctx_n / covered))
for (k, d), n in sorted(CLS.items(), key=lambda x: -x[1]):
    print('  %-16s %-5s %5d  %.1f %% of ctx samples' % (k, d, n, 100.0 * n / max(1, ctx_n)))
print('VR by register:', sorted(VRC.items(), key=lambda x: -x[1]))
print('GPR by register:', sorted(GRC.items(), key=lambda x: -x[1]))
for name, n in PERF.most_common(12):
    print('  %5d  %s' % (n, name[:110]))
