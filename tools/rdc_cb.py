# sasrt-nx (2026-10-20, after banjo-nx's rdc_*.py): the pixel (and vertex) shader's constant blocks at an event, as
# float4 rows (run inside qrenderdoc). RDC_IN, RDC_OUT (folder for cb.txt), RDC_EVENT, RDC_ROWS ("a-b;c-d", rows of 16
# bytes per block, default 0-63), RDC_STAGE ("ps" or "vs", default ps).
import os
import struct
import traceback

import renderdoc as rd

IN = os.environ.get("RDC_IN")
OUT = os.environ.get("RDC_OUT")
EVENT = int(os.environ.get("RDC_EVENT", "0"))
ROWS = [tuple(int(v) for v in r.split("-")) for r in os.environ.get("RDC_ROWS", "0-63").split(";") if r]
STAGE = rd.ShaderStage.Vertex if os.environ.get("RDC_STAGE", "ps") == "vs" else rd.ShaderStage.Pixel
log = open(os.path.join(OUT, "cb.txt"), "w")


def say(*parts):
    log.write(" ".join(str(p) for p in parts) + "\n")
    log.flush()


def descs(used):
    return used.descriptors if hasattr(used, "descriptors") else [used.descriptor]


try:
    cap = rd.OpenCaptureFile()
    if cap.OpenFile(IN, "", None) != rd.ResultCode.Succeeded:
        raise RuntimeError("open file")
    result = cap.OpenCapture(rd.ReplayOptions(), None)
    status, controller = result if isinstance(result, tuple) else (rd.ResultCode.Succeeded, result)
    buffers = {b.resourceId: b for b in controller.GetBuffers()}
    controller.SetFrameEvent(EVENT, True)
    state = controller.GetPipelineState()
    try:
        blocks = state.GetConstantBlocks(STAGE, True)
    except TypeError:
        blocks = state.GetConstantBlocks(STAGE)
    for i, used in enumerate(blocks):
        for d in descs(used):
            rid = d.resource
            if rid == rd.ResourceId.Null() or rid not in buffers:
                continue
            say("block %d buffer %d offset 0x%x size 0x%x" % (i, int(rid), d.byteOffset, d.byteSize))
            for a, b in ROWS:
                for r in range(a, b + 1):
                    if r * 16 + 16 > d.byteSize:
                        break
                    data = controller.GetBufferData(rid, d.byteOffset + r * 16, 16)
                    f = struct.unpack("<4f", data)
                    u = struct.unpack("<4I", data)
                    say("   [%3d] %12.6g %12.6g %12.6g %12.6g   %08X %08X %08X %08X" % ((r,) + f + u))
    controller.Shutdown()
    cap.Shutdown()
    say("done")
except Exception:
    say("ERROR", traceback.format_exc())
log.close()
os._exit(0)
