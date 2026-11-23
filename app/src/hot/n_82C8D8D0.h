// sub_82C8D8D0 - XDK CRT memset: r3 = dst, r4 = value (its low byte), r5 = n; returns r3 = dst unchanged.
// (sa2-nx's n_827EFEA0.h, the same routine: found here by its signature, tools/crt_signatures.py of sa2-nx, unique;
// sasrt-nx 2026-10-14, idea 4 of sa2-nx's list: library natives by signature.)
//
// The original (ori r6,r3,0; ctr = n + 1): stores single bytes until r6 is 4-aligned or n is used up, replicates the
// low byte of r4 into a word (rlwimi x2), then 16-byte blocks of four stw, then up to three stw, then up to three stb.
// Every store writes the low byte of r4 (or that byte replicated), each byte of [dst, dst + n) exactly once, nothing
// outside it, nothing on the stack, and nothing is read. So the effect is memset(dst, r4 & 0xFF, n).
// Declined (the original runs): garbage in the upper half of r5 (ctr = r5 + 1 is 64-bit: the head loop could run
// past n), ranges that wrap around 4 GB or leave a physical view.
// Registers: r0, r4, r5, r6, ctr, cr0 are scratch of an assembly routine; the native writes no register.
#pragma once

#include "hot/sasrt_hot_common.h"

namespace sasrt::hot::n_82C8D8D0 {

inline bool Native(PPCContext& ctx, uint8_t* base) {
  if (ctx.r5.u64 >> 32) return false;
  const uint32_t dst = ctx.r3.u32, n = ctx.r5.u32;
  if (n == 0) return true;
  if (CrossesView(dst, n)) return false;
  std::memset(Raw(base, dst), int(ctx.r4.u32 & 0xFF), n);
  Card(base, dst, n);  // sasrt-nx (2026-10-21): the store cards (sasrt_hot_common.h)
  return true;
}

inline void Writes(const PPCContext& ctx, const uint8_t*, ::sasrt::hot::Writes& w) { w.Add(ctx.r3.u32, ctx.r5.u32); }

}  // namespace sasrt::hot::n_82C8D8D0
