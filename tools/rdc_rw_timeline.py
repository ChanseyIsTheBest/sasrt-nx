# sasrt-nx (2026-10-20, after banjo-nx's rdc_*.py): the buffer writes of shaders in a RenderDoc capture and the draws that
# read what they wrote as vertices (run inside qrenderdoc: qrenderdoc.exe --python tools/rdc_rw_timeline.py). Made for
# captures of Ryujinx, whose resources carry no names of ours: a memexport draw is a vertex shader with a writable
# storage buffer, a stream conversion a dispatch with one, and a skinned draw one whose vertex buffer range overlaps
# bytes a writer wrote earlier in the frame.
#   RDC_IN (capture), RDC_OUT (folder for rw_timeline.txt), RDC_WORDS (words to print of each written range, default 8)
import os
import struct
import traceback

import renderdoc as rd

IN = os.environ.get("RDC_IN")
OUT = os.environ.get("RDC_OUT")
WORDS = int(os.environ.get("RDC_WORDS", "8"))
log = open(os.path.join(OUT, "rw_timeline.txt"), "w")


def say(*parts):
    log.write(" ".join(str(p) for p in parts) + "\n")
    log.flush()


def descs(used):
    return used.descriptors if hasattr(used, "descriptors") else [used.descriptor]


def flatten(actions):
    for a in actions:
        yield a
        yield from flatten(a.children)


def rw_buffers(state, stage, buffers):
    try:
        rw = state.GetReadWriteResources(stage, True)
    except TypeError:
        rw = state.GetReadWriteResources(stage)
    out = []
    for used in rw:
        for d in descs(used):
            rid = d.resource
            if rid == rd.ResourceId.Null() or rid not in buffers:
                continue
            size = getattr(d, "byteSize", 0) or buffers[rid].length
            out.append((rid, getattr(d, "byteOffset", 0), size))
    return out


def words(controller, rid, offset, count):
    data = controller.GetBufferData(rid, offset, count * 4)
    n = len(data) // 4
    return list(struct.unpack("<%dI" % n, data[:n * 4]))


try:
    cap = rd.OpenCaptureFile()
    if cap.OpenFile(IN, "", None) != rd.ResultCode.Succeeded:
        raise RuntimeError("open file")
    result = cap.OpenCapture(rd.ReplayOptions(), None)
    status, controller = result if isinstance(result, tuple) else (rd.ResultCode.Succeeded, result)
    buffers = {b.resourceId: b for b in controller.GetBuffers()}
    written = []  # (event, rid, offset, size, kind)
    for a in flatten(controller.GetRootActions()):
        is_draw = bool(a.flags & rd.ActionFlags.Drawcall)
        is_dispatch = bool(a.flags & rd.ActionFlags.Dispatch)
        if not (is_draw or is_dispatch):
            continue
        controller.SetFrameEvent(a.eventId, True)
        st = controller.GetPipelineState()
        if is_dispatch:
            rws = [("cs", r) for r in rw_buffers(st, rd.ShaderStage.Compute, buffers)]
        else:
            rws = [("vs", r) for r in rw_buffers(st, rd.ShaderStage.Vertex, buffers)]
            rws += [("ps", r) for r in rw_buffers(st, rd.ShaderStage.Pixel, buffers)]
        vs = st.GetShader(rd.ShaderStage.Compute if is_dispatch else rd.ShaderStage.Vertex)
        head = "event %d %s shader %d idx %d inst %d" % (a.eventId, "dispatch" if is_dispatch else "draw", int(vs),
                                                         a.numIndices, a.numInstances)
        if rws:
            say(head, "WRITES", " ".join("%s:buf%d+0x%x/0x%x" % (k, int(r[0]), r[1], r[2]) for k, r in rws))
            for k, r in rws:
                written.append((a.eventId, r[0], r[1], r[2], k))
                say("    after:", " ".join("%08X" % v for v in words(controller, r[0], r[1], min(WORDS, r[2] // 4))))
        if is_draw:
            hits = []
            for i, vb in enumerate(st.GetVBuffers()):
                if vb.resourceId == rd.ResourceId.Null():
                    continue
                lo = vb.byteOffset
                hi = lo + (vb.byteSize if vb.byteSize else buffers[vb.resourceId].length - lo)
                for ev, rid, off, size, kind in written:
                    if rid == vb.resourceId and lo < off + size and off < hi:
                        hits.append("vb%d buf%d+0x%x/0x%x stride %d <- %s@%d" % (i, int(rid), lo, hi - lo,
                                                                              vb.byteStride, kind, ev))
            if hits:
                say(head, "READS", "; ".join(hits[:4]), "(%d)" % len(hits) if len(hits) > 4 else "")
    controller.Shutdown()
    cap.Shutdown()
    say("done")
except Exception:
    say("ERROR", traceback.format_exc())
log.close()
os._exit(0)
