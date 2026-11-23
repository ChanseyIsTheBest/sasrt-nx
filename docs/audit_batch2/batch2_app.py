# Batch 2's app half (machine-copy ideas 39, 52, 35, 46), with batch 2's audit fixes. Idempotent (finding 14): a file
# already patched is left alone. Apply after round A's builds.
R = 'D:/sonic transformed/sasrt-nx/'
MARK = 'machine-copy batch 2 (2026-11-11)'


def load(p):
    b = open(R + p, 'rb').read()
    crlf = b'\r\n' in b
    return b.decode('utf-8').replace('\r\n', '\n'), crlf


def save(p, s, crlf):
    open(R + p, 'wb').write((s.replace('\n', '\r\n') if crlf else s).encode('utf-8'))


def rep(s, old, new):
    assert s.count(old) == 1, (old[:90], s.count(old))
    return s.replace(old, new)


def patch(path, edits):
    s, c = load(path)
    if MARK in s:
        print('already patched:', path)
        return
    for old, new in edits:
        s = rep(s, old, new)
    save(path, s, c)
    print('patched:', path)


# --- banjo_hot_common.h: the defaults (ideas 39 and 52) ---
patch('app/src/cpu/banjo_hot_common.h', [('''#define BANJO_HOT_STORE_U32_C(x, y)''', '''// sasrt-nx (2026-11-11, machine-copy batch 2 (2026-11-11), idea 52): a prefetch of the guest node a pointer-chasing
// loop just loaded (tools/localize_native.py, PREFETCH). A hint: it cannot fault. CMake SASRT_HOT_PREFETCH=OFF: nothing.
#ifndef REX_PREFETCH_GUEST
#if defined(SASRT_HOT_PREFETCH_OFF)
#define REX_PREFETCH_GUEST(a) ((void)0)
#else
#define REX_PREFETCH_GUEST(a) __builtin_prefetch(REX_RAW_ADDR((u32)(a)))
#endif
#endif
// Idea 39: tools/localize_native.py's store-card runs; nothing unless banjo_hot_prelude.h (the bulk shards,
// SASRT_HOT_CARD_RUNS, copies written with the runs) defines them.
#ifndef REX_CARD_RUN_DECL
#define REX_CARD_RUN_DECL
#endif
#ifndef REX_CARD_FLUSH
#define REX_CARD_FLUSH() ((void)0)
#endif
#define BANJO_HOT_STORE_U32_C(x, y)''')])

# --- banjo_hot_prelude.h: the runs (idea 39; audit findings 1, 2) ---
patch('app/src/cpu/banjo_hot_prelude.h', [('''#include "cpu/hot/banjo_hand_natives.h"''', '''#include "cpu/hot/banjo_hand_natives.h"
// sasrt-nx (2026-11-11, machine-copy batch 2 (2026-11-11), idea 39): store-card runs in the bulk copies
// (tools/localize_native.py, CARD_RUNS). A copy's function keeps the page of its run of stores (rex_card_run; 0xFFFFF:
// none pending) and marks a page's card when the run moves to another page; REX_CARD_FLUSH marks the pending one (before
// calls, fences and returns, and at the end) and clears it. A compare-and-swap marks the pending page and its own at
// once. With nothing pending a flush compiles to nothing (audit finding 1: a function that stores nothing marks
// nothing). Only for copies written with the runs (banjo_hot_options.h: audit finding 2). The hand-written natives
// above keep marking at each store.
#if __has_include("../../generated/hot/banjo_hot_options.h")
#include "../../generated/hot/banjo_hot_options.h"
#endif
#if defined(SASRT_HOT_CARD_RUNS) && defined(REX_CARD_RUNS_GENERATED) && !defined(REX_STORE_CARDS_OFF)
#undef REX_CARD
#undef REX_CARD_RUN_DECL
#undef REX_CARD_FLUSH
#undef REX_GUEST_CAS_C
#define REX_CARD_RUN_DECL [[maybe_unused]] u32 rex_card_run = 0xFFFFFu;
#define REX_CARD(ea)                                                                                      \\
  ((void)((((u32)(ea)) >> 12) != rex_card_run                                                            \\
              ? ((rex_card_run != 0xFFFFFu ? (void)(*(u8*)(base + rex_card_run) = 0) : (void)0),          \\
                 rex_card_run = ((u32)(ea)) >> 12, 0)                                                     \\
              : 0))
#define REX_CARD_FLUSH() \\
  ((void)(rex_card_run != 0xFFFFFu ? (*(u8*)(base + rex_card_run) = 0, rex_card_run = 0xFFFFFu, 0) : 0))
#define REX_GUEST_CAS_C(ea, p, e, d) \\
  (REX_CARD_FLUSH(), (void)(*(u8*)(base + (((u32)(ea)) >> 12)) = 0), REX_GUEST_CAS(p, e, d))
#endif''')])

# --- CMake: the switches (ideas 39, 52) ---
patch('app/CMakeLists.txt', [('''if(SASRT_HOT_LR_ELIDE)
    foreach(_shard RANGE 0 11)''', '''# sasrt-nx (2026-11-11, machine-copy batch 2 (2026-11-11), idea 52): the copies' pointer-chase prefetches.
option(SASRT_HOT_PREFETCH "Localized copies: a prefetch after a loop's next-pointer load (REX_PREFETCH_GUEST)" ON)
if(NOT SASRT_HOT_PREFETCH)
    target_compile_definitions(sasrt PRIVATE SASRT_HOT_PREFETCH_OFF)
endif()
# Idea 39: the bulk copies mark store cards per run of stores to a page (app/src/cpu/banjo_hot_prelude.h); OFF: at every
# store, as the tree does.
option(SASRT_HOT_CARD_RUNS "The bulk copies (shards 0-11): store cards marked per run of stores to a page" ON)
if(SASRT_HOT_CARD_RUNS)
    foreach(_shard RANGE 0 11)
        set_property(SOURCE src/cpu/banjo_hot_shard_${_shard}.cpp APPEND PROPERTY COMPILE_DEFINITIONS SASRT_HOT_CARD_RUNS)
    endforeach()
endif()
if(SASRT_HOT_LR_ELIDE)
    foreach(_shard RANGE 0 11)''')])

# --- banjo_hot_guest.h: idea 35's counters (audit finding 8: after the whole line, its comment kept) ---
patch('app/src/cpu/banjo_hot_guest.h', [('''  std::atomic<uint64_t> not_repeated{0};    // guarded calls that differed once and compared equal when repeated''',
                                          '''  std::atomic<uint64_t> not_repeated{0};    // guarded calls that differed once and compared equal when repeated
  // sasrt-nx (2026-11-11, machine-copy batch 2 (2026-11-11), idea 35, banjo_hot_guard_prefix): calls both forms stopped
  // in (an atomic, or a call outside the copy) whose stores before the stop were the same / not.
  std::atomic<uint64_t> prefix_equal{0};
  std::atomic<uint64_t> prefix_differ{0};''')])

# --- banjo_hot_guest.cpp: ideas 35 and 46 (audit findings 7, 8, 11, 12) ---
patch('app/src/cpu/banjo_hot_guest.cpp', [
    ('''#include <algorithm>
#include <chrono>''', '''#include <algorithm>
#include <chrono>
#include <iterator>
#include <mutex>
#include <thread>'''),
    ('''REXCVAR_DEFINE_INT32(banjo_hot_guard_calls,''', '''// sasrt-nx (2026-11-11, machine-copy batch 2 (2026-11-11), idea 35): the copies with atomics (and every copy that
// reaches a call outside itself) stop the guard's logged forms there: such a call was "not comparable". When both forms
// stopped, the bytes each wrote before its stop are compared too (the same inputs, the same path: the same stores up to
// the first atomic or outside call). Counted and logged only: a hand-written native in front of a callee can make the
// two forms stop at different points, so a difference here does not switch the copy off.
REXCVAR_DEFINE_BOOL(banjo_hot_guard_prefix, true, "SASRT/Localized copies",
                    "The guard: when the copy and the original both stop (an atomic or a call outside the copy), compare "
                    "the stores each made before it (counted in the [hot] summary; a difference is logged, not acted on)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
// Idea 46, part 1: which of the writable guest globals the copies load at a known address (tools/frozen_census.py,
// app/generated/hot/frozen_census.inc) the game writes once. A background thread reads them all every 8 ms from the
// first hook's start (racy reads of guest memory: a census, nothing depends on it) and keeps, per global, how often and
// when it last changed; 240 s in it lists them (with the time of the last change, so the race's start separates the ones
// written while loading from the ones that change while racing). Part 2 builds the stable ones into their copies.
REXCVAR_DEFINE_BOOL(sasrt_cpu_frozen_census, false, "SASRT/Localized copies",
                    "Diagnostics: sample the writable guest globals the localized copies load at a known address every "
                    "8 ms and list which change (\\"[frozen]\\" lines; machine-copy idea 46)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_INT32(banjo_hot_guard_calls,'''),
    ('''std::atomic<int64_t> g_last_report_ms{0};''', '''// Idea 35: what one logged form wrote (its ranges merged and sorted, their bytes after it; `at` the ranges' offsets).
struct Written {
  std::vector<Region> ranges;
  std::vector<size_t> at;
  std::vector<uint8_t> bytes;
};

void CaptureWritten(const WriteLog& log, uint8_t* base, Written& w) {
  w.ranges.clear();
  w.at.clear();
  w.bytes.clear();
  AddRanges(log, w.ranges);
  Merge(w.ranges);
  for (const Region& r : w.ranges) {
    w.at.push_back(w.bytes.size());
    const uint8_t* p = Raw(base, r.addr);
    w.bytes.insert(w.bytes.end(), p, p + r.len);
  }
}

// The kept buffers back to small after a big call (audit finding 8, as ScratchFrame's rule).
void TrimWritten(Written& w) {
  if (w.bytes.capacity() > (256u << 10)) {
    w.bytes = {};
    w.ranges = {};
    w.at = {};
  }
}

// The byte at guest address x after the form that wrote `w` (memory as it is now where the form did not write: both
// forms are rolled back when this runs, so that is the state before either). A binary search (audit finding 7).
uint8_t AfterForm(const Written& w, uint8_t* base, uint32_t x) {
  auto it = std::upper_bound(w.ranges.begin(), w.ranges.end(), x,
                             [](uint32_t v, const Region& r) { return v < r.addr; });
  if (it != w.ranges.begin()) {
    --it;
    if (uint64_t(x) < uint64_t(it->addr) + it->len) return w.bytes[w.at[size_t(it - w.ranges.begin())] + (x - it->addr)];
  }
  return *Raw(base, x);
}

bool PrefixEqual(uint8_t* base, const Written& a, const Written& b, std::string& where) {
  std::vector<Region> all = a.ranges;
  all.insert(all.end(), b.ranges.begin(), b.ranges.end());
  Merge(all);
  for (const Region& r : all) {
    for (uint32_t k = 0; k < r.len; ++k) {
      const uint32_t x = r.addr + k;
      const uint8_t va = AfterForm(a, base, x), vb = AfterForm(b, base, x);
      if (va != vb) {
        where = fmt::format("memory {:#010x} copy={:#04x} original={:#04x}", x, va, vb);
        return false;
      }
    }
  }
  return true;
}

std::atomic<int64_t> g_last_report_ms{0};'''),
    ('''  const bool native_stopped = t.log.stopped;
  bool overflow = t.log.overflow;
  AddRanges(t.log, t.ranges);
  t.log.RollBack();''', '''  const bool native_stopped = t.log.stopped;
  bool overflow = t.log.overflow;
  AddRanges(t.log, t.ranges);
  static const bool prefix = REXCVAR_GET(banjo_hot_guard_prefix);  // idea 35
  static thread_local Written native_written, reference_written;
  if (prefix && native_stopped && !t.log.overflow) CaptureWritten(t.log, base, native_written);
  t.log.RollBack();'''),
    ('''  const bool reference_stopped = t.log.stopped;
  overflow |= t.log.overflow;
  AddRanges(t.log, t.ranges);
  t.log.RollBack();''', '''  const bool reference_stopped = t.log.stopped;
  overflow |= t.log.overflow;
  AddRanges(t.log, t.ranges);
  if (prefix && reference_stopped && !overflow) CaptureWritten(t.log, base, reference_written);
  t.log.RollBack();'''),
    ('''      return Outcome::kPathsDiffer;
    }
    return Outcome::kNotComparable;''', '''      return Outcome::kPathsDiffer;
    }
    if (prefix && native_stopped && reference_stopped && !overflow) {  // idea 35
      std::string where;
      if (PrefixEqual(base, native_written, reference_written, where)) {
        h.prefix_equal.fetch_add(1, std::memory_order_relaxed);
      } else {
        const uint64_t n = h.prefix_differ.fetch_add(1, std::memory_order_relaxed) + 1;
        if (n <= 2)
          REXLOG_WARN("[hot] {}: the stores before the stop differ (banjo_hot_guard_prefix; not acted on): {}",
                      h.name, where);
      }
      TrimWritten(native_written);
      TrimWritten(reference_written);
    }
    return Outcome::kNotComparable;'''),
    ('''  uint64_t compared = 0, not_comparable = 0, differences = 0, not_repeated = 0;''',
     '''  uint64_t compared = 0, not_comparable = 0, differences = 0, not_repeated = 0, prefix_equal = 0, prefix_differ = 0;'''),
    ('''    const uint8_t state = h->state.load(std::memory_order_relaxed);
    bulk_total += h->bulk;''', '''    const uint8_t state = h->state.load(std::memory_order_relaxed);
    bulk_total += h->bulk;
    prefix_equal += h->prefix_equal.load(std::memory_order_relaxed);  // idea 35 (every hook: audit finding 8)
    prefix_differ += h->prefix_differ.load(std::memory_order_relaxed);'''),
    ('''              "of {} reached, {} on; {} calls compared so far, {} not comparable, {} differed once and not when "
              "repeated, differences: {}",
              reached, on, direct, REXCVAR_GET(banjo_cpu_native_bulk) ? "on" : "off", bulk_reached, bulk_total, bulk_on,
              compared, not_comparable, not_repeated, differences);''', '''              "of {} reached, {} on; {} calls compared so far, {} not comparable ({} of them stopped in both forms "
              "with the same stores before the stop, {} not), {} differed once and not when repeated, differences: {}",
              reached, on, direct, REXCVAR_GET(banjo_cpu_native_bulk) ? "on" : "off", bulk_reached, bulk_total, bulk_on,
              compared, not_comparable, prefix_equal, prefix_differ, not_repeated, differences);'''),
    ('''uint8_t InitHook(Hook& h, uint8_t* base) {
  // May run on several threads at once for the first call: every one of them stores the same values.''', '''namespace {

// Idea 46's census (sasrt_cpu_frozen_census above).
struct CensusGlobal {
  uint32_t addr;
  uint32_t size;
};
constexpr CensusGlobal kCensusGlobals[] = {
#if __has_include("../../generated/hot/frozen_census.inc")  // audit finding 11: a tree without it (classic) still builds
#include "../../generated/hot/frozen_census.inc"
#endif
    {0u, 0u},  // the end (the list may be empty)
};

void FrozenCensus(uint8_t* base) {
  using Clock = std::chrono::steady_clock;
  const size_t n = std::size(kCensusGlobals) - 1;
  std::vector<uint64_t> first(n), last(n);
  std::vector<uint32_t> changes(n, 0);
  std::vector<double> last_change_s(n, 0.0);
  auto read = [base](const CensusGlobal& g) {
    const uint8_t* p = Raw(base, g.addr);
    uint64_t v = 0;
    for (uint32_t k = 0; k < g.size; ++k) v = (v << 8) | p[k];
    return v;
  };
  for (size_t i = 0; i < n; ++i) first[i] = last[i] = read(kCensusGlobals[i]);
  const auto start = Clock::now();
  auto next_report = start + std::chrono::seconds(10);
  bool listed = false;
  uint64_t samples = 0;
  for (;;) {
    std::this_thread::sleep_for(std::chrono::milliseconds(8));
    ++samples;
    const auto now = Clock::now();
    const double t = std::chrono::duration<double>(now - start).count();
    for (size_t i = 0; i < n; ++i) {
      const uint64_t v = read(kCensusGlobals[i]);
      if (v != last[i]) {
        ++changes[i];
        last[i] = v;
        last_change_s[i] = t;
      }
    }
    if (now < next_report) continue;
    next_report += std::chrono::seconds(10);
    size_t changed = 0, changed_late = 0;
    for (size_t i = 0; i < n; ++i) {
      changed += changes[i] != 0;
      changed_late += changes[i] != 0 && t - last_change_s[i] < 10.0;
    }
    REXLOG_INFO("[frozen] census (sasrt_cpu_frozen_census), {:.0f} s: {} globals, {} changed at least once, {} in the "
                "last 10 s; {} samples", t, n, changed, changed_late, samples);
    if (!listed && t >= 240.0) {
      listed = true;
      for (size_t i = 0; i < n; ++i)
        REXLOG_INFO("[frozen] {:#010x} size {} value {:#x} (first {:#x}): {} changes, the last at {:.1f} s",
                    kCensusGlobals[i].addr, kCensusGlobals[i].size, last[i], first[i], changes[i], last_change_s[i]);
    }
  }
}

}  // namespace

uint8_t InitHook(Hook& h, uint8_t* base) {
  // sasrt-nx (2026-11-11, machine-copy idea 46): the census thread, once, from the first hook (sasrt_cpu_frozen_census).
  static std::once_flag census_once;
  if (REXCVAR_GET(sasrt_cpu_frozen_census) && std::size(kCensusGlobals) > 1)
    std::call_once(census_once, [base] { std::thread(FrozenCensus, base).detach(); });
  // May run on several threads at once for the first call: every one of them stores the same values.'''),
])
print('batch 2 app half done')
