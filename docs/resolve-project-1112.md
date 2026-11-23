# EDRAM resolves: the cost and what can come off it (sasrt-nx, from 2026-11-12)

The user, 2026-11-12 21:30: "work on the resolve stuff at the same time as the cpu stuff you have 48 hours".

## Why

Handheld (GPU 460.8 MHz) the race is GPU-bound: 34.7 ms of GPU a frame of ~35.5 (abCC2's GPU profile), the GPU
idle only 0.8-1.5 ms a frame. Resolves (the 360 copying an EDRAM render target out to a texture) were 7.2 ms of it
(colour 4.6, depth 2.6): the largest block after the scene's own draws. Every Renut port has the same machinery, so a
cheaper resolve is universal (the base, Blur, RR6, Viva, Banjo); the gain depends on each game's resolve mix.

## How a resolve runs (deko3d path; the agent's map, 2026-11-12)

- Colour: a draw (resolve_copy_ps, a texel Load into a target of the same format, scissored; DrawResolveCopy,
  draw.cpp), 1:1 in host texels (the destination is made at the source's scale), no format conversion (gamma and
  exponent bias apply at draw or fetch time). MSAA: resolveTextureRegion / blit. Copy-engine fallback measured slower.
- Depth: ResolveDepth draws the float (R32F) and, when wanted, the guest "words" (RGBA8, `(unorm24 or 20e4) << 8 |
  stencil`) in one MRT draw; the words are only for readers of the destination's memory as 8_8_8_8 (a texture fetch
  through a words view, SASRT's EDRAM depth restore). banjo_renut_depth_words_lazy writes them only once something
  read them, or during a destination's first 300 resolves (the probe).
- Elision that exists: colour / depth hand-over (whole source, same size / format / scale, 1 sample, no levels), taken
  at a whole clear, the sampled and read-only variants, scan-out hand-over; banjo_renut_resolve_skip (same signature).
  In SASRT none applies in the race: colour resolves are "part of the target into another size" (the 1200-pitch
  G-buffer into 1152-wide textures, bloom / luminance chains) or, with SMAA on, the hand-over is off (gpu round item
  45: flat when tried, 90 % of handed resolves drawn later anyway); depth: the atlas is written at y offsets and the
  scene depth's words are read.

## R1: census (2026-11-12, cycle A's build, race on Ocean View)

Per-kind GPU time a frame (banjo_renut_diag_gpu_shaders + sasrt_gpu_diag_profile_vs, diagR1, mid-race window; the
labels also take the barrier / decompression drains their transitions trigger):

| resolve | ms a frame |
|---|---|
| depth: shadow cascades (3 x 1024x1024 into the 1024x3072 atlas) | 2.70 |
| colour 1152x544 format 10 (the G-buffer, out of the 1200-pitch target) | 2.21 |
| colour 1280x720 format 20 | 1.15 |
| colour 1152x544 format 20 | 0.67 |
| colour 1200x544 format 20 | 0.65 |
| depth: the scene depth (1152x544) | 0.50 |
| small (256x256, 288x136, 64x64, 576x272) | ~0.47 |

Depth words by destination (renut_diag_gpu_census, new "depth resolve words by destination (R1)" field; per 10 s):

| destination | resolves with words | without | words read by the fetch / the restore |
|---|---|---|---|
| B5640EA8 1024x3072 (the cascades' atlas) | 240-297 | 282-381 | 0 / 0 |
| B5640B28 1152x544 (the scene depth) | 193-206 | 0 | 386-412 / 127-193 |

The atlas's words are never read, yet about half its resolves write them: the destination is made again at every
dynamic-resolution step ("resolve destination B5640EA8 ... made again (33 so far): scale differs, size differs") and
each new HostTexture starts the 300-resolve probe again.

Cycle B's console race (abB, 2026-11-12 23:58, the census in the shipping build): the atlas was made again 5 times in
the race; a window after a remake shows "300 with words, 594 without", one without a remake "0 with, 837 without". The
scene depth: 279-298 resolves with words a window, every one of them read twice by the fetch.

## R2: the probe kept across a remake (sasrt_gpu_words_probe_kept, cycle C)

A resolve destination made again at the same guest address and format keeps words_wanted and its probe count
(render/textures.cpp). Exact under the probe's own rule (a late reader is served as before: redrawn from an unchanged
source, else counted "read stale" and from then on the words are written). Expected: about half the cascade resolves
lose their RGBA8 output (4 MB a resolve) and use the float-only pipeline: ~0.3-0.5 ms of GPU a frame.

**Measured (cycle C, 2026-11-13 01:55, against a same-session cycle A control):** works as intended. The atlas wrote its
words in 300 of 24,954 resolves of the run (the first probe), B's race in 11,946 of 24,138 (49 %). GPU 33.95 -> 33.86 ms
a frame, but the dynamic resolution keeps the GPU at its 34.5 ms budget: the saving went into resolution, 679.0 ->
684.9 lines on average (+0.9 %). Kept (exact, universal: sent to RR6 with the cycle C notes).

**Measuring GPU items from here:** at a fixed 3D resolution (dynamic resolution off for the measurement runs), so the
GPU's ms a frame compare directly; with it on, compare the mean 3D lines as well.

## Next candidates

- The G-buffer copies (2.2 ms + 0.65): a sub-rectangle hand-over (sample the 1200-pitch target's image with the
  1152-wide window) only pays if the target is not drawn again before the textures are read; census first (how often
  the source is bound again before the destination is sampled).
- The cascades (2.7 ms): beyond the words, the depth decompression before each resolve and the float conversion; the
  atlas path (gpu round item 77, drawn straight into the atlas) was +0.45 ms from uncompressed casters and barriers.
- Finer timing: Marks in DrawResolveCopy / MaterialiseLocked and before the transitions, so the copy and the barrier
  wait show apart (the agent's map, section 4). **Done for cycle C (2026-11-13): sasrt_gpu_diag_resolve_split**
  (render/draw.cpp, off by default; with banjo_renut_diag_gpu_shaders and sasrt_gpu_diag_profile_vs). DrawResolveCopy
  and ResolveDepth mark "resolve parts | colour|depth WxH format F: barriers / draw / after". "barriers" holds the
  transitions: a fragment wait for the work before (the source's own draws), and for a depth source, plume's
  decompression of the bound depth target (Deko3DCommandList::barriers, depthResolve / lazyDepthResolve). "after" holds
  the destination's move back to shader read, the readback queue and the clear. The GPU time between two timestamps
  goes to the label that was open, so a barrier's wait shows under "barriers".
  **First reading (c1113_diagC, cycle C's build, 24 race reports, GPU 33.25 ms a frame), ms a frame:**

  | resolve | barriers | draw | after |
  |---|---|---|---|
  | depth 1024x1024 (the 3 shadow cascades) | 0.43 | 1.14 | 0.75 |
  | colour 1280x720 RGBA8 | - | 1.01 | 0.04 |
  | colour 1152x544 RGBA8 | - | 0.65 | - |
  | colour 1200x544 RGBA8 | - | 0.57 | - |
  | depth 1152x544 (the scene depth, with its words) | - | 0.49 | 0.09 |
  | colour 1152x544 RGBA16F (the G-buffer, fixed-point clamp path) | not split: 2.10 in all | | |

  ("-": under the report's cut-off.) The colour copies' barriers cost nothing visible; their cost is the copy draw.
  The cascades' "after" (0.25 ms each) is the destination's move to shader read, which waits for the copy draw, plus the
  cascade target's clear for the next cascade; the next cascade writes the very image the copy reads (the
  sasrt_renut_depth_resolve_wait finding of 10-30), so that wait is a real write-after-read. An exact way round it:
  give the target a fresh image at that whole clear (a small pool, like the colour hand-over's "taken at a whole
  clear") so the next cascade's clear and casters do not wait for the copy. The G-buffer path
  (ResolveFixed16Locked, resolve_clamp_ps: the console's -32..32 range) was not instrumented; it is from cycle D on, and
  each part now counts its resolves a frame (gpu_profile::CountDraw), so the cost per resolve can be read.
- Not worth it: the depth resolve moves dest->words to COLOR_WRITE even when no words are drawn, but an unread words
  texture stays in COLOR_WRITE, so the move is a no-op (no barrier) for the atlas.

**Second reading, with counts (c1113_diagE, the synced CG-13 build, 24 race reports, GPU 33.55 ms a frame; ms a frame):**

| resolve | a frame | draw | each | other parts |
|---|---|---|---|---|
| colour 1152x544 RGBA16F (the G-buffer, fixed-point clamp path) | 5 | 1.99 | 0.40 | barriers / after: under the cut-off |
| depth 1024x1024 (the shadow cascades) | 3 | 1.12 | 0.37 | after the move to shader read 0.68 (0.23 each), barriers 0.43 (0.14 each) |
| colour 1280x720 RGBA8 | 3 | 0.98 | 0.33 | after 0.04 |
| colour 1200x544 RGBA8 | 3 | 0.42 | 0.14 | |
| colour 1152x544 RGBA8 | 4 | 0.40 | 0.10 | |
| depth 1152x544 (the scene depth, with words) | 1 | 0.49 | 0.49 | after the move 0.08 |

Each copy draw moves its texels at about 22-25 GB/s (an RGBA16F 1152x544 copy is 10 MB read + written): the copies are
bandwidth-bound, so only fewer bytes or fewer copies help. The cascades' 0.23 ms each after the destination's move to
shader read is the next cascade's clear and its start: the target was decompressed for the copy (plume's
resolveBoundDepth), so that clear is most likely a full write rather than a compression fast clear. Next experiment:
time that clear apart (a mark after it), and try giving the cascade target a fresh compressed image at the whole clear
(the copy then reads the old image; the clear stays fast and needs no wait for the copy).

**GPU batch F (2026-11-13 09:25-09:55): three cascade experiments, none pays (all removed again).**
- Method: the in-run A/B (banjo_renut_ab_targets "247,248", 4 s halves, fixed resolution) is too noisy for these sizes:
  target 247 never acted (its guard refused every clear) and still showed -2.35 ms GPU and +8 ms render thread between
  its identical halves. The split labels (per-label GPU ms, whole races with a key on against off) are what resolves
  0.1-0.7 ms; use them.
- R3b, the atlas left in its write layout after a cascade's copy (A/B 248): no change; the 0.68 ms "after the move"
  just moved into the next clear's label.
- The new clear labels: **depth clears cost ~1.25 ms a frame**: the cascades' 1024x1024 depth-only clears 0.67 ms (3 a
  frame), the scene depth's 1152x544 depth clears 0.29 and depth-and-stencil clears 0.25 ms. All full-bandwidth writes.
- R3, a fresh compressed image at each cascade clear (pool of two): the game clears the cascades' depth only (flags
  0x10), so the exact guard refused every swap. R3c (an experiment that may change pixels) made those clears depth and
  stencil too: the swaps then ran (16,384) and the clear cost 0.73 ms: no fast path either way. deko3d's depth clears
  on this hardware are full writes whatever the image's state; no clear-side saving here.
- What is left for the cascades is bandwidth: copy 1.12 + clear 0.67 + decompress / barriers 0.43 ms a frame.

**GPU batch G (2026-11-13 13:00-14:00, console, handheld 1020 / 460.8 / 1600, the shipping NRO of cycle E unless said;
runs out/console_runs/c1113_G1..G6).** Toml-only tests, one race each, plus one shader-package test:

| run | what | fps | GPU ms a frame | mean 3D lines | input -> display |
|---|---|---|---|---|---|
| G1 | shipping toml, dynamic resolution budget 34.5 ms | 28.15 | 33.80 | 683.0 | 71.1 ms |
| G2 | budget 32 ms (the user's request) | 28.80 | 31.32 | 651.8 | 62.2 ms |
| G3 | fixed resolution, per-shader labels (control) | 28.18 | 33.70 | fixed | 69.0 ms |
| G4 | as G3, port 99's earlykill off + port 120's XMA kick without lock | 28.04 | 34.00 | fixed | 71.2 ms |
| G5 | as G3 (second control) | 28.13 | 34.10 | fixed | 68.1 ms |
| G6 | as G3, a package without port 100's invariant gl_Position | 27.51 | 38.23 | fixed | 78.8 ms |

- **The 32 ms budget** (now in app/sasrt_switch.toml, `banjo_renut_dynamic_gpu_ms = 32.0`): -4.6 % lines for +2.3 % fps,
  -9 ms input to display, worst frame of a 10 s window 39 ms (50 at 34.5). Frames are 34.7 ms with the GPU at 31.3:
  past ~32 ms the CPU side (render thread 23.7, game thread) and the frame's serial chain set the pace, not the GPU.
- **Control to control**: 33.70 / 34.10 ms whole-race GPU, 0.35 ms between the label sums: the noise floor.
- **Port 99 (earlykill) off**: +0.30 ms whole race, -0.04 ms in the label sums: within the noise. Stays on.
- **Port 120 (audio_xma_kick_without_lock)**: no change (kicks ~8 ms and lock waits 12-28 ms per 10 s either way; 0.03 ms
  a frame in all). Stays off.
- **Port 100 (invariant gl_Position) is worth ~3 ms of GPU a frame here**: without it (out/deko3d_shaders_noinv, the same
  49 passes but invariant; its own DKSH cache, 3,921 variants), 38.23 ms against 34.10; label sums +2.7 / +3.0 ms against
  the two controls, in a few pixel shaders that shade several times the pixels (65879BBB 0.10 -> 0.51 ms, DCFFDB1C
  0 -> 0.34, 6955E33F 0.04 -> 0.33, the cascades' 3ECDED03 0.61 -> 0.93): the depth pre-pass and the colour pass no
  longer make the same depth, so the early depth test stops rejecting hidden pixels. The picture looked right. The
  handoff note of batch_1113 that suspected port 100 of costing 1-4 lines was wrong (corrected there).
- **Vivapinata_shader_noearly (port 95) does not apply**: SASRT's package (the 11-08 GLSL) has no early alpha test
  block (`if (DK_ALPHA_FUNC != 7u)`: 0 of 2,007 shaders), so the pass finds nothing; only the final test, which
  earlykill (977, 1,169 shaders) moves up.
- Kameo's colour and scan-out hand-overs (on in the base and here, off in vivapinata-nx for its pink flash): 0 resolves
  handed over in every 10 s window of a race here (SMAA turns the colour hand-over off, and SASRT's colour resolves are
  parts of targets into other sizes); GPU item 45 kept it with SMAA: flat.
