// sub_82E7F918's kernels (the movies' colour conversion, n_82E7F918_yuv.h): one row pair of groups (8 pixels of two
// rows) from host pointers, with the tables already host-endian. No guest memory here, so tools/test_yuv_kernels.cpp
// builds them on the PC and compares them byte for byte (sasrt-nx, 2026-11-09).
//
// 2026-11-09 (the user: "optimise the intro video so it stops dropping frames and it has stuttering audio"; the intro
// at stock clocks: 21 fps, the SlRenderer thread busy 30 ms a movie frame, 6.3 ms of it this conversion, profile
// intro_movie/rex_profile_090): PairLanes, the same arithmetic as PairNeon with the table words loaded straight into
// vector lanes (PairNeon stored them to small arrays and loaded those back as vectors: on the A57 a 16-byte load of
// bytes just stored by 4-byte stores waits for the stores to reach the cache) and the clamp range checked once per row
// pair (PairNeon reduced across lanes twice for every group): a row pair with any group outside it is done again
// through PairNeon, whose results are exact for every group, over the same outputs (the inputs never overlap them).
#pragma once

#include <simde/arm/neon.h>

#include <algorithm>
#include <cstdint>
#include <cstring>

namespace sasrt::hot::n_82E7F918 {

constexpr int32_t kMaxIndices = 8192;

struct Tables {
  int32_t t0[256], t1[256], t2[256], t3[256], t4[256];
  int32_t imin, imax;
  uint32_t clamp[kMaxIndices];
  // The clamp around its 0 -> 1 step at k: clamp[i] == clamp(i - k, 0, 255) for i - k in [vlo, vhi] (the indices the
  // tables can make reach past that: below it the original reads T4's words). The NEON path checks each group's
  // indices against [vlo, vhi]; a group outside goes through the table.
  bool fast;
  int32_t k, vlo, vhi;
  // sasrt-nx (2026-11-09, PairLanes): with fast, the chroma terms with k << 20 taken off (c1: t0 - off, c3: t1 - off)
  // or put on (c2: t2 + off, plus t4), as PairNeon forms them for every group.
  int32_t t0o[256], t1o[256], t2o[256];
  // sasrt-nx (2026-11-09, PairPacked): the two terms of each chroma byte side by side, one 8-byte load for both:
  // ta[2a] = t0o[a], ta[2a + 1] = t2o[a]; tb[2b] = t1o[b], tb[2b + 1] = t4[b].
  alignas(8) int32_t ta[512], tb[512];
};

// Fills t0o, t1o, t2o (after LoadTables has set fast and k).
inline void OffsetTables(Tables& t) {
  if (!t.fast) return;
  const uint32_t off = uint32_t(t.k) << 20;
  for (int i = 0; i < 256; ++i) {
    t.t0o[i] = int32_t(uint32_t(t.t0[i]) - off);
    t.t1o[i] = int32_t(uint32_t(t.t1[i]) - off);
    t.t2o[i] = int32_t(uint32_t(t.t2[i]) + off);
    t.ta[2 * i] = t.t0o[i];
    t.ta[2 * i + 1] = t.t2o[i];
    t.tb[2 * i] = t.t1o[i];
    t.tb[2 * i + 1] = t.t4[i];
  }
}

// One group (8 pixels of both rows) in scalar code with the clamp table (any table contents).
inline void GroupTable(const Tables& t, const uint8_t* py0, const uint8_t* py1, const uint8_t* pa, const uint8_t* pb,
                       uint8_t* pd0, uint8_t* pd1) {
  const uint32_t* cl = t.clamp - t.imin;
  for (int j = 0; j < 4; ++j) {
    const uint8_t av = pa[j], bv = pb[j];
    const uint32_t k1 = uint32_t(t.t0[av]), k2 = uint32_t(t.t2[av]) + uint32_t(t.t4[bv]), k3 = uint32_t(t.t1[bv]);
    for (int r = 0; r < 2; ++r) {
      for (int x = 2 * j; x < 2 * j + 2; ++x) {
        const uint32_t l = uint32_t(t.t3[(r ? py1 : py0)[x]]);
        const uint32_t v1 = cl[int32_t(l + k1) >> 20], v2 = cl[int32_t(l - k2) >> 20], v3 = cl[int32_t(l + k3) >> 20];
        const uint32_t word = ((0xFFFF0000u | ((v1 << 8) & 0xFF00u) | v2) << 8) | v3;
        const uint32_t be = __builtin_bswap32(word);
        std::memcpy((r ? pd1 : pd0) + 4 * x, &be, 4);
      }
    }
  }
}

// A row pair: NEON for each group whose indices all fall in the clamp's straight part, else the table (2026-10-21).
inline void PairNeon(const Tables& t, const uint8_t* py0, const uint8_t* py1, const uint8_t* pa, const uint8_t* pb,
                     uint8_t* pd0, uint8_t* pd1, uint32_t groups) {
  if (!t.fast) {
    for (uint32_t g = 0; g < groups; ++g, py0 += 8, py1 += 8, pa += 4, pb += 4, pd0 += 32, pd1 += 32)
      GroupTable(t, py0, py1, pa, pb, pd0, pd1);
    return;
  }
  const int32_t off = t.k * (1 << 20);  // |k| < 2048: the indices come from 32-bit sums >> 20
  const simde_int32x4_t vlo = simde_vdupq_n_s32(t.vlo), vhi = simde_vdupq_n_s32(t.vhi);
  const simde_uint8x8_t ff = simde_vdup_n_u8(0xFF);
  alignas(16) int32_t l[2][8], c1[8], c2[8], c3[8];
  for (uint32_t g = 0; g < groups; ++g, py0 += 8, py1 += 8, pa += 4, pb += 4, pd0 += 32, pd1 += 32) {
    for (int j = 0; j < 4; ++j) {
      const uint8_t av = pa[j], bv = pb[j];
      c1[2 * j] = c1[2 * j + 1] = t.t0[av] - off;
      c2[2 * j] = c2[2 * j + 1] = t.t2[av] + t.t4[bv] + off;
      c3[2 * j] = c3[2 * j + 1] = t.t1[bv] - off;
    }
    for (int x = 0; x < 8; ++x) {
      l[0][x] = t.t3[py0[x]];
      l[1][x] = t.t3[py1[x]];
    }
    const simde_int32x4_t c1v[2] = {simde_vld1q_s32(c1), simde_vld1q_s32(c1 + 4)};
    const simde_int32x4_t c2v[2] = {simde_vld1q_s32(c2), simde_vld1q_s32(c2 + 4)};
    const simde_int32x4_t c3v[2] = {simde_vld1q_s32(c3), simde_vld1q_s32(c3 + 4)};
    // v[row][channel][half]: (sum >> 20) - k for the 8 pixels of a row
    simde_int32x4_t v[2][3][2];
    simde_int32x4_t mn = vhi, mx = vlo;
    for (int r = 0; r < 2; ++r) {
      for (int h = 0; h < 2; ++h) {
        const simde_int32x4_t lv = simde_vld1q_s32(l[r] + 4 * h);
        v[r][0][h] = simde_vshrq_n_s32(simde_vaddq_s32(lv, c1v[h]), 20);
        v[r][1][h] = simde_vshrq_n_s32(simde_vsubq_s32(lv, c2v[h]), 20);
        v[r][2][h] = simde_vshrq_n_s32(simde_vaddq_s32(lv, c3v[h]), 20);
        for (int c = 0; c < 3; ++c) {
          mn = simde_vminq_s32(mn, v[r][c][h]);
          mx = simde_vmaxq_s32(mx, v[r][c][h]);
        }
      }
    }
    if (simde_vminvq_s32(mn) < t.vlo || simde_vmaxvq_s32(mx) > t.vhi) [[unlikely]] {
      GroupTable(t, py0, py1, pa, pb, pd0, pd1);
      continue;
    }
    // In range: clamp(i - k, 0, 255) is the saturating narrow; each pixel's word big-endian is 0xFF, c1, c2, c3.
    for (int r = 0; r < 2; ++r) {
      simde_uint8x8x4_t px;
      px.val[0] = ff;
      for (int c = 0; c < 3; ++c)
        px.val[c + 1] = simde_vqmovn_u16(simde_vcombine_u16(simde_vqmovun_s32(v[r][c][0]),
                                                           simde_vqmovun_s32(v[r][c][1])));
      simde_vst4_u8(r ? pd1 : pd0, px);  // 0xFF, c1, c2, c3 per pixel: the big-endian word
    }
  }
}

// Four table words straight into the lanes of a vector.
inline simde_int32x4_t Gather4(const int32_t* tab, const uint8_t* idx) {
  simde_int32x4_t v = simde_vdupq_n_s32(tab[idx[0]]);
  v = simde_vsetq_lane_s32(tab[idx[1]], v, 1);
  v = simde_vsetq_lane_s32(tab[idx[2]], v, 2);
  v = simde_vsetq_lane_s32(tab[idx[3]], v, 3);
  return v;
}

// A row pair as PairNeon's NEON path (t.fast only): false when any group's indices left [vlo, vhi], the outputs then
// partly written and to be done again by PairNeon.
inline bool PairLanes(const Tables& t, const uint8_t* py0, const uint8_t* py1, const uint8_t* pa, const uint8_t* pb,
                      uint8_t* pd0, uint8_t* pd1, uint32_t groups) {
  simde_int32x4_t mn = simde_vdupq_n_s32(t.vhi), mx = simde_vdupq_n_s32(t.vlo);
  const simde_uint8x8_t ff = simde_vdup_n_u8(0xFF);
  for (uint32_t g = 0; g < groups; ++g, py0 += 8, py1 += 8, pa += 4, pb += 4, pd0 += 32, pd1 += 32) {
    // The chroma terms of the 4 columns pairs, each for its 2 pixels: [j0 j0 j1 j1] and [j2 j2 j3 j3].
    const simde_int32x4_t c1 = Gather4(t.t0o, pa);
    const simde_int32x4_t c3 = Gather4(t.t1o, pb);
    const simde_int32x4_t c2 = simde_vaddq_s32(Gather4(t.t2o, pa), Gather4(t.t4, pb));
    const simde_int32x4_t c1v[2] = {simde_vzip1q_s32(c1, c1), simde_vzip2q_s32(c1, c1)};
    const simde_int32x4_t c2v[2] = {simde_vzip1q_s32(c2, c2), simde_vzip2q_s32(c2, c2)};
    const simde_int32x4_t c3v[2] = {simde_vzip1q_s32(c3, c3), simde_vzip2q_s32(c3, c3)};
    for (int r = 0; r < 2; ++r) {
      const uint8_t* py = r ? py1 : py0;
      simde_int32x4_t v[3][2];
      for (int h = 0; h < 2; ++h) {
        const simde_int32x4_t lv = Gather4(t.t3, py + 4 * h);
        v[0][h] = simde_vshrq_n_s32(simde_vaddq_s32(lv, c1v[h]), 20);
        v[1][h] = simde_vshrq_n_s32(simde_vsubq_s32(lv, c2v[h]), 20);
        v[2][h] = simde_vshrq_n_s32(simde_vaddq_s32(lv, c3v[h]), 20);
      }
      mn = simde_vminq_s32(mn, simde_vminq_s32(simde_vminq_s32(simde_vminq_s32(v[0][0], v[0][1]),
                                                               simde_vminq_s32(v[1][0], v[1][1])),
                                               simde_vminq_s32(v[2][0], v[2][1])));
      mx = simde_vmaxq_s32(mx, simde_vmaxq_s32(simde_vmaxq_s32(simde_vmaxq_s32(v[0][0], v[0][1]),
                                                               simde_vmaxq_s32(v[1][0], v[1][1])),
                                               simde_vmaxq_s32(v[2][0], v[2][1])));
      simde_uint8x8x4_t px;
      px.val[0] = ff;
      for (int c = 0; c < 3; ++c)
        px.val[c + 1] = simde_vqmovn_u16(simde_vcombine_u16(simde_vqmovun_s32(v[c][0]), simde_vqmovun_s32(v[c][1])));
      simde_vst4_u8(r ? pd1 : pd0, px);
    }
  }
  return simde_vminvq_s32(mn) >= t.vlo && simde_vmaxvq_s32(mx) <= t.vhi;
}

// sasrt-nx (2026-11-09, the console's intro profile after PairLanes: no faster, the A57's one load pipe the limit:
// PairNeon and PairLanes both make 56 loads a group). PairPacked: the same arithmetic in 28 loads a group: each row's
// 8 luma bytes and each chroma plane's 4 bytes as one word (the indices taken out by shifts), and each chroma byte's
// two terms by one 8-byte load from ta / tb, sorted into lanes by unzips; the 16 luma words into lanes as before.
// Little-endian hosts only (byte j of a word is bits 8j..8j+7): the Switch and the PC.
template <int Lane>
inline simde_int32x4_t LaneLoad(const int32_t* tab, uint64_t word, int shift, simde_int32x4_t v) {
  return simde_vld1q_lane_s32(tab + ((word >> shift) & 0xFF), v, Lane);
}
inline simde_int32x4_t Gather4At(const int32_t* tab, uint64_t word, int base) {
  simde_int32x4_t v = simde_vld1q_dup_s32(tab + ((word >> base) & 0xFF));
  v = LaneLoad<1>(tab, word, base + 8, v);
  v = LaneLoad<2>(tab, word, base + 16, v);
  v = LaneLoad<3>(tab, word, base + 24, v);
  return v;
}
// sasrt-nx (2026-11-09, PairPacked<true>, kernel 4): each 64-byte line of the picture that this row pair's next two
// groups write whole is zeroed in the cache first (DC ZVA), so the stores that fill it do not read it from memory
// first (3.7 MB a picture read for nothing). The line's every byte is then stored by those groups (or, when the row
// pair leaves the clamp's straight part, by PairNeon after): the same bytes. aarch64 only, and only when DCZID_EL0
// allows it with 64-byte blocks; elsewhere the plain kernel.
inline bool ZvaUsable() {
#if defined(__aarch64__)
  static const bool ok = [] {
    uint64_t dczid;
    __asm__ volatile("mrs %0, dczid_el0" : "=r"(dczid));
    return (dczid & 16u) == 0 && (dczid & 15u) == 4;  // allowed; 4 words << 4 = 64 bytes
  }();
  return ok;
#else
  return false;
#endif
}
inline void ZeroLine(uint8_t* p) {
#if defined(__aarch64__)
  __asm__ volatile("dc zva, %0" : : "r"(p) : "memory");
#else
  (void)p;
#endif
}
template <bool Zva = false>
inline bool PairPacked(const Tables& t, const uint8_t* py0, const uint8_t* py1, const uint8_t* pa, const uint8_t* pb,
                       uint8_t* pd0, uint8_t* pd1, uint32_t groups) {
  simde_int32x4_t mn = simde_vdupq_n_s32(t.vhi), mx = simde_vdupq_n_s32(t.vlo);
  const simde_uint8x8_t ff = simde_vdup_n_u8(0xFF);
  for (uint32_t g = 0; g < groups; ++g, py0 += 8, py1 += 8, pa += 4, pb += 4, pd0 += 32, pd1 += 32) {
    uint32_t aw, bw;
    std::memcpy(&aw, pa, 4);
    std::memcpy(&bw, pb, 4);
    // [t0o, t2o] of a0..a3 and [t1o, t4] of b0..b3: unzipped into c1, c2's a part, c3, c2's b part
    const simde_int32x4_t a01 = simde_vcombine_s32(simde_vld1_s32(t.ta + 2 * (aw & 0xFF)),
                                                   simde_vld1_s32(t.ta + 2 * ((aw >> 8) & 0xFF)));
    const simde_int32x4_t a23 = simde_vcombine_s32(simde_vld1_s32(t.ta + 2 * ((aw >> 16) & 0xFF)),
                                                   simde_vld1_s32(t.ta + 2 * (aw >> 24)));
    const simde_int32x4_t b01 = simde_vcombine_s32(simde_vld1_s32(t.tb + 2 * (bw & 0xFF)),
                                                   simde_vld1_s32(t.tb + 2 * ((bw >> 8) & 0xFF)));
    const simde_int32x4_t b23 = simde_vcombine_s32(simde_vld1_s32(t.tb + 2 * ((bw >> 16) & 0xFF)),
                                                   simde_vld1_s32(t.tb + 2 * (bw >> 24)));
    const simde_int32x4_t c1 = simde_vuzp1q_s32(a01, a23);
    const simde_int32x4_t c3 = simde_vuzp1q_s32(b01, b23);
    const simde_int32x4_t c2 = simde_vaddq_s32(simde_vuzp2q_s32(a01, a23), simde_vuzp2q_s32(b01, b23));
    const simde_int32x4_t c1v[2] = {simde_vzip1q_s32(c1, c1), simde_vzip2q_s32(c1, c1)};
    const simde_int32x4_t c2v[2] = {simde_vzip1q_s32(c2, c2), simde_vzip2q_s32(c2, c2)};
    const simde_int32x4_t c3v[2] = {simde_vzip1q_s32(c3, c3), simde_vzip2q_s32(c3, c3)};
    if constexpr (Zva) {
      if (g + 1 < groups) {  // this group and the next write [pd, pd + 64) of each row
        if ((reinterpret_cast<uintptr_t>(pd0) & 63u) == 0) ZeroLine(pd0);
        if ((reinterpret_cast<uintptr_t>(pd1) & 63u) == 0) ZeroLine(pd1);
      }
    }
    for (int r = 0; r < 2; ++r) {
      uint64_t yw;
      std::memcpy(&yw, r ? py1 : py0, 8);
      simde_int32x4_t v[3][2];
      for (int h = 0; h < 2; ++h) {
        const simde_int32x4_t lv = Gather4At(t.t3, yw, 32 * h);
        v[0][h] = simde_vshrq_n_s32(simde_vaddq_s32(lv, c1v[h]), 20);
        v[1][h] = simde_vshrq_n_s32(simde_vsubq_s32(lv, c2v[h]), 20);
        v[2][h] = simde_vshrq_n_s32(simde_vaddq_s32(lv, c3v[h]), 20);
      }
      mn = simde_vminq_s32(mn, simde_vminq_s32(simde_vminq_s32(simde_vminq_s32(v[0][0], v[0][1]),
                                                               simde_vminq_s32(v[1][0], v[1][1])),
                                               simde_vminq_s32(v[2][0], v[2][1])));
      mx = simde_vmaxq_s32(mx, simde_vmaxq_s32(simde_vmaxq_s32(simde_vmaxq_s32(v[0][0], v[0][1]),
                                                               simde_vmaxq_s32(v[1][0], v[1][1])),
                                               simde_vmaxq_s32(v[2][0], v[2][1])));
      simde_uint8x8x4_t px;
      px.val[0] = ff;
      for (int c = 0; c < 3; ++c)
        px.val[c + 1] = simde_vqmovn_u16(simde_vcombine_u16(simde_vqmovun_s32(v[c][0]), simde_vqmovun_s32(v[c][1])));
      simde_vst4_u8(r ? pd1 : pd0, px);
    }
  }
  return simde_vminvq_s32(mn) >= t.vlo && simde_vmaxvq_s32(mx) <= t.vhi;
}

// The kernels a row pair can take (sasrt_movie_colour_kernel; 0 lets the first picture's timing choose).
enum class Kernel : int { kNeon = 1, kLanes = 2, kPacked = 3, kPackedZva = 4 };

// A row pair by the chosen kernel: PairLanes or PairPacked with PairNeon after them for a row pair that left the
// range, or PairNeon (also whenever the tables have no straight clamp part).
inline void PairHost(const Tables& t, const uint8_t* py0, const uint8_t* py1, const uint8_t* pa, const uint8_t* pb,
                     uint8_t* pd0, uint8_t* pd1, uint32_t groups, Kernel k) {
  if (t.fast) {
    if (k == Kernel::kPacked && PairPacked(t, py0, py1, pa, pb, pd0, pd1, groups)) return;
    if (k == Kernel::kPackedZva &&
        (ZvaUsable() ? PairPacked<true>(t, py0, py1, pa, pb, pd0, pd1, groups)
                     : PairPacked(t, py0, py1, pa, pb, pd0, pd1, groups)))
      return;
    if (k == Kernel::kLanes && PairLanes(t, py0, py1, pa, pb, pd0, pd1, groups)) return;
  }
  PairNeon(t, py0, py1, pa, pb, pd0, pd1, groups);
}

}  // namespace sasrt::hot::n_82E7F918
