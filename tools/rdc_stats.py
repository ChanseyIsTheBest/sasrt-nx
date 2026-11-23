# sasrt-nx (2026-10-20, after banjo-nx's rdc_*.py): value statistics of chosen textures of a RenderDoc capture at an
# event (run inside qrenderdoc: qrenderdoc.exe --python tools/rdc_stats.py). For float (16/32-bit) and 8-bit unorm
# textures: per channel the mean and the 1/50/99th percentiles of level 0, and the value at chosen texels.
#   RDC_IN, RDC_OUT (folder for stats.txt), RDC_TEXTURES ("id;id"), RDC_EVENT, RDC_TEXELS ("x,y;x,y", optional)
import os
import struct
import traceback

import renderdoc as rd

IN = os.environ.get("RDC_IN")
OUT = os.environ.get("RDC_OUT")
IDS = [int(v) for v in os.environ.get("RDC_TEXTURES", "").split(";") if v]
EVENT = int(os.environ.get("RDC_EVENT", "0"))
TEXELS = [tuple(int(c) for c in p.split(",")) for p in os.environ.get("RDC_TEXELS", "").split(";") if p.strip()]
log = open(os.path.join(OUT, "stats.txt"), "w")


def say(*parts):
    log.write(" ".join(str(p) for p in parts) + "\n")
    log.flush()


def decode(fmt, data):
    name = fmt.Name()
    if "R16G16B16A16_FLOAT" in name:
        n = len(data) // 2
        return 4, struct.unpack("<%de" % n, data[:n * 2])
    if "R32_FLOAT" in name:
        n = len(data) // 4
        return 1, struct.unpack("<%df" % n, data[:n * 4])
    if "R8G8B8A8" in name or "B8G8R8A8" in name:
        return 4, [b / 255.0 for b in data]
    if "R16G16B16A16_TYPELESS" in name or "R16G16B16A16_SNORM" in name:
        n = len(data) // 2
        return 4, [max(v / 32767.0, -1.0) for v in struct.unpack("<%dh" % n, data[:n * 2])]
    return 0, []


try:
    cap = rd.OpenCaptureFile()
    if cap.OpenFile(IN, "", None) != rd.ResultCode.Succeeded:
        raise RuntimeError("open file")
    result = cap.OpenCapture(rd.ReplayOptions(), None)
    status, controller = result if isinstance(result, tuple) else (rd.ResultCode.Succeeded, result)
    textures = {int(t.resourceId): t for t in controller.GetTextures()}
    if EVENT:
        controller.SetFrameEvent(EVENT, True)
    for tid in IDS:
        t = textures.get(tid)
        if not t:
            say(tid, "no such texture")
            continue
        sub = rd.Subresource(0, 0, 0)
        data = controller.GetTextureData(t.resourceId, sub)
        comps, values = decode(t.format, data)
        say(tid, "%dx%d %s" % (t.width, t.height, t.format.Name()), "bytes", len(data))
        if not comps:
            say("   format not decoded")
            continue
        for c in range(comps):
            ch = sorted(values[c::comps])
            if not ch:
                continue
            mean = sum(ch) / len(ch)
            pick = lambda q: ch[min(len(ch) - 1, int(q * len(ch)))]  # noqa: E731
            say("   channel %d: mean %.4f  p1 %.4f  p50 %.4f  p99 %.4f  max %.4f" % (c, mean, pick(0.01), pick(0.5),
                                                                                    pick(0.99), ch[-1]))
        for (x, y) in TEXELS:
            if x < t.width and y < t.height:
                i = (y * t.width + x) * comps
                say("   texel %d,%d:" % (x, y), " ".join("%.4f" % v for v in values[i:i + comps]))
    controller.Shutdown()
    cap.Shutdown()
    say("done")
except Exception:
    say("ERROR", traceback.format_exc())
log.close()
os._exit(0)
