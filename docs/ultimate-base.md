# The move to the ultimate base renderer (2026-11-08)

The user's request of 2026-11-08: move this port onto "our ultimate base renderer", the shared Renut base that the Ridge
Racer 6 session keeps at `D:\renut-ultimate\base` (branch `ultimate`, HEAD e0f961a002: katamari-nx 1.0.1 plus the fixes in
`D:\renut-ultimate\MERGES.md`), keep the far-cascade shadow fix (`sasrt_renut_scene_same_frame`), then find and add 15
pixel-identical GPU optimisations. `D:\renut-ultimate` is read-only from here; changes to the base go through the RR6 session
and the user.

## How

A three-way merge, as rr6-nx moved (`tools/ult_merge.py`, `tools/ult_resolve.py`, `tools/ult_conflicts.py`):

| | renderer (`gpu/`) | plume | translator (XenosRecomp) |
|---|---|---|---|
| ancestor | banjo-nx 894d3256 (`out/renut_sources/banjo`) | the same | the same commit, `git archive` (`out/renut_sources/banjo_xr`) |
| ours | this port's GENERATED renderer (`app/src/renut_engine/gpu`: sa2-nx's hybrid tree with every EDIT, the renames and the address maps) | `app/thirdparty/plume` | `app/thirdparty/reblue-XenosRecomp` |
| theirs | the base's `app/src/renut_engine/gpu` | the base's | the base's |

`--generated` merges into the generated tree rather than into the sa2-nx source the generator reads: on the source, 60 of the
port's 471 EDITS no longer applied and about 30 more duplicated the base's versions of this port's own fixes; on the generated
tree every change of both sides showed as a hunk to decide. **`tools/renut_from_sa2.py` is retired for this tree**:
`app/src/renut_engine/gpu` is the source now, edited directly. The pre-move tree, plume and translator are in
`D:\sonic transformed\backup_pre_ultimate_1108` (and `out/renut_sources` keeps the snapshots).

The per-XDK files are this port's whatever the base did (the base's are Katamari's XDK 2.0.5632): `d3d/hooks/*`, `d3d.h`,
`d3d_native.h`, `d3d_native_state.cpp`, `banjo_shared_hooks.h`. So are the device offsets in the merged files (`render/draw.h`'s
chunk boundaries, `render/draw.cpp`'s viewport words, `backend/queued.cpp`'s private range and its 40 compared chunks).

## Decisions

- **This port's fixes the base took** (MERGES.md ports 09-12, 25, 28, 29, 31, 33-37): the base's form everywhere, its keys
  defined once in `gpu/ultimate.cpp` (same names, so the tomls still work). `tools/ult_normalise.py` took this port's own
  definitions out.
- **Keys sa2-nx had renamed** (`sa2_renut_snapshot_deltas`, `_constants`, `_narrow`, `_verify`, `sa2_renut_capture_batches`,
  `sa2_renut_neon_compare`): back to banjo-nx's names, which the base's latched switches read. This port's default stays:
  `banjo_renut_snapshot_deltas_narrow` is off here (sasrt-nx: "off until derived for this game").
- **Keys the base renamed**: `sasrt_deko3d_msaa_positions`, `_a2c_dither`, `_strip_restart` are `banjo_deko3d_*` there, and
  `sasrt_strip_markers` is `rr6_strip_markers`; the tomls use those names now (same values).
- **Kept from this port** (not in the base): the recorded command buffer hooks and their splice / pool / run-at-splice keys, the
  same-frame scene fix (`sasrt_renut_scene_same_frame`), its own frames-ahead (`sasrt_renut_frames_ahead`, the toml's 0) and
  render-thread diagnostics, the recorded binds (`sasrt_renut_recorded_binds`), the recorded streams' capture, the replay
  overrides of surfaces and index buffer, the draw area over every bound target, the video scaler's resolved region, sa2-nx's
  game gamma ramp at scan-out (256 entries from SetGammaRamp), the deko3d package loading and test override, the deko3d colour
  compression and wait keys, the deferred chain (on), the double-buffer key (`pacman_renut_double_buffer`, off as before).
- **Taken from the base** besides its fixes: bangaio-nx's capture pool, delta masks and prefetch; halo3-nx's replay inheritance
  (h1), loop constants, split convert dispatches and export in place (h4); kameo-nx's hand-overs and cheaper scan-out (with the
  present's exponent skip: an output gamma of exactly 1 no longer goes through pow); rr6-nx's depth that covers its colour target
  and strip markers; renut-ultimate's audit fixes 38-41.
- **Dropped**: `g_RtScale` and `sasrt_renut_fixed16_scale` (off here, left out of the base: 16-bit fixed-point targets are FP16
  there, port 28; the shaders multiplied by 1); the translator's sign wrapping around each fetch (the base does it inside the
  fetch helpers). Diagnostics whose code sat in hunks the base rewrote: `sasrt_renut_diag_shadow_dump`, `_convert_check`,
  `_writeback_check` (their keys may remain without effect; re-add from the backup if needed).
- **Shared constants**: the base's 1552-byte layout (1360 the loop constants, 1488 the clip plane, 1504 `g_DepthRemap`).

## Building it

What the first builds needed (each a sasrt-nx comment where it is):

- `app/cmake/sasrt_renut_gpu.cmake`: the base's `gpu/ultimate.cpp` (its switches) added; `gpu/gpu.cmake`: the host
  shaders listed twice once.
- Duplicates the merge left: members of `render/surfaces.h`, the depth write sequence in `render/draw.cpp`, this port's
  `RestoreDepthFromColorLocked` (the base's port 29 stays).
- Declarations and stubs for what one side had and the other not: `REXCVAR_DECLARE` of the base's keys in the files that
  read them (`sasrt_renut_texture_memo_fetch_only` and its verify in `draw.cpp`; the keys `sasrt_renut_hooks.cpp` defined
  before); the base's `LastBindingOf` / `ApplyBindingLocked` (h3 recorded binds, answered by this port's own recorded
  binds: stubs in `d3d/hooks/shader.cpp`); `display_sync::LateInputGuardUs` (0: this port has no late-input guard);
  `KATAMARI_RENUT_HOOKS` in `banjo_renut_select.h` (the hook table is this port's).
- `backend/queued.cpp`: the `DrawCapture` members this port's replay reads (surfaces, index buffer, recorded streams and
  binds), `line_compare.h` for the delta masks, `banjo_renut_snapshot_deltas_narrow` defined once with this port's default.
- The shadow-dump diagnostic (`sasrt_renut_diag_shadow_dump`) is a stub: its code sat in a hunk the base rewrote.
- PC builds are started from the PowerShell tool after `tools\win\env.ps1` (VS 2022, MSVC 14.42). Started from the Bash
  tool they picked up VS 18's 14.51 (precompiled-header mismatches, `__std_rotate` at the link).
- The translator: 337 binary files of the XenosRecomp tree were damaged by a line-ending step of `tools/ult_merge.py`
  (DXC's DLL: exit 0xC000007B) and the zstd build files were missing; both restored from the backup, the script fixed
  (binary files byte for byte). Its intermittent access violation is older than the move (0xC0000409 on 2026-10-20);
  `tools/deko3d_spirv_all.py` tries a shader again when it happens.

## Replay inheritance (h1) off for this game

The first PC run stopped 5.7 s in with an access violation. `tools/win/lldb_*.ps1` did not catch it (under lldb it did
not happen); `sasrt_crash_log.cpp`'s handler (code, address, module offsets and the return addresses on the stack,
symbolized with `llvm-symbolizer`) put it in halo3-nx's `BuildInheritRuns` (`guest/command_buffers.cpp`), called from
`Replay` for a captured run that `sasrt_renut_scene_same_frame`'s slots replay (`QueueCapturedRunSlot`), writing
`inherit_runs` with a data address of 0x6. A captured run shares its command buffers with the live table, and h1 builds
its inheritance data inside the buffer while the game thread may begin recording the same buffer again (which clears
that data): two threads on one vector. `banjo_renut_replay_inherits = false` in both tomls; this port never had h1, so its
replays are as before the move. To take h1 here, the inheritance data would have to live with the captured run.

## Checks (2026-11-08)

- **PC build**: links (11:31), runs.
- **The race on the PC** (`-VideoAt 196 -VideoFrames 40 -VideoEvery 6`, the reference recorded before the move in
  `out/pc/captures_ref_master_1108`): the same scenes, lighting, shadows and HUD; the item in hand differs (the game's
  random item). Side by side: `out/ult_vs_ref_196.png`.
- **The same-frame scene fix**, the render thread slowed by 25 ms (`sasrt_renut_diag_render_delay_ms`), as sasrt_707
  before the move: 3054 places, 3053 filled by the next splice, none fell back, longest wait 3.2 ms (sasrt_707: 3260,
  3259, none, 2.4 ms). `tools/flicker/cam_match.py` needs the shadow-dump windows, which are a stub now (above).
- **Switch**: the deko3d shader package and SPIR-V cache made again from the merged translator
  (`tools/deko3d_spirv_all.py`: 2,058 shaders, 2,007 SPIR-V files, none failed, none needed a retry; then
  `tools/deko3d_shaders.py --no-uam`, `tools/deko3d_glsl_opt.py --check` (all 2,007 compile with uam),
  `tools/deko3d_shader_package.py`, `tools/renut_switch_shader_cache.py --pc out/pc`, `tools/deko3d_variant_cache.py`).
  The pre-move package and cache: `out/renut_sources/renut_switch_pre_ult`, `out/renut_sources/deko3d_shaders_pre_ult.bin`.
  The NRO links (one symbol the base's SDK has and this port's not: `RexGmLatencyTest`, a stub in
  `sasrt_compat.cpp`). Ryujinx: the race renders right (textures, lighting, shadows, water, the skinned drivers), the
  same-frame fix's places all filled by the same frame's splice.
- **Then**: the GPU round (docs/gpu-round-1108.md).

## Sync with the base, 2026-11-13 (ports 45-128)

The user, 2026-11-13 ~02:20: "Get all the blur stuff from the ultimate base. Actually try and sync up with the ultimate
base". Base HEAD 8de5d51a (ports to 128). Backup of this port's sources before it: `D:\sonic transformed\backup_pre_sync_1113`.

**How.** `tools/ult_port_sync.py` takes the base's ports one commit at a time: for each file a commit changes, a three-way
merge (git merge-file) of this port's file with the base's file before and after that commit, so only that port's change
comes in (logs: `out/ult_port_sync_pass1.txt`, `_pass127.txt`, `_pass123.txt`; the ports: `out/ult_ports_1113*.json`).
Ports this port made itself were skipped (44, 46, 49-52, 54, 58, 64, 65, 70-75, 78-83, 85, 89, 93, 119, 121, 122).
Taken: 45, 47-48, 53, 55-57, 59-63, 66-69, 76, 77, 84, 86-88, 90-92, 94-118, 120, 123-125, 127, 128. First pass: 106
files merged cleanly, 34 new files, 136 conflict blocks in 41 files and 25 hand ports, resolved by four agents (SDK;
renderer state and plume; renderer core and the per-XDK hooks; tools, CMake and the CPU files) and checked by hand.

**Left out (not applicable here)**
- 53, 97: this port has neither the base's profiler / WaitForFrameStart nor pacman-nx's display pacing (its own pacing
  already reports its waits); 66, 69: no ImGui dialogs, path wizard, switch_shaders.ps1 or renut_state_tables.py.
- 55 / 103: the guest core layout (RexSetGuestThreadCoresAtStart, ApplyGuestCoreLayoutAtWait): this SDK never had
  banjo-nx's layout code (the app stubs RexSetGuestThreadCoreLayout); 55's per-player button maps (this port's input
  driver has none) and katamari-nx's guest_network gate.
- 76: key 213 (occlusion queries: this XDK's query blocks are 32 bytes, and this port answers them with
  sasrt_renut_query_samples) and the d3d state hooks (this port's state.cpp is not built; its own CaptureSurfaces covers
  key 215).
- 84: SASRT_HOT_LR_ELIDE stays ON (this port's own idea 47; its guards found no difference).
- 94: the variant cache's vertex-shader plain guesses (they need port 44's PLAIN_GUESS table).
- 111, 120: the XMA frame cache keys (this port has no frame cache); 113 and the difftest tools.

**Adapted**
- Viva's shader-round A/B targets 150 / 151 / 152 / 156 are 240 / 241 / 242 / 246 here (this port's gpu_round items take
  A/B 90-172 by index).
- This port's own cuts sasrt_gpu_cut_gather_pcf and _pcf_half moved from sasrt_words[7] bits 9-16 / 17 and constants
  976 / 977 to bits 18-25 / 26 and constants 978 / 979: ports 95 / 99 use bits 9 / 10 and constants 976 / 977 (earlykill
  is on by default, so bit 10 would have turned the gather cut on for fetch constant 1, and each pass skipped itself when
  the other's constant was in the text).
- 123 (CG-13): the base's form replaced this port's own copy of it (CMake BLUR_FPCR_ONE_MODE, OFF;
  `tools/win/pgo_cycle.ps1 -OneMode` builds the A/B in out\nx-onemode*); its census counters are kCensusFpuRegions /
  kCensusFpuDenormal = 77 / 78 here (this port's rounding-mode counters are 73-76).
- 45: in, with this port's lazy decompress; `ultimate_deko3d_depth_resolve_lazy` OFF here (needs a console race with the
  cascades). Its resolvePendingDepth gained what resolveUnboundDepth does (markUsed, the target serial reset): RR6 made
  it base port 129 (with the base's defaults the serial was a live bug: draws with no targets after a null bind).
- 48 / 57: the base's lock-free guest clock came in with them (exact; it also stops the slow drift of the locked path),
  kept working with this port's per-vblank clock.
- 91: the gamma table at scan-out adapted to this port's 256-entry float ramp.
- 105: the lock-free render queue keeps this port's deferred Swap wait (a per-thread flag on the ring path).
- 112 / 118: this port's tomls set switch_guest_stack_mb = 4 (as before) and now msaa_level = 4 (the old default; the
  races make no multisampled target) and, in the PC toml, banjo_renut_smaa = false (the PC never ran SMAA).

**Default-on changes a run may show** (all from the base's defaults): rumble (59); controllers 2-4 signed in as guests
at the sign-in screen (55, xam_guest_signin); clock_nap_clamp (57: a gap of more than 250 ms without a clock read is cut
from guest time); switch_yield_backoff (56); the lock-free render queue (105), tiles once (87), resolve from the sibling
(88), Blur's resolve fixes 211, 212, 216, 217, 219, 221 (76: 219 draws biased resolves scaled: check the picture);
fmadds rounded once (96, SASRT_FMADDS_SINGLE ON: the Xenon's rounding); blur's vector forms (90, 107: post_codegen
steps); the shader round 94 and earlykill 99 (same pixels by the base's difftest), invariant gl_Position (100) and the
7e3 clamp (106, inert: no 7e3 target here).

**Needs before use:** a code generation and post_codegen (90, 96, 107, 108, 124), a new shader package and DKSH cache
(92, 94, 95, 99, 100, 102, 106), PGO retrained; then a Ryujinx guard, a console race against cycle C, and a picture check.
Noted, not fixed: shaders/host/present_ps.hlsl applies param0's exponent twice when banjo_renut_present_no_pow is off
(default on; only A/B 78's off half), an artifact of the 11-08 move.

**Builds and first run (2026-11-13 03:00-05:20).** Code generation with the synced generator: fma_single 4,598 fmadds
rounded once, vec_cvt_fixed 244, vec_shift_whole 449, vec_dcbz_zva 444, vec_prefetch_line 264, card_groups 2,218 groups,
vec_const_fold 403; 1,351 bulk copies. PC build clean (out/pc/sasrt.exe 04:10). Shader package from the shipping 11-08
GLSL (the translator ports 68 / 102 only fix shaders that failed, and none did here; Windows Defender quarantined the new
XenosRecomp.exe as a false positive, so it was not used): out/deko3d_shaders_sync/glsl_opt, 2,007 shaders, every one
compiled by uam (0 kept as before): invariant gl_Position in 583 vertex shaders, earlykill (977) in 1,169 pixel
shaders, this port's cuts at 978 (6) / 979 (1). DKSH cache from the 11 console pipeline lists + --sasrt-guess: 2,946
variants, 15.5 MB, 0 failed (the card's 80 MB cache of 11-11 is in out/console_runs/c1113_card_backup; its keys are
stale with the new text). The synced instrumented NRO's console race (c1113_syncgen): LAP 1, the picture as before, 0
errors in the log, 129 variants compiled on the console in the background (the card cache 16.5 MB after it), rumble on;
no biased resolve (key 219 inert here), no predicated tiles or multisampled resolve (87 / 88 inert). The optimised
build from its stream: one stream merged, 0 mismatches, 664 copies hot.

**First measurement (2026-11-13 05:52 / 06:02, handheld, same session): not yet a verdict.** Cycle C (c1113_ctlC2, with
its own 80 MB card cache) against the synced build (c1113_sync, the 16.5 MB cache after one training race): process
CPU 81.01 -> 89.92 ms a frame (+11 %), but 8.05 ms of it is a thread on core 3 that is the background shader compiler
(95 variants compiled on the console during the race, about 2 s each: the new DKSH cache lacks the specialised variants
the old cache had gathered over many runs). Without it: 81.87 ms (+1.1 %): Main XThread 22.53 -> 22.44, WaterThread
6.49 -> 6.41, render thread 18.71 -> 19.61, SlRenderer 14.51 -> 15.04. 3D resolution 685.9 -> 662.4 lines (GPU 33.6 ms
both): draws with generic pipelines while their specialised ones compile. Ryujinx dense guard of the synced build
(guardSync, 900 s): 1,230 of 1,351 bulk copies reached, 5.3 M calls compared, only the known v0 NaN-sign family (5
functions); 32.3 M stack forwards, 0 differences. Next: warm the cache (races that only compile), then measure again.

**Measured with a warm cache (2026-11-13 06:57-07:30, handheld, one session):** the cycle C controls 81.01 / 80.79 ms
process CPU; the synced build 81.70 (Main 22.28, render thread 19.65: +0.9 ms against C's 18.73); the same with
blur_renut_stack_surface_headers and dishonored_renut_vertex_readable_check off (both add work per queued op / converted
stream and never act here) 80.63 (render thread 19.23, its samples equal to C's): now off in app/sasrt_switch.toml.
So the sync is CPU-neutral (the game threads 0-1 % faster, the render thread back to C's), 0 errors, the picture as before.
**CG-13 A/B** (`pgo_cycle.ps1 -OneMode`, its own training race and profile; msr fpcr in the binary 20,499 -> 4,050):
78.77 ms against the synced build's 80.63 (-2.3 %): Main 22.28 -> 21.33 (-4.3 %), WaterThread -5.4 %, SlRenderer
-2.9 %; one race each. Picture check (c1113_cg13pic, a shot every 10 s, 3 laps with the boat sections): right. Its
measured race's 20 s shot caught a large yellow translucent shape over the car (the racers bunched: most likely an
item hit). NOT bit-exact (scalar denormals flushed): the user's decision; the card runs the synced build without it.

## Sync with the base, 2026-11-19 (ports 133-185)

The user, 2026-11-19: "please sync up with the latest ultimate base" (after the hold of 2026-11-13). Base HEAD 5017fe95
(ports 133-185, 55 port commits). Backup of every file the merge touched and the list of new files:
`%TEMP%\claude\...\scratchpad\sync185\backup`, `copied_new.txt` (the session's scratchpad).

**How.** One three-way merge per file over the whole range (ours / base@61d3f75e / base@5017fe95; `range_merge.py` in
the scratchpad, ult_port_sync.py's merge without the per-commit steps, so no conflict is met twice): 97 files clean, 57
new, 50 with conflicts (about 170 blocks, resolved by three agents for the renderer, the backend / plume and the SDK, and
by hand for CMake, the code generator, the copies and the tools), 21 hand ports (the per-XDK hooks, the base's files
this port has under its own names).

**Taken whole / by hand**
- Port 134 (XMA frame cache v2): xma_context.cpp and context.h taken whole, as the base's building.md section 7 says
  (this port's own lines there were only the absence of Katamari's loop code and the frame cache). Cache on (24 MB).
- Port 151 (small-block allocator, 32 MB): blur_small_alloc.cpp built, enabled in SasrtApp::OnPostSetup.
- Port 150 (guest CAS relaxed, fences split, both on): this port's enhancement table (sasrt_enhancements.cpp) with the
  base's key names; switch_profile_stacks_ms and switch_perf_count_calls there too; tools/guest_fences.py in
  post_codegen (471 fences in 133 files).
- Ports 136 / 140 / 144: post_codegen runs fnm_sign.py (+ its restore), float_loads.py's second pass (--any-mode
  --doubles), near_exact.py (the near-exact switches stay off: helpers with the generator's expression) and the
  near-exact r1 option; not fp_env_files.py (Blur's -fno-trapping-math file list: this port keeps trapping math).
- Port 138's viewport offset (kDeviceOffsetViewport) is this XDK's 0x3168 (title update 3). The queued clears and
  resolves keep this port's whole-device path (its EDRAM views read the destination packet, which the base's lean
  target words leave out); render/draw.cpp has a view-device scope for GatherTargetsWords and the resolve source.
- Per-XDK hooks: ForgetInPlaceShader / NoteInPlaceShader and the in-place memo (port 138), fetch filters (145), the
  bookkeeping after present (161, on), the scaler crop (169, off; from Swap's parameters only here), the setter census
  (177); port 173's unbound hook bodies are compiled, not bound. This port counts g_sasrt_game_frames, not the base's
  g_banjo_game_frames (port 156).
- Port 164's stream convert (four scalars, a switch) in this port's shaders/host/stream_convert.hlsli.

**Changed for this port**
- `banjo_renut_deferred_narrow` OFF here (base: on): a narrowed capture leaves out the device bytes before 0x480 and
  the private words 11008-12223, the same list banjo_renut_snapshot_deltas_narrow keeps off until it is derived for this
  XDK. An A/B candidate after a PC run with banjo_renut_deferred_narrow_poison.
- `input_menu_combo` empty here (base: A+B+X+Y+L+R): no game menu is built (game_menu.cpp is in the tree, not built: it
  needs the base's app layer), and the gate would hide A, B, X and Y from the game while L and R are held.
- XGetLanguage answers rex::system::EffectiveLanguage() as XConfig and the profile now do (key `language`, "System").
- The shader round's A/B target is 243 here (was 240): the base's host batch takes 230-240.
- builders/extra.cpp leaves out ldbrx / stdbrx / vavguw (this port has its own in memory.cpp / vector.cpp; link error).
- tools/near_exact.py reads `*_recomp.*.cpp` (the base's hard-coded renut_recomp.*.cpp: post_codegen stopped).
- The base's frame-draw counter of port 164 is `submit_frame_draws` here (this port's frame_draws is per slot).
- This port keeps banjo_renut_snapshot_deltas_narrow false and banjo_deko3d_eager_kicks true (so port 164's progressive
  submit has no effect yet).

**Left out:** the game menu (177-182: needs the base's app layer and Katamari's frame-cap code), the base's profiler /
stall watchdog files (153, 167: this port has no app/src/profiler), the controller applet and per-player tables of the
input driver, rdc_state.py / run_pc.ps1 / llamadas_directas.py. Port 155's target bias on the colour
(blur_renut_target_bias_rgb, on in code) needs the game shaders translated again with the new shader_common.h; the
package is still the shipping one (the GLSL optimiser did not change), so the constant has no effect until then.

**Builds.** Generator rebuilt (sdk/out/win-amd64/rexglue.exe). Code generation: guest_fences 27 sync / 402 lwsync / 42
eieio, fnm_sign 399, float_loads 1,181 + 195 loads / 979 stores (M-23) + 455 doubles, near_exact 964 / 150 / 133; 1,359
bulk copies (2 new from the c1113_G2 / G5 profiles). PC build clean (out/pc/sasrt.exe 07:27); PC race (out/pc/logs/
sasrt_740.log, video_205s): the race as before, 0 errors, guard 0 differences, XMA frame cache 55 % answered.
Switch builds: the instrumented in-place NRO (out/nx-inplace-gen, 122.7 MB) and the hooked one with guard forms
(out/nx-pgo-gen) compile clean. Ryujinx: the in-place NRO boots and races, forms self-check 45,370 of 45,370 (the base's
new float forms included), 0 errors; dense guard of the hooked NRO (guardSync1119h, 900 s, banjo_hot_guard_calls 4000,
period 64): 1,238 of 1,359 bulk copies reached, 6.19 M calls compared, 0 differences (4,694 register NaNs differing
only in their sign, port 141's rule), 40.7 M stack forwards, 0 differences.

**Ports 186-188 (2026-11-19, RR6's fixes of this sync's three notes; base 6cd02ae7).** 186 (the passes find the
generated files by project name): this port's passes already glob `*_recomp.*.cpp` / `*_pch.h`; its own forms kept,
the base's gen_file() helpers came in unused. 187 (port 144's builders in rex::codegen::extra_insn): extra.cpp taken
whole again (this port's ldbrx / stdbrx / vavguw in rex::codegen link beside them; the main table's entries win). 188
(A/B targets 256-511 are a port's own): sasrt::gpu_round's items moved from 90-172 to 256-338
(`kAbBase = 256`), its render-thread group from 200 to 400, and Viva's shader-round items are the base's 150, 151, 152
and 156 again (243 / 241 / 242 / 246 before). An A/B list written before this (banjo_renut_ab_targets) names the old
numbers: add 166 to a gpu_round item's.

**The game menu (2026-11-19, the user: "can you port the game menu please"; base ports 177-182, Blur's).**
src/game_menu.cpp built (app/CMakeLists.txt: the four embedded fonts in game_menu_fonts.h, imgui's include dirs),
attached by SasrtApp::OnConfigureFonts / OnCreateDialogs when Renut's renderer is active (its overlay drawer draws the
SDK's ImGui). Opened by input_menu_combo (A+B+X+Y+L+R by default again: while L and R are both held, A, B, X and Y go
to the menu, not the game) or F8 on the PC; + closes it; settings written to the config file (sasrt.toml).
- The input driver has the base's per-player maps now (input_p1_* ... input_p4_*, by pad index; BuildButtonTables,
  RebuildButtonMaps for the Controls tabs); empty, they are this driver's mappings exactly.
- Rows of keys this build does not define are left out (base port 189, from this port, RR6 2026-11-19, committed in the
  base but not pushed yet; frame_cap: this port's pacing is its own, so
  BlurSetFrameCapLive / BlurFrameCapNow are stubs in sasrt_enhancements.cpp; the sideways Joy-Con keys), and so are
  MSAA (no multisampled target in this game's races) and the fixed 3D heights while dynamic resolution is on.

**PGO cycle (2026-11-19 14:11-14:27, console, handheld 1020 / 460 / 1600).** The instrumented in-place NRO (out/nx-inplace-gen,
10:51) on the card with the shipping toml (the 32 ms GPU budget). The first session (c1119_gen, stream 30) pressed A for
only 40 s: the A presses ran out during loading, so the pre-race flyover sat at "A CONTINUE" for the whole drive. A
profile of the flyover, NOT merged. The second (c1119_gen2, stream 31) pressed A for 76 s as the 11-13 cycles did: the
race (lap 1 at 20 s), 0 errors, "game menu buttons: A+B+X+Y+L+R" in the log. Stream 31 alone went to
`pgo_cycle.ps1 -Step use -InPlace`. **Lesson:** `console_race.py OUT menus 76`, not 40, for this game's menus.

**A/B on the console (2026-11-19 15:33-16:06, handheld 1020 / 460.8 / 1600, the shipping toml without the user's two
menu changes, 32 ms budget; new, control, new, control).** New: out/nx-inplace (sync through 189 + the game menu, its
PGO from stream 31, LTO; c1119_abN1 / abN2). Control: c1113_cg13b's NRO (the 11-13 tree with CG-13; c1119_abC1 / abC2).
Pooled (2 races each, 50 report windows): fps 28.60 -> 28.90 (+1.1 %), GPU 31.56 -> 31.13 ms a frame (-1.4 %), render
thread 23.61 -> 23.50 ms, process CPU 77.74 -> 77.57 ms a frame (-0.2 %); 3D 652-653 lines on average in all four
(dynamic resolution, mostly 630-666). Same-build noise: N1 vs N2 2.1 % process CPU, C1 vs C2 0.3 %. By thread (ms a
frame): Main 21.19 -> 21.19, SlRenderer 14.36 -> 14.55, WaterThread 6.30 -> 6.72 (+6.7 %, both new races), XMA
Decoder 2.44 -> 1.40 (-42 %, the frame cache), render thread (core 1) 19.09 -> 19.31. Verdict: CPU-neutral, GPU and
fps slightly better, 0 errors in all four; the sync and the menu cost nothing measurable. Main's "generated" share
4.4 -> 7.7 % is sub_825B9A80 (not a copy in either build) showing on its own where the control's LTO had inlined it;
Main's total is unchanged. Lead: WaterThread +0.4 ms. The card runs the new build with the user's toml (Xbox layout,
menu opacity 70).

## Sync with the base, 2026-11-22 (ports 190-254)

The user, 2026-11-22: "Next render thread performance after you sync up and do a pgo training run". Base `ultimate`
cebb46af (GitHub main 83b7e242, ports 1-254). Ports 251 (banjo-nx's core-3 command stage, docs/render-thread-ideas-1120.md),
253 (the DKSH cache tool's per-pipeline generics) and 254 (banjo_system_core_uam off) were already in by hand that
morning; 252 is Katamari's tomls only. Ports 190-250: one three-way merge per file (ours / base@6d5ba1d4 port 189 /
base@7754b5a6 port 250; the 11-19 sync's range_merge.py, scratchpad sync250/), backups out/sync250_backup, the generated
tree before the post-codegen run out/sync250_generated_before. 43 files clean, 15 new, 28 with conflicts (about 75
blocks: the renderer's and the SDK's by two agents, CMake, the tools and the hand ports here).

**Taken, with this port's own forms**
- Renderer (ports 233-249, banjo-nx's render-thread rounds): RefreshEffective / the one-byte On() of the GPU round (237,
  245) with SASRT's groups 401-403 added to it (the base knows only 400); FillTextures' skips (246, A/B 170: a sampler
  cut change now also moves g_texture_bind_gen, since SlotLastEpochHolds skips BindingEpoch, which holds
  g_sasrt_sampler_generation); PrefetchShaderBehind (247, A/B 171) under port 251's gate; the per-draw counts with the
  logs (244); the census compiled out of the Switch build (236: RENUT_DIAG_CENSUS_OFF on sasrt_renut_gpu and sasrt;
  SASRT's inline CensusOn / stage census On() become constant false); BANJO_SWITCH_RENUT_DEBUG_INFO (239); the urgent
  compile without a rest and Deko3DHurryCompiles (234, 241); banjo_renut_ring_spin_us (249, 0); port 250's
  banjo_deko3d_copy_run_barriers OFF (Blur's fringes). Port 242's -fno-threadsafe-statics was already SASRT's (its
  render-thread round 2 #10); SASRT's census latch (round 2 #9) replaces port 233's.
- SDK: port 203's one Horizon file per path for files outside the read-only roots (saves, profiles: a lock per file
  over each transfer) beside SASRT's own descriptor sharing for the game files (filesystem_shared_handles = false: SASRT's
  for all, as before); 218 (read-only files keep their host handle, parked handles closed and retried); 192 (a semaphore
  release wakes one thread per count); 198 (XMA freeze fixes, into culdcept-nx's xma_context.cpp cleanly); 205, 210,
  215 (ImGui path), 216 (switch_message_box_focused on: a message box was never shown on the console before), 217, 220;
  195's input_stick_deadzone; 206's fire-on-release for the L+R+ZL A/B lap; 211's SetGuestWaitHook stored but inert
  (SASRT has no per-wait hook).
- Build: port 193's build stamp (src/build_stamp.cpp, app/cmake/build_stamp.cmake; "[build] ..." the first app log line;
  "no-git" here), 194's conditional zstd link.
- Tools / post-codegen: 191 (pointer_fixpoint), 199 (stack forwarding ends at every branch and call), 200
  (inline_memcalls lists; SASRT's addresses kept), 224 (reg_liveness, indirect_calls), the new census and profile tools.
  post_codegen.py re-run: 59 game files and 387 copy files really changed; stack forwards 510 (11-19) -> 555 (the inputs
  changed since; the pass now stops at every branch and call).
- Hand ports to SASRT's own files: 219 (an indirect call outside the image logged, sasrt_codegen_checks.cpp), 226 (256
  denormal sites, sasrt_enhancements.cpp; REX_NX_FCTI_NO_NAN in sasrt_forms_selfcheck.cpp).

**Changed or left out here**
- `sasrt_renut_depth_restore` ON in the code again (port 202 made it off for Sonic 4's sky; this game needs it).
- Port 196's "Shown" FPS counter (display_sync.cpp) and 208's banjo::renderdoc::GameFrame() tick (frame_stats.cpp): not
  called (no renut_engine/Fps.h overlay, SASRT's own RenderDoc in src/sasrt_renderdoc.cpp).
- Port 221's input_script_p2-p4 (SASRT's app script has them), the Switch keyboard halves of 215 and the L+R+ZR applet
  half of 206 (SASRT has neither), cvar LoadConfigString, the base's no-trapping-math CMake (SASRT keeps trapping math),
  run_pc.ps1 / build_pc.bat / cc_*_census.py (as at the 11-19 sync), XDK hooks/shader.cpp's 0x10 containers and
  GetFunction (196, 207: not this XDK's).
- The DKSH cache tool: the base's --round-guess (232) needs port 44's shader table, which this port never took: SASRT's
  own --round-guess on its lists' plain masks (926) instead, with 253's generics: on SASRT's console lists the run-time
  variants of the 11-20 logs not made go 27 -> 5 (with --earlykill-ab); candidate caches out/deko3d_shaders_p253
  (deko3d_shaders.bin: lists + generics + run-time logs, 6,282 variants; deko3d_shaders_rg.bin: + --round-guess
  --earlykill-ab, 8,393). Neither is on the card. The shader package is the shipping one (the translator's 0x10
  support and port 209's define change no shipped GLSL), so the card's cache still fits.
- **The shader compiles on core 2** (the user, 2026-11-22: first "Let the shader compiles float around instead", then
  "Or restrict it to core 2 actually"): new key `sasrt_compile_threads_core` (2; -1 floats them on every core of the
  process, the system core too; -2 the old banjo_* keys) for the uam thread and its spare-chunk thread (plume's
  compileCore / placeCompileThread), the pipeline prebuild workers, the list writer and the cache saver. The ring cleaner
  stays on core 3 (banjo_system_core_compiles = true in sasrt_switch.toml, the user's 2026-11-10 choice). Before, the
  prebuild workers were on core 3 with port 251's command stage, where RR6 saw a compile take 250-354 s.

**Builds.** The instrumented in-place NRO (out/nx-inplace-gen, 127.7 MB) links clean after two fixes above (196's
Fps.h, 208's GameFrame); the hooked one (out/nx-pgo-gen, 156.5 MB) too.

**Ryujinx.** Run sync254a (the in-place NRO, race_ryujinx_slow, 480 s): "[build] Sonic and All-Stars Racing
Transformed switch build no-git" first; the menus, the save opened and read (ast_save, port 203's sharing), the race
(1,300-1,800 draws a frame, ~20 fps under emulation); 0 errors; the prebuild workers and the list writer "pinned to
core 2 (sasrt_compile_threads_core)", the uam thread on core 2 (the ring cleaner on core 2 too here: Ryujinx has no
four-core mode, so no system core). Dense guard guardSync1122 (the hooked NRO, 900 s, banjo_hot_guard_calls 4000,
period 64, banjo_renut_fast_draw_verify): 1,214 of 1,371 bulk copies reached, 3,674,076 calls compared, **0
differences** (4,104 register NaNs differing only in their sign, port 141's rule; 18 differed once and not when
repeated); **17.4 M stack forwards, 0 differences**; 0 errors. fast_draw_verify's "kept or cached pipeline differs"
warning 3 times (the 11-13 guard had it twice, the 11-20 verify runs 4-8 times: not new). Next: the PGO training race on the console (scratchpad pgo_train.sh), `pgo_cycle.ps1 -Step use
-InPlace`, the render-thread runs. The console is held by the user (2026-11-22 ~12:30, "Cant use switch for a while").
