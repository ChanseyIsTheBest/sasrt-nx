// Sonic & All-Stars Racing Transformed: the game's Direct3D GPU wait sleeps instead of spinning (CPU enhancement
// sasrt_cpu_gpu_wait_sleep). sa2-nx's sa2_gpu_wait.cpp: this game links the same Direct3D (XDK 2.0.21119 vs SA2's
// 21076), and its wait iteration is the same code with other global addresses.
//
// WHAT THE GAME DOES
//   Direct3D's waits for the GPU (11 call sites, all through the .xidata thunk 0x8247A520) loop on one iteration
//   function, sub_82CD3668 (SA2: sub_8254F400). r3 = the wait record: [0] device, [8] the read pointer seen last time,
//   [12] the tick of its last change, [20] the time base at the start. One iteration is 32 db16cyc delays, then:
//   GPU already declared hung (bit 0x02 of [device+11069]) -> 0 (stop); the read pointer ([[device+11024]]) moved ->
//   remember it and its tick; no movement for longer than the game's limit -> the hang handler (sub_8247A760); else 1
//   (keep waiting). The caller re-checks its condition after each iteration. Same device offsets as SA2's.
//
// WHAT THIS DOES
//   Before an iteration in which nothing can have changed - the same wait record as the previous iteration on this
//   thread, the read pointer still the one the record saw, and no ring progress since the previous iteration returned
//   (the progress counter of me_ring_wait.cpp, bumped by the native renderer's ring thread after each ring segment,
//   each fence write and each interrupt) - it sleeps until the ring thread reports progress, at most
//   sasrt_gpu_wait_max_us. Then the original iteration runs as always. The counter is read AFTER the original returns,
//   i.e. before the caller re-checks its condition, so a change the caller could have missed always shows as progress
//   and the next iteration does not sleep. With the emulated GPU (no ring-thread progress) it never sleeps.
//
// WHY IT IS EXACT: the game reads the same memory and takes the same decisions; it only reaches them later, by at most
//   one wake-up latency (or max_us when the wake-up comes from something the ring does not report).
// RISK: a wait whose condition changes without ring progress or an interrupt gains up to max_us per iteration.
// KEY: sasrt_cpu_gpu_wait_sleep (with sasrt_cpu_enhancements); sasrt_gpu_wait_max_us.
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstring>

#include <rex/cvar.h>
#include <rex/hook.h>
#include <rex/platform.h>
#include <rex/ppc.h>

#include "me/me_native_system.h"
#include "sasrt_enhancements.h"
#include "renut_engine/sasrt_renut_yield.h"

SASRT_ENHANCEMENT(g_gpu_wait_sleep, sasrt_cpu_gpu_wait_sleep, ::sasrt::enhancements::Group::kCpu, true,
                  "The game's Direct3D GPU wait (sub_82CD3668) sleeps until the native renderer's ring thread makes "
                  "progress instead of spinning");
REXCVAR_DEFINE_INT32(sasrt_gpu_wait_max_us, 1000, "SASRT",
                     "sasrt_cpu_gpu_wait_sleep: longest sleep per iteration of the game's GPU wait, in microseconds")
    .range(50, 100000)
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

namespace {

constexpr uint32_t kIteration = 0x82CD3668;
constexpr uint32_t kIterationBytes = 224;  // 0x82CD3668-0x82CD3747 (its last instruction: b 0x82c8d7fc)
constexpr uint64_t kIterationHash = 0xCA1B288F7C4BEF0Dull;  // FNV-1a 64 of those bytes in default.xex 0.0.0.2

constexpr uint32_t kDeviceReadPointerWord = 11024;  // address of the word the GPU writes the read pointer back to
constexpr uint32_t kDeviceState = 11069;            // bit 0x02: GPU declared hung

inline uint32_t PhysOff(uint32_t a) {
#if REX_PLATFORM_WIN32 || (REX_PLATFORM_MAC && REX_ARCH_ARM64)
  return a >= 0xE0000000u ? 0x1000u : 0u;
#else
  (void)a;
  return 0u;
#endif
}
inline uint32_t Ld32(const uint8_t* base, uint32_t a) {
  uint32_t v;
  std::memcpy(&v, base + a + PhysOff(a), 4);
  return __builtin_bswap32(v);
}
inline uint8_t Ld8(const uint8_t* base, uint32_t a) { return base[a + PhysOff(a)]; }

// The previous iteration on this thread: its record, the record's start time base, and the progress counter when it
// returned.
thread_local uint32_t t_record = 0;
thread_local uint32_t t_record_start = 0;
thread_local uint32_t t_progress = 0;

std::atomic<int> g_state{0};  // 0 unknown, 1 on, -1 off (key off, emulated GPU, or code check failed); first call

}  // namespace

REX_EXTERN(__imp__sub_82CD3668);
REX_HOOK_RAW(sub_82CD3668) {
  SASRT_RENUT_YIELD_SHARED(sub_82CD3668)  // sasrt_renderer = "renut" (renut_engine/sasrt_renut_yield.h)
  int state = g_state.load(std::memory_order_relaxed);
  if (state == 0) {
    // Only the native renderer's ring thread reports progress; with the emulated GPU the counter never moves.
    const bool native = rex::cvar::GetFlagByName("masseffect_renderer_native") == "true";
    state = (g_gpu_wait_sleep.active && native &&
             sasrt::enhancements::GuestCodeMatches(base, kIteration, kIterationBytes, kIterationHash,
                                                   "sasrt_cpu_gpu_wait_sleep"))
                ? 1
                : -1;
    g_state.store(state, std::memory_order_relaxed);
  }
  if (state < 0) {
    __imp__sub_82CD3668(ctx, base);
    return;
  }
  const uint32_t record = ctx.r3.u32;
  const uint32_t start = Ld32(base, record + 20);
  if (record == t_record && start == t_record_start) {
    const uint32_t device = Ld32(base, record);
    if (device && !(Ld8(base, device + kDeviceState) & 0x02)) {
      const uint32_t word = Ld32(base, device + kDeviceReadPointerWord);
      if (word && Ld32(base, word) == Ld32(base, record + 8) && me::native::RingProgress() == t_progress) {
        static const uint32_t max_us = uint32_t(REXCVAR_GET(sasrt_gpu_wait_max_us));
        const auto t0 = std::chrono::steady_clock::now();
        me::native::WaitRingProgress(t_progress, max_us);
        g_gpu_wait_sleep.Use();
        g_gpu_wait_sleep.Add(uint64_t(std::chrono::duration_cast<std::chrono::microseconds>(
                                          std::chrono::steady_clock::now() - t0)
                                          .count()));
      }
    }
  }
  __imp__sub_82CD3668(ctx, base);
  t_record = record;
  t_record_start = start;
  t_progress = me::native::RingProgress();
}

namespace {
const bool g_unit = [] {
  g_gpu_wait_sleep.amount_unit = "us asleep";
  return true;
}();
}  // namespace
