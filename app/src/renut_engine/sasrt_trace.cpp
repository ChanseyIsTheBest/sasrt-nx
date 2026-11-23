// sasrt-nx (2026-11-08): see sasrt_trace.h.
#include "renut_engine/sasrt_trace.h"

#include <atomic>
#include <condition_variable>
#include <cstdio>
#include <deque>
#include <chrono>
#include <cstring>
#include <functional>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include <rex/cvar.h>
#include <rex/logging.h>

#include "renut_engine/gpu/guest/guest_memory.h"
#include "renut_engine/gpu/banjo_renut_tuning.h"  // sasrt-nx (2026-11-19): StartLongLivedThread

REXCVAR_DEFINE_BOOL(sasrt_renut_diag_trace, false, "SASRT",
                    "Diagnostic (the far-cascade flicker, 2026-11-08): a timeline of the game thread's Swap, pacing and "
                    "waits, the worker's command buffer recording (with the scene pass's camera), splices, submissions, "
                    "GPU callbacks and fence waits, written to the log ('[trace]' lines) from 1.5 s before to 1.5 s "
                    "after each shadow dump window's start")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
// sasrt-nx (2026-11-19): the shadow dump's windows (the trace's trigger) do nothing since the move to the ultimate base
// (draw.cpp SasrtShadowDumpWindow); these are the trace's own.
REXCVAR_DEFINE_STRING(sasrt_renut_diag_trace_windows, "", "SASRT",
                      "Diagnostic (2026-11-19): \"<first s>,<every s>,<windows>\": sasrt_renut_diag_trace's windows "
                      "(1.5 s each side) from <first s> after the first Swap, every <every s>, <windows> times")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

namespace sasrt::trace {

namespace {

struct Event {
  uint64_t t_us;
  uint64_t arg;
  uint64_t arg2;
  uint32_t thread;
  uint32_t sample;  // the watched word then
  uint16_t kind;
};

constexpr uint32_t kRing = 1u << 16;
Event g_ring[kRing];
std::atomic<uint64_t> g_next{0};
std::atomic<uint64_t> g_dump_after_us{0};  // when the pending dump is written (0: none)
std::atomic<uint64_t> g_dump_from_us{0};
std::mutex g_dump_mutex;
std::atomic<bool> g_after_swap{false};
std::atomic<bool> g_camera_after_swap{false};
std::atomic<uint32_t> g_watch{0};
std::atomic<bool> g_hunt{false};

uint64_t NowUs() {
  return uint64_t(std::chrono::duration_cast<std::chrono::microseconds>(
                      std::chrono::steady_clock::now().time_since_epoch())
                      .count());
}

uint32_t ThreadTag() {
  thread_local uint32_t tag = uint32_t(std::hash<std::thread::id>{}(std::this_thread::get_id()) % 100000u);
  return tag;
}

const char *Name(uint16_t kind) {
  switch (kind) {
    case kSwap: return "swap";
    case kPaceBegin: return "pace-begin";
    case kPaceEnd: return "pace-end";
    case kFrameWaitBegin: return "frame-wait-begin";
    case kFrameWaitEnd: return "frame-wait-end";
    case kBeginCb: return "begin-cb";
    case kEndCb: return "end-cb";
    case kSceneCamera: return "scene-camera";
    case kSplice: return "splice";
    case kSubmit: return "submit";
    case kCallbackInsert: return "callback-insert";
    case kCallbackRun: return "callback-run";
    case kFenceWaitBegin: return "fence-wait-begin";
    case kFenceWaitEnd: return "fence-wait-end";
    case kLateInputBegin: return "late-input-begin";
    case kLateInputEnd: return "late-input-end";
    case kRenderFrameDone: return "render-frame-done";
    case kWindow: return "window";
    case kGameFirstDraw: return "game-first-draw";
    case kGameCamera: return "game-camera";
    case kSpliceBuffer: return "splice-buffer";
    case kSubmitBuffer: return "submit-buffer";
    case kSlotFill: return "slot-fill";
    case kComposite: return "composite";
    case kRenderCamera: return "render-camera";
    case kSplitRun: return "split-run";
    default: return "?";
  }
}

void Dump(uint64_t from_us, uint64_t to_us) {
  std::lock_guard lock(g_dump_mutex);
  const uint64_t end = g_next.load(std::memory_order_acquire);
  const uint64_t begin = end > kRing ? end - kRing : 0;
  std::vector<Event> events;
  for (uint64_t i = begin; i < end; ++i) {
    const Event &e = g_ring[i % kRing];
    if (e.t_us >= from_us && e.t_us <= to_us)
      events.push_back(e);
  }
  REXLOG_INFO("[trace] {} events from {} to {} us", events.size(), from_us, to_us);
  for (const Event &e : events) {
    const auto f = [](uint64_t bits) {
      float v;
      const uint32_t w = uint32_t(bits);
      std::memcpy(&v, &w, 4);
      return v;
    };
    if (e.kind == kRenderCamera) {
      REXLOG_INFO("[trace] {} t{:05} {} x {:.3f} buffer {:X}", e.t_us, e.thread, Name(e.kind), f(e.arg), e.arg2);
    } else if (e.kind == kSpliceBuffer || e.kind == kSubmitBuffer || e.kind == kSlotFill || e.kind == kSplitRun ||
               (e.kind == kEndCb && e.arg2)) {
      REXLOG_INFO("[trace] {} t{:05} {} {:X} x {:.3f}", e.t_us, e.thread, Name(e.kind), e.arg, f(e.arg2));
    } else if (e.kind == kGameCamera) {
      REXLOG_INFO("[trace] {} t{:05} {} x {:.3f} y {:.3f}", e.t_us, e.thread, Name(e.kind), f(e.arg), f(e.arg2));
    } else if (e.kind == kSceneCamera) {
      float a, b;
      const uint32_t wa = uint32_t(e.arg), wb = uint32_t(e.arg2);
      std::memcpy(&a, &wa, 4);
      std::memcpy(&b, &wb, 4);
      REXLOG_INFO("[trace] {} t{:05} {} c133.w {:.4f} x {:.4f} watch {:.4f}", e.t_us, e.thread, Name(e.kind), a, b, [&] { float w; std::memcpy(&w, &e.sample, 4); return w; }());
    } else {
      float w;
      std::memcpy(&w, &e.sample, 4);
      REXLOG_INFO("[trace] {} t{:05} {} {:X} {:X} watch {:.4f}", e.t_us, e.thread, Name(e.kind), e.arg, e.arg2, w);
    }
  }
}

// sasrt-nx (2026-11-19): the dumps' own thread (banjo::renut_gpu::StartLongLivedThread: pthread with a stack of its
// own on the console), started by the first window.
std::mutex g_request_mutex;
std::condition_variable g_request_cv;
std::deque<std::pair<uint64_t, uint64_t>> g_requests;
void DumpThread() {
  for (;;) {
    std::pair<uint64_t, uint64_t> r;
    {
      std::unique_lock lock(g_request_mutex);
      g_request_cv.wait(lock, [] { return !g_requests.empty(); });
      r = g_requests.front();
      g_requests.pop_front();
    }
    Dump(r.first, r.second);
  }
}

}  // namespace

bool g_on_value = false;  // sasrt-nx (2026-11-12, batch C10)
std::atomic<bool> g_on_latched{false};
bool LatchOn() {
  static const bool on = REXCVAR_GET(sasrt_renut_diag_trace);
  g_on_value = on;
  g_on_latched.store(true, std::memory_order_release);
  return on;
}

void Note(Kind kind, uint64_t arg, uint64_t arg2) {
  if (!On())
    return;
  const uint64_t now = NowUs();
  const uint64_t i = g_next.fetch_add(1, std::memory_order_relaxed);
  Event &e = g_ring[i % kRing];
  e.t_us = now;
  e.arg = arg;
  e.arg2 = arg2;
  e.thread = ThreadTag();
  e.kind = uint16_t(kind);
  e.sample = 0;
  if (const uint32_t w = g_watch.load(std::memory_order_relaxed)) {
    if (const auto *p = ::renut::gpu::GuestPtr<const uint32_t>(w))
      e.sample = __builtin_bswap32(*p);
  }
  if (kind == kSwap) {
    g_after_swap.store(true, std::memory_order_relaxed);
    g_camera_after_swap.store(true, std::memory_order_relaxed);
    // sasrt-nx (2026-11-19): sasrt_renut_diag_trace_windows (the game thread's Swap: one thread).
    static int first_s = -1, every_s = 0, left = 0;
    static uint64_t first_swap_us = 0, next_us = 0;
    if (first_s < 0) {
      first_s = 0;
      const std::string v = REXCVAR_GET(sasrt_renut_diag_trace_windows);
      int a = 0, b = 0, c = 0;
      if (std::sscanf(v.c_str(), "%d,%d,%d", &a, &b, &c) == 3 && a >= 0 && b > 0 && c > 0) {
        first_s = a;
        every_s = b;
        left = c;
      }
      first_swap_us = now;
      next_us = now + uint64_t(first_s) * 1000000u;
    }
    if (left > 0 && now >= next_us) {
      --left;
      next_us += uint64_t(every_s) * 1000000u;
      WindowBegan(arg);
    }
  }
  // A pending dump is written by the first event after its end (any thread).
  uint64_t after = g_dump_after_us.load(std::memory_order_relaxed);
  const uint64_t to = after;
  if (after && now > after && g_dump_after_us.compare_exchange_strong(after, 0)) {
    // sasrt-nx (2026-11-19): to the dump thread (a detached std::thread a dump, on libnx's default stack, closed the
    // console's game right after its first dump: log 301).
    {
      std::lock_guard lock(g_request_mutex);
      g_requests.emplace_back(g_dump_from_us.load(), to);
    }
    g_request_cv.notify_one();
  }
}

void NoteDraw(uint64_t index_count) {
  if (On() && g_after_swap.exchange(false, std::memory_order_relaxed))
    Note(kGameFirstDraw, index_count);
}

void SetWatch(uint32_t guest_address) {
  g_watch.store(guest_address, std::memory_order_relaxed);
}

bool TakeHunt() {
  return On() && g_hunt.exchange(false, std::memory_order_relaxed);
}

void NoteGameCamera(const uint8_t *c) {
  if (!On())
    return;
  const auto word = [c](uint32_t reg, uint32_t k) {
    uint32_t v;
    std::memcpy(&v, c + reg * 16 + k * 4, 4);
    return __builtin_bswap32(v);
  };
  // sasrt-nx (2026-11-19, split screen): each change of the camera's x (c142.w), not only the first after a Swap.
  static std::atomic<uint32_t> last_x{0};
  if ((word(136, 2) >> 16) == 0xBF80u && (word(136, 3) >> 16) == 0xBF80u && word(137, 3) == 0) {
    const uint32_t x = word(142, 3);
    if (last_x.exchange(x, std::memory_order_relaxed) != x)
      Note(kGameCamera, x, word(143, 3));
  }
}

void NoteRenderCamera(const uint8_t *c136, const uint8_t *c137, const uint8_t *c142, uint32_t replay_buffer) {
  if (!On())
    return;
  if ((CameraWord(c136, 2) >> 16) != 0xBF80u || (CameraWord(c136, 3) >> 16) != 0xBF80u || CameraWord(c137, 3) != 0)
    return;
  static uint64_t last = 0;  // the render thread only
  const uint64_t key = CameraWord(c142, 3) | (uint64_t(replay_buffer) << 32);
  if (key == last)
    return;
  last = key;
  Note(kRenderCamera, CameraWord(c142, 3), replay_buffer);
}

std::atomic<uint64_t> g_diag_window_us{0};  // sasrt-nx (2026-11-20): DiagWindowNow

int DiagWindowNow() {
  const uint64_t w = g_diag_window_us.load(std::memory_order_relaxed);
  return w && NowUs() - w < 150000 ? 0 : -1;
}

void WindowBegan(uint64_t frame) {
  if (!On())
    return;
  g_diag_window_us.store(NowUs(), std::memory_order_relaxed);
  g_hunt.store(true, std::memory_order_relaxed);
  static std::once_flag started;
  std::call_once(started, [] { banjo::renut_gpu::StartLongLivedThread(&DumpThread, 512 * 1024); });
  const uint64_t now = NowUs();
  Note(kWindow, frame);
  uint64_t expected = 0;
  if (g_dump_after_us.compare_exchange_strong(expected, now + 1500000)) {
    g_dump_from_us.store(now > 1500000 ? now - 1500000 : 0);
  }
}

}  // namespace sasrt::trace
