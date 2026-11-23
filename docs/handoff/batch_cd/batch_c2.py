# sasrt-nx (2026-11-12, batch C part 2: the two analysis agents' exact items, audited). Applied after the guard build.
#  C4  the delta prefetch: only the chunks the marks path compares (the list's head + the marked chunks), when the
#      chain's delta will take that path; the full prefetch otherwise (sasrt_capture_marks_prefetch). Hints only.
#  C5  the replayed draw's surface overrides cleared lazily (sasrt_surface_override_lazy_clear): every captured draw set
#      them and cleared them after, two surface-epoch bumps a draw, so the next draw always re-gathered its targets
#      (GatherTargets, the slow surface lookups, BindTargets: ~89 % of fast draws). The clear is owed until something
#      reads the overrides or the epoch; a next list equal to the kept one undoes it unseen. Any reader settles it first.
#  C6  GetHostSurfaceSlow: one g_targets lookup, not count() then operator[] (same map contents).
#  C7  the command-buffer replay: the op three ahead's other read lines prefetched too (surfaces, ib, desc fields).
#  C8  the render thread's next draw item: the capture's call / surface / ib lines prefetched (was its first two lines);
#      the pool's next capture prefetched for writing over the same lines.
#  C9  CaptureDelta: g_capture_next_whole read before it is exchanged (no exclusive store a delta when it is clear).
#  C10 sasrt::trace::On() a plain latched load (inline), not a call and a static's guard in every draw hook.
#  C11 SyncPendingCount stores only a changed count (the line the recording threads read is not written each op).
#  C12 the XMA worker's full sweep visits only allocated contexts (the context bitmap's cleared bits, ascending).
#  C13 RenderScale::Factor from a table kept with the ratios (deko3d): the same float division, done once.
# Idempotent; asserts every anchor once.
R = 'D:/sonic transformed/sasrt-nx/'


def patch(rel, edits, mark):
    p = R + rel
    b = open(p, 'rb').read()
    crlf = b'\r\n' in b
    s = b.decode('utf-8').replace('\r\n', '\n')
    if mark in s:
        print('already patched:', rel, '(' + mark + ')')
        return
    for o, n in edits:
        assert s.count(o) == 1, (rel, o[:90], s.count(o))
        s = s.replace(o, n)
    open(p, 'wb').write((s.replace('\n', '\r\n') if crlf else s).encode('utf-8'))
    print('patched:', rel, '(' + mark + ')')


Q = 'app/src/renut_engine/gpu/backend/queued.cpp'
# ---- C4 + C9 + C8 (pool side)
patch(Q, [
    ('''void PrefetchDeltaLines(u32 device_va) {
  const u8 *device = GuestPtr<const u8>(device_va);
  if (!device)
    return;
  const DeltaRuns &runs''', '''// sasrt-nx (2026-11-12, batch C4): with the capture marks, the delta compares the list's head and the marked chunks
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
  const DeltaRuns &runs'''),
    ('''      const bool whole_next = g_capture_next_whole.exchange(false, std::memory_order_relaxed);  // audit finding 1''',
     '''      // (2026-11-12, batch C9: read first, exchanged only when set: no exclusive store at every delta; a store racing
      // with this is taken by this delta or the next, as with the exchange alone)
      const bool whole_next = g_capture_next_whole.load(std::memory_order_relaxed) &&
                              g_capture_next_whole.exchange(false, std::memory_order_relaxed);  // audit finding 1'''),
    ('''          __builtin_prefetch(next, 1);
          __builtin_prefetch(next + 64, 1);
          __builtin_prefetch(next + 128, 1);''', '''          __builtin_prefetch(next, 1);
          __builtin_prefetch(next + 64, 1);
          __builtin_prefetch(next + 128, 1);
          // sasrt-nx (2026-11-12, batch C8): the surface headers and index buffer lines CaptureSurfaces writes
          __builtin_prefetch(next + 256, 1);
          __builtin_prefetch(next + 320, 1);
          __builtin_prefetch(next + 384, 1);'''),
], 'batch C4')

# ---- C8 (render thread side)
patch('app/src/renut_engine/gpu/backend/render_thread.cpp', [
    ('''  if (const auto *a = static_cast<const char *>(item.prefetch[0])) {
    __builtin_prefetch(a);
    __builtin_prefetch(a + 64);
  }''', '''  if (const auto *a = static_cast<const char *>(item.prefetch[0])) {
    __builtin_prefetch(a);
    __builtin_prefetch(a + 64);
    // sasrt-nx (2026-11-12, batch C8): prefetch[0] is a draw's capture (QueuePrefetched's only caller): its call's
    // second line and the surface headers / index buffer the lambda reads first.
    __builtin_prefetch(a + 128);
    __builtin_prefetch(a + 256);
    __builtin_prefetch(a + 320);
    __builtin_prefetch(a + 384);
  }'''),
], 'batch C8')

S = 'app/src/renut_engine/gpu/render/surfaces.cpp'
# ---- C5 + C6 + C13 (setters)
patch(S, [
    ('''SurfaceMemo g_surface_memo[64];  // banjo-nx (2026-10-19, render-thread proposal 8): 64, indexed by a hash of the VA
uint64_t g_surface_epoch = 1;''', '''SurfaceMemo g_surface_memo[64];  // banjo-nx (2026-10-19, render-thread proposal 8): 64, indexed by a hash of the VA
uint64_t g_surface_epoch = 1;
// sasrt-nx (2026-11-12, batch C5, sasrt_surface_override_lazy_clear): a replayed draw's override clear not applied yet
// (SetReplaySurfaceOverridesLocked); whatever reads the overrides or the epoch applies it first (SettleOverridesSlow).
bool g_override_owed = false;
void SettleOverridesSlow();'''),
    ('''uint64_t SurfaceEpochLocked() { return g_surface_epoch; }''',
     '''uint64_t SurfaceEpochLocked() {
  if (g_override_owed) [[unlikely]]
    SettleOverridesSlow();  // sasrt-nx (2026-11-12, batch C5)
  return g_surface_epoch;
}'''),
    ('''void SetReplaySurfaceOverridesLocked(const u32 *surface_va, const d3d::SurfaceDesc *desc, u32 count) {
  count = count < 5 ? count : 5;
  // sasrt-nx (2026-10-29, the banjo-nx sync): other overrides are other targets for the same device words: the
  // surface epoch moves, which banjo-nx's chain reuse and fast path keep targets by.
  bool same = count == g_override_count;
  for (u32 i = 0; i < count && same; ++i)
    same = g_override_va[i] == surface_va[i] && std::memcmp(&g_override_desc[i], &desc[i], sizeof(desc[i])) == 0;
  if (same)
    return;''', '''// sasrt-nx (2026-11-12, batch C5; the render-thread agent's finding): every captured draw sets its overrides and
// clears them after (queued.cpp), two epoch bumps a draw, so the next draw's fast path always gathered its targets again
// (GatherTargets, the slow surface lookups, BindTargets). Lazy: the clear is owed; anything that reads the overrides or
// the epoch (ReplaySurfaceOverride, SurfaceEpochLocked: the memo reads after the former) applies it first, as it was;
// a next list equal to the kept one, with nothing read between, undoes the clear: nobody saw it.
REXCVAR_DEFINE_BOOL(sasrt_surface_override_lazy_clear, true, "SASRT/GPU",
                    "A replayed draw's surface overrides are cleared lazily: the next draw with the same recorded "
                    "surfaces keeps its targets (no surface-epoch bump) unless something read the cleared state between. "
                    "Off: cleared and bumped at once, as before")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

namespace {
void SettleOverridesSlow() {
  g_override_owed = false;
  ++g_surface_epoch;
  g_override_count = 0;
}
bool OverridesLazyOn() {
  static const bool on = REXCVAR_GET(sasrt_surface_override_lazy_clear);
  return on;
}
}  // namespace

void SetReplaySurfaceOverridesLocked(const u32 *surface_va, const d3d::SurfaceDesc *desc, u32 count) {
  count = count < 5 ? count : 5;
  // sasrt-nx (2026-10-29, the banjo-nx sync): other overrides are other targets for the same device words: the
  // surface epoch moves, which banjo-nx's chain reuse and fast path keep targets by.
  const auto same_as_kept = [&] {
    bool same = count == g_override_count;
    for (u32 i = 0; i < count && same; ++i)
      same = g_override_va[i] == surface_va[i] && std::memcmp(&g_override_desc[i], &desc[i], sizeof(desc[i])) == 0;
    return same;
  };
  if (OverridesLazyOn()) {  // sasrt-nx (2026-11-12, batch C5)
    if (count == 0) {
      if (g_override_count != 0)
        g_override_owed = true;  // (as before: no bump when there was nothing to clear)
      return;
    }
    if (g_override_owed) {
      if (same_as_kept()) {
        g_override_owed = false;  // the clear undone: no one saw it
        return;
      }
      SettleOverridesSlow();  // the clear as it was owed, then the new list as before
    }
  }
  if (same_as_kept())
    return;'''),
    ('''const d3d::SurfaceDesc *ReplaySurfaceOverride(u32 surface_va) {
  for (u32 i = 0; i < g_override_count; ++i)''', '''const d3d::SurfaceDesc *ReplaySurfaceOverride(u32 surface_va) {
  if (g_override_owed) [[unlikely]]
    SettleOverridesSlow();  // sasrt-nx (2026-11-12, batch C5)
  for (u32 i = 0; i < g_override_count; ++i)'''),
    # C6
    ('''  const uint64_t key = TargetKey(*desc, depth, format, scale);
  if (g_override_active) {
    // sasrt-nx: a replayed op's view; the surface's own binding (the title device's now) is left as it is, and
    // the view's target stays (one user for good).
    if (!g_targets.count(key))
      ++g_target_users[key];''', '''  const uint64_t key = TargetKey(*desc, depth, format, scale);
  // sasrt-nx (2026-11-12, batch C6): one lookup of the key (count() then operator[] was two; the same map contents)
  auto target_it = g_targets.find(key);
  if (g_override_active) {
    // sasrt-nx: a replayed op's view; the surface's own binding (the title device's now) is left as it is, and
    // the view's target stays (one user for good).
    if (target_it == g_targets.end())
      ++g_target_users[key];'''),
    ('''  }

  auto &slot = g_targets[key];
  // The view's target covers every surface over it, and every tile while''', '''  }

  if (target_it == g_targets.end())
    target_it = g_targets.try_emplace(key).first;  // (what operator[] does)
  auto &slot = target_it->second;
  // The view's target covers every surface over it, and every tile while'''),
    # C13 setters
    ('''  const uint32_t g = std::gcd(uint32_t(height), 720u);
  RenderScale::kNumerators[code] = uint32_t(height) / g;
  RenderScale::kDenominators[code] = 720u / g;''', '''  const uint32_t g = std::gcd(uint32_t(height), 720u);
  RenderScale::SetRatio(code, uint32_t(height) / g, 720u / g);  // sasrt-nx (2026-11-12, batch C13: with its factor)'''),
    ('''        const uint32_t g = std::gcd(uint32_t(h), 720u);
        RenderScale::kNumerators[code] = uint32_t(h) / g;
        RenderScale::kDenominators[code] = 720u / g;''', '''        const uint32_t g = std::gcd(uint32_t(h), 720u);
        RenderScale::SetRatio(code, uint32_t(h) / g, 720u / g);  // sasrt-nx (2026-11-12, batch C13)'''),
], 'batch C5')

# ---- C13 (the table)
patch('app/src/renut_engine/gpu/render/render_scale.h', [
    ('''  static inline uint32_t kNumerators[kCount] = {1, 2, 3, 2, 9, 4, 5, 4};
  static inline uint32_t kDenominators[kCount] = {1, 3, 2, 1, 10, 1, 4, 3};
#else''', '''  static inline uint32_t kNumerators[kCount] = {1, 2, 3, 2, 9, 4, 5, 4};
  static inline uint32_t kDenominators[kCount] = {1, 3, 2, 1, 10, 1, 4, 3};
  // sasrt-nx (2026-11-12, batch C13): Factor()'s quotient per code, kept with the ratios (SetRatio: the same single
  // float division, done when a ratio is set instead of at every call; the initial ones folded the same way).
  static inline float kFactors[kCount] = {float(1) / float(1), float(2) / float(3), float(3) / float(2),
                                          float(2) / float(1), float(9) / float(10), float(4) / float(1),
                                          float(5) / float(4), float(4) / float(3)};
  static void SetRatio(uint32_t code, uint32_t numerator, uint32_t denominator) {
    kNumerators[code] = numerator;
    kDenominators[code] = denominator;
    kFactors[code] = float(numerator) / float(denominator);
  }
#else'''),
    ('''  float Factor() const { return float(kNumerators[code]) / float(kDenominators[code]); }''',
     '''#if defined(PLUME_DEKO3D)
  float Factor() const { return kFactors[code]; }  // sasrt-nx (2026-11-12, batch C13)
#else
  float Factor() const { return float(kNumerators[code]) / float(kDenominators[code]); }
#endif'''),
], 'batch C13')

# ---- C7
patch('app/src/renut_engine/gpu/guest/command_buffers.cpp', [
    ('''        const char *three_ahead = reinterpret_cast<const char *>(&ops[op_index + 3]);
        __builtin_prefetch(three_ahead);
        __builtin_prefetch(three_ahead + 64);''', '''        const char *three_ahead = reinterpret_cast<const char *>(&ops[op_index + 3]);
        __builtin_prefetch(three_ahead);
        __builtin_prefetch(three_ahead + 64);
        // sasrt-nx (2026-11-12, batch C7): the op's other lines its replay reads (the recorded surfaces, their headers,
        // the index buffer, the streams / vertex shader words: misses in the abB console profile)
        __builtin_prefetch(three_ahead + 192);
        __builtin_prefetch(three_ahead + 384);
        __builtin_prefetch(three_ahead + 512);
        __builtin_prefetch(three_ahead + 576);
        __builtin_prefetch(three_ahead + 640);'''),
    # C11
    ('''void SyncPendingCount() { g_pending_count.store(g_pending_vertices.size(), std::memory_order_release); }''',
     '''// sasrt-nx (2026-11-12, batch C11): a changed count only (the sole writer holds g_record_mutex): the line every op's
// memo check reads is not written at each op with the same value. A reader that sees the count unchanged needs nothing
// the store would have published (0: it takes no pending data; not 0: it takes the mutex).
void SyncPendingCount() {
  const size_t n = g_pending_vertices.size();
  if (g_pending_count.load(std::memory_order_relaxed) != n)
    g_pending_count.store(n, std::memory_order_release);
}'''),
], 'batch C7')

# ---- C10
patch('app/src/renut_engine/sasrt_trace.h', [
    ('''#include <cstdint>

namespace sasrt::trace {''', '''#include <atomic>  // sasrt-nx (2026-11-12, batch C10)
#include <cstdint>

namespace sasrt::trace {'''),
    ('''bool On();''', '''// sasrt-nx (2026-11-12, batch C10): a plain load once latched (it was an out-of-line call and a static's guard, a
// load-acquire, in every draw hook); the value comes from the configuration only.
extern bool g_on_value;
extern std::atomic<bool> g_on_latched;
[[gnu::cold, gnu::noinline]] bool LatchOn();
[[gnu::always_inline]] inline bool On() {
  if (!g_on_latched.load(std::memory_order_relaxed)) [[unlikely]]
    return LatchOn();
  return g_on_value;
}'''),
], 'batch C10')
patch('app/src/renut_engine/sasrt_trace.cpp', [
    ('''bool On() {
  static const bool on = REXCVAR_GET(sasrt_renut_diag_trace);
  return on;
}''', '''bool g_on_value = false;  // sasrt-nx (2026-11-12, batch C10)
std::atomic<bool> g_on_latched{false};
bool LatchOn() {
  static const bool on = REXCVAR_GET(sasrt_renut_diag_trace);
  g_on_value = on;
  g_on_latched.store(true, std::memory_order_release);
  return on;
}'''),
], 'batch C10')

# ---- C12
patch('sdk/src/audio/xma_decoder.cpp', [
    ('''    if (!pending_was) {
      for (uint32_t n = 0; n < kContextCount && worker_running_; n++) {
        XmaContext& context = contexts_[n];
        bool worked = context.Work();
        if (worked) {
          context.SignalWorkDone();
          PROFILE_XMA_FRAME_DECODED();
        }
        did_work = did_work || worked;
      }
    }''', '''    // sasrt-nx (2026-11-12, batch C12): the allocated contexts only, by the context bitmap (a cleared bit is a taken
    // context: bit 63 - i of word w is context 64 w + i), in the same ascending order. A context is taken in the bitmap
    // before it is marked allocated and given back after it is released, so every one Work() would act on is visited;
    // the others returned at once (no side effect).
    if (!pending_was) {
      std::vector<uint64_t>& words = context_bitmap_.data();
      for (size_t w = 0; w < words.size() && worker_running_; w++) {
        uint64_t taken = ~__atomic_load_n(&words[w], __ATOMIC_RELAXED);
        while (taken && worker_running_) {
          const uint32_t i = uint32_t(__builtin_clzll(taken));
          taken &= ~(uint64_t(1) << (63 - i));
          const uint32_t n = uint32_t(w * 64) + i;
          if (n >= kContextCount)
            break;
          XmaContext& context = contexts_[n];
          bool worked = context.Work();
          if (worked) {
            context.SignalWorkDone();
            PROFILE_XMA_FRAME_DECODED();
          }
          did_work = did_work || worked;
        }
      }
    }'''),
], 'batch C12')
print('batchC2: done')
