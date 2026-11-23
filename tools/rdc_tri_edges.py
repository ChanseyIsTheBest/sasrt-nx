# sasrt-nx (2026-10-21): the triangles of chosen draws by edge length in the vertex input positions (attribute 0, float3),
# to tell a mesh fed mismatched vertices (long thin spikes: a few huge triangles among small ones) from a sound one
# (run inside qrenderdoc). RDC_IN = capture, RDC_OUT = folder for edges.txt, RDC_EVENTS = "event,event".
# For each event: index and vertex counts, the median and 99th-percentile longest edge, the triangles over 20x the
# median (count), and the five longest with their indices and positions.
import math
import os
import struct
import traceback

import renderdoc as rd

IN = os.environ.get("RDC_IN")
OUT = os.environ.get("RDC_OUT")
EVENTS = [int(e) for e in os.environ.get("RDC_EVENTS", "").replace(";", ",").split(",") if e.strip()]
log = open(os.path.join(OUT, "edges.txt"), "w")


def say(*parts):
    log.write(" ".join(str(p) for p in parts) + "\n")
    log.flush()


try:
    cap = rd.OpenCaptureFile()
    if cap.OpenFile(IN, "", None) != rd.ResultCode.Succeeded:
        raise RuntimeError("open file")
    result = cap.OpenCapture(rd.ReplayOptions(), None)
    status, controller = result if isinstance(result, tuple) else (rd.ResultCode.Succeeded, result)
    actions = {}

    def walk(list_):
        for a in list_:
            actions[a.eventId] = a
            walk(a.children)
    walk(controller.GetRootActions())
    # RDC_INDICES = "n": every draw with that many indices as well (the same mesh in another capture).
    if os.environ.get("RDC_INDICES"):
        want = int(os.environ["RDC_INDICES"])
        EVENTS += [e for e, a in sorted(actions.items())
                   if (a.flags & rd.ActionFlags.Drawcall) and a.numIndices == want and e not in EVENTS]
    for event in EVENTS:
        a = actions.get(event)
        controller.SetFrameEvent(event, True)
        state = controller.GetPipelineState()
        attrs = [x for x in state.GetVertexInputs() if x.used]
        pos = attrs[0]
        vbs = state.GetVBuffers()
        vb = vbs[pos.vertexBuffer]
        ib = state.GetIBuffer()
        n = a.numIndices
        isize = ib.byteStride or 2
        ibytes = controller.GetBufferData(ib.resourceId, ib.byteOffset + a.indexOffset * isize, n * isize)
        indices = struct.unpack_from("%d%s" % (n, "H" if isize == 2 else "I"), ibytes)
        base = a.baseVertex
        hi = max(indices) + base + 1
        raw = controller.GetBufferData(vb.resourceId, vb.byteOffset, hi * vb.byteStride + 16)

        def p(i):
            at = (i + base) * vb.byteStride + pos.byteOffset
            return struct.unpack_from("3f", raw, at) if at + 12 <= len(raw) else (float("nan"),) * 3

        tris = []
        for t in range(0, n - 2, 3):
            i0, i1, i2 = indices[t:t + 3]
            a0, a1, a2 = p(i0), p(i1), p(i2)
            e = max(math.dist(a0, a1), math.dist(a1, a2), math.dist(a2, a0))
            tris.append((e, (i0, i1, i2), (a0, a1, a2)))
        lengths = sorted(t[0] for t in tris if not math.isnan(t[0]))
        if not lengths:
            say("== event", event, "no triangles")
            continue
        med = lengths[len(lengths) // 2]
        p99 = lengths[int(len(lengths) * 0.99)]
        big = sum(1 for e in lengths if e > 20 * med)
        say("== event %d: %d indices, base vertex %d, index offset %d, vertices to %d; median edge %.3g, 99th %.3g, "
            "max %.3g; %d triangles over 20x the median" % (event, n, base, a.indexOffset, hi, med, p99, lengths[-1], big))
        for e, idx, ps in sorted(tris, key=lambda t: -t[0] if not math.isnan(t[0]) else 0)[:5]:
            say("   edge %.3g indices %s positions %s" % (e, idx, " ".join("(%.3g %.3g %.3g)" % q for q in ps)))
    controller.Shutdown()
    cap.Shutdown()
    say("done")
except Exception:
    say("ERROR", traceback.format_exc())
log.close()
os._exit(0)
