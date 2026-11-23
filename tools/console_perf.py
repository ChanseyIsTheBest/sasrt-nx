#!/usr/bin/env python3
"""sasrt-nx (2026-11-08, the second GPU round's console test): a console log's race windows as a performance summary.

    python tools/console_perf.py LOG [LOG ...] [--min-gpu-ms 30]

A window is one 10 s report: "[renut] 10.x s: N game frames (F fps), render thread busy R ms a frame, GPU G ms a frame"
and the "GPU profile:" block before it. Race windows: GPU ms above --min-gpu-ms and at least 700 draws a frame in the
profile's 1152x544 colour+depth line (the race's G-buffer pass; menus and loading screens have none). Prints each run's
race windows, their means, and the GPU profile's passes averaged over them.
"""
import argparse
import collections
import re


def windows(path):
    text = open(path, encoding='utf-8', errors='replace').read().splitlines()
    out = []
    prof = None
    i = 0
    while i < len(text):
        line = text[i]
        m = re.search(r'GPU profile: ([0-9.]+) ms per frame over (\d+) frames', line)
        if m:
            prof = {'total': float(m.group(1)), 'passes': collections.OrderedDict()}
            i += 1
            while i < len(text):
                pm = re.match(r'^\s+([0-9.]+) ms\s+(.*?)\s*(\(([0-9.]+) draws a frame\))?\s*$', text[i])
                if not pm:
                    break
                prof['passes'][pm.group(2).strip()] = (float(pm.group(1)), float(pm.group(4) or 0))
                i += 1
            continue
        m = re.search(r'\[renut\] ([0-9.]+) s: (\d+) game frames \(([0-9.]+) fps\), render thread busy ([0-9.]+) ms a frame'
                      r'.*?GPU ([0-9.]+) ms a frame', line)
        if m:
            w = {'fps': float(m.group(3)), 'frames': int(m.group(2)), 'render_ms': float(m.group(4)),
                 'gpu_ms': float(m.group(5)), 'prof': prof}
            cpu = re.search(r'CPU ([0-9.]+) ms a frame', line)
            w['cpu_ms'] = float(cpu.group(1)) if cpu else None
            out.append(w)
            prof = None
        i += 1
    return out


def is_race(w, min_gpu):
    if w['gpu_ms'] < min_gpu or not w['prof']:
        return False
    g = w['prof']['passes'].get('draws 1152x544 color+depth')
    return bool(g) and g[1] >= 700


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('logs', nargs='+')
    ap.add_argument('--min-gpu-ms', type=float, default=30.0)
    a = ap.parse_args()
    for path in a.logs:
        ws = [w for w in windows(path) if is_race(w, a.min_gpu_ms)]
        print(f'== {path}: {len(ws)} race windows')
        if not ws:
            continue
        for w in ws:
            print(f'   {w["fps"]:6.2f} fps  GPU {w["gpu_ms"]:6.2f} ms  render thread {w["render_ms"]:6.2f} ms')
        n = len(ws)
        fps = sum(w['fps'] for w in ws) / n
        gpu = sum(w['gpu_ms'] for w in ws) / n
        rt = sum(w['render_ms'] for w in ws) / n
        print(f'   mean: {fps:.2f} fps, GPU {gpu:.2f} ms a frame, render thread {rt:.2f} ms a frame')
        passes = collections.OrderedDict()
        for w in ws:
            for k, (ms, draws) in w['prof']['passes'].items():
                p = passes.setdefault(k, [0.0, 0.0, 0])
                p[0] += ms
                p[1] += draws
                p[2] += 1
        print('   GPU profile, mean of the race windows (ms a frame):')
        for k, (ms, draws, c) in sorted(passes.items(), key=lambda kv: -kv[1][0])[:16]:
            extra = f'  ({draws / c:.0f} draws)' if draws else ''
            print(f'     {ms / n:7.3f}  {k}{extra}')


if __name__ == '__main__':
    main()
