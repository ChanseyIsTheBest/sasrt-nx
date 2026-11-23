#!/usr/bin/env python3
"""sasrt-nx (2026-11-08, katamari-nx's tools/switch_hot_pcs.py on the link map): the hot instructions inside one
function of a console profile (logs/rex/rex_profile_NNN.log), with the disassembly of the hottest windows: what says
whether a hand-written native can remove the cost (docs/optimising-functions.md, "Reading the samples"). Needs the
link map and the ELF of the SAME build (the archived sasrt.map and sasrt.stripped.elf: the code is all there).

  python tools/switch_hot_pcs.py PROFILE MAP ELF "section name substring" [from_report=0] [windows=8] [win_bytes=64]
"""
import bisect
import collections
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import switch_hot_functions as shf  # noqa: E402

BIN = 'C:/devkitPro/devkitA64/bin/aarch64-none-elf-'
REPORT = re.compile(r'^==== ')
PC = re.compile(r'^\s+[\d.]+%\s+pc image\+0x([0-9a-f]+) x(\d+)')


def main():
    log, mapfile, elf, func = sys.argv[1:5]
    from_report = int(sys.argv[5]) if len(sys.argv) > 5 else 0
    windows = int(sys.argv[6]) if len(sys.argv) > 6 else 8
    win = int(sys.argv[7]) if len(sys.argv) > 7 else 64
    secs = [s for s in shf.load_map(mapfile) if func in s[2]]
    if not secs:
        sys.exit('no section matches ' + func)
    for start, end, name, obj in secs[:4]:
        print('%s %s [%x, %x) %d bytes' % (name, shf.module_of(obj), start, end, end - start))
    start, end = secs[0][0], secs[0][1]
    pcs = collections.Counter()
    report = 0
    for line in open(log, encoding='utf-8', errors='replace'):
        if REPORT.match(line):
            report += 1
            continue
        m = PC.match(line)
        if m and report > from_report:
            off = int(m.group(1), 16)
            if start <= off < end:
                pcs[off] += int(m.group(2))
    total = sum(pcs.values())
    print('%d samples in the function' % total)
    bins = collections.Counter()
    for off, n in pcs.items():
        bins[(off - start) // win] += n
    shown = sorted(b for b, _ in bins.most_common(windows))
    for b in shown:
        a = start + b * win
        print('\n== +0x%x (%d samples, %.0f %%)' % (b * win, bins[b], 100.0 * bins[b] / max(1, total)))
        dis = subprocess.run([BIN + 'objdump.exe', '-d', '--no-show-raw-insn', '--start-address=0x%x' % a,
                              '--stop-address=0x%x' % (a + win), elf], capture_output=True, text=True,
                             errors='replace').stdout
        for line in dis.splitlines():
            m = re.match(r'^\s+([0-9a-f]+):\s+(.*)$', line)
            if m:
                at = int(m.group(1), 16)
                print('%5s %6x  %s' % (('x%d' % pcs[at]) if pcs[at] else '', at - start, m.group(2)[:90]))


if __name__ == '__main__':
    main()
