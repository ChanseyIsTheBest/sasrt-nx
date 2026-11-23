# sasrt-nx (2026-10-21): every draw of a RenderDoc capture whose vertex shader puts vertices far off screen (|x/w| or
# |y/w| beyond RDC_LIMIT, default 8, with w > 0), the "exploded" meshes (run inside qrenderdoc).
#   RDC_IN = capture, RDC_OUT = folder for exploded.txt, RDC_LIMIT (NDC), RDC_MIN_FAR (far vertices to report, default 3)
# Draws without a depth target (full-screen passes, UI) are skipped. For each reported draw: event, vertex shader
# resource, entries, far count, the vertex buffer strides, and the draw's outputs.
import math
import os
import struct
import traceback

import renderdoc as rd

IN = os.environ.get("RDC_IN")
OUT = os.environ.get("RDC_OUT")
LIMIT = float(os.environ.get("RDC_LIMIT", "8"))
MIN_FAR = int(os.environ.get("RDC_MIN_FAR", "3"))
log = open(os.path.join(OUT, "exploded.txt"), "w")


def say(*parts):
    log.write(" ".join(str(p) for p in parts) + "\n")
    log.flush()


def flatten(actions, out):
    for a in actions:
        out.append(a)
        flatten(a.children, out)
    return out


try:
    cap = rd.OpenCaptureFile()
    if cap.OpenFile(IN, "", None) != rd.ResultCode.Succeeded:
        raise RuntimeError("open file")
    result = cap.OpenCapture(rd.ReplayOptions(), None)
    status, controller = result if isinstance(result, tuple) else (rd.ResultCode.Succeeded, result)
    draws = [a for a in flatten(controller.GetRootActions(), []) if a.flags & rd.ActionFlags.Drawcall]
    checked = reported = 0
    for a in draws:
        if a.depthOut == rd.ResourceId.Null() or a.numIndices < 3:
            continue
        controller.SetFrameEvent(a.eventId, True)
        mesh = controller.GetPostVSData(0, 0, rd.MeshDataStage.VSOut)
        if mesh.vertexResourceId == rd.ResourceId.Null() or not mesh.vertexByteStride:
            continue
        checked += 1
        data = controller.GetBufferData(mesh.vertexResourceId, mesh.vertexByteOffset, 0)
        stride = mesh.vertexByteStride
        count = min(len(data) // stride, 200000)
        far = 0
        worst = 0.0
        for v in range(count):
            x, y, z, w = struct.unpack_from("4f", data, v * stride)
            if w <= 0 or any(math.isnan(c) for c in (x, y, z, w)):
                continue
            m = max(abs(x / w), abs(y / w))
            if m > LIMIT:
                far += 1
                worst = max(worst, m)
        if far >= MIN_FAR:
            reported += 1
            state = controller.GetPipelineState()
            strides = [vb.byteStride for vb in state.GetVBuffers() if vb.resourceId != rd.ResourceId.Null()]
            vs = state.GetShader(rd.ShaderStage.Vertex)
            say("event %d vs %d entries %d far %d (worst ndc %.1f) strides %s outputs %s depth %d"
                % (a.eventId, int(vs), count, far, worst, strides,
                   [int(o) for o in a.outputs if o != rd.ResourceId.Null()], int(a.depthOut)))
    say("checked %d draws with a depth target, %d with %d+ vertices beyond ndc %.0f" % (checked, reported, MIN_FAR, LIMIT))
    controller.Shutdown()
    cap.Shutdown()
except Exception:
    say("ERROR", traceback.format_exc())
log.close()
os._exit(0)
