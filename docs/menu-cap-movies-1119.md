# 2026-11-19: menu settings, frame cap, live dynamic resolution, FFmpeg movies, two-player fix

## The game menu's rows (the user's list)

The user: "SMAA, handheld resolution, docked resolution (active if DR is off), dynamic resolution on/off, dynamic
resolution handheld maximum, dynamic resolution handheld minimum, dynamic resolution docked maximum, dynamic resolution
docked minimum, make sure xbox layout is on by default, framerate cap so we can increase the max framerate of the game to
60 let it be adjustable in increments of 5, make sure dynamic resolution targets the adjust framerate use the same ratio
we use now", and "make sure as much as possible can be changed immediately when the game is running and take effect".

- **Framerate cap** (`frame_cap`, 30-60 in steps of 5; renut_engine/gpu/sasrt_renut_pacing.cpp): 30 is the game's own
  presentation interval (TWO), as before. Above 30 the Swap is released at the cap's period: 60 on the display's refresh
  (banjo_display_sync), 35-55 on the pacing's own timer grid (not a whole number of refreshes: an image shows for one or
  two refreshes). Live (BlurSetFrameCapLive). The user's session (log 289, own clocks) raced at 50-60 fps with the cap at
  60 and the 3D at 540 lines.
- **Dynamic resolution** follows the cap: the budget is `banjo_renut_dynamic_gpu_ms x 30 / cap` (32 ms at 30 is 16 ms at
  60, the same share of the frame; surfaces.cpp DynamicBudgetMs). The CPU side's time still raises it
  (sasrt_dynamic_cpu_aware).
- **Dynamic resolution on/off and its four ends** (`banjo_renut_dynamic_resolution`, `_handheld_low/_high`,
  `_docked_low/_high`): no longer kInitOnly; the latch (LatchResolutionScaleLocked) builds the steps again when one
  changes (BuildDynamicSteps). The menu keeps a range's minimum under its maximum (the other end moves past it).
- **Fixed heights** (`banjo_renut_render_height_handheld / _docked`) always listed now, dimmed and tagged "used with
  dynamic res off" while dynamic resolution is on (and the ends "used with dynamic res on" while it is off). Heights in
  steps of 36 lines (64 pixels: whole 16:9 sizes): 360-720 handheld, 540-1080 docked.
- The heavy rows (the heights, dynamic resolution) take effect half a second after the last press, while the menu is open
  (Setting::apply_pending; not each step on the way: each height makes a set of render targets), and at the close.
- **SMAA** on and off at once; the game's FXAA it replaces comes back only at the next start (its pipelines are built
  with the replacement: sasrt_smaa_replaces_fxaa).
- **Xbox layout** (`input_xbox_layout`) on by default (sdk/src/input/switch/switch_input_driver.cpp). The console scripts
  press the Switch's B to accept since (tools/console_race.py CONFIRM; SASRT_CONFIRM=A for a toml with it off).
- New strings are English only (the other languages' rows end before them: Tr gives the English).

## The movies by FFmpeg (the user: "a native ffpmeg decoder for the videos ... like ... tw2de_nx")

`app/src/cpu/sasrt_usm_ffmpeg.cpp`, from tw2de_nx's tw2de_usm_ffmpeg.cpp (THIRD_PARTY_NOTICES.md). SASRT's CRI Sofdec is
TW2's version (the decoder's fields at the same offsets). The slice loop `sub_82EA4F08` is hooked and done natively (its
slice decoder `sub_82EA4B88` is a machine copy in place, so it cannot be hooked); each slice's bytes are taken off the
stream joint as Sofdec consumes them, and FFmpeg's mpeg2video (MPEG-1) decodes the picture into the guest's planes.
`sasrt_usm_ffmpeg` 0 Sofdec, 1 FFmpeg (default), 2 both compared. FFmpeg: `sdk/thirdparty/FFmpeg/config_sasrt_usm.h`
(included at the end of config.h), mpeg12dec.c / mpeg12.c / mpeg12data.c in the SDK's list, the codec list's entries;
the app links libavcodec / libavutil. After adding the hook, `tools/post_codegen.py` (direct_calls --redo) so the callers
call `sub_82EA4F08` and not its `__imp__`.

- PC, mode 2 (the intro): FFmpeg's planes equal Sofdec's (mean difference 0.00-0.01 by plane; +32 U, +36 V, +40 Y).
  Mode 1: 1,780 pictures, 0 failed, 0 black, 2.5-6.7 ms a picture (a busy PC); the sheet of the intro right.
- Console (the user's session 289, own clocks): the intro at its 30 fps (296 pictures in 10 s), 5.1 ms decoding and
  0.6 ms copying a picture, 0 failed. Before (Sofdec, the 15:04 build, stock clocks, c1119_intro_sofdec): 12.4 fps with
  the process at 105 % of three cores (the frames lost to the decoder's thread hand-offs; 21 fps on 11-09).

## Split screen (two to four players; the user: "performance is bad and visually its very very screwed up")

Tested by the PC driving the console with four virtual pads (a custom sys-botbase "2.6-files-kill-pads": `pad N`;
tools/switch_remote.py `--pad N`; the route to a local race in memory and in the scratchpad's split_race.py). Three
causes, three fixes:

1. **The UI redirect after the first composite** (render/draw.cpp, the composite's branch). Each player's view is
   composited separately; SMAA, the upscale to the UI target and its redirect ran after the first, so the next
   player's whole pass drew into display-scale targets (a cropped, banded view; targets made again every frame). Now
   they wait for the frame's last composite: as many as the frame before had (1 in a single player's race and the
   menus, 2-4 in split screen). A first version counted the viewports' coverage of the target; the game also binds the
   target with a half-height header, which one composite covers whole (log 293: the lower half banded again).
2. **The same-frame scene's waits** (sasrt_renut_hooks.cpp SceneSameFrameOn). In split screen the recording a place
   waits for is spliced only after the game's Swap, which waits for the render thread (frames ahead 0): every place
   waited its 50 ms timeout, twice a frame (log 290: 0 same-frame replays, 148 fallbacks a 10 s; 7 fps). While split
   screen was drawn in the last 60 frames, the scene replays its own recording as before 2026-11-08 (no wait); one
   player keeps the same-frame scene. A `[sasrt] same-frame scene off while the screen is split` line.
3. **The SDK's L+R+D-pad menus** opened by the game menu's buttons on single Joy-Cons: `input_sdk_menu_shortcuts`
   (off).
4. **Each view drew the other player's world, water and shadows** (the user: "the shadows and the water move with
   the oppopsite player on each screen"; and player 2's driver missing: the other camera's recording culled it).
   A composed buffer carries the scene the worker recorded after the submission *before* it; with one view a
   submission that is the previous view's. `sasrt_renut_split_scene` (sasrt_renut_hooks.cpp):
   - 1: a submission replays the recordings spliced into the submission (views - 1) before it, its own view's a
     frame late (log 302's video: each view its own world, both drivers drawn; the frame-late scene brought the
     far-cascade shadow flicker back, as the user saw).
   - 2 (default): the same frame's. In split screen the worker *ends* each view's scene recording before the Swap;
     only the splice comes after it (the 50 ms waits of fix 2). A submission opens a place with its view's camera
     (1's recording's: c142-c143, the rotation columns and the position's x, y); a scene recording's End fills the
     open place whose camera is nearest (under 40, or clearly nearer than the others, or the only one; a camera cut),
     else 1's after `sasrt_renut_scene_same_frame_timeout_ms`. Log 303 (two players, the sticks steering them apart):
     535-590 places a 10 s filled at an End, 0-8 fallbacks; the trace's replayed camera equals its own view's
     game-thread camera exactly in 1,033 of 1,039 views (6: window edges, one where both cameras met).
   - 0: as before (the other player's).
5. **A view of sky and sea for a frame or two under load** (2026-11-20, the user: "large full screen flashes or half
   screen flashes ... when cpu and gpu is under stress"; their Album clip 2026112000211800 at the race start). The
   worker splices a view's recording into the next composed buffer right after its End; loaded, the game submits that
   buffer first (log 305: 32 submissions named no recording around the countdown, then none). Such a submission ran
   nothing: the view drew its sky and sea alone. Now every submission of split screen is a view's place, its fallback
   and camera its view's last place's (a ring of the last `views` places; the End that fills a place updates it), and
   one player's gets a place too (the last scene its fallback); a splice into a segment already submitted is dropped
   (it stayed under the segment's address until the pool came round to it, then ran beside that splice's own), and a
   place whose wait ended is not filled (one too many in the queue goes after one timeout). The other "flashes" in
   the same clips are the game's own respawn wipe (the title logo over a view while its kart is put back on the
   track), frequent there because the test script steers into the walls and the water every 3 s.
   The trace (`sasrt_renut_diag_trace`) has windows of its own now, `sasrt_renut_diag_trace_windows` "first,every,
   count" (the shadow dump's have been stubs since 11-08), its dumps on a long-lived thread (a detached std::thread a
   dump closed the game at its first: log 301), and splice/submit/place/composite/drawn-camera events
   (scratchpad split_exact.py reads them).

Results (console, CPU 1020 / GPU 460.8 / memory 2733 MHz, the user's toml, frame cap 30, Ocean View):

| Players | fps | GPU ms | render thread ms | 3D lines |
|---|---|---|---|---|
| 2 (before) | 7.3 | 41 | 130 | 720 |
| 2 | 27-30 | 20-27 | 17-25 | 540-666 |
| 3 | 22-30 | 21-24 | 23-34 | 720 |
| 4 | 18-20 | 28-32 | 35-44 | 720 |

Every view right in the screenshots (out/console_runs/c1119_split_fix2/p2b, p3b, p4). Four players: the render
thread (2,400-3,200 draws a frame) sets the pace.

6. **Too-dark far shadows in three and four players** (2026-11-20, the user: "player 2 the ocean palace is dark grey
   look at player 1 and 3 it looks fine", "in is in too dark shadows"; open). The user's shot 01:05:27 (log 307):
   player 2's whole distant area flat grey, players 1 and 3 bright, with the 3D at 720 lines (1x) since 01:05:11: state
   left from the race start's dynamic-resolution ramp (540 -> 720 in 1 s steps, codes 4 and 6), not the ramp itself.
   One run with dynamic resolution off (log 310) showed none; another, only player 2 (intermittent). Found on the way:
   - Each view's cascades: the 512x512 depth target 831C391C resolved into a per-view 512x1024 texture (B57DEA28,
     B5698528, B57D4CA8), one resolve a frame each (the near half and the far half by turns); the light passes read
     it through another header (ResolvedAlias). Treated alike for every view in the census.
   - SASRT's shadow maps took the 3D scale (IsShadowMap missed square D24FS8): `sasrt_shadow_maps_native` (off) keeps
     them at 1x.
   - At the split screen's first frames with the 3D below 1x, the UI upscale and redirect ran after the first view's
     composite (the composite count still the single player's 1): "UI colour target for 831C385C: 576x288" and colour
     targets of two scales in one draw; a frame, then the count is right.
   - 2026-11-20 morning (console back at 07:33): clean runs 312 (3P, trace), 313 (4P, trace), 314 (3P,
     `banjo_renut_dynamic_test_s = 1`: 211 steps of the 3D height in the race), 316 (3P, the user's NRO and toml, Album
     captures); dark (the user watching: "Player 1 3 and 4 has the shadow issue this run", "It tends to be dark from the
     start and doesnt change") 317 (4P, rt3a, in-run A/B of 402 and 65). Not the dynamic resolution's steps then: a
     state made when the split screen begins and kept. Every run's first split frame drew views 2-4 into 1x UI targets
     (the composite count still the single player's 1: "Draw binds color targets of different render scales", "UI
     depth target for 831C391C: 576x288", view 2's depth resolve "words owner ... scale 1.000" at a 0.75 3D):
     `sasrt_split_layout_guard` (on) gives a frame whose composite target changed size no upscale or redirect.
   - Tools: scripted players 2-4 (`sasrt_input_script_p2..p4`, synthetic devices with `DeviceInfo::synthetic_user`;
     tools/win/ryujinx_run.ps1 -InputScriptP2..P4; tools/win/input/split3_ryujinx_p*.txt by game frame) and the
     light-volume bindings by view (scratchpad light_views.py), for the emulator while the console is away.
   - 2026-11-20 midday, run 318 (dark, the diagnostics on) read again: the sun pass (9041AFF6) of every view has the
     same constants (c7-c24 equal but the camera's) and its own scene depth (t0) and cascades (t2), each resolved every
     frame (resolves 17 -> 1149 over the race). The first split frame's restore copies of views 2-4 were refused ("the
     resolve's words ... of another scale", words owner at 1.000 under a 0.875 3D), the only depth-alias misses of the
     run. The sun is a full-screen light drawn against the EDRAM depth 831C391C, which the game restores for each view
     from its resolve; away from 1x that restore is the depth alias (SasrtDepthAliasLocked: the bind goes to the
     resolve's own source surface), whose fallback draw is wrong away from 1x. Distant pixels failing the light's depth
     test against a wrong depth would look exactly like this (near lit, distant flat grey, from the start). rt3d's
     light-volume lines name the bound colour and depth surfaces and the depth's alias, and every alias decision in a
     trace window is logged ("[sasrt] depth alias:"); scratchpad alias_views.py sorts them by view (own: the alias is
     t0's source surface).
   - 2026-11-20 12:00-13:10, five four-player runs on rt3d/rt3e, all clean (out/console_runs c1120_p4_rt3d = 319,
     _lowA = 320, _lowB = 321, _lowC = 322, _lowD = 323): 319 (the in-run A/B of the restore suspects) stayed at 720
     lines the whole race, so it tested nothing; 320 and 322 (guard off, banjo_renut_dynamic_handheld_high 630 so the
     split starts at 0.875) had the first-frame redirect exactly as 318 and stayed clean; 321 the same with the guard
     on; 323 used 318's own toml (A/B 402 and 65, host packets) on rt3e with the guard off: clean. So the first-frame
     redirect alone does not make it, and sasrt_split_layout_guard is not shown to fix anything (it stays on: the
     redirect into 1x targets is wrong anyway). In the clean runs every view's sun pass draws against its own scene
     depth (the alias is t0's resolve source, unwritten since), with its own cascades (448x896 at 0.875) and the same
     constants. Dark so far: 307, 308 (the user's NRO), 317, 318 (rt3a), one after another around 09:20-10:00; the
     dark state comes with the race and stays. Still needed: a dark run with rt3e's diagnostics.
   - Not a renderer bug: views showing the game's title logo with a red dot (shots 319 p011, 320 p005, 322 r08, 318
     r08 all four) are SASRT's own loading screen for a view, seen while the scripted bots fall off and respawn.
   - **The cause (2026-11-21, run 336, rt4h's `sasrt_renut_diag_view_dump`: each view's images written to files at
     one frame).** Every view's sun pass reads its cascades from one 512x1024 resolve destination: the near cascade
     resolved into its top half every frame, the far cascade into its bottom half only when the game redraws it, which
     in split screen is at the race's start (on the console that memory then keeps it). The split race starts below
     1x (the dynamic resolution at 540 lines) and the 3D steps up to 720 lines, about one step a second; each step
     makes every resolve destination again for the new scale ("made again: another scale", 296 and 193 in two 10 s
     windows), a new image whose content is undefined. The near half is resolved again the next frame; the far half
     keeps whatever memory the new image got. Run 336's dumps at 30 s and 90 s: the near halves real cascades in all
     four views; the far halves NaN, 3.4e38 and -25.7 (views 1, 2: identical garbage), edge-like garbage (view 4),
     strips of old scene depths (view 3); never a cascade. The shader's compare reads such texels as "lit" or as
     "shadowed" by chance: run 336's read as lit (the far area bright, without its shadows), the dark runs' as
     shadowed (the whole far area at the ambient grey). Everything seen fits: from the start, all race, some views of
     some runs, only at the user's clocks (at the overclock the 3D stays at 1x and nothing is made again), none with
     the dynamic resolution off (310) or in run 319 (1x throughout).
   - **The fix: `sasrt_resolve_remake_carry`** (render/textures.cpp ResolveTarget, render/draw.cpp
     SasrtCarryResolveContentLocked; 1 by default): a resolve destination made again only for its scale or size (the
     same description and format, a 2D single-level image that was resolved into) keeps its old image until the new
     one has its content: the old image (its raw view) drawn into the new one, point sampled and scaled (present_vs,
     ui_upscale_ps), then retired. 1 = depth destinations (the cascades), 2 = colour ones too, 0 = off. A "[sasrt]
     resolve destination ... made again at WxH: its content drawn into the new image" line (the first 8, then powers
     of two). The far cascade then keeps the race start's (scaled, as the console keeps it unscaled).
   - **Verified 2026-11-21 01:45, run 337 (rt4i, the user's clocks 1041 / 460.8 / 1600, four players, the view dump
     at 30 s and 90 s):** every view's far half a real far cascade (the course from the sun; the same in all four
     views, drawn at the start as on the console), no texel outside 0..1, none NaN (run 336, before: garbage in all
     four); 64+ destinations carried at the steps, none failed; all four views bright with their far shadows (shot
     p074); the race at 15.8-17.8 fps, as run 336 (15.8-18.3). Ryujinx with a step a second
     (`banjo_renut_dynamic_test_s = 1`, 210 steps): 256+ carried, 0 failed, nothing else changed. The card: rt4i
     (c1120_card_backup/sasrt_user_rt4i.nro; rt4e kept beside it) with the user's toml.
   - Three players too (run 338, 02:05, rt4i, the user's clocks): all three views' far halves the far cascade in both
     dumps, 64+ carried, none failed, every view bright (p074), 20.5-22.4 fps.
   - And the card exactly as installed (rt4i, the user's toml, no diagnostics; run 339, 06:25, four players): every view
     bright with its far shadows through the race (p072).

## Still open

- The game's speed above a 30 cap is not measured (the PC version runs at 60; this is the 360 code).
- A PGO cycle and a copies refresh for these changes (the test NROs used the 15:04 build's profile); then an A/B.
- The intro's slowness with Sofdec (12.4 fps on the 15:04 build vs 21 on 11-09) is moot with FFmpeg on, but its cause
  (thread hand-offs) may matter elsewhere.

7. **The menus' one-frame flash** (2026-11-20, the user: "can you fix the ocean flash in the menus", "it's hard to
   capture but there was a flash"). Every log, at the main menu ~frame 900 (Ryujinx frame 514): "[flash] texture
   0784582E (format 32) made from guest memory over resolve destination B5640DA8 (1152x544 format 6)". The menu resolves
   an RGBA8 1152x544 image (header B5640DA8) and an FP16 one of the same size (B5640C28) into the same memory (page
   07845); the renderer kept one resolve destination per page (the latest), so an FP16 read while the RGBA8 one held the
   page found another format, ResolvedAlias said no, and the texture was made from guest memory, which the GPU never
   wrote: a frame of garbage. Fix `sasrt_resolve_alias_previous` (on, render/textures.cpp): each page keeps its two
   earlier destinations; a read takes the one of its own description (SameData). In rt4b.
   - 2026-11-21 (Banjo): an apparent +14 % in N&B's draws with the key on turned out to be Showdown Town's day/night
     cycle (daytime draws more; every high run was a daytime one): cleared. SASRT's own draws a frame do not move with
     it either (the 11-19 build without the key 3,457 and 3,454; rt4e with it 3,411).

8. **Clocks and the dark shadows** (2026-11-20): the console ran at 1963.5 / 998.4 / 2733 MHz from ~11:57 to ~14:25 (a
   restart); all five runs then (319-323) were clean, while every dark run (307, 308, 317, 318) and both A/B races at
   the user's clocks again (325: players 1 and 3, seen by the user; 324: dark at the start, then gone) showed it. The
   guard (sasrt_split_layout_guard, on in 324/325) does not prevent it. Next: a traced race at the user's clocks
   (toml out/console_runs/c1120_p4_userclk) for the depth-alias lines of a dark view.
   - 2026-11-20 17:06, run 329 (rt4c, the user's toml and clocks, traced; out/console_runs/c1120_p4_userclk): dark
     views 1 and 3 again (shots p020-p068), bright 2 and 4. The 3D at 720 lines most of the race. Every view takes the
     same path frame after frame: the first restore (colour 831C388C) not aliased (RestoreDepthFromColorLocked draws it,
     right at 1x), the second (831C38BC) aliased to that surface, the sun pass against depth 831C391C gen 355 with its own
     t0 (scene depth, resolved from gen 353) and t2 (cascades). So not the alias or the bindings: the dark views'
     difference is in an image's content (the restored depth and stencil, the cascades, or the scene depth). Next: the
     images of a dark and a bright view read back in the same frame (sasrt_renut_diag_shadow_dump) at the user's
     clocks. Views 1 and 3 (the left column) were the dark ones in 318, 325 and 329.
