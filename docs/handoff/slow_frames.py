# sasrt-nx (2026-11-11 ~12:50, the user: "Remember i was getting large stutters even at a static resolution"; chose "Hunt
# stutters first"): the slow-frame log. A frame whose render-thread period passes a threshold is logged with what the
# render thread did in it (busy, waited on the GPU or a buffer, pipelines made on the slow path and their time, targets
# built, textures made, draws); a frame whose GPU time is far over the recent median is logged too. Logging only.
# Idempotent; asserts every anchor once.
R = 'D:/sonic transformed/sasrt-nx/app/src/renut_engine/gpu/'
MARK = 'sasrt_renut_diag_slow_frames'


def patch(path, edits, mark=MARK):
    b = open(R + path, 'rb').read()
    crlf = b'\r\n' in b
    s = b.decode('utf-8').replace('\r\n', '\n')
    if mark in s:
        print('already patched:', path)
        return
    for old, new in edits:
        assert s.count(old) == 1, (path, old[:80], s.count(old))
        s = s.replace(old, new)
    open(R + path, 'wb').write((s.replace('\n', '\r\n') if crlf else s).encode('utf-8'))
    print('patched:', path)


patch('backend/render_thread.h', [
    ('''// Shutdown: the thread finishes what is queued and ends; nothing waits for it''',
     '''// sasrt-nx (2026-11-11, sasrt_renut_diag_slow_frames): what the render thread spends a frame on, by kind, for the slow-
// frame log (render thread only; other threads are not counted).
enum class FrameCost : int { kPipeline = 0, kProvisional, kTarget, kTexture, kDraw, kCount };
void NoteFrameCost(FrameCost kind, uint64_t ns);
class CostScope {
public:
  explicit CostScope(FrameCost kind);
  ~CostScope();
  CostScope(const CostScope &) = delete;
  CostScope &operator=(const CostScope &) = delete;

private:
  std::chrono::steady_clock::time_point start_;
  FrameCost kind_;
  bool counted_;
};

// Shutdown: the thread finishes what is queued and ends; nothing waits for it'''),
])

patch('backend/render_thread.cpp', [
    ('''// Render thread only: time spent running work since the last frame ended, and
// when the running item started; of that time, how much it waited (WaitScope).
Clock::duration g_busy{};
Clock::time_point g_item_start{};
Clock::duration g_waited{};
thread_local bool t_render_thread = false;''', '''// Render thread only: time spent running work since the last frame ended, and
// when the running item started; of that time, how much it waited (WaitScope).
Clock::duration g_busy{};
Clock::time_point g_item_start{};
Clock::duration g_waited{};
thread_local bool t_render_thread = false;

// sasrt-nx (2026-11-11, the user: "large stutters even at a static resolution"; their fixed 648-line race: one frame of
// ~105-110 ms a 10 s window, all of it between the game's Swap and the present, the game thread's own worst 32-83 ms).
// The slow-frame log: a frame whose period on the render thread (its done to the next frame's done) is over the
// threshold is logged with its busy time, its waits (WaitScope: GPU fences, back buffers, the paced present), and what
// it spent on the kinds below. Logging only.
REXCVAR_DEFINE_BOOL(sasrt_renut_diag_slow_frames, true, "SASRT",
                    "Diagnostic: log each frame slower than sasrt_renut_diag_slow_frame_ms on the render thread with "
                    "what it did (busy, waited, pipelines made and their time, targets built, textures made, draws); "
                    "logging only")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_INT32(sasrt_renut_diag_slow_frame_ms, 60, "SASRT",
                     "sasrt_renut_diag_slow_frames: the render-thread frame period (ms) above which a frame is logged")
    .range(20, 1000)
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
uint64_t g_cost_ns[int(FrameCost::kCount)] = {};
uint32_t g_cost_n[int(FrameCost::kCount)] = {};
Clock::time_point g_last_frame_done{};'''),
    ('''    g_busy = -so_far;
    g_waited = {};
    frame_stats::OnRenderThreadFrame(busy_ms);''', '''    // sasrt-nx (2026-11-11, sasrt_renut_diag_slow_frames): the frame's period and costs; logged when slow.
    {
      static const bool slow_on = REXCVAR_GET(sasrt_renut_diag_slow_frames);
      static const double slow_ms = double(REXCVAR_GET(sasrt_renut_diag_slow_frame_ms));
      const Clock::time_point now = Clock::now();
      if (slow_on && g_last_frame_done != Clock::time_point{}) {
        const double period_ms = std::chrono::duration<double, std::milli>(now - g_last_frame_done).count();
        static uint32_t logged = 0;
        if (period_ms > slow_ms && logged < 300) {
          ++logged;
          auto ms = [](FrameCost k) { return double(g_cost_ns[int(k)]) / 1e6; };
          auto n = [](FrameCost k) { return g_cost_n[int(k)]; };
          RGPU_INFO("[slowframe] render frame {}: {:.1f} ms (busy {:.1f}, waited {:.1f}); pipelines made {} in {:.1f} ms "
                      "({} provisional), targets built {} in {:.1f} ms, textures made {} in {:.1f} ms, draws {}",
                      g_frames_done + 1, period_ms, busy_ms,
                      std::chrono::duration<double, std::milli>(g_waited).count(), n(FrameCost::kPipeline),
                      ms(FrameCost::kPipeline), n(FrameCost::kProvisional), n(FrameCost::kTarget), ms(FrameCost::kTarget),
                      n(FrameCost::kTexture), ms(FrameCost::kTexture), n(FrameCost::kDraw));
        }
      }
      g_last_frame_done = now;
      std::fill(std::begin(g_cost_ns), std::end(g_cost_ns), 0ull);
      std::fill(std::begin(g_cost_n), std::end(g_cost_n), 0u);
    }
    g_busy = -so_far;
    g_waited = {};
    frame_stats::OnRenderThreadFrame(busy_ms);'''),
    ('''WaitScope::WaitScope() : start_(Clock::now()), counted_(t_render_thread) {}''',
     '''WaitScope::WaitScope() : start_(Clock::now()), counted_(t_render_thread) {}

// sasrt-nx (2026-11-11, sasrt_renut_diag_slow_frames)
void NoteFrameCost(FrameCost kind, uint64_t ns) {
  if (!t_render_thread)
    return;
  g_cost_ns[int(kind)] += ns;
  ++g_cost_n[int(kind)];
}
CostScope::CostScope(FrameCost kind) : start_(Clock::now()), kind_(kind), counted_(t_render_thread) {}
CostScope::~CostScope() {
  if (counted_) {
    g_cost_ns[int(kind_)] += uint64_t(std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now() - start_).count());
    ++g_cost_n[int(kind_)];
  }
}'''),
])

patch('render/pipeline.cpp', [
    ('''#include "renut_engine/gpu/render/pipeline.h"''', '''#include "renut_engine/gpu/render/pipeline.h"
#include "renut_engine/gpu/backend/render_thread.h"  // sasrt-nx (2026-11-11): the slow-frame log'''),

    ('''  plume::RenderPipeline *result = GetPipelineSlow(key, inputs, kind, memo_epoch);''',
     '''  plume::RenderPipeline *result;
  {
    render_thread::CostScope cost(render_thread::FrameCost::kPipeline);  // sasrt-nx (2026-11-11, the slow-frame log)
    result = GetPipelineSlow(key, inputs, kind, memo_epoch);
  }
  if (kind == 1)
    render_thread::NoteFrameCost(render_thread::FrameCost::kProvisional, 0);  // sasrt_renut_diag_slow_frames'''),
], mark='the slow-frame log')

patch('render/surfaces.cpp', [
    ('''#include "renut_engine/gpu/render/surfaces.h"''', '''#include "renut_engine/gpu/render/surfaces.h"
#include "renut_engine/gpu/backend/render_thread.h"  // sasrt-nx (2026-11-11): the slow-frame log'''),

    ('''bool BuildTarget(HostSurface &surface, const d3d::SurfaceDesc &desc, uint32_t min_width,
                 uint32_t min_height, RenderScale scale) {''', '''bool BuildTarget(HostSurface &surface, const d3d::SurfaceDesc &desc, uint32_t min_width,
                 uint32_t min_height, RenderScale scale) {
  render_thread::CostScope cost(render_thread::FrameCost::kTarget);  // sasrt-nx (2026-11-11, the slow-frame log)'''),
], mark='the slow-frame log')

patch('render/textures.cpp', [
    ('''#include "renut_engine/gpu/render/textures.h"''', '''#include "renut_engine/gpu/render/textures.h"
#include "renut_engine/gpu/backend/render_thread.h"  // sasrt-nx (2026-11-11): the slow-frame log'''),

    ('''            plume::RenderFormat rt_format, bool swap_red_blue = false, RenderScale scale = {},
            bool host_levels = false) {
  ++g_texture_epoch;  // banjo-nx (CPU proposal 2)''', '''            plume::RenderFormat rt_format, bool swap_red_blue = false, RenderScale scale = {},
            bool host_levels = false) {
  render_thread::CostScope cost(render_thread::FrameCost::kTexture);  // sasrt-nx (2026-11-11, the slow-frame log)
  ++g_texture_epoch;  // banjo-nx (CPU proposal 2)'''),
], mark='the slow-frame log')

patch('backend/video.cpp', [
    ('''void Video::NoteFrameDrawLocked() {  // sasrt-nx (2026-11-11): the flash watch's count, every draw the frame is handed
  auto &s = State();
  ++s.frame_draws[s.frame];
}''', '''void Video::NoteFrameDrawLocked() {  // sasrt-nx (2026-11-11): the flash watch's count, every draw the frame is handed
  auto &s = State();
  ++s.frame_draws[s.frame];
  render_thread::NoteFrameCost(render_thread::FrameCost::kDraw, 0);  // the slow-frame log
}'''),
    # The GPU side: a frame whose GPU time is far over the recent median, logged by the flash watch's ring.
    ('''    if ((low_ms || low_draws) && logged < 500) {''', '''    // sasrt-nx (2026-11-11, the slow-frame log): a GPU frame far over the median (the stutter hunt).
    if (gpu_ms > 50.0 && gpu_ms > 1.6 * median_ms) {
      static uint32_t slow_logged = 0;
      if (slow_logged++ < 200)
        RGPU_WARN("[slowframe] GPU frame {} (guest swap {}): {:.1f} ms against a median of {:.1f}, {} draws against {}",
                  frames, swap, gpu_ms, median_ms, draws, median_draws);
    }
    if ((low_ms || low_draws) && logged < 500) {'''),
], mark='the slow-frame log')
print('slow_frames: done')
