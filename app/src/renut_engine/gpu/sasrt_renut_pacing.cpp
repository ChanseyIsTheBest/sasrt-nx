// sa2-nx (2026-10-20): the game's frame pacing with Renut's renderer (sasrt_renderer = "renut").
//
// On the console SA2's frames are paced by the vertical blank: after each Swap the GPU waits for the flip (a flag the
// game's vblank interrupt callback clears), and the game thread blocks on its fences once it is a frame or two ahead.
// SA2's game speed follows its frame rate, so that wait is what keeps the game at its speed. Renut's renderer has no
// GPU ring and no vblank interrupt: without this the game ran as fast as the host could go (300-1,900 frames a second
// on the PC test with the window minimized).
//
// Here each Swap is released at the presentation interval the game asked for (D3DPRESENT_PARAMETERS::
// PresentationInterval, which SA2's Direct3D keeps in the device: InitializePresentationParameters copies the parameters
// to +13948, so the interval is at +14000; SynchronizeToPresentationInterval reads it there): ONE (or DEFAULT) one
// refresh of 60 Hz, TWO two, THREE three, IMMEDIATE none. A frame that is late:
//   - sasrt_vsync_relaxed on (the player's default): goes at once, and the next one is due an interval after it (the
//     native renderer's relaxed vsync: 50-59 fps instead of a fall to 30);
//   - off: waits for the next refresh of the 60 Hz grid, as fixed vsync does.
#include "renut_engine/gpu/sasrt_renut_pacing.h"

#include <algorithm>
#include <cstdlib>  // sasrt-nx (2026-11-19): std::atoi (frame_cap)
#include <atomic>
#include <chrono>
#include <string>
#include <thread>

#include "renut_engine/perf/frame_stats.h"  // sasrt-nx (2026-11-09): the pacing sleep as a game-thread wait
#if defined(_WIN32)
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#ifndef CREATE_WAITABLE_TIMER_HIGH_RESOLUTION
#define CREATE_WAITABLE_TIMER_HIGH_RESOLUTION 0x00000002
#endif
#endif

#include <rex/cvar.h>
#include <rex/logging.h>

#include "sasrt_enhancements.h"
#include "renut_engine/gpu/backend/queued.h"
#include "renut_engine/display_sync.h"  // sa2-nx (2026-10-20): banjo_display_sync
#include "renut_engine/gpu/guest/guest_memory.h"
#include "renut_engine/gpu/banjo_renut_tuning.h"  // sasrt-nx (2026-11-10): g_ab_off (A/B 202)
#if defined(PLUME_DEKO3D)
namespace plume {
// sasrt-nx (2026-11-10, sasrt_pacing_on_display): plume_deko3d_commands.cpp. The swap interval the swapchain takes with
// vsync on (2 = each image shown for at least two refreshes); 0: 1, as before. Any thread; the next present applies it.
void Deko3DSetSwapIntervalOverride(int interval);
}  // namespace plume
#endif

REXCVAR_DEFINE_BOOL(sasrt_renut_vblank_pacing, true, "SASRT",
                    "Renut's renderer (sasrt_renderer = renut): each Swap is released at the game's presentation interval "
                    "(60 Hz refreshes), as the console's vertical blank paces the game; SA2's game speed follows its "
                    "frame rate. Off: the game runs as fast as the host renders (tests only)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
// sasrt-nx (2026-11-10, the user's thread-latency list, item 5: frame pacing off SlRenderer). With fixed vsync the
// thread that calls Swap (SlRenderer) slept at the Swap's start until the frame's slot on the 60 Hz grid (~10 ms a race
// frame, run lat2), before the frame's present and its own next frame: the GPU (34.5 ms a frame, 86 % busy) had nothing
// new until the slot. With this key the display paces instead: the swapchain's swap interval is the game's presentation
// interval (2: each image shown for at least two refreshes; a late one at the next refresh after that, as the fixed
// grid did), the Swap goes on at once, and the game is held back by what holds it already: the render thread finishing
// its frame (sasrt_renut_frames_ahead 0) and the three swapchain images (the present waits for a free one).
REXCVAR_DEFINE_BOOL(sasrt_pacing_on_display, false, "SASRT",
                    "Renut on deko3d with fixed vsync (sasrt_vsync_relaxed off): the game's presentation interval is "
                    "kept by the display (the swapchain's swap interval) instead of the Swap sleeping on the game's "
                    "thread until the slot; the next frame's work reaches the GPU sooner. In-run A/B 202 (the off half "
                    "paces as before). Off: the Swap sleeps (as before)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

// sasrt-nx (2026-11-11, the user: "modify the game to fix pacing to remove latency"; pacing step P2): with fixed vsync
// the Swap sleeps until its slot (PaceSwap below), and the game read its controller right after the previous Swap's
// release: at the console's clocks of 2026-11-11 01:30 the game thread worked 11.3 ms a frame and then slept 22 ms, so
// every frame's input was ~33 ms old at its present. banjo_late_input delays a frame's first controller read by the
// least slack of the last 16 frames less 2 ms, but it counted only the wait for the render thread. With this key the
// pacing sleep is slack too: the next read moves towards the end of the sleep, which shrinks to the margin, and the
// frame reaches its slot as before with input read that much later. Same frames, same pixels; off: as before.
REXCVAR_DEFINE_BOOL(sasrt_pacing_input_slack, false, "SASRT",
                    "Input latency: the Swap's pacing sleep (fixed vsync) counts as banjo_late_input's slack, so the "
                    "next frame reads its controller later by about that sleep (the sleep shrinks to the 2 ms margin)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
// The game thread's last pacing sleep (us), for render_thread.cpp's slack (sasrt_pacing_input_slack).
std::atomic<uint64_t> g_sasrt_pace_sleep_us{0};

// sasrt-nx (2026-11-19, the user: "framerate cap so we can increase the max framerate of the game to 60 let it be
// adjustable in increments of 5"; the PC version of the game runs at 60): the game asks for presentation interval TWO
// (30 fps) in its races and menus. Above 30 the Swap is released at the cap's rate instead: 60 on the display's
// refresh (banjo_display_sync, as the game's interval is), 35-55 on this file's timer grid (not a whole number of
// refreshes: each image shows for one or two refreshes). Whether the game's speed follows the clock rather than the
// frame count: docs/ultimate-base.md (the console check of 2026-11-19). The dynamic resolution's budget follows the cap
// (surfaces.cpp: banjo_renut_dynamic_gpu_ms x 30 / cap, the same share of the frame as at 30). Live: the game menu's
// Framerate cap row (BlurSetFrameCapLive below). The key's name is the base's (its menu row and file line).
REXCVAR_DEFINE_STRING(frame_cap, "30", "SASRT",
                      "The most frames a second: 30 (the game's own pace, as on the Xbox 360) to 60 in steps of 5. "
                      "Above 30 the frames are paced at the cap instead of the game's presentation interval, and the "
                      "dynamic resolution's GPU budget is banjo_renut_dynamic_gpu_ms x 30 / cap");

namespace {
int ParseFrameCap(const std::string &text) {
  const int v = std::atoi(text.c_str());
  if (v <= 0)
    return 30;  // "Off" (the base's choice) or nothing: the game's own
  return std::clamp((v + 2) / 5 * 5, 30, 60);
}
std::atomic<int> g_frame_cap{0};  // 0: not read from the key yet
}  // namespace

int sasrt::renut::FrameCap() {
  int v = g_frame_cap.load(std::memory_order_relaxed);
  if (!v) {
    v = ParseFrameCap(std::string(REXCVAR_GET(frame_cap)));
    g_frame_cap.store(v, std::memory_order_relaxed);
  }
  return v;
}

void BlurSetFrameCapLive(int fps) {
  const int v = ParseFrameCap(std::to_string(fps));
  rex::cvar::SetFlagByName("frame_cap", std::to_string(v));
  g_frame_cap.store(v, std::memory_order_relaxed);
}

int BlurFrameCapNow() { return sasrt::renut::FrameCap(); }

// The native renderer's relaxed vsync key (src/me/me_native_system.cpp), the player's setting.
extern ::sasrt::enhancements::Enhancement g_vsync_relaxed;

namespace sasrt::renut {

namespace {

using Clock = std::chrono::steady_clock;
constexpr uint32_t kDeviceOffsetPresentationInterval = 14000;  // the device's copy of D3DPRESENT_PARAMETERS + 52
constexpr Clock::duration kRefresh = std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double>(1.0 / 60.0));

// Refreshes per frame for D3DPRESENT_INTERVAL_*: as SA2's SynchronizeToPresentationInterval (sub_82CD9540) maps them.
uint32_t RefreshesPerFrame(uint32_t interval) {
  switch (interval) {
    case 0:  // DEFAULT
    case 1:  // ONE
      return 1;
    case 2:  // TWO
      return 2;
    case 4:  // THREE
      return 3;
    default:  // IMMEDIATE (0x80000000) and anything else
      return 0;
  }
}

Clock::time_point g_grid;  // the first Swap
Clock::time_point g_due;   // when the next Swap may go (on the 60 Hz grid while the game keeps up)
bool g_started = false;

// The 10 s report (2026-10-20, for the console test): the game thread's time from one Swap's release to the next
// Swap (its frame: the game's work, its Direct3D calls, the renderer's hooks, and any wait on the render thread), and
// the pacing's sleeps. Game thread only.
struct Stats {
  Clock::time_point since{};
  Clock::time_point released{};  // the last Swap's release
  uint64_t frames = 0, late = 0;
  double work_ms = 0.0, work_max_ms = 0.0, sleep_ms = 0.0;
};
Stats g_stats;

double Ms(Clock::duration d) { return std::chrono::duration<double, std::milli>(d).count(); }

// At a Swap's release ('now' the Swap's arrival).
void NoteRelease(Clock::time_point arrived, Clock::time_point released, bool late) {
  // sasrt-nx (2026-11-09, the user via RR6: "dynamic resolution only drops when the GPU is the limit"): the time the
  // game thread slept for its presentation slot is a wait, not CPU work. frame_stats' CPU time (the frame less the
  // game thread's waits) counted it, so an early frame's pacing (~8.7 ms a frame in the handheld race) raised
  // sasrt_dynamic_cpu_aware's budget towards the whole frame time.
  if (released > arrived)
    ::renut::frame_stats::OnGameThreadWait(Ms(released - arrived));
  // P2 (sasrt_pacing_input_slack): the sleep, for late input's slack (read by QueueFrame on this thread).
  static const bool input_slack = REXCVAR_GET(sasrt_pacing_input_slack);
  g_sasrt_pace_sleep_us.store(input_slack && released > arrived
                                  ? uint64_t(std::chrono::duration_cast<std::chrono::microseconds>(released - arrived)
                                                 .count())
                                  : 0,
                              std::memory_order_relaxed);
  Stats &s = g_stats;
  if (s.released != Clock::time_point{}) {
    const double work = Ms(arrived - s.released);
    s.work_ms += work;
    s.work_max_ms = std::max(s.work_max_ms, work);
    s.sleep_ms += Ms(released - arrived);
    ++s.frames;
    s.late += late ? 1 : 0;
  }
  s.released = released;
  if (s.since == Clock::time_point{}) s.since = released;
  if (released - s.since < std::chrono::seconds(10)) return;
  if (s.frames)
    REXLOG_INFO("[renut] game thread, {:.1f} s: {} frames, {:.2f} ms a frame from Swap to Swap (most {:.2f} ms), "
                "{:.2f} ms a frame paced; {} frames late (sasrt_renut_vblank_pacing)",
                Ms(released - s.since) / 1000.0, s.frames, s.work_ms / double(s.frames), s.work_max_ms,
                s.sleep_ms / double(s.frames), s.late);
  // The game thread's other measure: what its draws keep of the device (backend/queued.cpp).
  if (const std::string deltas = ::renut::gpu::SnapshotDeltaReport(); !deltas.empty())
    REXLOG_INFO("[renut] {}", deltas);
  s = Stats{};
  s.since = s.released = released;
}

// Until 't': a high-resolution waitable timer on Windows (a plain sleep there overshoots by up to a couple of
// milliseconds, and yielding under load gives the time slice away for a whole quantum), the kernel's sleep elsewhere
// (the Switch's is precise); the last 200 us spinning.
void SleepUntil(Clock::time_point t) {
  constexpr auto kSpin = std::chrono::microseconds(200);
#if defined(_WIN32)
  static HANDLE timer = [] {
    HANDLE h = CreateWaitableTimerExW(nullptr, nullptr, CREATE_WAITABLE_TIMER_HIGH_RESOLUTION, TIMER_ALL_ACCESS);
    return h ? h : CreateWaitableTimerExW(nullptr, nullptr, 0, TIMER_ALL_ACCESS);
  }();
#endif
  for (;;) {
    const auto now = Clock::now();
    if (now >= t) return;
    const auto left = t - now;
    if (left <= kSpin) continue;
    const auto wait = left - kSpin;
#if defined(_WIN32)
    LARGE_INTEGER due;
    due.QuadPart = -LONGLONG(std::chrono::duration_cast<std::chrono::nanoseconds>(wait).count() / 100);
    if (timer && SetWaitableTimer(timer, &due, 0, nullptr, nullptr, FALSE)) {
      WaitForSingleObject(timer, INFINITE);
      continue;
    }
#endif
    std::this_thread::sleep_for(wait);
  }
}

}  // namespace

// sa2-nx (2026-10-20, banjo_display_sync): the last release taken from the display's refresh (steady_clock ns).
uint64_t g_display_previous_ns = 0;

void PaceSwap(uint32_t device_va) {
  static const bool on = REXCVAR_GET(sasrt_renut_vblank_pacing);
  if (!on || !device_va) return;
  const auto *interval_word = ::renut::gpu::GuestPtr<const be_u32>(device_va + kDeviceOffsetPresentationInterval);
  const uint32_t game_refreshes = RefreshesPerFrame(interval_word ? uint32_t(*interval_word) : 1);
  // sasrt-nx (2026-11-19, frame_cap): above 30 the cap's period in place of the game's interval. refreshes: whole
  // refreshes a frame, which the display's grid can pace (60: 1), or 0 for 35-55 (the timer grid below); paced: the
  // game asked for an interval at all (IMMEDIATE stays unpaced).
  const int cap = FrameCap();
  const bool paced = game_refreshes > 0;
  const bool capped = cap > 30 && paced;
  static int last_cap = 30;
  if (cap != last_cap) {
    last_cap = cap;
    g_started = false;  // the grid starts again from the next Swap, at the new rate
    REXLOG_INFO("[renut] frame cap {} fps (frame_cap{})", cap,
                cap > 30 ? (60 % cap == 0 ? ": paced on the display's refresh" : ": paced by the timer")
                         : ": the game's own presentation interval");
  }
  const uint32_t refreshes = capped ? (60 % cap == 0 ? uint32_t(60 / cap) : 0u) : game_refreshes;
  const Clock::duration period =
      capped ? std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double>(1.0 / double(cap)))
             : kRefresh * refreshes;
  const auto now = Clock::now();
  // sasrt-nx (2026-11-10, the thread-latency round): in-run A/B 203 switches relaxed vsync off in its off half (with
  // sasrt_vsync_relaxed on), so one race compares relaxed and fixed vsync.
  const bool relaxed = g_vsync_relaxed.active && ::banjo::renut_gpu::g_ab_off.load(std::memory_order_relaxed) != 203;
  // sasrt-nx (2026-11-10, sasrt_pacing_on_display): the display keeps the interval; no sleep here.
#if defined(PLUME_DEKO3D)
  static const bool display_key = REXCVAR_GET(sasrt_pacing_on_display);
  if (display_key) {
    const bool display = !relaxed && refreshes > 0 &&
                         ::banjo::renut_gpu::g_ab_off.load(std::memory_order_relaxed) != 202;
    static int applied = -1;
    const int want = display ? int(refreshes) : 0;
    if (want != applied) {
      plume::Deko3DSetSwapIntervalOverride(want);
      REXLOG_INFO("[renut] sasrt_pacing_on_display: {} (presentation interval: {} refreshes)",
                  display ? "the display paces the frames" : "the Swap paces the frames", refreshes);
      applied = want;
      g_started = false;  // the Swap's grid starts again from the next Swap
    }
    if (display) {
      NoteRelease(now, now, false);
      return;
    }
  }
#endif
  // sa2-nx (2026-10-20, banjo_display_sync, Banjo's latency set): on the Switch the release follows the display's own
  // refresh (its vsync event) plus a measured phase, as late as the frame's image still makes the refresh, instead of
  // this clock's 60 Hz grid, which drifts against the display's. A late frame goes at once (as relaxed vsync); fixed
  // vsync (sasrt_vsync_relaxed off) and an unknown refresh (the PC, the first frames) keep the grid below.
  ::banjo::display_sync::Start();
  if (g_started && refreshes && relaxed) {
    const uint64_t now_ns = uint64_t(std::chrono::duration_cast<std::chrono::nanoseconds>(now.time_since_epoch()).count());
    const uint64_t period_ns = uint64_t(std::chrono::duration_cast<std::chrono::nanoseconds>(period).count());
    bool anchored = false;
    const uint64_t release = ::banjo::display_sync::NextRelease(now_ns, g_display_previous_ns, period_ns, &anchored);
    if (release) {
      const auto at = Clock::time_point(std::chrono::duration_cast<Clock::duration>(std::chrono::nanoseconds(release)));
      if (release > now_ns) SleepUntil(at);
      g_display_previous_ns = release;
      g_due = at + period;  // the grid follows, for when the refresh is not known for a while
      ::banjo::display_sync::NoteRelease(release, anchored);
      NoteRelease(now, Clock::now(), !anchored);
      return;
    }
  }
  if (!g_started || !paced) {
    g_started = true;
    g_grid = now;
    g_due = now + (paced ? period : kRefresh);
    NoteRelease(now, now, false);
    return;
  }
  // (period: the game's interval in refreshes, or the cap's; sasrt-nx 2026-11-19)
  if (now <= g_due) {
    // On time: released at the due refresh; the next is due a period after it (a fixed grid, so the sleep's own
    // lateness does not add up).
    SleepUntil(g_due);
    g_due += period;
    NoteRelease(now, Clock::now(), false);
    return;
  }
  if (relaxed) {
    // Late: at once. A little late (under half a refresh: the host's scheduling), the grid is kept; more, the next
    // frame is due a period after this one.
    g_due = now - g_due < kRefresh / 2 ? g_due + period : now + period;
    NoteRelease(now, now, true);
    return;
  }
  // Late, fixed vsync: the next refresh of the grid (g_due lies on it).
  const auto refreshes_late = (now - g_due + kRefresh - Clock::duration(1)) / kRefresh;
  const auto release = g_due + kRefresh * refreshes_late;
  SleepUntil(release);
  g_due = release + period;
  NoteRelease(now, Clock::now(), true);
}

}  // namespace sasrt::renut
