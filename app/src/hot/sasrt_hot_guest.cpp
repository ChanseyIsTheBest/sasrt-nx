// Sonic & All-Stars Racing Transformed - native replacements of hot guest functions (CPU enhancements
// sasrt_cpu_native_sub_*, with the batch master sasrt_cpu_natives; sa2-nx's sa2_hot_guest.cpp, from masseffect-nx).
//
// Every replacement is a localized copy of a recompiled function (tools/localize_native.py, from the list
// app/src/hot/localized.txt; post_codegen.py regenerates them into app/generated/hot/ after every codegen, so each
// matches the codegen flavour it is built with). The list came from the PC profile of the game's threads (busy
// samples, sasrt_pc_profile_s; ranked with their AArch64 cost by tools/arm_hot_functions.py). See sasrt_hot_guest.h
// for the guard. A hook also stays off when the loaded game code is not byte for byte the code it was made from.
// WHY EXACT: a localized copy runs the recompiled function's own operations (sasrt_hot_common.h). RISK: a difference
// on inputs no check saw (unguarded copies are checked end to end only). KEY: each sasrt_cpu_native_sub_* and
// sasrt_cpu_natives (both under sasrt_cpu_enhancements).

// The generated code's macros and helpers (the localized copies are made of generated code) ...
#include "../../generated/default/sasrt_pch.h"

// sasrt-nx (2026-10-21, as sa2-nx and banjo-nx): whether the generated code marks the store cards (tools/store_cards.py
// ran and REX_STORE_CARDS_OFF is not set): Renut proves its cached copies by them only then (banjo_renut_store_cards).
#if defined(REX_CARD) && !defined(REX_STORE_CARDS_OFF)
extern "C" const bool g_banjo_store_cards = true;
#else
extern "C" const bool g_banjo_store_cards = false;
#endif

#include <mutex>

// ... with plain guest memory: the recompiled code's accesses are volatile, which keeps the compiler from pairing and
// scheduling them; a replacement does not need that (a racing write from another thread is a race either way), with
// a compiler barrier at every loop header of the copies against hoisted polls (REX_LOOP_BARRIER). The displacement
// forms go through the plain ones (the generated pch's Windows form; it differs only for an access crossing 2^32,
// a guest fault anyway).
#undef REX_LOAD_U8
#undef REX_LOAD_U16
#undef REX_LOAD_U32
#undef REX_LOAD_U64
#undef REX_STORE_U8
#undef REX_STORE_U16
#undef REX_STORE_U32
#undef REX_STORE_U64
#undef REX_LOAD_D_U8
#undef REX_LOAD_D_U16
#undef REX_LOAD_D_U32
#undef REX_LOAD_D_U64
#undef REX_STORE_D_U8
#undef REX_STORE_D_U16
#undef REX_STORE_D_U32
#undef REX_STORE_D_U64
#define REX_LOAD_U8(x) (*(u8*)(base + (u32)(x) + REX_PHYS_HOST_OFFSET(x)))
#define REX_LOAD_U16(x) __builtin_bswap16(*(u16*)(base + (u32)(x) + REX_PHYS_HOST_OFFSET(x)))
#define REX_LOAD_U32(x) __builtin_bswap32(*(u32*)(base + (u32)(x) + REX_PHYS_HOST_OFFSET(x)))
#define REX_LOAD_U64(x) __builtin_bswap64(*(u64*)(base + (u32)(x) + REX_PHYS_HOST_OFFSET(x)))
#define REX_STORE_U8(x, y) (*(u8*)(base + (u32)(x) + REX_PHYS_HOST_OFFSET(x)) = (y))
#define REX_STORE_U16(x, y) (*(u16*)(base + (u32)(x) + REX_PHYS_HOST_OFFSET(x)) = __builtin_bswap16(y))
#define REX_STORE_U32(x, y) (*(u32*)(base + (u32)(x) + REX_PHYS_HOST_OFFSET(x)) = __builtin_bswap32(y))
#define REX_STORE_U64(x, y) (*(u64*)(base + (u32)(x) + REX_PHYS_HOST_OFFSET(x)) = __builtin_bswap64(y))
#define REX_LOAD_D_U8(r, d) REX_LOAD_U8((u32)(r) + (d))
#define REX_LOAD_D_U16(r, d) REX_LOAD_U16((u32)(r) + (d))
#define REX_LOAD_D_U32(r, d) REX_LOAD_U32((u32)(r) + (d))
#define REX_LOAD_D_U64(r, d) REX_LOAD_U64((u32)(r) + (d))
#define REX_STORE_D_U8(r, d, y) REX_STORE_U8((u32)(r) + (d), y)
#define REX_STORE_D_U16(r, d, y) REX_STORE_U16((u32)(r) + (d), y)
#define REX_STORE_D_U32(r, d, y) REX_STORE_U32((u32)(r) + (d), y)
#define REX_STORE_D_U64(r, d, y) REX_STORE_U64((u32)(r) + (d), y)
#ifndef REX_LOOP_BARRIER
#define REX_LOOP_BARRIER() __asm__ __volatile__("" ::: "memory")
#endif

#include "hot/sasrt_hot_guest.h"

#include <algorithm>
#include <string>
#include <vector>

#include <fmt/format.h>

#if defined(_WIN32)  // sasrt_diag_ps_constant_watch_writes (2026-10-30)
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <tlhelp32.h>
#include <dbghelp.h>
#include <atomic>
#include <thread>
#endif

#include <rex/cvar.h>
#include <rex/logging.h>

#include "me/me_verify.h"

REXCVAR_DECLARE(bool, sasrt_cpu_verify);
REXCVAR_DEFINE_BOOL(sasrt_cpu_natives, true, "SASRT",
                    "Native replacements of hot guest functions (localized copies, app/src/hot/localized.txt) as one "
                    "batch: false turns them all off (the A/B config sasrt_natives_off.toml); each also has its own key "
                    "sasrt_cpu_native_sub_<address>")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_INT32(sasrt_hot_guard_calls, 256, "SASRT",
                     "Native replacements: the first N calls of each thread of a guarded one are checked against the "
                     "recompiled original")
    .range(0, 1000000000)
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_INT32(sasrt_hot_guard_period, 4096, "SASRT",
                     "Native replacements: after the first N calls every P-th call of a guarded one is checked (rounded "
                     "to a power of two)")
    .range(1, 1 << 24)
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

// sasrt-nx (2026-11-11): the hand-written natives' range check repeats a difference before it counts, as the bulk
// copies' guard does (cpu/banjo_hot_guest.cpp, three passes). Run bt1 (2026-11-10): the CRT memcpy native
// (sub_82C8EEF0) switched itself off five seconds into the race on one byte of a 60-byte copy from the game image
// (another thread writing the source between the native's run and the original's), and the generated memcpy then
// took 108 samples of the race (the game thread's and the sound thread's top plain function).
REXCVAR_DEFINE_BOOL(sasrt_hot_guard_repeat, true, "SASRT",
                    "Native replacements: a range check's difference is made again from the same inputs (up to three "
                    "passes); one that does not repeat came from another thread and is counted, not acted on")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

// sasrt-nx (2026-10-30, diagnostics): who writes a pixel shader constant register (the race start's dark Ristar: his
// glow scales by c146.x, gITMGF of the game's cbViewProjection, 0.05 on every renderer).
REXCVAR_DEFINE_INT32(sasrt_diag_ps_constant_watch, -1, "SASRT",
                     "Diagnostics: a pixel shader constant register (0-255) whose uploads through the native "
                     "Direct3D constant writer (sub_82CC2368) log their value and guest caller, the first 8 uploads of "
                     "each caller; -1 off")
    .range(-1, 255)
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_diag_ps_constant_watch_writes, false, "SASRT",
                    "Diagnostics, the PC only (with sasrt_diag_ps_constant_watch): x86 data breakpoints on the watched "
                    "register's source buffers; each instruction that writes its first float is logged with its stack "
                    "(recompiled function names and generated source lines)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
namespace sasrt::hot::d3d_constants {
int32_t g_watch_ps_register = -1;
}  // namespace sasrt::hot::d3d_constants

namespace sasrt::hot {

void InitHook(Hook& h, uint8_t* base) {
  d3d_constants::g_watch_ps_register = REXCVAR_GET(sasrt_diag_ps_constant_watch);  // sasrt-nx (2026-10-30)
  // May run on several threads at once for the first call: every writer stores the same values.
  bool on = h.key->active && REXCVAR_GET(sasrt_cpu_natives);
  if (on && !::sasrt::enhancements::GuestCodeMatches(base, h.code_address, h.code_bytes, h.code_hash, h.key->key))
    on = false;
  const bool verify = REXCVAR_GET(sasrt_cpu_verify);
  const uint32_t guard_calls = verify ? 0xFFFFFFFFu : uint32_t(std::max(0, REXCVAR_GET(sasrt_hot_guard_calls)));
  const uint32_t period = uint32_t(std::max(1, REXCVAR_GET(sasrt_hot_guard_period)));
  uint32_t p2 = 1;
  while (p2 < period) p2 <<= 1;
  h.guard_calls = guard_calls;
  h.period_mask = p2 - 1;
  // sasrt_cpu_hook_counter_ctx: a slot of the per-thread counters. Two threads here at once each take a number and
  // one of them stays unused.
  if (h.slot.load(std::memory_order_relaxed) == 0xFF) {
    static std::atomic<uint32_t> next_slot{0};
    const uint32_t s = next_slot.fetch_add(1, std::memory_order_relaxed);
    uint8_t none = 0xFF;
    h.slot.compare_exchange_strong(none, s < kCtxSlots ? uint8_t(s) : uint8_t(0xFE), std::memory_order_relaxed);
  }
  if (on && h.state.load(std::memory_order_relaxed) == kUninit) {
    if (!h.shadow && !h.writes) {  // sasrt-nx (2026-10-21): the hand-written natives' range guard is a guard too
      REXLOG_INFO("[hot] {} ({}): native replacement ON (unguarded: it calls other functions)", h.name, h.key->key);
    } else if (verify) {
      REXLOG_INFO("[hot] {} ({}): native replacement ON, verify mode (every call checked)", h.name, h.key->key);
    } else {
      REXLOG_INFO("[hot] {} ({}): native replacement ON (guard: first {} calls, then 1 in {})", h.name, h.key->key,
                  guard_calls, p2);
    }
  }
  h.state.store(on ? kOn : kOff, std::memory_order_release);
}

namespace {

// The host FPU mode bits the guest state stands for (rounding and flush mode, FPSCRRegister::GuestMask). Not the
// sticky exception flags of x86's MXCSR (ARM's FPCR has none): a copy that skips one operation on a denormal leaves
// the denormal flag clear where the original raises it, which nothing in the guest can see.
inline uint32_t HwMode(uint32_t csr) { return csr & uint32_t(decltype(PPCContext::fpscr)::GuestMask); }

const PPCRegister* Gpr(const PPCContext& c, int n) {
  switch (n) {
#define G(i) case i: return &c.r##i;
    G(0) G(1) G(2) G(3) G(4) G(5) G(6) G(7) G(8) G(9) G(10) G(11) G(12) G(13) G(14) G(15) G(16) G(17) G(18) G(19)
    G(20) G(21) G(22) G(23) G(24) G(25) G(26) G(27) G(28) G(29) G(30) G(31)
#undef G
  }
  return nullptr;
}
const PPCRegister* Fpr(const PPCContext& c, int n) { return &c.f0 + n; }    // f0..f31 are consecutive
const PPCVRegister* Vr(const PPCContext& c, int n) { return &c.v0 + n; }    // v0..v127 are consecutive
const PPCCRRegister* Cr(const PPCContext& c, int n) { return &c.cr0 + n; }  // cr0..cr7 are consecutive

// First difference between the native run (a) and the original (b), or an empty string. `all`: every register (a
// localized leaf copy writes back every register it uses with the value the original leaves); otherwise r1, r3, f1, v1
// and the non-volatile registers (a hand-written CRT native writes only what the routine's callers may read).
std::string CompareRegs(const PPCContext& a, const PPCContext& b, bool all) {
  for (int i = 0; i < 32; ++i)
    if ((all || i == 1 || i == 3 || i >= 13) && Gpr(a, i)->u64 != Gpr(b, i)->u64)
      return fmt::format("r{} native={:#018x} original={:#018x}", i, Gpr(a, i)->u64, Gpr(b, i)->u64);
  for (int i = 0; i < 32; ++i)
    if ((all || i == 1 || i >= 14) && Fpr(a, i)->u64 != Fpr(b, i)->u64)
      return fmt::format("f{} native={:#018x} original={:#018x}", i, Fpr(a, i)->u64, Fpr(b, i)->u64);
  for (int i = 0; i < 128; ++i)
    if ((all || i == 1 || (i >= 14 && i < 32) || i >= 64) && std::memcmp(Vr(a, i)->u8, Vr(b, i)->u8, 16) != 0) {
      const auto* x = Vr(a, i)->u32;
      const auto* y = Vr(b, i)->u32;
      return fmt::format("v{} native={:08x}{:08x}{:08x}{:08x} original={:08x}{:08x}{:08x}{:08x}", i, x[0], x[1], x[2],
                         x[3], y[0], y[1], y[2], y[3]);
    }
  if (all) {
    for (int i = 0; i < 8; ++i)
      if (Cr(a, i)->raw() != Cr(b, i)->raw())
        return fmt::format("cr{} native={:x} original={:x}", i, Cr(a, i)->raw(), Cr(b, i)->raw());
    if (a.ctr.u64 != b.ctr.u64) return fmt::format("ctr native={:#x} original={:#x}", a.ctr.u64, b.ctr.u64);
    if (a.xer.so != b.xer.so || a.xer.ov != b.xer.ov || a.xer.ca != b.xer.ca) return "xer";
    if (a.reserved.u64 != b.reserved.u64) return "reserved";
    if (a.lr != b.lr) return fmt::format("lr native={:#x} original={:#x}", a.lr, b.lr);
  }
  if (a.fpscr.csr != b.fpscr.csr) return fmt::format("fpscr.csr native={:#x} original={:#x}", a.fpscr.csr, b.fpscr.csr);
  return {};
}

void Report(Hook& h, const PPCContext& in, const std::string& diff) {
  const uint64_t n = h.checks.fetch_add(1, std::memory_order_relaxed) + 1;
  if (!diff.empty()) {
    h.failed.store(true, std::memory_order_relaxed);
    ::me::native::VerifyDifference();
    REXLOG_ERROR("[hot] DIFFERENCE {} ({}): {}; inputs r3={:#x} r4={:#x} r5={:#x} r6={:#x} r7={:#x} f1={:#x} f2={:#x}; "
                 "native replacement switched off for the rest of the run",
                 h.name, h.key->key, diff, in.r3.u64, in.r4.u64, in.r5.u64, in.r6.u64, in.r7.u64, in.f1.u64,
                 in.f2.u64);
  } else if (n == 256 || n == 4096 || n == (1u << 20) || n == (1u << 24)) {
    REXLOG_INFO("[hot] {} ({}): {} checks, no difference ({} differences did not repeat)", h.name, h.key->key, n,
                h.not_repeated.load(std::memory_order_relaxed));
  }
}

// sasrt-nx (2026-11-11, round A's audit, finding 4): a range check running inside another's original (the generated
// memmove calls the hooked memcpy) would reuse the thread's buffers below: it runs unchecked instead.
thread_local int g_range_check_depth = 0;

// Hand-written natives: written ranges snapshotted, native, its result kept, rollback, original, comparison.
void CheckRanges(Hook& h, PPCContext& ctx, uint8_t* base) {
  if (g_range_check_depth) {
    if (!h.native(ctx, base)) h.orig(ctx, base);
    return;
  }
  Writes w;
  h.writes(ctx, base, w);
  if (w.overflow) {  // cannot verify: the native version is not trusted for this call
    h.orig(ctx, base);
    return;
  }
  size_t total = 0;
  for (int i = 0; i < w.n; ++i) total += w.r[i].len;
  // sasrt-nx (2026-10-21): a call writing over 1 MB is checked 4 times outside verify mode, then runs unchecked (each
  // check copies its bytes three times and runs the original too; verify mode, the PC's proof, checks every call).
  if (total > (1u << 20)) {
    static const bool verify = REXCVAR_GET(sasrt_cpu_verify);
    if (!verify && h.big_checks.fetch_add(1, std::memory_order_relaxed) >= 4) {
      if (!h.native(ctx, base)) h.orig(ctx, base);
      return;
    }
  }
  struct Depth {
    Depth() { ++g_range_check_depth; }
    ~Depth() { --g_range_check_depth; }
  } depth;
  static thread_local std::vector<uint8_t> before, native_out, orig_out;
  before.resize(total);
  native_out.resize(total);
  size_t off = 0;
  for (int i = 0; i < w.n; ++i) {
    std::memcpy(before.data() + off, Raw(base, w.r[i].addr), w.r[i].len);
    off += w.r[i].len;
  }
  const uint32_t hw_before = ctx.fpscr.getcsr();
  const uint32_t csr_before = ctx.fpscr.csr;
  const PPCContext in = ctx;
  PPCContext nat = ctx;
  if (!h.native(nat, base)) {  // declined: the original runs, nothing to compare
    h.orig(ctx, base);
    return;
  }
  const uint32_t hw_native = nat.fpscr.getcsr();
  off = 0;
  for (int i = 0; i < w.n; ++i) {
    std::memcpy(native_out.data() + off, Raw(base, w.r[i].addr), w.r[i].len);
    std::memcpy(Raw(base, w.r[i].addr), before.data() + off, w.r[i].len);  // roll back
    off += w.r[i].len;
  }
  ctx.fpscr.setcsr(hw_before);
  ctx.fpscr.csr = csr_before;
  h.orig(ctx, base);  // the call for real
  // (Round A's audit, finding 3: what the original left, to see whether another thread wrote the ranges since.)
  auto keep_orig = [&] {
    orig_out.resize(total);
    size_t o = 0;
    for (int i = 0; i < w.n; ++i) {
      std::memcpy(orig_out.data() + o, Raw(base, w.r[i].addr), w.r[i].len);
      o += w.r[i].len;
    }
  };
  keep_orig();
  auto compare = [&](const PPCContext& n, uint32_t hw_n) {
    std::string d = CompareRegs(n, ctx, false);
    if (d.empty() && HwMode(hw_n) != HwMode(ctx.fpscr.getcsr()))
      d = fmt::format("hardware FPU mode native={:#x} original={:#x}", hw_n, ctx.fpscr.getcsr());
    size_t o = 0;
    for (int i = 0; i < w.n && d.empty(); ++i) {
      const uint8_t* now = Raw(base, w.r[i].addr);
      for (uint32_t k = 0; k < w.r[i].len; ++k) {
        if (now[k] != native_out[o + k]) {
          d = fmt::format("memory {:#010x} (+{} of range {:#010x}+{}) native={:#04x} original={:#04x}",
                          w.r[i].addr + k, k, w.r[i].addr, w.r[i].len, native_out[o + k], now[k]);
          break;
        }
      }
      o += w.r[i].len;
    }
    return d;
  };
  std::string diff = compare(nat, hw_native);
  // sasrt-nx (2026-11-11, sasrt_hot_guard_repeat): a difference must repeat. The written ranges go back to what they
  // held before the call, the registers to the inputs, and the native and the original run again (the original for
  // real again: what the ranges hold at the end is its result, as after a single pass). The other threads see the
  // ranges change back and forth during the passes, as during the first one.
  static const bool repeat = REXCVAR_GET(sasrt_hot_guard_repeat);
  for (int attempt = 1; repeat && !diff.empty() && attempt < 3; ++attempt) {
    // Another thread wrote the ranges after the original ran: a repeat would roll its write back. The ranges stay as
    // they are, and the difference counts as not repeated (it came from that thread).
    bool moved = false;
    off = 0;
    for (int i = 0; i < w.n && !moved; ++i) {
      moved = std::memcmp(Raw(base, w.r[i].addr), orig_out.data() + off, w.r[i].len) != 0;
      off += w.r[i].len;
    }
    if (moved) {
      const uint32_t n = h.not_repeated.fetch_add(1, std::memory_order_relaxed) + 1;
      if (n <= 4 || n == 64 || n == 4096)
        REXLOG_WARN("[hot] {} ({}): another thread wrote the ranges after the original ran ({} not repeated so far; "
                    "the native stays on): {}", h.name, h.key->key, n, diff);
      diff.clear();
      break;
    }
    off = 0;
    for (int i = 0; i < w.n; ++i) {
      std::memcpy(Raw(base, w.r[i].addr), before.data() + off, w.r[i].len);
      off += w.r[i].len;
    }
    nat = in;
    nat.fpscr.setcsr(hw_before);
    nat.fpscr.csr = csr_before;
    if (!h.native(nat, base)) {  // declined this time: the original runs again for real, nothing compared
      ctx = in;
      ctx.fpscr.setcsr(hw_before);
      ctx.fpscr.csr = csr_before;
      h.orig(ctx, base);
      h.not_repeated.fetch_add(1, std::memory_order_relaxed);
      diff.clear();
      break;
    }
    const uint32_t hw_again = nat.fpscr.getcsr();
    off = 0;
    for (int i = 0; i < w.n; ++i) {
      std::memcpy(native_out.data() + off, Raw(base, w.r[i].addr), w.r[i].len);
      std::memcpy(Raw(base, w.r[i].addr), before.data() + off, w.r[i].len);  // roll back
      off += w.r[i].len;
    }
    ctx = in;
    ctx.fpscr.setcsr(hw_before);
    ctx.fpscr.csr = csr_before;
    h.orig(ctx, base);  // the call for real, again
    keep_orig();
    std::string again = compare(nat, hw_again);
    if (again.empty()) {
      const uint32_t n = h.not_repeated.fetch_add(1, std::memory_order_relaxed) + 1;
      if (n <= 4 || n == 64 || n == 4096)
        REXLOG_WARN("[hot] {} ({}): a difference did not repeat (pass {}; {} so far: another thread changed the "
                    "inputs between the runs; the native stays on): {}", h.name, h.key->key, attempt + 1, n, diff);
      diff.clear();
      break;
    }
    diff = std::move(again);
  }
  Report(h, in, diff);
}

}  // namespace

// The checked calls of one localized copy run one at a time (a striped lock; every copy with a shadow run is a leaf, so
// the lock is held across no call). Without it two threads making a function's first calls together see each other's
// stores between one's shadow run and its original: on track 0.0 (2026-10-07) sub_82611908's static initialisers had
// their guard word clear in one thread's shadow run and set by another thread before that thread's original ran, so the
// two runs took different paths (r8 differed) and verify switched a correct copy off. Calls the guard does not check
// still race as the game's own code does; verify mode checks every call.
static std::mutex g_check_locks[16];

void Check(Hook& h, PPCContext& ctx, uint8_t* base) {
  if (!h.shadow) {
    CheckRanges(h, ctx, base);
    return;
  }
  // Outside verify mode a copy whose calls store more than a check keeps is no longer checked: every check would run
  // the whole call twice (sub_82E7F918 stores 3.7 MB per call) and still verify nothing.
  if (h.unverifiable.load(std::memory_order_relaxed)) {
    if (!h.native(ctx, base)) h.orig(ctx, base);
    return;
  }
  std::lock_guard<std::mutex> lock(g_check_locks[(h.code_address >> 2) & 15]);
  static thread_local ShadowMemory* shadow = new ShadowMemory();  // per thread, never freed (threads outlive this)
  ShadowMemory& m = *shadow;
  m.Reset();
  // Verify mode (the PC's proof) keeps up to 32 MB per call; the console's guard 64 KB.
  static const bool verify = REXCVAR_GET(sasrt_cpu_verify);
  m.max_pages = verify ? ShadowMemory::kMaxPages : ShadowMemory::kGuardPages;
  const uint32_t hw_before = ctx.fpscr.getcsr();
  const uint32_t csr_before = ctx.fpscr.csr;
  const PPCContext in = ctx;  // inputs for the report
  PPCContext nat = ctx;
  h.shadow(nat, base, m);
  const uint32_t hw_native = nat.fpscr.getcsr();
  ctx.fpscr.setcsr(hw_before);  // the original starts from the same FPU mode
  ctx.fpscr.csr = csr_before;
  h.orig(ctx, base);  // the call for real
  const uint32_t hw_orig = ctx.fpscr.getcsr();
  if (m.overflow) {  // too many stores to keep: not verified (the original's result stands)
    const uint64_t u = h.unverified.fetch_add(1, std::memory_order_relaxed) + 1;
    if (u == 1 || (!verify && u == 4) || u == 256 || u == 4096 || u == (1u << 20))
      REXLOG_INFO("[hot] {} ({}): {} checked calls stored more bytes than a check keeps ({} KB; the last one {}): "
                  "not verified, the original's result stands{}", h.name, h.key->key, u,
                  m.max_pages * ShadowMemory::kPageBytes / 1024, m.attempted,
                  !verify && u >= 4 ? "; no more checks of it (verify mode keeps 32 MB)" : "");
    if (!verify && u >= 4) h.unverifiable.store(true, std::memory_order_relaxed);
    return;
  }

  std::string diff = CompareRegs(nat, ctx, true);
  if (diff.empty() && HwMode(hw_native) != HwMode(hw_orig))
    diff = fmt::format("hardware FPU mode native={:#x} original={:#x}", hw_native, hw_orig);
  for (uint32_t p = 0; diff.empty() && p < m.used; ++p) {
    const ShadowMemory::Page& page = *m.pages[p];
    for (uint32_t w = 0; diff.empty() && w < ShadowMemory::kPageBytes / 64; ++w) {
      for (uint64_t bits = page.valid[w]; bits; bits &= bits - 1) {
        const uint32_t o = w * 64 + uint32_t(__builtin_ctzll(bits));
        const uint32_t a = (page.number << ShadowMemory::kPageBits) + o;
        const uint8_t now = base[uint64_t(a) + PhysOff(a)];
        if (now != page.value[o]) {
          diff = fmt::format("memory {:#010x} native={:#04x} original={:#04x} ({} bytes stored)", a, page.value[o],
                             now, m.attempted);
          break;
        }
      }
    }
  }
  Report(h, in, diff);
}

}  // namespace sasrt::hot

// Hand-written natives.
SASRT_ENHANCEMENT(g_hook_counter_shared, sasrt_cpu_hook_counter_shared, ::sasrt::enhancements::Group::kCpu, true,
                  "Native replacements: one relaxed call counter per hook shared by all threads instead of a "
                  "thread_local one (on the Switch every thread_local access is a call to __aarch64_read_tp, on every "
                  "hooked call; sa2-nx's)");
SASRT_ENHANCEMENT(g_hook_counter_ctx, sasrt_cpu_hook_counter_ctx, ::sasrt::enhancements::Group::kCpu, true,
                  "Native replacements: each hook's call counter lives in the calling thread's own context "
                  "(PPCContext::host_counters) instead of one counter shared by all threads: no store into a cache "
                  "line every calling thread pulls to its core, and still no thread_local (~700,000 hooked calls a "
                  "second from several threads)");
namespace sasrt::hot {
// A shadow run's 16-byte vector loads and stores (tools/localize_native.py rewrites the recompiled code's
// simde_mm_load_si128 / simde_mm_store_si128 through REX_RAW_ADDR into these in Shadow() only): the 16 bytes in guest
// memory order, each through the shadow's kept stores, as REX_RAW_ADDR would address them.
inline simde__m128i ShLoadV(const ShadowMemory& m, const uint8_t* base, uint32_t a) {
  alignas(16) uint8_t b[16];
  for (uint32_t i = 0; i < 16; ++i) b[i] = ShLoad8(m, base, a + i);
  return simde_mm_load_si128(reinterpret_cast<const simde__m128i*>(b));
}
inline void ShStoreV(ShadowMemory& m, uint32_t a, simde__m128i v) {
  alignas(16) uint8_t b[16];
  simde_mm_store_si128(reinterpret_cast<simde__m128i*>(b), v);
  for (uint32_t i = 0; i < 16; ++i) m.Store8(a + i, b[i]);
}
}  // namespace sasrt::hot

#include "hot/n_82C8EEF0.h"
// The XDK CRT memcpy, byte for byte sa2-nx's (same size and hash): 0.5 % of the busy game threads on the PC profile.
SASRT_HOT_HOOK_NATIVE(82C8EEF0, sasrt_cpu_native_memcpy, "Native CRT memcpy (sub_82C8EEF0): host memcpy/memmove", 1160,
                      0xEE0EAEB1E0584297ull)

// Library natives found by signature (2026-10-14, idea 4 of sa2-nx's list; sa2-nx's natives of the same routines,
// tools/crt_signatures.py of sa2-nx matched each uniquely in this image). Each is guarded like memcpy: its written
// ranges are compared with the original's (every call in verify mode).
#include "hot/n_82C8D8D0.h"
#include "hot/n_82C8E720.h"
#include "hot/n_d3d_constants.h"
SASRT_HOT_HOOK_NATIVE(82C8D8D0, sasrt_cpu_native_memset, "Native CRT memset (sub_82C8D8D0): host memset", 160,
                      0x54D201DC8A21DABAull)
SASRT_HOT_HOOK_NATIVE(82C8E720, sasrt_cpu_native_memmove, "Native CRT memmove (sub_82C8E720): host memmove", 188,
                      0xC8BB412E78254ABCull)
namespace sasrt::hot::d3d_constants {
#if defined(_WIN32)
// The PC only (sasrt_diag_ps_constant_watch_writes): x86 data breakpoints on the watched register's first float in its
// source buffers (the game alternates two). Each distinct writing instruction is kept with a few return addresses of
// its stack and logged, resolved by the PDB, at the next upload.
struct WriteHit {
  std::atomic<uint64_t> rip{0};
  uint64_t frames[10]{};
  std::atomic<bool> ready{false};
  bool logged = false;
};
WriteHit g_write_hits[16];
std::atomic<uint64_t> g_write_hit_count{0};

LONG CALLBACK WriteWatchHandler(EXCEPTION_POINTERS* e) {
  if (e->ExceptionRecord->ExceptionCode != EXCEPTION_SINGLE_STEP || !(e->ContextRecord->Dr6 & 3))
    return EXCEPTION_CONTINUE_SEARCH;
  g_write_hit_count.fetch_add(1, std::memory_order_relaxed);
  const uint64_t rip = e->ContextRecord->Rip;  // a data breakpoint traps after the write: the next instruction
  for (WriteHit& h : g_write_hits) {
    uint64_t none = 0;
    if (h.rip.load(std::memory_order_relaxed) == rip)
      break;
    if (h.rip.compare_exchange_strong(none, rip)) {
      CONTEXT c = *e->ContextRecord;  // the writer's own frames: walked from its context
      STACKFRAME64 f{};
      f.AddrPC.Offset = c.Rip;
      f.AddrPC.Mode = AddrModeFlat;
      f.AddrFrame.Offset = c.Rbp;
      f.AddrFrame.Mode = AddrModeFlat;
      f.AddrStack.Offset = c.Rsp;
      f.AddrStack.Mode = AddrModeFlat;
      for (int k = 0; k < 10 && StackWalk64(IMAGE_FILE_MACHINE_AMD64, GetCurrentProcess(), GetCurrentThread(), &f, &c,
                                            nullptr, SymFunctionTableAccess64, SymGetModuleBase64, nullptr);
           ++k)
        h.frames[k] = f.AddrPC.Offset;
      h.ready.store(true, std::memory_order_release);
      break;
    }
  }
  e->ContextRecord->Dr6 = 0;
  return EXCEPTION_CONTINUE_EXECUTION;
}

void ArmWriteWatch(uintptr_t a0, uintptr_t a1) {
  SymSetOptions(SYMOPT_UNDNAME | SYMOPT_DEFERRED_LOADS | SYMOPT_FAIL_CRITICAL_ERRORS | SYMOPT_LOAD_LINES);
  SymInitialize(GetCurrentProcess(), nullptr, TRUE);  // a second initialisation (the profiler's) fails harmlessly
  AddVectoredExceptionHandler(1, WriteWatchHandler);
  std::thread([a0, a1] {
    const DWORD self = GetCurrentThreadId(), pid = GetCurrentProcessId();
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
    THREADENTRY32 te{};
    te.dwSize = sizeof(te);
    int armed = 0;
    for (BOOL ok = Thread32First(snap, &te); ok; ok = Thread32Next(snap, &te)) {
      if (te.th32OwnerProcessID != pid || te.th32ThreadID == self)
        continue;
      HANDLE t = OpenThread(THREAD_GET_CONTEXT | THREAD_SET_CONTEXT | THREAD_SUSPEND_RESUME, FALSE, te.th32ThreadID);
      if (!t)
        continue;
      if (SuspendThread(t) != DWORD(-1)) {
        CONTEXT c{};
        c.ContextFlags = CONTEXT_DEBUG_REGISTERS;
        if (GetThreadContext(t, &c)) {
          c.Dr0 = a0;
          c.Dr1 = a1;
          // L0 and L1 on; RW0 = RW1 = 01 (data writes), LEN0 = LEN1 = 11 (4 bytes).
          c.Dr7 = (1ull << 0) | (1ull << 2) | (1ull << 16) | (3ull << 18) | (1ull << 20) | (3ull << 22);
          armed += SetThreadContext(t, &c) ? 1 : 0;
        }
        ResumeThread(t);
      }
      CloseHandle(t);
    }
    CloseHandle(snap);
    REXLOG_INFO("[watch] write watch on host {:016X} and {:016X}: {} threads armed", a0, a1, armed);
  }).detach();
}

std::string WriteHitLabel(uint64_t pc) {
  alignas(SYMBOL_INFO) char buffer[sizeof(SYMBOL_INFO) + MAX_SYM_NAME]{};
  auto* symbol = reinterpret_cast<SYMBOL_INFO*>(buffer);
  symbol->SizeOfStruct = sizeof(SYMBOL_INFO);
  symbol->MaxNameLen = MAX_SYM_NAME;
  DWORD64 displacement = 0;
  std::string out = SymFromAddr(GetCurrentProcess(), pc, &displacement, symbol)
                        ? std::string(symbol->Name, symbol->NameLen)
                        : fmt::format("{:016X}", pc);
  IMAGEHLP_LINE64 line{};
  line.SizeOfStruct = sizeof(line);
  DWORD line_displacement = 0;
  if (SymGetLineFromAddr64(GetCurrentProcess(), pc, &line_displacement, &line) && line.FileName) {
    std::string file = line.FileName;
    const size_t slash = file.find_last_of("/\\");
    out += fmt::format(" ({}:{})", slash == std::string::npos ? file : file.substr(slash + 1), line.LineNumber);
  }
  return out;
}
#endif

void WatchPixelConstant(const PPCContext& ctx, const uint8_t* base) {
  const uint32_t reg = uint32_t(g_watch_ps_register), first = ctx.r4.u32, count = ctx.r6.u32;
  if (reg < first || reg - first >= count)
    return;
  static std::mutex mutex;
  static std::vector<std::pair<uint32_t, uint32_t>> callers;  // (lr, uploads logged)
  std::lock_guard<std::mutex> lock(mutex);
#if defined(_WIN32)
  if (REXCVAR_GET(sasrt_diag_ps_constant_watch_writes)) {
    static uint32_t sources[2] = {0, 0};
    static bool armed = false;
    const uint32_t source = ctx.r5.u32 + (reg - first) * 16;
    if (!armed) {
      if (!sources[0])
        sources[0] = source;
      else if (source != sources[0]) {
        sources[1] = source;
        armed = true;
        ArmWriteWatch(reinterpret_cast<uintptr_t>(base + sources[0]), reinterpret_cast<uintptr_t>(base + sources[1]));
      }
    }
    for (WriteHit& h : g_write_hits) {
      if (!h.ready.load(std::memory_order_acquire) || h.logged)
        continue;
      h.logged = true;
      std::string stack;
      for (uint64_t f : h.frames)
        if (f)
          stack += "\n    " + WriteHitLabel(f);
      REXLOG_INFO("[watch] c{} written at {} ({} hits so far); stack:{}", reg, WriteHitLabel(h.rip.load()),
                  g_write_hit_count.load(), stack);
    }
  }
#endif
  const uint32_t lr = uint32_t(ctx.lr);
  auto it = std::find_if(callers.begin(), callers.end(), [&](const auto& c) { return c.first == lr; });
  if (it == callers.end()) {
    if (callers.size() >= 64)
      return;
    callers.push_back({lr, 0});
    it = callers.end() - 1;
  }
  if (it->second++ >= 8)
    return;
  float v[4];
  for (uint32_t k = 0; k < 4; ++k) {
    uint32_t w;
    std::memcpy(&w, base + ctx.r5.u32 + (reg - first) * 16 + k * 4, 4);
    w = __builtin_bswap32(w);
    std::memcpy(&v[k], &w, 4);
  }
  REXLOG_INFO("[watch] c{} = ({} {} {} {}) from lr {:08X} (first c{}, {} registers, source {:08X})", reg, v[0], v[1], v[2],
              v[3], lr, first, count, ctx.r5.u32 + (reg - first) * 16);
}
}  // namespace sasrt::hot::d3d_constants
SASRT_HOT_HOOK_NATIVE(82CC2368, sasrt_cpu_native_d3d_constants_a,
                      "Native Direct3D constant upload (sub_82CC2368, constants 376+): one copy", 216,
                      0xA97944CBFFA1143Aull)
SASRT_HOT_HOOK_NATIVE(82CC2260, sasrt_cpu_native_d3d_constants_b,
                      "Native Direct3D constant upload (sub_82CC2260, constants 120+): one copy", 216,
                      0x9C7F63BCBF9EE982ull)

// The movies' colour conversion (2026-10-21; a localized copy before, batch 2): its written rows compared with the
// original's (every call in verify mode).
#include "hot/n_82E7F918_yuv.h"
SASRT_HOT_HOOK_NATIVE(82E7F918, sasrt_cpu_native_sub_82e7f918,
                      "Native movie colour conversion (sub_82E7F918, 4:2:0 to 32-bit pixels, every movie frame): "
                      "host tables and NEON (simde) instead of the localized copy",
                      2728, 0x40CFBCB5D8CED0C2ull)

// The localized copies: since 2026-11-08 in app/src/cpu/banjo_hot_guest.cpp (katamari-nx's localizer and guard, its
// lists in app/src/cpu/hot/). app/src/hot/localized.txt and app/generated/hot/hooks.inc are no longer used.

// sasrt-nx (2026-11-09, the user: "optimise the intro video so it stops dropping frames and it has stuttering audio";
// the intro at stock clocks ran 21 fps, the SlRenderer thread 30 ms a movie frame, 6.3 ms of it this conversion):
REXCVAR_DEFINE_INT32(sasrt_movie_colour_kernel, 0, "SASRT",
                     "sasrt_cpu_native_sub_82e7f918's kernel: 0 the fastest of the three on the first picture (timed, "
                     "logged), 1 the 2026-10-21 NEON path, 2 table words loaded into lanes, 3 packed tables (28 loads "
                     "a group instead of 56), 4 packed with each output line zeroed in the cache first (DC ZVA); all "
                     "give the same bytes (tools/test_yuv_kernels.cpp)")
    .range(0, 4)
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_INT32(sasrt_movie_colour_helpers, 2, "SASRT",
                     "sasrt_cpu_native_sub_82e7f918: threads that convert row pairs besides the caller (the first on "
                     "core 3 when the four-core mode has it, the second on the game's cores); the call returns once "
                     "every row is written: the same bytes. 0: the caller alone")
    .range(0, 2)
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
namespace sasrt::hot::n_82E7F918 {
int KernelKey() {
  static const int v = REXCVAR_GET(sasrt_movie_colour_kernel);
  return v;
}
int HelpersKey() {
  static const int v = REXCVAR_GET(sasrt_movie_colour_helpers);
  return v;
}
}  // namespace sasrt::hot::n_82E7F918
