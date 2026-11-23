#!/usr/bin/env python3
"""Counts isolated bright pixels ("specks") in the frames of a raw capture (captures/*.rgba + .txt).

Same test as tools/dump_view.py: a pixel brighter than all 8 neighbours by more than --gap (0-1) and by more than
--ratio times the brightest of them. Prints the count per sampled frame and the mean; with --marks <png> writes the
frame with the most specks, specks circled.

  python tools/speck_score.py <capture.rgba> [--step 1] [--gap 0.15] [--ratio 1.25] [--marks out.png]
"""
import argparse

import numpy as np
from PIL import Image, ImageDraw


def specks(lum, gap, ratio):
    h, w = lum.shape
    pad = np.pad(lum, 1, mode='edge')
    neigh = np.stack([pad[1 + dy:1 + dy + h, 1 + dx:1 + dx + w]
                      for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx])
    top = neigh.max(axis=0)
    return (lum > top + gap) & (lum > top * ratio)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('capture')
    ap.add_argument('--step', type=int, default=1)
    ap.add_argument('--gap', type=float, default=0.15)
    ap.add_argument('--ratio', type=float, default=1.25)
    ap.add_argument('--first', type=int, default=0)
    ap.add_argument('--last', type=int, default=-1)
    ap.add_argument('--marks')
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()
    w, h, fps, n = open(a.capture[:-5] + '.txt').read().split()
    w, h, n = int(w), int(h), int(n)
    frames = np.memmap(a.capture, np.uint8, 'r').reshape(-1, h, w, 4)[:n]
    last = n if a.last < 0 else min(a.last, n)
    counts = []
    best = (-1, 0, None)
    for i in range(a.first, last, a.step):
        rgb = np.asarray(frames[i, :, :, :3]).astype(np.float32) / 255.0
        s = specks(rgb @ np.array([0.299, 0.587, 0.114], np.float32), a.gap, a.ratio)
        c = int(s.sum())
        counts.append(c)
        if c > best[0]:
            best = (c, i, s)
        if not a.quiet:
            print(f'frame {i}: {c}')
    print(f'{a.capture}: {len(counts)} frames, mean {np.mean(counts):.1f}, median {np.median(counts):.0f}, '
          f'max {best[0]} (frame {best[1]})')
    if a.marks and best[2] is not None:
        img = Image.fromarray(np.asarray(frames[best[1], :, :, :3]))
        d = ImageDraw.Draw(img)
        ys, xs = np.nonzero(best[2])
        for x, y in zip(xs, ys):
            d.ellipse([x - 4, y - 4, x + 4, y + 4], outline=(255, 0, 255))
        img.save(a.marks)


if __name__ == '__main__':
    main()
