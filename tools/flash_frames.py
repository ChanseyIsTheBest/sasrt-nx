"""flash_frames.py (sasrt-nx, 2026-10-21; was out/tmp/flash.py) <raw rgba 640x360> [threshold]: single- or two-frame flashes: frames that differ from the frames around
them while those agree with each other (a model drawn wrong, missing or black for a frame or two). Prints the frame,
the score and where on screen (the 8x4 grid cells that changed most)."""
import sys

W, H = 640, 360
FS = W * H * 4
path = sys.argv[1]
thr = float(sys.argv[2]) if len(sys.argv) > 2 else 12.0
data = open(path, 'rb').read()
n = len(data) // FS
GX, GY, STEP = 8, 4, 4


def cells(i):
    d = data[i * FS:(i + 1) * FS]
    out = [0.0] * (GX * GY)
    cnt = [0] * (GX * GY)
    for y in range(0, H, STEP):
        row = y * W * 4
        cy = y * GY // H
        for x in range(0, W, STEP):
            p = row + x * 4
            c = cy * GX + x * GX // W
            out[c] += d[p] + d[p + 1] + d[p + 2]
            cnt[c] += 3
    return [o / max(c, 1) for o, c in zip(out, cnt)]


frames = [cells(i) for i in range(n)]
hits = []
for i in range(1, n - 1):
    for span in (1, 2):
        if i + span >= n:
            continue
        a, b, c = frames[i - 1], frames[i], frames[i + span]
        around = [abs(x - z) for x, z in zip(a, c)]
        jump = [min(abs(y - x), abs(y - z)) for x, y, z in zip(a, b, c)]
        score = max(j - 2 * r for j, r in zip(jump, around))
        if score > thr:
            worst = sorted(range(len(jump)), key=lambda k: -(jump[k] - 2 * around[k]))[:3]
            hits.append((i, span, score, worst))
            break
print('%s: %d frames, %d flash frames (threshold %.0f)' % (path, n, len(hits), thr))
for i, span, score, worst in hits[:60]:
    print('  frame %4d (+%d) score %5.1f cells %s' % (i, span, score, ' '.join('%d,%d' % (k % GX, k // GX) for k in worst)))
