# sasrt-nx (2026-10-20, after banjo-nx's rdc_*.py): the vertex shader's buffers at chosen draws of a RenderDoc capture
# (run inside qrenderdoc: qrenderdoc.exe --python tools/rdc_vsdata.py). For each event: every constant block and
# read-only buffer the vertex shader uses (resource, offset, size) and its first words; for the block that holds
# Renut's shared constants (RDC_SHARED_WORDS, "start-end" in words, default 140-150 and 243-246) those words too.
#   RDC_IN (capture), RDC_OUT (folder for vsdata.txt), RDC_EVENTS (comma list), RDC_WORDS (words per buffer, default 16)
import os
import struct
import traceback

import renderdoc as rd

IN = os.environ.get("RDC_IN")
OUT = os.environ.get("RDC_OUT")
EVENTS = [int(e) for e in os.environ.get("RDC_EVENTS", "").split(",") if e.strip()]
WORDS = int(os.environ.get("RDC_WORDS", "16"))
RANGES = [tuple(int(v) for v in r.split("-")) for r in os.environ.get("RDC_SHARED_WORDS", "140-150;243-246").split(";")]
log = open(os.path.join(OUT, "vsdata.txt"), "w")


def say(*parts):
    log.write(" ".join(str(p) for p in parts) + "\n")
    log.flush()


def words(controller, rid, offset, count):
    data = controller.GetBufferData(rid, offset, count * 4)
    n = len(data) // 4
    return list(struct.unpack("<%dI" % n, data[:n * 4]))


def descs(used):
    return used.descriptors if hasattr(used, "descriptors") else [used.descriptor]


try:
    cap = rd.OpenCaptureFile()
    if cap.OpenFile(IN, "", None) != rd.ResultCode.Succeeded:
        raise RuntimeError("open file")
    result = cap.OpenCapture(rd.ReplayOptions(), None)
    status, controller = result if isinstance(result, tuple) else (rd.ResultCode.Succeeded, result)
    buffers = {b.resourceId: b for b in controller.GetBuffers()}
    for event in EVENTS:
        controller.SetFrameEvent(event, True)
        state = controller.GetPipelineState()
        say("event", event)
        for stage, tag in ((rd.ShaderStage.Vertex, "vs"), (rd.ShaderStage.Pixel, "ps")):
            try:
                blocks = state.GetConstantBlocks(stage, True)
            except TypeError:
                blocks = state.GetConstantBlocks(stage)
            for i, used in enumerate(blocks):
                for d in descs(used):
                    rid = d.resource
                    if rid == rd.ResourceId.Null() or rid not in buffers:
                        continue
                    say("  %s cb%d buffer %d offset 0x%x size 0x%x" % (tag, i, int(rid), d.byteOffset, d.byteSize))
                    w = words(controller, rid, d.byteOffset, min(WORDS, max(1, d.byteSize // 4)))
                    say("     ", " ".join("%08X" % v for v in w))
                    if tag == "vs" and d.byteSize >= 1024:
                        for a, b in RANGES:
                            w = words(controller, rid, d.byteOffset + a * 4, b - a + 1)
                            say("      words %d-%d:" % (a, b), " ".join("%08X" % v for v in w))
            try:
                ro = state.GetReadOnlyResources(stage, True)
            except TypeError:
                ro = state.GetReadOnlyResources(stage)
            for used in ro:
                for d in descs(used):
                    rid = d.resource
                    if rid == rd.ResourceId.Null() or rid not in buffers:
                        continue
                    off = getattr(d, "byteOffset", 0)
                    size = getattr(d, "byteSize", 0)
                    say("  %s ro buffer %d offset 0x%x size 0x%x (buffer length 0x%x)" % (tag, int(rid), off, size,
                                                                                         buffers[rid].length))
                    w = words(controller, rid, off, WORDS)
                    say("     ", " ".join("%08X" % v for v in w))
    controller.Shutdown()
    cap.Shutdown()
    say("done")
except Exception:
    say("ERROR", traceback.format_exc())
log.close()
os._exit(0)
