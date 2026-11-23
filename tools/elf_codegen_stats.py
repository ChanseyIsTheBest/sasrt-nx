#!/usr/bin/env python3
"""Instruction and load/store counts of the recompiled game functions in a Switch ELF (the measure sa2-nx used for its
codegen rounds: static, so it compares two builds of the same code exactly, where a PC run is noisy).

A function is the span from its symbol to the next symbol (aarch64-none-elf-nm -n). Recompiled functions are the
`sub_XXXXXXXX` symbols (DEFINE_REX_FUNC bodies) and the `__imp__sub_XXXXXXXX` ones (the bodies of hooked functions; the
few hundred hooks themselves, named `sub_X`, are counted with them). Loads and stores: every A64 instruction of the
load/store encoding group (op0 = x1x0: integer, FP/SIMD, pairs, exclusives, LD1-LD4).

  python tools/elf_codegen_stats.py out/nx/sasrt [other unstripped ELF]   (sasrt.stripped.elf has no symbols)
"""
import struct
import subprocess
import sys

NM = r'C:\devkitPro\devkitA64\bin\aarch64-none-elf-nm.exe'


def text_sections(data):
    shoff, = struct.unpack_from('<Q', data, 0x28)
    shentsize, shnum = struct.unpack_from('<HH', data, 0x3A)
    out = []
    for i in range(shnum):
        name, type_, flags, addr, offset, size = struct.unpack_from('<IIQQQQ', data, shoff + i * shentsize)
        if type_ == 1 and flags & 0x4 and size:  # PROGBITS, executable
            out.append((addr, offset, size))
    return out


def stats(path):
    data = open(path, 'rb').read()
    assert data[:4] == b'\x7fELF' and data[4] == 2, path
    secs = text_sections(data)
    lines = subprocess.run([NM, '-n', path], capture_output=True, text=True).stdout.splitlines()
    syms = []
    for line in lines:
        parts = line.split()
        if len(parts) == 3 and parts[1] in 'tTwW':
            syms.append((int(parts[0], 16), parts[2]))
    syms.sort()
    totals = {'recompiled': [0, 0, 0], 'other': [0, 0, 0]}
    for i, (addr, name) in enumerate(syms):
        end = syms[i + 1][0] if i + 1 < len(syms) else addr
        if end <= addr:
            continue
        for base, off, size in secs:
            if base <= addr < base + size:
                end = min(end, base + size)
                code = data[off + addr - base:off + end - base]
                break
        else:
            continue
        n = len(code) // 4
        ls = 0
        for k in range(n):
            w, = struct.unpack_from('<I', code, 4 * k)
            if (w >> 25) & 0b0101 == 0b0100:
                ls += 1
        kind = 'recompiled' if name.startswith(('__imp__sub_', 'sub_')) else 'other'
        t = totals[kind]
        t[0] += 1
        t[1] += n
        t[2] += ls
    return totals


def main():
    results = [(p, stats(p)) for p in sys.argv[1:]]
    for path, totals in results:
        print(path)
        for kind, (funcs, insns, ls) in totals.items():
            print(f'  {kind:<10} {funcs:>8} functions {insns:>11,} instructions {ls:>11,} loads/stores')
    if len(results) == 2:
        a, b = results[0][1]['recompiled'], results[1][1]['recompiled']
        print(f'recompiled: instructions {a[1]:,} -> {b[1]:,} ({100.0 * (b[1] - a[1]) / a[1]:+.1f} %), '
              f'loads/stores {a[2]:,} -> {b[2]:,} ({100.0 * (b[2] - a[2]) / a[2]:+.1f} %)')


if __name__ == '__main__':
    main()
