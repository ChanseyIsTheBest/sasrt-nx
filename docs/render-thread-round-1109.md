# Render thread and cores (2026-11-09)

The user, after the GPU round: "work on render thread optimisation, check what banjo did and what didn't work"; then,
from the CPU breakdown: "move the XMA decoder and Model Instance to core 3, leave the shader compiles on cores 0-2;
that should free up enough to make the render thread more efficient, but a couple of render thread optimisations would
help"; and "give machine copies to things that don't have them if they show up in the profiler".

## Where the CPU goes (run X, rex_profile_076, the race: 18 windows of 10 s, 25.7 fps, stock clocks)

The process has three of the four cores (0-2; core 3 is the system's) and uses 263 % of 300 % in the race.

| Thread | Core | CPU | ms a 38.9 ms frame | What |
|---|---|---|---|---|
| Main XThread (game logic) | 0-2 | 65.7 % | 25.6 | 66 % localized copies, 29 % generated code |
| Renut's render thread | 1 (pinned) | 63.8 % | 24.8 | 81 % renderer, 19 % plume / deko3d / libnx / libc |
| SlRenderer (the game's Direct3D thread) | 0-2 | 43.5 % | 16.9 | 50 % copies, 26 % generated, 16 % Renut's capture |
| WaterThread | 0-2 | 20.2 % | 7.9 | hand-written natives and copies |
| Model Instance | 0-2 | 17.6 % | 6.8 | 50 % Renut (command-buffer recording: NewOp 37 %) |
| AK::EventManager (Wwise) | 0-2 | 13.7 % | 5.3 | game code |
| XMA Decoder | 0-2 | 9.6 % | 3.7 | the SDK's decoder |
| SlAnimManager, SlParticleThread, audio, timers, the rest | 0-2 | ~31 % | ~12 | |

The renderer as a whole is about 0.8 of a core (the render thread, plus its capture in SlRenderer and its recording in
Model Instance). Run X had the per-shader GPU profile on (a mark a draw), which costs the render thread a little.

The render thread's functions (run X, symbolised with the r6e map, which matches r6d's code): FastDrawLocked 14.5 %,
WholeGeometryTry 6.2, DrawStateLocked 4.4, PushFloatConstants 3.9, FillTextures 3.2, the capture queue's handler 2.7,
**DepthRestoreSourceLocked 2.6**, PagesClean 2.5, Replay 2.3, GetStreamSource 2.1, ConvertVertices 1.7, PrepareGeometry
1.6, GetHostSurfaceSlow 1.4, BindStreams 1.3; then a flat tail (**SasrtWordsViewOwnerLocked 0.75**, setting getters
~0.3 each, malloc/free 1.1, mutexes 1.2).

## What banjo-nx did (its docs, checked against this tree)

SASRT has every one of banjo-nx's render-thread keys (sa2-nx's renamed sa2_renut_*), and every one banjo-nx measured
slower is off here too (replay lookahead +2.15 ms, shadow sort +1.13, texture slot skip +0.64, replay stream shaders
+0.7, inline line compare, host packets (neutral, 1.6 MB of the 2 MB L2), record prefetch, merge draws (0 merges)).
banjo-nx's own conclusions: the profile is flat after its rounds; with cores 0-2 full only less work helps, not moving
it; 30 s A/B halves and three or more rounds, as 15 s pairs marked items wrong. Differences found: banjo-nx's PGO and
2 MB guest blocks (`banjo_window_blocks`, `banjo_code_blocks`) are not in this port; `sa2_renut_deferred_chain` is on
here (banjo-nx turned it off after hangs with two devices).

## The items (pixel-identical: the same answers, fewer instructions)

Each is a key of the GPU round's list (sasrt_gpu_round.h, latched at the first use), with an in-run A/B target.

| # | Key | A/B | What |
|---|---|---|---|
| RT1 (79) | `sasrt_rt_restore_candidates` | 169 | The EDRAM depth restore asks, for nearly every draw with a depth target (the fast path re-asks whenever any surface was written since), which RGBA8 colour target over the same EDRAM base and pitch was written after the depth. `DepthRestoreSourceLocked` scanned the whole target table twice for it (its own key, then every target). Now each depth target keeps its few candidates (same base and pitch, colour, one sample, its scale, RGBA8/BGRA8), found again only when a target is built or retired (`g_sasrt_table_epoch`, its own epoch: the surface epoch moves with every re-pointed surface). The same test of the same write sequences. |
| RT2 (80) | `sasrt_rt_words_owner_memo` | 170 | The restore copy (two draws a frame) looked up the texture owning its depth-words view slot by scanning every texture. The last answer is kept and checked (the texture by its address must still hold a view with that slot; a slot belongs to one view at a time). |

Run P1 (in-run A/B, 4 s halves): **RT1: render thread -1.2 ms (median of 14 race pairs), GPU -1.2 ms, +0.45 fps**;
111,197 lookups in 10 s (about 430 a frame), each of which was two scans of the target table. RT2: its memo answers
both of its calls a frame (456 in 10 s); the A/B read +3.7 ms of render thread, which two lookups a frame cannot cost:
inside this A/B's noise (render-thread halves scatter by +-5 ms; banjo-nx's lesson: 30 s halves, three rounds).

What the line-level profile (P1, r7b's line tables) points at next, not done (the user asked for "a couple"):
memcpy's bulk loop is 3.3 % of the render thread, 2.3 % of it the memexport seeds the CPU copies into fresh export
windows (`SasrtSeedExportsComputeLocked`, item 30: ~12 MB a second); the pipeline key's inputs recomputed at every fast
draw (`SasrtSpecWordsOf`, `SasrtPlainFetchMask`, `FetchSpecWords`: ~2.9 %; a memo needs a proof that the draw's
texture, sampler and shader words did not change); `PushFloatConstants` ~3 %. (The profile's `lr` lines are the link
register at the sample, which a leaf callee leaves unchanged: they name the last call made, not always the caller.)

## Four-core mode (the user's layout)

banjo-nx's four-core mode (2026-10-27, from NetherSX2_nx's 4-core support, MIT, NaGaa95) ported into this SDK
(`sdk/src/core/threading_switch.cpp`): with four cores granted, core 3 is the "system core"; the threads
`sasrt_system_core_threads` names (the user's choice: `XMA Decoder,Model Instance`) are moved there alone, and
`__wrap_svcSetThreadCoreMask` (a link-time wrap) takes core 3 out of every other mask. The shader compiles stay on cores
0-2 (`banjo_system_core_uam = false`, `banjo_system_core_compiles = false`). The XMA Decoder is named before it starts
(moved at its start); Model Instance names itself after it starts (moved by its handle in `XThread::set_name`). The
profile's 10 s report gains `system core 3: idle N%` (sampled by the XMA Decoder, which runs there).

banjo-nx's lesson: the system takes about half of core 3; its first layout (mixer, Audio Worker, XMA, compiles: 41-55 %)
stuttered, so it took XMA and the compiles back off. Here: XMA (~10 %) and Model Instance (~18 %).

The grant: the forwarder's NPDM must allow CPU 0-3. With `sasrt_forwarder_program_id = "05B2275AF7F68000"` (the user's
Sphaira forwarder of `sdmc:/switch/sasrt-nx/sasrt.nro`; the user agreed to SASRT writing it, 2026-11-09), SASRT writes
`sdmc:/atmosphere/contents/05B2275AF7F68000/exefs/main.npdm` at start when it is missing or different (banjo-nx's NPDM:
CPU 0-3, the name field `sasrt-nx`); Atmosphere's ExeFS replacement then gives the next launch four cores. Deleting
that file undoes it. The log says what happened: `process cores 0xF, system core 3 (...); forwarder NPDM in place: ...`.

## Console runs

| Run | NRO | What |
|---|---|---|
| P1 | r7b | three cores (wrote the NPDM), the line-level baseline profile, A/B 169 and 170 |
| P2 | r7b | four cores: XMA Decoder and Model Instance on core 3: **2 fps slower** (below) |
| P3 | r7c | four cores, the XMA Decoder alone on core 3; 42 more machine copies (A/B 70); the pacing wait counted: **24.85 fps** (P1 23.91), core 3 idle 48 % |
| P5 | r7c | the audio threads on core 3 too (Audio Worker, Wwise's AK::EventManager, IOThread, BankManager): 24.92 fps (P3 24.85), and **long silences in the audio** (the user heard them): back to the XMA Decoder alone |
| P6 | r7d | XMA, SlParticleThread and the unnamed threads ("XThread...": 22 of them, the game's job threads among them) on core 3: 23.08 fps and **stutters** (the user saw them): the worst frame of a 10 s window 311 ms (median) against P3's 69 ms, a frame over 80 ms in 21 of 22 windows. Not kept. (r7d: a thread renamed from a listed name to one the list lacks goes back to cores 0-2.) |
| P4 | r7c | as P3 with `sasrt_renut_frames_ahead = 1` (every other port's setting): **25.71 fps**, cores 0-2 at ~98 %; **the exploding polygons are back** (the user watched it): not shipped |

P3 and P4's A/B halves (4 s) could not resolve 1-3 ms of render thread: RT1 read -1.2 ms in P1 and +3.5 ms in P3, the
copies +1.6 ms (GPU -0.7). Item-level claims need banjo-nx's 30 s halves; the whole-run numbers above are what holds.

Frames ahead (2026-11-09, the user: "try with frames ahead 1; what do the other ports run with"): banjo-nx, sa2-nx,
halo3-nx, kameo-nx, katamari-nx and the base all run one frame ahead (`kMaxFramesAhead = 1`), rr6-nx too
(`rr6_frames_ahead`, default 1); SASRT alone waits at its Swap (`sasrt_renut_frames_ahead = 0`, 2026-10-21: the late
reads of streams the game rewrites made skinned meshes explode). With 1 the game and render threads overlap (+0.9 fps
over P3) but the explosions return, and the three game cores are then full (303 % of the process, 10 % of it on core 3).

### P1 against P2 (the same race and build, 21 race windows each)

| | P1: 3 cores | P2: 4 cores (XMA + Model Instance on core 3) |
|---|---|---|
| fps | 23.9 | 21.9 |
| frame | 41.8 ms | 45.7 ms |
| GPU a frame | 33.3 ms | 33.1 ms |
| render thread busy (with its waits) | 32.2 ms | 37.4 ms |
| render thread CPU (profile) | 26.4 ms | 25.7 ms |
| game thread, Swap to Swap | 33.4 ms | 37.9 ms |
| CPU | 264 % of 300 % | 241 % of 400 % (core 3: ours 25 %, the system's ~42 %, idle 33 %) |

Every thread did the same CPU work a frame in both. Model Instance records the game's command buffers, which the render
thread and the game thread wait for; on core 3, shared with the system's threads, it finishes later and both wait (the
render thread's busy time +5 ms, the game thread +4.5 ms). It is on the critical path: back on cores 0-2. The XMA
Decoder decodes ahead into buffers: it stays on core 3.

## Machine copies (the user: "give things machine copies that don't already have them if they show up in the profiler")

`tools/switch_hot_bulk.py` over P1's profile (r7b's map) with `--merge`: **42 functions added** to
`app/src/cpu/hot/localized_bulk.txt` (981 bulk copies now, 12 shards). The hottest generated functions cannot be copies:
sub_82754EC0 (3.7 % of the main thread), sub_825E0F28 (2.9 %), sub_82556FB8 (SlRenderer 2.9 %), sub_827506C0 (Model
Instance 5 %, SlRenderer 1.4 %), sub_82783D88, sub_8274FEE8 use atomic reservations (lwarx / stwcx: the game's locks and
interlocked counters), which the guard's roll-back would make visible to other threads; sub_8263F180 (AK::EventManager
1.9 %) calls the host's log2f. On 2026-11-08 the first 939 copies moved 40 % of the samples from generated to machine
code without a CPU saving the console could measure (exact, kept); these are A/B'd in P3 (target 70).

## Dynamic resolution: only when the GPU is the limit (the user via RR6)

`sasrt_dynamic_cpu_aware` raises the budget to the CPU side's time a frame (the larger of the render thread's busy time
and frame_stats' CPU time: the frame less the game thread's waits). The pacing's sleep until the 30 fps slot (8.7 ms a
frame in the handheld race) was not reported as a wait, so the CPU time held it and the budget rose towards the whole
frame. `sasrt_renut_pacing.cpp` `NoteRelease` now reports it (`frame_stats::OnGameThreadWait`). (RR6's port 53 fixed
the same gap in the shared base: its limiter's and display sync's waits.)

Steps and the step up (2026-11-09 evening, the user: "raise it if there's 1.0 ms of room for 1 second; minimum 540p
handheld, 720p docked"). The PGO + LTO race (P10, sasrt_087.log) sat at 612 lines from the race start to the end and
never stepped back up: the old rule wanted the next step predicted under 85 % of the budget (29.3 ms at 34.5), and at
612 the GPU took 26.7-30.5 ms a frame (684 predicted ~35 by the pixel ratio, ~31.7 by the race's two measured points:
720 at 33.5 ms in P9, 612 at 28.5 in P10, about 54 % of 720's GPU time scaling with pixels). Banjo's release, the
ultimate base, Kameo, RR6 and Bangaio all have the same 85 % rule, so the user's rule is new here:
`sasrt_dynamic_up_room_ms` (1.0; 0 = the 85 % rule) steps up when the next height's predicted time has been at least
1.0 ms under the budget for `banjo_renut_dynamic_up_s` (1 s) in a row; down is unchanged (over the budget, 5 s after a
change). Ranges: handheld 540-720 (540 576 612 648 684 720; 477 before), docked 720-1080 (720 792 864 936 1008 1080; 540
before). Expected in the handheld race: 648 or 684 most of the time (612's 28.5 ms predicts 648 at 32.0 <= 33.5).

Console race (run dynres_up, 17:00, sasrt_088.log; the PGO + LTO NRO rebuilt with the rule, the shipping toml): the race
ran at 648 (~64 % of it) and 684 (~36 %), switching every 5-10 s after the first minute (about 20 changes): at 648 the
GPU averaged ~28 ms, so 684 was predicted at ~31.3 (the pixel ratio, x1.11) and taken; at 684 it measured 34.5-37 ms
(x1.2-1.3, more than the pixels), over the budget, down 5 s later. Race windows: GPU 31.4-33.6 ms, 27.9 fps (P10 at 612:
28.35), late frames 14.5 % (10.9 %), worst frame of a window median 55 ms (43). The user: "it's fine if it doesn't
settle": kept as it is. (A fix was drafted and reverted unbuilt: predict a step up by the time ratio the two steps
measured at their last change instead of the pixel ratio; it would mostly hold 648.)

More steps (the user, evening: "I think we need more steps, especially in docked"): `banjo_renut_dynamic_steps` 9 (up
to 10 now, `kMaxDynamicSteps` 12) on each mode's own grid, `sasrt_dynamic_lines_handheld` 18 (36 gives only 6 heights
in 540-720) and `sasrt_dynamic_lines_docked` 36: handheld 540 558 576 594 612 630 648 666 684 702 720, docked 720 756
792 828 864 900 936 972 1008 1044 1080. At 18 lines a quarter-size target's edge rounds to the nearest pixel
(`RenderScale::Coord`, half a pixel at most). Console race steps_race (18:00, handheld): 648-720, mostly 666/684/702,
27.6 fps, late frames 17.2 % (dynres_up 14.5 %), and 17 changes of a settable code's height, each making 14 targets
again (dynres_up: 2): a step up went to the highest step with room, often two at once (666 -> 702) onto a height
neither code held. `sasrt_dynamic_up_one_step` (on): one step up at a time, so the moves stay between the heights the
two codes hold (and 720, code 0) unless the band moves.

The user's docked session (sasrt_089, 17:10, clocks changed by the user during it): docked at 864-1080, the GPU memory
budget under its 192 MB reserve from the race start (cold textures released every second; render targets 278 MB at
1.3x): the octopus on Ocean View (lap 3's water) stopped rendering, its vertices exploding. Under investigation
(octopus_tests/octo_A.toml: the render-thread items and the GPU round's memexport waits and cache drops off).

## RT3-RT5 and the group A/B (run P8, r8b, 30 s halves)

| # | Key | What | Result |
|---|---|---|---|
| RT3 (81) | `sasrt_rt_view_surface_memo` | a replayed op's colour EDRAM view through the surface memo too (keyed by its view words) | **off**: 264 hits against 4,566 slow lookups in 10 s: the surface epoch moves at every change of the replayed op's overrides (SetReplaySurfaceOverridesLocked), which this game makes all through a frame, and clears the memo |
| RT4 | (no key: code motion) | the per-draw counters (CountSharedConstants, CountPushedConstants) inline, the depth-writers key kept in draw.cpp | not measurable alone |
| RT5 (82) | `sasrt_rt_cached_export_seeds` | the memexport windows' buffer CPU-cached, each seed's lines cleaned after it is written | not measurable alone (P8 against P7) |

A/B 200 (RT1-RT3 together, 30 s halves): the three race pairs all better with them on (render thread -0.2, -2.6,
-4.9 ms; +0.4 to +2.0 fps), but the whole runs do not move (P7 25.74 fps, render thread 30.9 ms; P8 25.69, 31.0):
about 1 ms at most. The A/B line's "draws a frame" read the slow path's count in P8 (70 a frame); it now counts at
CountSharedConstants, every draw.

## 2 MB blocks (2026-11-09, the user: "do the 2 MB memory pages from banjo 1.0.2 + the NRO alignment")

banjo-nx 1.0.2's (from kameo-nx 1.0.1, the Torchlight port's findings): SASRT did not have them. `RexGmInit` passed 2 MB
as `virtmemFindAslr`'s second argument, a guard and not an alignment, so the guest window was never on a 2 MB boundary
and the kernel used 4 KB pages for all of the game's memory. Now (`banjo_window_blocks`) 2 MB more is reserved and the
base rounded up; and (`banjo_code_blocks`, `sdk/src/ui/switch_code_blocks.cpp`, reading sasrt.toml itself as it runs in
the first constructor) the NRO's text (51 MB) and read-only data (18 MB) are copied to heap in line with 2 MB blocks and
swapped in before any thread of ours starts (the loader's copy stays: ~70 MB more taken; the race leaves ~640 MB of the
heap never handed out).

| | P3 (r7c) | P7 (r8a, the blocks) |
|---|---|---|
| fps | 24.85 | **25.74** (+3.6 %; kameo-nx: +4.3 %) |
| game thread, Swap to Swap | 31.6 ms | 29.8 ms |
| render thread | 31.6 ms | 30.9 ms |
| frames late | 38 % | 30 % |

(Both with the stack sampler off. The sampler, `switch_profile_stacks`, pauses a thread every millisecond to read its
stack; a start-up race left it off in P3 and P5 (their profiles reused the run before's number) and on in P1, P2, P4 and
P6, which confounds those comparisons: from P7 on it is set explicitly.)

## Where it ended (2026-11-09 12:30)

Shipping: four-core mode with the XMA Decoder alone on core 3 (P3: +1 fps over three cores, core 3 48 % idle, no audio
or stutter problems), frames ahead 0, RT1 and RT2 on, the 42 more machine copies, the pacing wait counted for dynamic
resolution (on, 480-720 handheld, 540-1080 docked). Tried and not kept: Model Instance on core 3 (-2 fps), the audio
threads on core 3 (no gain, long silences), particles and unnamed threads on core 3 (stutters), frames ahead 1 (+0.9 fps,
exploding polygons, cores 0-2 full).

## Memory: idle render-target sets released (2026-11-09 evening)

The user: "feel free to improve our memory management ... 4 player mode will probably be memory intensive". A target is
keyed by its scale code too (`TargetKey`), so every scale the game has drawn at keeps a whole set until its code is
re-pointed: the user's docked race (sasrt_089) had 54-61 render targets, 277-300 MB, against 30 and 83 MB at 1x, and
after it went back to handheld at 1x it still held 278 MB; the heap reached 217 MB free with the 3D at 1008-1080. A
handheld test with the docked range (octo_scale, 864-1080 lines: the menus already at 864) ran the heap out (35 MB
free, a 28 MB depth resolve destination not made) and the game was closed by the system.

`sasrt_retire_idle_targets_frames` (300): every 30 frames, a target whose scale is neither the 3D's nor the HUD's and
which no lookup has asked for in that many frames (`HostSurface::sasrt_used_frame`, set by `GetHostSurfaceLocked` and
`FindHostSurfaceLocked`) is retired (`RetireTarget`), as a re-pointed code's targets are: its slot stays, and the next
lookup at that scale builds it again (`GetHostSurfaceSlow`). Targets the frame uses at another scale (the post buffers
stay 1x) are looked up every frame and stay; a released target is no generation's, so aliases and restore candidates
of it lapse as for any retired one. A `[renut] N render targets of another scale ... released: X MB` line says what
went.

## The picture darker with the 3D above 720 lines in handheld (2026-11-09 evening, fixed)

Seen in the octopus tests with the 3D fixed at 900 lines in handheld (octo_gpu, octo_gpu2): the whole picture dimmed,
menus and the copyright screen included. Console boots at fixed heights (dark_720 / dark_900 / dark_1080, the same menu
screens 8-49 s after the launch): 720 normal, 900 dim (about 0.67x), 1080 dimmer. The front buffer is a resolve
destination drawn at the 3D's scale, and above 1x `banjo_renut_host_mips` gives it a host level, which
`banjo_renut_lazy_resolve_mips` makes only when a draw first samples the texture. The scan-out is no draw: it minified
the 1600x900 or 1920x1080 front buffer into the 1280x720 screen with the linear sampler (LOD 0.32 at 900, 0.58 at 1080)
between level 0 and a level never made, so the picture took that share of an empty level. `FrontBufferImageLocked` now
makes the pending levels first (`FlushResolveMipsLocked`), as a draw would. The shipped settings never reach it
(handheld at most 720 lines; docked scans out 1:1 at 1080, with the texel load); the test configs and any handheld
height over 720 did.
Console check (darkfix_900 / darkfix_1080, NRO out/console_runs/dark_fix): the copyright screen 91.6 / 91.5 mean
brightness against 91.6 at 720 (42.9-61.7 at 900 before the fix); the logo and main menu screens as at 720.

## The docked race out of memory, and a memory governor (2026-11-09 night)

Run docked_1 (the user's docked mode by ReverseNX, their max clocks; NRO dark_fix): dynamic resolution climbed 720 ->
1080 in 18 s at one step a second (the GPU 16-30 ms); the idle-target release freed the older sets (42 + 83 + 17 + 66
MB: 17 render targets, 103 MB, at 1.5x). Then the race's load took the stream cache to 239 MB of its 240 MB pool and the
upload rings to 160 MB; at 21:13:16 two buffers (32 and 8 MB) found no room with 97 and 72 MB of the heap free, the GPU
budget read 0 MB left, and the game went on at one frame in 12-13 s (the track preview) until the system closed it four
minutes later ("The software was closed because an error occurred"; no rex_crash.log: not a fault of ours to catch).

`sasrt_memory_governor` (on), with `sasrt_memory_low_mb` 256 and `sasrt_memory_critical_mb` 128: once a second (every
30 frames, `plume::Deko3DHeapFreeBytes`: the free chunks in malloc's heap plus what sbrk can still give, as the
memory-block log lines count) the heap's free MB goes to `banjo::renut_gpu::g_heap_free_mb`. Under the low mark dynamic
resolution takes no step up, the stream cache is capped at 96 MB (copies refused at the cap put its idle pass under
pressure: copies unread for 150 frames go) and render targets of another scale go after 60 frames unused; under the
critical mark dynamic resolution steps down (one step every 2 s) and the cache is capped at 48 MB. Transitions are
logged (`[renut] heap N MB free: ...`). The same pixels: copies and targets are made again when needed.

Run docked_gov (NRO with the governor, heap-only figure): it crashed again, this time on the CPU side. Dynamic
resolution climbed to 1080 in the menus (the GPU at 5-15 ms); the heap went low (199 MB) and critical (105 MB), the 3D
dropped to 720 and 189 MB of targets went, but they went into the GPU region, which had 500-740 MB free in 6-7 ranges
afterwards while newlib's heap stayed short: at the race's load "command buffers: an arena's growth found no room in the
heap" eight times in 150 ms, then the game was closed (21:37:56). (The script's extra A presses then dismissed the
dialog and launched the game again: sasrt_108 is that second boot; the race script now presses only while SASRT runs.)

The region (banjo-nx h10) is carved from the heap's top and gives memory back only from its bottom, only once 128 MB
there is free (`kRegionGiveBackAt`); a block placed at the bottom when the region grew pins it ("0 times given back" in
every run). So: `plume::Deko3DRegionGiveBack` (whatever is free at the bottom, in 2 MB steps), called by the governor
once a second while the heap alone is under 192 MB, and by the command buffers' arena before it gives up
(`ReserveArena`'s bad_alloc path, after its spare buffers); the governor's figure is now the heap's free memory plus the
region's (the heap alone when it is under 48 MB); render and depth targets of 1 MB and more have chunks of their own
(`sasrt_dedicated_targets`), so a retired target's memory goes back to the region (for buffers too) at once; and the
image heap's empty chunks go back when the governor reads low.

Six more (the user: "6 more memory improvements please"), all the same pixels, all under `sasrt_memory_governor`'s
marks but the fifth:

1. The I/O range cache (`masseffect_io_ranges_mb`, up to 64 MB of heap) dropped while the heap itself is under 192 MB
   (`rex::filesystem::TrimRangeCache`, SDK host_path_file): a dropped range is read from the SD again.
2. The upload rings' chunks of a heavy frame (160-256 MB in race loads) go at the next reset while memory is low
   (`UploadTrimResets` 1), not after `banjo_renut_upload_trim_frames` (900).
3. Prebuilt pipelines no draw took for 10 s go while memory is low (`PrebuildReleaseSeconds`; 180 s otherwise), checked
   every 5 s (20), without the old heap-room gate (newlib's room, which the GPU region distorts): 3,080 of 3,617 were
   held unused in the docked race's load; a draw that asks for one builds it again.
4. The command buffers' arenas give back what is past a quarter of `kMaxKeptArena` and a quarter more than the last
   recording used while memory is low (`ResetForRecording`; past `kMaxKeptArena` and twice otherwise): the arena that
   could not grow in the crash.
5. The GPU region gives its free bottom back from 32 MB, keeping 16 (`kRegionGiveBackAt`, `kRegionKeep`: 128 and 64).
6. While memory is low, render targets of the 3D's or the HUD's own scale go too after 900 frames (30 s) unused (a
   menu's or a cutscene's targets during a race; made again at their next use).

Six more again (the user: "Maybe 6 more?"), the same pixels:

1. Guest thread stacks measured. Each guest thread's host stack is a 16 MB heap block (Xenia's size,
   `xthread.cpp`): 31 of them at once in the race (`[threads] ... at most in use at once`), about 500 MB of heap. libnx
   maps a stack into the stack region and the heap address is unreadable while the thread runs, so the profiler
   measures instead: at each 1 ms sample (`svcGetThreadContext3`) the thread's sp against the top of its mapping
   (`svcQueryMemory`); each per-thread line of `rex_profile_NNN.log` ends with `stack N KB deepest sampled (all threads
   N KB)`. The size is now a key, `switch_guest_stack_mb` (16; sasrt_switch.toml sets 16), to lower once the console's figures
   are in, with a wide margin (a sample every 1 ms misses short deeper calls; an overflow faults on the guard below the
   mapping, it does not corrupt). The pool keeps blocks of that size and more (8 MB and more before).
2. The thread stacks kept for the next threads go back to the heap while memory is low
   (`RexSwitchReleaseSpareStacks`, SDK threading_posix, called by the governor with the image chunks).
3. At most 8 kept stacks (`switch_thread_stack_pool` 8 in sasrt_switch.toml; 64, up to 1 GB, before; the race kept 6).
4. Cold textures (not bound for 120 frames, 8 when critical) go while memory is low whatever the driver's GPU budget
   says (`EvictColdTexturesLocked`: before, only under `banjo_renut_textures_reserve_mb` of that budget, which the
   heap and region figures never reached); made again from guest memory when bound.
5. Image heap chunks of 32 MB (`ImageChunkSize`, 64 before): a chunk goes back to the region only when empty, and a
   few textures left in a 64 MB one held all of it.
6. While memory is critical the vertex stream cache drops copies no draw read for 60 frames (150 under pressure,
   `banjo_renut_stream_cache_idle_s` otherwise).

### Run mem12 (22:20, docked, max clocks): Ocean View, then Dragon Canyon

The first docked run without a crash: the whole Ocean View race, its results, the World Tour map and Dragon Canyon to
lap 2, 28-30 fps, dynamic resolution 900-1080. Memory (the heap is 3,083 MB): the game's own memory ~1,120 MB (taken at
boot), guest thread stacks ~500 MB (31 x 16 MB) + 96-128 MB kept, the recorded command buffers 116-176 MB, the I/O
range cache up to 61 MB with **0 hits** in the whole run, the GPU region 1,130-1,300 MB (blocks 816-972 MB; render
targets 106-292, textures 150-200 of which resolve targets 117-162, the vertex stream cache up to 153 MB in its 256 MB
pool) with 200-300 MB free in 40-54 ranges, the largest 28-55 MB. **The deepest stack the profiler sampled in 15
minutes, in any thread: 55 KB** (rex_profile_109).

The one close call (22:30:41): on the results screen the GPU was light and dynamic resolution stepped 972 -> 1008 ->
1044 -> 1080 in three seconds; each step made a set of targets while the earlier sets stayed (300 frames), the heap
went to 35 MB free and 27 textures and targets were not made ("no memory", for about a second), until the governor's
next look went critical (128 MB of kept stacks, 42 MB of the range cache, the idle sets) and 793 MB were free again.
And the governor's look itself called `mallinfo` (through `Deko3DHeapFreeBytes`): 7-21 ms under malloc's lock on
the render thread, once a second.

### Memory round 3 (the user: "15-20 more memory management improvements ... they could go into the base")

All the same pixels.

1. **The governor's look in O(1)** (`Deko3DHeapRoomBytes`: what sbrk can still give) instead of `mallinfo`, which
   walked 43,000-135,000 free pieces under malloc's lock (7-21 ms a second on the render thread, every other thread's
   malloc waiting). The pieces it counted are a few KB each: no block or big allocation can use them.
2. **A look every 10 frames** (30 before): cheap now, and a spike is seen in a third of a second.
3. **Guest thread stacks 4 MB** (`switch_guest_stack_mb` 4 in sasrt_switch.toml; 16 before): the deepest sampled was
   55 KB, so 4 MB is a 70x margin; ~370 MB of heap back. (The key stays 16 by default in the SDK: a port measures first.)
4. **The I/O range cache off** for SASRT (`masseffect_io_ranges_mb` 0 in sasrt_switch.toml): 0 hits, 61 MB held.
5. **The range cache switches itself off** when 128 MB went in without a hit (`rex_io_ranges_auto_off_mb`, SDK), and
   frees what it held, as it already did for lack of RAM.
6. **At most two 3D sets of render targets** (`sasrt_retire_stale_sets`, `sasrt_retire_stale_frames` 8): the 3D's
   previous scale keeps `sasrt_retire_idle_targets_frames` (a step back finds its set), any other scale (neither the
   3D's, its previous one, nor the HUD's) goes after 8 frames unused. The results screen's case held four sets.
7. **Idle targets checked every 10 frames** (30 before).
8. **A step up only with memory for it** (`sasrt_dynamic_up_memory`): the 3D's set now times the pixel ratio must fit
   above the low mark in the heap and region's free memory (`g_current_set_mb`, from the retire walk).
9. **Memory emergencies** (`sasrt_memory_emergency`): a texture or memory block plume could not make sets a flag
   (`Deko3DTakeMemoryEmergency`); the next frame retires every other scale's targets unused for 4 frames, steps dynamic
   resolution down at once (not after 2 s), and the governor acts as critical for its next three looks (stacks,
   caches, chunks) without waiting for its next look.
10. **Best fit in the GPU region** (`sasrt_region_best_fit`, `Deko3DSetRegionBestFit`): a block goes to the smallest
    free range it fits (the bottom range last, at its top as before), not the highest. Host test
    `tools/test_gpu_region_bestfit.cpp` (target sets of 6-28 MB changing every 10 rounds among 64 KB-4 MB blocks):
    first fit 109 free ranges, the largest 118 MB; best fit 80, the largest 190 MB.
11. **The range cache's trim at the low mark** (whenever the heap's room was under 192 MB before: the room alone reads
    130-260 MB in a race now that the look no longer counts malloc's pieces).
12. **A CPU line in the memory report**: guest thread stacks in use x their size and the kept ones, the range cache,
    and the command buffers' ended recordings' bytes used against their capacity (`RexSwitchStackFigures`,
    `CommandBufferMemory::ended_used`): where the heap goes, for the next round.

### Memory round 4 (the user: "aim for 15 more memory improvements until the deadline")

All the same pixels.

1. **The upload ring's frame cap at 48 MB while memory is low** (`sasrt_renut_ring_frame_cap_mb` 96 otherwise): a load's
   frame grew the rings to 160-240 MB in the docked crashes; a frame ended at the cap is submitted and goes on.
2. **Best fit in the image heap** (`sasrt_image_best_fit`, `Deko3DSetImageBestFit`): an image goes to the smallest free
   range it fits among all the shared chunks (the first that fit, chunk by chunk, before): fewer holes, and chunks that
   empty go back to the region.
3. **The 3D's previous set is stale too while memory is low** (`sasrt_retire_stale_sets`): it goes after
   `sasrt_retire_stale_frames` like any other scale's set (it keeps `sasrt_retire_idle_targets_frames` otherwise).
4. **The 3D's and the HUD's own scale's targets after a minute unused** (`sasrt_retire_current_idle_frames` 1800):
   a menu's or a cutscene's targets during a race (only while memory was low before, after 900 frames).
5. **Textures no draw bound for a minute go** (`sasrt_texture_long_idle_frames` 1800) even with the GPU budget and the
   bindless table fine (Renut's backstop released idle textures only past 85 % of the budget or with the table three
   quarters full): the last race's and menus' textures; made again from guest memory if bound again.
6. **SMAA tried again after its textures could not be made**, 60 frames later, instead of off for the rest of the
   session (`Fail` set `failed` for good: a memory emergency's second would have turned the anti-aliasing off).
7. **Guest memory decommits counted** (`RexGmDecommitFigures`, a `Memory: guest:` line): the guest memory core frees a
   backing chunk only when a decommit covers all of it; the line shows what the game's decommits asked for against
   what they freed, to see whether splitting chunks is worth it.
8. **A recorded command buffer's slack given back when the game ends it** (`sasrt_cmdbuf_trim_ended`): run mem13's new
   CPU line showed the 63 recorded buffers holding 247 MB of capacity for 29-47 MB of recordings (a new recording takes
   a spare buffer of up to 8 MB whatever it needs, and keeps it). At `MarkRecordingEnded`, on the recording thread
   (nothing replays a recording before it is ended, and ops hold offsets into the arena, not pointers), a vector more
   than three times (and 1 MB past) what it holds is cut to that plus a quarter: one copy of the recording.
9. **Prebuilt pipelines no draw took for a minute go back** (`banjo_renut_prebuild_release_s` 60 in sasrt_switch.toml;
   180): the prebuild made ~3,000 pipelines at the race's load that no draw used.
10. **A heavy frame's upload ring chunks go after 10 s** (`banjo_renut_upload_trim_frames` 300; 900): the race's load
    left the rings at 256 MB for 30 s.
11. **The upload ring's frame cap at 64 MB** (`sasrt_renut_ring_frame_cap_mb` 64; 96): a load frame past it is
    submitted and goes on in the other slot.

### Run mem13 (23:00, docked, the round 3 build)

The heap's CPU side: 1,168 MB in use (1,526 MB in run mem12): guest thread stacks 88-124 MB (4 MB each) against ~500;
the range cache 0. The GPU region: 1,330-1,494 MB with 463-751 MB free, the largest range up to 171 MB (28-55 in
mem12). No memory emergency, no failed allocation. The new CPU line found the command buffers' slack (item 8 above).

### The octopus (Ocean View): GPU item 38 and the pipeline reuse

The user's album shots (lap 2, docked at 864-1080 lines) showed the lagoon's octopus in pieces: red ball segments
scattered in the water, white tentacle tips and thin red streaks in the sky. The track preview (the flyover after the
mod select, before the race) shows the octopus close up for several seconds: the quick test, about 3.5 minutes a run
(`out/console_runs/octopus_tests/preview.sh`, ten shots and a sheet).

- mem13's preview (dynamic resolution moving 1080 -> 900 with the GPU at 34-39 ms): broken; its race's lap 2 too.
- Docked fixed at 720 (1x), a stable 900, the resolution walking every 2 s (`banjo_renut_dynamic_test_s` 2): correct.
  (A "fixed 1080" through `docked_low = docked_high = 1080` or `renut_resolution = "1080p"` fell back to 720 in the
  preview: those runs said nothing about 1080.)
- **Held at 1080 under full GPU load** (`banjo_renut_dynamic_gpu_ms` 200): broken, every shot. The repro.
- The same with the 16 memexport and fetch items off (`make_toml.py`, `heavy_toml.sh`): correct. Bisect: waits and
  caches half off - broken; 29 30 32 33 off - broken; 38 + 41 off - correct; **38 alone off - correct**.

Item 38, `sasrt_gpu_fetch_endian_spec`, gives a vertex shader its memory fetches' byte order as key constants
(`sasrt_words[4-6]`); the octopus's skinning reads its bone matrices by address. The hole (RR6 found it reading the
base): the chain reuse's pipeline shortcut (`PipelineReuse preuse`, draw.cpp's slow path) handed back the previous
draw's pipeline whenever the base key was reused, without comparing the words the key takes from each draw after that
(`sasrt_words`, `fetch_pad`, the clip bit in `reserved`, `point_sprite`): a skinning draw whose bone fetch had another
byte order than the draw before ran the draw before's specialised pipeline. Under a heavy GPU more draws run in a row
without a lookup between them, hence the load dependence. Fixed: the reuse needs those words the same too (it covers
every `sasrt_words` item through that path: 41, the screen/remap/stack specialisations). **Confirmed (run octo_fix38,
2026-11-10 00:00): the fix with item 38 on, the same heavy-1080 preview: the octopus right in all ten shots.** Item 38
is on again (it was off for twenty minutes). (Its `sasrt_gpu_fetch_endian_spec` counter reads 0 in every run: the item
never counts; the toml sets it.)

### Run mem14 (2026-11-10 00:00, docked, round 4 + the reuse fix + item 38 on)

The heap's CPU side 1,080 MB in use (mem13 1,168; mem12 1,526); room 414-426 MB; the GPU region 1,336 MB with 267-402
MB free. The command buffers' capacity 118-131 MB for 19-58 MB recorded (247 MB before item 8). Guest memory: **534 MB
committed in 21 chunks, no decommit in the whole run** (`Memory: guest:`): splitting the core's chunks would gain
nothing, so item 7 stays a diagnostic. 398 menu textures went a minute after the race began (item 5). The race at
29-30 fps, the octopus right on lap 2 and in the preview. The prebuild still held ~3,100 unused pipelines: their
release (`ReleaseIdlePrebuiltPipelines`) runs only with the heap's room under 256 MB or memory low, so
`banjo_renut_prebuild_release_s` 60 acts under pressure only (each is under 1 KB: left to the governor).

12. **The kept guest thread stacks back after a minute with no thread made** (`sasrt_spare_stacks_idle_s` 60;
    `RexSwitchStacksTaken`, SDK): a race makes no thread, so the 8 kept stacks (32 MB) go back whatever memory says.
13. **The vertex stream cache's pool drained chunk by chunk** (`sasrt_stream_cache_drain`): run mem14 held 104-146 MB
    of copies in a 288 MB pool (a chunk goes back only empty, and copies spread over all of them). With the pool past
    1.5 times its copies and 64 MB, the sparsest chunk (not chunk 0) is drained: `CopyPool::Allocate` takes it last,
    and each 60-frame pass drops its copies no draw used in the last frame (stream and index entries keep their place:
    converted into the upload ring meanwhile, copied again when they hold); empty, it goes back (ReleaseSlot). Whole
    buffers' copies stay; a drain not done in 10 passes is given up. The same pixels.

### A GPU hang from item 5 (the minute-idle textures), and the drain's first run

Runs mem14, mem15 and home_test (round 4 builds, full docked races) hung the GPU 80-150 s into the race: "[deko3d] a
fence has not signalled after 2 s" doubling to 128 s, the console's screen capture empty (sys-botbase `pixelPeek`
returns 0 bytes) and HOME no longer closing the game (the close helper fell back to `killGame`, whose "closed because
an error occurred" dialog then needed A). The game's CPU side went on logging. Each hang came 4-5 s after a batch of
"host textures no draw bound for 1800 frames released". With items 5 and 4 and the two ring settings back at their old
values (run hang_A) and then with item 5 alone off (hang_B): two clean races, 0 fence timeouts, 0 empty shots, normal
closes. **Item 5 (`sasrt_texture_long_idle_frames`) is off by default (code 0, and 0 in sasrt_switch.toml).** Root
cause not found tonight: `ReleaseHostTextureLocked` retires the texture and bumps the binding epochs, and the fast bind
paths (`SlotLastHolds`, `TextureObjectHolds`) check them. The pressure-only cold eviction (`EvictColdTexturesLocked`)
releases through the same function, so it is suspect too (4-player mode under pressure): a follow-up task.

Item 13 (the stream cache drain), run mem15: one chunk given back, but the pool stayed at 288 MB: copies are spread
over the chunks with holes too small for new ones, so a new chunk is made while another drains. It does no harm (the
same pixels, no extra conversion seen); left on, worth less than hoped. Item 12 (the kept stacks): 32 MB given back
60 s into the race.

Two more runs on the hang (2026-11-10 01:15-01:35): item 5 on with round 4's image best fit (M32, `sasrt_image_best_fit`)
off - hang_C clean (32 release batches, 0 fence timeouts), hang_D hung (7 fence timeouts, 6 s after a release batch).
So the best fit is not the cause: with item 5 on, 4 of 5 races hung; with it off, 4 of 4 were clean (hang_A, hang_B,
mem16, and mem16's second race). Item 5 stays off; the best fit stays on. The card holds the final NRO (mem16's) and the
shipping toml.

The diagnostic (2026-11-10 02:00, `[m35diag]` lines, textures.cpp `g_long_idle_released`: active only with item 5 on;
run m35diag, which happened not to hang): 400+ releases, all plain mip-mapped 2D textures (guest formats 51, 20, 53,
18; not GPU-written, not targets, no words or swizzle views); 71 made again by a bind, 10 of them 16-21 frames after
their release (the median 561 frames): scenery seen once a lap (a lap is ~2,100 frames, past the 1,800 idle), released
just before it comes into view again, not a bind path missing `used_frame` (every normal bind sets
`fx.transition[0]` and `RefreshBindingLocked` marks it). No upload burst before any hang (1-2 texture uploads per 300
frames). In all three logged hangs the 15-20 s before held dynamic resolution's code re-points ("code 6 now 936 / code
4 now 972, 14 targets made again") and a 72 MB set of targets released. Not found: left to the follow-up task, item 5
off. (The card has mem16's NRO and the shipping toml.)

14. **The recording cut's ratio and slack as keys, tightened** (`sasrt_cmdbuf_trim_percent` 150 and
    `sasrt_cmdbuf_trim_slack_kb` 256 in sasrt_switch.toml; 300 % and 1 MB by default). Run mem17 (02:17) against mem16,
    the same race: the recorded buffers' capacity 32-70 MB (102-133 MB), 734 MB given back over 1,024+ cuts, and the
    race at 29.07 fps / render thread 12.91 ms / GPU 31.66 ms against 29.15 / 12.64 / 31.58: the same within noise.
    The same run tried the vertex stream cache at 192 MB (256): 22,828 copies refused at the cap and no smaller pool
    (it held 95-161 MB in its 256 MB pool regardless): not taken, the cache stays 256.

## Threads waiting on each other (2026-11-10, handheld 1020/460/1600)

The user: "is there any way we could reduce latency between threads so more CPU is utilised and they spend less time
waiting", then "base off one of our races at 1020/460/1600", "try relaxed vsync" and "fix 2 as well". The console is in
handheld from here on (ReverseNX handheld resolution and clocks, the user's setting).

Docked at max clocks the waits are not latency: the game is at its 30 fps cap and the GPU takes ~32 ms of each 33 ms
frame (run mem17: 120-150 % of 400 % CPU, core 3 72 % idle). In handheld the CPU side is the limit. Run P1 (r7b, the
newest handheld race whose profile has the wait stacks; `tools/nro_symbolize.py`-style naming with r7b's map, race
windows 11-30, ~24 fps, cores 0-2 at ~88 %), per 41.8 ms frame:

| Thread | Working | Waiting on |
|---|---|---|
| Main XThread | ~27 ms | late input's delay ~8 ms (banjo_late_input: the slack it measured, not lost), events ~3 ms, **the event's mutex inside XEvent::Set ~2.3 ms** (5.5 %, `PosixEvent::Set+0x20`) |
| SlRenderer | ~18 ms | QueueFrame (the render thread finishing the frame) ~10 ms, **PaceSwap ~8 ms**, events ~4 ms |
| Render thread | ~26 ms | the same-frame scene (the game's recordings) ~7 ms, idle ~9 ms |
| GPU | ~33 ms | (80 % busy) |

1. **The pacer holds late frames** (`sasrt_vsync_relaxed` off): `PaceSwap`'s fixed-vsync branch keeps a frame that
   missed its 33.3 ms slot until the next 60 Hz refresh. P1: 40-60 % of frames late (e.g. 136 of 229 in 10 s), 8.6 ms
   a frame paced; the PGO race (pgo_ship) 0-108 late frames per 10 s, the 25-27 fps windows the ones with most. The
   key was turned off on 2026-10 from a PC test of the native renderer's flip wait (enhancements.md); with Renut only
   PaceSwap reads it (the native vblank thread does not run). Console A/B (vsync1 / vsync0): pending, the console's
   screen was asleep (captures black, 0.2 W) at 03:15-09:30.
2. **The event mutex** (`thread_event_address_wait`, SDK, on): Horizon's condition variable gives a woken thread the
   mutex at the wake (svcSignalProcessWideKey takes the mutex tag for it) although it may not run for a while: with
   cores 0-2 busy a woken guest thread (0x3B) waits for its core, and a thread setting the same event meanwhile sleeps
   on the mutex behind it. An event's blocked threads now sleep on a 32-bit word (`svcWaitForAddress`, wait if equal)
   and take the mutex only when they run; Set changes the word under the mutex and wakes the address after it
   (`sdk/src/core/address_event_core.h`, `PosixCondition<Event>` in threading_posix.cpp, the syscalls in
   threading_switch.cpp). The 360's semantics, which the condition variable kept only because the second Set waited:
   an auto-reset Set that finds a thread blocked releases one (a grant; the event stays unsignalled), a manual-reset
   Set every thread blocked at that moment (a Reset right after, or Pulse, cannot strand them). WaitMultiple, Reset,
   Query and the other handle types are unchanged (the mutex still guards the state); a blocked thread re-checks every
   100 ms unwoken (a net: a release found that way is counted, `safety_releases`). Host test
   `tools/test_address_event.cpp` (the same header on WaitOnAddress): 200,000 ping-pongs, 20,000 rounds of 4 blocked
   waiters released by 4 back-to-back Sets and by a manual Set + Reset, 1,000 interrupts (worst 0.24 ms), random mixes
   of Sets, Resets, timeouts and interrupts with 16 consumers and 4 producers (15-16 million Sets): no lost wake-up,
   successes <= Sets, the counters back at 0, 0 safety releases (two full runs). Console A/B: pending (as above).
3. The render thread's ~7 ms on the same-frame scene is the frame order without running ahead (frames ahead 0); not
   touched (the user: "forget frames ahead 1 for the moment").

### The handheld A/B runs (2026-11-10 morning, 1020/460/1600, Ocean View, one build)

| Race | Settings | fps | late frames / 10 s | paced ms | GPU ms | render thread ms | input -> display |
|---|---|---|---|---|---|---|---|
| hh_base (1) | shipping; no stack sampling; two drivers (shots twice as often) | 26.6 | 47 | 10.6 | 34.5 | 27.4 | 68 |
| hh_relaxed (2) | `sasrt_vsync_relaxed = true`; sampling on | 22.1 | 113 | 5.5 | 33.5 | 34.3 | 88 (worst 141) |
| hh_base2 (3) | shipping; sampling on | 26.1 | 47 | 10.3 | 34.6 | 28.8 | 67 |
| hh_noevt (4) | `thread_event_address_wait = false` | GPU hang 35 s in (below) | | | | | |

Relaxed vsync: -4 fps against the same sampling (the game hands frames over faster than the render thread and the GPU
take them; SlRenderer waited 44 % on the render thread, frames queued for the display). Stays off. The event fix: the
main thread's samples in pthread_mutex_lock under PosixEvent::Set 0.0 % (P1, the old path: 5.6 %).

### The GPU hang: the EDRAM depth restore's fallback (2026-11-10)

Run hh_noevt hung the GPU (7 "a fence has not signalled", captures empty, sys-botbase silent; the game's CPU side
logged 4 minutes more; deko3d.log: only the timeouts). Every GPU hang so far has the same lead-up in the game log:
mem14, mem15, hang_D (docked, the night before, blamed on M35) and hh_noevt (handheld, M35 off). About 3 s after
render targets were released or remade (memory round: "14 render targets of another scale ... released: 72.2 MB";
handheld: "14 targets of its 666 lines made again" at a dynamic-resolution step), exactly two "EDRAM depth restore"
lines (depth 831C391C 1152x544 from colour 831C388C, then 831C38BC, 1200x544), and the first fence timeout 2.04-2.05 s
after them in all four: the frame holding those restores never finishes. Clean runs have none of these lines: the
game's restore (twice a frame) goes to the depth alias at scales other than 1x (`sasrt_gpu_cut_depth_alias` counts 586
per 10 s), and RestoreDepthFromColorLocked's draw runs only when the alias fails. Builds before the fifth GPU round
(r6a, 2026-11-09 10:02) drew that fallback every frame at 0.8-1x and never hung; it then cleared stencil only, and
`sasrt_gpu_depth_restore_whole_clear` (item 50) now clears depth and stencil first when the restore covers the target.
The queue never reported an error (deko3d's checkError runs in dkFenceWait every 100 ms and would put the queue in its
error state: plume logs that): a GPU lock-up rather than a page fault. Not the event fix (off in hh_noevt), not file
reads (the music stream's 64 KB reads go on through the hang). Diagnostic key `sasrt_diag_restore_no_alias` (every
game restore takes the fallback draw, as before the fifth round) and a fuller restore log line (scales, host sizes,
copy and hand-over state), to reproduce it: configs diagA (fallback forced), diagB (that without the whole clear),
diagC (targets retired after 20 / 4 / 60 frames).

### Peggle 1's file I/O fix (2026-11-10, the user: "do we have the fix from peggle one reading files through a buffer?")

Not here before: `PosixFileHandle::Read` / `Write` read and wrote straight into the caller's buffer (guest memory,
which Horizon's file system can refuse as a transfer buffer; Peggle's 23 MB read froze the console with no log). Now
on the Switch both go through a 1 MB host buffer per thread (sdk/src/core/filesystem_posix.cpp, peggle1-nx's form,
with this port's end-of-file rule kept): one memcpy more. HostPathFile's DirectRead and WriteSync use it.

### The GPU hang found: a depth-words copy past a texture's end (2026-11-10 afternoon)

The fallback restore was a symptom. With `sasrt_restore_skip_scaled_fallback` on (run fixY1) the console still hung.
Reproducer (config diagY): `banjo_renut_dynamic_test_s = 3` (a step every 3 s through 540-720) and
`sasrt_texture_long_idle_frames = 1800`: hung in ~2.5 min in diagY and fixY1. Their logs ("[sasrt restore] the
game's restore copy not recorded: no texture owns the fetch's words view") and the 10 s counter ("N with the copy":
0 in every window but the one holding such frames, 30) led to it:

- Codes 4 and 6 of RenderScale are the dynamic resolution's settable codes (their ratio is rewritten at each step);
  `RenderScale ==` compares the code. A texture over a depth resolve made when code 4 meant 666 lines was "the same
  scale" at 702 and kept its 666-line image.
- WordsViewSlot refused it (another size), so the bind took CopyDepthWords, whose box is the scale's size with the
  code's new ratio: larger than the image. plume's copyTextureRegion handed it to dkCmdBufCopyImage unchecked: an
  out-of-bounds GPU write. With the memory round's packing (best-fit GPU region and image heap, dedicated target
  chunks, retirement) it can hit live data: the GPU locks up (no deko3d error).
- Fix: `sasrt_texture_scale_size_check` (on; textures.cpp, the bind: such a texture is made again when its image is
  of another height of its code, as ResolveTarget does for destinations), CopyDepthWords's box clamped to both images,
  and plume's image copy clamped to both images (logged). `sasrt_restore_skip_scaled_fallback` back to off.

| Run | Settings | Resolution steps | M35 releases | Fix fired | Copies / misses / fallbacks | Hang |
|---|---|---|---|---|---|---|
| diagY, fixY1 | the reproducer, without the fix | ~30 | ~25 | - | 30 copies, misses | yes (~2.5 min) |
| fix2Y1 | the reproducer + fix | 81 | 28 | 3 (e.g. 1008x476 image, scale's size 1123x530) | 0 / 0 / 0 | no |
| fix2Y2 | the reproducer + fix | 81 | 31 | 2 | 0 / 0 / 0 | no |
| fix2Y3 | the reproducer + fix | 81 | 26 | 3 | 0 / 0 / 0 | no |

Handoff for RR6 (rr6-nx, the ultimate base) and Viva Piñata: `docs/handoff/gpu_hang_1110/README.md` (all three
trees had the same code).

### Dynamic resolution budget 32 ms against 34.5 (2026-11-10, the user: "lower the budget to 32ms and then test")

Handheld 1020/460/1600, Ocean View, the hang-fix build (blitship = 34.5, budget32 = `banjo_renut_dynamic_gpu_ms = 32.0`):
fps 26.04 -> 26.25, late frames per 10 s 52 -> 43, GPU 34.3 -> 33.0 ms a frame, average 3D height 689 -> 674 lines
(~4 % fewer pixels), input to display 65.8 -> 64.9 ms, render thread 28.5 -> 28.8 ms. The budget held (31 of 39
decisions at 32.0; the rest loads, raised by sasrt_dynamic_cpu_aware). Within one run's noise for fps (+-0.5 between
same-setting races); the frame is not the GPU's alone at ~38 ms (the render thread and the game thread take most of it
too). Shipping stays at 34.5 unless the user chooses 32.

## The thread-latency round (2026-11-10 afternoon, the user: "reduce latency between threads so more cpu is utilised")

The user's picks (14:45): 1 (game threads one priority up), 2 (WaterThread to core 3), 4 (replay recordings before
they end), 5 (frame pacing off SlRenderer), 6 (address waits for the render thread's queues), 7 (spin before sleeping),
the shader compiles to core 3, 9 (un-pin the render thread), 12 (a faster recording hook), 13 (a wait graph). Each its
own key, console A/B, pixel-identical. Handheld 1020/460/1600, Ocean View, dynamic resolution budget 34.5.

| Race | Change | fps | late / 10 s | paced ms | GPU ms | render thread ms | input -> display |
|---|---|---|---|---|---|---|---|
| lat1 | 9: render thread un-pinned (in-run A/B 2) | pinned 24.7, un-pinned 23.5 | | | | 22.7 / 26.8 | |
| lat1 | 2: WaterThread on core 3 | 23.5 | | | | | stutters, vertex explosions |
| lat2 | compiles on core 3 (`banjo_system_core_compiles`) | 25.05 | 65 | 10.0 | 34.6 | 28.5 | 67 |
| lat3 | 1: Main XThread + SlRenderer at 0x3A (`sasrt_boost_threads`) | 24.89 | 61 | 10.0 | 34.6 | 29.1 | 67 |
| lat4 | 6: the queue on an address (`sasrt_renut_queue_address_wait`) | 24.89 | 52 | 10.7 | 34.9 | 29.5 | 69 |
| lat5 | 6 + 7: and a 50 us spin first (`sasrt_renut_queue_spin_us = 50`) | 24.63 | 65 | 10.2 | 34.6 | 29.1 | 68 |

Kept: compiles on core 3 (the user: "confirmed safe on other ports"). Rejected: 9, 2, 1. 6 and 7: no fps (6 a little
more pacing slack), both stay off.

Why the CPU items show no frames: with fixed vsync the frames go on a 30 Hz grid (33.3 or 50 ms) and the GPU is at its
budget (34.5 ms, 86 % of a 40 ms frame). A faster CPU side only adds pacing slack. The GPU idles ~5.6 ms a frame
because `PaceSwap` sleeps at the start of the Swap, before the frame's present is queued and before SlRenderer starts
the next frame: the next frame's work cannot reach the GPU until the slot. Hence item 5 below.

Item 12, the recording hook: the recording thread (Model Instance, 17.8 % of a core in the race) spends 43 % of its
samples in NewOp, and 54 % of NewOp in halo3-nx's `NoteSetWords`: 936 device words compared with the device at the
buffer's Begin at every op, a word and a branch at a time. Its bits are read only by `BuildInheritRuns`, with
`banjo_renut_replay_inherits`, which SASRT has off. `sasrt_record_inherit_scan_gate` (on; in-run A/B 201) leaves the
scan and Begin's 12.7 KB image copy out when the inherits are off; `sasrt_record_inherit_scan_wide` (on) compares 16
bytes a step where the inherits are on (other ports; the same bits: host test of 200,000 random cases against the word
scan, `tools/test_inherit_scan.cpp`). Only the Model Instance thread records in this game.

Item 5, pacing on the display: `sasrt_pacing_on_display` (off; in-run A/B 202). The swapchain's swap interval becomes
the game's presentation interval (2: each image shown for at least two refreshes, a late one at the next refresh after
that, as the fixed grid did) and the Swap goes on at once; the game is held back by what holds it already (frames
ahead 0: the render thread finishing the frame; the present waits for one of the three images). Relaxed vsync, which
was worse (22.1 fps, frames queued for the display), released late frames at once on a 60 Hz swap interval; this keeps
the 30 Hz minimum on the display itself.

Item 13, the wait graph (`rex_wait_graph`, off; run wg, the lat build, 280 s of race): every guest wait timed per
waiting thread and object, every Set/Release counted per object and signalling thread, a "[waits]" line per thread
every 10 s. The game's chain: **SlRenderer is the hub**. Main XThread blocks on semaphore 30054018, released only by
SlRenderer (5.3 s of a 10 s window in the one window it was listed; its other waits: 0.4 s on SlParticleThread's
semaphore); the recording worker (Model Instance) waits on semaphore 300AB018 and the WaterThreads on 300CD018, both
released only by SlRenderer. SlRenderer itself waits on the render thread finishing its frame (frames ahead 0) and on
the pacing sleep (above). So the game's main thread waits for SlRenderer, which waits on the pacing and the render
thread: item 5 takes the pacing out of that chain. The report listed the ten most-blocked threads, which were the idle
ones (audio, file); since run wg it leaves out a thread blocked over 90 % of the window, so the busy threads show.

Run lat6 (15:47, the pacing build: item 5 in-run A/B 202 with 10 s halves, item 12's gate on throughout), pooled over
120 s a half: **the display pacing 24.07 fps (render thread 27.7 ms, GPU 34.5), the Swap pacing 26.10 fps (25.9,
33.8)**; whole race 24.92 fps, 0 fence timeouts. The display halves: the game thread 36-42 ms from Swap to Swap with 0
ms paced (its wait moved into QueueFrame), swap -> present 17-28 ms (7-14 in the Swap halves), and late input's delay
on the main thread 12-15 ms (2-9 in the Swap halves). Two readings: Horizon may latch an interval-2 image only every
other refresh (a frame late for its 33.3 ms slot then shown at 66.7, not 50: with a quarter of the frames late that
is 41.7 ms a frame, 24 fps, as measured), or late input takes the display's wait for slack and holds the main thread
back (the same as relaxed vsync's run, hh_relaxed: its late-input delay grew to 25 ms a frame where it fell to 17.5
fps). Run lat7 separates them (the same A/B with banjo_late_input off).

Item 12 in lat6 (gate on): the recording thread 13.7 % of a core (lat4: 18.2 %, -25 %); NewOp and its parts ~24 % of
its samples (lat4: 44 %). Its next cost is the whole-device compare at every op (`DifferingChunks`, 11 %): banjo-nx's
setter marks (`banjo_renut_tags`) never apply in SASRT ("0.0 % compared from the setters' marks"), the game's D3D
setters not being native here.

Run lat7 (16:00, the same A/B as lat6 with `banjo_late_input = false`): the display pacing 25.27 fps, the Swap pacing
25.88 (render thread 27.9 / 26.6 ms, GPU 34.0 / 33.6). Without late input the display halves lose 0.6 fps instead of
2.0: **late input caused most of lat6's loss** (it takes the Swap's wait on the render thread for slack, and with the
display pacing that wait is the display's, so it held the main thread back by 12-15 ms a frame). The same likely
explains much of relaxed vsync's -4 fps in hh_relaxed (its late-input delay reached 25 ms a frame in its 17.5 fps
window). Item 5 stays off: even without late input it is no faster, and input -> display rose (75 ms against 67).

Run lat8 (16:03, item 12's gate in-run A/B 201, 10 s halves): gate on 24.75 fps, off (the scan as before) 25.62
(render thread 27.8 / 27.5 ms, GPU 34.4 / 34.1). The gate only removes work from another thread, so the -0.9 is the
halves' track sections (a 10 s half can keep landing on the same stretch of the lap; race windows run 22-28 fps).
The profile is the measure for it (lat6: the recording thread 18.2 % -> 13.7 % of a core). Kept on (pixel-identical
by construction). Later A/Bs: the default 4 s halves.

Run wg2 (16:21, build 3: the wait graph with the busy threads listed, and the same-frame places' timing; shipping
otherwise). **Item 4 measured**: at the same-frame place the render thread waits 2.3-7.3 ms a frame (about 4.5 ms on
average); the worker's recording takes 2.6-7.2 ms from its BeginCommandBuffer to its End, and End to the game's
splice (which fills the place) is 0.02 ms. The render thread's wait is the recording itself: it reaches the place
about when the worker begins. Filling the place at End instead of the splice gains nothing; only replaying the
recording while it is being recorded would, and that is not done: the worker's op and arena vectors can reallocate
under a concurrent reader, `Replay` looks ahead at the next op and sorts whole runs (`banjo_renut_shadow_sort`), and it
would read the draws' vertex data before the game's submission point (the console's GPU reads them only after the
ring submission; the vertex explosions of the WaterThread test were late data). Left for a session of its own, with
the numbers above.

The wait graph with the busy threads (10 s windows in the race): Main XThread and SlRenderer hand frames to each other
(Main waits 65-200 ms a second on semaphore 30054018, released by SlRenderer; SlRenderer 6-58 ms a second on
30052018, released by Main): SlRenderer is the slower stage. SlRenderer also waits 31-65 ms a second (1.2-2.5 ms a
frame) on event 300DC018, set by the WaterThreads it starts (semaphore 300CD018, ~400 releases a second); the
recording worker (Model Instance) waits on semaphore 300AB018, released by SlRenderer. SlRenderer's host-side waits
(the pacing sleep, QueueFrame's wait for the render thread) are outside the graph (they are not guest waits).

The recording thread after the gate (wg2, 14.0 % of a core): about 40 % of it is ours, led by the whole-device compare
at every op (`DifferingChunks` 12.9 %, `MixedChunkFields` 6.0 %). banjo-nx compares only the chunks its native setters
marked; SASRT's setters are guest code (no marks), and the D3D pending tags alone do not cover the tail's pointers
(index buffer, shaders, stream and texture pointers): no exact cut there.

Run lat9 (16:45, the relaxed-vsync A/B 203 added to build 4: `sasrt_vsync_relaxed = true`, the off half fixed vsync,
4 s halves, late input off in both): relaxed 25.70 fps, fixed 25.33 (render thread 28.5 / 27.9 ms, GPU 34.3 / 34.3);
the race 25.37 fps, input -> display 74.5 ms. Without late input relaxed vsync is level with fixed (+0.4, within the
noise; its frames less even): the morning's -4 fps (hh_relaxed) was late input's. Shipping keeps fixed vsync (the
user's choice).

The round's outcome: in this game, on the handheld clocks, the frames are set by the GPU at its budget and the 30 Hz
grid; the CPU-side items (1, 6, 7, 9, 2) give no frames, the pacing items (5, relaxed) none either. Kept: compiles on
core 3 (config) and item 12's gate (the recording thread -25 %); added: the wait graph (13) and the same-frame timing
line. Item 4 measured, not built (above).

Run lat10 (16:52, build 4, shipping settings, the confirmation): 25.38 fps (lat2 25.05), late frames 57 / 10 s, paced
9.8 ms, GPU 34.1 ms, render thread 27.3 ms (28.5), input -> display 63.9 ms (67.3); the recording thread 14.2 % of a
core; the same-frame place 1.8-4.8 ms; 0 fence timeouts, 0 errors. Handoff: `docs/handoff/latency_1110/README.md`.

### The recording worker one priority up (17:00, from item 1's key; build 4, no new code)

The render thread's same-frame wait is the worker's recording (wg2), and at 0x3B the worker shares cores 0-2 with
Main XThread, SlRenderer and the WaterThreads in 10 ms slices. `sasrt_boost_threads = "Model Instance"` (0x3A) alone,
two races of each, alternated:

| Race | Worker | same-frame wait (ms a frame) | recording (ms) | fps | render thread ms | GPU ms | input -> display |
|---|---|---|---|---|---|---|---|
| lat10 | 0x3B (shipping) | 3.96 | 4.67 | 25.38 | 27.3 | 34.1 | 63.9 |
| lat11 | 0x3A | 3.20 | 4.54 | 25.58 | 26.6 | 34.1 | 66.2 |
| lat12 | 0x3B (shipping) | 3.98 | 4.64 | 25.26 | 27.7 | 34.1 | 63.8 |
| lat13 | 0x3A | 3.31 | 4.52 | 25.54 | 26.9 | 34.1 | 68.5 |

The wait 0.7 ms a frame shorter in both (the two baselines agree to 0.02 ms), fps +0.25, the render thread -0.7 ms;
input -> display 2-5 ms higher in both (within the day's 63-69 range). Scheduling only (no pixels). Both worker threads
took 0x3A at their start (the creating thread's earlier attempt at the rename logs "NOT set": the thread had not
started).

## Machine copies for everything the profiler caught (2026-11-10 evening, the user: "convert as much as you can")

Where each game thread's time went in the race (lat12, the round's final build; "native" = a hand-written native,
"copy" = a localized copy, "plain" = the recompiled code as generated):

| Thread | CPU (of a core) | native | copy | plain | ours (engine) | system |
|---|---|---|---|---|---|---|
| Main XThread | 63 % | 36 % | 34 % | 25 % | 2 % | 3 % |
| render thread | 58 % | | | | 86 % | 14 % |
| SlRenderer | 43 % | 34 % | 26 % | 19 % | 13 % | 9 % |
| WaterThread | 21 % | 51 % | 48 % | 0 % | | 1 % |
| Model Instance (recording) | 14 % | 15 % | 27 % | 13 % | 41 % | 4 % |
| AK::EventManager | 12 % | 48 % | 34 % | 12 % | 3 % | 3 % |
| SlAnimManager | 8 % | 58 % | 26 % | 11 % | 3 % | 2 % |
| SlParticleThread | 5 % | 18 % | 21 % | 45 % | 5 % | 11 % |

Why the plain code was left: (1) `tools/switch_hot_bulk.py` read a PGO/LTO build's map wrongly: a function in the hot
section is named `hot.__imp__sub_X` there, and every object is an LTO `ltrans` file, so no generated function was seen
as generated and the bulk list had not grown since 2026-11-09 (fixed: the section prefix stripped, an ltrans object's
generated names counted as generated; the app's hooks are still left out by `localize_native.Hooks`). (2)
`tools/localize_native.py` refused every function with a guest atomic: the lwarx / stwcx. pairs (a reservation load into
the local `reserved`, then `REX_GUEST_CAS` on the same word), sync / lwsync fences, and log2f: 3,741 of the 7,367
generated-code samples of four races (lat10, lat12-14). Now (`SASRT_LOCALIZE_ATOMICS`, default on; index format 9): a
copy keeps those statements as they are (the running form does the same atomic operations on the same guest words),
and each reservation load, compare-and-swap and fence is preceded by `if (s.Open()) return;`: the guard's logged forms
stop before the first one (that call is then not compared, as for a call outside the copy), the running form folds it
to nothing. log2f is pure.

The bulk list (app/src/cpu/hot/localized_bulk.txt): 999 -> 1,172 (the safe forms, 3 or more samples) -> 1,871 (atomics,
1 or more samples). Left out: 31 functions the app hooks, 5 tiny leaves, 2 raw guest accesses, 2 time-base reads, 1
threaded dispatch, 1 MMIO. About 90 % of the generated-code samples are now in copies.

First console runs of the 1,871-copy build (18:30; PGO profile of 2026-11-09, LTO):
- **hv1** (the dense guard: banjo_hot_guard_calls 4000, period 64): 3,275,697 calls compared with the originals, **0
  differences** (15 differed once and not when repeated: other threads' writes between the two runs; the one
  "DIFFERENCE" line is the hand-written memcpy native's, logged once and not repeated); 1,513 of the 1,869 bulk copies
  reached; 5,087,675 calls not comparable (they reach an atomic or a call outside the copy: expected). 0 fence timeouts.
  The guard's run was slow enough in the menus that the driver's presses ran out at the difficulty select (pressed by
  hand).
- **cp1** (shipping): 23.54 fps, GPU 35.7 ms, render thread 29.4 ms; the plain code down (Main XThread 25 -> 10 %,
  SlRenderer 19 -> 13 %, SlAnimManager 11 -> 2 %, SlParticleThread 45 -> 9 %), but Main XThread 0.727 samples a frame
  against 0.604 in lat12 (+20 %), spread over functions not localized today too.
- **cp2** (the same NRO, the 878 copies added today off by their keys): 24.55 fps, Main XThread 0.700 a frame. So the
  slowdown is mostly the build, not the new copies running: adding names to the bulk list changes the post-codegen
  analyses (the lists name functions as address-taken), 177 generated files changed, and a function changed since the
  PGO session keeps no profile (docs/pgo-lto.md: "a codegen re-run needs a new profile"; PGO was +9 % fps). Next: a new
  PGO session on the new code (instrumented build in out/nx-pgo-gen, one race, merge, the optimised build), then the
  copies measured against it.

## Item 24: the recording devices' marks (2026-11-10 evening)

The recording worker's NewOp compares the whole device (59 chunks of 64 bytes) at every op: banjo-nx's marks never
applied here. Why: SASRT's create path (`Sa2CreateDevice`, device.cpp) never called `TrackDeviceTouches`, so the two
no-hardware devices the game records on (0x4009E180, 0x400A4F80) had no mark slot (`recording device 0x4009e180: touch
slot 25` = a sink). And banjo-nx's native setters (d3d_native_state.cpp) carry N&B's layout (ZEnable at +0x2E64; SASRT's
own setter sub_82CCC1B8 stores it at +0x3014): they cannot replace SASRT's setters. SASRT's setters, read from its own
dispatch tables (render states 0x831702C0: 101 entries, 92 functions; sampler states 0x83170780: 20), are thunks to the
D3D library at 0x82CCxxxx, each storing a few fixed device offsets and its m_Pending tag (tools: scratch
setter_stores.py; 103 of 121 have exact store sets, the sampler setters store through r3 + the sampler's offset).

Run tv1 (19:03, `sasrt_record_device_slots = true`, `banjo_renut_tags_check = 1`: the verify form, every op compared
whole, each chunk changed without a mark logged once): with the slots, D3D's own dirty tags (m_Pending words 2-4,
`native::TagChunks`) marked 9.8-11 chunks an op and covered every change of a whole race but six chunks: before draws,
chunks 26 and 27 (the command buffer's tile predication words, +0x2B34 = 2, +0x2B40 = 0xC0000000) and 58 (the pixel
shader pointer +0x330C, set without a tag); before resolves, fetch chunks 0, 1 and 11 (cleared on the resolve path).
NewOp now (with the key) compares those three at every op and every chunk at a resolve; banjo's periodic whole compare
(`banjo_renut_tags_check`, 32) stays the net: a change found without a mark is logged and the marks are dropped for
the session. No hook of the game's setters is needed for what the race does.

Run tv2 (19:27, the instrumented build of the new code, `sasrt_record_device_slots = true` with the three untagged chunks
and whole resolves, `banjo_renut_tags_check = 1`): **0 chunks changed without a mark** in the whole race, every op
checked whole; 12-13 chunks marked an op (of 59).

The new PGO session (2026-11-10 19:34, docs/pgo-lto.md's three steps): the instrumented NRO (129.6 MB, out/nx-pgo-gen)
ran one race with the shipping toml and the recording marks on (run pgotrain; the session's stream sasrt_pgo_3.stream,
tv2's sasrt_pgo_2 left out); the marks held all race (100 % of ops from marks, 9-25 chunks an op, 0 changed without a
mark, a whole check every 32 ops). Merged into pgo/ (417 .gcda; the 2026-11-09 profile kept in pgo_1109/), then the
optimised build (PGO + LTO) of the 1,871 copies and item 24.
