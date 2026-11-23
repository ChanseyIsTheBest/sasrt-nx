# GPU optimisation candidates for the native renderer (Sonic & All-Stars Racing Transformed)

The renderer is sa2-nx's (masseffect-nx's PM4-ring Vulkan renderer as adapted by banjo-nx and sa2-nx), so every GPU
optimisation of those ports is already in (`docs/enhancements.md`, "The renderer's GPU work"; sa2-nx's
`docs/gpu-optimisation-candidates.md`). This file is what this game's frame needs on top of them. Every change must
keep the image identical; the speed is decided on the console (Tegra X1, 25.6 GB/s shared with the CPU): on this PC
the GPU is shared with other projects, so PC timings are only a rough guide.

## What a race frame costs (PC evidence, 2026-10-06)

`out/pc/logs/sasrt_072.log` (before the changes below), race at ~180 s, per 10 s (300 frames):

- GPU per Swap categories (the report multiplies the timestamps by 1.627, NVK's scale on the Switch, also on PC):
  the 1152x544 passes ("640") 17.7-20.8 ms, resolves ("copies") 6.4-7.2, EDRAM depth imports 4.5-6.0, color alias
  conversions 3.5-3.8, 9-pass imports (depth with stencil) 1.8-2.0, depth exports 1.3-1.4.
- EDRAM mode 4 transfers: 3,068,584 tiles (10,229 a frame, ~52 MB a frame read and written); 46,567 depth imports,
  17,738 color alias and 7,217 depth export operations.
- By cause: depth representation switches (1x <-> 4x of the same depth tiles) 1,173,912 tiles; color->depth 722,100;
  color->color 604,243; depth->color 468,917; depth->depth 130,620.

The EDRAM emulation (transfers, conversions, resolves) is about half of the GPU work of a race frame on PC, more than
the game's own drawing outside the G-buffer.

## Done

### 1. Direct3D's null-shader draws skipped (`sasrt_native_skip_null_draws`, non-CPU group)

Direct3D issues a one-point draw with its null vertex shader (15 microcode words, fingerprint `AFCC8377CE2A398F`:
`ps = FLT_MAX; ps = sqrt(-|ps|); oPos = ps`, a NaN position) through the 4x alias of the depth target (RB_SURFACE_INFO
`08020208`: pitch 520, MSAA 4x), once per memory-export draw: in a race the counts are equal (15,904 null draws and
15,904 export streams at the same moment, `sasrt_086.log`). No primitive with a NaN position is rasterized, and the
shader exports nothing, so the draw cannot change a pixel or a byte of memory. But each one made the renderer give
the shadow map's EDRAM tiles to the 4x image and back: two imports of the whole 1024x1024 map, 832 tiles each
(EDRAM tile trace of tile 100, frame 4460 of `sasrt_084.1.log`: `import-attempt ... count=832` before and after every
`vs=6` draw).

The draw is now dropped before the EDRAM synchronisation (`ContextTargets::Draw` asks `DrawsVulkan::SkipsNullDraw`).

| Race, per 10 s | before (`sasrt_072.log`) | after (`sasrt_086.log`) |
|---|---|---|
| EDRAM tiles transferred | 3,068,584 | 2,122,500 |
| depth representation switches | 20,766 ops, 1,173,912 tiles | 19,200 ops, 230,400 tiles |
| GPU: EDRAM depth imports, per Swap | 4.5-6.0 ms | 3.9-4.2 ms |
| GPU: 9-pass imports, per Swap | 1.8-2.0 ms | 1.6-1.9 ms |
| Swaps | 299-301 | 300-301 |

Image: the same race stretch, same frames (`video_150s` sheets).

### 2. The shadow map's first clear redirected too (`sasrt_native_edram4_grid_alias`, non-CPU group)

The shadow pass clears its depth through Direct3D's 4x alias, and sa2-nx's redirect clears the 1x view instead. Tiles
owned by a color image (last frame's 1280x720 or HDR target at the same EDRAM base) can only be handed to the 4x
view's known 1x alias: a depth-only clear (stencil kept) cannot be written into a color image. That alias is learned
when the 1x view imports from the 4x view, but only from a 4x view with horizontal samples (msaa x 1). This game's 4x
draws use the raster-grid view of the same surface (`1040x720 msaa 0,1 gridX 1`), so the alias was never learned:
the first clear of each frame was declined (`target C000/f0:1280x1280 samples1 (clear of 000/f1 mx1my1 depth 0
stencil -1)`), drawn into the 4x image and imported back to 1x by the shadow draws (`D000/f1:1040x720:mx0my1 ->
D000/f1:1040x1040` 19,200 ops / 230,400 tiles per 10 s).

Now the raster-grid 4x view teaches the alias too, and a clear planned on the plain 4x view uses its raster-grid
sibling's alias (same EDRAM base, tile pitch and depth encoding).

| Race, per 10 s (last four reports) | before (`sasrt_086.log`) | after (`sasrt_090.log`) |
|---|---|---|
| EDRAM tiles transferred | 2.12 M | 1.88-1.89 M |
| depth import operations | 44,700 | 25,300-25,600 |
| redirected depth clears | 2,100 | 2,700 |
| GPU: EDRAM depth imports, per Swap | 3.9-4.2 ms | 3.2-3.4 ms |
| Swaps | 300-301 | 298-301 |

Image: the same race stretch, shadows included (`video_150s` sheets). Still declined, once a frame each: the
320-pitch target's color + depth aliased clear (`also writes color (color 0 not redirectable)`) and one clear with a
partial edge tile owned by a view the partial path does not take.

## Candidates

### 3. Full-screen triangle grids (510 tiles a frame)

The tonemap pass into the 1280x720 target is a 48-vertex triangle list (VS n199 / PS n105, opaque, full mask). The
overwrite proof covers rectangle lists only, so the 1200-pitch image's 510 tiles are imported first
(`d4319 import ... count=510`). Proving that the 16 triangles form rectangles covering the target would skip it. The
pieces exist: the extent estimator already proves a 6-index triangle-list quad (`masseffect_native_edram4_quad_triangles`),
and `ProveRectangleList` (me_native_system.cpp) proves several rectangles one by one through the index offset; a branch
for triangle lists of 2-8 quads (count a multiple of 6, at most 48) stepping the offset by 6 would cover these draws.
The composite pass into the 1200-pitch target (VS n226, also 48 vertices) is the same case.

### 4. One barrier per memory export

`memexport, cumulative: ... 110,580 barriers for 110,693 streams`: the shadow pass is split once per character (the
export is read by the next draw). Hoisting the exports ahead of the pass would leave one barrier.

### 4b. From banjo-nx (2026-10-13/14)

**Ported on 2026-10-14** (docs/enhancements.md, "banjo-nx's EDRAM traffic items"): the triangle and leftover
tessellation proofs, the depth-only proof, split EDRAM tiles and rect split. Measured there: depth imports -17.5 %
and colour aliases -5 % in a race, the PC's EDRAM GPU time unchanged; rect split never fires in this game, and the
Clear operation was not ported (this game's surfaces are whole tiles). This game's EDRAM traffic is whole surfaces
read in another format (1.89 million tiles every 10 s), which none of these items address. The text below is as
written before the port.

- **A full-screen triangle and a leftover tessellation register in the overwrite proof** (`banjo_gpu_proof_triangle`,
  `banjo_gpu_proof_tess_leftover`; banjo-nx `app/src/me/me_native_draw_extent_estimator.h`). The estimator here has
  the same rule (it refuses every draw while `VGT_OUTPUT_PATH_CNTL` selects the tessellator, though the reference
  only tessellates in the explicit major mode). Whether this game leaves that register set is not measured. Banjo's
  tile traffic fell by 78 % with the two. Candidate 3 above is the many-triangle form of the same proof.
- **Memexport draws that rasterize for nothing** (`banjo_gpu_dead_raster`, banjo-nx-r `me_native_system.cpp`, not
  merged there yet): point-list draws with a memexport vertex shader and depth and color writes left on imported
  832 tiles a frame in Banjo; with color mask 0 and depth off the export still runs and no tile is needed. A cousin
  of `sasrt_native_skip_null_draws`. To check here: do this game's memexport draws (the character morphing) have a
  real pixel shader and target writes on?
- **Not worth trying:** dynamic state against the driver's per-pipeline state copy. masseffect-nx measured
  `masseffect_native_dynamic_state` on the console as a net loss (each bind 2.95 -> 4.36 us for 13 % fewer binds).
- **Deferred recording** stays off: slower on this PC, and futari-nx found it not pixel-identical.
- **Direct3D Clear's remainder** (`banjo_gpu_rect_split`, banjo-nx `me_native_system.cpp`, about 20 lines at the
  top of `Draw()`): a Clear of an area that does not end on tile boundaries draws an L of two rectangles as one
  rectangle list, and its EDRAM area was the box around both (42 tiles pulled for 16 touched in Banjo). Drawn as one
  draw per rectangle. This game uses the same Clear; its log has `depth clear redirect declined by: [partial tile:
  owner unsupported: 300]` per 10 s, which may be the same draws.
- **How banjo-nx's dead-raster rule decides** (for the memexport bullet above): a site is the hash of the shaders,
  surface, color and depth info, depth control and mask; after 4 uses in a row that the next draw overwrote whole it
  runs with color mask 0 and depth off; every use is still checked against the next draw's overwrite proof.
- **Two cautions from banjo-nx's console runs:** the PC's split of GPU time between passes was nothing like the
  console's (so the PC "GPU per Swap" categories here rank nothing), and localized copies of hot functions gave it
  about 1 % of game-thread time, because the codegen already keeps registers as locals (this port's 20 copies
  measured as noise on the PC too).

### 5. Not possible exactly

- The G-buffer's first draw imports the shadow map's tiles into the 1200-pitch color image (509 tiles): the game does
  not clear the G-buffer, so where nothing is drawn its pixels are those tiles' words.
- The two 1280x720 resolves to `05638000` that nothing samples in a race (`*** NOBODY READS IT ***`): probably the
  pause menu's background; dropping them would need a proof that nothing reads them later.
