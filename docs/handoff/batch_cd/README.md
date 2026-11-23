# Batches C and D (sasrt-nx, 2026-11-12): the exact, universal items for the ultimate base

The user, 2026-11-12: "after batch C and D are confirmed send the identical stuff to rr6". Only items that change no
pixel, no result and no timing semantics are listed as base items; SASRT-only ones are listed at the end so nothing is
missed. The patch scripts next to this file (`batch_c1.py`, `batch_c2.py`, `batch_d.py`, `batch_d6.py`) hold the exact
old -> new text of every edit (sasrt-nx paths; idempotent, every anchor asserted once). Line anchors may differ in the
base: port by the text, not the line.

## Batch C: measured (console, handheld 1020 / 460.8 / 1600, Ocean View, in-place PGO+LTO build)

Run abC2 against batch B's abB (both reached the race: LAP 1 HUD at 20 s; no screenshots while driving):

| | abB | abC2 | change |
|---|---|---|---|
| fps | 27.65 | 28.08 | +1.6 % |
| GPU ms a frame | 34.31 | 33.45 | -2.5 % |
| render thread busy ms a frame | 23.49 | 22.72 | -3.3 % |
| render thread CPU (core 1) | 19.48 | 19.05 | -2.2 % |
| input -> display | 71.2 ms | 66.6 ms | |
| fast draws | 89.0 % | 90.8 % | |
| process CPU ms a frame | 82.39 | 81.93 | -0.6 % |

(abC2 had ~7 % more draws a window than abB, so the per-frame gains are if anything understated.)
Ryujinx dense guard (banjo_hot_guard 4000/64, banjo_renut_fast_draw_verify on): 1.67 M calls compared, 0 differences
in anything batch C changed; fast-draw verify 0 warnings.

### Base items from batch C (all exact)

1. **C5 - the replayed draw's surface overrides cleared lazily** (render/surfaces.cpp, key
   `sasrt_surface_override_lazy_clear`, default true). The biggest one. Every captured draw's lambda (queued.cpp) set its
   recorded surface overrides before the draw and cleared them after: two `g_surface_epoch` bumps a draw, so the next
   draw's fast path always saw the epoch moved and gathered its targets again (GatherTargets, the slow surface lookups,
   FillTextures, BindTargets: ~89 % of fast draws). Now the clear is owed: `g_override_owed`, applied (the bump and the
   count reset, as before) by `SettleOverridesSlow()` in `SurfaceEpochLocked()` and `ReplaySurfaceOverride()` (the memo
   in GetHostSurfaceLocked reads after the latter); the next Set with a list equal to the kept one, with nothing read in
   between, undoes it unseen. Any other bump while owed is kept as is. Exact: no reader can see the state between.
   Only if the base has SASRT's replay surface overrides (SetReplaySurfaceOverridesLocked, from sasrt-nx 2026-10-20).
2. **C6 - GetHostSurfaceSlow: one `g_targets` lookup** (`find` once; `try_emplace` where `operator[]` inserted) instead
   of `count()` then `operator[]`. Same map contents.
3. **C7 - the command-buffer replay prefetches the op three ahead's other read lines** (guest/command_buffers.cpp: +192,
   +384, +512, +576, +640 of the 768-byte Op: the recorded surfaces, their headers, the index buffer, the stream / vertex
   shader words; misses in the console profile). Prefetches only.
4. **C8 - the render thread's next draw item and the pool's next capture prefetch the capture's other lines**
   (render_thread.cpp PrefetchItem: +128, +256, +320, +384; queued.cpp pool Take(): +256, +320, +384 for write). Hints.
5. **C11 - SyncPendingCount stores only a changed count** (guest/command_buffers.cpp; the sole writer holds
   g_record_mutex; a reader that sees the count unchanged needs nothing the store would publish).
6. **C12 - the XMA worker's full sweep visits only allocated contexts** (sdk/src/audio/xma_decoder.cpp): the context
   bitmap's cleared bits (bit 63 - i of word w = context 64 w + i), ascending, instead of all 320 contexts (32 of the
   sweep's samples were the is_allocated load-acquire of free contexts). Every context Work() would act on is visited.
7. **C13 - RenderScale::Factor from a table kept with the ratios** (render_scale.h, deko3d only: `kFactors[]`,
   `SetRatio()` used where surfaces.cpp sets kNumerators / kDenominators). The same single float division, done when a
   ratio is set (the initial ones constant-folded the same way, round to nearest).
8. **C1 - RtlLeaveCriticalSection as a raw export** (sdk/src/kernel/xboxkrnl/xboxkrnl_rtl.cpp), as Enter / TryEnter
   already are: no HostToGuestFunction thunk on the game's every leave. The same body as the _entry function.
9. **C2 (diagnostic) - the slow-frame log's image-memory line** (plume Deko3DAllocCostFigures + render_thread.cpp):
   blocks made / destroyed, retired-collect passes and deko3d textures with their time, per slow frame. It is what found
   D6 below. Only if the base has the slow-frame log (sasrt_renut_diag_slow_frames).
10. **C3 (method, not a patch) - refresh the bulk copy list from the newest console profile.** 4.6 % of all busy samples
    were in 69 generated functions that the old list (built from an early profile) missed; the copy tool took all 69
    and the guard found nothing. Each port's list is its own.

### SASRT-only (not for the base)

- C4 (the delta prefetch limited to the marked chunks) and C9 (g_capture_next_whole read before the exchange): they need
  SASRT's capture marks (sasrt_capture_marks), which the base does not have.
- C10 (sasrt::trace::On latched): SASRT's own trace.

## Batch D: measured (same conditions; abD against abC2, both racing: LAP 1 HUD at 20 s)

| | abC2 (batch C) | abD (batch D) | change |
|---|---|---|---|
| fps | 28.08 | 28.42 | +1.2 % |
| render thread busy ms a frame | 22.72 | 22.61 | -0.5 % |
| render thread CPU (core 1) | 19.05 | 18.61 | -2.3 % |
| process CPU ms a frame | 81.93 | 80.45 | -1.8 % |
| WaterThread CPU | 6.84 | 6.41 | -6.3 % (D5) |
| GPU ms a frame | 33.45 | 33.59 | +0.4 % (noise) |

Over both batches (abB -> abD): fps 27.65 -> 28.42 (+2.8 %), render thread busy 23.49 -> 22.61 ms, process CPU 82.39 ->
80.45 ms (-2.4 %), input -> display 71.2 -> 67.8 ms. Ryujinx dense guard of batch D: 1.16 M calls compared, 0
differences in anything batch D changed (the one difference both guards show is an older copy's NaN sign, fused
multiply-add's NaN order, known); fast-draw verify 0 warnings.

1. **D1 - FindHostTextureBySlotLocked remembers its last answer** (render/textures.cpp, key `sasrt_texture_slot_memo`):
   the remembered texture is re-checked with the same fields the scan tests (`SasrtSlotOwner`), so a slot's one live
   owner is returned without walking every texture (1.7 % of the render thread, from the copy-back check).
2. **D2 - held exports reuse their buffers** (render/draw.cpp): the retired buffers only the retired list holds go to a
   pool (64 at most, up to 1 MB each) at the flush, where no fill points into them any more; HoldExport assign()s into
   a pooled one. The same bytes; no 12 KB make_shared + free per export draw.
3. **D3 - sasrt::gpu_round::On reads its latched flag relaxed**, as banjo's Latch() does (no load-acquire at the ~70
   switch sites of a fast draw). Base equivalent: any per-draw switch accessor that load-acquires a ready flag.
4. **D4 - RenderScale::Coord in integers**: round half away from zero of guest * n / d, `(2|g|n + d) / (2d)` with the
   sign, int64. Exactly what lround of the double quotient gave: checked over 675 ratios x 2,451 values (1.65 M cases,
   including random 32-bit guests), 0 differences.
5. **D6 - headroom in new render-target blocks (NOT recommended for the base yet)** (plume Deko3DSetTargetBlockHeadroom, key
   `sasrt_target_block_headroom_8ths`, default 1). abC2's image-memory lines showed a resolution step's frame (65-110 ms)
   is almost all new blocks made (up to 24 a step, ~3 ms each) when the block cache has none of the new size. A new
   dedicated block is made 1/8 bigger than its image (the tail stays free in its own chunk, which the shared search
   skips), and the cache takes blocks up to (1 + (1 + headroom) / 8) times a request. Memory only. Result unclear in
   one race: abD had 3 step frames in the race (abC2 5), the later steps no longer slow, but the race's first step took
   279 ms (abC2: 71 ms), 251 ms of it in deko3d texture creation outside block making, not explained yet. SASRT keeps
   it on for more runs; the base should wait.
6. **D5 (SASRT's hand.txt) - `reads=` on a hand-written native that copies call in a loop.** Without it the copy tool
   treats the native's function as of unknown reach and stores every register before each call (~48 in SASRT's water
   loop); with `reads=` it stores only what the native reads and syncs everything only when it declines. Method for
   any port with hand natives called from copies.
