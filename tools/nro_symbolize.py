#!/usr/bin/env python3
"""sasrt-nx (2026-10-21): names the "pc image+0x..." lines of a console profile (logs/rex/rex_profile_NNN.log) from the
NRO's GNU ld map (out/nx/sdcard_sasrt.map, written by tools/win/package_switch.ps1 for the packaged NRO).

    python tools/nro_symbolize.py <map> <profile.log> [--block N] [--thread ID]

Without --block, every line of the profile; with it, only the N-th "====" block (1-based), and with --thread only that
thread's samples. Sample lines get the function (demangled with c++filt when it is on the PATH) and their offset in it,
and a per-function total is printed after each thread.
"""
import argparse
import bisect
import re
import shutil
import subprocess
import sys


def load_map(path):
    syms = []
    pending = None
    for line in open(path, encoding='utf-8', errors='replace'):
        m = re.match(r'^ \.text\.(\S+)\s*$', line)
        if m:
            pending = m.group(1)
            continue
        m = re.match(r'^ \.text\.(\S+)\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)', line)
        if m:
            syms.append((int(m.group(2), 16), int(m.group(3), 16), m.group(1)))
            pending = None
            continue
        if pending:
            m = re.match(r'^\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)\s', line)
            if m:
                syms.append((int(m.group(1), 16), int(m.group(2), 16), pending))
            pending = None
            continue
        m = re.match(r'^\s+0x([0-9a-f]{8,})\s+([A-Za-z_][\w:.$<>~]*)\s*$', line)
        if m:
            syms.append((int(m.group(1), 16), 0, m.group(2)))
    syms.sort()
    return syms


def demangle(names):
    tool = shutil.which('c++filt') or shutil.which('aarch64-none-elf-c++filt')
    if not tool or not names:
        return {n: n for n in names}
    out = subprocess.run([tool], input='\n'.join(names), capture_output=True, text=True).stdout.split('\n')
    return {n: (out[i] if i < len(out) and out[i] else n) for i, n in enumerate(names)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('map')
    ap.add_argument('profile')
    ap.add_argument('--block', type=int, default=0)
    ap.add_argument('--thread', default='')
    a = ap.parse_args()
    syms = load_map(a.map)
    starts = [s[0] for s in syms]

    def find(off):
        i = bisect.bisect_right(starts, off) - 1
        if i < 0:
            return None, 0
        return syms[i][2], off - syms[i][0]

    lines = open(a.profile, encoding='utf-8', errors='replace').read().split('\n')
    block = 0
    in_thread = not a.thread
    resolved = []
    for line in lines:
        if line.startswith('===='):
            block += 1
        if a.block and block != a.block:
            continue
        if line.startswith('-- thread'):
            in_thread = (not a.thread) or ('thread %s ' % a.thread) in line
        if not in_thread:
            continue
        m = re.search(r'pc image\+0x([0-9a-f]+)', line)
        resolved.append((line, find(int(m.group(1), 16)) if m else None))
    names = demangle(sorted({r[1][0] for r in resolved if r[1] and r[1][0]}))
    totals = {}
    for line, r in resolved:
        if r and r[0]:
            pct = re.match(r'\s*([0-9.]+)%', line)
            if pct:
                totals[r[0]] = totals.get(r[0], 0.0) + float(pct.group(1))
            print('%s   %s+0x%x' % (line, names[r[0]][:150], r[1]))
        else:
            if line.startswith('-- thread') and totals:
                for n, v in sorted(totals.items(), key=lambda kv: -kv[1])[:15]:
                    print('      total %5.1f%%  %s' % (v, names[n][:150]))
                totals = {}
            print(line)
    for n, v in sorted(totals.items(), key=lambda kv: -kv[1])[:15]:
        print('      total %5.1f%%  %s' % (v, names[n][:150]))


if __name__ == '__main__':
    sys.exit(main())
