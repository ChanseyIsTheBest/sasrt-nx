# sasrt-nx (2026-10-21): the draws that wrote one pixel of a colour target, in order (run inside qrenderdoc), to find
# which draw puts a wrong colour somewhere (the respawn's dark blocky cloud).
#   RDC_IN = capture, RDC_OUT = folder for history.txt, RDC_X / RDC_Y = the pixel in the target's own coordinates,
#   RDC_SIZE = "WxH" of the target (default 1152x544, the race's scene): the target written last at that size is used.
# For each modification: event, the colour before and after, whether the shader's output passed, and for the draws
# that changed it most the bound vertex / pixel shaders and the pixel shader's textures (resource, size, format).
import os
import traceback

import renderdoc as rd

IN = os.environ.get("RDC_IN")
OUT = os.environ.get("RDC_OUT")
X = int(os.environ.get("RDC_X", "576"))
Y = int(os.environ.get("RDC_Y", "400"))
want_w, want_h = (int(v) for v in os.environ.get("RDC_SIZE", "1152x544").lower().split("x"))
log = open(os.path.join(OUT, "history.txt"), "w")


def say(*parts):
    log.write(" ".join(str(p) for p in parts) + "\n")
    log.flush()


def flatten(actions, out):
    for a in actions:
        out.append(a)
        flatten(a.children, out)
    return out


def col(v):
    return "(%.3g %.3g %.3g %.3g)" % tuple(v.floatValue[:4])


try:
    cap = rd.OpenCaptureFile()
    if cap.OpenFile(IN, "", None) != rd.ResultCode.Succeeded:
        raise RuntimeError("open file")
    result = cap.OpenCapture(rd.ReplayOptions(), None)
    status, controller = result if isinstance(result, tuple) else (rd.ResultCode.Succeeded, result)
    textures = {t.resourceId: t for t in controller.GetTextures()}
    draws = [a for a in flatten(controller.GetRootActions(), []) if a.flags & rd.ActionFlags.Drawcall]
    # The target of that size that most draws write (the scene, not the last full-screen pass), or RDC_TARGET.
    counts = {}
    for a in draws:
        for o in a.outputs:
            t = textures.get(o)
            if t and t.width == want_w and t.height == want_h:
                counts[o] = counts.get(o, 0) + 1
    target = None
    if os.environ.get("RDC_TARGET"):
        target = next((r for r in counts if int(r) == int(os.environ["RDC_TARGET"])), None)
    if target is None and counts:
        target = max(counts, key=counts.get)
    if target is None:
        raise RuntimeError("no %dx%d target" % (want_w, want_h))
    say("target", int(target), "pixel", X, Y)
    sub = rd.Subresource(0, 0, 0)
    history = controller.PixelHistory(target, X, Y, sub, rd.CompType.Typeless)
    biggest = []
    for m in history:
        pre, post = m.preMod.col, m.postMod.col
        change = sum(abs(a - b) for a, b in zip(pre.floatValue[:3], post.floatValue[:3]))
        flags = []
        if m.shaderDiscarded:
            flags.append("discarded")
        if m.depthTestFailed:
            flags.append("depth failed")
        if m.backfaceCulled:
            flags.append("culled")
        say("event %d prim %d: %s -> %s, shader out %s %s" % (m.eventId, m.primitiveID, col(pre), col(post),
                                                            col(m.shaderOut.col), " ".join(flags)))
        if not flags:
            biggest.append((change, m.eventId))
    for change, event in sorted(biggest, reverse=True)[:6]:
        controller.SetFrameEvent(event, True)
        state = controller.GetPipelineState()
        vs = state.GetShader(rd.ShaderStage.Vertex)
        ps = state.GetShader(rd.ShaderStage.Pixel)
        texs = []
        for used in state.GetReadOnlyResources(rd.ShaderStage.Pixel, True):
            res = getattr(used, "descriptor", None)
            rid = res.resource if res is not None else None
            if rid is None or rid == rd.ResourceId.Null():
                continue
            t = textures.get(rid)
            texs.append("%d %s" % (int(rid), "%dx%d fmt %s" % (t.width, t.height, t.format.Name()) if t else ""))
        say("== event %d (change %.3g): vs %d ps %d, pixel shader resources: %s" % (event, change, int(vs), int(ps),
                                                                                "; ".join(texs) or "none"))
    controller.Shutdown()
    cap.Shutdown()
    say("done")
except Exception:
    say("ERROR", traceback.format_exc())
log.close()
os._exit(0)
