# sasrt-nx (2026-11-11 ~15:00, the stutter hunt): the slow-frame log's "waited" split by what the render thread waited
# on (slow1: the race's stalls of 117-335 ms were nearly all "waited", and no GPU frame was slow then). Each WaitScope
# site names its kind; a slow frame's line lists the kinds it waited on with their time, count and longest wait.
# Logging only. Idempotent; asserts every anchor once.
R = 'D:/sonic transformed/sasrt-nx/app/src/renut_engine/gpu/'
MARK = 'enum class WaitKind'


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
    ('''class WaitScope {
public:
  WaitScope();
  ~WaitScope();
  WaitScope(const WaitScope &) = delete;
  WaitScope &operator=(const WaitScope &) = delete;

private:
  std::chrono::steady_clock::time_point start_;
  bool counted_;
};''', '''// sasrt-nx (2026-11-11, the slow-frame log): what a wait was on, for the slow-frame log's split of "waited".
enum class WaitKind : int {
  kOther = 0,
  kAcquire,     // the swap chain's next image (a back buffer)
  kPresent,     // the present, held to the display's refresh
  kSlotFence,   // a frame slot's fence (the GPU finishing an older frame)
  kFlushFence,  // a mid-frame submit waited on at once (a readback, a full flush)
  kKickFence,   // the latency trim's wait on the last kick
  kCleaner,     // the upload ring's cleaner
  kDrain,       // the deferred recording's drain
  kCount
};
class WaitScope {
public:
  explicit WaitScope(WaitKind kind = WaitKind::kOther);
  ~WaitScope();
  WaitScope(const WaitScope &) = delete;
  WaitScope &operator=(const WaitScope &) = delete;

private:
  std::chrono::steady_clock::time_point start_;
  bool counted_;
  WaitKind kind_;
};'''),
], mark=MARK)

patch('backend/render_thread.cpp', [
    ('''uint64_t g_cost_ns[int(FrameCost::kCount)] = {};
uint32_t g_cost_n[int(FrameCost::kCount)] = {};''', '''uint64_t g_cost_ns[int(FrameCost::kCount)] = {};
uint32_t g_cost_n[int(FrameCost::kCount)] = {};
// sasrt-nx (2026-11-11, the slow-frame log): the frame's waits by kind (WaitKind): time, count, the longest.
uint64_t g_wait_ns[int(WaitKind::kCount)] = {};
uint32_t g_wait_n[int(WaitKind::kCount)] = {};
uint64_t g_wait_max_ns[int(WaitKind::kCount)] = {};'''),
    ('''                      n(FrameCost::kTexture), ms(FrameCost::kTexture), n(FrameCost::kDraw));
        }''', '''                      n(FrameCost::kTexture), ms(FrameCost::kTexture), n(FrameCost::kDraw));
          // The waits by kind (WaitKind), the ones the frame had: total ms, count, longest ms.
          static const char *const kWaitNames[int(WaitKind::kCount)] = {
              "other", "back buffer", "present", "slot fence", "flush fence", "kick fence", "cleaner", "drain"};
          std::string waits;
          for (int k = 0; k < int(WaitKind::kCount); ++k) {
            if (!g_wait_n[k])
              continue;
            waits += fmt::format("{}{} {:.1f} ms x{} (longest {:.1f})", waits.empty() ? "" : ", ", kWaitNames[k],
                                 double(g_wait_ns[k]) / 1e6, g_wait_n[k], double(g_wait_max_ns[k]) / 1e6);
          }
          RGPU_INFO("[slowframe]   frame {} waited on: {}", g_frames_done + 1, waits.empty() ? "nothing" : waits);
        }'''),
    ('''      std::fill(std::begin(g_cost_n), std::end(g_cost_n), 0u);''', '''      std::fill(std::begin(g_cost_n), std::end(g_cost_n), 0u);
      std::fill(std::begin(g_wait_ns), std::end(g_wait_ns), 0ull);
      std::fill(std::begin(g_wait_n), std::end(g_wait_n), 0u);
      std::fill(std::begin(g_wait_max_ns), std::end(g_wait_max_ns), 0ull);'''),
    ('''WaitScope::WaitScope() : start_(Clock::now()), counted_(t_render_thread) {}''',
     '''WaitScope::WaitScope(WaitKind kind) : start_(Clock::now()), counted_(t_render_thread), kind_(kind) {}'''),
    ('''WaitScope::~WaitScope() {
  if (counted_)
    g_waited += Clock::now() - start_;
}''', '''WaitScope::~WaitScope() {
  if (counted_) {
    const Clock::duration d = Clock::now() - start_;
    g_waited += d;
    // sasrt-nx (2026-11-11, the slow-frame log): by kind
    const uint64_t ns = uint64_t(std::chrono::duration_cast<std::chrono::nanoseconds>(d).count());
    const int k = int(kind_);
    g_wait_ns[k] += ns;
    ++g_wait_n[k];
    if (ns > g_wait_max_ns[k])
      g_wait_max_ns[k] = ns;
  }
}'''),
], mark='g_wait_max_ns')

patch('backend/present.cpp', [
    ('''    render_thread::WaitScope wait;
    return s.swap_chain->acquireTexture(acquire, &image_index);''',
     '''    render_thread::WaitScope wait(render_thread::WaitKind::kAcquire);  // sasrt-nx (2026-11-11, the slow-frame log)
    return s.swap_chain->acquireTexture(acquire, &image_index);'''),
    ('''    render_thread::WaitScope wait;
    presented = s.swap_chain->present(image_index, waits, 1);''',
     '''    render_thread::WaitScope wait(render_thread::WaitKind::kPresent);  // sasrt-nx (2026-11-11, the slow-frame log)
    presented = s.swap_chain->present(image_index, waits, 1);'''),
], mark='WaitKind::kAcquire')

patch('backend/video.cpp', [
    ('''      render_thread::WaitScope wait;
      done_cv_.wait(lock, [&] { return working_ == 0 || working_ > ticket; });''',
     '''      render_thread::WaitScope wait(render_thread::WaitKind::kCleaner);  // sasrt-nx (2026-11-11, the slow-frame log)
      done_cv_.wait(lock, [&] { return working_ == 0 || working_ > ticket; });'''),
    ('''    render_thread::WaitScope wait;
    plume::Deko3DFenceCopyWait(t.last_kick[prev], s.device.get());''',
     '''    render_thread::WaitScope wait(render_thread::WaitKind::kKickFence);  // sasrt-nx (2026-11-11, the slow-frame log)
    plume::Deko3DFenceCopyWait(t.last_kick[prev], s.device.get());'''),
    ('''    render_thread::WaitScope wait;
    s.queue->waitForCommandFence(s.fences[slot].get());''',
     '''    render_thread::WaitScope wait(render_thread::WaitKind::kSlotFence);  // sasrt-nx (2026-11-11, the slow-frame log)
    s.queue->waitForCommandFence(s.fences[slot].get());'''),
    ('''    render_thread::WaitScope wait;
    s.queue->waitForCommandFence(s.fences[cur].get());''',
     '''    render_thread::WaitScope wait(render_thread::WaitKind::kFlushFence);  // sasrt-nx (2026-11-11, the slow-frame log)
    s.queue->waitForCommandFence(s.fences[cur].get());'''),
], mark='WaitKind::kCleaner')

patch('banjo_renut_record.cpp', [
    ('''        ::renut::gpu::render_thread::WaitScope wait;''',
     '''        ::renut::gpu::render_thread::WaitScope wait(::renut::gpu::render_thread::WaitKind::kDrain);  // sasrt-nx'''),
], mark='WaitKind::kDrain')
print('slow_waits: done')
