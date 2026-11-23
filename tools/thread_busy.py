#!/usr/bin/env python3
"""Busy share and CPU seconds per thread of a PC profile (logs/pc_profile.log of sasrt_pc_profile_s), averaged over the
chosen report windows: for A/B runs of an enhancement (tools/win/natives_ab.ps1).

  python tools/thread_busy.py out/pc/logs/pc_profile.log [--from-window 12] [--to-window N]
"""
import argparse
import collections
import re

WINDOW = re.compile(r'^== pc profile window ([\d.]+) s')
THREAD = re.compile(r'^thread (\d+) "(.*)": busy ([\d.]+)% \((\d+) samples\), cpu ([\d.]+) s')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('log')
    ap.add_argument('--from-window', type=int, default=1)
    ap.add_argument('--to-window', type=int, default=10 ** 9)
    a = ap.parse_args()
    window = 0
    busy = collections.defaultdict(list)
    cpu = collections.defaultdict(float)
    for line in open(a.log, encoding='utf-8', errors='replace'):
        m = WINDOW.match(line)
        if m:
            window += 1
            continue
        m = THREAD.match(line)
        if m and a.from_window <= window <= a.to_window:
            name = re.sub(r' \([0-9A-F]+\)$', '', m.group(2))
            busy[name].append(float(m.group(3)))
            cpu[name] += float(m.group(5))
    windows = max(1, min(window, a.to_window) - a.from_window + 1)
    total = 0.0
    for name, values in sorted(busy.items(), key=lambda kv: -sum(kv[1])):
        mean = sum(values) / windows
        total += cpu[name]
        if mean >= 1.0:
            print(f'  {mean:5.1f} % busy  {cpu[name] / windows:5.2f} s cpu per 10 s  {name}')
    print(f'  {windows} windows; all threads {total / windows:.2f} s cpu per 10 s')


if __name__ == '__main__':
    main()
