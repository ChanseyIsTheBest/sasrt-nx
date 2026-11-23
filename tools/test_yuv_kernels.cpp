// sasrt-nx (2026-11-09): sub_82E7F918's row-pair kernels (app/src/hot/n_82E7F918_kernels.h) compared byte for byte:
// PairLanes (with PairNeon after a row pair that left the clamp's straight part) against PairNeon, the 2026-10-21 path
// verified against the original on the PC and Ryujinx. The tables as the game builds them (sub_82E7F7A0: doubles from
// the image's .rdata, a fused multiply-add for the luma, truncation), the clamp table as it fills it, and the words
// after it (indices 768 to 790, other data in the game) random. Pictures: random bytes (they reach indices -21..790)
// and smooth gradients (a real picture's range).
//
//   "D:/sonic transformed/_tools/llvm/bin/clang++.exe" -O2 -std=c++20 -I sdk/thirdparty/simde -I app/src
//       tools/test_yuv_kernels.cpp -o out/test_yuv_kernels.exe && out/test_yuv_kernels.exe
#include <cmath>
#include <cstdio>
#include <random>
#include <vector>

#include "hot/n_82E7F918_kernels.h"

using namespace sasrt::hot::n_82E7F918;

static int32_t Fctiwz(double v) {  // the PowerPC's truncation to a 32-bit integer, saturating
  if (std::isnan(v)) return INT32_MIN;
  if (v >= 2147483647.0) return INT32_MAX;
  if (v <= -2147483648.0) return INT32_MIN;
  return int32_t(std::trunc(v));
}

int main() {
  // sub_82E7F7A0's constants (out/default_image.bin): f0 2^20, luma 1.164 and 256.5, chroma 1.596 0.392 0.813 2.017.
  const double f0 = 1048576.0, la = 1.164, lb = 256.5;
  const double kt0 = 1.596, kt4 = 0.392, kt2 = 0.813, kt1 = 2.017;
  static Tables t;
  std::vector<uint32_t> words(8192 / 4 + 64);  // T0..T4 and the clamp, as guest words, then what follows them
  for (int i = 0; i < 256; ++i) {
    t.t3[i] = Fctiwz(std::fma(double(i - 16), la, lb) * f0);
    const double j = double(i - 128);
    t.t0[i] = Fctiwz(j * kt0 * f0);
    t.t4[i] = Fctiwz(j * kt4 * f0);
    t.t2[i] = Fctiwz(j * kt2 * f0);
    t.t1[i] = Fctiwz(j * kt1 * f0);
  }
  for (int i = 0; i < 256; ++i) {
    words[i] = uint32_t(t.t0[i]);
    words[256 + i] = uint32_t(t.t1[i]);
    words[512 + i] = uint32_t(t.t2[i]);
    words[768 + i] = uint32_t(t.t3[i]);
    words[1024 + i] = uint32_t(t.t4[i]);
    words[1280 + i] = 0;
    words[1280 + 256 + i] = uint32_t(i);
    words[1280 + 512 + i] = 255;
  }
  std::mt19937 rng(20261109);
  for (size_t i = 1280 + 768; i < words.size(); ++i) words[i] = rng();
  // LoadTables' range, clamp and step (n_82E7F918_yuv.h)
  int64_t mn[5], mx[5];
  const int32_t* tabs[5] = {t.t0, t.t1, t.t2, t.t3, t.t4};
  for (int k = 0; k < 5; ++k) {
    mn[k] = INT64_MAX;
    mx[k] = INT64_MIN;
    for (int i = 0; i < 256; ++i) {
      mn[k] = std::min<int64_t>(mn[k], tabs[k][i]);
      mx[k] = std::max<int64_t>(mx[k], tabs[k][i]);
    }
  }
  const int64_t lo[3] = {mn[3] + mn[0], mn[3] - (mx[2] + mx[4]), mn[3] + mn[1]};
  const int64_t hi[3] = {mx[3] + mx[0], mx[3] - (mn[2] + mn[4]), mx[3] + mx[1]};
  int64_t smin = INT64_MAX, smax = INT64_MIN;
  for (int c = 0; c < 3; ++c) {
    smin = std::min(smin, lo[c]);
    smax = std::max(smax, hi[c]);
  }
  t.imin = int32_t(smin) >> 20;
  t.imax = int32_t(smax) >> 20;
  for (int32_t i = t.imin; i <= t.imax; ++i) t.clamp[i - t.imin] = words[1280 + i];
  t.fast = false;
  for (int32_t i = t.imin; i < t.imax; ++i)
    if (t.clamp[i - t.imin] == 0 && t.clamp[i + 1 - t.imin] == 1) {
      t.k = i;
      t.fast = true;
      break;
    }
  auto is_clamp = [&](int32_t i) { return t.clamp[i - t.imin] == uint32_t(std::min(std::max(i - t.k, 0), 255)); };
  int32_t plo = t.k, phi = t.k + 1;
  while (plo > t.imin && is_clamp(plo - 1)) --plo;
  while (phi < t.imax && is_clamp(phi + 1)) ++phi;
  t.vlo = plo - t.k;
  t.vhi = phi - t.k;
  OffsetTables(t);
  std::printf("indices %d..%d, step at %d, straight part %d..%d, fast %d\n", t.imin, t.imax, t.k, t.k + t.vlo,
              t.k + t.vhi, int(t.fast));

  const uint32_t w = 1280, groups = w / 8;
  uint64_t pairs = 0, differ = 0, lanes_ok = 0, packed_ok = 0;
  std::vector<uint8_t> y0(w), y1(w), a(w / 2), b(w / 2), o0(w * 4), o1(w * 4), n0(w * 4), n1(w * 4);
  for (int round = 0; round < 4000; ++round) {
    const int kind = round % 4;
    for (uint32_t x = 0; x < w; ++x) {
      if (kind == 0) {  // random bytes: every index the tables can make
        y0[x] = uint8_t(rng());
        y1[x] = uint8_t(rng());
      } else {  // a gradient with a little noise, as a picture
        y0[x] = uint8_t(std::clamp<int>(16 + int((x * 219) / w) + int(rng() % 7) - 3 + round % 50, 0, 255));
        y1[x] = uint8_t(std::clamp<int>(int(y0[x]) + int(rng() % 5) - 2, 0, 255));
      }
    }
    for (uint32_t x = 0; x < w / 2; ++x) {
      a[x] = kind == 0 ? uint8_t(rng()) : uint8_t(128 + int(rng() % (kind * 40 + 1)) - kind * 20);
      b[x] = kind == 0 ? uint8_t(rng()) : uint8_t(128 + int(rng() % (kind * 40 + 1)) - kind * 20);
    }
    std::fill(o0.begin(), o0.end(), 0xAB);
    std::fill(o1.begin(), o1.end(), 0xAB);
    std::fill(n0.begin(), n0.end(), 0xCD);
    std::fill(n1.begin(), n1.end(), 0xCD);
    PairNeon(t, y0.data(), y1.data(), a.data(), b.data(), o0.data(), o1.data(), groups);
    lanes_ok += PairLanes(t, y0.data(), y1.data(), a.data(), b.data(), n0.data(), n1.data(), groups);
    for (Kernel k : {Kernel::kLanes, Kernel::kPacked, Kernel::kPackedZva, Kernel::kNeon}) {
      std::fill(n0.begin(), n0.end(), 0xCD);
      std::fill(n1.begin(), n1.end(), 0xCD);
      PairHost(t, y0.data(), y1.data(), a.data(), b.data(), n0.data(), n1.data(), groups, k);
      ++pairs;
      if (o0 != n0 || o1 != n1) {
        if (differ++ < 5) std::printf("row pair %d (kind %d) kernel %d differs\n", round, kind, int(k));
      }
    }
    std::fill(n0.begin(), n0.end(), 0xCD);
    std::fill(n1.begin(), n1.end(), 0xCD);
    packed_ok += PairPacked(t, y0.data(), y1.data(), a.data(), b.data(), n0.data(), n1.data(), groups);
  }
  // Every group also through GroupTable (the scalar table path PairNeon falls back to) against PairNeon's NEON path.
  uint64_t group_differ = 0;
  for (int round = 0; round < 2000; ++round) {
    uint8_t gy0[8], gy1[8], ga[4], gb[4], g0[32], g1[32], h0[32], h1[32];
    for (int i = 0; i < 8; ++i) gy0[i] = uint8_t(rng()), gy1[i] = uint8_t(rng());
    for (int i = 0; i < 4; ++i) ga[i] = uint8_t(rng()), gb[i] = uint8_t(rng());
    GroupTable(t, gy0, gy1, ga, gb, g0, g1);
    PairLanes(t, gy0, gy1, ga, gb, h0, h1, 1) ? void() : PairNeon(t, gy0, gy1, ga, gb, h0, h1, 1);
    group_differ += std::memcmp(g0, h0, 32) != 0 || std::memcmp(g1, h1, 32) != 0;
    PairPacked(t, gy0, gy1, ga, gb, h0, h1, 1) ? void() : PairNeon(t, gy0, gy1, ga, gb, h0, h1, 1);
    group_differ += std::memcmp(g0, h0, 32) != 0 || std::memcmp(g1, h1, 32) != 0;
  }
  std::printf("%llu row pairs (four kernel choices): %llu differ (in range alone: PairLanes %llu, PairPacked %llu); 2000 "
              "groups against the table path (two kernels): %llu differ\n", (unsigned long long)pairs,
              (unsigned long long)differ, (unsigned long long)lanes_ok, (unsigned long long)packed_ok,
              (unsigned long long)group_differ);
  return differ || group_differ ? 1 : 0;
}
