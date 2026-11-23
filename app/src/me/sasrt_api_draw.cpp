// Sonic & All-Stars Racing Transformed: the native Direct3D draws (sasrt_api_draws; sa2-nx's sa2_api_draw.cpp, ported,
// plus DrawIndexedVertices, which sa2-nx has not made native): DrawIndexedVertices, DrawVertices, DrawVerticesUP and
// BeginVertices (the inline-vertex draw) and the window scissor writer. See sasrt_api.h and sasrt_api_internal.h.
#include "me/sasrt_api_internal.h"

SASRT_ENHANCEMENT(g_api_thread_stats, sasrt_api_thread_stats, sasrt::enhancements::Group::kCpu, true,
                  "Native Direct3D layer: its per-call statistics and its timer's call counter on the drawing "
                  "thread's own memory, added to the shared totals every 64 records (two threads draw: six shared "
                  "words were loaded and stored per native call)");
SASRT_ENHANCEMENT(g_api_draws, sasrt_api_draws, sasrt::enhancements::Group::kCpu, true,
                  "Native Direct3D draws (sa2-nx's API-level renderer): DrawIndexedVertices, DrawVertices, "
                  "DrawVerticesUP / BeginVertices and the window scissor writer as native code, with Direct3D's "
                  "draw-time state flush and shader load, writing "
                  "the ring's records directly (no PM4); only into the main command buffer (verify mode: every call "
                  "compared with the original run on a copy of the device)");

// The originals verify mode runs on a device copy.
REX_EXTERN(__imp__sub_82CD1DB8);  // D3DDevice_DrawIndexedVertices
REX_EXTERN(__imp__sub_82CD18D0);  // D3DDevice_DrawVertices
REX_EXTERN(__imp__sub_82CD0BB8);  // D3DDevice_BeginVertices [82565758]

namespace sasrt::api {
using namespace detail;

namespace {
// A native draw call: the shadow run in verify mode, the shader objects noted, the ops, the marker's space (Direct3D's
// own check, which may submit), the record published on this thread's ring, then the marker, then the comparison.
template <class WriteOps>
bool NativeDraw(ThreadData& t, PPCContext& ctx, uint8_t* base, const char* what,
                void (*original)(PPCContext&, uint8_t*), WriteOps&& write_ops) {
  const uint32_t d = ctx.r3.u32;
  if (const Fallback fb = Check(Direct{base}, d)) [[unlikely]] {
    Bump(g_fallbacks[fb]);
    return false;
  }
  Shadow shadow;
  if (VerifyMode()) [[unlikely]] shadow = RunShadow(t, base, ctx, d, original);
  NoteObjects(t, base, d);
  Direct m{base};
  Ops ops = OpenOps(t);
  Ctx<Direct> c{m, ops, base, ctx, d, Scratch(), t};
  write_ops(c);
  const uint32_t submissions = m.L32(d + 11088);
  const uint32_t w = MarkerSpace(t, base, ctx, d);
  SetPacketAddresses(ops, w + 16);
  uint32_t seq = 0;
  if (!Publish(t, seq, ops)) return true;  // the device is already updated: this draw is lost (logged)
  rex::memory::store_and_swap<uint32_t>(HostOf(base, d + dev::kWptr), PutMarker(base, w, seq));
  if (shadow.ok)
    CompareShadow(t, what, base, d, shadow, ops,
                  rex::memory::load_and_swap<uint32_t>(HostOf(base, shadow.copy + dev::kWptr)),
                  m.L32(d + 11088) != submissions, {});
  return true;
}
}  // namespace

static bool DrawIndexedVerticesNative(PPCContext& ctx, uint8_t* base) {
  ThreadData* const tp = Enabled(g_api_draws, ctx, base);
  if (!tp) return false;
  const uint32_t type = ctx.r4.u32, base_vertex = ctx.r5.u32, start = ctx.r6.u32, count = ctx.r7.u32;
  const bool done = NativeDraw(*tp, ctx, base, "DrawIndexedVertices", &__imp__sub_82CD1DB8, [&](Ctx<Direct>& c) {
    DrawIndexedVerticesOps(c, type, base_vertex, start, count, 0);
  });
  if (done) Count(*tp, &ThreadStats::indexed, g_indexed);
  return done;
}

static bool DrawVerticesNative(PPCContext& ctx, uint8_t* base) {
  ThreadData* const tp = Enabled(g_api_draws, ctx, base);
  if (!tp) return false;
  const uint32_t type = ctx.r4.u32, start = ctx.r5.u32, count = ctx.r6.u32;
  return NativeDraw(*tp, ctx, base, "DrawVertices", &__imp__sub_82CD18D0, [&](Ctx<Direct>& c) {
    DrawVerticesOps(c, type, start, count, 0);
  });
}

namespace {
// D3DDevice_BeginVertices(device, type, count, stride) natively (sa2-nx's); false when it does not apply. `data` = the
// inline vertices' address (0: no space, or the record could not be published).
bool BeginVerticesCall(ThreadData& t, const PPCContext& ctx, uint8_t* base, uint32_t d, uint32_t type, uint32_t count,
                       uint32_t stride, uint32_t& data) {
  if (const Fallback fb = Check(Direct{base}, d, 0x80000)) [[unlikely]] {
    Bump(g_fallbacks[fb]);
    return false;
  }
  Shadow shadow;
  if (VerifyMode()) [[unlikely]] {
    PPCContext c = ctx;  // the original's arguments (DrawVerticesUP's registers differ)
    c.r4.u64 = type;
    c.r5.u64 = count;
    c.r6.u64 = stride;
    shadow = RunShadow(t, base, c, d, &__imp__sub_82CD0BB8);
  }
  NoteObjects(t, base, d);
  Direct m{base};
  Ops ops = OpenOps(t);
  Ctx<Direct> c{m, ops, base, ctx, d, Scratch(), t};
  uint32_t marker_end = 0;
  bool ok = true, submitted = false;
  data = BeginVerticesNative(c, type, count, stride, marker_end, ok, submitted);
  if (!ok) {
    data = 0;
    return true;
  }
  if (data) m.S32(d + 13844, marker_end);  // EndVertices moves the write pointer there
  Count(t, &ThreadStats::inline_draws, g_inline);
  if (shadow.ok) {
    // The inline vertices' address (the shadow run's allocator answered with its own block): mapped by CompareShadow.
    CompareShadow(t, "BeginVertices", base, d, shadow, ops,
                  rex::memory::load_and_swap<uint32_t>(HostOf(base, shadow.copy + 13844)), submitted,
                  {{13844, 13852}});
  }
  return true;
}
}  // namespace

static bool BeginVerticesEntry(PPCContext& ctx, uint8_t* base) {
  ThreadData* const tp = Enabled(g_api_draws, ctx, base);
  if (!tp) return false;
  uint32_t data = 0;
  if (!BeginVerticesCall(*tp, ctx, base, ctx.r3.u32, ctx.r4.u32, ctx.r5.u32, ctx.r6.u32, data)) return false;
  ctx.r3.u64 = data;
  return true;
}

static bool DrawVerticesUPNative(PPCContext& ctx, uint8_t* base) {
  // D3DDevice_DrawVerticesUP(device, type, count, data, stride): BeginVertices, the vertices copied in, EndVertices.
  ThreadData* const tp = Enabled(g_api_draws, ctx, base);
  if (!tp) return false;
  const uint32_t d = ctx.r3.u32, count = ctx.r5.u32, src = ctx.r6.u32, stride = ctx.r7.u32;
  uint32_t data = 0;
  if (!BeginVerticesCall(*tp, ctx, base, d, ctx.r4.u32, count, stride, data)) return false;
  if (data) {
    std::memmove(HostOf(base, data), HostOf(base, src), size_t(count) * stride);
    rex::memory::store_and_swap<uint32_t>(HostOf(base, d + dev::kWptr),
                                          rex::memory::load_and_swap<uint32_t>(HostOf(base, d + 13844)));
  }
  return true;
}

// sub_82CCB540(device, x0, y0, x1, y1) [sa2-nx's sub_8254FCE8]: the window offset and scissor (registers 0x2080-0x2082),
// which Direct3D writes straight into the command buffer from SetViewport / SetScissorRect / the render target setters
// (they keep no shadow of them). Tiling (+11068 flags 0x10 / 0x20) wraps them per tile: excluded by the check.
static bool WindowScissorNative(PPCContext& ctx, uint8_t* base) {
  ThreadData* const tp = Enabled(g_api_draws, ctx, base);
  if (!tp) return false;
  ThreadData& t = *tp;
  const uint32_t d = ctx.r3.u32;
  const uint32_t x0 = ctx.r4.u32, y0 = ctx.r5.u32, x1 = ctx.r6.u32, y1 = ctx.r7.u32;
  const Direct m{base};
  if (m.L8(d + dev::kFlags68) & 0x30) [[unlikely]] {
    Bump(g_fallbacks[kFbFlags]);
    return false;
  }
  Shadow shadow;
  if (VerifyMode()) [[unlikely]] shadow = RunShadow(t, base, ctx, d, &__imp__sub_82CCB540);
  Ops ops = OpenOps(t);
  ops.Regs(0x2080, {0, Rlwinm(y0, 16, 2, 15) | Rlwinm(x0, 0, 18, 31), Rlwinm(y1, 16, 2, 15) | Rlwinm(x1, 0, 18, 31)});
  const uint32_t submissions = m.L32(d + 11088);
  const uint32_t w = MarkerSpace(t, base, ctx, d);
  uint32_t seq = 0;
  if (!Publish(t, seq, ops)) return true;
  rex::memory::store_and_swap<uint32_t>(HostOf(base, d + dev::kWptr), PutMarker(base, w, seq));
  Count(t, &ThreadStats::window, g_window);
  if (shadow.ok)
    CompareShadow(t, "WindowScissor", base, d, shadow, ops,
                  rex::memory::load_and_swap<uint32_t>(HostOf(base, shadow.copy + dev::kWptr)),
                  m.L32(d + 11088) != submissions, {});
  return true;
}

// The public entry points (the hooks): each native call timed now and then (Timed: the [api] line's cost).
bool DrawIndexedVertices(PPCContext& ctx, uint8_t* base) {
  return Timed(ctx, [&] { return DrawIndexedVerticesNative(ctx, base); });
}
bool DrawVertices(PPCContext& ctx, uint8_t* base) {
  return Timed(ctx, [&] { return DrawVerticesNative(ctx, base); });
}
bool WindowScissor(PPCContext& ctx, uint8_t* base) {
  return Timed(ctx, [&] { return WindowScissorNative(ctx, base); });
}
bool BeginVertices(PPCContext& ctx, uint8_t* base) {
  return Timed(ctx, [&] { return BeginVerticesEntry(ctx, base); });
}
bool DrawVerticesUP(PPCContext& ctx, uint8_t* base) {
  return Timed(ctx, [&] { return DrawVerticesUPNative(ctx, base); });
}

bool ShadowInlineAlloc(PPCContext& ctx, uint8_t* base) {
  // Verify mode, inside the original's shadow run (on the device copy): Direct3D's inline-data allocator would work on
  // the copy's stale bookkeeping and could wait for GPU progress the copy never sees. Its address does not matter to
  // the comparison (the native side's own allocation stands in for it): a scratch area, at once (sa2-nx's).
  if (!g_shadow) return false;
  ThreadData& t = Thread();
  if (!t.in_original) return false;
  (void)base;
  // The shadow buffer's unused upper half, one block per allocation (aligned as asked), recorded in order.
  const uint32_t words = ctx.r4.u32, align = std::max<uint32_t>(4, ctx.r5.u32);
  uint32_t a = (t.shadow_bump + align - 1) & ~(align - 1);
  if (a + words * 4 > g_shadow + kShadowCopy + kShadowBuffer - 8) a = g_shadow + kShadowCopy + kShadowBuffer / 2;
  t.shadow_bump = a + words * 4;
  t.shadow_allocs.push_back({a, words, false});
  ctx.r3.u64 = a;
  return true;
}

uint64_t ClearCount();

void Report() {
  const uint64_t native = g_native.load(std::memory_order_relaxed);
  const uint64_t original = g_original.load(std::memory_order_relaxed);
  std::string fb;
  for (uint32_t i = 1; i < kFbCount; ++i)
    if (const uint64_t n = g_fallbacks[i].load(std::memory_order_relaxed)) fb += fmt::format(" {} {};", kFallbackNames[i], n);
  const uint64_t outside = g_outside.load(std::memory_order_relaxed);
  if (!native && !original && fb.empty() && !outside) return;
  REXLOG_INFO("[api] native records (sasrt_api_*, cumulative): {} ({:.1f} op words each; {} DrawIndexedVertices, {} "
              "window scissor, {} inline-vertex draws, {} clears), {} by the original in verify mode (on a device "
              "copy); left to the old path: {} outside "
              "the main command buffer or in tiling;{} (device flag bits +11068 {:02X}, +11071 {:02X}); verify: {} "
              "compared, {} differences{}",
              native, native ? double(g_ops_words.load(std::memory_order_relaxed)) / double(native) : 0.0,
              g_indexed.load(std::memory_order_relaxed), g_window.load(std::memory_order_relaxed),
              g_inline.load(std::memory_order_relaxed), ClearCount(), original, outside,
              fb.empty() ? " no other fallback" : fb, g_fb_flags68.load(std::memory_order_relaxed),
              g_fb_flags71.load(std::memory_order_relaxed), g_checked.load(std::memory_order_relaxed),
              g_differences.load(std::memory_order_relaxed), g_failed.load(std::memory_order_relaxed) ? " (STOPPED)" : "");
  // The layer's cost on the drawing thread since the last report (about 10 s): the timed calls' average times all
  // native calls (Timed).
  static uint64_t last_calls = 0, last_ns = 0, last_timed = 0;
  const uint64_t calls = g_calls.load(std::memory_order_relaxed), ns = g_timed_ns.load(std::memory_order_relaxed),
                 timed = g_timed_calls.load(std::memory_order_relaxed);
  const uint64_t dc = calls - last_calls, dns = ns - last_ns, dt = timed - last_timed;
  last_calls = calls;
  last_ns = ns;
  last_timed = timed;
  if (dt) {
    const double per_ns = double(dns) / double(dt);
    const double total_ms = per_ns * double(dc) / 1e6;
    REXLOG_INFO("[api] drawing-thread cost (10 s): {:.2f} us per native call (every 16th timed: {} of {}), {:.1f} ms "
                "in all = {:.2f} % of one core",
                per_ns / 1000.0, dt, dc, total_ms, total_ms / 100.0);
  }
}

}  // namespace sasrt::api
