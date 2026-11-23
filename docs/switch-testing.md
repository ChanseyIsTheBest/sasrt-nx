# Testing sasrt-nx on the Switch

## SD card layout

```
sdmc:/switch/sasrt-nx/sasrt.nro               the game (optimised codegen; the only NRO, see below)
sdmc:/switch/sasrt-nx/sasrt.toml              settings (app/sasrt_switch.toml)
sdmc:/switch/sasrt-nx/configs/                premade variants of sasrt.toml (enhancements off, verify mode, ...)
sdmc:/switch/sasrt-nx/sasrt_shaders.mesp      shader package of the NVK renderer (unused by the driver-free NRO)
sdmc:/switch/sasrt-nx/sasrt_shaders.mesp.idx
sdmc:/switch/sasrt-nx/deko3d_shaders.bin      compiled shaders of the native deko3d renderer (configs/sasrt_renderer_deko3d.toml)
sdmc:/switch/sasrt-nx/game_root/              your game files (the extracted Games on Demand folder, 22 files)
sdmc:/switch/sasrt-nx/dlc/                    optional: DLC packages (out\pc\dlc)
```

`tools\win\build_switch_package.ps1` builds the NRO, checks it and lays out this whole folder in
`out\nx\sdcard\switch\sasrt-nx` (`tools\win\package_switch.ps1 -IncludeGame` does the last step alone): copy it to the
card as `switch\sasrt-nx`. A `sasrt_optimised.nro` left on the card by an earlier package is outdated: delete it.

The asset cache (`game_root.nxpack` + `game_root.nxidx`, one file in place of the folder) works too:
`package_switch.ps1 -IncludeGame -Pack` builds it on the PC. It is off by default for this game: the data is only 22
files, and the pack is 4.7 GB, over the 4 GiB file limit of a FAT32 card (each loose file fits; the largest is
3.1 GB). Use it only on an exFAT card. When a pack exists it is used instead of the folder.

## Launching

Start it with a title takeover (hold R while starting a game, then open the Homebrew Menu), or with a forwarder that
has full memory. From the Album applet there is not enough memory.

The first session compiles the pipelines as the game first uses them (short stutters in the first menus and races);
the list is kept next to the NRO, and the next sessions recreate those pipelines at start in the background.

The shader package covers all 20 tracks (1,982 shaders, harvested from every track with the 100% save; 59 MB plus a
4 MB index). Only the index is held in memory; each shader is read from the package when it is first used, so a
track you have not raced before stutters a little more the first time. The NRO and `sasrt_shaders.mesp` must come
from the same build: copy them together.

## Driving the console from the PC (sys-botbase and sys-ftpd, 2026-11-08)

With sys-botbase (masagrator's fork, TCP 6000) and sys-ftpd-light (TCP 5000, anonymous) running under Atmosphere, two
scripts drive a test run over the LAN. They are rr6-nx's `tools/switch_remote.py` and `tools/console_run.py` of
2026-11-04/05 (credit the Ridge Racer 6 port), adapted to this port's names; the console's address comes from
`--host`, the `SASRT_SWITCH_HOST` environment variable, or `out/switch_host.txt`.

```
python tools/switch_remote.py shot [out.jpg]       the screen (pixelPeek)
python tools/switch_remote.py click A              taps; hold BTN [ms]; chord A B X Y [ms] (the shadow dump's press)
python tools/switch_remote.py stick L 0 1 [ms]     a stick, -1..1
python tools/switch_remote.py title                getTitleID (0 on the home menu)
python tools/switch_remote.py ls [path]            the card, inside /switch/sasrt-nx only; get, put, rm likewise
python tools/console_run.py NAME --toml FILE [--nro FILE] --script "5:click A,60:shot,..." --until 460
python tools/console_run.py NAME --logs-only       fetch the newest sasrt_*.log and logs/rex without pressing anything
```

`console_run.py` uploads the toml as `sasrt.toml` (and the NRO as `sasrt.nro` when given), presses A once on the
home menu, waits until this game's title id is the running one, runs the timed actions (`shot`, `click X`,
`press ZR`, `release ZR`, `stick L x y`, `chord A B X Y`), closes the game with HOME, X, A at `--until` (killGame only
if that fails: it leaves the system's error dialog), and fetches the logs into `out/console_runs/NAME` with a sheet
of the screenshots. The rules it is built around: every console run needs the user's word first; only the
`/switch/sasrt-nx` folder of the card is touched (every ftp path is checked, the Album and `/atmosphere` are never
read); before the A on the home menu a screenshot is read and the game's icon must be the selected one (the cursor
is never moved blind; the wrong title running stops the run); one session drives the console at a time; every
switch of a test goes in the one toml. `SASRT_TITLE` in `console_run.py` is 0 until the forwarder's title id has been
read once with `switch_remote.py title` while the game runs: with 0 the script refuses to launch. In Git Bash set
`MSYS_NO_PATHCONV=1` for card paths such as `/switch/...`.

## The NRO of 2026-10-29: the renderer synced with banjo-nx

The renderer now carries banjo-nx's renderer work of 10-21 to 10-29 (docs/deko3d-renderer.md, "Banjo sync 2026-10-29"):
its fast draw path (most draws re-derive only what changed), record-time objects, the replay stream, the fetch cache,
the GPU memory region at the heap's top, per-stage binds, async shader variants and its memory policies. And a fix of
this port's own: textures bound by fetch constant (all of this game's) are answered by the texture memo instead of a
bind at every draw (`sasrt_renut_texture_memo_fetch_only`). The picture should be the same as the 21/10 NRO's (every
piece has a verify mode, all clean in the emulator and on the PC). If something looks wrong or slower, these configs
switch one piece off each (`configs/`): `sasrt_banjo_fast_draw_off`, `sasrt_banjo_record_objects_off`,
`sasrt_banjo_replay_stream_off`, `sasrt_banjo_fetch_cache_off`, `sasrt_banjo_gpu_region_off`,
`sasrt_banjo_async_variants_off`. Please send `logs/rex/*.log` after a race: the "[renut] fast draws" and "texture
slots" lines show the new paths at work, and the frame and render-thread times compare with the 21/10 NRO's logs.

**The far shadows gone every other frame (2026-10-29 evening):** only the console shows it (the PC and Ryujinx do
not; docs/deko3d-renderer.md, "The far-cascade shadow flicker"), so the suspects are the GPU's own depth features the
emulator skips. Three configs in the folder's root, each in place of `sasrt.toml` for one race (rename the original
first): `sasrt_banjo_zcull_off.toml` (no hierarchical depth culling), `sasrt_renut_depth_uncompressed.toml` (no depth
compression), `sasrt_renut_depth_plain.toml` (neither, nor the depth hand-over). A clip of the podium spin after the
race shows it best.

**2026-10-30 (newlogs6 results):** compression off kept the flicker. Both Zcull-off configs stopped during the boot;
the likely cause, a plume bug, is fixed in the 2026-10-30 NRO, which also has the plume multisample and strip fixes
(docs/deko3d-renderer.md). Next round with that NRO, one race each:
1. `sasrt.toml` as it is (the fixes alone).
2. `sasrt_flicker_all_safe.toml`: everything the console's GPU does that Ryujinx does not emulate, off together.
3. If 2 cured it: `sasrt_banjo_zcull_off.toml`, `sasrt_renut_sync_frames.toml`, `sasrt_renut_barriers_full.toml`,
   `sasrt_banjo_upload_uncached.toml`, one at a time.

**2026-10-30 afternoon:** Ristar is bright on the console now (`sasrt_renut_resolve_readback`). The flicker stayed with
the all-safe config ("more frequent"). Next round, one race each:
1. `sasrt_renut_shadow_dump.toml`: race normally. Be in a race within three minutes of launching: at 180, 240, 300 and 360 s after launch,
   four frames of the shadow inputs are written to `shadow_dump/` in the NRO's folder (about 520 MB in all; the game
   pauses a moment at each). Send that folder back with the logs.

**2026-10-30 evening:** that dump hung the console after one frame (the render thread wrote it a row a call), and
colour uncompressed kept the flicker. The new dump writes from a thread of its own and takes only the shadow mask, the
lit scene and the scene depth, 8 consecutive frames every 30 s from 30 s to 5 minutes in (10 windows, 60 MB a
window, 600 MB in all; the game may slow for a second or two at each). `sasrt_renut_shadow_dump.toml` again, one race, in a race by
three minutes after launch; send `shadow_dump/` and the logs. Delete the old `shadow_dump/` first.

**2026-10-30, later:** that run's masks are wrong in some frames on the console (docs/deko3d-renderer.md, the
flicker). Next: `sasrt_renut_shadow_dump_atlas.toml`, the shadow atlas and the mask of the same 8 frames every 30 s
from 30 to 240 s (about 930 MB; the game pauses a few seconds at each while the SD card catches up). Race through all
of it; send `shadow_dump/` and the `logs/` folder (the last run's `logs` folder came empty).

**2026-10-30 night:** the atlas dump had no bad frame, so the dump's own GPU barriers ended the flicker; the fix does
the same by itself (`sasrt_renut_depth_resolve_wait`, on in `sasrt.toml`). Every config now dumps on **A+B+X+Y**
pressed together in a race (the next 8 frames' mask, lit scene and depth, 7.5 MB a frame; press again for another
window). One race each, pressing A+B+X+Y whenever the shadows flicker (and once anyway):
1. `sasrt.toml`: the fix. Do the shadows still flicker?
2. `sasrt_renut_depth_resolve_wait_off.toml`: the fix off (the flicker, as a check that it still shows).
3. `sasrt_renut_depth_resolve_wait_idle.toml`: the fix's cheaper form.
4. `sasrt_deko3d_read_wait.toml`, `sasrt_deko3d_write_wait.toml`, `sasrt_deko3d_clear_wait.toml`: the fix off, one
   other wait each; whichever also ends the flicker names the hazard.
Send `shadow_dump/` and `logs/` after each (or rename the folder per config).

**2026-10-30 late night:** `sasrt.toml`'s fix did not end the flicker (newlogs8), so `sasrt.toml` has it off again.
One race each, A+B+X+Y when the shadows flicker:
1. `sasrt_renut_shadow_dump_late.toml` first: the dump also copies the shadow atlas (19.5 MB a frame). A bad
   frame's cascades show whether the shadow maps or the shading lost the shadows.
2. `sasrt_renut_depth_resolve_wait_copy.toml`, `_texel.toml`, `_idle.toml`; `sasrt_deko3d_compression_off.toml`;
   `sasrt_deko3d_read_wait.toml`, `_write_wait.toml`, `_clear_wait.toml`: does the flicker go?
The `logs/` folder has come back empty twice: send `sdmc:/switch/sasrt-nx/logs/` after quitting the game normally.

**Also (the user asked for more to test at once):** three groups of console-only suspects outside the GPU barriers,
each ran a Ryujinx race without a crash. One race each, A+B+X+Y when the shadows flicker:
3. `sasrt_flicker_shaders_plain.toml`: banjo-nx's shader compiler passes and specialisations off, among them uam's
   dropped reconvergence around branches it takes for uniform (real Maxwell relies on it; Ryujinx does not). It
   stutters while shaders compile at first, so race a lap before judging.
4. `sasrt_flicker_submit_whole.toml`: each frame goes to the GPU whole at the present, with no recording worker
   and no ring cleaner thread.
5. `sasrt_flicker_caches_state.toml` and `sasrt_flicker_caches_data.toml`: Renut's "unchanged, skip it" caches off,
   on the constants' way and on the data's way. Slower.
A group that ends the flicker gets split next.

**The same night, the user's request (as few tomls as possible):** `sasrt_flicker_fix_all.toml` has every candidate
not yet ruled out on the console at once (49 keys; a Ryujinx race at 3.5-5 fps against about 15, no crash), and
A+B+X+Y also copies the shadow atlas after the mask. Race in it first:
- flicker gone: `sasrt_flicker_fix_gpu.toml` and `sasrt_flicker_fix_cpu.toml`, its two halves (one of them ends it,
  and that half gets split next);
- flicker still there: none of these is it; send the A+B+X+Y dump of a bad frame (with the atlas in it).
2. `sasrt_deko3d_color_uncompressed.toml`: does the flicker go?

**2026-11-03 (newlogs9): `sasrt_flicker_fix_all` kept the flicker**, so none of the GPU or CPU candidates is it. Its
dump shows the shading pass giving different masks from near-identical atlas and depth, in every distance band
(docs/enhancements.md, `sasrt_renut_diag_light_volumes = -1`). Next round, one race:
1. `sasrt_flicker_bindings.toml`: race normally and press **A+B+X+Y** whenever the shadows flicker (and once anyway),
   a few presses in all; each press dumps 8 frames and logs every shading draw of those frames with its bindings.
   Quit the game normally (the log's tail is written then). Send `shadow_dump/` and `sdmc:/switch/sasrt-nx/logs/`.
   This NRO (2026-11-03 evening) also carries `sasrt_strip_markers`, rr6-nx's fix of the range draw path
   (docs/enhancements.md), on in every config. If the flicker is gone in this run, that fix is the likely cure:
   confirm with `sasrt_strip_markers_off.toml` (the flicker should come back).

**2026-11-03, late (newlogs10): the bindings were the same in good and bad frames**, and the strips carry no
markers. The one thing new every frame in the shading pass was the scene depth texture, remade each frame for the
game's double-buffered memory; `sasrt_renut_resolve_target_pages` (docs/enhancements.md) keeps it now, on in
`sasrt.toml`. The same NRO debounces the controller (`input_switch_disconnect_grace_ms`, 1 s). Next, one race each:
1. `sasrt.toml` as it is: do the shadows still flicker? Does the "controller disconnected" stop still happen?
2. If the flicker is gone: `sasrt_renut_resolve_target_pages_off.toml` (it should come back).
3. If not: `sasrt_flicker_bindings.toml` again with A+B+X+Y presses, holding the camera still before each press.
Send `logs/` each time (the "kept across its base pages" and "pad N back after" lines are in it).

**23:30: the flicker stayed with the destination kept.** Next, one race with `sasrt_flicker_passes.toml`: hold the
camera still for a second, press A+B+X+Y, keep still another second (the look-behind flips the camera at press and
release; frames right after a flip are wrong by design); a few presses. Each press costs about 300 MB. Send
`shadow_dump/` and `logs/`. The files named "pass" are the mask after each ring's draw.

**2026-11-04, 01:30 (newlogs11): the console's GPU is not at fault.** Each ring's shading draw was redone in software
from the dumped scene depth, atlas and constants (scratch `soft_match2.py`): it reproduces 93-98 % of the pixels the
console darkened, draw by draw, in good and bad frames alike. The bad frame (w4 f2661: a solid black wedge the first
draw painted over the near track, gone the next frame) is shadow acne: the near cascade's stored depth sits
0.0002-0.0003 closer to the light than the shading's receiver depth, which is what a one-frame (6-8 texel) offset
between the cascade's render matrices and the mask draws' c16-c18 gives on sloped ground. In the steady window (w1)
the two agree to 0.3 texel on the console as on the PC. So the atlas and the shading constants come from different
game frames now and then, on the console only; the GPU draws what it is given. The matching caster-pass lines logged
only screen-space quads (c0 = 2^23); this NRO (01:4x) logs the first six world-space casters per frame instead (the
meshes read their matrices from c128-c131 and c136-c143, which the lines now carry; checked on the PC, sasrt_676), so
the next capture shows the cascade's matrices beside the shading's frame by frame.
Next round, one race each, A+B+X+Y as before (each toml also keeps the passes diagnostics):
1. `sasrt_direct_state_off.toml`: the direct renderer off (per-draw state from the ring's packets, not host records).
   If the flicker is gone, the records are a frame stale sometimes; `sasrt_direct_flush_off.toml` then halves it.
2. `sasrt_me_native_plain.toml`: the ring's console-only CPU fast paths off (`masseffect_native_pm4_fast`, fast_pair,
   raw_microcode, flat_identity, compare_fast, fast_copy, indices_cache, CRC fingerprint, dedupe size).
3. `sasrt_clear_repeat_off.toml`: whole clears always sent (a skipped cascade clear would leave the previous frame's
   ground under the new render: the same acne).
4. `sasrt_renut_frames_ahead_1.toml` (in `configs/`): the game one frame ahead, as the PC.
Send `shadow_dump/` and `logs/` of whichever run still flickers; the one that does not is the answer.

**2026-11-04, morning: a cause found and fixed in the NRO (unverified on the console).** The worker's shadow pass was
taken at the composed buffer's splice before the worker had recorded this frame's, so the atlas was a frame behind the
mask's matrices (docs/enhancements.md, `sasrt_renut_splice_ended`, on in `sasrt.toml`). Test order now:
1. `sasrt.toml` as shipped (the fix on): a race or two. If the flicker is gone, confirm with
   `sasrt_splice_ended_off.toml` (it should come back). Send `logs/` of both: the "Renut hooks so far" line's splice
   counts show how often the console lost the race the fix closes.
2. Only if it still flickers with the fix on: the four tomls above, one race each, with A+B+X+Y presses.
The same NRO (09:44) also carries `sasrt_deko3d_copy_wait` (on; docs/enhancements.md): a full barrier when a texture
leaves a copy layout, so a draw cannot sample a texture the copy engine is still uploading (streamed textures' first
frames). Its A/B: `sasrt_deko3d_copy_wait_off.toml`. Not expected to touch the flicker. It also passes 256-rounded
uniform buffer sizes to deko3d (the SharedConstants and float-constants pushes), which devkitPro's debug deko3d had
refused; with those, a 460 s emulator run under the debug library (boot, menus, two minutes of a race) refused
nothing, so what this port asks of deko3d passes its input checks.

**2026-11-04, 11:05 run (the user: "no improvement").** Its 10 s lines settle it: every splice on the console took an
ended, not-yet-taken recording (4,151 taken ended, 0 left, 0 resolved at an end), so the worker's recording is whole
and fresh at the splice there too and `sasrt_renut_splice_ended` changes nothing. The recording itself is not stale;
what reaches the GPU may still differ from it: the ring-side work found that Direct3D patches the packets of the
command buffers it runs from inside a segment after the draw call returned (`sasrt_direct_state_nested`'s note), and
Renut's recorded draws carry the device as it was at the worker's draw call, never the patched packets. Next round,
one race with `sasrt_flicker_pm4.toml`, A+B+X+Y when it flickers: the log's "splice pm4" lines show the casters'
matrix as the buffer's PM4 holds it at the splice and at the submission ("the same" / "DIFFERS"), and the frame's
"shadow caster" lines the recorded snapshot's; the 10 s line counts "differing at the submission". Send `logs/`
(the dumps too if the card has room). The same run's "light volume" and "shadow caster" lines now carry replay tags
(docs/enhancements.md): per bound texture and per draw, the recording (buffer, id, swap counts at Begin / End /
submission) that produced it, so a mask draw whose atlas or scene depth came from another swap's recording than its
own constants shows at once (scratch `tag_table.py <log>` tabulates them per frame). On the PC (sasrt_686) every
frame reads: the mask draws from a recording begun and ended at swap S and submitted at S+1, the casters from the
previous recording (begun/ended S-1, submitted S): the worker's shadow pass is one swap ahead by design and the two
line up every frame; the console's table will show the frames where they do not and which side moved. The "splice
pm4" PM4 compare found nothing to compare: the submitted segments are a single NOP at the submission and the game
fills them afterwards ("changed after its submission" lines; the 360's GPU is behind the CPU), so the packets the
GPU would read do not exist at Renut's replay time. NRO 11:48 on the SD carries all of this.

**2026-11-08, 05:56 run (`sasrt_flicker_pm4.toml`, driven from the PC; 12 A+B+X+Y windows).** The replay tags show
the PC's pairing in every frame, and the atlas matches the shading. The bad frames (the whole ground shadowed, or no
shadow at all) are computed right by the GPU from inputs that disagree: the shading's cascade constants fit the scene
depth of the next frame, not the one it reads, in every frame where the camera moved (docs/enhancements.md, "console
dumps of 2026-11-08"). The recording that holds the shading runs on the GPU before the scene its constants belong to.
Next round: `sasrt_flicker_depth_writers.toml` (NRO 06:37 of 2026-11-08), one race with A+B+X+Y now and then (the
chord turns the camera round while held, which shows the fault strongly): its "seq:" lines and the "src:" part of
the light-volume lines say which draws wrote the scene depth and where the recording's replay lands among them.

**2026-11-08, morning: the flicker's cause found and fixed (`sasrt_renut_scene_same_frame`, on in `sasrt.toml`).**
The worker thread records each frame's scene pass right after the game thread submits, and Renut replayed it a frame
later, under the next frame's shadows, whose camera is a frame newer (docs/enhancements.md). Reproduced on the PC
(the render thread slowed by 25 ms: `sasrt_renut_diag_render_delay_ms`), measured from the log by
`tools/flicker/cam_match.py`, fixed: each submission now replays the scene recorded right after it. Console run of
09:00 (NRO 08:55, `sasrt_flicker_same_frame.toml`, driven from the PC): the shading's camera matches the replayed
scene's in every frame to 0.01-0.03 mrad (before: off by the frame's turn, 1,600 mrad at a camera cut), no fallbacks,
the render thread's longest wait for the worker 5 ms, 23-30 fps as before. The fix off: `sasrt_scene_same_frame_off.toml`.

**2026-11-08, 10:40 and 10:48: the localized copies and natives (NRO 10:36, stock clocks, driven from the PC).**
docs/optimising-functions.md. Run `hot_1040` (the normal toml, direct dispatch): the first race, 4 minutes; generated
code fell from 56.6 % of the samples to 14.8 %. Run `hot_ab` (`banjo_renut_ab_target = 70`, 4 s halves): 97.1 ms of CPU
a frame (all threads) with the copies, 96.8 ms without, 17.7 and 17.9 fps: no measurable saving. The card has the 10:36
NRO and the normal `sasrt.toml` (the copies on, `banjo_hot_guard_calls = banjo_hot_guard_period = 0`).

**2026-11-08, afternoon: the move to the ultimate base renderer and the GPU round (NRO 13:29, not yet on the console).**
The renderer is now the shared Renut base (`D:\renut-ultimate\base`, docs/ultimate-base.md) with this port's fixes,
the same-frame shadow fix kept; the shader package and `deko3d_shaders.bin` are new (copy both with the NRO). Then 15
pixel-identical GPU optimisations (docs/gpu-round-1108.md), 13 on in `sasrt.toml`. What a console run should do:
1. The normal toml, a race: the picture as before (shadows, water, characters, HUD), and the `[sasrt gpu]` and
   `GPU profile` lines.
2. `configs/sasrt_gpu_round_off.toml`, the same race: the round's whole effect (GPU ms a frame, fps).
3. `configs/sasrt_gpu_try_tiled_cache.toml` and `configs/sasrt_gpu_try_lazy_depth.toml`: the two items that are off
   until the console shows the same picture with them (Ryujinx emulates neither tiled caching nor depth compression).
4. `configs/sasrt_gpu_ab_<n>.toml`: one item's in-run A/B; `configs/sasrt_gpu_round_profile.toml`: the GPU time by
   pixel shader and the barriers by cause, for the next round.

**2026-11-08, evening: the second GPU round (NRO 16:41, not yet on the console).** 15 more pixel-identical GPU
optimisations (docs/gpu-round-1108.md, "Round 2"; items 15-29, all on in `sasrt.toml`). The shader package and
`deko3d_shaders.bin` are new again (copy both with the NRO). What a console run should do:
1. The normal toml, a race: the picture as before, and the `[sasrt gpu]` and `GPU profile` lines.
2. `configs/sasrt_gpu_round2_off.toml`, the same race: this round's whole effect (GPU ms a frame, fps).
3. `configs/sasrt_gpu_ab_<n>.toml` (n 15-29): one item's in-run A/B; `configs/sasrt_gpu_trace.toml`: one frame's
   command stream every 600 frames, for the next round.

## The native deko3d renderer, and no Vulkan driver (2026-10-20)

The NRO's renderer is now Renut's Direct3D-level renderer on deko3d (no PM4 ring, no EDRAM emulation;
docs/deko3d-renderer.md), and the NRO links no Vulkan driver (the user's request of 2026-10-20: Mesa's NVK is no longer
in it, 14 MB smaller; `REXGLUE_SWITCH_LINK_NVK` in sdk/cmake/rexglue_switch.cmake brings it back). sasrt.toml selects it
(`sasrt_renderer = "renut"`, `renut_gpu_backend = "deko3d"`, in every premade config too); keep `deko3d_shaders.bin` next
to the NRO (the compiled shader variants; without it the console compiles each one with uam at its first draw, a long
stutter each). This port's NVK renderer (`masseffect_renderer_native`, with `sasrt_shaders.mesp`) needs an NRO built with
the driver. On the PC (D3D12 and Vulkan) Renut's renderer plays a whole race with the right picture, and so does the
driver-free NRO in banjo-nx's patched Ryujinx (boot, menus, World Tour, whole races, no crash; docs/deko3d-renderer.md,
"Status"). Ryujinx runs it at 5-6 frames a second, its CPU emulation, so the console's speed is unknown: please send
`logs/rex/*.log` after a race (the "[renut]" lines give the frame rate and the render thread's time a frame), and say
whether the picture matches the screenshots of the default renderer.

## The NRO of 2026-10-19: banjo-nx's codegen rounds, and no LTO

The NRO in the SD folder was the one of **2026-10-19** (since replaced by the NRO of 2026-10-20 04:57, below: the same
game code plus the Renut renderer): the 2026-10-15 17:25 build (kept as
`out\nx\sasrt_2026-10-15_1725.nro`) plus banjo-nx's codegen improvements of 2026-10-15 to 2026-10-19
(docs/enhancements.md, "banjo-nx's codegen rounds, ported 2026-10-19"). The shader package is unchanged: the one
already on the card belongs to it too.

- **Built without LTO** (the user's rule of 2026-10-19: LTO for final builds only). Every earlier NRO since 2026-10-07
  had it, so a frame-rate difference against the 2026-10-15 build can come from either change.
- **What changed in the game code, all build-time** (nothing to switch on the card): constants of the read-only data
  followed into loops (6,235 more loads folded); 20,801 guest register writes nothing reads left out (+654 record
  forms); link-register write-backs that store what is already there compile to nothing (19,615); the guest stack
  pointer kept in a register across calls in 17,348 functions (chosen by measuring each function's Switch code);
  VMX `vsel` as one NEON instruction (2,220); tiny leaf functions copied into the files that call them (38,401 calls),
  which without LTO is the only cross-file inlining; loop barriers that no longer make the compiler reload the
  context; the renderer thread's bitstream decoder `sub_82EB6B78` dispatching from each handler; three generator
  forms (shift / extract forms of `rlwinm`, float copies through sign operations, the game's prefetch hints).
- **Checked on the PC**: a poison build (every left-out write replaced by 0xDEADBEEF...) through the boot, menus and a
  race with no crash and a correct picture; the PC build's self-checks of every new form (330 million r1 checks, 193
  million link-register write-backs, 273 million folded loads, 476 million proven flush checks in one race: 0
  differences); the post-codegen run is idempotent (a second run over the first's output changes 0 files).
- **On the console, please:** one race on the default config, and say whether it boots, looks and plays as the
  2026-10-15 build did, and send `logs/rex/rex_profile_NNN.log` (the game threads' CPU is what this round is about). If
  anything is wrong only in this build, the 2026-10-15 NRO is the comparison.

## The console test of the 2026-10-13 build, in order

The 2026-10-13 NRO is the 2026-10-08 one plus three things, none of which has run on a console (the 2026-10-12 NRO it
replaces never ran either). docs/enhancements.md has each: "The CPU round of 2026-10-12", "The CPU rounds of
2026-10-13" and "The GPU round of 2026-10-13".

The NRO in the SD folder now is the one of **2026-10-15 17:25** (66,947,269 bytes; `tools/check_switch_build.py`
passed) with a **new shader package** (2026-10-15 17:03, 65,149,932 bytes: vertex shaders now drop the outputs their
pixel shader does not read, which they were meant to do all along, docs/enhancements.md "masseffect_native_vs_pruned_
outputs never worked here"; and banjo-nx's shader items 4 and 2, below. **Copy the package together with the NRO**;
the first races compile their pipelines again): the 2026-10-13 build plus the
2026-10-14/15 items below (the save fix, the codegen ideas, banjo-nx's
EDRAM items including its Clear operation, the dead-draw skip, and banjo-nx's step 4 on the renderer thread), and a
correction of two of the codegen ideas' analyses: the NROs from 2026-10-14 18:22 to 2026-10-15 01:55 had 4 register
write-backs and 10 single-precision operations wrong in 8 game functions (docs/enhancements.md, "A third gap"). If an
earlier one of those NROs is still on the card, replace it. None of this has run on a console.

- **CPU, build-time:** fewer flush-mode switches in the game code (each an `msr fpcr`), no frame pointer in the game
  code, read-only loads as constants, the usual indirect calls as guarded direct calls, registers of call-free loops
  as locals, and the other items of sa2-nx's rounds 2 and 3. These are in the code: no key turns them off.
- **CPU, run-time keys:** compare-and-swap without the trailing `dmb`, signals that skip the wake syscall when
  nobody waits, per-thread counters, critical-section owners from the guest context.
- **GPU:** all 30 plain resolve copies a frame drawn on the 3D engine instead of the copy engine, and five shader
  specializations. **The SD folder's shader package is new (61.7 MB) and belongs to this NRO: copy both.**
- **Long sessions:** resolved textures the game stopped using are released (sa2-nx's fix for "after an hour or two
  shadows glitch, textures turn black, geometry goes missing until a restart"; this port had the same cause).
- **Saving works on the Switch now** (2026-10-14): the first console run crashed when the game created its save.
  The Switch cannot open, or even stat, a file that is already open for writing, and the game opens its save file
  a second time while writing it; the SDK now shares the open file between the two. Please try "create new game
  data" again and say whether the save is there at the next start.
- **A compiler pass is off** (`-mearly-ra=none`): on peggle2-nx's console it produced textures that were garbage
  after their first megabytes, with every PC check clean. Nothing in this game's code showed the fault where it was
  looked for, but if textures or models are partly garbage in the same way every run, say so: that would be the
  same family of fault, which no PC test can see.
- **The codegen ideas of 2026-10-14** (sa2-nx's list of nine; docs/enhancements.md has each, all checked on the PC
  with verify mode): a vperm of one vector as a one-register lookup, fneg / fabs as float instructions, leaf
  write-backs no caller reads skipped, single-precision arithmetic in float where its inputs are singles, small
  memcpy / memset calls inline, the unaligned vector stores without byte loops (all build-time, in the code), and
  natives for memset, memmove and Direct3D's two shader-constant writers (run-time keys `sasrt_cpu_native_memset`,
  `_memmove`, `_d3d_constants_a`, `_d3d_constants_b`, in the `sasrt_cpu_natives` batch: `configs/sasrt_natives_off.toml`
  turns them all off). The start-up self-check has 520 results now; `sasrt_selfcheck_failed.txt` next to the NRO
  means one of the new ARM forms gave another result than its reference: send it. A log line
  `[enh] the game selected the round-up or round-down mode` would mean the float sign forms assumed something the
  game does not keep to: send the log (the PC never saw it).
- **banjo-nx's EDRAM traffic items** (2026-10-14; docs/enhancements.md "banjo-nx's EDRAM traffic items"): the first
  console run spent 43-45 ms of GPU a frame on the EDRAM emulation. Three more overwrite proofs, split tiles (a draw
  that overwrites part of a tile takes it without a copy), rect split, and Direct3D's Clear as an operation (a Clear
  of a whole surface takes the surface's edge tiles whole instead of copying the pitch padding in from the tile's
  previous owner). On the PC with the console's settings: depth imports -17.5 % with the first four, then -82 % with
  the Clear operation; transfer operations -31 %; the PC's EDRAM GPU time about 10.9 -> 9.3 ms a frame. Run-time keys
  `sasrt_gpu_proof_tess_leftover`, `sasrt_gpu_proof_triangle`, `sasrt_gpu_proof_depth_only`,
  `sasrt_gpu_edram4_split_tiles`, `sasrt_gpu_rect_split`, `sasrt_gpu_api_clear`;
  `configs/sasrt_test_edram_banjo_off.toml` turns all six off, `configs/sasrt_test_api_clear_off.toml` the Clear
  operation alone. Found while answering banjo-nx's question about
  which draws pull the transfers: draws that can write nothing (130-170 a frame) are now skipped before their EDRAM
  preparation (`sasrt_gpu_skip_dead_draws`). Two of them imported a whole surface each every frame: on the PC the
  tiles moved fell 16 %. `configs/sasrt_test_dead_draws_off.toml` draws them again.
- **banjo-nx's step 4 on the renderer thread** (2026-10-15; docs/enhancements.md "banjo-nx's step 4"): a resolve
  clears only the sampler cache entries it can affect (`sasrt_cpu_ring_texture_invalidate_range`; the table's misses
  31.6 -> 6.7 % on the PC), and 16-bit indices keep their converted copy across frames in a persistent buffer
  (`sasrt_cpu_ring_index_persistent`; about 4 MB a frame neither converted nor copied). Both are checked in verify
  mode. `configs/sasrt_test_ring_step4_off.toml` turns both off: the A/B of the renderer thread's CPU.
- **banjo-nx's shader items 4 and 2** (2026-10-15 evening; docs/enhancements.md "Item 4 ported, item 1 tried and
  taken out"): the bone-palette and morph vertex shaders load their matrices without a branch per word
  (`sasrt_gpu_vfetch_block`: the 14 such shaders -23 % instructions, half their branches), and in a draw where some
  texture has signs, a gamma curve or a bias, the other textures' fetches no longer run those tests
  (`sasrt_gpu_texture_signs_per_slot`: three quarters of the draws in a race have such a texture; in the G-buffer
  shader PS n1349 it takes about a third of the instructions out). **They need this NRO's shader package.** Off
  configs: `configs/sasrt_test_vfetch_block_off.toml`, `configs/sasrt_test_signs_per_slot_off.toml` (both with the
  per-shader GPU table on, so either one against `configs/sasrt_test_gpu_groups.toml` is the A/B).
- **Which scene shaders the console's GPU spends its time in:** `configs/sasrt_test_gpu_groups.toml`, one race. Its
  log's `[native] GPU time by pass` lines then list up to 48 groups as `[cat C VS600xx PSn: t ms]` per 10 s (600xx =
  60000 + 1 alpha test, 2 blend, 4 depth write, 8 depth test, 16 no colour write; PSn = the pixel shader). Please send
  that log: it says where the next GPU work should go (on the PC the scene cost is spread over many modest shaders).

1. Default config, one race (track 2.3 is the one the PC numbers are from): does it boot, look, play and sound as
   before? The first seconds of the first races compile every pipeline again (new specialization bits: the list of
   earlier sessions, if the card has one, does not match), so judge the frame rate on a second race.
   If a file `sasrt_selfcheck_failed.txt` appears next to the NRO: send it. It is written by the start-up check of
   the instruction forms only the ARM build has, when one gives another result than its plain C++ reference (the
   game goes on; on the PC the 520 results of the x86 forms pass).
2. The profile of that run (`logs/rex/rex_profile_NNN.log`):
   - its header's "FPCR on this CPU" line: what one flush-mode switch costs on the A57. That number decides whether
     the generator's remaining option (`fp_mode_lookahead_past_branch`) goes back on;
   - the game threads' CPU and the frames per second against the 2026-10-08 build's run;
   - "GPU per Swap" and its categories: the resolves' share should have fallen;
   - the "system per second" line's last field: signals with nobody blocked (the wake syscalls saved).
3. `configs/sasrt_test_gpu_round13_off.toml`, the same race: the six GPU keys off (same shader package). The
   difference in "GPU per Swap" and in frames per second is the GPU round's share. If the picture is wrong only in
   run 1, this config tells whether a GPU key is the cause.
4. `configs/sasrt_test_cpu_round12_off.toml`, the same race: the CPU run-time keys' share. The build-time parts stay
   on in both, so this A/B understates the CPU rounds.
5. `configs/sasrt_test_edram_banjo_off.toml`, the same race: banjo-nx's EDRAM items off. Compare the "GPU per Swap"
   line's `edram_import`, `edram_export` and `edram_alias` with run 1. If something is drawn wrongly only with the
   items on (a block of wrong colour or depth at a tile's edge, 80x16 pixels or a part of that), this config tells.
   `configs/sasrt_test_dead_draws_off.toml` is the same for the skipped dead draws (only if something is missing
   or wrong that the first config does not cure).
6. Only if the frame rate falls from 30 straight to 20 in a heavy race (not to 25-29):
   `configs/sasrt_test_vsync_relaxed_on.toml`. On the PC this game is not held to the vsync tick when a frame is
   late, so the key is off.
7. **A long session, when there is time for one** (an hour, several races and menus in one go): nothing should
   degrade. Please keep its `logs/rex/rex.log`: every 20 s it has a line `[native] targets: N resolved textures,
   ... hold M MB; K released when idle so far`. N and M should stay in the same range all session. The same log
   has `[native] C3 slots: 2D N of 4095 in use, 3D ..., cube ...` every 20 s: no heap should creep up to its
   limit, and `views found no slot` must stay 0 (`configs/sasrt_test_texture_slots_off.toml` is the old behaviour:
   on the third track or so the cube maps would run out and new ones be drawn black).
   `configs/sasrt_test_resolved_retire_off.toml` turns the release off (N and M then grow with every scene); use
   it only if a texture or a shadow goes wrong and you want to know whether the release did it.
8. If anything misbehaves only in this build and no off config cures it: it is build-time. Say so; the
   2026-10-08 NRO is the comparison.

The profiler's caller chains stop where they reach a game function (the game code has no frame pointer); the pc
samples, and so the per-function profile and `tools/hot_order.py`, are unaffected.

## The console test of the 2026-10-08 00:01 build

The 2026-10-08 00:01 NRO is the evening build below plus two fixes for vertex shaders Direct3D patched beyond an exact
match (`sasrt_gpu_vs_swizzle_variants`, `sasrt_gpu_vs_fetch_reorder`; docs/enhancements.md): such draws were dropped.
They only act on loads that used to be dropped. If something now draws wrongly, `configs/sasrt_test_vs_identify_off.toml`
turns both off to tell; a `shader_misses/` folder next to the NRO, if one appears, holds any vertex program still
unidentified (worth sending back).

### The 2026-10-07 evening build's tests

This build changes more at once than any before it, all checked on the PC first (verify mode on three tracks, 0
differences):
- the native Direct3D layer (`sasrt_api_draws`, `sasrt_api_clears`): DrawIndexedVertices, DrawVertices,
  DrawVerticesUP, Clear and the window scissor writer are native code that writes the ring's records (no PM4);
- the codegen: `non_argument_as_local` (r0/r2/r11/r12/f0 as locals) and the game's 127,349 jump-thunk calls as plain
  direct calls;
- the compiler set sa2-nx ships: LTO with `-fipa-pta`, and the hottest functions first in the code (from a PC
  profile for now).

1. `sasrt.toml` (the default): boot, menus and one race. If it stops early or misbehaves where the 15:21 NRO did not:
   say how far it got, then run `configs/sasrt_test_api_off.toml` (the native Direct3D layer off). If that one plays,
   the layer is the cause; if it does not, the build-time changes are (codegen, LTO): say so and the next NRO is built
   without LTO to tell those apart.
2. The native layer's A/B: `configs/sasrt_test_api_off.toml` at the same spot of the same race as run 1, or one run
   with `sasrt_ab_keys = "sasrt_api_draws;sasrt_api_clears"` in `sasrt.toml` (the `[ab]` lines: whole-process CPU per
   Swap is the number; on sa2-nx's console these calls' PM4 encode and decode was 8-9 % of the game thread). Watch the
   Swaps per second: peggle2-nx's native Clear stops its game after about 20 s (open there); this game's ran every PC
   run without a stall. `configs/sasrt_test_api_zero_ahead_off.toml` is the A/B of DC ZVA on the layer's ring.
3. `configs/sasrt_cpu_verify.toml`, one race: the `[verify]` lines and the `[api] native records` line must say
   `0 differences`.
4. Please send back `logs/rex/rex_profile_NNN.log` of run 1: it replaces the PC-made hot-function order
   (`tools/hot_order.py --profile`) in the next NRO.

The older tests below still apply.

### The 2026-10-07 morning build's tests (still useful)

1. `sasrt.toml` (the default): boot, menus and one race. This was the first console run with the new codegen
   (registers as locals, docs/enhancements.md "Build-time"): it either plays or stops early. If it plays, the logs
   carry the ring thread's own time per frame (`[native] ring thread: ...`) and the CPU profile.
2. The round's console A/B, either way:
   - `configs/sasrt_test_ab_round.toml` (easier, one run): the round's six ring keys switch off and on together every
     2 s during the run. Every 10 s an `[ab] window` line gives both phases' ring time and the ring thread's own CPU
     cycles per draw (Horizon's thread ticks scaled to A57 cycles at 1,020 MHz). On the PC,
     `python tools/ab_summary.py <log> --from-window N` adds up the race windows.
   - `configs/sasrt_test_ring_round_off.toml` at the same spot of the same race as run 1: the six keys off for the
     whole run.

   On the PC the round measured −21 to −33 % ring cycles per draw and −15 to −23 % whole-process CPU per frame.
   The direct renderer's step 2 (`sasrt_cpu_direct_flush`, from the build after 09:30) only works inside draws that
   `sasrt_cpu_direct_state` converts, so this A/B switches it with the round. Its own A/B is
   `configs/sasrt_test_direct_flush_off.toml`, or `sasrt_ab_keys = "sasrt_cpu_direct_flush"` in `sasrt.toml` (one
   run; the `[ab]` lines' whole-process CPU is the number, since it saves work on the drawing thread, not on the ring).
3. The keys added around 11:00 (all on in `sasrt.toml`), if there is time for more A/B runs:
   - `configs/sasrt_test_vertex_binds_off.toml`: vertex bindings (an NVK macro each). The `[ab]` lines of
     `sasrt_ab_keys = "sasrt_cpu_vertices_base_zero_r0;sasrt_cpu_ring_bind_changed"` give both phases' bindings per
     draw and ring cycles per draw.
   - `configs/sasrt_test_note_shader_off.toml`: the drawing threads' shader notes (a mutex four times per draw
     before). Compare the drawing threads' CPU % in `rex_profile.log`.
   - `sasrt_ab_keys = "sasrt_cpu_native_sub_82e7f918"`: the SlRenderer thread's tiling-like loop as a localized copy
     (−24 % of its samples on the PC).
4. `configs/sasrt_cpu_verify.toml`, one race: every fast path checked on every use (slow). The `[verify]` lines must
   say `differences: 0`.

If run 1 stops early or misbehaves where the previous NRO did not, the codegen round is the first suspect: say how far
it got.

The log is written by a thread of its own since the 13:14 build (the current NRO is from 13:18) (`log_file_writer`, futari-nx's fix for the SD-card
hitches): up to a second of the newest lines reaches the file late. A crash report (`rex_crash.log`) carries the lines
not yet written. A `[log] N lines dropped` line means the writer fell behind; it should not appear.

Since the 15:21 build, guest thread stacks are kept in a small pool (sa2-nx's fix for second-long hitches when a
thread is created). A `[threads] creating a thread with a ... KB stack failed` line says which resource was missing
(heap block, stack region or kernel thread slot): worth sending back if it appears.

## What to send back after a run

- `sdmc:/switch/sasrt-nx/logs/` (the whole folder): the native renderer writes a report every 10 s (swaps, draws,
  rejected draws, unidentified shaders, GPU time per category).
- `sdmc:/switch/sasrt-nx/shader_misses/` if it exists: every shader the package lacked (the next package adds them).
- How far it got (boot screens, title, menus, a race), and anything that looks wrong, with a photo if possible.
- Which config it ran with, if not the default `sasrt.toml` (the first `[enhancements]` log line names the build,
  its date and its codegen flavour, and lists the keys that were on).

## Enhancements (CPU and non-CPU)

Every enhancement has its own key in `sasrt.toml` and two master keys (`sasrt_cpu_enhancements`,
`sasrt_noncpu_enhancements`); see `docs/enhancements.md`. The log shows:

- `[enhancements] sasrt-nx build ...`: which build this is and which enhancements are on;
- `[enh] uses in the last 10 s`: that they ran (the GPU wait also says how long the game thread slept);
- `[verify] checks done ... differences: 0` in verify mode.

The `configs/` folder next to the NRO has premade variants (the A/B pair CPU on / CPU off, natives off, non-CPU off,
all off, verify mode, profile, and the tests of the direct renderer's round: `sasrt_test_direct_state_off.toml`,
`sasrt_test_direct_flush_off.toml`, `sasrt_test_vertex_binds_off.toml`, `sasrt_test_note_shader_off.toml`,
`sasrt_test_vertex_containment_off.toml`, `sasrt_test_vertex_no_fingerprint_off.toml`, `sasrt_test_deferred_on.toml`,
`sasrt_test_ring_round_off.toml` (the whole round off at once) and `sasrt_test_ab_round.toml` (the round switched off
and on every 2 s in one run); every one but verify mode with the profiler on, like `sasrt.toml`). The most useful
console A/B is `sasrt_test_ab_round.toml`, or `sasrt.toml` against `sasrt_test_ring_round_off.toml` at the same spot.

The direct renderer (2026-10-07, docs/enhancements.md "The direct renderer") prints two lines worth sending back:
`[native] ring thread: X ms of work per Swap (Y us per draw, ...)` (the ring thread's own work per frame, the number
the round aims at), `[native] ring per draw` / `targets per draw` / `draw recording per timed draw` (where that time
goes), `[native] vertex containment ...` (the vertex bytes no longer copied) and `[native] direct state (cumulative):
...`, whose "lost" must stay 0.
To use one, copy it over `sasrt.toml`. `sasrt_cpu_verify.toml` checks every renderer fast path against the original
path on every use: slower, and its `[verify]` lines must say `differences: 0`.

## One NRO, comparisons by config

`sasrt.nro` is the only build: the "optimised codegen" (guest registers kept as C++ locals, guest memory accessed
without `volatile`, calls through the game's jump thunks and between functions made direct, a compiler barrier at
every loop header; docs/enhancements.md, "Build-time"). Since 2026-10-07 it also keeps r14-r31 and f14-f31 in
locals (the vector registers stay in ctx, as before: some game functions read an uninitialized one on rare paths),
without their save/restore helper calls or the link-register stores before each
call (`non_volatile_as_local`, `elide_lr_stores`, and the game code compiled with `-fno-math-errno
-fno-trapping-math`). That code shrank by 10 %, and the game threads should need less CPU per frame. It also skips most
of the `msr fpcr` writes the generator put around scalar float moves in VMX code (`fp_moves_modeless`, sa2-nx's: on
the A57 each one stalls the pipeline). Since the 2026-10-07 evening build r0, r2, r11, r12 and f0 are locals too
(`non_argument_as_local`), the calls through the game's jump thunks are plain direct calls, and the NRO is linked
with LTO and `-fipa-pta`, its hottest functions first (sa2-nx's compiler set). There is no second NRO to compare
with (the user's rule of 2026-10-06): every feature is compared through its `sasrt.toml` key and the premade configs
above, at the same spot of the game, with one change between the two runs. The build was checked before packaging:
it names the optimised codegen, it has no infinite loop the compiler could have made from a guest poll (only the
game's own halts), it carries the NVK driver (Mesa 26.2.2), its start-up code is at address 0, and no vector fused
multiply-add leaked into the game code.

## The profiler (CPU and GPU)

The profiler is on in `sasrt.toml` and in every config of `configs/` except `sasrt_cpu_verify.toml` (verify mode checks,
it does not measure): every run brings its profile, and the two runs of a comparison pay the same cost.

- CPU, `switch_profile_stacks = true`: every busy thread's code address is sampled every 1 ms. The 10-second report in
  `logs/rex/rex_profile_NNN.log` lists each sampled address with its count; on the PC,
  `python tools/switch_hot_functions.py rex_profile.log --map out/nx/sdcard_sasrt.map` adds them up per function. That
  map is the one of the NRO in the SD folder (the package step keeps it; `out/nx/sasrt.map` is the last build's, which
  may be newer than the NRO on the card).
- GPU, `masseffect_gpu_marks_categories = true`: the "GPU per Swap" log lines give the GPU time per pass category and
  the idle gap. The image does not change.

Both are plain keys: the enhancement masters (`sasrt_cpu_off.toml`, `sasrt_all_off.toml`, ...) do not touch them. For
a run without the profiler, set both to false. There is no `logs/rex/stacks_profile.flag` any more: delete it from the
card if an earlier package put it there (it turns the CPU sampler on whatever the config says, verify mode included).

For an A/B of the CPU group, run `configs/sasrt_cpu_on.toml` and `configs/sasrt_cpu_off.toml` at the same spot: their
`rex_profile.log` and game logs compare side by side. `configs/sasrt_natives_off.toml` is the A/B side for the native
replacements of hot game functions (docs/enhancements.md, "Native replacements"): everything as `sasrt_cpu_on.toml` but
that batch off; compare the game threads' CPU in the two `rex_profile.log` files at the same spot.

An older `sasrt.toml` left on the card is safe: a key it lacks is turned on when its group master is on (the
`[enhancements]` line counts them as "not in the config, turned on"). Still, copy the new `sasrt.toml` with each new
NRO: it is the tested combination.
