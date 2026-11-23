# sasrt-nx (2026-10-21): one draw's state in a RenderDoc capture (run inside qrenderdoc): its shaders (names), blend
# state, targets and their formats, pixel shader resources, vertex inputs, and the first vertices' input values.
#   RDC_IN = capture, RDC_OUT = folder for state.txt, RDC_EVENT = the event
import os
import struct
import traceback

import renderdoc as rd

IN = os.environ.get("RDC_IN")
OUT = os.environ.get("RDC_OUT")
EVENT = int(os.environ.get("RDC_EVENT", "0"))
log = open(os.path.join(OUT, "state.txt"), "w")


def say(*parts):
    log.write(" ".join(str(p) for p in parts) + "\n")
    log.flush()


try:
    cap = rd.OpenCaptureFile()
    if cap.OpenFile(IN, "", None) != rd.ResultCode.Succeeded:
        raise RuntimeError("open file")
    result = cap.OpenCapture(rd.ReplayOptions(), None)
    status, controller = result if isinstance(result, tuple) else (rd.ResultCode.Succeeded, result)
    names = {r.resourceId: r.name for r in controller.GetResources()}
    textures = {t.resourceId: t for t in controller.GetTextures()}
    controller.SetFrameEvent(EVENT, True)
    state = controller.GetPipelineState()
    for stage in (rd.ShaderStage.Vertex, rd.ShaderStage.Pixel):
        sid = state.GetShader(stage)
        say("shader", str(stage), int(sid), names.get(sid, ""))
        refl = state.GetShaderReflection(stage)
        if refl:
            say("   entry", refl.entryPoint, "debug files", len(refl.debugInfo.files))
    for i, o in enumerate(state.GetOutputTargets()):
        rid = o.resource if hasattr(o, "resource") else o.resourceId
        if rid != rd.ResourceId.Null():
            t = textures.get(rid)
            say("target", i, int(rid), names.get(rid, ""), "%dx%d %s" % (t.width, t.height, t.format.Name()) if t else "")
    try:
        cb = state.GetColorBlends()
        for i, b in enumerate(cb[:2]):
            say("blend", i, "enabled", b.enabled, "color", str(b.colorBlend.source), str(b.colorBlend.operation),
                str(b.colorBlend.destination), "alpha", str(b.alphaBlend.source), str(b.alphaBlend.operation),
                str(b.alphaBlend.destination), "mask", b.writeMask)
    except Exception as e:
        say("blend: n/a", e)
    for used in state.GetReadOnlyResources(rd.ShaderStage.Pixel, True):
        res = getattr(used, "descriptor", None)
        rid = res.resource if res is not None else None
        if rid is None or rid == rd.ResourceId.Null():
            continue
        t = textures.get(rid)
        say("ps resource", int(rid), names.get(rid, ""), "%dx%d %s" % (t.width, t.height, t.format.Name()) if t else "")
    attrs = [a for a in state.GetVertexInputs() if a.used]
    vbs = state.GetVBuffers()
    for a in attrs:
        say("input", a.name, "slot", a.vertexBuffer, "offset", a.byteOffset, a.format.Name())
    a0 = controller.GetDrawcall(EVENT) if hasattr(controller, "GetDrawcall") else None
    for a in attrs:
        vb = vbs[a.vertexBuffer]
        data = controller.GetBufferData(vb.resourceId, vb.byteOffset, vb.byteStride * 4 + 64)
        vals = []
        for v in range(4):
            at = v * vb.byteStride + a.byteOffset
            n = a.format.compCount
            if a.format.compType == rd.CompType.Float and a.format.compByteWidth == 4 and at + 4 * n <= len(data):
                vals.append(tuple(round(x, 4) for x in struct.unpack_from("%df" % n, data, at)))
            elif at + 4 <= len(data):
                vals.append(data[at:at + 4 * max(1, n * a.format.compByteWidth // 4)].hex())
        say("   values", a.name, vals)
    controller.Shutdown()
    cap.Shutdown()
    say("done")
except Exception:
    say("ERROR", traceback.format_exc())
log.close()
os._exit(0)
