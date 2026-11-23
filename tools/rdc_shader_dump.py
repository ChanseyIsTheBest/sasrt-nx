# sasrt-nx (2026-10-21): a draw's pixel (or vertex) shader disassembly and its constant buffers' contents (run inside
# qrenderdoc). RDC_IN = capture, RDC_OUT = folder for shader.txt, RDC_EVENT, RDC_STAGE = ps (default) or vs.
import os
import traceback

import renderdoc as rd

IN = os.environ.get("RDC_IN")
OUT = os.environ.get("RDC_OUT")
EVENT = int(os.environ.get("RDC_EVENT", "0"))
STAGE = rd.ShaderStage.Vertex if os.environ.get("RDC_STAGE") == "vs" else rd.ShaderStage.Pixel
log = open(os.path.join(OUT, "shader.txt"), "w")


def say(*parts):
    log.write(" ".join(str(p) for p in parts) + "\n")
    log.flush()


try:
    cap = rd.OpenCaptureFile()
    if cap.OpenFile(IN, "", None) != rd.ResultCode.Succeeded:
        raise RuntimeError("open file")
    result = cap.OpenCapture(rd.ReplayOptions(), None)
    status, controller = result if isinstance(result, tuple) else (rd.ResultCode.Succeeded, result)
    controller.SetFrameEvent(EVENT, True)
    state = controller.GetPipelineState()
    refl = state.GetShaderReflection(STAGE)
    pipe = state.GetGraphicsPipelineObject()
    targets = controller.GetDisassemblyTargets(True)
    say("targets", list(targets))
    text = controller.DisassembleShader(pipe, refl, targets[0])
    say(text[:200000])
    for i, cb in enumerate(refl.constantBlocks):
        bound = state.GetConstantBlock(STAGE, i, 0)
        desc = getattr(bound, "descriptor", bound)
        res = getattr(desc, "resource", None)
        off = getattr(desc, "byteOffset", 0)
        size = getattr(desc, "byteSize", 0)
        vars_ = controller.GetCBufferVariableContents(pipe, refl.resourceId, STAGE, refl.entryPoint, i,
                                                      res, off, size)
        say("== constant block", i, cb.name, "variables", len(vars_))

        def show(v, depth=0):
            if v.members:
                for m in v.members[:400]:
                    show(m, depth + 1)
            else:
                vals = [v.value.f32v[k] for k in range(v.columns * max(1, v.rows))]
                if any(abs(x) > 0 for x in vals):
                    say("  " * depth + v.name, ["%.5g" % x for x in vals])
        for v in vars_:
            show(v)
    controller.Shutdown()
    cap.Shutdown()
    say("done")
except Exception:
    say("ERROR", traceback.format_exc())
log.close()
os._exit(0)
