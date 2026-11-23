#!/usr/bin/env python3
"""Adds up the in-run A/B windows of a log (sasrt_ab_keys; app/src/sasrt_enhancements.cpp, AbSwap): the "[ab] window"
lines carry each phase's raw sums for the last report period, so the race can be taken without the boot, the menus and
the loading screens (the windows are numbered from 1 in the order of the log).

    python tools/ab_summary.py out/pc/logs/sasrt_216.log [--from-window 12] [--to-window 99]

Prints, for the windows chosen, each phase's Swaps per second, ring work per Swap and per draw, ring cycles per draw,
the whole process's CPU per Swap and the vertex bindings bound per draw (logs after 2026-10-07 10:30), and on against
off.
"""
import argparse
import re

SUMS = r'(\d+) Swaps ([\d.]+) s ring ([\d.]+) ms (\d+) draws (\d+) cycles process ([\d.]+) ms(?: (\d+) bindings)?'
LINE = re.compile(r'\[ab\] window (\S+): on ' + SUMS + r' \| off ' + SUMS + r' \|\|')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('log')
    ap.add_argument('--from-window', type=int, default=1)
    ap.add_argument('--to-window', type=int, default=10 ** 9)
    args = ap.parse_args()
    total = {'on': [0.0] * 7, 'off': [0.0] * 7}
    names = None
    used = 0
    window = 0
    for line in open(args.log, encoding='utf-8', errors='replace'):
        m = LINE.search(line)
        if not m:
            continue
        window += 1
        if window < args.from_window or window > args.to_window:
            continue
        names = m.group(1)
        used += 1
        values = [float(v) if v is not None else 0.0 for v in m.groups()[1:]]
        for k, side in enumerate(('on', 'off')):
            for i in range(7):
                total[side][i] += values[k * 7 + i]
    if not used:
        raise SystemExit('no "[ab] window" line in the windows chosen')

    def figures(t):
        swaps, seconds, ring_ms, draws, cycles, process_ms, bindings = t
        return {
            'swaps_per_s': swaps / seconds if seconds else 0.0,
            'ring_ms_per_swap': ring_ms / swaps if swaps else 0.0,
            'ring_us_per_draw': ring_ms * 1000.0 / draws if draws else 0.0,
            'kcycles_per_draw': cycles / 1000.0 / draws if draws else 0.0,
            'process_ms_per_swap': process_ms / swaps if swaps else 0.0,
            'draws_per_swap': draws / swaps if swaps else 0.0,
            'bindings_per_draw': bindings / draws if draws else 0.0,
        }

    on, off = figures(total['on']), figures(total['off'])
    print(f'{names}: windows {args.from_window}-{min(args.to_window, window)} of {window} ({used} used); '
          f'on {int(total["on"][0])} Swaps in {total["on"][1]:.1f} s, off {int(total["off"][0])} Swaps in '
          f'{total["off"][1]:.1f} s')
    for key, label in (('swaps_per_s', 'Swaps per second'), ('ring_ms_per_swap', 'ring ms per Swap'),
                       ('ring_us_per_draw', 'ring us per draw'), ('kcycles_per_draw', 'ring kcycles per draw'),
                       ('process_ms_per_swap', 'process CPU ms per Swap'), ('draws_per_swap', 'draws per Swap'),
                       ('bindings_per_draw', 'vertex bindings per draw')):
        change = f'{(on[key] / off[key] - 1.0) * 100.0:+.1f} %' if off[key] else '-'
        print(f'  {label:<26} on {on[key]:10.2f}   off {off[key]:10.2f}   on against off {change}')


if __name__ == '__main__':
    main()
