// The XDK's two shader float-constant writers (Direct3D, called for every constant upload of every draw), found here
// by their signatures (tools/crt_signatures.py of sa2-nx; byte for byte sa2-nx's 8255D990 / 8255D8B8, same FNV-1a
// hashes). sa2-nx's n_d3d_constants.h, ported 2026-10-14 (idea 4 of sa2-nx's list: library natives by signature):
//   sub_82CC2368: r3 = device, r4 = first constant, r5 = source (any alignment), r6 = count of 16-byte vectors,
//                 r7 = 64-bit dirty bits. Destination (r3 + (r4 + 376) * 16) & ~15; dirty mask at r3 + 8.
//   sub_82CC2260: the same with (r4 + 120) and the dirty mask at r3 + 0.
// (sa2-nx's console profile: 1.3 % and 1.2 % of its game thread.)
//
// The originals copy four vectors per iteration and then one per iteration: lvlx128 + lvrx128 + vor128 is an
// unaligned 16-byte load at r11 (lvrx at r11 + 16 loads nothing when r11 is aligned), stvx128 an aligned store at
// r10 & ~15, r10 and r11 advance by 16 per vector; dcbt are hints. Then ld / or r7 / std on the dirty mask. Facts used:
//   * every address is the 32-bit part (ea = u32 + u32); the vector count is r6 (cmplwi, mtctr of r6 - 4k): a count
//     with nonzero upper 32 bits would make the 64-bit CTR huge, so the native DECLINES it;
//   * the destination of vector k is ((r3 + (r4 + first) * 16) & ~15) + 16 k, its source r5 + 16 k: for
//     non-overlapping ranges that is a plain copy of 16 * count bytes, in guest byte order; overlapping ranges are
//     DECLINED (the four-at-a-time loop loads before it stores), as are ranges that wrap around 4 GB or leave a
//     physical view, and (sasrt-nx) ranges that may share bytes through two different physical views;
//   * the dirty mask is updated after the copy (the same order here).
// Registers: the originals leave r4-r11, CTR, CR6 and v59-v63 as scratch (some only on some paths, so callers compiled
// with interprocedural allocation must treat them all as clobbered); the native writes no register at all.
#pragma once

#include "hot/sasrt_hot_common.h"

namespace sasrt::hot::d3d_constants {

// sasrt-nx (2026-10-30, diagnostics, sasrt_diag_ps_constant_watch in sasrt_hot_guest.cpp): a pixel shader constant
// register to watch; each upload that covers it logs the value and the guest caller (the first of each caller).
void WatchPixelConstant(const PPCContext& ctx, const uint8_t* base);
extern int32_t g_watch_ps_register;

struct Plan {
  uint32_t dst, src, mask;
  uint64_t bytes;
};

inline Plan PlanOf(const PPCContext& c, uint32_t first, uint32_t mask_offset) {
  return {(((c.r4.u32 + first) << 4) + c.r3.u32) & ~15u, c.r5.u32, c.r3.u32 + mask_offset, uint64_t(c.r6.u32) * 16};
}

inline bool Upload(PPCContext& ctx, uint8_t* base, uint32_t first, uint32_t mask_offset) {
  if (ctx.r6.u64 >> 32) return false;
  const Plan p = PlanOf(ctx, first, mask_offset);
  if (CrossesView(p.mask, 8)) return false;  // every decision before anything is written
  if (p.bytes) {
    if (p.bytes > 0xFFFFFFFFull) return false;
    const uint32_t n = uint32_t(p.bytes);
    if (CrossesView(p.dst, n) || CrossesView(p.src, n)) return false;
    if (MayOverlap(p.dst, p.src, n)) return false;
    std::memcpy(Raw(base, p.dst), Raw(base, p.src), n);
    Card(base, p.dst, n);  // sasrt-nx (2026-10-21): the store cards (sasrt_hot_common.h)
  }
  uint64_t m;
  std::memcpy(&m, Raw(base, p.mask), 8);
  m = __builtin_bswap64(__builtin_bswap64(m) | ctx.r7.u64);
  std::memcpy(Raw(base, p.mask), &m, 8);
  Card(base, p.mask, 8);
  return true;
}

inline void WritesOf(const PPCContext& c, ::sasrt::hot::Writes& w, uint32_t first, uint32_t mask_offset) {
  const Plan p = PlanOf(c, first, mask_offset);
  if (p.bytes) {
    if (p.bytes > ::sasrt::hot::Writes::kMaxBytes) {
      w.overflow = true;
      return;
    }
    w.Add(p.dst, uint32_t(p.bytes));
  }
  w.Add(p.mask, 8);
}

}  // namespace sasrt::hot::d3d_constants

namespace sasrt::hot::n_82CC2368 {
inline bool Native(PPCContext& ctx, uint8_t* base) {
  if (d3d_constants::g_watch_ps_register >= 0) [[unlikely]]
    d3d_constants::WatchPixelConstant(ctx, base);
  return d3d_constants::Upload(ctx, base, 376, 8);
}
inline void Writes(const PPCContext& c, const uint8_t*, ::sasrt::hot::Writes& w) {
  d3d_constants::WritesOf(c, w, 376, 8);
}
}  // namespace sasrt::hot::n_82CC2368

namespace sasrt::hot::n_82CC2260 {
inline bool Native(PPCContext& ctx, uint8_t* base) { return d3d_constants::Upload(ctx, base, 120, 0); }
inline void Writes(const PPCContext& c, const uint8_t*, ::sasrt::hot::Writes& w) {
  d3d_constants::WritesOf(c, w, 120, 0);
}
}  // namespace sasrt::hot::n_82CC2260
