# Dynamic-resolution step stutters: the target-block cache (sasrt-nx, 2026-11-11), for the ultimate base

## The problem (console, handheld 1020/460.8/1600, race, dynamic resolution 648-720 lines)

Each dynamic-resolution step cost **one render-thread frame of 80-130 ms plus one or two of ~60 ms**. The slow-frame
log (below) showed it was all render-thread work, not waits: the step's new code builds ~16 render targets and ~17
resolve textures, each a *dedicated* deko3d memory block since the 2026-11-09 memory round (`sasrt_dedicated_targets`:
an nvmap of its own and four GPU mappings, ~2.5 ms each in the driver), and two frames later the old code's ~33 blocks
are destroyed (unmap + nvmap free, the ~60 ms frames). The profile's libnx counters agree: windows with steps showed
~280-400 ms of nvMapCreate + MapBufferEx per 10 s. In run slow2, 55 of the driven race's 60 frames over 60 ms came right
after a step (33 steps in ~205 s).

## The fix (plume + one key)

An emptied dedicated target chunk keeps its block in a capped cache instead of destroying it; a new dedicated target
takes a cached block of its size or up to an eighth bigger (the smallest such), else makes one.

- `plume::Deko3DSetTargetBlockCacheMb(mb)` (plume_deko3d.h/.cpp): `Deko3DDevice::targetCache` (heapMutex),
  `cacheTargetBlockLocked` (oldest evicted over the cap), `takeCachedTargetBlockLocked`, `releaseTargetCacheLocked`;
  `imageAlloc`'s dedicated path tries the cache first; `collectRetired` caches an emptied dedicated chunk's block;
  **`releaseEmptyChunksLocked` releases the cache too**, so the memory governor's low-mark path
  (`Deko3DReleaseEmptyImageChunks`) and every "block could not be made" retry path give it back.
- Key `sasrt_target_block_cache_mb` (default **160**, 0 = off: destroyed at once as before).
- The governor counts the cache as free room (surfaces.cpp, `room += cache.bytes`), so it never steps the resolution
  down because of it; `Deko3DTargetCacheFigures` feeds a `Memory: kept target blocks` line (memory_report.cpp).
- A reused block holds what its last target left, exactly as the shared image chunks' freed ranges always have (a new
  colour target is cleared by BuildTarget; a resolve writes its destination). No pixel changes.

Port script (idempotent, asserts every anchor): `docs/handoff/target_block_cache.py` (paths are sasrt-nx's).

## Numbers (console, the same race, no screenshots in the driven part)

| | slow2 (no cache) | cache1 (cache 160 MB) |
|---|---|---|
| race fps (racemeans) | 26.79 | **27.45** |
| render thread a frame | 25.54 ms | **23.85 ms** |
| GPU a frame | 33.52 ms | 33.76 ms |
| worst frame of a 10 s window, median | 108 ms | **59 ms** |
| steady windows (after the race start) | 55-105 ms in every window with a step | **14-30 ms** in most, 40-76 ms in a few |
| cache | - | 1,476 targets took a kept block, 227 made one (87 %), 112-158 MB kept, 0 given back (no pressure in handheld) |

What is left at a step is a miss (a height no kept block fits): 60-100 ms, a few times in the race.

## The diagnostics used (optional for the base)

- The slow-frame log (`sasrt_renut_diag_slow_frames`, `_ms` 60): each render-thread frame over the threshold with busy
  / waited, pipelines made, targets built, textures made (with their time) and draws; plus a split of "waited" by kind
  (back buffer, present, slot fence, flush fence, kick fence, cleaner, drain). Scripts: `docs/handoff/slow_frames.py`,
  `docs/handoff/slow_waits.py`.
- It also found the next stall: at the race start the render thread waited 280-350 ms for the upload ring's cleaner
  thread (0x3B on core 3) mid-range. Fix in test: `sasrt_ring_cleaner_take_over` (the render thread cleans that range
  itself: a dc cvac is repeatable). Will follow once measured.
