#!/usr/bin/env python3
"""Instruction, load/store, call and frame-setup counts of AArch64 object files (or ELFs), for comparing two builds of
the same source with different compiler options. One objdump -d pass per file.

  python tools/obj_insn_stats.py a.o b.o [...]
"""
import os
import re
import subprocess
import sys

DEVKITA64 = next((d + '/devkitA64/bin/' for d in (os.environ.get('DEVKITPRO', ''), 'C:/devkitPro', '/opt/devkitpro')
                  if d and os.path.isdir(d + '/devkitA64/bin')), 'C:/devkitPro/devkitA64/bin/')
EXE = '.exe' if os.name == 'nt' else ''
INS = re.compile(r'^\s+[0-9a-f]+:\s+(\S+)\s*(.*)$')
LOADS = ('ldr', 'ldp', 'ldur', 'ldrb', 'ldrh', 'ldrsw', 'ldrsb', 'ldrsh', 'ldurb', 'ldurh', 'ldursw', 'ld1')
STORES = ('str', 'stp', 'stur', 'strb', 'strh', 'sturb', 'sturh', 'st1')


def stats(path):
    proc = subprocess.Popen([DEVKITA64 + 'aarch64-none-elf-objdump' + EXE, '-d', '--no-show-raw-insn', path],
                            stdout=subprocess.PIPE, text=True, errors='replace', bufsize=1 << 20)
    n = loads = stores = sp_loads = sp_stores = calls = frames = fpcr = 0
    for line in proc.stdout:
        m = INS.match(line)
        if not m:
            continue
        op, args = m.groups()
        n += 1
        if op in LOADS:
            loads += 1
            sp_loads += '[sp' in args
        elif op in STORES:
            stores += 1
            sp_stores += '[sp' in args
        elif op in ('bl', 'blr'):
            calls += 1
        elif op == 'mov' and args.replace(' ', '') == 'x29,sp':
            frames += 1
        elif op == 'msr' and args.startswith('fpcr'):
            fpcr += 1
    proc.wait()
    return n, loads, stores, sp_loads, sp_stores, calls, frames, fpcr


def main():
    rows = [(p, stats(p)) for p in sys.argv[1:]]
    names = ('instructions', 'loads', 'stores', 'stack loads', 'stack stores', 'calls', 'frame setups', 'msr fpcr')
    for p, s in rows:
        print(p + ': ' + ', '.join(f'{v:,} {k}' for k, v in zip(names, s)))
    if len(rows) >= 2:
        a = rows[0][1]
        for p, b in rows[1:]:
            print(f'{p} against {rows[0][0]}: ' + ', '.join(
                f'{k} {100.0 * (y - x) / x:+.2f} %' for k, x, y in zip(names, a, b) if x))


if __name__ == '__main__':
    main()
