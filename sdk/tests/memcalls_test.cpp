// sasrt-nx (2026-10-14; idea 6 of sa2-nx's list): the inline constant-size memcpy (rex/ppc/memcalls.h, written by
// tools/inline_memcalls.py) against the semantics of the C runtime routine it replaces:
//   - CopyConst<N> for every N of 1-64 and every relative position of the two ranges within 160 bytes: where the
//     helper copies (CopySmears false), the result must be memmove's (the CRT routine's for dst <= src and for
//     ranges that do not overlap); CopySmears must be true exactly when dst > src and dst - src < N;
//   - PlainRange<N> at the edges of the hardware-register window (0x7F000000), the physical views (0xA0000000) and
//     4 GB.
//
//   clang++ -O2 -std=c++23 -Isdk/include sdk/tests/memcalls_test.cpp -o out/tools/memcalls_test.exe [run_sdk_tests]
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <utility>

#include <rex/ppc/memcalls.h>

namespace {

uint64_t g_checked = 0, g_failures = 0;

void Fail(const char* what, unsigned n, long a, long b) {
  if (g_failures++ < 12) std::printf("DIFFERENCE: %s N=%u (%ld, %ld)\n", what, n, a, b);
}

template <uint32_t N>
void CheckCopy() {
  uint8_t pattern[160], got[160], want[160];
  for (int i = 0; i < 160; ++i) pattern[i] = uint8_t(i * 37 + 11);
  for (int d = 0; d + int(N) <= 160; ++d) {
    for (int s = 0; s + int(N) <= 160; ++s) {
      const bool smears = rex::ppc::CopySmears<N>(uint32_t(d), uint32_t(s));
      const bool expect_smear = d > s && d - s < int(N);
      ++g_checked;
      if (smears != expect_smear) Fail("CopySmears", N, d, s);
      if (smears) continue;
      std::memcpy(got, pattern, 160);
      std::memcpy(want, pattern, 160);
      rex::ppc::CopyConst<N>(got + d, got + s);
      std::memmove(want + d, want + s, N);
      if (std::memcmp(got, want, 160) != 0) Fail("CopyConst", N, d, s);
    }
  }
}

template <uint32_t N>
void CheckRange() {
  struct Case {
    uint32_t x;
    bool plain;
  };
  const Case cases[] = {
      {0x00000000u, true},
      {0x7F000000u - N, true},
      {0x7F000000u - N + 1, false},  // the last byte reaches the hardware-register window
      {0x7F000000u, false},
      {0x7FFFFFFFu, false},
      {0x80000000u, true},
      {0x9FFFFFFFu - (N - 1), true},
      {0xA0000000u - N + 1, false},   // its last byte is 0xA0000000
      {0xA0000000u, false},
      {0xFFFFFFFFu - (N - 1), false},
      {0xFFFFFFF0u, false},
  };
  for (const Case& c : cases) {
    ++g_checked;
    if (rex::ppc::PlainRange<N>(c.x) != c.plain) Fail("PlainRange", N, long(c.x), c.plain);
  }
}

// CoversSlot<N>(dst, slot): exactly when [dst, dst + N) and the 8-byte slot share a byte (brute force), also across
// the 4 GB wrap.
template <uint32_t N>
void CheckSlot() {
  const uint32_t bases[] = {0x40001000u, 0x00000004u, 0xFFFFFFF0u};
  for (uint32_t base : bases) {
    for (int64_t off = -80; off <= 80; ++off) {
      const uint32_t dst = base, slot = uint32_t(int64_t(base) + off);
      bool overlap = false;
      for (uint32_t i = 0; i < N && !overlap; ++i)
        for (uint32_t j = 0; j < 8 && !overlap; ++j) overlap = uint32_t(dst + i) == uint32_t(slot + j);
      ++g_checked;
      if (rex::ppc::CoversSlot<N>(dst, slot) != overlap) Fail("CoversSlot", N, long(dst), long(off));
    }
  }
}

template <std::size_t... I>
void All(std::index_sequence<I...>) {
  (CheckCopy<uint32_t(I + 1)>(), ...);
  (CheckRange<uint32_t(I + 1)>(), ...);
  (CheckSlot<uint32_t(I + 1)>(), ...);
}

}  // namespace

int main() {
  All(std::make_index_sequence<64>());
  std::printf("%llu checks of the inline constant-size memcpy (N = 1..64, every relative position)\n",
              (unsigned long long)g_checked);
  std::printf(g_failures ? "RESULT: FAILED (%llu differences)\n" : "RESULT: ok (0 differences)\n",
              (unsigned long long)g_failures);
  return g_failures ? 1 : 0;
}
