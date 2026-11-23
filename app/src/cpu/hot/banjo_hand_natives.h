// sasrt-nx (2026-11-08) - hand-written native versions of hot guest functions (keys sasrt_hand_*).
//
// The framework is katamari-nx's app/src/cpu/hot/banjo_hand_natives.h (banjo-nx's, GPL-3.0; sa2-nx's natives before
// it): app/src/cpu/hot/hand.txt lists the functions, tools/localize_native.py puts each native IN FRONT of the
// generated copy of its function wherever that copy is used (as the function of a hook, and inlined inside every other
// copy that calls it). A native returns false to DECLINE a call it does not cover (nothing written yet): the generated
// copy of the original then runs, in the same place. Each is a template on the store policy of banjo_hot_common.h, so
// the guard's logged form records what it is about to write like any generated copy; the guard compares every hook
// whose copy contains a native against the ORIGINAL statements (docs/optimising-functions.md).
//
// Registers: a native writes back every register its processed original writes back, unless hand.txt's exact= leaves
// one out (it is then the hook's skip set: the guard does not compare it).
//
// Guest function addresses may be named in this folder only (tools/localize_native.py reads every other source's
// addresses as hooked functions).
#pragma once

#include <bit>
#include <cmath>
#include <cstdint>
#include <cstring>

#include <rex/ppc/context.h>

#if defined(__aarch64__)
#include <arm_neon.h>
#endif

#include "cpu/banjo_hot_common.h"
// blur-nx (2026-11-12; port 96): the natives' fmadds / fnmsubs take the generated code's form (tools/fma_single.py
// writes it into the pch; a file without the pch gets the same definition here).
// sasrt-nx (2026-11-13, base port 96): none of this port's natives below emulates fmadds / fmsubs / fnmadds / fnmsubs
// today (no std::fma in them); the definition is here for one that will, so it takes the generated code's form.
#ifndef REX_FMADDS
#include <rex/ppc/fma_single.h>
#define REX_FMADDS(a, b, c) rex::ppc::FmaddsSingle((a), (b), (c))
#endif
#include <rex/ppc/diet_ops.h>  // rex::ppc::SingleToDoublePure, QuietSingleBits, fctiwz

REX_EXTERN(__imp__sub_82C92CC8);  // the stack cookie check (its failure path)
REX_EXTERN(sub_82C92CC8);         // ... through its hook (the copies inside the natives below call it so)

// The natives: X(index, key, name, unit of the size histogram, description). The keys are defined in
// app/src/cpu/banjo_hot_guest.cpp; the code of each is below, in namespace banjo::hand::n_<address>.
#define SASRT_HAND_NATIVES(X)                                                                                    \
  X(0, sasrt_hand_cookie_check, "stack cookie check", "calls",                                                   \
    "Hand-written native of the C runtime's stack cookie check (sub_82C92CC8, at the end of every function with "  \
    "a stack buffer): the equal path inside each localized copy instead of a real call that stored and loaded "     \
    "all of its registers (and that kept the guard from comparing those copies); the failure path declines")       \
  X(1, sasrt_hand_water_table, "water table lookup", "calls",                                                    \
    "Hand-written native of the water thread's table lookup (sub_82872180): no host flush-mode switch (two msr "  \
    "fpcr a call), no stack round trips; declines denormal or tiny lanes and the original's other paths; checked "  \
    "by the guards of the hooks that contain it")                                                               \
  X(2, sasrt_hand_sphere_fit, "bounding sphere fit", "calls",                                                    \
    "Hand-written native of the renderer thread's bounding sphere of a point list (sub_8279A888): the flush mode "  \
    "stays on through its distance loop, the square root and add of each point computed mode-free (two msr fpcr "  \
    "a point before); otherwise the machine copy's statements; checked by the guards of its hooks") \
  X(3, sasrt_hand_resampler, "audio resampler", "calls", \
    "Hand-written native of the audio resampler (sub_82720840): the unaligned vector store of each step " \
    "as one 16-byte store instead of the stvlx / stvrx byte-piece helpers; otherwise the machine copy's " \
    "statements; checked by the guards of its hooks") \
  X(4, sasrt_hand_water_step, "water simulation step", "calls", \
    "Hand-written native of the water surface simulation step (sub_8286C230, the hottest guest function): each " \
    "misaligned vector store (four stvewx of one vector) as one 16-byte store instead of four lane extractions, " \
    "byte swaps, stores and card marks; otherwise the machine copy's statements; checked by the guards of its hooks")

namespace banjo::hand {

enum : uint32_t {
#define SASRT_HAND_ENUM(ID, KEY, NAME, UNIT, DESC) k_##KEY = ID,
  SASRT_HAND_NATIVES(SASRT_HAND_ENUM)
#undef SASRT_HAND_ENUM
#define SASRT_HAND_ONE(ID, KEY, NAME, UNIT, DESC) +1
  kNatives = 0 SASRT_HAND_NATIVES(SASRT_HAND_ONE)
#undef SASRT_HAND_ONE
};
// The natives' own keys (banjo_hot_guest.cpp), each read once: 0 not read yet, 1 off, 2 on.
extern uint8_t g_state[kNatives + 1];
extern const char* const kNames[kNatives + 1];
extern const char* const kKeys[kNatives + 1];
extern const char* const kUnits[kNatives + 1];
uint8_t Init(uint32_t which);
[[gnu::always_inline]] inline bool On(uint32_t which) {
  const uint8_t state = g_state[which];
  if (state == 2) [[likely]] return true;
  return state == 0 && Init(which) == 2;
}

namespace detail {

// 16 bytes through a register (any alignment; one NEON load or store on the A57).
struct B16 {
  uint8_t b[16];
};
[[gnu::always_inline]] inline B16 L16(const uint8_t* p) {
  B16 v;
  std::memcpy(v.b, p, 16);
  return v;
}
[[gnu::always_inline]] inline void S16(uint8_t* p, const B16& v) { std::memcpy(p, v.b, 16); }

// 1 <= n <= 64; all loads before all stores (memmove semantics for dst <= src overlap).
[[gnu::always_inline]] inline void CopySmall(uint8_t* d, const uint8_t* s, uint32_t n) {
  if (n >= 16) {
    if (n > 32) {
      const B16 a = L16(s), b = L16(s + 16), c = L16(s + n - 32), e = L16(s + n - 16);
      S16(d, a);
      S16(d + 16, b);
      S16(d + n - 32, c);
      S16(d + n - 16, e);
    } else {
      const B16 a = L16(s), e = L16(s + n - 16);
      S16(d, a);
      S16(d + n - 16, e);
    }
  } else if (n >= 8) {
    uint64_t a, e;
    std::memcpy(&a, s, 8);
    std::memcpy(&e, s + n - 8, 8);
    std::memcpy(d, &a, 8);
    std::memcpy(d + n - 8, &e, 8);
  } else if (n >= 4) {
    uint32_t a, e;
    std::memcpy(&a, s, 4);
    std::memcpy(&e, s + n - 4, 4);
    std::memcpy(d, &a, 4);
    std::memcpy(d + n - 4, &e, 4);
  } else if (n >= 2) {
    uint16_t a, e;
    std::memcpy(&a, s, 2);
    std::memcpy(&e, s + n - 2, 2);
    std::memcpy(d, &a, 2);
    std::memcpy(d + n - 2, &e, 2);
  } else {
    *d = *s;
  }
}

// 64 < n <= 128; all loads before all stores. (Banjo's calls: a fifth are 64 to 127 bytes.)
[[gnu::always_inline]] inline void CopyMedium(uint8_t* d, const uint8_t* s, uint32_t n) {
  const B16 a = L16(s), b = L16(s + 16), c = L16(s + 32), e = L16(s + 48);
  const B16 f = L16(s + n - 64), g = L16(s + n - 48), h = L16(s + n - 32), i = L16(s + n - 16);
  S16(d, a);
  S16(d + 16, b);
  S16(d + 32, c);
  S16(d + 48, e);
  S16(d + n - 64, f);
  S16(d + n - 48, g);
  S16(d + n - 32, h);
  S16(d + n - 16, i);
}

// 1 <= n <= 64, every byte = v.
[[gnu::always_inline]] inline void FillSmall(uint8_t* d, uint8_t v, uint32_t n) {
  if (n >= 16) {
    B16 x;
    std::memset(x.b, v, 16);
    S16(d, x);
    S16(d + n - 16, x);
    if (n > 32) {
      S16(d + 16, x);
      S16(d + n - 32, x);
    }
  } else {
    const uint64_t x = uint64_t(v) * 0x0101010101010101ull;
    if (n >= 8) {
      std::memcpy(d, &x, 8);
      std::memcpy(d + n - 8, &x, 8);
    } else if (n >= 4) {
      std::memcpy(d, &x, 4);
      std::memcpy(d + n - 4, &x, 4);
    } else if (n >= 2) {
      std::memcpy(d, &x, 2);
      std::memcpy(d + n - 2, &x, 2);
    } else {
      *d = v;
    }
  }
}

// [a, a + n) is one stretch of host memory: it does not wrap around 4 GB and (on hosts with the physical-view
// offset) does not cross its boundary. n >= 1.
[[gnu::always_inline]] inline bool Straight(uint32_t a, uint32_t n) {
  if (uint64_t(a) + n > 0x100000000ull) return false;
  return ::banjo::hot::PhysOff(a) == ::banjo::hot::PhysOff(a + n - 1u);
}

// Guest (big-endian) loads and stores through the host's view of guest memory.
[[gnu::always_inline]] inline uint8_t Load8(uint8_t* base, uint32_t a) { return *::banjo::hot::Raw(base, a); }
[[gnu::always_inline]] inline uint32_t Load32(uint8_t* base, uint32_t a) {
  uint32_t v;
  std::memcpy(&v, ::banjo::hot::Raw(base, a), 4);
  return __builtin_bswap32(v);
}
[[gnu::always_inline]] inline void Store32(uint8_t* base, uint32_t a, uint32_t v) {
  v = __builtin_bswap32(v);
  std::memcpy(::banjo::hot::Raw(base, a), &v, 4);
}
[[gnu::always_inline]] inline void Store64(uint8_t* base, uint32_t a, uint64_t v) {
  v = __builtin_bswap64(v);
  std::memcpy(::banjo::hot::Raw(base, a), &v, 8);
}

// sasrt-nx (2026-11-08): single-precision steps of the FPU (flush mode off) computed in either mode. 0 < |d| < 2^-126:
// the doubles whose conversion to single the flush mode can change (rex::ppc::DoubleToSingleAnyMode's test).
[[gnu::always_inline]] inline bool SingleTiny(double d) {
  const uint64_t a = std::bit_cast<uint64_t>(d) & 0x7FFFFFFFFFFFFFFFull;
  return a - 1u < 0x3810000000000000ull - 1u;
}
#if defined(__aarch64__)
#define SASRT_HAND_FP_BARRIER(x) __asm__ __volatile__("" : "+w"(x))
#elif defined(__x86_64__) || defined(_M_X64)
#define SASRT_HAND_FP_BARRIER(x) __asm__ __volatile__("" : "+x"(x))
#else
#define SASRT_HAND_FP_BARRIER(x) ((void)0)
#endif
[[gnu::noinline, gnu::cold]] inline double SqrtsOff(double a) noexcept {
  using P = rex::platform::FPSCRPlatform;
  const auto saved = P::getcsr();
  P::setcsr(decltype(saved)(saved & ~decltype(saved)(P::FlushMask)));
  SASRT_HAND_FP_BARRIER(a);
  double r = REX_FSQRTS(a);
  SASRT_HAND_FP_BARRIER(r);
  P::setcsr(saved);
  return r;
}
[[gnu::noinline, gnu::cold]] inline double FaddsOff(double a, double b) noexcept {
  using P = rex::platform::FPSCRPlatform;
  const auto saved = P::getcsr();
  P::setcsr(decltype(saved)(saved & ~decltype(saved)(P::FlushMask)));
  SASRT_HAND_FP_BARRIER(a);
  SASRT_HAND_FP_BARRIER(b);
  double r = REX_FADDS(a, b);
  SASRT_HAND_FP_BARRIER(r);
  P::setcsr(saved);
  return r;
}
#undef SASRT_HAND_FP_BARRIER
// fsqrts: an operand outside the single denormal range converts and roots the same in either mode (a root of a
// normal single is normal).
[[gnu::always_inline]] inline double Sqrts(double a) {
  if (SingleTiny(a)) [[unlikely]] return SqrtsOff(a);
  return REX_FSQRTS(a);
}
// fadds (REX_FADDS: float(a) + float(b)): operands outside the single denormal range convert the same; the sum can
// differ only where it is tiny (the vector mode flushes it to zero; tininess before rounding on AArch64: a sum that
// rounds to FLT_MIN too), so a result of magnitude FLT_MIN or less takes the cold path unless it is an exact
// cancellation (x + -x: +0 in either mode).
[[gnu::always_inline]] inline double Fadds(double a, double b) {
  if (SingleTiny(a) || SingleTiny(b)) [[unlikely]] return FaddsOff(a, b);
  const float fa = float(a), fb = float(b);
  const float r = fa + fb;
  if ((std::bit_cast<uint32_t>(r) & 0x7FFFFFFFu) <= 0x00800000u && !(fa == -fb)) [[unlikely]] return FaddsOff(a, b);
  return double(r);
}

// sasrt-nx (2026-11-08): the four stvewx of one vector at e0, e0 + 4, e0 + 8, e0 + 12 (e0 4-aligned): word j of
// [e0, e0 + 16) gets the vector's lane 3 - (((e0 >> 2) + j) & 3) (the generated code's lane-by-address form); with the
// host's lane order that is the vector rotated by (e0 >> 2) & 3 lanes, then one byte-swapped 16-byte store, and the
// four card marks of the four stores. false: the logged form's run is over (nothing written).
template <class S>
[[gnu::always_inline]] inline bool StoreWordsOfVector(uint8_t* base, S& s, uint32_t e0, const PPCVRegister& v) {
  if (!s.Note(e0, 16u)) return false;
  simde__m128i h = simde_mm_load_si128((const simde__m128i*)v.u8);
  switch ((e0 >> 2) & 3u) {
    case 1:
      h = simde_mm_shuffle_epi32(h, 0x93);  // lanes (3, 0, 1, 2)
      break;
    case 2:
      h = simde_mm_shuffle_epi32(h, 0x4E);  // lanes (2, 3, 0, 1)
      break;
    case 3:
      h = simde_mm_shuffle_epi32(h, 0x39);  // lanes (1, 2, 3, 0)
      break;
    default:
      break;
  }
  simde_mm_storeu_si128((simde__m128i*)REX_RAW_ADDR(e0), REX_BSWAP128(h));
  REX_CARD(e0);
  REX_CARD(e0 + 4u);
  REX_CARD(e0 + 8u);
  REX_CARD(e0 + 12u);
  return true;
}

}  // namespace detail


// ---------------------------------------------------------------------------------------------------------------
// sub_82C92CC8 - the C runtime's stack cookie check (__security_check_cookie): r3 = the cookie the caller saved at its
// entry. The processed original (sasrt_recomp.124.cpp): r11 = the global cookie (0x8316E980), cr6 = compare(r3, r11);
// equal: return; not equal: the failure report (sub_82C9A6A0, which reaches an app hook). r11 and cr6 are locals of
// the generated function (the register diet), so the equal path writes no register and no memory.
//
// Why by hand (2026-11-08): it ends every function with a stack buffer, 73 of the 713 localized copies among them.
// Its failure path reaches an app hook, so tools/localize_native.py could not take it into a copy: every one of those
// copies made a REAL call at its end (all of its registers stored before and loaded after it) and the guard could
// never compare them (a real call cannot be repeated). This native answers the equal path in the copy itself and
// declines the other (the generated copy then makes the real call, as before).
namespace n_82C92CC8 {

template <class S>
[[gnu::always_inline]] inline bool Native(PPCContext& __restrict ctx, uint8_t* base, [[maybe_unused]] S& s) {
  if (!On(k_sasrt_hand_cookie_check)) [[unlikely]] return false;
  return ctx.r3.u32 == detail::Load32(base, 0x8316E980u);
}

}  // namespace n_82C92CC8

// ---------------------------------------------------------------------------------------------------------------
// sub_82872180 - WaterThread's table lookup (the second-hottest guest function of the stock-clock console profile,
// rex_profile_008: 1.9 % of all guest samples). r3 = out A, r4 = out B, r5 = an input vector: each lane times a scale
// (the float at 0x820C6308, splatted), truncated to an int, (i & 0xFF) indexes a table of 8-byte entries at 0x831C8DD0;
// A gets the entries' second floats, B their first. In between the processed original switches the host's flush mode
// off (one scalar float load) and on again (one vector multiply), stores the product to the stack and loads its lanes
// back, stores the four conversions as doublewords and loads their low words back, and puts the table values on the
// stack to load them as a vector.
//
// The samples (tools/switch_hot_pcs.py, 143 in the function): 22 on the two `msr fpcr` and the branch after them;
// the rest spread over the stack round trips. This native has no mode switch: it leaves the mode ON at the end as the
// original does (enableFlushMode: nothing when it already was), and computes the multiply in whatever mode the call
// came with, which gives the original's lanes exactly when no input lane is a denormal and no product is in or next to
// the denormal range (|p| <= 2^-126, where the original's flush to zero could differ): those calls DECLINE, and so do
// the original's other two paths (the flag byte at 0x831C95D0 set: a call; the table not built yet: its builder) and
// outputs that overlap the new stack frame or the table (the original's order of loads and stores would then matter).
// Every register the original writes back is written with the same value (the 64-bit images included: r5-r8 are the
// sign-extended table address + 4, as the original's addi leaves them), every byte it leaves in memory is left (the
// stack temporaries with their final values, once), and the cookie check at the end is the native above.
namespace n_82872180 {

[[gnu::always_inline]] inline bool Tiny(uint32_t b) {
  return (b & 0x7F800000u) <= 0x00800000u && (b & 0x7FFFFFFFu) != 0u;  // denormal, or the smallest normal
}
[[gnu::always_inline]] inline bool Denormal(uint32_t b) { return (b & 0x7F800000u) == 0u && (b & 0x007FFFFFu) != 0u; }

template <class S>
[[gnu::always_inline]] inline bool Native(PPCContext& __restrict ctx, uint8_t* base, [[maybe_unused]] S& s) {
  if (!On(k_sasrt_hand_water_table)) [[unlikely]] return false;
  constexpr uint32_t kTable = 0x831C8DD0u, kFlag = 0x831C95D0u, kScale = 0x820C6308u, kCookie = 0x8316E980u;
  if (detail::Load8(base, kFlag) != 0) return false;                      // the original's other path (a call)
  if ((detail::Load32(base, kTable) & 0x7FFFFFFFu) == 0) return false;    // the table is not built yet
  // The new frame (the original's r1 arithmetic: the low word moves, the high word stays).
  PPCRegister r1n = ctx.r1;
  r1n.u32 = ctx.r1.u32 - 176u;
  const uint32_t fr = r1n.u32;
  const uint32_t out_a = ctx.r3.u32 & ~0xFu, out_b = ctx.r4.u32 & ~0xFu, in = ctx.r5.u32 & ~0xFu;
  auto overlaps = [](uint32_t a, uint32_t lo, uint32_t hi) { return a + 16u > lo && a < hi; };
  if (overlaps(out_a, fr, fr + 176u) || overlaps(out_b, fr, fr + 176u) || overlaps(out_a, kTable, kTable + 0x800u))
    [[unlikely]] return false;
  // v63 = the input, v62 = the scale's lvlx, v61 = its lane 0 splatted, v60 = the product (the original's statements).
  PPCVRegister v63, v62, v61, v60;
  simde_mm_store_si128((simde__m128i*)v63.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(in))));
  {
    const uint32_t t = kScale;
    simde_mm_store_si128((simde__m128i*)v62.u8, REX_SHUFFLE_TABLE(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(t & ~0xF)), &VectorMaskL[(t & 0xF) * 16]));
  }
  simde_mm_store_si128((simde__m128i*)v61.u32, simde_mm_shuffle_epi32(simde_mm_load_si128((simde__m128i*)v62.u32), 0xFF));
  if (Denormal(v61.u32[0]) || Denormal(v63.u32[0]) || Denormal(v63.u32[1]) || Denormal(v63.u32[2]) ||
      Denormal(v63.u32[3])) [[unlikely]]
    return false;
  simde_mm_store_ps(v60.f32, simde_mm_mul_ps(simde_mm_load_ps(v63.f32), simde_mm_load_ps(v61.f32)));
  if (Tiny(v60.u32[0]) || Tiny(v60.u32[1]) || Tiny(v60.u32[2]) || Tiny(v60.u32[3])) [[unlikely]] return false;

  // Accepted. The lanes in guest order (host lane 3 is guest element 0).
  const uint32_t e0 = v60.u32[3], e1 = v60.u32[2], e2 = v60.u32[1], e3 = v60.u32[0];
  PPCRegister f7, f8, f9, f10, f11, f12;
  f8.f64 = rex::ppc::SingleToDoublePure(e1);
  f12.f64 = rex::ppc::SingleToDoublePure(e2);
  f9.s64 = rex::ppc::fctiwz(rex::ppc::SingleToDoublePure(e0));
  f10.s64 = rex::ppc::fctiwz(rex::ppc::SingleToDoublePure(e3));
  f11.s64 = rex::ppc::fctiwz(f12.f64);
  f7.s64 = rex::ppc::fctiwz(f8.f64);
  const uint32_t i0 = (uint32_t(f9.u64) << 3) & 0x7F8u, i1 = (uint32_t(f7.u64) << 3) & 0x7F8u;
  const uint32_t i2 = (uint32_t(f11.u64) << 3) & 0x7F8u, i3 = (uint32_t(f10.u64) << 3) & 0x7F8u;
  const uint32_t a0 = detail::Load32(base, kTable + 4u + i0), a1 = detail::Load32(base, kTable + 4u + i1);
  const uint32_t a2 = detail::Load32(base, kTable + 4u + i2), a3 = detail::Load32(base, kTable + 4u + i3);
  const uint32_t b0 = detail::Load32(base, kTable + i0), b1 = detail::Load32(base, kTable + i1);
  const uint32_t b2 = detail::Load32(base, kTable + i2), b3 = detail::Load32(base, kTable + i3);
  const uint32_t cookie = detail::Load32(base, kCookie);

  // Memory: the back chain, the saved cookie, the conversions' doublewords (+80 holds the last one, f7), the vector
  // temporary at +112 (its last contents: B), out A, out B.
  if (!s.Note(fr, 4)) [[unlikely]] return true;
  detail::Store32(base, fr, ctx.r1.u32);
  if (!s.Note(fr + 128u, 4)) [[unlikely]] return true;
  detail::Store32(base, fr + 128u, cookie);
  if (!s.Note(fr + 80u, 24)) [[unlikely]] return true;
  detail::Store64(base, fr + 80u, f7.u64);
  detail::Store64(base, fr + 88u, f10.u64);
  detail::Store64(base, fr + 96u, f11.u64);
  const uint32_t qa0 = rex::ppc::QuietSingleBits(a0), qa1 = rex::ppc::QuietSingleBits(a1);
  const uint32_t qa2 = rex::ppc::QuietSingleBits(a2), qa3 = rex::ppc::QuietSingleBits(a3);
  const uint32_t qb0 = rex::ppc::QuietSingleBits(b0), qb1 = rex::ppc::QuietSingleBits(b1);
  const uint32_t qb2 = rex::ppc::QuietSingleBits(b2), qb3 = rex::ppc::QuietSingleBits(b3);
  if (!s.Note(fr + 112u, 16)) [[unlikely]] return true;
  REX_CARD(fr + 112u);
  detail::Store32(base, fr + 112u, qb0);
  detail::Store32(base, fr + 116u, qb1);
  detail::Store32(base, fr + 120u, qb2);
  detail::Store32(base, fr + 124u, qb3);
  if (!s.Note(out_a, 16)) [[unlikely]] return true;
  REX_CARD(out_a);
  detail::Store32(base, out_a, qa0);
  detail::Store32(base, out_a + 4u, qa1);
  detail::Store32(base, out_a + 8u, qa2);
  detail::Store32(base, out_a + 12u, qa3);
  if (!s.Note(out_b, 16)) [[unlikely]] return true;
  REX_CARD(out_b);
  detail::Store32(base, out_b, qb0);
  detail::Store32(base, out_b + 4u, qb1);
  detail::Store32(base, out_b + 8u, qb2);
  detail::Store32(base, out_b + 12u, qb3);

  // Registers, as the original leaves them.
  PPCRegister t5;
  t5.s64 = int64_t(-2095251456) + -29232 + 4;  // r31 + 4, sign-extended as the original's addi leaves it
  ctx.r3.u64 = cookie;
  ctx.r4.s64 = r1n.s64 + 112;
  ctx.r5 = t5;
  ctx.r6 = t5;
  ctx.r7 = t5;
  ctx.r8 = t5;
  ctx.r9.u64 = i0;
  ctx.r10.u64 = i3;
  ctx.f1.f64 = rex::ppc::SingleToDoublePure(b1);
  ctx.f2.f64 = rex::ppc::SingleToDoublePure(b0);
  ctx.f3.f64 = rex::ppc::SingleToDoublePure(a3);
  ctx.f4.f64 = rex::ppc::SingleToDoublePure(a2);
  ctx.f5.f64 = rex::ppc::SingleToDoublePure(a1);
  ctx.f6.f64 = rex::ppc::SingleToDoublePure(a0);
  ctx.f7 = f7;
  ctx.f8 = f8;
  ctx.f9 = f9;
  ctx.f10 = f10;
  ctx.f11 = f11;
  ctx.f12 = f12;
  ctx.f13.f64 = rex::ppc::SingleToDoublePure(b3);
  ctx.v63 = v63;
  ctx.v62 = v62;
  ctx.v61 = v61;
  ctx.v60 = v60;
  // v59 / v58: the vector loads of the temporary (A, then B) as the original's lvx leaves them.
  ctx.v59.u32[3] = qa0;
  ctx.v59.u32[2] = qa1;
  ctx.v59.u32[1] = qa2;
  ctx.v59.u32[0] = qa3;
  ctx.v58.u32[3] = qb0;
  ctx.v58.u32[2] = qb1;
  ctx.v58.u32[1] = qb2;
  ctx.v58.u32[0] = qb3;
  ctx.fpscr.enableFlushMode();  // the original's last mode change (nothing when it was on already)
  // The cookie check (its native: equal, nothing to do). Unequal only if another thread rewrote the global: the
  // original's real call, which a guarded run cannot repeat.
  if (detail::Load32(base, kCookie) != cookie) [[unlikely]] {
    if (s.Open()) return true;
    ctx.r1 = r1n;
    __imp__sub_82C92CC8(ctx, base);
    ctx.r1.s64 = ctx.r1.s64 + 176;
    return true;
  }
  ctx.r1.s64 = r1n.s64 + 176;
  return true;
}

}  // namespace n_82872180


// ---------------------------------------------------------------------------------------------------------------
// sub_8279A888 - a bounding sphere of a linked list of points (SlRenderer; 0.6 % of the stock-clock console profile's
// guest samples, a localized copy since 2026-10-06). Loop 1 sums the points (vector, flush mode on), loop 2 measures
// each point's distance from the centre (vector subtract and dot product, flush mode on) and then its square root and
// the radius in single precision (the FPU, flush mode off): the original switches the host's mode off and on again at
// every point, two `msr fpcr`. The samples (tools/switch_hot_pcs.py, 57 in the copy): 17 on the two msr and the branch
// after them, 14 on the next point's loads.
//
// This native is the machine copy's own statements (tools/localize_native.py's f_sub_8279A888, registers in locals)
// with loop 2 changed: the mode stays on through the loop, the square root and the add give the FPU mode's result
// (detail::Sqrts / detail::Fadds: exact, a cold path with the mode cleared for an operand or result in the denormal
// range), the add of the margin and the load of the stored radius are the SDK's mode-free helpers, and each exit of
// the loop sets the mode the original's last iteration leaves (off). Everything else is the copy's text.
namespace n_8279A888 {

template <class S>
[[gnu::always_inline]] inline bool Native(PPCContext& __restrict ctx, uint8_t* base, [[maybe_unused]] S& s) {
#if defined(REX_SINGLE_FLOATS_OFF)
  return false;  // detail::Fadds is the single-float form of REX_FADDS
#endif
  if (!On(k_sasrt_hand_sphere_fit)) [[unlikely]] return false;
	PPCRegister l_f1 = ctx.f1;
	PPCRegister l_f10 = ctx.f10;
	PPCRegister l_f11 = ctx.f11;
	PPCRegister l_f12 = ctx.f12;
	PPCRegister l_f13 = ctx.f13;
	PPCRegister l_r1 = ctx.r1;
	PPCRegister l_r3 = ctx.r3;
	PPCRegister l_r4 = ctx.r4;
	PPCRegister l_r5 = ctx.r5;
	PPCRegister l_r6 = ctx.r6;
	PPCRegister l_r7 = ctx.r7;
	PPCRegister l_r8 = ctx.r8;
	PPCRegister l_r9 = ctx.r9;
	PPCRegister l_r10 = ctx.r10;
	PPCVRegister l_v0 = ctx.v0;
	PPCVRegister l_v12 = ctx.v12;
	PPCVRegister l_v13 = ctx.v13;
	PPCVRegister l_v61 = ctx.v61;
	PPCVRegister l_v62 = ctx.v62;
	PPCVRegister l_v63 = ctx.v63;
	s.Hit(0);
	REX_FUNC_PROLOGUE();
	PPCXERRegister xer{};
	PPCCRRegister cr0{};
	PPCCRRegister cr6{};
	PPCRegister r11{};
	PPCRegister r30{};
	PPCRegister r31{};
	PPCRegister f0{};
	PPCRegister temp{};
	PPCRegister fb0{};
	PPCRegister fb11{};
	PPCRegister fb12{};
	PPCRegister fb13{};
	uint32_t ea{};
	REX_DEAD_SAVE(BANJO_HOT_STORE_D_U64(l_r1.u32, -16, r30.u64));
	if (s.Stopped()) return true;
	REX_DEAD_SAVE(BANJO_HOT_STORE_D_U64(l_r1.u32, -8, r31.u64));
	if (s.Stopped()) return true;
	l_r7.u64 = REX_LOAD_D_U32(l_r3.u32, 20);
	l_r10.u64 = l_r3.u64;
	l_r5.s64 = l_r3.s64 + 20;
	cr6.compare<uint32_t>(l_r7.u32, 0, xer);
	if (!cr6.eq) goto loc_8279A8AC;
	s.Hit(1);
	l_r3.s64 = 1;
	goto loc_8279AA3C;
loc_8279A8AC:
	s.Hit(2);
	l_r6.u64 = REX_LOAD_D_U32(l_r10.u32, 40);
	l_r4.s64 = l_r10.s64 + 40;
	r11.u64 = (l_r6.u32 & 0x8u);
	cr0.compare<int32_t>(r11.s32, 0, xer);
	if (!cr0.eq) goto loc_8279AA38;
	s.Hit(3);
	l_r9.s64 = -2113798144;
	r11.s64 = 0;
	l_r3.s64 = l_r9.s64 + -31328;
	l_r9.u64 = r11.u64;
	l_r8.u64 = l_r7.u64;
	ea = (l_r3.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)l_v62.u8, REX_RO_V128(0x820185A0, 0x0000000000000000ull, 0x0000000000000000ull));
loc_8279A8D4:
	s.Hit(4);
	REX_LOOP_BARRIER();
	ea = (l_r8.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)l_v63.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	l_r8.u64 = REX_LOAD_D_U32(l_r8.u32, 24);
	l_r9.s64 = l_r9.s64 + 1;
	ctx.fpscr.enableFlushMode();
	simde_mm_store_ps(l_v62.f32, simde_mm_add_ps(simde_mm_load_ps(l_v62.f32), simde_mm_load_ps(l_v63.f32)));
	cr6.compare<uint32_t>(l_r8.u32, 0, xer);
	if (!cr6.eq) goto loc_8279A8D4;
	s.Hit(5);
	cr6.compare<int32_t>(l_r9.s32, 0, xer);
	if (cr6.eq) goto loc_8279AA2C;
	s.Hit(6);
	l_r9.s64 = l_r9.s32;
	ea = (l_r10.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)l_v13.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	l_r8.s64 = l_r1.s64 + -32;
	BANJO_HOT_STORE_D_U32(l_r1.u32, -32, r11.u32);
	if (s.Stopped()) return true;
	BANJO_HOT_STORE_D_U64(l_r1.u32, -48, l_r9.u64);
	if (s.Stopped()) return true;
	f0.u64 = REX_LOAD_D_U64(l_r1.u32, -48);
	f0.f64 = double(f0.s64);
	l_r9.s64 = -1;
	BANJO_HOT_STORE_D_U32(l_r1.u32, -28, r11.u32);
	if (s.Stopped()) return true;
	l_f13.f64 = rex::ppc::RoundToSingleAnyMode(f0.f64);
	BANJO_HOT_STORE_D_U32(l_r1.u32, -24, r11.u32);
	if (s.Stopped()) return true;
	l_r3.s64 = -2113929216;
	BANJO_HOT_STORE_D_U32(l_r1.u32, -20, l_r9.u32);
	if (s.Stopped()) return true;
	ea = (l_r8.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)l_v12.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	r31.s64 = l_r1.s64 + -48;
	simde_mm_store_si128((simde__m128i*)l_v63.u8, simde_mm_load_si128((simde__m128i*)l_v13.u8));
	r30.s64 = -2113929216;
	l_r8.u64 = l_r7.u64;
	fb0.u32 = REX_RO_CFG_U32(0x82002490, 0x3F800000u, REX_LOAD_D_U32(l_r3.u32, 9360));
	f0.f64 = rex::ppc::SingleToDoublePure(fb0.u32);
	fb12.u32 = REX_RO_CFG_U32(0x82002494, 0x0u, REX_LOAD_D_U32(r30.u32, 9364));
	l_f12.f64 = rex::ppc::SingleToDoublePure(fb12.u32);
	f0.f64 = rex::ppc::DivSingleAnyMode(f0.f64, l_f13.f64);
	temp.f32 = rex::ppc::DoubleToSingleAnyMode(f0.f64);
	BANJO_HOT_STORE_D_U32(l_r1.u32, -48, temp.u32);
	if (s.Stopped()) return true;
	temp.u32 = r31.u32;
	simde_mm_store_si128((simde__m128i*)l_v61.u8, REX_SHUFFLE_TABLE(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(temp.u32 & ~0xF)), &VectorMaskL[(temp.u32 & 0xF) * 16]));
	simde_mm_store_si128((simde__m128i*)l_v61.u32, simde_mm_shuffle_epi32(simde_mm_load_si128((simde__m128i*)l_v61.u32), 0xFF));
	simde_mm_store_si128((simde__m128i*)l_v61.u32, simde_mm_shuffle_epi32(simde_mm_load_si128((simde__m128i*)l_v61.u32), 0xFF));
	f0.f64 = l_f12.f64;
	simde_mm_store_ps(l_v0.f32, simde_mm_mul_ps(simde_mm_load_ps(l_v62.f32), simde_mm_load_ps(l_v61.f32)));
	simde_mm_store_si128((simde__m128i*)l_v12.u8, REX_VSEL(simde_mm_load_si128((simde__m128i*)l_v12.u8), simde_mm_load_si128((simde__m128i*)l_v0.u8), simde_mm_load_si128((simde__m128i*)l_v13.u8)));
	ea = (l_r10.u32) & ~0xF;
	if (s.Note((u32)(ea), 16)) REX_CARD(ea), simde_mm_store_si128((simde__m128i*)REX_RAW_ADDR(ea), REX_BSWAP128(simde_mm_load_si128((simde__m128i*)l_v12.u8)));
	if (s.Stopped()) return true;
	simde_mm_store_si128((simde__m128i*)l_v62.u8, simde_mm_load_si128((simde__m128i*)l_v12.u8));
loc_8279A96C:
	s.Hit(7);
	REX_LOOP_BARRIER();
	ea = (l_r8.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)l_v61.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	l_r7.s64 = l_r1.s64 + -48;
	ctx.fpscr.enableFlushMode();
	simde_mm_store_ps(l_v61.f32, simde_mm_sub_ps(simde_mm_load_ps(l_v62.f32), simde_mm_load_ps(l_v61.f32)));
	simde_mm_store_ps(l_v61.f32, simde_mm_dp_ps(simde_mm_load_ps(l_v61.f32), simde_mm_load_ps(l_v61.f32), 0xEF));
	simde_mm_store_si128((simde__m128i*)l_v61.u32, simde_mm_shuffle_epi32(simde_mm_load_si128((simde__m128i*)l_v61.u32), 0xFF));
	ea = (l_r7.u32) & ~0x3;
	BANJO_HOT_STORE_U32_C(ea, l_v61.u32[3 - ((ea & 0xF) >> 2)]);
	if (s.Stopped()) return true;
	fb13.u32 = REX_LOAD_D_U32(l_r8.u32, 12);
	l_f13.f64 = rex::ppc::SingleToDoublePure(fb13.u32);
	fb11.u32 = REX_LOAD_D_U32(l_r1.u32, -48);
	l_f11.f64 = rex::ppc::SingleToDoublePure(fb11.u32);
	// sasrt-nx: no switch to the FPU's mode here (the original's msr fpcr, then another at the next iteration's
	// vector steps): the two single-precision steps give the FPU mode's result in the vector mode (detail::Sqrts,
	// detail::Fadds: a cold path with the mode cleared where an operand or the result is in the denormal range).
	l_f11.f64 = detail::Sqrts(l_f11.f64);
	l_f13.f64 = detail::Fadds(l_f11.f64, l_f13.f64);
	cr6.compare(l_f13.f64, f0.f64);
	if (!cr6.gt) goto loc_8279A9B0;
	s.Hit(8);
	l_f11.f64 = rex::ppc::AddSingleAnyMode(l_f13.f64, l_f1.f64);
	l_f10.f64 = rex::ppc::SingleToDoublePure(REX_LOAD_D_U32(l_r10.u32, 12));
	f0.f64 = l_f13.f64;
	cr6.compare(l_f11.f64, l_f10.f64);
	if (!cr6.lt) goto loc_8279A9CC;
loc_8279A9B0:
	s.Hit(9);
	l_r8.u64 = REX_LOAD_D_U32(l_r8.u32, 24);
	cr6.compare<uint32_t>(l_r8.u32, 0, xer);
	if (!cr6.eq) goto loc_8279A96C;
	ctx.fpscr.disableFlushMode();  // sasrt-nx: the mode the original's loop leaves
	s.Hit(10);
	REX_FLUSH_KNOWN_OFF();
	f0.f64 = double(float(f0.f64 + l_f1.f64));
	temp.f32 = float(f0.f64);
	BANJO_HOT_STORE_D_U32_C(l_r10.u32, 12, temp.u32);
	if (s.Stopped()) return true;
	r11.u64 = REX_LOAD_D_U32(l_r5.u32, 0);
	goto loc_8279AA24;
loc_8279A9CC:
	ctx.fpscr.disableFlushMode();  // sasrt-nx: the mode the original's loop leaves
	s.Hit(11);
	l_r8.s64 = l_r1.s64 + -32;
	BANJO_HOT_STORE_D_U32(l_r1.u32, -32, r11.u32);
	if (s.Stopped()) return true;
	BANJO_HOT_STORE_D_U32(l_r1.u32, -28, r11.u32);
	if (s.Stopped()) return true;
	simde_mm_store_si128((simde__m128i*)l_v0.u8, simde_mm_load_si128((simde__m128i*)l_v63.u8));
	BANJO_HOT_STORE_D_U32(l_r1.u32, -24, r11.u32);
	if (s.Stopped()) return true;
	r11.u64 = __builtin_rotateleft64(l_r6.u32 | (l_r6.u64 << 32), 0) & 0xFFFFFFFFFFFFFFEF;
	BANJO_HOT_STORE_D_U32(l_r1.u32, -20, l_r9.u32);
	if (s.Stopped()) return true;
	ea = (l_r8.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)l_v13.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	simde_mm_store_si128((simde__m128i*)l_v13.u8, REX_VSEL(simde_mm_load_si128((simde__m128i*)l_v13.u8), simde_mm_load_si128((simde__m128i*)l_v0.u8), simde_mm_load_si128((simde__m128i*)l_v12.u8)));
	ea = (l_r10.u32) & ~0xF;
	if (s.Note((u32)(ea), 16)) REX_CARD(ea), simde_mm_store_si128((simde__m128i*)REX_RAW_ADDR(ea), REX_BSWAP128(simde_mm_load_si128((simde__m128i*)l_v13.u8)));
	if (s.Stopped()) return true;
	goto loc_8279AA34;
loc_8279A9F8:
	s.Hit(12);
	REX_LOOP_BARRIER();
	REX_FLUSH_KNOWN_OFF();
	f0.f64 = double(REX_LOAD_D_F32(l_r10.u32, 12));
	l_f13.f64 = double(REX_LOAD_D_F32(r11.u32, 12));
	f0.f64 = REX_FSUBS(f0.f64, l_f13.f64);
	temp.f32 = float(f0.f64);
	BANJO_HOT_STORE_D_U32_C(r11.u32, 48, temp.u32);
	if (s.Stopped()) return true;
	cr6.compare(f0.f64, l_f12.f64);
	if (cr6.gt) goto loc_8279AA18;
	s.Hit(13);
	temp.f32 = float(l_f12.f64);
	BANJO_HOT_STORE_D_U32_C(r11.u32, 48, temp.u32);
	if (s.Stopped()) return true;
	goto loc_8279AA20;
loc_8279AA18:
	s.Hit(14);
	REX_FLUSH_KNOWN_OFF();
	f0.f64 = REX_FMULS(f0.f64, f0.f64);
	temp.f32 = float(f0.f64);
	BANJO_HOT_STORE_D_U32_C(r11.u32, 48, temp.u32);
	if (s.Stopped()) return true;
loc_8279AA20:
	s.Hit(15);
	r11.u64 = REX_LOAD_D_U32(r11.u32, 24);
loc_8279AA24:
	s.Hit(16);
	cr6.compare<uint32_t>(r11.u32, 0, xer);
	if (!cr6.eq) goto loc_8279A9F8;
loc_8279AA2C:
	s.Hit(17);
	r11.u64 = REX_LOAD_D_U32(l_r4.u32, 0);
	r11.u64 = __builtin_rotateleft64(r11.u32 | (r11.u64 << 32), 0) & 0xFFFFFFFFFFFFFFEF;
loc_8279AA34:
	s.Hit(18);
	BANJO_HOT_STORE_D_U32_C(l_r4.u32, 0, r11.u32);
	if (s.Stopped()) return true;
loc_8279AA38:
	s.Hit(19);
	l_r3.s64 = 0;
loc_8279AA3C:
	s.Hit(20);
	r30.u64 = REX_LOAD_D_U64(l_r1.u32, -16);
	r31.u64 = REX_LOAD_D_U64(l_r1.u32, -8);
	{ ctx.f10 = l_f10; ctx.f11 = l_f11; ctx.f12 = l_f12; ctx.f13 = l_f13; ctx.r3 = l_r3; ctx.r4 = l_r4; ctx.r5 = l_r5; ctx.r6 = l_r6; ctx.r7 = l_r7; ctx.r8 = l_r8; ctx.r9 = l_r9; ctx.r10 = l_r10; ctx.v0 = l_v0; ctx.v12 = l_v12; ctx.v13 = l_v13; ctx.v61 = l_v61; ctx.v62 = l_v62; ctx.v63 = l_v63; return true; }
	return true;
}

}  // namespace n_8279A888


// ---------------------------------------------------------------------------------------------------------------
// sub_82720840 - an audio resampler (16-bit samples to floats with linear interpolation, four a step; 0.8 % of the
// stock-clock console profile's guest samples). The samples (tools/switch_hot_pcs.py, 64 in the function): 20 in the
// byte loops of the unaligned vector store that ends each step (the generated code's stvlx and stvrx helpers: 8, 4,
// 2 and 1-byte pieces chosen by the address, the branches mispredicted as the address moves). This native is the
// machine copy's own statements (tools/localize_native.py's f_sub_82720840, registers in locals) with that pair as one
// 16-byte store of the same bytes (the original's r31 is the constant 16 there; anything else, or a range across the
// PC's physical-view boundary, runs the two helpers as before) and the same two store-card marks.
namespace n_82720840 {

template <class S>
[[gnu::always_inline]] inline bool Native(PPCContext& __restrict ctx, uint8_t* base, [[maybe_unused]] S& s) {
  if (!On(k_sasrt_hand_resampler)) [[unlikely]] return false;
	PPCRegister l_f10 = ctx.f10;
	PPCRegister l_f11 = ctx.f11;
	PPCRegister l_f12 = ctx.f12;
	PPCRegister l_f13 = ctx.f13;
	PPCRegister l_r1 = ctx.r1;
	PPCRegister l_r3 = ctx.r3;
	PPCRegister l_r4 = ctx.r4;
	PPCRegister l_r5 = ctx.r5;
	PPCRegister l_r6 = ctx.r6;
	PPCRegister l_r7 = ctx.r7;
	PPCRegister l_r8 = ctx.r8;
	PPCRegister l_r9 = ctx.r9;
	PPCRegister l_r10 = ctx.r10;
	PPCVRegister l_v0 = ctx.v0;
	PPCVRegister l_v1 = ctx.v1;
	PPCVRegister l_v2 = ctx.v2;
	PPCVRegister l_v3 = ctx.v3;
	PPCVRegister l_v4 = ctx.v4;
	PPCVRegister l_v5 = ctx.v5;
	PPCVRegister l_v6 = ctx.v6;
	PPCVRegister l_v7 = ctx.v7;
	PPCVRegister l_v8 = ctx.v8;
	PPCVRegister l_v9 = ctx.v9;
	PPCVRegister l_v10 = ctx.v10;
	PPCVRegister l_v11 = ctx.v11;
	PPCVRegister l_v12 = ctx.v12;
	PPCVRegister l_v13 = ctx.v13;
	PPCVRegister l_v31 = ctx.v31;
	PPCVRegister l_v56 = ctx.v56;
	PPCVRegister l_v57 = ctx.v57;
	PPCVRegister l_v58 = ctx.v58;
	PPCVRegister l_v59 = ctx.v59;
	PPCVRegister l_v60 = ctx.v60;
	PPCVRegister l_v61 = ctx.v61;
	PPCVRegister l_v62 = ctx.v62;
	PPCVRegister l_v63 = ctx.v63;
	s.Hit(0);
	REX_FUNC_PROLOGUE();

	REX_LOOP_LOCAL(PPCRegister, ll_f10, l_f10);
	REX_LOOP_LOCAL(PPCRegister, ll_f11, l_f11);
	REX_LOOP_LOCAL(PPCRegister, ll_f12, l_f12);
	REX_LOOP_LOCAL(PPCRegister, ll_f13, l_f13);
	REX_LOOP_LOCAL(PPCRegister, ll_r1, l_r1);
	REX_LOOP_LOCAL(PPCRegister, ll_r3, l_r3);
	REX_LOOP_LOCAL(PPCRegister, ll_r5, l_r5);
	REX_LOOP_LOCAL(PPCRegister, ll_r7, l_r7);
	REX_LOOP_LOCAL(PPCRegister, ll_r8, l_r8);
	REX_LOOP_LOCAL(PPCRegister, ll_r9, l_r9);
	REX_LOOP_LOCAL(PPCRegister, ll_r10, l_r10);
	REX_LOOP_LOCAL(PPCVRegister, ll_v0, l_v0);
	REX_LOOP_LOCAL(PPCVRegister, ll_v1, l_v1);
	REX_LOOP_LOCAL(PPCVRegister, ll_v2, l_v2);
	REX_LOOP_LOCAL(PPCVRegister, ll_v3, l_v3);
	REX_LOOP_LOCAL(PPCVRegister, ll_v4, l_v4);
	REX_LOOP_LOCAL(PPCVRegister, ll_v5, l_v5);
	REX_LOOP_LOCAL(PPCVRegister, ll_v6, l_v6);
	REX_LOOP_LOCAL(PPCVRegister, ll_v7, l_v7);
	REX_LOOP_LOCAL(PPCVRegister, ll_v8, l_v8);
	REX_LOOP_LOCAL(PPCVRegister, ll_v9, l_v9);
	REX_LOOP_LOCAL(PPCVRegister, ll_v10, l_v10);
	REX_LOOP_LOCAL(PPCVRegister, ll_v11, l_v11);
	REX_LOOP_LOCAL(PPCVRegister, ll_v12, l_v12);
	REX_LOOP_LOCAL(PPCVRegister, ll_v13, l_v13);
	REX_LOOP_LOCAL(PPCVRegister, ll_v31, l_v31);
	REX_LOOP_LOCAL(PPCVRegister, ll_v56, l_v56);
	REX_LOOP_LOCAL(PPCVRegister, ll_v57, l_v57);
	REX_LOOP_LOCAL(PPCVRegister, ll_v58, l_v58);
	REX_LOOP_LOCAL(PPCVRegister, ll_v59, l_v59);
	REX_LOOP_LOCAL(PPCVRegister, ll_v63, l_v63);
	PPCRegister ctr{};
	PPCXERRegister xer{};
	PPCCRRegister cr6{};
	PPCRegister r11{};
	PPCRegister r12{};
	PPCRegister r20{};
	PPCRegister r21{};
	PPCRegister r22{};
	PPCRegister r23{};
	PPCRegister r24{};
	PPCRegister r25{};
	PPCRegister r26{};
	PPCRegister r27{};
	PPCRegister r28{};
	PPCRegister r29{};
	PPCRegister r30{};
	PPCRegister r31{};
	PPCRegister f0{};
	PPCRegister temp{};
	uint32_t ea{};
	r12.u64 = ctx.lr;
	r11.u64 = REX_LOAD_D_U32(l_r6.u32, 32);
	l_r10.s64 = 0;
	l_r8.u64 = REX_LOAD_D_U32(l_r6.u32, 36);
	r24.s64 = l_r6.s64 + 32;
	r29.u64 = l_r10.u64 | 65535;
	l_r10.u64 = REX_LOAD_D_U32(l_r6.u32, 28);
	l_r9.u64 = l_r8.u64 - r11.u64;
	r25.u64 = REX_LOAD_D_U16(l_r3.u32, 14);
	r21.u64 = l_r5.u64 - l_r10.u64;
	l_r7.u64 = l_r9.u64 + r29.u64;
	r23.s64 = l_r6.s64 + 28;
	r27.u64 = rex::ppc::divwu(l_r7.u32, l_r8.u32);
	r26.s64 = l_r3.s64 + 14;
	if (l_r8.s32 == 0 || l_r8.u32 < 0u) { if (s.Open()) return true; ppc_trap(ctx, base, 0); }
	l_r5.u64 = (r11.u32 >> 16);
	l_r7.u64 = r11.u32 & 0xFFFF;
	cr6.compare<uint32_t>(r21.u32, r27.u32, xer);
	if (!cr6.lt) goto loc_82720894;
	s.Hit(1);
	r27.u64 = r21.u64;
loc_82720894:
	s.Hit(2);
	l_r9.u64 = REX_LOAD_D_U32(l_r4.u32, 0);
	l_r10.u64 = ((uint32_t)(l_r10.u32 << 2));
	r31.u64 = REX_LOAD_D_U32(l_r6.u32, 24);
	r30.s64 = -2113470464;
	l_r9.u64 = l_r10.u64 + l_r9.u64;
	l_r3.u64 = REX_LOAD_D_U32(l_r3.u32, 0);
	l_r10.u64 = ((uint32_t)(r31.u32 << 1));
	r31.u64 = REX_LOAD_D_U16(l_r6.u32, 0);
	r22.s64 = l_r6.s64 + 24;
	l_r10.u64 = l_r10.u64 + l_r3.u64;
	ctx.fpscr.disableFlushMode();
	temp.u32 = REX_RO_U32(0x82070714, 0x30000000);
	f0.f64 = double(temp.f32);
	cr6.compare<uint32_t>(r27.u32, 0, xer);
	l_r10.s64 = l_r10.s64 + -2;
	if (cr6.eq) goto loc_8272091C;
	s.Hit(3);
	l_r5.u64 = REX_LOAD_D_U16(l_r10.u32, 2);
	l_r3.s64 = r31.s16;
	r30.u64 = ((uint32_t)(r31.u32 << 16));
	ctr.u64 = r27.u64;
	r31.s64 = l_r5.s16;
	REX_LOOP_IN(ll_f10, l_f10);
	REX_LOOP_IN(ll_f11, l_f11);
	REX_LOOP_IN(ll_f12, l_f12);
	REX_LOOP_IN(ll_f13, l_f13);
	REX_LOOP_IN(ll_r1, l_r1);
	REX_LOOP_IN(ll_r3, l_r3);
	REX_LOOP_IN(ll_r5, l_r5);
	REX_LOOP_IN(ll_r7, l_r7);
	REX_LOOP_IN(ll_r8, l_r8);
	REX_LOOP_IN(ll_r9, l_r9);
loc_827208E0:
	s.Hit(4);
	REX_LOOP_BARRIER();
	ll_r5.u64 = r31.u64 - ll_r3.u64;
	r11.u64 = ll_r8.u64 + r11.u64;
	ll_r7.s64 = int64_t(ll_r5.s32) * int64_t(ll_r7.s32);
	ll_r7.u64 = ll_r7.u64 + r30.u64;
	ll_r5.u64 = (r11.u32 >> 16);
	r28.s64 = ll_r7.s32;
	ll_r7.u64 = r11.u32 & 0xFFFF;
	BANJO_HOT_STORE_D_U64(ll_r1.u32, -160, r28.u64);
	if (s.Stopped()) return true;
	ll_f13.u64 = REX_LOAD_D_U64(ll_r1.u32, -160);
	ll_f12.f64 = double(ll_f13.s64);
	REX_FLUSH_KNOWN_OFF();
	ll_f11.f64 = double(float(ll_f12.f64));
	ll_f10.f64 = REX_FMULS(ll_f11.f64, f0.f64);
	temp.f32 = float(ll_f10.f64);
	BANJO_HOT_STORE_D_U32_C(ll_r9.u32, 0, temp.u32);
	if (s.Stopped()) return true;
	ll_r9.s64 = ll_r9.s64 + 4;
	--ctr.u64;
	if (ctr.u32 != 0) goto loc_827208E0;
	s.Hit(5);
	REX_LOOP_OUT(ll_f10, l_f10);
	REX_LOOP_OUT(ll_f11, l_f11);
	REX_LOOP_OUT(ll_f12, l_f12);
	REX_LOOP_OUT(ll_f13, l_f13);
	REX_LOOP_OUT(ll_r5, l_r5);
	REX_LOOP_OUT(ll_r7, l_r7);
	REX_LOOP_OUT(ll_r9, l_r9);
loc_8272091C:
	s.Hit(6);
	r31.u64 = ((uint32_t)(r25.u32 << 16));
	l_r3.u64 = r21.u64 - r27.u64;
	r31.u64 = r31.u64 - r11.u64;
	if (l_r8.s32 == 0 || l_r8.u32 < 0u) { if (s.Open()) return true; ctx.r3 = l_r3; ppc_trap(ctx, base, 0); }
	r31.u64 = r31.u64 + l_r8.u64;
	r30.u64 = l_r3.u64;
	r31.s64 = r31.s64 + -1;
	r31.u64 = rex::ppc::divwu(r31.u32, l_r8.u32);
	cr6.compare<uint32_t>(l_r3.u32, r31.u32, xer);
	if (cr6.lt) goto loc_82720948;
	s.Hit(7);
	r30.u64 = r31.u64;
loc_82720948:
	s.Hit(8);
	r28.u64 = r30.u64;
	cr6.compare<uint32_t>(r30.u32, 4, xer);
	if (cr6.lt) goto loc_82720A78;
	s.Hit(9);
	l_r7.u64 = ((uint32_t)(l_r8.u32 << 1));
	BANJO_HOT_STORE_D_U32(l_r1.u32, -144, r29.u32);
	if (s.Stopped()) return true;
	l_r5.u64 = ((uint32_t)(l_r8.u32 << 1));
	BANJO_HOT_STORE_D_U32(l_r1.u32, -160, r11.u32);
	if (s.Stopped()) return true;
	l_r7.u64 = l_r8.u64 + l_r7.u64;
	l_r5.u64 = l_r5.u64 + r11.u64;
	l_r7.u64 = l_r7.u64 + r11.u64;
	BANJO_HOT_STORE_D_U32(l_r1.u32, -152, l_r5.u32);
	if (s.Stopped()) return true;
	l_r5.s64 = l_r1.s64 + -144;
	BANJO_HOT_STORE_D_U32(l_r1.u32, -148, l_r7.u32);
	if (s.Stopped()) return true;
	l_r3.s64 = l_r1.s64 + -160;
	r31.u64 = l_r8.u64 + r11.u64;
	r29.s64 = l_r1.s64 + -128;
	BANJO_HOT_STORE_D_U32(l_r1.u32, -156, r31.u32);
	if (s.Stopped()) return true;
	l_r7.u64 = (r30.u32 >> 2);
	ea = (l_r5.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)l_v61.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	simde_mm_store_si128((simde__m128i*)l_v63.u32, simde_mm_shuffle_epi32(simde_mm_load_si128((simde__m128i*)l_v61.u32), 0xFF));
	temp.u32 = l_r3.u32;
	simde_mm_store_si128((simde__m128i*)l_v0.u8, REX_SHUFFLE_TABLE(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(temp.u32 & ~0xF)), &VectorMaskL[(temp.u32 & 0xF) * 16]));
	l_r3.u64 = ((uint32_t)(l_r8.u32 << 2));
	simde_mm_store_si128((simde__m128i*)l_v60.u8, simde_mm_and_si128(simde_mm_load_si128((simde__m128i*)l_v0.u8), simde_mm_load_si128((simde__m128i*)l_v63.u8)));
	cr6.compare<uint32_t>(l_r7.u32, 0, xer);
	BANJO_HOT_STORE_D_U32(l_r1.u32, -128, l_r3.u32);
	if (s.Stopped()) return true;
	l_r3.u64 = (r30.u32 & 0xFFFFFFFCu);
	ea = (r29.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)l_v62.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	simde_mm_store_si128((simde__m128i*)l_v8.u32, simde_mm_shuffle_epi32(simde_mm_load_si128((simde__m128i*)l_v62.u32), 0xFF));
	r28.u64 = r30.u64 - l_r3.u64;
	ctx.fpscr.enableFlushMode();
	simde_mm_store_ps(l_v12.f32, simde_mm_mul_ps(rex::ppc::simde_mm_cvtepu32_ps_(simde_mm_load_si128((simde__m128i*)l_v60.u32)), simde_mm_castsi128_ps(simde_mm_set1_epi32(int(0x37800000)))));
	if (cr6.eq) goto loc_82720A70;
	s.Hit(10);
	ctr.u64 = l_r7.u64;
	r31.s64 = 16;
	REX_LOOP_IN(ll_r1, l_r1);
	REX_LOOP_IN(ll_r3, l_r3);
	REX_LOOP_IN(ll_r5, l_r5);
	REX_LOOP_IN(ll_r7, l_r7);
	REX_LOOP_IN(ll_r9, l_r9);
	REX_LOOP_IN(ll_r10, l_r10);
	REX_LOOP_IN(ll_v0, l_v0);
	REX_LOOP_IN(ll_v1, l_v1);
	REX_LOOP_IN(ll_v2, l_v2);
	REX_LOOP_IN(ll_v3, l_v3);
	REX_LOOP_IN(ll_v4, l_v4);
	REX_LOOP_IN(ll_v5, l_v5);
	REX_LOOP_IN(ll_v6, l_v6);
	REX_LOOP_IN(ll_v7, l_v7);
	REX_LOOP_IN(ll_v8, l_v8);
	REX_LOOP_IN(ll_v9, l_v9);
	REX_LOOP_IN(ll_v10, l_v10);
	REX_LOOP_IN(ll_v11, l_v11);
	REX_LOOP_IN(ll_v12, l_v12);
	REX_LOOP_IN(ll_v13, l_v13);
	REX_LOOP_IN(ll_v31, l_v31);
	REX_LOOP_IN(ll_v56, l_v56);
	REX_LOOP_IN(ll_v57, l_v57);
	REX_LOOP_IN(ll_v58, l_v58);
	REX_LOOP_IN(ll_v59, l_v59);
	REX_LOOP_IN(ll_v63, l_v63);
loc_827209CC:
	s.Hit(11);
	REX_LOOP_BARRIER();
	ll_r7.u64 = REX_LOAD_D_U32(ll_r1.u32, -156);
	ll_r3.u64 = ((r11.u32 >> 15) & 0x1FFFEu);
	r11.u64 = REX_LOAD_D_U32(ll_r1.u32, -152);
	simde_mm_store_si128((simde__m128i*)ll_v0.u32, rex::ppc::simde_mm_adds_epu32(simde_mm_load_si128((simde__m128i*)ll_v0.u32), simde_mm_load_si128((simde__m128i*)ll_v8.u32)));
	r29.u64 = REX_LOAD_D_U32(ll_r1.u32, -148);
	ll_r5.u64 = ((ll_r7.u32 >> 15) & 0x1FFFEu);
	ll_r7.u64 = ((r11.u32 >> 15) & 0x1FFFEu);
	r11.u64 = ((r29.u32 >> 15) & 0x1FFFEu);
	temp.u32 = ll_r3.u32 + ll_r10.u32;
	simde_mm_store_si128((simde__m128i*)ll_v13.u8, REX_SHUFFLE_TABLE(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(temp.u32 & ~0xF)), &VectorMaskL[(temp.u32 & 0xF) * 16]));
	r29.s64 = ll_r3.s64 + 2;
	ll_r3.s64 = ll_r5.s64 + 2;
	simde_mm_store_si128((simde__m128i*)ll_v59.u8, simde_mm_and_si128(simde_mm_load_si128((simde__m128i*)ll_v0.u8), simde_mm_load_si128((simde__m128i*)ll_v63.u8)));
	temp.u32 = ll_r5.u32 + ll_r10.u32;
	simde_mm_store_si128((simde__m128i*)ll_v10.u8, REX_SHUFFLE_TABLE(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(temp.u32 & ~0xF)), &VectorMaskL[(temp.u32 & 0xF) * 16]));
	ll_r5.s64 = r11.s64 + 2;
	r20.s64 = ll_r7.s64 + 2;
	temp.u32 = ll_r7.u32 + ll_r10.u32;
	simde_mm_store_si128((simde__m128i*)ll_v9.u8, REX_SHUFFLE_TABLE(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(temp.u32 & ~0xF)), &VectorMaskL[(temp.u32 & 0xF) * 16]));
	temp.u32 = r11.u32 + ll_r10.u32;
	simde_mm_store_si128((simde__m128i*)ll_v7.u8, REX_SHUFFLE_TABLE(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(temp.u32 & ~0xF)), &VectorMaskL[(temp.u32 & 0xF) * 16]));
	r11.s64 = ll_r1.s64 + -160;
	simde_mm_store_si128((simde__m128i*)ll_v6.u16, simde_mm_unpackhi_epi16(simde_mm_load_si128((simde__m128i*)ll_v9.u16), simde_mm_load_si128((simde__m128i*)ll_v13.u16)));
	temp.u32 = r29.u32 + ll_r10.u32;
	simde_mm_store_si128((simde__m128i*)ll_v11.u8, REX_SHUFFLE_TABLE(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(temp.u32 & ~0xF)), &VectorMaskL[(temp.u32 & 0xF) * 16]));
	simde_mm_store_si128((simde__m128i*)ll_v5.u16, simde_mm_unpackhi_epi16(simde_mm_load_si128((simde__m128i*)ll_v7.u16), simde_mm_load_si128((simde__m128i*)ll_v10.u16)));
	temp.u32 = ll_r3.u32 + ll_r10.u32;
	simde_mm_store_si128((simde__m128i*)ll_v13.u8, REX_SHUFFLE_TABLE(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(temp.u32 & ~0xF)), &VectorMaskL[(temp.u32 & 0xF) * 16]));
	temp.u32 = ll_r5.u32 + ll_r10.u32;
	simde_mm_store_si128((simde__m128i*)ll_v4.u8, REX_SHUFFLE_TABLE(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(temp.u32 & ~0xF)), &VectorMaskL[(temp.u32 & 0xF) * 16]));
	temp.u32 = r20.u32 + ll_r10.u32;
	simde_mm_store_si128((simde__m128i*)ll_v10.u8, REX_SHUFFLE_TABLE(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(temp.u32 & ~0xF)), &VectorMaskL[(temp.u32 & 0xF) * 16]));
	simde_mm_store_si128((simde__m128i*)ll_v2.u16, simde_mm_unpackhi_epi16(simde_mm_load_si128((simde__m128i*)ll_v4.u16), simde_mm_load_si128((simde__m128i*)ll_v13.u16)));
	ea = (r11.u32) & ~0xF;
	if (s.Note((u32)(ea), 16)) REX_CARD(ea), simde_mm_store_si128((simde__m128i*)REX_RAW_ADDR(ea), REX_BSWAP128(simde_mm_load_si128((simde__m128i*)ll_v0.u8)));
	if (s.Stopped()) return true;
	simde_mm_store_si128((simde__m128i*)ll_v3.u16, simde_mm_unpackhi_epi16(simde_mm_load_si128((simde__m128i*)ll_v10.u16), simde_mm_load_si128((simde__m128i*)ll_v11.u16)));
	simde_mm_store_si128((simde__m128i*)ll_v1.u16, simde_mm_unpackhi_epi16(simde_mm_load_si128((simde__m128i*)ll_v5.u16), simde_mm_load_si128((simde__m128i*)ll_v6.u16)));
	simde_mm_store_si128((simde__m128i*)ll_v31.u16, simde_mm_unpackhi_epi16(simde_mm_load_si128((simde__m128i*)ll_v2.u16), simde_mm_load_si128((simde__m128i*)ll_v3.u16)));
	simde_mm_store_si128((simde__m128i*)ll_v58.s32, simde_mm_cvtepi16_epi32(simde_mm_unpackhi_epi64(simde_mm_load_si128((simde__m128i*)ll_v1.s16), simde_mm_load_si128((simde__m128i*)ll_v1.s16))));
	simde_mm_store_si128((simde__m128i*)ll_v57.s32, simde_mm_cvtepi16_epi32(simde_mm_unpackhi_epi64(simde_mm_load_si128((simde__m128i*)ll_v31.s16), simde_mm_load_si128((simde__m128i*)ll_v31.s16))));
	ctx.fpscr.enableFlushMode();
	simde_mm_store_ps(ll_v13.f32, simde_mm_mul_ps(simde_mm_cvtepi32_ps(simde_mm_load_si128((simde__m128i*)ll_v58.u32)), simde_mm_castsi128_ps(simde_mm_set1_epi32(int(0x38000000)))));
	simde_mm_store_ps(ll_v56.f32, simde_mm_mul_ps(simde_mm_cvtepi32_ps(simde_mm_load_si128((simde__m128i*)ll_v57.u32)), simde_mm_castsi128_ps(simde_mm_set1_epi32(int(0x38000000)))));
	simde_mm_store_ps(ll_v11.f32, simde_mm_sub_ps(simde_mm_load_ps(ll_v56.f32), simde_mm_load_ps(ll_v13.f32)));
	simde_mm_store_ps(ll_v13.f32, REX_VMADDFP(simde_mm_load_ps(ll_v11.f32), simde_mm_load_ps(ll_v12.f32), simde_mm_load_ps(ll_v13.f32)));
	simde_mm_store_ps(ll_v12.f32, simde_mm_mul_ps(rex::ppc::simde_mm_cvtepu32_ps_(simde_mm_load_si128((simde__m128i*)ll_v59.u32)), simde_mm_castsi128_ps(simde_mm_set1_epi32(int(0x37800000)))));
	ea = ll_r9.u32;
	if (r31.u32 == 16u && detail::Straight(ea, 16u)) [[likely]] {
		// sasrt-nx: stvlx at ea and stvrx at ea + 16 write the vector's 16 bytes to [ea, ea + 16) in guest order (the
		// first the bytes up to the next 16-byte boundary, the second those from it): one store, the same two cards.
		if (s.Note((u32)(ea), 16u)) {
			simde_mm_storeu_si128((simde__m128i*)REX_RAW_ADDR(ea), REX_BSWAP128(simde_mm_load_si128((simde__m128i*)ll_v13.u8)));
			REX_CARD(ea);
			REX_CARD(ea + 16u);
		}
		if (s.Stopped()) return true;
		ea = ll_r9.u32 + r31.u32;
	} else {
		ea = ll_r9.u32;
		if (s.Note((u32)(ea), 16u - ((u32)(ea) & 0xFu))) REX_STVLX_C(ea, ll_v13);
		if (s.Stopped()) return true;
		ea = ll_r9.u32 + r31.u32;
		if (s.Note((u32)(ea) & ~0xFu, (u32)(ea) & 0xFu)) REX_STVRX_C(ea, ll_v13);
		if (s.Stopped()) return true;
	}
	r11.u64 = REX_LOAD_D_U32(ll_r1.u32, -160);
	ll_r9.s64 = ll_r9.s64 + 16;
	--ctr.u64;
	if (ctr.u32 != 0) goto loc_827209CC;
	s.Hit(12);
	REX_LOOP_OUT(ll_r3, l_r3);
	REX_LOOP_OUT(ll_r5, l_r5);
	REX_LOOP_OUT(ll_r7, l_r7);
	REX_LOOP_OUT(ll_r9, l_r9);
	REX_LOOP_OUT(ll_v0, l_v0);
	REX_LOOP_OUT(ll_v1, l_v1);
	REX_LOOP_OUT(ll_v2, l_v2);
	REX_LOOP_OUT(ll_v3, l_v3);
	REX_LOOP_OUT(ll_v4, l_v4);
	REX_LOOP_OUT(ll_v5, l_v5);
	REX_LOOP_OUT(ll_v6, l_v6);
	REX_LOOP_OUT(ll_v7, l_v7);
	REX_LOOP_OUT(ll_v8, l_v8);
	REX_LOOP_OUT(ll_v9, l_v9);
	REX_LOOP_OUT(ll_v10, l_v10);
	REX_LOOP_OUT(ll_v11, l_v11);
	REX_LOOP_OUT(ll_v12, l_v12);
	REX_LOOP_OUT(ll_v13, l_v13);
	REX_LOOP_OUT(ll_v31, l_v31);
	REX_LOOP_OUT(ll_v56, l_v56);
	REX_LOOP_OUT(ll_v57, l_v57);
	REX_LOOP_OUT(ll_v58, l_v58);
	REX_LOOP_OUT(ll_v59, l_v59);
	REX_LOOP_OUT(ll_v63, l_v63);
loc_82720A70:
	s.Hit(13);
	l_r5.u64 = (r11.u32 >> 16);
	l_r7.u64 = r11.u32 & 0xFFFF;
loc_82720A78:
	s.Hit(14);
	cr6.compare<uint32_t>(r28.u32, 0, xer);
	if (cr6.eq) goto loc_82720ADC;
	s.Hit(15);
	ctr.u64 = r28.u64;
	l_r3.s64 = l_r9.s64 + -4;
	REX_LOOP_IN(ll_f10, l_f10);
	REX_LOOP_IN(ll_f11, l_f11);
	REX_LOOP_IN(ll_f12, l_f12);
	REX_LOOP_IN(ll_f13, l_f13);
	REX_LOOP_IN(ll_r1, l_r1);
	REX_LOOP_IN(ll_r3, l_r3);
	REX_LOOP_IN(ll_r5, l_r5);
	REX_LOOP_IN(ll_r7, l_r7);
	REX_LOOP_IN(ll_r8, l_r8);
	REX_LOOP_IN(ll_r9, l_r9);
	REX_LOOP_IN(ll_r10, l_r10);
loc_82720A88:
	s.Hit(16);
	REX_LOOP_BARRIER();
	ll_r9.u64 = ((uint32_t)(ll_r5.u32 << 1));
	r11.u64 = ll_r8.u64 + r11.u64;
	ll_r9.u64 = ll_r9.u64 + ll_r10.u64;
	ll_r5.u64 = (r11.u32 >> 16);
	r31.u64 = REX_LOAD_D_U16(ll_r9.u32, 0);
	ll_r9.u64 = REX_LOAD_D_U16(ll_r9.u32, 2);
	r29.s64 = r31.s16;
	ll_r9.s64 = ll_r9.s16;
	r31.u64 = __builtin_rotateleft32(r31.u32, 16);
	ll_r9.u64 = ll_r9.u64 - r29.u64;
	ll_r9.s64 = int64_t(ll_r9.s32) * int64_t(ll_r7.s32);
	ll_r9.u64 = ll_r9.u64 + r31.u64;
	ll_r7.u64 = r11.u32 & 0xFFFF;
	ll_r9.s64 = ll_r9.s32;
	BANJO_HOT_STORE_D_U64(ll_r1.u32, -160, ll_r9.u64);
	if (s.Stopped()) return true;
	ll_f13.u64 = REX_LOAD_D_U64(ll_r1.u32, -160);
	ll_f12.f64 = double(ll_f13.s64);
	ctx.fpscr.disableFlushMode();
	ll_f11.f64 = double(float(ll_f12.f64));
	ll_f10.f64 = double(float(ll_f11.f64 * f0.f64));
	ea = 4 + ll_r3.u32;
	temp.f32 = float(ll_f10.f64);
	BANJO_HOT_STORE_U32_C(ea, temp.u32);
	if (s.Stopped()) return true;
	ll_r3.u32 = ea;
	--ctr.u64;
	if (ctr.u32 != 0) goto loc_82720A88;
	s.Hit(17);
	REX_LOOP_OUT(ll_f10, l_f10);
	REX_LOOP_OUT(ll_f11, l_f11);
	REX_LOOP_OUT(ll_f12, l_f12);
	REX_LOOP_OUT(ll_f13, l_f13);
	REX_LOOP_OUT(ll_r3, l_r3);
	REX_LOOP_OUT(ll_r5, l_r5);
	REX_LOOP_OUT(ll_r7, l_r7);
	REX_LOOP_OUT(ll_r9, l_r9);
loc_82720ADC:
	s.Hit(18);
	cr6.compare<uint32_t>(l_r5.u32, r25.u32, xer);
	if (cr6.lt) goto loc_82720AE8;
	s.Hit(19);
	l_r5.u64 = r25.u64;
loc_82720AE8:
	s.Hit(20);
	cr6.compare<uint32_t>(l_r5.u32, 0, xer);
	if (cr6.eq) goto loc_82720AFC;
	s.Hit(21);
	l_r9.u64 = ((uint32_t)(l_r5.u32 << 1));
	l_r8.u64 = REX_LOAD_U16(l_r9.u32 + l_r10.u32);
	BANJO_HOT_STORE_D_U16_C(l_r6.u32, 0, l_r8.u16);
	if (s.Stopped()) return true;
loc_82720AFC:
	s.Hit(22);
	l_r9.u64 = ((uint32_t)(l_r5.u32 << 16));
	l_r10.u64 = r30.u64 + r27.u64;
	l_r8.u64 = r11.u64 - l_r9.u64;
	cr6.compare<uint32_t>(l_r5.u32, r25.u32, xer);
	BANJO_HOT_STORE_D_U32_C(r24.u32, 0, l_r8.u32);
	if (s.Stopped()) return true;
	l_r7.u64 = REX_LOAD_D_U16(r26.u32, 0);
	l_r6.u64 = l_r7.u64 - l_r5.u64;
	BANJO_HOT_STORE_D_U16_C(r26.u32, 0, l_r6.u16);
	if (s.Stopped()) return true;
	r11.u64 = REX_LOAD_D_U32(r23.u32, 0);
	r11.u64 = l_r10.u64 + r11.u64;
	BANJO_HOT_STORE_D_U16_C(l_r4.u32, 14, r11.u16);
	if (s.Stopped()) return true;
	if (!cr6.eq) goto loc_82720B34;
	s.Hit(23);
	r11.s64 = 0;
	goto loc_82720B3C;
loc_82720B34:
	s.Hit(24);
	r11.u64 = REX_LOAD_D_U32(r22.u32, 0);
	r11.u64 = l_r5.u64 + r11.u64;
loc_82720B3C:
	s.Hit(25);
	BANJO_HOT_STORE_D_U32_C(r22.u32, 0, r11.u32);
	if (s.Stopped()) return true;
	cr6.compare<uint32_t>(l_r10.u32, r21.u32, xer);
	if (!cr6.eq) goto loc_82720B50;
	s.Hit(26);
	l_r3.s64 = 45;
	{ ctx.f10 = l_f10; ctx.f11 = l_f11; ctx.f12 = l_f12; ctx.f13 = l_f13; ctx.r3 = l_r3; ctx.r5 = l_r5; ctx.r6 = l_r6; ctx.r7 = l_r7; ctx.r8 = l_r8; ctx.r9 = l_r9; ctx.r10 = l_r10; ctx.v0 = l_v0; ctx.v1 = l_v1; ctx.v2 = l_v2; ctx.v3 = l_v3; ctx.v4 = l_v4; ctx.v5 = l_v5; ctx.v6 = l_v6; ctx.v7 = l_v7; ctx.v8 = l_v8; ctx.v9 = l_v9; ctx.v10 = l_v10; ctx.v11 = l_v11; ctx.v12 = l_v12; ctx.v13 = l_v13; ctx.v31 = l_v31; ctx.v56 = l_v56; ctx.v57 = l_v57; ctx.v58 = l_v58; ctx.v59 = l_v59; ctx.v60 = l_v60; ctx.v61 = l_v61; ctx.v62 = l_v62; ctx.v63 = l_v63; return true; }
loc_82720B50:
	s.Hit(27);
	r11.u64 = REX_LOAD_D_U32(r23.u32, 0);
	l_r3.s64 = 43;
	r11.u64 = l_r10.u64 + r11.u64;
	BANJO_HOT_STORE_D_U32_C(r23.u32, 0, r11.u32);
	if (s.Stopped()) return true;
	{ ctx.f10 = l_f10; ctx.f11 = l_f11; ctx.f12 = l_f12; ctx.f13 = l_f13; ctx.r3 = l_r3; ctx.r5 = l_r5; ctx.r6 = l_r6; ctx.r7 = l_r7; ctx.r8 = l_r8; ctx.r9 = l_r9; ctx.r10 = l_r10; ctx.v0 = l_v0; ctx.v1 = l_v1; ctx.v2 = l_v2; ctx.v3 = l_v3; ctx.v4 = l_v4; ctx.v5 = l_v5; ctx.v6 = l_v6; ctx.v7 = l_v7; ctx.v8 = l_v8; ctx.v9 = l_v9; ctx.v10 = l_v10; ctx.v11 = l_v11; ctx.v12 = l_v12; ctx.v13 = l_v13; ctx.v31 = l_v31; ctx.v56 = l_v56; ctx.v57 = l_v57; ctx.v58 = l_v58; ctx.v59 = l_v59; ctx.v60 = l_v60; ctx.v61 = l_v61; ctx.v62 = l_v62; ctx.v63 = l_v63; return true; }
	return true;
}

}  // namespace n_82720840


// ---------------------------------------------------------------------------------------------------------------
// sub_8286C230 - the water surface simulation step (WaterThread; the hottest guest function of the stock-clock console
// profile: 2.3 % of all guest samples, 31 % of its thread's). The samples (tools/switch_hot_pcs.py, 207 in the
// function): 32 in the vector square-root / divide chain at +0x180 (latency the exact form needs: not removable), and
// about 70 between +0x1100 and +0x1280: the game's misaligned vector store idiom, four times per step (vperm by the
// address's lvsr, then four stvewx at ea, ea+4, ea+8, ea+12, each storing the lane its address selects); the generated
// code spills the vector to the stack and loads each lane back by a computed index, byte-swaps it, stores it and marks
// its store card, four times. This native is the machine copy's own statements (tools/localize_native.py's
// f_sub_8286C230, registers in locals) with each such group as one 16-byte store of the same four words (the lanes
// rotated by the address, detail::StoreWordsOfVector) and the same four card marks. A group whose offsets are not the
// constants 4 / 8 / 12, or whose range crosses the PC's physical-view boundary, stores as before.
namespace n_8286C230 {

template <class S>
[[gnu::always_inline]] inline bool Native(PPCContext& __restrict ctx, uint8_t* base, [[maybe_unused]] S& s) {
  if (!On(k_sasrt_hand_water_step)) [[unlikely]] return false;
	PPCRegister l_f10 = ctx.f10;
	PPCRegister l_f11 = ctx.f11;
	PPCRegister l_f12 = ctx.f12;
	PPCRegister l_f13 = ctx.f13;
	PPCRegister l_r1 = ctx.r1;
	PPCRegister l_r3 = ctx.r3;
	PPCRegister l_r4 = ctx.r4;
	PPCRegister l_r5 = ctx.r5;
	PPCRegister l_r6 = ctx.r6;
	PPCRegister l_r7 = ctx.r7;
	PPCRegister l_r8 = ctx.r8;
	PPCRegister l_r9 = ctx.r9;
	PPCRegister l_r10 = ctx.r10;
	PPCVRegister l_v0 = ctx.v0;
	PPCVRegister l_v1 = ctx.v1;
	PPCVRegister l_v2 = ctx.v2;
	PPCVRegister l_v3 = ctx.v3;
	PPCVRegister l_v4 = ctx.v4;
	PPCVRegister l_v5 = ctx.v5;
	PPCVRegister l_v6 = ctx.v6;
	PPCVRegister l_v7 = ctx.v7;
	PPCVRegister l_v8 = ctx.v8;
	PPCVRegister l_v9 = ctx.v9;
	PPCVRegister l_v10 = ctx.v10;
	PPCVRegister l_v11 = ctx.v11;
	PPCVRegister l_v12 = ctx.v12;
	PPCVRegister l_v13 = ctx.v13;
	PPCVRegister l_v14 = ctx.v14;
	PPCVRegister l_v15 = ctx.v15;
	PPCVRegister l_v16 = ctx.v16;
	PPCVRegister l_v17 = ctx.v17;
	PPCVRegister l_v18 = ctx.v18;
	PPCVRegister l_v19 = ctx.v19;
	PPCVRegister l_v20 = ctx.v20;
	PPCVRegister l_v21 = ctx.v21;
	PPCVRegister l_v22 = ctx.v22;
	PPCVRegister l_v23 = ctx.v23;
	PPCVRegister l_v24 = ctx.v24;
	PPCVRegister l_v25 = ctx.v25;
	PPCVRegister l_v26 = ctx.v26;
	PPCVRegister l_v27 = ctx.v27;
	PPCVRegister l_v28 = ctx.v28;
	PPCVRegister l_v29 = ctx.v29;
	PPCVRegister l_v30 = ctx.v30;
	PPCVRegister l_v31 = ctx.v31;
	PPCVRegister l_v32 = ctx.v32;
	PPCVRegister l_v33 = ctx.v33;
	PPCVRegister l_v34 = ctx.v34;
	PPCVRegister l_v35 = ctx.v35;
	PPCVRegister l_v36 = ctx.v36;
	PPCVRegister l_v37 = ctx.v37;
	PPCVRegister l_v38 = ctx.v38;
	PPCVRegister l_v39 = ctx.v39;
	PPCVRegister l_v40 = ctx.v40;
	PPCVRegister l_v41 = ctx.v41;
	PPCVRegister l_v42 = ctx.v42;
	PPCVRegister l_v43 = ctx.v43;
	PPCVRegister l_v44 = ctx.v44;
	PPCVRegister l_v45 = ctx.v45;
	PPCVRegister l_v46 = ctx.v46;
	PPCVRegister l_v47 = ctx.v47;
	PPCVRegister l_v48 = ctx.v48;
	PPCVRegister l_v49 = ctx.v49;
	PPCVRegister l_v50 = ctx.v50;
	PPCVRegister l_v51 = ctx.v51;
	PPCVRegister l_v52 = ctx.v52;
	PPCVRegister l_v53 = ctx.v53;
	PPCVRegister l_v54 = ctx.v54;
	PPCVRegister l_v55 = ctx.v55;
	PPCVRegister l_v56 = ctx.v56;
	PPCVRegister l_v57 = ctx.v57;
	PPCVRegister l_v58 = ctx.v58;
	PPCVRegister l_v59 = ctx.v59;
	PPCVRegister l_v60 = ctx.v60;
	PPCVRegister l_v61 = ctx.v61;
	PPCVRegister l_v62 = ctx.v62;
	PPCVRegister l_v63 = ctx.v63;
	s.Hit(0);
	REX_FUNC_PROLOGUE();
	REX_LOOP_LOCAL(PPCRegister, ll_f11, l_f11);
	REX_LOOP_LOCAL(PPCRegister, ll_f12, l_f12);
	REX_LOOP_LOCAL(PPCRegister, ll_f13, l_f13);
	REX_LOOP_LOCAL(PPCRegister, ll_r1, l_r1);
	REX_LOOP_LOCAL(PPCRegister, ll_r3, l_r3);
	REX_LOOP_LOCAL(PPCRegister, ll_r4, l_r4);
	REX_LOOP_LOCAL(PPCRegister, ll_r5, l_r5);
	REX_LOOP_LOCAL(PPCRegister, ll_r6, l_r6);
	REX_LOOP_LOCAL(PPCRegister, ll_r7, l_r7);
	REX_LOOP_LOCAL(PPCRegister, ll_r8, l_r8);
	REX_LOOP_LOCAL(PPCRegister, ll_r9, l_r9);
	REX_LOOP_LOCAL(PPCRegister, ll_r10, l_r10);
	REX_LOOP_LOCAL(PPCVRegister, ll_v0, l_v0);
	REX_LOOP_LOCAL(PPCVRegister, ll_v1, l_v1);
	REX_LOOP_LOCAL(PPCVRegister, ll_v2, l_v2);
	REX_LOOP_LOCAL(PPCVRegister, ll_v3, l_v3);
	REX_LOOP_LOCAL(PPCVRegister, ll_v4, l_v4);
	REX_LOOP_LOCAL(PPCVRegister, ll_v5, l_v5);
	REX_LOOP_LOCAL(PPCVRegister, ll_v6, l_v6);
	REX_LOOP_LOCAL(PPCVRegister, ll_v7, l_v7);
	REX_LOOP_LOCAL(PPCVRegister, ll_v8, l_v8);
	REX_LOOP_LOCAL(PPCVRegister, ll_v9, l_v9);
	REX_LOOP_LOCAL(PPCVRegister, ll_v10, l_v10);
	REX_LOOP_LOCAL(PPCVRegister, ll_v11, l_v11);
	REX_LOOP_LOCAL(PPCVRegister, ll_v12, l_v12);
	REX_LOOP_LOCAL(PPCVRegister, ll_v13, l_v13);
	REX_LOOP_LOCAL(PPCVRegister, ll_v14, l_v14);
	REX_LOOP_LOCAL(PPCVRegister, ll_v15, l_v15);
	REX_LOOP_LOCAL(PPCVRegister, ll_v16, l_v16);
	REX_LOOP_LOCAL(PPCVRegister, ll_v17, l_v17);
	REX_LOOP_LOCAL(PPCVRegister, ll_v18, l_v18);
	REX_LOOP_LOCAL(PPCVRegister, ll_v19, l_v19);
	REX_LOOP_LOCAL(PPCVRegister, ll_v20, l_v20);
	REX_LOOP_LOCAL(PPCVRegister, ll_v21, l_v21);
	REX_LOOP_LOCAL(PPCVRegister, ll_v22, l_v22);
	REX_LOOP_LOCAL(PPCVRegister, ll_v23, l_v23);
	REX_LOOP_LOCAL(PPCVRegister, ll_v24, l_v24);
	REX_LOOP_LOCAL(PPCVRegister, ll_v25, l_v25);
	REX_LOOP_LOCAL(PPCVRegister, ll_v26, l_v26);
	REX_LOOP_LOCAL(PPCVRegister, ll_v27, l_v27);
	REX_LOOP_LOCAL(PPCVRegister, ll_v28, l_v28);
	REX_LOOP_LOCAL(PPCVRegister, ll_v29, l_v29);
	REX_LOOP_LOCAL(PPCVRegister, ll_v30, l_v30);
	REX_LOOP_LOCAL(PPCVRegister, ll_v31, l_v31);
	REX_LOOP_LOCAL(PPCVRegister, ll_v32, l_v32);
	REX_LOOP_LOCAL(PPCVRegister, ll_v33, l_v33);
	REX_LOOP_LOCAL(PPCVRegister, ll_v34, l_v34);
	REX_LOOP_LOCAL(PPCVRegister, ll_v35, l_v35);
	REX_LOOP_LOCAL(PPCVRegister, ll_v36, l_v36);
	REX_LOOP_LOCAL(PPCVRegister, ll_v37, l_v37);
	REX_LOOP_LOCAL(PPCVRegister, ll_v38, l_v38);
	REX_LOOP_LOCAL(PPCVRegister, ll_v39, l_v39);
	REX_LOOP_LOCAL(PPCVRegister, ll_v40, l_v40);
	REX_LOOP_LOCAL(PPCVRegister, ll_v41, l_v41);
	REX_LOOP_LOCAL(PPCVRegister, ll_v42, l_v42);
	REX_LOOP_LOCAL(PPCVRegister, ll_v43, l_v43);
	REX_LOOP_LOCAL(PPCVRegister, ll_v44, l_v44);
	REX_LOOP_LOCAL(PPCVRegister, ll_v45, l_v45);
	REX_LOOP_LOCAL(PPCVRegister, ll_v46, l_v46);
	REX_LOOP_LOCAL(PPCVRegister, ll_v47, l_v47);
	REX_LOOP_LOCAL(PPCVRegister, ll_v48, l_v48);
	REX_LOOP_LOCAL(PPCVRegister, ll_v49, l_v49);
	REX_LOOP_LOCAL(PPCVRegister, ll_v50, l_v50);
	REX_LOOP_LOCAL(PPCVRegister, ll_v51, l_v51);
	REX_LOOP_LOCAL(PPCVRegister, ll_v52, l_v52);
	REX_LOOP_LOCAL(PPCVRegister, ll_v53, l_v53);
	REX_LOOP_LOCAL(PPCVRegister, ll_v54, l_v54);
	REX_LOOP_LOCAL(PPCVRegister, ll_v55, l_v55);
	REX_LOOP_LOCAL(PPCVRegister, ll_v56, l_v56);
	REX_LOOP_LOCAL(PPCVRegister, ll_v57, l_v57);
	REX_LOOP_LOCAL(PPCVRegister, ll_v58, l_v58);
	REX_LOOP_LOCAL(PPCVRegister, ll_v59, l_v59);
	REX_LOOP_LOCAL(PPCVRegister, ll_v60, l_v60);
	REX_LOOP_LOCAL(PPCVRegister, ll_v61, l_v61);
	REX_LOOP_LOCAL(PPCVRegister, ll_v62, l_v62);
	REX_LOOP_LOCAL(PPCVRegister, ll_v63, l_v63);
	PPCRegister ctr{};
	PPCXERRegister xer{};
	PPCCRRegister cr0{};
	PPCCRRegister cr6{};
	PPCRegister r11{};
	PPCRegister r12{};
	PPCRegister r19{};
	PPCRegister r20{};
	PPCRegister r21{};
	PPCRegister r22{};
	PPCRegister r23{};
	PPCRegister r24{};
	PPCRegister r25{};
	PPCRegister r26{};
	PPCRegister r27{};
	PPCRegister r28{};
	PPCRegister r29{};
	PPCRegister r30{};
	PPCRegister r31{};
	PPCRegister f0{};
	PPCRegister temp{};
	PPCVRegister vTemp{};
	uint32_t ea{};
	r12.u64 = ctx.lr;
	ea = -352 + l_r1.u32;
	REX_CHAIN_STORE(BANJO_HOT_STORE_U32(ea, l_r1.u32));
	if (s.Stopped()) return true;
	l_r1.u32 = ea;
	l_r10.s64 = -2095644672;
	l_r9.u64 = REX_LOAD_D_U32(l_r4.u32, 16);
	r11.s64 = -2113798144;
	BANJO_HOT_STORE_D_U32(l_r1.u32, 380, l_r4.u32);
	if (s.Stopped()) return true;
	l_r8.s64 = -2113142784;
	r20.s64 = r11.s64 + -31312;
	l_r8.s64 = l_r8.s64 + 20976;
	r31.u64 = REX_LOAD_D_U32(l_r10.u32, -5760);
	r30.s64 = 80;
	r11.s64 = -2113929216;
	r29.s64 = 0;
	r19.s64 = r11.s64 + 23260;
	ea = (r20.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)l_v10.u8, REX_RO_V128(0x820185B0, 0x3F8000003F800000ull, 0x3F8000003F800000ull));
	l_r10.u64 = r29.u64;
	simde_mm_store_si128((simde__m128i*)l_v56.u8, simde_mm_load_si128((simde__m128i*)l_v10.u8));
	ea = (l_r8.u32 + r30.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)l_v7.u8, REX_RO_V128(0x820C5240, 0xFFFFFFFF00000000ull, 0xFFFFFFFF00000000ull));
	BANJO_HOT_STORE_D_U32(l_r1.u32, 84, r19.u32);
	if (s.Stopped()) return true;
	cr6.compare<uint32_t>(l_r9.u32, 0, xer);
	BANJO_HOT_STORE_D_U32(l_r1.u32, 224, r31.u32);
	if (s.Stopped()) return true;
	if (!cr6.gt) goto loc_8286C300;
	s.Hit(1);
	simde_mm_store_si128((simde__m128i*)l_v62.u32, simde_mm_set1_epi32(int(0x0)));
	temp.u32 = r19.u32;
	simde_mm_store_si128((simde__m128i*)l_v61.u8, REX_SHUFFLE_TABLE(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(temp.u32 & ~0xF)), &VectorMaskL[(temp.u32 & 0xF) * 16]));
	r11.u64 = r29.u64;
	simde_mm_store_si128((simde__m128i*)l_v63.u32, simde_mm_shuffle_epi32(simde_mm_load_si128((simde__m128i*)l_v61.u32), 0xFF));
	vTemp.u32[0] = l_v62.u8[3] | 0x3F800000;
	vTemp.u32[1] = l_v62.u8[0] | 0x3F800000;
	vTemp.u32[2] = l_v62.u8[1] | 0x3F800000;
	vTemp.u32[3] = l_v62.u8[2] | 0x3F800000;
	l_v8 = vTemp;
	REX_LOOP_IN(ll_r4, l_r4);
	REX_LOOP_IN(ll_r8, l_r8);
	REX_LOOP_IN(ll_r9, l_r9);
	REX_LOOP_IN(ll_r10, l_r10);
	REX_LOOP_IN(ll_v0, l_v0);
	REX_LOOP_IN(ll_v7, l_v7);
	REX_LOOP_IN(ll_v8, l_v8);
	REX_LOOP_IN(ll_v9, l_v9);
	REX_LOOP_IN(ll_v10, l_v10);
	REX_LOOP_IN(ll_v11, l_v11);
	REX_LOOP_IN(ll_v12, l_v12);
	REX_LOOP_IN(ll_v13, l_v13);
	REX_LOOP_IN(ll_v56, l_v56);
	REX_LOOP_IN(ll_v58, l_v58);
	REX_LOOP_IN(ll_v59, l_v59);
	REX_LOOP_IN(ll_v60, l_v60);
	REX_LOOP_IN(ll_v63, l_v63);
loc_8286C2A0:
	s.Hit(2);
	REX_LOOP_BARRIER();
	ll_r9.u64 = REX_LOAD_D_U32(ll_r4.u32, 24);
	simde_mm_store_si128((simde__m128i*)ll_v13.u8, simde_mm_load_si128((simde__m128i*)ll_v56.u8));
	ll_r8.u64 = REX_LOAD_D_U32(ll_r4.u32, 20);
	ll_r10.s64 = ll_r10.s64 + 1;
	ll_r9.u64 = ll_r9.u64 + r11.u64;
	ea = (ll_r9.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v0.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	simde_mm_store_si128((simde__m128i*)ll_v12.u8, simde_mm_load_si128((simde__m128i*)ll_v0.u8));
	ctx.fpscr.enableFlushMode();
	simde_mm_store_ps(ll_v0.f32, REX_VMADDFP(simde_mm_load_ps(ll_v0.f32), simde_mm_load_ps(ll_v0.f32), simde_mm_load_ps(ll_v10.f32)));
	simde_mm_store_si128((simde__m128i*)ll_v11.u8, REX_VSEL(simde_mm_load_si128((simde__m128i*)ll_v7.u8), simde_mm_load_si128((simde__m128i*)ll_v13.u8), simde_mm_load_si128((simde__m128i*)ll_v12.u8)));
	simde_mm_store_si128((simde__m128i*)ll_v60.u8, simde_mm_load_si128((simde__m128i*)ll_v0.u8));
	simde_mm_store_ps(ll_v0.f32, REX_VRSQRTEFP(simde_mm_load_ps(ll_v60.f32)));
	simde_mm_store_si128((simde__m128i*)ll_v13.u8, simde_mm_load_si128((simde__m128i*)ll_v60.u8));
	simde_mm_store_ps(ll_v12.f32, simde_mm_mul_ps(simde_mm_load_ps(ll_v0.f32), simde_mm_load_ps(ll_v0.f32)));
	simde_mm_store_ps(ll_v9.f32, simde_mm_mul_ps(simde_mm_load_ps(ll_v0.f32), simde_mm_load_ps(ll_v63.f32)));
	simde_mm_store_ps(ll_v10.f32, REX_VNMSUBFP(simde_mm_load_ps(ll_v13.f32), simde_mm_load_ps(ll_v12.f32), simde_mm_load_ps(ll_v8.f32)));
	simde_mm_store_ps(ll_v0.f32, REX_VMADDFP(simde_mm_load_ps(ll_v10.f32), simde_mm_load_ps(ll_v9.f32), simde_mm_load_ps(ll_v0.f32)));
	simde_mm_store_si128((simde__m128i*)ll_v59.u32, simde_mm_shuffle_epi32(simde_mm_load_si128((simde__m128i*)ll_v0.u32), 0xF5));
	simde_mm_store_ps(ll_v58.f32, simde_mm_mul_ps(simde_mm_load_ps(ll_v11.f32), simde_mm_load_ps(ll_v59.f32)));
	ea = (r11.u32 + ll_r8.u32) & ~0xF;
	if (s.Note((u32)(ea), 16)) REX_CARD(ea), simde_mm_store_si128((simde__m128i*)REX_RAW_ADDR(ea), REX_BSWAP128(simde_mm_load_si128((simde__m128i*)ll_v58.u8)));
	if (s.Stopped()) return true;
	ll_r9.u64 = REX_LOAD_D_U32(ll_r4.u32, 16);
	ea = (r20.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v10.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	r11.s64 = r11.s64 + 16;
	cr6.compare<uint32_t>(ll_r10.u32, ll_r9.u32, xer);
	if (cr6.lt) goto loc_8286C2A0;
	s.Hit(3);
	REX_LOOP_OUT(ll_r8, l_r8);
	REX_LOOP_OUT(ll_r9, l_r9);
	REX_LOOP_OUT(ll_r10, l_r10);
	REX_LOOP_OUT(ll_v0, l_v0);
	REX_LOOP_OUT(ll_v7, l_v7);
	REX_LOOP_OUT(ll_v8, l_v8);
	REX_LOOP_OUT(ll_v9, l_v9);
	REX_LOOP_OUT(ll_v10, l_v10);
	REX_LOOP_OUT(ll_v11, l_v11);
	REX_LOOP_OUT(ll_v12, l_v12);
	REX_LOOP_OUT(ll_v13, l_v13);
	REX_LOOP_OUT(ll_v56, l_v56);
	REX_LOOP_OUT(ll_v58, l_v58);
	REX_LOOP_OUT(ll_v59, l_v59);
	REX_LOOP_OUT(ll_v60, l_v60);
	REX_LOOP_OUT(ll_v63, l_v63);
loc_8286C300:
	s.Hit(4);
	r21.s64 = l_r5.s64 + 36;
	ctx.fpscr.disableFlushMode();
	f0.f64 = double(REX_LOAD_D_F32(l_r5.u32, 16));
	l_r9.s64 = -2113929216;
	l_r10.s64 = -2113798144;
	BANJO_HOT_STORE_D_U32(l_r1.u32, 88, r21.u32);
	if (s.Stopped()) return true;
	r26.s64 = 1;
	r22.s64 = l_r5.s64 + 16;
	r11.u64 = REX_LOAD_D_U32(r21.u32, 0);
	r23.s64 = l_r10.s64 + -31264;
	temp.u32 = REX_RO_U32(0x82002490, 0x3F800000);
	l_f13.f64 = double(temp.f32);
	r28.s64 = r11.s64 + 1;
	cr6.compare(f0.f64, l_f13.f64);
	if (!cr6.lt) goto loc_8286C438;
	s.Hit(5);
	temp.u32 = r22.u32;
	simde_mm_store_si128((simde__m128i*)l_v57.u8, REX_SHUFFLE_TABLE(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(temp.u32 & ~0xF)), &VectorMaskL[(temp.u32 & 0xF) * 16]));
	l_r10.u64 = REX_LOAD_D_U32(l_r4.u32, 24);
	r11.u64 = ((uint32_t)(r28.u32 << 4));
	l_r9.u64 = REX_LOAD_D_U32(l_r4.u32, 20);
	simde_mm_store_si128((simde__m128i*)l_v63.u32, simde_mm_shuffle_epi32(simde_mm_load_si128((simde__m128i*)l_v57.u32), 0xFF));
	r27.s64 = r28.s64 + -1;
	l_r10.u64 = l_r10.u64 + r11.u64;
	ea = (r23.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)l_v55.u8, REX_RO_V128(0x820185E0, 0x3F0000003F000000ull, 0x3F0000003F000000ull));
	l_r9.u64 = l_r9.u64 + r11.u64;
	r11.s64 = l_r10.s64 + 16;
	ctx.fpscr.enableFlushModeUnconditional();
	simde_mm_store_ps(l_v54.f32, simde_mm_sub_ps(simde_mm_load_ps(l_v10.f32), simde_mm_load_ps(l_v63.f32)));
	l_r10.s64 = l_r9.s64 + 16;
	l_r8.u64 = r26.u64;
	cr6.compare<int32_t>(r27.s32, 1, xer);
	simde_mm_store_ps(l_v0.f32, simde_mm_mul_ps(simde_mm_load_ps(l_v54.f32), simde_mm_load_ps(l_v55.f32)));
	if (!cr6.gt) goto loc_8286C438;
	s.Hit(6);
	REX_LOOP_IN(ll_r8, l_r8);
	REX_LOOP_IN(ll_r9, l_r9);
	REX_LOOP_IN(ll_r10, l_r10);
	REX_LOOP_IN(ll_v0, l_v0);
	REX_LOOP_IN(ll_v12, l_v12);
	REX_LOOP_IN(ll_v13, l_v13);
	REX_LOOP_IN(ll_v52, l_v52);
	REX_LOOP_IN(ll_v53, l_v53);
	REX_LOOP_IN(ll_v63, l_v63);
loc_8286C374:
	s.Hit(7);
	REX_LOOP_BARRIER();
	r31.s64 = r27.s64 + -1;
	ll_r9.u64 = r26.u64;
	ctr.u64 = r31.u64;
loc_8286C380:
	s.Hit(8);
	REX_LOOP_BARRIER();
	r31.u64 = ll_r9.u64 | ll_r8.u64;
	r31.u64 = r31.u32 & 0x1;
	cr6.compare<int32_t>(r31.s32, 0, xer);
	if (cr6.eq) goto loc_8286C410;
	s.Hit(9);
	r30.u64 = ll_r9.u64 & ll_r8.u64;
	ea = (r11.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v53.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	r31.u64 = ll_r8.u32 & 0x1;
	REX_FLUSH_KNOWN_ON();
	simde_mm_store_ps(ll_v13.f32, simde_mm_mul_ps(simde_mm_load_ps(ll_v53.f32), simde_mm_load_ps(ll_v63.f32)));
	r30.u64 = ((uint32_t)(r30.u32 << 1) & 0x2u);
	r25.u64 = ll_r9.u64 ^ ll_r8.u64;
	xer.ca = r31.u32 <= 0;
	r31.u64 = static_cast<uint64_t>(0) - r31.u64;
	r30.u64 = r30.u64 & r25.u64;
	temp.u8 = (~r31.u32 + r31.u32 < ~r31.u32) | (~r31.u32 + r31.u32 + xer.ca < xer.ca);
	r31.u64 = ~r31.u64 + r31.u64 + xer.ca;
	xer.ca = temp.u8;
	r25.u64 = ll_r9.u32 & 0x1;
	r31.u64 = r31.u64 & r28.u64;
	r30.u64 = r25.u64 - r30.u64;
	r31.u64 = r30.u64 + r31.u64;
	r31.u64 = ((uint32_t)(r31.u32 << 4));
	ea = (r11.u32) & ~0xF;
	if (s.Note((u32)(ea), 16)) REX_CARD(ea), simde_mm_store_si128((simde__m128i*)REX_RAW_ADDR(ea), REX_BSWAP128(simde_mm_load_si128((simde__m128i*)ll_v13.u8)));
	if (s.Stopped()) return true;
	r30.u64 = r11.u64 - r31.u64;
	r25.u64 = ll_r10.u64 - r31.u64;
	ea = (r30.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v12.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	simde_mm_store_ps(ll_v13.f32, REX_VMADDFP(simde_mm_load_ps(ll_v12.f32), simde_mm_load_ps(ll_v0.f32), simde_mm_load_ps(ll_v13.f32)));
	ea = (r11.u32) & ~0xF;
	if (s.Note((u32)(ea), 16)) REX_CARD(ea), simde_mm_store_si128((simde__m128i*)REX_RAW_ADDR(ea), REX_BSWAP128(simde_mm_load_si128((simde__m128i*)ll_v13.u8)));
	if (s.Stopped()) return true;
	ea = (r31.u32 + r11.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v12.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	simde_mm_store_ps(ll_v13.f32, REX_VMADDFP(simde_mm_load_ps(ll_v12.f32), simde_mm_load_ps(ll_v0.f32), simde_mm_load_ps(ll_v13.f32)));
	ea = (r11.u32) & ~0xF;
	if (s.Note((u32)(ea), 16)) REX_CARD(ea), simde_mm_store_si128((simde__m128i*)REX_RAW_ADDR(ea), REX_BSWAP128(simde_mm_load_si128((simde__m128i*)ll_v13.u8)));
	if (s.Stopped()) return true;
	ea = (ll_r10.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v52.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	simde_mm_store_ps(ll_v13.f32, simde_mm_mul_ps(simde_mm_load_ps(ll_v52.f32), simde_mm_load_ps(ll_v63.f32)));
	ea = (ll_r10.u32) & ~0xF;
	if (s.Note((u32)(ea), 16)) REX_CARD(ea), simde_mm_store_si128((simde__m128i*)REX_RAW_ADDR(ea), REX_BSWAP128(simde_mm_load_si128((simde__m128i*)ll_v13.u8)));
	if (s.Stopped()) return true;
	ea = (r25.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v12.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	simde_mm_store_ps(ll_v13.f32, REX_VMADDFP(simde_mm_load_ps(ll_v12.f32), simde_mm_load_ps(ll_v0.f32), simde_mm_load_ps(ll_v13.f32)));
	ea = (ll_r10.u32) & ~0xF;
	if (s.Note((u32)(ea), 16)) REX_CARD(ea), simde_mm_store_si128((simde__m128i*)REX_RAW_ADDR(ea), REX_BSWAP128(simde_mm_load_si128((simde__m128i*)ll_v13.u8)));
	if (s.Stopped()) return true;
	ea = (r31.u32 + ll_r10.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v12.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	simde_mm_store_ps(ll_v13.f32, REX_VMADDFP(simde_mm_load_ps(ll_v12.f32), simde_mm_load_ps(ll_v0.f32), simde_mm_load_ps(ll_v13.f32)));
	ea = (ll_r10.u32) & ~0xF;
	if (s.Note((u32)(ea), 16)) REX_CARD(ea), simde_mm_store_si128((simde__m128i*)REX_RAW_ADDR(ea), REX_BSWAP128(simde_mm_load_si128((simde__m128i*)ll_v13.u8)));
	if (s.Stopped()) return true;
loc_8286C410:
	s.Hit(10);
	r11.s64 = r11.s64 + 16;
	ll_r10.s64 = ll_r10.s64 + 16;
	ll_r9.s64 = ll_r9.s64 + 1;
	--ctr.u64;
	if (ctr.u32 != 0) goto loc_8286C380;
	s.Hit(11);
	ll_r8.s64 = ll_r8.s64 + 1;
	r11.s64 = r11.s64 + 32;
	ll_r10.s64 = ll_r10.s64 + 32;
	cr6.compare<int32_t>(ll_r8.s32, r27.s32, xer);
	if (cr6.lt) goto loc_8286C374;
	s.Hit(12);
	REX_LOOP_OUT(ll_r8, l_r8);
	REX_LOOP_OUT(ll_r9, l_r9);
	REX_LOOP_OUT(ll_r10, l_r10);
	REX_LOOP_OUT(ll_v0, l_v0);
	REX_LOOP_OUT(ll_v12, l_v12);
	REX_LOOP_OUT(ll_v13, l_v13);
	REX_LOOP_OUT(ll_v52, l_v52);
	REX_LOOP_OUT(ll_v53, l_v53);
	REX_LOOP_OUT(ll_v63, l_v63);
	ea = (r20.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)l_v10.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
loc_8286C438:
	s.Hit(13);
	r11.s64 = r28.s64 + -1;
	BANJO_HOT_STORE_D_U32(l_r1.u32, 208, r26.u32);
	if (s.Stopped()) return true;
	BANJO_HOT_STORE_D_U32(l_r1.u32, 216, r26.u32);
	if (s.Stopped()) return true;
	r26.u64 = r29.u64;
	l_r10.s64 = int64_t(r11.s32) * int64_t(r28.s32);
	BANJO_HOT_STORE_D_U32(l_r1.u32, 212, r28.u32);
	if (s.Stopped()) return true;
	BANJO_HOT_STORE_D_U32(l_r1.u32, 220, r28.u32);
	if (s.Stopped()) return true;
	BANJO_HOT_STORE_D_U32(l_r1.u32, 116, r11.u32);
	if (s.Stopped()) return true;
	BANJO_HOT_STORE_D_U32(l_r1.u32, 112, r29.u32);
	if (s.Stopped()) return true;
	BANJO_HOT_STORE_D_U32(l_r1.u32, 120, l_r10.u32);
	if (s.Stopped()) return true;
	BANJO_HOT_STORE_D_U32(l_r1.u32, 124, r29.u32);
	if (s.Stopped()) return true;
	r25.s64 = l_r5.s64 + 20;
	r27.u64 = r29.u64;
	r24.s64 = l_r5.s64 + 8;
	REX_LOOP_IN(ll_f11, l_f11);
	REX_LOOP_IN(ll_f12, l_f12);
	REX_LOOP_IN(ll_f13, l_f13);
	REX_LOOP_IN(ll_r1, l_r1);
	REX_LOOP_IN(ll_r4, l_r4);
	REX_LOOP_IN(ll_r5, l_r5);
	REX_LOOP_IN(ll_r8, l_r8);
	REX_LOOP_IN(ll_r9, l_r9);
	REX_LOOP_IN(ll_r10, l_r10);
	REX_LOOP_IN(ll_v0, l_v0);
	REX_LOOP_IN(ll_v10, l_v10);
	REX_LOOP_IN(ll_v12, l_v12);
	REX_LOOP_IN(ll_v13, l_v13);
	REX_LOOP_IN(ll_v47, l_v47);
	REX_LOOP_IN(ll_v48, l_v48);
	REX_LOOP_IN(ll_v49, l_v49);
	REX_LOOP_IN(ll_v50, l_v50);
	REX_LOOP_IN(ll_v51, l_v51);
	REX_LOOP_IN(ll_v63, l_v63);
loc_8286C470:
	s.Hit(14);
	REX_LOOP_BARRIER();
	r11.u64 = REX_LOAD_U8(r24.u32 + r26.u32);
	ll_r10.u64 = REX_LOAD_D_U8(ll_r5.u32, 12);
	r11.u64 = ll_r10.u64 - r11.u64;
	cr0.compare<int32_t>(r11.s32, 0, xer);
	if (!cr0.gt) goto loc_8286C488;
	s.Hit(15);
	ctx.fpscr.disableFlushMode();
	f0.f64 = double(REX_LOAD_D_F32(r25.u32, 0));
	goto loc_8286C4A0;
loc_8286C488:
	s.Hit(16);
	ctx.fpscr.disableFlushMode();
	f0.f64 = double(REX_LOAD_D_F32(r22.u32, 0));
	cr6.compare<int32_t>(r11.s32, 0, xer);
	if (!cr6.eq) goto loc_8286C4A0;
	s.Hit(17);
	ll_f12.f64 = double(REX_LOAD_D_F32(r25.u32, 0));
	ll_f11.f64 = REX_FSUBS(ll_f12.f64, f0.f64);
	f0.f64 = rex::ppc::GeZeroAnyMode(ll_f11.f64) ? f0.f64 : ll_f12.f64;
loc_8286C4A0:
	s.Hit(18);
	REX_FLUSH_KNOWN_OFF();
	temp.f32 = float(f0.f64);
	BANJO_HOT_STORE_D_U32(ll_r1.u32, 80, temp.u32);
	if (s.Stopped()) return true;
	cr6.compare(f0.f64, ll_f13.f64);
	if (!cr6.lt) goto loc_8286C57C;
	s.Hit(19);
	ll_r10.s64 = ll_r1.s64 + 80;
	ll_r9.u64 = REX_LOAD_D_U32(ll_r4.u32, 24);
	xer.ca = r11.u32 <= 0;
	ll_r8.u64 = static_cast<uint64_t>(0) - r11.u64;
	r30.u64 = REX_LOAD_D_U32(ll_r4.u32, 20);
	ll_r8.u64 = (r11.u32 >> 31);
	ea = (r23.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v51.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	r31.s64 = ll_r1.s64 + 208;
	temp.u8 = (ll_r8.u32 + 0xFFFFFFFFu < ll_r8.u32) | (ll_r8.u32 + 0xFFFFFFFFu + xer.ca < xer.ca);
	ll_r8.u64 = ll_r8.u64 + xer.ca + 0xFFFFFFFFFFFFFFFFull;
	xer.ca = temp.u8;
	temp.u32 = ll_r10.u32;
	simde_mm_store_si128((simde__m128i*)ll_v50.u8, REX_SHUFFLE_TABLE(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(temp.u32 & ~0xF)), &VectorMaskL[(temp.u32 & 0xF) * 16]));
	ll_r10.s64 = ll_r1.s64 + 112;
	r11.u64 = ll_r8.u64 & r11.u64;
	simde_mm_store_si128((simde__m128i*)ll_v63.u32, simde_mm_shuffle_epi32(simde_mm_load_si128((simde__m128i*)ll_v50.u32), 0xFF));
	ll_r8.u64 = REX_LOAD_U32(r27.u32 + r31.u32);
	r31.s64 = r11.s64 + 1;
	ll_r10.u64 = REX_LOAD_U32(r27.u32 + ll_r10.u32);
	ll_r8.u64 = r11.u8 & 0x20 ? 0 : (ll_r8.u32 << (r11.u8 & 0x3F));
	ctx.fpscr.enableFlushModeUnconditional();
	simde_mm_store_ps(ll_v49.f32, simde_mm_sub_ps(simde_mm_load_ps(ll_v10.f32), simde_mm_load_ps(ll_v63.f32)));
	r11.u64 = ll_r10.u64 + ll_r8.u64;
	temp.u32 = r31.u32 & 0x3F;
	if (temp.u32 > 0x1F) temp.u32 = 0x1F;
	xer.ca = (r28.s32 < 0) & (((r28.s32 >> temp.u32) << temp.u32) != r28.s32);
	r31.s64 = r28.s32 >> temp.u32;
	cr0.compare<int32_t>(r31.s32, 0, xer);
	ll_r10.u64 = ((uint32_t)(r11.u32 << 4));
	simde_mm_store_ps(ll_v0.f32, simde_mm_mul_ps(simde_mm_load_ps(ll_v49.f32), simde_mm_load_ps(ll_v51.f32)));
	r11.u64 = ll_r9.u64 + ll_r10.u64;
	ll_r10.u64 = r30.u64 + ll_r10.u64;
	if (cr0.eq) goto loc_8286C57C;
	s.Hit(20);
	ll_r9.u64 = ((uint32_t)(ll_r8.u32 << 4));
	ctr.u64 = r31.u64;
	r31.u64 = ((uint32_t)(ll_r8.u32 << 5));
	ll_r8.u64 = r11.u64 - ll_r9.u64;
loc_8286C51C:
	s.Hit(21);
	REX_LOOP_BARRIER();
	ea = (r11.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v48.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	r30.u64 = ll_r10.u64 - ll_r9.u64;
	REX_FLUSH_KNOWN_ON();
	simde_mm_store_ps(ll_v13.f32, simde_mm_mul_ps(simde_mm_load_ps(ll_v48.f32), simde_mm_load_ps(ll_v63.f32)));
	ea = (r11.u32) & ~0xF;
	if (s.Note((u32)(ea), 16)) REX_CARD(ea), simde_mm_store_si128((simde__m128i*)REX_RAW_ADDR(ea), REX_BSWAP128(simde_mm_load_si128((simde__m128i*)ll_v13.u8)));
	if (s.Stopped()) return true;
	ea = (ll_r8.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v12.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	simde_mm_store_ps(ll_v13.f32, REX_VMADDFP(simde_mm_load_ps(ll_v12.f32), simde_mm_load_ps(ll_v0.f32), simde_mm_load_ps(ll_v13.f32)));
	ea = (r11.u32) & ~0xF;
	if (s.Note((u32)(ea), 16)) REX_CARD(ea), simde_mm_store_si128((simde__m128i*)REX_RAW_ADDR(ea), REX_BSWAP128(simde_mm_load_si128((simde__m128i*)ll_v13.u8)));
	if (s.Stopped()) return true;
	ea = (ll_r9.u32 + r11.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v12.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	simde_mm_store_ps(ll_v13.f32, REX_VMADDFP(simde_mm_load_ps(ll_v12.f32), simde_mm_load_ps(ll_v0.f32), simde_mm_load_ps(ll_v13.f32)));
	ea = (r11.u32) & ~0xF;
	if (s.Note((u32)(ea), 16)) REX_CARD(ea), simde_mm_store_si128((simde__m128i*)REX_RAW_ADDR(ea), REX_BSWAP128(simde_mm_load_si128((simde__m128i*)ll_v13.u8)));
	if (s.Stopped()) return true;
	r11.u64 = r31.u64 + r11.u64;
	ea = (ll_r10.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v47.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	simde_mm_store_ps(ll_v13.f32, simde_mm_mul_ps(simde_mm_load_ps(ll_v47.f32), simde_mm_load_ps(ll_v63.f32)));
	ea = (ll_r10.u32) & ~0xF;
	if (s.Note((u32)(ea), 16)) REX_CARD(ea), simde_mm_store_si128((simde__m128i*)REX_RAW_ADDR(ea), REX_BSWAP128(simde_mm_load_si128((simde__m128i*)ll_v13.u8)));
	if (s.Stopped()) return true;
	ll_r8.u64 = r11.u64 - ll_r9.u64;
	ea = (r30.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v12.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	simde_mm_store_ps(ll_v13.f32, REX_VMADDFP(simde_mm_load_ps(ll_v12.f32), simde_mm_load_ps(ll_v0.f32), simde_mm_load_ps(ll_v13.f32)));
	ea = (ll_r10.u32) & ~0xF;
	if (s.Note((u32)(ea), 16)) REX_CARD(ea), simde_mm_store_si128((simde__m128i*)REX_RAW_ADDR(ea), REX_BSWAP128(simde_mm_load_si128((simde__m128i*)ll_v13.u8)));
	if (s.Stopped()) return true;
	ea = (ll_r9.u32 + ll_r10.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v12.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	simde_mm_store_ps(ll_v13.f32, REX_VMADDFP(simde_mm_load_ps(ll_v12.f32), simde_mm_load_ps(ll_v0.f32), simde_mm_load_ps(ll_v13.f32)));
	ea = (ll_r10.u32) & ~0xF;
	if (s.Note((u32)(ea), 16)) REX_CARD(ea), simde_mm_store_si128((simde__m128i*)REX_RAW_ADDR(ea), REX_BSWAP128(simde_mm_load_si128((simde__m128i*)ll_v13.u8)));
	if (s.Stopped()) return true;
	ll_r10.u64 = r31.u64 + ll_r10.u64;
	--ctr.u64;
	if (ctr.u32 != 0) goto loc_8286C51C;
	s.Hit(22);
	ea = (r20.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v10.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
loc_8286C57C:
	s.Hit(23);
	r27.s64 = r27.s64 + 4;
	r26.s64 = r26.s64 + 1;
	r25.s64 = r25.s64 + 4;
	cr6.compare<uint32_t>(r27.u32, 16, xer);
	if (cr6.lt) goto loc_8286C470;
	s.Hit(24);
	REX_LOOP_OUT(ll_f11, l_f11);
	REX_LOOP_OUT(ll_f12, l_f12);
	REX_LOOP_OUT(ll_r8, l_r8);
	REX_LOOP_OUT(ll_r9, l_r9);
	REX_LOOP_OUT(ll_r10, l_r10);
	REX_LOOP_OUT(ll_v0, l_v0);
	REX_LOOP_OUT(ll_v10, l_v10);
	REX_LOOP_OUT(ll_v12, l_v12);
	REX_LOOP_OUT(ll_v13, l_v13);
	REX_LOOP_OUT(ll_v47, l_v47);
	REX_LOOP_OUT(ll_v48, l_v48);
	REX_LOOP_OUT(ll_v49, l_v49);
	REX_LOOP_OUT(ll_v50, l_v50);
	REX_LOOP_OUT(ll_v51, l_v51);
	REX_LOOP_OUT(ll_v63, l_v63);
	r28.u64 = REX_LOAD_D_U32(r21.u32, 0);
	r27.s64 = l_r1.s64 + 208;
	BANJO_HOT_STORE_D_U64(l_r1.u32, 208, r28.u64);
	if (s.Stopped()) return true;
	r11.s64 = -2113929216;
	REX_DEAD_DEF(r5, l_r5.u64 = r28.u64);
	l_r10.u64 = REX_LOAD_D_U16(l_r7.u32, 0);
	xer.ca = r28.u32 > 4294967294;
	r28.s64 = r28.s64 + 1;
	cr0.compare<int32_t>(r28.s32, 0, xer);
	BANJO_HOT_STORE_D_U32(l_r1.u32, 80, r28.u32);
	if (s.Stopped()) return true;
	l_r9.u64 = REX_LOAD_D_U16(l_r7.u32, 2);
	r22.s64 = r11.s64 + 9364;
	l_r8.u64 = REX_LOAD_D_U16(l_r7.u32, 4);
	l_r5.u64 = __builtin_rotateleft32(l_r10.u32, 2);
	l_r7.u64 = REX_LOAD_D_U16(l_r7.u32, 6);
	r31.u64 = __builtin_rotateleft32(l_r9.u32, 2);
	r11.u64 = REX_LOAD_D_U32(l_r3.u32, 88);
	r30.u64 = __builtin_rotateleft32(l_r8.u32, 2);
	l_r3.u64 = __builtin_rotateleft32(l_r7.u32, 2);
	l_r9.u64 = l_r9.u64 + r31.u64;
	l_r5.u64 = l_r10.u64 + l_r5.u64;
	l_r8.u64 = l_r8.u64 + r30.u64;
	l_r7.u64 = l_r7.u64 + l_r3.u64;
	l_r9.u64 = ((uint32_t)(l_r9.u32 << 4));
	l_r10.u64 = ((uint32_t)(l_r5.u32 << 4));
	l_r8.u64 = ((uint32_t)(l_r8.u32 << 4));
	l_r7.u64 = ((uint32_t)(l_r7.u32 << 4));
	r25.u64 = l_r9.u64 + r11.u64;
	r26.u64 = l_r10.u64 + r11.u64;
	r24.u64 = l_r8.u64 + r11.u64;
	r23.u64 = l_r7.u64 + r11.u64;
	f0.u64 = REX_LOAD_D_U64(l_r1.u32, 208);
	l_r9.u64 = r29.u64;
	l_f12.f64 = double(f0.s64);
	ctx.fpscr.disableFlushMode();
	l_f11.f64 = double(float(l_f12.f64));
	l_f10.f64 = REX_FDIVS(l_f13.f64, l_f11.f64);
	temp.f32 = float(l_f10.f64);
	BANJO_HOT_STORE_D_U32(l_r1.u32, 208, temp.u32);
	if (s.Stopped()) return true;
	temp.u32 = r27.u32;
	simde_mm_store_si128((simde__m128i*)l_v46.u8, REX_SHUFFLE_TABLE(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(temp.u32 & ~0xF)), &VectorMaskL[(temp.u32 & 0xF) * 16]));
	temp.u32 = r22.u32;
	simde_mm_store_si128((simde__m128i*)l_v45.u8, REX_SHUFFLE_TABLE(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(temp.u32 & ~0xF)), &VectorMaskL[(temp.u32 & 0xF) * 16]));
	simde_mm_store_si128((simde__m128i*)l_v54.u32, simde_mm_shuffle_epi32(simde_mm_load_si128((simde__m128i*)l_v45.u32), 0xFF));
	simde_mm_store_si128((simde__m128i*)l_v59.u32, simde_mm_shuffle_epi32(simde_mm_load_si128((simde__m128i*)l_v46.u32), 0xFF));
	simde_mm_store_si128((simde__m128i*)l_v55.u8, simde_mm_load_si128((simde__m128i*)l_v54.u8));
	if (cr0.eq) goto loc_8286C9EC;
	s.Hit(25);
	r11.s64 = -2113142784;
	l_r10.s64 = -2113798144;
	r30.s64 = -1;
	r31.s64 = 8;
	l_r3.s64 = 12;
	l_r5.s64 = 4;
	l_r7.s64 = r11.s64 + 20936;
	r22.s64 = l_r10.s64 + -31328;
	REX_LOOP_IN(ll_r1, l_r1);
	REX_LOOP_IN(ll_r3, l_r3);
	REX_LOOP_IN(ll_r4, l_r4);
	REX_LOOP_IN(ll_r5, l_r5);
	REX_LOOP_IN(ll_r6, l_r6);
	REX_LOOP_IN(ll_r7, l_r7);
	REX_LOOP_IN(ll_r8, l_r8);
	REX_LOOP_IN(ll_r9, l_r9);
	REX_LOOP_IN(ll_r10, l_r10);
	REX_LOOP_IN(ll_v0, l_v0);
	REX_LOOP_IN(ll_v1, l_v1);
	REX_LOOP_IN(ll_v2, l_v2);
	REX_LOOP_IN(ll_v3, l_v3);
	REX_LOOP_IN(ll_v4, l_v4);
	REX_LOOP_IN(ll_v5, l_v5);
	REX_LOOP_IN(ll_v6, l_v6);
	REX_LOOP_IN(ll_v7, l_v7);
	REX_LOOP_IN(ll_v8, l_v8);
	REX_LOOP_IN(ll_v9, l_v9);
	REX_LOOP_IN(ll_v10, l_v10);
	REX_LOOP_IN(ll_v11, l_v11);
	REX_LOOP_IN(ll_v12, l_v12);
	REX_LOOP_IN(ll_v13, l_v13);
	REX_LOOP_IN(ll_v14, l_v14);
	REX_LOOP_IN(ll_v15, l_v15);
	REX_LOOP_IN(ll_v16, l_v16);
	REX_LOOP_IN(ll_v17, l_v17);
	REX_LOOP_IN(ll_v18, l_v18);
	REX_LOOP_IN(ll_v19, l_v19);
	REX_LOOP_IN(ll_v20, l_v20);
	REX_LOOP_IN(ll_v21, l_v21);
	REX_LOOP_IN(ll_v22, l_v22);
	REX_LOOP_IN(ll_v23, l_v23);
	REX_LOOP_IN(ll_v24, l_v24);
	REX_LOOP_IN(ll_v25, l_v25);
	REX_LOOP_IN(ll_v26, l_v26);
	REX_LOOP_IN(ll_v27, l_v27);
	REX_LOOP_IN(ll_v28, l_v28);
	REX_LOOP_IN(ll_v29, l_v29);
	REX_LOOP_IN(ll_v30, l_v30);
	REX_LOOP_IN(ll_v31, l_v31);
	REX_LOOP_IN(ll_v32, l_v32);
	REX_LOOP_IN(ll_v33, l_v33);
	REX_LOOP_IN(ll_v34, l_v34);
	REX_LOOP_IN(ll_v35, l_v35);
	REX_LOOP_IN(ll_v36, l_v36);
	REX_LOOP_IN(ll_v37, l_v37);
	REX_LOOP_IN(ll_v38, l_v38);
	REX_LOOP_IN(ll_v39, l_v39);
	REX_LOOP_IN(ll_v40, l_v40);
	REX_LOOP_IN(ll_v41, l_v41);
	REX_LOOP_IN(ll_v42, l_v42);
	REX_LOOP_IN(ll_v43, l_v43);
	REX_LOOP_IN(ll_v44, l_v44);
	REX_LOOP_IN(ll_v45, l_v45);
	REX_LOOP_IN(ll_v46, l_v46);
	REX_LOOP_IN(ll_v47, l_v47);
	REX_LOOP_IN(ll_v48, l_v48);
	REX_LOOP_IN(ll_v49, l_v49);
	REX_LOOP_IN(ll_v50, l_v50);
	REX_LOOP_IN(ll_v51, l_v51);
	REX_LOOP_IN(ll_v52, l_v52);
	REX_LOOP_IN(ll_v53, l_v53);
	REX_LOOP_IN(ll_v54, l_v54);
	REX_LOOP_IN(ll_v55, l_v55);
	REX_LOOP_IN(ll_v56, l_v56);
	REX_LOOP_IN(ll_v57, l_v57);
	REX_LOOP_IN(ll_v58, l_v58);
	REX_LOOP_IN(ll_v59, l_v59);
	REX_LOOP_IN(ll_v60, l_v60);
	REX_LOOP_IN(ll_v61, l_v61);
	REX_LOOP_IN(ll_v62, l_v62);
	REX_LOOP_IN(ll_v63, l_v63);
loc_8286C654:
	s.Hit(26);
	REX_LOOP_BARRIER();
	r11.s64 = r23.s64 + 16;
	ea = (r23.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v13.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	ea = (r26.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v43.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	simde_mm_store_si128((simde__m128i*)ll_v0.u32, simde_mm_shuffle_epi32(simde_mm_load_si128((simde__m128i*)ll_v55.u32), 0xFF));
	ea = (r24.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v9.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	ctx.fpscr.enableFlushMode();
	simde_mm_store_ps(ll_v31.f32, simde_mm_sub_ps(simde_mm_load_ps(ll_v43.f32), simde_mm_load_ps(ll_v13.f32)));
	ea = (r25.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v44.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	ll_r10.u64 = REX_LOAD_D_U32(r21.u32, 0);
	simde_mm_store_ps(ll_v2.f32, simde_mm_sub_ps(simde_mm_load_ps(ll_v44.f32), simde_mm_load_ps(ll_v9.f32)));
	simde_mm_store_si128((simde__m128i*)ll_v62.u8, simde_mm_load_si128((simde__m128i*)ll_v54.u8));
	ea = (r11.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v12.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	r11.s64 = r23.s64 + 32;
	xer.ca = ll_r10.u32 > 4294967294;
	ll_r10.s64 = ll_r10.s64 + 1;
	cr0.compare<int32_t>(ll_r10.s32, 0, xer);
	simde_mm_store_ps(ll_v55.f32, simde_mm_add_ps(simde_mm_load_ps(ll_v55.f32), simde_mm_load_ps(ll_v59.f32)));
	ea = (r11.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v11.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	r11.s64 = r23.s64 + 64;
	simde_mm_store_ps(ll_v31.f32, REX_VMADDFP(simde_mm_load_ps(ll_v0.f32), simde_mm_load_ps(ll_v31.f32), simde_mm_load_ps(ll_v13.f32)));
	ea = (r11.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v10.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	r11.s64 = r24.s64 + 16;
	simde_mm_store_ps(ll_v26.f32, REX_VMADDFP(simde_mm_load_ps(ll_v0.f32), simde_mm_load_ps(ll_v2.f32), simde_mm_load_ps(ll_v9.f32)));
	ea = (r11.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v8.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	r11.s64 = r24.s64 + 32;
	ea = (r11.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v7.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	r11.s64 = r24.s64 + 64;
	ea = (r11.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v6.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	r11.s64 = r26.s64 + 16;
	ea = (r11.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v42.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	r11.s64 = r26.s64 + 32;
	simde_mm_store_ps(ll_v30.f32, simde_mm_sub_ps(simde_mm_load_ps(ll_v42.f32), simde_mm_load_ps(ll_v12.f32)));
	ea = (r11.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v41.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	r11.s64 = r26.s64 + 64;
	simde_mm_store_ps(ll_v29.f32, simde_mm_sub_ps(simde_mm_load_ps(ll_v41.f32), simde_mm_load_ps(ll_v11.f32)));
	ea = (r11.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v40.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	r11.s64 = r25.s64 + 16;
	simde_mm_store_ps(ll_v1.f32, simde_mm_sub_ps(simde_mm_load_ps(ll_v40.f32), simde_mm_load_ps(ll_v10.f32)));
	simde_mm_store_ps(ll_v12.f32, REX_VMADDFP(simde_mm_load_ps(ll_v0.f32), simde_mm_load_ps(ll_v30.f32), simde_mm_load_ps(ll_v12.f32)));
	ea = (r11.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v39.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	r11.s64 = r25.s64 + 32;
	simde_mm_store_ps(ll_v3.f32, simde_mm_sub_ps(simde_mm_load_ps(ll_v39.f32), simde_mm_load_ps(ll_v8.f32)));
	simde_mm_store_ps(ll_v11.f32, REX_VMADDFP(simde_mm_load_ps(ll_v0.f32), simde_mm_load_ps(ll_v29.f32), simde_mm_load_ps(ll_v11.f32)));
	ea = (r11.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v38.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	r11.s64 = r25.s64 + 64;
	simde_mm_store_ps(ll_v4.f32, simde_mm_sub_ps(simde_mm_load_ps(ll_v38.f32), simde_mm_load_ps(ll_v7.f32)));
	simde_mm_store_ps(ll_v13.f32, REX_VMADDFP(simde_mm_load_ps(ll_v0.f32), simde_mm_load_ps(ll_v1.f32), simde_mm_load_ps(ll_v10.f32)));
	ea = (r11.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v37.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	simde_mm_store_ps(ll_v5.f32, simde_mm_sub_ps(simde_mm_load_ps(ll_v37.f32), simde_mm_load_ps(ll_v6.f32)));
	simde_mm_store_ps(ll_v25.f32, REX_VMADDFP(simde_mm_load_ps(ll_v0.f32), simde_mm_load_ps(ll_v3.f32), simde_mm_load_ps(ll_v8.f32)));
	simde_mm_store_ps(ll_v24.f32, REX_VMADDFP(simde_mm_load_ps(ll_v0.f32), simde_mm_load_ps(ll_v4.f32), simde_mm_load_ps(ll_v7.f32)));
	simde_mm_store_ps(ll_v23.f32, REX_VMADDFP(simde_mm_load_ps(ll_v0.f32), simde_mm_load_ps(ll_v5.f32), simde_mm_load_ps(ll_v6.f32)));
	if (cr0.eq) goto loc_8286C9E0;
	s.Hit(27);
	temp.u32 = r19.u32;
	simde_mm_store_si128((simde__m128i*)ll_v36.u8, REX_SHUFFLE_TABLE(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(temp.u32 & ~0xF)), &VectorMaskL[(temp.u32 & 0xF) * 16]));
	BANJO_HOT_STORE_D_U32(ll_r1.u32, 112, r29.u32);
	if (s.Stopped()) return true;
	BANJO_HOT_STORE_D_U32(ll_r1.u32, 116, r29.u32);
	if (s.Stopped()) return true;
	r21.u64 = ll_r10.u64 + ll_r9.u64;
	BANJO_HOT_STORE_D_U32(ll_r1.u32, 120, r29.u32);
	if (s.Stopped()) return true;
	ctr.u64 = ll_r10.u64;
	BANJO_HOT_STORE_D_U32(ll_r1.u32, 124, r30.u32);
	if (s.Stopped()) return true;
	ll_r8.u64 = ((uint32_t)(ll_r9.u32 << 4));
	BANJO_HOT_STORE_D_U32(ll_r1.u32, 128, r29.u32);
	if (s.Stopped()) return true;
	r28.s64 = ll_r4.s64 + 20;
	BANJO_HOT_STORE_D_U32(ll_r1.u32, 132, r29.u32);
	if (s.Stopped()) return true;
	r27.s64 = ll_r4.s64 + 24;
	BANJO_HOT_STORE_D_U32(ll_r1.u32, 160, r29.u32);
	if (s.Stopped()) return true;
	ll_r10.s64 = ll_r1.s64 + 112;
	BANJO_HOT_STORE_D_U32(ll_r1.u32, 164, r29.u32);
	if (s.Stopped()) return true;
	ll_r9.s64 = ll_r1.s64 + 128;
	BANJO_HOT_STORE_D_U32(ll_r1.u32, 200, r29.u32);
	if (s.Stopped()) return true;
	ll_r4.s64 = ll_r1.s64 + 160;
	BANJO_HOT_STORE_D_U32(ll_r1.u32, 144, r29.u32);
	if (s.Stopped()) return true;
	r20.s64 = ll_r1.s64 + 144;
	BANJO_HOT_STORE_D_U32(ll_r1.u32, 156, r30.u32);
	if (s.Stopped()) return true;
	r19.s64 = ll_r1.s64 + 176;
	BANJO_HOT_STORE_D_U32(ll_r1.u32, 208, r21.u32);
	if (s.Stopped()) return true;
	r21.s64 = ll_r1.s64 + 192;
	BANJO_HOT_STORE_D_U32(ll_r1.u32, 136, r29.u32);
	if (s.Stopped()) return true;
	simde_mm_store_ps(ll_v22.f32, simde_mm_sub_ps(simde_mm_load_ps(ll_v12.f32), simde_mm_load_ps(ll_v25.f32)));
	BANJO_HOT_STORE_D_U32(ll_r1.u32, 140, r30.u32);
	if (s.Stopped()) return true;
	simde_mm_store_ps(ll_v21.f32, simde_mm_sub_ps(simde_mm_load_ps(ll_v11.f32), simde_mm_load_ps(ll_v24.f32)));
	BANJO_HOT_STORE_D_U32(ll_r1.u32, 168, r29.u32);
	if (s.Stopped()) return true;
	simde_mm_store_si128((simde__m128i*)ll_v63.u32, simde_mm_set1_epi32(int(0x0)));
	BANJO_HOT_STORE_D_U32(ll_r1.u32, 172, r30.u32);
	if (s.Stopped()) return true;
	simde_mm_store_ps(ll_v20.f32, simde_mm_sub_ps(simde_mm_load_ps(ll_v31.f32), simde_mm_load_ps(ll_v26.f32)));
	BANJO_HOT_STORE_D_U32(ll_r1.u32, 192, r29.u32);
	if (s.Stopped()) return true;
	simde_mm_store_ps(ll_v19.f32, simde_mm_sub_ps(simde_mm_load_ps(ll_v13.f32), simde_mm_load_ps(ll_v23.f32)));
	BANJO_HOT_STORE_D_U32(ll_r1.u32, 196, r29.u32);
	if (s.Stopped()) return true;
	simde_mm_store_si128((simde__m128i*)ll_v58.u32, simde_mm_shuffle_epi32(simde_mm_load_si128((simde__m128i*)ll_v36.u32), 0xFF));
	BANJO_HOT_STORE_D_U32(ll_r1.u32, 204, r30.u32);
	if (s.Stopped()) return true;
	r11.s64 = ll_r6.s64 + 32;
	BANJO_HOT_STORE_D_U32(ll_r1.u32, 148, r29.u32);
	if (s.Stopped()) return true;
	BANJO_HOT_STORE_D_U32(ll_r1.u32, 152, r29.u32);
	if (s.Stopped()) return true;
	BANJO_HOT_STORE_D_U32(ll_r1.u32, 176, r29.u32);
	if (s.Stopped()) return true;
	BANJO_HOT_STORE_D_U32(ll_r1.u32, 180, r29.u32);
	if (s.Stopped()) return true;
	BANJO_HOT_STORE_D_U32(ll_r1.u32, 184, r29.u32);
	if (s.Stopped()) return true;
	ea = (ll_r10.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v18.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	BANJO_HOT_STORE_D_U32(ll_r1.u32, 188, r30.u32);
	if (s.Stopped()) return true;
	ea = (r19.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v57.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	ea = (ll_r9.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v17.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	ea = (ll_r4.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v16.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	ea = (r21.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v15.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	ea = (r20.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v14.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
loc_8286C7E4:
	s.Hit(28);
	REX_LOOP_BARRIER();
	simde_mm_store_si128((simde__m128i*)ll_v0.u32, simde_mm_shuffle_epi32(simde_mm_load_si128((simde__m128i*)ll_v62.u32), 0xFF));
	ll_r4.u64 = REX_LOAD_D_U32(r27.u32, 0);
	ll_r9.s64 = 16;
	temp.u32 = ll_r7.u32 + r31.u32;
	simde_mm_store_si128((simde__m128i*)ll_v34.u8, REX_SHUFFLE_TABLE(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(temp.u32 & ~0xF)), &VectorMaskL[(temp.u32 & 0xF) * 16]));
	temp.u32 = ll_r7.u32 + ll_r3.u32;
	simde_mm_store_si128((simde__m128i*)ll_v33.u8, REX_SHUFFLE_TABLE(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(temp.u32 & ~0xF)), &VectorMaskL[(temp.u32 & 0xF) * 16]));
	ll_r10.u64 = REX_LOAD_D_U32(r28.u32, 0);
	simde_mm_store_ps(ll_v33.f32, simde_mm_blend_ps(simde_mm_load_ps(ll_v33.f32), simde_mm_permute_ps(simde_mm_load_ps(ll_v34.f32), 57), 4));
	temp.u32 = ll_r6.u32;
	simde_mm_store_si128((simde__m128i*)ll_v7.u8, simde_mm_load_si128((simde__m128i*)&VectorShiftTableR[(temp.u32 & 0xF) * 16]));
	REX_FLUSH_KNOWN_ON();
	simde_mm_store_ps(ll_v11.f32, REX_VMADDFP(simde_mm_load_ps(ll_v0.f32), simde_mm_load_ps(ll_v22.f32), simde_mm_load_ps(ll_v25.f32)));
	ll_r10.u64 = ll_r8.u64 + ll_r10.u64;
	simde_mm_store_ps(ll_v13.f32, REX_VMADDFP(simde_mm_load_ps(ll_v0.f32), simde_mm_load_ps(ll_v21.f32), simde_mm_load_ps(ll_v24.f32)));
	ea = (ll_r4.u32 + ll_r8.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v51.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	ll_r4.s64 = ll_r1.s64 + 96;
	temp.u32 = ll_r7.u32 + ll_r9.u32;
	simde_mm_store_si128((simde__m128i*)ll_v32.u8, REX_SHUFFLE_TABLE(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(temp.u32 & ~0xF)), &VectorMaskL[(temp.u32 & 0xF) * 16]));
	simde_mm_store_ps(ll_v33.f32, simde_mm_blend_ps(simde_mm_load_ps(ll_v33.f32), simde_mm_permute_ps(simde_mm_load_ps(ll_v32.f32), 78), 2));
	ea = (r22.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v60.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	simde_mm_store_si128((simde__m128i*)ll_v53.u8, simde_mm_load_si128((simde__m128i*)ll_v32.u8));
	temp.u32 = ll_r7.u32;
	simde_mm_store_si128((simde__m128i*)ll_v35.u8, REX_SHUFFLE_TABLE(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(temp.u32 & ~0xF)), &VectorMaskL[(temp.u32 & 0xF) * 16]));
	ea = (ll_r10.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v61.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	vTemp.u32[0] = ll_v63.u8[3] | 0x3F800000;
	vTemp.u32[1] = ll_v63.u8[0] | 0x3F800000;
	vTemp.u32[2] = ll_v63.u8[1] | 0x3F800000;
	vTemp.u32[3] = ll_v63.u8[2] | 0x3F800000;
	ll_v29 = vTemp;
	temp.u32 = ll_r7.u32 + ll_r5.u32;
	simde_mm_store_si128((simde__m128i*)ll_v52.u8, REX_SHUFFLE_TABLE(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(temp.u32 & ~0xF)), &VectorMaskL[(temp.u32 & 0xF) * 16]));
	simde_mm_store_si128((simde__m128i*)ll_v5.u8, simde_mm_load_si128((simde__m128i*)ll_v63.u8));
	ea = (ll_r4.u32) & ~0xF;
	if (s.Note((u32)(ea), 16)) REX_CARD(ea), simde_mm_store_si128((simde__m128i*)REX_RAW_ADDR(ea), REX_BSWAP128(simde_mm_load_si128((simde__m128i*)ll_v7.u8)));
	if (s.Stopped()) return true;
	simde_mm_store_si128((simde__m128i*)ll_v4.u8, simde_mm_load_si128((simde__m128i*)ll_v33.u8));
	simde_mm_store_ps(ll_v53.f32, simde_mm_blend_ps(simde_mm_load_ps(ll_v53.f32), simde_mm_permute_ps(simde_mm_load_ps(ll_v35.f32), 57), 4));
	simde_mm_store_ps(ll_v27.f32, REX_VMADDFP(simde_mm_load_ps(ll_v0.f32), simde_mm_load_ps(ll_v20.f32), simde_mm_load_ps(ll_v26.f32)));
	simde_mm_store_si128((simde__m128i*)ll_v12.u8, simde_mm_load_si128((simde__m128i*)ll_v56.u8));
	simde_mm_store_si128((simde__m128i*)ll_v50.u32, simde_mm_shuffle_epi32(simde_mm_load_si128((simde__m128i*)ll_v51.u32), 0xAA));
	simde_mm_store_si128((simde__m128i*)ll_v6.u8, simde_mm_load_si128((simde__m128i*)ll_v63.u8));
	simde_mm_store_ps(ll_v0.f32, REX_VMADDFP(simde_mm_load_ps(ll_v0.f32), simde_mm_load_ps(ll_v19.f32), simde_mm_load_ps(ll_v23.f32)));
	simde_mm_store_ps(ll_v4.f32, simde_mm_blend_ps(simde_mm_load_ps(ll_v4.f32), simde_mm_permute_ps(simde_mm_load_ps(ll_v32.f32), 147), 1));
	ll_r9.s64 = r11.s64 + 16;
	simde_mm_store_si128((simde__m128i*)ll_v49.u8, simde_mm_load_si128((simde__m128i*)ll_v11.u8));
	simde_mm_store_si128((simde__m128i*)ll_v48.u8, simde_mm_load_si128((simde__m128i*)ll_v13.u8));
	simde_mm_store_si128((simde__m128i*)ll_v1.u32, simde_mm_shuffle_epi32(simde_mm_load_si128((simde__m128i*)ll_v50.u32), 0xFF));
	simde_mm_store_ps(ll_v53.f32, simde_mm_blend_ps(simde_mm_load_ps(ll_v53.f32), simde_mm_permute_ps(simde_mm_load_ps(ll_v52.f32), 78), 2));
	simde_mm_store_si128((simde__m128i*)ll_v45.u8, rex::ppc::simde_mm_perm_epi8_(simde_mm_load_si128((simde__m128i*)ll_v61.u8), simde_mm_load_si128((simde__m128i*)ll_v60.u8), simde_mm_load_si128((simde__m128i*)ll_v4.u8)));
	simde_mm_store_si128((simde__m128i*)ll_v28.u8, REX_VSEL(simde_mm_load_si128((simde__m128i*)ll_v18.u8), simde_mm_load_si128((simde__m128i*)ll_v11.u8), simde_mm_load_si128((simde__m128i*)ll_v12.u8)));
	simde_mm_store_si128((simde__m128i*)ll_v47.u32, simde_mm_shuffle_epi32(simde_mm_load_si128((simde__m128i*)ll_v49.u32), 0x78));
	simde_mm_store_si128((simde__m128i*)ll_v12.u8, simde_mm_load_si128((simde__m128i*)ll_v63.u8));
	simde_mm_store_si128((simde__m128i*)ll_v46.u32, simde_mm_shuffle_epi32(simde_mm_load_si128((simde__m128i*)ll_v48.u32), 0x9C));
	simde_mm_store_si128((simde__m128i*)ll_v11.u8, simde_mm_load_si128((simde__m128i*)ll_v48.u8));
	simde_mm_store_si128((simde__m128i*)ll_v13.u32, simde_mm_shuffle_epi32(simde_mm_load_si128((simde__m128i*)ll_v49.u32), 0x9C));
	simde_mm_store_si128((simde__m128i*)ll_v3.u8, simde_mm_load_si128((simde__m128i*)ll_v53.u8));
	simde_mm_store_si128((simde__m128i*)ll_v8.u32, simde_mm_shuffle_epi32(simde_mm_load_si128((simde__m128i*)ll_v48.u32), 0x78));
	simde_mm_store_si128((simde__m128i*)ll_v9.u8, simde_mm_load_si128((simde__m128i*)ll_v49.u8));
	simde_mm_store_si128((simde__m128i*)ll_v43.u32, simde_mm_shuffle_epi32(simde_mm_load_si128((simde__m128i*)ll_v45.u32), 0x78));
	simde_mm_store_si128((simde__m128i*)ll_v10.u8, simde_mm_load_si128((simde__m128i*)ll_v63.u8));
	simde_mm_store_ps(ll_v7.f32, simde_mm_mul_ps(simde_mm_load_ps(ll_v46.f32), simde_mm_load_ps(ll_v47.f32)));
	simde_mm_store_ps(ll_v3.f32, simde_mm_blend_ps(simde_mm_load_ps(ll_v3.f32), simde_mm_permute_ps(simde_mm_load_ps(ll_v32.f32), 147), 1));
	simde_mm_store_si128((simde__m128i*)ll_v44.u8, rex::ppc::simde_mm_perm_epi8_(simde_mm_load_si128((simde__m128i*)ll_v61.u8), simde_mm_load_si128((simde__m128i*)ll_v60.u8), simde_mm_load_si128((simde__m128i*)ll_v3.u8)));
	simde_mm_store_si128((simde__m128i*)ll_v42.u32, simde_mm_shuffle_epi32(simde_mm_load_si128((simde__m128i*)ll_v44.u32), 0x9C));
	simde_mm_store_si128((simde__m128i*)ll_v41.u32, simde_mm_shuffle_epi32(simde_mm_load_si128((simde__m128i*)ll_v44.u32), 0x55));
	simde_mm_store_ps(ll_v4.f32, REX_VNMSUBFP(simde_mm_load_ps(ll_v8.f32), simde_mm_load_ps(ll_v13.f32), simde_mm_load_ps(ll_v7.f32)));
	simde_mm_store_si128((simde__m128i*)ll_v8.u32, simde_mm_shuffle_epi32(simde_mm_load_si128((simde__m128i*)ll_v45.u32), 0x9C));
	simde_mm_store_ps(ll_v2.f32, simde_mm_mul_ps(simde_mm_load_ps(ll_v42.f32), simde_mm_load_ps(ll_v43.f32)));
	simde_mm_store_si128((simde__m128i*)ll_v7.u32, simde_mm_shuffle_epi32(simde_mm_load_si128((simde__m128i*)ll_v44.u32), 0x78));
	simde_mm_store_si128((simde__m128i*)ll_v40.u8, simde_mm_load_si128((simde__m128i*)ll_v4.u8));
	simde_mm_store_ps(ll_v2.f32, REX_VNMSUBFP(simde_mm_load_ps(ll_v7.f32), simde_mm_load_ps(ll_v8.f32), simde_mm_load_ps(ll_v2.f32)));
	simde_mm_store_ps(ll_v39.f32, simde_mm_dp_ps(simde_mm_load_ps(ll_v40.f32), simde_mm_load_ps(ll_v40.f32), 0xEF));
	simde_mm_store_ps(ll_v13.f32, REX_VRSQRTEFP(simde_mm_load_ps(ll_v39.f32)));
	simde_mm_store_si128((simde__m128i*)ll_v3.u8, simde_mm_load_si128((simde__m128i*)ll_v39.u8));
	simde_mm_store_ps(ll_v31.f32, simde_mm_cmpeq_ps(simde_mm_load_ps(ll_v63.f32), simde_mm_load_ps(ll_v39.f32)));
	simde_mm_store_ps(ll_v4.f32, simde_mm_mul_ps(simde_mm_load_ps(ll_v13.f32), simde_mm_load_ps(ll_v13.f32)));
	simde_mm_store_ps(ll_v30.f32, simde_mm_mul_ps(simde_mm_load_ps(ll_v13.f32), simde_mm_load_ps(ll_v58.f32)));
	simde_mm_store_ps(ll_v29.f32, REX_VNMSUBFP(simde_mm_load_ps(ll_v3.f32), simde_mm_load_ps(ll_v4.f32), simde_mm_load_ps(ll_v29.f32)));
	simde_mm_store_si128((simde__m128i*)ll_v3.u8, REX_VSEL(simde_mm_load_si128((simde__m128i*)ll_v16.u8), simde_mm_load_si128((simde__m128i*)ll_v9.u8), simde_mm_load_si128((simde__m128i*)ll_v10.u8)));
	simde_mm_store_si128((simde__m128i*)ll_v9.u32, simde_mm_shuffle_epi32(simde_mm_load_si128((simde__m128i*)ll_v44.u32), 0xFF));
	simde_mm_store_ps(ll_v13.f32, REX_VMADDFP(simde_mm_load_ps(ll_v29.f32), simde_mm_load_ps(ll_v30.f32), simde_mm_load_ps(ll_v13.f32)));
	simde_mm_store_si128((simde__m128i*)ll_v4.u8, REX_VSEL(simde_mm_load_si128((simde__m128i*)ll_v31.u8), simde_mm_load_si128((simde__m128i*)ll_v13.u8), simde_mm_load_si128((simde__m128i*)ll_v5.u8)));
	simde_mm_store_si128((simde__m128i*)ll_v38.u32, simde_mm_shuffle_epi32(simde_mm_load_si128((simde__m128i*)ll_v4.u32), 0xFF));
	simde_mm_store_ps(ll_v4.f32, REX_VMADDFP(simde_mm_load_ps(ll_v28.f32), simde_mm_load_ps(ll_v1.f32), simde_mm_load_ps(ll_v27.f32)));
	simde_mm_store_ps(ll_v13.f32, simde_mm_mul_ps(simde_mm_load_ps(ll_v40.f32), simde_mm_load_ps(ll_v38.f32)));
	simde_mm_store_si128((simde__m128i*)ll_v5.u8, REX_VSEL(simde_mm_load_si128((simde__m128i*)ll_v17.u8), simde_mm_load_si128((simde__m128i*)ll_v13.u8), simde_mm_load_si128((simde__m128i*)ll_v6.u8)));
	simde_mm_store_si128((simde__m128i*)ll_v6.u32, simde_mm_shuffle_epi32(simde_mm_load_si128((simde__m128i*)ll_v44.u32), 0xAA));
	simde_mm_store_si128((simde__m128i*)ll_v13.u8, REX_VSEL(simde_mm_load_si128((simde__m128i*)ll_v15.u8), simde_mm_load_si128((simde__m128i*)ll_v11.u8), simde_mm_load_si128((simde__m128i*)ll_v12.u8)));
	simde_mm_store_si128((simde__m128i*)ll_v11.u8, simde_mm_load_si128((simde__m128i*)ll_v3.u8));
	simde_mm_store_si128((simde__m128i*)ll_v12.u8, simde_mm_load_si128((simde__m128i*)ll_v48.u8));
	simde_mm_store_si128((simde__m128i*)ll_v37.u8, simde_mm_load_si128((simde__m128i*)ll_v13.u8));
	simde_mm_store_si128((simde__m128i*)ll_v13.u8, simde_mm_load_si128((simde__m128i*)ll_v49.u8));
	simde_mm_store_ps(ll_v3.f32, simde_mm_mul_ps(simde_mm_load_ps(ll_v37.f32), simde_mm_load_ps(ll_v41.f32)));
	simde_mm_store_si128((simde__m128i*)ll_v35.u32, simde_mm_shuffle_epi32(simde_mm_load_si128((simde__m128i*)ll_v2.u32), 0x55));
	ea = (ll_r4.u32) & ~0xF;
	simde_mm_store_si128((simde__m128i*)ll_v7.u8, REX_BSWAP128(simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR(ea))));
	simde_mm_store_si128((simde__m128i*)ll_v8.u32, simde_mm_shuffle_epi32(simde_mm_load_si128((simde__m128i*)ll_v2.u32), 0xAA));
	simde_mm_store_ps(ll_v6.f32, REX_VMADDFP(simde_mm_load_ps(ll_v11.f32), simde_mm_load_ps(ll_v6.f32), simde_mm_load_ps(ll_v3.f32)));
	simde_mm_store_si128((simde__m128i*)ll_v36.u8, REX_VPERM1(simde_mm_load_si128((simde__m128i*)ll_v4.u8), simde_mm_load_si128((simde__m128i*)ll_v7.u8)));
	temp.u32 = ll_r9.u32;
	simde_mm_store_si128((simde__m128i*)ll_v4.u8, simde_mm_load_si128((simde__m128i*)&VectorShiftTableR[(temp.u32 & 0xF) * 16]));
	simde_mm_store_si128((simde__m128i*)ll_v10.u32, simde_mm_shuffle_epi32(simde_mm_load_si128((simde__m128i*)ll_v2.u32), 0xFF));
	ll_r10.s64 = r11.s64 + -16;
	simde_mm_store_ps(ll_v7.f32, simde_mm_mul_ps(simde_mm_load_ps(ll_v37.f32), simde_mm_load_ps(ll_v35.f32)));
	simde_mm_store_si128((simde__m128i*)ll_v34.u8, REX_VPERM1(simde_mm_load_si128((simde__m128i*)ll_v0.u8), simde_mm_load_si128((simde__m128i*)ll_v4.u8)));
	temp.u32 = r11.u32;
	simde_mm_store_si128((simde__m128i*)ll_v1.u8, simde_mm_load_si128((simde__m128i*)&VectorShiftTableR[(temp.u32 & 0xF) * 16]));
	simde_mm_store_ps(ll_v62.f32, simde_mm_add_ps(simde_mm_load_ps(ll_v62.f32), simde_mm_load_ps(ll_v59.f32)));
	ll_r8.s64 = ll_r8.s64 + 16;
	temp.u32 = ll_r10.u32;
	simde_mm_store_si128((simde__m128i*)ll_v2.u8, simde_mm_load_si128((simde__m128i*)&VectorShiftTableR[(temp.u32 & 0xF) * 16]));
	if (ll_r5.u32 == 4u && r31.u32 == 8u && ll_r3.u32 == 12u && detail::Straight(ll_r6.u32 & ~0x3u, 16u)) [[likely]] {
		// sasrt-nx: the four stvewx of ll_v36 (each the lane its address selects) as one 16-byte store
		if (!detail::StoreWordsOfVector(base, s, ll_r6.u32 & ~0x3u, ll_v36)) return true;
		ea = (ll_r6.u32 + ll_r3.u32) & ~0x3;
	} else {
		ea = (ll_r6.u32) & ~0x3;
		BANJO_HOT_STORE_U32_C(ea, ll_v36.u32[3 - ((ea & 0xF) >> 2)]);
		if (s.Stopped()) return true;
		ea = (ll_r6.u32 + ll_r5.u32) & ~0x3;
		BANJO_HOT_STORE_U32_C(ea, ll_v36.u32[3 - ((ea & 0xF) >> 2)]);
		if (s.Stopped()) return true;
		ea = (ll_r6.u32 + r31.u32) & ~0x3;
		BANJO_HOT_STORE_U32_C(ea, ll_v36.u32[3 - ((ea & 0xF) >> 2)]);
		if (s.Stopped()) return true;
		ea = (ll_r6.u32 + ll_r3.u32) & ~0x3;
		BANJO_HOT_STORE_U32_C(ea, ll_v36.u32[3 - ((ea & 0xF) >> 2)]);
		if (s.Stopped()) return true;
	}
	ll_r6.s64 = ll_r6.s64 + 64;
	simde_mm_store_ps(ll_v0.f32, REX_VMADDFP(simde_mm_load_ps(ll_v11.f32), simde_mm_load_ps(ll_v8.f32), simde_mm_load_ps(ll_v7.f32)));
	simde_mm_store_ps(ll_v11.f32, REX_VMADDFP(simde_mm_load_ps(ll_v5.f32), simde_mm_load_ps(ll_v9.f32), simde_mm_load_ps(ll_v6.f32)));
	simde_mm_store_ps(ll_v0.f32, REX_VMADDFP(simde_mm_load_ps(ll_v5.f32), simde_mm_load_ps(ll_v10.f32), simde_mm_load_ps(ll_v0.f32)));
	simde_mm_store_si128((simde__m128i*)ll_v10.u8, simde_mm_load_si128((simde__m128i*)ll_v57.u8));
	simde_mm_store_si128((simde__m128i*)ll_v10.u8, REX_VSEL(simde_mm_load_si128((simde__m128i*)ll_v10.u8), simde_mm_load_si128((simde__m128i*)ll_v11.u8), simde_mm_load_si128((simde__m128i*)ll_v12.u8)));
	simde_mm_store_si128((simde__m128i*)ll_v33.u8, REX_VPERM1(simde_mm_load_si128((simde__m128i*)ll_v10.u8), simde_mm_load_si128((simde__m128i*)ll_v1.u8)));
	simde_mm_store_si128((simde__m128i*)ll_v12.u8, REX_VSEL(simde_mm_load_si128((simde__m128i*)ll_v14.u8), simde_mm_load_si128((simde__m128i*)ll_v0.u8), simde_mm_load_si128((simde__m128i*)ll_v13.u8)));
	simde_mm_store_si128((simde__m128i*)ll_v32.u8, REX_VPERM1(simde_mm_load_si128((simde__m128i*)ll_v12.u8), simde_mm_load_si128((simde__m128i*)ll_v2.u8)));
	if (ll_r5.u32 == 4u && r31.u32 == 8u && ll_r3.u32 == 12u && detail::Straight(ll_r10.u32 & ~0x3u, 16u)) [[likely]] {
		// sasrt-nx: the four stvewx of ll_v32 (each the lane its address selects) as one 16-byte store
		if (!detail::StoreWordsOfVector(base, s, ll_r10.u32 & ~0x3u, ll_v32)) return true;
		ea = (ll_r10.u32 + ll_r3.u32) & ~0x3;
	} else {
		ea = (ll_r10.u32) & ~0x3;
		BANJO_HOT_STORE_U32_C(ea, ll_v32.u32[3 - ((ea & 0xF) >> 2)]);
		if (s.Stopped()) return true;
		ea = (ll_r10.u32 + ll_r5.u32) & ~0x3;
		BANJO_HOT_STORE_U32_C(ea, ll_v32.u32[3 - ((ea & 0xF) >> 2)]);
		if (s.Stopped()) return true;
		ea = (ll_r10.u32 + r31.u32) & ~0x3;
		BANJO_HOT_STORE_U32_C(ea, ll_v32.u32[3 - ((ea & 0xF) >> 2)]);
		if (s.Stopped()) return true;
		ea = (ll_r10.u32 + ll_r3.u32) & ~0x3;
		BANJO_HOT_STORE_U32_C(ea, ll_v32.u32[3 - ((ea & 0xF) >> 2)]);
		if (s.Stopped()) return true;
	}
	if (ll_r5.u32 == 4u && r31.u32 == 8u && ll_r3.u32 == 12u && detail::Straight(r11.u32 & ~0x3u, 16u)) [[likely]] {
		// sasrt-nx: the four stvewx of ll_v33 (each the lane its address selects) as one 16-byte store
		if (!detail::StoreWordsOfVector(base, s, r11.u32 & ~0x3u, ll_v33)) return true;
		ea = (r11.u32 + ll_r3.u32) & ~0x3;
	} else {
		ea = (r11.u32) & ~0x3;
		BANJO_HOT_STORE_U32_C(ea, ll_v33.u32[3 - ((ea & 0xF) >> 2)]);
		if (s.Stopped()) return true;
		ea = (r11.u32 + ll_r5.u32) & ~0x3;
		BANJO_HOT_STORE_U32_C(ea, ll_v33.u32[3 - ((ea & 0xF) >> 2)]);
		if (s.Stopped()) return true;
		ea = (r11.u32 + r31.u32) & ~0x3;
		BANJO_HOT_STORE_U32_C(ea, ll_v33.u32[3 - ((ea & 0xF) >> 2)]);
		if (s.Stopped()) return true;
		ea = (r11.u32 + ll_r3.u32) & ~0x3;
		BANJO_HOT_STORE_U32_C(ea, ll_v33.u32[3 - ((ea & 0xF) >> 2)]);
		if (s.Stopped()) return true;
	}
	r11.s64 = r11.s64 + 64;
	if (ll_r5.u32 == 4u && r31.u32 == 8u && ll_r3.u32 == 12u && detail::Straight(ll_r9.u32 & ~0x3u, 16u)) [[likely]] {
		// sasrt-nx: the four stvewx of ll_v34 (each the lane its address selects) as one 16-byte store
		if (!detail::StoreWordsOfVector(base, s, ll_r9.u32 & ~0x3u, ll_v34)) return true;
		ea = (ll_r9.u32 + ll_r3.u32) & ~0x3;
	} else {
		ea = (ll_r9.u32) & ~0x3;
		BANJO_HOT_STORE_U32_C(ea, ll_v34.u32[3 - ((ea & 0xF) >> 2)]);
		if (s.Stopped()) return true;
		ea = (ll_r9.u32 + ll_r5.u32) & ~0x3;
		BANJO_HOT_STORE_U32_C(ea, ll_v34.u32[3 - ((ea & 0xF) >> 2)]);
		if (s.Stopped()) return true;
		ea = (ll_r9.u32 + r31.u32) & ~0x3;
		BANJO_HOT_STORE_U32_C(ea, ll_v34.u32[3 - ((ea & 0xF) >> 2)]);
		if (s.Stopped()) return true;
		ea = (ll_r9.u32 + ll_r3.u32) & ~0x3;
		BANJO_HOT_STORE_U32_C(ea, ll_v34.u32[3 - ((ea & 0xF) >> 2)]);
		if (s.Stopped()) return true;
	}
	--ctr.u64;
	if (ctr.u32 != 0) goto loc_8286C7E4;
	s.Hit(29);
	r21.u64 = REX_LOAD_D_U32(ll_r1.u32, 88);
	r19.u64 = REX_LOAD_D_U32(ll_r1.u32, 84);
	r28.u64 = REX_LOAD_D_U32(ll_r1.u32, 80);
	ll_r9.u64 = REX_LOAD_D_U32(ll_r1.u32, 208);
	ll_r4.u64 = REX_LOAD_D_U32(ll_r1.u32, 380);
loc_8286C9E0:
	s.Hit(30);
	xer.ca = r28.u32 > 0;
	r28.s64 = r28.s64 + -1;
	cr0.compare<int32_t>(r28.s32, 0, xer);
	BANJO_HOT_STORE_D_U32(ll_r1.u32, 80, r28.u32);
	if (s.Stopped()) return true;
	if (!cr0.eq) goto loc_8286C654;
	s.Hit(31);
	REX_LOOP_OUT(ll_r4, l_r4);
	REX_LOOP_OUT(ll_r6, l_r6);
	REX_LOOP_OUT(ll_r8, l_r8);
	REX_LOOP_OUT(ll_r9, l_r9);
	REX_LOOP_OUT(ll_r10, l_r10);
	REX_LOOP_OUT(ll_v0, l_v0);
	REX_LOOP_OUT(ll_v1, l_v1);
	REX_LOOP_OUT(ll_v2, l_v2);
	REX_LOOP_OUT(ll_v3, l_v3);
	REX_LOOP_OUT(ll_v4, l_v4);
	REX_LOOP_OUT(ll_v5, l_v5);
	REX_LOOP_OUT(ll_v6, l_v6);
	REX_LOOP_OUT(ll_v7, l_v7);
	REX_LOOP_OUT(ll_v8, l_v8);
	REX_LOOP_OUT(ll_v9, l_v9);
	REX_LOOP_OUT(ll_v10, l_v10);
	REX_LOOP_OUT(ll_v11, l_v11);
	REX_LOOP_OUT(ll_v12, l_v12);
	REX_LOOP_OUT(ll_v13, l_v13);
	REX_LOOP_OUT(ll_v14, l_v14);
	REX_LOOP_OUT(ll_v15, l_v15);
	REX_LOOP_OUT(ll_v16, l_v16);
	REX_LOOP_OUT(ll_v17, l_v17);
	REX_LOOP_OUT(ll_v18, l_v18);
	REX_LOOP_OUT(ll_v19, l_v19);
	REX_LOOP_OUT(ll_v20, l_v20);
	REX_LOOP_OUT(ll_v21, l_v21);
	REX_LOOP_OUT(ll_v22, l_v22);
	REX_LOOP_OUT(ll_v23, l_v23);
	REX_LOOP_OUT(ll_v24, l_v24);
	REX_LOOP_OUT(ll_v25, l_v25);
	REX_LOOP_OUT(ll_v26, l_v26);
	REX_LOOP_OUT(ll_v27, l_v27);
	REX_LOOP_OUT(ll_v28, l_v28);
	REX_LOOP_OUT(ll_v29, l_v29);
	REX_LOOP_OUT(ll_v30, l_v30);
	REX_LOOP_OUT(ll_v31, l_v31);
	REX_LOOP_OUT(ll_v32, l_v32);
	REX_LOOP_OUT(ll_v33, l_v33);
	REX_LOOP_OUT(ll_v34, l_v34);
	REX_LOOP_OUT(ll_v35, l_v35);
	REX_LOOP_OUT(ll_v36, l_v36);
	REX_LOOP_OUT(ll_v37, l_v37);
	REX_LOOP_OUT(ll_v38, l_v38);
	REX_LOOP_OUT(ll_v39, l_v39);
	REX_LOOP_OUT(ll_v40, l_v40);
	REX_LOOP_OUT(ll_v41, l_v41);
	REX_LOOP_OUT(ll_v42, l_v42);
	REX_LOOP_OUT(ll_v43, l_v43);
	REX_LOOP_OUT(ll_v44, l_v44);
	REX_LOOP_OUT(ll_v45, l_v45);
	REX_LOOP_OUT(ll_v46, l_v46);
	REX_LOOP_OUT(ll_v47, l_v47);
	REX_LOOP_OUT(ll_v48, l_v48);
	REX_LOOP_OUT(ll_v49, l_v49);
	REX_LOOP_OUT(ll_v50, l_v50);
	REX_LOOP_OUT(ll_v51, l_v51);
	REX_LOOP_OUT(ll_v52, l_v52);
	REX_LOOP_OUT(ll_v53, l_v53);
	REX_LOOP_OUT(ll_v54, l_v54);
	REX_LOOP_OUT(ll_v55, l_v55);
	REX_LOOP_OUT(ll_v56, l_v56);
	REX_LOOP_OUT(ll_v57, l_v57);
	REX_LOOP_OUT(ll_v58, l_v58);
	REX_LOOP_OUT(ll_v59, l_v59);
	REX_LOOP_OUT(ll_v60, l_v60);
	REX_LOOP_OUT(ll_v61, l_v61);
	REX_LOOP_OUT(ll_v62, l_v62);
	REX_LOOP_OUT(ll_v63, l_v63);
loc_8286C9EC:
	s.Hit(32);
	l_r3.u64 = REX_LOAD_D_U32(l_r1.u32, 224);
	{ ctx.r3 = l_r3; if (!::banjo::hand::n_82C92CC8::Native(ctx, base, s)) { if (s.Open()) return true; ctx.f10 = l_f10; ctx.f11 = l_f11; ctx.f12 = l_f12; ctx.f13 = l_f13; ctx.r1 = l_r1; ctx.r3 = l_r3; ctx.r4 = l_r4; ctx.r5 = l_r5; ctx.r6 = l_r6; ctx.r7 = l_r7; ctx.r8 = l_r8; ctx.r9 = l_r9; ctx.r10 = l_r10; ctx.v0 = l_v0; ctx.v1 = l_v1; ctx.v2 = l_v2; ctx.v3 = l_v3; ctx.v4 = l_v4; ctx.v5 = l_v5; ctx.v6 = l_v6; ctx.v7 = l_v7; ctx.v8 = l_v8; ctx.v9 = l_v9; ctx.v10 = l_v10; ctx.v11 = l_v11; ctx.v12 = l_v12; ctx.v13 = l_v13; ctx.v14 = l_v14; ctx.v15 = l_v15; ctx.v16 = l_v16; ctx.v17 = l_v17; ctx.v18 = l_v18; ctx.v19 = l_v19; ctx.v20 = l_v20; ctx.v21 = l_v21; ctx.v22 = l_v22; ctx.v23 = l_v23; ctx.v24 = l_v24; ctx.v25 = l_v25; ctx.v26 = l_v26; ctx.v27 = l_v27; ctx.v28 = l_v28; ctx.v29 = l_v29; ctx.v30 = l_v30; ctx.v31 = l_v31; ctx.v32 = l_v32; ctx.v33 = l_v33; ctx.v34 = l_v34; ctx.v35 = l_v35; ctx.v36 = l_v36; ctx.v37 = l_v37; ctx.v38 = l_v38; ctx.v39 = l_v39; ctx.v40 = l_v40; ctx.v41 = l_v41; ctx.v42 = l_v42; ctx.v43 = l_v43; ctx.v44 = l_v44; ctx.v45 = l_v45; ctx.v46 = l_v46; ctx.v47 = l_v47; ctx.v48 = l_v48; ctx.v49 = l_v49; ctx.v50 = l_v50; ctx.v51 = l_v51; ctx.v52 = l_v52; ctx.v53 = l_v53; ctx.v54 = l_v54; ctx.v55 = l_v55; ctx.v56 = l_v56; ctx.v57 = l_v57; ctx.v58 = l_v58; ctx.v59 = l_v59; ctx.v60 = l_v60; ctx.v61 = l_v61; ctx.v62 = l_v62; ctx.v63 = l_v63; sub_82C92CC8(ctx, base); l_f10 = ctx.f10; l_f11 = ctx.f11; l_f12 = ctx.f12; l_f13 = ctx.f13; l_r1 = ctx.r1; l_r3 = ctx.r3; l_r4 = ctx.r4; l_r5 = ctx.r5; l_r6 = ctx.r6; l_r7 = ctx.r7; l_r8 = ctx.r8; l_r9 = ctx.r9; l_r10 = ctx.r10; l_v0 = ctx.v0; l_v1 = ctx.v1; l_v2 = ctx.v2; l_v3 = ctx.v3; l_v4 = ctx.v4; l_v5 = ctx.v5; l_v6 = ctx.v6; l_v7 = ctx.v7; l_v8 = ctx.v8; l_v9 = ctx.v9; l_v10 = ctx.v10; l_v11 = ctx.v11; l_v12 = ctx.v12; l_v13 = ctx.v13; l_v14 = ctx.v14; l_v15 = ctx.v15; l_v16 = ctx.v16; l_v17 = ctx.v17; l_v18 = ctx.v18; l_v19 = ctx.v19; l_v20 = ctx.v20; l_v21 = ctx.v21; l_v22 = ctx.v22; l_v23 = ctx.v23; l_v24 = ctx.v24; l_v25 = ctx.v25; l_v26 = ctx.v26; l_v27 = ctx.v27; l_v28 = ctx.v28; l_v29 = ctx.v29; l_v30 = ctx.v30; l_v31 = ctx.v31; l_v32 = ctx.v32; l_v33 = ctx.v33; l_v34 = ctx.v34; l_v35 = ctx.v35; l_v36 = ctx.v36; l_v37 = ctx.v37; l_v38 = ctx.v38; l_v39 = ctx.v39; l_v40 = ctx.v40; l_v41 = ctx.v41; l_v42 = ctx.v42; l_v43 = ctx.v43; l_v44 = ctx.v44; l_v45 = ctx.v45; l_v46 = ctx.v46; l_v47 = ctx.v47; l_v48 = ctx.v48; l_v49 = ctx.v49; l_v50 = ctx.v50; l_v51 = ctx.v51; l_v52 = ctx.v52; l_v53 = ctx.v53; l_v54 = ctx.v54; l_v55 = ctx.v55; l_v56 = ctx.v56; l_v57 = ctx.v57; l_v58 = ctx.v58; l_v59 = ctx.v59; l_v60 = ctx.v60; l_v61 = ctx.v61; l_v62 = ctx.v62; l_v63 = ctx.v63; } else { if (s.Stopped()) return true; } }
	l_r1.s64 = l_r1.s64 + 352;
	{ ctx.f10 = l_f10; ctx.f11 = l_f11; ctx.f12 = l_f12; ctx.f13 = l_f13; ctx.r1 = l_r1; ctx.r4 = l_r4; ctx.r5 = l_r5; ctx.r6 = l_r6; ctx.r7 = l_r7; ctx.r8 = l_r8; ctx.r9 = l_r9; ctx.r10 = l_r10; ctx.v0 = l_v0; ctx.v1 = l_v1; ctx.v2 = l_v2; ctx.v3 = l_v3; ctx.v4 = l_v4; ctx.v5 = l_v5; ctx.v6 = l_v6; ctx.v7 = l_v7; ctx.v8 = l_v8; ctx.v9 = l_v9; ctx.v10 = l_v10; ctx.v11 = l_v11; ctx.v12 = l_v12; ctx.v13 = l_v13; ctx.v14 = l_v14; ctx.v15 = l_v15; ctx.v16 = l_v16; ctx.v17 = l_v17; ctx.v18 = l_v18; ctx.v19 = l_v19; ctx.v20 = l_v20; ctx.v21 = l_v21; ctx.v22 = l_v22; ctx.v23 = l_v23; ctx.v24 = l_v24; ctx.v25 = l_v25; ctx.v26 = l_v26; ctx.v27 = l_v27; ctx.v28 = l_v28; ctx.v29 = l_v29; ctx.v30 = l_v30; ctx.v31 = l_v31; ctx.v32 = l_v32; ctx.v33 = l_v33; ctx.v34 = l_v34; ctx.v35 = l_v35; ctx.v36 = l_v36; ctx.v37 = l_v37; ctx.v38 = l_v38; ctx.v39 = l_v39; ctx.v40 = l_v40; ctx.v41 = l_v41; ctx.v42 = l_v42; ctx.v43 = l_v43; ctx.v44 = l_v44; ctx.v45 = l_v45; ctx.v46 = l_v46; ctx.v47 = l_v47; ctx.v48 = l_v48; ctx.v49 = l_v49; ctx.v50 = l_v50; ctx.v51 = l_v51; ctx.v52 = l_v52; ctx.v53 = l_v53; ctx.v54 = l_v54; ctx.v55 = l_v55; ctx.v56 = l_v56; ctx.v57 = l_v57; ctx.v58 = l_v58; ctx.v59 = l_v59; ctx.v60 = l_v60; ctx.v61 = l_v61; ctx.v62 = l_v62; ctx.v63 = l_v63; return true; }
	return true;
}

}  // namespace n_8286C230

}  // namespace banjo::hand
