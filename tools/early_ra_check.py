#!/usr/bin/env python3
"""Does devkitA64 GCC's AArch64 early register allocation pass (-mearly-ra, on from -O2) lose table lookups in the
recompiled code? peggle2-nx found on a console (2026-10-13) that it does: in the XDK's streaming copy the pass
dropped 38 of 145 `tbl` instructions and let a data load overwrite the register holding the byte-reversal constant
(`tbl v30, {v30}, v30`): garbage textures, with the PC build (clang) and every PC check correct. The trigger there
is the two-register lookup of the NEON vperm helper (uint8x16x2_t + vqtbl2q_u8: a tuple that needs consecutive
registers).

This script compiles generated files with -mearly-ra=all and with -mearly-ra=none, with the Switch build's flags
(tools/one_file_ab.py's method: the file's own build statement of out/nx/build.ninja, without LTO and the precompiled
header), and compares the `tbl` / `tbx` count of every function. What a difference means (peggle2-nx compared its
whole tree, 33,670 functions: 9 differ):
  - the same count in both is the evidence wanted: nothing was dropped;
  - FEWER lookups with the pass on is a function to READ, not proof of damage. Two of Peggle's nine were the damaged
    streaming copies; in six the pass-on code is right and shorter (with the pass on a byte-reversed table pair is
    kept across several two-register lookups; the general allocator repeats the reversal);
  - fewer with the pass OFF also happens (post-reload tail merging joined a region the pass had kept apart).
peggle2-nx's tools/switch/check_lookup_constants.py follows the index of every lookup in one function's assembly
and fails on the fault itself, for functions of the streaming copy's shape.

  python tools/early_ra_check.py 158 94 41        the given generated files
  python tools/early_ra_check.py --all [--jobs 4] every generated file (minutes per file pair)
Also lists self-indexed lookups (`tbl vA, {vB}, vB` with A's table equal to its index) in either object: no generated
statement permutes a vector by itself.
"""
import argparse
import collections
import concurrent.futures
import os
import re
import shlex
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREFIX = 'sasrt_recomp'
DEVKITA64 = next((d + '/devkitA64/bin/' for d in (os.environ.get('DEVKITPRO', ''), 'C:/devkitPro', '/opt/devkitpro')
                  if d and os.path.isdir(d + '/devkitA64/bin')), 'C:/devkitPro/devkitA64/bin/')
EXE = '.exe' if os.name == 'nt' else ''
OUT = os.path.join(ROOT, 'out', 'early_ra_check')
HEAD = re.compile(r'^[0-9a-f]+ <(.*)>:$')
SELF1 = re.compile(r'\{(v\d+)\.16b\}, (v\d+)\.16b')
SELF2 = re.compile(r'\{(v\d+)\.16b-(v\d+)\.16b\}, (v\d+)\.16b')


def command(n, extra):
    lines = open(os.path.join(ROOT, 'out', 'nx', 'build.ninja'), encoding='utf-8').read().split('\n')
    head = 'build CMakeFiles/%s.dir/generated/default/%s.%s.cpp.obj:' % (PREFIX, PREFIX, n)
    start = next((i for i, l in enumerate(lines) if l.startswith(head)), None)
    if start is None:
        sys.exit('no build statement for file %s in out/nx/build.ninja (configure the Switch tree first)' % n)
    values = {}
    for l in lines[start + 1:start + 12]:
        m = re.match(r'\s+(DEFINES|FLAGS|INCLUDES) = (.*)$', l)
        if m:
            values[m.group(1)] = m.group(2)
    flags = [f for f in shlex.split(values['FLAGS'].replace('\\', '/'))
             if not f.startswith('-flto') and f not in ('-fno-fat-lto-objects', '-Winvalid-pch')]
    while '-include' in flags:
        i = flags.index('-include')
        del flags[i:i + 2]
    source = os.path.join(ROOT, 'app', 'generated', 'default', '%s.%s.cpp' % (PREFIX, n))
    return ([DEVKITA64 + 'aarch64-none-elf-g++' + EXE] + shlex.split(values['DEFINES'].replace('\\', '/')) +
            shlex.split(values['INCLUDES'].replace('\\', '/')) + flags + extra + ['-c', source])


def counts(obj):
    text = subprocess.run([DEVKITA64 + 'aarch64-none-elf-objdump' + EXE, '-d', obj], capture_output=True,
                          text=True).stdout
    per = collections.defaultdict(lambda: [0, 0, 0])  # tbl/tbx, two-register ones, self-indexed
    name = ''
    for line in text.split('\n'):
        m = HEAD.match(line)
        if m:
            name = m.group(1)
            continue
        if '\ttbl\t' not in line and '\ttbx\t' not in line:
            continue
        c = per[name]
        c[0] += 1
        m2 = SELF2.search(line)
        if m2:
            c[1] += 1
            c[2] += m2.group(3) in (m2.group(1), m2.group(2))
        else:
            m1 = SELF1.search(line)
            c[2] += bool(m1) and m1.group(1) == m1.group(2)
    return per


def check(n):
    os.makedirs(OUT, exist_ok=True)
    objs = {}
    for name, extra in (('all', []), ('none', ['-mearly-ra=none'])):
        objs[name] = os.path.join(OUT, 'r%s_%s.o' % (n, name))
        r = subprocess.run(command(n, extra) + ['-o', objs[name]], capture_output=True, text=True,
                           cwd=os.path.join(ROOT, 'out', 'nx'))
        if r.returncode:
            return n, None, r.stderr[-400:]
    a, b = counts(objs['all']), counts(objs['none'])
    rows = []
    for f in sorted(set(a) | set(b)):
        if a[f][:2] != b[f][:2] or a[f][2] or b[f][2]:
            rows.append((f, a[f], b[f]))
    total = (sum(v[0] for v in a.values()), sum(v[0] for v in b.values()))
    for o in objs.values():
        os.remove(o)
    return n, rows, total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('files', nargs='*')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--jobs', type=int, default=4)
    a = ap.parse_args()
    files = a.files
    if a.all:
        gen = os.path.join(ROOT, 'app', 'generated', 'default')
        files = sorted((m.group(1) for m in (re.match(PREFIX + r'\.(\d+)\.cpp$', f) for f in os.listdir(gen)) if m),
                       key=int)
    if not files:
        sys.exit(__doc__)
    suspects = 0
    with concurrent.futures.ThreadPoolExecutor(a.jobs) as pool:
        for n, rows, total in pool.map(check, files):
            if rows is None:
                print('file %s: COMPILE FAILED: %s' % (n, total))
                suspects += 1
                continue
            print('file %s: %d table lookups with the pass, %d without; %d functions differ or have a self-indexed '
                  'lookup' % (n, total[0], total[1], len(rows)), flush=True)
            for f, x, y in rows:
                suspects += 1
                print('    %s: with the pass %d lookups (%d two-register, %d self-indexed); without %d (%d, %d)' %
                      (f, x[0], x[1], x[2], y[0], y[1], y[2]))
    print('RESULT: %d functions to read (lookup counts differ, or a self-indexed lookup) in %d files' %
          (suspects, len(files)))
    sys.exit(1 if suspects else 0)


if __name__ == '__main__':
    main()
