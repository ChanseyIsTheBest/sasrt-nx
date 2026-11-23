#!/usr/bin/env python3
"""What the named functions of a Switch ELF contain that the A57 pays for and a PC profile hides: integer divides
(udiv/sdiv: 20-40 cycles for 64 bits; libstdc++'s unordered containers take the hash modulo a prime bucket count, so
every lookup has one where MSVC's STL masks), calls into the hash tables and the allocator, atomics and TLS reads.

  python tools/arm_func_ops.py out/nx/sasrt NAME_PART [NAME_PART ...] [--calls]
A function is listed when its demangled name contains one of the NAME_PARTs. --calls prints its call targets too.
"""
import collections
import os
import re
import subprocess
import sys

DEVKITA64 = next((d + '/devkitA64/bin/' for d in (os.environ.get('DEVKITPRO', ''), 'C:/devkitPro', '/opt/devkitpro')
                  if d and os.path.isdir(d + '/devkitA64/bin')), 'C:/devkitPro/devkitA64/bin/')
EXE = '.exe' if os.name == 'nt' else ''
HEAD = re.compile(r'^[0-9a-f]+ <(.+)>:$')
INS = re.compile(r'^\s+[0-9a-f]+:\s+(\S+)\s*(.*)$')
TARGET = re.compile(r'<([^>+]+)')


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    elf, parts = args[0], args[1:]
    show_calls = '--calls' in sys.argv
    proc = subprocess.Popen([DEVKITA64 + 'aarch64-none-elf-objdump' + EXE, '-d', '-C', '--no-show-raw-insn', elf],
                            stdout=subprocess.PIPE, text=True, errors='replace', bufsize=1 << 20)
    func = None
    stats = {}
    for line in proc.stdout:
        m = HEAD.match(line)
        if m:
            name = m.group(1)
            func = name if any(p in name for p in parts) else None
            if func:
                stats[func] = {'n': 0, 'div': 0, 'llsc': 0, 'tls': 0, 'hash': 0, 'alloc': 0, 'bl': 0, 'blr': 0,
                               'calls': collections.Counter()}
            continue
        if not func:
            continue
        m = INS.match(line)
        if not m:
            continue
        op, a = m.groups()
        s = stats[func]
        s['n'] += 1
        if op in ('udiv', 'sdiv'):
            s['div'] += 1
        elif op in ('ldxr', 'ldaxr', 'ldxrb', 'ldaxrb', 'ldxrh', 'ldaxrh'):
            s['llsc'] += 1
        elif op == 'blr':
            s['blr'] += 1
        elif op in ('bl', 'b'):
            t = TARGET.search(a)
            if not t or t.group(1) == func:
                continue
            target = t.group(1)
            if op == 'bl':
                s['bl'] += 1
            if target == '__aarch64_read_tp':
                s['tls'] += 1
            elif '_Hashtable' in target or '_Hash_bytes' in target or '_Prime_rehash' in target or \
                    'unordered_' in target:
                s['hash'] += 1
            elif target in ('malloc', 'free', 'operator new(unsigned long)', 'operator delete(void*)',
                            'operator delete(void*, unsigned long)', 'memalign', 'realloc'):
                s['alloc'] += 1
            if op == 'bl' or target in ('malloc', 'free'):
                s['calls'][target[:110]] += 1
    proc.wait()
    for name, s in sorted(stats.items(), key=lambda kv: -kv[1]['n']):
        print(f"{s['n']:7d} insns  div {s['div']:3d}  llsc {s['llsc']:3d}  tls {s['tls']:2d}  hash-calls {s['hash']:3d}  "
              f"alloc-calls {s['alloc']:3d}  bl {s['bl']:4d}  blr {s['blr']:3d}  {name[:120]}")
        if show_calls:
            for t, n in s['calls'].most_common(25):
                print(f'            {n:3d}  {t}')


if __name__ == '__main__':
    main()
