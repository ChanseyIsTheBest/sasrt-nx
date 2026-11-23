# sasrt-nx (2026-10-21): every use of chosen resources of a RenderDoc capture, by resource id (run inside qrenderdoc).
#   RDC_IN = capture, RDC_OUT = folder for uses.txt, RDC_RESOURCES = "id,id"
# For each use: event, usage kind (ColorTarget, CopyDst, PS_Resource ...) and the action's name.
import os
import traceback

import renderdoc as rd

IN = os.environ.get("RDC_IN")
OUT = os.environ.get("RDC_OUT")
WANT = [int(r) for r in os.environ.get("RDC_RESOURCES", "").replace(";", ",").split(",") if r.strip()]
log = open(os.path.join(OUT, "uses.txt"), "w")


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
    sfile = controller.GetStructuredFile()
    names = {a.eventId: a.GetName(sfile) for a in flatten(controller.GetRootActions(), [])}
    ids = {}
    for r in controller.GetResources():
        ids[int(r.resourceId)] = r
    # RDC_AT = "event,event": every resource used at those events (a copy's source and destination, say).
    at = [int(e) for e in os.environ.get("RDC_AT", "").replace(";", ",").split(",") if e.strip()]
    if at:
        for rid, r in ids.items():
            for u in controller.GetUsage(r.resourceId):
                if u.eventId in at:
                    log.write("   at event %d: resource %d %s %s\n" % (u.eventId, rid, r.name,
                                                                     str(u.usage).replace("ResourceUsage.", "")))
    for want in WANT:
        r = ids.get(want)
        if r is None:
            log.write("resource %d: not found\n" % want)
            continue
        log.write("== resource %d %s\n" % (want, r.name))
        for u in controller.GetUsage(r.resourceId):
            log.write("   event %d %s %s\n" % (u.eventId, str(u.usage).replace("ResourceUsage.", ""),
                                             names.get(u.eventId, "")))
    controller.Shutdown()
    cap.Shutdown()
    log.write("done\n")
except Exception:
    log.write("ERROR " + traceback.format_exc())
log.close()
os._exit(0)
