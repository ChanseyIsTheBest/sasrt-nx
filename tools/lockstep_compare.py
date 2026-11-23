#!/usr/bin/env python3
"""Pixel identity of two lockstep captures (sa2-nx's method): every frame of A is hashed and looked up among all the
frames of B, at any offset. Two runs of the same scripted session with vblank_per_swap (sasrt_video_frame, frame-timed
input) show the same frames; a renderer change that is pixel-identical leaves every gameplay frame of A somewhere in B.
The game-frame labels (.frames, written by the recorder) are only a guide: the ring presents a frame or two after the
game thread's Swap, and that latency differs between renderer paths.

  python tools/lockstep_compare.py base.rgba test.rgba [--worst 4 --out diff.png]

Prints: frames of A found in B (byte-identical), distinct images of A found in B, the first unmatched frames of A with
their label and the mean absolute difference to the nearest-label frame of B; --out writes the worst of those side by
side (A | B | 8x difference). Each .rgba needs its .txt (width height fps count). Needs numpy (and Pillow for --out).
"""
import argparse
import hashlib
import os

import numpy as np


def open_raw(path):
    w, h, _fps, _count = open(os.path.splitext(path)[0] + '.txt').read().split()[:4]
    w, h = int(w), int(h)
    n = os.path.getsize(path) // (w * h * 4)
    frames = np.memmap(path, np.uint8, 'r', shape=(n, h, w, 4))
    labels_path = os.path.splitext(path)[0] + '.frames'
    labels = None
    if os.path.exists(labels_path):
        labels = np.fromfile(labels_path, dtype=np.uint64)[:n]
        if len(labels) < n:  # a capture stopped early: its label file was not flushed whole
            labels = np.concatenate([labels, np.full(n - len(labels), np.iinfo(np.uint64).max, dtype=np.uint64)])
    return frames, labels


def digests(frames):
    # The X byte of R8G8B8X8 is not part of the image.
    return [hashlib.blake2b(np.ascontiguousarray(f[..., :3]).tobytes(), digest_size=16).digest() for f in frames]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('a')
    ap.add_argument('b')
    ap.add_argument('--worst', type=int, default=4)
    ap.add_argument('--out')
    a = ap.parse_args()
    fa, la = open_raw(a.a)
    fb, lb = open_raw(a.b)
    if fa.shape[1:] != fb.shape[1:]:
        raise SystemExit(f'sizes differ: {fa.shape[1:]} vs {fb.shape[1:]}')
    ha, hb = digests(fa), digests(fb)
    where_b = {}
    for i, h in enumerate(hb):
        where_b.setdefault(h, i)
    matched = [where_b.get(h) for h in ha]
    found = sum(m is not None for m in matched)
    distinct_a = set(ha)
    distinct_found = sum(h in where_b for h in distinct_a)
    print(f'A: {len(ha)} frames ({len(distinct_a)} distinct images); B: {len(hb)} frames ({len(set(hb))} distinct)')
    print(f'frames of A found in B (byte-identical, any offset): {found} of {len(ha)}; distinct images of A found in B: '
          f'{distinct_found} of {len(distinct_a)}')
    if la is not None and lb is not None:
        print(f'labels: A game frames {int(la[la != np.iinfo(np.uint64).max].min()) if (la != np.iinfo(np.uint64).max).any() else "-"}'
              f'..{int(la[la != np.iinfo(np.uint64).max].max()) if (la != np.iinfo(np.uint64).max).any() else "-"}, '
              f'B {int(lb[lb != np.iinfo(np.uint64).max].min()) if (lb != np.iinfo(np.uint64).max).any() else "-"}'
              f'..{int(lb[lb != np.iinfo(np.uint64).max].max()) if (lb != np.iinfo(np.uint64).max).any() else "-"}')
        # Offsets of the matches by label (how far the presented frame of A sits from the same image in B).
        offs = {}
        for i, m in enumerate(matched):
            if m is not None and la[i] != np.iinfo(np.uint64).max and lb[m] != np.iinfo(np.uint64).max:
                d = int(lb[m]) - int(la[i])
                offs[d] = offs.get(d, 0) + 1
        if offs:
            print('label offset of the matches (B - A: count): ' +
                  ', '.join(f'{d}: {c}' for d, c in sorted(offs.items(), key=lambda x: -x[1])[:8]))
    unmatched = [i for i, m in enumerate(matched) if m is None]
    if unmatched:
        runs, start = [], unmatched[0]
        for p, q in zip(unmatched, unmatched[1:] + [None]):
            if q != p + 1:
                runs.append((start, p))
                start = q
        print(f'unmatched frames of A: {len(unmatched)} in {len(runs)} runs: ' +
              ', '.join(f'{s}-{e}' if s != e else f'{s}' for s, e in runs[:20]) + (' ...' if len(runs) > 20 else ''))
        scored = []
        for i in unmatched[:: max(1, len(unmatched) // 64)]:
            j = min(range(len(fb)), key=lambda k: abs(int(lb[k]) - int(la[i])) if la is not None and lb is not None
                    else abs(k - i))
            diff = np.abs(fa[i][..., :3].astype(np.int16) - fb[j][..., :3].astype(np.int16))
            scored.append((float(diff.mean()), int((diff.max(axis=2) > 0).sum()), i, j))
        scored.sort(reverse=True)
        for mad, px, i, j in scored[:8]:
            print(f'  A {i} (label {int(la[i]) if la is not None else "-"}) vs B {j}: mean abs diff {mad:.3f}, '
                  f'{px} pixels differ')
        if a.out and scored:
            from PIL import Image
            rows = []
            for _mad, _px, i, j in scored[: a.worst]:
                x, y = fa[i][..., :3], fb[j][..., :3]
                d = np.clip(np.abs(x.astype(np.int16) - y.astype(np.int16)) * 8, 0, 255).astype(np.uint8)
                rows.append(np.concatenate([x, y, d], axis=1))
            Image.fromarray(np.concatenate(rows, axis=0)).save(a.out)
            print(f'wrote {a.out}')


if __name__ == '__main__':
    main()
