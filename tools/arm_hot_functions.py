#!/usr/bin/env python3
"""Which of the PC profile's hot game functions cost the most on the Switch's ARM CPU (A57).

A PC profile ranks functions by x86 time; the Switch runs the same recompiled C++ compiled by GCC for AArch64, where
some guest operations cost far more than on x86. This scores each hot function of a PC profile by what its AArch64
code in the Switch ELF contains:

  msr fpcr   a floating-point mode switch (the PPC's per-instruction FPSCR/VSCR flush mode). It serialises the FP
             pipeline: 3-6 % of the game thread in UnleashedRecomp-NX and MarathonRecomp-NX;
  rev        a byte swap, one per big-endian guest load/store;
  dmb        a memory barrier (lwsync/sync/eieio);
  bl/blr     calls (with direct calls, the inlined ones are gone).

  python tools/arm_hot_functions.py out/pc/logs/pc_profile.log [--elf out/nx/sasrt] [--from-window 8] [--pick 30]
                                     [--exclude <hooked addresses>]

The ranking it prints: PC share of the busy game threads x (1 + FPCR switches per 100 instructions). The pick is the
top-N by that score, excluding the functions that already have a native replacement.
"""
import argparse
import collections
import os
import re
import struct
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

NM = r'C:\devkitPro\devkitA64\bin\aarch64-none-elf-nm.exe'

WINDOW = re.compile(r'^== pc profile window')
THREAD = re.compile(r'^thread (\d+) "(.*)": busy ([\d.]+)% \((\d+) samples\)')
LINE = re.compile(r'^\s+[\d.]+%\s+\S*sub_([0-9A-F]{8}) x(\d+)$')


def busy_ranking(log, skip, first_window):
    """Guest function -> busy samples over the game's threads (sasrt-nx: logs/pc_profile.log of sasrt_pc_profile_s, which
    samples busy threads only, self time), and the threads' busy total. Threads whose name contains one of `skip` (the
    renderer's own host threads) are left out."""
    counts, busy = collections.Counter(), 0
    window, keep = 0, False
    for line in open(log, encoding='utf-8', errors='replace'):
        if WINDOW.match(line):
            window += 1
            keep = False
            continue
        m = THREAD.match(line)
        if m:
            keep = window >= first_window and not any(k in m.group(2) for k in skip)
            if keep:
                busy += int(m.group(4))
            continue
        if line.startswith('== '):  # the all-threads summary
            keep = False
            continue
        m = LINE.match(line)
        if keep and m:
            counts[m.group(1)] += int(m.group(2))
    return counts, busy


def elf_functions(elf):
    """name -> (address, size) for __imp__sub_X and sub_X (hooks), from nm -S."""
    out = {}
    text = subprocess.run([NM, '-S', '--defined-only', elf], capture_output=True, text=True).stdout
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 4 and parts[2] in 'tTwW':
            out[parts[3]] = (int(parts[0], 16), int(parts[1], 16))
    return out


def elf_code(elf):
    data = open(elf, 'rb').read()
    shoff, = struct.unpack_from('<Q', data, 0x28)
    shentsize, shnum = struct.unpack_from('<HH', data, 0x3A)
    segs = []
    for i in range(shnum):
        _, type_, flags, addr, offset, size = struct.unpack_from('<IIQQQQ', data, shoff + i * shentsize)
        if type_ == 1 and flags & 0x4 and size:
            segs.append((addr, offset, size))
    return data, segs


def classify(data, segs, addr, size):
    for base, off, sz in segs:
        if base <= addr < base + sz:
            words = struct.unpack_from('<%dI' % (size // 4), data, off + addr - base)
            break
    else:
        return None
    c = collections.Counter()
    for w in words:
        if (w & 0xFFFFFFE0) == 0xD51B4400:
            c['fpcr'] += 1                      # msr fpcr, xN
        elif (w & 0xFFFFFC00) in (0x5AC00800, 0xDAC00C00, 0x5AC00400, 0xDAC00800):
            c['rev'] += 1                       # rev w / rev x / rev16 w / rev32 x
        elif (w & 0xFFFFF0FF) == 0xD50330BF:
            c['dmb'] += 1
        elif (w & 0xFC000000) == 0x94000000 or (w & 0xFFFFFC1F) == 0xD63F0000:
            c['call'] += 1                      # bl / blr
    c['ins'] = len(words)
    return c


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('log', help='logs/pc_profile.log (sasrt_pc_profile_s)')
    ap.add_argument('--elf', default=os.path.join(ROOT, 'out', 'nx', 'sasrt'))
    ap.add_argument('--from-window', type=int, default=1)
    ap.add_argument('--skip', nargs='*', default=['GPU ring native', 'GPU VSync'])
    ap.add_argument('--exclude', nargs='*', default=[], help='addresses already hooked or native')
    ap.add_argument('--top', type=int, default=60)
    ap.add_argument('--pick', type=int, default=30)
    a = ap.parse_args()
    counts, busy = busy_ranking(a.log, a.skip, a.from_window)
    funcs = elf_functions(a.elf)
    data, segs = elf_code(a.elf)
    listed = os.path.join(ROOT, 'app', 'src', 'hot', 'localized.txt')
    native = set(re.findall(r'^([0-9A-F]{8})', open(listed).read(), re.M)) if os.path.exists(listed) else set()
    native |= {x.upper().replace('SUB_', '') for x in a.exclude}
    rows = []
    for addr, n in counts.most_common(a.top):
        body = funcs.get('__imp__sub_' + addr) or funcs.get('sub_' + addr)
        c = classify(data, segs, *body) if body else None
        if not c:
            continue
        share = 100.0 * n / busy
        fpcr_rate = 100.0 * c['fpcr'] / max(c['ins'], 1)
        score = share * (1.0 + fpcr_rate)
        rows.append((score, addr, share, c, fpcr_rate, addr in native))
    rows.sort(reverse=True)
    print(f'{busy} busy samples of the game threads')
    print(f'{"function":12} {"PC %":>5} {"ARM ins":>8} {"fpcr":>5} {"/100":>5} {"rev":>5} {"dmb":>4} {"calls":>5} '
          f'{"score":>6}  native/hooked')
    for score, addr, share, c, rate, nat in rows:
        print(f'sub_{addr} {share:5.2f} {c["ins"]:8d} {c["fpcr"]:5d} {rate:5.2f} {c["rev"]:5d} {c["dmb"]:4d} '
              f'{c["call"]:5d} {score:6.2f}  {"yes" if nat else ""}')
    pick = [r for r in rows if not r[5]][:a.pick]
    print()
    print(f'Pick ({len(pick)}, not yet native or hooked): ' + ' '.join(r[1] for r in pick))


if __name__ == '__main__':
    main()
