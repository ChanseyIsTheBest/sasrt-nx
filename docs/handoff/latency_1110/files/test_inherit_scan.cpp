// sasrt-nx (2026-11-10, sasrt_record_inherit_scan_wide): the 16-byte NoteSetWords scan against the word scan on random
// devices. Build: C:\devkitPro\msys2\clang64\bin\clang++.exe -O2 -std=c++20 tools/test_inherit_scan.cpp -o test_inherit_scan.exe
#include <cstdint>
#include <cstring>
#include <cstdio>
#include <random>
using u8 = uint8_t; using u32 = uint32_t;
constexpr u32 kFetchBegin = 0x480, kVertexShaderF = 0x780, kTail = 0x2780, kSize = 13088;
void ref(u32 *w, const u8 *d, const u8 *b, u32 from, u32 to) {
  for (u32 at = from; at < to; at += 4) if (std::memcmp(d + at, b + at, 4) != 0) w[at / 128] |= 1u << ((at / 4) & 31);
}
void wide(u32 *w, const u8 *d, const u8 *bb, u32 from, u32 to) {
  for (u32 at = from; at < to; at += 16) {
    uint64_t a[2], b[2]; std::memcpy(a, d + at, 16); std::memcpy(b, bb + at, 16);
    const uint64_t x0 = a[0] ^ b[0], x1 = a[1] ^ b[1];
    if (!(x0 | x1)) continue;
    const u32 bits = u32(u32(x0) != 0) | u32((x0 >> 32) != 0) << 1 | u32(u32(x1) != 0) << 2 | u32((x1 >> 32) != 0) << 3;
    w[at / 128] |= bits << ((at / 4) & 31);
  }
}
int main() {
  static_assert(kSize % 16 == 0);
  std::mt19937 rng(1);
  static u8 d[kSize], b[kSize];
  long bad = 0, words = 0;
  for (int it = 0; it < 200000; ++it) {
    for (u32 i = 0; i < kSize; ++i) b[i] = d[i] = u8(rng());
    int n = rng() % 40;
    for (int k = 0; k < n; ++k) { u32 at = rng() % kSize; d[at] ^= u8(1 + rng() % 255); }
    u32 w1[kSize / 128 + 1] = {}, w2[kSize / 128 + 1] = {};
    // pre-set bits too (the OR keeps them)
    for (int k = 0; k < 3; ++k) { u32 v = rng(); w1[k * 7] = w2[k * 7] = v; }
    ref(w1, d, b, kFetchBegin, kVertexShaderF); ref(w1, d, b, kTail, kSize);
    wide(w2, d, b, kFetchBegin, kVertexShaderF); wide(w2, d, b, kTail, kSize);
    if (std::memcmp(w1, w2, sizeof(w1))) ++bad;
    for (u32 x : w1) words += __builtin_popcount(x);
  }
  std::printf("%s: %ld mismatches, %ld bits compared\n", bad ? "FAIL" : "OK", bad, words);
  return bad != 0;
}
