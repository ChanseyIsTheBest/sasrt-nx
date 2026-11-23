# Base handoff, 2026-11-11 evening (sasrt-nx): the ring-cleaner take-over, and GPU rows 1, 2 and 4

## Numbers (console, handheld 1020/460.8/1600, race, PGO + LTO; opt1 against cache1s, both with stack sampling)

| | cache1s | opt1 |
|---|---|---|
| fps | 27.42 | 27.66 (+0.9 %) |
| render thread a frame | 23.74 ms | 23.46 ms |
| average 3D height (dynamic resolution) | 691 lines | 695 lines |
| render-thread waits on the ring cleaner over 50 ms | 14 (7 in cache1) | **0** |
| frames over 150 ms in the whole log | 23 | 16 |

opt1 also carries Blur's vector-lane pass (neutral on CPU here) and the rows below.

## 1. The ring cleaner take-over (tested, universal)

At the race start the render thread waited 280-350 ms (three times a race) for the upload ring's cleaner thread to finish
the range it was cleaning: the cleaner runs at 0x3B on the system core and was kept off it. The clean is a dc cvac by address
(plume Deko3DBuffer::unmap), repeatable and safe on two cores at once, so a submit that needs that range now cleans it
itself. Key `sasrt_ring_cleaner_take_over` (default true).

## 2-4. GPU rows 1, 2, 4 (exact by construction, universal, but NOT exercised in SASRT)

Census counts in the race: row 1 (no-op stencil pipelines) 0, row 2 (pipelines whose depth mark the precise rule dropped) 0,
row 4 (cull-both pipelines) 0. So SASRT never takes these paths: correct by reading, cheap, untested in practice. Take them
only if a game of the base has such states (a counter first is the safe order). Keys: `sasrt_gpu_stencil_noop`,
`sasrt_gpu_precise_stencil_write` (sets plume::g_deko3dOptions.preciseStencilWrite), `sasrt_gpu_skip_cull_both` (with
banjo_renut_cull_both on).

## Not for the base

- `sasrt_gpu_scaled_copy_deferred` (SASRT's EDRAM restore copy at scaled resolutions): no gain, now off by default.
- Row 3 (cleared-depth resolve as a fill): 0 of 1,167 depth resolves qualified; not built.

## The code

### 1. The ring cleaner take-over (TESTED) - app/src/renut_engine/gpu/backend/video.cpp

```cpp
// sasrt-nx (2026-11-11, the stutter hunt, run cache1: the race's three 280-350 ms frames were the render thread waiting for
// the cleaner's range in progress, the cleaner at 0x3B on core 3 kept off it by other work there). A clean (dc cvac, plume
// Deko3DBuffer::unmap) can be repeated and run on two cores at once: the render thread cleans that range itself instead
// of waiting for the thread to finish it.
REXCVAR_DEFINE_BOOL(sasrt_ring_cleaner_take_over, true, "SASRT/Graphics",
                    "A submit that needs the range the ring cleaner thread is cleaning cleans it itself (a cache clean "
                    "by address, repeatable) instead of waiting for the thread, which runs at the lowest priority on the "
                    "system core and was kept off it for 280-350 ms at the race start")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
// ... in RingCleaner::Wait, after the queued ranges up to the ticket are cleaned here:
      // sasrt-nx (2026-11-11, sasrt_ring_cleaner_take_over): the range in progress cleaned here too; every range up to
      // 'ticket' is then clean (the queue's were taken above; a later job of the thread has a later ticket).
      static const bool take_over = REXCVAR_GET(sasrt_ring_cleaner_take_over);
      if (take_over) {
        const UploadRing::Range r = working_range_;
        lock.unlock();
        Clean(r);
        banjo::renut_gpu::CountKickSubmit(2);
        return;
// ... in Run(), with working_ = job.ticket:   working_range_ = job.range;
// ... the member:  UploadRing::Range working_range_{};
```

### 2. Row 1, a no-op stencil built off (exact; 0 cases in SASRT) - app/src/renut_engine/gpu/render/pipeline.cpp

```cpp
// sasrt-nx (2026-11-11, the pixel-identical GPU list's row 1): a stencil test that does nothing, built with the stencil
// off; and the census's count of the pipelines that cull both faces (row 4). draw.cpp's census reports both.
REXCVAR_DEFINE_BOOL(sasrt_gpu_stencil_noop, true, "SASRT/GPU",
                    "A stencil test that passes every pixel (compare always) and cannot change the stencil plane (write "
                    "mask 0, or keep on every outcome that can happen) is built with the stencil off: the same pixels "
                    "and the same stencil, without the stencil work (the depth half of the rule is banjo-nx's)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
std::atomic<uint32_t> g_census_stencil_noop{0}, g_census_cull_both{0};
// ... after the stencil back face is set in the pipeline description:
    // sasrt-nx (2026-11-11, sasrt_gpu_stencil_noop, the GPU list's row 1): a face's test that compares always rejects no
    // pixel (its fail operation cannot happen); with a write mask of 0, or keep on the pass outcome and on the depth-fail
    // outcome where the depth test can fail, it changes no stencil value either. Both faces so: the stencil off is exact.
    static const bool noop_on = REXCVAR_GET(sasrt_gpu_stencil_noop);
    if (desc.stencilEnabled && noop_on) {
      const bool depth_can_fail =
          desc.depthEnabled && desc.depthFunction != plume::RenderComparisonFunction::ALWAYS;
      const auto noop = [&](const auto &f) {
        if (f.compareFunction != plume::RenderComparisonFunction::ALWAYS)
          return false;
        if ((desc.stencilWriteMask & 0xFF) == 0)
          return true;
        return f.passOp == plume::RenderStencilOp::KEEP &&
               (!depth_can_fail || f.depthFailOp == plume::RenderStencilOp::KEEP);
      };
      if (noop(desc.stencilFrontFace) && noop(desc.stencilBackFace)) {
        desc.stencilEnabled = false;
        g_census_stencil_noop.fetch_add(1, std::memory_order_relaxed);
      }
    }
  }
  if (desc.cullMode == plume::RenderCullMode::FRONT_AND_BACK)  // sasrt-nx (2026-11-11, the census's row 4)
    g_census_cull_both.fetch_add(1, std::memory_order_relaxed);
  desc.depthTargetFormat = key.depth_format;
```

### 3. Row 2, precise depth-write marks for stencil (exact; 0 cases in SASRT) - plume_deko3d.cpp (option in plume_deko3d.h Deko3DOptions)

```cpp
            // sasrt-nx (2026-11-11, Deko3DOptions::preciseStencilWrite): the stencil plane changes only through an outcome
            // that can happen (pass always can; fail only when the test can fail; depth-fail only when the depth test can
            // fail) whose operation is not keep, and only with write mask bits. Depth writes as before (not looked at).
            if (g_deko3dOptions.preciseStencilWrite && p->writesDepthStencil && !desc.depthWriteEnabled) {
                const bool depthCanFail = desc.depthEnabled && desc.depthFunction != RenderComparisonFunction::ALWAYS;
                const auto writes = [&](const RenderStencilFaceDesc &f) {
                    return f.passOp != RenderStencilOp::KEEP ||
                           (f.compareFunction != RenderComparisonFunction::ALWAYS && f.failOp != RenderStencilOp::KEEP) ||
                           (depthCanFail && f.depthFailOp != RenderStencilOp::KEEP);
                };
                const bool stencilWrites = desc.stencilEnabled && (desc.stencilWriteMask & 0xFF) != 0 &&
                                           (writes(desc.stencilFrontFace) || writes(desc.stencilBackFace));
                if (!stencilWrites) {
                    p->writesDepthStencil = false;
                    g_deko3dPreciseStencilSaved.fetch_add(1, std::memory_order_relaxed);
```

### 4. Row 4, triangle draws culling both faces skipped (exact; 0 cases in SASRT) - render/draw.cpp

```cpp
// sasrt-nx (2026-11-11, the pixel-identical GPU list's row 4): a triangle draw culling both faces, built as FRONT_AND_BACK
// (banjo_renut_cull_both, pipeline.cpp), rasterises nothing; left out when neither shader exports memory (an export
// draw's vertex shader still runs). Points have no facing and lines are not culled: only triangle kinds.
REXCVAR_DEFINE_BOOL(sasrt_gpu_skip_cull_both, true, "SASRT/GPU",
                    "A triangle draw that culls both faces (with banjo_renut_cull_both, which builds such draws culling "
                    "everything) and exports no memory is left out: it draws no pixel either way");
uint64_t g_census_cull_both_skipped = 0;  // the census line's count (renut_diag_gpu_census)
[[gnu::noinline]] bool SasrtCullBothLocked(const u8 *device_state, const DrawCall &call) {
  if (call.primitive != kTriangleList && call.primitive != kTriangleFan && call.primitive != kTriangleStrip &&
      call.primitive != kRectangleList && call.primitive != kQuadList)
    return false;
  const GuestDevice device(device_state);
  if (!device.valid() || (u32(device.dev().m_ControlPacket.ModeControl) & 3u) != 3u)
    return false;
  const auto exports = [](const ShaderRecord *r) {
    if (!r->entry)
      return true;
    for (const u32 m : r->entry->memExportConstants)
      if (m)
        return true;
    return false;
  };
  const ShaderRecord *vs = FindShaderLocked(device.U32(d3d::kDeviceOffsetVertexShader), RecordKind::VertexShader);
  if (!vs || exports(vs))
    return false;
  if (const u32 ps_va = device.U32(d3d::kDeviceOffsetPixelShader)) {
    const ShaderRecord *ps = FindShaderLocked(ps_va, RecordKind::PixelShader);
    if (!ps || exports(ps))
      return false;
  }
  ++g_census_cull_both_skipped;
  return true;
}
// ... first thing in DrawStateLocked:
  {  // sasrt-nx (2026-11-11, sasrt_gpu_skip_cull_both)
    static const bool cull_both = REXCVAR_GET(sasrt_gpu_skip_cull_both) && banjo::renut_gpu::CullBothOn();
    if (cull_both && SasrtCullBothLocked(device_state, call)) [[unlikely]]
      return true;
  }
```
