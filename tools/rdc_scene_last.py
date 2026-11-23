# sasrt-nx (2026-10-21, from banjo-nx's rdc_last.py): saves the colour target of the last draw into a target of the
# given size (the scene, not the larger shadow map rdc_last.py picks), to see which frame a capture caught (run inside
# qrenderdoc, like rdc_passes.py).
#   RDC_IN = capture, RDC_OUT = PNG path, RDC_SIZE = "WxH" (default 1152x544, the race's scene). Writes <RDC_OUT>.txt
#   with the event id, the target and the number of draws into targets of that size.
import os
import traceback

import renderdoc as rd

IN = os.environ.get("RDC_IN")
OUT = os.environ.get("RDC_OUT")
SIZE = os.environ.get("RDC_SIZE", "1152x544")
want_w, want_h = (int(v) for v in SIZE.lower().split("x"))
log = open(OUT + ".txt", "w")


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
    textures = {t.resourceId: t for t in controller.GetTextures()}
    last = None
    draws = 0
    for a in flatten(controller.GetRootActions(), []):
        if not (a.flags & rd.ActionFlags.Drawcall):
            continue
        o = a.outputs[0] if len(a.outputs) else rd.ResourceId.Null()
        t = textures.get(o)
        if t is None or t.width != want_w or t.height != want_h:
            continue
        if t.format.compCount == 1:
            continue  # a single-channel target (depth words, luminance), not the picture
        draws += 1
        last = (a.eventId, o)
    if last:
        controller.SetFrameEvent(last[0], True)
        s = rd.TextureSave()
        s.resourceId = last[1]
        s.destType = rd.FileType.PNG
        s.alpha = rd.AlphaMapping.Discard
        controller.SaveTexture(s, OUT)
        t = textures[last[1]]
        log.write("event %d target %d %dx%d %s, %d draws into %s targets\n"
                  % (last[0], int(last[1]), t.width, t.height, t.format.Name(), draws, SIZE))
    controller.Shutdown()
    cap.Shutdown()
    log.write("done\n")
except Exception:
    log.write("ERROR " + traceback.format_exc())
log.close()
os._exit(0)
