// Sonic & All-Stars Racing Transformed - native replacements of hot guest functions: hook dispatch (sa2-nx's
// sa2_hot_guest.h, from masseffect-nx's me_hot_guest.h; see sasrt_hot_common.h).
//
// Three kinds of replacement:
//   - localized leaf copies (tools/localize_native.py) whose memory accesses all go through the guest-memory macros
//     check themselves through a shadow run (SASRT_HOT_HOOK_SHADOW): Shadow() runs on a copy of the registers with its
//     stores kept aside, the original (__imp__sub_X) runs for real, and every register, every byte the shadow stored
//     and the FPU mode are compared;
//   - hand-written natives (app/src/hot/n_<ADDR>.h, e.g. the CRT memcpy) check themselves through their written
//     ranges (SASRT_HOT_HOOK_NATIVE, sa2-nx's guard): the ranges are snapshotted, the native runs, its result is kept,
//     the memory is rolled back, the original runs, and memory, the return/non-volatile registers and the FPU mode
//     are compared;
//   - localized copies that call other functions run unguarded (SASRT_HOT_HOOK_UNGUARDED): a check would run the
//     callees' side effects twice. Exact by construction.
// A check runs for the first sasrt_hot_guard_calls calls of each thread (every call in verify mode) and every
// sasrt_hot_guard_period-th call afterwards. A difference logs "[hot] DIFFERENCE ..." and switches that hook off for the
// rest of the run (the original already left the correct state).
//
// Hot-path cost matters (memcpy is called from thousands of places): the Hook object is constant-initialised (no
// function-local static guard), the only per-call shared state is one byte load, and the call counter that decides
// which calls are checked is thread-local.
#pragma once

#include <atomic>
#include <cstdint>

#include <rex/hook.h>

#include "hot/sasrt_hot_common.h"
#include "sasrt_enhancements.h"

// sasrt_cpu_hook_counter_shared (defined in sasrt_hot_guest.cpp): see DispatchShared.
extern ::sasrt::enhancements::Enhancement g_hook_counter_shared;
// sasrt_cpu_hook_counter_ctx (defined in sasrt_hot_guest.cpp): see DispatchCtx.
extern ::sasrt::enhancements::Enhancement g_hook_counter_ctx;

namespace sasrt::hot {

enum : uint8_t { kUninit = 0, kOff = 1, kOn = 2 };

struct Hook {
  const char* name;
  PPCFunc* orig;
  bool (*native)(PPCContext&, uint8_t*);                       // false = declined: nothing modified, the original runs
  void (*shadow)(PPCContext&, uint8_t*, ShadowMemory&);        // localized leaf copies: the shadow guard
  void (*writes)(const PPCContext&, const uint8_t*, Writes&);  // hand-written natives: the ranges guard
  ::sasrt::enhancements::Enhancement* key;
  uint32_t code_address;  // the guest code the replacement was made from
  uint32_t code_bytes;
  uint64_t code_hash;
  // Runtime state. Until the first call initialises it the zeros are harmless: kUninit goes to the slow path, and a
  // stale guard_calls/period_mask of 0 on another core only means "check this call".
  std::atomic<uint8_t> state{kUninit};
  uint32_t guard_calls = 0;         // the first N calls of each thread are always checked ...
  uint32_t period_mask = 0;         // ... afterwards every (mask+1)-th call
  std::atomic<bool> failed{false};  // a check found a difference: the original runs from now on
  std::atomic<uint64_t> checks{0};
  std::atomic<uint64_t> unverified{0};  // checked calls that stored more than a shadow check keeps
  std::atomic<bool> unverifiable{false};  // outside verify mode: its calls overflow a check, so none is checked
  // sasrt-nx (2026-10-21): range checks of calls writing over 1 MB made outside verify mode (after 4, such calls are
  // no longer checked: sub_82E7F918 writes 3.7 MB a call, 30 times a second in a movie).
  std::atomic<uint32_t> big_checks{0};
  // sasrt-nx (2026-11-11, sasrt_hot_guard_repeat): range checks whose difference did not repeat from the same inputs.
  std::atomic<uint32_t> not_repeated{0};
  // sasrt_cpu_hook_counter_ctx: this hook's counter in every thread's context (PPCContext::host_counters), given at
  // the first call (InitHook); kNoSlot until then and when the slots ran out.
  std::atomic<uint8_t> slot{0xFF};
};
// PPCContext::host_counters: the hooks' slots; the last ones belong to the native Direct3D layer (kHostCounterTick,
// sasrt_api_internal.h).
// sasrt-nx (2026-11-08): 8, the slots 8-59 belong to the localized copies of app/src/cpu/banjo_hot_guest.cpp
// (tools/localize_native.py, SLOT_BASE); the six natives here take the first ones.
inline constexpr uint8_t kCtxSlots = 8;

// First call of a hook (any thread): key, master, code check, guard settings. Defined in sasrt_hot_guest.cpp.
void InitHook(Hook& h, uint8_t* base);

// One checked call (see above). Leaves the state exactly as the original does. Defined in sasrt_hot_guest.cpp.
void Check(Hook& h, PPCContext& ctx, uint8_t* base);

// A localized copy's Native() as a hook's native (it never declines).
template <auto F>
inline bool Always(PPCContext& ctx, uint8_t* base) {
  F(ctx, base);
  return true;
}

inline void CountUse(Hook& h, uint32_t c) {
  if ((c & 255) == 0) h.key->Use(256);
}

// One counted call: the guard's check for the first calls and every period-th one, else the replacement.
inline void DispatchCount(Hook& h, uint32_t c, PPCContext& ctx, uint8_t* base) {
  CountUse(h, c);
  if ((h.shadow || h.writes) && (c < h.guard_calls || (c & h.period_mask) == 0)) [[unlikely]] {
    Check(h, ctx, base);
    return;
  }
  if (!h.native(ctx, base)) h.orig(ctx, base);
}

inline void Dispatch(Hook& h, uint32_t& n, PPCContext& ctx, uint8_t* base) {
  // h.key->active: on at start for an engaged hook; the in-run A/B (sasrt_ab_keys) switches it off and on at a Swap,
  // and each call then runs either the copy or the original, both exact. One byte load (the key is constant-initialised).
  if (h.failed.load(std::memory_order_relaxed) || !h.key->active) [[unlikely]] {
    h.orig(ctx, base);
    return;
  }
  DispatchCount(h, n++, ctx, base);
}

// sasrt_cpu_hook_counter_shared (sa2-nx's): one counter per hook for all threads, a relaxed load and store with no
// read-modify-write (racing threads may count a call twice, which only moves which calls the guard samples). On the
// Switch a thread_local costs a call to __aarch64_read_tp on every hooked call (memcpy alone comes from thousands of
// call sites). The guard then checks the first N calls of the process instead of the first N of each thread.
inline void DispatchShared(Hook& h, std::atomic<uint32_t>& n, PPCContext& ctx, uint8_t* base) {
  if (h.failed.load(std::memory_order_relaxed) || !h.key->active) [[unlikely]] {
    h.orig(ctx, base);
    return;
  }
  const uint32_t c = n.load(std::memory_order_relaxed);
  n.store(c + 1, std::memory_order_relaxed);
  if ((c & 255) == 0) [[unlikely]] ::g_hook_counter_shared.Use(256);
  DispatchCount(h, c, ctx, base);
}

// sasrt_cpu_hook_counter_ctx: the call counter of each hook in the calling thread's own context, which the hook is
// handed anyway: the per-thread counter the guard was designed with (the first N calls of each thread checked, then
// every period-th), without the thread_local's call to __aarch64_read_tp and without the shared counter's store,
// whose cache line every thread calling the hook pulls to its core (memcpy and the hot leaf copies are called from the
// game's main, render and job threads alike, ~700,000 hooked calls a second in a race).
inline void DispatchCtx(Hook& h, uint32_t& n, PPCContext& ctx, uint8_t* base) {
  if (h.failed.load(std::memory_order_relaxed) || !h.key->active) [[unlikely]] {
    h.orig(ctx, base);
    return;
  }
  const uint32_t c = n++;
  if ((c & 255) == 0) [[unlikely]] ::g_hook_counter_ctx.Use(256);
  DispatchCount(h, c, ctx, base);
}

}  // namespace sasrt::hot

// The hook of one replacement. ADDR: hex address without 0x; KEY: its enhancement key (sasrt_cpu_native_*);
// BYTES / HASH: the guest code it was made from (tools/guest_code_hash.py; the localizer computes them itself).
#define SASRT_HOT_HOOK_IMPL(ADDR, KEY, DESC, NATIVE, SHADOW, WRITES, BYTES, HASH)                    \
  SASRT_ENHANCEMENT(g_enh_##ADDR, KEY, ::sasrt::enhancements::Group::kCpu, true, DESC);          \
  REX_EXTERN(__imp__sub_##ADDR);                                                                 \
  REX_HOOK_RAW(sub_##ADDR) {                                                                     \
    static ::sasrt::hot::Hook h{"sub_" #ADDR, &__imp__sub_##ADDR, NATIVE, SHADOW, WRITES,        \
                                &g_enh_##ADDR, 0x##ADDR##u, BYTES, HASH};                          \
    uint8_t st = h.state.load(std::memory_order_relaxed);                                        \
    if (st == ::sasrt::hot::kUninit) [[unlikely]] {                                              \
      ::sasrt::hot::InitHook(h, base);                                                           \
      st = h.state.load(std::memory_order_relaxed);                                              \
    }                                                                                            \
    if (st == ::sasrt::hot::kOn) [[likely]] {                                                    \
      const uint8_t slot = h.slot.load(std::memory_order_relaxed);                               \
      if (::g_hook_counter_ctx.active && slot < ::sasrt::hot::kCtxSlots) [[likely]] {            \
        ::sasrt::hot::DispatchCtx(h, ctx.host_counters[slot], ctx, base);                        \
      } else if (::g_hook_counter_shared.active) [[likely]] {                                    \
        static std::atomic<uint32_t> n_shared;                                                   \
        ::sasrt::hot::DispatchShared(h, n_shared, ctx, base);                                    \
      } else {                                                                                   \
        static thread_local uint32_t n_calls;                                                    \
        ::sasrt::hot::Dispatch(h, n_calls, ctx, base);                                           \
      }                                                                                          \
      return;                                                                                    \
    }                                                                                            \
    __imp__sub_##ADDR(ctx, base);                                                                \
  }

// A localized leaf copy, checked through its shadow run.
#define SASRT_HOT_HOOK_SHADOW(ADDR, KEY, DESC, BYTES, HASH)                                      \
  SASRT_HOT_HOOK_IMPL(ADDR, KEY, DESC, &::sasrt::hot::Always<&::sasrt::hot::n_##ADDR::Native>,  \
                      &::sasrt::hot::n_##ADDR::Shadow, nullptr, BYTES, HASH)
// A localized copy that calls other functions: unguarded.
#define SASRT_HOT_HOOK_UNGUARDED(ADDR, KEY, DESC, BYTES, HASH)                                   \
  SASRT_HOT_HOOK_IMPL(ADDR, KEY, DESC, &::sasrt::hot::Always<&::sasrt::hot::n_##ADDR::Native>,  \
                      nullptr, nullptr, BYTES, HASH)
// A hand-written native (app/src/hot/n_<ADDR>.h: bool Native(), void Writes()), checked through its written ranges.
#define SASRT_HOT_HOOK_NATIVE(ADDR, KEY, DESC, BYTES, HASH)                                      \
  SASRT_HOT_HOOK_IMPL(ADDR, KEY, DESC, &::sasrt::hot::n_##ADDR::Native, nullptr,                \
                      &::sasrt::hot::n_##ADDR::Writes, BYTES, HASH)
