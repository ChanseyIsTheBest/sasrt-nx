# The GPU round of 2026-11-08 (after the move to the ultimate base)

The user's request of 2026-11-08: after the move to the ultimate base renderer (docs/ultimate-base.md) and with the
far-cascade shadow fix kept, find 15 pixel-identical GPU optimisations and implement them. Each is its own key, on by
default (`SASRT/GPU`, `app/src/renut_engine/gpu/sasrt_gpu_round.{h,cpp}`), switched off with every non-CPU enhancement
by the group's master key, and has an in-run A/B target: `banjo_renut_ab_target = 90 + its number` runs the "off"
half without it (`[renut A/B]` lines). The 10 s line `[sasrt gpu] GPU round (2026-11-08), in the last 10 s:` counts
what each did.

"Pixel-identical" here means by construction: each item removes work whose result was not used, or does the same work
on another unit, or merges waits; none changes a value a pixel is computed from. The checks are the PC race against
the reference recorded before the move (`out/pc/captures_ref_master_1108`) and the same race in Ryujinx (deko3d, the
console's code path); the speed is the console's to say (the PC splits its GPU time nothing like the Tegra X1 does).

## Where the console's GPU time goes (the evidence)

The console's GPU profile of the race (run `hot_ab`, NRO 10:36, before the move; ms a frame of 61):

| Pass | ms | Draws a frame |
|---|---|---|
| 1152x544 colour + depth (G-buffer, lights, stencil volumes) | 26.5 | 736 |
| 1024x1024 depth (three shadow cascades) | 11.5 | 407 |
| resolves | 5.5 | |
| 1152x544 colour (post passes) | 4.3 | 5 |
| depth resolves | 3.3 | |
| 1280x720 colour (FXAA) | 2.1 | 1 |
| 576x272 depth (4x multisampled) | 1.9 | 2 |
| 576x272 colour | 1.4 | 3 |
| exported stream conversion | 1.2 | |
| present | 0.9 | |

Ryujinx (deko3d, the merged tree, `sasrt_deko3d_diag_barriers`), per race frame: 1,129 draws; 241 barriers (97 waits for
the 3D engine to go idle, 119 fragment barriers, 25 full barriers that also wait for the copy engine); 17 depth
decompressions; 47 copy-engine buffer copies for 23 draws that read exported vertices; 3 readbacks.
Causes of the barriers (`fragments (none)` are the ones after a depth decompression):

| Per frame | Mode | Cause |
|---|---|---|
| 60.6 | wait for idle | buffer (graphics) |
| 36.3 | wait for idle | buffer + compute (the exported streams' conversions) |
| 34.2 | fragments | a texture into a read layout |
| 32.4 | fragments | read + colour, merged (resolves) |
| 31.3 | fragments | a target into the colour layout |
| 23.1 | full | copy + buffer (the exported vertices' fetch data) |
| 12.0 | fragments | after a depth decompression |

## The items

| # | Key | Default | A/B | What |
|---|---|---|---|---|
| 0 | `sasrt_gpu_skip_inert_draws` | on | 90 | Draws that can write nothing (no colour channel in the mask, no depth write, no stencil operation, no memory export in either shader) are not drawn and their targets are not bound for them: the race's two draws a frame into the 576x272 4x depth target (depth test NEVER), 1.9 ms a frame on the console with their target changes; their binds also emptied the scene depth's Zcull twice a frame. |
| 1 | `sasrt_gpu_precise_depth_resolve` | on | 91 | A compressed depth target is decompressed (`sasrt_deko3d_depth_resolve`) only if a draw, clear or copy wrote it since its last decompression, not every time it was bound: the lighting takes the scene depth on and off dozens of times a frame and only tests it (13-16 binds a frame kept clean). |
| 2 | `sasrt_gpu_plain_fetches` | on | 92 | Pixel shaders compiled without the sign / gamma / exponent-adjust block of the fetches whose fetch constants have none for the draw (constant 926, a bit a fetch constant; `tools/deko3d_glsl_opt.py` pass `plainfetch`). The block is a uniform branch, but its temporaries counted in the registers. |
| 3 | `sasrt_gpu_alpha_spec` | on | 93 | banjo-nx's alpha test specialization (constant 903) for this game: without the alpha test no compare and no discard, the shader no longer "kills pixels", and the GPU tests depth before shading opaque draws. sa2-nx turned it off after flat colours in Ryujinx; this game's race renders right with it there. |
| 4 | `sasrt_gpu_gamma_upload_once` | on | 94 | The game's display gamma ramp (sa2-nx's ramp code) copied to its texture when it changes (and in the first 300 frames), not every frame (a copy-engine upload between a full barrier and another barrier). |
| 5 | `sasrt_gpu_decompress_merge` | on | 95 | The barrier after a depth decompression at a change of targets merged with the barrier already pending (the decompression recorded first). |
| 6 | `sasrt_gpu_readback_barrier_merge` | on | 96 | An image readback's full barriers each merged with the full barrier next to them (four drains of the whole GPU to two for the race's 1x1 luminance). |
| 7 | `sasrt_gpu_fetch_copy_compute` | on | 97 | The copies the memory exports need made by a compute shader on the 3D engine (`fetch_copy_cs`) instead of the copy engine: each memexport window's seed (24-34 a frame) and the fetch data of a draw reading exported vertices from memory. A wait for the 3D engine on each side instead of a full barrier; and the export draw no longer races the seed copy (the barrier after the copy waited for the 3D engine only). |
| 8 | `sasrt_gpu_data_cache_invalidate` | on | 98 | Buffer barriers invalidate the shaders' global-data and constant caches (Maxwell's InvalidateShaderCaches, bits 4 and 12), not their instruction cache too: about 150 a frame. |
| 9 | `sasrt_gpu_one_x` | on | 99 | A draw whose targets are 1x and whose sampled textures have scale code 0 gets its pixel shader with both folded (constant 926 bit 31, pass `onex`: banjo-nx's scale1 and fragscale as a draw's choice; the docked HUD is 1.5x). |
| 10 | `sasrt_gpu_face_sign` | on | none | The Xenos face register's sign (`clamp(1 / Y, -FLT_MAX, FLT_MAX) >= 0`) as Y's sign bit (pass `facesign`, constant 928, 1 by default): a quarter-rate reciprocal, two clamps and a compare a pixel fewer in nine shaders, the race's most-drawn G-buffer shader among them. Y is never NaN. Off: `configs/sasrt_gpu_face_sign_off.toml`. |
| 11 | `sasrt_gpu_readback_compute` | on | 101 | The memexport readbacks (one group at a list's end) copied by `fetch_copy_cs` instead of the copy engine, then a wait and the L2 written back for the CPU (`plume::Deko3DFlushL2`). |
| 12 | `sasrt_gpu_tiled_cache` | **off** | 102 | Maxwell's tiled caching (binning), which NVN uses and deko3d leaves off. The bandwidth of the G-buffer and the additive lights is what it saves. Same pixels by the hardware's design (deko3d's barriers order tiles and fragments, its fences flush them; a full barrier gets a flush ahead of it here), but Ryujinx does not emulate it: off until a console run shows the same picture (`configs/sasrt_gpu_try_tiled_cache.toml`). |
| 13 | `sasrt_gpu_texel_readback_compute` | on | 103 | The 1x1 float resolve the CPU reads every frame (the average luminance) read back by `texel_readback_cs` on the 3D engine: no move into and out of the copy layout with their full barriers. |
| 14 | `sasrt_gpu_lazy_depth_resolve` | **off** | 104 | A written compressed depth target decompressed right before something reads it (bound alone for it), not at each unbind and list end. Ryujinx emulates no depth compression: off until a console run (`configs/sasrt_gpu_try_lazy_depth.toml`). |

Constant 926 now carries two items (bits 0-30 plain fetch constants, bit 31 the 1x fold): the pipeline key's spare word
(`PipelineKey::fetch_pad`), so the pipeline lists keep their version; `tools/deko3d_variant_cache.py` reads it.

## What the counts say (Ryujinx, deko3d, the race)

Per race frame (`sasrt_deko3d_diag_barriers`): the merged renderer before the round (run ult1), items 0-9 on (gpu9b),
and the final build with every item on but 12 and 14 (gpu15). The scenes differ a little between runs (the race is not
replayed frame for frame); the counts are per frame of each run's race.

| | Before | Items 0-9 | Final |
|---|---|---|---|
| Full barriers (the whole GPU idle, the copy engine with it) | 25.5 | 7.0 | 0.0 |
| Waits for the 3D engine (the copies' full barriers became these) | 97 | 146 | 199 |
| Fragment barriers | 119 | 103 | 103 |
| Barriers after a depth decompression | 12 | 1 | 0 |
| Depth decompressions | 17 | 13 | 13 |
| Depth binds kept clean (`sasrt_gpu_precise_depth_resolve`) | | 13-16 | 13 |
| Export seeds on the 3D engine | | 24-34 | 46-63 |
| Inert draws not drawn | | 2 | 2 |

uam's code for the pixel shaders of the PC's GPU profile (`tools/deko3d_shader_stats.py`, every fetch plain): GPU-time
weighted instructions -78 % (static code: the sign blocks were branched over at run time, so the runtime saving is the
registers): the final FXAA pass 42 -> 23 GPRs (and 150 -> 121 instructions with item 9), a G-buffer light shader 47 -> 31,
a post pass 41 -> 24, the most-drawn G-buffer shader 33 -> 28. 32 or fewer leaves every warp slot of the SM in use.

## Checks

- PC (D3D12; items 0 and 4 act there, the rest are deko3d's): the race against the reference recorded before the move:
  the same scenes and features; inert draws 2 a frame, the gamma ramp copy skipped every frame after start-up.
- Ryujinx (deko3d): the race renders right with items 0-9 (textures, lighting, shadows, water, the skinned drivers; no
  flat colours with the alpha specialization). Items 10, 11 and 13 and the shader package with passes `onex` and
  `facesign`: below as they are run.
- After any change of `tools/deko3d_glsl_opt.py` the DKSH cache must be made again (`tools/deko3d_variant_cache.py`
  into `out/deko3d_shaders/deko3d_shaders.bin`): every variant's text changes, and a stale cache made Ryujinx compile
  every shader at run time (66 s of draws waiting) - the console would stutter the same way.

- The pipeline lists record a specialised pipeline only when it is built on the spot, not one a background job finished
  (the plain-fetch and 1x keys are all of that kind), so `tools/deko3d_variant_cache.py` cannot make their variants from
  the lists. The Ryujinx run compiled them with the NRO's own uam (the console's compiler) into the SD's
  `deko3d_shaders.bin`; that file is merged into the shipped cache (`--merge`): 3,989 variants instead of 3,475, so the
  console starts with them too (`out/deko3d_shaders_ult/ryujinx_sd_cache_r15.bin`).
- The final build in Ryujinx (all items on but 12 and 14): no full barrier left in the race (25.5 a frame before the
  round); the memexport readback group and the luminance readback on the 3D engine every frame; the race renders right
  (water, the boat transform, sparks, shadows, lighting, the skinned drivers). The PC race matches the reference.

- Items 12 and 14 on in Ryujinx (run gpu15try, `configs/sasrt_gpu_try_*` keys): the race renders right; depth
  decompressions 13 -> 4 a frame (one a frame now waits for its read and is made then: the rebind path works). Ryujinx
  emulates neither depth compression nor tiled caching, so what they would break only shows on the console.

## For the console (the user's runs)

`configs/sasrt_gpu_round_off.toml` (every item off) against the normal toml gives the round's whole effect;
`configs/sasrt_gpu_ab_<n>.toml` one item's, in one run; `configs/sasrt_gpu_round_profile.toml` the GPU time by pixel
shader and the barriers by cause, for the next round. Items 12 and 14 need a console run before they can be on.

# Round 2 (2026-11-08, evening): 15 more

The user's request: "Look for 15 more gpu optimisations". The same rules as round 1: each item its own key in
`SASRT/GPU` (`sasrt_gpu_round.{h,cpp}`, items 15-29), on by default, switched off with every non-CPU enhancement by the
group's master key, an in-run A/B target `banjo_renut_ab_target = 90 + its number` (105-119), a count in the same
`[sasrt gpu]` line. Pixel-identical by construction: each removes a wait, a cache drop, a copy, a bind or shader work
whose result was not used, or gives the same bytes another way.

## How they were found: the command stream of one frame

Two diagnostics (off by default, `configs/sasrt_gpu_trace.toml` turns both on with the barrier causes):

- `sasrt_deko3d_diag_trace`: every 600th frame's command stream as tokens in the log (`[deko3d trace]` lines): barriers
  (`B` + P wait for idle / F fragment barrier / X full + their causes + `i` when the texture cache is dropped), draws
  `D`, dispatches `X`, target binds `T<colour>:<depth>` (images numbered in order of appearance), clears `Cc` / `Cd`,
  depth decompressions `Z`, copy-engine copies `K`, descriptor invalidations `I`, list ends `E`; runs as `D*554`.
- the census, at the end of the deko3d line with `sasrt_deko3d_diag_barriers`: descriptor and code invalidations,
  framebuffer binds and depth target changes, lists, dispatches, clears.

What a race frame's trace showed (Ryujinx, NRO with round 1 and item 15): each skinned mesh is
`X T BPbi D BPbki X BPbi T D` - a memexport seed dispatch, its targets bound again, a wait, the export draw, a wait, the
stream conversion, a wait, the targets bound again, the draw that reads the converted vertices - about 30 times a frame
(in the shadow cascades and the G-buffer); the memexport readback at a list's end was 44 dispatches; target binds and
clears came in runs at a pass's start (`T12:0 BFC Cc T13:0 BFC Cc ...`). Descriptor invalidations were 851 in a whole
run (not worth an item); depth target changes (each empties Zcull) 13 a frame.

## The items

| # | Key | A/B | What |
|---|---|---|---|
| 15 | `sasrt_gpu_seed_no_lead_wait` | 105 | The memexport seeds (round 1's `fetch_copy_cs` dispatches) start without the wait for the 3D engine before them: the windows they write are fresh (past the slot's last window, 256-byte aligned), so nothing recorded before read or wrote those bytes. The wait after them stays. |
| 16 | `sasrt_gpu_convert_lead_wait` | 106 | A stream conversion skips its leading wait when the list recorded a buffer barrier (a wait that drops the data caches) since its last memexport draw (`plume::Deko3DBufferWaits`). Mostly superseded by item 18 in this race (the conversions it applied to are reused now): 0-5 a frame. |
| 17 | `sasrt_gpu_identity_ramp` | 107 | The scan-out does not look the game's gamma ramp up (three dependent texture loads a pixel) when the ramp is the linear one: the XDK's default repeats i's bits (`i << 2 | i >> 6`), every entry within 0.185 of level i at 8 bits, so the 8-bit target stores i either way; the shader writes `i / 255` (param1 = 1). Both back ends. |
| 18 | `sasrt_gpu_convert_memo_keep` | 108 | banjo-nx's conversion memo (`banjo_renut_convert_reuse`) is kept across new exports: a new export writes a fresh window, a key no entry has. It is cleared when a slot's exports complete, a window is written in place, an export or stream buffer is replaced, or the frame changes. 12-31 conversions a frame used again (11 a frame before), each a dispatch and two waits fewer. Both back ends. |
| 19 | `sasrt_gpu_depth_resolve_float_ps` | 109 | A depth resolve whose words nothing reads (the race's three cascades and the scene depth: the words target bound and write-masked) is drawn by `depth_resolve_float_ps`: the depth loaded and written, without the stencil load, the 24-bit / 20e4 encode and the masked output. Both back ends. |
| 20 | `sasrt_gpu_same_targets_kept` | 110 | plume does not bind the render targets again when the framebuffer object asked for is the one this list bound last (a framebuffer's views never change, the one in use is alive; plume's own binds forget it): the renderer asks again after every dispatch and resolve. 110-150 binds a frame. |
| 21 | `sasrt_gpu_readback_spans` | 111 | The memexport readback's windows that follow one another (each from the last's 256-aligned end) copied by one dispatch, padding with them (bytes the CPU never reads): 44 dispatches a frame became 1. |
| 22 | `sasrt_gpu_seed_wait_only` | 112 | The barrier between the seeds and the export draw is a wait alone: the export draw only writes the windows; every later reader has its own barrier that drops the caches. 50-76 a frame keep the texture, data and constant caches. |
| 23 | `sasrt_gpu_readback_fence_flush` | 113 | Round 1's compute readbacks (memexport and the 1x1 luminance, 4 a frame) record no L2 flush of their own (a wait, the dirty lines out, and on the Tegra X1 the whole L2 dropped): the CPU reads after the slot's fence, which plume signals with deko3d's cache flush (`SyncptAction` FlushCache). |
| 24 | `sasrt_gpu_convert_tail_vertex_only` | 114 | The wait between a conversion and its draw drops the texture cache only (the vertex fetch's, as before), not the shaders' global-data and constant caches, which the stream buffer's only reader does not use. |
| 25 | `sasrt_gpu_convert_lead_data_only` | 115 | The wait before a conversion drops the global-data cache alone (its storage-buffer loads). Its push constants are fresh transient memory: plume now drops the constant and global-data caches at every list's start (`freshComputeConstants`), which also covers the seeds' upload-ring reads (reused two frames on) now that no barrier comes right before them. |
| 26 | `sasrt_gpu_clip_spec` | 116 | Every vertex shader wrote `gl_ClipDistance[0] = dot(position, plane 0)` and the clip slot was on for every draw (rr6-nx's `banjo_deko3d_user_clip_enable`); this game never sets a plane (zeros: a distance of 0 clips nothing). A draw without a plane (`PipelineKey::reserved` bit 3 clear) gets constant 929 = 0 (pass `clipspec`: no dot product a vertex) and plume sets `SET_USER_CLIP_ENABLE` 0 while its pipeline is bound (`Deko3DGraphicsPipeline::noUserClip`). A draw with a plane keeps both. |
| 27 | `sasrt_gpu_lean_barrier_skip` | 117 | A barrier that only moves textures into a colour or depth target layout (a fragment barrier dropping nothing) is not recorded when no draw, dispatch, copy or decompression came since the last barrier that waited for the fragments with no dispatch since a wait for idle: the reads it would order are done. Clears read no texture and write in order. 13-17 a frame (the runs of binds and clears). |
| 28 | `sasrt_gpu_readback_barriers_trim` | 118 | The memexport readback at a list's end: its wait drops the global-data cache alone, and no barrier after its copies (the list ends there; the slot's windows are written again only after its fence was waited for). |
| 29 | `sasrt_gpu_export_raster_discard` | 119 | A draw whose vertex shader only exports to memory (export mode 7, multipass: the Xenos kills its primitives) is drawn with an empty scissor and the rasterizer off (3D method `RasterizerEnable` 0, then on again): its vertex shader runs and exports, no primitive reaches clipping or setup. This tree never set `ShaderRecord::export_only` (the base has only the draw side of vivapinata-nx's `banjo_renut_export_only_draws`): its `ContainerIsExportOnly` is ported to `d3d/hooks/shader.cpp`, and with this key off such draws are rasterized as before. Every seeded export draw of the race is one: about 60 a frame. |

## What the counts say (Ryujinx, deko3d, the race; per race frame of the traces)

| | Round 1 final (gpu15) | Round 2 (r2e) |
|---|---|---|
| Waits for the 3D engine | 199 | 122 |
| Fragment barriers | 103 | 92 |
| Full barriers | 0 | 0 |
| Barriers that drop the texture cache | about 212 (r2a) | 111 |
| Compute dispatches | 136 (r2a) | 83 |
| Target binds asked for / made | 187 / 187 (r2a) | 170 / about 45 |
| Stream conversions dispatched / used again | 88 / 0 | about 60 / 20-30 |
| Memexport readback dispatches | 44 | 1 |
| L2 flushes recorded by the renderer | 4 | 0 |
| Export draws rasterized | about 60 | 0 |

(r2a was the census build with item 15 on; the scenes differ a little between runs.) Every vertex shader of the race
draws without its clip distance (1,600 pipelines built with constant 929 = 0) and the scan-out without its ramp lookup.

## Checks

- Ryujinx (deko3d), runs r2a-r2e with `out/ryu_*` comparison sheets: the race renders right after each step (water, the
  boat transform and its skinned drivers, shadows, lighting, HUD). The title logo in r2a's first frames is the game's
  own respawn wipe (the user, 2026-11-08). r2e compiled no shader at run time (`uam 0 compiles`): the DKSH cache
  (`out/deko3d_shaders_ult/deko3d_shaders_r29b.bin`, 4,745 variants) has every variant, the clip ones included.
- PC (Renut on Vulkan, `-Set 'sasrt_renderer=renut;renut_gpu_backend=vulkan;banjo_renut_replay_inherits=false'`: the PC's
  own `out/pc/sasrt.toml` sets neither): the race against the reference recorded before the move and round 1's run
  (`out/gpu_r29_pc_vs_ref.png`): the same picture. Items 17-19 act there (the scan-out runs only for the captures while
  the test window is minimised: 40 identity scan-outs for 40 captured frames).
- A PC run without the renderer key draws with the emulated Xenos GPU on the default DXGI adapter (the laptop's AMD
  integrated GPU here) and its exposure is wrong: that is not this round (all its keys off: the same picture).
- After a change of `tools/deko3d_glsl_opt.py` (here pass `clipspec`) every vertex variant's text changes: the shader
  package (`app/out/renut_switch`) and the DKSH cache are made again, and the cache merged with a Ryujinx run's SD
  cache (`--merge`), as in round 1.
- One mistake on my side: run r2a recorded its video at 425 s, the time run gpu15try had used, and replaced that
  recording (`video_425s.rgba` of 13:49; its comparison sheet `out/ryu_gpu15_vs_try.png` is kept). Later runs used times
  no recording had (433, 435, 437, 439; PC 200-203).

## Found and not done

- Shadow cascades in D32F instead of D32F_S8: the game's depth is the 20e4 float format, so scene and shadow depth are
  Maxwell's 64-bit ZF32_X24S8; the shadow map uses no stencil, and plain D32F holds the same depth values in half the
  bytes. It needs the surface made again (with its stencil set from the last clear) the first time a stencil test
  appears: not done in this round.
- The vertex shaders' epilogue (the screen-space branch on `v[60].z`, the depth remap on `v[94].x`) as constants: about
  six instructions a vertex; needs a new pipeline-key word (list version 6).
- Deferred depth clears (`T1:2 BFC Cc Cd Z`: a cleared depth target decompressed with nothing drawn) and decompressions
  at kicks: the lazy decompression's ground (item 14, off; the base's `ultimate_deko3d_depth_resolve_lazy` from rr6-nx
  is the same idea). The console's shadow cascades are the test either way.
- The waits around each skinned mesh that remain (seed -> export draw, export draw -> conversion -> draw) are real
  orderings: removing them needs the export to write the host stream itself.

## For the console (the user's runs)

`configs/sasrt_gpu_round2_off.toml` (the second round off, the first on) against the normal toml gives this round's
whole effect; `configs/sasrt_gpu_ab_<n>.toml` (n 15-29) one item's. Copy the NRO, `deko3d_shaders.bin` and the configs
together: the shader package changed (pass `clipspec`).

## Console results (2026-11-08 17:44-18:14, NRO 16:41, stock clocks: GPU 460.8 MHz, CPU 1020 MHz)

The same race four times (`out/console_runs/{r12_off,r2_off,r2_on,r2_on_b}`, driven from the PC with the user's word;
`tools/console_perf.py`): the first 10 race windows of 10 s from the start line (the loading window dropped), GPU
profile in ms a frame:

| Pass | Both rounds off | Round 1 only | Rounds 1 + 2 |
|---|---|---|---|
| 1152x544 colour + depth (G-buffer, lights) | 29.80 | 20.46 | 20.74 |
| 1024x1024 depth (shadow cascades) | 13.78 | 13.79 | 11.23 |
| resolves | 3.99 | 3.94 | 3.95 |
| depth resolves | 3.30 | 3.30 | 2.39 |
| 1152x544 colour (post passes) | 4.80 | 3.33 | 3.20 |
| 1280x720 colour (FXAA) | 3.32 | 2.85 | 3.10 |
| 1200x544 colour | 1.29 | 2.39 | 2.39 |
| 576x272 colour | 2.56 | 2.18 | 2.21 |
| 576x272 depth | 1.84 | 0 | 0 |
| exported stream conversion | 1.16 | 1.16 | 0.81 |
| present | 0.96 | 0.85 | 0.65 |
| the rest | 1.61 | 0.84 | 0.83 |
| **GPU a frame** | **68.4** | **55.1** | **51.5** |
| fps | 14.6 | 18.0 | 19.1 |
| render thread busy (ms a frame) | 34.1 | 34.8 | 35.8 |

Round 2: -3.6 ms GPU a frame (-6.5 %), +1.1 fps; its passes: shadow cascades -2.6, depth resolves -0.9, stream
conversion -0.35, present -0.2. Round 1: -13.3 ms (-19 %), +3.4 fps; the G-buffer pass -9.3. Against the NRO before
the move (hot_ab, 10:36, the same measure): 59.6 -> 51.5 ms, 16.7 -> 19.1 fps. One run a configuration: a window's GPU
ms varies by 1-2 ms within a run; the round-2 run from mid-lap (r2_on) gave 49.4 ms. The race still waits for the GPU
(51.5 ms) more than for the render thread (35.8 ms). To look at next: the 1200x544 colour pass is 1.1 ms slower with
round 1 on than off (2 draws: its A/B items 2 and 9 first), and the G-buffer and shadow passes are 62 % of the frame.
The race rendered right in every run (the screenshots in each folder).


# Round 3 (2026-11-08, night): 15 items, 10 kept

The user: "Try to aim for 20 more pixel identical gpu optimisations", then "up to 60 ... you can include shader
optimisations as well", "remember you can do tricks like banjo's skin once shader thing", "optimising the shader
translator will help other ports", and "get to 50 and then we will test". 15 items were written (30-44, keys
`sasrt_gpu_*`, A/B 120-134), every one checked on the console in the race (no Ryujinx run first, the user's call: the
DKSH cache got the new variants from `tools/deko3d_variant_cache.py --sasrt-guess`). Four did not pass and are off by
default: 39 and 40 made the G-buffer pass slower, 42 broke the picture, and 44 does nothing without 42. Item 32 is
correct but found nothing to do in this game.

New infrastructure: PipelineKey gained `sasrt_words[12]` (pipeline list version 6; version 3-5 lists are converted with
the words 0, the generic pipelines), the draw's values its shaders read at run time as specialization constants
(render/draw.cpp `SasrtSpecWordsOf`), built in the background with the generic pipeline meanwhile as the round-1
plain-fetch key. plume's `sasrtRound` and the round's tables hold 64 items; `banjo_renut_ab_targets` takes targets up to
255.

## The items

| # | Key | Default | A/B | What |
|---|---|---|---|---|
| 30 | `sasrt_gpu_seed_cpu_direct` | on (2026-11-23: briefly off while the 1.0.0 release run's vertex explosions were bisected; not their cause) | 120 | A memexport draw's fresh windows get their seed (the guest memory's bytes) written by the CPU straight into the slot's export buffer (plume's deko3d memory is CPU-uncached and mapped), not through the upload ring and a compute copy: no dispatch and no wait before the export draw. The windows are fresh, the slot was last used before its fence (which writes the GPU's caches out) and every queue flush drops the GPU's L2 (deko3d postSubmitFlush), as for the upload ring. The wait stays when an export of the same list has had no buffer wait since. |
| 31 | `sasrt_gpu_convert_tail_no_texture_drop` | on | 121 | The wait after a stream conversion keeps the texture cache: the converted streams are written past everything the frame wrote or read, so no cache holds their lines. |
| 32 | `sasrt_gpu_vs_input_mask` | on (inert) | 122 | Vertex attributes the bound vertex variant never reads (its shader program header's input map, read from the DKSH at load) are bound as constants, which the vertex fetch does not read. Correct, but the race's draws fetch nothing their variants leave unread: 0 binds changed. |
| 33 | `sasrt_gpu_export_no_pixel_shader` | on | 123 | An export-only draw (rasterizer off, item 29) is built without its pixel shader: its vertex shader then writes no output for it (constant 905 = 0), and its pixel shader's constants and textures are not set up. |
| 34 | `sasrt_gpu_vs_screen_space_spec` | on | 124 | Every vertex shader's epilogue tests `SharedConstants.screen_space` at run time: the draw's value as constant 932 (`sasrt_words[0]`, pass `vsepi`). About 250 bytes less code a vertex shader. |
| 35 | `sasrt_gpu_vs_depth_remap_spec` | on | 125 | The same for the epilogue's depth remap test (`depth_remap[0]`, never set on deko3d). |
| 36 | `sasrt_gpu_stacked_3d_spec` | on | 126 | A 3D fetch picks a stacked texture (two array fetches and a blend between layers, with a size query) or a volume texture at run time: the draw's choice per fetch constant as constant 934 (`sasrt_words[1]`, pass `stack3d`). Seven pixel shaders, the race's full-screen ED0A8D53 (14.8 -> 9.5-10 KB of code) and the composite among them. |
| 37 | `sasrt_gpu_stacked_filter_spec` | on | 127 | The same for a stacked fetch's layer filter and Z wrap (935, 936). |
| 38 | `sasrt_gpu_fetch_endian_spec` | on | 128 | A vertex fetch by address swaps each word every way and picks the byte order at run time from the fetch slot's word: the draw's order for the slots its shader reads as constants 937-939 (`sasrt_words[4-6]`, pass `fetchendian`). Renut translator output: any port's. |
| 39 | `sasrt_gpu_gpr_cap` | **off** | 129 | Pixel shaders 364C9BF8 (light volumes), F646B7A8 and 92D1F7E4 (34, 33, 38 registers) compiled with 32 (constant 910). **Slower on the console** (see below). |
| 40 | `sasrt_gpu_gpr_cap_filter` | **off** | 130 | The 60-register filter 9041AFF6 compiled with 32. **Slower on the console.** |
| 41 | `sasrt_gpu_export_format_spec` | on | 131 | A memory export packs every value through a switch over the export formats and a loop with run-time indexed arrays, keyed by the format word of its address register (eA = c<N> + the index): the draw's z word of up to three such registers (as the constant buffer holds it: the literal if the shader defines one, NaN-flushed as uploaded; only a zero or normal float) as constants 940-943 (`sasrt_words[8-11]`, pass `expfmt`), replacing the read of eA.z (exact: eA.z = i * 0 + c.z for the finite index of any export that happens). The race's skinning export shader: 18.4 -> 12.0 KB. Renut translator output: any port's. |
| 42 | `sasrt_gpu_texture_drop_tracked` | **off** | 132 | A read move dropped the texture cache only if the texture was sampled since the last drop. **Wrong on the console**: the main menu's 3D scene and sky washed out white (run r3_all; bisected in r3_bis1 / r3_bis2). The render targets are hardware-compressed, and the drop after rendering into one is needed whatever was sampled before. Kept for study, not to be ported. |
| 43 | `sasrt_gpu_target_wait_tracked` | on | 133 | A barrier that only moves textures into target layouts is skipped when none of them was sampled, copied, resolved or decompressed since the last fragment wait (plume: per texture the fragment-wait epoch of its last use; what is bound is marked again at each wait; the marks are kept whatever the options, so an A/B half finds them current). About 65 barriers a race frame. |
| 44 | `sasrt_gpu_read_wait_tracked` | **off** | 134 | A read move waits only for a texture written since the last wait or with its drop due: without item 42 a drop is always due, so it does nothing. |

Looked at and not done: banjo-nx's skin-once (the export repeat diagnostic, now also without the window addresses: 0
of 6,300 export draws per 10 s repeat another's skinning; each mesh is skinned once a frame already, as point lists of
about 1,370 vertices); the bound-fetch type words as constants (the race's vertex shaders use no bound fetch); an
export-only vertex shader without its position (no code saved: the position is the exported value); the 1200x544 pass
(A393B1E0, 1.2 ms a draw for one fetch: its coordinates alternate 80 pixels apart column by column, which looks like
anisotropic filtering at work; removing it changes pixels); the D32F shadow cascades (needs a migration path for a
stencil that appears later); the fragment barriers' own wait-for-idle on a texture drop (deko3d's choice, as NVN does).

## Console results (2026-11-08 20:49-21:08, stock clocks, same session, the race from the start line, 200 s)

| | Round 3 off (r3_off) | Round 3 with the caps (r3_bis2) | Round 3 as kept (r3_nocap) |
|---|---|---|---|
| race windows of 10 s | 26 | 25 | 24 |
| fps | 19.89 | 19.24 | **20.96** |
| GPU ms a frame | 50.14 | 51.64 | **47.10** |
| render thread ms a frame | 33.20 | 32.08 | 32.00 |
| 1152x544 colour + depth (G-buffer, lights) | 20.39 | 23.68 | 19.38 |
| 1024x1024 depth (shadow cascades) | 11.58 | 9.94 | 9.83 |
| resolves | 4.84 | 4.83 | 4.85 |
| 576x272 colour | 1.08 | 1.20 | 1.09 |
| waits for idle a frame | 104.0 | 69.9 | 68.8 |
| fragment barriers a frame | 96.3 | 70.7 | 70.8 |
| texture-cache drops a frame | 108.0 | 73.9 | 73.9 |

Round 3 as kept: -3.0 ms GPU a frame (-6 %), +1.07 fps; the shadow cascades -1.75 ms (the skinning export chains:
items 30, 31, 33, 41, and 43), the G-buffer pass -1.0 ms. One run a configuration (a window varies 1-2 ms). From both
earlier rounds off (68.4 ms, 14.6 fps the same way): 47.1 ms and 21.0 fps.


# Round 4 (2026-11-08/09, night: "getting down to 33 ms GPU time, pixel identical")

The user's goal: 33 ms of GPU time a race frame (from 46-47 ms), every pixel as before, console-tested, the confirmed
savings to the Ridge Racer 6 port. This round first measured where the time could come from, with experiments that
change pixels on purpose (keys `sasrt_gpu_exp_*`, off by default, never for shipping) and diagnostics, all on the
console in the race (stock clocks, 200 s from the start line).

## Result (console, the race, the shipped set: run r4_ship against round 3's r3_ship)

| | Round 3 as kept | Round 4 as kept |
|---|---|---|
| fps | 20.78 | **23.59** |
| GPU ms a frame | 46.59 | **38.79** |
| render thread ms a frame | 32.09 | 29.36 |
| shadow cascades (profile) | 9.77 | 3.15 |
| the skinning export draws (profile) | 8.44 | 0.48 |

-7.8 ms of GPU time a frame, +2.8 fps, the same pixels. The final build's confirmation run (r4_final, 02:35, the
shipping toml, no per-shader profile): 40.27 ms, 22.88 fps over 23 race windows (runs differ by 1-2 ms with the part of
the track the windows catch). Ridge Racer 6 ported the round as its port 50 (renut_nx_ultimate_base main 7690eede15):
items 46 and 48 count 0 there (no memexport draws), its race unchanged at 60 fps. The 33 ms goal is not reached: the rest of the frame is the
G-buffer and lighting pass (19.5 ms), colour resolves (4.9), depth resolves (2.5), the 1200x544 pass (2.5) and post
passes (about 5), all doing the work their pixels need (below).

## How it was found

| Run | GPU ms a frame | fps | Finding |
|---|---|---|---|
| r4b: item 45 on, the export-order and resolve-list diagnostics | 47.52 | 20.71 | baseline of the night |
| exp_nowaits: the stream conversion's two waits left out (35 of 68 waits for idle a frame) | 47.53 | 20.67 | **waits cost nothing** here |
| exp_nofill: the shadow cascades' depth-only draws with a 1x1 scissor | 44.53 | 21.86 | the cascades' fill is 1.5 ms of their 10 ms; the rest is geometry |
| exp_twice: every memexport draw drawn twice (the second writes the same bytes) | **55.19** | 18.03 | **+8.56 ms**: the ~45 skinning export draws (~47,000 points) cost ~8.5 ms a frame |
| r4e_prof: the export draws by size | | | ~180 ns a point at every size (the 34K-point draw 6.1 ms): a per-point cost |
| r4h_parts0/1/2/4, r4j_parts15: the export shader without its stores, its bone loads, its inputs, all of them | | | the 34K-point draw 4.8 / 4.7 / 4.0 / 4.0 / **4.1** ms: the cost is not in the vertex shader at all |
| r4i_sph1: the program header's DoesGlobalStore bit cleared; r4k_pos16: the position moved outside the view volume; r4g: triangle or line lists | | | no change, no change, slower |
| r4l_ab: item 48 off and on (in-run A/B) | on 36-43, off 44-49 | | **-6.7 ms on average** |

Renut gives every Xenos point list key.point_sprite = 1 (render/draw.cpp MakeKey), which attaches the point-sprite
geometry shader (point_sprite_gs): also to the export draws recorded with the rasterizer off (item 29). The geometry
shader made a quad of every skinned point for a rasterizer that was off, ~120 ns a point whatever the vertex shader did.

The order diagnostic (`sasrt_gpu_diag_export_order`) shows the game skins and draws one mesh at a time (export draw,
its conversion, the draw that reads it, the next export, about 45 chains a frame), so the conversions cannot be batched;
exp_nowaits shows there would be nothing to gain anyway. The resolve split (`sasrt_gpu_diag_profile_vs` with the shaders'
breakdown, run r4m_prof): the 1152x544 RGBA16F resolves 2.2 ms (three a frame, ~13.5 GB/s each), the 1280x720 RGBA8
ones 1.2 ms, the rest under 0.8 ms; depth resolves 2.5 ms.

After item 48 the only draws of the race still drawn through a Renut geometry shader are A393B1E0's two rectangle-list
draws (one rectangle each: the geometry shader's share is nothing; run r4n_prof, labels tagged by
`sasrt_gpu_diag_profile_vs`). Its 2.5 ms are its one fetch's anisotropic filtering over coordinates 80 pixels apart.

Checked and dropped: the declared-but-unwritten vertex outputs (Renut declares 27 interpolators in every vertex shader;
taking unread ones out compiled to a byte-identical program: uam already leaves unwritten outputs out of the program
header); item 45 (flat in the race: 90 % of the handed resolves are drawn later anyway); item 47 (slower: +0.9 ms on
average over 10 A/B pairs).

## The items

| # | Key | Default | A/B | What |
|---|---|---|---|---|
| 45 | `sasrt_gpu_handover_with_smaa` | **off** | 135 | banjo's colour hand-over kept with SMAA (SMAA's target settled first). Correct, flat in the race. |
| 46 | `sasrt_gpu_export_window_ubo` | on | 136 | A memexport vertex shader's window loop reads the constant buffer itself, `g_UboShared.v[61u + min(i, 3u)]`, not a local copy (constant 944 from `sasrt_words[7]` bit 2, memexport vertex shaders only; pass `expwin`). The same four words (i < 4 wherever the loop reads them). D80AC859: local memory 6144 -> 0 bytes a warp, code 6912 -> 6144 bytes; 944 = 0 compiles byte-identical to before. Console: export draws 8.44 -> 6.83 ms a frame; in-run A/B -2.1 ms on average (8 pairs). Renut translator output: any port with memexport. |
| 47 | `sasrt_gpu_export_list_topology` | **off** | 137 | Export point lists with the rasterizer off drawn as triangle or line lists. Same exports; slower (+0.9 ms). |
| 48 | `sasrt_gpu_export_no_point_gs` | on | 138 | An export draw recorded with the rasterizer off (decided once in DrawStateLocked before the key: `sasrt_export_discard`, which the discard also uses) that is a point list is built without the point-sprite geometry shader (`key.point_sprite = 0`, also on a reused chain key). Its vertex shader runs once a point either way: the same exports, no pixel either way; its vertex variant now gets constant 905 = 0 (no outputs). Console: in-run A/B -6.7 ms on average (10 pairs); export draws 6.83 -> 0.48 ms a frame; shadow cascades 9.09 -> 3.15 ms. |

Diagnostics (off by default): `sasrt_gpu_diag_export_order` (one frame's export draws, conversions, resolves and the
draws between them every N seconds), `sasrt_gpu_diag_profile_vs` (with `banjo_renut_diag_gpu_shaders`: depth-only draws
split by vertex shader, export draws by size, resolves by source size and format). Experiments (off; most change pixels):
`sasrt_gpu_exp_no_chain_waits`, `sasrt_gpu_exp_shadow_nofill`, `sasrt_gpu_exp_no_exports`, `sasrt_gpu_exp_shadow_d32f`,
`sasrt_gpu_exp_export_twice` (same pixels), `sasrt_gpu_exp_export_parts` (constant 945, pass `expparts`: 0 compiles
byte-identical), `sasrt_gpu_exp_sph_no_global_store` (plume `expSphStoreBits`).

Shader package and DKSH cache: passes `expwin` and `expparts` change the 21 memexport vertex shaders' texts, so their
variants were compiled again (`out/deko3d_shaders_ult/deko3d_shaders_r4c.bin`: the console's pipeline list of the first
item-48 run merged, 6,290 variants, 0 failed).

## Checked after the round (2026-11-09 02:45-03:10, console, the final build, shipping toml)

| Run | What | Result |
|---|---|---|
| r4p_sweep | in-run A/B of banjo's GPU-side switches: precise barriers (1), blend skip (8), depth-only (11), output trim (12), eager kicks (18), colour hand-over (73) | none costs time now (the first pairs carry pipeline compiles of the toggles; without them each is neutral or a gain) |
| r4q_ab11 | depth-only (11) alone, 31 pairs | median -0.17 ms on: keep |
| r4r_nozcull | `banjo_deko3d_zcull = false` | GPU 40.27 -> 42.74 ms: ZCull works, keep |
| r4s_copyres | `banjo_deko3d_draw_resolves = false` (copy engine) | resolves 4.89 -> 6.48 ms, GPU +1.6 ms: drawn resolves stay |

Not done: a host-order mirror of the exports (to drop the 0.7 ms stream conversion). The export windows are seeded with
guest bytes for the words the export draw does not write (interleaved vertex buffers), and a mirror would need those
seeds swapped per consumer element, which the export draw cannot know. A stream conversion drawn as a vertex pass
(no 3D/compute switch) was estimated at ~0.3 ms and left for later.

# Round 5 (2026-11-09, morning: "A393B1E0, much more efficient and close to pixel identical"; then 12 hours, 80 items)

The user's requests: the 1200x544 pass A393B1E0 much cheaper and close to pixel identical; then "15 more"; then "work
for 12 hours uninterrupted improving GPU performance, let's try to get to 80 total"; then "work on non-pixel identical
GPU cuts as well ... I'll determine what stays in at the end ... don't send non-pixel identical things to RR6"; then
"stuff other than dynamic resolution as well". So this round has two kinds of item: **identical** (pixel-identical by
construction or checked on the GPU; on) and **cuts** (they change pixels; each its own key, OFF, marked "CHANGES PIXELS"
in its description: the user picks). Every item is in-run A/B target 90 + its number unless it is decided when a target
is made (then a whole-run comparison of the profile's sections against a run with the same toml).

**Where it ended (2026-11-09 10:50, the user: "we can just leave it at 78 for now"):** items 0-78 over the five
rounds, 79 keys. In the shipping toml 49 are pixel-identical and on; 19 are cuts that change pixels, all off, for the
user to pick from (54-58, 61, 62, 64-67, 70-76, 78; the tables have each one's console saving; cut 58 is visibly bad);
11 are identical but off because the console measured them flat or slower (12, 14, 39, 40, 42, 44, 45, 47, 53, 59, 77;
53 is on in the code, off in the toml). Cut 61 turned out identical in the
race (run X) but stays off (gain unclear, split-screen unchecked). Outside the count: dynamic resolution (banjo's,
the user's ranges) with `sasrt_dynamic_cpu_aware`, and SMAA after the race-start composite too (found on the way).

## A393B1E0 is the game's EDRAM depth restore (not anisotropic filtering)

Round 3 guessed anisotropic filtering from its coordinates; wrong: all 256 of the game's samplers are made without
anisotropy, and `c255 = (40, -40, 0.5, 0.0125)`: the shader swaps the two 40-pixel halves of each 80-pixel tile column
(`fract(x / 80) >= 0.5`), the EDRAM tile layout of depth against colour. The G-buffer fills the EDRAM exactly (four
1200-pitch surfaces of 510 tiles: colour 0-2 and depth). The light pass puts its accumulation target at tile 0 and its
depth at tile 510 (colour 1's place), the composite its RGBA16F target over tiles 0-1019 and its depth at 1020 (colour
2's place). So the game restores the scene depth twice a frame: the depth resolve's words (an 8_8_8_8 view) drawn as
colour by A393B1E0 into colour 1 (then 2), the halves swapped, and that EDRAM bound as depth. Renut keeps a host target
per surface, so its restore (`sasrt_renut_depth_restore`, 2026-10-20) draws the colour back into the depth target
(`depth_restore_ps`). The console's profile (run J, item 49 off): **the two A393B1E0 draws cost 2.60 ms a frame**.

## The items

| # | Key | Kind | Default | A/B | Console | What |
|---|---|---|---|---|---|---|
| 49 | `sasrt_gpu_depth_restore_direct` | identical (GPU-checked) | **on** | 139 | **-1.35 ms** (run I, 8 pairs) | The copy draw (A393B1E0, with the checks in `SasrtRestoreCopyLocked`) is left out and the restore computes in one pass what the copy and the restore give a pixel: `depth_restore_direct.hlsli` samples the copy's own words view with its sampler, size and coordinates at the pixel `depth_restore_ps` reads (the other 40-pixel half), rounds the bytes as the RGBA8 target stores them and decodes as `depth_restore_ps`. The colour target is drawn (`restore_copy_ps`) before anything else uses it (both are, every frame, at the next G-buffer bind: cheap). **First form** (the resolve's float at the pixel): run G found 60 % of texels different (the copy point-samples the words at texel corners, `(x, y) / size`, which the hardware can take to the neighbour). **Fused form** (run I): `sasrt_gpu_diag_restore_verify 8`, the restored depth of the old chain against the fused one: 118 restores, 74 M texels, **0 differ**. |
| 50 | `sasrt_gpu_depth_restore_whole_clear` | identical | on | 140 | (with 49) | The restore cleared the stencil alone (no fast clear) before drawing every pixel's depth; when its rectangle is the whole target it clears depth and stencil together. |
| 51 | `sasrt_gpu_fetch_conversion_spec` | identical | on | 141 | **-3.30 ms** (run B) | A fetch's signs, gamma and exponent words (sampler bits 13-19, the 2D word's bits 20-25) as constants 950-957 (`PipelineKey::sasrt_words[12-15]`, list version 7, pass `fetchconv`): uam keeps only the conversions the draw's texture has. Unset: byte-identical DKSH. 9805DE9C 238 -> 167 TGSI, ED0A8D53 1072 -> 370. |
| 52 | `sasrt_gpu_fetch_exp_3d_spec` | identical | on | 142 | -0.64 ms (run B) | The same for the 3D and cube words' exponent (958-973, `sasrt_words[16-19]`): the composite's 3D lookup tables. |
| 53 | `sasrt_gpu_convert_vertex_pass` | identical | off | 143 | flat (+0.21, run D) | Exported stream conversions as a vertex pass (`stream_convert_vs`) instead of ~45 small dispatches. |
| 54 | `sasrt_gpu_cut_depth_alias` | **cut** | off | 144 | -0.37 ms (run F) | CHANGES PIXELS: the light and composite passes test against the G-buffer's own depth (unquantised), no restore. |
| 55 | `sasrt_gpu_cut_restore_copy_drop` | **cut** | off | 145 | flat (run F) | CHANGES PIXELS where the G-buffer leaves pixels: a restore copy left out is never drawn. |
| 56 | `sasrt_gpu_cut_mip_nearest` | **cut** | off | 146 | -0.86 ms (run F) | CHANGES PIXELS: trilinear textures sampled bilinear (the nearer mip level). |
| 57 | `sasrt_gpu_cut_lod_bias` | **cut** | off | 147 | flat (run F) | CHANGES PIXELS: mipmapped textures sampled half a level smaller. |
| 58 | `sasrt_gpu_cut_shadow_two_thirds` | **cut** | off | — | -0.5 ms (run N vs M: shadows -0.35, depth resolves -0.89, scene +0.58) | CHANGES PIXELS: the shadow maps at two thirds of their size. **Visibly bad**: the user saw the area around the car look glitchy in the loop (run N); the car's own shadow is a smeared blob there (run N's drive_137 against clean run Q's drive_135.4: crisp in Q). Not recommended. |
| 59 | `sasrt_gpu_shadow_uncompressed` | identical | off | — | **worse**: shadows +0.62, depth resolves -0.20 ms (run K vs J) | Shadow-map depth targets without hardware compression. |
| 60 | `sasrt_gpu_depth_restore_reuse` | identical | on | 150 | **-1.12 ms** (run B) | The composite's restore (the same resolve as the light pass's, its depth unchanged) binds the light pass's restored target, its stencil cleared. |
| 61 | `sasrt_gpu_cut_take_on_overwrite` | identical in the race (GPU-checked), kept off | off | 151 | -0.51 (K), -0.97 (L), -0.10 (R), +0.03 ms (X): unclear | A handed resolve keeps the image a full-screen post pass overwrites (needs item 45). **It never took before build r5o** (run J: 0 takes): `HandOverBeforeDrawLocked`, early in both draw paths, copied the resolve out first; now `SasrtPreTakeLocked` takes from the device's state before it, and the fast path hands those draws to the full path. `sasrt_gpu_diag_take_cover N` clears the new image to a sentinel and counts what the draw leaves: 7 / 19 texels of 143 M / 220 M (runs K, L), about what RGBA8 image pixels equal to the RGB sentinel by chance give; the check now compares four channels (an alpha images seldom have) and counts float and RGBA8 targets apart. | **Run X (sentinel (3, 251, 7, 3), a colour no race image has): 0 texels left of 324 M** (1,819 checked takes): the 6-26 of runs M-R were image pixels equal to the old sentinel, (51, 102, 153) being a sky blue (the first at 440,131, in the sky). Kept off: its gain is not clear across four runs, and it checks the scissor, not the viewport (a split-screen post pass drawn into half the target by its viewport alone is not checked).
| 62 | `sasrt_gpu_cut_gather_pcf` | **cut** (may change) | off | 152 | -0.75 ms (run E) | MAY CHANGE PIXELS at exact texel edges: four point shadow taps half a texel around one place as one gather (976, pass `gatherpcf`). |
| 63 | `sasrt_gpu_depth_restore_clear_skip` | identical | on | 153 | **-0.96 ms** (run E); -0.27 median with 49 fused (run X, 8 pairs) | The direct restore clears to the scene's clear depth (0 or 1, exact in 24 bits) and discards the pixels at it: they keep the fast clear. |
| 64 | `sasrt_gpu_cut_ssao_off` | **cut** | off | 154 | **-1.93 ms** (run E) | CHANGES PIXELS: no ambient occlusion (the SSAO draw is a clear to white). |
| 65 | `sasrt_gpu_cut_pcf_half` | **cut** | off | 155 | flat (run H) | CHANGES PIXELS: the shadow filter 9041AFF6 averages 4 of its 8 bilinear PCF places (977, pass `pcfhalf`; 64 -> 39 registers): its cost is not its fetches. |
| 66 | `sasrt_gpu_cut_no_aa` | **cut** | off | 156 | **-1.66 ms** (run H) | CHANGES PIXELS: no anti-aliasing (SMAA not run; the game's FXAA pass stays its centre sample). |
| 67 | `sasrt_gpu_cut_shadow_alpha_casters` | **cut** | off | 157 | flat (run H) | CHANGES PIXELS: the shadow maps' alpha-tested casters (3ECDED03, ~21 draws a frame) not drawn. |
| 68 | `sasrt_gpu_shadow_d32f` | identical | **on** | — | shadows -0.15, depth resolves -0.11 ms (run L vs J) | The shadow maps (square 512-2048 depth) as D32F: SASRT's depth is the 20e4 float format, so every depth target is ZF32_X24S8 (8 bytes a pixel); the casters use no stencil (no `[sasrt] stencil on a depth target without stencil` in run L). Round 2's experiment `sasrt_gpu_exp_shadow_d32f` made an item. |

Re-measured on the way (run I, at their defaults): item 12 (tiled caching) -0.73 ms median, noisy (stays off); item 13
(the luminance readback on compute) -1.48 ms on (stays on; run G's +0.99 had tiled caching on all run); item 14 (lazy
depth decompression) flat (stays off). Item 45 (colour hand-over with SMAA): +0.97 / +0.83 ms (runs K, L): stays off.

| 69 | `sasrt_gpu_skip_copy_back` | identical (GPU-checked) | **on** | 159 | **-1.22 ms** (run R, 9 pairs; ~45 copies skipped a second) | The post chain's copy shaders 50544D63 and BA4853E3 copy a texture that is a whole resolve of the same 1152x544 RGBA16F target with nothing written to the target since (the post-chain map, run O: "THIS target, unchanged"): they write what the target holds. Left out when that holds (colour resolves now record their source, as depth resolves did); a later resolve of the unchanged target into the same texture is then skipped too (banjo_renut_resolve_skip). `sasrt_gpu_diag_copy_back_verify 4` (run O): 5,050 such copies drawn anyway and the target compared with the texture after: 3.16 G texels, **0 differ**. |
| 70 | `sasrt_gpu_cut_far_cascade` | **cut** | off | 160 | **-1.93 ms** (run O, 14 pairs) | CHANGES PIXELS: the far shadow cascade (the third 1024x1024 map, atlas y 2048) not drawn (its casters; memory-export draws still run): no shadows in its range. The cascade order comes from the atlas resolves (cascade = destination y / 1024). |
| 71 | `sasrt_gpu_cut_far_cascade_half_rate` | **cut** | off | 161 | -0.46 ms (run P, 22 pairs) | CHANGES PIXELS: the far cascade drawn and resolved every other frame (the atlas keeps the last): far shadows move at half rate. Fewer frames skipped than expected (14-37 per 10 s). |
| 73 | `sasrt_gpu_cut_smaa_low` | **cut** | off | 163 | -0.82 ms (run S, 14 pairs) | CHANGES PIXELS: SMAA finds edges at its low preset's threshold (0.15 instead of 0.1): fewer edges smoothed (softer steps between similar colours stay aliased). |
| 74 | `sasrt_gpu_cut_ssao_half_rate` | **cut** | off | 164 | **worse** (+0.47 ms, run S) | CHANGES PIXELS: SSAO and its blur every other frame, their resolves left out on the others (the composite reuses the last AO). Does not pay. |
| 75 | `sasrt_gpu_cut_shadows_off` | **cut** | off | 165 | **-2.51 ms** (run T, 5 pairs) | CHANGES PIXELS: no shadows: no caster drawn into any shadow map (memory-export draws still run); the maps keep their clear, so the light pass sees everything lit. |
| 76 | `sasrt_gpu_cut_point_lights_off` | **cut** | off | 166 | -0.96 ms (run T, 4 pairs) | CHANGES PIXELS: no point lights: in the light pass, the draws into the light target after the sun's (9041AFF6) are left out until the targets change: each point light's two stencil-volume draws (VS 98B53A18) and its light draw. The sun and the ambient stay. |
| 77 | `sasrt_gpu_shadow_atlas_direct` | identical | off | 167 | **worse**: +0.45 ms (run W, 21 pairs without one outlier; median +0.40) | The three shadow cascades drawn straight into their slices of the 1024x3072 atlas: the atlas is made uncompressed, and three D32F depth images are made over its memory (plume `Deko3DCreateAliasTexture`: the same block-linear rows, 128-row tiles, 4 MB a slice). At each cascade's whole clear the shadow target takes the next slice's image (the order learnt from the resolves); the resolve into that slice is then left out (a read barrier instead). A different order: the resolve copies as before. The cascade resolves cost 2.13 ms (run U's split label); the shadow maps' depth becomes uncompressed (item 59's +0.6 ms). `sasrt_gpu_diag_atlas_verify N`: the depth as the resolve reads it against the slice's float bits. | **Run W:** the shadow casters' cost rose with the depth uncompressed (D44C3E58 1.35 -> 1.67 ms with the item on half the time), and the in-place cascades' barrier (their writes before the atlas's reads) shows as 0.86 ms on the resolve label: the copies saved are given back. Its check read 0 differ for its first 47 cascades, then differences once the A/B began switching it (the check's depth view most likely a stale descriptor after the slice images swap back; not followed further, the item being slower).
| 78 | `sasrt_gpu_cut_ambient_sky` | **cut** | off | 168 | flat (run X: median -0.21, mean +0.07 without one outlier, 10 pairs) | CHANGES PIXELS where the sky's ambient term shows: the HDR composite's full-screen additive pass ED0A8D53 (~1.5 ms; three volume-texture lookups a pixel, 47 registers, no depth or stencil test) drawn with the depth bounds test (`plume::Deko3DSetDepthBounds`, dkCmdBufSetDepthBounds) excluding the clear depth of the restored scene depth bound to it (0 or 1, known at the restore and exact there), so the sky's pixels (~40 % of a race frame) are not shaded. The sun's and the point lights' passes skip the sky already (their stencil test). Identical only if a later pass replaces the sky's pixels (not checked). | It took (~23 draws a second), but saves nothing measurable: most likely the depth bounds test runs after the shader here (the pass has a discard and no depth test of its own), so the sky's pixels are still shaded. Does not pay: off.
| 72 | `sasrt_gpu_cut_bloom_off` | **cut** | off | 162 | -0.54 ms (run R, 8 pairs) | CHANGES PIXELS: no bloom: the 160x68 blurs (0EFBCCD0, 4404297A, 8C086C29) cleared to black; the composite 2414CA96 adds their result (fetch 1, B5642CA8). The 288x136 bright pass 27759BE0 stays: the luminance chain (AC15549E..., the 1x1 the CPU reads for exposure) starts from it too (the post-chain map, run O). |

## Dynamic resolution (the user, 10:00: "add dynamic resolution, handheld 480p to 720p, docked 540p to 1080p, just take banjo's")

Banjo's `banjo_renut_dynamic_resolution` is on in `sasrt_switch.toml`: handheld 477 (480 rounded to a multiple of 9) 540
576 612 684 720, docked 540 648 756 864 972 1080 (the swapchain and the HUD at 1920x1080 docked), by the GPU's time a
frame against 34.5 ms (down at once, up after 1 s of fitting). Three changes were needed:

- Banjo's code wanted 720 at one end of each range; on deko3d any height has a scale code (`CodeForHeightLocked`), so a
  range without it now starts at its step nearest below 720 (docked 540-1080 starts at 648).
- **SASRT's EDRAM depth restore was wrong at any scale but 1x**: `depth_restore_ps` swaps the 40-pixel halves of the
  tile columns in host pixels, the game's copy (A393B1E0) in guest pixels (40 x the scale), so half the columns would
  get their depth from 40 x (scale - 1) pixels away. At a scale other than 1x the copy is now only recorded and the light
  pass and the composite test against the G-buffer's own depth (item 54's alias, exact at every scale); item 69 (verified
  at 1x) stays at 1x.
- (item 78, `sasrt_dynamic_cpu_aware`, on) The user's own race (10:05, handheld) showed it: the render thread took 33-50
  ms a frame and the GPU 28-30 ms at 612 lines (37 at 720), so the race ran at 18-25 fps whatever the height, and the
  dynamic resolution had given up lines for nothing. The budget is now the larger of 34.5 ms and the CPU side's time a
  frame (the render thread's or the game thread's, moving averages): the height steps down only when the GPU is what
  holds the frame.

Run V (`banjo_renut_dynamic_test_s 6`: a step every 6 s): every handheld step looks right.

The user watched run N live: "the area around the car looked a bit glitchy" in the loop. Clean run Q (the shipping
defaults, every cut off, a screenshot every 0.6 s through the loop) looks right; N's frame shows the car's own shadow
smeared: cut 58. Marked visibly bad above.

## Found on the way

- **SMAA started a few seconds into the race** (the user, 2026-11-09 10:45: "anti-aliasing only pops up a couple of
  seconds after the race starts"): the menus and the race's first seconds draw the composite without bloom,
  670FBDA9D99C678B (the same tonemap and grading, one target), and the race switches to 2414CA96 a few seconds in (run
  W's profile). SMAA ran only after 2414CA96 while the game's FXAA pass is its centre sample (sasrt_smaa_replaces_fxaa),
  so those frames had no anti-aliasing at all. `banjo_renut_smaa_after_ps` now lists both (app/sasrt_switch.toml).

- **The variant cache tool read the pipeline list 4 bytes off** since round 1 (`fetch_types` from 192 instead of 188,
  `tess_kind` 208/204, the plain-fetch word 212/208, the sasrt words 216/212): every specialised variant got 926 and
  932-944 from the next word; the console compiled what it drew and the SD cache kept it. Fixed (list version 7).
- **Depth hand-over never applies in SASRT** (the resolve-kind lines): the three cascades resolve into one 1024x3072
  atlas at y 0 / 1024 / 2048 (not whole), and the scene depth's words are read (the restore).
- **With SMAA on, banjo's colour hand-over is off entirely**; 14 colour resolves a frame are "part of a target into
  another size" (the 1200-pitch G-buffer surfaces into 1152-wide textures, the bloom and luminance chains).
- The light pass's no-pixel-shader draws (VS 98B53A18, 1.9 ms) are the deferred lights' stencil volumes, two a light.
- Why the post chain copies its own resolves back (item 69): on the 360 every post pass renders at EDRAM base 0 (the
  1152x544 image, the 576x272 SSAO, the 288x136 and 160x68 bloom targets, the 64x64 luminance chain all at 831C385C), so
  each half-size pass overwrites the full-size image and the game copies it back from its resolve. Renut keeps a host
  surface per size and format, so the image is still there: the copy writes what it holds.
- The shadow filter 9041AFF6 (1.9 ms) already has plain fetches in the race (926 = 0x80000007); 59 registers; the
  32-register cap was slower in round 3.

## Diagnostics added (off)

`sasrt_gpu_diag_restore_verify N` (the restore checks above), `sasrt_gpu_diag_gbuffer_cover` (texels at the clear depth
after the G-buffer: ~40 % in the race), `sasrt_gpu_diag_take_cover N` (cut 61), `sasrt_gpu_diag_copy_back` (the post
chain's copies: their texture and whether it is a resolve of the same unchanged target), and one-time `[sasrt depth
resolve]` / `[sasrt colour resolve]` lines for each kind of resolve drawn rather than left in an image.

## Console runs (2026-11-09, stock clocks, the race from the start line, 200 s, in-run A/B)

| Run | NRO | What |
|---|---|---|
| B, D | r5a-r5i | items 49-53, 60 (51 -3.30, 52 -0.64, 60 -1.12, 49 first form ~-0.6) |
| E | r5j | 49 first form, 63, cuts 61, 62, 64; the verify (its depth readback inconclusive) |
| F | r5j | cuts 54-57 |
| G | r5k | items 13, 14; the verify's math check: **49's first form differs on 60 % of texels** |
| H | r5l | cuts 65-67; resolve trace and draw log (the post chain) |
| I | r5m | **49 fused: 0 of 74 M texels differ, -1.35 ms**; items 12-14 at their defaults |
| J | r5n | cut 61 with the coverage check: 0 takes (the bug above) |
| K | r5o | cut 61 fixed; item 59 (worse) |
| L | r5p | item 68 (D32F shadows) |
| M | r5s | cut 61's coverage check v2 (6 texels of 277 M, RGBA8 only); the post-chain map (empty: textures looked up wrong); item 12 again (+0.62: off) |
| N | r5t | cut 58 (shadow maps 2/3): -0.5 ms; **the user saw the artifact around the car** |
| Q | r5u | clean shipping defaults, dense screenshots through the loop: right |
| O | r5u | cut 70 -1.93 ms; **item 69's check: 5,050 copies, 0 texels differ**; the post-chain map |
| P | r5u | cut 71 -0.46 ms |
| S | r5x | cut 73 -0.82 ms, cut 74 +0.47 (worse) |
| T | r5y | cut 75 -2.51 ms, cut 76 -0.96; the barrier census (per frame: ~80 fragment barriers for reads, ~77 vertex-stage ones for buffers: the skinning export chains) |
| U | r5z | item 69 -1.24 ms again; cut 73 flat (-0.02); the split profile: cascade resolves 2.13 ms, scene depth 0.54, the fused restore draw 1.02 |
| W | r6c | item 77: +0.45 ms (worse: off); its check differs once the A/B switches it |
| X | r6d | **cut 61's coverage: 0 of 324 M texels** (new sentinel); 61 +0.03 ms, item 63 -0.27, cut 78 flat |
| R | r5w | item 69 -1.22 ms; cut 72 -0.54; cut 61 -0.10 (10 pairs; its check: 26 texels of 340 M, the first at 440,131 of a 1152x544 RGBA8 target: inside the image, so most likely chance matches, but not proven) |

RR6's handoff (identical items 51, 52 and the tool fix only): docs/handoff/gpu_round5_1109.
