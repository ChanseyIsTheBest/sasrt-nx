# The native deko3d renderer: Renut's Direct3D-level renderer for this game (2026-10-19/20)

**Status:** in progress. See "Status" below, which is kept current.

The user's goal of 2026-10-19: a native renderer with **no ring emulation and no EDRAM emulation**, on deko3d on the
Switch, based on banjo-nx's work and its optimised shader generator, tested in the patched Ryujinx banjo-nx uses.

Credit: the renderer is Renut's (github.com/masterspike52/reNut, by masterspike52), as banjo-nx carries it (plume with
banjo-nx's deko3d back end, Renut's XenosRecomp with banjo-nx's changes), as sa2-nx retargeted it to a 2012 XDK.

## What changes against this port's own renderer

| | This port's renderer (`sasrt_renderer = "native"`, the default) | Renut's (`sasrt_renderer = "renut"`) |
|---|---|---|
| Direct3D | the game's own, recompiled; it writes PM4 into its command buffers | the game's own for state, resources and Present; Renut's hooks own creation, the ring and fences, the draws, Clear / Resolve's host side, Swap, shader and declaration objects, recorded command buffers and tiling |
| PM4 ring | a host thread parses the packets like the GPU's command processor | none: the ring the game's Direct3D writes is a sink nothing reads |
| EDRAM | emulated (tiles, ownership, transfers, resolves out of EDRAM) | none: render targets are images per Direct3D surface; clears and resolves act on surfaces |
| Shaders | XenosRecomp (this port's) -> SPIR-V -> NVK | Renut's XenosRecomp -> SPIR-V (PC: Vulkan or D3D12 through plume) / -> SPIR-V -> SPIRV-Cross GLSL -> banjo-nx's GLSL optimiser -> uam at run time (Switch: deko3d) |
| Back end | Vulkan (NVK on the Switch) | plume: Vulkan / D3D12 on the PC, deko3d on the Switch (`renut_gpu_backend`) |

## How it got here

1. **Which Direct3D.** This game's Direct3D is XDK 2.0.21119; sa2-nx's is 2.0.21076. Of the 640 functions of SA2's
   Direct3D range, 634 have a function here of exactly the same instruction shape (opcodes and registers; immediates
   and branch targets aside); the device layout is the same (index buffer +12812, render targets +12816, PS / VS
   +13068 / +13072, declaration +12240, strides +12904, fences +11024 / +11036, flags +11068-72, command buffer
   +13920, the Begin*Vertices ring end +13844). So sa2-nx's retargeting of Renut (its `d3d.h` layout, its hooks)
   applies here with only the addresses changed.
2. **The translation** (`tools/renut_from_sa2.py`): sa2-nx's `app/src/renut_engine` is copied and every SA2 address
   rewritten: functions through `app/config/renut_sa2_map.tsv` (the exact-shape pairs, plus XMemFree matched by
   hand), guest globals through `app/config/renut_sa2_globals.tsv` (in two functions of identical shape, the k-th
   lis-built absolute address of one is the k-th of the other: 605 globals). N&B constants sa2-nx left in paths it
   does not take get this game's values (`tools/renut_patches/sasrt_edits.py`, found through the same pairs: the state
   tables 0x831702C0 / 0x83170780, the format table 0x822F7088, D3DCAPS9 0x822F7E18, the full viewport 0x822F6C50,
   the HiZ owner 0x831FE570, VdGlobalDevice's slot 0x83370CA8). The tool reports any address it cannot map; 0 now.
3. **This game beyond SA2** (`app/src/renut_engine/sasrt_renut_hooks.cpp`):
   - recorded command buffers (a second drawing thread records, the title device runs them, thousands of times a
     race): the recording starts after the game's own BeginCommandBuffer (Renut's draw, clear and resolve hooks ask
     `IsRecordingCommandBuffer`, which reads +13920), a run is queued or recorded before the game's own Run;
   - predicated tiling: Renut backs the bound tile-sized surfaces with targets covering every tile between
     BeginTiling and EndTiling; the tiling clear and per-tile resolves of the game's own functions reach Renut's
     hooked ClearF and resolve entry;
   - shader objects the game never registers (static ones in the image's data) are registered at their first draw
     (`sasrt_edits.py`, FindShaderLocked);
   - composed command buffers: the game never calls RunCommandBuffer. Its title device splices the worker's recorded
     buffers into a composed buffer (`sub_82CEF770`, noted under the physical address of the composed buffer's write
     pointer) and submits that through the ring submit (`sub_82CDE200`, hooked with no original: there is no ring);
     the recorded buffers are replayed there, in order. The worker records on a device of its own, with its own
     3-target G-buffer surface headers;
   - surface headers as they were: the game points one surface header at many EDRAM layouts in a frame (and the
     worker shares them), so each recorded op and queued draw, clear and resolve keeps the headers it bound
     (`command_buffers.cpp` / `queued.cpp`, `SetReplaySurfaceOverridesLocked`), and the targets come from the
     destination packet's view of them;
   - the window offset and scissor: this Direct3D writes registers 0x2080-0x2082 straight into the command buffer
     (`D3D_SetSurfaceClip`, `sub_82CCB540`) with no device shadow, which Renut's draws read: the hook shadows the packet
     (without it the scene's composite was cut to an earlier 1152x544 pass);
   - `D3DDevice_BeginIndexedVertices` (`sub_82CD11C0`), which SA2 never calls: every post-processing pass and the
     scene's composite onto the 1280x720 output draw through it. Hooked as Renut hooks BeginVertices (the renderer's
     memory handed out, one deferred copy of vertices then indices; the inline End restores the ring pointer it was);
   - reverse depth: the game's viewport runs MinZ 1 to MaxZ 0. deko3d and Vulkan take a backwards host depth range;
     D3D12 does not (every depth-tested draw was lost on the PC). There the host viewport spans 0-1 and the vertex
     shaders write `z * zscale + w * zoffset`, the guest's depth itself (`g_DepthRemap`, shared constant 1352);
   - `D3DVertexShader_Bind` (`sub_82CE3340`; `sasrt_renut_hooks.cpp`), which SA2 never needed: this game binds its
     scene shaders to their declarations (the bind writes the formats, offsets and strides into the shader's fetch
     instructions) and then draws with no declaration set. The dumped containers predate the bind (fetches with format
     0), so Renut built no input layout for them: every vertex of the track, the karts and the scenery read the zero
     stream and collapsed to one point (found with a RenderDoc capture of the PC's D3D12: every post-VS vertex the
     same; the race showed only the sky and the sea). The game's Bind runs, then the shader record takes the
     declaration and strides on the render thread in order with the draws (as Renut's N&B hook does);
   - the EDRAM depth restore (`sasrt_renut_depth_restore`): the game restores its scene depth for its light and HDR
     passes by drawing the resolved depth words as colour into the EDRAM where that pass's depth buffer sits; Renut's
     per-surface targets take the colour target's words as depth (`shaders/host/depth_restore_ps.hlsl`);
   - the texture exponent adjust (`sasrt_renut_texture_exp_adjust`): a texture fetch constant's dword 3 bits 13-18
     scale the fetch's result by 2^adjust. The game's FXAA (the Xbox 360 FXAA, ps `6C215354C35798B8`) reads its input
     through two more headers with -1 and -2; ignored, its blends were 2 and 4 times too bright (a white outline on
     every edge, sparkles on the track). Such a fetch reads a copy of the texture times 2^adjust, made once per frame
     and texture epoch (`shaders/host/exp_scale_ps.hlsl`, two 1152x544 copies a frame), so no other shader pays. One
     copy per adjust and size, made again when the source changes: a copy per source slot grew to 32 on deko3d (the
     FXAA input's slot changes from frame to frame) and helped run Ryujinx out of memory;
   - stacked textures on deko3d (`app/thirdparty/plume/plume_deko3d.cpp`): Renut views a stacked texture (a 2D array
     the shaders fetch as 3D, through a `sampler2DArray`) with a plain 2D view desc. plume's Vulkan back end makes that
     a 2D array view when the image has more than one layer; its deko3d back end made a single-layer 2D view, so every
     fetch read layer 0. deko3d now keeps the array as Vulkan does (what the next item needs);
   - volume textures on deko3d (`sasrt_renut_deko3d_volume_as_array`): the game's colour grading LUT is a 16x16x16
     volume texture, and as a deko3d 3D image it read wrong: the frame after the tonemap pass came out in bands of false
     colour, on deko3d alone. A single-level volume texture is held as a 2D array of its slices there (read with the 3D
     untiling, copied slice by slice) and sampled through the shaders' stacked path, which filters between the two
     layers around the coordinate as the volume filter says; the PC renders the same picture through that path;
   - the deko3d memory budget (`sasrt_renut_deko3d_budget_mb`, 1024): Renut reported no budget on deko3d, and
     banjo_renut_memory_policy releases cold textures only against one, so the image heap only grew (512 MB of images,
     955 MB of deko3d memory, then an abort at the next 64 MB chunk in a Ryujinx race);
   - the 16-bit fixed-point render targets (`sasrt_renut_fixed16_float`): Xenos' k_16_16 / k_16_16_16_16 targets span
     -32..32. The game draws its HDR scene into k_16_16_16_16; Renut's SNORM clipped it at 1, so the bright pass and
     the average luminance saw no highlights and the auto exposure washed the frame out (white track, pale car). FP16
     now, as this port's native renderer stores them (`me_formats_color.h`). Their resolves clamp to [-32, 32] as the
     console stores them (`sasrt_renut_fixed16_clamp`, `shaders/host/resolve_clamp_ps.hlsl`);
   - their blending (`sasrt_renut_fixed16_scale`, **off**): the emulated GPU's default path (host render targets)
     holds these targets as -1..1 with the shaders' outputs divided by 32, so a blend with the source alpha uses
     alpha/32 there. With the key Renut does the same (shader_common.h `g_RtScale`, clears / 32, resolves * 32). Off
     because the emulated GPU's exact path (`render_target_path_d3d12 = rov`, which blends at -32..32 with the source
     clamped as Xenos does) agrees with Renut without it: recordings of all three on 2026-10-20 (out/pc/captures
     video_152s and video_330s ROV, video_95s / video_133s the default path) show the World Tour islands' waterfalls
     and the menus' sea in ROV and in Renut, and not in the default path;
   - texture signs (`sasrt_renut_texture_signs`): Renut chose a signed or unsigned host format when all four
     components agreed and otherwise read every component as unsigned; gamma components (TextureSign 3, Xenos'
     piecewise-linear gamma) and unsigned biased ones (2x - 1) were read raw. The game's albedo textures (DXT1 with
     gamma X-Z) read too bright and pale: Sonic and his car near white, the track washed out, against the emulated
     GPU's deep blue and beige. The translator now wraps every texture fetch in `renutSigns`, which applies them per
     result component after filtering (as the emulated GPU does) from bits 13-19 of the texture word (the slot is below
     bit 13) on the PC, of the sampler word on deko3d: there the texture word's low 20 bits are the handle's image id
     (`dkh`, `(t & 0xFFFFF) | (s & 0xFFF00000)`, the form Ryujinx follows back to the constant buffer, and plume's
     bound textures read them so too), and a first build with the flags there bound every gamma texture to a wrong
     image: all-black frames in Ryujinx (run deko31). The shaders' slot mask stays 0x03FFFFFF on deko3d
     (`BANJO_DEKO3D`): it folds into dkh's 0xFFFFF, while the PC's 0x1FFF made `(t & 0x1FFF)`, a form Ryujinx's
     translator does not follow back to the constant buffer, and every texture read nothing (run deko34);
   - 3D, cube and stacked fetches' exponent adjust (`sasrt_renut_texture_exp_adjust`): the adjust above was applied to
     2D fetches only; the emulated GPU applies it to every fetch. Those fetches carry it as a power of two in their
     descriptor index (bits 20-25) and the shaders multiply (`renutExpScale`). The one such fetch is the race's
     lighting volume (32x8x32 k_16_16_16_16, exponent -10), which also asks for the integer number format (dword 3
     bit 0: read as integers, 0..65535). The emulated GPU ignores that (its texture cache's comment: multipliers to
     be added "if any game is seen using num_format 1 for fixed-point formats"), and so does Renut by default
     (`sasrt_renut_texture_int_format`, off): on, the volume reads up to 64 and tints the track grey-blue against the
     emulated GPU's warm beige (A/B: out/pc/captures video_140s on, video_142s off, video_330s the ROV reference).
4. **Hooks that both renderers have** (this port's PM4-renderer hooks, its native Direct3D layer, the census, the
   trace) start with `SASRT_RENUT_YIELD_SHARED` (Renut's side) or `SASRT_RENUT_YIELD` (the original) when Renut's
   renderer is chosen (`app/src/renut_engine/sasrt_renut_yield.h`; the tool rewrites them).
5. **Post-codegen:** a hook set change needs `python tools/post_codegen.py` (tools/direct_calls.py makes calls to
   functions it does not see hooked direct, and inline_leaves.py copies tiny ones into their callers: a new hook would
   be bypassed). A hook on a large function needs only `python tools/direct_calls.py --redo`.

The other route, kept: `tools/renut_gpu_retarget.py` retargets banjo-nx's full Renut tree (every Direct3D entry point
native, N&B's device layout) with `app/config/renut_gpu_funcs.toml`, this game's addresses of 342 of Renut's 359 names
(exact shapes against sa2-nx, call-graph propagation from confirmed pairs, the state tables by index). Not used:
Renut's native device work keeps N&B's private layout, and every Direct3D function the game calls would have to be
Renut's.

## Shaders (banjo-nx's generator)

- The game's shader containers: this port's dumps (`out/shaders/in`, 2,033; `sasrt_dump_shaders` and its memory
  scan), copied to `out/renut_shader_dump` (game data, the build tree only).
- Renut's XenosRecomp (`app/thirdparty/reblue-XenosRecomp`, banjo-nx's copy) translates them for the PC cache
  (`out/pc/renut_gpu/shader_cache.cpp`, DXIL and SPIR-V). This game needed one translator fix: a vertex fetch whose
  destination takes no fetched component (only 0 / 1 / masked) wrote `r1. = iPosition0.;` (76 vertex shaders);
  only its constant components are written now. 2 containers still fail (one crash, one DXC error):
  `out/renut_shader_dump_crash`, not in the caches.
- banjo-nx's early alpha pass is off (`BANJO_RENUT_EARLY_ALPHA`): its first, dump-only run fails fast on this game's
  set while the plain run translates every shader.
- deko3d: the same translator with `BANJO_DEKO3D_SPIRV_DIR` writes each shader's deko3d SPIR-V (run per shader: the
  run over the whole directory fails fast part way through), `tools/deko3d_shaders.py --no-uam` (SPIRV-Cross ->
  uam GLSL), `tools/deko3d_glsl_opt.py --check` (banjo-nx's optimiser), `tools/deko3d_shader_package.py`
  (`app/out/renut_switch/deko3d_glsl.bin`, embedded). The Switch's SPIR-V cache: `tools/renut_switch_shader_cache.py
  --pc out/pc`. The console compiles variants with uam at run time (plume's deko3d back end).

## banjo-nx's optimisations (2026-10-20)

The renderer carries banjo-nx's render-thread proposals (all 17) and CPU proposals (all 9) through sa2-nx's tree, and
its deko3d shader optimisations of 2026-10-19/20 directly: `tools/renut_from_sa2.py` takes `banjo_renut_tuning.*`,
`render/pipeline.cpp`, `render/textures.cpp` and `render/draw.h` from banjo-nx's tree (`FROM_BANJO`), plume's deko3d
back end and uam (with banjo-nx's flag 1024, the 128-bit bone rows) are banjo-nx's, and `tools/deko3d_glsl_opt.py` is
banjo-nx's newest (passes up to `deadcomp`, `guardsel`, `txq` 908, `earlyz` 909; `gpr32` 910 and `lightbranch` 911 are
banjo-nx's A/B keys, off, with empty shader lists here). `banjo_deko3d_alpha_spec` stays off, as sa2-nx found SA2's
textures sampled at their smallest mip with it in Ryujinx. The DKSH cache (`deko3d_shaders.bin`, next to the NRO) is
compiled on the PC by banjo-nx's uam from the pipeline lists runs write (`tools/deko3d_variant_cache.py`), so the console
compiles only what the lists missed. The translator reads pinned snapshots of sa2-nx's and banjo-nx's trees
(`out/renut_sources`, `--refresh` when both build): both trees change while their sessions work.

## Banjo sync 2026-10-29

The user's request: the renderer brought up to banjo-nx's (its CPU, GPU, shader and memory work of 10-21 to 10-29,
`docs/porting-guide-renderer.md` in banjo-nx). sa2-nx's tree had little of it, so the source is now banjo-nx itself:

- **The source tree** (`out/renut_sources/sa2_banjo`, what `tools/renut_from_sa2.py` reads by default): banjo-nx
  894d3256 (`out/renut_sources/banjo`) merged three-way with sa2-nx's tree of 10-20 (`sa2`) over their common
  ancestor banjo-nx 25940a65 (`banjo_25940a65`; sa2-nx's tree is that commit's to within renames). The merge kept
  sa2-nx's side for what is SA2's (and this game's): the CDevice-private layout (`d3d.h`, `d3d_native.h`), the hooks
  at SA2's addresses, its guest shader and declaration objects, gamma ramp, MSAA, screen and pacing; banjo-nx's for the
  renderer. `render/draw.cpp` and `guest/command_buffers.cpp` are banjo-nx's whole, with sa2-nx's guest declaration
  fallback in both of the draw paths' lookups. The integration changes, made in that tree: banjo-nx's title update 3
  layout literals as SA2's (`FieldOfOffset`'s private boundaries, the tag chunks, the snapshot's last chunk of 32 bytes,
  not 48); N&B's base constants where this port's edits replace them; sa2-nx's guest record paths tell the fast path
  when a record goes (`InvalidateFastDrawForRecordLocked`); banjo-nx's Switch CPU profiler call answered by the SDK
  (`sasrt_compat/profiler/switch_cpu_profiler.h`, `RexSwitchPerfTotalThreadTicks` in `sdk/src/ui/switch_perf.cpp`).
  plume's deko3d back end is merged the same way (this port's depth resolve with banjo-nx's GPU region, per-stage
  binds and async variants); `app/thirdparty/smaa` is banjo-nx's (MIT).
- **This port's edits** (`tools/renut_patches/sasrt_edits.py`, then `sasrt_edits_banjo_sync.py`): 21 re-anchored on
  banjo-nx's text (the same changes), 19 dropped because banjo-nx's own work does the same now (its stream cache
  pressure and no hash at the cap for `sasrt_renut_stream_cache_follow`, its packed vertex tables for the 8_8_8_8 one,
  its measured chain-reuse defaults) or because they were octopus-hunt diagnostics whose code was rewritten, and new
  ones for banjo-nx's **fast path** (`FastDrawLocked`, which most draws take on deko3d and which does
  `DrawStateLocked`'s steps itself): the baked fetches' declaration and stream salt (also in both paths' whole-buffer
  copies and stream keys), `g_DepthRemap` and `g_RtScale` through `SetShared` (the persistent block pushes only marked
  lines), the depth targets' write sequence and the EDRAM depth restore check (only when another writer moved the
  write sequence), and the exponent adjust's per-bind copy kept out of banjo-nx's texture memo (`BindingWords`, where
  the slot words are made now, with the signs and the integer format scale). `SharedConstants` keeps this port's
  layout (`g_DepthRemap` at 1352, `g_RtScale` at 1360); banjo-nx's two words there (skin mode, internal heights) moved to
  1376, the block padded to 1424 bytes (22 lines and the 16-byte tail its line compare reads).
- **Not taken**: banjo-nx's setter marks (they need native setters at this game's addresses; the recorder compares
  every chunk instead, `TakeTouches` false), the four-core mode (no system core: `me_platform_compat.h`), title update
  3 and N&B's game code. Banjo-nx's measured defaults hold (slower on the console: replay look-ahead, shadow sort, texture
  slot skip, host packets off); its enhancements that change the picture are off by default here too (SMAA, internal
  and dynamic resolution, portrait MSAA).
- **Tools**: `deko3d_shader_package.py`, `deko3d_variant_cache.py` (`--generic` for the async variants'
  generic variants), `renut_switch_shader_cache.py` and `deko3d_glsl_compress.py` are banjo-nx's; `deko3d_glsl_opt.py`
  merged (its internal resolution codes only).
- **Found in the first runs** (both fixed, edits in `sasrt_edits_banjo_sync.py` and at the end of `sasrt_edits.py`):
  this port's `GatherTargets` reads the destination packet (each slot's EDRAM view) and, in a replay, the surfaces'
  headers as recorded: banjo-nx's chain reuse and fast path kept targets across a change of either
  (`banjo_renut_chain_reuse_verify`: "the reused targets differ" at the menus' re-pointed 831C385C). The overrides now
  move the surface epoch when they change, and the destination packet counts among the targets' inputs. And this game
  binds every texture by fetch constant alone (no header pointer in the device's slots), so banjo-nx's texture memo and
  record-time texture objects never applied: `sasrt_renut_texture_memo_fetch_only` (docs/enhancements.md). The texture
  objects themselves (keyed by the header) still never apply here: open.
- **Verified** (2026-10-29): Ryujinx (deko3d) into the race with `banjo_renut_fast_draw_verify`, `_resource_objects_`,
  `_record_extents_`, `_whole_buffers_`, `_persistent_shared_`, `_fetch_cache_` and `_chain_reuse_verify`: 0 differences;
  the fast path takes 92-97 % of the draws. The memo's verify: 786,432 answers bound again in Ryujinx and 8.4 million on
  the PC, 0 differ; in the race 89 % of the texture slots are answered without a bind (0 % before). PC (Vulkan, the full
  path) race recordings `out/pc/captures/video_175s` and `video_177s`, Ryujinx `captures/video_470s`: the right picture.

## The far-cascade shadow flicker (2026-10-29, open)

The user's console race (newlogs5, 30 fps at the highest clocks): the large shadows of distant casters (the loop over
the podium, the bridges over the ramp) are drawn in one frame and gone in the next. The clips' dark-pixel share of the
road alternates frame by frame (`out/scratch_to_delete/u1029b/shadowalt.py`: 0.30 in clip 17394300, frames 200-207 of
the podium spin plainly so); PC recordings (Vulkan, the full path) and Ryujinx recordings (deko3d) score 0 or below.
No frame is presented out of order (`order.py`).

The race's shadows: three cascades rendered into one 1024x1024 D24FS8 target (831C391C, 32-bit float on deko3d) and
copied into a 1024x3072 R32F atlas; then the light volumes (pass 12, 1152x544): for each of six rings (cascade 1,
the 1-2 blend, cascade 2, the 2-3 blend, cascade 3, the fade) a sphere marks the stencil where the scene is inside it
(GEQUAL, Replace on depth fail), the sphere before clears its part, and a shading draw where the stencil is 1 reads
the atlas, a 32x32 noise texture and the scene's depth as a texture (pixel shader constants c7-c24: the cascade
matrices and parameters, `SharedConstants` rows 0, 24, 34, 83, 85).

Ruled out, with two diagnostics (docs/enhancements.md: `sasrt_renut_diag_constants_verify`,
`sasrt_renut_diag_light_volumes`):
- the float constant uploads and pushes: every register a draw reads is the device's, 8.4 million stages on the PC
  (ring uploads), 6.3 million in Ryujinx (deko3d pushes), none stale;
- the game's own inputs: the spheres' transforms and the cascade matrices change smoothly every frame and come from
  the draws' own recorded state (none from the running device); c23's x and y vary per frame by the game's design;
- the atlas (rendered every frame, the frames' differences are the cascades' own small moves), the scene depth the
  shading reads (each frame's own), the samplers and `SharedConstants` (the same objects and values in both frames);
- the depth hand-over (never applies in this game), 24-bit depth (the cascades are D24FS8), the casters' clipping
  (none turns PA_CL_CLIP_CNTL.CLIP_DISABLE on; Renut leaves depth clip on for every pipeline), the game thread's lead
  (`sasrt_renut_frames_ahead` 0 on the PC alternates no more).

What is left is what only the console's GPU does: Ryujinx emulates neither hierarchical depth culling (Zcull,
`banjo_deko3d_zcull`, on) nor depth compression (`banjo_deko3d_depth_compression`, on; decompressed before a read by
`sasrt_deko3d_depth_resolve`). The marks the shading depends on are written by fragments that fail the depth test
(Replace on depth fail), the ones Zcull exists to drop. Console tests: `sasrt_banjo_zcull_off.toml`,
`sasrt_renut_depth_uncompressed.toml`, `sasrt_renut_depth_plain.toml` (both and the hand-over off).

The user's console runs of 2026-10-30 (newlogs6): depth compression off kept the flicker, so it is not that. Both
configs with Zcull off stopped during the boot, about 20 s in, with nothing in the log. In plume's
`invalidateZcullAfterCopy` the `if` had no braces, so the Zcull invalidate was recorded after every copy and upload,
with Zcull on or off. A Zcull invalidate on a queue created without Zcull is the most likely cause of the stop. Fixed
(braces; the same bug is in banjo-nx's and sa2-nx's plume). Zcull itself is still untested.

The same day's plume audit (prompted by a Final Fantasy XIII port on these plume files, where a grid showed around
ice) found three places where plume's deko3d back end kept deko3d's defaults and the other back ends behave
differently. All three are fixed, each with its own key (docs/enhancements.md):
- **Sample positions** (`sasrt_deko3d_msaa_positions`): `dkMultisampleStateDefaults` puts every sample at the pixel's
  centre, and `dkCmdBufBindMultisampleState` always writes them (method 0x11E0). So 2x and 4x targets had no edge
  antialiasing on the console. Ryujinx ignores the positions.
- **Alpha-to-coverage dither** (`sasrt_deko3d_a2c_dither`, now off): on by default in deko3d, which gives a fixed grid.
- **Primitive restart for indexed strips** (`sasrt_deko3d_strip_restart`): the Vulkan back end turns it on, but deko3d
  never does.

In a Ryujinx race (run fix1030_race), this game has one multisampled pipeline and no alpha to coverage, but about
115 indexed strips a frame. Of the three, only the strip fix changes what this game draws.

Still to test on the console: Zcull off again, then the rest of what the console's GPU does and Ryujinx does not
emulate. `sasrt_flicker_all_safe.toml` covers all of it at once: Zcull and compression off, each frame waiting for
the GPU, full barriers, and the upload ring uncached. Then one at a time: `sasrt_renut_sync_frames.toml`,
`sasrt_renut_barriers_full.toml`, `sasrt_banjo_upload_uncached.toml`.

The user's console run of 2026-10-30 evening (`sasrt_renut_shadow_dump.toml`, the mask, the lit scene and the scene
depth of 8 consecutive frames every 30 s; `newlogs+goodshadowdump`): the console's GPU computes the shadow mask
(`B5640E28`) wrongly in some frames, while the scene depth beside it changes smoothly. The PC's masks of a race change
smoothly from frame to frame.
- Window 6 (frames 5879-5886, under the rock overhang by the water): 5880, 5882 and 5884 are bad. The water under the
  rock shows regular diagonal stripes (shadow acne: the surface shadowing itself) and coarse stair-steps, and the sunny
  road on the right is black. 5879, 5881 and 5883 are right (the near water shadowed by the rock, the far road lit
  with the palms' shadows).
- Window 5 (frames 4980-4986, under the bridge): in 4981 and 4985 the bridge's shadow on the far road is gone.

Acne means the cascade read for those pixels holds the surface's own depth where the rock should be: in a bad frame
an occluder is missing from a cascade, or the lookup reads another cascade than the one it should. The first console
dump (frames 5208-5209, every resolve) found the cascades whole, but it copied each cascade out right after its
resolve, which also orders the GPU's work there. Next: `sasrt_renut_shadow_dump_atlas.toml`, the atlas and the mask of
the same frames (no bad frame at all would point at that ordering).

That run (newlogs7, 7 windows): no bad frame. Window by window, frames two apart differed more than neighbours did
(normal motion), where the mask-only run's window 6 had scored every frame as an outlier. The cascades were whole and
smooth. The one outlier frame differed only in the jitter grain the game changes every frame on purpose. Dumping
the atlas ended the flicker. Its readback copies put `DkBarrier_Full` and a texture-cache drop after each cascade's
depth resolve. The fix does that by itself: `sasrt_renut_depth_resolve_wait` (docs/enhancements.md), with
`sasrt_deko3d_read_wait`, `_write_wait` and `_clear_wait` as console A/Bs for the hazard behind it.

The user's console run with that fix (newlogs8, 15 windows on A+B+X+Y): still there. In window 2, frame 3034 has
no shadows from the wall and the tree across the road, and 3035 has them; window 0 is the same with a palm's shadow.
The atlas dump's run may only have missed the places where it shows. Next (docs/enhancements.md): the atlas copied
after the mask (`sasrt_renut_diag_shadow_dump_late`), the dump's own copy after each cascade
(`sasrt_renut_depth_resolve_wait` 3 and 4), and both compressions off at once.

## Debugging with RenderDoc (2026-10-20)

- **PC (D3D12 or Vulkan), one frame at a chosen time:** `tools\win\boot_test.ps1 -RenderDoc -Set
  "sasrt_renderer=renut;sasrt_renderdoc_capture_s=185" -InputScript tools\win\input\race.txt -Seconds 225` runs the
  game under banjo-nx's portable RenderDoc 1.46 (`D:\Banjo kazooie port\tools\RenderDoc_1.46_64`); the capture lands in
  `out\rdc`. The window stays minimised (no presents), so `app/src/sasrt_renderdoc.cpp` brackets one frame with
  `StartFrameCapture` / `EndFrameCapture` queued on Renut's render thread after one Swap and the next.
- **Analysis:** banjo-nx's scripts, copied to `tools/rdc_*.py`, run inside qrenderdoc: `qrenderdoc.exe --python
  tools\rdc_passes.py` with `RDC_IN` (the capture) and `RDC_OUT` (a folder) in the environment. `rdc_passes.py` saves
  every pass's target; `rdc_draws.py` (`RDC_EVENTS=first-last`) lists draws, targets and textures; `rdc_draw_detail.py`
  names the pipelines `vs_<hash> ps_<hash>`; `rdc_event.py` gives the post-VS vertices; `rdc_pixel.py` the pixel
  history; `rdc_mips.py` every level's range; `rdc_save.py` a texture after an event. `tools/rdc_vsdata.py` (this port)
  dumps a draw's constant blocks and buffers.
- **Ryujinx:** `tools\win\ryujinx_run.ps1 -RenderDoc` starts it under RenderDoc and `tools/rdc_trigger.py` takes
  captures by target control, but a minimised Ryujinx presents nothing, so no capture completes; the test runs stay
  minimised. With the user's permission for one run, `-RenderDoc -Visible -Set audio_mute=true` (a normal window,
  muted) captures: RenderDoc comes in only as the Vulkan layer, through `VK_ADD_LAYER_PATH`, `VK_INSTANCE_LAYERS` and
  `ENABLE_VULKAN_RENDERDOC_CAPTURE` for that process (renderdoccmd's own launch crashed the visible window's
  compositor), and `out/tmp/rdc_trig.sh` runs the trigger (copies land in out\rdc\trig). The resources of a Ryujinx
  capture carry no names of ours: `tools/rdc_rw_timeline.py` lists every draw and dispatch that writes a buffer and
  the draws that read those bytes as vertices; `tools/rdc_shader_at.py` disassembles the shaders at chosen events
  (Ryujinx's SPIR-V shows what became of a guest shader's memory accesses) and prints buffer ranges there.
  `tools\win\boot_test.ps1 -RenderDoc` sets the same three variables now, for the PC's Vulkan captures. On deko3d, `banjo_renut_diag_show_texture = "g<N>,<M>,..."` shows render targets by generation (the
  `[surface] gen` lines name them; 5 s each) in place of the frame, on screen and in `sasrt_video_s` recordings.

## Status

As of 2026-10-20 16:45 (`sasrt_renderer = "renut"`, `renut_gpu_backend = "deko3d"`: app/sasrt_switch.toml's default
now; on the PC, app/sasrt.toml picks `renut_gpu_backend = "vulkan"` for Renut). Building: the PC only inside
`. tools\win\env.ps1` (its vcvars select MSVC 14.42; a bare shell's clang picks VS 18's 14.51 and the precompiled
headers no longer match). Renut's shader-cache step (XenosRecomp over out/renut_shader_dump) crashed there three times
out of four on 2026-10-20 (0xC0000409, cause not found) and never from bash: run that step from bash with VS's ninja
(`.../CMake/Ninja/ninja.exe -C out/pc renut_gpu/shader_cache.cpp`). After a shader change the Switch needs
`tools/renut_switch_shader_cache.py --pc out/pc` as well as the deko3d chain (SPIR-V, GLSL, package, variant cache):
without it the NRO pairs new host code with old shaders. The Switch NRO links no Vulkan driver since 2026-10-20 (the user's request; `REXGLUE_SWITCH_LINK_NVK`, off, in
sdk/cmake/rexglue_switch.cmake and plume's CMakeLists; `app/src/sasrt_switch_no_vulkan.cpp` answers the five entry
points the code still references, plus newlib's missing `posix_memalign` Mesa used to supply): 54 MB instead of 68 MB,
and `tools/check_switch_build.py` checks that no Mesa driver is in it.

- **PC, D3D12 and Vulkan: plays.** Boot, menus, World Tour and a whole race (Ocean View) at the game's 30 fps
  (render thread about 26 ms a frame in a race, GPU about 7 ms on the PC's NVIDIA card), the picture matching this
  port's own renderer: the scene, lighting, the HDR pass, bloom, auto exposure, FXAA and the HUD. Vulkan's device-lost
  of the 19th no longer happens (a whole race recorded).
- **Switch (deko3d, banjo-nx's patched Ryujinx): plays, with the right picture.** Boot, menus, World Tour and whole
  races without a crash (memory held under the budget), every shader variant from the DKSH cache (0 uam compiles in a
  race), the race's picture as on the PC (2026-10-20 13:12, run deko28). Ryujinx runs it at 5-6 frames a second (its
  CPU emulation: render thread 150-185 ms a frame there), which says nothing of the console's speed.
  The last bug was deko3d's: the frame after the tonemap pass came out in bands of false colour. Found by elimination
  with `banjo_renut_diag_show_texture` (`"g<N>"` render targets, `"p<hash>:<slot>"` what a pass sampled): the HDR scene
  and the bloom were right on deko3d, and A/B runs ruled out the FP16 targets, the exponent-adjust copies, the depth
  restore, new targets left uncleared, banjo-nx's deko3d runtime features and the wide-row uam flag. The colour grading
  LUT (a 16x16x16 volume texture) as a deko3d 3D image read wrong; held as a 2D array of its slices
  (`sasrt_renut_deko3d_volume_as_array`) through the shaders' stacked path (checked on the PC too: the same picture),
  the frame is right. Why deko3d's 3D image reads wrong (its upload's copy engine or the image layout's tile depth;
  plume's small-image tile fix skips 3D images) is not known.
- **Colours against the emulated GPU (2026-10-20 afternoon, the user's "Sonic in the car?" and "overblown"):** Sonic
  and his car came out near white and the track washed out. Compared with the emulated GPU in both its paths (the
  default host render targets and the exact ROV path, `render_target_path_d3d12 = rov`; recordings video_95s,
  video_133s, video_152s, video_330s, video_121s): the cause was the texture signs (gamma albedo read raw), fixed
  above (`sasrt_renut_texture_signs`), plus the 3D exponent adjust. Now the race start matches (car 62,85,178 against
  ROV's 68,102,184; the track the same warm beige on Vulkan). The emulated GPU's default path differs from its own ROV
  path in this game: it hides the World Tour islands' waterfalls and thins the sea and haze (alpha / 32 blends);
  Renut follows ROV there (`sasrt_renut_fixed16_scale` off).
- **Switch (deko3d) after the colour fixes: right picture again** (Ryujinx run deko35, 2026-10-20 17:23: character
  select, loading, the flyover and the race as the emulated GPU draws them; 279 DKSH hits, 6 compiles). Runs deko30-34
  between were black or near black: the DKSH cache on Ryujinx's SD was stale (`ryujinx_run.ps1` now copies it), the
  sign flags sat in the handle's bits, and the slot mask broke Ryujinx's handle tracking (all fixed, above).
- **First run on the console (2026-10-20 19:26): crashed after 23 s**, while the game loaded its menus
  (Frontend.M00): a frame of 1.4 s without a Swap uploaded about 640 MB, every frame slot's upload ring only grows
  within a frame (32 MB chunks), the deko3d blocks reached 988 MB and the next image heap chunk was not made (the
  deko3d log's last line, "image heap: chunk 4 of 64 MiB"). Before that it ran 19-27 fps (GPU 15-16 ms a frame,
  render thread 5-10 ms). Fixed by `sasrt_renut_ring_frame_cap_mb` (96): a draw that finds its frame's ring past the
  cap ends the frame for the renderer first (detail::SubmitAndAdvance, as a minimised window's present; the other
  slot's fence is waited and its ring reused). Checked on the PC with the cap at 2 MB (the frame ended about six
  times a game frame, 30 fps, the picture right: video_113s). Not yet run on the console again.
- **Second console run (2026-10-20 20:06): boots, menus and a whole race; Sonic in his car.** The user's clips showed
  one-frame glitches: huge stretched polygons over the sky (green, red, black), the ground black and glossy with
  sparkles, teal-tinted frames; it ran 19-21 fps in the race (render thread about 50 ms a frame: its cached-stream
  checks hashed 1.1 GB a second, as this port's generated code marks no store cards; GPU about 25 ms). The PC's D3D12
  showed the same glitches (its GPU 8-11 ms a frame), its Vulkan almost never (1-4 ms). Waiting for the GPU every
  frame (`sasrt_renut_diag_sync_frames`) removed them on D3D12 (0 bad frames in 440, against 4-25); banjo-nx pointed
  out that this also stops the game running ahead of the render thread (`sasrt_renut_diag_no_frames_ahead` splits the
  two).
- **Refreshed to sa2-nx's and banjo-nx's trees of 2026-10-20 evening** (the user: take banjo-nx's CPU and GPU work;
  `tools/renut_from_sa2.py --refresh`, the snapshots of 05:44 kept in out/renut_sources_0544, the tree before in
  out/renut_engine_tree_2026-10-20_2030): about 4,700 changed lines of banjo-nx's and 15,400 of sa2-nx's (snapshot
  deltas, capture batches, wake batching, the done notify, prefetch, stream masks, eager kicks, display sync with
  banjo-nx's __nx_win_init override, late input through the SDK's new controller read hook (it never ran in this port
  before: `rex/input/read_hook.h`), the DKSH cache and pipeline list synced to the card, the run-time variant log
  that `tools/deko3d_variant_cache.py --runtime-log` reads). Off here, as banjo-nx measured: chain reuse, the inline
  line compare, sa2-nx's core layout; off until derived for this game: the narrow delta compare; off: sa2-nx's 2x
  MSAA. plume's deko3d back end and the deko3d shader tools are banjo-nx's now. With it the PC's D3D12 races show no
  such glitch (two dense recordings of the race, video_143s and video_144s: the only outliers the logo cut and a
  tunnel). Store cards stay off (this port's generated code does not mark them; `sasrt_store_cards.cpp`).
- Open, the most visible: **Sonic missing from his car on Vulkan and deko3d** (the user's "Sonic is in the car?"). On
  D3D12 he is in every race frame; on Vulkan (PC) and deko3d (Ryujinx) the cockpit shows the empty red seat for long
  stretches (out/tmp/cockpit.py over dense recordings: video_123s, video_119s, video_118s, video_117s against
  video_129s on D3D12). Older than the day's colour work: with sasrt_renut_texture_signs and
  sasrt_renut_texture_exp_adjust off, Vulkan loses him all the same (video_114s). Not the cause (A/B on Vulkan): banjo_gpu_bool_spec, banjo_renut_pipeline_memo,
  banjo_renut_linked_stages, banjo_renut_precise_barriers; Renut sets no depth bias and uses no clip distances on any
  back end; the vertex inputs are float formats. The user's hardware test says the console shows him: the deko3d
  case is Ryujinx's. **Ryujinx, 2026-10-20 23:05 (RenderDoc of Ryujinx itself, the visible run):** his body is
  GPU-skinned by memexport (the export draws write the memexport buffer fine) and reaches his draws through
  stream_convert_cs, whose output buffer stayed all zero after every dispatch of the frame, so his draws read zero
  positions. Ryujinx's translation of the shader showed one cause: it read the export buffer as
  `g_Buffers[g_Push.source]`, an element of a storage buffer array picked at run time, which uam reaches through a
  computed constant buffer offset; Ryujinx's translator cannot trace that back to a binding and guessed two unrelated
  constant buffer words (c7[0] and the push constants' c1[5]) as the buffer's address, so the loads read 0 (the
  convert's storage descriptors are c0[20..22]). Fixed for deko3d by constant indices (a `sasrt_edits.py` edit of
  stream_convert_cs.hlsl). Not enough on its own: Ryujinx run deko40 still showed the empty seat (7 of 12 frames).
  `sasrt_renut_diag_convert_check = "<vs hash>"` (deko3d diagnostic, [convertcheck]: per checked job the export
  window, the export as the GPU copied it back after the draw, the job's stream words filled with 5A5A5A5A before the
  dispatch and as the GPU copied them right after it; `"<vs hash>:probe"` makes the shader report what it computes
  instead of converting) found the second cause (runs deko43-47, 2026-10-21): the export is right on the GPU, the
  push constants, element words, vertex index, source offset and a load at it are all right, and the conversion's
  stores land (the pattern is overwritten), but with zeros: its loads sat in loops (`for (i < words) ...
  LoadSource(src + i * 4)`), whose address uam advances from one iteration to the next, which Ryujinx's translator
  cannot trace either. Those three loops are unrolled on deko3d (constant offsets from the buffer's base, as the
  probe's loads that read right). (An edit that also made the push constants' element pair a constant index came from
  a wrong guess: the probe read the run-time indexed push words right; it is harmless and stays.) Lessons for deko3d
  shaders that Ryujinx must run: never index a storage buffer array at run time, and keep storage buffer loads out of
  loops whose address advances (unroll them); Ryujinx zeroes such loads silently (its log says "Failed to find
  storage buffer" only for some, only at a shader's first translation, and its shader cache hides it later). The
  console reads the addresses themselves. [writeback] (`sasrt_renut_diag_writeback_check`) compares each export's
  write-back to guest memory with what the next export of that memory finds: mostly different, but the game reuses
  those addresses for other meshes from frame to frame (the same base comes back with other sizes), so no fault shown.
  The PC's Vulkan back end lost him too before the evening refresh (video_123s and others); not checked since.
- **The console's visual faults (the user's hardware run of 2026-10-21 00:43-00:48, the 00:30 NRO):** the race's
  sky dropping out (black), green, or in stretched triangles; frames mixing the scene with another image of it (the
  "ocean" frames, every few seconds on the console against 2-3 in 440 on the PC); dimmed frames; flashing models in
  the race-select menus. The console's render thread was busy 96-122 ms a frame (GPU 59-69 ms, 8-10 fps): Renut's
  render thread lags far behind the game there. `sasrt_renut_diag_render_delay_ms` (a test: each frame's work on the
  render thread waits this long first) makes the PC lag the same way, and at 50 ms the PC shows the console's faults
  (red and yellow stretched skies, ghosted frames, the "ocean" frames): a race between the game running ahead and the
  render thread reading what the game changes meanwhile, not deko3d. Ruled out on the PC with the delay (contact
  sheets of dense recordings; out/tmp/outliers.py undercounts faults that last several frames): banjo-nx's capture
  pool, sa2-nx's render-thread CPU group, the snapshot deltas (sa2_renut_snapshot_deltas_verify: 0 of 425,000
  rebuilt devices differ), the index buffer objects (now copied with each draw, ReplayIndexBuffer; its "[ib]" count
  found none changed), honest fences for memexport results (`sasrt_renut_diag_fence_exports`, a test).
  **The "ocean" frames found (2026-10-21 03:00):** they come in pairs two frames apart at a steady period, on every
  back end, delay or not (out/tmp/ocean.py over the recordings). `sasrt_renut_diag_trace_window = "<s>,<frames>"`
  (with banjo_renut_diag_resolve_trace) traces every frame of a window; out/tmp/trace_frames.py compares them: in the
  flashing frames the scene's main pass, which a worker device's recorded command buffer draws (302 draws, after a
  16x16 resolve of the worker's surface 4009C8EC), had one draw. **Cause and fix (04:00):** each frame's composed
  command buffer is spliced at the frame's start (sub_82CEF770) into the next 4 KB segment of a pool that walks down a
  page a frame, and submitted under that segment about a frame later (sub_82CDE200), where the hooks run its recorded
  buffers. When the pool wraps (every ~63 frames, on each of two chains), the last splice before the wrap is never
  submitted under its own segment: a padding submission of another segment (one type-3 NOP over it) comes in its
  place, and that frame's recorded buffers never ran (out of 300 submissions per 10 s, 290 found their splice). A
  padding submission that names no splice now runs the composed buffer spliced last (sasrt_renut_hooks.cpp; the
  "[sasrt] composed segment ... submitted as ... (its pool wrapped)" line): 0 "ocean" frames in 300 (10 before), every
  submission matched, and the PC with sasrt_renut_diag_render_delay_ms 50 shows none of the console's faults any more
  (no ghosted or dark frames, no broken sky). Ruled out on the way: capturing the recordings at the splice (kept:
  `CaptureCommandBufferRun` / `QueueCapturedRun`, what the 360's spliced packets point at), segments nested in other
  segments, packets written into the device's ring, padding segments patched later. Replaying at the splice instead
  (`sasrt_renut_run_at_splice`, a test, off) put the worker's pass before the title device's clears: every frame lost
  it, which proved the missing pass is the "ocean" frame. Console tests for the morning:
  `tools/make_renut_test_configs.py` writes configs/sasrt_renut_*.toml (sync frames, no frames ahead, banjo-nx's deko3d
  GPU work off, the render-thread CPU work off, kicks off, full barriers, plain depth).
  **The menus' flashing models are the same fault (04:40):** in the user's console video of the menus (World Tour ->
  Coastal Cruise -> Difficulty Select), the floating island and everything 3D vanish for single frames, leaving the
  sky (tools/flash_frames.py: frames that differ from both neighbours while those agree; scores 90+). The fix now has a key,
  `sasrt_renut_pool_wrap_run` (on): with it off the PC's menus (render delay 50 ms) lose their island and models every
  ~63 frames (frames 88, 151, 214, ... 466 of a 600-frame recording, scores 80-150); with it on, nothing above 15
  (the one 14 is a lighting change in a camera cut). configs/sasrt_renut_pool_wrap_off.toml shows the fault on the
  console for comparison.
  **Still open (06:45): the race start's smears and sky triangles, a late read.** With the render thread lagging
  (`sasrt_renut_diag_render_delay_ms` 50) the PC shows, for 2-3 s after the pre-race logo wipe and at moments later,
  Sonic's car missing or smeared into a dark blocky cloud, and big flat red / green triangles over the sky: the
  console's videos show the same sky triangles (green, teal) at the countdown. Without the lag the race start is clean
  (a rare dark smear later, frames 850 / 1180 of video_94s). What it is not: the composed-buffer pool wrap (fixed, on),
  banjo-nx's console memory policy (off: the same), the 96 MB frame cap (`sasrt_renut_ring_frame_cap_mb` 0: the same),
  the export fences (`sasrt_renut_diag_fence_exports`: the same), vertex data read at the kick instead of at the draw
  (`sasrt_renut_diag_convert_at_bind`, a test added for this: the same). What clears it:
  `sasrt_renut_diag_no_frames_ahead` (the game waits at its Swap until the render thread has done the frame): so the
  game changes, during the frame after, data a draw of the frame before reads, before the render thread replays that
  draw (not between the replay and the kick). The looks (a skinned car exploded, triangles across the sky) point at
  vertex or constant data of skinned meshes; the composed buffers, which reach the render thread only at their ring
  submission a frame after their splice, are the first suspect (a fence the game waits on can complete before their
  draws are even queued). `sasrt_renut_diag_late_streams` (diagnostics, off) hashes each draw's bound vertex streams
  (first 4 KB) on the game thread at the call, again at the replay and at the conversion, and the title device's
  streams once more at the game's kick: thousands a second change after the call with or without the lag (this game
  fills vertex buffers after the draw call, which the 360 allows: its GPU reads them after the kick, Renut at the
  kick's flush), and almost none (one per run) after the kick, with or without the lag. So the title device's vertex
  streams are read as the 360 would read them. Index data (read at the replay, since the vertex range comes from it)
  is hashed the same way. The race's 3D scene is drawn almost wholly by the workers' recorded command buffers, so
  their draws' ranges are hashed at the composed segment's ring submission too (QueueCapturedRun, where the 360's
  GPU gets them): indices, 100,000+ ranges per 10 s compared, 0 differ with the lag or without: index data is read
  right. Their streams change after the submission as often without the lag as with it (the hash covers the first
  4 KB from the fetch constant's base, which in a shared buffer holds other draws' vertices): no answer there. Left:
  textures and constants read through pointers, and a stream hash over each draw's own vertex range (from its
  indices). Meanwhile
  configs/sasrt_renut_no_frames_ahead.toml shows on the
  console whether this is all of the sky fault (at a cost: the game and the render thread no longer overlap). The
  stream cache fix below shortens the console's lag 2-3x, which should make it rarer.
  **Skinned meshes collapsing to a point, fixed (2026-10-21 09:50): `sasrt_renut_exports_held`.** The order log
  (`sasrt_renut_diag_layout_log`) caught draws reading all-zero positions from memexport results: the title device
  exports skinned positions in frame F; the workers' recorded draws that read them replay at the composed segment's
  submission, a frame later, when the game has already cleared that memory for its next export. On the 360 the GPU
  runs the composed buffer before the CPU clears. The export results are now kept on the host after their write-back
  (`CompleteMemExportsLocked`, 4 frames), and a vertex stream inside a kept export reads them, uncached.
  **The race's octopus, fixed (2026-10-21 11:30): `sasrt_renut_baked_fetches`.** The octopus at the first race
  stretch was a ball of long spikes on every back end, lag or not (the user's console videos; the emulated GPU curls
  its tentacles). RenderDoc on the PC (`tools/rdc_tri_edges.py`, the 95,022-index draw: ~3,000 triangles 20x longer
  than the median, longest edge 97). Its positions come from a memexport skinning pass (vs 3CBD81B71CF37791, 33,942
  points, the bone palette by address, 76 bones, all valid). The skinning shader was dumped as `D3DVertexShader_Bind`
  had left it: its vfetches name their formats and strides (BLENDWEIGHT k16_16_16_16_FLOAT, 2 dwords), and their
  destination swizzles already hold the bind's pair exchange for 8in16 data under the stream's 8in32 swap (`.yxwz` on
  BLENDWEIGHT and NORMAL). Renut swapped the pairs back on the CPU too (`BoundDeclType`'s 1032, `UnswapHalves`), so
  each weight met another bone's index. Tests on the way: the UBYTE4 indices reversed (~950 spikes) or pair-swapped
  (13,672: worse), every 16-bit element left unswapped (`sasrt_renut_test_keep_swapped_halves`: the octopus right,
  but the sky split blue/teal, Sonic's head black, textures smeared: those shaders are not bound). The package's
  vertex inputs split cleanly (out/pc/renut_gpu/shader_cache.cpp): 1,118 name a format and a stride (bound when
  dumped; none read through vfetchBound), 889 name neither; every 16-bit float input of a bound one reads a
  pair-exchanged swizzle (.yx, .yxw, .yxwz). The key builds, once per declaration and set of bound locations, the
  declaration as such a shader reads it (its 8in16 elements at those locations as 8in32 ones: no swap back), with the
  same host formats (the same pipelines) and its own stream cache key. PC capture at 141 s: 0 spikes, longest edge
  5.8, the rest of the scene as before. It also corrects the generic skinning shader D80AC8598297CDEE (its blend
  weights; the characters) and vs 7BAF693FF0995445 (a 19,200-vertex race mesh: its normals, tangents and texture
  coordinates were swapped). A `[sasrt] baked fetches` line names the first 24 declarations it changes.
  **The user's console videos of the 11:39 NRO (2026-10-21 11:50):** the octopus right. Left, console only (neither
  the PC, with or without `sasrt_renut_diag_render_delay_ms` 50, nor Ryujinx shows them): whole objects intact but in
  the wrong place for a few frames (a blue and red truss over the start line with a translucent light shaft, large dark
  patches on the track in the same frames, its shadow), and a dark and a teal triangle over the start grid for about two
  game frames. Ryujinx draws neither Sonic nor the octopus (its own limit: the console draws them), so it cannot judge
  skinned meshes. Not it: a late constant read (the title device's draw constants are taken at the call, a recorded
  buffer's at its record and submission), the store cards (`banjo_renut_store_cards_verify` on the PC: 0 of ~10 million
  proven copies changed under clean cards; the natives mark them, `sasrt_hot_common.h` `Card`), the codegen's
  floating-point contraction (`-ffp-contract=off` on the Switch's game code), primitive restart (see below). Console
  bisect configs: `sasrt_renut_deko3d_plain.toml` (banjo-nx's deko3d shader specialisations and uam options off),
  `sasrt_renut_store_cards_off.toml`, `sasrt_renut_capture_streams.toml`, `sasrt_renut_no_frames_ahead.toml`.
  **The respawn's dark blocky cloud is the game's own** (13:30): after a respawn the car blinks through a dark smoky
  cloud with blue cubes (RenderDoc: pixel shaders of the 2B4BE79A788DA9F0 family, the game's particle shader). The
  emulated GPU's exact path (ROV) draws it the same (video_203s frames 49, 53, 54, 60). On the way: a RenderDoc trigger
  for a few frames after the game's logo wipe (`sasrt_renderdoc_after_wipe`, with a video, whose recorder spots the
  wipe; `sasrt_renderdoc_capture_frame`), `tools/rdc_pixel_history.py`, `tools/rdc_event_state.py`,
  `tools/rdc_shader_dump.py`.
  **Brightness:** Renut (PC) and the emulated GPU match over a race stretch (165 matched frames: mean luma 129.8 /
  131.4, blown-out pixels 2.27 / 2.16 %), the console matches the PC at the start grid, and this game's display gamma
  ramp is the identity. The look is the game's; `sasrt_display_gamma` (enhancements.md) darkens the midtones for those
  who want. Ryujinx (deko3d) is up to 20 % brighter in the seconds after the dark respawn wipe, within 2 % elsewhere.
  **The user's console configs (2026-10-21 16:10, newlogs3):** `sasrt_renut_diag_no_frames_ahead` removed most of the
  explosions and ran the race at 30 fps (render thread 16-22 ms a frame against 38-44, the upload churn a seventh,
  input to screen 24 ms against 78): now the console's default, `sasrt_renut_frames_ahead` 0 (enhancements.md).
  `sasrt_renut_capture_streams` and `sasrt_renut_store_cards_off` made them worse (both cost render-thread time).
  Some explosions, the overblown look and flickering lighting remain (the HUD's colours right). Also in the logs: two
  vertex shaders the console's caches lacked (4DAB63F59919EA27, 65363C7E90CC3945: the PC's cache had them since
  09:04; their draws were dropped; the Switch caches rebuilt at 16:30 from per-shader translator runs), and once per
  run at frame 517 a texture made from guest memory over an 8-bit resolve destination read as 16-bit float (loading).
  **The user's console run of the 16:31 NRO (2026-10-21 17:16, newlogs4):** no explosions left (the two missing vertex
  shaders back, frames ahead 0), the race at 30 fps; the flickering and overblown lighting the same with
  `sasrt_renut_deko3d_plain` (run 1) and without (run 2). The clips show it: the ground black with bright specks under
  whole shadow cascades (a straight edge across road and grass where a cascade ends; the start straight, the water),
  coming and going over about a second, the driver a black ball. Cause: depth targets compressed by the GPU
  (`banjo_deko3d_depth_compression`, on in both runs) were read by the shadow maps' copies without being decompressed;
  fixed by `sasrt_deko3d_depth_resolve` (enhancements.md; plume decompresses with `dkCmdBufResolveDepthValues` before a
  read). The overblown stretches are likely the auto exposure brightening a half-black picture. Not yet confirmed on the
  console (Ryujinx emulates no compression: the 18:00 NRO runs there, about 11 decompressions a frame).
  **Correction (2026-10-21 19:31-20:50):** the user's next run had the decompression (~10 a frame) and the same black
  darks; the user then showed Ryujinx (the loop, the start) too dark as well: not the console. The cause was the GI:
  the race's lighting volumes read normalized instead of as integers (`sasrt_renut_texture_int_format`, on since,
  enhancements.md), so no ambient light reached any shadow, on every renderer and in the emulated GPU used as the
  reference. PS3 footage of the intro flyover (the gate's pillars light grey stone) confirmed it; the user judged the
  PC result accurate.
  **UnleashedRecomp-NX and MarathonRecomp-NX, read for fixes (2026-10-21, the user's request):**
  - *Vertex data at the right time:* both copy a vertex buffer when the game unlocks it (Marathon: a snapshot taken on
    the game thread at `Unlock`, uploaded by the render thread; its "fix: sync buffer unlocking" undid an earlier
    deferred copy that read data the game had changed), and the game waits at Present until the render thread has
    recorded the frame. Renut reads guest memory when the render thread gets to it, and the workers' composed buffers
    a frame later still: `sasrt_renut_capture_recorded_streams` is the Marathon way for those (a test).
  - *Translator passes:* Unleashed's dark eyes (`docs/SWITCH-DARK-EYES.md` there) were a bug in a translator
    optimisation, not the driver, found by running old and new translations on random inputs; Marathon proves its
    alpha-test sinking at build time (`sink_check.cpp`). The console here runs banjo-nx's `tools/deko3d_glsl_opt.py`
    (29 passes, the PC none) and its uam options; checked only by "uam compiles it". Passes that change SASRT shaders:
    alpha 1424, vsout 2005, pszero 1995, deadcomp 1896, sel 1591, earlyz 1419, vszero 581, dowhile 169, tess 162,
    bool01 45, txq 17, aw4 15 (bone rows; their 16-byte alignment holds in both fetch paths), scale1 / fragscale 10,
    bonerow 4, pred 3, ifmerge 1, guardsel 1; the Banjo-only ones (lightbranch, skinonce, bonesel, gpr32, nullps)
    none. A GLSL audit like Unleashed's would settle them; meanwhile the console configs above turn their runtime
    parts off (`sasrt_renut_txq_verify.toml`: magenta wherever plume's texture sizes differ from the texture's).
  - *Primitive restart:* plume's Vulkan back end enables it for strips, the deko3d one never calls
    `dkCmdBufSetPrimitiveRestart`, and Renut neither honours Xenos's reset index nor keeps 0xFFFF through its index
    rebasing. Latent here: the emulated GPU saw only indexed triangle lists without restart in 318 runs.
  - *Occlusion queries / conditional rendering:* Marathon implements Direct3D's conditional surveys (its lens flares
    showed through geometry before). This game issues occlusion query batches (`sub_82CF1518` fills their 32-byte
    results with Direct3D's "not done" sentinel); Renut never answers them, the emulated GPU answers 1000 samples (in
    host order). The title device's ring holds no EVENT_WRITE_ZPD in a race (`sasrt_renut_query_samples` -2): what
    they decide, if anything, is open.
  - *BeginShaderConstantF4:* Marathon's hook led to `sasrt_renut_constant_f4_pending` (enhancements.md).
  - Not applicable here: their Mesa / NVK driver work (this port's console renderer is deko3d), their per-game
    frame-rate patches (but note: this game at the console's 16 fps runs its logic at half its 30, which no real 360
    did).
- Open (2026-10-20; (1) FIXED 2026-10-21, the composed buffer pool wrap above): (1) a one-frame flash, Renut only (both back ends; 0 in 186 densely recorded frames of the emulated GPU, 2-3
  in 440 of Renut's): the frame shows a fixed view over the open sea, stretched, under the HUD. The race's frames
  start with a 288x256 render (viewport 256x256, its own depth) resolved to a texture, through the same colour
  surface header (831C385C) as the 1152x544 scene; the flash looks like that image as the scene, so Renut's surface
  of that header likely mixes the two sizes now and then (not proven; `banjo_renut_diag_resolve_trace` shows the
  passes). Ruled out by A/B: banjo-nx's resolve skip, lazy depth words, precise barriers, CPU memos, cached uploads,
  shared-constant dedupe, store cards, capture pool, PMULL hash, pipeline memo, linked stages, this port's CPU
  enhancements. (2) On D3D12 only, the race's sky drops out or shows stretched triangles in many frames (Vulkan is
  clean): the PC's toml now picks Vulkan for Renut. (3) The 2x1 and 1x1 levels of some textures read as zero (a
  packed mip tail; far away only).
