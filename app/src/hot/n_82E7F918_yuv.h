// sub_82E7F918 - the movie player's colour conversion (sasrt-nx, 2026-10-21; a localized copy since batch 2 of
// 2026-10-07, which took it for a tiling loop): one decoded 4:2:0 picture (a luma plane and two chroma planes of half
// width and height) into 32-bit pixels, once per frame of every movie (all four are 1280x720 at 30 fps: 3.7 MB of
// pixels a call). The console's profile of the intro movie: 62 % of the SlRenderer thread in the copy.
//
// r3 = source: +0 luma, +4 chroma "b", +8 chroma "a" (pointers), +12 luma pitch, +16 "b" pitch, +20 "a" pitch;
// r4 = target: +0 pixels, +4 width, +8 height, +12 pitch (bytes). Six 256-entry tables of 32-bit words at
// 0x832ECF50 (lis/addi in the original): T0 (+0) and T2 (+2048) by "a", T1 (+1024) and T4 (+4096) by "b", T3 (+3072)
// by luma, and the clamp T5 (+5120) indexed by (sum >> 20), an arithmetic shift, negative indices included. For a
// pixel of row r of a pair and column x (a, b the chroma bytes of column x / 2):
//   L = T3[y]; c1 = T5[(L + T0[a]) >> 20]; c2 = T5[(L - (T2[a] + T4[b])) >> 20]; c3 = T5[(L + T1[b]) >> 20];
//   word = ((0xFFFF0000 | (c1 & 0xFF) << 8 | c2) << 8) | c3, stored big-endian (sums in 32 bits).
// The loops: width / 8 groups of 8 pixels in two rows (no tail: the original drops width % 8), height / 2 row pairs;
// after each pair every pointer moves by the original's own arithmetic (its skips are computed from the width, so a
// width that is not a multiple of 8 moves the rows back: kept). r3 at the return: the last row pair's second-row
// pointer as the original leaves it (CompareRegs checks r3); no other register the guard compares is written. The
// original also writes scratch below r1 (dead after the return; not compared, not written here).
//
// Here: the tables copied host-endian once per call (with the clamp over exactly the indices the tables can make, which
// is checked to be free of 32-bit overflow), then every pixel from host memory: with simde's NEON (native on the
// Switch) for each group of 16 pixels whose indices all fall where the clamp table is clamp(i - k, 0, 255) (the
// saturating narrows do that), else in scalar code with the clamp table (the game's tables reach indices -21..790 and
// below 0 the original reads the next table's words: kept for groups that get there). Declined (the original runs): negative sizes, a range that leaves its guest view or wraps, the target
// overlapping the sources or the tables, sums that could overflow 32 bits, an index range over 8,192.
#pragma once

#include <simde/arm/neon.h>

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <memory>
#include <mutex>
#include <thread>
#include <vector>

#include "hot/n_82E7F918_kernels.h"  // sasrt-nx (2026-11-09): Tables and the row-pair kernels
#include "hot/sasrt_hot_common.h"
#include "me/me_platform_compat.h"  // the system core (no-ops off the Switch)

namespace sasrt::hot::n_82E7F918 {

constexpr uint32_t kTables = 0x832ECF50u;

inline uint32_t Be32(const uint8_t* base, uint32_t a) {
  uint32_t v;
  std::memcpy(&v, Raw(base, a), 4);
  return __builtin_bswap32(v);
}

struct Plan {
  uint32_t y0, y1, a, b, d0, d1;   // the first row pair's pointers
  uint32_t yskip, askip, bskip, dskip;
  uint32_t w8, pairs;
  uint32_t lo = 0, hi = 0;         // the rows written: [lo, hi) (empty when w8 or pairs is 0)
  uint64_t r3 = 0;                 // r3 at the return
};

// [lo, hi) of every row of a plane the loops touch (rows of `bytes` bytes, two rows a pair `step` apart when two), or
// false when one wraps around 4 GB.
inline bool Extent(uint32_t first, uint32_t second, bool two, uint32_t bytes, uint32_t advance, uint32_t pairs,
                   uint32_t& lo, uint32_t& hi) {
  uint64_t mn = UINT64_MAX, mx = 0;
  uint32_t p0 = first, p1 = second;
  for (uint32_t i = 0; i < pairs; ++i) {
    for (int r = 0; r < (two ? 2 : 1); ++r) {
      const uint32_t p = r ? p1 : p0;
      if (uint64_t(p) + bytes > 0x100000000ull) return false;
      mn = std::min<uint64_t>(mn, p);
      mx = std::max<uint64_t>(mx, uint64_t(p) + bytes);
    }
    p0 += advance;
    p1 += advance;
  }
  lo = uint32_t(mn);
  hi = uint32_t(mx);
  return mx > mn ? !CrossesView(lo, hi - lo) : true;
}

inline bool MakePlan(const PPCContext& ctx, const uint8_t* base, Plan& p, uint32_t (&src)[3][2]) {
  const uint32_t s = ctx.r3.u32, t = ctx.r4.u32;
  if (CrossesView(s, 24) || CrossesView(t, 16)) return false;
  const uint32_t y = Be32(base, s), b = Be32(base, s + 4), a = Be32(base, s + 8);
  const uint32_t ypitch = Be32(base, s + 12), bpitch = Be32(base, s + 16), apitch = Be32(base, s + 20);
  const uint32_t dst = Be32(base, t), dpitch = Be32(base, t + 12);
  const int32_t w = int32_t(Be32(base, t + 4)), h = int32_t(Be32(base, t + 8));
  if (w < 0 || h < 0) return false;
  p.w8 = uint32_t(w / 8);
  p.pairs = uint32_t(h / 2);
  const uint32_t wh = uint32_t(w / 2);
  p.yskip = (uint32_t(ypitch << 1) - uint32_t(w)) & ~3u;
  p.bskip = (bpitch - wh) & ~3u;
  p.askip = (apitch - wh) & ~3u;
  p.dskip = (uint32_t((dpitch >> 2) << 1) - uint32_t(w)) << 2;
  p.y0 = y;
  p.y1 = y + (ypitch & ~3u);
  p.a = a;
  p.b = b;
  p.d0 = dst;
  p.d1 = dst + (dpitch & ~3u);
  // r3 as the original leaves it: its second-row pointer, a 64-bit register that only the inner loop's stores and
  // reloads cut back to 32 bits.
  if (p.pairs == 0) {
    p.r3 = uint64_t(dpitch & ~3u) + dst;
  } else if (p.w8 == 0) {
    p.r3 = uint64_t(dpitch & ~3u) + dst + uint64_t(p.pairs) * p.dskip;
  } else {
    const uint32_t last = p.d1 + (p.pairs - 1) * (32u * p.w8 + p.dskip);
    p.r3 = uint64_t(uint32_t(last + 32u * p.w8 - 4u)) + 4u + p.dskip;
  }
  if (p.w8 == 0 || p.pairs == 0) return true;
  if (!Extent(p.d0, p.d1, true, 32u * p.w8, 32u * p.w8 + p.dskip, p.pairs, p.lo, p.hi)) return false;
  if (!Extent(p.y0, p.y1, true, 8u * p.w8, 8u * p.w8 + p.yskip, p.pairs, src[0][0], src[0][1])) return false;
  if (!Extent(p.a, p.a, false, 4u * p.w8, 4u * p.w8 + p.askip, p.pairs, src[1][0], src[1][1])) return false;
  if (!Extent(p.b, p.b, false, 4u * p.w8, 4u * p.w8 + p.bskip, p.pairs, src[2][0], src[2][1])) return false;
  return true;
}

inline bool Overlaps(uint32_t lo0, uint32_t hi0, uint32_t lo1, uint32_t hi1) { return lo0 < hi1 && lo1 < hi0; }

// Tables: n_82E7F918_kernels.h.

// The tables host-endian, the indices they can make, and the clamp over those: false when a sum could overflow.
inline bool LoadTables(const uint8_t* base, Tables& t) {
  int64_t mn[5], mx[5];
  int32_t* dst[5] = {t.t0, t.t1, t.t2, t.t3, t.t4};
  for (int k = 0; k < 5; ++k) {
    mn[k] = INT64_MAX;
    mx[k] = INT64_MIN;
    for (int i = 0; i < 256; ++i) {
      const int32_t v = int32_t(Be32(base, kTables + uint32_t(k) * 1024u + uint32_t(i) * 4u));
      dst[k][i] = v;
      mn[k] = std::min<int64_t>(mn[k], v);
      mx[k] = std::max<int64_t>(mx[k], v);
    }
  }
  // c1 = L + T0, c2 = L - (T2 + T4), c3 = L + T1, with L = T3: every sum within 32 bits for any bytes.
  const int64_t lo[3] = {mn[3] + mn[0], mn[3] - (mx[2] + mx[4]), mn[3] + mn[1]};
  const int64_t hi[3] = {mx[3] + mx[0], mx[3] - (mn[2] + mn[4]), mx[3] + mx[1]};
  if (mn[2] + mn[4] < INT32_MIN || mx[2] + mx[4] > INT32_MAX) return false;
  int64_t smin = INT64_MAX, smax = INT64_MIN;
  for (int c = 0; c < 3; ++c) {
    if (lo[c] < INT32_MIN || hi[c] > INT32_MAX) return false;
    smin = std::min(smin, lo[c]);
    smax = std::max(smax, hi[c]);
  }
  t.imin = int32_t(smin) >> 20;
  t.imax = int32_t(smax) >> 20;
  if (t.imax - t.imin + 1 > kMaxIndices) return false;
  for (int32_t i = t.imin; i <= t.imax; ++i)
    t.clamp[i - t.imin] = Be32(base, kTables + 5120u + uint32_t(i) * 4u);
  // The step: an entry 0 followed by an entry 1 gives k; the range around it where the entries are the clamp.
  t.fast = false;
  for (int32_t i = t.imin; i < t.imax; ++i) {
    if (t.clamp[i - t.imin] == 0 && t.clamp[i + 1 - t.imin] == 1) {
      t.k = i;
      t.fast = true;
      break;
    }
  }
  if (!t.fast) return true;
  auto is_clamp = [&](int32_t i) { return t.clamp[i - t.imin] == uint32_t(std::min(std::max(i - t.k, 0), 255)); };
  int32_t plo = t.k, phi = t.k + 1;
  while (plo > t.imin && is_clamp(plo - 1)) --plo;
  while (phi < t.imax && is_clamp(phi + 1)) ++phi;
  t.vlo = plo - t.k;
  t.vhi = phi - t.k;
  // With k taken off the chroma terms (c1, c3 minus k << 20, c2 plus it) the shifts give i - k directly: those sums
  // must stay within 32 bits too.
  const int64_t off = int64_t(t.k) * (1 << 20);
  for (int c = 0; c < 3; ++c)
    if (lo[c] - off < INT32_MIN || hi[c] - off > INT32_MAX) t.fast = false;
  OffsetTables(t);  // sasrt-nx (2026-11-09): PairLanes' chroma terms
  return true;
}

// GroupTable, PairNeon, PairLanes: n_82E7F918_kernels.h.

// sasrt-nx (2026-11-09): sasrt_movie_colour_kernel (0: timed at the first picture; 1 PairNeon, 2 PairLanes, 3
// PairPacked) and sasrt_movie_colour_helpers (threads besides the caller: 0-2), keys in sasrt_hot_guest.cpp.
int KernelKey();
int HelpersKey();

// Row pair i of the plan: its pointers as the original's loop leaves them after i pairs (the same 32-bit sums).
struct PairPtrs {
  const uint8_t *y0, *y1, *a, *b;
  uint8_t *d0, *d1;
};
inline PairPtrs PairPointers(uint8_t* base, const Plan& p, uint32_t i) {
  const uint32_t y0 = p.y0 + i * (8u * p.w8 + p.yskip), y1 = p.y1 + i * (8u * p.w8 + p.yskip);
  const uint32_t a = p.a + i * (4u * p.w8 + p.askip), b = p.b + i * (4u * p.w8 + p.bskip);
  const uint32_t d0 = p.d0 + i * (32u * p.w8 + p.dskip), d1 = p.d1 + i * (32u * p.w8 + p.dskip);
  return {Raw(base, y0), Raw(base, y1), Raw(base, a), Raw(base, b), Raw(base, d0), Raw(base, d1)};
}
inline void PairAt(uint8_t* base, const Tables& t, const Plan& p, uint32_t i, Kernel k) {
  const PairPtrs q = PairPointers(base, p, i);
  PairHost(t, q.y0, q.y1, q.a, q.b, q.d0, q.d1, p.w8, k);
}

// sasrt-nx (2026-11-09, sasrt_movie_colour_kernel 0): the kernel the console runs fastest, timed once on the first
// picture with the straight clamp part (each kernel twice over every row pair into a scratch picture of the same size,
// the best of the two), logged. Every kernel gives the same bytes (tools/test_yuv_kernels.cpp), so the choice changes
// no pixel. Before the timing (and with the key set) the key's kernel.
inline std::atomic<int> g_kernel{0};
inline Kernel ChooseKernel(uint8_t* base, const Tables& t, const Plan& p) {
  const int key = KernelKey();
  if (key >= 1 && key <= 4) return Kernel(key);
  if (const int k = g_kernel.load(std::memory_order_relaxed)) return Kernel(k);
  if (!t.fast) return Kernel::kNeon;
  static std::atomic<bool> timing{false};
  if (timing.exchange(true)) return Kernel::kNeon;  // another thread is timing: this call as before
  std::vector<uint8_t> scratch(size_t(p.pairs) * 64u * p.w8 + 64u);
  double best[5] = {1e30, 1e30, 1e30, 1e30, 1e30};
  for (int round = 0; round < 2; ++round) {
    for (int k = 1; k <= 4; ++k) {
      const auto start = std::chrono::steady_clock::now();
      uint8_t* out = scratch.data();
      for (uint32_t i = 0; i < p.pairs; ++i, out += 64u * p.w8) {
        const PairPtrs q = PairPointers(base, p, i);
        PairHost(t, q.y0, q.y1, q.a, q.b, out, out + 32u * p.w8, p.w8, Kernel(k));
      }
      const double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - start).count();
      best[k] = std::min(best[k], ms);
    }
  }
  int pick = 1;
  for (int k = 2; k <= 4; ++k)
    if (best[k] < best[pick]) pick = k;
  static const char* const kNames[5] = {"", "PairNeon", "PairLanes", "PairPacked", "PairPacked with DC ZVA"};
  REXLOG_INFO("[hot] sub_82E7F918 kernels on the first picture ({}x{}): PairNeon {:.2f} ms, PairLanes {:.2f} ms, "
              "PairPacked {:.2f} ms, PairPacked with DC ZVA {:.2f} ms{}: {} for the session (sasrt_movie_colour_kernel "
              "0; the same bytes)", p.w8 * 8, p.pairs * 2, best[1], best[2], best[3], best[4],
              ZvaUsable() ? "" : " (DC ZVA not usable here: plain)", kNames[pick]);
  g_kernel.store(pick, std::memory_order_relaxed);
  return Kernel(pick);
}

// sasrt-nx (2026-11-09, sasrt_movie_colour_helpers; the user: "optimise the intro video so it stops dropping frames"):
// up to two more threads take row pairs too (chunks of kChunk from one counter, so none waits on a slow share): the
// first on the system core where there is one (core 3: the XMA decoder's, idle about half the time), the second on the
// game's cores (a third of them idle in the intro). The conversion is a pure function of the planes and the tables
// into rows that overlap neither (Native checks): split by row pairs, the same bytes. The calling thread returns once
// every row pair is written (the guest sees the whole picture when the call returns, as with one thread), not waiting
// for a helper that has not woken: each call is a job of its own (its plan copied, its counters), so a helper waking
// late finds that job's rows all taken and touches nothing (the tables are read only for rows it took, all done before
// the call returns). One call at a time uses the helpers (a second thread's call meanwhile converts alone).
class Helper {
 public:
  // row pairs: 8 rows of a 1280-pixel picture, 40 KB of pixels (8 pairs before the console's movie_fix2 run: the
  // caller did 41 % of the rows and still waited about 1.6 ms a picture for the helpers' last chunks)
  static constexpr uint32_t kChunk = 4;
  static constexpr int kMaxThreads = 2;

  // Converts every row pair of 'p', with 'threads' helpers when they are free; false when they were not (nothing done).
  bool Run(uint8_t* base, const Tables& t, const Plan& p, Kernel k, int threads) {
    std::unique_lock<std::mutex> busy(busy_, std::try_to_lock);
    if (!busy.owns_lock()) return false;
    Start(threads);
    auto job = std::make_shared<Job>();
    job->base = base;
    job->t = &t;
    job->p = p;
    job->k = k;
    {
      std::lock_guard<std::mutex> lock(m_);
      job_ = job;
      ++posted_;
    }
    wake_.notify_all();
    const uint32_t mine = Work(*job);
    {
      std::unique_lock<std::mutex> lock(m_);
      done_cv_.wait(lock, [&] { return job->finished.load(std::memory_order_acquire) >= job->p.pairs; });
    }
    caller_pairs_.fetch_add(mine, std::memory_order_relaxed);
    all_pairs_.fetch_add(p.pairs, std::memory_order_relaxed);
    return true;
  }
  // The row pairs the callers did themselves, of all, since the last time asked (for the timing line).
  void Shares(uint64_t& caller, uint64_t& all) {
    caller = caller_pairs_.exchange(0, std::memory_order_relaxed);
    all = all_pairs_.exchange(0, std::memory_order_relaxed);
  }

 private:
  struct Job {
    uint8_t* base = nullptr;
    const Tables* t = nullptr;
    Plan p;
    Kernel k = Kernel::kNeon;
    std::atomic<uint32_t> next{0}, finished{0};
  };

  void Start(int threads) {
    for (int i = started_; i < std::min(threads, kMaxThreads); ++i) {
      threads_[i] = std::thread([this, i] { Loop(i); });
      started_ = i + 1;
    }
  }
  static uint32_t Work(Job& j) {
    uint32_t done = 0;
    for (;;) {
      const uint32_t i0 = j.next.fetch_add(kChunk, std::memory_order_relaxed);
      if (i0 >= j.p.pairs) return done;
      const uint32_t i1 = std::min(i0 + kChunk, j.p.pairs);
      for (uint32_t i = i0; i < i1; ++i) PairAt(j.base, *j.t, j.p, i, j.k);
      j.finished.fetch_add(i1 - i0, std::memory_order_release);
      done += i1 - i0;
    }
  }
  void Loop(int index) {
#if REX_PLATFORM_SWITCH
    // The first helper on core 3 when the four-core mode has it; the second on the game's cores. Both at the render
    // thread's priority (0x2C, the game's threads 0x3B): movie_fix2 had them at 0x3B, where a decoder thread on the
    // same core took turns with a helper mid-chunk while the caller waited (the core-3 helper ran 2.5 % CPU).
    if (index == 0 && RexSwitchSystemCore() >= 0)
      RexSwitchMoveCurrentThreadToSystemCore(0x2C);
    else
      (void)RexSwitchSetCurrentThreadPriorityOk(0x2C);
#endif
    (void)index;
    uint64_t seen = 0;
    for (;;) {
      std::shared_ptr<Job> job;
      {
        std::unique_lock<std::mutex> lock(m_);
        wake_.wait(lock, [&] { return posted_ != seen; });
        seen = posted_;
        job = job_;
      }
      Work(*job);
      { std::lock_guard<std::mutex> lock(m_); }  // the caller's wait checks under the lock: no lost wake-up
      done_cv_.notify_all();
    }
  }

  std::mutex busy_, m_;
  std::condition_variable wake_, done_cv_;
  std::thread threads_[kMaxThreads];
  int started_ = 0;
  uint64_t posted_ = 0;
  std::shared_ptr<Job> job_;
  std::atomic<uint64_t> caller_pairs_{0}, all_pairs_{0};
};

inline Helper& TheHelper() {
  static Helper* helper = new Helper();  // never freed: its threads live as long as the process
  return *helper;
}

// sasrt-nx (2026-11-09): a line every 300 pictures: the call's time (the caller's, from its tables to its last row) and
// the share of row pairs the caller did itself.
inline void NoteTiming(double ms, uint32_t w, uint32_t h, Kernel k, int helpers) {
  static std::atomic<uint64_t> calls{0};
  static std::atomic<uint64_t> total_us{0};
  total_us.fetch_add(uint64_t(ms * 1000.0), std::memory_order_relaxed);
  if (calls.fetch_add(1, std::memory_order_relaxed) % 300 != 299) return;
  const double avg = double(total_us.exchange(0, std::memory_order_relaxed)) / 300000.0;
  uint64_t caller = 0, all = 0;
  TheHelper().Shares(caller, all);
  REXLOG_INFO("[hot] sub_82E7F918 ({}x{}): {:.2f} ms a picture over the last 300, kernel {}, {} helpers, the calling "
              "thread did {:.0f} % of the row pairs", w, h, avg, int(k), helpers,
              all ? 100.0 * double(caller) / double(all) : 100.0);
}

inline bool Native(PPCContext& ctx, uint8_t* base) {
  Plan p;
  uint32_t src[3][2];
  if (!MakePlan(ctx, base, p, src)) return false;
  if (p.lo != p.hi) {
    for (const auto& s : src)
      if (Overlaps(p.lo, p.hi, s[0], s[1])) return false;
    if (Overlaps(p.lo, p.hi, kTables, kTables + 5120u)) return false;
    static thread_local Tables* tables = new Tables();  // per thread, never freed (33 KB)
    Tables& t = *tables;
    if (!LoadTables(base, t)) return false;
    // The clamp's own range, read above, must not be under the target either.
    if (Overlaps(p.lo, p.hi, kTables + 5120u + uint32_t(t.imin) * 4u, kTables + 5124u + uint32_t(t.imax) * 4u))
      return false;
    static std::atomic<bool> logged{false};
    if (!logged.exchange(true, std::memory_order_relaxed))
      REXLOG_INFO("[hot] sub_82E7F918 (the movies' colour conversion): {}x{} pixels, clamp indices {}..{}, {}",
                  p.w8 * 8, p.pairs * 2, t.imin, t.imax,
                  t.fast ? fmt::format("a clamp at k {} over {}..{}: NEON for groups inside it", t.k, t.k + t.vlo,
                                       t.k + t.vhi)
                         : std::string("no clamp step found: the table path"));
    // sasrt-nx (2026-11-09): the kernel and the helper threads, each its own key.
    const auto start = std::chrono::steady_clock::now();
    const Kernel k = ChooseKernel(base, t, p);
    const int helpers = HelpersKey();
    if (!(helpers > 0 && p.pairs >= 2 * Helper::kChunk && TheHelper().Run(base, t, p, k, helpers)))
      for (uint32_t i = 0; i < p.pairs; ++i) PairAt(base, t, p, i, k);
    NoteTiming(std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - start).count(), p.w8 * 8,
               p.pairs * 2, k, helpers);
    Card(base, p.lo, p.hi - p.lo);
  }
  ctx.r3.u64 = p.r3;
  return true;
}

inline void Writes(const PPCContext& ctx, const uint8_t* base, ::sasrt::hot::Writes& w) {
  Plan p;
  uint32_t src[3][2];
  if (MakePlan(ctx, base, p, src) && p.lo != p.hi) w.Add(p.lo, p.hi - p.lo);
}

}  // namespace sasrt::hot::n_82E7F918
