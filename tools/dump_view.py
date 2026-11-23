#!/usr/bin/env python3
"""Turns the renderer's image dumps (dumps/<name>.raw + .txt, sasrt_debug_dump_s) into PNGs and counts specks.

A speck is a pixel whose luminance is above every one of its 8 neighbours by more than --gap and by more than
--ratio times the brightest of them: the isolated bright dots this was written for. Each image gets a PNG (RGB; HDR
formats through x / (1 + x) after --exposure; depth as its value), and with --marks a second PNG with the specks
circled.

  python tools/dump_view.py out/pc/dumps [--out folder] [--match swap] [--marks] [--exposure 1.0]
"""
import argparse
import glob
import os

import numpy as np
from PIL import Image, ImageDraw

# VkFormat values the dumps use.
R8G8B8A8_UNORM, B8G8R8A8_UNORM, A2B10G10R10_UNORM = 37, 44, 64
R16G16B16A16_SFLOAT, R32G32_SFLOAT, R16G16_SFLOAT = 97, 103, 83
R32_SFLOAT, D32_SFLOAT, D24_UNORM_S8_UINT, D32_SFLOAT_S8_UINT = 100, 126, 129, 130


def load(raw):
    w, h, bpp, fmt, aspect = [int(v) for v in open(raw[:-4] + '.txt').read().split()]
    data = np.fromfile(raw, np.uint8)
    if aspect & 2 or aspect & 4:  # depth / stencil
        if bpp == 4:
            if fmt in (D24_UNORM_S8_UINT,):
                v = (data.view('<u4').reshape(h, w) & 0xFFFFFF).astype(np.float32) / 0xFFFFFF
            else:
                v = data.view('<f4').reshape(h, w)
        else:
            v = data.reshape(h, w).astype(np.float32) / 255.0
        return 'depth', np.repeat(v[:, :, None], 3, axis=2), w, h
    if bpp == 8 and fmt == R16G16B16A16_SFLOAT:
        v = data.view('<f2').reshape(h, w, 4).astype(np.float32)
        return 'hdr', v, w, h
    if bpp == 8 and fmt == R32G32_SFLOAT:
        v = data.view('<f4').reshape(h, w, 2)
        return 'hdr', np.dstack([v, np.zeros((h, w, 2), np.float32)]), w, h
    if bpp == 4 and fmt == R32_SFLOAT:
        v = data.view('<f4').reshape(h, w)
        return 'hdr', np.dstack([v, v, v, np.ones_like(v)]), w, h
    if bpp == 4 and fmt == R16G16_SFLOAT:
        v = data.view('<f2').reshape(h, w, 2).astype(np.float32)
        return 'hdr', np.dstack([v, np.zeros((h, w, 2), np.float32)]), w, h
    v = data.reshape(h, w, 4).astype(np.float32) / 255.0
    if fmt == B8G8R8A8_UNORM:
        v = v[:, :, [2, 1, 0, 3]]
    return 'ldr', v, w, h


def specks(lum, gap, ratio):
    h, w = lum.shape
    pad = np.pad(lum, 1, mode='edge')
    neigh = np.stack([pad[1 + dy:1 + dy + h, 1 + dx:1 + dx + w]
                      for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx])
    top = neigh.max(axis=0)
    return (lum > top + gap) & (lum > top * ratio)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('folder')
    ap.add_argument('--out')
    ap.add_argument('--match', default='')
    ap.add_argument('--marks', action='store_true')
    ap.add_argument('--exposure', type=float, default=1.0)
    ap.add_argument('--gap', type=float, default=0.15)
    ap.add_argument('--ratio', type=float, default=1.5)
    a = ap.parse_args()
    out = a.out or os.path.join(a.folder, 'png')
    os.makedirs(out, exist_ok=True)
    for raw in sorted(glob.glob(os.path.join(a.folder, '*.raw'))):
        name = os.path.basename(raw)[:-4]
        if a.match not in name:
            continue
        kind, v, w, h = load(raw)
        rgb = v[:, :, :3]
        if kind == 'hdr':
            finite = np.isfinite(rgb)
            bad = int((~finite).any(axis=2).sum())
            rgb = np.where(finite, rgb, 0.0)
            shown = rgb * a.exposure
            shown = np.clip(shown / (1.0 + np.abs(shown)), 0, 1)
            info = f'min {rgb.min():.3f} max {rgb.max():.3f} mean {rgb.mean():.3f} non-finite {bad}'
        else:
            shown = np.clip(rgb, 0, 1)
            info = f'mean {rgb.mean():.3f}'
        lum = shown @ np.array([0.299, 0.587, 0.114], np.float32)
        s = specks(lum, a.gap, a.ratio)
        img = Image.fromarray((shown * 255 + 0.5).astype(np.uint8))
        img.save(os.path.join(out, name + '.png'))
        if v.shape[2] == 4 and kind != 'depth':
            alpha = np.clip(v[:, :, 3], 0, 1) if kind == 'ldr' else np.clip(v[:, :, 3] / (1 + np.abs(v[:, :, 3])), 0, 1)
            Image.fromarray((alpha * 255 + 0.5).astype(np.uint8)).save(os.path.join(out, name + '_a.png'))
        if a.marks:
            m = img.copy()
            d = ImageDraw.Draw(m)
            ys, xs = np.nonzero(s)
            for x, y in zip(xs[:4000], ys[:4000]):
                d.ellipse([x - 3, y - 3, x + 3, y + 3], outline=(255, 0, 255))
            m.save(os.path.join(out, name + '_specks.png'))
        print(f'{name}: {w}x{h} {kind}, {info}, specks {int(s.sum())}')


if __name__ == '__main__':
    main()
