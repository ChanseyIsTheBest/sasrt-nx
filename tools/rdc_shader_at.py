# sasrt-nx (2026-10-20): the shaders of chosen events of a RenderDoc capture, disassembled, and words of chosen buffer
# ranges at those events (run inside qrenderdoc: qrenderdoc.exe --python tools/rdc_shader_at.py). Made for Ryujinx
# captures: its translated SPIR-V shows what became of a guest shader's memory accesses.
#   RDC_IN (capture), RDC_OUT (folder for shader_<event>_<stage>.txt and shader_at.txt), RDC_EVENTS (comma list),
#   RDC_RANGES ("buffer id:offset:words;..." printed at each event, offsets in hex)
import os
import struct
import traceback

import renderdoc as rd

IN = os.environ.get("RDC_IN")
OUT = os.environ.get("RDC_OUT")
EVENTS = [int(e) for e in os.environ.get("RDC_EVENTS", "").split(",") if e.strip()]
RANGES = []
for r in os.environ.get("RDC_RANGES", "").split(";"):
    if r.strip():
        rid, off, n = r.split(":")
        RANGES.append((int(rid), int(off, 16), int(n)))
log = open(os.path.join(OUT, "shader_at.txt"), "w")


def say(*parts):
    log.write(" ".join(str(p) for p in parts) + "\n")
    log.flush()


try:
    cap = rd.OpenCaptureFile()
    if cap.OpenFile(IN, "", None) != rd.ResultCode.Succeeded:
        raise RuntimeError("open file")
    result = cap.OpenCapture(rd.ReplayOptions(), None)
    status, controller = result if isinstance(result, tuple) else (rd.ResultCode.Succeeded, result)
    ids = {int(b.resourceId): b.resourceId for b in controller.GetBuffers()}
    targets = controller.GetDisassemblyTargets(True)
    for event in EVENTS:
        controller.SetFrameEvent(event, True)
        st = controller.GetPipelineState()
        say("event", event)
        for stage, tag in ((rd.ShaderStage.Vertex, "vs"), (rd.ShaderStage.Pixel, "ps"), (rd.ShaderStage.Compute, "cs")):
            refl = st.GetShaderReflection(stage)
            if refl is None:
                continue
            pipe = st.GetComputePipelineObject() if stage == rd.ShaderStage.Compute else st.GetGraphicsPipelineObject()
            text = controller.DisassembleShader(pipe, refl, targets[0])
            path = os.path.join(OUT, "shader_%d_%s.txt" % (event, tag))
            with open(path, "w") as f:
                f.write(text)
            say("  %s shader %d: %d lines -> %s" % (tag, int(refl.resourceId), text.count("\n"), path))
        for rid, off, n in RANGES:
            if rid not in ids:
                say("  no buffer", rid)
                continue
            data = controller.GetBufferData(ids[rid], off, n * 4)
            w = struct.unpack("<%dI" % (len(data) // 4), data[:len(data) // 4 * 4])
            nonzero = sum(1 for v in w if v)
            say("  buf%d+0x%x: %d words, %d non-zero" % (rid, off, len(w), nonzero))
            for i in range(0, min(len(w), 64), 8):
                say("    +0x%04x:" % (off + i * 4), " ".join("%08X" % v for v in w[i:i + 8]))
    controller.Shutdown()
    cap.Shutdown()
    say("done")
except Exception:
    say("ERROR", traceback.format_exc())
log.close()
os._exit(0)
