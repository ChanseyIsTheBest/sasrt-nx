# sasrt-nx (2026-10-21, after banjo-nx's rdc_mesh.py): a draw's vertex inputs against its vertex shader's output, to
# tell whether vertices that land far off screen were fed wrong data or transformed wrongly (run inside qrenderdoc).
#   RDC_IN = capture, RDC_OUT = folder for inputs.txt, RDC_EVENTS = "event,event"
# For each event: the vertex input layout (attribute, buffer slot, offset, format), the vertex buffers (resource, offset,
# stride, size), the post-VS position range in NDC, and the first vertices whose NDC is beyond +-4 (or w <= 0, or NaN)
# beside a well placed one: each with its index and every attribute decoded from the buffers as the GPU read them.
import math
import os
import struct
import traceback

import renderdoc as rd

IN = os.environ.get("RDC_IN")
OUT = os.environ.get("RDC_OUT")
EVENTS = [int(e) for e in os.environ.get("RDC_EVENTS", "").replace(";", ",").split(",") if e.strip()]
log = open(os.path.join(OUT, "inputs.txt"), "w")


def say(*parts):
    log.write(" ".join(str(p) for p in parts) + "\n")
    log.flush()


def decode(raw, fmt):
    """The attribute's components as the GPU reads them (the formats plume uses for vertex inputs)."""
    name = fmt.Name()
    n = fmt.compCount
    try:
        if "FLOAT" in name and fmt.compByteWidth == 4:
            return struct.unpack_from("%df" % n, raw)
        if "FLOAT" in name and fmt.compByteWidth == 2:
            return struct.unpack_from("%de" % n, raw)
        if fmt.compByteWidth == 2:
            vals = struct.unpack_from("%dh" % n if "SNORM" in name or "SINT" in name else "%dH" % n, raw)
            if "SNORM" in name:
                return tuple(max(v / 32767.0, -1.0) for v in vals)
            if "UNORM" in name:
                return tuple(v / 65535.0 for v in vals)
            return vals
        if fmt.compByteWidth == 1:
            vals = struct.unpack_from("%db" % n if "SNORM" in name or "SINT" in name else "%dB" % n, raw)
            if "SNORM" in name:
                return tuple(max(v / 127.0, -1.0) for v in vals)
            if "UNORM" in name:
                return tuple(v / 255.0 for v in vals)
            return vals
    except struct.error:
        return ("short",)
    return ("?" + name,)


try:
    cap = rd.OpenCaptureFile()
    if cap.OpenFile(IN, "", None) != rd.ResultCode.Succeeded:
        raise RuntimeError("open file")
    result = cap.OpenCapture(rd.ReplayOptions(), None)
    status, controller = result if isinstance(result, tuple) else (rd.ResultCode.Succeeded, result)
    resources = {r.resourceId: r.name for r in controller.GetResources()}
    for event in EVENTS:
        controller.SetFrameEvent(event, True)
        state = controller.GetPipelineState()
        say("== event", event)
        attrs = state.GetVertexInputs()
        vbs = state.GetVBuffers()
        for a in attrs:
            if not a.used:
                continue
            say("   attr %-12s slot %d offset %3d format %s" % (a.name, a.vertexBuffer, a.byteOffset, a.format.Name()))
        buffers = {}
        for i, vb in enumerate(vbs):
            if vb.resourceId == rd.ResourceId.Null():
                continue
            say("   vb%d %s offset %d stride %d size %d" % (i, resources.get(vb.resourceId, str(int(vb.resourceId))),
                                                         vb.byteOffset, vb.byteStride, vb.byteSize))
            buffers[i] = (vb, controller.GetBufferData(vb.resourceId, vb.byteOffset, vb.byteSize))
        ib = state.GetIBuffer()
        say("   ib %s offset %d stride %d" % (resources.get(ib.resourceId, str(int(ib.resourceId))), ib.byteOffset,
                                             ib.byteStride))
        mesh = controller.GetPostVSData(0, 0, rd.MeshDataStage.VSOut)
        if mesh.vertexResourceId == rd.ResourceId.Null():
            say("   no post-VS data")
            continue
        data = controller.GetBufferData(mesh.vertexResourceId, mesh.vertexByteOffset, 0)
        stride = mesh.vertexByteStride
        count = min(len(data) // stride, 65536) if stride else 0
        # Post-VS data is in index order (one entry per index) for indexed draws: the vertex index comes from the
        # index buffer read the same way.
        indices = None
        if mesh.indexResourceId != rd.ResourceId.Null():
            ibytes = controller.GetBufferData(mesh.indexResourceId, mesh.indexByteOffset, 0)
            fmtc = "H" if mesh.indexByteStride == 2 else "I"
            indices = struct.unpack_from("%d%s" % (min(len(ibytes) // mesh.indexByteStride, count), fmtc), ibytes)
        lo = [1e30] * 3
        hi = [-1e30] * 3
        bad, good = [], []
        for v in range(count):
            x, y, z, w = struct.unpack_from("4f", data, v * stride)
            vi = indices[v] if indices and v < len(indices) else v
            if any(math.isnan(c) for c in (x, y, z, w)) or w <= 0:
                bad.append((vi, (x, y, z, w)))
                continue
            ndc = (x / w, y / w, z / w)
            for i in range(3):
                lo[i] = min(lo[i], ndc[i])
                hi[i] = max(hi[i], ndc[i])
            (bad if max(abs(ndc[0]), abs(ndc[1])) > 4 else good).append((vi, (x, y, z, w)))
        say("   post-VS entries", count, "far/bad", len(bad), "ndc x %.2f..%.2f y %.2f..%.2f z %.4f..%.4f"
            % (lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]))
        seen = set()
        shown = 0
        for label, entries in (("good", good[:2]), ("far", bad)):
            for vi, pos in entries:
                if vi in seen:
                    continue
                seen.add(vi)
                say("   %s vertex %d clip (%.4g %.4g %.4g %.4g)" % ((label, vi) + pos))
                for a in attrs:
                    if not a.used or a.vertexBuffer not in buffers:
                        continue
                    vb, raw = buffers[a.vertexBuffer]
                    at = vi * vb.byteStride + a.byteOffset
                    chunk = raw[at:at + 16]
                    words = " ".join("%08X" % w for w in struct.unpack_from("%dI" % (len(chunk) // 4), chunk))
                    say("      %-12s %s  [%s]" % (a.name, " ".join("%.4g" % c if isinstance(c, float) else str(c)
                                                                for c in decode(chunk, a.format)), words))
                if label == "far":
                    shown += 1
                    if shown >= 6:
                        break
    controller.Shutdown()
    cap.Shutdown()
    say("done")
except Exception:
    say("ERROR", traceback.format_exc())
log.close()
os._exit(0)
