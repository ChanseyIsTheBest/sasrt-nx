# sasrt-nx (2026-10-20): every use of the buffers whose name holds RDC_NAME, in a RenderDoc capture (run inside
# qrenderdoc): RDC_IN, RDC_OUT (folder for usage.txt), RDC_NAME (a part of the resource name), RDC_KINDS (optional,
# comma separated usage names to keep, e.g. "CS_RWResource,VS_RWResource,CopyDst"). For each use: event, usage, and the
# action's vertex and pixel (or compute) shader names.
import os
import traceback

import renderdoc as rd

IN = os.environ.get("RDC_IN")
OUT = os.environ.get("RDC_OUT")
NAME = os.environ.get("RDC_NAME", "exported")
KINDS = [k for k in os.environ.get("RDC_KINDS", "").split(",") if k]
log = open(os.path.join(OUT, "usage.txt"), "w")


def say(*parts):
    log.write(" ".join(str(p) for p in parts) + "\n")
    log.flush()


try:
    cap = rd.OpenCaptureFile()
    if cap.OpenFile(IN, "", None) != rd.ResultCode.Succeeded:
        raise RuntimeError("open file")
    result = cap.OpenCapture(rd.ReplayOptions(), None)
    status, controller = result if isinstance(result, tuple) else (rd.ResultCode.Succeeded, result)
    names = {int(r.resourceId): r.name for r in controller.GetResources()}
    for r in controller.GetResources():
        if NAME not in r.name:
            continue
        say("resource", int(r.resourceId), r.name)
        for u in controller.GetUsage(r.resourceId):
            kind = str(u.usage).split(".")[-1]
            if KINDS and kind not in KINDS:
                continue
            controller.SetFrameEvent(u.eventId, True)
            st = controller.GetPipelineState()
            shaders = []
            for stage in (rd.ShaderStage.Vertex, rd.ShaderStage.Pixel, rd.ShaderStage.Compute):
                sid = st.GetShader(stage)
                if sid != rd.ResourceId.Null():
                    shaders.append("%s %s" % (str(stage).split(".")[-1], names.get(int(sid), int(sid))))
            say("  event", u.eventId, kind, " ".join(shaders))
    controller.Shutdown()
    cap.Shutdown()
    say("done")
except Exception:
    say("ERROR", traceback.format_exc())
log.close()
os._exit(0)
