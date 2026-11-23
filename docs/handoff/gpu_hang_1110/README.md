# The GPU hang: a depth-words copy past a texture's end (SASRT, 2026-11-10)

For RR6 (rr6-nx and the ultimate base, `D:\renut-ultimate\base`) and Viva Piñata (`vivapinata-nx`). All three trees
have the same code as SASRT had before this fix (checked 2026-11-10 13:30): the bind check in
`app/src/renut_engine/gpu/render/textures.cpp` (`if (slot && !slot->gpu_written && slot->scale != scale)`),
`CopyDepthWords`'s box (`plume::RenderBox box(0, 0, int32_t(t.scale.Size(t.width)), ...)`), plume's deko3d image copy
(`const DkImageRect drect = {dstX, dstY, ...}` in `Deko3DCommandList::copyTextureRegion`), and the settable scale codes
(`render_scale.h`: `static inline uint32_t kNumerators[kCount] = {1, 2, 3, 2, 9, 4, 5, 4};`).

## Symptom

The console locks up (screen frozen, captures empty, sys-botbase and HOME dead) and the log shows `[deko3d] a fence
has not signalled after 2 s` and on; no deko3d error, no crash report. SASRT had six: docked (mem14, mem15, hang_D) and
handheld (hh_noevt, diagY, fixY1). Any game with dynamic resolution (`banjo_renut_dynamic_resolution`) that samples a
depth resolve's words can hit it.

## Cause

1. Codes 4 and 6 of `RenderScale` are the dynamic resolution's settable codes: their ratio (`kNumerators` /
   `kDenominators`) is rewritten at each step (code 4 = 666/720, then 702/720 ...). `RenderScale::operator==` compares
   the code only.
2. A texture over a depth resolve (the bind path in `textures.cpp`, `depth_source` set) is made at its source's scale.
   At a step that keeps the code (666 -> 702 lines, both code 4) `slot->scale != scale` is false: the texture keeps its
   image of the old height. (`ResolveTarget` already makes a resolve destination again when `alloc_width !=
   scale.Size(width)`; the textures sampling it had no such check.)
3. `WordsViewSlot` then refuses (the sizes differ) and the bind falls back to `CopyDepthWords`, whose box is
   `t.scale.Size(t.width) x t.scale.Size(t.height)` with the code's NEW ratio: larger than the texture's image.
4. plume's `copyTextureRegion` passes the box to `dkCmdBufCopyImage` unchecked: an out-of-bounds GPU write past the
   image. Usually it lands on slack or another texture (a few wrong pixels for a frame); since the memory batch
   (best-fit GPU region and image heap, dedicated target chunks, retirement) packs memory tightly it can land on live
   data (command memory, descriptors) and the GPU locks up.

SASRT's own symptoms on top (SASRT-only code, not in the base): the game's EDRAM restore copy was not recognised in
those frames, so its depth alias failed and the fallback restore drew; those were symptoms (skipping the fallback did
not stop the hang).

## Evidence (SASRT, handheld 1020/460/1600, Ocean View)

- Reproducer: `banjo_renut_dynamic_test_s = 3` (a step every 3 s) + `sasrt_texture_long_idle_frames = 1800`: hung in
  ~2.5 min twice (diagY, fixY1). The log of the hung run: in the frames before the hang "the game's restore copy not
  recorded: no texture owns the fetch's words view", and the 10 s counter "N with the copy" (CopyDepthWords) went
  from 0 to 30 in the one window of such frames that got printed.
- With the fix (runs fix2Y1, fix2Y2, fix2Y3: the same settings, 81 resolution steps and ~30 texture releases each):
  no hang, 0 copies, 0 misses; the fix fired 2-3 times a race, e.g. "texture 0605DCCE over a depth resolve made
  again: 1008x476 host, its scale's size now 1123x530" (the copy would have written 1123x530 into 1008x476).

## The fix (three parts, and a fourth safety clamp; pixel-identical whenever the sizes agree)

### 1. textures.cpp, the bind: make the texture again when its image is of another height of its code

Right after the existing block

```cpp
  const RenderScale scale = depth_source ? depth_source->scale : RenderScale{};
  if (slot && !slot->gpu_written && slot->scale != scale) {
    Retire(*slot);
    slot.reset();
  }
```

add

```cpp
  // (2026-11-10, sasrt-nx: the GPU hang) the same code at another height: codes 4 and 6 change their ratio at each
  // dynamic-resolution step and RenderScale compares the code only.
  static const bool size_check = REXCVAR_GET(sasrt_texture_scale_size_check);
  if (size_check && slot && !slot->gpu_written && slot->texture && depth_source && scale.code != 0 &&
      plume::RenderFormatBlockWidth(slot->host_format) <= 1 &&
      (slot->alloc_width != scale.Size(slot->width) || slot->alloc_height != scale.Size(slot->height))) {
    static uint64_t remade = 0;
    if (const uint64_t n = ++remade; n <= 8 || (n & (n - 1)) == 0)
      RGPU_INFO("[sasrt] texture {:08X} over a depth resolve made again: {}x{} host, its scale's size now {}x{} "
                "(the code's height changed; sasrt_texture_scale_size_check; {} so far)", texture_va, slot->alloc_width,
                slot->alloc_height, scale.Size(slot->width), scale.Size(slot->height), n);
    Retire(*slot);
    slot.reset();
  }
```

and the key near the other texture keys (rename the prefix to your port's):

```cpp
REXCVAR_DEFINE_BOOL(sasrt_texture_scale_size_check, true, "SASRT/Graphics",
                    "A texture over a depth resolve whose image is of another height of its dynamic-resolution code "
                    "(codes 4 and 6 change their ratio at each step) is made again at its bind; before, its depth words "
                    "were copied into it past its end (the GPU hangs of 2026-11-09/10). false = as before (tests only)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
```

### 2. textures.cpp, CopyDepthWords: never past either image

Replace `const plume::RenderBox box(0, 0, int32_t(t.scale.Size(t.width)), int32_t(t.scale.Size(t.height)));` with

```cpp
  const uint32_t copy_w = std::min({t.scale.Size(t.width), t.alloc_width, source.words->alloc_width});
  const uint32_t copy_h = std::min({t.scale.Size(t.height), t.alloc_height, source.words->alloc_height});
  if (copy_w != t.scale.Size(t.width) || copy_h != t.scale.Size(t.height)) {
    static uint32_t logged = 0;
    if (logged++ < 16)
      RGPU_WARN("[sasrt] depth words copy into {:08X} clamped to {}x{} (its image {}x{}, the words {}x{}, the scale's "
                "size {}x{})", t.guest_va, copy_w, copy_h, t.alloc_width, t.alloc_height, source.words->alloc_width,
                source.words->alloc_height, t.scale.Size(t.width), t.scale.Size(t.height));
  }
  const plume::RenderBox box(0, 0, int32_t(copy_w), int32_t(copy_h));
```

### 3. plume_deko3d_commands.cpp, copyTextureRegion's image-to-image branch: clamp to both images

Replace `const DkImageRect drect = {dstX, dstY, dt->type == DkImageType_3D ? dstZ : 0, srect.width, srect.height, srect.depth};` with

```cpp
            DkImageRect drect = {dstX, dstY, dt->type == DkImageType_3D ? dstZ : 0, srect.width, srect.height, srect.depth};
            {  // (2026-11-10, sasrt-nx: the GPU hang) never past either image (dkCmdBufCopyImage does not check)
                const uint32_t sw = mipDim(st->desc.width, srcLoc.subresource.mipLevel);
                const uint32_t sh = mipDim(st->desc.height, srcLoc.subresource.mipLevel);
                const uint32_t dw = mipDim(dt->desc.width, dstLoc.subresource.mipLevel);
                const uint32_t dh = mipDim(dt->desc.height, dstLoc.subresource.mipLevel);
                if (srect.x >= sw || srect.y >= sh || drect.x >= dw || drect.y >= dh) {
                    static std::atomic<uint32_t> logged{0};
                    if (logged.fetch_add(1) < 16)
                        logf("image copy refused: source %ux%u at (%u, %u), destination %ux%u at (%u, %u)", sw, sh, srect.x,
                             srect.y, dw, dh, drect.x, drect.y);
                    return;
                }
                const uint32_t w = std::min({srect.width, sw - srect.x, dw - drect.x});
                const uint32_t h = std::min({srect.height, sh - srect.y, dh - drect.y});
                if (w != srect.width || h != srect.height) {
                    static std::atomic<uint32_t> logged{0};
                    if (logged.fetch_add(1) < 16)
                        logf("image copy clamped: %ux%u to %ux%u (source %ux%u at (%u, %u), destination %ux%u at (%u, %u))",
                             srect.width, srect.height, w, h, sw, sh, srect.x, srect.y, dw, dh, drect.x, drect.y);
                    srect.width = drect.width = w;
                    srect.height = drect.height = h;
                }
            }
```

(`srect` must not be `const` there; in SASRT's tree it already was a plain `DkImageRect srect;`.)

### 4. plume_deko3d_commands.cpp, resolveTextureRegion's region blit: the same clamp (added 2026-11-10 afternoon)

The user asked for the same safety clamp on the multisample region resolve (`dkCmdBufBlitImage`, which does not check
either). In `Deko3DCommandList::resolveTextureRegion` replace the two lines

```cpp
        const DkImageRect srect = {uint32_t(r.left), uint32_t(r.top), 0, uint32_t(r.right - r.left), uint32_t(r.bottom - r.top), 1};
        const DkImageRect drect = {dstX, dstY, 0, srect.width, srect.height, 1};
```

(base ~1833, rr6-nx ~1952, vivapinata-nx ~1878, just above `dkCmdBufBlitImage(cmd, &sv, &srect, &dv, &drect, ...)`) with

```cpp
        // (2026-11-10, sasrt-nx) the region never past either image (dkCmdBufBlitImage does not check). Without scaling
        // here (the same width and height both sides), so both rectangles shrink alike.
        if (r.left < 0 || r.top < 0 || r.right <= r.left || r.bottom <= r.top || uint32_t(r.left) >= st->desc.width ||
            uint32_t(r.top) >= st->desc.height || dstX >= dt->desc.width || dstY >= dt->desc.height) {
            static std::atomic<uint32_t> logged{0};
            if (logged.fetch_add(1) < 16)
                logf("resolve blit refused: source rect (%d, %d)-(%d, %d) of %ux%u, destination %ux%u at (%u, %u)", r.left, r.top,
                     r.right, r.bottom, st->desc.width, st->desc.height, dt->desc.width, dt->desc.height, dstX, dstY);
            return;
        }
        DkImageRect srect = {uint32_t(r.left), uint32_t(r.top), 0, uint32_t(r.right - r.left), uint32_t(r.bottom - r.top), 1};
        {
            const uint32_t w = std::min({srect.width, st->desc.width - srect.x, dt->desc.width - dstX});
            const uint32_t h = std::min({srect.height, st->desc.height - srect.y, dt->desc.height - dstY});
            if (w != srect.width || h != srect.height) {
                static std::atomic<uint32_t> logged{0};
                if (logged.fetch_add(1) < 16)
                    logf("resolve blit clamped: %ux%u to %ux%u (source %ux%u at (%u, %u), destination %ux%u at (%u, %u))", srect.width,
                         srect.height, w, h, st->desc.width, st->desc.height, srect.x, srect.y, dt->desc.width, dt->desc.height,
                         dstX, dstY);
                srect.width = w;
                srect.height = h;
            }
        }
        const DkImageRect drect = {dstX, dstY, 0, srect.width, srect.height, 1};
```

## Worth checking in your tree (not part of the tested fix)

- Other textures kept across a dynamic-resolution step by `scale == scale` alone (anything made at code 4 or 6 and
  sized with `scale.Size(...)` later): the same mismatch could size another copy or view wrongly. The "image copy
  clamped" log line (part 3) reports any copy that would have gone past an image.
- A long-idle texture release like SASRT's M35 (`sasrt_texture_long_idle_frames`, off) made the copy path more
  frequent; the cause is the size mismatch, not the release.

Full write-up: `docs/render-thread-round-1109.md` ("The GPU hang ...").
