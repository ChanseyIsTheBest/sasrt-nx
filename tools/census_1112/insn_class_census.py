#!/usr/bin/env python3
"""Samples by instruction class (the sampled instruction itself, plus a skid window for stalling ones), guest vs host,
from a console profile + the same build's map and ELF.  python insn_class_census.py PROFILE MAP ELF [top=600]"""
import bisect, collections, re, subprocess, sys, os
sys.path.insert(0, r'D:/sonic transformed/sasrt-nx/tools')
import switch_hot_functions as shf
PROF, MAP, ELF = sys.argv[1:4]
TOP = int(sys.argv[4]) if len(sys.argv) > 4 else 600
OBJ = 'C:/devkitPro/devkitA64/bin/aarch64-none-elf-objdump.exe'
secs = sorted(shf.load_map(MAP)); starts = [s[0] for s in secs]
PC = re.compile(r'^\s+[\d.]+%\s+pc image\+0x([0-9a-f]+) x(\d+)')
pcs = collections.Counter(); rep = 0; total = 0
for line in open(PROF, encoding='utf-8', errors='replace'):
    if line.startswith('==== '):
        rep += 1
        continue
    m = PC.match(line)
    if m and rep > 9:
        pcs[int(m.group(1), 16)] += int(m.group(2)); total += int(m.group(2))
byf = collections.defaultdict(collections.Counter)
for a, n in pcs.items():
    i = bisect.bisect_right(starts, a) - 1
    if i >= 0 and a < secs[i][1]:
        byf[i][a] += n


def is_guest(name):
    return (('banjo3hot' in name or 'sasrt3hot' in name or re.search(r'sub_[0-9A-F]{8}', name) is not None)
            and 'renut' not in name)


ATOM = {'ldaxr', 'stlxr', 'ldxr', 'stxr', 'ldar', 'stlr', 'ldaxrb', 'stlxrb', 'ldaxrh', 'stlxrh', 'ldxrb', 'stxrb',
        'ldaxp', 'stlxp', 'dmb', 'dsb', 'isb', 'clrex'}
MOVS = {'dup', 'ins', 'umov', 'mov', 'fmov', 'ext', 'tbl', 'tbx', 'zip1', 'zip2', 'uzp1', 'uzp2', 'trn1', 'trn2', 'xtn',
        'movi', 'movk', 'movz', 'adrp', 'adr', 'smov'}
cls = {'guest': collections.Counter(), 'host': collections.Counter()}
skid = collections.Counter()
per_fn_atomic = collections.Counter()
per_fn_blr = collections.Counter()
analysed = collections.Counter()
nfn = collections.Counter()
for i in sorted(byf, key=lambda k: -sum(byf[k].values()))[:TOP]:
    s, e, name = secs[i][0], secs[i][1], secs[i][2]
    g = 'guest' if is_guest(name) else 'host'
    nfn[g] += 1
    out = subprocess.run([OBJ, '-d', '--no-show-raw-insn', '--start-address=0x%x' % s, '--stop-address=0x%x' % e, ELF],
                         capture_output=True, text=True, errors='replace').stdout.splitlines()
    ins = []
    for l in out:
        m = re.match(r'^\s*([0-9a-f]+):\s+(.*)$', l)
        if m:
            ins.append((int(m.group(1), 16), m.group(2).strip()))
    analysed[g] += sum(byf[i].values())
    for k, (a, t) in enumerate(ins):
        n = byf[i].get(a, 0)
        parts = t.split(None, 1)
        op = parts[0] if parts else ''
        args = parts[1] if len(parts) > 1 else ''
        if n:
            if op in ATOM:
                c = 'atomic/barrier'
            elif op in ('msr', 'mrs'):
                c = 'msr/mrs'
            elif op.startswith('rev'):
                c = 'rev (byte swap)'
            elif op in ('fdiv', 'fsqrt', 'sdiv', 'udiv'):
                c = 'div/sqrt'
            elif op in ('blr', 'br'):
                c = 'indirect branch'
            elif op == 'bl':
                c = 'bl'
            elif op == 'ret':
                c = 'ret'
            elif op.startswith('ld') or op.startswith('st'):
                q = re.match(r'^(q\d+|d\d+|s\d+|x\d+|w\d+|b\d+|h\d+|v\d+)', args)
                reg = q.group(1) if q else ''
                kind = 'load' if op.startswith('ld') else 'store'
                vec = reg[:1] in ('q', 'd', 's', 'b', 'h', 'v')
                if '[sp' in args:
                    c = kind + (' vec/fp' if vec else ' gpr') + ' [sp]'
                elif 'uxtw' in args:
                    c = kind + ' [base, wN, uxtw]'
                elif re.search(r'\[x0(,|\])', args):
                    c = kind + ' [x0..]'
                else:
                    c = kind + (' vec/fp' if vec else ' gpr') + ' other'
            elif op.startswith('b.') or op in ('b', 'cbz', 'cbnz', 'tbz', 'tbnz'):
                c = 'branch'
            elif op == 'prfm':
                c = 'prfm'
            elif op in MOVS:
                c = 'mov/perm'
            elif op.startswith('f'):
                c = 'fp arith'
            else:
                c = 'int/simd alu'
            cls[g][c] += n
        if op in ATOM:
            sh = sum(byf[i].get(ins[q][0], 0) for q in range(k, min(k + 3, len(ins))))
            skid[g + ' atomic/barrier + next 2'] += sh
            per_fn_atomic[name] += sh
        if op == 'msr' and 'fpcr' in args:
            skid[g + ' msr fpcr + next 2'] += sum(byf[i].get(ins[q][0], 0) for q in range(k, min(k + 3, len(ins))))
        if op == 'blr':
            sh = sum(byf[i].get(ins[q][0], 0) for q in range(k, min(k + 2, len(ins))))
            skid[g + ' blr + next 1'] += sh
            per_fn_blr[name] += sh
        if op == 'bl':
            skid[g + ' bl + next 1'] += sum(byf[i].get(ins[q][0], 0) for q in range(k, min(k + 2, len(ins))))
        if op in ('fdiv', 'fsqrt'):
            skid[g + ' fdiv/fsqrt + next 2'] += sum(byf[i].get(ins[q][0], 0) for q in range(k, min(k + 3, len(ins))))
        if op in ('ldr', 'ldur') and 'uxtw' in args:
            # a guest load whose result feeds a rev in the next instruction
            if k + 1 < len(ins) and ins[k + 1][1].startswith('rev'):
                skid[g + ' guest load followed by rev (load+rev samples)'] += n + byf[i].get(ins[k + 1][0], 0)
print('total samples (reports > 9): %d; analysed guest %d (%d fns), host %d (%d fns)' % (
    total, analysed['guest'], nfn['guest'], analysed['host'], nfn['host']))
for g in ('guest', 'host'):
    print('== %s (%d analysed)' % (g, analysed[g]))
    for c, n in cls[g].most_common(40):
        print('  %6d  %5.1f %%  %s' % (n, 100.0 * n / max(1, analysed[g]), c))
print('== windows (share of ALL samples)')
for c, n in skid.most_common():
    print('  %6d  %5.2f %%  %s' % (n, 100.0 * n / total, c))
print('== atomic windows by function')
for nme, n in per_fn_atomic.most_common(15):
    print('  %5d  %s' % (n, nme[:110]))
print('== blr windows by function')
for nme, n in per_fn_blr.most_common(10):
    print('  %5d  %s' % (n, nme[:110]))
