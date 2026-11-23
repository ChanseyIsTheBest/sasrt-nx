#!/usr/bin/env python3
"""Side-by-side sheets of the track tests (tools/win/track_tests.ps1 -Mode test): for each track with captures from
both renderers, one PNG with N frames of the native renderer above N frames of the emulated GPU, spread evenly over
each capture, and a line of figures per capture:

  mean      mean luminance (0-255) of the sampled frames
  washed    share of pixels brighter than 240 (an overexposed, white image)
  specks    mean isolated bright pixels per frame (tools/speck_score.py's test)

  python tools/compare_tracks.py out/pc/captures/tracks [--frames 5] [--out folder]
"""
import argparse
import glob
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def frames(path):
    w, h, fps, n = open(path[:-5] + '.txt').read().split()
    w, h, n = int(w), int(h), int(n)
    return np.memmap(path, np.uint8, 'r').reshape(-1, h, w, 4)[:n]


def specks(lum, gap=0.15, ratio=1.25):
    h, w = lum.shape
    pad = np.pad(lum, 1, mode='edge')
    neigh = np.stack([pad[1 + dy:1 + dy + h, 1 + dx:1 + dx + w]
                      for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx])
    top = neigh.max(axis=0)
    return int(((lum > top + gap) & (lum > top * ratio)).sum())


def figures(f, picks):
    lums, washed, sp = [], [], []
    for i in picks:
        rgb = np.asarray(f[i, :, :, :3]).astype(np.float32)
        lum = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
        lums.append(lum.mean())
        washed.append((lum > 240).mean())
        sp.append(specks(lum / 255.0))
    return np.mean(lums), np.mean(washed), np.mean(sp)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('folder')
    ap.add_argument('--frames', type=int, default=5)
    ap.add_argument('--out')
    a = ap.parse_args()
    out = a.out or os.path.join(a.folder, 'compare')
    os.makedirs(out, exist_ok=True)
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 18)
    tw, th = 384, 216
    rows = []
    for native in sorted(glob.glob(os.path.join(a.folder, 't*_native.rgba'))):
        name = os.path.basename(native)[:-len('_native.rgba')]
        emu = os.path.join(a.folder, name + '_emu.rgba')
        caps = [('native', native)] + ([('emulated', emu)] if os.path.exists(emu) else [])
        sheet = Image.new('RGB', (tw * a.frames, th * len(caps)), (0, 0, 0))
        line = [name]
        for row, (label, path) in enumerate(caps):
            f = frames(path)
            n = len(f)
            # Skip the first tenth (menus, loading) and spread the rest.
            picks = [int(n * (0.1 + 0.9 * (k + 0.5) / a.frames)) for k in range(a.frames)]
            mean, washed, sp = figures(f, picks)
            line.append(f'{label}: mean {mean:.0f} washed {washed * 100:.1f}% specks {sp:.0f}')
            for k, i in enumerate(picks):
                im = Image.fromarray(np.asarray(f[i, :, :, :3])).resize((tw, th), Image.BILINEAR)
                d = ImageDraw.Draw(im)
                d.rectangle([0, 0, 150, 24], fill=(0, 0, 0))
                d.text((5, 2), f'{label} {i}', fill=(255, 255, 0), font=font)
                sheet.paste(im, (k * tw, row * th))
        sheet.save(os.path.join(out, name + '.png'))
        rows.append(' | '.join(line))
        print(rows[-1])
    with open(os.path.join(out, 'figures.txt'), 'w') as fh:
        fh.write('\n'.join(rows) + '\n')


if __name__ == '__main__':
    main()
