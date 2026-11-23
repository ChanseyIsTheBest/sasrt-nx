/**
 * @file    gpu/backend/queued.cpp
 */
#include "renut_engine/gpu/backend/queued.h"
#include "renut_engine/gpu/host_batch.h"  // blur-nx (2026-11-18, the Renut host batch)

#include <algorithm>
#include <atomic>
#include <bit>
#include <cstddef>
#include <cstring>
#include <initializer_list>
#include <memory>
#include <mutex>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

#include <fmt/format.h>
#include <rex/cvar.h>

#include "renut_engine/gpu/guest/callbacks.h"
#include "renut_engine/gpu/guest/guest_records.h"  // blur-nx (2026-11-13, #13): records::Lookup
#include "renut_engine/gpu/guest/resources.h"      // blur-nx (2026-11-13, #13): ShaderRecord
#include "renut_engine/gpu/shaders/shader_cache.h"  // blur-nx (2026-11-13, #13): ShaderCacheEntry::floatConstants
#include "renut_engine/gpu/guest/command_buffers.h"
#include "renut_engine/gpu/d3d/d3d.h"
#include "renut_engine/gpu/guest/guest_memory.h"
#include "renut_engine/gpu/log.h"
#include "renut_engine/gpu/render/surfaces.h"  // blur-nx (2026-11-10, port 76; its key 215): StackHeaderSet
#include "renut_engine/gpu/backend/render_thread.h"
#include "renut_engine/gpu/banjo_renut_tuning.h"
#include "renut_engine/gpu/render/surfaces.h"
#include "renut_engine/gpu/sa2_line_compare.h"
#include "renut_engine/gpu/line_compare.h"  // sasrt-nx (2026-11-08): the base's, with the delta masks
#include "renut_engine/gpu/d3d/d3d_native.h"  // sasrt-nx (2026-11-10, sasrt_capture_marks): the marks and the tags

#include <chrono>

// sasrt-nx (2026-10-21, sasrt_renut_recorded_binds): app/src/renut_engine/sasrt_renut_hooks.cpp.
bool SasrtRecordedBindsOn();
bool SasrtBindingOf(uint32_t shader_va, uint32_t *declaration, uint32_t *strides);
void SasrtApplyRecordedBinding(uint32_t shader_va, uint32_t declaration, const uint32_t *strides);

REXCVAR_DEFINE_BOOL(sasrt_renut_diag_late_streams, false, "SASRT",
                    "Diagnostics: each draw's bound vertex streams (their first 4 KB) hashed at the game's draw "
                    "call and again when Renut's render thread replays the draw; the ones that changed between are "
                    "logged ([sasrt] late stream)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

namespace renut::gpu {

const SasrtStreamHashes *g_sasrt_draw_streams = nullptr;
bool g_sasrt_draw_recorded = false;

// sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams): the title device's streams since the last kick (game
// thread), and their hashes at the kick (render thread).
std::mutex g_sasrt_kick_mutex;
std::vector<std::pair<u32, u32>> g_sasrt_kick_list;
std::unordered_map<u32, uint64_t> g_sasrt_kick_hashes;

// sasrt-nx (2026-10-21): what the replays read of index data since the last kick (render thread).
std::unordered_map<u32, uint64_t> g_sasrt_replay_indices;

void SasrtCountIndexCompare(u32 address, bool same) {
  static uint64_t compared = 0, differ = 0, logged = 0;
  static auto next = std::chrono::steady_clock::now() + std::chrono::seconds(10);
  ++compared;
  if (!same && (++differ, logged++ < 60 || logged % 1000 == 0))
    RGPU_INFO("[sasrt] late indices: a draw's indices at {:08X} as the replay read them differ from the game's "
              "at its kick ({} so far)", address, logged);
  if (std::chrono::steady_clock::now() >= next) {
    next = std::chrono::steady_clock::now() + std::chrono::seconds(10);
    RGPU_INFO("[sasrt] late indices in 10 s: {} compared with the kick, {} differ", compared, differ);
    compared = differ = 0;
  }
}

void SasrtNoteReplayIndices(u32 address, const u8 *data, u32 size) {
  if (!SasrtLateStreamsOn() || !data || !size)
    return;
  const uint64_t hash = banjo::renut_gpu::ContentHash64(data, std::min<u32>(size, 4096u));
  // A recorded buffer's draw: its kick hashes came before its replay.
  if (auto it = g_sasrt_kick_hashes.find(address); it != g_sasrt_kick_hashes.end())
    SasrtCountIndexCompare(address, it->second == hash);
  else
    g_sasrt_replay_indices[address] = hash;
}

void SasrtNoteKickRange(u32 va, u32 size) {
  std::lock_guard lock(g_sasrt_kick_mutex);
  g_sasrt_kick_list.emplace_back(va, size);
}

void SasrtCompareReplayIndices() {
  for (const auto &[address, hash] : g_sasrt_replay_indices) {
    if (auto it = g_sasrt_kick_hashes.find(address); it != g_sasrt_kick_hashes.end())
      SasrtCountIndexCompare(address, it->second == hash);
  }
  g_sasrt_replay_indices.clear();
}

void SasrtQueueKickHashes() {
  if (!SasrtLateStreamsOn())
    return;
  std::vector<std::pair<u32, uint64_t>> hashes;
  {
    std::lock_guard lock(g_sasrt_kick_mutex);
    hashes.reserve(g_sasrt_kick_list.size());
    for (const auto &[va, size] : g_sasrt_kick_list) {
      // GPU (physical) addresses of vertex streams; an index buffer's may be a CPU one.
      if (const u8 *p = va < 0x20000000u ? GuestPhysicalPtr<const u8>(va) : GuestPtr<const u8>(va))
        hashes.emplace_back(va, banjo::renut_gpu::ContentHash64(p, size));
    }
    g_sasrt_kick_list.clear();
  }
  render_thread::QueueUnlocked([hashes = std::move(hashes)] {
    for (const auto &[va, hash] : hashes)
      g_sasrt_kick_hashes[va] = hash;
    SasrtCompareReplayIndices();  // sasrt-nx: index data
  });
}

void SasrtCheckKick(u32 va, u32 size) {
  static uint64_t checked = 0, changed = 0, logged = 0;
  static auto next = std::chrono::steady_clock::now() + std::chrono::seconds(10);
  auto it = g_sasrt_kick_hashes.find(va);
  const u8 *p = GuestPhysicalPtr<const u8>(va);
  if (it != g_sasrt_kick_hashes.end() && p) {
    ++checked;
    if (banjo::renut_gpu::ContentHash64(p, size) != it->second) {
      ++changed;
      if (logged++ < 60 || logged % 1000 == 0)
        RGPU_INFO("[sasrt] late stream after the kick: a draw's stream at {:08X} changed between the game's "
                  "kick and the conversion ({} so far)", va, logged);
    }
  }
  if (std::chrono::steady_clock::now() >= next) {
    next = std::chrono::steady_clock::now() + std::chrono::seconds(10);
    RGPU_INFO("[sasrt] late streams after the kick in 10 s: {} compared, {} changed", checked, changed);
    checked = changed = 0;
  }
}

void SasrtClearKickHashes() {
  g_sasrt_kick_hashes.clear();
}

bool SasrtLateStreamsOn() {
  static const bool on = REXCVAR_GET(sasrt_renut_diag_late_streams);
  return on;
}

void SasrtHashStreams(const u8 *device_bytes, SasrtStreamHashes &out) {
  out.count = 0;
  for (u32 s = 0; s < 16u && out.count < 4; ++s) {  // the vertex streams (kMaxVertexStreams)
    if (!u32(*reinterpret_cast<const be_u32 *>(device_bytes + d3d::kDeviceOffsetStreamSources + s * 4)))
      continue;  // no vertex buffer bound there
    const u32 index = d3d::kFirstVertexFetchIndex + d3d::StreamFetchIndex(s);
    const u8 *w = device_bytes + offsetof(d3d::Device, m_Constants) + index * 8;
    const u32 w0 = *reinterpret_cast<const be_u32 *>(w), w1 = *reinterpret_cast<const be_u32 *>(w + 4);
    const u32 va = w0 & ~3u, size = std::min<u32>(w1 & 0x3FFFFFCu, 4096u);
    const u8 *p = va && size ? GuestPhysicalPtr<const u8>(va) : nullptr;
    if (!p)
      continue;
    out.va[out.count] = va;
    out.size[out.count] = size;
    out.stream[out.count] = s;
    out.hash[out.count] = banjo::renut_gpu::ContentHash64(p, size);
    ++out.count;
  }
}

void SasrtCheckStreams(const SasrtStreamHashes &in, bool recorded) {
  static std::mutex mutex;
  static uint64_t checked = 0, changed[2] = {}, logged = 0, total_changed = 0;
  static auto next = std::chrono::steady_clock::now() + std::chrono::seconds(10);
  std::lock_guard lock(mutex);
  for (u32 i = 0; i < in.count; ++i) {
    const u8 *p = GuestPhysicalPtr<const u8>(in.va[i]);
    ++checked;
    if (!p || banjo::renut_gpu::ContentHash64(p, in.size[i]) == in.hash[i])
      continue;
    ++changed[recorded ? 1 : 0];
    if (logged++ < 60 || ++total_changed % 2000 == 0)
      RGPU_INFO("[sasrt] late stream: {} draw's stream {} at {:08X} ({} bytes hashed) changed between the "
                "game's draw call and the replay", recorded ? "a recorded buffer's" : "a title device", in.stream[i],
                in.va[i], in.size[i]);
  }
  if (std::chrono::steady_clock::now() >= next) {
    next = std::chrono::steady_clock::now() + std::chrono::seconds(10);
    RGPU_INFO("[sasrt] late streams in 10 s: {} checked, {} changed in title device draws, {} in recorded "
              "buffers' draws", checked, changed[0], changed[1]);
    checked = changed[0] = changed[1] = 0;
  }
}

}  // namespace renut::gpu

REXCVAR_DECLARE(bool, blur_renut_flush_fast_local);  // blur-nx (2026-11-17): defined in guest/command_buffers.cpp

// sa2-nx (2026-10-20): see SnapshotKind below.
REXCVAR_DEFINE_BOOL(banjo_renut_snapshot_deltas, true, "SA2/Renderer",
                    "Renut's renderer: a draw keeps what changed in the device since the device's previous draw (its "
                    "64-byte chunks that differ, and the float constant groups the game marked dirty) instead of a "
                    "copy of the device's first 13,088 bytes; the render thread rebuilds the device from them. Off: "
                    "the whole copy for every draw")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(banjo_renut_snapshot_deltas_constants, true, "SA2/Renderer",
                    "Renut's renderer (banjo_renut_snapshot_deltas): the chain's draws tell the constant uploads which "
                    "float constant groups changed since the previous draw, so only those are compared with what the "
                    "GPU holds (as a recorded command buffer's replayed draws do); a frame's first draw compares them "
                    "all. Off: every draw compares every group its shaders read")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(banjo_renut_capture_batches, true, "SA2/Renderer",
                    "Renut's renderer (with banjo_renut_capture_pool): the game thread takes its draws' captures from "
                    "the pool, and the render thread gives them back, 32 at a time instead of one lock of the pool's "
                    "per draw on each thread. Off: one at a time")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
// bangaio-nx (2026-10-29): see CapturePool::Keeps.
REXCVAR_DEFINE_BOOL(banjo_renut_small_captures, true, "Banjo/Enhancements",
                    "Renut's renderer (banjo_renut_capture_pool): a delta is written into the chain's own scratch and "
                    "copied into its capture at its size (about 250 bytes), instead of into the capture's 12.9 KB "
                    "storage (zero-filled when the capture was made), and the pool keeps up to 8,192 captures or 32 MB "
                    "instead of 2,048. Bangai-O's missile storms queue ~4,250 draws a frame: past 2,048 the pool deleted "
                    "and made again ~2,200 captures a frame. Same data. In-run A/B target 82 (70 in bangaio-nx)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
// sasrt-nx (2026-11-10, item 24 for the game's own draws: SlRenderer's CaptureDelta was 9 % of that thread, run lat12).
// Each draw on the title device compared the device's 40 read chunks with the chain's shadow. With this key the title
// device gets a mark slot too (d3d/hooks/device.cpp) and a delta compares only the chunks marked since the chain's last
// draw: D3D's own dirty tags (m_Pending words 2-4, read before the delta clears them, native::TagChunks), the native
// layer's marks, and the chunks run tv1 found written without a tag (the tile predication words and the pixel shader
// pointer). Every sasrt_capture_marks_check-th delta compares all of them and checks that nothing changed unmarked: a
// change found is logged and the marks are not used again (1: every delta compared whole, each such chunk logged once).
REXCVAR_DEFINE_BOOL(sasrt_capture_marks, false, "SASRT/Recording",
                    "The game's own draws (CaptureDelta, SlRenderer): a delta compares only the device chunks marked "
                    "or tagged since the chain's previous draw instead of every read chunk (the title device gets a mark "
                    "slot). Off: every read chunk compared (as before)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_INT32(sasrt_capture_marks_check, 32, "SASRT/Recording",
                     "sasrt_capture_marks: every Nth delta compares every read chunk and checks the marks (a chunk changed "
                     "without one: logged, and the marks are not used again). 1: the verify form (every delta compared "
                     "whole, each such chunk logged once, the marks kept). 0: never checked")
    .range(0, 1 << 20)
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

// bangaio-nx (2026-10-29): see DeltaRuns.
REXCVAR_DEFINE_BOOL(banjo_renut_delta_masks, true, "Banjo/Enhancements",
                    "Renut's renderer on the Switch (banjo_renut_snapshot_deltas): the game thread finds a draw's "
                    "changed device chunks with one NEON reduction per four chunks of a run (the 40 compared chunks are "
                    "three runs), then visits only those (1.1 a draw), instead of a reduction, a move to a register and "
                    "a branch per chunk (65 % of CaptureDelta, 18 % of the game thread in the v4 console storm). The "
                    "same chunks. In-run A/B target 81 (73 in bangaio-nx)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
// bangaio-nx (2026-10-29, v6): see PrefetchDeltaLines.
REXCVAR_DEFINE_BOOL(banjo_renut_delta_prefetch, true, "Banjo/Enhancements",
                    "Renut's renderer (banjo_renut_snapshot_deltas): a queued draw first asks for the device and shadow "
                    "lines its delta compares (80 lines), so that their cache misses overlap each other and the draw's "
                    "other work instead of stalling the compare (CaptureDelta's samples were its loads in the v5 console "
                    "storm). A hint only: the same data. In-run A/B target 84 (74 in bangaio-nx)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
// blur-nx (2026-11-13, #13 of Blur's docs/cpu-near-exact-50-1113.md, found exact): a Begin*Vertices draw's capture (a
// whole device, queued later than made) copies of the float constants only the registers its two shaders read. The
// render thread reads a whole capture's state for that draw alone (DeviceForDraw), and of the 8 KB of float constants
// only the registers in the bound shaders' cache entries (ShaderCacheEntry::floatConstants: UploadFloatConstants'
// vs_used / ps_used, all of them when the shader indexes the register file); every other byte is copied. A shader
// missing from the cache, or neither a renderer record nor an in-place XGRegister shader: the whole device as before.
// (The first census found none narrowed: every shader of Blur's is an in-place one, which only the render thread's map
// held; the game threads now keep their own, InPlaceShaderEntry.) Blur's console races: ~3,000 such draws a second at 12.9 KB each on the Game Master.
// sasrt-nx (2026-11-19, base port 138 merge): OFF in this port. Besides the float constants its shaders read, a
// narrowed capture leaves out the device bytes before 0x480 and the private words 11008-12223 (#54), the list
// banjo_renut_snapshot_deltas_narrow keeps off here until it is derived for this game's XDK. A candidate for an A/B
// after a PC run with banjo_renut_deferred_narrow_poison.
REXCVAR_DEFINE_BOOL(banjo_renut_deferred_narrow, false, "Banjo/Enhancements",
                    "Renut's renderer: a Begin*Vertices draw's device capture copies of the float constants only the "
                    "registers its vertex and pixel shaders read (their cache entries' masks; the whole device when a "
                    "shader has none). Exact: the render thread reads no other register of that capture. Off: the "
                    "whole device, as before")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(banjo_renut_deferred_narrow_groups, true, "Banjo/Enhancements",
                    "banjo_renut_deferred_narrow (blur-nx #53): the float constants copied by the 64-byte groups "
                    "(four registers) the shaders read, not up to their highest register. Exact either way")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(banjo_renut_deferred_narrow_poison, false, "Banjo/Debug",
                    "banjo_renut_deferred_narrow's check: the float constant registers a narrowed capture leaves out "
                    "are filled with NaNs (a render path that read them would draw visibly wrong)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
// sasrt-nx (2026-11-08): this port's default: off (sasrt-nx, 2026-10-20: "off until derived for this game").
REXCVAR_DEFINE_BOOL(banjo_renut_snapshot_deltas_narrow, false, "Banjo/Enhancements",
                    "Renut's renderer (banjo_renut_snapshot_deltas): the game thread compares only the device chunks the "
                    "render thread reads (40 of 77 in SASRT: not the dirty masks, ring pointers and call tables before "
                    "the fetch constants, nor the private words from 11008 to 12223). Off in this port until the list "
                    "is derived for this game: all 77")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sa2_renut_deferred_chain, true, "SA2/Renderer",
                    "Renut's renderer (from futari-nx, as peggle2-nx has it): Begin*Vertices draws are deltas of the "
                    "device snapshot chain too, not whole 13 KB copies (banjo_renut_snapshot_deltas). Made and queued "
                    "under the chain's lock; every hook queues its device's waiting Begin*Vertices draw first, so the "
                    "chain stays in order. Off: whole copies outside the chain, as before")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(banjo_renut_neon_compare, true, "SA2/Renderer",
                    "Renut's renderer on the Switch: the device chunks of the delta chain and the pushed shared "
                    "constants' lines are compared 64 bytes at a time with NEON (four 128-bit loads a side) instead of "
                    "eight 64-bit words, which GCC left scalar. Off: the 64-bit words")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(banjo_renut_snapshot_deltas_verify, false, "SA2/Renderer",
                    "Tests (banjo_renut_snapshot_deltas): every draw also keeps the whole copy, and the render thread "
                    "counts the draws whose rebuilt device differs from it in any byte (the 10 s \"[renut] device "
                    "snapshots\" line)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

namespace renut::gpu {

namespace {

// sa2-nx (2026-10-20, banjo_renut_snapshot_deltas): how a queued draw holds its device.
//   Whole:  DrawCapture::state is the device's first kDeviceSnapshotSize bytes (every draw before; the Begin*Vertices
//           draws, which are queued later than they are captured, still).
//   Rebase: the same, and the render thread takes it as its device (the chain's first draw, and each frame's).
//   Delta:  DrawCapture::state is a DeltaHeader and the bytes it names: the render thread applies them to its device.
// SA2 records no command buffers, so every draw was a whole copy: 13 KB a draw, 15-18 MB a frame of City Escape's
// 1,100-1,400 draws written on the game thread, into pooled captures last touched by the render thread on another
// core, then read back by the render thread. A draw changes a few bindings, render states and constants: the deltas are
// those. The chain's order is the queue's: deltas are made and queued under g_delta.mutex, and the render thread runs
// the queue in order.
enum class SnapshotKind : u8 { Whole, Rebase, Delta };

// What a queued draw reads besides guest memory the game keeps until a fence.
struct DrawCapture {
  std::vector<u8> state;  // the device, kDeviceSnapshotSize bytes (or a delta: SnapshotKind)
  std::vector<u8> vertices, indices;
  SnapshotKind snapshot = SnapshotKind::Whole;  // sa2-nx (2026-10-20)
  std::vector<u8> verify;  // sa2-nx: the whole device as well (banjo_renut_snapshot_deltas_verify)
  DrawCall call;
  u32 binding = 0;  // halo3-nx (2026-11-03, banjo_renut_recorded_binds): the shader's bind at the draw (LastBindingOf)
  // banjo-nx (2026-10-19, CPU proposal 23): a queued clear's or resolve's arguments. They come from the same pool as
  // the draws' captures: each made three heap allocations on the game thread (its arguments, a device snapshot, a
  // closure too large for std::function's own storage), freed on the render thread through the one malloc lock.
  u32 flags = 0;
  bool has_rect = false, has_color = false, has_dest_format = false;
  ClearRect rect{};
  float color[4] = {};
  float depth = 0.0f;
  u32 stencil = 0;
  u32 dest_texture_va = 0, dest_level = 0, dest_slice = 0;
  i32 dest_x = 0, dest_y = 0;
  d3d::TextureFetchConstant dest_format{};
  u32 resolve_targets[kResolveTargetWords] = {};  // blur-nx (2026-11-13, M-35): a resolve's device words (draw.h)
  float clear_viewport[4] = {};                    // blur-nx (2026-11-13, #55): a clear's viewport (draw.h)
  u32 held = 0;  // bangaio-nx (2026-10-29): the bytes it holds, set when it goes back to the pool (CapturePool::Give)
  // sasrt-nx: the bound surfaces' headers at the call (render targets 0-3, then depth).
  u32 surfaces = 0;
  u32 surface_va[5] = {};
  d3d::SurfaceDesc surface_desc[5] = {};
  u32 ib_va = 0;          // sasrt-nx (2026-10-21): the bound index buffer object, as it was (CaptureSurfaces)
  d3d::IndexBuffer ib{};
  SasrtStreamHashes sasrt_streams;  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams)
  // sasrt-nx (2026-10-21, sasrt_renut_recorded_binds): the vertex shader's binding at the call (0: none known).
  u32 sasrt_vs = 0, sasrt_decl = 0;
  u32 sasrt_strides[d3d::kMaxStreams] = {};
  // blur-nx (2026-11-10, port 76; its key 215: blur_renut_stack_surface_headers): the headers of the stack surfaces bound
  // as targets when this draw, clear or resolve was captured (render/surfaces.h); count 0 nearly always.
  // sasrt-nx (2026-11-13, base port 76): a subset of 'surface_desc' above, which render/surfaces.cpp reads first.
  StackHeaderSet stack_headers;
  // blur-nx (2026-11-13, #13, banjo_renut_deferred_narrow): a narrowed whole capture's device (allocated once per
  // pooled capture, not initialised: a narrowed capture writes every byte the render thread reads); 'narrowed' says the
  // draw reads it instead of 'state' (cleared when the capture goes back to the pool).
  std::unique_ptr<u8[]> narrow;
  bool narrowed = false;
  // blur-nx (2026-11-13, #13's fix): the cache entries whose registers a narrowed capture holds (NarrowCheckLocked).
  const ShaderCacheEntry *narrow_vs = nullptr;
  const ShaderCacheEntry *narrow_ps = nullptr;
};

// banjo-nx (banjo_renut_capture_pool): a draw's capture comes from a pool and goes back to it once the render thread
// has drawn it. Each draw made three heap allocations on the game thread (the capture, its 12.7 KB device snapshot,
// the queued closure) and freed them on the render thread: about 2,000 a frame through the Switch's one malloc lock.
// A pooled capture keeps its snapshot's storage, and the closure holds a plain pointer, which std::function stores
// without allocating. Off: every capture is deleted after use, as before (a new one per draw).
// sa2-nx (2026-10-20, banjo_renut_capture_batches): the pool's lock was taken twice a draw, by the game thread (Take) and
// by the render thread (Give), on two cores: its cache line went back and forth about 1,800 times a City Escape frame.
// Each thread now keeps a few captures of its own and goes to the pool kBatch at a time.
bool CaptureBatchesOn();
bool SmallCapturesOn();

class CapturePool {
public:
  // bangaio-nx (2026-10-29): room for the most the pool keeps, so that no push under the lock reallocates.
  CapturePool() {
    free_.reserve(kMaxFreeSmall);
    free_held_.reserve(kMaxFreeSmall);
  }

  // banjo-nx (2026-10-20, from sa2-nx): 'chain_locked' when the caller holds g_delta.mutex (the chain's draws): its batch is a plain
  // list that lock guards. Thread-local lists cost a call a use here (this toolchain's TLS goes through
  // __aarch64_read_tp: 0.8 % of the render thread in the second console run).
  DrawCapture *Take(bool chain_locked = false) {
    if (CaptureBatchesOn() && chain_locked) {
      std::vector<DrawCapture *> &taken = chain_taken_;
      if (taken.empty()) {
        std::lock_guard lock(mutex_);
        const size_t n = std::min(kBatch, free_.size());
        taken.assign(free_.end() - std::ptrdiff_t(n), free_.end());
        free_.resize(free_.size() - n);
        DropHeldLocked(n);
      }
      if (!taken.empty()) {
        DrawCapture *capture = taken.back();
        taken.pop_back();
        // bangaio-nx (2026-10-29, ARM): the next draw's capture, last written by the render thread on another core, is
        // fetched for writing while the game runs to that draw (its first lines read in CaptureDelta were a miss each
        // draw in the v4 console profile).
        if (!taken.empty()) {
          const char *next = reinterpret_cast<const char *>(taken.back());
          __builtin_prefetch(next, 1);
          __builtin_prefetch(next + 64, 1);
          __builtin_prefetch(next + 128, 1);
          // sasrt-nx (2026-11-12, batch C8): the surface headers and index buffer lines CaptureSurfaces writes
          __builtin_prefetch(next + 256, 1);
          __builtin_prefetch(next + 320, 1);
          __builtin_prefetch(next + 384, 1);
        }
        return capture;
      }
      return new DrawCapture();
    }
    {
      std::lock_guard lock(mutex_);
      if (!free_.empty()) {
        DrawCapture *capture = free_.back();
        free_.pop_back();
        DropHeldLocked(1);
        return capture;
      }
    }
    return new DrawCapture();
  }
  // sa2-nx (2026-10-20): 'render_thread' from the render thread's items (only that thread then touches its batch; a
  // queue run inline at shutdown has the render thread gone).
  // bangaio-nx (2026-10-29): the captures the pool does not keep are deleted after its lock is let go (the frees take
  // the malloc lock, which the game thread's allocations wait on).
  void Give(DrawCapture *capture, bool render_thread = false) {
    if (!capture)
      return;
    if (banjo::renut_gpu::CapturePoolOn()) {
      capture->vertices.clear();
      capture->indices.clear();
      capture->narrowed = false;  // blur-nx (2026-11-13, #13)
      capture->held = HeldBytes(*capture);  // its lines are this thread's now: not read again under the lock
      if (CaptureBatchesOn() && render_thread) {
        std::vector<DrawCapture *> &given = render_given_;
        given.push_back(capture);
        if (given.size() < kBatch)
          return;
        const bool small = SmallCapturesOn();  // its guard and the A/B word read once, not under the lock a capture
        {
          std::lock_guard lock(mutex_);
          for (DrawCapture *&c : given) {
            if (KeepLocked(c, small))
              c = nullptr;
          }
        }
        for (DrawCapture *c : given)
          delete c;
        given.clear();
        return;
      }
      const bool small = SmallCapturesOn();
      {
        std::lock_guard lock(mutex_);
        if (KeepLocked(capture, small))
          return;
      }
    }
    delete capture;
  }

private:
  // bangaio-nx (2026-10-29, banjo_renut_small_captures, A/B 82 here): the console's missile storm queued ~4,250 draws a frame.
  // At 2,048 the pool deleted the rest when the render thread gave them back, and the game thread made ~2,200 again a
  // frame: each a malloc, and a 12.9 KB zero-fill of its delta storage, under the one malloc lock that the render
  // thread's frees took too. CaptureDelta now copies a delta into its capture at its size, so a capture keeps a few
  // hundred bytes, and the pool keeps up to kMaxFreeSmall. Whole copies (rebases, clears, resolves, deltas off) keep
  // 12.9 KB each: the byte cap holds them to about as many as before (32 MB: 2,048 of those were 26 MB).
  static constexpr size_t kMaxFree = 2048;        // more than a frame's draws in flight (banjo-nx: ~2,000 a frame)
  static constexpr size_t kMaxFreeSmall = 8192;   // bangaio-nx: twice the storm's
  static constexpr size_t kMaxHeldBytes = size_t(32) << 20;
  static constexpr size_t kBatch = 32;      // banjo-nx (from sa2-nx): captures a thread takes or gives back at once

  static u32 HeldBytes(const DrawCapture &c) {
    return u32(sizeof(DrawCapture) + c.state.capacity() + c.vertices.capacity() + c.indices.capacity() +
               c.verify.capacity() + (c.narrow ? d3d::kDeviceSnapshotSize : 0));
  }
  // Under mutex_; 'small': SmallCapturesOn().
  bool KeepLocked(DrawCapture *c, bool small) {
    if (small ? free_.size() >= kMaxFreeSmall || held_ + c->held > kMaxHeldBytes : free_.size() >= kMaxFree)
      return false;
    free_.push_back(c);
    free_held_.push_back(c->held);
    held_ += c->held;
    return true;
  }
  // Under mutex_: the last n captures' bytes, which left free_, from free_held_ (contiguous, so no capture is read).
  void DropHeldLocked(size_t n) {
    const size_t end = free_held_.size();
    size_t bytes = 0;
    for (size_t i = end - n; i < end; ++i)
      bytes += free_held_[i];
    free_held_.resize(end - n);
    held_ -= bytes;
  }

  std::mutex mutex_;
  std::vector<DrawCapture *> free_;
  std::vector<u32> free_held_;  // bangaio-nx (2026-10-29): free_'s captures' bytes, in the same order
  size_t held_ = 0;             // their sum
  std::vector<DrawCapture *> chain_taken_;   // banjo-nx (from sa2-nx): under g_delta.mutex
  std::vector<DrawCapture *> render_given_;  // banjo-nx (from sa2-nx): the render thread's
};
CapturePool g_capture_pool;

// A Begin*Vertices draw waiting for its vertices, per device.
struct DeferredDraw {
  DrawCapture *capture = nullptr;  // owned (g_capture_pool)
  const u8 *scratch = nullptr;
  u32 bytes = 0;
};
std::mutex g_deferred_mutex;
std::unordered_map<u32, DeferredDraw> g_deferred;
// sa2-nx (2026-10-20, sa2_renut_callbacks_fast): g_deferred.size(), kept under g_deferred_mutex and read without it
// (FlushDeferredVertices: every hook calls it first). A Begin*Vertices draw is flushed by the next hook of its device,
// on the thread that made it, which sees the count in program order.
std::atomic<size_t> g_deferred_count{0};
// blur-nx (2026-11-17, the 24-hour run; blur_renut_flush_fast_local): the same count per device, hashed (a collision
// only sends a hook through the locks), so one device's hooks are not sent through the chain's lock and the deferred
// map's by another device's Begin*Vertices draw. Changed under g_deferred_mutex with the map; read without it by the
// thread that flushes its own device, as the count above.
constexpr u32 kDeferredSlots = 64;
std::atomic<u32> g_deferred_by_device[kDeferredSlots];
inline std::atomic<u32> &DeferredOf(u32 device_va) { return g_deferred_by_device[(device_va * 2654435761u) >> 26]; }
// blur-nx (2026-11-13, #52's census): FlushDeferredVertices' copies, for the snapshot report.
std::atomic<uint64_t> g_deferred_vertex_bytes{0}, g_deferred_vertex_draws{0};

// sa2-nx (2026-10-20, banjo_renut_snapshot_deltas): the delta chain's layout. Of the device's first kDeviceSnapshotSize
// bytes, the float constants (VertexShaderF, PixelShaderF: 8 KB, two thirds) go by the groups m_Pending marks dirty
// (one bit per four registers, bit 63 - group, as the recorded command buffers keep them: command_buffers.cpp); the
// rest goes by 64-byte chunks (30 before the constants, 47 after them, the last one 32 bytes), those that differ from
// the chain's previous draw (compared on the game thread with its shadow).
constexpr u32 kDeltaVertexF = u32(offsetof(d3d::Device, m_Constants) + offsetof(d3d::Constants, VertexShaderF));
constexpr u32 kDeltaPixelF = u32(offsetof(d3d::Device, m_Constants) + offsetof(d3d::Constants, PixelShaderF));
constexpr u32 kDeltaTailBegin = kDeltaPixelF + 256 * 16;
constexpr u32 kDeltaUnitBytes = 64;  // a chunk, and a constant group
constexpr u32 kDeltaHeadChunks = kDeltaVertexF / kDeltaUnitBytes;
constexpr u32 kDeltaTailBytes = d3d::kDeviceSnapshotSize - kDeltaTailBegin;
constexpr u32 kDeltaChunks = kDeltaHeadChunks + (kDeltaTailBytes + kDeltaUnitBytes - 1) / kDeltaUnitBytes;
static_assert(kDeltaVertexF % kDeltaUnitBytes == 0 && kDeltaPixelF == kDeltaVertexF + 256 * 16);
static_assert(kDeltaTailBegin == u32(offsetof(d3d::Device, m_Constants) + offsetof(d3d::Constants, VertexShaderB)));
static_assert(kDeltaChunks <= 128);
static_assert(kDeltaHeadChunks == kChainHeadChunks && kDeltaTailBegin == kChainTailBegin);  // draw.h's ChainHint

constexpr u32 DeltaChunkOffset(u32 i) {
  return i < kDeltaHeadChunks ? i * kDeltaUnitBytes : kDeltaTailBegin + (i - kDeltaHeadChunks) * kDeltaUnitBytes;
}
constexpr u32 DeltaChunkSize(u32 i) {
  return i < kDeltaHeadChunks ? kDeltaUnitBytes
                              : std::min(kDeltaUnitBytes, kDeltaTailBytes - (i - kDeltaHeadChunks) * kDeltaUnitBytes);
}

// sa2-nx (2026-10-20, banjo_renut_snapshot_deltas_narrow): the device bytes the render thread never reads from a draw's
// device (DrawStateLocked and what it calls: the accessors of render/draw.cpp, textures.cpp, surfaces.cpp, the pipeline
// key): before the fetch constants (the dirty masks, ring pointers and Set/Get*State call tables, which a recorded
// command buffer's replay leaves zero too), and the private words 11008-12223 (the creation thread, the fences, the
// swap flags: the hooks read and write them on the live device). Their chunks are not compared; the render thread's
// device keeps them as the frame's whole copy had them.
constexpr u32 kDeltaUnreadEnd = kDeltaVertexF - 0x300;  // 0x480: the fetch constants' start
constexpr u32 kDeltaPrivateUnreadBegin = 11008, kDeltaPrivateUnreadEnd = 12224;
constexpr bool DeltaChunkRead(u32 i) {
  const u32 at = DeltaChunkOffset(i);
  return !(at < kDeltaUnreadEnd || (at >= kDeltaPrivateUnreadBegin && at + 64 <= kDeltaPrivateUnreadEnd));
}
static_assert(kDeltaUnreadEnd == 0x480 && kDeltaUnreadEnd % kDeltaUnitBytes == 0);
static_assert((kDeltaPrivateUnreadBegin - kDeltaTailBegin) % kDeltaUnitBytes == 0 &&
              (kDeltaPrivateUnreadEnd - kDeltaTailBegin) % kDeltaUnitBytes == 0);
static_assert(d3d::kDeviceOffsetVertexDeclaration >= kDeltaPrivateUnreadEnd);
// The chunks compared: all, or the read ones.
struct DeltaChunkList {
  u32 count = 0;
  u8 index[128] = {};
};
constexpr DeltaChunkList MakeDeltaChunkList(bool narrow) {
  DeltaChunkList l{};
  for (u32 i = 0; i < kDeltaChunks; ++i)
    if (!narrow || DeltaChunkRead(i))
      l.index[l.count++] = u8(i);
  return l;
}
constexpr DeltaChunkList kDeltaAllChunks = MakeDeltaChunkList(false);
constexpr DeltaChunkList kDeltaReadChunks = MakeDeltaChunkList(true);
// sasrt-nx (2026-11-11, batch B3): a list split for the capture marks: its entries before the first markable chunk
// (always compared) and a mask of its markable entries (bit i - kDeltaMarkFirst), so a delta visits only the set bits.
struct DeltaMarkedList {
  u32 pre_count = 0;
  u8 pre[32] = {};
  uint64_t markable = 0;
};
constexpr u32 kDeltaMarkFirstChunk = (0x480 / kDeltaUnitBytes);  // = kDeltaMarkFirst (below)
static_assert(kDeltaChunks - kDeltaMarkFirstChunk <= 64);
constexpr DeltaMarkedList MakeDeltaMarkedList(const DeltaChunkList &l) {
  DeltaMarkedList m{};
  for (u32 k = 0; k < l.count; ++k) {
    const u32 i = l.index[k];
    if (i < kDeltaMarkFirstChunk)
      m.pre[m.pre_count++] = u8(i);
    else
      m.markable |= uint64_t(1) << (i - kDeltaMarkFirstChunk);
  }
  return m;
}
constexpr DeltaMarkedList kDeltaAllMarked = MakeDeltaMarkedList(kDeltaAllChunks);
constexpr DeltaMarkedList kDeltaReadMarked = MakeDeltaMarkedList(kDeltaReadChunks);
static_assert(kDeltaReadChunks.count == 40);  // sasrt-nx: SA2 / SASRT (N&B 39; bangaio-nx's XDK 20209: 40)

// bangaio-nx (2026-10-29, banjo_renut_delta_masks, A/B 81 here, 73 in bangaio-nx): a chunk list as runs of whole chunks at consecutive
// offsets, and each short chunk (the tail's last, 24 bytes in XDK 20209) as a run of its own. CaptureDelta asks
// Lines64DifferMask which chunks of a run differ (line_compare.h: one NEON reduction per four chunks and no branch per
// chunk), then visits the set bits in order: the chunks the per-chunk loop found, in its order. The narrow list is
// three runs (12, 12 and 15 chunks) and the short chunk.
struct DeltaRun {
  u8 first = 0;  // chunk index
  u8 count = 0;  // chunks (at most 32: Lines64DifferMask's)
  bool short_chunk = false;
};
struct DeltaRuns {
  u32 count = 0;
  DeltaRun run[16] = {};
};
constexpr DeltaRuns MakeDeltaRuns(const DeltaChunkList &l) {
  DeltaRuns r{};
  for (u32 k = 0; k < l.count; ++k) {
    const u32 i = l.index[k];
    const bool whole = DeltaChunkSize(i) == kDeltaUnitBytes;
    if (whole && r.count) {
      DeltaRun &last = r.run[r.count - 1];
      if (!last.short_chunk && last.count < 32 && last.first + last.count == i &&
          DeltaChunkOffset(i) == DeltaChunkOffset(last.first) + last.count * kDeltaUnitBytes) {
        ++last.count;
        continue;
      }
    }
    r.run[r.count++] = DeltaRun{u8(i), u8(1), !whole};
  }
  return r;
}
// A short chunk (fewer than 64 bytes): 8 bytes at a time, inline (memcmp with a size known only at run time was a call).
inline bool ShortChunkDiffers(const u8 *a, const u8 *b, u32 size) {
  uint64_t diff = 0;
  u32 k = 0;
  for (; k + 8 <= size; k += 8) {
    uint64_t x, y;
    std::memcpy(&x, a + k, 8);
    std::memcpy(&y, b + k, 8);
    diff |= x ^ y;
  }
  for (; k < size; ++k)
    diff |= u8(a[k] ^ b[k]);
  return diff != 0;
}
constexpr DeltaRuns kDeltaAllRuns = MakeDeltaRuns(kDeltaAllChunks);
constexpr DeltaRuns kDeltaReadRuns = MakeDeltaRuns(kDeltaReadChunks);
// renut-ultimate: bangaio-nx asserted its XDK's layout (4 runs, the last the short chunk); the runs are made from whatever the
// chunk lists are, so only their number is bounded here.
static_assert(kDeltaReadRuns.count <= 16 && kDeltaAllRuns.count <= 16);
// Whether device byte 'at' is one the render thread reads (the verify mode compares those).
constexpr bool DeltaByteRead(u32 at) {
  return !(at < kDeltaUnreadEnd || (at >= kDeltaPrivateUnreadBegin && at < kDeltaPrivateUnreadEnd));
}

struct DeltaHeader {
  uint64_t chunks[2];  // chunk i follows: bit i % 64 of word i / 64
  uint64_t vs, ps;     // the float constant groups that follow (bit 63 - group), the vertex shader's first
};
// The most a delta holds: every chunk and every group.
constexpr size_t kDeltaMaxBytes = sizeof(DeltaHeader) + d3d::kDeviceSnapshotSize;

// Calls f(first, count) for each run of consecutive groups in an m_Pending mask (bit 63 - group).
template <typename F>
void ForEachGroupRun(uint64_t mask, F f) {
  while (mask) {
    const u32 first = u32(std::countl_zero(mask));
    const u32 count = u32(std::countl_one(mask << first));
    f(first, count);
    mask = first + count >= 64 ? 0 : mask & (~uint64_t(0) >> (first + count));
  }
}

// Whether two whole chunks differ: fixed-size loads the compiler keeps inline and vectorises.
bool DeltaChunkDiffers(const u8 *a, const u8 *b) {
  uint64_t diff = 0;
  for (u32 k = 0; k < kDeltaUnitBytes; k += 8) {
    uint64_t x, y;
    std::memcpy(&x, a + k, 8);
    std::memcpy(&y, b + k, 8);
    diff |= x ^ y;
  }
  return diff != 0;
}

// The game threads' side of the chain.
struct DeltaChain {
  std::mutex mutex;                     // the chain's draws are made and queued in one order
  // The device it follows; none: the next draw rebases. banjo-nx (2026-10-26): atomic so ForgetSnapshotDeltas can
  // tell without the lock that a recorded op's device is not the chain's; written under the lock only.
  std::atomic<const d3d::Device *> device{nullptr};
  uint64_t vs = 0, ps = 0;              // groups whole captures consumed since its last draw: they follow
  uint64_t deltas = 0, rebases = 0, bytes = 0, chunks = 0, groups = 0;  // the 10 s report's
  uint64_t whole = 0;  // sa2-nx: whole captures outside the chain (Begin*Vertices draws), under the lock too
  uint64_t narrowed = 0, narrowed_bytes = 0;  // blur-nx (2026-11-13, #13): of those, narrowed, and the bytes they copied
  uint64_t narrowed_prefix_bytes = 0;         // ... what #13's prefixes alone would have copied (#53 / #54's census)
  // blur-nx (2026-11-13, #51, banjo_renut_deferred_chain): the device whose Begin*Vertices delta of the chain waits for
  // its vertices (0: none). While one waits, a draw of any other device is a whole capture outside the chain: queued
  // before that delta, it would have been applied ahead of it on the render thread (N&B's hangs with the chain on and
  // two devices drawing from two threads), so the chain's order stays its queue order however many devices draw.
  // 'cross': the draws made whole that way (the 10 s report's).
  u32 deferred_device = 0;
  uint64_t cross = 0;
  alignas(64) u8 shadow[d3d::kDeviceSnapshotSize];  // the device at its last draw (the chunks)
  // bangaio-nx (2026-10-29, banjo_renut_small_captures): each delta is written here, then copied into its capture at its
  // size. The same lines every draw: they stay in the game thread's cache.
  alignas(64) u8 scratch[kDeltaMaxBytes];
  // sasrt-nx (2026-11-10, sasrt_capture_marks): the marks were taken at the chain's last draw (a delta may use them),
  // deltas since the last whole check, and the 10 s report's counts.
  bool marks_primed = false;
  uint32_t marks_unchecked = 0;
  uint64_t marks_deltas = 0, marks_chunks = 0, marks_checks = 0, marks_missed = 0;
};
DeltaChain g_delta;
// sasrt-nx (2026-11-10, sasrt_capture_marks): a check found a chunk changed without a mark: whole compares from then on.
std::atomic<bool> g_capture_marks_failed{false};
// sasrt-nx (2026-11-10, the batch's audit, finding 1): run tv1 found the resolve path changing fetch chunks 0, 1 and 11
// without a tag (NewOp compares every chunk at a resolve op). The chain's next delta after a resolve compares every
// chunk the same way: QueueResolve sets this, CaptureDelta takes it.
std::atomic<bool> g_capture_next_whole{false};
// The audit's finding 3: the tags a whole capture of the chain's device cleared (ClearPending), for its next delta.
uint64_t g_capture_cleared_tags = 0;  // under g_delta.mutex, as the chain
std::string g_capture_marks_report;  // the audit's finding 7: SnapshotDeltaReport's part (under g_delta.mutex)
// The chunks found written without a tag or a mark: run tv1 on the recording devices (26, 27: tile predication; 58: the
// pixel shader pointer) and run tv3 on the title device (every delta compared whole, 2026-11-10 21:40: 1, a fetch
// constant at +0x4C0; 54, the index buffer / render target / depth pointers at +0x3200; 57, texture pointers of slots
// 18-25 at +0x32C0, which a texture unset changes without its fetch tag). Mark bits (delta chunk - 18).
constexpr uint64_t kCaptureUntagged = (uint64_t(1) << 26) | (uint64_t(1) << 27) | (uint64_t(1) << 58) |
                                      (uint64_t(1) << 1) | (uint64_t(1) << 54) | (uint64_t(1) << 57);
// A delta chunk's mark bit (d3d_native.h's numbering: the fetch constants 0-11, the tail from 12): delta chunks 18 on.
constexpr u32 kDeltaMarkFirst = (0x480 / kDeltaUnitBytes);
static_assert(kDeltaMarkFirst == 18 && kDeltaHeadChunks == kDeltaMarkFirst + 12);

// The render thread's side: the device the chain's draws rebuild.
alignas(64) u8 g_delta_device[d3d::kDeviceSnapshotSize];
std::atomic<uint64_t> g_delta_verified{0}, g_delta_differ{0};

// blur-nx (2026-11-13, M-31 of docs/cpu-moonshots-50-1113.md and its audit: the census first). The devices that draw and
// the threads they draw from, since the start (at most four of each; more counted apart): banjo_renut_deferred_chain is
// off by default because one chain serves every device and N&B drew on two devices from two threads. A thread notes
// itself and a device only when its device changes, so a draw pays one thread-local compare.
std::atomic<uint64_t> g_census_devices[4]{}, g_census_threads[4]{};
std::atomic<uint32_t> g_census_more_devices{0}, g_census_more_threads{0};
void CensusNote(std::atomic<uint64_t> (&set)[4], std::atomic<uint32_t> &more, uint64_t value) {
  for (auto &slot : set) {
    uint64_t seen = slot.load(std::memory_order_relaxed);
    if (seen == value)
      return;
    if (seen == 0 && (slot.compare_exchange_strong(seen, value, std::memory_order_relaxed) || seen == value))
      return;
  }
  more.fetch_add(1, std::memory_order_relaxed);
}
void NoteDrawer(u32 device_va) {
  thread_local u32 last_device = 0;
  if (last_device == device_va)
    return;
  if (last_device == 0) {
    static thread_local char tag;  // (its address: one per thread)
    CensusNote(g_census_threads, g_census_more_threads, uint64_t(reinterpret_cast<uintptr_t>(&tag)));
  }
  last_device = device_va;
  CensusNote(g_census_devices, g_census_more_devices, device_va);
}
std::string DrawerCensus() {
  std::string devices;
  uint32_t n_devices = 0, n_threads = 0;
  for (auto &slot : g_census_devices)
    if (const uint64_t v = slot.load(std::memory_order_relaxed)) {
      devices += fmt::format("{}{:08X}", n_devices ? " " : "", uint32_t(v));
      ++n_devices;
    }
  for (auto &slot : g_census_threads)
    n_threads += slot.load(std::memory_order_relaxed) != 0;
  return fmt::format("; drawing since the start: {} devices ({}{}), {} threads{}", n_devices, devices,
                     g_census_more_devices.load(std::memory_order_relaxed) ? " and more" : "", n_threads,
                     g_census_more_threads.load(std::memory_order_relaxed) ? " and more" : "");
}
// banjo_renut_snapshot_deltas_constants: the chain as a replay of the constant uploads' tracking (draw.h,
// ReplayConstants): its id (a new one at each whole copy; the top bit keeps it apart from the command buffers'
// replays, numbered from 1) and the float constant groups written since the upload last consumed them.
uint64_t g_chain_id = 0, g_chain_count = 0;
uint64_t g_chain_vs_dirty = ~uint64_t(0), g_chain_ps_dirty = ~uint64_t(0);
// sa2_renut_chain_reuse: the number of the chain's last draw (draw.h ChainHint::seq; from 2).
uint64_t g_chain_seq = 1;

bool DeltasOn() {
  static const bool on = REXCVAR_GET(banjo_renut_snapshot_deltas);
  return on;
}
bool ChainConstantsOn() {
  static const bool on = DeltasOn() && REXCVAR_GET(banjo_renut_snapshot_deltas_constants);
  return on;
}
// bangaio-nx (2026-10-29, ARM): these read the latched switches (banjo_renut_tuning.h, plain loads), not function
// statics: each static's guard was a load-acquire at every draw on the game thread (the v4 console profile).
bool CaptureBatchesOn() {
  return banjo::renut_gpu::Latch().capture_batches;
}
bool SmallCapturesOn() {
  return banjo::renut_gpu::Latch().small_captures && banjo::renut_gpu::g_ab_off.load(std::memory_order_relaxed) != 82;  // 70 in bangaio-nx
}
bool NeonCompareOn() {
  return banjo::renut_gpu::Latch().neon_compare;
}
bool DeltasNarrowOn() {
  return banjo::renut_gpu::Latch().deltas_narrow;
}
bool DeltaMasksOn() {  // bangaio-nx (2026-10-29, A/B 81 here)
  return banjo::renut_gpu::Latch().delta_masks && banjo::renut_gpu::g_ab_off.load(std::memory_order_relaxed) != 81;  // 73 in bangaio-nx
}
bool DeltaPrefetchOn() {  // bangaio-nx (2026-10-29, v6, A/B 74)
  return banjo::renut_gpu::Latch().delta_prefetch && banjo::renut_gpu::g_ab_off.load(std::memory_order_relaxed) != 84;  // 74 in bangaio-nx
}
// sa2-nx (2026-10-20, from futari-nx via peggle2-nx): sa2_renut_deferred_chain (QueueDeferredDraw).
bool DeferredChainOn() {
  static const bool on = REXCVAR_GET(sa2_renut_deferred_chain);
  return on;
}
bool DeltasVerifyOn() {
  return banjo::renut_gpu::Latch().deltas_verify;  // bangaio-nx (2026-10-29): latched (with the deltas on)
}

// The original draw calls consume the device's dirty masks as they write
// their packets; a snapshot taken after this has them clear, as the command
// buffer ops' do.
void ClearPending(d3d::Device *device) {
  // sa2-nx (banjo_renut_snapshot_deltas): the dirty constant groups a whole capture consumes go with the chain's next
  // delta (its callers hold g_delta.mutex when the deltas are on).
  if (device == g_delta.device.load(std::memory_order_relaxed)) {
    g_delta.vs |= uint64_t(device->m_Pending[0]);
    g_delta.ps |= uint64_t(device->m_Pending[1]);
    // sasrt-nx (2026-11-10, the audit's finding 3): their tags' chunks go with the chain's next delta too.
    g_capture_cleared_tags |= native::TagChunks(u64(device->m_Pending[2]), u64(device->m_Pending[3]),
                                                u64(device->m_Pending[4]));
  }
  for (auto &mask : device->m_Pending)
    mask = 0;
}

// sa2-nx (banjo_renut_snapshot_deltas), on the render thread: the device a queued draw reads.
const u8 *DeviceForDraw(const DrawCapture &capture) {
  if (capture.snapshot == SnapshotKind::Whole) {
    // banjo-nx (2026-10-28, per-draw night, A/B 62): a number of its own, every chunk and field changed (as a replay's
    // first draw): the fast path may take it after the draw before it. The chain's own number stays (its next delta
    // draw is not consecutive with it: every chunk then too). Off half: not a chain draw, as before.
    if (banjo::renut_gpu::g_ab_off.load(std::memory_order_relaxed) == 62) {
      g_chain_hint = {};  // not a chain draw (banjo_renut_chain_reuse)
    } else {
      g_chain_hint.seq = NextChainSeq();
      g_chain_hint.changed[0] = g_chain_hint.changed[1] = ~uint64_t(0);
      g_chain_hint.fields = kFieldsAll;
    }
    return capture.narrowed ? capture.narrow.get() : capture.state.data();  // blur-nx (2026-11-13, #13)
  }
  if (capture.snapshot == SnapshotKind::Rebase) {
    std::memcpy(g_delta_device, capture.state.data(), d3d::kDeviceSnapshotSize);
    g_chain_id = (uint64_t(1) << 63) | ++g_chain_count;  // its first draw compares every group
    g_chain_vs_dirty = g_chain_ps_dirty = ~uint64_t(0);
    g_chain_hint.seq = ++g_chain_seq;
    g_chain_hint.changed[0] = g_chain_hint.changed[1] = ~uint64_t(0);  // a whole copy: every chunk
    g_chain_hint.fields = kFieldsAll;
  } else {
    const u8 *from = capture.state.data();
    DeltaHeader h;
    std::memcpy(&h, from, sizeof(h));
    from += sizeof(h);
    const uint64_t seq = NextChainSeq();
    const bool consecutive = seq == g_chain_seq + 1;  // banjo-nx: no replayed draw in between
    g_chain_hint.seq = g_chain_seq = seq;
    g_chain_hint.changed[0] = consecutive ? h.chunks[0] : ~uint64_t(0);
    g_chain_hint.changed[1] = consecutive ? h.chunks[1] : ~uint64_t(0);
    g_chain_hint.fields = consecutive ? ChainFields(h.chunks) : kFieldsAll;  // banjo-nx (2026-10-26)
    g_chain_vs_dirty |= h.vs;
    g_chain_ps_dirty |= h.ps;
    for (u32 word = 0; word < 2; ++word) {
      for (uint64_t bits = h.chunks[word]; bits; bits &= bits - 1) {
        const u32 i = word * 64 + u32(std::countr_zero(bits));
        const u32 size = DeltaChunkSize(i);
        // Whole chunks as a fixed-size copy, which stays inline.
        if (size == kDeltaUnitBytes)
          std::memcpy(g_delta_device + DeltaChunkOffset(i), from, kDeltaUnitBytes);
        else
          std::memcpy(g_delta_device + DeltaChunkOffset(i), from, size);
        from += size;
      }
    }
    for (const auto [dirty, base] : {std::pair{h.vs, kDeltaVertexF}, std::pair{h.ps, kDeltaPixelF}}) {
      ForEachGroupRun(dirty, [&](u32 first, u32 count) {
        const u32 bytes = count * kDeltaUnitBytes;
        std::memcpy(g_delta_device + base + first * kDeltaUnitBytes, from, bytes);
        from += bytes;
      });
    }
  }
  if (!capture.verify.empty()) {
    g_delta_verified.fetch_add(1, std::memory_order_relaxed);
    // sa2-nx (banjo_renut_snapshot_deltas_narrow): the bytes the render thread reads; with the narrow compare off, all.
    bool same;
    if (DeltasNarrowOn()) {
      same = std::memcmp(g_delta_device + kDeltaUnreadEnd, capture.verify.data() + kDeltaUnreadEnd,
                         kDeltaPrivateUnreadBegin - kDeltaUnreadEnd) == 0 &&
             std::memcmp(g_delta_device + kDeltaPrivateUnreadEnd, capture.verify.data() + kDeltaPrivateUnreadEnd,
                         d3d::kDeviceSnapshotSize - kDeltaPrivateUnreadEnd) == 0;
    } else {
      same = std::memcmp(g_delta_device, capture.verify.data(), d3d::kDeviceSnapshotSize) == 0;
    }
    if (!same) {
      g_delta_differ.fetch_add(1, std::memory_order_relaxed);
      static uint32_t logged = 0;
      if (logged < 8) {
        ++logged;
        u32 at = 0;
        while (at < d3d::kDeviceSnapshotSize &&
               (g_delta_device[at] == capture.verify[at] || (DeltasNarrowOn() && !DeltaByteRead(at))))
          ++at;
        RGPU_WARN("Device snapshot delta: the rebuilt device differs from the device at +{} ({} draw): {:02X}, the "
                  "device {:02X} (banjo_renut_snapshot_deltas_verify)",
                  at, capture.snapshot == SnapshotKind::Rebase ? "a whole" : "a delta", g_delta_device[at],
                  capture.verify[at]);
      }
    }
  }
  return g_delta_device;
}

// sasrt-nx: the headers of the surfaces the device binds, as they are now (from the device itself: a snapshot-delta
// capture holds only the bytes that changed).
void CaptureSurfaces(DrawCapture *c, const u8 *bytes) {
  c->surfaces = 0;
  c->ib_va = 0;
  c->sasrt_streams.count = 0;
  c->sasrt_vs = 0;
  if (!bytes)
    return;
  if (SasrtRecordedBindsOn()) {  // sasrt-nx (2026-10-21, sasrt_renut_recorded_binds)
    const u32 vs = u32(*reinterpret_cast<const be_u32 *>(bytes + d3d::kDeviceOffsetVertexShader));
    if (vs && SasrtBindingOf(vs, &c->sasrt_decl, c->sasrt_strides))
      c->sasrt_vs = vs;
  }
  if (SasrtLateStreamsOn())  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams)
    SasrtHashStreams(bytes, c->sasrt_streams);
  if (SasrtLateStreamsOn() && c->call.indexed && !c->call.up_indices && c->ib_va) {  // sasrt-nx: index data
    const u32 is32 = (u32(c->ib.resource.Common) & d3d::kIndexBufferCommon32Bit) ? 1u : 0u;
    const u32 address = u32(c->ib.Address) + c->call.start_index * (is32 ? 4u : 2u);
    const u32 size = std::min<u32>(c->call.count * (is32 ? 4u : 2u), 4096u);
    std::lock_guard lock(g_sasrt_kick_mutex);
    g_sasrt_kick_list.emplace_back(address, size);
  }
  if (c->sasrt_streams.count) {  // sasrt-nx: noted for the hash at the kick (SasrtQueueKickHashes)
    std::lock_guard lock(g_sasrt_kick_mutex);
    for (u32 i = 0; i < c->sasrt_streams.count; ++i)
      g_sasrt_kick_list.emplace_back(c->sasrt_streams.va[i], c->sasrt_streams.size[i]);
  }
  // sasrt-nx (2026-10-21): the bound index buffer object too (ReplayIndexBuffer).
  if (const u32 ib = u32(*reinterpret_cast<const be_u32 *>(bytes + d3d::kDeviceOffsetIndexBuffer))) {
    if (const auto *object = GuestPtr<const d3d::IndexBuffer>(ib)) {
      std::memcpy(&c->ib, object, sizeof(c->ib));
      c->ib_va = ib;
    }
  }
  for (u32 i = 0; i < 5; ++i) {
    const u32 offset = i < 4 ? d3d::kDeviceOffsetRenderTargets + i * 4 : d3d::kDeviceOffsetDepthStencil;
    const u32 surface = u32(*reinterpret_cast<const be_u32 *>(bytes + offset));
    const auto *desc = surface ? GuestPtr<const d3d::SurfaceDesc>(surface + sizeof(d3d::Resource)) : nullptr;
    if (!desc)
      continue;
    c->surface_va[c->surfaces] = surface;
    c->surface_desc[c->surfaces] = *desc;
    ++c->surfaces;
  }
}

// blur-nx (2026-11-13, #13's fix): a narrowed capture's shaders as the render thread finds them for its draw. One whose
// cache entry is not the one the capture was narrowed for (the guest re-registering a shader in the memory of one a
// queued draw uses) reads registers the capture may have left out: counted, and reported every 10 s.
std::atomic<uint64_t> g_narrow_checked{0}, g_narrow_differ{0};

void NarrowCheckLocked(const DrawCapture &capture, const u8 *device) {
  auto word = [device](u32 offset) {
    u32 v;
    std::memcpy(&v, device + offset, 4);
    return __builtin_bswap32(v);
  };
  const ShaderRecord *vs = FindShaderLocked(word(d3d::kDeviceOffsetVertexShader), RecordKind::VertexShader);
  const ShaderRecord *ps = FindShaderLocked(word(d3d::kDeviceOffsetPixelShader), RecordKind::PixelShader);
  // A shader the draw cannot use (none found, or no cache entry: GetHostShader gives none) reads no register.
  const bool vs_differs = vs && vs->entry && vs->entry != capture.narrow_vs;
  const bool ps_differs = ps && ps->entry && ps->entry != capture.narrow_ps;
  g_narrow_checked.fetch_add(1, std::memory_order_relaxed);
  if (vs_differs || ps_differs)
    g_narrow_differ.fetch_add(1, std::memory_order_relaxed);
}

void QueueCapture(DrawCapture *capture) {
  // sa2-nx (2026-10-20, sa2_renut_prefetch_next): the capture and its device bytes, written on the game thread's core,
  // are fetched into the render thread's cache while it does the item before this one.
  render_thread::QueuePrefetched(capture, capture->narrowed ? capture->narrow.get() : capture->state.data(), [capture] {
    DrawCall call = capture->call;
    if (!capture->vertices.empty())
      call.up_vertices = capture->vertices.data();
    if (!capture->indices.empty())
      call.up_indices = capture->indices.data();
    if (call.up_index_offset && call.up_vertices)  // sasrt-nx: BeginIndexedVertices
      call.up_indices = call.up_vertices + call.up_index_offset;
    const u8 *device = DeviceForDraw(*capture);
    SetReplaySurfaceOverridesLocked(capture->surface_va, capture->surface_desc, capture->surfaces);  // sasrt-nx
    SetReplayIndexBufferLocked(capture->ib_va, &capture->ib);  // sasrt-nx (2026-10-21)
    // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams): compared at the conversion (FlushVertexFillsLocked).
    g_sasrt_draw_streams = capture->sasrt_streams.count ? &capture->sasrt_streams : nullptr;
    g_sasrt_draw_recorded = false;
    if (capture->sasrt_vs)  // sasrt-nx (2026-10-21, sasrt_renut_recorded_binds)
      SasrtApplyRecordedBinding(capture->sasrt_vs, capture->sasrt_decl, capture->sasrt_strides);
    if (capture->narrowed)  // blur-nx (2026-11-13, #13's fix)
      NarrowCheckLocked(*capture, device);
    banjo::renut_gpu::CountDrawSource(0);
    // blur-nx (2026-11-10, port 76; its key 215)
    SetReplayStackHeaders(capture->stack_headers.count ? &capture->stack_headers : nullptr);
    if (capture->binding) {  // halo3-nx (2026-11-03): after a replay's, this draw's own
      ApplyBindingLocked(capture->binding);
      capture->binding = 0;
    }
    if (capture->snapshot != SnapshotKind::Whole && ChainConstantsOn()) {
      // sa2-nx (banjo_renut_snapshot_deltas_constants): every constant is the rebuilt device's (no running device).
      const ReplayConstants chain{nullptr, ~uint64_t(0), ~uint64_t(0), &g_chain_vs_dirty, &g_chain_ps_dirty,
                                  g_chain_id};
      DrawStateLocked(device, call, &chain);
    } else {
      DrawStateLocked(device, call);
    }
    SetReplaySurfaceOverridesLocked(nullptr, nullptr, 0);  // sasrt-nx
    SetReplayIndexBufferLocked(0, nullptr);  // sasrt-nx (2026-10-21)
    g_sasrt_draw_streams = nullptr;  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams)
    g_chain_hint = {};  // sa2-nx: only for the draw itself
    SetReplayStackHeaders(nullptr);  // blur-nx (2026-11-10, port 76; its key 215)
    g_capture_pool.Give(capture, true);
  });
}

DrawCapture *Capture(u32 device_va, const DrawCall &call) {
  auto *device = GuestPtr<d3d::Device>(device_va);
  if (!device)
    return nullptr;
  ClearPending(device);
  DrawCapture *capture = g_capture_pool.Take();
  // assign() keeps a pooled capture's storage (Snapshot() made a new vector each time).
  const auto *bytes = reinterpret_cast<const u8 *>(device);
  capture->state.assign(bytes, bytes + d3d::kDeviceSnapshotSize);
  capture->snapshot = SnapshotKind::Whole;  // sa2-nx
  CaptureStackHeaders(bytes, capture->stack_headers);  // blur-nx (2026-11-10, port 76; its key 215)
  capture->verify.clear();
  capture->call = call;
  CaptureSurfaces(capture, reinterpret_cast<const u8 *>(device));  // sasrt-nx
  capture->call.up_vertices = nullptr;
  capture->call.up_indices = nullptr;
  return capture;
}

// blur-nx (2026-11-13, #13, banjo_renut_deferred_narrow): the float constant registers the bound shader at 'offset' reads,
// as a count from register 0 (its highest one + 1); false when it is neither a renderer record of 'kind' nor an in-place
// shader of 'kind' (FindShaderLocked's order: the record registry, then the in-place shaders), or has no cache entry.
// 'none_ok': a null shader reads none (the pixel shader: the render thread then uses kNoRegisters). 'out': the entry.
bool ShaderRegisters(const u8 *device, u32 offset, RecordKind kind, bool none_ok, u32 &count, uint64_t &groups,
                     const ShaderCacheEntry *&out) {
  const u32 va = (u32(device[offset]) << 24) | (u32(device[offset + 1]) << 16) | (u32(device[offset + 2]) << 8) |
                 u32(device[offset + 3]);
  groups = 0;
  out = nullptr;
  if (!va) {
    count = 0;
    return none_ok;
  }
  RecordKind found;
  const ShaderCacheEntry *entry = nullptr;
  if (records::Lookup(va, &found) && found == kind) {
    const auto *record = GuestPtr<const ShaderRecord>(va);
    if (!record)
      return false;
    entry = record->entry;
  } else if (!InPlaceShaderEntry(va, kind, &entry)) {  // blur-nx (2026-11-13, #13's fix): Blur's shaders
    return false;
  }
  if (!entry)
    return false;
  out = entry;
  count = 0;
  for (int w = 7; w >= 0; --w) {
    if (const u32 bits = entry->floatConstants[w]) {
      count = u32(w) * 32 + 32 - u32(__builtin_clz(bits));
      break;
    }
  }
  // blur-nx (2026-11-13, #53): the 64-byte groups (four registers) holding a register it reads.
  for (u32 w = 0; w < 8; ++w) {
    const u32 bits = entry->floatConstants[w];
    for (u32 g = 0; g < 8; ++g)
      if ((bits >> (4 * g)) & 0xFu) groups |= uint64_t(1) << (w * 8 + g);
  }
  return true;
}

// blur-nx (2026-11-13, #53): the groups of 'groups' (bit g = registers 4g..4g+3, 64 bytes) copied in runs; the bytes.
size_t CopyGroups(u8 *out, const u8 *bytes, u32 base, uint64_t groups) {
  size_t copied = 0;
  while (groups) {
    const u32 first = u32(__builtin_ctzll(groups));
    const uint64_t rest = groups >> first;
    const u32 run = rest == ~uint64_t(0) >> first ? 64 - first : u32(__builtin_ctzll(~rest));
    std::memcpy(out + base + first * 64, bytes + base + first * 64, size_t(run) * 64);
    copied += size_t(run) * 64;
    groups = first + run >= 64 ? 0 : groups & ~((uint64_t(1) << (first + run)) - 1);
  }
  return copied;
}

// The capture of a Begin*Vertices draw: Capture()'s, with only the float constant registers its shaders read (the
// rest of the device whole); Capture() itself when a shader's registers are not known.
DrawCapture *CaptureDeferred(u32 device_va, const DrawCall &call) {
  static const bool narrow_on = REXCVAR_GET(banjo_renut_deferred_narrow);
  if (!narrow_on)
    return Capture(device_va, call);
  auto *device = GuestPtr<d3d::Device>(device_va);
  if (!device)
    return nullptr;
  const auto *bytes = reinterpret_cast<const u8 *>(device);
  u32 vs_regs = 0, ps_regs = 0;
  uint64_t vs_groups = 0, ps_groups = 0;
  const ShaderCacheEntry *vs_entry = nullptr, *ps_entry = nullptr;
  if (!ShaderRegisters(bytes, d3d::kDeviceOffsetVertexShader, RecordKind::VertexShader, false, vs_regs, vs_groups,
                       vs_entry) ||
      !ShaderRegisters(bytes, d3d::kDeviceOffsetPixelShader, RecordKind::PixelShader, true, ps_regs, ps_groups,
                       ps_entry))
    return Capture(device_va, call);
  ClearPending(device);
  DrawCapture *capture = g_capture_pool.Take();
  capture->narrow_vs = vs_entry;  // blur-nx (2026-11-13, #13's fix): checked on the render thread (NarrowCheckLocked)
  capture->narrow_ps = ps_entry;
  if (!capture->narrow)
    capture->narrow.reset(new u8[d3d::kDeviceSnapshotSize]);
  u8 *out = capture->narrow.get();
  static const bool poison = REXCVAR_GET(banjo_renut_deferred_narrow_poison);
  if (poison)  // NaNs (0xFF bytes) in every byte left out
    std::memset(out, 0xFF, d3d::kDeviceSnapshotSize);
  // blur-nx (2026-11-13, #54): the device's never-read ranges left out too (the delta chain's narrow map, which
  // banjo_renut_snapshot_deltas_verify checks: the dirty masks, ring pointers and call tables before the fetch
  // constants, the private words 10880-11775); banjo_renut_deferred_narrow_groups: #53's groups, else the prefixes.
  static const bool groups_on = REXCVAR_GET(banjo_renut_deferred_narrow_groups);
  size_t copied = 0;
  std::memcpy(out + kDeltaUnreadEnd, bytes + kDeltaUnreadEnd, kDeltaVertexF - kDeltaUnreadEnd);
  copied += kDeltaVertexF - kDeltaUnreadEnd;
  if (groups_on) {
    copied += CopyGroups(out, bytes, kDeltaVertexF, vs_groups);
    copied += CopyGroups(out, bytes, kDeltaPixelF, ps_groups);
  } else {
    std::memcpy(out + kDeltaVertexF, bytes + kDeltaVertexF, size_t(vs_regs) * 16);
    std::memcpy(out + kDeltaPixelF, bytes + kDeltaPixelF, size_t(ps_regs) * 16);
    copied += size_t(vs_regs + ps_regs) * 16;
  }
  std::memcpy(out + kDeltaTailBegin, bytes + kDeltaTailBegin, kDeltaPrivateUnreadBegin - kDeltaTailBegin);
  std::memcpy(out + kDeltaPrivateUnreadEnd, bytes + kDeltaPrivateUnreadEnd,
              d3d::kDeviceSnapshotSize - kDeltaPrivateUnreadEnd);
  copied += (kDeltaPrivateUnreadBegin - kDeltaTailBegin) + (d3d::kDeviceSnapshotSize - kDeltaPrivateUnreadEnd);
  capture->narrowed = true;
  capture->snapshot = SnapshotKind::Whole;
  CaptureStackHeaders(bytes, capture->stack_headers);  // blur-nx (2026-11-10, port 76; its key 215)
  capture->verify.clear();
  capture->call = call;
  CaptureSurfaces(capture, bytes);  // sasrt-nx (as Capture)
  capture->call.up_vertices = nullptr;
  capture->call.up_indices = nullptr;
  if (DeltasOn()) {  // (the caller holds g_delta.mutex then)
    ++g_delta.narrowed;
    g_delta.narrowed_bytes += copied;
    g_delta.narrowed_prefix_bytes += d3d::kDeviceSnapshotSize - size_t(512 - vs_regs - ps_regs) * 16;  // #13's alone
  }
  return capture;
}

// sa2-nx (2026-10-20, banjo_renut_snapshot_deltas): a draw of the chain. Requires g_delta.mutex, held until the capture
// is queued.
DrawCapture *CaptureDelta(u32 device_va, const DrawCall &call) {
  auto *device = GuestPtr<d3d::Device>(device_va);
  if (!device)
    return nullptr;
  DeltaChain &c = g_delta;
  DrawCapture *capture = g_capture_pool.Take(true);
  capture->call = call;
  CaptureSurfaces(capture, reinterpret_cast<const u8 *>(device));  // sasrt-nx
  capture->call.up_vertices = nullptr;
  capture->call.up_indices = nullptr;
  const auto *bytes = reinterpret_cast<const u8 *>(device);
  CaptureStackHeaders(bytes, capture->stack_headers);  // blur-nx (2026-11-10, port 76; its key 215)
  if (c.device.load(std::memory_order_relaxed) != device) {
    // The chain's first draw (or a frame's): the whole device, which the render thread takes as its own.
    for (auto &mask : device->m_Pending)
      mask = 0;
    capture->state.assign(bytes, bytes + d3d::kDeviceSnapshotSize);
    std::memcpy(c.shadow, bytes, d3d::kDeviceSnapshotSize);
    c.device.store(device, std::memory_order_relaxed);
    c.vs = c.ps = 0;
    capture->snapshot = SnapshotKind::Rebase;
    if (static const bool marks_on = REXCVAR_GET(sasrt_capture_marks); marks_on) {  // sasrt-nx (2026-11-10)
      uint64_t unused;
      c.marks_primed = native::TakeTouches(device_va, &unused);
    }
    ++c.rebases;
    c.bytes += d3d::kDeviceSnapshotSize;
  } else {
    const uint64_t vs = c.vs | uint64_t(device->m_Pending[0]);
    const uint64_t ps = c.ps | uint64_t(device->m_Pending[1]);
    c.vs = c.ps = 0;
    // sasrt-nx (2026-11-10, sasrt_capture_marks): the chunks marked or tagged since the chain's last draw.
    static const bool marks_on = REXCVAR_GET(sasrt_capture_marks);
    static const uint32_t marks_period = uint32_t(REXCVAR_GET(sasrt_capture_marks_check));
    uint64_t marked = 0;
    bool use_marks = false, check_marks = false;
    if (marks_on) {
      uint64_t touched = 0;
      const bool slot = native::TakeTouches(device_va, &touched);
      // (2026-11-12, batch C9: read first, exchanged only when set: no exclusive store at every delta; a store racing
      // with this is taken by this delta or the next, as with the exchange alone)
      const bool whole_next = g_capture_next_whole.load(std::memory_order_relaxed) &&
                              g_capture_next_whole.exchange(false, std::memory_order_relaxed);  // audit finding 1
      const uint64_t cleared = g_capture_cleared_tags;  // audit finding 3
      g_capture_cleared_tags = 0;
      if (slot && c.marks_primed && !whole_next && !g_capture_marks_failed.load(std::memory_order_relaxed)) {
        marked = touched | kCaptureUntagged | cleared |
                 native::TagChunks(u64(device->m_Pending[2]), u64(device->m_Pending[3]), u64(device->m_Pending[4]));
        use_marks = true;
        if (marks_period && ++c.marks_unchecked >= marks_period) {
          c.marks_unchecked = 0;
          check_marks = true;
        }
      }
      c.marks_primed = slot;
    }
    for (auto &mask : device->m_Pending)
      mask = 0;
    std::vector<u8> &out = capture->state;
    // bangaio-nx (2026-10-29, banjo_renut_small_captures): into the chain's scratch, copied into the capture at its size
    // below; off, into the capture's own storage at its greatest size.
    const bool small = SmallCapturesOn();
    if (!small && out.size() < kDeltaMaxBytes)
      out.resize(kDeltaMaxBytes);  // once per pooled capture: written below, never cleared
    u8 *const begin = small ? c.scratch : out.data();
    u8 *to = begin + sizeof(DeltaHeader);
    DeltaHeader h{};
    u32 chunks = 0;
    // A changed chunk: into the shadow and the delta, and its bit. bangaio-nx (2026-10-29, ARM): a whole chunk with
    // constant-size copies (inline q-register pairs; a variable size was two memcpy calls).
    const auto take = [&](u32 i) {
      const u32 at = DeltaChunkOffset(i), size = DeltaChunkSize(i);
      if (size == kDeltaUnitBytes) {
        std::memcpy(c.shadow + at, bytes + at, kDeltaUnitBytes);
        std::memcpy(to, bytes + at, kDeltaUnitBytes);
      } else {
        std::memcpy(c.shadow + at, bytes + at, size);
        std::memcpy(to, bytes + at, size);
      }
      to += size;
      h.chunks[i / 64] |= uint64_t(1) << (i % 64);
      ++chunks;
    };
    const bool narrow = DeltasNarrowOn();
    if (use_marks && !check_marks) {
      // sasrt-nx (2026-11-10, sasrt_capture_marks): the marked chunks only, in the list's (ascending) order; a chunk
      // before the fetch constants has no mark and is compared (the narrow list has none).
      const bool neon = NeonCompareOn();
      // sasrt-nx (2026-11-11, batch B3): the list's unmarkable head, then its marked chunks by their set bits: the same
      // chunks in the same ascending order as the list walk, without testing the ~77 entries' marks one by one.
      static_assert(kDeltaMarkFirst == kDeltaMarkFirstChunk);
      const DeltaMarkedList &ml = narrow ? kDeltaReadMarked : kDeltaAllMarked;
      u32 compared = 0;
      const auto visit = [&](u32 i) {
        ++compared;
        const u32 at = DeltaChunkOffset(i), size = DeltaChunkSize(i);
        const bool differs = size == kDeltaUnitBytes ? banjo::renut_gpu::Line64Differs(bytes + at, c.shadow + at, neon)
                                                     : std::memcmp(bytes + at, c.shadow + at, size) != 0;
        if (differs)
          take(i);
      };
      for (u32 k = 0; k < ml.pre_count; ++k)
        visit(ml.pre[k]);
      for (uint64_t bits = marked & ml.markable; bits; bits &= bits - 1)
        visit(kDeltaMarkFirst + u32(std::countr_zero(bits)));
      c.marks_chunks += compared;
      ++c.marks_deltas;
    } else if (DeltaMasksOn()) {
      // bangaio-nx (2026-10-29, banjo_renut_delta_masks): which chunks of each run differ, then those in order.
      const DeltaRuns &runs = narrow ? kDeltaReadRuns : kDeltaAllRuns;
      for (u32 r = 0; r < runs.count; ++r) {
        const DeltaRun &run = runs.run[r];
        const u32 at = DeltaChunkOffset(run.first);
        uint32_t mask = run.short_chunk ? uint32_t(ShortChunkDiffers(bytes + at, c.shadow + at, DeltaChunkSize(run.first)))
                                        : banjo::renut_gpu::Lines64DifferMask(bytes + at, c.shadow + at, run.count);
        for (; mask; mask &= mask - 1)
          take(run.first + u32(std::countr_zero(mask)));
      }
    } else {
      const DeltaChunkList &list = narrow ? kDeltaReadChunks : kDeltaAllChunks;
      const bool neon = NeonCompareOn();  // banjo-nx (from sa2-nx) (banjo_renut_neon_compare)
      for (u32 k = 0; k < list.count; ++k) {
        const u32 i = list.index[k];
        const u32 at = DeltaChunkOffset(i), size = DeltaChunkSize(i);
        const bool differs = size == kDeltaUnitBytes ? banjo::renut_gpu::Line64Differs(bytes + at, c.shadow + at, neon)
                                                     : std::memcmp(bytes + at, c.shadow + at, size) != 0;
        if (differs)
          take(i);
      }
    }
    if (check_marks) {
      // sasrt-nx (2026-11-10, sasrt_capture_marks): the whole compare above against the marks.
      ++c.marks_checks;
      for (u32 w = 0; w < 2; ++w) {
        for (uint64_t bits = h.chunks[w]; bits; bits &= bits - 1) {
          const u32 i = w * 64 + u32(std::countr_zero(bits));
          if (i < kDeltaMarkFirst || ((marked >> (i - kDeltaMarkFirst)) & 1))
            continue;
          ++c.marks_missed;
          static std::atomic<uint64_t> logged{0};
          const uint64_t bit = uint64_t(1) << (i - kDeltaMarkFirst);
          if (!(logged.fetch_or(bit, std::memory_order_relaxed) & bit))
            RGPU_WARN("[renut] sasrt_capture_marks: title device chunk {} (+0x{:X}) changed without a mark", i,
                      DeltaChunkOffset(i));
          if (marks_period != 1 && !g_capture_marks_failed.exchange(true, std::memory_order_relaxed))
            RGPU_ERROR("[renut] sasrt_capture_marks: a chunk changed without a mark; every delta compares every read "
                       "chunk from now on");
        }
      }
    }
    for (const auto [dirty, base] : {std::pair{vs, kDeltaVertexF}, std::pair{ps, kDeltaPixelF}}) {
      ForEachGroupRun(dirty, [&](u32 first, u32 count) {
        const u32 group_bytes = count * kDeltaUnitBytes;
        std::memcpy(to, bytes + base + first * kDeltaUnitBytes, group_bytes);
        to += group_bytes;
      });
    }
    h.vs = vs;
    h.ps = ps;
    std::memcpy(begin, &h, sizeof(h));
    if (small)
      out.assign(begin, to);  // the capture's storage kept (a pooled vector keeps its capacity)
    capture->snapshot = SnapshotKind::Delta;
    ++c.deltas;
    c.bytes += uint64_t(to - begin);
    c.chunks += chunks;
    c.groups += uint64_t(std::popcount(vs) + std::popcount(ps));
  }
  if (DeltasVerifyOn())
    capture->verify.assign(bytes, bytes + d3d::kDeviceSnapshotSize);
  else
    capture->verify.clear();
  return capture;
}

} // namespace

void SnapshotDeltasNewFrame() {
  if (!DeltasOn())
    return;
  std::lock_guard lock(g_delta.mutex);
  g_delta.device.store(nullptr, std::memory_order_relaxed);  // the frame's first draw rebases: whatever went wrong lasts a frame at most
}

void ForgetSnapshotDeltas(const void *device) {
  if (!DeltasOn())
    return;
  // banjo-nx (2026-10-26): only the chain's own device's masks matter to it; a recording device's ops (every recorded
  // op came here) took the chain's lock each, and made its next draw a whole copy, for nothing. The chain's device is
  // the title device, which the game does not record on while it draws on it elsewhere: an op of it is ordered with
  // its draws by the game, and so is this load with the store that made it the chain's.
  if (g_delta.device.load(std::memory_order_relaxed) != device)
    return;
  std::lock_guard lock(g_delta.mutex);
  g_delta.device.store(nullptr, std::memory_order_relaxed);
}

std::string SnapshotDeltaReport() {
  if (!DeltasOn())
    return {};
  uint64_t deltas, rebases, bytes, chunks, groups, whole, narrowed, narrowed_bytes, narrowed_prefix, cross;
  {
    std::lock_guard lock(g_delta.mutex);
    whole = g_delta.whole;
    g_delta.whole = 0;
    // sasrt-nx (2026-11-10, the batch's audit, finding 7): sasrt_capture_marks' counts since the last report.
    g_capture_marks_report = fmt::format(
        "; capture marks (sasrt_capture_marks): {} deltas from marks, {:.1f} chunks compared a delta, {} whole checks, "
        "{} chunks changed without a mark{}",
        g_delta.marks_deltas, g_delta.marks_deltas ? double(g_delta.marks_chunks) / double(g_delta.marks_deltas) : 0.0,
        g_delta.marks_checks, g_delta.marks_missed,
        g_capture_marks_failed.load(std::memory_order_relaxed) ? " (marks off: a miss was found)" : "");
    g_delta.marks_deltas = g_delta.marks_chunks = g_delta.marks_checks = g_delta.marks_missed = 0;
    cross = g_delta.cross;  // blur-nx (2026-11-13, #51)
    g_delta.cross = 0;
    narrowed = g_delta.narrowed;  // blur-nx (2026-11-13, #13)
    narrowed_bytes = g_delta.narrowed_bytes;
    narrowed_prefix = g_delta.narrowed_prefix_bytes;
    g_delta.narrowed = g_delta.narrowed_bytes = g_delta.narrowed_prefix_bytes = 0;
    deltas = g_delta.deltas;
    rebases = g_delta.rebases;
    bytes = g_delta.bytes;
    chunks = g_delta.chunks;
    groups = g_delta.groups;
    g_delta.deltas = g_delta.rebases = g_delta.bytes = g_delta.chunks = g_delta.groups = 0;
  }
  const uint64_t draws = deltas + rebases;
  if (!draws)
    return {};
  const double per_delta = double(std::max<uint64_t>(deltas, 1));
  std::string line = fmt::format(
      "device snapshots (banjo_renut_snapshot_deltas): {} draws, {:.0f} bytes kept a draw on average (the whole device "
      "is {}); {:.1f} chunks and {:.1f} constant groups a delta; {} whole copies (the frames' first draws); {} "
      "Begin*Vertices draws as whole copies ({} of them narrowed to their shaders' float constants, {:.0f} bytes a "
      "copy, {:.0f} with the prefixes alone; banjo_renut_deferred_narrow; {} checked on the render thread, {} drawn "
      "with other shaders since the start); their vertex data {} draws, {:.0f} KB (#52's census)",
      draws, double(bytes) / double(draws), d3d::kDeviceSnapshotSize, double(chunks) / per_delta,
      double(groups) / per_delta, rebases, whole, narrowed,
      narrowed ? double(narrowed_bytes) / double(narrowed) : 0.0,
      narrowed ? double(narrowed_prefix) / double(narrowed) : 0.0,
      g_narrow_checked.exchange(0, std::memory_order_relaxed),  // blur-nx (2026-11-13, #13's fix)
      g_narrow_differ.load(std::memory_order_relaxed),
      g_deferred_vertex_draws.exchange(0, std::memory_order_relaxed),
      double(g_deferred_vertex_bytes.exchange(0, std::memory_order_relaxed)) / 1024.0);
  if (DeferredChainOn())  // blur-nx (2026-11-13, #51)
    line += fmt::format("; Begin*Vertices deltas in the chain (banjo_renut_deferred_chain), {} draws of another device "
                        "made whole while one waited", cross);
  line += DrawerCensus();  // blur-nx (2026-11-13, M-31)
  if (DeltasVerifyOn()) {
    line += fmt::format("; verify: {} draws checked, {} differ", g_delta_verified.exchange(0, std::memory_order_relaxed),
                        g_delta_differ.exchange(0, std::memory_order_relaxed));
  }
  line += g_capture_marks_report;  // sasrt-nx (2026-11-10, the audit's finding 7)
  return line;
}

// bangaio-nx (2026-10-29, v6, banjo_renut_delta_prefetch): the lines CaptureDelta is about to compare, the device's and
// the shadow's, asked for at once (prfm: a hint, which cannot fault). The game's own work between two draws pushes them
// out of the L1, and the compare then waited on them a group at a time.
// sasrt-nx (2026-11-12, batch C4): with the capture marks, the delta compares the list's head and the marked chunks
// only (~38 of ~77): those lines alone, read here as CaptureDelta will decide (nothing taken: a hint).
REXCVAR_DEFINE_BOOL(sasrt_capture_marks_prefetch, true, "SASRT/Recording",
                    "sasrt_capture_marks: the delta prefetch asks only for the chunks the marked delta compares (the "
                    "list's head and the marked chunks) instead of every chunk. Hints only")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

void PrefetchDeltaLines(u32 device_va) {
  const u8 *device = GuestPtr<const u8>(device_va);
  if (!device)
    return;
  static const bool marks_prefetch = REXCVAR_GET(sasrt_capture_marks) && REXCVAR_GET(sasrt_capture_marks_prefetch);
  if (marks_prefetch &&
      g_delta.device.load(std::memory_order_relaxed) == reinterpret_cast<const d3d::Device *>(device) &&
      !g_capture_next_whole.load(std::memory_order_relaxed) && !g_capture_marks_failed.load(std::memory_order_relaxed)) {
    // The device's mark slot, its fast lookup only (TouchSlotOf's slow path may give a slot).
    const uint64_t e = native::g_touch_map[native::TouchMapIndex(device_va)].load(std::memory_order_relaxed);
    const u32 slot = (e && u32(e >> 32) == device_va) ? u32(e) : 0u;
    if (slot - 1 < native::kTouchSlots - 1) {
      const auto *d = reinterpret_cast<const d3d::Device *>(device);
      const uint64_t marked = native::g_touch[slot].chunks | kCaptureUntagged |
                              native::TagChunks(u64(d->m_Pending[2]), u64(d->m_Pending[3]), u64(d->m_Pending[4]));
      const DeltaMarkedList &ml = DeltasNarrowOn() ? kDeltaReadMarked : kDeltaAllMarked;
      for (u32 k = 0; k < ml.pre_count; ++k) {
        const u32 at = DeltaChunkOffset(ml.pre[k]);
        __builtin_prefetch(device + at);
        __builtin_prefetch(g_delta.shadow + at);
      }
      for (uint64_t bits = marked & ml.markable; bits; bits &= bits - 1) {
        const u32 at = DeltaChunkOffset(kDeltaMarkFirst + u32(std::countr_zero(bits)));
        __builtin_prefetch(device + at);
        __builtin_prefetch(g_delta.shadow + at);
      }
      return;
    }
  }
  const DeltaRuns &runs = DeltasNarrowOn() ? kDeltaReadRuns : kDeltaAllRuns;
  for (u32 r = 0; r < runs.count; ++r) {
    const u32 at = DeltaChunkOffset(runs.run[r].first);
    for (u32 k = 0; k < runs.run[r].count; ++k) {
      __builtin_prefetch(device + at + k * kDeltaUnitBytes);
      __builtin_prefetch(g_delta.shadow + at + k * kDeltaUnitBytes);
    }
  }
}

void QueueDraw(u32 device_va, const DrawCall &call, u32 up_vertex_bytes, u32 up_index_bytes) {
  // blur-nx (2026-11-18, the census's #29): the immediate draws and their queueing time on the game threads.
  struct HbScope {
    bool on;
    uint64_t t0;
    ~HbScope() {
      if (on) {
        ::renut::gpu::host_batch::Add(::renut::gpu::host_batch::kImmediateDraws);
        ::renut::gpu::host_batch::Add(::renut::gpu::host_batch::kImmediateTicks, ::renut::gpu::host_batch::Ticks() - t0);
      }
    }
  } hb_scope{::renut::gpu::host_batch::CensusOn(),
             ::renut::gpu::host_batch::CensusOn() ? ::renut::gpu::host_batch::Ticks() : 0};
  NoteDrawer(device_va);  // blur-nx (2026-11-13, M-31's census)
  const bool deltas = DeltasOn();  // bangaio-nx (2026-10-29, ARM): its static's guard read once, not three times
  if (deltas && DeltaPrefetchOn())
    PrefetchDeltaLines(device_va);  // bangaio-nx (2026-10-29, v6)
  FlushDeferredVertices(device_va);
  RunReadyCallbacks();
  // sa2-nx (2026-10-20, banjo_renut_snapshot_deltas): made and queued under the chain's lock.
  std::unique_lock<std::mutex> chain;
  if (deltas)
    chain = std::unique_lock<std::mutex>(g_delta.mutex);
  // blur-nx (2026-11-13, #51): another device's Begin*Vertices delta waiting: this draw whole, outside the chain.
  const bool cross = deltas && g_delta.deferred_device && g_delta.deferred_device != device_va;
  if (cross)
    ++g_delta.cross;
  DrawCapture *capture = deltas && !cross ? CaptureDelta(device_va, call) : Capture(device_va, call);
  if (!capture)
    return;
  if (call.up_vertices)
    capture->vertices.assign(call.up_vertices, call.up_vertices + up_vertex_bytes);
  if (call.up_indices)
    capture->indices.assign(call.up_indices, call.up_indices + up_index_bytes);
  if (const auto *guest_device = GuestPtr<const u8>(device_va)) {
    u32 vs_word;
    std::memcpy(&vs_word, guest_device + d3d::kDeviceOffsetVertexShader, 4);
    capture->binding = LastBindingOf(__builtin_bswap32(vs_word));
  }
  QueueCapture(capture);
}

void QueueDeferredDraw(u32 device_va, const DrawCall &call, const u8 *scratch, u32 bytes) {
  NoteDrawer(device_va);  // blur-nx (2026-11-13, M-31's census)
  FlushDeferredVertices(device_va);
  RunReadyCallbacks();
  // sa2-nx (2026-10-20, sa2_renut_deferred_chain, from futari-nx via peggle2-nx): a Begin*Vertices draw of the chain
  // too. Made under the chain's lock and queued by FlushDeferredVertices under it as well, before any other draw of the
  // device is made (every hook flushes its device's deferred draw first), so the render thread still applies the chain
  // in order. A draw that will not be queued (no scratch) stays a whole capture outside the chain, as before.
  // blur-nx (2026-11-13, #51): not while another device's delta waits (then a whole capture below, outside the chain).
  if (DeltasOn() && DeferredChainOn() && scratch) {
    std::unique_lock<std::mutex> chain(g_delta.mutex);
    if (g_delta.deferred_device && g_delta.deferred_device != device_va) {
      ++g_delta.cross;  // blur-nx (2026-11-13, #51): the whole capture below
    } else {
      {
        std::lock_guard lock(g_deferred_mutex);
        auto it = g_deferred.find(device_va);
        if (it != g_deferred.end()) {
          // One not flushed (FlushDeferredVertices above queued it, so none is expected): dropped as the original
          // replaced it; its delta never reaches the render thread, so the chain rebases.
          g_capture_pool.Give(it->second.capture);
          g_deferred.erase(it);
          DeferredOf(device_va).fetch_sub(1, std::memory_order_acq_rel);  // blur-nx (2026-11-17)
          g_deferred_count.store(g_deferred.size(), std::memory_order_release);
          g_delta.device.store(nullptr, std::memory_order_relaxed);
        }
      }
      DrawCapture *capture = CaptureDelta(device_va, call);
      if (!capture)
        return;
      std::lock_guard lock(g_deferred_mutex);
      if (!g_deferred.count(device_va))
        DeferredOf(device_va).fetch_add(1, std::memory_order_acq_rel);  // blur-nx (2026-11-17)
      g_deferred[device_va] = {capture, scratch, bytes};
      g_deferred_count.store(g_deferred.size(), std::memory_order_release);
      g_delta.deferred_device = device_va;  // blur-nx (2026-11-13, #51): cleared when FlushDeferredVertices queues it
      return;
    }
  }
  DrawCapture *capture = nullptr;
  {
    // sa2-nx (banjo_renut_snapshot_deltas): a whole capture (queued later than made: outside the chain), whose dirty
    // constant groups ClearPending hands to the chain's next delta.
    std::unique_lock<std::mutex> chain;
    if (DeltasOn())
      chain = std::unique_lock<std::mutex>(g_delta.mutex);
    capture = CaptureDeferred(device_va, call);  // blur-nx (2026-11-13, #13): Capture() unless narrowed
    if (DeltasOn())
      ++g_delta.whole;
  }
  if (!capture)
    return;
  if (!scratch) {
    g_capture_pool.Give(capture);
    return;
  }
  std::lock_guard lock(g_deferred_mutex);
  if (!g_deferred.count(device_va))
    DeferredOf(device_va).fetch_add(1, std::memory_order_acq_rel);  // blur-nx (2026-11-17)
  DeferredDraw &slot = g_deferred[device_va];
  g_capture_pool.Give(slot.capture);  // one not flushed (the original replaced it the same way)
  slot = {capture, scratch, bytes};
  g_deferred_count.store(g_deferred.size(), std::memory_order_release);
}

void FlushDeferredVertices(u32 device_va) {
  FlushRecordedVertices(device_va);
  // sa2-nx (2026-10-20): none waiting, no lock. blur-nx (2026-11-17, blur_renut_flush_fast_local): none of this
  // device's (the find below looks for nothing else).
  static const bool local = REXCVAR_GET(blur_renut_flush_fast_local);
  if (HookFastPathsOn() && (local ? DeferredOf(device_va).load(std::memory_order_acquire) == 0
                                  : g_deferred_count.load(std::memory_order_acquire) == 0))
    return;
  // sa2-nx (2026-10-20, sa2_renut_deferred_chain): a chain draw is queued under the chain's lock (taken before the
  // deferred map's, as QueueDeferredDraw takes them), so no draw of the chain is made or queued between.
  std::unique_lock<std::mutex> chain;
  if (DeltasOn() && DeferredChainOn())
    chain = std::unique_lock<std::mutex>(g_delta.mutex);
  DeferredDraw deferred;
  {
    std::lock_guard lock(g_deferred_mutex);
    auto it = g_deferred.find(device_va);
    if (it == g_deferred.end())
      return;
    deferred = std::move(it->second);
    g_deferred.erase(it);
    DeferredOf(device_va).fetch_sub(1, std::memory_order_acq_rel);  // blur-nx (2026-11-17)
    g_deferred_count.store(g_deferred.size(), std::memory_order_release);
  }
  deferred.capture->vertices.assign(deferred.scratch, deferred.scratch + deferred.bytes);
  // blur-nx (2026-11-13, #52's census): the vertex bytes the flush copies (a scratch ring could leave them in place).
  g_deferred_vertex_bytes.fetch_add(deferred.bytes, std::memory_order_relaxed);
  g_deferred_vertex_draws.fetch_add(1, std::memory_order_relaxed);
  QueueCapture(deferred.capture);
  if (chain.owns_lock() && g_delta.deferred_device == device_va)
    g_delta.deferred_device = 0;  // blur-nx (2026-11-13, #51): its delta queued; the chain is free for any device
}

void QueueClear(u32 device_va, u32 flags, const ClearRect *rect, const float color[4], float depth,
                u32 stencil) {
  FlushDeferredVertices(device_va);
  RunReadyCallbacks();
  const auto *device = GuestPtr<const u8>(device_va);
  if (!device)
    return;
  DrawCapture *args = g_capture_pool.Take();  // banjo-nx (2026-10-19): pooled, see DrawCapture
  // sasrt-nx (2026-11-19, base port 138): the whole device still, not blur-nx's #55 target words and viewport:
  // ClearStateLocked's views come from its destination packet (render/draw.cpp, SasrtViewDeviceScope).
  args->state.assign(device, device + d3d::kDeviceSnapshotSize);
  CaptureSurfaces(args, args->state.data());  // sasrt-nx
  args->has_rect = rect != nullptr;
  args->rect = rect ? *rect : ClearRect{};
  std::memcpy(args->color, color, sizeof(args->color));
  args->flags = flags;
  args->depth = depth;
  args->stencil = stencil;
  CaptureStackHeaders(device, args->stack_headers);  // blur-nx (2026-11-10, port 76; its key 215)
  render_thread::Queue([args] {
    SetReplaySurfaceOverridesLocked(args->surface_va, args->surface_desc, args->surfaces);  // sasrt-nx
    SetReplayStackHeaders(args->stack_headers.count ? &args->stack_headers : nullptr);  // port 76 (215)
    ClearStateLocked(args->state.data(), args->flags, args->has_rect ? &args->rect : nullptr, args->color,
                     args->depth, args->stencil);
    SetReplaySurfaceOverridesLocked(nullptr, nullptr, 0);  // sasrt-nx
    SetReplayIndexBufferLocked(0, nullptr);  // sasrt-nx (2026-10-21)
    g_sasrt_draw_streams = nullptr;  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams)
    SetReplayStackHeaders(nullptr);  // port 76 (215)
    g_capture_pool.Give(args, true);
  });
}

void QueueResolve(u32 device_va, u32 flags, const ClearRect *source_rect, u32 dest_texture_va,
                  i32 dest_x, i32 dest_y, u32 dest_level, u32 dest_slice,
                  const float clear_color[4], float clear_depth, u32 clear_stencil) {
  FlushDeferredVertices(device_va);
  RunReadyCallbacks();
  const auto *device = GuestPtr<const u8>(device_va);
  if (!device)
    return;
  // sasrt-nx (2026-11-10, the batch's audit, finding 1): the chain's next delta compares every chunk (sasrt_capture_marks).
  g_capture_next_whole.store(true, std::memory_order_relaxed);
  // The destination header as it is now: the game often builds it on the
  // stack (as for recorded resolves).
  DrawCapture *args = g_capture_pool.Take();  // banjo-nx (2026-10-19): pooled, see DrawCapture
  // sasrt-nx (2026-11-19, base port 138): the whole device still, not blur-nx's M-35 target words: ResolveStateLocked
  // takes the source's view from its destination packet (render/draw.cpp, SasrtViewDeviceScope).
  args->state.assign(device, device + d3d::kDeviceSnapshotSize);
  CaptureSurfaces(args, args->state.data());  // sasrt-nx
  args->has_rect = source_rect != nullptr;
  args->rect = source_rect ? *source_rect : ClearRect{};
  args->has_color = clear_color != nullptr;
  if (clear_color)
    std::memcpy(args->color, clear_color, sizeof(args->color));
  const auto *header = GuestPtr<const d3d::BaseTexture>(dest_texture_va);
  args->has_dest_format = header != nullptr;
  if (header)
    args->dest_format = header->Format;
  args->flags = flags;
  args->dest_texture_va = dest_texture_va;
  args->dest_x = dest_x;
  args->dest_y = dest_y;
  args->dest_level = dest_level;
  args->dest_slice = dest_slice;
  args->depth = clear_depth;
  args->stencil = clear_stencil;
  CaptureStackHeaders(device, args->stack_headers);  // blur-nx (2026-11-10, port 76; its key 215)
  render_thread::Queue([args] {
    SetReplaySurfaceOverridesLocked(args->surface_va, args->surface_desc, args->surfaces);  // sasrt-nx
    SetReplayStackHeaders(args->stack_headers.count ? &args->stack_headers : nullptr);  // port 76 (215)
    ResolveStateLocked(args->state.data(), args->flags, args->has_rect ? &args->rect : nullptr,
                       args->dest_texture_va, args->has_dest_format ? &args->dest_format : nullptr,
                       args->dest_x, args->dest_y, args->dest_level, args->dest_slice,
                       args->has_color ? args->color : nullptr, args->depth, args->stencil);
    SetReplaySurfaceOverridesLocked(nullptr, nullptr, 0);  // sasrt-nx
    SetReplayIndexBufferLocked(0, nullptr);  // sasrt-nx (2026-10-21)
    g_sasrt_draw_streams = nullptr;  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams)
    SetReplayStackHeaders(nullptr);  // port 76 (215)
    g_capture_pool.Give(args, true);
  });
}

} // namespace renut::gpu
