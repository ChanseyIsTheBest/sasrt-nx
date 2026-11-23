# sasrt-nx (2026-11-12, the 12 h round, batch C; the user: large batches of 10-15). Exact items, one PGO cycle.
#  C1 RtlLeaveCriticalSection as a raw export (as Enter / TryEnter already are): no HostToGuestFunction thunk (an
#     out-of-line call translating the pointer) on the game's every leave (main 0.7 %, AK 0.4 % in the thunk).
#  C2 the slow-frame log's image-memory figures: blocks made / destroyed, retired-collect passes and deko3d textures
#     made, their time, per frame (the resolution step frames: 16 targets in ~33 ms + 17 textures in ~27 ms although the
#     target-block cache hits; this says where those ms go). Diagnostic only.
# Idempotent; asserts every anchor once.
R = 'D:/sonic transformed/sasrt-nx/'


def patch(rel, edits, mark):
    p = R + rel
    b = open(p, 'rb').read()
    crlf = b'\r\n' in b
    s = b.decode('utf-8').replace('\r\n', '\n')
    if mark in s:
        print('already patched:', rel, '(' + mark + ')')
        return
    for o, n in edits:
        assert s.count(o) == 1, (rel, o[:80], s.count(o))
        s = s.replace(o, n)
    open(p, 'wb').write((s.replace('\n', '\r\n') if crlf else s).encode('utf-8'))
    print('patched:', rel, '(' + mark + ')')


# ---- C1
patch('sdk/src/kernel/xboxkrnl/xboxkrnl_rtl.cpp', [
    ('''struct X_TIME_FIELDS {''', '''// sasrt-nx (2026-11-12, batch C1): the game's leaves through a raw export, as its enters (no thunk translating the
// pointer); the same body as RtlLeaveCriticalSection_entry.
void RtlLeaveCriticalSection_raw(PPCContext& ctx, uint8_t* base) {
  auto* cs = rex::memory::GuestPtr<X_RTL_CRITICAL_SECTION*>(base, ctx.r3.u32);
  if (--cs->recursion_count != 0) {
    rex::thread::atomic_dec(&cs->lock_count);
    return;
  }
  cs->owning_thread = 0;
  if (rex::thread::atomic_dec(&cs->lock_count) != -1) {
    xeKeSetEvent(reinterpret_cast<X_KEVENT*>(cs), 1, 0);
  }
}

struct X_TIME_FIELDS {'''),
    ('''REX_EXPORT(__imp__RtlLeaveCriticalSection, rex::kernel::xboxkrnl::RtlLeaveCriticalSection_entry)''',
     '''REX_HOOK_RAW(__imp__RtlLeaveCriticalSection) {  // sasrt-nx (2026-11-12, batch C1)
  rex::kernel::xboxkrnl::RtlLeaveCriticalSection_raw(ctx, base);
}
static rex::ppc::detail::PPCFuncRegistrar _ppc_reg___imp__RtlLeaveCriticalSection(
    "__imp__RtlLeaveCriticalSection", &__imp__RtlLeaveCriticalSection);'''),
], 'batch C1')

# ---- C2
patch('app/thirdparty/plume/plume_deko3d.h', [
    ('''    void Deko3DTargetCacheFigures(Deko3DTargetCacheInfo &out);
''', '''    void Deko3DTargetCacheFigures(Deko3DTargetCacheInfo &out);
    // sasrt-nx (2026-11-12, batch C2): what image memory costs, running totals since the start (the slow-frame log
    // takes a frame's share as the difference): blocks made and destroyed, retired-collect passes, deko3d textures made.
    struct Deko3DAllocCosts {
        uint64_t makeNs = 0, destroyNs = 0, collectNs = 0, textureNs = 0;
        uint64_t makes = 0, destroys = 0, collects = 0, textures = 0;
    };
    void Deko3DAllocCostFigures(Deko3DAllocCosts &out);
'''),
], 'batch C2')
patch('app/thirdparty/plume/plume_deko3d.cpp', [
    ('''    static std::atomic<bool> g_dedicatedTargets{true};
''', '''    static std::atomic<bool> g_dedicatedTargets{true};
    // sasrt-nx (2026-11-12, batch C2): Deko3DAllocCosts' totals (system ticks; relaxed adds, a few a frame).
    struct AllocCostCounter {
        std::atomic<uint64_t> ticks{0}, n{0};
    };
    static AllocCostCounter g_costMake, g_costDestroy, g_costCollect, g_costTexture;
    struct AllocCostScope {
        AllocCostCounter &c;
        const uint64_t start;
        explicit AllocCostScope(AllocCostCounter &counter) : c(counter), start(armGetSystemTick()) {}
        ~AllocCostScope() {
            c.ticks.fetch_add(armGetSystemTick() - start, std::memory_order_relaxed);
            c.n.fetch_add(1, std::memory_order_relaxed);
        }
    };
    void Deko3DAllocCostFigures(Deko3DAllocCosts &out) {
        auto ns = [](const AllocCostCounter &c) { return armTicksToNs(c.ticks.load(std::memory_order_relaxed)); };
        out.makeNs = ns(g_costMake);
        out.destroyNs = ns(g_costDestroy);
        out.collectNs = ns(g_costCollect);
        out.textureNs = ns(g_costTexture);
        out.makes = g_costMake.n.load(std::memory_order_relaxed);
        out.destroys = g_costDestroy.n.load(std::memory_order_relaxed);
        out.collects = g_costCollect.n.load(std::memory_order_relaxed);
        out.textures = g_costTexture.n.load(std::memory_order_relaxed);
    }
'''),
    ('''    Deko3DTexture::Deko3DTexture(Deko3DDevice *device, const RenderTextureDesc &desc) : device(device), desc(desc) {
''', '''    Deko3DTexture::Deko3DTexture(Deko3DDevice *device, const RenderTextureDesc &desc) : device(device), desc(desc) {
        AllocCostScope costScope(g_costTexture);  // sasrt-nx (2026-11-12, batch C2)
'''),
    ('''    DkMemBlock Deko3DDevice::makeBlock(uint32_t size, uint32_t flags, const char *what) {
''', '''    DkMemBlock Deko3DDevice::makeBlock(uint32_t size, uint32_t flags, const char *what) {
        AllocCostScope costScope(g_costMake);  // sasrt-nx (2026-11-12, batch C2)
'''),
    ('''    void Deko3DDevice::destroyBlock(DkMemBlock block) {
        if (!block)
            return;
''', '''    void Deko3DDevice::destroyBlock(DkMemBlock block) {
        if (!block)
            return;
        AllocCostScope costScope(g_costDestroy);  // sasrt-nx (2026-11-12, batch C2)
'''),
    ('''    void Deko3DDevice::collectRetired() {
        std::lock_guard<std::mutex> lock(retireMutex);
        if (retired.empty())
            return;
''', '''    void Deko3DDevice::collectRetired() {
        std::lock_guard<std::mutex> lock(retireMutex);
        if (retired.empty())
            return;
        AllocCostScope costScope(g_costCollect);  // sasrt-nx (2026-11-12, batch C2): a pass with something to look at
'''),
], 'batch C2')
patch('app/src/renut_engine/gpu/backend/render_thread.cpp', [
    ('''#include "renut_engine/display_sync.h"  // sa2-nx (2026-10-28): LateInputGuardUs
''', '''#include "renut_engine/display_sync.h"  // sa2-nx (2026-10-28): LateInputGuardUs
#if defined(PLUME_DEKO3D)
#include <plume_deko3d.h>  // sasrt-nx (2026-11-12, batch C2): the slow-frame log's image-memory figures
#endif
'''),
    ('''          RGPU_INFO("[slowframe]   frame {} waited on: {}", g_frames_done + 1, waits.empty() ? "nothing" : waits);
        }
      }
      g_last_frame_done = now;''', '''          RGPU_INFO("[slowframe]   frame {} waited on: {}", g_frames_done + 1, waits.empty() ? "nothing" : waits);
#if defined(PLUME_DEKO3D)
          // sasrt-nx (2026-11-12, batch C2): the frame's image memory (the difference from the last frame's totals).
          {
            plume::Deko3DAllocCosts a;
            plume::Deko3DAllocCostFigures(a);
            const plume::Deko3DAllocCosts &p = g_alloc_last;
            RGPU_INFO("[slowframe]   frame {} image memory: blocks made {} in {:.1f} ms, destroyed {} in {:.1f} ms, "
                      "retired-collect passes {} in {:.1f} ms, deko3d textures {} in {:.1f} ms",
                      g_frames_done + 1, a.makes - p.makes, double(a.makeNs - p.makeNs) / 1e6, a.destroys - p.destroys,
                      double(a.destroyNs - p.destroyNs) / 1e6, a.collects - p.collects,
                      double(a.collectNs - p.collectNs) / 1e6, a.textures - p.textures,
                      double(a.textureNs - p.textureNs) / 1e6);
          }
#endif
        }
      }
#if defined(PLUME_DEKO3D)
      if (slow_on)
        plume::Deko3DAllocCostFigures(g_alloc_last);  // sasrt-nx (2026-11-12, batch C2)
#endif
      g_last_frame_done = now;'''),
    ('''uint64_t g_cost_ns[int(FrameCost::kCount)] = {};
''', '''uint64_t g_cost_ns[int(FrameCost::kCount)] = {};
#if defined(PLUME_DEKO3D)
plume::Deko3DAllocCosts g_alloc_last;  // sasrt-nx (2026-11-12, batch C2): the totals at the last frame's end
#endif
'''),
], 'batch C2')
print('batchC: done')
