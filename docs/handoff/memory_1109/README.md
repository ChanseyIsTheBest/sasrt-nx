# SASRT memory round: batch for RR6 / the ultimate base (2026-11-09 night to 2026-11-10)

The user: "once we test that all new memory management changes are good and effective ... send them to RR6 and for the
ultimate base", and "15-20 more memory management improvements would help as they could go into the base as well".
Every item gives the same pixels (none changes a draw's result); each has its own key. The full write-up, with the
console runs behind each item, is `docs/render-thread-round-1109.md` (sections from "Memory: idle render-target sets
released" on). `files/` holds the changed files whole (SASRT's tree as of the last tested build); the base has none
of these items (checked 2026-11-09 22:55 against `D:\renut-ultimate\base`).

**Also in this batch, a correctness fix (not memory): the chain reuse's pipeline shortcut** (draw.cpp, `PipelineReuse
preuse`; RR6's diagnosis). It handed back the previous draw's pipeline without comparing the key's per-draw words
(`sasrt_words`, `fetch_pad`, the clip bit in `reserved`, `point_sprite`): with GPU item 38 (`sasrt_gpu_fetch_endian_spec`)
the Ocean View octopus came apart under a heavy GPU. Fixed and confirmed on the console (run octo_fix38). Any port with
item 38, 41 or the other `sasrt_words` specialisations wants it.

## Console results (docked, max clocks, Ocean View; the heap is 3,083 MB)

| Run | Build | Heap CPU side in use | Free (heap room + GPU region free) | Notes |
|---|---|---|---|---|
| docked_1, docked_gov | before | crashed at the race load | 0 / CPU side out | the two crashes that started this |
| mem12 | rounds 1-2 | 1,526 MB | ~100-800 MB | first docked run without a crash; one near-miss (35 MB) at a results screen |
| mem13 | + round 3 | 1,168 MB | 600-1,100 MB | stacks 4 MB, range cache off |
| mem14 | + round 4 | 1,080 MB | ~700-800 MB in the race | command buffers 247 -> ~120 MB; the GPU hung at 150 s (M35, now off) |
| hang_A, hang_B | round 4, M35 off | 1,080 MB | ~700-800 MB | two clean races, normal closes |
| mem16 | final (M35 off by default) | 1,220 MB after both races | ~800 MB | Ocean View to its end, the map, Dragon Canyon: 0 fence timeouts, normal close (the batch's files/) |

## The items (key, default, what, where)

Round 1 (the governor; SASRT app code unless noted)

| Item | Key | What |
|---|---|---|
| M1 | `sasrt_memory_governor` (on), `sasrt_memory_low_mb` 256, `sasrt_memory_critical_mb` 128 | a look at free memory (heap room + GPU region free) every 10 frames: under low no dynamic-resolution step up, stream cache capped at 96 MB, idle targets sooner; under critical a step down and the cache at 48 MB |
| M2 | (plume) `Deko3DRegionGiveBack` | the GPU region's free bottom back to newlib on request (the governor below 192 MB of room; the command buffers' arena before it gives up) |
| M3 | `sasrt_dedicated_targets` (on) | render/depth targets >= 1 MB in their own chunk, freed to the region at once |
| M4 | (plume) `Deko3DReleaseEmptyImageChunks` | empty image chunks back while low |
| M5 | `sasrt_retire_idle_targets_frames` 300 | targets of another scale than the 3D's and the HUD's released after 300 frames unused |
| M6 | (SDK) `TrimRangeCache` | the I/O range cache trimmed on request |
| M7 | (tuning) | upload ring chunks of a heavy frame at the next reset while low |
| M8 | (tuning) | prebuilt pipelines unused 10 s go while low |
| M9 | (command_buffers) | arenas give back more while low |
| M10 | (plume) `kRegionGiveBackAt` 32 MB, `kRegionKeep` 16 MB | the region gives its bottom back sooner (128/64) |
| M11 | (surfaces) | current-scale targets after 900 frames while low |

Round 2

| Item | Key | What |
|---|---|---|
| M12 | (SDK switch_perf) | the profiler's thread lines give each thread's deepest sampled stack |
| M13 | (SDK) `switch_guest_stack_mb` (16; SASRT's toml 4) | a guest thread's host stack size (SASRT's deepest sampled: 55 KB in 15 minutes); smaller sizes pooled too |
| M14 | (SDK) `RexSwitchReleaseSpareStacks` | kept stacks back while low |
| M15 | `switch_thread_stack_pool` 8 (toml) | at most 8 kept stacks |
| M16 | (textures) | cold textures released while low whatever the driver budget says |
| M17 | (plume) `ImageChunkSize` 32 MB | (64) |
| M18 | (draw) | stream cache copies unread for 60 frames dropped while critical |

Round 3

| Item | Key | What |
|---|---|---|
| M19 | (plume) `Deko3DHeapRoomBytes` | the governor's look in O(1): it called `mallinfo` (7-21 ms under malloc's lock, once a second) |
| M20 | (surfaces) | the look every 10 frames |
| M21 | `switch_guest_stack_mb` 4 (SASRT toml) | ~370 MB back |
| M22 | `masseffect_io_ranges_mb` 0 (SASRT toml) | 0 hits in SASRT |
| M23 | (SDK) `rex_io_ranges_auto_off_mb` 128 | the range cache switches itself off after 128 MB stored with no hit |
| M24 | `sasrt_retire_stale_sets` (on), `sasrt_retire_stale_frames` 8 | at most two 3D target sets: the previous scale's keeps 300 frames, any other goes after 8 |
| M25 | (surfaces) | idle targets checked every 10 frames |
| M26 | `sasrt_dynamic_up_memory` (on) | a dynamic-resolution step up only if its target set fits above the low mark |
| M27 | `sasrt_memory_emergency` (on), (plume) `Deko3DTakeMemoryEmergency` | a texture/block plume could not make: the next frame frees what it can and steps down at once |
| M28 | `sasrt_region_best_fit` (on), (plume) `Deko3DSetRegionBestFit` | the GPU region's best fit (host test `tools/test_gpu_region_bestfit.cpp`: largest free range 118 -> 190 MB) |
| M29 | (surfaces) | range-cache trim at the low mark |
| M30 | (memory_report, SDK) `RexSwitchStackFigures` | a `Memory: CPU:` line (stacks, range cache, command buffers used/capacity) |

Round 4

| Item | Key | What |
|---|---|---|
| M31 | (draw) | the upload ring's frame cap 48 MB while low |
| M32 | `sasrt_image_best_fit` (on), (plume) `Deko3DSetImageBestFit` | best fit across the image heap's chunks |
| M33 | `sasrt_retire_stale_sets` | the previous 3D set stale too while low |
| M34 | `sasrt_retire_current_idle_frames` 1800 | the 3D's/HUD's own scale's targets after a minute unused |
| M35 | `sasrt_texture_long_idle_frames` **0 (off)** | textures no draw bound for a minute go whatever the budget. **Do not turn on: with 1800 every docked race hung the GPU (3 of 3; off: 0 of 2). Root cause not found; `EvictColdTexturesLocked` (pressure only) releases through the same `ReleaseHostTextureLocked`: suspect it under pressure too.** With M35 on, 4 of 5 races hung (M32 on or off); off, 4 of 4 clean. |
| M36 | (smaa) | SMAA tried again 60 frames after its textures could not be made (it went off for the session) |
| M37 | (SDK guest_memory_switch, memory_report) `RexGmDecommitFigures` | a `Memory: guest:` line (SASRT: 534 MB, never a decommit). **Touches guest_memory_switch.cpp/.h (diagnostic only): diff against the base main 262f9e5afe** |
| M38 | `sasrt_cmdbuf_trim_ended` (on) | a recording's slack cut when the game ends it (247 -> ~120 MB) |
| M42 | `sasrt_cmdbuf_trim_percent` (300; SASRT toml 150), `sasrt_cmdbuf_trim_slack_kb` (1024; SASRT 256) | M38's thresholds as keys; tightened in SASRT: capacity ~120 -> 32-70 MB, the same frame times (run mem17). Needs M38 (left out of the base) |
| M39 | SASRT toml: `banjo_renut_prebuild_release_s` 60, `banjo_renut_upload_trim_frames` 300, `sasrt_renut_ring_frame_cap_mb` 64 | load-time memory back sooner |
| M40 | `sasrt_spare_stacks_idle_s` 60, (SDK) `RexSwitchStacksTaken` | kept stacks back after a minute with no thread made |
| M41 | `sasrt_stream_cache_drain` (on) | the stream cache pool's sparsest chunk drained (mem14: 104-146 MB of copies in 288 MB). First run (mem15): one chunk back, the pool refilled to 288 MB (copies spread with small holes): harmless, weak |

## What to port

Everything above is generic to the Renut/deko3d tree except the toml values (SASRT's measurements: a port measures
its own stack depth with M12 before lowering `switch_guest_stack_mb`, and its own range-cache hits). The SDK items
(M6, M12-M14, M23, M30, M37, M40) are in `sdk/`; the plume ones in `app/thirdparty/plume/`.
