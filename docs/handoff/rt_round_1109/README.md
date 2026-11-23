# SASRT render-thread round: batch for RR6 / the ultimate base (2026-11-09, 13:25) — pixel-identical items only

The user: "send anything over that you haven't to RR6 for the ultimate base that is pixel identical and gives extra
perf". Checked against `D:\renut-ultimate\base` first: it already has the 2 MB blocks (window and code), the inline
atomics (`-mno-outline-atomics`), the SDK in LTO/PGO (`BANJO_SWITCH_SDK_OPT`, `REXGLUE_OUTPUT_IN_BUILD`), the four-core
mode and RR6's port 53 (the limiter's / display sync's waits counted for the CPU-aware dynamic resolution). So this
batch is only what the base lacks. Every item gives the same answers from the same inputs (the same pixels); none
changes a GPU command. The code is in `files/` (excerpts with their line context; SASRT's keys and A/B numbers, which
do not match the base's 54-item list: give them the base's own).

| # | What | Applies in the base when | SASRT console result | Port? |
|---|---|---|---|---|
| RT1 | `DepthRestoreSourceLocked`: each depth target keeps its few candidate colour targets (same EDRAM base and pitch, colour, one sample, its scale, RGBA8/BGRA8), found again only when a target is built, retired or leaves the table (`g_sasrt_table_epoch`, an epoch of its own: the surface epoch moves with every re-pointed surface and override change). Before: two scans of the whole target table per call. | the EDRAM depth restore is on (`sasrt_renut_depth_restore`; the fast path asks for nearly every draw with depth bound: ~430 calls a frame in SASRT's race, each two table scans) | 2.6 % of the render thread before (function profile, run X); in-run A/B (4 s halves) -1.2 ms render thread, -1.2 ms GPU, +0.45 fps (14 pairs, P1); with RT2/RT3 as one group in 30 s halves: -0.2, -2.6, -4.9 ms render thread in the 3 race pairs; whole runs: within noise (~1 ms at most) | **yes** (inert without the restore) |
| RT5 | The memexport windows' buffer CPU-cached: plume makes it an upload buffer with `HOST_CACHED` (flushed once at creation, so no older dirty line lands on the GPU's results: plume_deko3d.cpp now flushes every cached buffer at creation, not only readback ones), and the CPU seed path (`SasrtSeedExportsCpuLocked`) cleans each seed's own lines (`unmap(0, &range)`; a no-op on uncached memory). Windows start on 256-byte boundaries, so no line holds two windows, and every line a seed touches is wholly its own (the last one's padding is no window's); the CPU never reads the buffer. Before: memcpy into CPU-uncached memory. | the CPU seeds are on (SASRT's `sasrt_gpu_seed_cpu_direct`) and the game has memexport draws (RR6 has none) | memcpy's bulk loop was ~3.3 % of the render thread, ~2.3 % of it the seeds (P1's line profile); not separately measurable on the console (P8 against P7: flat) | yes, for memexport games |
| RT4 | `CountSharedConstants`, `CountPushedConstants` inline in banjo_renut_tuning.h (a load and a store, as `Bump`), and draw.cpp's depth-writers key read through a draw.cpp static: code motion, the same counts. | always (no LTO in test builds: they were calls into another file at every draw, ~0.7 % + ~0.3 % of SASRT's render thread) | not measurable alone | yes (trivial) |
| tool | The `[renut A/B]` lines give each half's draws a frame and render-thread microseconds a draw (`g_ab_draws`, counted in `CountSharedConstants`, every draw on both paths), so halves that caught different scenes can be compared per draw (the user's request). A group A/B target (SASRT's 200) switches all the round's items at once. | always | tooling | yes |

## Findings the base may want (not code to port)

- **Four-core layout:** only work-ahead threads belong on core 3. The XMA Decoder alone: +1 fps over three cores, core 3
  48 % idle. The game's "Model Instance" thread (it records command buffers the render and game threads wait for): -2 fps.
  Wwise's threads (AK::EventManager, IOThread, BankManager) and the Audio Worker: no fps gain and long audio silences
  (the user heard them). Unnamed "XThreadNNNN" threads (the game's job threads, 22 of them): 300 ms stutters.
- **The stack sampler (`switch_profile_stacks`) is left off at random:** in two of six SASRT sessions the profile said
  "Stack sampling: disabled" and its file reused the run before's number (`rex_profile_NNN.log` written over the previous
  session's): the profiler thread reads the key and picks its number before the toml and the session's log are set up,
  depending on timing. It pauses every thread each millisecond when on, so runs with and without it are not comparable
  (P3's apparent +1 fps over P1 was partly this). Set it explicitly in test tomls.
- **4 s A/B halves cannot resolve 1-3 ms of render thread** (RT1 read -1.2 ms in one run and +3.5 ms in the next):
  banjo-nx's 30 s halves, and judge per draw.
- **Frames ahead:** SASRT alone ran 0 (the base and every other port 1). With 1: +0.9 fps, the three game cores full
  (~98 %), and the skinned-mesh "exploding polygons" (late reads) back: SASRT stays at 0.
- **2 MB blocks** (already in the base) measured +3.6 % fps in SASRT's race (25.74 against 24.85, sampling off in both):
  game thread -1.9 ms, render thread -0.75 ms, late frames 38 % -> 30 %.
