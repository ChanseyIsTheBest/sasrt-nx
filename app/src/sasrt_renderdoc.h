// sasrt-nx (2026-10-20): RenderDoc capture at a chosen time (sasrt_renderdoc_capture_s; sasrt_renderdoc.cpp).
#pragma once

namespace sasrt::renderdoc {
// After each D3DDevice_Swap (its present work queued): starts the capture once its time has come, ends it a Swap later.
// direct: the calls at once (the emulated GPU), else queued on Renut's render thread.
void AfterSwap(bool direct = false);
}  // namespace sasrt::renderdoc
