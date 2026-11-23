// sasrt-nx (2026-10-20): a RenderDoc capture of one frame at a chosen time, for runs started under RenderDoc
// (tools\win\boot_test.ps1 -RenderDoc). The test runs reach a race a couple of minutes in with the window minimised,
// where Renut presents nothing (no swap chain images): RenderDoc's own frame boundaries never come. So the capture is
// bracketed on Renut's render thread instead: StartFrameCapture queued after one Swap's present work, EndFrameCapture
// after the next Swap's, which holds exactly one frame's work. With the emulated Xenos GPU (direct): called at the Swaps
// themselves (its command processor runs the ring behind them, so about one frame). A diagnostic: nothing happens without the key or without
// RenderDoc in the process. PC only, Renut's renderer only.
#include "sasrt_renderdoc.h"

#include <chrono>

#include <rex/cvar.h>
#include <rex/logging.h>

REXCVAR_DEFINE_INT32(sasrt_renderdoc_capture_s, 0, "SASRT",
                     "Diagnostic (PC, the game started under RenderDoc, sasrt_renderer = renut): seconds after the "
                     "first frame at which RenderDoc captures one frame; 0: never")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_INT32(sasrt_renderdoc_capture_count, 1, "SASRT",
                     "Diagnostic (with sasrt_renderdoc_capture_s): how many frames RenderDoc captures, each its own "
                     "capture, one after the other (2026-10-21: catching a fault that shows in some frames only)")
    .range(1, 64)
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_INT32(sasrt_renderdoc_capture_frame, 0, "SASRT",
                     "Diagnostic (with sasrt_renderdoc_capture_s): after those seconds, also wait for this game frame "
                     "(sasrt_capture's count, as sasrt_video_frame; 2026-10-21: an effect a few frames long, the "
                     "respawn's); 0: none")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_INT32(sasrt_renderdoc_after_wipe, 0, "SASRT",
                     "Diagnostic (with sasrt_renderdoc_capture_s and a video, sasrt_video_s, whose recorder spots the "
                     "game's logo wipe): the captures start this many game frames after the first wipe that ends "
                     "after those seconds (the respawn's); 0: off")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

#if defined(_WIN32) && SASRT_RENUT_RENDERER
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>

#include <algorithm>

#include "../../sdk/thirdparty/renderdoc/renderdoc_app.h"
#include "renut_engine/gpu/backend/render_thread.h"
#include "sasrt_capture.h"  // g_sasrt_game_frames

namespace renut::gpu {
void *SasrtRenderDocDevicePointer();  // backend/backend.cpp
}  // namespace renut::gpu

namespace sasrt::renderdoc {
namespace {

RENDERDOC_API_1_0_1 *Api() {
  static RENDERDOC_API_1_0_1 *api = [] {
    RENDERDOC_API_1_0_1 *a = nullptr;
    HMODULE module = GetModuleHandleA("renderdoc.dll");
    if (!module)
      return a;
    auto get_api = reinterpret_cast<pRENDERDOC_GetAPI>(GetProcAddress(module, "RENDERDOC_GetAPI"));
    if (!get_api || !get_api(eRENDERDOC_API_Version_1_0_1, reinterpret_cast<void **>(&a)))
      a = nullptr;
    return a;
  }();
  return api;
}

// RenderDoc's device for StartFrameCapture / EndFrameCapture (Renut's back end: the Vulkan instance's dispatch
// pointer, without which a capture with nothing presented fails; null on D3D12).
void *DevicePointer() { return renut::gpu::SasrtRenderDocDevicePointer(); }

}  // namespace

void AfterSwap(bool direct) {
  static const int32_t at = REXCVAR_GET(sasrt_renderdoc_capture_s);
  if (at <= 0)
    return;
  static const auto start = std::chrono::steady_clock::now();
  static int stage = 0;  // 0 waiting, 1 started, 2 done
  if (stage == 2 || (stage == 0 && std::chrono::steady_clock::now() - start < std::chrono::seconds(at)))
    return;
  static const uint64_t at_frame = uint64_t(std::max(0, REXCVAR_GET(sasrt_renderdoc_capture_frame)));
  if (stage == 0 && g_sasrt_game_frames.load(std::memory_order_relaxed) < at_frame)
    return;
  // sasrt_renderdoc_after_wipe: a logo wipe that ends after the seconds above, then that many frames.
  if (static const int32_t after = REXCVAR_GET(sasrt_renderdoc_after_wipe); stage == 0 && after > 0) {
    static const uint64_t before = g_sasrt_wipe_end_frame.load(std::memory_order_relaxed);
    const uint64_t end = g_sasrt_wipe_end_frame.load(std::memory_order_relaxed);
    if (end == before || g_sasrt_game_frames.load(std::memory_order_relaxed) + 1 < end + uint64_t(after))
      return;
  }
  RENDERDOC_API_1_0_1 *api = Api();
  if (!api) {
    REXLOG_WARN("[renderdoc] sasrt_renderdoc_capture_s: RenderDoc is not in the process");
    stage = 2;
    return;
  }
  static int32_t left = REXCVAR_GET(sasrt_renderdoc_capture_count);  // captures still to take
  auto begin_capture = [api] {
    api->StartFrameCapture(DevicePointer(), nullptr);
    REXLOG_INFO("[renderdoc] capture started (game frame {})", g_sasrt_game_frames.load(std::memory_order_relaxed));
  };
  auto end_capture = [api] {
    const uint32_t ok = api->EndFrameCapture(DevicePointer(), nullptr);
    REXLOG_INFO("[renderdoc] capture ended ({})", ok ? "written" : "failed");
  };
  auto run = [direct](auto f) {
    if (direct)
      f();
    else
      renut::gpu::render_thread::Queue(f);
  };
  if (stage == 0) {
    stage = 1;
    run(begin_capture);
  } else {
    // The next capture starts right after (consecutive frames, sasrt_renderdoc_capture_count), or none.
    run(end_capture);
    if (--left > 0)
      run(begin_capture);
    else
      stage = 2;
  }
}

}  // namespace sasrt::renderdoc
#else
namespace sasrt::renderdoc {
void AfterSwap(bool) {}
}  // namespace sasrt::renderdoc
#endif
