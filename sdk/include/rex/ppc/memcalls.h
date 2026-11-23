/**
 * @file        rex/ppc/memcalls.h
 * @brief       The pure parts of the inline constant-size memcpy / memset (sasrt-nx, 2026-10-14)
 *
 * tools/inline_memcalls.py writes the C runtime's memcpy / memset calls whose size is a constant of 1-64 bytes as
 * REX_MEMCPY_CONST / REX_MEMSET_CONST (sa2-nx's idea 6, sonic-unleashed-nx's SWITCH_INLINE_MEMCPY). The helpers that
 * touch guest memory live in the generated pch (they need its address macros); what they decide with lives here, so
 * sdk/tests/memcalls_test.cpp tests the same code.
 */
#pragma once

#include <cstdint>

namespace rex::ppc {

/// A guest range of N bytes the inline helpers may handle: not in 0x7F000000-0x7FFFFFFF (hardware registers, where
/// the width of each write matters) or from 0xA0000000 (the physical views, which alias each other: two different
/// guest addresses can be the same memory), and not wrapping around 4 GB. Anything else runs the original routine.
template <uint32_t N>
[[gnu::always_inline]] inline bool PlainRange(uint32_t x) noexcept {
  static_assert(N >= 1 && N <= 64);
  const uint32_t e = x + (N - 1);
  if (e < x) return false;
  if (x < 0x7F000000u) return e < 0x7F000000u;
  return x >= 0x80000000u && e < 0xA0000000u;
}

/// The CRT memcpy copies forward, unit by unit with each unit's loads before its stores: for dst <= src that is what
/// memmove gives, for dst > src with overlapping ranges it smears already-copied bytes. The helper copies like
/// memmove, so that case must run the original: true when dst > src and dst - src < N.
template <uint32_t N>
[[gnu::always_inline]] inline bool CopySmears(uint32_t dst, uint32_t src) noexcept {
  return uint32_t(dst - src - 1u) < N - 1u;
}

/// The CRT memcpy stores r3 at -8(r1) first and RELOADS r3 from that slot before every return: a copy whose
/// destination covers any byte of [slot, slot + 8) returns copied bytes in r3. The helper leaves r3 as it came, so that
/// case must run the original (banjo-nx found it, 2026-10-14). True when [dst, dst + N) and [slot, slot + 8) overlap.
template <uint32_t N>
[[gnu::always_inline]] inline bool CoversSlot(uint32_t dst, uint32_t slot) noexcept {
  return uint64_t(uint32_t(slot + 7u - dst)) < uint64_t(N) + 7u;
}

/// N bytes, 1 <= N <= 64, every load before every store (the native memcpy's CopySmall with N known at compile
/// time: two to eight loads and as many stores, overlapping where N is not a power of two).
template <uint32_t N>
[[gnu::always_inline]] inline void CopyConst(uint8_t* d, const uint8_t* s) noexcept {
  static_assert(N >= 1 && N <= 64);
  if constexpr (N > 32) {
    uint8_t a[16], b[16], c[16], e[16];
    __builtin_memcpy(a, s, 16);
    __builtin_memcpy(b, s + 16, 16);
    __builtin_memcpy(c, s + N - 32, 16);
    __builtin_memcpy(e, s + N - 16, 16);
    __builtin_memcpy(d, a, 16);
    __builtin_memcpy(d + 16, b, 16);
    __builtin_memcpy(d + N - 32, c, 16);
    __builtin_memcpy(d + N - 16, e, 16);
  } else if constexpr (N >= 16) {
    uint8_t a[16], e[16];
    __builtin_memcpy(a, s, 16);
    __builtin_memcpy(e, s + N - 16, 16);
    __builtin_memcpy(d, a, 16);
    __builtin_memcpy(d + N - 16, e, 16);
  } else if constexpr (N >= 8) {
    uint64_t a, e;
    __builtin_memcpy(&a, s, 8);
    __builtin_memcpy(&e, s + N - 8, 8);
    __builtin_memcpy(d, &a, 8);
    __builtin_memcpy(d + N - 8, &e, 8);
  } else if constexpr (N >= 4) {
    uint32_t a, e;
    __builtin_memcpy(&a, s, 4);
    __builtin_memcpy(&e, s + N - 4, 4);
    __builtin_memcpy(d, &a, 4);
    __builtin_memcpy(d + N - 4, &e, 4);
  } else if constexpr (N >= 2) {
    uint16_t a, e;
    __builtin_memcpy(&a, s, 2);
    __builtin_memcpy(&e, s + N - 2, 2);
    __builtin_memcpy(d, &a, 2);
    __builtin_memcpy(d + N - 2, &e, 2);
  } else {
    *d = *s;
  }
}

}  // namespace rex::ppc
