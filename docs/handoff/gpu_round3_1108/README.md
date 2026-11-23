# SASRT GPU round 3: batch 1 for RR6 and the ultimate base (2026-11-08, 21:50)

Console-confirmed in SASRT's race (stock clocks, the same session, 200 s from the start line):

| | Round 3 off (`configs`: round 3 keys false) | Round 3 kept set, run 1 | Run 2 |
|---|---|---|---|
| GPU ms a frame | 50.14 | 47.10 | 46.59 |
| fps | 19.89 | 20.96 | 20.78 |
| Shadow cascades (1024x1024 depth) | 11.58 | 9.83 | 9.73 |
| G-buffer and lights (1152x544 colour + depth) | 20.39 | 19.38 | 18.97 |
| Waits for idle / fragment barriers / texture drops a frame | 104 / 96 / 108 | 69 / 71 / 74 | |

About -3.3 ms of GPU time a frame together; no per-item console numbers (the in-run A/B of the tracking items is not
safe in the build those runs used; it is now). Pixel-identical by construction; screenshots of every run looked
right (menus, race, skinned driver, boat transform, shadows, water).

`files/` holds this tree's final versions of every file the round touched: diff them against your copies. Every hunk
is marked `sasrt-nx (2026-11-08, <key>` or "the third GPU round". docs/gpu-round-1108.md "Round 3" has the full text.

## The items (send these)

| # | Key (default) | Generic? | Optimiser / DKSH? | Where | What |
|---|---|---|---|---|---|
| 30 | `sasrt_gpu_seed_cpu_direct` (on) | Renut | no | draw.cpp `SasrtSeedExportsCpuLocked`, `SasrtSeedExportsComputeLocked`, `PrepareMemExportLocked` | memexport seeds written by the CPU straight into the fresh export windows (plume deko3d buffers are CPU-uncached and mapped): no copy dispatch, no wait before the export draw (kept when an export of the same list has had no buffer wait since). Needs round 1's `sasrt_gpu_fetch_copy_compute` path. |
| 31 | `sasrt_gpu_convert_tail_no_texture_drop` (on) | Renut | no | draw.cpp, the conversion's tail barrier | the wait after a stream conversion keeps the texture cache (the converted stream is written past everything the frame touched) |
| 33 | `sasrt_gpu_export_no_pixel_shader` (on) | Renut | no (new VS variants: 905 = 0) | draw.cpp after `DrawsWithoutPixelShader` | export-only draws (rasterizer off, round 2's item 29) built without their pixel shader. Needs vivapinata's `ContainerIsExportOnly` (d3d/hooks/shader.cpp) |
| 34 | `sasrt_gpu_vs_screen_space_spec` (on) | Renut + optimiser | **yes**: pass `vsepi`, constant 932 | draw.cpp `SasrtSpecWordsOf`, pipeline.cpp | the vertex epilogue's screen-space test as a constant of the draw |
| 35 | `sasrt_gpu_vs_depth_remap_spec` (on) | Renut + optimiser | **yes** (932) | same | the epilogue's depth remap test (never on deko3d) |
| 36 | `sasrt_gpu_stacked_3d_spec` (on) | Renut + optimiser | **yes**: pass `stack3d`, 934 | same | a 3D fetch's stacked/volume choice as a constant |
| 37 | `sasrt_gpu_stacked_filter_spec` (on) | Renut + optimiser | **yes** (935, 936) | same | its layer filter and Z wrap |
| 38 | `sasrt_gpu_fetch_endian_spec` (on) | Renut translator output + optimiser | **yes**: pass `fetchendian`, 937-939 | same | vfetchMemory's byte order as constants (one swap a word instead of four and three selects) |
| 41 | `sasrt_gpu_export_format_spec` (on) | Renut translator output + optimiser | **yes**: pass `expfmt`, 940-943 | draw.cpp `SasrtExportFormatWords` | a memexport's format word (eA.z) as a constant: the format switch folds (the skinning export shader 18.4 -> 12.0 KB). Only zero or normal-float z words; the literal if the shader defines the register; NaN-flushed as the upload does |
| 43 | `sasrt_gpu_target_wait_tracked` (on) | plume | no | plume_deko3d_commands.cpp `barriers()`, `markSampled`, `markUsed`, `emitBarrier` | a barrier that only moves textures into target layouts is skipped when none was sampled, copied, resolved or decompressed since the last fragment wait (~65 a frame). Marks are kept whatever the options. |

Infrastructure the items need (generic):
- `PipelineKey::sasrt_words[12]` (render/pipeline.h), **pipeline list version 6** (v3-5 lists converted with the words 0);
  `Specialised()` / the generic fallback / the prebuild's key filter know the words.
- `SasrtSpecWordsOf` (render/draw.cpp) at the four key sites (fast path, its verify, full path, chain-reuse verify).
- The round's item tables to 64 (`sasrt_gpu_round.h`, plume `Deko3DStats::sasrtRound[64]`); `banjo_renut_ab_targets` up to 255
  (banjo_renut_tuning.cpp).
- tools/deko3d_variant_cache.py: list v6, the words to constants, `--sasrt-guess` (adds 932 = 5 to every listed pipeline
  for a cache made before any v6 list exists; the values are SASRT's race draws', generic enough: no screen-space, no
  depth remap).
- Diagnostics: `sasrt_gpu_diag_export_dupes` also counts repeats without the window addresses and the export draws by
  primitive (SASRT: 0 repeats, point lists of ~1,370 vertices).

## Do not port (tested, failed)

| # | Key | Why |
|---|---|---|
| 39, 40 | `sasrt_gpu_gpr_cap`, `sasrt_gpu_gpr_cap_filter` (off) | 32-register caps (constant 910) on 364C/F646/92D1 and 9041: the G-buffer pass 23.7 ms with them, 19.4 without. Spills cost more than occupancy gave. |
| 42 | `sasrt_gpu_texture_drop_tracked` (off) | Skipping the texture-cache drop on read moves of textures not sampled since the last drop: **broke the picture** (menu scene washed white). Compressed render targets need the drop after rendering whatever was sampled before. Worth knowing for any similar idea. |
| 44 | `sasrt_gpu_read_wait_tracked` (off) | only acts with 42. |
| 32 | `sasrt_gpu_vs_input_mask` (on, inert) | correct (unused vertex attributes bound as constants from the SPH input map), but SASRT's race never had one to drop: untested benefit. Port only if you want it; RR6 may have some. |

## Traps found
- `sasrt_deko3d_diag_barriers` together with `banjo_renut_diag_gpu_shaders` hung SASRT at its first scene once (GPU idle,
  a core spinning); either alone is fine.
- Test keys in a toml: top level only (your note); SASRT's tomls have no tables.
- After any optimiser change: rebuild the shader package and the DKSH cache (every vertex shader's text changes with
  `vsepi`).
