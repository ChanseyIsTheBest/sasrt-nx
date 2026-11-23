# SASRT GPU round 4: batch for RR6 and the ultimate base (2026-11-09, 02:20)

Console-confirmed in SASRT's race (stock clocks, the same session, 200 s from the start line), pixel-identical:

| | Round 3 as kept (r3_ship) | Round 4 as kept (r4_ship) |
|---|---|---|
| fps | 20.78 | **23.59** |
| GPU ms a frame | 46.59 | **38.79** |
| render thread ms a frame | 32.09 | 29.36 |
| shadow cascades (profile) | 9.77 | 3.15 |
| skinning export draws (profile) | 8.44 | 0.48 |

`files/` holds this tree's final versions of every file the round touched: diff them against the round-3 batch
(`docs/handoff/gpu_round3_1108/files/`). Every hunk is marked `sasrt-nx (2026-11-08` or `(2026-11-09`, with its key.
docs/gpu-round-1108.md "Round 4" has the full account (how each was found, every console run).

## Port these

| # | Key (default) | A/B | Generic? | Optimiser / DKSH? | Where | What |
|---|---|---|---|---|---|---|
| 48 | `sasrt_gpu_export_no_point_gs` (on) | 138 | Renut | no (the export vertex variants get 905 = 0) | render/draw.cpp DrawStateLocked: `sasrt_export_discard` / `sasrt_no_point_gs` before the key, `key.point_sprite` after it, the discard block uses the same decision | Renut gives every Xenos point list `key.point_sprite = 1` (MakeKey), so the point-sprite geometry shader also ran for memexport draws recorded with the rasterizer off: a quad for every skinned point for a rasterizer that is off. Those draws are now built without it. The vertex shader runs once a point either way, so the exports are the same, and no pixel either way. SASRT: -6.7 ms GPU a frame (in-run A/B, 10 pairs). Inert where no point-list memexport draw exists (RR6). |
| 46 | `sasrt_gpu_export_window_ubo` (on) | 136 | Renut translator output | **yes**: pass `expwin`, constant 944 from `sasrt_words[7]` bit 2 (memexport vertex shaders only) | render/draw.cpp `SasrtSpecWordsOf`, render/pipeline.cpp, tools/deko3d_glsl_opt.py, tools/deko3d_variant_cache.py (944 from the word; `--sasrt-guess` adds 944 = 1) | Renut's memexport window search loops over a local `uvec4 _N[4]` copy of SharedConstants 61-64 indexed at run time (local memory); with 944 = 1 it reads `g_UboShared.v[61u + min(i, 3u)]`. Same words. 944 = 0 compiles byte-identical. SASRT: export draws 8.44 -> 6.83 ms a frame, in-run A/B -2.1 ms. |

Infrastructure: `render/pipeline.cpp`'s spec array grew to 300 entries (the round's constants 932-945 with 256 bools
could pass 280). `banjo_renut_ab_targets` items 135-140 are this round's.

## Do not port as items (off; kept for the record)

| # | Key | Why |
|---|---|---|
| 45 | `sasrt_gpu_handover_with_smaa` (off) | banjo's colour hand-over with SMAA: correct, but flat in the race (90 % of the handed resolves are drawn later anyway). |
| 47 | `sasrt_gpu_export_list_topology` (off) | export point lists as triangle/line lists: slower (+0.9 ms). plume `Deko3DSetNextPrimitive` stays (unused). |

## Diagnostics and experiments (off by default; port if useful)

- `sasrt_gpu_diag_export_order` (int seconds): one frame's export draws, conversions (with their waits), resolves and
  draws between them as one token line. It showed SASRT skins and draws one mesh at a time.
- `sasrt_gpu_diag_profile_vs` (with `banjo_renut_diag_gpu_shaders`): depth-only draws by vertex shader, memexport draws by
  vertex count, resolves by source size and format. This is how the 120 ns a point showed up.
- `sasrt_gpu_exp_export_twice` (same pixels: every memexport draw twice) measures what export draws really cost.
- `sasrt_gpu_exp_export_parts` (constant 945, pass `expparts`, 945 = 0 byte-identical), `sasrt_gpu_exp_sph_no_global_store`
  (plume `expSphStoreBits`), `sasrt_gpu_exp_no_chain_waits`, `sasrt_gpu_exp_shadow_nofill`, `sasrt_gpu_exp_no_exports`:
  change pixels, measurements only.

## Findings worth knowing in any port

- Removing 35 of 68 waits for idle a frame (exp_nowaits) changed the GPU time by 0.0 ms: on this GPU the passes' own work
  sets the frame time, not the waits between them.
- uam already leaves unwritten vertex outputs out of the program header: undeclaring unread outputs compiles to a
  byte-identical program.
- A Profile label's time can hide fixed-function work: the export draws cost the same with an empty vertex shader.
  Drawing the suspect twice (same bytes) is a clean way to measure a draw's real cost.

After the optimiser change: rebuild the shader package and the DKSH cache (the memexport vertex shaders' texts change).
