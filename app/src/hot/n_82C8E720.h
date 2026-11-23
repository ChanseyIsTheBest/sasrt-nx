// sub_82C8E720 - XDK CRT memmove: r3 = dst, r4 = src, r5 = n; returns r3 = dst (all 64 bits).
// (sa2-nx's n_827EF8B0.h, the same routine up to one branch target: found here by its signature; sasrt-nx 2026-10-14,
// idea 4 of sa2-nx's list.)
//
// The original compares the low words SIGNED (cmpw r3,r4): equal -> return; dst < src -> tail branch to memcpy
// (through the jump thunk 823F1FD0 to sub_82C8EEF0, a forward copy whose first instruction is `std r3,-8(r1)`);
// dst > src -> backward copy (byte tail down to a 4-aligned dst end, words - assembled from bytes when src is
// unaligned - then bytes), r3/r4 run from dst + n / src + n back down, so r3 ends equal to dst; no stack store.
// The forward copy equals memmove when dst <= src (unsigned) or the ranges do not overlap; the backward copy when
// dst >= src or no overlap. The two orders only disagree for ranges on both sides of 0x80000000: an overlap there is
// declined (the original runs). Also declined: garbage in the upper half of r5 (ctr = r5 + 1 is 64-bit), ranges that
// wrap around 4 GB or leave a physical view, ranges that may share bytes through two different views, and (memcpy
// path) a copy onto the stack word memcpy saves r3 in.
// Registers: r0, r4, r5, r7-r10, ctr, cr0/cr6 are scratch of an assembly routine; r3 ends as it started; the native
// writes no register. The memcpy path stores r3 at -8(r1) as memcpy does (lesson (b) of sa2-nx's audit).
#pragma once

#include "hot/sasrt_hot_common.h"

namespace sasrt::hot::n_82C8E720 {

inline bool ViaMemcpy(const PPCContext& ctx) { return int32_t(ctx.r3.u32) < int32_t(ctx.r4.u32); }

inline bool Native(PPCContext& ctx, uint8_t* base) {
  if (ctx.r5.u64 >> 32) return false;
  const uint32_t dst = ctx.r3.u32, src = ctx.r4.u32, n = ctx.r5.u32;
  if (dst == src) return true;  // cmpw equal: beqlr, before anything else
  const bool via_memcpy = ViaMemcpy(ctx);
  const uint32_t saved = ctx.r1.u32 - 8;
  if (n) {
    if (CrossesView(dst, n) || CrossesView(src, n)) return false;
    const bool overlap = dst < src ? src - dst < n : dst - src < n;
    if (overlap && via_memcpy != (dst < src)) return false;  // signed and unsigned order disagree
    if (!overlap && MayOverlap(dst, src, n)) return false;  // the same bytes through two views
    if (via_memcpy && (uint32_t(saved - dst) < n || uint32_t(dst - saved) < 8)) return false;
  }
  if (via_memcpy) {
    const uint64_t v = __builtin_bswap64(ctx.r3.u64);
    std::memcpy(Raw(base, saved), &v, 8);
  }
  if (n) {
    std::memmove(Raw(base, dst), Raw(base, src), n);
    Card(base, dst, n);  // sasrt-nx (2026-10-21): the store cards (sasrt_hot_common.h)
  }
  return true;
}

inline void Writes(const PPCContext& ctx, const uint8_t*, ::sasrt::hot::Writes& w) {
  if (ctx.r3.u32 == ctx.r4.u32) return;
  w.Add(ctx.r3.u32, ctx.r5.u32);
  if (ViaMemcpy(ctx)) w.Add(ctx.r1.u32 - 8, 8);
}

}  // namespace sasrt::hot::n_82C8E720
