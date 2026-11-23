// sasrt-nx (2026-10-20): Renut's renderer for what this game does and Sonic Adventure 2 does not, around the game's
// own Direct3D (sa2-nx's hybrid route, tools/renut_from_sa2.py; docs/deko3d-renderer.md):
//
//  - Recorded command buffers. The game records parts of its frame on a second drawing thread
//    (D3DDevice_BeginCommandBuffer .. EndCommandBuffer) and runs them on the title device, many times
//    (D3DDevice_RunCommandBuffer; one ran 17,719 times in 170 s of a race). Renut keeps the draws, clears and resolves
//    of a recording device with the device state they read (guest/command_buffers.h: the draw hooks ask
//    IsRecordingCommandBuffer, which reads the device's command buffer field the game's own BeginCommandBuffer
//    writes, +13920), and replays them when a buffer runs. Here: the recording starts after the original Begin, and a
//    run is queued (or, on a recording device, recorded) before the original Run, whose packets nothing reads.
//  - Predicated tiling. Between D3DDevice_BeginTiling and EndTiling the game binds tile-sized surfaces and draws once
//    for every tile; Renut backs the bound surfaces with targets covering every tile (SetTilingExtentLocked) and
//    clears each tile (SetTilesLocked). The tiling clear and the per-tile resolves of the game's own BeginTiling and
//    EndTiling go through Renut's hooked ClearF (sub_82CE7038) and resolve entry (sub_82CDCC98) themselves.
//
// Addresses: app/config/renut_gpu_funcs.toml (this game's map of Renut's names). Credit reNut and masterspike52.
#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cmath>  // sasrt-nx (2026-11-19): SasrtCameraDistance
#include <deque>
#include <mutex>
#include <unordered_map>
#include <string>
#include <vector>

#include <fmt/format.h>

#include <rex/cvar.h>
#include <rex/hook.h>
#include <rex/ppc.h>
#include <rex/types.h>
#include <rex/platform.h>
#if !REX_PLATFORM_SWITCH
#include <rex/system/kernel_state.h>
#include <rex/system/xmemory.h>
#endif
#include <cstring>

#include "renut_engine/gpu/backend/queued.h"
#include "renut_engine/gpu/backend/render_thread.h"
#include "renut_engine/gpu/backend/video.h"
#include "renut_engine/gpu/banjo_renut_select.h"
#include "renut_engine/gpu/guest/callbacks.h"
#include "renut_engine/gpu/guest/command_buffers.h"
#include "renut_engine/gpu/guest/guest_memory.h"
#include "renut_engine/sasrt_trace.h"  // sasrt-nx (2026-11-08, sasrt_renut_diag_trace)
#include "renut_engine/gpu/guest/guest_records.h"
#include "renut_engine/gpu/guest/resources.h"
#include "renut_engine/gpu/log.h"
#include "renut_engine/gpu/render/draw.h"
#include "renut_engine/gpu/render/surfaces.h"

namespace renut::gpu {
std::string SasrtSlotTimingReport();  // sasrt-nx (2026-11-10): command_buffers.cpp
}  // namespace renut::gpu

using namespace renut::gpu;

namespace {

// Diagnostic counts, one [renut] line every 10 s (the tiling and command-buffer paths of this game).
std::atomic<uint64_t> g_begin_tiling{0}, g_begin_cb{0}, g_run_queued{0}, g_run_recorded{0};
std::atomic<uint64_t> g_composed_runs{0}, g_composed_submits{0}, g_submits{0};
std::atomic<uint64_t> g_composed_range_matches{0};
// sasrt-nx (2026-11-04, sasrt_renut_splice_ended): at the splices, recordings taken ended / left for still being
// recorded / left for taken before and not recorded again / none; at the recordings' ends, splices resolved (left
// before) / replaced (taken before, ended again); at the submissions, splices still unresolved (taken as they are
// then, as before).
std::atomic<uint64_t> g_splice_ended{0}, g_splice_in_progress{0}, g_splice_taken_before{0}, g_splice_none{0};
// sasrt-nx (2026-11-08, sasrt_renut_scene_same_frame): places opened at submissions, filled by splices, splices unmatched.
std::atomic<uint64_t> g_slot_opened{0}, g_slot_spliced{0}, g_slot_unmatched{0};
std::atomic<uint64_t> g_splice_resolved{0}, g_splice_replaced{0}, g_splice_at_submit{0};
// sasrt-nx (2026-11-04, sasrt_renut_diag_splice_pm4): spliced buffers whose PM4 was searched, those where the
// c128-c131 packets were found, and those whose values differed at the submission (Direct3D patched them).
std::atomic<uint64_t> g_pm4_checked{0}, g_pm4_found{0}, g_pm4_differ{0}, g_pm4_logged{0};
bool DiagSplicePm4On();
bool SpliceEndedOn();
void SasrtRecordingEnded(u32 command_buffer_va);
void SasrtSplitPlaceEnded(u32 command_buffer_va);  // sasrt-nx (2026-11-19, sasrt_renut_split_scene 2)

}  // namespace
REXCVAR_DEFINE_BOOL(sasrt_renut_run_at_splice, false, "SASRT",
                    "Renut's renderer: a composed command buffer's recorded buffers run where they are spliced "
                    "(sub_82CEF770), not at the composed buffer's ring submission, which some frames send by a path "
                    "the hooks do not see. A test (2026-10-21): it puts the worker's scene pass before the title device clears its "
                    "targets, and every frame lost it")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_renut_pool_wrap_run, true, "SASRT",
                    "Renut's renderer: at a composed command buffer pool's wrap (every ~63 frames), the game submits "
                    "a padding segment where the last spliced composed buffer should go; its recorded buffers (a "
                    "worker's scene pass) run there. Off: that frame loses its scene (the race's \"ocean\" frames, "
                    "the menus' vanishing islands and models)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
// sasrt-nx (2026-11-04, the far-cascade shadow flicker). A composed buffer's splice (sub_82CEF770) took each recorded
// buffer's recording as it was at that moment (the 2026-10-21 "ocean" fix: at the submission a worker could already be
// recording the next frame's). But the worker's shadow pass may not have been recorded yet at the splice either: the
// main thread lays the frame's composed buffer out while the worker fills the buffers it names, and the 360's GPU reads
// them only at the submission. Taken at the splice, such a buffer's recording was the previous frame's (ended, whole)
// or a partial one, and the shadow atlas was drawn with the previous frame's matrices while the mask pass had this
// frame's: the ground shadowed itself in solid patches (newlogs11 w4 f2661; docs/enhancements.md). Now a recording is
// taken only once the game's EndCommandBuffer has run for it; one still being recorded is taken at that End, and a
// recording ended after the splice but before the segment's submission replaces the one taken.
REXCVAR_DEFINE_BOOL(sasrt_renut_splice_ended, true, "SASRT",
                    "Renut's renderer: a composed command buffer's splice takes a recorded buffer's recording only "
                    "once its EndCommandBuffer has run; a buffer still being recorded at the splice (a worker's shadow "
                    "pass begun after the main thread spliced it) is taken at that End, and a recording ended after "
                    "the splice but before the segment's ring submission replaces the one taken (the GPU reads the "
                    "buffer at the submission). Off: the recording as it is at the splice, whatever its state (the "
                    "previous frame's when the worker had not begun this frame's: the shadow atlas a frame behind the "
                    "mask's matrices, the far-cascade flicker's candidate)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
// sasrt-nx (2026-11-08, the far-cascade shadow flicker's cause; docs/enhancements.md): the worker records the scene pass
// (the scene's depth: about 300-800 draws) right after the game thread submits a composed segment, and splices it into
// the next composed buffer, which the next frame submits: Renut replayed each frame's scene a frame after it was
// recorded, beside the next frame's shading (the shadow cascades and the mask), whose camera is the camera the scene
// was recorded with a frame later (tools/flicker/cam_match.py on the PC: the shading's camera matches the scene
// recorded in its own frame to 0.01 mrad, the one replayed with it is off by the frame's turn; a camera cut put the
// whole ground in shadow or none). With the key, a submission's place in the render stream replays the recording
// spliced after it (the scene recorded in the same frame), waiting for it there up to the timeout; the recording the
// submission named is the fallback.
REXCVAR_DEFINE_BOOL(sasrt_renut_scene_same_frame, true, "SASRT",
                    "Renut's renderer: a composed segment's submission replays the scene pass the worker records right "
                    "after it (the same frame's, whose camera the frame's shadows use) instead of the one spliced the "
                    "frame before; the render thread waits for it at that place (sasrt_renut_scene_same_frame_timeout_ms, "
                    "then the previous one). Off: a frame's scene is drawn a frame late, under the next frame's shadows "
                    "(the far-cascade flicker)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_INT32(sasrt_renut_scene_same_frame_timeout_ms, 50, "SASRT",
                     "sasrt_renut_scene_same_frame: how long the render thread waits for the same frame's scene pass")
    .range(1, 1000)
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_INT32(sasrt_renut_split_scene, 2, "SASRT",  // 2 since log 303 (1,033 of 1,039 views exact)
                     "Renut's renderer, split screen (2026-11-19): 1 a submission replays the scene recorded for its "
                     "own view (the recordings spliced into the submission a view count before it: a composed buffer "
                     "carries the scene recorded after the submission before it, the previous view's), a frame late "
                     "(the far-cascade shadow flicker, as one player's before the same-frame scene); 2 the same frame's: "
                     "a submission's place in the render stream takes the first scene recording to end whose camera "
                     "is its view's (nearest to 1's), waiting sasrt_renut_scene_same_frame_timeout_ms (then 1's); 0 the "
                     "recordings its own composed buffer names (each view drew the other player's world, water and "
                     "shadows)")
    .range(0, 2)
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DECLARE(bool, sasrt_deko3d_copy_wait);  // sasrt-nx (2026-11-08): renut-ultimate's now (gpu/ultimate.cpp)
namespace renut::gpu {
bool SasrtDeko3DCopyWaitOn() {
  static const bool on = REXCVAR_GET(sasrt_deko3d_copy_wait);
  return on;
}
}  // namespace renut::gpu
// sasrt-nx (2026-11-08): the console's shadow dumps of 2026-11-08 (12 windows) show every shading pass's cascade
// constants fitting the scene depth of the frame after the one it samples (to texel precision wherever the camera
// moved); a sharp turn then shadows the whole ground for a frame. Which draws wrote that depth, and in what order the
// recordings replay against the game thread's own draws, is what this logs (docs/enhancements.md).
REXCVAR_DEFINE_BOOL(sasrt_renut_diag_depth_writers, false, "SASRT",
                    "Diagnostic (the far-cascade flicker, 2026-11-08): every depth target remembers which draws wrote it "
                    "since its last whole clear (the game thread's own or a replayed recording's, and the game frame); "
                    "its depth resolves carry that into the destination, and the light-volume lines print it with the "
                    "binding (\"src: ...\"). In a shadow dump window each replayed recording's start and end is logged "
                    "with the depth-writing draws on each side (\"seq:\" lines). (With or without it, the replay tag is "
                    "left empty after each run since 2026-11-08: the game thread's own resolves are untagged.)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
namespace renut::gpu {
bool SasrtDiagDepthWritersOn() {
  static const bool on = REXCVAR_GET(sasrt_renut_diag_depth_writers);
  return on;
}
}  // namespace renut::gpu
REXCVAR_DEFINE_BOOL(sasrt_renut_diag_splice_pm4, false, "SASRT",
                    "Diagnostic (the far-cascade flicker, 2026-11-04): at each splice the spliced buffers' own PM4 (the "
                    "indirect-buffer packets the composer wrote) is searched for the packets writing vertex constants "
                    "c128-c131 (the shadow casters' matrix); the values are logged for the first splices and read "
                    "again at the segment's submission: a buffer Direct3D patched after the splice shows differing "
                    "values (always logged, up to 200). The recorded snapshot's values are the frame's \"shadow caster\" "
                    "lines (sasrt_renut_diag_light_volumes = -1). Counts in the 10 s Renut hooks line")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
extern std::atomic<uint64_t> g_sasrt_game_frames;  // src/sasrt_capture.cpp
extern std::atomic<uint64_t> g_sasrt_split_screen_frame;  // render/draw.cpp (sasrt-nx 2026-11-19: SceneSameFrameOn)
extern std::atomic<uint32_t> g_sasrt_split_views;  // render/draw.cpp (sasrt-nx 2026-11-19): composites a render frame
namespace {  // sasrt-nx (2026-10-21): splices found nested in a segment
std::atomic<uint32_t> g_last_tiles{0}, g_last_tile_w{0}, g_last_tile_h{0}, g_last_extent_w{0}, g_last_extent_h{0};
std::atomic<int64_t> g_next_report_ms{0};

void MaybeReport() {
  const int64_t now = std::chrono::duration_cast<std::chrono::milliseconds>(
                          std::chrono::steady_clock::now().time_since_epoch()).count();
  int64_t due = g_next_report_ms.load(std::memory_order_relaxed);
  if (now < due || !g_next_report_ms.compare_exchange_strong(due, now + 10000))
    return;
  uint64_t slot_filled = 0, slot_fallbacks = 0, slot_longest = 0;
  SasrtRunSlotCounts(slot_filled, slot_fallbacks, slot_longest);
  RGPU_INFO("[sasrt] {}", renut::gpu::SasrtSlotTimingReport());  // sasrt-nx (2026-11-10, item 4's measure)
  RGPU_INFO("[sasrt] Renut hooks so far: BeginTiling {} (last {} tiles, first {}x{}, extent {}x{}), "
            "BeginCommandBuffer {}, RunCommandBuffer {} queued + {} recorded; ring submissions {}, of composed "
            "buffers {} ({} of them at a pool wrap), recorded buffers replayed from them {}; splices (sasrt_renut_"
            "splice_ended): {} taken ended, {} left still being recorded, {} left taken before (not recorded again), {} "
            "without a recording; at the recordings' ends {} resolved, {} replaced; {} taken at the submission; pm4 "
            "(sasrt_renut_diag_splice_pm4): {} buffers searched, c128 found in {}, differing at the submission {}; "
            "same-frame scene (sasrt_renut_scene_same_frame): {} places, {} filled by the next splice, {} splices "
            "without a place; in the last 10 s {} replayed the same frame's, {} the fallback, longest wait {} us",
            g_begin_tiling.load(),
            g_last_tiles.load(), g_last_tile_w.load(), g_last_tile_h.load(), g_last_extent_w.load(),
            g_last_extent_h.load(), g_begin_cb.load(), g_run_queued.load(), g_run_recorded.load(), g_submits.load(),
            g_composed_submits.load(), g_composed_range_matches.load(), g_composed_runs.load(),
            g_splice_ended.load(), g_splice_in_progress.load(), g_splice_taken_before.load(), g_splice_none.load(),
            g_splice_resolved.load(), g_splice_replaced.load(), g_splice_at_submit.load(), g_pm4_checked.load(),
            g_pm4_found.load(), g_pm4_differ.load(), g_slot_opened.load(), g_slot_spliced.load(),
            g_slot_unmatched.load(), slot_filled, slot_fallbacks, slot_longest);
}

std::vector<ClearRect> ReadTiles(u32 rects_va, u32 count) {
  std::vector<ClearRect> tiles;
  const auto *words = rects_va ? GuestPtr<const be_u32>(rects_va) : nullptr;
  for (u32 i = 0; words && i < count && i < 16; ++i) {
    tiles.push_back(ClearRect{i32(u32(words[i * 4])), i32(u32(words[i * 4 + 1])), i32(u32(words[i * 4 + 2])),
                              i32(u32(words[i * 4 + 3]))});
  }
  return tiles;
}

}  // namespace

// HRESULT D3DDevice_BeginCommandBuffer(D3DDevice*, D3DCommandBuffer*, DWORD Flags, const D3DTAGCOLLECTION*, ...)
// [sub_82CEB850; N&B 0x82657CB0]
BANJO_RENUT_HOOK_RAW(sub_82CEB850) {
  const u32 device = ctx.r3.u32, command_buffer = ctx.r4.u32;
  FlushDeferredVertices(device);  // a Begin*Vertices draw recorded into the previous buffer
  g_begin_cb.fetch_add(1, std::memory_order_relaxed);
  sasrt::trace::Note(sasrt::trace::kBeginCb, command_buffer);  // sasrt-nx (2026-11-08, sasrt_renut_diag_trace)
  MaybeReport();
  __imp__sub_82CEB850(ctx, base);
  if (command_buffer)
    BeginRecording(device, command_buffer);
}

REXCVAR_DECLARE(bool, sasrt_renut_constant_f4_pending);  // sasrt-nx (2026-11-08): renut-ultimate's now (gpu/ultimate.cpp)

BANJO_RENUT_HOOK_RAW(sub_82CC2108) {
  const u32 device = ctx.r3.u32, pixel = ctx.r4.u32, start = ctx.r5.u32, count = ctx.r8.u32;
  __imp__sub_82CC2108(ctx, base);
  static const bool on = REXCVAR_GET(sasrt_renut_constant_f4_pending);
  if (!on || ctx.r3.u32 != 0 || !count || start + count > 256)
    return;
  auto *d = GuestPtr<d3d::Device>(device);
  if (!d)
    return;
  uint64_t mask = 0;  // bit 63 - group, a group per 4 registers (D3DTAGCOLLECTION)
  for (u32 g = start >> 2; g <= (start + count - 1) >> 2; ++g)
    mask |= uint64_t(1) << (63 - g);
  d->m_Pending[pixel ? 1 : 0] = u64(d->m_Pending[pixel ? 1 : 0]) | mask;
  static std::atomic<uint64_t> calls{0};
  if (calls.fetch_add(1, std::memory_order_relaxed) == 0)
    RGPU_INFO("[sasrt] D3DDevice_BeginShaderConstantF4 used (first: device {:08X}, {} shader, registers {}-{}, "
              "recording {}): its range kept pending (sasrt_renut_constant_f4_pending)", device,
              pixel ? "pixel" : "vertex", start, start + count - 1, IsRecordingCommandBuffer(device) ? "yes" : "no");
}

// sasrt-nx (2026-11-08, sasrt_renut_diag_trace; PC only): where the game keeps the scene pass's camera. The rows the
// worker recorded (c131-c133, c140-c143: the device image's bytes, which are guest memory's order) are looked for in
// every committed, readable region of the guest heaps; the matches are logged with their surroundings, and the first
// c133 match's w becomes the trace's watched word, so every later event shows the camera the game holds then.
void SasrtHuntCamera(const u32 *regs) {
#if !REX_PLATFORM_SWITCH
  auto *memory = rex::system::kernel_state()->memory();
  const auto start = std::chrono::steady_clock::now();
  // c142.w / c143.w: the camera's world position x / y (c142-c143.xyz are the view rotation's columns), as the game's
  // camera object holds them: looked for as a pair (x, y adjacent) and, failing that, x alone.
  const u32 px = regs[14 * 4 + 3], py = regs[15 * 4 + 3];  // big-endian words, as guest memory
  std::vector<std::pair<u32, u32>> found;  // (kind: 0 pair, 1 x alone, guest address)
  for (int pass = 0; pass < 2 && found.empty(); ++pass) {
    for (uint32_t heap_base : {0x40000000u, 0x70000000u, 0x80000000u, 0x90000000u, 0xA0000000u, 0xC0000000u, 0xE0000000u}) {
      auto *heap = memory->LookupHeap(heap_base);
      if (!heap)
        continue;
      const uint32_t end = heap->heap_base() + heap->heap_size();
      for (uint32_t a = heap->heap_base(); a < end && found.size() < 32;) {
        rex::memory::HeapAllocationInfo info{};
        if (!heap->QueryRegionInfo(a, &info) || !info.region_size)
          break;
        if ((info.state & rex::memory::kMemoryAllocationCommit) && (info.protect & rex::memory::kMemoryProtectRead)) {
          const uint32_t size = std::min<uint32_t>(info.region_size, end - a);
          const auto *host = memory->TranslateVirtual<const uint8_t *>(a);
          for (uint32_t off = 0; off + 8 <= size && found.size() < 32; off += 4) {
            u32 w0, w1;
            std::memcpy(&w0, host + off, 4);
            if (w0 != px)
              continue;
            std::memcpy(&w1, host + off + 4, 4);
            if (pass == 1 || w1 == py)
              found.push_back({u32(pass), a + off});
          }
        }
        if (info.region_size >= end - a)
          break;
        a += info.region_size;
      }
    }
  }
  RGPU_INFO("[sasrt] camera hunt: {} matches ({:.0f} ms)", found.size(),
            std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - start).count());
  u32 watch = 0;
  for (const auto &[kind, address] : found) {
    std::string around;
    if (const auto *p = GuestPtr<const be_u32>(address - 32))
      for (u32 i = 0; i < 24; ++i) {
        const u32 v = p[i];
        float f;
        std::memcpy(&f, &v, 4);
        around += fmt::format(" {:.4g}", f);
      }
    RGPU_INFO("[sasrt] camera hunt: {} at {:08X}:{}", kind ? "x" : "x,y", address, around);
    // The game's camera object: a world matrix whose translation row (x y z 1) holds the position.
    if (const auto *p = GuestPtr<const be_u32>(address + 12); p && u32(*p) == 0x3F800000u && !watch)
      watch = address;
  }
  if (watch)
    sasrt::trace::SetWatch(watch);
#else
  (void)regs;
#endif
}

// HRESULT D3DDevice_EndCommandBuffer(D3DDevice*) [sub_82CEFA78; N&B 0x826582A0]
BANJO_RENUT_HOOK_RAW(sub_82CEFA78) {
  FlushDeferredVertices(ctx.r3.u32);
  // sasrt-nx (2026-11-08, sasrt_renut_diag_trace): the end, and for the scene pass (its first draw's camera block:
  // c136 = (0 0 -1 -1), c137 = (0 0 -1 0)) the camera rows' w, as the worker recorded them.
  if (sasrt::trace::On()) {
    if (const u32 ended = RecordingCommandBuffer(ctx.r3.u32)) {
      sasrt::trace::Note(sasrt::trace::kEndCb, ended);
      if (auto run = CaptureCommandBufferRun(ended)) {
        u32 regs[16 * 4] = {};  // the device image's words: big-endian
        const auto w = [&regs](u32 i) { return __builtin_bswap32(regs[i]); };
        const auto camera_block = [](const u32 *r) {
          return (__builtin_bswap32(r[8 * 4 + 2]) >> 16) == 0xBF80u && (__builtin_bswap32(r[8 * 4 + 3]) >> 16) == 0xBF80u &&
                 (__builtin_bswap32(r[9 * 4 + 2]) >> 16) == 0xBF80u && r[9 * 4 + 3] == 0;
        };
        if (CapturedRunFindVertexConstants(*run, ended, 128, 16, +camera_block, regs)) {
          sasrt::trace::Note(sasrt::trace::kEndCb, ended, w(14 * 4 + 3));  // the recording's camera x (c142.w)
          if (sasrt::trace::TakeHunt())
            SasrtHuntCamera(regs);
        }
      }
    }
  }
  // sasrt-nx (2026-11-04, sasrt_renut_splice_ended): the recording is ended before the original clears the device's
  // command buffer field; a splice waiting for it (or holding an older recording of the buffer) takes it now.
  if (SpliceEndedOn()) {
    if (const u32 ended = RecordingCommandBuffer(ctx.r3.u32)) {
      MarkRecordingEnded(ended);
      SasrtRecordingEnded(ended);
      SasrtSplitPlaceEnded(ended);  // sasrt-nx (2026-11-19, sasrt_renut_split_scene 2)
    }
  }
  __imp__sub_82CEFA78(ctx, base);
}

// void D3DDevice_RunCommandBuffer(D3DDevice*, D3DCommandBuffer*, DWORD PredicationSelect)
// [sub_82CEFF70; N&B 0x82222888]
BANJO_RENUT_HOOK_RAW(sub_82CEFF70) {
  const u32 device = ctx.r3.u32, command_buffer = ctx.r4.u32;
  if (command_buffer) {
    if (IsRecordingCommandBuffer(device)) {
      g_run_recorded.fetch_add(1, std::memory_order_relaxed);
      MaybeReport();
      RecordRun(device, command_buffer);
    } else {
      g_run_queued.fetch_add(1, std::memory_order_relaxed);
      MaybeReport();
      RunReadyCallbacks();
      QueueRunCommandBuffer(device, command_buffer);
    }
  }
  __imp__sub_82CEFF70(ctx, base);
}

// void D3DDevice_BeginTiling(D3DDevice*, DWORD Flags, DWORD Count, const D3DRECT *pTileRects,
//     const D3DVECTOR4 *pClearColor, float ClearZ, DWORD ClearStencil) [sub_82CE7868; N&B 0x822788A0]
// This port hooks it too (src/me/sasrt_me_hooks.cpp: SASRT_RENUT_YIELD_SHARED).
BANJO_RENUT_HOOK_RAW_SHARED(sub_82CE7868) {
  const u32 device = ctx.r3.u32;
  if (!IsRecordingCommandBuffer(device)) {
    FlushDeferredVertices(device);
    const std::vector<ClearRect> tiles = ReadTiles(ctx.r6.u32, ctx.r5.u32);
    u32 width = 0, height = 0;
    for (const ClearRect &rect : tiles) {
      width = std::max(width, u32(rect.x2));
      height = std::max(height, u32(rect.y2));
    }
    g_begin_tiling.fetch_add(1, std::memory_order_relaxed);
    g_last_tiles.store(u32(tiles.size()), std::memory_order_relaxed);
    if (!tiles.empty()) {
      g_last_tile_w.store(u32(tiles[0].x2 - tiles[0].x1), std::memory_order_relaxed);
      g_last_tile_h.store(u32(tiles[0].y2 - tiles[0].y1), std::memory_order_relaxed);
    }
    g_last_extent_w.store(width, std::memory_order_relaxed);
    g_last_extent_h.store(height, std::memory_order_relaxed);
    MaybeReport();
    render_thread::Queue([tiles, width, height] {
      SetTilingExtentLocked(width, height);
      SetTilesLocked(tiles.data(), u32(tiles.size()));
    });
  }
  __imp__sub_82CE7868(ctx, base);
}

// HRESULT D3DDevice_EndTiling(D3DDevice*, DWORD ResolveFlags, const D3DRECT*, D3DBaseTexture*, ...)
// [sub_82CE8098; N&B 0x82212328]: the original's per-tile resolves are queued by the resolve entry's hook first.
BANJO_RENUT_HOOK_RAW_SHARED(sub_82CE8098) {
  const u32 device = ctx.r3.u32;
  __imp__sub_82CE8098(ctx, base);
  if (!IsRecordingCommandBuffer(device)) {
    render_thread::Queue([] {
      SetTilingExtentLocked(0, 0);
      SetTilesLocked(nullptr, 0);
    });
  }
}

// The submission of command buffer segments to the GPU's primary ring (sub_82CDE200; SA2's sub_8254DC00): indirect
// buffer packets into the ring at +15300 and the write pointer into CP_RB_WPTR (MMIO 0x7FC80714). With Renut's
// renderer there is no ring: the hardware path that sets the ring up (+15300, +15304) does not run, and the segments
// themselves are the sink nobody reads. sa2-nx's hooks keep SA2 away from it (KickOff, KickOffSegment); this game also
// reaches it from 12 other Direct3D functions (sub_82D07E50, ...): the first PC boot wrote through the null ring.
namespace {

// Composed command buffers (below): the physical address of a composed buffer's segment, as the ring submission names
// it, -> the recorded buffers sub_82CEF770 put into it, in order, each with its recording as it was at the splice
// (2026-10-21: captured at the submission, a worker could already be recording the next frame's into the same buffer,
// and the run replayed that nearly empty recording: the "ocean" frames, the scene's main pass without its draws).
struct SplicedBuffer {
  u32 buffer = 0;
  std::shared_ptr<CapturedRun> recording;
  // sasrt-nx (2026-11-04, sasrt_renut_diag_splice_pm4): the buffer's indirect-buffer range as the composer wrote it,
  // and c128-c131 as its PM4 held them at the splice (found: all 16 words seen).
  u32 ib_phys = 0, ib_dwords = 0;
  uint64_t frame = 0;
  bool found = false;
  u32 at_splice[16] = {};
};
// sasrt-nx (2026-10-21, diagnostics): true from 150 to 153 s after the first use (a race window), for sequence logs.
bool SequenceWindow() {
  static const auto start = std::chrono::steady_clock::now();
  const auto s = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - start).count();
  return s >= 150000 && s < 153000;
}
std::mutex g_composed_mutex;
// sasrt-nx (2026-11-08, sasrt_renut_scene_same_frame): submissions' runs waiting for the recording spliced after them
// (oldest first; under g_composed_mutex), and the counts.
std::deque<std::shared_ptr<SasrtRunSlot>> g_open_slots;
// sasrt-nx (2026-11-19, the user's two-player race: 7 fps, the world following the other player): in split screen the
// recording a place waits for is spliced only after the game's Swap, which waits for the render thread (frames ahead 0):
// every place waited its whole timeout (log 290: 0 same-frame replays, 148 fallbacks a 10 s, the longest wait 50 ms; two
// a frame). While split screen was drawn in the last 60 frames (draw.cpp's partial composites) a submission replays its
// own spliced recording as before 2026-11-08 (a frame late, no wait); one player: the same-frame scene.
bool SceneSameFrameOn() {
  static const bool on = REXCVAR_GET(sasrt_renut_scene_same_frame);
  if (!on)
    return false;
  const uint64_t split = g_sasrt_split_screen_frame.load(std::memory_order_relaxed);
  const bool split_now = split && g_sasrt_game_frames.load(std::memory_order_relaxed) < split + 60;
  static std::atomic<int> said{-1};
  if (said.exchange(split_now ? 1 : 0, std::memory_order_relaxed) != (split_now ? 1 : 0))
    RGPU_INFO("[sasrt] same-frame scene {} (sasrt_renut_scene_same_frame)",
              split_now ? "off while the screen is split" : "on (one player)");
  return !split_now;
}
// sasrt-nx (2026-11-19, split screen: each view's world, water and shadows following the other player's camera). A
// composed buffer carries the scene the worker recorded after the submission before it; with one view per submission
// that is the previous view's (two players: view 1 replayed view 2's scene and view 2 view 1's). With
// sasrt_renut_split_scene 1 a submission in split screen replays the recordings spliced into the submission (views - 1)
// before it: its own view's, a frame late (as one player's before the same-frame scene). 0: its own composed buffer's.
int SplitSceneMode() {
  static const int mode = REXCVAR_GET(sasrt_renut_split_scene);
  return mode;
}
bool SplitSceneOn() {
  return SplitSceneMode() >= 1;
}
std::deque<std::vector<SplicedBuffer>> g_split_history;  // the last submissions' spliced lists (under g_composed_mutex)
std::atomic<bool> g_split_history_used{false};
// sasrt-nx (2026-11-19, sasrt_renut_diag_trace): a recording's scene camera x (c142.w of its first draw with the camera
// block: c136 = (0 0 -1 -1), c137.w = 0), as the float's bits; 0 none.
u32 SasrtRunCameraX(const CapturedRun *run, u32 buffer) {
  if (!run || !buffer)
    return 0;
  u32 regs[16 * 4] = {};
  const auto camera_block = [](const u32 *r) {
    return (__builtin_bswap32(r[8 * 4 + 2]) >> 16) == 0xBF80u && (__builtin_bswap32(r[8 * 4 + 3]) >> 16) == 0xBF80u &&
           (__builtin_bswap32(r[9 * 4 + 2]) >> 16) == 0xBF80u && r[9 * 4 + 3] == 0;
  };
  return CapturedRunFindVertexConstants(*run, buffer, 128, 16, +camera_block, regs) ? __builtin_bswap32(regs[14 * 4 + 3])
                                                                                     : 0u;
}
// sasrt-nx (2026-11-19, sasrt_renut_split_scene 2): a recording's scene camera, c142 and c143 (the view's rotation
// columns and its position's x and y) as floats; false: no scene pass.
bool SasrtRunCamera(const CapturedRun *run, u32 buffer, float *out8) {
  if (!run || !buffer)
    return false;
  u32 regs[16 * 4] = {};
  const auto camera_block = [](const u32 *r) {
    return (__builtin_bswap32(r[8 * 4 + 2]) >> 16) == 0xBF80u && (__builtin_bswap32(r[8 * 4 + 3]) >> 16) == 0xBF80u &&
           (__builtin_bswap32(r[9 * 4 + 2]) >> 16) == 0xBF80u && r[9 * 4 + 3] == 0;
  };
  if (!CapturedRunFindVertexConstants(*run, buffer, 128, 16, +camera_block, regs))
    return false;
  for (u32 i = 0; i < 8; ++i) {
    const u32 w = __builtin_bswap32(regs[14 * 4 + i]);
    std::memcpy(&out8[i], &w, 4);
  }
  return true;
}
// How far two scene cameras are apart: the position's x and y, and the rotation columns (x20: a quarter turn is ~28).
float SasrtCameraDistance(const float *a, const float *b) {
  float d = std::fabs(a[3] - b[3]) + std::fabs(a[7] - b[7]);
  for (u32 i : {0u, 1u, 2u, 4u, 5u, 6u})
    d += 20.0f * std::fabs(a[i] - b[i]);
  return d;
}
// sasrt-nx (2026-11-19, sasrt_renut_split_scene 2): the open places of split screen's submissions, each with its view's
// camera (1's recording's: the view's scene a frame before), filled at a scene recording's End (under g_composed_mutex).
// sasrt-nx (2026-11-20, the user's "full screen flashes or half screen flashes" under load: log 305's "ocean" frames, a
// view of sky and sea alone): each split screen place's view, in submission order (the last `views` of them; under
// g_composed_mutex). The worker splices a view's recording into the next composed buffer right after its End; loaded,
// the game submits that buffer first (32 submissions at log 305's race start named no recording) and the view ran
// nothing. A place's view holds the recording that filled it (its fallback until then): the next place of the same
// view, `views` submissions on, takes it as its fallback and camera, whatever the composed buffer names.
struct SplitView {
  u32 buffer = 0;
  std::shared_ptr<CapturedRun> recording;
  float camera[8] = {};
  bool has_camera = false;
};
std::deque<std::shared_ptr<SplitView>> g_split_ring;
struct SplitPlace {
  std::shared_ptr<SasrtRunSlot> slot;
  float camera[8];
  std::shared_ptr<SplitView> view;
};
// sasrt-nx (2026-11-20): segments submitted before their splice (the worker behind); their late splice is dropped (it
// stayed under the segment's address until the pool came round to it again, ~63 frames on, and was run then beside
// that splice's own). And the last scene recording a one-player place had, the fallback of one whose submission named
// none. Both under g_composed_mutex.
std::deque<u32> g_late_keys;
u32 g_last_scene_buffer = 0;
std::shared_ptr<CapturedRun> g_last_scene;
std::atomic<uint64_t> g_empty_submits{0}, g_late_splices{0};
std::deque<SplitPlace> g_split_places;
std::atomic<uint64_t> g_split_place_fills{0}, g_split_place_unmatched{0};
// Every 10 s while split screen's places are used: how many a recording's End filled, and Ends no place took.
void SplitPlaceReport() {
  static std::atomic<int64_t> next_ms{0};
  const int64_t now = std::chrono::duration_cast<std::chrono::milliseconds>(
                          std::chrono::steady_clock::now().time_since_epoch()).count();
  int64_t due = next_ms.load(std::memory_order_relaxed);
  if (now < due || !next_ms.compare_exchange_strong(due, now + 10000))
    return;
  RGPU_INFO("[sasrt] split screen's same-frame places (sasrt_renut_split_scene 2): {} filled at a recording's End, {} "
            "scene recordings no place took; {} submissions named no recording (their splice late: {}) (10 s)",
            g_split_place_fills.exchange(0), g_split_place_unmatched.exchange(0), g_empty_submits.exchange(0),
            g_late_splices.exchange(0));
}
bool SlotDone(SasrtRunSlot &slot) {
  std::lock_guard lock(slot.mutex);
  return slot.filled;
}
// At a recording's End (the worker): the open place whose camera is nearest the recording's, if near enough.
void SasrtSplitPlaceEnded(u32 buffer) {
  if (SplitSceneMode() != 2 || !g_split_history_used.load(std::memory_order_relaxed))
    return;
  {
    std::lock_guard lock(g_composed_mutex);
    if (g_split_places.empty())
      return;
  }
  std::shared_ptr<CapturedRun> run = CaptureCommandBufferRun(buffer);
  float camera[8];
  if (!SasrtRunCamera(run.get(), buffer, camera))
    return;  // not a scene pass
  std::shared_ptr<SasrtRunSlot> slot;
  {
    std::lock_guard lock(g_composed_mutex);
    while (!g_split_places.empty() && SlotDone(*g_split_places.front().slot))
      g_split_places.pop_front();  // timed out (their fallback ran)
    size_t best = g_split_places.size();
    float best_d = 1e30f, second_d = 1e30f;
    for (size_t i = 0; i < g_split_places.size(); ++i) {
      const float d = SasrtCameraDistance(camera, g_split_places[i].camera);
      if (d < best_d) {
        second_d = best_d;
        best_d = d;
        best = i;
      } else if (d < second_d) {
        second_d = d;
      }
    }
    // Near its view's camera of a frame before, or (a camera cut, a respawn: log 303's 0-8 places a 10 s that waited
    // their whole timeout) clearly nearer one open place than any other, or the only place open: the next scene
    // recording to end is that view's (the other views' places of the frame are filled; the next frame's recordings
    // begin after the Swap, which waits for this place).
    if (best < g_split_places.size() && (best_d < 40.0f || best_d * 2.0f < second_d)) {
      slot = std::move(g_split_places[best].slot);
      if (const auto &view = g_split_places[best].view) {  // sasrt-nx (2026-11-20): the view's recording now
        view->buffer = buffer;
        view->recording = run;
        std::memcpy(view->camera, camera, sizeof(camera));
        view->has_camera = true;
      }
      g_split_places.erase(g_split_places.begin() + ptrdiff_t(best));
    }
  }
  if (!slot) {
    g_split_place_unmatched.fetch_add(1, std::memory_order_relaxed);
    SplitPlaceReport();
    return;
  }
  FillCapturedRunSlot(*slot, buffer, run);
  g_split_place_fills.fetch_add(1, std::memory_order_relaxed);
  SplitPlaceReport();
  if (sasrt::trace::On())
    sasrt::trace::Note(sasrt::trace::kSlotFill, buffer, SasrtRunCameraX(run.get(), buffer));
}
// sasrt-nx (2026-10-21, diagnostics): submitted segments that ran nothing, and their first words then (under the lock).
struct NopWatch {
  u32 address, bytes, device, w0, w1, w2, w3;
};
std::vector<NopWatch> g_nop_watch;
// sasrt-nx (2026-10-21): the segment of the composed buffer spliced last (the "ocean" frames' fix, below).
u32 g_last_splice_key = 0;
// Logs the watched segments whose first words changed since their submission (and forgets them).
void CheckNopWatchLocked(const char *where) {
  for (size_t i = 0; i < g_nop_watch.size();) {
    const NopWatch &n = g_nop_watch[i];
    const auto *seg = GuestPhysicalPtr<const be_u32>(n.address);
    if (seg && (u32(seg[0]) != n.w0 || u32(seg[1]) != n.w1 || u32(seg[2]) != n.w2 || u32(seg[3]) != n.w3)) {
      static uint32_t logged = 0;
      if (logged++ < 12) {
        std::string words;
        for (u32 k = 0; k < 24 && k < n.bytes / 4; ++k)
          words += fmt::format(" {:08X}", u32(seg[k]));
        RGPU_INFO("[sasrt] submitted segment {:08X} changed after its submission (seen at {}): {:08X} {:08X} -> {}",
                  n.address, where, n.w0, n.w1, words);
      }
      g_nop_watch.erase(g_nop_watch.begin() + std::ptrdiff_t(i));
    } else {
      ++i;
    }
  }
}
std::unordered_map<u32, std::vector<SplicedBuffer>> g_composed;

bool SpliceEndedOn() {
  static const bool on = REXCVAR_GET(sasrt_renut_splice_ended);
  return on;
}

bool DiagSplicePm4On() {
  static const bool on = REXCVAR_GET(sasrt_renut_diag_splice_pm4);
  return on;
}

// sasrt-nx (2026-11-04, sasrt_renut_diag_splice_pm4): the words of vertex constants c128-c131 (registers 0x4200-0x420F)
// as the PM4 at 'phys' (dwords long) writes them: type-0 register runs, SET_CONSTANT (ALU type 0), SET_CONSTANT2 /
// SET_SHADER_CONSTANTS, and LOAD_ALU_CONSTANT (the data in memory). The last write of each word stands. True when all
// 16 words were seen.
bool ReadC128FromPm4(u32 phys, u32 dwords, u32 out[16]) {
  const auto *w = GuestPhysicalPtr<const be_u32>(phys & 0x1FFFFFFFu);
  if (!w || dwords == 0 || dwords > (1u << 20))
    return false;
  u32 seen = 0;
  const auto take = [&](u32 first_reg, u32 count, const be_u32 *data) {
    for (u32 i = 0; i < count; ++i) {
      const u32 reg = first_reg + i;
      if (reg >= 0x4200u && reg < 0x4210u) {
        out[reg - 0x4200u] = u32(data[i]);
        seen |= 1u << (reg - 0x4200u);
      }
    }
  };
  for (u32 i = 0; i < dwords;) {
    const u32 h = u32(w[i]);
    const u32 type = h >> 30;
    if (type == 0) {
      const u32 count = h ? ((h >> 16) & 0x3FFFu) + 1 : 0;
      if (!h) {
        ++i;
        continue;
      }
      if (i + 1 + count > dwords)
        break;
      if (!((h >> 15) & 1))
        take(h & 0x7FFFu, count, w + i + 1);
      i += 1 + count;
    } else if (type == 2) {
      ++i;
    } else if (type == 3) {
      const u32 op = (h >> 8) & 0x7Fu, count = ((h >> 16) & 0x3FFFu) + 1;
      if (i + 1 + count > dwords)
        break;
      const be_u32 *data = w + i + 1;
      if (op == 0x2D && count >= 2) {  // SET_CONSTANT
        const u32 type_index = u32(data[0]);
        if (((type_index >> 16) & 0xFFu) == 0)
          take(0x4000u + (type_index & 0x7FFu), count - 1, data + 1);
      } else if ((op == 0x55 || op == 0x56) && count >= 2) {  // SET_CONSTANT2 / SET_SHADER_CONSTANTS
        take(u32(data[0]) & 0xFFFFu, count - 1, data + 1);
      } else if (op == 0x2F && count >= 3) {  // LOAD_ALU_CONSTANT: the data in memory
        const u32 address = u32(data[0]) & 0x3FFFFFFFu, type_index = u32(data[1]), n = u32(data[2]) & 0xFFFu;
        if (((type_index >> 16) & 0xFFu) == 0) {
          if (const auto *mem = GuestPhysicalPtr<const be_u32>(address & 0x1FFFFFFFu))
            take(0x4000u + (type_index & 0x7FFu), n, mem);
        }
      }
      i += 1 + count;
    } else {
      i += 3;  // type 1: two registers
    }
  }
  return seen == 0xFFFFu;
}

std::string C128Text(const u32 v[16]) {
  std::string t;
  for (u32 r = 0; r < 4; ++r) {
    float f[4];
    for (u32 k = 0; k < 4; ++k)
      std::memcpy(&f[k], &v[r * 4 + k], 4);
    t += fmt::format(" c{} ({:.5g} {:.5g} {:.5g} {:.5g})", 128 + r, f[0], f[1], f[2], f[3]);
  }
  return t;
}

// sasrt-nx (2026-11-04, sasrt_renut_splice_ended): a recording of 'command_buffer_va' just ended: every splice not yet
// submitted that names the buffer takes it (resolved when it had none, replaced when it held an older one). The
// capture is made outside the composed lock (it takes the recordings' own), and only when a splice wants it.
void SasrtRecordingEnded(u32 command_buffer_va) {
  bool wanted = false;
  {
    std::lock_guard lock(g_composed_mutex);
    for (const auto &[key, list] : g_composed) {
      for (const SplicedBuffer &s : list) {
        if (s.buffer == command_buffer_va) {
          wanted = true;
          break;
        }
      }
      if (wanted)
        break;
    }
  }
  if (!wanted)
    return;
  int state = 3;
  std::shared_ptr<CapturedRun> recording = CaptureIfEndedRun(command_buffer_va, &state);
  if (!recording)
    return;
  std::lock_guard lock(g_composed_mutex);
  for (auto &[key, list] : g_composed) {
    for (SplicedBuffer &s : list) {
      if (s.buffer != command_buffer_va)
        continue;
      (s.recording ? g_splice_replaced : g_splice_resolved).fetch_add(1, std::memory_order_relaxed);
      s.recording = recording;
    }
  }
}

}  // namespace

BANJO_RENUT_HOOK_RAW(sub_82CDE200) {
  // This game runs its recorded command buffers this way, not through D3DDevice_RunCommandBuffer (which it never
  // calls): sub_82CEF770 writes indirect-buffer packets to the recorded buffers into a composed buffer's segment, and
  // the segment goes to the ring here (r4: a list of r5 {size and flags, physical address} pairs). The recorded
  // buffers' draws are Renut's (recorded while their device recorded them): replayed here, on the submitting device,
  // in the order they were put in.
  const u32 device = ctx.r3.u32, count = ctx.r5.u32;
  const auto *list = ctx.r4.u32 ? GuestPtr<const be_u32>(ctx.r4.u32) : nullptr;
  g_submits.fetch_add(1, std::memory_order_relaxed);
  for (u32 i = 0; list && i < count && i < 64; ++i) {
    const u32 address = u32(list[i * 2 + 1]) & 0x1FFFFFFFu;
    // The segment's size: the indirect buffer packet's dword count (bits 0-19).
    const u32 bytes = (u32(list[i * 2]) & 0xFFFFFu) * 4u;
    std::vector<SplicedBuffer> buffers;
    {
      std::lock_guard lock(g_composed_mutex);
      // sasrt-nx (2026-11-04, sasrt_renut_diag_splice_pm4): every submitted segment's first words are kept and
      // compared at the next submission: a segment the game fills after submitting it (the 360's GPU being behind)
      // shows as changed (CheckNopWatchLocked logs the first 12).
      if (DiagSplicePm4On()) {
        CheckNopWatchLocked("the next submission");
        if (g_nop_watch.size() < 64) {
          if (const auto *seg = GuestPhysicalPtr<const be_u32>(address); seg && bytes >= 16)
            g_nop_watch.push_back({address, bytes, device, u32(seg[0]), u32(seg[1]), u32(seg[2]), u32(seg[3])});
        }
      }
      auto it = g_composed.find(address);
      if (it != g_composed.end()) {
        buffers = std::move(it->second);
        g_composed.erase(it);
      }
      // sasrt-nx (2026-10-21, the "ocean" frames): each frame's composed buffer is spliced at the frame's start into the
      // next segment of a pool that walks down a page a frame, and submitted under that segment ~a frame later. When
      // the pool wraps (every ~63 frames, two chains), the last splice before the wrap is never submitted under its
      // own segment: a padding submission of another segment (one NOP over it) comes at its place, and that frame's
      // recorded buffers (a worker's scene pass) never ran: the frame showed the sky and sea under the HUD. A
      // submission that names no splice runs the composed buffer spliced last, if it is still waiting.
      // Only a padding submission: a segment that is one type-3 NOP (opcode 0x10) over all but its last words.
      const auto *pad = buffers.empty() && bytes >= 64 ? GuestPhysicalPtr<const be_u32>(address) : nullptr;
      const u32 pad_word = pad ? u32(pad[0]) : 0u;
      const bool padding = pad && (pad_word >> 30) == 3 && ((pad_word >> 8) & 0x7F) == 0x10 &&
                           (((pad_word >> 16) & 0x3FFF) + 2) * 4 + 16 >= bytes;
      static const bool wrap_run = REXCVAR_GET(sasrt_renut_pool_wrap_run);
      if (wrap_run && padding && g_last_splice_key && g_last_splice_key != address) {
        auto last = g_composed.find(g_last_splice_key);
        if (last != g_composed.end()) {
          static uint32_t logged = 0;
          if (logged++ < 8)
            RGPU_INFO("[sasrt] composed segment {:08X} submitted as {:08X} (its pool wrapped): its {} recorded buffers "
                      "run", g_last_splice_key, address, last->second.size());
          g_composed_range_matches.fetch_add(1, std::memory_order_relaxed);
          buffers = std::move(last->second);
          g_composed.erase(last);
        }
      }
      if (buffers.empty()) {
        // sasrt-nx (2026-10-21, diagnostics): a submission that ran no recorded buffer, with the splices still waiting.
        static uint32_t logged = 0;
        if (logged++ < 8 || SequenceWindow()) {
          std::string waiting;
          for (const auto &[key, list_waiting] : g_composed)
            waiting += fmt::format(" {:08X}({})", key, list_waiting.size());
          RGPU_INFO("[sasrt] ring submission without recorded buffers: segment {} of {}: {:08X} + {:X} bytes (word "
                    "{:08X}); splices waiting:{}", i, count, address, bytes, u32(list[i * 2]),
                    waiting.empty() ? std::string(" none") : waiting);
          // Its type-3 packets (opcode and first words), for the indirect buffers it runs.
          if (logged <= 4) {
            if (const auto *seg = GuestPhysicalPtr<const be_u32>(address)) {
              std::string packets;
              for (u32 w = 0, n = 0; w < bytes / 4 && n < 40; ++n) {
                const u32 h = u32(seg[w]);
                if ((h >> 30) == 3) {
                  const u32 op = (h >> 8) & 0x7F, len = ((h >> 16) & 0x3FFF) + 1;
                  packets += fmt::format(" [{:02X}", op);
                  for (u32 k = 1; k <= len && k <= 3 && w + k < bytes / 4; ++k)
                    packets += fmt::format(" {:08X}", u32(seg[w + k]));
                  packets += "]";
                  w += 1 + len;
                } else {
                  packets += fmt::format(" ({:08X})", h);
                  w += 1 + ((h >> 30) == 0 ? ((h >> 16) & 0x3FFF) + 1 : 0);
                }
              }
              RGPU_INFO("[sasrt]   its packets:{}", packets);
            }
          }
        }
        // sasrt-nx (2026-11-20): its splice may still come (the worker behind the game): dropped then (the splice hook).
        if (!padding) {
          g_late_keys.push_back(address);
          if (g_late_keys.size() > 16)
            g_late_keys.pop_front();
        }
        g_empty_submits.fetch_add(1, std::memory_order_relaxed);
        // Its place in the stream still gets a scene: the same-frame scene's next splice (one player) or its view's
        // next recording (split screen's places); before, nothing ran there (the view of sky and sea).
        if (!SceneSameFrameOn() && !(SplitSceneMode() == 2 && g_split_history_used.load(std::memory_order_relaxed)))
          continue;
      }
    }
    g_composed_submits.fetch_add(1, std::memory_order_relaxed);
    sasrt::trace::Note(sasrt::trace::kSubmit, address, buffers.size());  // sasrt-nx (2026-11-08, sasrt_renut_diag_trace)
    {  // sasrt-nx (2026-10-21, diagnostics): the matched submissions in order, with the splices still waiting.
      if (SequenceWindow()) {
        std::string waiting;
        {
          std::lock_guard lock(g_composed_mutex);
          for (const auto &[key, list_waiting] : g_composed)
            waiting += fmt::format(" {:08X}({})", key, list_waiting.size());
        }
        RGPU_INFO("[sasrt] composed submission {:08X}: {} buffers; still waiting:{}", address, buffers.size(),
                  waiting.empty() ? std::string(" none") : waiting);
      }
    }
    RunReadyCallbacks();
    // sasrt-nx (2026-11-04, sasrt_renut_diag_splice_pm4): the segment's indirect-buffer packets, in order, name the
    // spliced buffers' PM4; c128-c131 read there (what the GPU would execute) against the recorded snapshot's.
    std::vector<std::pair<u32, u32>> pm4_ibs;
    if (DiagSplicePm4On() && !buffers.empty()) {
      if (const auto *seg = GuestPhysicalPtr<const be_u32>(address)) {
        const u32 n = std::min<u32>(bytes / 4, 1u << 16);
        for (u32 i = 0; i < n && pm4_ibs.size() < buffers.size();) {
          const u32 h = u32(seg[i]);
          const u32 type = h >> 30;
          if (type == 3) {
            const u32 op = (h >> 8) & 0x7Fu, c = ((h >> 16) & 0x3FFFu) + 1;
            if ((op == 0x3F || op == 0x37) && c >= 2 && i + 2 < n)
              pm4_ibs.emplace_back(u32(seg[i + 1]) & 0x1FFFFFFFu, u32(seg[i + 2]) & 0xFFFFFu);
            i += 1 + c;
          } else if (type == 0) {
            i += h ? ((h >> 16) & 0x3FFFu) + 2 : 1;
          } else {
            i += type == 1 ? 3 : 1;
          }
        }
      }
    }
    if (DiagSplicePm4On() && !buffers.empty()) {  // sasrt-nx (2026-11-04): the segment's packets, the first eight times
      static std::atomic<uint32_t> census_logged{0};
      if (census_logged.load(std::memory_order_relaxed) < 8) {
        std::string census;
        bool other = false;  // anything besides NOPs and empty words
        if (const auto *seg = GuestPhysicalPtr<const be_u32>(address)) {
          const u32 n = std::min<u32>(bytes / 4, 4096);
          u32 packets = 0;
          for (u32 i = 0; i < n && packets < 48; ++packets) {
            const u32 h = u32(seg[i]);
            const u32 type = h >> 30;
            if (type == 3) {
              const u32 op = (h >> 8) & 0x7Fu, c = ((h >> 16) & 0x3FFFu) + 1;
              other |= op != 0x10;
              census += fmt::format(" [3:{:02X} n{}", op, c);
              for (u32 k = 1; k <= c && k <= 3 && i + k < n; ++k)
                census += fmt::format(" {:08X}", u32(seg[i + k]));
              census += "]";
              i += 1 + c;
            } else if (type == 0) {
              const u32 c = h ? ((h >> 16) & 0x3FFFu) + 1 : 0;
              other |= h != 0;
              census += fmt::format(" [0:{:04X} n{}]", h & 0x7FFFu, c);
              i += h ? 1 + c : 1;
            } else {
              census += fmt::format(" [{}:{:08X}]", type, h);
              i += type == 1 ? 3 : 1;
            }
          }
        }
        if (other && census_logged.fetch_add(1, std::memory_order_relaxed) < 8)
          RGPU_INFO("[sasrt] splice pm4 census: segment {:08X} + {:X} bytes, {} spliced buffers (first {:08X}):{}", address,
                    bytes, buffers.size(), buffers.empty() ? 0u : buffers[0].buffer, census);
      }
    }
    size_t pm4_k = 0;
    // sasrt-nx (2026-11-19, sasrt_renut_split_scene): decided once for the submission.
    const bool same_frame = SceneSameFrameOn();
    const u32 views = std::clamp<u32>(g_sasrt_split_views.load(std::memory_order_relaxed), 1u, 4u);
    const bool split_shift = !same_frame && SplitSceneOn() && views > 1;
    for (SplicedBuffer &spliced : buffers) {
      g_composed_runs.fetch_add(1, std::memory_order_relaxed);
      if (sasrt::trace::On())  // sasrt-nx (2026-11-19)
        sasrt::trace::Note(sasrt::trace::kSubmitBuffer, spliced.buffer,
                           SasrtRunCameraX(spliced.recording.get(), spliced.buffer));
      if (DiagSplicePm4On() && pm4_k < pm4_ibs.size() && spliced.recording) {
        const auto [ib_phys, ib_dwords] = pm4_ibs[pm4_k++];
        g_pm4_checked.fetch_add(1, std::memory_order_relaxed);
        u32 pm4[16] = {}, snap[16] = {};
        const bool have_pm4 = ReadC128FromPm4(ib_phys, ib_dwords, pm4);
        const bool have_snap = CapturedRunVertexConstants(*spliced.recording, spliced.buffer, 128, 4, snap);
        if (have_pm4 && have_snap) {
          g_pm4_found.fetch_add(1, std::memory_order_relaxed);
          const bool differ = std::memcmp(pm4, snap, sizeof(pm4)) != 0;
          if (differ)
            g_pm4_differ.fetch_add(1, std::memory_order_relaxed);
          static std::atomic<uint32_t> differ_logged{0};
          if ((differ && differ_logged.fetch_add(1, std::memory_order_relaxed) < 200) ||
              g_pm4_logged.fetch_add(1, std::memory_order_relaxed) < 48)
            RGPU_INFO("[sasrt] splice pm4: frame {} buffer {:08X} ib {:08X}+{:X}: {} | PM4 at the submission:{} | the "
                      "recording's first draw:{}", g_sasrt_game_frames.load(std::memory_order_relaxed), spliced.buffer,
                      ib_phys, ib_dwords * 4, differ ? "DIFFERS" : "the same", C128Text(pm4), C128Text(snap));
        } else if (g_pm4_logged.fetch_add(1, std::memory_order_relaxed) < 48) {
          RGPU_INFO("[sasrt] splice pm4: frame {} buffer {:08X} ib {:08X}+{:X}: c128 {} in the PM4, {} in the recording",
                    g_sasrt_game_frames.load(std::memory_order_relaxed), spliced.buffer, ib_phys, ib_dwords * 4,
                    have_pm4 ? "found" : "not found", have_snap ? "found" : "not found");
        }
      }
      if (!spliced.recording)  // sasrt-nx (2026-11-04, sasrt_renut_splice_ended): never ended before the submission
        g_splice_at_submit.fetch_add(1, std::memory_order_relaxed);
      if (spliced.found) {  // sasrt-nx (2026-11-04, sasrt_renut_diag_splice_pm4)
        u32 now[16] = {};
        const bool ok = ReadC128FromPm4(spliced.ib_phys, spliced.ib_dwords, now);
        const bool differ = !ok || std::memcmp(now, spliced.at_splice, sizeof(now)) != 0;
        if (differ)
          g_pm4_differ.fetch_add(1, std::memory_order_relaxed);
        static std::atomic<uint32_t> differ_logged{0};
        if ((differ && differ_logged.fetch_add(1, std::memory_order_relaxed) < 200) ||
            g_pm4_logged.load(std::memory_order_relaxed) <= 48)
          RGPU_INFO("[sasrt] splice pm4: frame {} buffer {:08X} at the submission (frame {} now): {}{}", spliced.frame,
                    spliced.buffer, g_sasrt_game_frames.load(std::memory_order_relaxed),
                    differ ? (ok ? "DIFFERS:" : "NOT FOUND NOW") : "the same", differ && ok ? C128Text(now) : std::string());
      }
      if (same_frame) {
        // sasrt-nx (2026-11-08, sasrt_renut_scene_same_frame): the recording spliced next fills this place; this one
        // (the previous frame's) is the fallback.
        auto slot = std::make_shared<SasrtRunSlot>();
        slot->fallback_buffer = spliced.buffer;
        slot->fallback = spliced.recording ? std::move(spliced.recording) : CaptureCommandBufferRun(spliced.buffer);
        {
          std::lock_guard lock(g_composed_mutex);
          g_last_scene_buffer = slot->fallback_buffer;  // sasrt-nx (2026-11-20)
          g_last_scene = slot->fallback;
          while (g_open_slots.size() >= 4) {  // never filled (no splice came): their own fallback, now
            auto old = std::move(g_open_slots.front());
            g_open_slots.pop_front();
            FillCapturedRunSlot(*old, old->fallback_buffer, old->fallback);
          }
          g_open_slots.push_back(slot);
        }
        g_slot_opened.fetch_add(1, std::memory_order_relaxed);
        static const uint32_t timeout = uint32_t(REXCVAR_GET(sasrt_renut_scene_same_frame_timeout_ms));
        QueueCapturedRunSlot(device, std::move(slot), timeout);
      } else if (!split_shift) {
        QueueCapturedRun(device, spliced.buffer, std::move(spliced.recording));
      }
    }
    if (same_frame && buffers.empty()) {
      // sasrt-nx (2026-11-20): the submission named no recording (its splice late): its place as any other, the last
      // scene its fallback.
      auto slot = std::make_shared<SasrtRunSlot>();
      {
        std::lock_guard lock(g_composed_mutex);
        slot->fallback_buffer = g_last_scene_buffer;
        slot->fallback = g_last_scene;
        while (g_open_slots.size() >= 4) {
          auto old = std::move(g_open_slots.front());
          g_open_slots.pop_front();
          FillCapturedRunSlot(*old, old->fallback_buffer, old->fallback);
        }
        g_open_slots.push_back(slot);
      }
      g_slot_opened.fetch_add(1, std::memory_order_relaxed);
      static const uint32_t timeout = uint32_t(REXCVAR_GET(sasrt_renut_scene_same_frame_timeout_ms));
      QueueCapturedRunSlot(device, std::move(slot), timeout);
    }
    // sasrt-nx (2026-11-19, sasrt_renut_split_scene): in split screen the list (views - 1) submissions before this one
    // runs; this submission's is kept for the ones after (its buffers' recordings as at the splice, or now).
    std::vector<SplicedBuffer> run;
    std::shared_ptr<SplitView> prev;  // sasrt-nx (2026-11-20): this view's last place (mode 2)
    if (split_shift || g_split_history_used.load(std::memory_order_relaxed)) {  // one player: no lock
      std::lock_guard lock(g_composed_mutex);
      g_split_history_used.store(split_shift, std::memory_order_relaxed);
      if (!split_shift) {
        g_split_history.clear();
        g_split_ring.clear();
      } else {
        if (!buffers.empty()) {
          for (SplicedBuffer &b : buffers)
            if (!b.recording)
              b.recording = CaptureCommandBufferRun(b.buffer);
          g_split_history.push_back(std::move(buffers));
          while (g_split_history.size() > views)
            g_split_history.pop_front();
          // The oldest kept: views - 1 submissions back once the history is full; this one's until then.
          run = g_split_history.size() == views ? g_split_history.front() : g_split_history.back();
        }
        if (SplitSceneMode() == 2 && g_split_ring.size() >= views)
          prev = g_split_ring[g_split_ring.size() - views];
      }
    }
    if (split_shift && SplitSceneMode() == 2) {
      // sasrt-nx (2026-11-20): every submission of split screen is a view's place, named recordings or not: its
      // fallback and camera its view's last place's (`views` submissions back), else the history's (the first frames).
      auto view = std::make_shared<SplitView>();
      {
        std::lock_guard lock(g_composed_mutex);
        if (prev && prev->recording) {
          *view = *prev;
        } else if (run.size() == 1 && run[0].recording) {
          view->buffer = run[0].buffer;
          view->recording = run[0].recording;
          view->has_camera = SasrtRunCamera(run[0].recording.get(), run[0].buffer, view->camera);
        }
        g_split_ring.push_back(view);
        while (g_split_ring.size() > views)
          g_split_ring.pop_front();
      }
      if (view->recording && view->has_camera) {
        if (sasrt::trace::On())
          sasrt::trace::Note(sasrt::trace::kSplitRun, view->buffer, SasrtRunCameraX(view->recording.get(), view->buffer));
        auto slot = std::make_shared<SasrtRunSlot>();
        slot->fallback_buffer = view->buffer;
        slot->fallback = view->recording;
        {
          std::lock_guard lock(g_composed_mutex);
          while (!g_split_places.empty() && (g_split_places.size() >= 8 || SlotDone(*g_split_places.front().slot)))
            g_split_places.pop_front();
          SplitPlace place;
          place.slot = slot;
          std::memcpy(place.camera, view->camera, sizeof(place.camera));
          place.view = view;
          g_split_places.push_back(std::move(place));
        }
        static const uint32_t timeout = uint32_t(REXCVAR_GET(sasrt_renut_scene_same_frame_timeout_ms));
        QueueCapturedRunSlot(device, std::move(slot), timeout);
        run.clear();
      } else if (view->recording) {
        QueueCapturedRun(device, view->buffer, view->recording);
        run.clear();
      }
    }
    for (SplicedBuffer &b : run) {
      if (sasrt::trace::On())
        sasrt::trace::Note(sasrt::trace::kSplitRun, b.buffer, SasrtRunCameraX(b.recording.get(), b.buffer));
      // sasrt-nx (2026-11-19, sasrt_renut_split_scene 2): a place for the same frame's scene of this view (the first
      // scene recording to end with a camera near this one's), this recording its fallback.
      float camera[8];
      if (false && SplitSceneMode() == 2 && run.size() == 1 && SasrtRunCamera(b.recording.get(), b.buffer, camera)) {
        auto slot = std::make_shared<SasrtRunSlot>();
        slot->fallback_buffer = b.buffer;
        slot->fallback = b.recording;
        {
          std::lock_guard lock(g_composed_mutex);
          while (!g_split_places.empty() && (g_split_places.size() >= 8 || SlotDone(*g_split_places.front().slot)))
            g_split_places.pop_front();
          SplitPlace place;
          place.slot = slot;
          std::memcpy(place.camera, camera, sizeof(camera));
          g_split_places.push_back(std::move(place));
        }
        static const uint32_t timeout = uint32_t(REXCVAR_GET(sasrt_renut_scene_same_frame_timeout_ms));
        QueueCapturedRunSlot(device, std::move(slot), timeout);
        continue;
      }
      QueueCapturedRun(device, b.buffer, b.recording);
    }
  }
  MaybeReport();
}

// void sub_82CEF770(D3DCommandBuffer *pComposed, D3DCommandBuffer **ppBuffers, const DWORD *pValues, UINT Count,
//     DWORD Flags): indirect-buffer packets to each of ppBuffers' segments (with a packet of pValues[i] before each)
// written at the composed buffer's write pointer (+108). The buffers are noted under the write pointer's physical
// address, which the ring submission of the segment names (above).
BANJO_RENUT_HOOK_RAW(sub_82CEF770) {
  const u32 composed = ctx.r3.u32, buffers_va = ctx.r4.u32, count = ctx.r6.u32;
  sasrt::trace::Note(sasrt::trace::kSplice, composed, count);  // sasrt-nx (2026-11-08, sasrt_renut_diag_trace)
  const auto *words = composed ? GuestPtr<const be_u32>(composed) : nullptr;
  const auto *buffers = buffers_va ? GuestPtr<const be_u32>(buffers_va) : nullptr;
  // sasrt-nx (2026-10-21, the "ocean" frames): the recorded buffers run where they are spliced, on the title device. The
  // composed buffer's ring submission (sub_82CDE200) follows the splice at once, but every ~63 frames (the ring
  // wrapping) one went to the GPU by a path this hook does not see, so its buffers never ran: that frame's scene pass (a
  // worker's recorded buffer) was missing, the sky and sea left under the HUD.
  static const bool at_splice = REXCVAR_GET(sasrt_renut_run_at_splice);
  if (at_splice && words && buffers && count) {
    const u32 device = Video::GuestDevice();
    g_composed_submits.fetch_add(1, std::memory_order_relaxed);
    RunReadyCallbacks();
    for (u32 i = 0; i < count && i < 256; ++i) {
      if (const u32 b = buffers[i]) {
        g_composed_runs.fetch_add(1, std::memory_order_relaxed);
        QueueCapturedRun(device, b, CaptureCommandBufferRun(b));
      }
    }
  } else if (words && buffers && count) {
    const u32 key = u32(words[108 / 4]) & 0x1FFFFFFFu;
    // The recordings as they are now (what the spliced packets point at), taken before the composed lock.
    std::vector<SplicedBuffer> spliced;
    for (u32 i = 0; i < count && i < 256; ++i) {
      const u32 b = buffers[i];
      if (!b)
        continue;
      if (SpliceEndedOn()) {
        // sasrt-nx (2026-11-04): only a recording ended and not taken by a splice before (a buffer not recorded again
        // since holds the previous frame's); one still being recorded, or not recorded again yet, is taken at its end
        // (or, failing that, at the submission: QueueCapturedRun with none captured takes the buffer as it is then).
        int state = 3;
        std::shared_ptr<CapturedRun> recording = CaptureIfEndedRun(b, &state);
        (state == 0 ? g_splice_ended : state == 1 ? g_splice_in_progress : state == 2 ? g_splice_taken_before : g_splice_none)
            .fetch_add(1, std::memory_order_relaxed);
        spliced.push_back({b, std::move(recording)});
      } else {
        spliced.push_back({b, CaptureCommandBufferRun(b)});
      }
    }
    if (sasrt::trace::On())  // sasrt-nx (2026-11-19)
      for (const SplicedBuffer &s : spliced)
        sasrt::trace::Note(sasrt::trace::kSpliceBuffer, s.buffer, SasrtRunCameraX(s.recording.get(), s.buffer));
    std::lock_guard lock(g_composed_mutex);
    if (SceneSameFrameOn()) {  // sasrt-nx (2026-11-08, sasrt_renut_scene_same_frame)
      for (const SplicedBuffer &s : spliced) {
        if (!s.recording)
          continue;
        // sasrt-nx (2026-11-20): places whose wait ended (their fallback ran) are not filled: one too many in the queue
        // (a submission that was not a place's) is then gone after one timeout, not a timeout every frame.
        while (!g_open_slots.empty() && SlotDone(*g_open_slots.front()))
          g_open_slots.pop_front();
        if (g_open_slots.empty()) {
          g_slot_unmatched.fetch_add(1, std::memory_order_relaxed);
          continue;
        }
        auto slot = std::move(g_open_slots.front());
        g_open_slots.pop_front();
        FillCapturedRunSlot(*slot, s.buffer, s.recording);
        g_slot_spliced.fetch_add(1, std::memory_order_relaxed);
        if (sasrt::trace::On())  // sasrt-nx (2026-11-19)
          sasrt::trace::Note(sasrt::trace::kSlotFill, s.buffer, SasrtRunCameraX(s.recording.get(), s.buffer));
      }
    }
    // sasrt-nx (2026-11-20): a splice into a segment already submitted (the worker behind) is not kept.
    if (auto late = std::find(g_late_keys.begin(), g_late_keys.end(), key); late != g_late_keys.end()) {
      g_late_keys.erase(late);
      g_late_splices.fetch_add(1, std::memory_order_relaxed);
    } else {
      auto &list = g_composed[key];
      for (SplicedBuffer &s : spliced)
        list.push_back(std::move(s));
      g_last_splice_key = key;
    }
    if (g_composed.size() > 4096)  // never submitted (a composed buffer dropped): forget the oldest bookkeeping
      g_composed.erase(g_composed.begin());
  }
  // sasrt-nx (2026-10-21, diagnostics): where the splice's packets went, and whether a submission ran inside the call.
  const u32 before = words ? u32(words[108 / 4]) : 0u;
  // sasrt-nx (2026-11-04, sasrt_renut_diag_splice_pm4): the words at the write pointer before the original writes the
  // splice's packets there (the pointer word itself did not move across the call in the logged splices).
  constexpr u32 kPm4Watch = 1024;  // a page: the pool walks a page a frame
  u32 pm4_before[kPm4Watch];
  bool pm4_watch = false;
  if (DiagSplicePm4On() && !at_splice && words && buffers && count) {
    if (const auto *seg = GuestPhysicalPtr<const be_u32>(before & 0x1FFFFFFFu)) {
      for (u32 i = 0; i < kPm4Watch; ++i)
        pm4_before[i] = u32(seg[i]);
      pm4_watch = true;
    }
  }
  const uint64_t submits_before = g_submits.load(std::memory_order_relaxed);
  __imp__sub_82CEF770(ctx, base);
  const u32 after = words ? u32(words[108 / 4]) : 0u;
  // sasrt-nx (2026-11-04, sasrt_renut_diag_splice_pm4): the indirect-buffer packets written between the two write
  // pointers name each spliced buffer's PM4; c128-c131 read from it now, compared again at the submission.
  if (pm4_watch) {
    std::vector<std::pair<u32, u32>> ibs;
    if (const auto *seg = GuestPhysicalPtr<const be_u32>(before & 0x1FFFFFFFu)) {
      u32 n = 0, first_changed = kPm4Watch;  // the changed range
      for (u32 i = 0; i < kPm4Watch; ++i) {
        if (u32(seg[i]) != pm4_before[i]) {
          n = i + 1;
          first_changed = std::min(first_changed, i);
        }
      }
      (void)first_changed;  // the splice writes nothing into this page (PC, 2026-11-04): the compare is at the submission
      for (u32 i = 0; i < n && ibs.size() < count;) {
        const u32 h = u32(seg[i]);
        const u32 type = h >> 30;
        if (type == 3) {
          const u32 op = (h >> 8) & 0x7Fu, c = ((h >> 16) & 0x3FFFu) + 1;
          if ((op == 0x3F || op == 0x37) && c >= 2 && i + 2 < n)
            ibs.emplace_back(u32(seg[i + 1]) & 0x1FFFFFFFu, u32(seg[i + 2]) & 0xFFFFFu);
          i += 1 + c;
        } else if (type == 0) {
          i += h ? ((h >> 16) & 0x3FFFu) + 2 : 1;
        } else {
          i += type == 1 ? 3 : 1;
        }
      }
    }
    const uint64_t frame = g_sasrt_game_frames.load(std::memory_order_relaxed);
    std::lock_guard lock(g_composed_mutex);
    auto it = g_composed.find(before & 0x1FFFFFFFu);
    if (it != g_composed.end() && !ibs.empty()) {
      std::vector<SplicedBuffer> &list = it->second;
      const size_t first = list.size() >= ibs.size() ? list.size() - ibs.size() : 0;
      for (size_t k = 0; k < ibs.size() && first + k < list.size(); ++k) {
        SplicedBuffer &e = list[first + k];
        e.ib_phys = ibs[k].first;
        e.ib_dwords = ibs[k].second;
        e.frame = frame;
        e.found = ReadC128FromPm4(e.ib_phys, e.ib_dwords, e.at_splice);
        g_pm4_checked.fetch_add(1, std::memory_order_relaxed);
        if (e.found) {
          g_pm4_found.fetch_add(1, std::memory_order_relaxed);
          if (g_pm4_logged.fetch_add(1, std::memory_order_relaxed) < 48)
            RGPU_INFO("[sasrt] splice pm4: frame {} buffer {:08X} ib {:08X}+{:X} dwords at the splice:{}", frame,
                      e.buffer, e.ib_phys, e.ib_dwords * 4, C128Text(e.at_splice));
        }
      }
    }
  }
  const uint64_t submits_inside = g_submits.load(std::memory_order_relaxed) - submits_before;
  static uint32_t logged = 0;
  const bool odd = after < before || after - before > 0x400 || submits_inside;
  if ((odd && logged < 200) || logged < 6 || SequenceWindow()) {
    ++logged;
    RGPU_INFO("[sasrt] splice of {} buffers into {:08X}: write pointer {:08X} -> {:08X}{}", count, composed, before, after,
              submits_inside ? fmt::format(" ({} ring submissions inside the call)", submits_inside) : std::string());
  }
}

// D3D_SetSurfaceClip (sub_82CCB540; N&B 0x82223270): the window offset and scissor (registers 0x2080-0x2082, a type-0
// packet), which SetRenderTarget, SetViewport and SetScissorRect write straight into the command buffer: this game's
// Direct3D (2.0.21119) keeps no shadow of them, while Renut's draws take them from the device's window packet
// (+0x28C0, as N&B's Direct3D kept it). The packet the original wrote (between the write pointer before and after,
// +0x30, which points at the last word written) goes into that shadow. Without it, the frame's composite onto the
// 1280x720 output was cut to the window of an earlier 1152x544 pass.
BANJO_RENUT_HOOK_RAW_SHARED(sub_82CCB540) {
  const u32 device = ctx.r3.u32;
  auto *bytes = device ? GuestPtr<u8>(device) : nullptr;
  const auto word_at = [](const u8 *p) { return u32(*reinterpret_cast<const be_u32 *>(p)); };
  const u32 before = bytes ? word_at(bytes + 0x30) : 0u;
  __imp__sub_82CCB540(ctx, base);
  if (!bytes)
    return;
  const u32 after = word_at(bytes + 0x30);
  if (after <= before || after - before > 64 * 4)
    return;  // a new segment (or nothing written): left as it was
  for (u32 a = before + 4; a + 12 <= after; a += 4) {
    const auto *w = GuestPtr<const be_u32>(a);
    if (!w || u32(w[0]) != 0x00022080u)  // type 0, three registers from 0x2080
      continue;
    auto *packet = reinterpret_cast<be_u32 *>(bytes + 0x28C0);  // WindowOffset, WindowScissorTL, WindowScissorBR
    packet[0] = u32(w[1]);
    packet[1] = u32(w[2]);
    packet[2] = u32(w[3]);
    break;
  }
}

// void D3DVertexShader_Bind(D3DVertexShader*, DWORD Flags, D3DVertexDeclaration*, const DWORD *pStreamStrides,
//     D3DPixelShader*) [sub_82CE3340; N&B 0x82230E58 (Renut's D3DVertexShader_Bind_hook)]: the bind writes the
// declaration's formats, offsets and strides into the vertex shader's fetch instructions. This game binds its scene
// shaders so and then draws with no declaration set, so the containers dumped before the bind carry fetches without a
// format (Renut's shader cache: format 0, stride 0) and no layout came of them: every input read the zero stream and
// the race's track, karts and scenery collapsed to one point (a RenderDoc capture of the PC's D3D12: every post-VS
// vertex the same). sa2-nx's SA2 sets a declaration for its draws and never needed this. The game's own Bind runs (the
// microcode is the game's), then the shader record takes a copy of the declaration and the strides on the render
// thread, in order with the draws, as Renut's N&B hook does: a draw without a declaration uses the last bind, as the
// patched microcode does on the console.
REXCVAR_DEFINE_STRING(sasrt_renut_diag_bind_watch, "", "SASRT",
                      "Diagnostics: a vertex shader object (hex guest address) whose D3DVertexShader_Bind calls are "
                      "logged with their declarations' elements ([sasrt] bind watch)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_renut_recorded_binds, false, "SASRT",
                    "Renut's renderer: each draw keeps the vertex formats its shader was bound with when the game "
                    "made the draw (D3DVertexShader_Bind, sub_82CE3340), and its replay uses those. The workers' "
                    "recorded command buffers replay a frame after their binds, and the game binds one shader with "
                    "other layouts meanwhile: the draws read their vertices with another mesh's formats (the race's "
                    "octopus and sky triangles). Off: a draw uses the last bind queued before its replay")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

namespace {

// sasrt-nx (2026-10-21, sasrt_renut_recorded_binds): the last Bind of each vertex shader on the game threads (what its
// patched microcode holds now), and on the render thread the declaration each shader record was last given.
struct SasrtBinding {
  u32 declaration = 0;
  std::array<u32, d3d::kMaxStreams> strides{};
};
std::mutex g_bind_mutex;
std::unordered_map<u32, SasrtBinding> g_game_binds;
std::unordered_map<u32, SasrtBinding> g_applied_binds;  // render thread
std::atomic<uint64_t> g_binds_reapplied{0};

void ApplyBindingLocked(u32 shader_va, u32 declaration_va, const std::array<u32, d3d::kMaxStreams> &strides) {
  auto *shader = FindShaderLocked(shader_va, RecordKind::VertexShader);
  const VertexDeclarationRecord *declaration = FindGuestDeclarationLocked(declaration_va);
  if (!declaration)
    declaration = FindRecord<VertexDeclarationRecord>(declaration_va, RecordKind::VertexDeclaration);
  if (!shader || !declaration) {
    static uint32_t logged = 0;  // sasrt-nx (2026-10-21, diagnostics): a Bind Renut could not apply
    if (logged++ < 40)
      RGPU_INFO("[sasrt] bind of vertex shader {:08X} with declaration {:08X} not applied: {}", shader_va,
                declaration_va, !shader ? "no record of the shader yet" : "no record of the declaration");
    return;
  }
  // sasrt-nx (2026-10-29, the banjo-nx sync): the fast path (render/draw.cpp) may hold the declaration this replaces
  // (freed here) or one baked from it, and the strides below.
  InvalidateFastDrawForRecordLocked(shader);
  shader->bound_declaration = std::make_unique<VertexDeclarationRecord>(*declaration);
  for (const GuestVertexElement &element : declaration->elements)
    if (u32(element.Stream) < d3d::kMaxStreams)
      shader->bound_strides[u32(element.Stream)] = strides[u32(element.Stream)];
  {  // sasrt-nx (2026-10-21, diagnostics, sasrt_renut_diag_bind_watch): the binds of one shader object
    static const u32 watch = [] {
      const std::string v = REXCVAR_GET(sasrt_renut_diag_bind_watch);
      return v.empty() ? 0u : u32(std::strtoul(v.c_str(), nullptr, 16));
    }();
    static uint32_t logged = 0;
    if (watch && shader_va == watch && logged++ < 40) {
      std::string elements;
      for (const GuestVertexElement &e : declaration->elements)
        elements += fmt::format(" [s{} +{} type {:08X} usage {}{}]", u32(e.Stream), u32(e.Offset), u32(e.Type),
                                u32(e.Usage), u32(e.UsageIndex));
      RGPU_INFO("[sasrt] bind watch {:08X}: declaration {:08X} strides {} {} {} {} {} {} elements{}", shader_va,
                declaration_va, strides[0], strides[1], strides[2], strides[3], strides[4], strides[5], elements);
    }
  }
  g_applied_binds[shader_va] = SasrtBinding{declaration_va, strides};
}

}  // namespace

bool SasrtRecordedBindsOn() {
  static const bool on = REXCVAR_GET(sasrt_renut_recorded_binds);
  return on;
}

// A game thread, at a draw: the binding of 'shader_va' as the game made it last (false: never bound).
bool SasrtBindingOf(uint32_t shader_va, uint32_t *declaration, uint32_t *strides) {
  std::lock_guard lock(g_bind_mutex);
  auto it = g_game_binds.find(shader_va);
  if (it == g_game_binds.end())
    return false;
  *declaration = it->second.declaration;
  std::copy(it->second.strides.begin(), it->second.strides.end(), strides);
  return true;
}

// The render thread, at a draw's replay: the shader record given the draw's binding unless it holds it already.
void SasrtApplyRecordedBinding(uint32_t shader_va, uint32_t declaration, const uint32_t *strides) {
  std::array<u32, d3d::kMaxStreams> copy;
  std::copy(strides, strides + d3d::kMaxStreams, copy.begin());
  auto it = g_applied_binds.find(shader_va);
  if (it != g_applied_binds.end() && it->second.declaration == declaration && it->second.strides == copy)
    return;
  const uint64_t n = ++g_binds_reapplied;
  if (n <= 16 || n % 5000 == 0)
    RGPU_INFO("[sasrt] vertex shader {:08X} drawn with the binding it had at the draw (declaration {:08X}; the "
              "last bound was {:08X}; {} so far)",
              shader_va, declaration, it != g_applied_binds.end() ? it->second.declaration : 0u, n);
  ApplyBindingLocked(shader_va, declaration, copy);
}

BANJO_RENUT_HOOK_RAW(sub_82CE3340) {
  const u32 shader_va = ctx.r3.u32, declaration_va = ctx.r5.u32, strides_va = ctx.r6.u32;
  __imp__sub_82CE3340(ctx, base);
  if (!shader_va || !declaration_va)
    return;
  u32 strides[d3d::kMaxStreams] = {};
  if (const auto *guest_strides = strides_va ? GuestPtr<const be_u32>(strides_va) : nullptr)
    for (u32 st = 0; st < d3d::kMaxStreams; ++st)
      strides[st] = u32(guest_strides[st]);
  std::array<u32, d3d::kMaxStreams> copy;
  std::copy(std::begin(strides), std::end(strides), copy.begin());
  {  // sasrt-nx (2026-10-21, sasrt_renut_recorded_binds)
    std::lock_guard lock(g_bind_mutex);
    g_game_binds[shader_va] = SasrtBinding{declaration_va, copy};
  }
  render_thread::Queue([shader_va, declaration_va, copy] { ApplyBindingLocked(shader_va, declaration_va, copy); });
}

// HRESULT D3DDevice_BeginIndexedVertices(D3DDevice*, D3DPRIMITIVETYPE, INT BaseVertexIndex, UINT NumVertices,
//     UINT IndexCount, D3DFORMAT IndexDataFormat, UINT VertexStreamZeroStride, void **ppIndexData,
//     void **ppVertexData) [sub_82CD11C0]: ppVertexData is the caller's argument word at +84. The original reserves the
// vertices and indices in the command buffer after a DRAW_INDX packet and hands them out; the caller writes them and
// ends inline (D3DDevice_EndIndexedVertices, sub_82CD0B88: m_pRing = [device + 13844]). Every pass of the game's
// post-processing (sub_8278D2E8: the bloom and luminance chains, the tone map and the scene's composite onto the
// 1280x720 output) draws this way, and SA2's Renut has no hook for it (SA2 never calls it): without this the scene
// stayed white. As Renut's BeginVertices hook does: the renderer's own guest memory is handed out, the inline end
// leaves the ring as it was, and the draw (vertices then indices, one copy) is taken at the device's next hook.
namespace {
constexpr u32 kIndexedScratchSize = 4u << 20;
std::mutex g_indexed_scratch_mutex;
std::unordered_map<u32, u32> g_indexed_scratch;  // per device, as BeginVertices' scratch

u32 IndexedScratch(u32 device) {
  std::lock_guard lock(g_indexed_scratch_mutex);
  u32 &scratch = g_indexed_scratch[device];
  if (!scratch)
    scratch = records::AllocPhysicalBlock(kIndexedScratchSize);
  return scratch;
}

u32 Load32(u32 va) {
  const auto *p = GuestPtr<const be_u32>(va);
  return p ? u32(*p) : 0u;
}

void Store32(u32 va, u32 value) {
  if (auto *p = GuestPtr<be_u32>(va))
    *p = value;
}
}  // namespace

BANJO_RENUT_HOOK_RAW(sub_82CD11C0) {
  const u32 device = ctx.r3.u32, primitive = ctx.r4.u32, num_vertices = ctx.r6.u32, index_count = ctx.r7.u32;
  const i32 base_vertex = ctx.r5.s32;
  const bool indices_32 = (ctx.r8.u32 & 4) != 0;  // D3DFMT_INDEX32, as the original reads it
  const u32 stride = ctx.r9.u32, index_out = ctx.r10.u32, vertex_out = Load32(ctx.r1.u32 + 84);
  const u64 vertex_bytes = u64(num_vertices) * stride;
  const u32 index_offset = u32((vertex_bytes + 15) & ~u64(15));
  const u64 bytes = u64(index_offset) + u64(index_count) * (indices_32 ? 4 : 2);
  const u32 scratch = (vertex_bytes && index_count && bytes <= kIndexedScratchSize) ? IndexedScratch(device) : 0u;
  if (!scratch) {
    Store32(vertex_out, 0);
    Store32(index_out, 0);
    ctx.r3.u64 = 0x8007000Eu;  // E_OUTOFMEMORY, as the original's failure
    return;
  }
  // The inline end: m_pRing = [device + kDeviceOffsetVerticesRingEnd], left where it is.
  Store32(device + d3d::kDeviceOffsetVerticesRingEnd, Load32(device + u32(offsetof(d3d::Device, m_pRing))));
  DrawCall call;
  call.primitive = primitive;
  call.indexed = true;
  call.count = index_count;
  call.base_vertex = base_vertex;
  call.up_vertices = GuestPtr<const u8>(scratch);
  call.up_stride = stride;
  call.up_vertex_count = num_vertices;
  call.up_indices_32 = indices_32;
  call.up_index_offset = index_offset;
  auto &s = State();
  if (IsRecordingCommandBuffer(device))
    RecordDeferredDraw(device, call, call.up_vertices, u32(bytes));
  else if (s.host_ready && !s.shutting_down.load(std::memory_order_acquire))
    QueueDeferredDraw(device, call, call.up_vertices, u32(bytes));
  else
    FlushDeferredVertices(device);
  Store32(vertex_out, scratch);
  Store32(index_out, scratch + index_offset);
  ctx.r3.u64 = 0;
}

// sasrt-nx (2026-10-21, sasrt_renut_query_samples): this game issues occlusion queries in batches (Direct3D's
// occlusion query batch, sub_82CF1518 fills its 32-byte results with the "not done" sentinel 0xFFFFFEED). On the 360
// the GPU writes each result at the ring's EVENT_WRITE_ZPD (to RB_SAMPLE_COUNT_ADDR: begin, then end with the sentinel
// in it); Renut never runs the ring, so every result stays "not done". The emulated GPU answers them on the CPU (begin
// 0, end 1000 samples: me_native_system.cpp). A test: the title device's ring since its last rewind is walked here at
// the kick and the queries answered with the given count (-1: not at all, as before; -2: only counted, a [sasrt]
// line every 600 kicks).
REXCVAR_DEFINE_INT32(sasrt_renut_query_samples, -1, "SASRT",
                     "A test: Renut answers the game's occlusion queries (EVENT_WRITE_ZPD in the title device's ring) "
                     "with this many samples passed: 0 every query occluded, 1000 every one visible (the emulated "
                     "GPU's answer); -1 none (Direct3D's 'not done' stays, as before); -2 only counted")
    .range(-2, 1 << 20)
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

namespace {

void SasrtAnswerQueries(u32 begin, u32 end) {
  static const int32_t samples = REXCVAR_GET(sasrt_renut_query_samples);
  if (samples == -1 || end <= begin || end - begin > (16u << 20))
    return;
  const auto *w = GuestPtr<const be_u32>(begin);
  if (!w)
    return;
  static std::atomic<uint64_t> kicks{0}, begins{0}, ends{0}, other{0}, indirect{0};
  constexpr u32 kSampleCountAddr = 0x2325, kSentinel = 0xFFFFFEEDu;
  const u32 n = (end - begin) / 4;
  u32 sample_addr = 0;
  for (u32 i = 0; i < n;) {
    const u32 h = w[i];
    u32 count;
    switch (h >> 30) {
    case 0: count = h ? ((h >> 16) & 0x3FFF) + 1 : 0; break;
    case 1: count = 2; break;
    case 2: count = 0; break;
    default: count = ((h >> 16) & 0x3FFF) + 1; break;
    }
    if (i + 1 + count > n)
      break;
    const be_u32 *d = w + i + 1;
    if ((h >> 30) == 0 && h) {
      const u32 index = h & 0x7FFF;
      const bool single = (h >> 15) & 1;
      for (u32 k = 0; k < count; ++k)
        if ((single ? index : index + k) == kSampleCountAddr)
          sample_addr = d[k];
    } else if ((h >> 30) == 3) {
      const u32 op = (h >> 8) & 0x7F;
      if (op == 0x2D && count >= 1 && ((u32(d[0]) >> 16) & 0xFF) == 4) {  // SET_CONSTANT, registers
        const u32 base = 0x2000 + (u32(d[0]) & 0x7FF);
        for (u32 k = 1; k < count; ++k)
          if (base + k - 1 == kSampleCountAddr)
            sample_addr = d[k];
      } else if (op == 0x3F) {  // INDIRECT_BUFFER: not followed
        indirect.fetch_add(1, std::memory_order_relaxed);
      } else if (op == 0x5B) {  // EVENT_WRITE_ZPD
        auto *counts = sample_addr ? GuestPhysicalPtr<be_u32>(sample_addr & ~3u) : nullptr;
        if (!counts) {
          other.fetch_add(1, std::memory_order_relaxed);
        } else {
          // Total_A, Total_B, ZFail_A, ZFail_B, ZPass_A, ZPass_B, StencilFail_A, StencilFail_B (big-endian words)
          const bool is_end = u32(counts[2]) == kSentinel || u32(counts[3]) == kSentinel ||
                              u32(counts[4]) == kSentinel || u32(counts[5]) == kSentinel;
          (is_end ? ends : begins).fetch_add(1, std::memory_order_relaxed);
          if (samples >= 0) {
            for (u32 k = 0; k < 8; ++k)
              counts[k] = 0u;
            if (is_end)
              counts[0] = counts[4] = u32(samples);
          }
        }
      }
    }
    i += 1 + count;
  }
  if (const uint64_t k = kicks.fetch_add(1, std::memory_order_relaxed) + 1; k % 600 == 0)
    RGPU_INFO("[sasrt] occlusion queries in the title device's ring: {} begins, {} ends, {} without an address, {} "
              "indirect buffers not followed, in {} kicks (sasrt_renut_query_samples {})", begins.load(),
              ends.load(), other.load(), indirect.load(), k, samples);
}

}  // namespace

// sasrt-nx (2026-10-21, the "ocean" frames): the device ring's words between 'begin' and 'end' (written since its last
// rewind, d3d/hooks/device.cpp: KickOff, KickOffSegment, BeginRingBig) searched for the segments of composed command
// buffers still waiting for their submission: about every 63 frames the game sends one by writing its indirect-buffer
// packet into the ring itself, not through sub_82CDE200, and its recorded buffers (a worker's scene pass) never ran.
// They run here, in the ring's order, on the kicking device.
void SasrtScanRingForComposed(u32 device_va, u32 begin, u32 end) {
  SasrtAnswerQueries(begin, end);  // sasrt-nx (2026-10-21, sasrt_renut_query_samples)
  // 2026-10-21: no composed buffer was found in the ring (the frames' loss was the pool wrap, above): kept, unused.
  static constexpr bool kScan = false;
  if (!kScan || end <= begin || end - begin > (4u << 20))
    return;
  std::vector<SplicedBuffer> run;
  {
    std::lock_guard lock(g_composed_mutex);
    if (g_composed.empty())
      return;
    const auto *words = GuestPtr<const be_u32>(begin);
    if (!words)
      return;
    const u32 count = (end - begin) / 4;
    for (u32 i = 0; i < count && !g_composed.empty(); ++i) {
      const u32 v = u32(words[i]) & 0x1FFFFFFCu;
      if (!v)
        continue;
      auto it = g_composed.find(v);
      if (it == g_composed.end())
        continue;
      static uint32_t logged = 0;
      if (logged++ < 8)
        RGPU_INFO("[sasrt] composed segment {:08X} sent through device {:08X}'s ring (word {} of {}): its {} recorded "
                  "buffers run", v, device_va, i, count, it->second.size());
      g_composed_range_matches.fetch_add(1, std::memory_order_relaxed);
      for (SplicedBuffer &s : it->second)
        run.push_back(std::move(s));
      g_composed.erase(it);
    }
  }
  if (run.empty())
    return;
  g_composed_submits.fetch_add(1, std::memory_order_relaxed);
  RunReadyCallbacks();
  for (SplicedBuffer &spliced : run) {
    g_composed_runs.fetch_add(1, std::memory_order_relaxed);
    QueueCapturedRun(device_va, spliced.buffer, std::move(spliced.recording));
  }
}
