# Plan

The order is the one of sa2-nx (`docs/porting-a-360-game-prompt.md` there), which took it from nfsmw-nx and
masseffect-nx: every problem of the translation is far easier to find on a PC than on the console, and ReXGlue's
emulated GPU is the right way to see the first frames, but far too slow on the Switch. Each stage is verified before
the next one starts; what was found is in [sasrt-notes.md](sasrt-notes.md), with its evidence.

## The game

| | |
|---|---|
| Package | Games on Demand (`5345085D/00007000`), 30 SVOD data files, XGD2 game partition; DLC "Bonus Pack" (`00000002`) |
| `default.xex` | 19,808,256 bytes, XEX2, AES + basic compression, version 0.0.0.2, `ASN_Xb360_10.exe`, XDK 2.0.21119 |
| Image | base `0x82000000`, size `0x015E0000`, entry `0x824679C0`; code `0x823B0000`-`0x8302BFD3` (`.xidata` thunks, `.text`, `PSFD00`) |
| Data | `Data/*.M00` archives with `.toc`, Wwise `.pck` sound banks (XMA), CRI `.usm` movies (decoded by the game's code) |

## Stage 1: extract and inspect - done (2026-10-05)

`tools/god_extract.py` (new: reads the GOD package directly and checks its whole SHA-1 tree) extracted the 22 files;
`tools/stfs_extract.py` the DLC. One code module: `default.xex` imports only `xam.xex` and `xboxkrnl.exe`, and the disc
has no other executable. The unusual part is the 62,826-thunk table in `.xidata` (sasrt-notes.md).

## Stage 2: code generator and translation - done (2026-10-05)

- The SDK's analysis had three quadratic loops that never finished on ~135K functions; fixed (codegen: 30 s).
- `tools/thunk_table.py` declares every thunk and every thunk target without `.pdata`.
- `ldbrx`/`stdbrx`/`vavguw` implemented in the generator.
- Sweeps: pointer fixpoint and audit (nothing missing), jump tables (181, one corrected), setjmp/longjmp (none).

## Stage 3: boot on PC with the emulated GPU - working (2026-10-05)

`out\pc\sasrt.exe` (clang 20, `-march=x86-64-v2`) boots through the logos, the intro movie, the autosave warning,
the title, the main menu and the Career menus into a race (Ocean View, laps 1-2), with sound, saving and the Bonus
Pack DLC installed and mounted. Test runs: `tools\win\boot_test.ps1 -InputScript tools\win\input\race.txt` (scripted
controller, `app/src/sasrt_input_script.cpp`), muted and minimized, with video (`-VideoAt`). Logs clean: no call to
an unregistered function, no trap, no unimplemented instruction; one stub (`XCustomSetAction`).

Speed with the emulated GPU (D3D12, this PC's integrated AMD Radeon, other GPU work running at the same time): menus
about 25 frames per second, a race 1-12. The game presents at most 30.

To do: a kernel/XAM import audit (stubs that could break menus: avatars, parties, voice, marketplace); longer soak
runs (a full race, the other modes).

## Stage 4: native renderer on PC - working (2026-10-06)

The PM4-ring Vulkan renderer of masseffect-nx, as adapted by banjo-nx and sa2-nx (`app/src/me`). The game's Direct3D
is the same library as SA2's (all hook targets have SA2's code with other global addresses; table in sasrt-notes.md),
so SA2's hooks carry over with this game's addresses. Then the shader library loop, frame-by-frame comparison against
the emulated GPU, and the fixes, until no visible difference across boot, menus, gameplay and movies.

Result: boot, movies, menus and races render natively at the game's 30 frames per second on this PC (28.0 measured
over a recorded race stretch, with the recorder running). What it took is in sasrt-notes.md ("The native renderer:
what this game needed"): 16-bit fixed-point render targets, the depth restore (raw depth words, parameter generation,
unnormalized fetches; checked exact by `tools/depth_dump_check.py`: restored depth within 5.2e-8 of the resolve), and
the GPU skinning by memory export (banjo-nx's port plus mirror validity, precise barriers, and indexed fetches in
shaders with an element table). The emulated GPU is not a perfect reference for this game (no clouds in races, 1-12
frames per second), so the remaining differences were judged one by one; two small ones are open (notes).

## Stage 5: optimizations, then the Switch - working (2026-10-06)

devkitA64 + libnx, NVK from mesa-switch, the SDK's Horizon layer. Every optimization keeps the image and the game's
behaviour the same and has its own key (docs/enhancements.md: two group masters, premade configurations, verify mode,
a 10 s use report); build-time ones go into the one NRO (the optimised codegen; no A/B pair of NROs since the user's
rule of 2026-10-06, features are compared by config).

- CPU: the game's Direct3D GPU wait sleeps on the ring's progress (`sasrt_cpu_gpu_wait_sleep`: the waiting thread now
  sleeps 7.5-9.4 s of every 10 s in a race); the renderer's CPU fast paths masseffect-nx leaves off in its code, on in
  `app/sasrt_switch.toml` (verify mode: 0 differences over 5.18 M identity, 928 k pairing, 1.31 M PM4-run checks);
  deferred recording stays off (a third slower here); the memory-export mirrors found by a sorted lookup (2,900 -> 108
  live mirrors).
- Codegen flavour "optimised": sa2-nx's codegen options, guest memory without `volatile`, the 127,648 calls through
  the `.xidata` jump thunks made direct (`tools/thunk_calls.py`, this game's), direct calls between unhooked functions.
- GPU: Direct3D's null-shader draws skipped before the EDRAM sync (`sasrt_native_skip_null_draws`) and the shadow
  map's first aliased clear redirected (`sasrt_native_edram4_grid_alias`): race EDRAM transfers 3.07 M -> 1.89 M tiles
  per 10 s, depth imports 46,567 -> 25,500 operations. The candidates left are in docs/gpu-optimisation-candidates.md.
- futari-nx's ring-thread fixes (cached scratch for vertex repacks, no register-file copy per rectangle list, hashed
  diagnostic keys) and its PC profiler (`sasrt_pc_profile_s`, `tools/pc_hot_functions.py`).
- Profiler: futari-nx's all-pcs console profile (`switch_profile_stacks`) with the GPU time per pass category
  (`masseffect_gpu_marks_categories`), both on in `sasrt.toml` and every premade config but verify mode; the Switch
  link map (`out/nx/sdcard_sasrt.map`) and `tools/switch_hot_functions.py`.

## Stage 6: the Switch renderer and an NRO to test - built (2026-10-06)

`tools\win\build_switch_package.ps1` builds `out\nx\sasrt.nro` (`tools\win\build_switch.ps1`), checks it
(`tools/check_switch_build.py`) and lays out the SD card folder `out\nx\sdcard\switch\sasrt-nx`
(`tools\win\package_switch.ps1 -IncludeGame`, docs/switch-testing.md), with the NRO's map in `out\nx\sdcard_sasrt.map`. Build notes: the generated function registration (one function of 135,310 calls) is
compiled at -O0 (GCC 16 did not finish it in 30 minutes at -O3); the NRO title has no `&` (cmd.exe runs the packaging
commands). Not yet run on a console.

Rebuilt 2026-10-06 12:18 with `tools\win\build_switch_ab.ps1` (both flavours, then the SD folder) after the track
work, with two build fixes from the other ports:

- The NVK driver is now linked by full path (`sdk/cmake/rexglue_switch.cmake`): with `-lvulkan` the toolchain's
  portlibs folder came first and every earlier NRO carried the generic Mesa 26.2.1 instead of the nfsmw NVK SDK's
  26.2.2 (banjo-nx's finding). Both NROs now say "Mesa 26.2.2 (git-babaf52908)".
- The optimised flavour has loop barriers (`tools/loop_barriers.py`, futari-nx's finding: GCC hoisted guest polls
  out of loops and the console hung at boot). Branch-to-self instructions in recompiled functions: optimised 1,
  classic 4 (genuine guest halts). The earlier optimised NROs had no barriers and are gone from `out\nx\ab`.

Also new in the SD folder: the 1,982-shader package, `configs/sasrt_cpu_on.toml` and `sasrt_cpu_off.toml` with the
profiler, and an empty `logs/rex/stacks_profile.flag` (every run records a CPU profile; futari-nx's request).

One NRO from 2026-10-06 evening (the user's rule, relayed through sa2-nx): only the optimised codegen is delivered,
with no classic / optimised A/B pair; build-time changes go into it and features are compared through their keys and
the configs. `tools\codegen.ps1` defaults to the optimised flavour, so the PC tree builds the same code as the console
(classic stays available on the PC for diagnosis; the package step refuses a classic NRO). `build_switch_ab.ps1` is
superseded by `build_switch_package.ps1` (it now stops at once). Built 2026-10-06 17:56 (`out\switch_build.log`,
4.8 minutes): 69.3 MB, the NRO names the optimised codegen, 1 branch-to-self in a recompiled function (`sub_82E687D8`,
one of the game's 4 own halts), Mesa 26.2.2 (git-babaf52908); the SD folder has this one NRO. The PC tree, built from
the same generated code, passed verify mode on tracks 2.3 and 0.0 (0 differences, `sasrt_169.log` / `sasrt_170.log`).
`out\nx\ab` still holds the former A/B pair (stale, never packaged again).

The profiler in every config from 2026-10-06 evening (the user's rule, relayed through sa2-nx): `switch_profile_stacks`
and `masseffect_gpu_marks_categories` are on in `sasrt.toml` and set explicitly on in every premade config, off only in
`sasrt_cpu_verify.toml`. The GPU marks left the enhancement table (a non-CPU master used to switch them), the package
step clears `configs\*.toml` before writing them again and no longer makes `logs/rex/stacks_profile.flag` (it forced
the sampler on in verify mode too). Rebuilt and packaged 2026-10-06 22:36 (the same checks passed); a PC boot with the
non-CPU master off and the GPU marks set false logged them false (`sasrt_171.log`: the master no longer touches them).


## After the guide: every track with the 100% save (2026-10-06)

With the user's 100% save (installed in a D: user data root, `out\pc\user_100`; `REX_USER_DATA_ROOT`) every track
can be raced from Career > Single Race, so `tools\win\track_tests.ps1` scripts a race on any of the 20 (cup and slot
of the menu). What that found and fixed (details in sasrt-notes.md):

- The shader package only had what the first World Tour race drew: other tracks lost up to 99,000 shader loads per
  race. A memory scan of the loaded shader objects (`sasrt_dump_shaders_scan_s`) harvested every track in one visit
  each: 250 -> 1,982 shaders, no unidentified shader left on the tracks tested since.
- The specks: FXAA 360 relies on the texture fetch constant's exponent bias, which the renderer ignored, so every
  edge FXAA blended came out twice as bright. Applied now (`sasrt_native_texture_exp_bias`): isolated bright pixels
  per frame 266.6 -> 9.4.
- The GI volumes' integer number format is understood but left off, as in the emulated GPU (open: their 3D data).
  2026-10-21: on in Renut (`sasrt_renut_texture_int_format`): without it every shadow was black (PS3 footage agrees).

Native against emulated captures of the same tracks: results in sasrt-notes.md ("Track tests").

Native replacements of hot game functions (sa2-nx's method, 2026-10-06, docs/enhancements.md): PC profile of a race
-> 30 hottest guest functions ranked with their ARM cost -> localized copies + the CRT memcpy native, verified in
verify mode on three tracks (0 differences; leaf copies checked by a shadow run). A PC A/B showed the call-heavy copies
slower (register syncs at every call), so 14 leaf copies + memcpy ship; on the PC only memcpy measurably helps. The
console decides (`configs/sasrt_natives_off.toml`). On the PC the renderer's ring thread, not the game, limits the
heavy tracks.

## The direct renderer: removing the ring's emulation (2026-10-07)

The user's order, relayed by sa2-nx: remove the CPU-side emulation of the ring renderer, PM4 first, with sa2-nx's
direct renderer as the base; the goal is the ring thread at 8-10 ms a frame on the console and 50-60 % less CPU in
all, every step pixel-identical and A/B-able by config (docs/enhancements.md, "The direct renderer").

- `sasrt_cpu_direct_state`: Direct3D's per-draw state packets reach the ring as host records. This game needed three
  things sa2-nx's version lacks: only draws in the main command buffer (Direct3D patches the command buffers it runs
  from inside a segment after the draw call), a record ring per drawing thread (two threads draw at once), and records
  found by number with the marker's words written back when applied (out-of-order and repeated runs). About 24-52 % of
  the draws converted (by track); verify mode 0 differences over 3.39 M records checked twice.
- `sasrt_cpu_ring_edram_memo` (86-91 % of the draws, 9.0 M hits checked, 0 differences) and
  `sasrt_cpu_ring_compare_uploaded` with the cached upload buffer (`masseffect_native_upload_memory = 1`).
- Deferred Vulkan recording stays explicit-only (futari-nx's lockstep captures found a fade that differs with it).
- The ring's time per draw split by new stopwatches: on the PC the biggest cost is copying vertices (8.7-9.7 of 16.6-18.7
  us per draw; 33-36 GB of vertex data per 10 s in a race), not PM4 parsing (1.4 us). `sasrt_cpu_vertex_containment`
  reuses a draw's vertex window when it lies inside a larger copy of the same buffer in the upload buffer: about 73 %
  fewer vertex bytes copied, verify mode 581,059 reuses checked, 0 differences; the ring thread's own CPU cycles per
  draw 20-38 % lower at the same draw counts. `sasrt_cpu_vertex_merge` copies the contiguous union of overlapping
  windows (copied share of the vertex bytes ~28 % -> ~24 %, verify 0 differences). A cache across frames would need
  write tracking: the game never locks a vertex buffer.
- Lockstep captures cannot prove pixel identity here: two identical runs already differ (races and menus), even with
  the SDK's new `vblank_per_swap_count` and `clock_per_vblank`; verify mode is the proof (0 differences).
- Tools: `tools/win/boot_test.ps1 -SwitchConfig -Set ... -NoMp4` (the console's settings on the PC),
  `tools/win/key_ab.ps1` (PC A/B of one key with the profiler), `tools/win/lockstep_runs.ps1` +
  `tools/lockstep_compare.py` (pixel identity of lockstep captures; the SDK's `vblank_per_swap_count = 2` for this
  30 fps game), `tools/ppc_listing.py` (instruction listing of a recompiled function).
- The game threads, build-time (2026-10-07 ~04:15): `non_volatile_as_local` and `elide_lr_stores` in the optimised
  codegen, `-fno-math-errno -fno-trapping-math` on the game code. Unlocked by fixing `tools/thunk_table.py`, which had
  hidden 82 register save/restore helpers from the generator. `ctx.r14`-`r31` uses fell from 669,839 to 1,586, and
  29,172 helper calls and 158,515 link-register stores went. Executable 63.1 -> 56.5 MB, NRO 69.4 -> 66.7 MB. Verify
  mode on tracks 0.0 and 3.0: 0 differences. The PC now holds the game's 30 fps cap in the race, with the ring
  waiting 4-5 ms a frame for the game (docs/enhancements.md, "Build-time").
  Corrected ~08:20 (banjo-nx's finding): the read-before-write check had ignored every vector register read, since
  each vector instruction looked like a memory store to it. Fixed, it found 9 functions reading an uninitialized
  vector register on a rare path, where the 360 reads the caller's leftovers. So the vector registers are back in ctx
  (`non_volatile_vector_as_local = false`, an option added to this SDK; the 272 VMX helper calls stay), and r14-r31
  and f14-f31 stay locals (0 readers). The NROs packaged between 04:36 and 06:36 had vector locals; the one after
  this does not.
- The in-run A/B (`sasrt_ab_keys`, futari-nx's method; docs/enhancements.md): back-to-back runs are useless while the
  other ports build on this PC, so one run alternates the keys every 2 s and measures both phases. The same-range
  vertex dedupe's reuses are now checked against guest memory like the containment's.
- The round's five runtime keys together (`sasrt_cpu_direct_state`, `_ring_edram_memo`, `_ring_compare_uploaded`,
  `_vertex_containment`, `_vertex_merge`), in-run A/B over the race of track 2.3 (`sasrt_218`, 61 s per phase,
  2,000-2,100 draws per Swap in both):

  | | keys on | keys off | change |
  |---|---|---|---|
  | ring CPU cycles per draw | 48.4 k | 61.6 k | −21.4 % |
  | ring work per Swap | 32.4 ms | 42.7 ms | −24.2 % |
  | ring work per draw | 16.0 µs | 20.6 µs | −22.2 % |
  | whole-process CPU per Swap | 85.1 ms | 99.7 ms | −14.6 % |
  | Swaps per second | 16.8 | 14.7 | +14.3 % |

  The run was GPU-bound: the ring was busy 53 % of the time, and the host GPU took 38-47 ms per menu frame, shared with
  the other ports' tests. The ring's milliseconds include its waits for the host GPU; the cycle count does not.
  Again with the reuse epoch fixed (below) and all six keys, including `sasrt_cpu_vertex_no_fingerprint` (`sasrt_224`,
  62 s per phase; a Switch build ran during part of it, so the absolute numbers are low and both phases shared the
  load):

  | | keys on | keys off | change |
  |---|---|---|---|
  | ring CPU cycles per draw | 40.4 k | 60.2 k | −32.9 % |
  | ring work per draw | 11.6 µs | 18.5 µs | −37.2 % |
  | ring work per Swap | 31.0 ms | 46.0 ms | −32.6 % |
  | whole-process CPU per Swap | 93.6 ms | 116.1 ms | −19.4 % |
  | Swaps per second | 16.7 | 14.2 | +17.5 % |

  Once more after the epoch rule was refined (only waits on memory count; `sasrt_227`, 12 race windows). This run was
  CPU-bound (ring 98.7 % busy), so the frame rate counts too:

  | | keys on | keys off | change |
  |---|---|---|---|
  | ring CPU cycles per draw | 52.1 k | 76.6 k | −32.0 % |
  | ring work per draw | 16.5 µs | 24.7 µs | −33.1 % |
  | ring work per Swap | 38.2 ms | 53.9 ms | −29.2 % |
  | whole-process CPU per Swap | 104.7 ms | 136.7 ms | −23.4 % |
  | Swaps per second | 25.0 | 17.8 | +40.6 % |

  The runs differ by more than their keys (the load did too): read them as the range of the round's effect on the PC,
  −21 to −33 % of the ring's cycles per draw and −15 to −23 % of all CPU per frame. The console A/B is
  `configs/sasrt_test_ab_round.toml` (one run) or `configs/sasrt_test_ring_round_off.toml`.

  Each key alone, the rest of the round on (in-run A/B, race of track 2.3, 61 s per phase, epoch fixed; the
  hash-free dedupe's run, `sasrt_222`, was before the epoch fix):

  | key | ring cycles per draw | ring time per draw | whole-process CPU per Swap | Swaps per second |
  |---|---|---|---|---|
  | `sasrt_cpu_vertex_containment` + `_merge` (`sasrt_230`) | −24.3 % | −33.5 % | −15.2 % | +22.8 % |
  | `sasrt_cpu_ring_edram_memo` (`sasrt_229`) | −2.3 % | −2.9 % | −2.3 % | +1.6 % |
  | `sasrt_cpu_vertex_no_fingerprint` (`sasrt_222`) | −1.4 % | −3.0 % | −2.4 % | +2.2 % |
  | `sasrt_cpu_direct_state` (`sasrt_228`) | −1.7 % | −0.6 % | +1.0 % | −1.7 % |
  | `sasrt_cpu_direct_flush` (`sasrt_238`, at the 30 fps cap) | −1.2 % | −3.7 % | −1.6 % | 0.0 % |
  | `sasrt_cpu_ring_compare_uploaded` (`sasrt_231`, at the 30 fps cap) | −0.7 % | −1.4 % | −1.5 % | +0.5 % |

  The vertex copies are the round's lever on the PC. Direct state moves work from the ring to the drawing thread
  rather than removing it; which matters on the console is the console's in-run A/B to say.
- Correctness fix (banjo-nx's finding, ~05:20): the reuse epoch of the vertex and index reuse was never incremented,
  and Direct3D's command-buffer segments (inline vertices) are recycled without a fence. Now the ring bumps the epoch
  at every point where the game can see GPU progress: about 6-8 times a frame in the menus, about 16 in a race, and
  about 49 in a race when the end of every WAIT_REG_MEM counted too (futari-nx's addition). Only waits on memory
  count now: a wait on a register polls the GPU's own state, which the game neither releases nor sees. Vertex and
  index ranges in command-buffer pages are never reused by address (docs/enhancements.md, "Correctness flags").
  Reuse shrinks: in the menus, containment still avoids about 42 % of the bytes, but the same-range dedupe nearly
  vanishes. The round's numbers above were measured with frame-wide reuse and are measured again with the fix.
- `sasrt_diag_vertex_static`: 98-100 % of the vertex bytes still copied come from guest pages unchanged since a copy
  last read them (about 6-8 pages change per frame). A cache across frames could skip nearly all of it, if it knew
  exactly which pages the game wrote. On the Switch that needs write tracking (a watched page is unmapped there and
  reads fault too), so it is the next round's question, not tonight's.

- The game threads again (~06:10, sa2-nx's round 7): `fp_moves_modeless`, sa2-nx's generator option, ported into this
  SDK (the NRO had 29,792 `msr fpcr`, serializing on the A57; sa2-nx's VMX-heavy thread spent 20-26 % of its samples
  right after one), and texture fingerprints full again (`masseffect_native_fingerprints_sampling` = 0: sa2-nx's
  guard caught the sampled recheck missing a change in 56 of 58 runs). docs/enhancements.md, "Build-time" and
  "Correctness flags". `msr fpcr` in the NRO: 29,792 -> 23,339 (-21.7 %). Verify mode on that build (tracks 2.3 and 3.0, `sasrt_232`/`sasrt_233`): 0 differences, with
  2.9 M direct-state records, 0.5 M containment and 5.1 M dedupe reuses checked.
- The direct renderer's step 2 (~09:30, sa2-nx's request): `sasrt_cpu_direct_flush`. Inside a converted draw call,
  Direct3D's three state flush functions (`sub_82CE1760` constants, `sub_82CE15C0` fetch, `sub_82CE1310` register
  groups; sa2-nx's instruction for instruction) put their register runs into the draw's record and a 3-word
  placeholder into the command buffer, instead of PM4 that `EndDrawDirect` decoded straight back. Each drawing thread
  holds its own producer's marking from its first placeholder (sa2-nx has one drawing thread, this game two). Verify
  mode on track 2.3: 17.1 M flushes checked against the original run on a copy of the device, 0 differences, every
  path exercised (docs/enhancements.md). PC in-run A/B: −1.6 % process CPU per frame at the 30 fps cap; the console
  A/B decides. 43 % of the flushes stay with the original, because their draws lie outside the main command buffer
  (step 1's limit in this game).
- sa2-nx's round 6, the parts that apply here (~10:00):
  - `sasrt_cpu_vertices_base_zero_r0` and the new `sasrt_cpu_ring_bind_changed`: no draw took the base-zero vertex
    binding (every single-binding VS reads r0). Now 33-44 % do, and a draw binds only the bindings that changed: vertex
    bindings per draw −15.7 %, bind calls per draw 0.67-0.92 -> 0.46. Each binding is an NVK macro on the console.
  - `sasrt_cpu_note_shader_fast` / `_pair`: `NoteShaderObject` took a diagnostic mutex four times per draw, on two
    drawing threads. On sa2-nx's console that was about 5.4 % of its main thread.
  - `sasrt_cpu_ring_bound_plan_memo`, and `masseffect_native_fingerprint_mode = 2` (the A57's CRC32 pair) on the
    console.
  - Not ported: `sa2_cpu_direct_pair` and `sa2_cpu_ring_identity_memo` (this game pairs only ~19 % of its draws by
    address; its draws are identified by the ring with the content memo), `sa2_cpu_direct_state_refs`.
- Natives, batches 2 and 3 (~10:45-11:45):
  - `sub_82E7F918`, SlRenderer's hottest function, as a localized copy: −24 % of its PC samples. It stores a whole
    1280x720x4 surface per call, which broke the shadow guard (a linear search, verify crawled). The guard now keeps
    stores by 4 KB page: 32 MB per call in verify mode, 64 KB otherwise.
  - The localizer now takes over 16-byte vector loads and stores in the shadow run, so VMX leaves are guarded too: 20
    copies, all guarded.
  - Five more VMX leaves were added (neutral on the PC; the console decides) and one was dropped as slower.
- The log writer (~13:10, futari-nx's finding): on futari-nx's console the big hitches (a 1,022 ms frame, several of
  250-440 ms) were the ring thread writing its own 10 s report to the SD card. newlib's FILE buffer is 1 KB, so each
  long line was an SD write of its own, 50-150 ms while the music streams from the same card. This port's SDK now has
  futari-nx's `log_file_writer` (default on, `sdk/src/core/logging.cpp`). The logging thread only copies the line to
  memory; a "Log writer" thread at 0x3B writes the batch once a second, or at 64 KB, or on a warning. It never blocks
  (past `log_file_writer_buffer_kb` it drops and counts lines), FlushLogging stays synchronous, and a Switch fatal
  error appends the unwritten tail to rex_crash.log. PC verify run: 6,364 lines, in order, none dropped.
  The ring's shader identity audit logged about 7 warning lines a second in a race, each forcing a flush: those three
  lines are info now, and so are the SDK's `[io] SLOW` open/read lines (futari-nx: 229 of the 304 warnings of a
  6-minute console run, a 128 KB read at 8-10 ms being the SD's normal speed). NRO 13:18.
- The thread stack pool (~15:20, sa2-nx's relay): this SDK had sa2-nx's thread reaper but not the pool that followed
  it. On sa2-nx's console, when the reaper joined a finished guest thread its 16 MB stack went back to a fragmented
  heap, and new guest threads then failed ("heap has NO a 16448 KB block" with 1+ GB free) and waited for joins:
  0.3-1 s frames, 74 s in one run. This game also creates short-lived guest threads during loads. Ported from
  sa2-nx (`sdk/src/core/threading_posix.cpp`, namespace `switch_reaper`, plus `RexSwitchDescribeThreadFailure` in
  `threading_switch.{h,cpp}`; the files differed only by that work). Guest stacks of 8 MB and up are blocks of our
  own, given to libnx through `pthread_attr_setstack`, and up to 4 (80 MB) are kept for the next thread of that
  size. The SDK's own 4 MB threads stay with libnx. A failed creation joins finished threads at once and says which
  resource was missing (`[threads] creating a thread ... failed`). Switch only: the Windows build does not compile
  that file. NRO 15:21.
- Next for the direct renderer (sa2-nx, ~11:50): sa2-nx is removing the guest Direct3D library, PM4 and EDRAM emulation
  altogether, on the user's order to it, and will be the base the other ports start from. Its guide (design,
  verification, per-port address and layout tables) follows when tested; no new step-2-style work here before then.
  This port's constraints for it were sent: two drawing threads, depth-2 command buffers patched after the draw,
  shader objects in .data and physical memory.
- The native Direct3D layer (16:00-17:30, the user's "removing directx for a native arm api"; sa2-nx's API-level
  renderer): DrawIndexedVertices (98 % of this game's draws, which sa2-nx has not made native), DrawVertices,
  DrawVerticesUP / BeginVertices, Clear and the window scissor writer are native code writing the ring's records,
  no PM4 (docs/enhancements.md, "The native Direct3D layer"). Every draw of the main command buffer goes through it;
  steps 1-2 now convert none. Verify mode: 2.0-2.8 M calls per track compared with the original on a device copy,
  0 differences on tracks 2.3, 0.0 and 3.0. Left from sa2-nx's roadmap: the resolve (off by default in sa2-nx
  still), the transport switch (records without marker NOPs) and the EDRAM emulation's removal.
- The codegen (17:20-18:05, the user's "codegen improvements"): `non_argument_as_local` with sa2-nx's keep list and a
  vector rule of this port's own, and the jump-thunk calls as plain direct calls (docs/enhancements.md, "Build-time").
  `ctx.r11` uses 1.17 M -> 15 k. Verify mode on three tracks: 0 differences.
- The Switch compiler set (18:05): sa2-nx's LTO, `-fipa-pta` and hot-function order, with the checks it needs
  (`_start` at 0, no vector FMA). NRO 18:36 (68.07 MB), and the build after it adds the identity memo
  (`sasrt_cpu_ring_identity_memo`, sa2-nx's round 6; 1.24 M draws checked in verify mode, 0 differences).
- Candidates left for the drawing threads, for when the console profile shows them: the Draw* record queue takes a
  CAS per draw and `g_draw_records` a `fetch_add`, both shared by the two drawing threads. Per-thread queues would
  change which records the 32 MB-aliased record table evicts, and so which draws pair, so they need care. Also
  `sub_82E7F918` (a 2D loop that looks like the XDK's texture tiling, about 17 % of SlRenderer on the PC) as a
  native.

### Next: a vertex cache across frames (design, not built)

The biggest item left on the ring, by the numbers above, is the 10-14 GB per 10 s of vertex copies in a race,
nearly all of them from unchanged pages. An exact cache across frames would need:

- **Write tracking from the SDK.** `RegisterPhysicalMemoryInvalidationCallback` and the physical access watches are
  Xenia's, kept in the SDK. On Horizon a watched page is protected by `guest_memory_switch.cpp`: it tries a real
  read-only permission first (`svcSetProcessMemoryPermission`) and unmaps the page if Horizon refuses. Every
  committed chunk also has a private "shadow" alias that is always accessible. The ring would read guest vertex
  memory through that shadow, so only the game's own accesses to a watched page would fault.
- **The cache itself.** A persistent buffer for vertex ranges, keyed like the dedupe (address, size, byte order):
  - A clean range is bound where it already is.
  - A dirty one (the watch callback fired) is copied again to new space, since the GPU may still read the old copy
    for a frame or two; that space is freed after its fence.
  - The draw then binds that buffer instead of the per-frame upload buffer.
- **Console questions first:**
  - Does the read-only permission take on the views, or is every watched page unmapped, so that game reads fault too?
  - What does one fault cost?
  - How many of the game's writes hit watched pages per frame? The diagnostic says 6-27 changed pages per frame;
    each would fault once per frame.
- **Proof:** verify mode compares every cache hit with guest memory, like the containment's check.

The same design would serve every port on this renderer (sa2-nx, banjo-nx, futari-nx have the same copies).

## The CPU round of 2026-10-12 (the user: 15 CPU optimisations for every ReXGlue port, then 15, then 10 more)

Round 1 is in the 2026-10-12 NRO: docs/enhancements.md, "The CPU round of 2026-10-12" (13 changes; its three
censuses, what was measured and dropped, the results). The find was the PC census of flush-mode switches by code
address: 1.4-2.1 million `msr fpcr` a second in a race, halved per frame by two new generator options.

Candidates for the next rounds, from this round's measurements:
- The remaining switches (about 32,000 a frame): longer scalar runs between vector code. Any-mode forms for runs of
  three and more, the fused operations on AArch64, and vector operations in scalar code, once a console run says what
  an `msr fpcr` costs against about twenty extra instructions per operation.
- The vertex copies of the ring (about 0.5 GB per 10 s after containment): an exact cache across frames through page
  protection with a second mapping for the ring's own reads (the design under "Next: a vertex cache across frames").
- Indirect calls: 22,506 sites load from a table of 8 bytes per 4 bytes of code (26 MB, one page per 2 KB of code):
  TLB reach on the A57. A denser table or per-site caches.
- `non_argument_vector_as_local` (15 functions read unwritten lanes: per-lane proofs).
- The SDK libraries inside the LTO link (kernel exports called 170,000 times a second stay out-of-line calls).
- A critical-section spin count from the console profile (500-700 contended enters a second fall into a host wait).

## The rounds of 2026-10-13: sa2-nx's CPU rounds 2 and 3, its GPU keys (the user: all three rounds, and the other CPU and GPU optimisations of sa2-nx; no new LTO or PGO work, that is for the release build)

Done and in the 2026-10-13 NRO; docs/enhancements.md has both sections ("The CPU rounds of 2026-10-13", "The GPU
round of 2026-10-13") and docs/switch-testing.md the console test.

- CPU: sa2-nx's rounds 2 and 3 ported (read-only loads as constants, promoted indirect calls, loop and leaf locals,
  inline divisions, critical-section owners from the guest context, the start-up check of the ARM forms), this
  port's own second round (vector byte reversal and shuffles as known permutations, NEON forms of the VMX helpers),
  and three corrections of what shipped before (the any-mode bet off, `-fno-trapping-math` off, `fctid` rounding).
  Static result against the last ELF counted: -3.8 % instructions, -5.6 % loads and stores in the game code.
- GPU: all 30 plain resolve copies a frame drawn on the 3D engine, four shader specializations, relaxed vsync ported
  and left off (this game is not held to the vsync tick when a frame is late: measured).
- `tools/post_codegen.py` keeps the time of every file its steps leave unchanged: an SDK edit no longer recompiles
  104 generated files.
- The Switch compiler's early register allocation pass is off (`-mearly-ra=none`; peggle2-nx's console finding:
  it drops table lookups in recompiled vector code, and no PC check can see it). Not reproduced in this game's code;
  `tools/early_ra_check.py` compares any generated file with the pass on and off.
- Long sessions, second part (sa2-nx's finding of 2026-10-14, asked for here by the user): the texture cache also
  evicts for descriptor slots and pool gaps and counts memory, not texels (`sasrt_native_texture_slots_evict`). In
  this game the cube heap (64) and the 3D heap (16) are the tight ones: one race takes 20 and 4.
- Long sessions (sa2-nx's report, the same renderer): resolved textures are released when nothing resolved to or
  read them for two minutes, with the crops and depth words derived from them
  (`sasrt_native_resolved_retire_idle`). Before, every address ever resolved to kept its image all session (78
  images after one race) and two bounded caches filled with stale entries.

Still open, in the order I would take them:
1. **The console run.** Everything above is PC-verified only. The profile header's "FPCR on this CPU" line decides
   `fp_mode_lookahead_past_branch`; "GPU per Swap" gives the resolves' real cost.
2. **For the release build (the user's decision):** a console profile session and PGO (sa2-nx's largest single
   step), the inline limit with that profile, the hot-function order from the console profile.
3. **The front buffers:** three 1280x720 resolves a frame that only the Swap reads
   (`masseffect_native_lazy_front`, off here and in sa2-nx; or sa2-nx's alias idea for the front buffer pair).
4. **The six resolves a frame that are not plain copies** (depth resolves through compute, format conversions).
5. From the list above, unchanged: the vertex cache across frames, `non_argument_vector_as_local`, the function
   table without never-address-taken functions (sa2-nx's LTO census: the largest link-time lever, the risky one).
6. sa2-nx's `sa2_native_partial_resolve_inside` is NOT taken: this game resolves its shadow atlas in three parts, and
   banjo-nx found sa2-nx's rule too narrow for that (use banjo-nx's corrected height test if a case ever needs it).

## The first console run (2026-10-14, the user's; the NRO of 2026-10-13 15:30)

- **It crashed when the game created its save** (`rex_crash`: std::terminate, "filesystem error: status: error
  [.../ast_save/ast_save.bin]"). The game creates `ast_save.bin` for reading and writing, writes 600 KB, opens the
  file again for its attributes while the first handle is still open, then closes both (traced on the PC with the
  new SDK diagnostic `diag_save_io`, fresh profile `out/pc/user_fresh`). The Switch refuses that: devkitPro's
  `stat()` opens the file, and Horizon will not open a file that is open for writing (the Where's My Water port's
  notes, `C:/devkitPro/wmw_nx/PORTING_WMW.md` 10.2). The VFS's existence check threw; the second open itself would
  have failed too. Fixed in the SDK: no throwing `std::filesystem` call on the save paths, a path's host descriptor
  is shared between handles (`filesystem_posix.cpp`), path queries about a file we hold answer from it, a read at
  or past the end is end-of-file (WMW 10.1), and `open` / `close` are serialised (WMW 10.3). PC: the save is created
  as before; the Switch part is compiled, not run.
- **Performance: GPU-bound, 3 to 18 frames a second** in handheld mode with the console overclocked (CPU 2.4 GHz,
  GPU 1.23 GHz). The GPU needed 61-100 ms a frame in play; the renderer thread waited for it 5.2-6.5 s of every
  10 s; the CPU was 0.5-0.8 of its 3 cores busy. **The EDRAM emulation alone took 43-45 ms of GPU a frame**
  (imports 12-14, exports 11, aliases 5, nine-pass depth-and-stencil imports 15): more than a whole 30 fps frame.
  The scene passes took 11-49 ms, resolve copies 3 ms. So the next work is the EDRAM traffic (banjo-nx's
  overwrite-proof fixes, its split tiles, rect split and dead raster; docs/gpu-optimisation-candidates.md "4b").
  **Done on 2026-10-14** (docs/enhancements.md, "banjo-nx's EDRAM traffic items" and "Draws that can write
  nothing"): the proofs, split tiles, rect split and the Clear operation ported (depth imports -82 %, transfer
  operations -31 %), and draws that can write nothing skipped before their EDRAM preparation (tiles moved -16 %);
  the PC's EDRAM GPU time about 10.9 -> 9.3 ms a frame with the Clear operation. What is left is real reads (a depth restored through a colour
  alias) and first draws over a surface last used in another format: banjo-nx's reusable Vulkan API and its third
  step (render targets per surface) are what would remove them, and the user's decision is to wait for those.
- **`msr fpcr` measured:** 18.8 ns for a write that toggles the flush mode (about 45 cycles at 2.4 GHz). The
  certain any-mode forms save about 17,000 switches a frame, about 0.3 ms; the bet
  (`fp_mode_lookahead_past_branch`) stays off: its extra operations cost more than the switches it saves.
- **The native memcpy switched itself off** after one `[hot] DIFFERENCE` (byte 32 of a 128-byte copy). The guard
  runs the native, rolls the memory back and runs the original: a source buffer another thread writes in between
  gives exactly this. The copy then runs the original, which is correct either way. To look at.
- **A magenta flash before the SEGA logo:** nothing in the log points at it. To look for in the PC's first frames.

## Open, from the other ports (2026-10-14; nothing built)

- **Split screen is untested, and probably cannot work yet.** The SDK signs in user 0 only
  (`sdk/src/kernel/xam/xam_user.cpp`: every other index is "not signed in"), and the scripted test controller feeds
  user 0 only. peggle2-nx hit exactly this ("Press A on another controller" did nothing) and fixed it in its SDK:
  `xam_guest_signin` signs every further connected controller in as a guest of the profile when the game shows the
  sign-in UI, and answers the sign-in queries for guests (D:\peggle 2\peggle2-nx, same file). To do here: take that
  key, give the input script a second pad, and try a two-player race. Not checked there: a game that ignores the
  guest flag and tries to load or save for the guest.
- **60 frames a second** (peggle2-nx's method, game-specific): presentation interval 1 alone doubled Peggle's game
  speed, because its frame step runs a fixed number of logic updates per drawn frame; one generated-code line asks
  the port how many updates a frame gets. Whether this game steps the same way is not looked at. Only worth it
  where the hardware holds 60, so not for the Switch.
- **Who calls a function reached through a vtable** (diagnostic): the host call stack at a hook is the game's call
  chain (CaptureStackBackTrace + DbgHelp); the guest stack cannot be walked.
- banjo-nx's renderer items: docs/gpu-optimisation-candidates.md, "4b". The EDRAM ones are ported (2026-10-14).
  Its dead raster (memexport point draws that rasterize for nothing) is not needed so far: no point-list draw is
  among the draws that pull the heaviest transfers (sasrt_332's pair report). The persistent vertex arena is ported
  but off (docs/enhancements.md, "banjo-nx's step 4"). Offered 2026-10-15 and waiting: `banjo_ring_pmull_fingerprint`
  (a PMULL-folded CRC-64 instead of the CRC32 pair; banjo-nx's gain comes from its arena's 1.35 GB of hashing per
  10 s, which this port does not have: take it if banjo-nx's console run shows a gain), `banjo_gpu_early_alpha` (no
  alpha-tested group in this game's PC table: revisit with the console's table). Its shader-size items (2026-10-15
  evening, docs/enhancements.md "Item 4 ported, item 1 tried and taken out"): 4 (bone-palette fetches without
  branches) and 2 (texture tests per fetch register) ported, 1 (select() for ?:) measured to change nothing here and
  taken out, 3 (bool constants) does not apply. Next GPU step: the console's per-shader table with these two keys on
  and off.
- banjo-nx's codegen note of 2026-10-16: (1) the generator's `dcbt` / `dcbtst` prefetch read the operands as dcbz's
  ({RA, RB}) where the disassembler gives {CT, RA, RB}: fixed in `sdk/src/codegen/builders/system.cpp`, no output
  change here (`dcbt_prefetch` is off, the generated code has no prefetch); (2) `rotate_word_shifts` (the `rlwinm` /
  `rlwimi` forms GCC makes one instruction of; banjo-nx -0.59 % instructions on 12 files) and (3)
  `tools/ro_constants_cfg.py` (read-only constants followed over loop heads; 2,730 more folds there): offered for the
  build after the console test of the 2026-10-15 17:25 NRO, so that test's results stay with the code it ran.
  Ported on 2026-10-19 with the rest of banjo-nx's codegen rounds (docs/enhancements.md, "banjo-nx's codegen rounds,
  ported 2026-10-19").
- **A fully native deko3d renderer (no PM4 ring, no NVK), banjo-nx's route** (offered by banjo-nx 2026-10-19 at the
  user's request; not started: waits for the user's go-ahead). The kit: `D:\Banjo kazooie port\banjo-nx\docs\
  deko3d-native-renderer-kit.md` (after `docs\rexglue-api-renderer-guide.md`). Renut's Direct3D-level renderer (reNut's
  author permits the user's other ports to reuse it: credit reNut and masterspike52) on plume's deko3d back end, shaders
  XenosRecomp -> SPIR-V -> SPIRV-Cross GLSL -> uam, a DKSH cache built on the PC. Steps for this port, from banjo-nx:
  (1) census of the ~125 Direct3D functions Renut hooks (`D:\Banjo kazooie port\reNut\config\renut_gpu_funcs.toml`)
  against this XDK 2.0.21119 (the SA2-matched names cover part); (2) `tools\renut_gpu_import.py` rewrites the hooks to
  sub_<address> dispatchers, this PM4 renderer stays the reference behind a boot key, and the sasrt_api_* draw / clear
  hooks become the shared case; (3) check every `kDeviceOffset*` of Renut's `d3d.h` (Banjo's 2008 XDK) against this
  XDK's setters before anything renders; (4) the present: the game's interval 2 set to immediate and a 30 fps limiter
  on the display's refresh (banjo-nx's `display_sync.cpp`); (5) order: the PC (plume Vulkan) until frames match this
  renderer, then deko3d in the patched Ryujinx, then the console.
- **Hand-written natives** (banjo-nx, 2026-10-14: sa2-nx's memcpy, memset and Direct3D's two float-constant writers,
  2 to 3 % of its game-thread time by A57 instruction counts; not console-run). Done since, as idea 4 below: memset,
  memmove and the two constant writers are in. banjo-nx's lesson still stands: count A57 instructions per call from
  the Switch compiler's output before calling a native a gain; nothing of that shows on a PC.

## The codegen ideas of 2026-10-14 (the user, through sa2-nx: nine ideas from its hand-written functions)

docs/enhancements.md, "The codegen ideas of 2026-10-14", has each with its counts and checks. Built, each behind its
own switch (`SASRT_GEN_*` in app/CMakeLists.txt) and checked on the PC with verify mode (tracks 2.3 and 0.0, 0
differences): 8 (one-source vperm), 7 (float sign operations, after a census that the game never changes the rounding
mode), 1 (leaf write-backs no caller reads, with a poison build), 2 (single-precision arithmetic in float), 6 (small
memcpy / memset inline), 5 (unaligned stores without byte loops), 4 (memset, memmove and Direct3D constant natives
found by signature). Measured and not built: 9 (the XDK streaming copies never run in this game's profile) and 3 (no
hot loop to version; the hottest main-thread function is straight-line matrix code whose stores are vector registers
kept in the context). Not run on a console.

Open from it, for later:
- single values carried around a loop (an accumulator) still convert each pass: float-typed loop locals;
- a left / right unaligned store pair as one 16-byte store (needs the +16 proof of the index register);
- vector registers as locals between the calls of non-leaf functions, or the dead write-backs of their tails
  (`sub_825E0F28`: 174 stores for 20 guest vector stores);
- sonic-unleashed-nx's candidates of 2026-10-14: the guest clock's dropped remainder on the Switch (an SDK bug,
  negligible in this game at 3,100 reads a second, worth fixing for every port), a flush-mode policy per site from
  the census, record-form vector compares without movemask, unaligned load pairs, and **fused vmaddfp / vnmsubfp
  (one NEON fma: faster and closer to the 360's definition, but it changes results against the PC reference, so it
  is the user's decision)**.
