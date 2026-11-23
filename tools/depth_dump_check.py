#!/usr/bin/env python3
"""Checks the native renderer's depth restore stage by stage, from the images that sasrt_debug_dump_* writes to
out/pc/dumps (see masseffect_native_targets.cpp, DebugDumpAfterDraw).

Sonic & All-Stars Racing Transformed restores its G-buffer depth into EDRAM by sampling the depth resolve as
k_8_8_8_8 and drawing its raw words into a color target aliasing the depth target's tiles. The chain on the native
renderer, and what each dump must show:

  resolve_<addr>  R32F guest depth (me_depth_resolve_guestspace.comp)
  words_<addr>    RGBA8 raw words of the same resolve: depth24 (20e4) << 8 | stencil, byte 0 = R
  d<n>_..._C<base>  the color alias after the restore draw: the words with the two 40-pixel columns of every
                    80-pixel tile swapped (the restore shader's +-40 and the color/depth tile layouts)
  d<n>_..._D<base>_depth  the depth target after the import: host z = guest z * 0.5 (D24FS8 on a half-range D32)

  python tools/depth_dump_check.py [out/pc/dumps]
"""
import glob
import os
import sys

import numpy as np


def load(path):
    w, h, bpt, fmt, aspect = open(path[:-4] + '.txt').read().split()
    w, h, bpt = int(w), int(h), int(bpt)
    data = np.fromfile(path, np.uint8)
    return w, h, bpt, int(fmt), data


def from20e4(bits):
    bits = bits & 0xFFFFFF
    mantissa = bits & 0xFFFFF
    exponent = bits >> 20
    out = np.zeros(bits.shape, np.float32)
    normal = exponent != 0
    f = ((exponent.astype(np.uint32) + 112) << 23) | (mantissa.astype(np.uint32) << 3)
    out[normal] = f[normal].view(np.float32)
    denormal = (exponent == 0) & (mantissa != 0)
    out[denormal] = mantissa[denormal].astype(np.float32) * np.float32(2.0 ** -34)
    return out


def words_of_rgba8(data, w, h):
    b = data.reshape(h, w, 4).astype(np.uint32)
    return b[..., 0] | (b[..., 1] << 8) | (b[..., 2] << 16) | (b[..., 3] << 24)


def column_swap(a):
    """The two 40-pixel halves of every 80-pixel tile exchanged (x -> x +- 40)."""
    h, w = a.shape[:2]
    x = np.arange(w)
    src = np.where((x % 80) < 40, x + 40, x - 40)
    src = np.clip(src, 0, w - 1)
    return a[:, src]


def stats(name, z):
    finite = z[np.isfinite(z)]
    zero = float((z == 0).mean())
    print(f'  {name}: min {finite.min():.6g} max {finite.max():.6g} mean {finite.mean():.6g} zero {zero:.1%}')


def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else 'out/pc/dumps'
    resolves = sorted(glob.glob(os.path.join(folder, 'resolve_*.raw')))
    words_files = sorted(glob.glob(os.path.join(folder, 'words_*.raw')))
    z_resolve = None
    if resolves:
        w, h, bpt, fmt, data = load(resolves[0])
        z_resolve = data.view(np.float32).reshape(h, w)
        print(os.path.basename(resolves[0]), f'{w}x{h}')
        stats('guest z', z_resolve)
    word = None
    if words_files:
        w, h, bpt, fmt, data = load(words_files[0])
        word = words_of_rgba8(data, w, h)
        z_words = from20e4(word >> 8)
        print(os.path.basename(words_files[0]), f'{w}x{h}')
        stats('z from words', z_words)
        print(f'  stencil bytes: {np.unique(word & 0xFF)[:16]}')
        if z_resolve is not None:
            diff = np.abs(z_words - z_resolve)
            print(f'  |words - resolve|: max {diff.max():.3g}, mean {diff.mean():.3g}, '
                  f'> 1e-4: {(diff > 1e-4).mean():.2%}')
    for path in sorted(glob.glob(os.path.join(folder, 'd*_*.raw'))):
        name = os.path.basename(path)[:-4]
        w, h, bpt, fmt, data = load(path)
        print(name, f'{w}x{h} {bpt} B/texel format {fmt}')
        if name.endswith('_stencil'):
            s = data.reshape(h, w)
            values, counts = np.unique(s, return_counts=True)
            order = np.argsort(-counts)[:6]
            print('  stencil values:', ', '.join(f'{values[i]}:{counts[i] / s.size:.1%}' for i in order))
            continue
        if name.endswith('_depth'):
            z = data.view(np.float32).reshape(h, w)
            stats('host z', z)
            if z_resolve is not None:
                hh, ww = min(h, z_resolve.shape[0]), min(w, z_resolve.shape[1])
                guest = 2.0 * z[:hh, :ww]
                diff = np.abs(guest - z_resolve[:hh, :ww])
                print(f'  |2 * host z - resolve| over {ww}x{hh}: max {diff.max():.3g}, mean {diff.mean():.3g}, '
                      f'> 1e-3: {(diff > 1e-3).mean():.2%}')
            continue
        if bpt == 4 and fmt == 37:  # VK_FORMAT_R8G8B8A8_UNORM: a color alias of depth words?
            c = words_of_rgba8(data, w, h)
            z = from20e4(c >> 8)
            stats('z read as words', z)
            if word is not None:
                hh, ww = min(h, word.shape[0]), min(w, word.shape[1])
                expected = column_swap(word)[:hh, :ww]
                same = (c[:hh, :ww] == expected).mean()
                plain = (c[:hh, :ww] == word[:hh, :ww]).mean()
                print(f'  equals the column-swapped words: {same:.2%} (unswapped: {plain:.2%})')


if __name__ == '__main__':
    main()
