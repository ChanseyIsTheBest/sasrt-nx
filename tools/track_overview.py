#!/usr/bin/env python3
"""Overview images of the track tests (tools/win/track_tests.ps1 -Mode test): one row per track.

  paired:  for tracks with both captures, 3 native frames then 3 emulated frames (spread evenly over each capture);
  native:  for the rest, 6 native frames.

  python tools/track_overview.py out/pc/captures/tracks --names "0.0=Ocean View" ... [--out folder]
"""
import argparse
import glob
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

TW, TH = 320, 180


def frames(path):
    w, h, fps, n = open(path[:-5] + '.txt').read().split()
    return np.memmap(path, np.uint8, 'r').reshape(-1, int(h), int(w), 4)[:int(n)]


def tiles(path, count, label, font):
    f = frames(path)
    n = len(f)
    out = []
    for k in range(count):
        i = int(n * (0.12 + 0.86 * (k + 0.5) / count))
        im = Image.fromarray(np.asarray(f[min(i, n - 1), :, :, :3])).resize((TW, TH), Image.BILINEAR)
        d = ImageDraw.Draw(im)
        d.rectangle([0, TH - 20, 74, TH], fill=(0, 0, 0))
        d.text((4, TH - 19), label, fill=(255, 255, 0) if label == 'native' else (120, 220, 255), font=font)
        out.append(im)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('folder')
    ap.add_argument('--names', nargs='*', default=[])
    ap.add_argument('--out')
    a = ap.parse_args()
    out = a.out or a.folder
    names = dict(n.split('=', 1) for n in a.names)
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 15)
    big = ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf', 18)
    paired, native_only = [], []
    for native in sorted(glob.glob(os.path.join(a.folder, 't[0-9][0-9]_native.rgba'))):
        t = os.path.basename(native)[1:3]
        emu = os.path.join(a.folder, f't{t}_emu.rgba')
        (paired if os.path.exists(emu) else native_only).append((t, native, emu))
    for kind, rows in (('paired', paired), ('native', native_only)):
        if not rows:
            continue
        label_w = 170
        sheet = Image.new('RGB', (label_w + 6 * TW, len(rows) * TH), (20, 20, 20))
        d = ImageDraw.Draw(sheet)
        for r, (t, native, emu) in enumerate(rows):
            slot = f'{t[0]}.{t[1]}'
            d.text((8, r * TH + 60), slot, fill=(255, 255, 255), font=big)
            d.text((8, r * TH + 86), names.get(slot, ''), fill=(200, 200, 200), font=font)
            ims = (tiles(native, 3, 'native', font) + tiles(emu, 3, 'emulated', font)) if kind == 'paired' \
                else tiles(native, 6, 'native', font)
            for k, im in enumerate(ims):
                sheet.paste(im, (label_w + k * TW, r * TH))
        path = os.path.join(out, f'overview_{kind}.png')
        sheet.save(path)
        sheet.convert('RGB').save(path[:-4] + '.jpg', quality=82)
        print(path, sheet.size)


if __name__ == '__main__':
    main()
