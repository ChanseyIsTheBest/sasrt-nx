# sasrt-nx (2026-10-20): the vertex and index buffers a draw reads in a RenderDoc capture (run inside qrenderdoc):
#   RDC_IN = capture, RDC_OUT = folder for buffers.txt, RDC_EVENTS = "event;event"
# Each buffer by its resource name (Renut names its upload rings, stream cache pool chunks and so on), offset, stride.
import os
import traceback

import renderdoc as rd

IN = os.environ.get("RDC_IN")
OUT = os.environ.get("RDC_OUT")
EVENTS = [int(v) for v in os.environ.get("RDC_EVENTS", "").split(";") if v]
log = open(os.path.join(OUT, "buffers.txt"), "w")


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
    for event in EVENTS:
        controller.SetFrameEvent(event, True)
        st = controller.GetPipelineState()
        say("event", event)
        ib = st.GetIBuffer()
        say("  index", names.get(int(ib.resourceId), int(ib.resourceId)), "offset", ib.byteOffset, "stride",
            ib.byteStride)
        for i, vb in enumerate(st.GetVBuffers()):
            if vb.resourceId == rd.ResourceId.Null():
                continue
            say("  vertex", i, names.get(int(vb.resourceId), int(vb.resourceId)), "offset", vb.byteOffset, "stride",
                vb.byteStride, "size", vb.byteSize)
        for a in st.GetVertexInputs():
            say("  input", a.name, "buffer", a.vertexBuffer, "offset", a.byteOffset, a.format.Name())
    controller.Shutdown()
    cap.Shutdown()
    say("done")
except Exception:
    say("ERROR", traceback.format_exc())
log.close()
os._exit(0)
