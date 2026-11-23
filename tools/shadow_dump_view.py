#!/usr/bin/env python3
"""Pictures of sasrt_renut_diag_shadow_dump's files (docs/enhancements.md, "sasrt_renut_diag_shadow_dump").

    python tools/shadow_dump_view.py <shadow_dump folder> [out folder]

Each file is w<window>_f<game frame>_<serial>_<kind>_<guest address>_x<x>_y<y>_<w>x<h>_fmt<plume format>.bin, raw
texels row by row: fmt34 R32_FLOAT (a depth resolve's float result: the shadow cascades' regions of the 1024x3072
atlas, the scene depth), fmt20 R8G8B8A8_UNORM (the colour resolves: G-buffer, shadow mask).

Writes, per window, one sheet per resolve (by guest address and region): the window's frames side by side (floats
stretched over the range all of them share, 1 = white) and below each frame after the first its difference from the
frame before (grey = the same, brighter = changed). And stats.txt: per file the mean, the share of texels at the
clear value (1.0 for depth) and the mean absolute difference from the frame before.
"""
import os
import re
import sys
from collections import defaultdict

import numpy as np
from PIL import Image

NAME = re.compile(r'w(\d+)_f(\d+)_(\d+)_(\w+?)_([0-9A-F]{8})_x(\d+)_y(\d+)_(\d+)x(\d+)_fmt(\d+)\.bin$')


def load(path, w, h, fmt):
    raw = np.fromfile(path, dtype=np.uint8)
    if raw.size != w * h * (8 if fmt == 10 else 4):  # cut short (the console's run stopped while writing it)
        return None
    if fmt == 34:
        return raw.view('<f4').reshape(h, w)
    if fmt in (20, 21):
        return raw.reshape(h, w, 4)
    if fmt == 10:
        return raw.view('<f2').reshape(h, w, 4).astype(np.float32)
    return None


def picture(a, lo, hi):
    if a.ndim == 2:
        g = np.clip((a - lo) / max(hi - lo, 1e-9), 0, 1)
        return Image.fromarray((g * 255).astype(np.uint8), 'L').convert('RGB')
    if a.dtype == np.uint8:
        return Image.fromarray(np.ascontiguousarray(a[:, :, :3]), 'RGB')
    return Image.fromarray((np.clip(a[:, :, :3], 0, 1) * 255).astype(np.uint8), 'RGB')


def main():
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(src, 'view')
    os.makedirs(out, exist_ok=True)
    groups = defaultdict(list)
    for name in sorted(os.listdir(src)):
        m = NAME.match(name)
        if not m:
            continue
        window, frame, serial, kind, va, x, y, w, h, fmt = m.groups()
        # The same resolve in each frame: its address, region and its place among that address's resolves of the frame.
        groups[(int(window), kind, va, int(x), int(y), int(w), int(h), int(fmt))].append((int(frame), int(serial), name))
    stats = open(os.path.join(out, 'stats.txt'), 'w')
    for key, files in sorted(groups.items()):
        window, kind, va, x, y, w, h, fmt = key
        by_frame = defaultdict(list)
        for frame, serial, name in files:
            by_frame[frame].append((serial, name))
        occurrences = max(len(v) for v in by_frame.values())
        for k in range(occurrences):  # several resolves into the same place in one frame: kept apart
            seq = []
            for frame in sorted(by_frame):
                items = sorted(by_frame[frame])
                if k < len(items):
                    a = load(os.path.join(src, items[k][1]), w, h, fmt)
                    if a is not None:
                        seq.append((frame, a))
            if not seq:
                continue
            if seq[0][1].ndim == 2:
                finite = np.concatenate([a[np.isfinite(a)].ravel()[::7] for _, a in seq])
                lo, hi = (np.percentile(finite, 1), np.percentile(finite, 99.5)) if finite.size else (0, 1)
            else:
                lo, hi = 0, 1
            scale = 256 / max(w, h)
            tw, th = max(1, int(w * scale)), max(1, int(h * scale))
            sheet = Image.new('RGB', (tw * len(seq), th * 2), (40, 40, 40))
            prev = None
            for i, (frame, a) in enumerate(seq):
                sheet.paste(picture(a, lo, hi).resize((tw, th)), (i * tw, 0))
                mean = float(np.nanmean(a.astype(np.float64)))
                clear = float(np.mean(a >= 1.0)) if a.ndim == 2 else float('nan')
                diff = float(np.nanmean(np.abs(a.astype(np.float64) - prev.astype(np.float64)))) if prev is not None else 0.0
                stats.write('w%d %s %s x%d y%d %dx%d #%d frame %d: mean %.6g, at 1.0 %.4f, mean |diff| %.6g\n'
                            % (window, kind, va, x, y, w, h, k, frame, mean, clear, diff))
                if prev is not None:
                    d = np.abs(a.astype(np.float32) - prev.astype(np.float32))
                    if d.ndim == 3:
                        d = d[:, :, :3].mean(axis=2) / 255.0
                    else:
                        d = d / max(hi - lo, 1e-9)
                    dimg = Image.fromarray((np.clip(0.25 + d * 4, 0, 1) * 255).astype(np.uint8), 'L').convert('RGB')
                    sheet.paste(dimg.resize((tw, th)), (i * tw, th))
                prev = a
            sheet.save(os.path.join(out, 'w%d_%s_%s_x%d_y%d_%dx%d_%d.png' % (window, kind, va, x, y, w, h, k)))
    stats.close()
    print('written to', out)


if __name__ == '__main__':
    main()
