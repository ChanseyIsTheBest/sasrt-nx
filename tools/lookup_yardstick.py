#!/usr/bin/env python3
"""The source as the yardstick for GCC's early register allocation fault (sa2-nx's out/shared_tools/lookup_yardstick.py,
with this port's one-source vperm): per recompiled function, the table lookups the generated C++ asks for against the
lookups in a Switch ELF. Read-only.

  - a two-source vperm (rex::ppc::simde_mm_perm_epi8_) = one two-register tbl;
  - a one-source vperm (REX_VPERM1, tools/vperm_one_source.py), a 128-bit byte reversal (REX_BSWAP128) or a
    shuffle-table use (REX_SHUFFLE_TABLE) = one one-register tbl (a reversal may also be rev64 + ext).

The fault removes lookups (peggle2-nx; in sa2-nx's standalone compile the streaming copy kept 25 of 87 one-register
lookups); inlining and the allocator's recomputation only add. A function's code is counted wherever GCC put it: its
own symbol, the clones split off it (sub_X.part.0, .isra.0, .constprop.0, .cold), the body it shares with another
function (identical code folding: one address, several names) and the function a one-instruction thunk branches to.
GCC also cancels a load's byte reversal against a store's and merges neighbouring constant shuffles (fewer
one-register lookups, not a fault), so only a shortfall of TWO-register lookups, or a self-indexed lookup
(tools/check_switch_build.py), points at the fault; a one-register shortfall is a function to read.

  python tools/lookup_yardstick.py app/generated/default out/nx/sasrt.elf [<elf> ...]
"""
import collections
import glob
import os
import re
import subprocess
import sys

DEVKITA64 = next((d + '/devkitA64/bin/' for d in (os.environ.get('DEVKITPRO', ''), 'C:/devkitPro', '/opt/devkitpro')
                  if d and os.path.isdir(d + '/devkitA64/bin')), 'C:/devkitPro/devkitA64/bin/')
EXE = '.exe' if os.name == 'nt' else ''
OBJDUMP = DEVKITA64 + 'aarch64-none-elf-objdump' + EXE
NM = DEVKITA64 + 'aarch64-none-elf-nm' + EXE
HEAD = re.compile(r'^DEFINE_REX_FUNC\((sub_[0-9A-F]{8})\) \{$', re.M)
LABEL = re.compile(r'^([0-9a-f]+) <(.+)>:$')
INSN = re.compile(r'^\s+[0-9a-f]+:\t(\S+)\t?(.*)$')
TBL = re.compile(r'^v(\d+)\.16b, \{([^}]*)\}, v(\d+)\.16b')
BRANCH = re.compile(r'^[0-9a-f]+ <(.+)>$')


def source(gen):
    """function -> (two-source vperm, one-source vperm, reversals, shuffle tables)."""
    out = {}
    for path in glob.glob(os.path.join(gen, '*_recomp.*.cpp')):
        text = open(path, encoding='utf-8', errors='replace').read()
        heads = list(HEAD.finditer(text))
        for i, m in enumerate(heads):
            body = text[m.end():heads[i + 1].start() if i + 1 < len(heads) else len(text)]
            counts = (body.count('simde_mm_perm_epi8_('), body.count('REX_VPERM1('), body.count('REX_BSWAP128'),
                      body.count('REX_SHUFFLE_TABLE'))
            if any(counts):
                out[m.group(1)] = counts
    return out


def base_name(symbol):
    # __imp__sub_X.part.0 -> sub_X (a clone counts for its function)
    return symbol.replace('__imp__', '').split('.')[0]


def elf(path):
    # Every name of every address (identical code folding gives one address several names).
    names = collections.defaultdict(set)
    nm = subprocess.run([NM, path], capture_output=True, text=True, errors='replace').stdout
    for line in nm.split('\n'):
        parts = line.split()
        if len(parts) == 3 and parts[1] in 'tTwW' and 'sub_' in parts[2]:
            names[int(parts[0], 16)].add(base_name(parts[2]))
    two, one, selfed, rev = (collections.Counter() for _ in range(4))
    size = collections.Counter()
    thunk = {}
    first_insn = {}
    p = subprocess.Popen([OBJDUMP, '-d', '--no-show-raw-insn', path], stdout=subprocess.PIPE, text=True,
                         errors='replace', bufsize=1 << 20)
    cur = None
    for line in p.stdout:
        m = LABEL.match(line)
        if m:
            cur = int(m.group(1), 16)
            continue
        m = INSN.match(line)
        if not m or cur is None:
            continue
        op = m.group(1)
        size[cur] += 1
        if size[cur] == 1:
            first_insn[cur] = (op, m.group(2))
        if op == 'rev64' and '.16b' in m.group(2):
            rev[cur] += 1
        if op not in ('tbl', 'tbx'):
            continue
        t = TBL.match(m.group(2))
        if not t:
            continue
        several = ',' in t.group(2) or '-' in t.group(2)
        (two if several else one)[cur] += 1
        if t.group(3) in re.findall(r'v(\d+)\.16b', t.group(2)):
            selfed[cur] += 1
    p.wait()
    # A one-instruction body that branches to another function: count that function's code.
    for address, n in size.items():
        if n == 1 and first_insn[address][0] == 'b':
            b = BRANCH.match(first_insn[address][1])
            if b:
                thunk[address] = base_name(b.group(1))
    # Per function name: the counts of every address carrying that name (its body, its clones).
    per = {k: collections.Counter() for k in ('two', 'one', 'selfed', 'rev')}
    for address in size:
        for name in names.get(address, ()):
            per['two'][name] += two[address]
            per['one'][name] += one[address]
            per['selfed'][name] += selfed[address]
            per['rev'][name] += rev[address]
    for address, target in thunk.items():
        for name in names.get(address, ()):
            for k in per:
                per[k][name] += per[k][target]
    return per['two'], per['one'], per['selfed'], per['rev']


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    src = source(sys.argv[1])
    total = [sum(v[i] for v in src.values()) for i in range(4)]
    print('generated code: %d functions ask for lookups: %d two-source vperm, %d one-source vperm, %d byte reversals, '
          '%d shuffle-table uses' % (len(src), *total))
    for path in sys.argv[2:]:
        two, one, selfed, rev = elf(path)
        short_two, short_one = [], []
        for f, (vperm, vperm1, reversals, tables) in sorted(src.items()):
            if two[f] < vperm:
                short_two.append((f, vperm, two[f]))
            have = one[f] + rev[f]            # a reversal may also be rev64 + ext
            want = vperm1 + reversals + tables
            if have < want:
                short_one.append((want - have, f, vperm1, reversals, tables, one[f], rev[f]))
        with_vperm = [f for f, v in src.items() if v[0] or v[1]]
        print(path)
        print('  functions with vperm: %d; their lookups: %d two-register, %d one-register' % (
            len(with_vperm), sum(two[f] for f in with_vperm), sum(one[f] for f in with_vperm)))
        print('  functions with fewer two-register lookups than two-source vperm statements: %d' % len(short_two))
        for f, a, b in short_two[:20]:
            print('    %s: %d statements, %d lookups' % (f, a, b))
        print('  functions with fewer one-register lookups (or rev64) than one-source vperm + reversals + shuffle '
              'tables: %d of %d' % (len(short_one), len(src)))
        for deficit, f, vperm1, reversals, tables, o, r in sorted(short_one, reverse=True)[:25]:
            print('    %s: %d one-source vperm + %d reversals + %d shuffle tables, %d one-register tbl + %d rev64 '
                  '(short by %d)' % (f, vperm1, reversals, tables, o, r, deficit))
        print('  self-indexed lookups in these functions: %d' % sum(selfed[f] for f in src))


if __name__ == '__main__':
    main()
