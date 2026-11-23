# sasrt-nx's universal improvements for the ultimate base (2026-11-22)

The user (2026-11-22): "Send universal improcements to ultimate base please". sasrt-nx is synced to the base through
port 254 (docs/ultimate-base.md, "Sync with the base, 2026-11-22"), so everything below is what SASRT has that the
base (`ultimate` cebb46af) does not, and is not SASRT's game alone. Read sasrt-nx's working tree only
(D:\sonic transformed\sasrt-nx); the diffs here are SASRT's current files against base HEAD, **only the hunks that name
the item's key** (tools: scratchpad base_hunks.py): a map for porting, not a patch to apply blind (SASRT's names,
SASRT's A/B numbers).

**A/B numbers:** SASRT's items are 339-364 with groups 401-403 (ports own 256-511 since port 188); in the base they need
numbers below 256. **RefreshEffective** (ports 237/245) knows only group 400: SASRT added its 401-403 there
(sasrt_gpu_round.cpp); the base's needs the same for whatever groups it gives these. **PGO:** these rounds change the
hottest draw-path functions: judge them only after a fresh PGO cycle (SASRT's first build with them was 3.7 % slower on
the old profile, -12 % a frame after a new one).

## 1a. `rt_rounds_base.patch`: the rounds' universal items as a patch for the base (2026-11-22, asked by rr6-nx)

`git apply` on `ultimate` e9b93869 (ports 1-255), from the repo root: 8 files, +469 -33. Made from the base's own
files (each item copied from sasrt-nx's working tree into them), so no SASRT-only code comes with it. On by default,
each its own key (as in SASRT).

| A/B | key | where |
|---|---|---|
| 190 | sasrt_rt2_drop_throttle | draw.cpp DropReplacedRanges |
| 191 | sasrt_rt2_pages_tail | draw.cpp PagesClean (AArch64) |
| 192 | sasrt_rt2_ring_prefetch | backend/render_thread.cpp |
| 193 | sasrt_rt2_readable_memo | draw.cpp GuestBytesReadable + the SDK's `rex::memory::g_page_access_generation` (xmemory.h/.cpp) |
| 194 | sasrt_rt2_texture_memo_two_way | draw.cpp TextureMemoSlot |
| 195 | sasrt_rt2_repeat_ring | draw.cpp WholeRepeatHit / WholeGeometryTry |
| 196 | sasrt_rt2_held_export_bitmap | draw.cpp HoldExport / GetStreamSource / AdvanceStreamCacheFrameLocked |
| 197 | sasrt_rt2_color_alias_memo | surfaces.cpp ColorAliasesLocked, surfaces.h (two fields) |
| 198 | sasrt_rt3_surface_memo_256 | surfaces.cpp GetHostSurfaceLocked |
| 199 | sasrt_rt3_depth_bias_fields | draw.cpp FastDrawLocked |
| 201 | sasrt_rt4_push_runs_merged | draw.cpp PushFloatConstants |
| 202 | sasrt_rt4_state_id_crc | draw.cpp RenderStateIdLocked (AArch64 with CRC) |
| 203 | sasrt_rt4_export_reads_fast | draw.cpp SasrtExportStreamsOnGpu / FastDrawLocked, in banjo-nx's form |

Groups: 241 = 190-197 (round 2), 242 = 198-199 (round 3), 243 = 201-203 (round 4). sasrt_gpu_round.h: the items after
kRtCachedExportSeeds (items 56-68), `AbTargetOf(i)` (90 + i before them; 190 on, 200 skipped), kRt2First / kRt3First /
kRt4First; RefreshEffective and AbName use it. Port 54's group 200 now switches only its own two items, not everything
after kRtRestoreCandidates. kCount is 69: plume counts only items 1-44, so `static_assert(kRt2First <= 64)` replaces
`kCount <= 64` (Report adds plume's counts to items below 64, which the new items never get).

**Left out, beyond your list:** spec_memo (the base has banjo-nx's SpecKeep, A/B 172, doing the same job in
FastDrawLocked; SASRT kept its own memo at the sync), spec_key_skip (it works on spec_memo's answers and measured noise,
+0.09 +- 0.94 %), slot_index (FindHostTextureBySlotLocked is SASRT's own: the base has no such lookup) and
repeat_recorded_index (ReplayIndexBuffer is SASRT's own: the base's WholeGeometryTry and WholeRepeatHit both read the
live header, so they agree already).

**Changed from SASRT's code:**
- readable_memo's counter: SASRT raised it only when Decommit / Release / Protect / Reset / Restore / AllocFixed
  started. A query running beside one of them could read the raised value, see the pages still readable (it takes the
  heap mutex first), and keep that answer after the change. Here a guard (PageAccessChange) raises it again when the
  operation returns. sasrt-nx has the same fix now.
- export_reads_fast in banjo-nx's form (its 2026-11-21 handoff): one render-thread `static GpuStreams`, set only for a
  draw with export streams; BindStreams with the constant `GpuStreams{}` on the common path, so LTO keeps the fast
  path's specialised copy. Switched by the key (A/B 203), not banjo-nx's 305.

**Checked here:** applies cleanly to e9b93869 (a scratch checkout of it), and `git apply --check` passes on the base's
working tree when the patch was written (with your uncommitted 256-258 work in it). Compiled syntax-only with the base's
own commands (`ninja -t commands`), scratch headers first:
- Switch (app/out/switch, devkitA64 GCC -O3): every changed file plus the round header's other includers
  (present.cpp, banjo_renut_deko3d.cpp, pipeline.cpp, ultimate.cpp, banjo_renut_tuning.cpp, textures.cpp,
  command_buffers.cpp): 0 errors, no new warnings.
- PC (app/out/pc, clang++ for x86_64-pc-windows-msvc, in the VS 18 developer environment): the changed files and
  banjo_renut_tuning.cpp: 0 errors, no new warnings.

Not built, linked or run here; that's yours (Katamari PC + Ryujinx).

**Watch for:**
- banjo-nx measured SASRT's whole rounds 2-4 set at ~1 us a draw slower in N&B by day (9.1-9.7 against its lean set's
  8.2-8.6). Its own notes say day and night differ by 10-15 % of draws, and it ran no PGO cycle for the set. It kept
  only export_reads_fast and depth_bias_fields. After a PGO cycle, the groups 241-243 show what each round does on
  Katamari.
- texture_memo_two_way is the idea of blur-nx's #17 (the two-way texture memo, removed 2026-11-18 for ghosting on its
  console). That ghosting was later traced to banjo_deko3d_copy_run_barriers (port 250). If ghosting shows, A/B 194
  first.

## 1. Render-thread rounds 2-4 (sasrt-nx 2026-11-20; `rt_rounds_2_4.diff`)

Measured on the console, 4 players standing still, the user's clocks (1020 / 460.8 / 1600), after a PGO cycle: rounds
2-4 against the 11-19 build, render thread -12 % a frame, -10 % a draw, fps 15.5 -> 16.7, GPU unchanged; as groups in
run: rounds 1-4 -8 % a draw, 2-4 -6 to -7.5 %, 3-4 -5 %, 4 -2 to -3 %. All pixel-identical, each its own key.
The full record and every A/B: `docs/handoff/rt_rounds_1120/README.md` (the item tables, "for Banjo" = universal) and
`docs/render-thread-ideas-1120.md`. Already in the base: round 1 (port 54) and round 2's #10 -fno-threadsafe-statics
(port 242); SASRT's inline census latch (round 2 #9) covers what port 233 does.

Universal (take): round 2 `sasrt_rt2_` slot_index, spec_memo, drop_throttle, pages_tail, repeat_recorded_index (a
correctness fix too), ring_prefetch, readable_memo (**SDK**: `rex::memory::g_page_access_generation`, raised in
xmemory.cpp's Decommit / Release / Protect / Reset / Restore), texture_memo_two_way, repeat_ring; held_export_bitmap
(memexport games); color_alias_memo (with the EDRAM depth restore). Round 3 `sasrt_rt3_` surface_memo_256,
depth_bias_fields. Round 4 `sasrt_rt4_` push_runs_merged, state_id_crc, spec_key_skip (with spec_memo),
export_reads_fast (memexport games). **With export_reads_fast take banjo-nx's two fixes of it** (D:\Banjo kazooie
port\banjo-nx-ult\out\ultimate_handoff_2026-11-21.patch, FastDrawLocked): one render-thread GpuStreams set only when a
draw has export streams (it zeroed ~320 bytes every fast draw), and the export-streams BindStreams call kept apart from
the common one so LTO keeps the fast path's specialised BindStreams copy.

SASRT-only or off (leave, or take off by default): place_wait_unlocked, place_spin, host_packets_split (split-screen
"places"), words_owner_table (SASRT's restore copy), bind_layout_narrow (no effect), pipeline_four_way and
stream_memo_two_way (OFF: slower), ring_lock_once (inconclusive; holding State().mutex across a waiting item can
deadlock), inert_keeps_chain (never fires).

## 2. Resolve fixes (`resolve_carry_and_alias.diff`)

- **`sasrt_resolve_remake_carry`** (on in SASRT; 2026-11-21, `docs/handoff/shadow_carry_1121/`): a resolve destination
  made again at another render scale (every dynamic-resolution step) had undefined content (discardTexture). A
  destination with a part the game resolves only now and then lost that part: SASRT's 3-4 player far shadow cascades
  (the bottom half of one 512x1024 image, resolved only at the race's start) came out as NaN / 3.4e38 / old depths and
  drew flat dark. textures.cpp ResolveTarget keeps the old image (`carry_from`) when only scale or size changed (same
  description and format, 2D, one level, has resolves); draw.cpp SasrtCarryResolveContentLocked draws its raw view into
  the new one (present_vs + ui_upscale_ps, point clamp, scaled), then retires it. Universal: any game with dynamic
  resolution and partly-resolved destinations. Verified on the console (run 337, before / after images there).
- `sasrt_resolve_alias_previous` (the menus' one-frame flash: two destinations of different formats on one page; each
  page keeps its two earlier destinations, a read takes the one of its own description). Banjo found no effect in N&B;
  neither answer is the 360's: OFF by default outside SASRT.

## 3. The shader compile threads' core (`compile_threads_core.diff`)

`sasrt_compile_threads_core` (the user, 2026-11-22: "restrict it to core 2"; 2 by default): the uam thread and its
spare-chunk thread, the pipeline prebuild workers, the list writer and the cache saver on that core; -1 floats them
(every core of the process, the system core too: RexSwitchSetCurrentThreadCoresWithSystem(-1, process mask), no
preferred core; plume gets `Deko3DOptions::placeCompileThread` for its two threads); -2 the old banjo_* keys. Port 254
moved only the uam thread; with banjo_system_core_compiles on, the prebuild workers were still on core 3 behind port
251's stage (where RR6 saw a compile take 250-354 s). The ring cleaner is not a compile and keeps
banjo_system_core_compiles. Ryujinx: "pinned to core 2 (sasrt_compile_threads_core)" for each.

## 4. Smaller game files: LZ4 / ZXC, H.265 movies, Opus audio (`docs/media-compression-1121.md`)

The base has only version 1 (LZ4) `.lz4b` (port 61). What the ports now share, all in sasrt-nx's SDK (and the other
ports' SDKs, as noted): the base could carry one copy for every port (the user has asked this of SASRT, Banjo, Blur,
NiGHTS and Viva Pinata).
- `.lz4b` version 2 (ZXC blocks): rr6-nx's `sdk/src/filesystem/lz4_blocks.cpp`, `include/rex/filesystem/lz4_blocks.h`,
  `sdk/thirdparty/zxc`, the `rexblockcodecs` block in `sdk/src/filesystem/CMakeLists.txt`.
- The lookup: rr6-nx's `sdk/src/filesystem/devices/host_path_*` (NAME.lz4b / .hevc / .opcm / .xmo answer for NAME,
  AnswerRank, the VFS index version 2); sasrt-nx's copy has .xmop / .xmop.lz4b / .xmo instead of .opcm.
- XMA as Opus: culdcept-nx's `.xmo` (one XMA file) and sasrt-nx's **`.xmop`** (a package of many sounds, Wwise here):
  `sdk/include/rex/filesystem/xmo.h` (the format spec), `sdk/src/filesystem/xmo.cpp`, `sdk/src/audio/xmo_opus.*`,
  `sdk/src/audio/xma_context.cpp` / `include/rex/audio/xma/context.h` (culdcept-nx's DecodeXmoFrame with SASRT's
  additions: the Opus rate per sound, 48 / 24 kHz decoded at their rate, 44.1 kHz from 48 kHz Opus through a 16-tap
  polyphase 160/147 resampler, which also serves 22.05 kHz from 24 kHz Opus), libopus. Fix found here and taken by
  culdcept-nx 1.0.1: only packets a frame starts in carry the tag.
- H.265 movies: rr6-nx's `sfd_hevc` (RXSFDH01), culdcept-nx's `tools/switch/nxvideo` (FFmpeg 7.1 + nvtegra in one
  object, only nxv_* global; the CMake block `SASRT_NXVIDEO` / `RR6_NXVIDEO`); the per-player hooks are each game's
  (SASRT's CRI USM, Culdcept's / Banjo's XMedia WMV9).
- rr6-nx's `.opcm` (raw PCM as Opus) and sa2-nx's `.adxo` (CRI ADX) are the other two audio forms.

## 5. Two portability notes from SASRT's sync (ports 196 and 208)

- `app/src/renut_engine/display_sync.cpp` (port 196) includes `renut_engine/Fps.h` and `renut_engine/hooks.h` for the
  "Shown" FPS counter: a port without the base's Fps.h overlay does not compile it. A weak `RenutCountShownFrame()` (or
  a define) would let such ports build it unchanged.
- `app/src/renut_engine/perf/frame_stats.cpp` (port 208) calls `banjo::renderdoc::GameFrame()`, defined in
  me/banjo_renderdoc.cpp: a port with its own RenderDoc file fails to link. A weak definition would do.
SASRT left both calls out (its own FPS line and src/sasrt_renderdoc.cpp).

## Not universal (for reference)

SASRT's USM slice loop for H.265 (sasrt_usm_ffmpeg.cpp), its Wwise package reader, its split-screen place items, its
gpu_round sampler cuts (their g_texture_bind_gen bump: SASRT's BindingEpoch holds g_sasrt_sampler_generation), and the
depth restore default (on in SASRT, off in the base by port 202).

Questions: the "sonic racing" session (sasrt-nx).
