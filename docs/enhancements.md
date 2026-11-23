# Enhancements

Performance changes that keep the rendered image and the game's behaviour the same. Every one has its own key in
`sasrt.toml` and belongs to a group whose master key must also be on (`sasrt_cpu_enhancements`,
`sasrt_noncpu_enhancements`). The framework is `app/src/sasrt_enhancements.{h,cpp}` (futari-nx's table of keys plus
sa2-nx's registered enhancements with use counters).

What the log shows:

- `[enhancements] sasrt-nx build <date> <time> (<codegen flavour>); masters: ... | N of M active (K not in the
  config, turned on): ... | off: ...`: the startup line. It names the build and its codegen flavour (always the
  optimised codegen on the console: one NRO, see "Build-time") and lists every key, active or not (`(master off)` when
  only the master stops it).

On the console a key that the config leaves out is turned on when its master is on (the K above): a `sasrt.toml` left
on the SD card from an older build lacks the newer keys, and they used to stay at their code defaults, mostly off
(futari-nx's console run of 2026-10-06 had 21 CPU enhancements off that way). A key set in the config, the
environment or on the command line is respected. The three deferred-recording keys are explicit-only: never turned on
that way (a third slower in this game, and with `masseffect_native_output_no_wait` futari-nx measured ~100 ms stalls
per copy). The PC keeps the code defaults: its `sasrt.toml` lists no keys, and the PC measurements here were made
with them.
- `[enh] uses in the last 10 s: ...`: how often each of the port's own enhancements ran, and its amount (time asleep
  for the GPU wait). An enhancement that is on but never appears here did not run.
- `[verify] checks done: ... | differences: D` every 10 s in verify mode: D must stay 0.

Premade configurations (`python tools/make_enhancement_configs.py`; `tools\win\package_switch.ps1` puts them in
`configs/` next to the NRO):

| File | Change from `sasrt.toml` |
|---|---|
| `sasrt_cpu_on.toml` | nothing (A/B side "on") |
| `sasrt_cpu_off.toml` | the CPU group off (A/B side "off") |
| `sasrt_natives_off.toml` | the native replacements batch off (`sasrt_cpu_natives = false`) |
| `sasrt_noncpu_off.toml` | the non-CPU group off |
| `sasrt_all_off.toml` | both groups off: the original paths everywhere |
| `sasrt_cpu_verify.toml` | `sasrt_cpu_verify = true`: every renderer fast path is checked against the original path on every use (the vertex copies: the first 20,000); slower. The profiler OFF |
| `sasrt_profile.toml` | nothing (the same as `sasrt_cpu_on.toml`; kept for older notes) |
| `sasrt_test_direct_state_off.toml` | `sasrt_cpu_direct_state = false` (A/B of the direct renderer's draw state records) |
| `sasrt_test_direct_flush_off.toml` | `sasrt_cpu_direct_flush = false` (A/B of the direct renderer's step 2) |
| `sasrt_test_vertex_containment_off.toml` | `sasrt_cpu_vertex_containment = false` (A/B of the vertex window reuse) |
| `sasrt_test_vertex_no_fingerprint_off.toml` | `sasrt_cpu_vertex_no_fingerprint = false` (A/B of the hash-free dedupe) |
| `sasrt_test_vertex_binds_off.toml` | `sasrt_cpu_vertices_base_zero_r0` and `sasrt_cpu_ring_bind_changed` false (A/B of the vertex bindings) |
| `sasrt_test_note_shader_off.toml` | `sasrt_cpu_note_shader_fast` and `sasrt_cpu_note_shader_pair` false (A/B of the drawing threads' shader notes) |
| `sasrt_test_ring_round_off.toml` | the direct renderer round's six ring keys false (A/B of the whole round) |
| `sasrt_test_ab_round.toml` | the same six keys switched off and on every 2 s in one run (the in-run A/B) |
| `sasrt_test_deferred_on.toml` | deferred Vulkan recording on (the console A/B; not pixel-identical in futari-nx) |
| `sasrt_test_cpu_round12_off.toml` | the run-time keys of the CPU round of 2026-10-12 false: `sasrt_cpu_guest_cas_no_barrier`, `sasrt_cpu_index_no_fingerprint`, `sasrt_cpu_ring_draw_trims`, `sasrt_cpu_hook_counter_ctx`, `sasrt_api_thread_stats`, `thread_signal_skip_idle`, and since 2026-10-13 `kernel_critsec_pcr_owner` (the build-time parts stay) |
| `sasrt_test_gpu_round13_off.toml` | the six GPU keys of 2026-10-13 false: `sasrt_gpu_resolve_draw`, `sasrt_gpu_index_base_held`, `sasrt_gpu_blend_skip`, `sasrt_gpu_texcoords_unswapped`, `sasrt_gpu_no_texture_signs`, `sasrt_gpu_identity_remap` (same shader package) |
| `sasrt_test_vsync_relaxed_on.toml` | `sasrt_vsync_relaxed = true` (off by default: no effect measured on the PC) |
| `sasrt_test_resolved_retire_off.toml` | `sasrt_native_resolved_retire_idle = false`: resolved textures kept for the whole session, as before 2026-10-13 |
| `sasrt_test_texture_slots_off.toml` | `sasrt_native_texture_slots_evict = false`: the texture cache evicts by texel bytes only, as before 2026-10-14 |
| `sasrt_test_edram_banjo_off.toml` | banjo-nx's EDRAM items of 2026-10-14 off, the Clear operation included |
| `sasrt_test_dead_draws_off.toml` | `sasrt_gpu_skip_dead_draws = false`: draws that can write nothing drawn again |
| `sasrt_test_api_clear_off.toml` | `sasrt_gpu_api_clear = false`: banjo-nx's Clear operation alone off |
| `sasrt_test_ring_step4_off.toml` | banjo-nx's step 4 on the ring off (texture range invalidation, persistent indices) |
| `sasrt_test_gpu_groups.toml` | `sasrt_diag_gpu_groups = 2`: GPU time per draw state and pixel shader (measurement) |
| `sasrt_test_vfetch_block_off.toml` | `sasrt_gpu_vfetch_block = false` (bone-palette fetches word by word again), with the per-shader GPU table |
| `sasrt_test_signs_per_slot_off.toml` | `sasrt_gpu_texture_signs_per_slot = false` (texture tests removed per draw only), with the per-shader GPU table |

Any of the port's own keys can also be A/B'd within one run: `sasrt_ab_keys = "key1;key2"` switches them off and on
together every `sasrt_ab_period_ms` (2,000) at a Swap ("In-run A/B" below).

The profiler is on in `sasrt.toml` and in every configuration (the user's choice of 2026-10-06, relayed from sa2-nx:
every test run brings its profile; since 2026-10-21, "the profiler on in all logs", the verify config too):
`switch_profile_stacks = true` (the CPU sampler, every busy thread's pc every 1 ms into `rex_profile_NNN.log`, one per
session with the number of its `sasrt_NNN.log`: a single `rex_profile.log` was rewritten at every start, so of two runs
only the last one's came back), `masseffect_gpu_marks_categories = true` (GPU time per pass category and the idle gap
in the "GPU per Swap" lines; it does not change the image) and `renut_gpu_profile = 10` (Renut's "GPU profile" line
every 10 s, the GPU's time per frame by kind of work). Every A/B side pays the same cost. The generator sets the keys
explicitly in each config, and none is in the enhancement table, so no master turns them on or off (the GPU marks
used to be a non-CPU row, which `sasrt_noncpu_off` / `sasrt_all_off` set to on). The measurements that cost GPU time
or extra work stay at their off defaults: `masseffect_native_stats_pipeline` (pipeline statistics queries),
`masseffect_native_stats_per_draw_s` (per-draw queries), `masseffect_native_nvk_measure_failures` and
`masseffect_native_count_changes_pipeline`. The empty `logs/rex/stacks_profile.flag` the SD folder used to carry is
gone: it turned the sampler on whatever the config said, verify mode included.

How to measure: the same spot with one configuration changed. The game presents at most 30 frames a second, so
compare the CPU % of the threads in `rex_profile.log` and the `[enh] uses` sleep time, not only the frame rate.

## CPU group

### Localized copies of every profiled function and five hand-written natives (2026-11-08; katamari-nx's method)

The user's request of 2026-11-08: Beautiful Katamari's `docs/optimising-functions.md` for this port, "machine optimise
all copies the profiler catches and optimise the top ten hottest functions", verified in the emulator.
`docs/optimising-functions.md` has the details; credit to katamari-nx, banjo-nx (the localizer and the guard), bejeweled3-nx
(the bulk list and the direct dispatch) and sa2-nx (the localized copies and its first natives).

- **Machine track**: katamari-nx's `tools/localize_native.py` and guard (`app/src/cpu/banjo_hot_guest.cpp`, twelve bulk
  shards) replace sa2-nx's older ones for the localized copies. Every generated function the stock-clock console profile
  sampled (`rex_profile_008`, `tools/switch_hot_bulk.py` on the link map) is a copy unless the tool refuses it: 23 listed
  and 939 bulk copies (1,094 hooked addresses; `tools/direct_calls.py` routes their callers through the hooks). Keys:
  `sasrt_cpu_native_sub_<address>` each, `banjo_cpu_native_bulk` for the bulk list, `banjo_hot_guard_calls` /
  `banjo_hot_guard_period` for the guard (both 0: the direct dispatch).
- **The localizer's changes for this port**: hand-written natives in front of a real call (`hand.txt` `reads=`, for the stack
  cookie check at the end of 73 copies), the proven-dead leaf write-backs out of the guard's compare, and merged vector
  stores in the copies (an stvlx / stvrx pair or four stvewx of one vector as one 16-byte store; CMake
  `SASRT_HOT_MERGED_STORES`, ON).
- **Hand track**: five natives in `app/src/cpu/hot/banjo_hand_natives.h`, each with its own key, default on:
  `sasrt_hand_water_step` (`sub_8286C230`, the hottest function), `sasrt_hand_water_table` (`sub_82872180`, second),
  `sasrt_hand_resampler` (`sub_82720840`), `sasrt_hand_sphere_fit` (`sub_8279A888`) and `sasrt_hand_cookie_check`
  (`sub_82C92CC8`). The rest of the top ten declined with the reason recorded (three have atomics, four are arithmetic the
  exact form needs, one is a call).
- **Exact**: the guard compares each copy and native with the recompiled original (registers, written bytes, the flush mode).
  The PC race of `sasrt_711`: 4,828,068 calls compared, 0 differences; Ryujinx `hot_verify2` (race): 6,779,144 compared,
  0 differences. Test tomls: `sasrt_hot_verify` (dense guard) and `sasrt_hot_off`.
- **Console (stock clocks, the in-run A/B target 70)**: 97.1 ms of CPU a frame (all threads) with the copies, 96.8 ms
  without: no measurable saving in the race (GPU-bound at 17.7 fps either way). The NRO grew by 12.5 MB.

### `sasrt_cpu_gpu_wait_sleep` (+ `sasrt_gpu_wait_max_us`, default 1000)

Direct3D's waits for the GPU (11 call sites, all through the `.xidata` thunk `0x8247A520`) loop on one iteration
function, `sub_82CD3668`: 32 `db16cyc` delays, then a look at the GPU read pointer and the hang timer. It is sa2-nx's
`sub_8254F400`, the same code with other global addresses (`app/src/sasrt_gpu_wait.cpp`; the hook checks the FNV-1a
hash of the 224 bytes of game code it was written from). Before an iteration in which nothing can have changed, the
hook sleeps on the native renderer's ring progress:

- the same wait record as the previous iteration on this thread;
- the read pointer unchanged;
- no ring progress, fence write or interrupt since that iteration returned.

With the emulated GPU (no ring thread) it never sleeps.

- **Why exact:** the game reads the same memory and takes the same decisions, only later. The progress counter is read
  after the original iteration returns, so progress the caller could have missed always prevents the next sleep.
- **Risk:** a wait for something that neither the ring nor an interrupt reports would lose up to `max_us` per
  iteration.
- **Measured (PC, race, 2026-10-06):** 4,646 to 5,274 sleeps and 7.5 to 9.4 s asleep per 10 s, time the waiting
  thread used to spend spinning. The recorded race stretch ran at 29.6 frames per second (the game's cap is 30; 28.0
  in the run before, also with the recorder). On Windows a 1 ms timed wait lasts about 1.8 ms on average (timer
  granularity); a wake-up by the ring thread is immediate.

### The renderer's and the SDK's CPU work (table in `sasrt_enhancements.cpp`)

These are cvars of the native renderer (masseffect-nx, banjo-nx, sa2-nx) and the SDK, listed with the value that
switches each one on and the value that turns it off; `sasrt_cpu_enhancements = false` sets them all to "off". Most
are on in the code. The ones masseffect-nx measured on the console but left off in its code are turned on by
`app/sasrt_switch.toml`:

- `masseffect_native_deferred_recording`, `masseffect_deferred_native_fast`, `masseffect_deferred_native_update`: a
  worker thread records the Vulkan commands (Mass Effect: ring thread 62 % -> 40 %);
- `masseffect_native_fast_pair`, `masseffect_native_raw_microcode`, `masseffect_native_pm4_fast`,
  `masseffect_native_flat_identity`, `masseffect_native_compare_fast`, `masseffect_native_fast_copy`,
  `masseffect_native_indices_cache`, `masseffect_notify_no_lock`, `masseffect_native_fingerprint_mode = 1`,
  `masseffect_native_dedupe_max_fingerprint = 16384`: the ring thread's per-draw work;
- `masseffect_native_diag_reuse = false`, `masseffect_native_diag_memory_upload = false`,
  `masseffect_native_precise_marks = false`: diagnostics that cost time.

Each of these has its own self-check (the old and the new path compared on the first uses, `DIFFERENCE` / `MISMATCH`
logged and that path turned off). Checked on PC with all of them on in verify mode: see "Verification" below.

### Native replacements of hot guest functions (`sasrt_cpu_native_*`, batch master `sasrt_cpu_natives`)

sa2-nx's method (2026-10-06), in `app/src/hot`: find the hottest guest functions, replace them by native versions
that are faster on the Switch's ARM cores, check on the PC that the game behaves exactly the same, measure on the
console.

- **Find.** The PC profile of a race (`sasrt_pc_profile_s`, busy samples, self time, every game thread except the
  renderer's own) ranked by `tools/arm_hot_functions.py`, which adds each function's AArch64 cost in the Switch ELF
  (FP-mode switches, byte swaps, barriers, calls). The profile is flat: the hottest function is 1.1 % of the game
  threads' busy samples, the 30 picked together about 12 %. On the PC the renderer's ring thread, not the game, limits
  the heavy tracks (99.5 % busy on track 2.3).
- **Write.** Localized copies (`tools/localize_native.py`, list `app/src/hot/localized.txt`, regenerated into
  `app/generated/hot/` by `tools/post_codegen.py` after every codegen, so each copy matches its codegen flavour): the
  recompiled function's own C++ with the guest registers in C++ locals (written back before every call and return:
  it never writes a register the original leaves alone, which interprocedural register allocation requires), plain
  guest memory and a compiler barrier at every loop header (GCC hoists guest polls otherwise). The first batch had
  36: 28 of the profile's top functions (sub_82C90430 refused: bare double arithmetic) and 8 lower-ranked leaves added
  for guard coverage. After the PC A/B (below) 14 remain: the leaves and sub_827C56C8, whose only calls are the
  register save/restore helpers.
  The CRT memcpy (`sub_82C8EEF0`, byte for byte sa2-nx's `sub_827F05C0`) is sa2-nx's hand-written native (host
  memcpy/memmove; the forward-overlap case runs the original).
- **Guard.** Leaf copies whose memory accesses all go through the guest-memory macros (10 of them) also get a
  `Shadow()` version whose stores are kept aside: for the first 256 calls of each thread and 1 in 4096 afterwards
  (every call with `sasrt_cpu_verify`), the shadow runs on a copy of the registers, the original runs for real, and
  every register, every stored byte and the FPU mode are compared. memcpy is checked through its written range (rolled
  back between the two runs). A difference logs `[hot] DIFFERENCE` and turns that hook off. The 26 copies that call
  other functions run unguarded (a check would run their callees' side effects twice): exact by construction.
- **Each** has its own key (`sasrt_cpu_native_sub_<addr>`, `sasrt_cpu_native_memcpy`), engages only if the loaded
  game code has the FNV-1a hash it was made from, and counts its calls in the `[enh] uses` line. `sasrt_cpu_natives =
  false` turns the batch off (`configs/sasrt_natives_off.toml`, the A/B config, profiler on like `sasrt_cpu_on.toml`).
- **Verified (PC, verify mode, races on tracks 2.3, 0.0 and 3.0, the first batch: 37 hooks, the 15 kept among them):** 0 differences; 8 guarded hooks over
  1 M checks per run. The first run had one false difference: x86's MXCSR holds sticky exception flags, and a copy
  that skipped one operation on a denormal left the denormal flag clear; the guard now compares only the
  guest-controlled FPU bits (`FPSCRRegister::GuestMask`). Those runs had the classic codegen; with the optimised one,
  the only flavour since 2026-10-06 evening (the copies are then made from its code), tracks 2.3 and 0.0 again: the 15
  hooks on, 0 differences (`sasrt_169.log`, `sasrt_170.log`).
- **Measured (PC, `tools/win/natives_ab.ps1`: the same race on track 2.3 with `sasrt_cpu_natives` on and off, the PC
  profiler on, 100-110 s of racing each):** with all 36 copies the game threads used 13-18 % MORE CPU per frame.
  Per function, the copies that call other functions got slower (sub_82754EC0 850 -> 1,538 samples, sub_8274C300 503
  -> 1,060, sub_825E0F28 1,410 -> 1,931): a copy writes back and reloads every localized register at each call, which
  cost more than the locals saved; they were left out (they need a localizer that syncs only what a call can read or
  change). With the 15 kept: the replaced functions' samples 466 -> 426 per 10 s (-9 %), nearly all of it memcpy (58
  -> 1); the leaves are within the run-to-run noise on the PC (x86 and clang already handle them well). The console
  decides (the A/B pair `configs/sasrt_cpu_on.toml` / `configs/sasrt_natives_off.toml`).
- **Risk:** an unguarded copy that differs on inputs no check saw (the transformation is mechanical and the guarded
  ones exercise it; sa2-nx's guard caught two localizer bugs, fixed in the tool this port took).
- **Batch 2 (2026-10-07): `sub_82E7F918`**, the hottest function of the SlRenderer thread in a PC race profile (17 %
  of its samples, `sasrt_242`). It is a 2D loop with lookup tables that looks like the XDK's texture tiling, called
  through `sub_82E803C8`, and its only calls are the register save/restore helpers. The recompiled code makes about
  1,000 uses of ctx.r3-r11; the copy keeps them in C++ locals and accesses guest memory without `volatile`. It is a
  leaf with the shadow guard (11 registers, 2 loops). Key:
  `sasrt_cpu_native_sub_82e7f918`. Its calls store a whole 1280x720x4 surface (3.7 MB) each, about 25-50 times a
  second in a race. Verify mode (`sasrt_249`): 256 calls checked in full, no difference. PC in-run A/B of this key
  (`sasrt_250`, the profiler's samples by phase, off and on phases of 106 and 107 s): the original 36.0 samples per
  second, the copy 27.4 (−24 %). Whole-process CPU is within noise at that size.
  **2026-10-21: a hand-written native now** (`app/src/hot/n_82E7F918_yuv.h`, the same key; out of `localized.txt`).
  The function is the movie player's colour conversion, not tiling: one decoded 4:2:0 picture (luma, two chroma
  planes) into 32-bit pixels through six 256-entry tables at 0x832ECF50 (luma, two chroma terms each way, a clamp
  indexed by sum >> 20), once per frame of every movie (all four are 1280x720 at 30 fps). The console's profile of the
  logos movie: 62 % of the SlRenderer thread in the copy; the user's console ran the intro movie at 18 fps at stock
  clocks. The native copies the tables host-endian once a call (the clamp over exactly the indices the tables can make,
  checked free of 32-bit overflow) and does 16 pixels at a time with simde's NEON (native on the Switch) where the
  clamp table is clamp(i - 256, 0, 255) (indices 0..767; the saturating narrows), any group reaching outside that
  (the tables can make -21..790, and below 0 the original reads the next table's words) through the table in scalar
  code; r3 left as the original leaves it. Declines (the original runs) on negative sizes, ranges leaving their view,
  the target overlapping the sources or tables. Verify mode: PC 256 calls and Ryujinx (the ARM NEON code) 256+ calls
  of the intro, no difference. Guard: its range check now allows 16 MB a call (`Writes::kMaxBytes`, was 1 MB), and
  outside verify mode a call writing over 1 MB is checked 4 times, then runs unchecked (each check copies its bytes
  three times and runs the original too). Config: `sasrt_movie_colour_native_off.toml`.
- **The shadow guard, made fit for large writers (2026-10-07):** its first verify run crawled (36 frames in 240 s).
  The shadow kept at most 4,096 stored bytes and found each by a linear search, also after an overflow. A call that
  stores more than that (this loop does) then scanned 4,096 entries on every guest access, about a billion compares
  per checked call, and verify mode checks every call. Outside verify mode the first 256 calls of each thread would
  have stalled the same way on the console. This function stores a whole 1280x720x4 surface per call (3,686,504
  bytes). Now the kept bytes are held by 4 KB page (a valid bit and a value per byte), found through a small
  generation-tagged index of page numbers and a last-page cache. In verify mode a check keeps up to 32 MB per call, so
  this copy is verified on the PC (`sasrt_249`: 256 calls, each comparing its 3.7 MB, no difference). Outside verify
  mode a check keeps 64 KB. After four checked calls that store more, a hook is no longer checked (each check would run
  the whole call twice for nothing), so the console's first calls do not stall. All of this is logged (`[hot] ...
  checked calls stored more bytes than a check keeps`), and every hook reports its first 256 checks too.
- **Batch 3 (2026-10-07): six VMX leaves**, the next hottest functions of the game threads in the same profile:
  `sub_82EB23E0` (3.3 % of SlRenderer), `sub_82EB6B78` (1.7 %), `sub_830260A0` (1.5 %), `sub_82D7B288` (1.0 % of a
  worker thread), `sub_83027D38` and `sub_830291B8`. Their only raw memory accesses are 16-byte vector loads and stores
  through `REX_RAW_ADDR` (`simde_mm_load_si128` / `simde_mm_store_si128`). `tools/localize_native.py` now rewrites
  exactly those two shapes in the `Shadow()` body into `ShLoadV` / `ShStoreV` (`sasrt_hot_guest.cpp`), 16 bytes each
  through the shadow's kept stores, so these leaves get the shadow guard. Any other raw access still leaves a copy
  unguarded. The same change guards the batch-1 leaves that ran unguarded for that reason (`sub_82757940`,
  `sub_82748550`, `sub_8279A888`, and `sub_827C56C8`, a leaf since the helper calls are elided): all 21 copies now
  have the guard. Verify mode on track 2.3 (`sasrt_253`): 0 differences. `sub_82EB23E0`, `sub_82757940` and
  `sub_82748550` passed over a million checks, the others over 4,096, and `sub_830260A0`, `sub_83027D38` and
  `sub_830291B8` ran fewer than 256 times. PC in-run A/B of the six (`sasrt_254`, samples by phase):
  `sub_82EB23E0` 2,137 -> 2,057 (−4 %), and `sub_82EB6B78` 1,207 -> 1,363 (+13 %), so it was left out.
  `sub_82D7B288` 109 -> 124 is too few samples to tell. The small ones inline into their hooks, so the profile cannot
  separate them. Whole-process CPU per Swap −1.3 % (noise level). As with batch 1's leaves, the console decides
  (`sasrt_ab_keys` with their keys). 20 copies in all, every one guarded.
- **In-run A/B of a native:** the hooks now follow their key on every call (one byte load), so `sasrt_ab_keys =
  "sasrt_cpu_native_sub_<addr>"` switches a native off and on within one run. Each call runs either the copy or the
  original, both exact.
- **Checks of one copy run one at a time (2026-10-07):** verify mode on track 0.0 (`sasrt_264`) switched off
  `sub_82611908` (a quaternion decode the animation threads call) for r8 native=0xffffffff82020000 against
  original=2. The copy was right: its first call initialises two statics behind a guard word, the shadow run found
  the guard clear, and another thread's first call set it before this thread's original ran, so the two runs took
  different paths. The shadow run keeps the guard store aside (the generated `Shadow()` redirects it), so the store
  that changed it came from another thread. Checked calls now hold a lock per copy (16 striped mutexes, by address)
  from the shadow run to the comparison. Every copy with a shadow run is a leaf, so the lock is held across no call.
  In verify mode, where every call is checked, a copy's calls on different threads cannot cross. Elsewhere only the
  checked calls take the lock (the first 256 and 1 in 4,096), and calls that are not checked still race as the
  game's own code does. Verify mode afterwards: tracks 0.0 (`sasrt_265`; `sub_82611908` passed 4,096 checks) and 3.0
  (`sasrt_266`), 0 differences.

### Ring-thread fixes from futari-nx's PC profiler (always on)

Changes of how the renderer does something, not alternative paths, so they have no key:

- Vertex repacks (10/11-bit vertex formats) are converted in a cached scratch copy and written to the upload buffer
  in one go. The upload buffer has no CPU cache on the Switch (write-combined on the PC), and the in-place conversion
  read every packed word back from it; it was 91 % of Futari's ring thread. The 10 s line
  `null draws skipped ...; vertex ranges repacked` counts them.
- `ProveRectangleList` changes the two registers the extent estimate needs in place and restores them, instead of
  copying the whole register file for every rectangle list.
- The bounded-extent diagnostic keys the cases it has logged by a hash, not by a string formatted for every such draw.

The PC profiler that found them is in too: `sasrt_pc_profile_s = N` writes `logs/pc_profile.log` every N seconds
(self time, hot lines, callers), `python tools/pc_hot_functions.py out/pc/logs/pc_profile.log` adds the windows up.

### The direct renderer (2026-10-07): removing the ring's emulation, sa2-nx's round 5

The user's order (relayed by sa2-nx): remove the CPU-side emulation of the ring renderer, PM4 first, with sa2-nx's
direct renderer as the base (`D:\sonic adventure 2\sa2-nx\docs\direct-renderer.md`); the goal is the ring thread at
8-10 ms a frame on the console and 50-60 % less CPU in all. Every step keeps the image identical, checks itself and has
its own key (CPU group).

#### `sasrt_cpu_direct_state`: the draw state without PM4

- **What:** the hooks of the three Draw* functions (`sub_82CD18D0`, `sub_82CD1DB8`, `sub_82CD1168`,
  `src/me/sasrt_me_hooks.cpp`) call `BeginDrawDirect` before the original and `EndDrawDirect` right after it.
  `EndDrawDirect` (`src/me/me_native_system.cpp`, namespace `direct`) decodes the packets the call wrote before its draw
  packet into a host record (register runs in host order, type-1 pairs, the type-3 packets the ring handles anyway) and
  covers them with one NOP packet (header, `'SA2D'`, the record's number). The ring applies the record in `Type3`'s NOP
  case through the same register writes, at the same place in the stream.
- **This game's Direct3D** (XDK 21119, SA2's 21076 with other addresses): device+48 is the last word written (`stwu`
  pre-increment), +52 the segment end, +56 the end less 160 bytes (`sub_82CDCD20` / `sub_82CDCD90` set them). Found
  with `tools/ppc_listing.py` (the instruction listing of any recompiled function).
- **What this game needed beyond sa2-nx's version** (each found by a self-check, not by a picture):
  - **Only the main command buffer.** Direct3D also runs command buffers from inside a segment (indirect buffers at
    depth 2, 05293000-08C356B4 on the PC, written by a second drawing thread; one ran 17,719 times in 170 s). Their
    packets are changed after the draw call returns: the ring's check found every such record different from the
    region its marker covered (the region decoded to fewer operations). So a draw is converted only when its packets
    lie in the main command buffer: the address range the primary ring's own indirect buffers cover, learned by the
    ring (`g_pool_lo/hi`). The diagnostic key `sasrt_direct_state_nested` converts the others too, to see it again.
    That leaves 24-52 % of the draws converted, by track (the report's "outside the main command buffer").
  - **Two drawing threads.** Two threads call Draw* at the same time (each with its own write pointer); records of
    both landed on the same words. Each drawing thread has its own record ring and index; the producer is in the top
    bits of the record's number. No lock and no atomic read-modify-write per draw (the ARM rule).
  - **Out of order and run again.** Markers are found by number through an index, not in order, and when the ring
    applies a record it writes the three words the marker replaced back, so a range run again (a replay, a tile pass)
    parses the original packets. Records are released when applied, or once 16,384 newer markers were reached.
  - Between `D3DDevice_BeginTiling` and `EndTiling` (hooked) nothing is converted (the tiled range runs once per tile).
- **Why exact:** the same register writes in the same order at the same place in the stream.
- **Self-checks:** the first 4,096 records (every record in verify mode) are re-encoded and compared word for word with
  what Direct3D wrote, at the draw; and, banjo-nx's check, when the ring applies a record it rebuilds the region as the
  command buffer holds it then (the three saved words and the rest of the payload) and compares again, which is what
  shows a packet changed after the call. A difference or a lost record logs DIFFERENCE / an error, counts in the
  `[verify]` line and stops the conversion.
- **Verify mode (PC, the console settings, track 2.3, `sasrt_183.log`):** 3,386,261 records checked at the draw and
  3,385,223 when applied, 0 differ, 0 lost; every renderer check 0 differences.
- **Measured (PC, `tools/win/key_ab.ps1`, the PC loaded by four other ports):** the ring thread's work per draw in the
  race about 22.0 -> 17.4 µs (-21 %), sa2-nx's version, before the main-buffer limit.
- **Measured again, 2026-10-07, in-run A/B of this key alone with the rest of the round on** (`sasrt_228`, race of
  track 2.3, 61 s per phase): ring cycles per draw −1.7 %, ring time per draw −0.6 %, whole-process CPU per Swap
  +1.0 %. With the main-buffer limit it converts 24-52 % of the draws, depending on the track (the rest: 16-51 % in
  command buffers outside the main one, 18-49 % with fewer than three state words, too few for a marker). On the PC
  parsing was already cheap (0.35-1.5 µs of a ~16 µs draw). So the key mostly moves work from the ring to the drawing
  thread, which re-encodes the packets; on the console, where the ring is the bottleneck, that still matters. The
  console's own in-run A/B decides (`sasrt_ab_keys = "sasrt_cpu_direct_state"`).
- **Key:** `sasrt_cpu_direct_state`. A/B: `configs/sasrt_test_direct_state_off.toml`.
- **Report:** `[native] direct state (cumulative): ...`: draws converted, records applied (out of order, at depth 2),
  lost (must stay 0), why the others were left as PM4, the drawing threads, the records checked against their region.

#### `sasrt_cpu_direct_flush`: Direct3D's state flush writes the record (step 2, sa2-nx's, 2026-10-07)

- **Why:** after step 1 the drawing thread still encodes every dirty register into PM4 (Direct3D's flush functions),
  and `EndDrawDirect` decodes it straight back into the record. On sa2-nx's console that decode plus its barrier stalls
  were 5.3 % of the game thread, the flush functions 3-4 %.
- **The three flush functions** (called by each Draw* function's inlined FlushState with r3 = device, r4 = dirty mask,
  bit 63 first, r5 = first register, r6 = shadow). They are sa2-nx's instruction for instruction (read with
  `tools/ppc_listing.py`):
  - `sub_82CE1760`, the shader constants: 16 registers per bit at 0x4000 (VS) / 0x4400 (PS); up to three type-2
    fillers put the values on 16 bytes; fast path while `w + (count + 3) * 4 < device+52`.
  - `sub_82CE15C0`, the fetch constants: 6 registers per bit from 0x4800, shadow at device+1152; one filler puts the
    values on 8 bytes; it ends with registers 0x5000-0x5002 = (0, 0x25000, 0) on its fast path (two `std` of 37 << 44)
    and (0, 0, 0) on its slow path.
  - `sub_82CE1310`, the register groups: 1 register per bit, called eight times by the Draw* functions.
- **Inside a converted draw call** (between BeginDrawDirect and EndDrawDirect), each hook (`src/me/sasrt_me_hooks.cpp`)
  calls `FlushRunsDirect`. It follows the original's fast path on paper (the same space checks and fillers); if any
  run would take the slow path, the original runs. Otherwise the register runs, values byte-swapped from the shadow,
  go into the drawing thread's pending ops, and a 3-word placeholder NOP [0xC0011000]['SA2F'][spot] goes into the
  command buffer where the first packet would have started (device+48 advances by 12).
- **`EndDrawDirect`** decodes the region as in step 1; on a placeholder of this call it copies that spot's ops into
  the record at that place (ops `kFlushSpot` and `kFlushRun`), so the stream order is exact.
- **When the record is not made** (any of step 1's reasons), `PublishSpots` turns each placeholder into a record of
  its own: the placeholder is rewritten into a step-1 marker [header]['SA2D'][seq], the same three words.
- **Concurrency:** a placeholder must never reach the ring unpublished.
  - From the call's first placeholder to the end of the call the drawing thread holds its producer's marking, so a
    submission from another thread waits (`WriteMmio`).
  - A submission the drawing thread makes itself inside the call publishes its placeholders first (`FlushOwnKick`) and
    does not wait for the marking it holds.
  - Each drawing thread has its own producer and marking here (sa2-nx has one of each).
- **Only where step 1 converts:** the main command buffer, outside predicated tiling. Direct3D runs nested command
  buffers many times and patches them after the call, and a converted placeholder is a one-shot record.
- **This game's step 1 needed one more thing:** its ring-side region check (banjo-nx's) rebuilds the region and
  compares. A placeholder in the region now matches the record's `kFlushSpot` op, and the `kFlushRun` ops after it are
  the flush's values.
- **Self-checks:**
  - The first 4,096 flushes, and every one in verify mode, run the original on a copy of the device: 32 KB in a
    SystemHeapAlloc scratch area whose +48/+52/+56 point at a scratch command buffer. What it wrote is decoded and
    compared word for word, together with the copy's first 64 bytes (the dirty masks). The real device is never
    touched.
  - Step 1's re-encode check treats a placeholder as its spot's ops.
  - A placeholder that reaches the ring is a DIFFERENCE.
- **Verify mode (PC, the console settings, track 2.3, `sasrt_237`):** 4.66 M constant, 3.84 M fetch and 8.64 M
  register-group flushes written as records (313 M words), 17.14 M of them checked against the original on the device
  copy, 0 differences. Every path ran: 1,534 slow paths and 198 "submitted first" calls left to the original, 11,875
  placeholders published alone (4,644 in the drawing thread's own submissions), 0 "no room", 0 placeholders at the
  ring. Step 1's checks on the same run: 3.85 M records checked at the draw and when applied, 0 differ, 0 lost.
  12.96 M flushes stayed with the original because their draw is not converted (outside the main command buffer).
- **Measured (PC, in-run A/B of this key alone, the rest on, `sasrt_238`, race of track 2.3, 60.5 s per phase, at the
  game's 30 fps cap):** whole-process CPU per Swap −1.6 % (88.4 -> 87.0 ms), ring time per draw −3.7 %, ring cycles
  per draw −1.2 %. The drawing thread's PM4 encode and decode are a small part of the PC's process; on sa2-nx's
  console they were 8-9 % of the game thread, which is what the console A/B
  (`sasrt_ab_keys = "sasrt_cpu_direct_flush"`) measures.
- **Report:** `[native] direct flush (sasrt_cpu_direct_flush, cumulative): ...` with the flushes written as records,
  those left to the original (slow path, no room, submitted first, outside), placeholders taken into the call's
  record or published alone (and in the thread's own submissions), checks, and placeholders that reached the ring.
- **Key:** `sasrt_cpu_direct_flush`. A/B: `configs/sasrt_test_direct_flush_off.toml`.

#### The native Direct3D layer: `sasrt_api_draws`, `sasrt_api_clears` and `sasrt_api_ring_zero_ahead` (sa2-nx's API-level renderer, 2026-10-07)

- **Why:** after steps 1 and 2 the drawing threads still run Direct3D's draw functions as recompiled guest code, which
  encode PM4 (or placeholders) that the ring decodes again. sa2-nx's API-level renderer is the next step of removing
  Direct3D, and later the PM4 transport and the EDRAM emulation: Direct3D's entry points become native code that
  writes the ring's record ops itself. Files: `src/me/sasrt_api.h`, `sasrt_api_internal.h` (made from sa2-nx's
  `sa2_api_internal.h`, its addresses remapped), `sasrt_api_draw.cpp`.
- **Which entry points (the census, `sasrt_diag_d3d_census`, PC race of track 2.3, `sasrt_258`, per second):**
  DrawIndexedVertices 44,118 calls (32.6 PM4 words each), the window scissor writer 12,052 (4 words), resolve 1,073
  (98 words), DrawVertices 604 (53), Clear 209 (157), DrawVerticesUP 119 (45). DrawIndexedVertices is 98.4 % of this
  game's draws; sa2-nx has not made it native (its game draws through DrawVertices and DrawVerticesUP), so this port
  transliterated it from the listing the same way.
- **Native now:**
  - `D3DDevice_DrawIndexedVertices` (`sub_82CD1DB8`) and `D3DDevice_DrawVertices` (`sub_82CD18D0`): Direct3D's
    draw-time state flush (FlushState: the three flush functions of step 2 and the shader load with its flags), then
    the draw packet. DrawIndexedVertices splits a draw of more than 65,535 indices into chunks with the primitive
    table's overlap, as the original does, one packet and one pairing record per chunk.
  - The window scissor writer (`sub_82CCB540`): registers 0x2080-0x2082, which SetViewport, SetScissorRect and the
    render target setters write straight into the command buffer (Direct3D keeps no shadow of them).
  - `D3DDevice_DrawVerticesUP` (`sub_82CD1168`) and `D3DDevice_BeginVertices` (`sub_82CD0BB8`, which only
    DrawVerticesUP calls here): the inline-vertex draw, its vertices in Direct3D's inline-data area as before
    (sa2-nx's code, its addresses remapped).
  - `D3DDevice_Clear` (`sub_82CE71B0`, key `sasrt_api_clears`; sa2-nx's `sa2_api_clear.cpp`): Direct3D clears with a
    draw of its own clear shaders (loaded inline) over a rect list whose vertices carry the color and depth, with the
    fast path that clears a color buffer bound as depth, and the tile-aligned interior through a 4x alias. The six
    functions of the chain are sa2-nx's instruction for instruction but for nine global addresses
    (`tools/listing_diff.py`), remapped in `sasrt_api_clear.cpp`; the fast path's packed value comes from the
    recompiled `sub_82CDAE90` (a pure function).
  - Verify mode runs the originals on the device copy; inside such a run Direct3D's inline-data allocator
    (`sub_82CDDF30`, a new hook, hence a codegen run: `tools/direct_calls.py` makes calls to unhooked functions
    direct) answers at once with a scratch block (`ShadowInlineAlloc`, sa2-nx's), instead of working on the copy's
    stale bookkeeping. The comparison maps the inline allocations onto each other in order.
- **Transport:** the ops go on the drawing thread's own ring of records (one per thread, as steps 1-2). Into the
  command buffer goes only a 3-word marker NOP [header]['SA2A'][seq], after Direct3D's own space check (the space
  function, which may submit); the ring applies the record when it reaches the marker. The record's `kPair` op gives
  the draw's pairing directly (no lookup by packet address).
- **Where:** the main command buffer outside predicated tiling, as steps 1-2. Nested command buffers stay on the old
  path (Direct3D patches them after the call): 247,667 calls on track 0.0.
- **Device flag 0x08 of +11071**, seen at the shader load, is handled natively at both of its sites (the first
  version fell back to the original for it); no device flag makes a call fall back now (the `[api]` line shows the
  flag bits a fallback met).
- **Self-check:** in verify mode every native call also runs the original on a copy of the device (a scratch area
  with its own command buffer). The copy's PM4 is decoded and compared word for word with the native ops, and the
  device bytes after the call with the real device's. Direct3D's space function, called by the native side and not
  by the copy (its command buffer is large enough), changes device bytes (+32): `MarkerSpace` snapshots the device
  around it in verify mode and the comparison leaves those bytes out (the original, run for real, would have made
  the same call at the same point). That artifact was the first run's only difference (`sasrt_259`).
- **Verify mode (PC, the console settings):** track 2.3 (`sasrt_263`): 933,649 native records, all compared with the
  original, 0 differences, no fallback. Track 0.0 (`sasrt_264`): 3,017,580 records (1,538,391 DrawIndexedVertices,
  1,461,678 window scissor; 35.1 op words each), 0 differences. With the guard's lock (below), track 0.0
  (`sasrt_265`): 1,945,768 records, and track 3.0 (`sasrt_266`): 975,196 records; 0 differences in both runs, in the
  layer and everywhere else. With Clear and the inline-vertex draws native, track 2.3 (`sasrt_267`): 2,720,738
  records (1,677,366 DrawIndexedVertices, 996,574 window scissor, 11,136 inline-vertex draws, 16,708 clears; 46.6 op
  words each), all compared, 0 differences, no fallback; 0 records released unreached or lost. Every draw of the main
  command buffer now goes through the native layer: steps 1 and 2 convert none ("0 draws converted").
- **Cost:** 0.43-0.51 us per native call on the PC (every 16th call timed), 0.5-1.0 % of one core.
- **Measured (PC, in-run A/B, `sasrt_261`, race of track 2.3, 60.5 s per phase):** process CPU per Swap −0.7 %
  (102.5 -> 101.8 ms), ring time per draw −1.7 %, ring cycles per draw −1.3 %; over all 110 switches (menus and
  loading too) process CPU per Swap +0.7 %. On the PC that is noise: its cores run the guest Direct3D code fast.
  With Clear and the inline-vertex draws (`sasrt_268`, both keys switched together): process CPU per Swap −1.0 %
  (98.5 -> 97.5 ms) in the race windows and −1.1 % over all 110 switches, ring cycles per draw −2.3 %, 29.4 Swaps a
  second in both phases. peggle2-nx's native Clear stops its submissions after about 20 s (open there); this game's
  ran its whole verify run (240 s) and every A/B phase without a stall.
  On sa2-nx's console the PM4 encode and decode of these calls was 8-9 % of the game thread, which is what the
  console's A/B measures (`configs/sasrt_test_api_off.toml`, or `sasrt_ab_keys = "sasrt_api_draws"`).
- **`sasrt_api_ring_zero_ahead`** (sa2-nx's round 11): a drawing thread's ring of records (8 MB) is larger than the
  A57's 2 MB L2, so every record line was a write miss, read from DRAM before the stores could complete. DC ZVA
  allocates zeroed lines in the cache without reading memory; free ring space up to 1,024 words ahead of the head is
  readied that way after each record. The consumer's tail is cached and read again only when the cached value says
  there is no room (sa2-nx's round 10: the line the ring thread keeps writing was a miss per record). Elsewhere a
  memset of the same blocks runs the same logic, so the PC's verify runs cover which words are zeroed; verify mode
  checks that every zeroed block lies past the head and inside the free space. A/B:
  `configs/sasrt_test_api_zero_ahead_off.toml`.
- **Next (sa2-nx's roadmap):** the resolve (sa2-nx's `sa2_api_resolve.cpp`, still off by default there: this port
  takes it once it is on), then the transport switch (records only, no marker NOPs) and the EDRAM emulation's
  removal.
- **Report:** `[api] native records (sasrt_api_draws, cumulative): ...` (records, op words, fallbacks and why, verify
  counts) and `[api] drawing-thread cost (10 s): ...`.
- **Keys:** `sasrt_api_draws`, `sasrt_api_clears`, `sasrt_api_ring_zero_ahead`. A/B: `configs/sasrt_test_api_off.toml`
  (the first two off). Census: `sasrt_diag_d3d_census` (a diagnostic, off).

#### Vertex bindings: `sasrt_cpu_vertices_base_zero_r0` and `sasrt_cpu_ring_bind_changed` (2026-10-07)

- **Why:** every `vkCmdBindVertexBuffers` binding is an NVK macro (`NVK_MME_BIND_VB`) of about a microsecond on the A57
  (sa2-nx's measure). In this game no draw took the base-zero binding (`masseffect_native_vertices_base_zero`), since
  every single-binding vertex shader reads r0. That left 0.67-0.92 bind calls per draw at 2,400-2,600 draws a frame
  in a race, and 60-75 % of the draws have two or more bindings.
- **`sasrt_cpu_vertices_base_zero_r0`** (sa2-nx's round 6): a draw whose vertex shader reads r0 takes the base-zero
  binding too: the upload buffer is bound once at 0 and the draw is shifted by firstVertex / vertexOffset, with the
  vertex index base (`g_VertexIndexBase`, shared[136]) set to vmin - first_vertex instead of vmin. The decision moved
  ahead of the shared block, where that base is written. It is not taken for Mass Effect's postponed sky (drawn again
  later with its own binding) or for a binding redirected to a memexport mirror.
- **Why exact:** XenosRecomp's r0 is `float(iVertexId + g_VertexIndexBase)`, in unsigned arithmetic, and `iVertexId`
  (SV_VertexID) is used nowhere else. DXC runs without `-fvk-support-nonzero-base-vertex`
  (`shaders/tools/compile_spirv_one.sh`), so SV_VertexID is SPIR-V's VertexIndex, which includes the draw's
  vertexOffset / firstVertex. A scan of the package's SPIR-V confirms it: 516 of the 558 vertex shaders read
  VertexIndex and none BaseVertex. So r0 is the same for every vertex (index + first_vertex - vmin + vmin -
  first_vertex), and the attribute addresses are the same bytes (`CheckBaseZero`: every draw in verify mode, otherwise
  the first 200,000 and then 1 in 4,096).
- **`sasrt_cpu_ring_bind_changed`:** a draw whose bindings differ from what is bound binds only the range from the
  first to the last binding whose offset changed. `recorded_bindings_` counts the leading bindings whose offsets are
  known; it drops to 0 on a new command buffer, a buffer change, the sky or external state, as before. The other
  bindings stay bound at the same offsets, so the GPU reads the same bytes. Verify mode checks after every bind that
  the tracked offsets are the draw's.
- **Verify mode (PC, track 2.3, `sasrt_241`), race windows:** 33-42 % of the draws on the base-zero path,
  0.45-0.46 bind calls per draw, 1.16-1.23 bindings bound per draw against 1.41-1.53 when all of a changed draw's
  bindings are bound; 0 differences.
- **Measured (PC, in-run A/B of both keys, `sasrt_242`, race of track 2.3, 60 s per phase):** vertex bindings bound
  per draw 1.51 -> 1.27 (−15.7 %); bind calls per draw 0.67-0.92 in the race windows before (`sasrt_238`), 0.45-0.46
  with the keys (`sasrt_241`). The PC's time is flat (ring cycles per
  draw +1.4 %, process CPU per Swap −0.4 %, within noise): AMD's driver binds cheaply, while NVK runs a macro per
  binding. The A/B lines now carry the bindings per draw of each phase (`ab_summary.py` prints them), so the console's
  in-run A/B (`sasrt_ab_keys = "sasrt_cpu_vertices_base_zero_r0;sasrt_cpu_ring_bind_changed"`) shows both counts and
  cycles.
- **What stays:** base-zero draws interleaved with several-binding draws still rebind binding 0. Several-binding
  draws (55-65 %) cannot share one shift: each binding's copy would have to start at the same vertex number, which
  the containment reuse rules out.
- **Keys:** `sasrt_cpu_vertices_base_zero_r0`, `sasrt_cpu_ring_bind_changed`. A/B: `configs/sasrt_test_vertex_binds_off.toml`
  (both off). Report: the `[native] C6 zero-base vertices` line.

#### The drawing threads' shader notes: `sasrt_cpu_note_shader_fast` and `sasrt_cpu_note_shader_pair` (2026-10-07)

- **Why:** `NoteShaderObject` runs four times per draw on the drawing threads (the shader-load hook `sub_82CE27D8` and
  `NoteDrawCall`, for the VS and the PS). Its startup diagnostic took a mutex on every call, also after its 32 lines
  were written, and the finished objects were looked up in a `thread_local` table: four lock/unlock pairs (atomic
  read-modify-writes on the A57) and four TLS lookups per draw, with two drawing threads sharing the lock. On
  sa2-nx's console this diagnostic alone was about 5.4 % of the main thread (2.4 % in the set's insert, 3 % in the
  lock); sa2-nx fixed it in its rounds 3 and 6, and this port had neither.
- **`sasrt_cpu_note_shader_fast`:** once the 32 traced objects are logged, the diagnostic no longer locks, and a key
  already in its set is remembered in a 64-slot lock-free table. Finished objects (seen and code-mapped, or seen and
  never identified: nothing is ever erased from those sets) sit in one 512-slot table shared by the game threads,
  with relaxed loads and stores and no read-modify-write. A hit returns exactly where the locked path would; a racing
  reader at worst misses and takes the locked path.
- **`sasrt_cpu_note_shader_pair`:** both hooks test the VS/PS pair against that table first (`ShaderObjectsFinished`,
  two loads) and skip both calls when both objects are finished.
- **Self-check:** in verify mode every pair hit is checked against the locked sets (seen, and code-mapped or never
  identified); a miss is a DIFFERENCE. The report line `[native] shader notes ...` counts the checks. The first
  verify run (`sasrt_243`, 9.26 M checks) flagged object 0 (no pixel shader bound): the zeroed table "finds" it.
  That is exact, because `NoteShaderObject` returns at its first line for a non-shader address, but the check now
  accepts such slots.
- **Measured (PC, in-run A/B of both keys, `sasrt_244`, race of track 2.3, 60 s per phase):** whole-process CPU per
  Swap −0.8 % at the 30 fps cap. Windows' uncontended locks are cheap; the console's are what sa2-nx measured.
- **Keys:** `sasrt_cpu_note_shader_fast`, `sasrt_cpu_note_shader_pair`. A/B: `configs/sasrt_test_note_shader_off.toml`
  (both off).

#### `sasrt_cpu_ring_bound_plan_memo` (sa2-nx's round 6)

`PlanEdramBoundRanges` (the EDRAM ranges a draw's render targets cover, and which same-base views are suppressed) is
a pure function of its request: pitch, sample count, used height, color mask, depth use and the five views' bases. A
draw whose request equals the previous draw's takes the previous plan (`SameBoundRequest`, field by field). Verify
mode computes the plan anyway and compares (`SameBoundPlan`); the count is in the `[native] EDRAM bound-plan memo`
line. Key: `sasrt_cpu_ring_bound_plan_memo`.

#### `sasrt_cpu_ring_identity_memo`: the pairing and identity checks once per change, not per draw (sa2-nx's round 6)

- **What:** a directly paired draw (the native Direct3D layer's `kPair`: every draw of the main command buffer)
  reuses the previous draw's pairing and final VS/PS choice when all of these equal that draw's: the two shader
  objects, the object table's version (bumped on every publish), the loaded VS and PS entries and their load
  generations, and the fast-pair, flat-identity and accept-fast switches. A pair the table rule refuses goes on to the
  replay and queue paths, so it is never memoised.
- **Why exact:** the pairing and identity functions read only those inputs (their audit counters and the one-time
  dump of a rewritten vertex shader aside); `EnsureTargets` still runs on every draw.
- **Self-check:** verify mode never uses the memo: every draw whose key equals the stored one must reach the stored
  outcome through the full checks (a DIFFERENCE otherwise; counted in the `[native] shader loads reused ...` line).
- **Key:** `sasrt_cpu_ring_identity_memo` (named `pair_memo_*` in the code: `identity_memo_` is the shader-load memo).

#### `masseffect_native_fingerprint_mode = 2` on the console (sa2-nx's round 6)

The index cache's fingerprint and the sampled fingerprints use the A57's hardware CRC32 pair
(`masseffect_crc_fingerprint.h`: CRC32C and CRC32 in two lanes, 2^-64 collision odds like XXH3) instead of XXH3's NEON
loop. In the PC profile the index cache was about half of the ring's XXH3 time in a race, and the texture recheck's
full fingerprint most of the rest. That full fingerprint (`raw_fingerprint`, base level then mips) now goes through
the same mode (`BlockFingerprint`); it is only ever compared with itself within a session. In mode 0 it is the same
value as before, since XXH3 seeded with 0 is plain XXH3. Builds without `+crc` (the PC) use mode 1, chained XXH3
blocks.

#### `sasrt_cpu_ring_edram_memo`: the EDRAM preparation of a draw like the previous one

sa2-nx's, unchanged (`PrepareDrawEDRAM4` is the same function in both ports): a draw whose 14 render-target registers
equal the previous draw's reuses that draw's EDRAM preparation when the full path would change nothing (same images,
tiles owned in the same epoch, nothing pending, the same stencil sources). The first 4,096 hits (every hit in verify
mode) run the full path too and compare. Verify mode (PC, track 2.3): 86-91 % of the draws from the memo, 9.0 M hits
checked, 0 differences. Key: `sasrt_cpu_ring_edram_memo`. In-run A/B of this key alone with the rest of the round on
(`sasrt_229`, race of track 2.3, 61 s per phase): ring cycles per draw −2.3 %, ring time per draw −2.9 %,
whole-process CPU per Swap −2.3 %.

#### `sasrt_cpu_ring_compare_uploaded` and the cached upload buffer

sa2-nx's: the constants dedupe and the shared block's change test compare with the block already uploaded instead of
a second CPU-side copy of every upload. It needs the upload buffer in CPU-cached memory, sa2-nx's round-3
`masseffect_native_upload_memory = 1` (now a CPU-group key on in `app/sasrt_switch.toml`; sa2-nx's console wrote 5,251
MB/s there against 2,506 in the uncached type the SDK picks). Verify mode keeps the copies and compares them with the
uploaded blocks. Key: `sasrt_cpu_ring_compare_uploaded`.

Switching it during a run (the in-run A/B) needs care: while it is on the CPU-side copies are not kept, so after a
switch to off they would be stale. A draw that sees the key changed makes every block upload afresh once (the
constants' and the shared block's epochs reset). The first in-run A/B ran without that (`sasrt_217`): its menus and
race slowed to 2-4 frames per second.

#### Where the ring's time goes in this game, and `sasrt_cpu_vertex_containment`

Two sampled stopwatches (1 draw in 64) split the ring's work per draw: `[native] ring per draw` (pairing, the draw's
preparation, `targets_->Draw`, and the rest: parsing and the other packets), `[native] targets per draw` (EDRAM
preparation, the draw's recording in DrawsVulkan, EDRAM publish) and `[native] draw recording per timed draw` (the
DrawsVulkan stage stopwatch, which was collected but never printed). PC race, the console settings (`sasrt_197.log`):

| Part | µs per draw |
|---|---|
| the ring's work (ring timer) | 16.6-18.7 |
| parsing and the other packets | 1.4 |
| pairing | 0.4 |
| EDRAM preparation | 1.7-2.5 |
| the draw's recording (DrawsVulkan) | 12.6-13.5 |
| ... of which vertex copies | 8.7-9.7 |
| ... of which the pipeline and the draw call | 1.9-2.4 |

So in this game PM4 parsing is a small part on the PC and the ring's biggest cost is copying vertices: a race reads
33-36 GB of vertex data per 10 s (about 130 MB a frame), byte-swapped into the upload buffer. The draws read different
[vmin, vmax] windows of the same big vertex buffers, and the same-frame dedupe only reuses a range with the same start
and size (about 16 % of the bytes). Measured with `sasrt_diag_vertex_union` (a diagnostic key): per upload buffer only
8-10 % of the bytes are new, and 66-75 % lie inside one earlier copy of the same buffer.

- **What:** a draw's vertex window inside a larger window of the same vertex buffer and byte order already copied in
  this upload buffer binds that copy at an offset instead of copying again (`ContainVertices`,
  `masseffect_native_vertices_dedupe.h`; up to 8 copies kept per buffer).
- **Why exact:** the dedupe's own rules. The bytes were read by an earlier draw of the same upload buffer, so the game
  cannot rewrite them before it synchronizes with the GPU (a guest wait clears the table, as it clears the dedupe),
  and the upload buffer keeps the copy until it is replaced. Only the large ranges the dedupe already matches by
  address (`masseffect_native_dedupe_max_fingerprint`, 16 KB); the small, possibly transient ones keep their
  fingerprint check.
- **Not done, and why:** a cache across frames. Nearly all the vertex data is the same from frame to frame (the
  diagnostic `masseffect_native_diag_vertices_repeated`: 84 % equal to an earlier frame), but this game never locks a
  vertex buffer (0 `D3DVertexBuffer_Lock` calls in a whole session: it writes vertex memory directly), so nothing tells
  the renderer when a buffer changes; only hashing every range every frame (memory-bound, as costly as the copy on the
  console) or page-protection write tracking would make it exact.
- **Self-check:** the first 4,096 reuses (every reuse in verify mode) compare the guest bytes with the reused copy, word
  for word (DIFFERENCE: off for the session).
- **Numbers (PC race):** 16-17 GB of the ~28 GB a 10 s window used to copy are now reused (32,000-34,000 windows), 7.6-8.1
  GB copied: about 73 % fewer vertex bytes copied. Verify mode (`sasrt_206.log`): 581,059 reuses checked, 0
  differences. The PC's wall-clock timers are too noisy (four other ports share it) to show the time; the console's
  copies are bound by memory bandwidth, so the bytes are the measure.
- **Key:** `sasrt_cpu_vertex_containment`. A/B: `configs/sasrt_test_vertex_containment_off.toml`.
- **Measured in the ring thread's own CPU cycles** (futari-nx's method: `QueryThreadCycleTime`, in the ring timer line,
  steady on a loaded PC where wall time is not; `tools/win/key_ab.ps1 -SwitchConfig`): at the same draw counts the ring
  went from 59.7-68.2 to 48.3-50.0 kcycles per draw (about 2,100-2,250 draws per Swap) and from 51.6-52.7 to 32.2-32.3
  (about 3,500): 20-38 % less ring CPU per draw, 0.13-0.18 -> 0.10-0.12 Gcycles per Swap; in some windows the ring now
  waits for the game.
- **Measured again with the reuse epoch fixed** (in-run A/B of containment and merge together, the rest of the round
  on; `sasrt_230`, race of track 2.3, 61 s per phase): ring cycles per draw −24.3 %, ring time per draw −33.5 %,
  whole-process CPU per Swap −15.2 %, Swaps per second +22.8 %. Most of the round's effect is here.
- **`sasrt_cpu_vertex_merge`** (on top): a window that overlaps or touches earlier copies of its buffer copies their
  contiguous union (`ContainVertices::Hull`, at most 4 MB) instead of itself, so later windows inside the union reuse
  it. Exact for the same reason (every byte of the union was read by a draw of this upload buffer; no gap can enter).
  The copied share of the vertex bytes went from about 28 % to about 24 %; verify mode (`sasrt_209.log`): 778,413
  reuses checked, 0 differences.
- **Report:** `[native] vertex containment ..., 10 s: N windows reused, X MB not copied; Y MB reused by the same-range
  dedupe; Z MB copied; checks`.
- **The same-range dedupe is checked too (2026-10-07):** containment is exact under the dedupe's rules, and those
  rules were masseffect-nx's, never checked in this game. The dedupe matches ranges over
  `masseffect_native_dedupe_max_fingerprint` (16 KB) by address, size and byte order only. Smaller ones it matches by
  `SampleFingerprint`, which with 4 KB blocks and every 8th block sampled hashes only the first and last block of a
  16 KB range. Its reuses now go through the same `CheckContained` against guest memory: the first 4,096 per
  session, every one in verify mode. A difference turns the dedupe off for the session and counts in `[verify]`. The
  count is in the containment line ("same-range dedupe reuses checked: N").
- **`sasrt_cpu_vertex_no_fingerprint`** (2026-10-07, on): the dedupe matches every window by address, size and byte
  order within a synchronization epoch, as it already did for windows over 16 KB. Before, it hashed each window of
  16 KB or less (`SampleFingerprint`) before knowing whether an earlier copy existed: 5.7 % of the ring thread's
  samples in a PC race profile were `XXH3_hashLong`, and masseffect-nx measured the full hash at ~18 % of its console
  ring thread. Exact by the dedupe's own rule: the game cannot rewrite a range it already drew without synchronizing
  with the GPU, and the table is cleared at every synchronization the ring serves. The containment and the large
  windows rely on the same rule, and no "stale vertex reuse prevented" line appeared in any run of this game. Checked
  by the dedupe's new `CheckContained` (verify mode: every reuse). Switching it during a run is safe: an entry made
  without a hash and searched with one counts as a miss. A/B: `configs/sasrt_test_vertex_no_fingerprint_off.toml`.
  The rule holds only with real synchronization epochs: see "The reuse epoch and the command-buffer pages" below,
  fixed the same night. Verify mode (tracks 2.3 and 1.1, before that fix): 5.74 M reuses compared with guest
  memory, 0 differences; after it (tracks 0.0 and 2.3), 0 differences again. PC in-run A/B (`sasrt_222`, race): ring
  cycles per draw −1.4 %, ring time per draw −3.0 %, process CPU per Swap −2.4 %. XXH3 has AVX2 on the PC; on the
  console the hash costs relatively more.
- **Diagnostic `sasrt_diag_vertex_static`:** of the bytes still copied, the share read from 4 KB guest pages unchanged
  since a copy last read them (an XXH3 per page, once per frame). That share is what a cross-frame cache could skip if
  it knew which pages the game wrote. Without such knowledge it cannot: the game never calls `D3DVertexBuffer_Lock`,
  and on the Switch a write-watched page is unmapped, so reads fault as well. Measured (`sasrt_223`, track 2.3,
  2026-10-07): in the menus 98-100 % of the copied bytes came from unchanged pages, and in the race 100 %
  (13,581 of 13,619 MB in 10 s). About 6-27 of the 700-2,200 pages read per frame changed. A cache across frames
  with exact write tracking would remove nearly all vertex copying: the biggest single item left on the ring.

#### Lockstep captures: not possible for this game

sa2-nx proves pixel identity with lockstep captures (the same scripted session twice, frames compared by hash). Here two
runs with identical settings already differ: with `vblank_per_swap` (and the SDK's new `vblank_per_swap_count = 2` for
this 30 fps game) the races diverge from the start (other positions), even with frame-timed input
(`tools/win/lockstep_runs.ps1 -InputScript`, frame holds `+<n>f` in `sasrt_input_script`) and with the SDK's new
`clock_per_vblank` (the guest clock advances exactly 1/60 s per vblank: then the races stay close, the same place and
position, but not identical: items and AI still differ). Menus too: 10 of 1,200 frames identical between two baseline
runs (and the same 10 against the all-on run). So the proof of this round is verify mode: every changed path is
checked against the original at every use (records re-encoded at the draw and checked against their region when
applied, every EDRAM memo hit against the full path, every reused vertex window against guest memory, every uploaded
block against its copy): 0 differences.

#### Deferred Vulkan recording: still explicit-only

sa2-nx turned it on in its round 5. Its PC slowdowns here (a third slower) and in futari-nx were Windows' sleep
granularity in its queue waits, now fixed (`ShortPause`, PC only). But futari-nx's lockstep captures (2026-10-07) found a
menu fade that differs with it, by up to 65 levels on 4 frames and differently in each run, so it stays off:
`configs/sasrt_test_deferred_on.toml` is the console A/B.

#### The ring's own timer

`[native] ring thread: X ms of work per Swap (Y µs per draw, N draws per Swap), Z ms per Swap waiting for the game
(WAIT_REG_MEM)` every 10 s: the ring's parse loop less its waits for the game. It includes the waits for the host GPU,
so on a loaded PC it moves with the other work; compare runs back to back.

#### In-run A/B (`sasrt_ab_keys`, `sasrt_ab_period_ms`; futari-nx's method)

Back-to-back runs are not comparable on this PC while other ports build: the first whole-round A/B (2026-10-07,
`sasrt_212`/`sasrt_213`) ran its "on" half while nine compiler processes held all 16 hardware threads. The components
the keys do not touch (pipeline and draw, framing, textures) came out 1.5 times slower than in the "off" half, and the
game threads used 20-30 % more CPU at the same frame rate. Thread cycle counts inflate as well, because a busy SMT
sibling slows the thread down while its cycles still count.

So one run measures both sides. `sasrt_ab_keys` names port keys (`SASRT_ENHANCEMENT`, `;`-separated, on at start). The
GPU ring thread switches them off and on together every `sasrt_ab_period_ms` (2000) at a Swap, so a load spike from
other work weighs on both phases alike. Switching is exact at any Swap: each fast path decides per use and falls back
to the plain path when off. The EDRAM memo invalidates itself when off, containment is per frame, and a draw whose
`BeginDrawDirect` saw the key off is not converted.

Each phase adds up its Swaps, wall time, the ring's work and its own cycles, draws, and the whole process's CPU time
(`GetProcessTimes`, all threads: the game threads too). Every 10 s the log has two lines:
- `[ab] window ...`: the raw sums for the last 10 s, plus per-Swap and per-draw figures with on against off.
- `[ab] cumulative (...)`: the same over the whole run.

`tools/ab_summary.py <log> --from-window N` adds up the chosen windows, so the race can be taken without the boot,
menus and loading screens. `tools\win\key_ab.ps1 -InRun -Key 'k1;k2'` does the run and the summary (windows 11 on).
On the Switch the ring thread's own CPU comes from Horizon's thread ticks (`me_switch_cycles.cpp`,
`InfoType_ThreadTickCount`), scaled to A57 cycles at 1,020 MHz; the process CPU reads 0 there.
`configs/sasrt_test_ab_round.toml` runs the round's A/B on the console.

### The CPU round of 2026-10-12: flush-mode switches, lock words, per-thread counters

The user's request: fifteen CPU optimisations, as many as possible usable by every ReXGlue port, tested on the PC and
judged for the Switch's A57. Thirteen changes came out of it, eleven of them in the generator, the post-codegen
tools, the SDK or the build (any port can take them as they are); two are in this port's renderer copy. Two more
candidates were measured and dropped (at the end). Everything here is in the one NRO;
`configs/sasrt_test_cpu_round12_off.toml` turns the run-time keys off.

#### How the candidates were found: three censuses

A PC profile does not show what costs on the A57 and not on x86, so three counts were added.

- **Static, on the Switch ELF** (`tools/arm_cost_census.py out/nx/sasrt`, `tools/arm_func_ops.py`): per function, the
  instructions an x86 profile hides: `msr fpcr` (28,881 sites), exclusive load/store pairs (10,670) and the `dmb`
  after them (10,188), calls of `__aarch64_read_tp` (one per `thread_local` access with `-mtp=soft`: 416), integer
  divides, frame set-ups (54,224 recompiled functions).
- **Run-time calls of the SDK, on the PC** (`sasrt_diag_runtime_census`; `rex/sys_counters.h`, `REX_SYS_CENSUS`: counted
  off the Switch only). Per second in a race (`sasrt_277.log`): 85,000 critical sections entered (500-700 fell into
  a host wait), 31,000 handle lookups under the global lock (70 found it taken), 12,400 events set and 6,650
  semaphores released, 8,900 waits, 2,900 guest clock reads, 1,000 timestamp ticks.
- **Flush-mode switches by code address, on the PC** (the same key; `CensusSite` counts the return address of every
  real mode write, `tools/census_sites.py <log>` turns the log's `[census] flush-mode switch sites` line into
  functions, generated source lines and PowerPC instructions with llvm-symbolizer). This was the find of the round:
  **1.4 to 2.1 million switches a second** in a race (`sasrt_278.log`), each one an `msr fpcr` on the console, which
  the A57 serializes (sa2-nx's console profile had 20-26 % of a VMX-heavy thread's samples right after one). They
  came from three shapes: a float load or `frsp` at the top of a function called from vector code (the function
  switched off there and on again at its first vector instruction, on every call), one or two scalar single
  operations between vector instructions in a loop (four switches per iteration in `sub_8275E3D0` and
  `sub_8274F568`), and long scalar runs between vector code (two per run, which stay).

`tools/one_file_ab.py` (one recompiled file compiled with the Switch build's own flags in several variants,
instructions / loads / stores counted, 15 s a variant) decided the compiler questions without a full build.

#### 1-3. The generator: `fp_compares_modeless` and `fp_mode_lookahead` (new options of this SDK's code generator)

sa2-nx's `fp_moves_modeless` made float moves switch nothing and gave `lfs` / `stfs` any-mode conversions while VMX
mode was current. The same idea, further:

- **`fp_compares_modeless`** (1): `fcfid` (integer to double), `fctiwz` / `fctidz` (truncation: a denormal gives 0 in
  either mode) and `fsel` (its `>= 0.0` test done on the bits, `GeZeroAnyMode`) cannot be changed by the mode: no
  switch, no check, in any state. `fcmpu` / `fcmpo` get `CompareAnyMode` (a compare writes no float result, so the
  mode can only act through a denormal operand: those compare in a cold helper with the mode cleared) and `frsp`
  gets `RoundToSingleAnyMode` (sa2-nx's two conversions composed).
- **`fp_mode_lookahead`, conversions** (2): before a scalar float instruction switches, the generator looks at the
  next instruction that needs a particular mode (`BuilderContext::next_float_demand`: in address order within the
  block, up to 24 instructions or the next branch). An `lfs` / `stfs` / `frsp` / `fcmpu` takes its any-mode form
  whenever the mode is not known to be FPU and a vector instruction comes next, or nothing comes before the next
  branch and the function contains vector float code at all. It keeps the plain form behind the usual check when
  scalar arithmetic follows (the check is needed anyway) and in functions without vector float code (one check per
  function is cheaper than a test per conversion: such functions are generated exactly as before).
- **`fp_mode_lookahead`, arithmetic** (3): one or two `fadds` / `fsubs` / `fmuls` / `fdivs` in front of vector code
  compute in whatever mode is current (`rex::ppc::AddSingleAnyMode` and friends, `rex/ppc/diet_ops.h`). The mode can
  change `double(float(a op b))` in three places, each ruled out or sent to the cold helper (the plain expression
  with the mode cleared): a denormal double operand (tested first); a tiny double result, which the mode turns into
  a zero (AArch64 flushes on tininess before rounding, x86 on a tiny inexact result), so a result that is not zero
  was not flushed, and a zero is accepted only where it is exact (x + (-x), x - x, a zero factor, a zero dividend);
  and the rounding to single, through `RoundToSingleAnyMode`. Three or more operations in a row switch once, as
  before. The fused forms (`fmadds` ...) are left out: `std::fma` is a library routine on x86 without FMA3, whose
  inner steps the mode could disturb, so the PC could not check them.

- **Why exact:** each helper returns, in either mode, the bits the plain expression gives with the mode off.
  `sdk/tests/fp_any_mode_test.cpp` checks that: 4,096 pairs of edge values (zeros, the denormal range's ends,
  DBL_MIN, the single denormal range and FLT_MIN as doubles, rounding ties, the integer limits, FLT_MAX, infinities,
  quiet and signalling NaNs) and 30 million random pairs with the exponents and mantissas drawn from those edges and
  near-equal partners for cancellation: **600 million comparisons, 0 differences**, and the mode left as found. Its
  negative control (the plain operations in the helpers' place) reports 448,806 differences in 2 million pairs, so
  the inputs do reach the cases where the mode matters (1.46 million of the 30 million pairs for add and sub, 0.7
  million for mul and div). The PC tests x86's flush rules; the AArch64 difference (tininess before rounding) is
  covered by the argument above (any flushed result is a zero), not by a run.
- **Static result** (the generated code): sites that always switch 2,268 -> 464; conditional checks 27,234 ->
  24,317, of which 9,811 are proven away (below).
- **Dynamic result on the PC** (the same scripted race): see the table under "Results".
- **Keys:** build-time (`app/perf_overrides.toml`); the generator's defaults are off, so other ports opt in.

#### 4-5. `tools/flush_mode_flow.py`: the checks the control flow fixes (post-codegen)

What is left of the mode calls are conditional checks (`ctx.fpscr.disableFlushMode()`: a load of the cached mode word,
a test and a branch; guest stores may alias the context for all the compiler knows, so each is really compiled).

- **Within a function** (4): a forward must-dataflow over the function's statements (labels, `goto`, `if (...) goto`,
  returns): the mode is on / off / unknown, unknown at the entry, after anything that hands `ctx` to other code,
  after any other mention of `fpscr`, and around every structured statement (blocks, `switch`, `for`): what the
  generator writes besides labels and gotos is not followed, only fenced off. A check that asks for the mode every
  path already has is proven.
- **Across calls** (5): a summary per recompiled function. "Keeps": no flush-mode statement and nothing but direct
  calls of functions that keep it (the largest such set: 64,736 functions). "Returns on / off / as entered": every
  return of a function with flush-mode statements is reached in that mode (4,235 functions; computed from "unknown"
  to a fixed point, so recursion stays unknown). Only `__imp__sub_X(ctx, base)` calls count, which
  `tools/direct_calls.py` writes only for functions no hook replaces.
- **Result:** 9,811 of 24,317 checks proven (8,921 of 27,234 before the generator change, without the summaries). A
  proven check becomes `REX_FLUSH_KNOWN_ON()` / `REX_FLUSH_KNOWN_OFF()`.
- **Self-check:** on the Switch the macros are nothing. In the PC build each keeps its test and calls
  `RexFlushFlowMismatch` (a `[enh] DIFFERENCE: flush-mode flow` line, counted every 10 s) before switching after all:
  every PC run checks every proof it executes, at the old cost. `SASRT_SWITCH_FLUSH_FLOW=OFF` (`REX_FLUSH_FLOW_OFF`)
  compiles the original checks on the Switch.

#### 6-7. Compare-and-swap without the legacy barrier: `sasrt_cpu_guest_cas_no_barrier`

- **What:** the generator writes `stwcx.` / `stdcx.` as `__sync_bool_compare_and_swap`, and the SDK's POSIX atomics
  (`rex::thread::atomic_inc` / `_dec` / `_cas` / `_exchange_add`: every critical-section enter and leave, the kernel
  spin locks, the interlocked lists) used the `__sync` builtins too. On AArch64 without LSE, GCC ends each of those
  with **`dmb ish`** after the exclusive loop, because the legacy builtins promise a full barrier (GCC PR 65697).
  (6) `tools/guest_cas.py` rewrites the 8,264 generated sites into `REX_GUEST_CAS`, defined in the generated pch as
  `__atomic_compare_exchange_n` with sequentially consistent ordering: the same loop with acquire/release
  exclusives and no trailing barrier. (7) `sdk/src/core/atomic_posix.cpp` does the same with the `__atomic` builtins
  (about 170,000 calls a second from the critical sections alone).
- **Why exact:** on PowerPC `lwarx` / `stwcx.` order nothing; where the game needs ordering it has its own
  `lwsync` / `sync` / `eieio` (402 / 27 / 42 in this game, none next to a `stwcx.`), which the generator translates
  separately into fences. Acquire/release exclusives are still stronger than what the 360 code had. The SDK's uses
  are lock words and counters, whose every access is one of these atomics.
- **Self-check:** none is possible on the PC (both forms are `lock cmpxchg` there; the PC build runs the rewritten
  expression). The key off sets `g_rex_atomic_legacy_barrier`, which puts the `dmb ish` back after every one of
  them at run time: the console A/B. `REX_GUEST_CAS_LEGACY` is the build-time off switch.

#### 8. No frame pointer in the game code: `SASRT_SWITCH_OMIT_FRAME_POINTER` (Switch build option)

AArch64 GCC keeps the x29 frame chain in every non-leaf function unless told otherwise; 54,224 recompiled functions
set it up. `-fomit-frame-pointer` on the game code only: -1.4 % instructions, -1.8 % loads and -1.7 % stores in a
recompiled file (same flags otherwise), and x29 becomes one more callee-saved register for code that is short of
them. The SDK and the app keep theirs. Cost: the console profiler's pc samples are unaffected, but its caller chains
(it walks x29, bounds-checked against the thread's stack) end where they reach a game function.

#### 9. `thread_signal_skip_idle` (SDK, POSIX/Switch)

- **What:** setting an event or releasing a semaphore called `notify_all` every time; on Horizon that is always a
  syscall (`svcSignalProcessWideKey`), also with nobody waiting. The waiters of each condition are now counted under
  its own mutex around the wait, the signaller reads the count together with its state change, and without a waiter
  the notify is skipped. About 19,000 signals a second in a race here (the game's job system).
- **Why exact:** a waiter is counted before `wait` releases the mutex, so a signaller that changes the state under
  the same mutex sees every thread its notify could wake; a thread that arrives later finds the state changed and
  does not block. Mutants, timers and thread handles notify as before.
- **Self-check:** `sdk/tests/signal_skip_idle_test.cpp` runs the protocol on the PC (the file itself is Switch-only):
  auto-reset ping-pong, a semaphore between 2 producers and 3 consumers, manual-reset broadcasts; a lost wake-up
  leaves a thread blocked and fails the run. 8 s while the PC was building: 19.7 million signals notified, 3.3
  million skipped, no lost wake-up. On the console the profiler's "system per second" line counts the skipped
  signals.

#### 10. `sasrt_cpu_hook_counter_ctx`: the hot-native hooks' call counters in the thread's own context

About 700,000 hooked calls a second reach the native replacements (memcpy and the localized leaf copies), from the
game's main, render and job threads alike. Each loaded and stored one counter per hook shared by all threads
(`sasrt_cpu_hook_counter_shared`, which had replaced a `thread_local`): a store into a cache line every calling
thread pulls to its core. `PPCContext` now ends with 64 host counters (`host_counters`, a new SDK field: not guest
state, zero in a new thread's context), and each hook counts in its slot of the context it is handed anyway: the
per-thread counter the guard was designed with, without the TLS call and without the shared store. The counter only
decides which calls the guard checks.

#### 11. `sasrt_api_thread_stats`: the native Direct3D layer's statistics per drawing thread

Two threads draw in this game, and each native call loaded and stored six shared words (records, op words, the call
type, the timer's tick and call count, the key's use counter). They are now fields of the thread's own data, added
to the shared totals every 64 records; the timer's tick is a slot of the context's host counters and a timed call
stands for the 16 of its period. The `[api]` lines read the totals as before (at most 63 records behind per thread).

#### 12. `sasrt_cpu_index_no_fingerprint`: the index cache without a hash per draw

- **What:** the ring's index cache (16-bit indices converted and uploaded once per frame and synchronization epoch)
  hashed every range up to 16 KB on every indexed draw, before it knew whether the range was cached, and matched
  larger ranges by address and count alone. Now every range is matched that way.
- **Why exact:** the rule the vertex dedupe already relies on (`sasrt_cpu_vertex_no_fingerprint`): the cache's
  generation changes at every synchronization the ring serves, and ranges on command-buffer pages are never cached.
- **Self-check:** verify mode still hashes, keeps the hash of the bytes each entry was made from and compares it on
  every hit (`[native] ME index cache: ... hits checked by hash (verify mode), N differences`).

#### 13. `sasrt_cpu_ring_draw_trims`

The index-layout diagnostic (banjo-nx's) inserted into a hash set on every indexed draw (a hash, a divide by the
bucket count and a bucket walk on the A57) to learn whether the layout was new. There are 16 layouts: one bit each.

#### Results

Flush-mode switches in the same scripted race (track 2.3, PC, the console's settings, the last 60 s of each run, all
at the 30 Swaps a second cap; the game is not deterministic, so the scenes differ a little: per draw is the fairer
figure):

| build | log | switches / s | per Swap | per draw |
|---|---|---|---|---|
| before the generator changes | `sasrt_278` | 1,826,000 | 60,800 | 28.9 |
| `fp_compares_modeless` | `sasrt_279` | 1,618,000 | 53,800 | 27.7 |
| + `fp_mode_lookahead`, any-mode conversions in every function (not shipped) | `sasrt_280` | 773,000 | 25,800 | 11.9 |
| + `fp_mode_lookahead` as shipped | `sasrt_281` | 958,000 | 31,900 | 12.5 |

So about half of the mode writes per frame are gone (-48 % per Swap, -57 % per draw). What is left is real
alternation: scalar runs of three or more operations between vector code (`tools/census_sites.py` on `sasrt_281`:
`sub_8275E3D0`'s four `fmuls` per iteration, the localized copies `n_8279A888` and `n_827C56C8`, `sub_8275EDE0`).
Whether those are cheaper as any-mode operations too depends on what an `msr fpcr` costs on the A57 against about
twenty extra instructions per operation; that needs a console measurement, and the threshold (two operations) is
one constant in `next_float_demand`.

Static, in the generated code: 2,268 -> 464 sites that always switch; 27,234 -> 14,506 flush-mode checks compiled on
the Switch (24,317 left by the generator, 9,811 of them proven); 8,264 compare-and-swap sites without the trailing
barrier; 832 any-mode arithmetic, 7,595 `lfs`, 5,141 `stfs`, 2,346 compare and 566 `frsp` any-mode sites.

Checks on the PC build of 2026-10-12 (the final one):
- Verify mode on tracks 2.3, 0.0 and 3.0 (`sasrt_282` / `283` / `284`, 240 s each): `differences: 0` on all three;
  the native Direct3D layer compared 3.37 / 3.41 / 3.41 million records with the original, 0 differences; the index
  cache's hits were checked by hash 481,597 / 481,382 / 483,161 times, 0 differences; no `DIFFERENCE` line; the only
  error line is the third-party Vulkan layer's that every run has.
- Every run of the PC build tests the flush-mode proofs it executes (`RexFlushFlowMismatch`): 0 mismatches in the
  four census races and the three verify runs.
- `sdk/tests/fp_any_mode_test.cpp`: 600 million comparisons, 0 differences; negative control positive.
- `sdk/tests/signal_skip_idle_test.cpp`: no lost wake-up.

Not measurable on the PC, so for the console to say: the `dmb` removal (both forms are `lock cmpxchg` on x86), the
skipped wake syscalls (the PC does not build that file), the frame pointer (a Switch compile flag) and the cost of
the mode writes themselves. `configs/sasrt_test_cpu_round12_off.toml` against the default gives the run-time keys'
share; the "system per second" line counts the skipped signals.

For the other ports: the generator options (`sdk/src/codegen`, `rex/ppc/diet_ops.h`, `rex/codegen/config.h`), the two
post-codegen tools, `atomic_posix.cpp`, the waiter count in `threading_posix.cpp`, `PPCContext::host_counters`, the
census (`rex/sys_counters.h`, `clock.cpp`) with `tools/census_sites.py`, and the two tests are not specific to this
game. A port should run the census first: how many switches a second it has decides how much the generator work is
worth there.

#### Measured and dropped

- **A loop barrier that fences only guest memory** (`asm("" : "+r"(base))` instead of the full memory clobber, so
  loops would not store and reload the context registers): the one-file build got larger (33,032 against 32,538
  instructions, loads and stores up too). No.
- **`NoteShaderObject`'s remaining locked path** (shader objects whose microcode is in `.data`): 1,900-5,400 lock
  acquisitions a second: not worth a new exactness argument.
- **A critical-section fast path**: the enter and leave wrappers are 15 instructions each already; only the barrier
  (above) was worth removing.
- **`fp_mode_lookahead` with any-mode conversions in every function** (the first version): 0.74-0.81 million
  switches a second, but 28,630 `lfs` and 23,081 `stfs` sites carried the denormal test where most had been plain.
  The shipped rule keeps functions without vector float code as they were.

### The CPU rounds of 2026-10-13: sa2-nx's rounds 2 and 3 ported, this port's second round, three corrections

After the round above the other ports took it over, and sa2-nx built two more rounds on it and released them
(sa2-nx 1.0.1; the user's console estimate there: about 15 % better than 1.0.0, one build with all rounds, a new PGO
profile and a higher inline limit, so the parts are not separated). The user asked for all of it here, without new
link-time or PGO work (that is for the release build). This section is what changed in sasrt-nx on 2026-10-13. The
reference for every ported item is `D:\sonic adventure 2\sa2-nx\docs\cpu-rounds.md`.

Nothing here has run on a console; see "Results and checks" at the end.

#### Three corrections of what was shipped before

- **`fp_mode_lookahead` no longer bets** (`fp_mode_lookahead_past_branch = false`, sa2-nx's option). The rule of
  2026-10-12 also gave conversions and compares their any-mode form when nothing that needs a mode followed before
  the next branch. Nobody had counted how often those forms RUN. sa2-nx added counters to the helpers
  (`REX_DIET_CENSUS_ON`, PC builds of the game code only), and in SA2 the bet cost 93,656 tests a frame for 9
  switches. Measured here, same scripted race, per Swap:

  | rule | flush-mode switches | any-mode operations executed |
  |---|---|---|
  | before the generator work (`sasrt_278`) | 60,800 | not counted |
  | with the bet (`sasrt_287`) | 28,800 | 259,200 (217,400 conversions, 32,600 compares, 9,200 arithmetic) |
  | certain only (`sasrt_288`, shipped now) | 43,600 | 44,800 (32,500 / 5,100 / 7,200) |

  The certain forms save 17,200 switches a frame for 44,800 operations: 2.6 operations per switch. The bet saves
  14,700 more for 214,400 more operations, about 64 extra instructions per switch saved: close to what one `msr fpcr`
  may cost on the A57, so no clear gain and a clear cost in code size. It is off until the console says what a
  switch costs (the profiler's report header now measures it, "FPCR on this CPU", sa2-nx's addition); the option
  stays for that A/B. The "mode-free functions" rule of this port's second round went the same way (it is part of
  the bet). The race is not deterministic: switches per frame vary by about 15 % from run to run, so the table's
  ratios are good to that.
- **`-fno-trapping-math` is off** (`SASRT_GAME_NO_TRAPPING_MATH`, was on since 2026-10-07). It lets the compiler
  run a float operation earlier than the code does, and the compiler does not know that the operation depends on
  the flush mode the code switches in between. No wrong result was ever seen; sa2-nx's audit found the hole and
  measured at most 0.5 % of one file for the flag. `-fno-math-errno` stays, and the app is now compiled with it too:
  GCC does not inline between two float-using functions that differ in it, and the app holds the localized copies.
- **`fctid` / `fctiw` round halves to even on the Switch** (`fcti_inline`, sa2-nx's generator option). simde's
  conversion off x86 is C `round()`: exact halves went AWAY from zero on the console, unlike the 360 and the PC
  build. 12 instructions here (18 `fcvtas` in 13 functions of the 2026-10-12 ELF). The helper is `frinti` and a
  saturating `fcvtzs`; `fctidz` becomes the instruction as well.

One more thing found on the way: **three localized copies had never run.** `tools/direct_calls.py` took only
`82xxxxxx` addresses for hooks, and this game's code runs to `0x8302BFD3`: the callers of `sub_830260A0`,
`sub_83027D38` and `sub_830291B8` called the originals directly (0 uses in every log). The pattern is `8[23]xxxxxx`
now; in a race `sub_830291B8` runs 17,000-51,000 times a second and `sub_83027D38` 42,000.

#### This port's second round (2026-10-12, paused; kept)

- **`tools/vec_byteswap.py`:** the 16-byte reversal of every guest vector load and store (40,154 sites) was
  `pshufb` with a mask from a writable table: on AArch64 an AND with 0x8F and a TBL, the mask loaded each time. As
  `vextq_u8(vrev64q_u8(v))` the compiler knows the permutation: it folds it to one TBL with a literal mask, without
  the AND, and merges it with neighbouring reversals and constant shuffles (one file: -1.7 % instructions, -2.4 %
  loads). The 4,129 unaligned forms keep their table lookup, without the AND (`REX_SHUFFLE_TABLE`; every byte of
  the two mask tables is 0..15 or 0xFF, where `pshufb` and TBL agree). Test: `sdk/tests/vec_byteswap_test.cpp`.
- **`tools/pch_neon_shuffles.py`:** `simde_mm_shuffle_epi32` / `simde_mm_permute_ps` (16,900 sites) as constant
  permutations on AArch64 instead of simde's lane-by-lane DUP + INS chain. Test: sa2-nx's
  `sdk/tests/neon_shuffles_test.cpp`.
- **NEON forms of the VMX helpers** (`rex/ppc/intrinsics.h`): vperm as one two-register TBL (8 instructions
  against 12), vctsxs / vctuxs as FCVTZS / FCVTZU (2 against 14 and 29; counts from sa2-nx's
  `tools/arm_forms_check.py`), and the small helpers (sa2-nx added seven more). Tests:
  `sdk/tests/vmx_helpers_neon_test.cpp`, `sdk/tests/vmx_small_helpers_test.cpp`.
- **The SDK's lock words inline** (`rex/thread/atomic.h` on POSIX builds).
- **Dropped: `rotate_word_narrow`.** Exact, but sa2-nx measured 0.07-0.12 % MORE instructions with the Switch
  compiler (it already folds the 64-bit form of a shift). The option exists and is off.

#### sa2-nx's second round, ported

| Item | Here | Count in this game |
|---|---|---|
| Loads from the image's read-only data as constants (`tools/ro_constants.py`; the PC build still loads and compares) | on (`SASRT_GEN_RO_CONSTANTS`) | 14,398 float, 602 double, 206 integer and 2,783 vector loads |
| Indirect calls: every `bctrl` tagged, a PC census, the usual targets as guarded direct calls (`tools/indirect_calls.py`, `tools/indirect_promotions.py`, `app/indirect_promotions.txt`) | on (`SASRT_GEN_PROMOTED_CALLS`) | 20,973 sites tagged; census of a race: 1.36 million indirect calls a second (45,000 a frame) from 5,085 sites; 223 sites promoted (31 with two or three targets), their guards catch 70.0 % of the census's calls |
| Single-precision loads straight into a float register (`tools/float_loads.py`: `ldr s; rev32` instead of `ldr w; rev; fmov`) | on (`SASRT_GEN_FLOAT_LOADS`) | 25,371 loads |
| ctx registers as locals in leaf functions with loops (`tools/leaf_locals.py`) | on (`SASRT_GEN_LEAF_LOCALS`) | 2,871 functions |
| Loop barriers only where a guest load could be hoisted (`tools/loop_barriers.py`) | on | 4,497 of 29,058 loop headers lose their barrier |
| The trap helper out of line and cold (`tools/pch_cold_traps.py`) | on (`SASRT_GEN_COLD_TRAPS`) | pch only |
| A function's entry flush mode from its direct callers (`tools/flush_mode_flow.py --image`), proofs redone after `direct_calls.py --redo` | on | 11,435 of 27,046 checks proven |
| `fp_copy_pairs` (a float copied through a register needs no mode, where vector mode is current) | on | 877,000 loads and 50,000 stores a second in a race |
| Critical sections take their owner from the guest context (`kernel_critsec_pcr_owner`, SDK key; the PC build compares with the lookup on every call) | on | 88,000 enters a second |
| `Memory::TranslateVirtual` without a heap lookup off Windows; `XObject::Retain` / `Release` inline; `kernel_state()` inline off Windows (round 3) | on | 39,000 / 63,700 / 58,800 calls a second |
| `tools/direct_calls.py`: only the code of C/C++ files names a hook (not comments or `__imp__` references), `--redo` | on | 130 hooked names; 193,103 direct calls |

A hazard of `tools/ro_constants.py` that this game does not have (futari-nx's finding, 2026-10-14): a XEX's import
records are words inside the image that the loader fills at run time (the address of each imported kernel
variable), and in sa2-nx's and banjo-nx's executables they stand at the start of `.rdata`, so the tool folded 86 and
77 loads of them to the values the generator's own process happened to get. Here the 765 records (xam.xex 384,
xboxkrnl.exe 381) are at `824B56C0`-`83370EB8`, outside the range the tool folds (`82000400`-`8235FE15`): **0 of the
17,989 folded loads touch one** (`tools/xex_import_records.py <xex> <generated folder>` prints it; run it again if
the image or the tool's range changes).

Not taken: sa2-nx's three stack-frame elisions (`tools/frame_traffic.py`; off there too: removing the prologue saves
of non-volatile locals tinted SA2's characters, the game reads a stack word it never wrote) and
`fp_copy_only_functions` (lost there by the census).

#### sa2-nx's third round, ported

| Item | Here | Count in this game |
|---|---|---|
| ctx registers as locals for the length of a call-free loop (`tools/loop_locals.py`; the barrier stays) | on (`SASRT_GEN_LOOP_LOCALS`) | 11,264 loop regions in 5,131 functions |
| Promoted call sites with two or three targets | on | 31 of the 223 sites |
| Divisions as the instruction (`div_inline`: `sdiv` / `udiv` and one select) | on | generator option |
| Vector loads from read-only data as constants (`REX_RO_V128`) | on | the 2,783 above |
| A start-up check of every form only one processor has, against plain C++ references (`app/src/sasrt_forms_selfcheck.cpp`; the idea is banjo-nx's) | on | 248 results; on the console a failure also writes `sasrt_selfcheck_failed.txt` next to the program |
| The census of calls per kernel export (`rex/hook.h`, PC builds) | diagnostic | in a race, per second (two consecutive 10 s reports of `sasrt_287`): `RtlLeaveCriticalSection` 88,400, `KeTlsGetValue` 11,600, `NtSetEvent` 11,500, `NtWaitForSingleObjectEx` 8,700, `NtReleaseSemaphore` 6,800, `KeGetCurrentProcessType` 1,600, the rest under 900 each |

#### GCC's early register allocation pass is off on the Switch (2026-10-13, peggle2-nx's console finding)

peggle2-nx ran on a console on 2026-10-13 and its large textures were garbage after their first megabytes, the same
in every run, with verify mode clean and the PC right. Its session traced it to the Switch compiler, in two steps:

- First reading (wrong, and corrected by that session within the hour): by-value vector locals of
  `tools/leaf_locals.py` / `tools/loop_locals.py` lost by scalar replacement of aggregates.
- **What the dumps show:** devkitA64's GCC 16.1 has an AArch64 early register allocation pass (`-mearly-ra`, `all`
  from -O2, `none` at -O1). In Peggle's copy of the XDK's streaming copy the optimised code is correct up to that
  pass and 38 of its 145 table lookups are gone after it; a register holding the byte-reversal constant is
  overwritten by a data load inside the loop (`tbl v30, {v30}, v30`). The trigger there is the two-register lookup
  of the NEON vperm helper (`uint8x16x2_t` + `vqtbl2q_u8`: a tuple that needs consecutive registers). **That helper
  is this port's, from its round of 2026-10-12**, which sa2-nx and peggle2-nx took. Clang compiles the same text
  correctly, so no PC run, lockstep or verify mode can see it.

What this port did:

- **Looked for the fault in its own code, and did not find it.** The 13:58 ELF has no table lookup indexed by its
  own table, in the one-register form (41,441 lookups) or the two-register form (2,857). `tools/early_ra_check.py`
  compiles a generated file with the Switch's flags with the pass on and off and compares the table lookups of every
  function: files 158 and 94 (this game's copies of the streaming copy, `sub_82CBCEA0` and `sub_82CBC4A4`), 95, 0,
  41 and 71, 1,802 lookups, **0 functions differ**, so nothing was dropped in them. (A difference would be a
  function to read, not proof: peggle2-nx compared its whole tree and found nine functions that differ, two damaged
  and six where the pass-on code is right and shorter.) That is six of 177 files and code compiled without LTO: no
  proof for the rest (`--all` runs them all, minutes per file).
- **How little "not found" says:** sa2-nx then checked its own tree. Its released ELF (LTO and PGO) is healthy on
  every signature, but the same source compiled per file has both streaming copies damaged with the pass on (71
  two-register lookups for 72 vperm statements, 25 one-register instead of 87, 6 indexed by their own table).
  Whether the pass strikes depends on inlining and layout, not on the source alone.
- **Turned the pass off anyway**, for everything built for the console: `-mearly-ra=none` on every compile and on
  the link (`app/CMakeLists.txt`, `SASRT_SWITCH_NO_EARLY_RA`, set before the SDK is added so its libraries and the
  LTO link have it). It costs 0 to 0.3 % of the instructions (file 158: 39,189 to 39,303; file 41: unchanged; file
  10: 31,776 to 31,801). A pass known to drop instructions in this very code family is not worth that.
- **Two build checks** (`tools/check_switch_build.py`): every compile statement and the link carry the flag, and no
  recompiled function has a table lookup indexed by its own table.
- **Vector registers stay references in the leaf and loop locals** (`RexLocalOf<PPCVRegister>` in the two tools'
  macros). Done on the first reading; it is NOT the fix (peggle2-nx's function is still wrong with it). Kept because
  the Switch compiler makes slightly less code that way (file 158: 39,189 against 39,582 instructions, 5,712 against
  5,799 loads; file 41: 34,830 against 35,036, 4,877 against 5,000) and it is the same program: a reference to the
  register instead of a copy in and out. General and float registers keep their locals; the generated code never
  takes a pointer to one (0 in the tree, against 24,300 pointer casts onto vector locals).
- **Every earlier NRO was built with the pass on**; the four that also have the two-register helper are those of
  2026-10-12 14:59 and 2026-10-13 02:46, 03:46 and 13:58. None of them ran on a console.
- **The NRO of 2026-10-13 15:30** (66,840,773 bytes, the one on the SD folder now) is built this way. Its checks:
  `early register allocation off (-mearly-ra=none): 732 of 732 compile statements, the link has it`, `table lookups
  in recompiled functions: 39565, indexed by their own table: 0`, and the earlier ones. Recompiled code: 7,973,300
  instructions and 3,080,155 loads and stores (the 02:46 ELF: 7,982,128 and 3,083,611): the references saved more
  than the pass cost. By sa2-nx's yardstick (a vperm statement compiles to one two-register lookup, and inlining
  can only add lookups to a function): the 172 functions with vperm statements have 1,630 two-register lookups for
  1,419 statements, and none has fewer than its statements except `sub_82817028`, which the linker folded into a
  branch to its identical twin `sub_8280BEA8`. PC, with the reference macros: verify mode on tracks 2.3 and 0.0 (`sasrt_304`, `sasrt_305`),
  `differences: 0`. The flag itself changes nothing on the PC (clang), so no PC run says anything about it; only a
  console run can. **peggle2-nx's console run with the flag (its build of 2026-10-13 15:15) draws its atlases
  right:** the flag is confirmed on hardware for the fault it was meant for. This port's own build has not run.

#### The post-codegen sequence now

`tools/post_codegen.py`: pch_no_volatile, thunk_calls (this game's), indirect_calls, loop_barriers, pch_cold_traps,
direct_calls `--redo`, guest_cas, flush_mode_flow `--redo --image`, vec_byteswap, pch_neon_shuffles,
**localize_native**, ro_constants, float_loads, loop_locals, leaf_locals, and since 2026-10-14 (the codegen ideas
below) vperm_one_source, fp_sign_ops, leaf_dead_stores, single_floats, inline_memcalls, vec_unaligned_stores. The
two analyses (leaf_dead_stores, single_floats) take their earlier rewrites back and decide again on every run, so a
changed tree (a new hook, an inline call) can withdraw a proof; the whole script now takes about four minutes. The
localized copies are made before the
last four steps: this port's localizer rewrites the load and store macros it knows into its shadow memory and does
not know the forms those steps write (peggle2-nx's store-log guard has the same constraint). A second run on a
processed tree leaves the copies alone. `tools/codegen.ps1` writes the image dump the two `--image` steps read
(`out/default_image.bin`).

Two rules learned the hard way: never read the generated tree while the generator runs (on Windows a reader made
it fail half-way with a write error), and never edit SDK headers while a PC build runs.

The script also keeps the time of every file its steps leave with the text it had. On a processed tree
`thunk_calls.py` rewrites the calls inside the promoted call sites (their targets are thunks) and
`indirect_calls.py` writes them back: the same text, but 104 files with a new time, which the build compiled again
after every run of the script, and the PC build runs it whenever the generator binary changes, which any SDK edit
does. Checked: a second run reports "104 files written by the steps, 104 of them with the text they had", and the
build after an SDK edit compiles 14 files instead of 121.

#### Results and checks

PC build of 2026-10-13 (clean codegen, all of the above):

- **SDK unit tests** (`tools\win\run_sdk_tests.ps1`, nine programs): 0 failed. `fp_any_mode_test` 600 million
  comparisons (negative control positive), `rotate_word_test` 2.57 million, `signal_skip_idle_test` no lost wake-up,
  `vec_byteswap_test`, `vmx_helpers_neon_test` 19.0 million, `vmx_small_helpers_test` (all 2^32 inputs of vcfux,
  6 + 3 million random vector pairs), `neon_shuffles_test` 10.2 million (256 immediates), `fcti_copy_test` 17.4
  billion checks, `float_loads_test` all 2^32 patterns: 0 differences each.
- **A race with the PC build's own checks** (`sasrt_288`, track 2.3): 244 million folded constants compared with
  the load, 128 million promoted calls compared with the indirect target, 14.3 million critical-section owners
  compared with the lookup, 297 million flush-mode proofs tested: 0 differences. The forms self-check at start: 248
  of 248 (on the PC these are the x86 forms; the ARM forms are checked on the console at every start).
- **Verify mode** on tracks 2.3, 0.0 and 3.0 (`sasrt_289` / `290` / `291`): `differences: 0` on all three; the
  native Direct3D layer compared 873,673 / 962,192 / 995,942 records with the original, 0 differences; no
  `DIFFERENCE` line; the only error line is the third-party Vulkan layer's that every run has. These runs cover
  fewer frames than those of 2026-10-12: the three `83xxxxxx` copies run now, and verify mode runs the original of
  every copy next to it on every call.

Switch NRO of 2026-10-13 02:46 (`out/nx/sdcard/switch/sasrt-nx/sasrt.nro`, 66,828,485 bytes; the 2026-10-12 one
was 68,413,637: -2.3 %; link-time settings unchanged, build 20.8 minutes):

- `tools/check_switch_build.py`: all checks passed (optimised codegen, the one known guest halt, NVK Mesa 26.2.2,
  `_start` at 0, no vector fused multiply-add).
- `tools/arm_forms_check.py` (the ARM-only forms compiled with the Switch compiler and its flags): all claims hold.
  `fctid` 7 instructions with one `frinti` and one `fcvtzs`; `divwu` 2 instructions against 4, `divw` 6 against 9.
- `fcvtas` in recompiled functions: 0 (18 in the 2026-10-12 ELF). The 34 left are the renderer's own `round()`
  calls, libm and Mesa.
- Recompiled code (`tools/elf_codegen_stats.py`): 7,982,128 instructions and 3,083,611 loads and stores. The last
  ELF counted this way was 2026-10-07's (8,296,881 and 3,267,907), so across both rounds: -3.8 % instructions,
  -5.6 % loads and stores.
- `msr fpcr` sites in recompiled functions: 21,822 (20,372 with the bet: more sites switch, far fewer test).
  Frame set-ups in game code: 42, as before.

That NRO was replaced an hour later by the one with the GPU round below (2026-10-13 03:46, 66,873,541 bytes): the
same generated code; the renderer and the shader package differ, and the link's inlining moved the counts by a few
(`msr fpcr` sites in recompiled functions 21,829; frame set-ups in game code 42). The NRO on the SD folder is a
third build, of 13:58 (66,889,925 bytes): that one plus the long-session fix and one correction in the renderer;
and then a fourth, of 15:30 (66,840,773 bytes), with a compiler pass switched off (the section on GCC's early
register allocation below).

Not run on a console.

What no PC run can say, so for the console: every speed. The static counts above are instructions and loads the
Switch compiler no longer emits, not time. `configs/sasrt_test_cpu_round12_off.toml` still separates the run-time
keys (now with `kernel_critsec_pcr_owner`); the build-time items are in the one NRO and have no switch at run time
(compare with the 2026-10-12 NRO if a build-time item is suspected).

### The codegen ideas of 2026-10-14 (sa2-nx's list of nine, from its hand-written functions)

The user asked, through the sa2-nx session, for nine code-generation ideas, each behind its own switch, checked on the
PC, and for 2, 5, 7, 8 and 9 also on the Switch compiler's output (a fault of devkitA64 GCC 16.1 shows only there:
peggle2-nx's lost table lookups). sa2-nx's audit lists the incidents every idea is checked against: (a) GCC's early
register allocation dropping table lookups (this port builds with `-mearly-ra=none`), (b) the game reading stack
words it never wrote, (c) the port's own code reading emulated registers, (d) values the loader writes at run time,
(e) the 360 compiler allocating registers across functions (callers read registers the ABI calls scratch), (f) a
profile lost where branching changes (this port has no PGO yet). The order is sa2-nx's: 8, 7, 1, 2, then 5, 6 and 9,
then 3. All are post-codegen steps (`tools/post_codegen.py`, after `leaf_locals.py`) with a compile-time switch in
`app/CMakeLists.txt` that gives the old statements back.

#### 8. A vperm of one vector as a one-register lookup (`tools/vperm_one_source.py`, `SASRT_GEN_VPERM1`)

- **Count:** 427 of the game's 1,419 vperm statements take both sources from the same register (SA2: 90 of 509).
  All 1,419 use plain register loads as operands, so the step sees every one.
- **What:** `REX_VPERM1(a, c)` = `rex::ppc::simde_mm_perm1_epi8_` (`rex/ppc/intrinsics.h`): one `TBL` with one table
  register and the index `(c & 0x0F) ^ 0x0F`, instead of a two-register `TBL` that needs a register pair; x86: one
  `pshufb`. Exact for every control byte (with a == b, bit 4 chooses between equal halves).
- **Checks:** `sdk/tests/vmx_helpers_neon_test.cpp` compares both forms with the two-source x86 form for every
  control value at every byte position (0 differences); the start-up self-check has 8 new results (`perm1_epi8`);
  `tools/arm_forms_check.py` checks `check_vperm1` is one one-register `tbl`, no longer than the two-source form.
  PC: verify mode on tracks 2.3 and 0.0 (`sasrt_314`, `sasrt_315`, with idea 7), see below.
- **Lesson (a) stays:** a one-register lookup is not safe from the early-allocation fault either (SA2's standalone
  compile lost one-register lookups too); `-mearly-ra=none` stays on.
- **ELF yardstick** (`tools/lookup_yardstick.py`, sa2-nx's with the one-source form): before, on the NRO of 15:22,
  the 172 functions with vperm statements had 1,631 two-register lookups for 1,419 statements, none short, none
  self-indexed. The numbers of the new build are in the Switch section below.

#### 7. fneg / fabs / fnabs as float operations (`tools/fp_sign_ops.py`, `SASRT_GEN_FP_SIGN_OPS`)

- **The gate first, a census of the rounding modes the game sets** (`[census] FPSCR rounding mode written by the
  game`, `sasrt_diag_runtime_census`, `REX_SYS_CENSUS` in `FPSCRRegister::storeFromGuest`): in 150 s of boot, menus
  and a race the game wrote the FPSCR **0 times**: it runs in round-to-nearest throughout. Statically the five
  `mtfsf` sites are the C runtime's control-word functions (`sub_82C9BC40` with 21 callers sets the default word,
  round to nearest, and later restores the saved one; `sub_82C9BCA4` sets exception bits; `sub_82C9BC80` clears bits;
  `sub_82C9BCC4` is a `_set_fpscr` with no direct caller) and the context restore `sub_82CA77CC`.
- **What:** the generator writes the three as integer operations on the register's bits (an XOR, AND-NOT or OR of
  the sign bit), which on AArch64 takes the value out of the float register and back. They are now
  `REX_FNEG(d, s)` = `d.f64 = -s.f64`, `REX_FABS` = `__builtin_fabs`, `REX_FNABS` = `-__builtin_fabs`: one `FNEG` /
  `FABS`, which only flip or clear the sign bit (no NaN quieting, not touched by the flush mode). 917 fneg, 596
  fabs and 2 fnabs (SA2: 1,528, 1,620 and 16).
- **Why the census:** a float negation lets the compiler fold it into the arithmetic next to it (`-(a * b)` as
  `(-a) * b`), which is exact in the symmetric roundings (to nearest, toward zero) and not in round-up or
  round-down. The existing fnmadd / fnmsub forms (`-std::fma`) have the same exposure. So the guard stays in the
  program: every platform counts guest writes of round-up / round-down (`g_rex_directed_rounding_writes`, defined
  by the program because the PC's SDK runtime is a DLL), and the `[enh]` report says it once if the game ever does
  (a WARN line asking to keep the log).
- **Checks:** `sdk/tests/fp_sign_ops_test.cpp`: 14.7 billion comparisons of the float and integer forms (special
  values, every single-precision pattern widened, random 64-bit patterns; flush off and on; four rounding modes), 0
  differences. The start-up self-check has 72 new results (12 values incl. a signalling NaN and denormals, flush off
  and on, three operations). PC: verify mode on tracks 2.3 (`sasrt_314`: 0 differences) and 0.0 (`sasrt_315`: one
  native-layer byte difference, see below).

#### The native-layer byte differences of `sasrt_315` and `sasrt_321` (not from these ideas)

`[api] DIFFERENCE: DrawIndexedVertices: guest byte FF172D12 native 40 original 00 (+17 of region FF172D01+E4, 00
before the call; thread F800007C)`. The original `D3DDevice_DrawIndexedVertices` (`sub_82CD1DB8`) and the 72
functions it reaches contain none of the new forms (no one- or two-source vperm, no sign operation), so neither
idea touched what was compared. It is the second time in about twenty verify runs (`sasrt_269` had one, before any of
this, in the same function), now with the details the message was extended for: a byte of the region the layer
compares (the bound vertex shader's object), 0 before the call, left 0 by the original on the device copy, 0x40
from the native layer. Still unexplained; it disables only that path for the rest of the run.

`sasrt_321` (ideas 1 and 2 in the build) had the third: `DrawVertices: guest byte F600EC51 native 86 original B4 (+0
of region F600EC51+150, B4 before the call; thread F800007C)`. Same thread as `sasrt_315`, and in all three the region
is a vertex binding program's (`ExternalRegions`: the program's offset word plus the shader object's base, sized by
its length word) and starts at an ODD address (FF2DF501, FF172D01, F600EC51): the native layer wrote a byte the
original left as it was. This time two functions with today's forms are in the original's call tree:
`sub_82CD3138` (two single-precision multiplies of idea 2) and `sub_82CDD318` (r9 and r10 not written back, idea 1;
checked by hand: its direct caller writes both before reading them, its other caller is a jump thunk the analysis
follows). With the same shape before any idea existed, this stays filed as the native layer's open issue; the odd
start of the region is where to look next.

`sasrt_337` (verify 2.3 after the Clear operation, 2026-10-14 ~22:25) had the fourth, in the same place as the third:
`DrawVertices: guest byte F600EC51 native C7 original F4 (+0 of region F600EC51+150, F4 before the call; thread
F800007C)`. The Clear operation adds NOPs to the native Clear's own record and writes no guest memory; the dead-draw
skip and the widening are on the ring's side. Same region start, same byte, same thread: one cause, still open.

#### 1. Leaf write-backs no caller can read (`tools/leaf_dead_stores.py`, `SASRT_GEN_LEAF_DEAD`)

- **What:** `tools/leaf_locals.py` keeps a leaf function's registers in C++ locals and writes every register the
  function wrote back to `ctx` at each exit. A write-back of a register no caller can read is now
  `REX_LEAF_DEAD_R` / `_F`: nothing (or the poison of the PC test).
- **The analysis** (on the guest code: the instruction comments of the generated tree and the C++ control flow
  around them; 134,681 functions, 2.6 million instructions, about a minute):
  - per function, the registers it or its callees may read before writing them, to a fixed point over the call
    graph; a call kills nothing (lesson (e): callers read registers the ABI calls scratch, so a callee is never
    assumed to overwrite one);
  - per call site, what is live after it: read later in the caller before being written, or still unwritten when
    the caller returns and live after the CALLER returns (its own LiveOut, to a fixed point); a tail call passes the
    caller's LiveOut on;
  - everything is live after a function with an address outside direct calls: a data word of the image (any section
    but `.pdata`: 18,050 functions), a `lis` + `addi` / `ori` pair anywhere in a function (3,418; a jump thunk's own
    pair, which the generator already turned into a direct tail call, is not counted), the entry point, a promoted
    indirect target, any `8[23]xxxxxx` in the port's sources (hooks, natives, the verify mode that compares
    registers, host code that calls guest functions), or no direct caller at all (except a jump thunk the generator
    bypasses); everything is live at an indirect call, a hooked call, a trap, an unknown instruction and before a
    callee that is not in the tree; r1, r2, r13 and the return registers r3 and f1 are always written back.
- **Count:** 13,268 of the 36,611 leaf write-backs (36 %), in 1,815 of the 2,871 leaf functions. Of the leaf
  functions, 2,298 are analysed, 337 have everything live after one of their call sites, 150 have their address
  taken and 86 have no direct caller.
- **Checked by hand:** `sub_826B3370` (28 call sites, dead f11-f13, r4, r10): every caller writes those registers
  before reading them, on both paths of its first branch. `sub_824ED980` (dead r9, r10) has no caller but its jump
  thunk, whose address is nowhere in the image: unreached code.
- **PC poison test** (lesson (c); `SASRT_GEN_LEAF_DEAD_POISON=ON` writes 0xDEADBEEFDEADBEEF into a skipped general
  register and a signalling NaN into a skipped float register): a race (`sasrt_316`, `sasrt_317`): no crash, no
  DIFFERENCE, the race's pictures right (car, track, HUD, minimap); verify mode on tracks 2.3 and 0.0 (`sasrt_318`,
  `sasrt_319`): 0 differences in every check, self-check 328 of 328.
- **Calls through the hooks of hand-written natives** (memcpy, and since idea 4 memset, memmove and the Direct3D
  constant writers) count as calls of the originals: the native takes only the original's arguments, and its guard
  compares only the return and non-volatile registers. Every other hooked call stays "everything live". With it the
  count is 13,609 write-backs in 1,824 functions.
- **Without poison** (`sasrt_320`, `sasrt_321`, with idea 2): verify 2.3: 0 differences; 0.0: one native-layer byte
  difference, the third of its kind (below).

#### 2. Single-precision arithmetic in float where its inputs are singles (`tools/single_floats.py`, `SASRT_GEN_SINGLE_FLOATS`)

- **What:** `X.f64 = double(float(A.f64 op B.f64))` becomes `X.f64 = REX_FADDS(A.f64, B.f64)` =
  `double(float(A) + float(B))` (and `REX_FSUBS`, `REX_FMULS`, `REX_FDIVS`, `REX_FSQRTS`) when A and B are proven
  singles. Exact: double has more than 2 x 24 + 2 bits, so rounding to double and then to single equals rounding to
  single once, for +, -, *, / and sqrt in every rounding mode. Where A and B are locals defined from floats the
  compiler then drops the `float(double(t))` pairs. Fused operations stay double fma + one rounding (Unleashed's
  test: a single-precision fma differed 32 times in 30 million samples). The statements stay where they are, in
  the FPU mode (flush off) the generator switches to before every scalar float operation; the any-mode forms are
  left alone.
- **"Proven single"** (per function, a forward must-analysis on the guest code): after `lfs` / `lfsx` / `lfsu` /
  `lfsux`, a single operation, `frsp`, `fmr` / `fneg` / `fabs` / `fnabs` of a single, `fsel` of two singles;
  nothing at entry; every call, indirect call, trap or unknown statement forgets everything.
- **Count:** 3,034 of 4,166 fadds, 3,088 of 4,472 fsubs, 7,326 of 10,230 fmuls, 1,549 of 2,121 fdivs and 279 of
  311 fsqrts (72 %); no frsp has a single input.
- **Switch compiler, one file at a time** (`tools/one_file_ab.py`, now also counting `fcvt`): file 144 (the most
  rewritten statements) 857 -> 728 `fcvt` and 33,000 -> 32,927 instructions; file 15 668 -> 567 and 32,430 ->
  32,327; file 115 400 -> 395 and 30,819 -> 30,811. A modest gain.
- **Not covered:** a single carried around a loop (an accumulator). The loop local is a double, so each pass still
  converts it to single and back; sonic-unleashed-nx measured 13 instructions against 10 for such a loop with a
  float variable. That needs float-typed loop locals (`tools/loop_locals.py`), a larger change for later.
- **Checks:** `sdk/tests/single_floats_test.cpp`: 160 million comparisons of the two forms (special values, every
  operand class, ties of the single rounding, four rounding modes, flush off), 0 differences; its negative control
  with flush-to-zero on finds 709,128 differences, as it must (that is why only the FPU-mode statements are
  rewritten). The start-up self-check has 160 new results (eight pairs, five operations, four rounding modes).

#### 6. memcpy / memset calls of a constant size inline (`tools/inline_memcalls.py`, `SASRT_GEN_INLINE_MEMCALLS`)

- **Count** (the C runtime found by signature, below: memcpy 82C8EEF0, memset 82C8D8D0, memmove 82C8E720): memcpy
  1,600 direct calls, 776 with a constant size, **322 of 1 to 64 bytes**; memset 1,177, 765 and **322**; memmove 379
  calls, 8 with a constant size (left alone). Most common: memset 52 bytes x59, memset 32 x43, memcpy 32 x36,
  memcpy 64 x32 (SA2: 3,468 calls of 64 bytes or less).
- **What:** a call whose `r5` is set by `li` earlier in the same straight line (no label, call or write of r5 in
  between) becomes `REX_MEMCPY_CONST(N, call)` / `REX_MEMSET_CONST(N, call)`: the N bytes with two to eight loads
  and stores the compiler picks for the constant (`rex/ppc/memcalls.h`, `CopyConst`: every load before every store),
  or the original call where the helper must not:
  - memcpy copies FORWARD: with dst > src and the ranges overlapping it smears, so the original runs
    (`CopySmears`); for dst <= src an overlap gives what memmove gives, which the helper does;
  - a range in 0x7F000000-0x7FFFFFFF (hardware registers) or from 0xA0000000 (the physical views, which alias each
    other), or wrapping around 4 GB, runs the original (`PlainRange`);
  - memcpy keeps its first instruction, `std r3,-8(r1)` (lesson (b)); memset has no stack store; r3 stays.
- **Checks:** `sdk/tests/memcalls_test.cpp`: every N of 1-64 at every relative position of the two ranges within
  160 bytes, and the range edges: 1,079,328 checks, 0 differences.

#### 5. stvlx / stvrx without byte loops (`tools/vec_unaligned_stores.py`, `SASRT_GEN_VEC_UNALIGNED`)

- **Count:** 988 sites in 76 functions (766 stvlx, 222 stvrx); 292 of them in the four XDK streaming copies (idea 9),
  60 in `sub_82D03208`, 64 in `sub_8302AA90` (SA2: 74 per streaming copy and 60 in one Direct3D routine, the same
  library). The generator writes each as a loop of up to 16 single-byte stores.
- **What:** `REX_STVLX(ea, v)` / `REX_STVRX(ea, v)` (`rex/ppc/vec_unaligned.h`): the vector reversed once (one
  table lookup or rev64 + ext) and the same bytes stored with at most five stores (16 / 8 / 4 / 2 / 1). Exact: the
  same bytes get the same values and no other byte is written; the range stays inside one 16-byte block, which
  never straddles the 0xE0000000 host offset.
- **Not done:** merging a left / right pair into one 16-byte store. It needs a proof that the right half's address is
  the left's + 16, and in this code the index register that holds 16 is set elsewhere (`li r10,16` before the loop);
  each half is already a few stores. The unaligned loads (3,602 lvlx, 360 lvrx) are not touched.
- **Checks:** `sdk/tests/vec_unaligned_test.cpp`: every alignment with random vectors against the loops, 640,000
  comparisons, 0 differences; the start-up self-check has 32 new results (both halves, 16 alignments, compared over
  48 bytes around the block).

#### 4. Library natives by signature (`sasrt_cpu_native_memset`, `_memmove`, `_d3d_constants_a`, `_d3d_constants_b`)

sa2-nx's `tools/crt_signatures.py` with signatures made from sa2-nx's image (`make`) found, each uniquely, in this
image: memcpy 82C8EEF0, memmove 82C8E720, memset 82C8D8D0 (the three of its database), the two Direct3D shader
float-constant writers 82CC2368 and 82CC2260 (byte for byte sa2-nx's 8255D990 and 8255D8B8: the same FNV-1a hashes),
and the four XDK streaming copies 82CBC180, 82CBC4A4, 82CBCB10, 82CBCEA0 (idea 9). sa2-nx has natives for the first
five (its `n_827EFEA0.h`, `n_827EF8B0.h`, `n_d3d_constants.h`); this port had memcpy only. Ported, each a hand-written
native with the memcpy native's guard (its written ranges compared with the original's on a copy; every call in
verify mode), its own key, and its code hash checked at start:
- `n_82C8D8D0.h` memset: `memset(dst, r4 & 0xFF, n)`; declines garbage in the upper half of r5, a range that wraps
  or leaves a physical view.
- `n_82C8E720.h` memmove: as sa2-nx's, plus the store of r3 at -8(r1) on the path where the original branches to
  memcpy (dst < src, signed compare), which sa2-nx's native leaves out (lesson (b)).
- `n_d3d_constants.h`: one copy of the constant vectors plus the dirty-mask update, as sa2-nx's (sa2-nx's console
  profile: 1.3 % and 1.2 % of its game thread).
- All of them, and memcpy, now also decline two ranges that may share bytes through different physical views
  (`MayOverlap` in `sasrt_hot_common.h`: the views at 0xA0000000, 0xC0000000 and 0xE0000000 map the same memory) and
  a range that leaves its view (`CrossesView`).
- **memcpy, a correction:** the original's first instruction is `std r3,-8(r1)` and it reloads r3 from there before
  every return. The native memcpy (since 2026-10-06) never stored that word: the stack word below the caller's stack
  pointer kept a stale value where the original leaves r3. It stores it now (its guard compares those 8 bytes too),
  and declines the one case where the copy itself would overwrite the saved word.

#### PC results of ideas 6, 5 and 4 (one build with all three)

- **A race** (`sasrt_322`, census on): no DIFFERENCE, no crash, every new hook's code hash accepted; the start-up
  self-check 520 of 520. Uses per 10 s: Direct3D constant writers 56,576 and 142,080 calls, memset native 4,096,
  memmove 256; the memcpy native 160,768 (the small constant copies are inline now).
- **Verify mode** on tracks 2.3 and 0.0 (`sasrt_323`, `sasrt_324`): 0 differences in every check; the native
  layer compared 881,157 and 2,011,378 calls with the original, 0 differences; the new natives' guards: e.g.
  `sasrt_cpu_native_d3d_constants_b` 1,048,576 checks, memset and `_d3d_constants_a` 4,096 each, no difference.

#### A correction of the two analyses (found while building idea 6)

`tools/leaf_dead_stores.py` and `tools/single_floats.py` (through the first's parser) recognised a call only as
`sub_X(ctx, base);`. Once idea 6 had written calls as `REX_MEMCPY_CONST(N, sub_X(ctx, base));`, a later run of the
post-codegen chain no longer saw those 644 calls: the registers they read were not counted, and single values were
assumed to survive them. The pattern now finds a call inside the macro too (the inline path reads no more than the
call), and single_floats now takes its earlier rewrites back and decides again on every run, as leaf_dead_stores
always did. Effect: leaf_dead_stores the same 13,609 write-backs (its rerun wrote 0 files); single_floats withdrew 9
rewrites one run had added in one file (likely harmless, the fallback memcpy / memset touch no float register, but not
proven), back to 15,276.

**A second gap, found by banjo-nx (2026-10-15).** `tools/leaf_dead_stores.py` parses only `DEFINE_REX_FUNC(sub_X)`
bodies. A function the generator names (`DEFINE_REX_FUNC(<name>)`) was never read, so a `sub_` function it called
directly would have had the LiveOut of its other callers only, and a write-back the named caller reads could have been
left out. Here the named functions are the 236 save / restore helpers (they call nothing) and `xstart` (it calls only
indirectly), so nothing was wrong in any build; banjo-nx has CRT functions under names too. The tool now also reads the
named bodies and treats every `sub_` function one of them calls directly as taken (everything live after it): a check
run finds none and gives the same 13,609 write-backs, so the generated code does not change.

**A third gap, also found by banjo-nx (2026-10-15), and this one changed the result.** `tools/loop_locals.py` writes
border stubs (`loc_F0000001:` with only `REX_LOOP_IN` / `REX_LOOP_OUT` copies, then `goto loc_<real>;`; 4,585 of them
here). `parse_function()` gave a label the guest instruction that follows it in the text, so a goto into a stub (a
loop's entry, its exits) became an edge to the wrong instruction: a read on the real path could be missed (leaf
write-backs taken for unread) and a join could miss a predecessor (single values taken for proven). `resolve_stubs()`
now redirects every goto to a stub to its final target before the parse (same lines, same count). Effect, in both
analyses (`single_floats.py` uses the same parser): leaf write-backs 13,609 -> 13,605 (`sub_82D5FDD8` writes f13 and r5
back again: a caller reads them through a loop-exit stub); single-precision rewrites 15,276 -> 15,272 (10 withdrawn in
`sub_8263F180`, `sub_82AA88D8`, `sub_8269DA88`, `sub_82A66890`, `sub_82C14C18`, `sub_82DC78E8`, `sub_826A6F08`; 6 more
proven in `sub_82C3BC20`). Every NRO from 2026-10-14 18:22 to 2026-10-15 01:55 had the 14 wrong sites; verify mode
cannot see them (it checks the native paths, not the generated code). The NRO built after this fix replaces them.

A fourth one banjo-nx found, mid-asm hooks (a hook's register arguments, and a `goto` inside its `if` block taken as
the instruction's unconditional end, which hid the guest call after it), does not occur here: the generated tree
declares no hook (`extern void|bool` none) and has no `if (hook())` form; every other call passes `(ctx, base)`.

#### The Switch build with ideas 8, 7, 1, 2, 6, 5 and 4 (NRO of 2026-10-14 18:22, 66,812,101 bytes)

What only the Switch compiler's output can show (lesson (a)), checked on its ELF:
- `tools/check_switch_build.py`: table lookups in recompiled functions 40,286 (2,279 two-register), **0 indexed by
  their own table**; **no vector fused multiply-add**; `-mearly-ra=none` on 732 of 732 compile statements and the
  link; the other checks as before.
- `tools/lookup_yardstick.py` (the source as the yardstick): the 172 functions with vperm statements have 1,203
  two-register lookups for 992 two-source statements and **none has fewer**; their one-register lookups rose from
  5,323 to 6,202 (the 427 one-source statements, more where inlined). The functions with fewer one-register lookups
  than byte reversals are the same as before the ideas (1,797; the compiler cancels a load's reversal against a
  store's: not the fault).
- sa2-nx's `tbl_canary.py`: 0 lookups whose table is also their index, in any function.
- `tools/arm_forms_check.py` (the forms compiled alone with the Switch flags): all claims hold; the one-source vperm
  is 4 instructions with one one-register `tbl` (two-source: 8), fneg / fabs one float instruction each, the
  unaligned stores straight-line (stvlx 35 instructions, stvrx 27; the first try with the vector bytes read in place
  was 62, with an overlap test and a byte-by-byte path the compiler added because it could not prove the bytes do not
  overlap its temporary: they are copied to a local first now).
- The forms in the recompiled code: 1,532 scalar `fneg` and 600 `fabs` (inlining repeats the 917 and 596 sites), **no
  `eor` with the sign mask left**; every scalar fused multiply-add is double precision (4,359 fmadd, 42 fmsub, 15
  fnmadd, 716 fnmsub: the guest's own, from std::fma), so the single-precision forms of idea 2 were not contracted.
- `tools/elf_codegen_stats.py`: recompiled code 7,955,732 instructions and 3,079,299 loads and stores (the NRO of
  2026-10-13 15:30: 7,973,300 and 3,080,155). Static counts understate the round: inlining the 644 small copies adds
  code at the call sites while it removes the calls, and the byte loops of idea 5 ran up to 16 times per store.

Not run on a console.

**The NRO of 2026-10-14 21:44 (66,869,445 bytes)** replaces it: the same plus banjo-nx's fix of the inline memcpy
(`CoversSlot`: a destination over the stack word at -8(r1) runs the original, which returns the copied bytes in r3),
banjo-nx's EDRAM items and the dead-draw skip (below). Its ELF: table lookups 40,288 (2,279 two-register), 0 indexed
by their own table, no vector fused multiply-add, `-mearly-ra=none` on 732 of 732 compile statements and the link;
the yardstick unchanged (1,203 two-register lookups for 992 two-source vperm statements, none short; 6,202
one-register; the same 1,797 functions with fewer one-register lookups than reversals); recompiled code 7,956,764
instructions (+1,032: the slot test at the 322 inline memcpy sites) and 3,079,023 loads and stores. Same shader
package. Not run on a console.

**The NRO of 2026-10-14 22:34 (66,881,733 bytes)** replaces that one: the same plus banjo-nx's Clear operation
(`sasrt_gpu_api_clear`). Its ELF: table lookups 40,285 (2,279 two-register), 0 indexed by their own table, no vector
fused multiply-add, `-mearly-ra=none` on 732 of 732 and the link; the yardstick as before (1,203 two-register
lookups for 992 two-source statements, none short; 6,202 one-register); recompiled code 7,956,572 instructions and
3,079,034 loads and stores (the link's partitioning moves a few hundred; no recompiled source changed). Same shader
package. Not run on a console.

**The NRO of 2026-10-15 01:55 (66,934,981 bytes)** replaces it: the same plus banjo-nx's step 4 on the renderer thread
(the sampler cache invalidated by range, persistent 16-bit indices; the persistent vertex arena in the code but off)
and the per-shader GPU diagnostic. Its ELF checks as before (40,286 table lookups, 0 indexed by their own table, no
vector fused multiply-add, `-mearly-ra=none` everywhere; 1,203 two-register lookups for 992 two-source vperm statements,
none short). Same shader package. Not run on a console.

**The NRO of 2026-10-15 06:55 (66,934,981 bytes: the same size by page alignment)** replaces it: the analyses'
correction ("A third gap" above: 4 write-backs back in `sub_82D5FDD8`, 10 single-precision operations withdrawn, 6 more
proven). Recompiled code 7,957,316 instructions (+8). Every build check as before. PC verify mode after the
correction (`sasrt_345`): 0 differences. Not run on a console.

#### 9. Natives for the XDK's vector streaming copies: measured, not built

- **Found** by signature (above): 82CBC180, 82CBC4A4, 82CBCB10 and 82CBCEA0, the same four routines as sa2-nx's.
  Each is called from one place, two small dispatchers (82CB8ED8 and the function before it), through jump thunks.
- **How often they run here:** never in the PC profile (220 s, boot to race, 359,898 busy samples: not one sample
  in any of the four or their dispatchers); none of their thunks in the indirect-call census of a race (186 million
  calls). The Direct3D constant writers, by comparison, are 1-2.5 % of their thread in the same profile.
- **What a native would have to match:** the routines copy in 1,024- and 128-byte units with aligned loads (and a
  vperm pipeline for an unaligned source in three of them), overrun for a size that is not a multiple of 128, and
  leave the last chunk in v1-v63, which includes v14-v31 that the natives' guard compares; three of them also
  store r30, r31, v64 and v65 below the stack pointer and restore them. An exact native per variant is possible,
  but for code this game does not run it buys nothing.
- **Their exposure to lesson (a)** (sa2-nx's reason, besides speed): the build keeps `-mearly-ra=none`, and the
  lookup yardstick of the Switch build (below) finds no function with fewer two-register lookups than its two-source
  vperm statements. Their byte-loop stores are gone with idea 5.

#### 3. Hot loops versioned by a run-time overlap check: audited, no candidate

sa2-nx's evidence is its hand-written vertex loaders and matrix multiply, which read their inputs once per call
because they check once at entry that the output does not overlap them. This port's PC profile has no such loop
worth the risk: the hottest guest functions of the main thread are `sub_825E0F28` (3.7 % of that thread),
`sub_82ECA7A8` (3.1 %) and `sub_825BCD10` (2.6 %); none has a loop. `sub_825E0F28` is straight-line 4x4 matrix
code (48 splats, 38 vector loads, 36 multiply-adds, 20 vector stores, 7 calls); on the Switch it compiles to 714
instructions with 99 loads and **174 stores**. The stores are the vector registers written to the context, because a
function with calls keeps its vector registers there (`non_volatile_vector_as_local` stays off, see the CPU rounds),
not reloads forced by aliasing. So the lever there is a different one: vector registers as locals between the calls
of non-leaf functions, or the dead write-backs of their tails (sonic-unleashed-nx's suggestion: tools/leaf_dead_stores.py
extended past the leaves). Listed for later, not built.

### banjo-nx's codegen rounds, ported 2026-10-19

The user asked for "as many as possible" of banjo-nx's codegen improvements of 2026-10-15 to 2026-10-19
(`D:\Banjo kazooie port\banjo-nx\docs\codegen-enhancements.md`), ported at once and then verified. Each is a generator
option (`app/perf_overrides.toml`) or a post-codegen step (`tools/post_codegen.py`, in banjo-nx's order) with a CMake
switch back (`app/CMakeLists.txt`, `SASRT_GEN_*`). Counts are from the codegen of 2026-10-19.

**Generator options (the SDK's generator, `sdk/src/codegen`):**

- `rotate_word_shifts`: `rlwinm` / `rlwimi` with a mask that does not wrap as the shift, extract or 32-bit rotate the
  mask makes of them, `(x << sh) & m`, `(x >> (32 - sh)) & m` or `rotl32(x, sh) & m`. GCC turns each of those into one
  `lsl` / `lsr` / `ubfiz` / `ubfx`; this port's own `rotate_word_narrow` (a rotate and a mask) did not get there and
  stays off. `sdk/tests/rotate_word_test.cpp` (banjo-nx's superset of this port's test): 5,136,384 comparisons of the
  shift and narrow forms with the 64-bit forms, every shift and mask, 0 differences.
- `fp_copy_forwarding`: with `fp_copy_pairs`, a float copied through a register (`lfs` ... `stfs`) keeps its bits in
  any flush mode and through other instructions, an in-place `fneg` / `fabs` / `fnabs` included (the stored bits are
  `(QuietSingleBits(bits) & keep) ^ flip`), not only where vector mode is known current.
- `dcbt_prefetch`: the game's `dcbt` / `dcbtst` hints as the host's prefetch of the same address. Its operands are
  read as {CT, RA, RB} since banjo-nx's fix of 2026-10-16 (the generator read dcbz's {RA, RB} and prefetched RA alone,
  or r0); the option had been off here, so no build had the wrong ones. `SASRT_GEN_DCBT_PREFETCH=OFF`: nothing.

**Post-codegen steps, new (each its own tool, adapted from banjo-nx's):**

| Step | What | Here | Switch back |
|---|---|---|---|
| `frame_traffic.py` | marks the stack-frame statements (`REX_LR_READ`, `REX_LR_WRITE`, ...); its three elisions stay off (not exact: a game can read a stack word it never wrote) | 20,995 `mflr`, 22,098 `mtlr` marked | (marks only) |
| `ro_constants_cfg.py` | read-only constants followed over the control-flow graph: the loads `ro_constants.py` missed because a label (a loop head) stood between the base register's constant and the load. The PC build compares each with the load (`RexRoCheck`) | 6,235 more loads (5,816 `lfs`) | `SASRT_GEN_RO_CFG` |
| `dead_ctx_defs.py` | guest register writes no instruction can read are left out (backward liveness per function on `leaf_dead_stores.py`'s whole-program analysis; a record form keeps its cr0) | 20,792 writes and 646 record forms in 13,001 functions | `SASRT_GEN_DEAD_DEFS` (test: `SASRT_GEN_DEAD_DEFS_POISON`) |
| `flush_hoist.py` | a loop header's flush-mode check in front of the loop where the loop is call-free and its checks go one way (the PC build's flush-flow check counts it) | 256 loops in 162 functions | `SASRT_GEN_FLUSH_HOIST` |
| `switch_goto.py --thread` | a jump-table dispatch as a computed goto copied into each handler (GCC's cross-jumping off for that function). Here only `sub_82EB6B78`, the renderer thread's bitstream decoder (4.6 % of the guest samples of the PC profile): a 9-bit code read from a bit buffer, 512 cases, 137 handlers jumping back to the dispatch | 1 function | `SASRT_GEN_SWITCH_THREAD` |
| `lr_preserve.py` | since `elide_lr_stores` ctx.lr changes only at epilogues, a write-back stores the value ctx.lr already holds wherever every callee preserves it: those compile to nothing (`REX_LR_WRITE_SAME`; the PC build compares every one) | 21,763 sites proven of 22,098 | `SASRT_GEN_LR_WRITE_SAME` |
| `r1_preserve.py`, `r1_local.py` | guest r1 as a local mirror (`r1l`), every write stored to ctx at once, the reload after a call dropped where the whole-program proof says the callee returns with r1 unchanged (the PC build checks the assumed calls: `REX_R1_CHECK`). Only in the functions of a measured choice list: banjo-nx found it a loss over all functions together | proof: 76,045 functions strictly, 129,382 with the assumptions | `SASRT_GEN_R1_LOCAL` |
| `vsel_neon.py` | VMX `vsel` as one NEON `vbslq_u8` (simde's three operations were fused by GCC only some of the time) | 2,220 | `SASRT_GEN_VSEL_NEON` |
| `inline_leaves.py` | each generated file gets a `static inline` copy of every tiny leaf (at most 12 guest instructions, no calls) it calls directly in another file, and calls the copy (GCC can inline it) | 38,401 calls to 32,521 copies of 26,284 leaves | `SASRT_GEN_INLINE_LEAVES` |

**Changes to this port's existing tools:** the loop barrier clobbers the 4 GB guest window only, not all memory
(ctx and the host stack keep their registers across it; `SASRT_GEN_NARROW_LOOP_BARRIER`); `direct_calls.py` no longer
takes a `#` comment of a toml or of CMakeLists.txt, or the `non_argument_as_local_keep` list, for a hook (17 functions
were on the weak alias only because of them: their calls can now be inlined); `ro_constants.py --xex` keeps loads of
the XEX's import records (none of the 765 was under a folded load here); `loop_locals.py` / `leaf_locals.py` read an
opt-out list (`app/config/locals_optout.txt`) and their macro block has banjo-nx's corrected note on by-value vector
locals; `leaf_dead_stores.py`'s parser knows mid-asm hooks (this port has none: its result is identical, checked list
for list); the vector registers of the loop and leaf locals are values, not ctx references
(`SASRT_GEN_VECTOR_LOCALS_BY_VALUE`; safe with `-mearly-ra=none`, peggle2-nx's real cause of its 2026-10-13 fault).

**The per-function choices, measured** (`tools/codegen_choice.py`, new: banjo-nx's method, its `cc.py` and
`tools/locals_choice.py`, as one tool). Every generated file compiled with the Switch build's own command line (without
`-flto`, so the object holds machine code) as built (form A) and with one step's switch back (form B), each function's
A57 code costed from `objdump`: the loop-weighted cost sum(w * (1 + is_mem)), w = 10 inside a cycle of the function's
control-flow graph, code reached only after `ppc_trap` left out. Static counts of the compiled code, not run-time
samples (2026-10-19, `out/choice`):

| Step | Functions | Form A against B, all of them | Chosen | With the choice |
|---|---|---|---|---|
| r1 as a local mirror (`r1_local.py`) | 32,641 | +0.03 % (a wash, as banjo-nx found: a loss in some, a gain in others) | 17,348 keep it (`app/config/r1_local_choice.json`) | -1.15 % of the cost without it |
| link-register write-backs (`lr_preserve.py`) | 20,741 | -4.55 % | 18,623 keep them (cheaper or equal; `app/config/lr_write_same_choice.json`) | -5.00 % |
| loop / leaf locals (this port's, since 2026-10-12) | 8,002 | -9.94 % | 123 opt out, cheaper without by more than 2 % (`app/config/locals_optout.txt`) | another -0.97 % |
| vector locals by value (`SASRT_GEN_VECTOR_LOCALS_BY_VALUE`) | 372 | -4.15 % (+3.3 % instructions: fewer of them in loops) | global, on | |

**Found while verifying: a second run of the steps changed the tree** (the user pointed to sa2-nx's fix). A PC build
re-ran `tools/post_codegen.py` on the already processed tree (a CMake re-configure re-runs the codegen command, and the
generator, seeing its stamp, leaves the files). The late steps take their own rewrites out first, but the earlier
steps of the round stayed in place and the base steps decided differently on their forms: single_floats proved a few
fewer operations, flush_hoist hoisted 249 loops instead of 256, ro_constants folded 17 more vector loads (each exact,
but the tree depended on how often the script had run, and that run rewrote 279 files while a Switch build was reading
them: the build failed on a half-processed pch and was rebuilt alone). Fixed with sa2-nx's copy of peggle2-nx's
`tools/round_restore.py`: after the late steps' restores it takes the round's other rewrites back out too (dead
definitions, CFG constants, unaligned stores, inline memcalls, single floats, leaf write-backs, sign operations, one-
source vperm), so every step reads the text it had in the first run. With it, the narrow loop barrier's window is
4 GB + 4 KB (peggle2-nx's correction: on the PC an address from 0xE0000000 up lies 4 KB higher). Checked
2026-10-20 with sa2-nx's fix adopted (and `tools/inline_leaves.py`'s restore dropping the blank line it added): a
second post-codegen run over the first's output writes the same text (0 files differ); the generated headers
converge after the second run.
Lesson kept: a Switch build must not run while a PC build can regenerate the tree.

**Not ported, with the reason:** `hot_layout.py` (this port already gathers its 1,043 hottest functions at the front
of `.text` with `app/hot_functions.ld`, which `.text.hot.*` sections would bypass); `limiter_lazy_log10.py` (the XAudio
limiter it rewrites is not in this game's function table, and no limiter shows in the profile); `store_cards.py`
(marks pages for banjo-nx's own renderer's caches: no consumer here then; ported on 2026-10-21 for Renut, below);
`-mno-outline-atomics` (no effect, banjo-nx
measured); the hot-edge inline copies (they need a console profile's call edges).

### The store cards (banjo-nx's CPU proposal 1, by way of sa2-nx; 2026-10-21)

Since this port renders with Renut, `store_cards.py` has a consumer: Renut proves its cached vertex, index and texture
copies by hashing their guest bytes again after every kick (the console's render thread, race of 2026-10-21: 25 % of
it in `PmullHash`, about 51 MB hashed a frame, and about 217 texture uploads a frame of dynamic textures). With the
cards every guest store outside the stack also zeroes its 4 KB page's card (a byte at guest address `ea >> 12`, in the
guest window's first MB, which `Memory::Initialize` now reserves for them, read-write), and Renut re-hashes or
re-uploads only what a written page holds (`banjo_renut_store_cards`, on; `banjo_renut_store_cards_verify` hashes
anyway and counts the copies the cards would have missed).

- `tools/store_cards.py` (sa2-nx's copy, credit banjo-nx) runs last in `tools/post_codegen.py`, on the tree and the
  localized copies (app/generated/hot), and is taken out first like the other late rewrites. It leaves preprocessor
  lines alone (this port's localized copies' `Shadow()` sections define the store macros themselves). Codegen of
  2026-10-21: cards on 178,227 D-form, 15,599 X-form, 17,358 vector, 113 dcbz, 8,546 compare-and-swap and 992
  stvlx / stvrx stores; 130,667 stack stores left plain. `REX_STORE_CARDS_OFF` (compile time) makes them no-ops.
- The host writers of guest memory mark their pages: the SDK's CRT memory hooks (`sdk/src/kernel/crt/memory.cpp`),
  `PhysicalHeap::TriggerCallbacks` (file reads into physical memory, decommits, releases), this port's hand-written
  natives (`Card` in `app/src/hot/sasrt_hot_common.h`: memcpy, memset, memmove, the Direct3D constant copies), and
  Renut's memexport write-back. `g_banjo_store_cards` (whether the generated code marks them) is in
  `app/src/hot/sasrt_hot_guest.cpp`, which sees the generated code's macros.

### Renut's render thread, the rest of the console profile (2026-10-21)

The console profile of the 00:30 NRO's race (render thread 100 % busy, the game at 8-10 fps waiting for it): 27 %
`PmullHash` (the store cards above), 29 % vertex conversion (`ConvertVertices` 15 %, `ExpandElement` 14 %), 11 %
`memmove`, the rest spread out. Three keys came from it (all in `tools/renut_patches/sasrt_edits.py`, all on):

- **`sasrt_renut_texture_keep_on_signs`** (`render/textures.cpp`, `BindTextureLocked`). SASRT samples the same
  texture memory with gamma signs (fetch dword 0 `..FE`) and plain ones (`..02`), through fetch constants set without
  `SetTexture` (Renut's header-less keys, `texture_va` bit 0). Renut compared the whole data description, the signs
  included, and retired and made the texture again at every switch: about 60,000 retires in a 3-minute PC race, every
  texture upload a first one (9-37 a frame on the PC; about 217 a frame on the console). The signs are applied when
  sampling (`draw.cpp`, `sasrt_renut_texture_signs`), and `Create` only asks whether all four are "signed" (the
  format's signed variant): a texture whose description differs only in the signs, both or neither all signed, is
  kept. PC race: retires 60,000 -> 13 (each a texture of other data at a reused address), uploads in the race 0-13 per
  300 frames (thousands before); the picture is the same (contact sheets against the run before).
- **`sasrt_renut_vertex_expand_tables`** (`render/vertex_format.cpp`). The diagnostic key
  `sasrt_renut_diag_vertex_formats` (a `[sasrt] vertex conversion in 10 s` line) showed what the CPU expands to floats
  in a race: format 7 (2_10_10_10, signed: the packed normals), up to 4.2 million vertices per 10 s (~140k a frame),
  and a little of format 6 (UBYTE4 blend indices). No host vertex format reads them (plume has no 10:10:10:2 format,
  D3D12 no SNORM one), so they stay expanded, but each component went through `DecodeComponent` (branches on the type
  and a float division). They now come from tables `DecodeComponent` itself filled (8-, 10- and 2-bit fields for each
  of signed / integer: the same floats bit for bit), in a straight loop for the XYZW and XYZ1 swizzles.
  `sasrt_renut_diag_vertex_expand_verify` expands every such vertex again with the decoder and compares: PC race, 36
  million vertices, 0 differ. Since the banjo-nx sync of 2026-10-29 the 8_8_8_8 and 2_10_10_10 cases use banjo-nx's
  own tables (`PackedComponentTables`, the same idea), so the key no longer changes anything (kept for old tomls).
- **`sasrt_renut_stream_cache_follow`** (`render/draw.cpp`) **and a 256 MB stream cache on the Switch** (the biggest
  of the three). banjo-nx's console memory policy holds Renut's converted-stream cache (vertex streams and index
  ranges) to 128 MB (`banjo_renut_stream_cache_mb`); the console's log showed it full from the first race on (the
  PC's race fills about 490 MB without the policy). Full, the cache only lost copies idle for 20 s, so the geometry of
  the track ahead was never cached: converted on every draw, and hashed at every flush by `TrackConvertedStream` /
  `TrackIndices` only for the copy to be refused for room. The PC with the console's policy reproduces it: 5.4-7.0 GB
  of vertex data swapped and 84-101 million normals expanded per 10 s (0.3 GB and 4 million with room), render
  thread 11-17 ms a frame (5-6). The key: a stream or range with no room is not hashed for the cache, and while the
  cache is full the copies no draw read in the last 60 frames go at the 60-frame cleanup (a `[sasrt] stream cache
  full` line each time). At 128 MB that halves the conversions (render thread 5-13 ms); `app/sasrt_switch.toml` now
  sets `banjo_renut_stream_cache_mb = 256`, at which the race never fills it (155-250 MB) and the PC with the policy
  converts what it does without one (render thread 4.6-6.3 ms). The memory comes back from the upload rings, which the
  conversions had grown to 224-256 MB on the console (64 MB on the PC once streams are cached).
  **Retired 2026-10-29** with the banjo-nx renderer sync (`docs/deko3d-renderer.md`, "Banjo sync 2026-10-29"):
  banjo-nx's own cache does both now (no hash of a stream or range at the cap, and
  `banjo_renut_stream_cache_pressure`, on: after copies were refused, the 60-frame pass drops those no draw read for
  60 frames). The key is gone; the 256 MB setting stays.
- **`sasrt_renut_texture_memo_fetch_only`** (on, 2026-10-29, `render/draw.cpp` FillTextures; verify:
  `sasrt_renut_texture_memo_fetch_only_verify`). Found in the banjo-nx sync's first runs: this game binds its textures by
  fetch constant alone, so the device's texture slots hold no header pointer, and banjo-nx's texture memo (keyed by
  the slot's header) and its record-time texture objects never applied: every bound slot of every draw went through
  `BindTextureLocked` (Ryujinx race: 148,561 binds and 0 memo answers per 10 s, before the sync too). With the key, a
  slot without a header pointer is answered by the memo keyed by its fetch words, with the memo's other checks (the
  frame, the binding epoch of the texture's pages, the depth epoch); the words of a per-bind copy (the exponent
  adjust's) stay out of it. banjo-nx's two draw paths keep a draw's texture words while each slot's header is the same
  (`SasrtSlotHeader`: the same zero stand-in for these slots), so a draw that changes no fetch constant keeps them
  without asking the memo. The verify key binds every such memo answer again and compares the words (a 10 s-ish
  `memo answers bound again, N differ` line, the first differences logged).
- **Diagnostics and tests of the night** (all off; `docs/deko3d-renderer.md`, the console faults section):
  `sasrt_renut_pool_wrap_run` (the composed-buffer pool wrap fix, on; off undoes it), `sasrt_renut_diag_late_streams`
  (vertex streams and index data hashed at the draw call, the kick, the replay and the conversion: what the game
  changes before Renut reads it), `sasrt_renut_diag_convert_at_bind` (vertex streams converted at the replay instead of
  the kick's flush, uncached: a test), `sasrt_renut_diag_vertex_formats`, `sasrt_renut_diag_vertex_expand_verify`.
- **Test configurations** (in the SD's `configs/`, made by `tools/make_renut_test_configs.py`):
  `sasrt_renut_stream_cache_128.toml` (the old 128 MB without the key), `sasrt_renut_stream_cache_384.toml`;
  `sasrt_renut_signs_retire.toml` and `sasrt_renut_expand_decoder.toml` turn each off;
  `sasrt_renut_alpha_spec.toml` turns on banjo-nx's `banjo_deko3d_alpha_spec` (on in banjo-nx, off in sa2-nx and here
  because it gave SA2 flat colours in Ryujinx: the console's to say).

### Renut's skinned meshes (2026-10-21; correctness, `tools/renut_patches/sasrt_edits.py`, both on)

- **`sasrt_renut_exports_held`** (`render/draw.cpp`). Memexport results (the GPU-skinned characters and objects) are
  kept on the host for 4 frames after their write-back, and a vertex stream inside one reads them, not guest memory:
  the workers' recorded draws replay a frame after the export, when the game has already cleared that memory for its
  next export (meshes collapsing to the origin). A `[sasrt] vertex streams read from kept export results` line.
  Off: guest memory.
- **`sasrt_renut_baked_fetches`** (`render/draw.cpp`, `guest/resources.h`, `render/vertex_format.*`). A vertex shader
  the package holds as `D3DVertexShader_Bind` left it (1,118 of the package's 2,007 vertex inputs name a format and a
  stride) already exchanges the pairs of its 16-bit data in its fetch swizzles; Renut swapped them back on the CPU as
  well. For such a shader, its 8in16 elements (FLOAT16, SHORT) are converted as the stream's 8in32 fetch leaves them:
  a declaration per set of bound locations, built once, with the same host formats and pipelines and its own stream
  cache key. Fixes the race's octopus (a ball of spikes: its blend weights met the wrong bones; PC RenderDoc: 3,000
  long triangles -> 0), the generic skinning shader's blend weights (the characters) and a race mesh's normals,
  tangents and texture coordinates. A `[sasrt] baked fetches` line per changed declaration (the first 24). Off:
  swapped back for every shader. Details: `docs/deko3d-renderer.md`, the console faults section.
- **Test configurations:** `sasrt_renut_baked_fetches_off.toml`, `sasrt_renut_exports_held_off.toml` (the SD's
  `configs/`, `tools/make_renut_test_configs.py`) show each fault again for comparison.
- **`sasrt_renut_constant_f4_pending`** (on; `app/src/renut_engine/sasrt_renut_hooks.cpp`, found through
  MarathonRecomp-NX, which implements the same call). `D3DDevice_BeginShaderConstantF4` (`sub_82CC2108`, Sonic '06's
  `sub_825466E8` in shape) gives the game pointers into the device's constant shadow and the ring and clears the range's
  pending bits; a worker's recorded draw takes only pending groups from its own device and inherits the rest from the
  title device at the replay, so constants set this way would come from the wrong device. The hook sets the bits again.
  Not seen called in the races tested so far (a `[sasrt] D3DDevice_BeginShaderConstantF4 used` line names the first
  call); `tools/direct_calls.py --redo` makes its one caller (the thunk `sub_824938A0`) reach the hook.

### `sasrt_renut_frames_ahead` (2026-10-21; 0 on the console, 1 on the PC)

How many frames the game may run ahead of Renut's render thread (`backend/render_thread.cpp`, QueueFrame's wait;
`sasrt_renut_diag_no_frames_ahead` still forces 0). The user's console run with the game waiting at its Swap until the
render thread has done the frame (the diagnostic config of 2026-10-20): the race at 30 fps (16-18 one frame ahead), 0
frames late, the render thread 16-22 ms a frame (38-44), the upload rings' churn about 0.6 GB per 10 s (4.2-4.9 GB), input
to screen 24 ms (78), and most of the skinned meshes' explosions gone. One frame ahead, the game rewrote data before the
render thread read it: stale copies converted again and uploads redone, which made the render thread later still. As
MarathonRecomp-NX's Present waits until the render thread has recorded the frame. `app/sasrt_switch.toml` sets 0;
`configs/sasrt_renut_frames_ahead_1.toml` goes back. Two configs that add render-thread work
(`sasrt_renut_capture_streams`, `sasrt_renut_store_cards_off`) made the explosions worse, the same story.

### `sasrt_renut_texture_int_format` (2026-10-21; correctness, on; every back end)

The user's complaint, on the console, in Ryujinx and on the PC alike: the dark parts far too black (the loop's road
dark navy where the sky is bright, the start gate's pillars black silhouettes), with flickering as the car moved
between sun and shade. The emulated GPU, used as the reference, draws the same, so every comparison against it
agreed. PS3 footage of the same intro flyover settled it: the pillars are light grey stone there.
- *Cause:* the track's GI pass (`ps_ed0a8d53da14a749`) reads three lighting volumes (`gGILight0`-`2`, 32x8x32
  k_16_16_16_16, linear, 8in16) whose fetch constant asks for the integer number format with an exponent of -10: the
  hardware returns the raw 16-bit integers times 2^-10 (0..64), which the shader recentres by -32 into L1 lighting
  coefficients (each volume an axis's RGB plus one channel's base term). Read normalized (0..1, times 2^-10) they come
  out near -32 and the GI adds nothing: no ambient light anywhere the sun does not reach. The emulated GPU ignores the
  number format too (its texture cache's comment asks for multipliers "if any game is seen using num_format 1").
- *Fix:* the key existed since 2026-10-20 (off, because it did not match the emulated GPU): on now. The volume's scale
  (exponent plus 16 bits) is a power of two in the descriptor index (bits 20-25) that the shaders apply
  (`renutExpScale`), also through deko3d's stacked 2D-array path (Ryujinx run gi_ryu_1: "texture scale 2^6 ... stacked
  true"). PC A/B: `out/pc/captures` video_210s/212s (race), video_103s/104s (intro flyover). The user judged it
  accurate. Diagnostic of the hunt: `sasrt_renut_diag_dump_volumes` (each 3D k_16_16_16_16 texture's guest bytes and
  host rows next to the executable).
- Config: `sasrt_renut_gi_normalized.toml` (the black shadows back).

### `sasrt_deko3d_depth_resolve` (2026-10-21; deko3d's rule, on; the console only)

Taken first for the race's flickering black ground on the console (the ground black with bright specks inside
straight-edged areas, the driver a black ball). The user's next console run (19:31, the decompression ran ~10 times a
frame) showed the same: that was the GI above, on every renderer. Kept, as deko3d's rule for sampling a compressed
depth image:
- *How the game shadows:* three cascades a frame, each drawn into one 1024x1024 depth target and copied by a draw into
  its third of a 1024x3072 float texture that the scene samples (RenderDoc of a PC race frame, `tools/rdc_passes.py`).
- *Cause:* banjo-nx's `banjo_deko3d_depth_compression` gives depth targets the GPU's hardware compression, and nothing
  decompressed them before the copy read them. Maxwell's texture unit cannot read compressed depth tiles: deko3d's
  `dkCmdBufResolveDepthValues` (NVN's `nvnCommandBufferResolveDepthBuffer`) is the step for that; it writes command
  0x8001047F, Maxwell's `DECOMPRESS_ZETA_SURFACE` with Z on (libdeko3d disassembled). Flat ground seen from the sun is
  what the hardware compresses best, so the cascades over it read garbage. Ryujinx emulates no compression.
- *Fix:* plume's deko3d back end (`Deko3DOptions::depthResolve`) decompresses a compressed depth target while it is
  still bound: when it moves to a read layout (sampled, copied, resolved), when another depth target or none is bound
  (a texture barrier follows), and at the end of a command list; written again while bound (a barrier back to
  DEPTH_WRITE, a depth clear), it is decompressed again before the next read. About 11 a frame in a race (Ryujinx run depthres_1);
  the compression's bandwidth saving stays.
- Configs: `sasrt_deko3d_depth_resolve_off.toml` (the fault back), `sasrt_renut_depth_uncompressed.toml`
  (`banjo_deko3d_depth_compression` off: nothing to decompress, the other cure, more GPU bandwidth).

### `sasrt_renut_resolve_readback` (2026-10-30; correctness, on; every renderer path of Renut)

The race start's Ristar, on his disc above the starting line, was black on the console, on the PC and with the
emulated GPU, where the 360 shows him bright yellow. The traced cause:
- **His material:** pixel shader `21601CF1FD53537E` (`gColourMul`, `gToneReflParams`, `gITMGF`...). With
  `gToneReflParams.x` = 20 it stores its colour times `gITMGF.x` in the colour buffer. The deferred lighting pass adds
  that colour back as light. 41 other shaders divide by `gITMGF.x`; 107 use it.
- **The value:** `gITMGF` is c146 of the camera buffer (`cbViewProjection`: c131-c146). It was 0.05 for every object,
  every frame. A write watch on the buffer found the writer: `sub_82747610` stores the tone mapper's value. The tone
  mapper `sub_827A0A20` locks a texture (D3D Lock/Unlock: `sub_8244bd40` / `sub_824096e0`) and computes
  `gITMGF.x = 2.5 * (L + 0.01) / key`, where L is the float it reads there.
- **Why L was 0:** that texture is a 1x1 `k_32_FLOAT` resolve of the scene's average luminance. Renut's resolves stay
  on the GPU (nothing was written back to guest memory), so the CPU read 0 and the factor came out 0.05. With the
  real luminance it is about 2.5, so the glow is now about 50 times brighter. The emulated GPU was dark too: it does not
  read resolves back by default either.
- **The fix:** a resolve into a 1x1 32-bit float texture also copies its texel to a small readback buffer of the frame
  slot (`SasrtQueueResolveReadbackLocked`). When the slot's fence is waited, with that slot's memexport results, the
  texel is written to the texture's guest memory, big-endian, as the CPU's `lfs` reads it
  (`SasrtCompleteResolveReadbacksLocked`). That is one or two frames later; the tone mapper reads a texture of its
  ring a frame behind. The race's 1x1 luminance chain is about five such resolves a frame, one 4-byte copy each.
- **What changes:** only the glow of emissive materials (`gITMGF` users). The race's overall brightness and the
  camera fades measure the same (PC A/B, `video_112s` against `video_115s`).
- **Diagnostics used:** `sasrt_diag_ps_constant_watch` (a pixel constant register: each upload through the native
  constant writer `sub_82CC2368` logs its value and source). `sasrt_diag_ps_constant_watch_writes`, the PC only: x86
  data breakpoints on the watched register's source buffers, logging each writing instruction with its stack as
  recompiled function names and generated source lines. `sasrt_renut_diag_ps_constants` now also logs c0-c7, c142-c146
  and c254.
- Config: `sasrt_renut_resolve_readback_off.toml` (Ristar black again).

### The far-shadow flicker's console tools: `sasrt_deko3d_color_compression`, `sasrt_renut_diag_shadow_dump` (2026-10-30)

- `sasrt_deko3d_color_compression` (on, as always): colour render targets get the GPU's hardware compression
  (`DkImageFlags_HwCompression`; plume `Deko3DOptions::colorCompression`). The all-safe config turned off every
  other console-only feature and the far-shadow flicker stayed. Colour compression was the last one no config could
  turn off, and the shadow atlas and the shadow mask are colour targets. Ryujinx emulates no compression. Config:
  `sasrt_deko3d_color_uncompressed.toml`.
- `sasrt_renut_diag_shadow_dump = "<first s>,<every s>,<windows>[,<frames>[,<address>...]]"` (diagnostic, off): for
  `<frames>` (8) consecutive game frames at each time mark, it writes to `shadow_dump/` next to the NRO:
  - each depth resolve's float result: the three cascades' regions of the 1024x3072 atlas (4 MB each), and the scene
    depth `B5640B28`;
  - each 1152x544 8-bit colour resolve (2.5 MB each): the G-buffer (`B5640CA8`, `B5640D28`, `B5640DA8`), the shadow
    mask `B5640E28` (the same in all four channels: white, black where shadowed) and the lit scene (`B5642E28`, again
    as `B5642D28`).
  With addresses (hex, as the files are named) only those resolves. Each is copied to a readback buffer of its own
  after the resolve. When the slot's fence is waited, the render thread copies it to memory and queues it, and a
  writer thread writes each file with one `fwrite`. The thread comes from `banjo::renut_gpu::StartLongLivedThread`, a
  pthread on the console, where `std::thread` throws "Function not implemented"; a `std::thread` writer ended the first
  console run at its first file. The render thread waits for the writer only when 48 MB are
  queued, for up to 3 s; after a wait that long it drops the rest of the window. The log has the files queued and
  dropped per frame and the writer's MB/s. The first version (2026-10-30 morning) wrote every resolve from the
  render thread a row a call: 76 s for one frame's 30 MB on the console's SD card, a hang after the second frame. `tools/shadow_dump_view.py <folder>` makes one sheet per resolve (the frames side by side,
  their differences below) and `stats.txt` (per frame: mean, share at 1.0, mean difference from the frame before). PC
  baseline (race, 180 s): the cascades change by 0.0003-0.012 from frame to frame. Config:
  `sasrt_renut_shadow_dump.toml` (`"30,30,10,8,B5640E28,B5642E28,B5640B28"`: the mask, the lit scene and the scene
  depth, 8 frames every 30 s from 30 to 300 s after the first resolve, 60 MB a window, 600 MB in all).

### The far-cascade shadow flicker's A/Bs: `sasrt_renut_depth_resolve_wait` (2026-10-30; the deko3d renderer only)

**Update, the same night:** `2` did not end the flicker on the console (newlogs8, 15 A+B+X+Y windows; the shadows of
the palm and the wall over the road gone in a frame, back in the next). The atlas dump's clean run was weaker evidence
than it looked: the flicker shows only in some places, and its timed windows may simply have missed them. The key's
default is now 0, and it has two more values: `3` copies one texel and `4` copies the whole region of each depth
resolve into a scratch buffer, through plume's readback copy: `DkBarrier_Full` and the texture cache dropped
before it, `DkBarrier_Full` and the L2 cache dropped after it, as the atlas dump did. Configs:
`sasrt_renut_depth_resolve_wait_idle` / `_full` / `_texel` / `_copy.toml`, and `sasrt_deko3d_compression_off.toml`
(depth and colour targets both uncompressed: each alone kept the flicker, both together never ran). Diagnostic:
`sasrt_renut_diag_shadow_dump_late = "B5640EA8@B5640E28"` copies the shadow atlas whole right after the shadow mask's
resolve in a dump window. That shows the cascades as the shading read them, with no copy between the cascades
(`sasrt_renut_shadow_dump_late.toml`). A bad frame with whole cascades puts the fault in the light-volume shading;
cascades missing their casters put it in the shadow pass. The original text follows.

The console's dumps (`sasrt_renut_diag_shadow_dump`) found the shadow mask itself wrong in some frames: acne and
coarse steps under the rock overhangs, the far road black, or the bridge's far shadow gone. With the shadow atlas
dumped as well, no frame was wrong. Dumping the atlas puts a readback copy after each cascade's depth resolve, and
plume brackets such a copy with `DkBarrier_Full` (the GPU drained) and the texture cache dropped.

The three cascades are rendered one after another into one depth target. After each one, a draw (`ResolveDepth`)
copies the target into its region of the 1024x3072 atlas, and the target is cleared and drawn again. Between the copy
and the clear, plume recorded only deko3d's fragment barrier (`DkBarrier_Fragments`). On the console, a cascade's
copy took in some of the next cascade. Ryujinx never runs two draws' work at once, so it never showed this.

- `sasrt_renut_depth_resolve_wait = 2` (the default at first, now 0): after each depth resolve draw,
  `DkBarrier_Full` with the texture cache dropped. That is 4 a frame (3 cascades and the scene depth).
- `1`: `DkBarrier_Primitives` (wait for idle) with the texture cache dropped, a cheaper form.
- `0`: off, as before (the flicker). Configs: `sasrt_renut_depth_resolve_wait_off.toml`, `_idle.toml`.

The console A/Bs for the mechanism, each with the fix off, in plume's `Deko3DOptions`:
- `sasrt_deko3d_read_wait`: every texture moving to a read layout (rendered, then sampled) waits for idle and drops
  the texture cache with its own invalidate (method 0x1288). The default is deko3d's fragment barrier with the tiled
  cache's invalidate (0xF74).
- `sasrt_deko3d_write_wait`: every texture moving to a write layout (sampled, then rendered or cleared again) waits
  for idle instead of the fragment barrier.
- `sasrt_deko3d_clear_wait`: the GPU waits for idle before each clear.

Configs: `sasrt_deko3d_read_wait.toml`, `sasrt_deko3d_write_wait.toml`, `sasrt_deko3d_clear_wait.toml`. Whichever of
these also ends the flicker names the hazard. The others cost a wait at every transition or clear, so they stay off.

Three more console A/B groups (configs only, `tools/make_renut_test_configs.py`), for the console-only differences
outside the GPU's barriers:
- `sasrt_flicker_shaders_plain`: banjo-nx's uam passes (PRMT, value numbering, no reconvergence around uniform
  branches, wide rows) and shader specialisations off, with no generic variant drawing while a variant compiles.
  Real Maxwell needs the SSY/SYNC reconvergence the uniform-branch pass drops; Ryujinx rebuilds control flow
  itself, so it would never show that pass misjudging a branch.
- `sasrt_flicker_submit_whole`: no kicks (each frame to the GPU whole at the present), no recording worker, no
  ring cleaner thread.
- `sasrt_flicker_caches_state` / `sasrt_flicker_caches_data`: Renut's caches that skip work they judge unchanged.
  The console's A57 reorders memory accesses; Ryujinx's x86 host does not, so a missing barrier between the game
  thread's writes and the render thread's checks would show only on the console. Both halves together ran a
  Ryujinx race at a sixth of the speed, hence two halves.

### The shading draws' bindings in the dump windows: `sasrt_renut_diag_light_volumes = -1` (2026-11-03; diagnostic)

The user's console run of `sasrt_flicker_fix_all.toml` (newlogs9: every GPU and CPU candidate off at once, 16 A+B+X+Y
windows with the atlas copied after the mask) kept the flicker, and its dump says where to look next: in windows whose
camera barely moves (w10, frames 2785-2790; w15) the shadow atlas and the scene depth change by the frame's small
motion, yet the mask's shadow coverage swings in every distance band (under the car 12 % <-> 24 % dark; the 19-30
band of w15 3 % -> 25 % -> 1 % -> 13 % -> 67 %), where the PC's holds within a point or two (its own A+B+X+Y dump,
out/pc/shadow_dump_look). So the shading pass computes differently from near-identical atlas and depth, and not in one
cascade or ring. What else it is given is what no config switches: the texture slots as bound, the stencil state the
spheres mark with, the alpha test and the shared words. `sasrt_renut_diag_light_volumes = -1` logs that:
- the light-volume log's window is the shadow dump's A+B+X+Y window (the same game frames as the dumped files, so each
  frame's lines pair with its mask);
- each light-volume draw's line (the marking spheres without a pixel shader too) adds the device's depth control,
  hi-z, clip, mode and colour words, the stencil bytes (+0x2900-0x2903, +0x28FC-0x28FF), the shared block's alpha
  test, FLT_MAX, depth remap, target scale and the pixel booleans, and for texture slots 0-3 the guest address, the
  descriptor index, the sampler word and the host texture that index names at the draw (its guest address, size,
  host format, slot, whether a resolve target, GPU- or CPU-written, its resolve count and description words 0-2);
- the shadow casters' lines as before;
- always on: a resolve destination made again (`ResolveTarget`: its target flag, description, texture, format, scale
  or size no longer those of the last resolve) is logged with the reason, the first 64 and then every 1,024th
  ("[sasrt] resolve destination ... made again").
The PC run that proved the log (sasrt_670, out/pc/shadow_dump_look) showed the scene depth bound through two host
textures on alternate frames (slots 173 / 18, later 223 / 16), both resolve targets written by the GPU; with one
host texture per address that means the destination is made again every frame, which the next run's line will say.
Reading it: a bad frame whose lines equal a good frame's puts the fault in the GPU's execution of the same commands
(the shader's compiled code, the hardware); a line that differs names the stale binding or word.
- Config: `sasrt_flicker_bindings.toml` (the fixes off as in `sasrt.toml`, the key, the atlas copied after the mask).

### `sasrt_strip_markers` (2026-11-03; correctness, on; from rr6-nx's `rr6_strip_markers`, credit rr6-nx)

Ridge Racer 6's port found a deko3d-only fault in Renut's range draw path (`PrepareGeometry`, render/draw.cpp) and
fixed it; ported here as it is, under this port's key. An indexed strip's restart marker (0xFFFF in a 16-bit index
buffer, D3D's strip cut) was taken into the draw's vertex range as vertex 65535: the range became the buffer's whole
tail (65536 vertices converted a draw), `max_index` past 0xFFFE made the host indices 32-bit, and a 32-bit index
buffer restarts only at 0xFFFFFFFF on deko3d and Vulkan, so the strip ran on through every cut and the cut's vertex
(65535 - lo) read past the copy: zeros, a triangle to the object's origin (Ridge Racer 6's wedges across the sky and
torn meshes). Direct3D 12 cuts at 0xFFFF whatever the width (plume's IBStripCutValue), so the PC never showed it. The
whole-buffer path (`WholeIndexCopy`, `banjo_renut_whole_buffers`) keeps the guest's 16-bit indices, so the fault lasted
only until a mesh's whole copy existed: a frame or few after each camera cut in Ryujinx, longer on the console, which
makes those copies slowly and refuses them under memory pressure; that is why it looked like a late read there.
- *Fix:* for a line or triangle strip whose highest index is the guest's marker, the markers are left out of the range
  (lo and hi rescanned without them), and before the rebase each marker is rewritten to `lo + host marker`, so the
  rebase leaves the host format's marker (0xFFFF for 16-bit host indices, 0xFFFFFFFF for 32-bit ones on deko3d and
  Vulkan, 0xFFFF on D3D12). The cached copy (`TrackIndices`) is rebased from the same indices. A "[sasrt] strip with
  restart markers" line counts such draws (the first 8, then every power of two): this game has about 115 indexed
  strips a frame (deko3d-renderer.md); whether they carry markers the next logs say.
- *Why it may matter for the far-cascade shadow flicker:* a draw takes the range path whenever its whole copy does not
  exist; on the console the stream cache sits full and drops copies unused for 60 frames, so a draw can alternate
  between the whole path (right) and the range path (the fault) from frame to frame: console-only, not timing, immune
  to every barrier key. `sasrt_flicker_fix_all` had `banjo_renut_whole_buffers` off (every draw on the range path),
  which fits "the flicker still there". Settled by the next console run.
- Config: `sasrt_strip_markers_off.toml` (the fault back).

### `sasrt_renut_resolve_target_pages` (2026-11-03; on; the far-cascade shadow flicker's candidate)

The user's console run of `sasrt_flicker_bindings.toml` (newlogs10: 12 A+B+X+Y windows, 95 frames of shading draws
with their bindings) settled what the shading draws are given: in every bad frame the same state words, the same
alpha test, the same noise texture (slot 18) and atlas (slot 3) as in the good frames around it, and the scene depth
through a host texture that rotates among a few slots in good and bad frames alike (the recreation below). The
depth hand-over never applied (its counters 0). So the GPU gets the same commands and computes different masks, and
the one object new in every frame of that pass is the scene depth texture, made again each frame by `ResolveTarget`
(next section). This key keeps it:
- *Fix:* a destination whose new description differs from the last resolve's only in dword 1's base page (the format,
  size, tiling, mips and dimension the same) keeps its host texture and takes the description; the page's entries in
  `g_resolve_targets` and `g_depth_words` are set as before, so the current page's binds find it. A read of the other
  page finds no destination (a texture from guest memory, as before). Counted by "[sasrt] resolve destination ...
  kept across its base pages".
- *What it saves on the console:* per frame a 1152x544 R32F image, its words twin and framebuffer, the lit scene's
  1152x544 image, the downsample chain's, their descriptor slots freed and taken, and the heap churn of all that.
- Config: `sasrt_renut_resolve_target_pages_off.toml` (made again every frame, as before).

**The user's run of that build (2026-11-03, 23:30): the flicker stayed** with the destination kept (16 "kept across
its base pages" lines), so the recreation was not it either; the key stays for what it saves. With every input the
CPU hands the shading draws proven the same, the light-volume pass's own algorithm is what is left. Decoded from the
bindings log (PC frame 4845 of sasrt_670): per ring, a sphere draw with no pixel shader marks the stencil (test ALWAYS,
depth test GEQUAL with no depth write, REPLACE 1 on depth fail), a second sphere draw unmarks with REPLACE 0, and the
shading draw (stencil EQUAL 1, write mask 0, no depth test) shades the shell between them; rings go so that nearer
shells overwrite farther results (the far ring is shaded first over everything within 298 units, then 14.5, 50.6 and
289 with the blends between). A wrong mask is therefore either a wrong shell (the sphere's depth-fail test against the
scene depth target, or the sphere geometry) or wrong shading inside a right shell (the shader's reads), and the final
mask cannot tell them apart.

### The mask after each ring: `sasrt_renut_diag_shadow_dump_passes` (2026-11-03; diagnostic)

In a shadow dump window, the colour target is copied out after each light-volume shading draw (660 indices, a pixel
shader; both draw paths): files "w<window>_f<frame>_<serial>_pass_<draw number>_...". A bad frame then shows which
ring's draw first differs from the good frame beside it and whether its change lies inside its shell (shading) or
outside it (stencil). The copies add a barrier between the rings; if the fault vanishes under them, that is itself a
finding (an ordering fault inside the pass, which no key covers: the rings share one framebuffer and get no barrier).
- Config: `sasrt_flicker_passes.toml` (the bindings run plus this; about 20 MB more a frame).
- Checked on the way (the user asked whether deko3d's source would show the fault): the stencil state reaches deko3d
  with both face sets (plume sets both; `pipeline.cpp` copies the front ops to the back when the 360's back-face
  stencil is off), and deko3d's `dkCmdBufBarrier` (source/maxwell/gpu_base.cpp) emits a 3D FragmentBarrier for
  `DkBarrier_Fragments`, WaitForIdle for `Primitives`, and a GPFIFO reference plus NoPrefetch split for `Full`; the
  Image flag invalidates the texture data cache. What FragmentBarrier itself waits for is the hardware's, not in
  the source, and the console runs with full waits everywhere (`sasrt_flicker_fix_all`) flickered the same, so the
  barrier semantics are not where the answer is.

### The far-cascade flicker, newlogs11 (2026-11-04): the inputs are a frame apart, the GPU draws them right

The capture of `sasrt_flicker_passes.toml` (6 A+B+X+Y windows, the mask after each ring's draw) was read whole.
What the mask pass is (from the logged draws, `scratch caster_vs_shading.py` and the pass files): a screen-space
draw (D44C, depth write), then per ring a sphere draw marking stencil 1 (REPLACE on depth fail, ref 1), a sphere
draw unmarking the previous ring (ref 0), and a full-screen shading draw where stencil is 1. The spheres have one
radius per cascade band (18.6 / 65 / 373 units at 372.9) and centres walking down the view axis (6.2, 10, 22, 35,
125, 199 units), so each shell is a band of view depth; the first shading draw (ps 9041) covers the near sphere,
not the far one, and the far band is the sixth (ps 453E). The 9041/C805 and 14C8/40BB pairs are the same bands
shaded with the cascade below and above (c16-c18 and c20-c22 carry two cascades; |c16| 0.027 near, 0.008 middle,
0.0013 far). The passes 1, 3 and 5 are byte-identical to 0, 2 and 4 in most frames: the second shader of each pair
changes nothing there.

The software model (`soft_match2.py`: view position from the scene depth as 0.25/z through the sphere draw's
projection, c16-c18 to the atlas, u over 1024 and v over the whole 3072 rows, the game's bias c13, four point taps
compared then weighted) reproduces 93-98 % of the pixels each console draw darkened, in every frame tried. The
console's GPU, then, draws exactly what its inputs say. The flicker frame of window 4 (f2661, a solid black wedge
over the near track that the first draw painted and the next frame has not) is the model's too: the near cascade's
stored ground depth is 0.0002-0.0003 nearer the light than the receiver depth the shading computes, past the bias,
so the ground shadows itself. That is what a 6-8 texel offset between the cascade's render matrices and the shading
matrices gives on sloped ground (the stored plane's gradient is 3e-5 per texel); the same test in the steady window
w1 gives 0.2-0.6 texel on the console and on the PC's captures (sasrt_670, `plane_fit.py`). The depth hand-over
counters are 0 on this game (the resolve is always drawn), no depth resolve was skipped, the clears are skipped on
both platforms alike, and the "shadow caster" lines of the diagnostic only ever logged the first six draws into the
cascade target, which are screen-space quads (c0 = 2^23, c1-c3 zero), the same every frame on both platforms. The
meshes and the billboards (vs D44C, 2328, F149) read constant groups 32, 34 and 35 (c128-c131: a view-like matrix,
c136-c143: the cascade's projection terms; c0-c3 stay as the device had them: a first version of this change that
looked for a 4x4 in c0-c3 logged nothing, PC sasrt_675; sasrt_676 shows the lines). The diagnostic now
logs the first six casters whose shader reads a group past 1, with the registers of its first two such groups, so the
next capture compares the atlas's matrices with the mask draws' frame by frame.

Candidates left, all console-only ways per-draw state reaches the renderer, each as a toml of
`tools/make_renut_test_configs.py` (`sasrt_direct_state_off`, `sasrt_direct_flush_off`, `sasrt_me_native_plain`,
`sasrt_clear_repeat_off`; docs/switch-testing.md 2026-11-04). The scratch scripts of the analysis (the session
scratchpad: `soft_match2.py`, `plane_fit.py`, `pair_test.py`, `caster_vs_shading.py`, `ring_passes.py`) read the dump
folder and the log by frame label; a frame's label drifts against the render stream (the game thread's counter is read
on the render thread), so a window's depth file can carry the next label: pair by stream order, not label.

### `sasrt_renut_splice_ended` (2026-11-04; correctness, on; the far-cascade shadow flicker's cause)

This game never calls `D3DDevice_RunCommandBuffer`: a worker thread records parts of the frame (the shadow pass among
them) into D3DCommandBuffers, the main thread splices indirect-buffer packets to them into a composed buffer
(`sub_82CEF770`), and the composed segment goes to the ring submission (`sub_82CDE200`) about a frame later, where
Renut replays the recorded draws. Since 2026-10-21 the splice took each recorded buffer's recording "as it was at the
splice" (at the submission, a worker could already be recording the next frame's into the same buffer: the "ocean"
frames). But the 360's GPU reads the buffer only at the submission, and the main thread lays the composed buffer out
while the worker is still filling the buffers it names, so at the splice the worker's shadow pass may not have been
begun again since the previous frame, or be half recorded. Taken then, the replay drew the shadow atlas from the
previous frame's recording while the mask pass (the main thread's recording) had this frame's matrices: the ground's
stored depth sat a few ten-thousandths nearer the light than the receiver depth (a 6-8 texel offset on sloped ground,
past the game's bias) and shadowed itself in solid patches that came and went with the worker's timing: newlogs11 w4
f2661, reproduced in software from the dumped atlas and constants (the GPU draws what it is given). The console's
slower worker loses that race far more often than the PC's.

Now a recording carries whether the game's `EndCommandBuffer` ran for it and whether a splice took it. A splice takes
a recording only once ended and not taken before (a buffer not recorded again since its last splice still holds the
previous frame's); one still being recorded, or not recorded again yet, is left and taken at its End (`sub_82CEFA78`,
before the original clears the device's command-buffer field), and a recording ended after the splice but before the
segment's submission replaces the one taken, as the GPU would read it. A splice still unresolved at the submission is
taken as it is then (the behaviour before; right for a buffer the game runs again without recording it again). The
10 s "Renut hooks so far" line counts the splices by state (taken ended / left still being recorded / left taken
before and not recorded again / without a recording), the ends that resolved or replaced one, and the submissions
that took one as it was. On the PC (sasrt_677, before the taken-before state existed) every one of ~4,000 splices
found an ended recording: the worker is always done by the splice there, which is why the PC never flickers; the
console's counts will say how often it is not. Off: `configs/sasrt_splice_ended_off.toml` (the
flicker should return). Found with the dumps of 2026-11-03/04 (the section above) and the game's command-buffer flow in
`sasrt_renut_hooks.cpp`; unverified on the console at the time of writing.

Also from the same morning: devkitPro's debug deko3d (`PLUME_DEKO3D_DEBUG`, the Ridge Racer session's suggestion,
run in Ryujinx) refused the SharedConstants pushes for a uniform buffer size of 1424 bytes (DK_UNIFORM_BUF_ALIGNMENT is
256), and, once that was rounded, the float constants' pushed buffer for 4112 (256 registers and the zero row,
`kFloatConstantsUboBytes`; the pushed buffer's stride was the rounded 4352 already, which the pushes and binds pass
now). The release library rounds both up itself and the buffers are allocated rounded, so the hardware saw no
difference. The debug library reports only the first refused input and then traps the calling thread
(`dk_device.cpp` RaiseError, the Ridge Racer session's reading), so each such size stopped the emulator run at boot
with one message: "nothing else" after a message means nothing *before* it, and the run is repeated after each fix
until the race renders. Procedure: `cmake -DPLUME_DEKO3D_DEBUG=ON out\nx`, build, `tools\win\ryujinx_run.ps1 -Name
<n> -Seconds 460 -InputScript tools\win\input\race_ryujinx.txt`, grep `out\ryujinx\<n>.log` for "deko3d says", then
`-DPLUME_DEKO3D_DEBUG=OFF` and build again before packaging. With both sizes rounded, a 460 s run (deko_debug3:
boot, menus and about two minutes of a race, 31,657 replayed draws per 10 s at the end) produced no refusal and no
guard-byte failure: everything this port asks of deko3d passes its input checks, the Ridge Racer port's result too.
Whatever is console-only from here is the hardware's behaviour below those checks, or the data (the splice above).

### `sasrt_deko3d_copy_wait` (2026-11-04; correctness, on; the deko3d renderer only)

From reading deko3d's source (`maxwell/gpu_base.cpp` dkCmdBufBarrier, `dk_image.cpp` dkCmdBufCopyImage,
`maxwell/gpu_transfer.cpp` BlitCopyEngine) for the flicker: image copies and buffer-to-image uploads run on the copy
engine, apart from the 3D engine, and the only barrier that waits for it is `DkBarrier_Full` (a GPFIFO reference and
a split with prefetch off); `DkBarrier_Fragments` and `DkBarrier_Primitives` drain the 3D engine only. plume emits
Full for a copy-stage barrier, and Renut's layout moves declared the copy stage only when entering a copy layout (the
full barrier before an upload, right for the 3D engine's earlier reads). Leaving one, an uploaded texture moved to
SHADER_READ with the graphics stage: a fragment barrier, so the draw after an upload could sample the texture while
the copy engine was still writing it. The console's 10 s lines count 42-258 first uploads per 300 frames in a race
(streamed textures, 4,667 level uploads per 10 s) and up to 265 dynamic ones per 300 frames in the menus; in a race
the dynamic count is 0, so the mask pass's CPU-written 32x32 noise texture is not rewritten then. Ryujinx runs the
engines in order, so it never showed: a glitch on a streamed texture's first frames would be the console's symptom.
Now a texture or render target leaving a copy layout on deko3d moves with the copy stage too (plume: a full barrier
with the texture cache dropped). Cost: a full barrier per upload or copy before its first use (about one a frame in a
race here). Off: `configs/sasrt_deko3d_copy_wait_off.toml`. Not the acne of the section above (that is the atlas a
frame behind), but a second way a frame could read stale texels on the console only.

Read in the same pass and found in order: `dkCmdBufBarrier` (Tiles / Fragments / Primitives = 3D-engine waits with
the texture cache dropped, Full = the GPFIFO reference), `BindDepthStencilState` (`state.mme`: both faces' ops and
functions from the 8-byte state; `dkCmdBufSetStencil` writes ref, mask and write mask per face, plume giving both
faces the front's as Direct3D 12 does; the mask pass's spheres cull their back faces anyway), Zcull
(`ConditionalZcullInvalidate` drops the data only when the depth target's address changes, and `zetaType` is always
2: no stencil in Zcull, so the stencil marking is not Zcull's to cull; the software model's 93-98 % matches say the
shells were marked whole), the viewport depth transform (`isDepthOpenGL` halves the range; Renut uses the zero-to-one
mode), and `dkCmdBufSetDepthBias`, which doubles the constant factor on the way to `PolygonOffsetUnits`: a game depth
bias in the caster pass would be twice the PC's on the console, a constant offset (peter-panning), not a flicker;
whether this game sets one for its casters is not logged (the caster lines carry the clip control only).

### The casters' matrix in the worker buffers' own PM4: `sasrt_renut_diag_splice_pm4` (2026-11-04; diagnostic)

The console run of the splice fix (11:05) counted every splice as "taken ended" and none left: the worker's recording
is whole and fresh at the splice on the console as on the PC, so `sasrt_renut_splice_ended` is a no-op and the atlas's
one-frame lag is not a stale recording. What the GPU executes is the buffer's PM4 at the submission, and the ring-side
work had found that Direct3D patches the packets of the command buffers it runs from inside a segment after the draw
call returned (the note on `sasrt_direct_state_nested`: "the ring's check finds every one of them different"); Renut's
recorded draws carry the device as it was at the worker's draw call and never see those patches. This diagnostic reads
the vertex constants c128-c131 (the casters' view-like matrix, the registers the mesh casters read) from each spliced
buffer's own PM4: the indirect-buffer packets the composer wrote between the composed buffer's write pointers name the
buffer's range; its type-0 runs, SET_CONSTANT, SET_CONSTANT2 / SET_SHADER_CONSTANTS and LOAD_ALU_CONSTANT (the data in
memory) are followed and the last write of each word kept. The values are logged at the splice (the first 48) and read
again at the segment's ring submission, "the same" or "DIFFERS" with the new values (every difference logged, up to
200); the recorded snapshot's values are the frame's "shadow caster" lines (`sasrt_renut_diag_light_volumes = -1`).
The 10 s "Renut hooks so far" line counts the buffers searched, those with c128 found and those differing. Config:
`sasrt_flicker_pm4.toml`. If the console shows differences where the PC shows none, the fix is to replay the worker's
draws with the constants the PM4 holds at the submission (or to capture them then), not the record-time device.

### Replay tags on the resolves (2026-11-04; diagnostic, always kept, printed with `sasrt_renut_diag_light_volumes = -1`)

Every resolve destination (the scene depth, the atlas, the mask) now remembers which replayed recording wrote it:
the spliced buffer, its recording id and the swap counts at the recording's Begin, End and the segment's submission
(`HostTexture::sasrt_tag_*`, set in ResolveStateLocked from `g_sasrt_replay_tag`, which QueueRunCommandBuffer /
QueueCapturedRun set before each run's Replay). The light-volume lines print, per bound texture, that tag beside the
shading draw's own ("own tag buf .. rec .. swaps b/e/s"), and the caster lines theirs. A frame whose atlas (t2) or
scene depth (t0) came from a recording of another swap than the mask draws' shows directly, with which thread's
recording lags: the one answer the dumps could not give (their labels drift against the stream). On the PC the three
tags of a mask draw are expected to share the submission swap.

The segment census (`sasrt_renut_diag_splice_pm4`, first eight submissions): the composed segment's packets by type
and opcode with their first words, since no indirect-buffer packet was found in any submitted segment on the PC
(sasrt_683): the composer's layout is not what the splice hook's comment assumed. The census (sasrt_686) found the
submitted segments to be one 640-word NOP each at the submission, and the watch on them ("changed after its
submission", 12 of the first 64) found the game writing their packets afterwards: the 360's GPU runs behind the CPU
and the game fills a segment after submitting it. So the packets the GPU would read do not exist at Renut's replay
time (the submission), and a compare of the PM4 against the recording is not possible there; the replay tags carry
the question instead. PC baseline of the tags (sasrt_686, every frame): mask draws from a recording begun/ended at
swap S, submitted S+1; the casters' recording begun/ended S-1, submitted S: the worker's shadow pass is one swap ahead
by design and the pairing holds every frame on the PC.

### The far-cascade flicker, console dumps of 2026-11-08: the shading's constants a frame ahead of the scene depth

One console race with `sasrt_flicker_pm4.toml` (NRO 11:48 of 2026-11-04, driven over the LAN: tools/console_run.py,
docs/switch-testing.md), twelve A+B+X+Y windows, 89 dumped frames (`out/console_runs/pm4_0556`: the log, the masks of
all windows, and every window's scene depth, atlas copy and lit image; window 0's per-pass masks).

- **The replay tags are the PC's.** In every logged frame the mask draws' scene depth (t0) comes from the mask's own
  recording and the atlas (t2) from the previous one, the casters' (`tools/flicker/tag_table.py`): no recording is paired
  with another swap's.
- **The atlas and the shading agree.** The near cascade's scale (|c16| of each near-band shading draw against half
  |c138| of the casters of the recording its atlas came from) is equal in all 94 near-band draws, also over the
  frames where the cascade's radius changed (`tools/flicker/scale_pair.py`).
- **The bad frames are the ground shadowing itself, and the GPU computes them right.** The near band's first ring
  darkens 42 % of the screen in f5198 and f5202 (window 0); redone in software from the dumped atlas, scene depth and
  logged constants (`tools/flicker/soft_match2.py`) it darkens exactly the pixels the console darkened (100 %), with the
  stored depth 3e-3 nearer the light than the ground: the inputs disagree with each other, the GPU does not.
- **The constants fit the next frame's scene depth.** The same draw redone with the scene depth of the previous, its
  own and the next dumped frame (`tools/flicker/depth_pair.py`): wherever any pairing fits to texel precision (the median
  of |margin - bias| under 5e-5), it is the next frame's depth, in 22 frames, and never the own one alone (the five
  frames where the own one fits too are frames where the camera hardly moved). The lit image matches its own frame's
  scene depth (edge overlap, `tools/flicker/lit_vs_depth.py`), so the scene depth and the lit scene are in step and the
  shading's constants are the ones a frame ahead. Every frame is off by that frame; it shows when the camera turns or
  cuts in a frame (the dump chord's B/Y turns the camera round: whole-ground shadow or none at all), and as moving,
  shimmering far shadows in ordinary driving.
- The recording that carries the shading (and the next frame's casters) is queued for replay at its composed
  segment's ring submission (sub_82CDE200, on the game thread, one recorded buffer a submission); the game thread's
  own draws are queued as they are issued. Where the run lands among the game thread's draws therefore follows when
  the submission comes, which the game reaches from a dozen Direct3D paths, waits for the GPU among them, and which
  fills the segment after submitting it. Which draws wrote the scene depth the shading reads, and in what order, is the
  next diagnostic's question (below).

### Which draws wrote a depth target: `sasrt_renut_diag_depth_writers` (2026-11-08; diagnostic, off)

Every depth target remembers, since its last whole clear, which recording cleared it (0: the game thread), how many
depth-writing draws of the game thread and of replayed recordings wrote it, and the last writer with the game frame
(`HostSurface::sasrt_*`, stamped where the draw paths count a surface's writes). A depth resolve carries that into
its destination (`HostTexture::sasrt_src_*`) and the light-volume lines print it with the binding (" src: cleared by
.. f..; then N depth draws of the game thread, M of recordings; the last .. f.."). In a shadow dump window every
replayed recording's start and end is logged ("seq:" lines) with the depth-writing draws of the game thread since the
previous run and the run's own, by target kind (scene-sized, the 1024x1024 cascade target, other). Since 2026-11-08 the
replay tag is left empty after each run in every build, so a resolve of the game thread's own is untagged (before, it
kept the last run's tag). Console test: `sasrt_flicker_depth_writers.toml`.

First reading on the PC (sasrt_688, NRO and PC build of 2026-11-08 06:37): the tags of 2026-11-04 were partly stale.
The game thread itself draws the shadow casters into the atlas (290 depth draws after its own clear, in the mask's
frame), resolves the scene depth and draws the mask; the one worker recording in the frame is the scene pass (about
465 depth draws into the scene depth, recorded the swap before and replayed at its submission, after the game
thread's clear of that target). So "the casters' recording is the previous one" (above) was the scene pass's tag
left over after its run: the atlas and the mask are the game thread's, of one frame, and the console finding reads:
the game thread's shading and the worker's scene pass are a frame apart there.

### The flicker on the PC: `sasrt_renut_diag_render_delay_ms = 25` reproduces it (2026-11-08)

The second console run (`sasrt_flicker_depth_writers.toml`, NRO 06:37, 8 windows) shows the same: the replay order is
the PC's (each frame the game thread clears the scene depth, the worker's scene-pass run draws it, the game thread
resolves it and shades; the atlas is the game thread's, of the same frame), and the shading's constants fit the next
frame's scene depth (18 frames only next, 2 only own). The worker's scene-pass draws set every vertex constant they
read themselves (the camera's view rows c131-c133 / c140-c143, the projection c134-c137; none from the running
device: "scene pass:" lines), so the worker records a camera a frame older than the game thread's shading.

On the PC the same test fits the frame's own depth (sasrt_689: no lead, also at the look-behind camera's cut). With
the console's settings and the render thread slowed (`sasrt_renut_diag_render_delay_ms = 25`, an existing key) the
PC shows the lead as the console does (sasrt_691: next to texel precision, own off by up to 4e-3, the whole ground
black in a frame). Not the cause (the lead stays): `sasrt_renut_frames_ahead = 1` (sasrt_692), the Swap's wait held
over to the game thread's next queued work (`sasrt_renut_swap_wait_deferred`, kept, off: sasrt_693), `banjo_late_input`
off (sasrt_694).

### The frame's thread timeline: `sasrt_renut_diag_trace` (2026-11-08; diagnostic, off)

A ring of timestamped events from every thread that makes a frame (`app/src/renut_engine/sasrt_trace.cpp`): the game
thread's Swap, its pacing and its wait for the render thread, its first draw after a Swap; the worker's
BeginCommandBuffer / EndCommandBuffer and splice; the composed segment's submission; GPU callbacks and fence waits;
the controller reads (`banjo_late_input`'s delay); the render thread's frame ends. Written to the log ("[trace]") from
1.5 s before to 1.5 s after each shadow dump window's start; `tools/flicker/trace_timeline.py` names the threads. At the
first scene-pass draw of a window the PC build looks for the camera rows in guest memory ("camera hunt") and every
later event samples the found camera word ("watch"), so the timeline shows when the game publishes a camera.

What it showed (sasrt_695 slowed, sasrt_696 normal): every frame the game thread makes its first draw, submits the
composed segment about 2 ms later, and the worker begins its scene pass within 20 us of that submission, ends it about
1 ms later and splices it into the next composed buffer; then the game thread's Swap. The scene recorded in a frame
is replayed in the next, beside that frame's shading. The game's update thread (the controller reads) starts its
iteration at the game thread's frame start.

### `sasrt_renut_scene_same_frame` (2026-11-08; correctness; the far-cascade shadow flicker's cause)

**The cause.** The worker thread records the scene pass (the scene's depth: 300-800 draws) right after the game thread
submits a composed segment (the trace: within 20 us of the submission), and splices it into the next composed buffer,
which the game thread submits in the next frame; Renut replays a submission's spliced buffers at the submission. So
each frame's scene was drawn a frame after it was recorded, under the next frame's shading (the game thread's own
shadow cascades, the scene-depth resolve and the light-volume mask, all drawn with that frame's camera). The scene
pass carries its own camera (its draws set c131-c143; none inherited), recorded with the frame's camera, so the scene
depth and the shading's camera were a frame apart: by the frame's turn in ordinary driving (shadows swimming, acne
where the ground shadows itself), and by a whole view at a camera cut (the look-behind button, respawns, the race's
cuts: the whole ground in shadow, or none, for a frame).

**How it was pinned down** (`tools/flicker/`): the console's dumps (2026-11-08, 20 windows) fit the shading's
constants to the next frame's scene depth (`depth_pair.py`); `cam_match.py` compares, from the log alone, the shading's
c16 (view -> atlas u) with the casters' c138 rotated by each scene pass's camera: on the PC as on the console, the
shading's camera is the camera of the scene recorded in its own frame (to 0.01 mrad), and the scene replayed with it is
off by the frame's turn (0.5-3 mrad driving, 1,400-1,600 mrad at a cut). The PC shows it too (its cut frames' masks are
wrong as well); the console shows it more. `sasrt_renut_diag_render_delay_ms = 25` makes it plain on the PC.

**The fix.** With the key on, a composed segment's submission queues a place in the render stream (where its buffers
replayed) that replays the recording the next splice brings (the worker's scene pass recorded right after this
submission: the same frame's); the render thread waits for it there (`sasrt_renut_scene_same_frame_timeout_ms`, 50;
then the recording the submission named, as before). Off: as before. PC, render thread slowed (sasrt_707): every
place filled by the next splice, none fell back, the longest wait 2.4 ms; the shading's camera matches the replayed
scene's in 17 of 21 frames to 0.01 mrad (the rest: no scene line or label drift); the depth test fits the frame's own
scene depth (window 1, the camera cutting: own 2.6-3.3e-5, the neighbours 29-300e-5); every mask matches its lit
image, the look-behind cut included. The 10 s "Renut hooks so far" line counts the places, the fills, the fallbacks
and the longest wait. Console test: `sasrt_flicker_same_frame.toml`.

### The controller reported disconnected once a race: `input_switch_disconnect_grace_ms` (2026-11-03; SDK, 1000)

The user: the game says the controller is disconnected about once a race, with the pad connected, in this game
only. `SwitchInputDriver::Poll` (sdk/src/input/switch/switch_input_driver.cpp) took `padIsConnected` at its word:
one poll with the attribute clear (a Bluetooth hiccup, a layout change) dropped the slot's device, the game's next
`XInputGetState` got `ERROR_DEVICE_NOT_CONNECTED`, and SASRT stops the race for that; shipped games wait. Now a pad
reported absent keeps its device and its last state until it has been absent for the grace time (1,000 ms; 0 as
before), and the log says "pad N back after M ms absent: kept connected" or "absent for M ms: reported
disconnected", so the next logs show how long the blips are. No key of the game's own was involved.

### Resolve destinations made again every frame (2026-11-03; found, kept across pages by the key above)

The bindings log above (the PC run sasrt_671) showed why the scene depth is bound through two host textures on
alternate frames: `ResolveTarget` (render/textures.cpp) retires and recreates the destination whenever the header's
description differs from the last resolve's, and this game double-buffers the memory behind several of its resolve
textures (the scene depth B5640B28: base pages 07119 / 0737D on alternate frames; the 288x136 and 144x68 chain and the
lit scene B5642E28 likewise). So every frame a 1152x544 R32F texture, its words twin and their framebuffer are made
and retired (each "resolves 1") and the descriptor slots freed and taken again. `Retire` erases the retired texture
from `g_resolve_targets` and `g_depth_words` (textures.cpp), so nothing dangles (rr6-nx checked the same in its
tree); the cost is the recreation, and a read of the page not resolved this frame finds no destination (it is made
from guest memory then, which the resolve never wrote). Not changed tonight: the right shape is one destination per
(header, base page). Logged by the "[sasrt] resolve destination ... made again" line.

### The shadow dump on A+B+X+Y: `sasrt_renut_diag_shadow_dump_buttons` (2026-10-30; diagnostic, the user's request)

With `sasrt_renut_diag_shadow_dump_buttons = true`, `sasrt_renut_diag_shadow_dump`'s windows start when A, B, X and
Y are down together on a pad, instead of at its times. `<first s>` and `<every s>` go unused, and `<windows>` is the
number of presses taken (0 for any number). The input system calls a function with each state the game reads
(`rex::input::SetStateHook`, the SDK's `rex/input/read_hook.h`). All four down, after one of them was up, is a press
(logged). The next eligible resolve starts a window of `<frames>`.

`app/sasrt_switch.toml` turns it on with `"0,0,0,8,B5640E28,B5642E28,B5640B28"`: the shadow mask, the lit scene and
the scene depth of 8 frames, 7.5 MB a frame. Keep the shadow atlas (`B5640EA8`) out: its copies hide the flicker.

### plume's deko3d defaults: `sasrt_deko3d_msaa_positions`, `sasrt_deko3d_a2c_dither`, `sasrt_deko3d_strip_restart` (2026-10-30; fixes, the deko3d renderer only)

The trigger was a report from a Final Fantasy XIII port that uses these plume deko3d files: a grid around the ice,
from the alpha-to-coverage dither, which deko3d turns on by default. The audit that followed (libdeko3d disassembled)
found three places where plume's deko3d back end kept deko3d's defaults while the Vulkan and D3D12 back ends behave
differently:
- `sasrt_deko3d_msaa_positions` (on): a multisampled pipeline gets the standard sample positions for its sample count
  (`dkMultisampleStateSetLocations` with none given; the same table as nouveau's `nvc0_get_sample_locations`).
  `dkMultisampleStateDefaults` puts every sample at the pixel's centre (`0x88888888`), and
  `dkCmdBufBindMultisampleState` always writes them to method 0x11E0. Before this, 2x and 4x targets had no edge
  antialiasing on the console. Ryujinx ignores the positions, so it never showed this.
- `sasrt_deko3d_a2c_dither` (off): the hardware's alpha-to-coverage dither. Xenos dithers alpha to mask with its own
  offsets, which Renut does not emulate, and the other back ends have no dither control.
- `sasrt_deko3d_strip_restart` (on): an indexed triangle or line strip starts again at the all-ones index of its
  index size, as the Vulkan back end (`primitiveRestartEnable` for strips) and D3D's strip cut. deko3d never turns
  primitive restart on; only `dkCmdBufSetPrimitiveRestart` writes method 0x591. The state is set only when it changes
  (one compare per indexed draw).
- With the same audit, plume's `invalidateZcullAfterCopy` got its braces back (no key). Without them, the Zcull
  invalidate was recorded after every copy and upload, with Zcull on or off. That is the likely cause of the
  console's stop during the boot with `banjo_deko3d_zcull = false` (newlogs6).
- The `deko3d:` report line every 10 s gives multisampled pipelines (those with alpha to coverage, those given the
  positions) and indexed strips drawn with restart.
- What this game uses (Ryujinx run fix1030_race, 480 s, boot to race): one multisampled pipeline in the whole run,
  without alpha to coverage, so the positions and the dither change little here. The race draws about 115 indexed
  strips a frame (none in the menus), all without restart before this fix.
- Configs (the old behaviour back): `sasrt_deko3d_msaa_positions_off.toml`, `sasrt_deko3d_a2c_dither_on.toml`,
  `sasrt_deko3d_strip_restart_off.toml`.

### Display: `sasrt_display_gamma` (2026-10-21; user option, default 1.0; scan-out, so the HUD too)

An exponent on every colour at scan-out, applied in Renut's gamma ramp lookup (`sa2_renut_gamma_ramp`), so it costs
nothing per pixel: above 1 darkens the midtones (1.15 for a less washed-out look in the sunlit stretches), below 1
lightens them; black and white stay. As UnleashedRecomp's brightness slider and Xbox colour correction. Why an option
and not a fix: matched frames of Renut (PC) and the emulated GPU's exact path (ROV) agree (mean luma 129.8 / 131.4,
blown-out pixels 2.27 / 2.16 %, 165 frames of the same race stretch), the console matches the PC at the start grid
(track 147 / 148), and this game's display gamma ramp is the identity (SA2's is not). Config:
`sasrt_display_gamma_115.toml`.
- **Tests and diagnostics of the hunt** (all off): `sasrt_renut_test_keep_swapped_halves` (no 16-bit element swapped
  back, any shader), `sasrt_renut_test_ubyte4_reverse` (UBYTE4 blend indices in w z y x order),
  `sasrt_renut_capture_recorded_streams` (the workers' vertex streams, up to 2 MB each, copied on the game thread at
  the composed buffer's ring submission, as MarathonRecomp-NX copies a buffer at its Unlock; about 20 MB a submission.
  A version copying only each draw's index range drew planes across the screen in most frames: some draws read
  outside it; dropped), `sasrt_renut_query_samples` (the game's occlusion queries answered on the CPU at the ring's
  EVENT_WRITE_ZPD, as the emulated GPU does: -1 none, -2 counted; the title device's ring holds none in a race, about
  six indirect buffers a kick not followed), `sasrt_renut_diag_ps_constants` (the constants a listed pixel shader's
  draws read and where from),
  `sasrt_renut_diag_layout_log` (stream layouts, the order of exports and their reads, the octopus's bones),
  `sasrt_renut_diag_late_streams`, `sasrt_renut_diag_constants_verify` (2026-10-29, the far-cascade shadow flicker:
  after each draw's float constants went up, by the ring upload or the deko3d pushes, every register the shader reads
  but its literal ones must be held by the model of the buffer with the bytes the draw's constants have now; the first
  64 that are not are logged, and a count every 2^20 stages; the PC race: 8.4 million stages, none),
  `sasrt_renut_diag_light_volumes` (2026-10-29: after that many frames that drew the race's light volumes, ten frames
  of them: the cascade spheres' transforms, the shading pixel shaders' cascade constants c7-c24, where each comes from,
  and the shadow casters' first draws and counts). Tools: `tools/rdc_tri_edges.py` (a draw's triangles by edge length),
  `tools/rdc_exploded.py`, `tools/rdc_scene_last.py`, `tools/rdc_draw_inputs.py`, `tools/rdc_uses.py`.

### `sasrt_cpu_verify`

A check mode, not an enhancement: `masseffect_native_verify_n` is set to "every use" and
`masseffect_native_fast_copy_verify` to the first 20,000 copies (see "Verification"), and the renderer's comparisons
count into the `[verify]` line.

## Non-CPU group

### `sasrt_handheld_gpu_boost`

In handheld mode it asks for the official 0x92220008 configuration (GPU 460.8 MHz, memory clock unchanged) through
the SDK's `switch_apm.cpp`, which checks the real clocks for 1.5 s and reverts if the memory clock moved. Docked, it
requests nothing (nfsmw-nx, UnleashedRecomp-NX, MarathonRecomp-NX and sa2-nx ship the same).

- **Why exact:** it changes a clock, not a setting.
- **Risk:** more power draw in handheld mode.

### `sasrt_native_skip_null_draws`

Direct3D follows every memory-export draw with a one-point draw of its null vertex shader (a NaN position: nothing is
rasterized or exported) through the 4x alias of the depth target. Each one made the renderer move the shadow map's
EDRAM tiles to the 4x image and back (two imports of 832 tiles). The draw is now dropped before the EDRAM
synchronisation. Evidence and numbers: `docs/gpu-optimisation-candidates.md`, item 1 (race: EDRAM tiles transferred
3.07 M -> 2.12 M per 10 s, depth imports 4.5-6.0 -> 2.9-4.1 ms per Swap on PC).

- **Why exact:** a primitive with a NaN position covers no sample, and the shader writes no memory; the EDRAM
  round trip it caused copied the same depth back.
- **Risk:** none known; the draw is recognised by its exact 15 microcode words.

### `sasrt_native_edram4_grid_alias`

The shadow map's first aliased clear of each frame is redirected into the 1x view like the others: the 1x alias of the
4x clear view is now also learned through the raster-grid 4x view that this game's draws use. Race: depth import
operations 44,700 -> 25,500 per 10 s, EDRAM depth imports 3.9-4.2 -> 3.2-3.4 ms per Swap on PC
(`docs/gpu-optimisation-candidates.md`, item 2).

- **Why exact:** the redirect's existing rules decide what each tile gets (the clear's depth in the 1x alias, the
  stencil bits kept by the lazy-stencil record); only the source of the alias changed.
- **Risk:** a raster-grid view with the same base and pitch that is not the clear's surface; the lookup requires the
  same EDRAM base, tile pitch, sample rows and depth encoding.

### Vertex shaders Direct3D patched beyond an exact match: `sasrt_gpu_vs_swizzle_variants`, `sasrt_gpu_vs_fetch_reorder` (2026-10-07)

Direct3D's vertex fetch patcher (`sub_82CE18F8`, sa2-nx's `sub_82555E18`) rewrites a vertex shader's fetches for the
vertex declaration it is drawn with. The renderer identifies a loaded program by holding each fetch at its own slot
with the bits Direct3D does not touch (`kFetchKeeps`), so two kinds of rewrite left a load unidentified, and its draws
were dropped:

- **Destination swizzles** (futari-nx's fix, in sa2-nx's `Identify`; this port lacked it): float3 -> xyz1, D3DCOLOR ->
  zyxw, float2 -> xy01. `sasrt_gpu_vs_swizzle_variants`: after no exact match, the candidate the draw-time identity
  check accepts (`VertexShaderIdentityMatches`) is taken, the closest first (fewest swizzle components to remap). The
  draw path already applies such swizzles through its input remap, a select chain, so the result is exact.
- **Fetches moved to each other's slots** (sa2-nx's, from its Chao garden): `sasrt_gpu_vs_fetch_reorder`. When no
  entry matches a load in its own order, `ProveVertexFetchReorder` (`src/me/me_vertex_fetch_reorder.h`, sa2-nx's file
  as it is) runs the offline repair tool's proof against the package entries of the same length: every non-fetch
  word identical; exactly the declared slots executed as fetches, once each, in unconditional clauses; a unique
  bijection by destination register, write mask, source, predicate and a representable swizzle that the draw path's
  own selection agrees with; each move inside one fetch-only interval between equivalent full-fetch bases. The
  library shader's SPIR-V then computes what the loaded program computes: the fetches write their own registers
  before any ALU instruction reads them, in either order. The chosen entry is the only extra candidate the draw-time
  identity check accepts for that load, and only while the proof holds again on its words (`FetchReordered`).
- **What stays:** a load any entry matches in order keeps that entry; both paths run only for loads that used to be
  dropped.
- **Self-check:** the first 64 reordered programs, and every one in verify mode, are also searched by brute force
  (every placement of the declared fetches against the ordered predicate; only the proven one may pass). A
  difference turns the reorder off for the session (a DIFFERENCE line).
- **This game's containers** (`shaders/tests/test_vertex_fetch_reorder.cpp --orders`, sa2-nx's test, built here with
  clang and a three-line `unistd.h` shim in `out/tools/posix_shim`): every placement of a container's declared fetches
  over its declared slots, as Direct3D could load it, against the run-time proof. The first 28 of the 533 vertex
  shader dumps in `out/pc/shaders` (2 to 7 fetches): 7,162 placements, 5,537 proven with the right mapping, the rest
  refused because the move would cross inequivalent full/mini fetch bases; 13 containers have every order proven.
  The test places every permutation, so its time grows as n!: the 29th container did not finish in 15 minutes.
- **Seen in this game:** three verify runs of track 3.0 (`sasrt_163`, `sasrt_211`, `sasrt_240`) dropped about 30 draws
  per 10 s late in the race: one 186-word vertex program (`F0554006 00001200 C2000000 0000600A ...`, object
  `09196640`) no entry matched. Whether it is a swizzle or reorder variant or a shader the package lacks is still
  open: two runs of the same track since did not reach it (300 s at normal speed with the shader dump on: 0
  unidentified loads; verify mode with both keys, `sasrt_276`: 0 unidentified loads, 0 draws without shaders, 0
  differences, and neither new path was needed). The dump (`MASSEFFECT_SHADER_DISCOVERY` on the PC, `shader_misses/`
  on the console) keeps such a program when it comes back.
- **Keys:** `sasrt_gpu_vs_swizzle_variants`, `sasrt_gpu_vs_fetch_reorder` (non-CPU group). Both off:
  `configs/sasrt_test_vs_identify_off.toml`. Report: `[native] shaders: VS n.. identified with destination swizzles
  patched by D3D`, `[native] sasrt_gpu_vs_fetch_reorder: VS n.. identified with its fetches reordered` (the first 16
  each) and `[native] VS loads identified with their fetches reordered by Direct3D (sasrt_gpu_vs_fetch_reorder): N`.

### The GPU round of 2026-10-13: sa2-nx's GPU keys, and relaxed vsync for a 30 fps game

The user asked for sa2-nx's GPU optimisations here. Seven keys, all in the non-CPU group and on by default; five of
them need the shader package of this build (`tools\win\rebuild_shader_package.ps1`; 2,033 containers, 1,982 shaders,
61,757,240 bytes, 5 % larger than the last one: the new variants). The old package still works with this renderer and
the new one with an older renderer: a bit nobody tests changes nothing. Nothing here has run on a console.
`configs/sasrt_test_gpu_round13_off.toml` turns the six GPU keys off, `sasrt_test_vsync_relaxed_off.toml` the seventh.

#### `sasrt_gpu_resolve_draw`: resolves drawn on the 3D engine

- **What:** a resolve whose render target and texture have the same host format is one fragment pass (texel (x, y)
  of the texture = texel (x, y) + delta of the render target) instead of `vkCmdCopyImage`.
- **Why:** NVK records `vkCmdCopyImage` on the copy engine (NV90B5), with a wait for idle at each engine switch.
  sa2-nx measured up to 2.5 ms of a 9 ms GPU frame for its 8 resolves a frame on the console. This game resolves
  36 times a frame in a race; 30 of them are such copies.
- **Three formats, counted in a race (`sasrt_293`):** RGBA8 13 a frame (the scene and its post-processing steps),
  RGBA16F 10 a frame (the bloom chain), R32F 7 a frame (the luminance chain). sa2-nx's key covers RGBA8 only (SA2
  resolves nothing else).
- **Why exact:** UNORM8 values round-trip exactly through a float pass (n / 255 written back is n), as in the EDRAM
  color conversions. A float pass would not promise a NaN its payload, so the two float formats go through integer
  views of the same texels (`ViewRawBits`: `R16G16B16A16_UINT`, `R32_UINT`; `shaders/sasrt_resolve_copy_uint.frag`):
  the pass moves bit patterns, as the copy did. R32F images are created with a mutable format for that, as the
  RGBA16F ones already were. The render pass's dependencies order the pass as the copy's barriers did, with exact
  access masks (sa2-nx's: `MEMORY_READ | MEMORY_WRITE` makes NVK invalidate every cache at each pass end).
- **What declines** (the copy is recorded as before, and counted): another format pair, a scaled, gridded or
  multisampled image, a rectangle outside an image, no pass or descriptor set.
- **Checked (PC):** `sasrt_294`, a race: 9,126 resolves drawn per 10 s (4,009 RGBA8, 3,010 RGBA16F, 2,107 R32F), 0
  copied as before, no `DIFFERENCE` line, the picture as before (bloom and exposure included).
- **Report line:** `[native] targets: resolves drawn on the 3D engine (sasrt_gpu_resolve_draw) since the previous
  report: N (...)`. The six resolves a frame left are depth resolves and format conversions, which were never plain
  copies.
- **A defect of the first build of this key (the NRO of 2026-10-13 03:46, replaced):** R32F resolved textures were
  created without the color-attachment usage, and the pass drew into them through a view that asked for it, which
  Vulkan does not allow. The PC's driver did not object and this PC has no validation layer installed, so nothing
  reported it; I found it reading `GetResolved` for the long-session fix below. Every resolved texture that is not
  a depth format has the usage now. The Switch's driver was never given the invalid view: that NRO did not run.

#### Four shader specializations (they need the new shader package)

The translator (`shaders/XenosRecomp`) emits each as a variant under a specialization bit; the renderer sets the bit
per pipeline. The bit numbers are this port's (bits 2-6 are the pixel parameter generation here): 7, 10-13 and 19.

- **`sasrt_gpu_index_base_held`:** the translator proves that a vertex shader never reads the vertex index r0 starts
  with (`vertexIndexMayBeRead`, sa2-nx's: any read of r0 counts except the Xenos zero idiom `-|r0| > 0`; the answer
  is no once r0.x is surely overwritten). **382 of this game's 558 vertex shaders.** With the bit their r0 starts at
  0, and the renderer writes 0 as the vertex index base, so consecutive draws with the same textures keep the same
  shared constant block. Not for rectangle lists. In a race 52 % of the draws (`sasrt_293`).
- **`sasrt_gpu_blend_skip`** (UnleashedRecomp-NX's idea): a pixel whose blend would leave the target exactly as it
  was is discarded before the blend, which saves the blend's read-modify-write. Only on one RGBA8 UNORM target
  without exponent bias (the blend clamps to [0, 1] there, so a source of 0 or less contributes exactly 0 and
  destination x 1 is exact), with no alpha to coverage, no depth write, no stencil write of any kind, op ADD and a
  destination factor that is exactly 1 once the source is 0. A NaN is never discarded. Occlusion queries are answered
  on the CPU here too. 32 draws a frame in a race.
- **`sasrt_gpu_texcoords_unswapped`, `sasrt_gpu_no_texture_signs`, `sasrt_gpu_identity_remap`:** three facts the
  renderer knows per pipeline, so the shaders stop testing them per vertex or per pixel: `g_SwappedTexcoords` is
  always 0 (every draw); no texture of the draw has a signed, gamma or biased component, an integer format or an
  exponent bias (bits 12-31 of every texture slot word are 0: 32 % of the draws in a race; the tracks' lighting
  volumes and FXAA's biased fetches keep the test); every vertex input keeps its component order (87 %). Each bit
  replaces exactly the early return its test would take. Verify mode checks the shared block each relies on.

sa2-nx's `sa2_gpu_push_once` was here already (`sasrt_gpu_push_once`).

Not taken, with the reason:

- **`sa2_gpu_structured_cf`:** it replaces the `skipTo` form of forward-only control flow. None of this game's 1,982
  translated shaders has that form.
- **`sa2_gpu_resolve_alias`:** it drops SA2's duplicate resolve of one render target into a second texture. This
  game's unread resolves are its front buffers (three 1280x720 copies a frame, read by the Swap only); deferring
  them is `masseffect_native_lazy_front`, which is off here as in sa2-nx. A candidate.
- **`sa2_gpu_prewarm_current_keys`, `sa2_gpu_render_scale`, `sa2_gpu_msaa`:** the render resolution and MSAA
  settings and their pipeline-list handling. Not asked for here.
- **`sa2_native_partial_resolve_inside`** (SA2's Chao garden fix): this game resolves its 1024x3072 shadow atlas in
  three parts, and banjo-nx found sa2-nx's rule too narrow for exactly that (the lower bands became textures of their
  own). If it is ever taken, take banjo-nx's corrected height test.

#### `sasrt_vsync_relaxed`: no fall from 30 straight to 20

sa2-nx's relaxed vsync gives the game its vblank when the flip waits for it, so a late frame is shown when it is
ready instead of at the next 1/60 s tick. peggle2-nx adapted it to a game that presents every second vblank (only the
vblank that can release the flip follows the game; the ones before it stay 1/60 s ticks; which wait is the flip and
how many vblanks a flip takes are learned at start). This game presents the same way, so that form is ported
(`app/src/me/me_native_system.cpp`): on the PC it learns `the flip wait polls 1FCA3006` and `a flip takes 2
vblank(s)`, and an on-time race keeps its 300 Swaps per 10 s.

**It is off by default, because this game does not have the problem.** Measured on the PC with a simulated slow frame
(`sasrt_diag_ring_swap_delay_us` spins the ring thread at each swap, the SDK's `diag_vdswap_delay_us` the game thread
in VdSwap; 75 s runs, Swaps per 10 s once the game is in its menus and race):

| Simulated load | key on | key off |
|---|---|---|
| ring +30 ms per frame (39 ms of ring work per Swap) | 255-280 (`sasrt_295`) | 265-279 (`sasrt_296`) |
| game thread +30 ms per frame | 232-233, then 262 and 300 as the load screens end (`sasrt_297`) | 232-233, 263, 300 (`sasrt_298`) |

With 39 ms of ring work a frame the game presents every 39 ms, not every 50: the ring spends 0.00 ms per Swap in the
flip wait, because the flag is already clear when it gets there. Direct3D's flip rule (peggle2-nx read it from the
swap code) shows a late frame at once or at the next vblank, and here a late ring makes the game thread late too.
peggle2-nx measured 20 against 26-27 frames a second in its ring test; that game queues its flips differently.
`configs/sasrt_test_vsync_relaxed_on.toml` turns the key on for a console A/B: if the console's "Swaps" fall from 30
to 20 in a race rather than to 25-29, try it.

#### Checks of the round (PC)

- **The translator and the package:** 2,033 containers translated and compiled, 0 failed.
- **A race with everything on** (`sasrt_294`, track 2.3, the Switch's settings): no `DIFFERENCE` line; 300 Swaps per
  10 s; the picture as before (a captured frame of the race compared by eye with the runs before: track, cars, HUD,
  bloom and exposure).
- **Verify mode** on tracks 2.3, 0.0 and 3.0 (`sasrt_299` / `300` / `301`, 240 s each): `differences: 0` on all
  three and no `DIFFERENCE:` line. The native Direct3D layer compared 931,314 / 1,988,584 / 2,021,449 records with
  the original; the three per-pipeline facts are compared with the shared block on every draw that sets their bit.
  The only error line is the third-party Vulkan layer's that every run has.
- **The index proof and the blend skip have no run-time check**: a shader cannot be asked what it read. The proof is
  sa2-nx's code (frame-identical in its lockstep runs there, on its 22 vertex shaders); here it stands on the
  translator's argument and on the pictures. This game is not deterministic, so no frame-by-frame comparison exists:
  if a mesh or a transparent effect is wrong on the console, `configs/sasrt_test_gpu_round13_off.toml` is the test.
- **Switch NRO of 2026-10-13 03:46** (66,873,541 bytes) with this package: `tools/check_switch_build.py` passed.
  Replaced at 13:58 (66,889,925 bytes, same package, checks passed) by the build with the R32F correction above
  and the long-session fix below; the race and the verify run were repeated with it (`sasrt_302`, `sasrt_303`).
- **No GPU time was gained on the PC, and none was expected:** "copies" is 5.7-6.0 ms per Swap before (`sasrt_288`)
  and 5.5-6.2 after (`sasrt_294`). What the resolve key removes is NVK's engine switch, which the PC's driver does
  not have, and the PC's GPU is shared with other work. The console's "GPU per Swap" line is the measure.

### `sasrt_native_resolved_retire_idle`: long sessions (2026-10-13, sa2-nx's fix, wider here)

sa2-nx 1.0.0 and nfsmw-nx were reported to break after one to two hours of play: shadows glitch, then textures turn
black and geometry goes missing until the game is restarted. sa2-nx found the cause in the renderer all these ports
share and sent it round; this port had it, with two effects of its own.

- **The cause:** the renderer kept one image per address ever resolved to, for the whole session. The game frees a
  render target's texture when a scene ends and the next scene allocates its own elsewhere. Here: **78 images
  created at 71 addresses after the boot, the menus and one race** (23 of them 1152x544); an address only lost its
  image when the game resolved another size or format to it. GPU memory fills up;
  then an image cannot be created, the texture cache is dropped to make room, and at last things go missing.
- **This port's second effect:** the crops and the depth-word images derived from resolved textures live in bounded
  caches (32 crops or 128 MB; 16 depth-word images) that never let go either. One session of menus and one race
  uses 15 crops. Once stale addresses fill a cache, every later fetch that needs a new entry fails ("bounded crop
  cache capacity", "words cache full") and its draw is rejected: the luminance chain's 1x1 crops are such fetches.
- **Third:** this game's ordinary textures are tiled, and a tiled fetch at an address found in the resolved map is
  drawn from the resolved image. A texture loaded later at a stale address was therefore drawn from the old render
  target's image (or rejected, with another size).
- **The fix** (sa2-nx's `sa2_native_resolved_retire_idle`, commit 3aff36c there): every entry records the presented
  frame of its last resolve and of its last read. Every 64 presented frames, an entry with neither for
  `sasrt_native_resolved_idle_frames` (3,600: two minutes at this game's 30 frames a second) is released, and here
  its crops and depth words with it; the parked shapes too. An entry with a deferred front copy or an EDRAM tile
  owner stays. A failed GPU allocation makes the next Swap release everything idle for 120 frames. No wait for the
  GPU is needed: no pending submission can reference an image unused for that long.
- **Why it is safe:** a read keeps a texture alive however old its resolve is (a resolved texture is looked up once
  a frame per sampler: its sampler-cache entry is valid for one frame only), and a write is every path that calls
  `ResolvedWritten`, partial resolves included (the shadow atlas's three parts write their owner).
- **Checked (PC):**
  - A stress run with the idle time at 120 frames (`sasrt_302`, a race): 27 textures released (29 MB), 37 live ones
    holding 63 MB at the end, **0 fetches at released addresses** (the PC build remembers released addresses and
    reports a fetch there before the next resolve), no `DIFFERENCE:` line, no rejected draw or crop, the picture
    right. The oldest read of a texture came 356 presented frames after its resolve: reads, not resolves, are what
    keeps some textures alive.
  - Verify mode with the default idle time (`sasrt_303`, track 2.3, 240 s): `differences: 0`, no `DIFFERENCE:`
    line, 2,581,888 native Direct3D records compared. Nothing is released in a run that short (33 live textures,
    58 MB): this run only shows the bookkeeping changes nothing.
- **NOT shown:** the console running out of memory (no log of it exists for any port), and a session of several
  races on the PC (the scripted test plays one). A long console session is the test. The report line every 600
  presented frames, `[native] targets: N resolved textures, ... hold M MB; K released when idle so far`, is what to
  read in its log: with the key off (`configs/sasrt_test_resolved_retire_off.toml`) the same line shows the growth.
- **In the Switch NRO of 2026-10-13 13:58** (66,889,925 bytes; `tools/check_switch_build.py` passed), which replaced
  the 03:46 one, and in the 15:30 one that replaced it.

### `sasrt_native_texture_slots_evict`: long sessions, second part (2026-10-14, sa2-nx's finding)

sa2-nx's build with the fix above still broke after three to four hours (black textures, missing geometry). Its
session found the second cause in the texture cache of the renderer these ports share, and the user asked for it
here too. The cache released a texture only by bytes, and that was no bound:

- **The descriptor heaps are a limit of their own.** 4,096 2D views, 64 cube maps, 16 3D textures (the slot is 12
  bits of the word the shaders get). When no slot is free a new view gets slot 0, the EMPTY texture ("texture pool
  full", logged once), and nothing ever made room: from then on whatever is loaded is drawn black or, where the draw
  tests alpha, not at all, until restart.
- **In this game the small heaps come first.** Measured (`sasrt_307`): the boot and the menus hold 542-616 2D
  slots, 12-14 cube maps and one 3D texture; the first race adds about 480 2D slots, **20 cube maps and 4 3D
  textures** (1,095 of 4,095, 33 of 63 and 5 of 15 after it). If every track's textures are new ones, the cube heap
  is full on the third track and the 3D heap soon after; the 2D heap would last about seven. (Not measured: how many
  a second track really adds. The scripted test plays one.)
- **The bytes counted were texels, not memory.** A texture takes whole 64 KB units of the pool: 161 MB in use
  after the menus and one race, against 116 MB of texels counted (`sasrt_310`, the key off): 1.4 times. The pool is
  capped at the limit plus one slab (544 MB), and the limit's eviction began at 75 % of 512 MB of TEXELS, which is
  about 533 MB of pool: no margin, and the pool is fragmented (largest gap 32 MB of 94 MB free), so textures stop
  finding gaps before that. A texture that finds no gap takes a dedicated allocation, one NvMap handle each: the
  route the pool's header describes as ending in error 0x235C and a black screen.

What changed (sa2-nx's design for the slots, `EvictTexturesForSlots` in `masseffect_native_draws.cpp`; the two
memory parts are this port's, on sa2-nx's note for games with larger textures):

- A heap more than three quarters full sheds its 32 coldest textures (unused for 120 frames) every 16 frames until
  it is under five eighths; a view that found no slot makes an eighth of the heap go at the next frame. All three
  image heaps.
- A texture counts as the memory it takes (its texels rounded up to the pool's unit). The counted total now matches
  the pool's own figure (159 MB against 161 MB in use), so the limit bounds the pool.
- A texture that found no gap in the pool makes 64 cold textures go at the next frame.
- Every 600 frames: `[native] C3 slots: 2D N of 4095 in use, 3D ..., cube ..., samplers ...; T textures in the
  cache (M MB counted); R released for slots or pool gaps so far, V views found no slot, G textures found no pool
  gap`.
- `sasrt_diag_texture_slots = N` hands out only N slots of the 2D heap, so a PC run meets the shortage in minutes.

Checked (PC):

- **With the shortage forced** (`sasrt_308`: 900 2D slots, which the menus plus one race exceed by 200): 448 cold
  textures released as the race loaded, 582-640 slots in use afterwards, **0 views without a slot**, no
  `DIFFERENCE:` line, no rejected draw, the picture of the race right.
- **Without it** (`sasrt_307`): nothing released, the counts above.
- **Verify mode** (`sasrt_309`, 240 s): `differences: 0`, no `DIFFERENCE:` line.
- **sa2-nx's lockstep test of the same code in its tree** (384 slots handed out, its attract demo against the
  reference): with the fix off the heap is full after 3 minutes, 2,582 views find no slot and 701 of 2,979 frames
  differ (billboards and benches black, a blended shield gone: its users' report); with it on, 224 textures
  released and 2,982 of 2,982 frames identical. This game cannot make that comparison (it is not deterministic).
- **In the Switch NRO of 2026-10-14 11:45** (66,853,061 bytes; all build checks passed), which replaces the
  2026-10-13 15:30 one.
- **NOT shown:** the cube and 3D heaps running short (the diagnostic shortens the 2D heap only; the code path is the
  same, the heap index differs), a second track in one session, and anything on a console. sa2-nx's own PC test of
  its version was still running when this was built. A long console session is the test: the `C3 slots` line shows
  whether a heap creeps up, and `V views found no slot` must stay 0.
  `configs/sasrt_test_texture_slots_off.toml` turns it off.

### banjo-nx's EDRAM traffic items (2026-10-14, non-CPU group; the user's go-ahead)

The console's first run spent 43-45 ms of GPU a frame on the EDRAM emulation. banjo-nx has not removed that emulation
(its "surfaces instead of EDRAM tiles" is the third step of its API plan, not started), but it cut its traffic with
the items below, all ported (the Clear operation some hours after the others: I had first skipped it on a wrong
reading of this game's surface sizes, see below). Off together: `configs/sasrt_test_edram_banjo_off.toml`.

| Key (here) | banjo-nx's | What |
|---|---|---|
| `sasrt_gpu_proof_tess_leftover` | `banjo_gpu_proof_tess_leftover` | the overwrite proof treats `VGT_OUTPUT_PATH_CNTL` as the reference renderer does (in force only in the explicit major mode): a tessellator setting left over refuses no Clear |
| `sasrt_gpu_proof_triangle` | `banjo_gpu_proof_triangle` | one auto-indexed triangle covering its whole viewport or scissor (full-screen passes) proves a full overwrite like a rectangle; exact edge test in double precision |
| `sasrt_gpu_proof_depth_only` | `banjo_gpu_proof_depth_only` | in the depth-only EDRAM mode the alpha-test / alpha-to-coverage bits do not stop the proof (no pixel shader runs there, and this renderer draws those draws without a fragment stage too) |
| `sasrt_gpu_edram4_split_tiles` (+ `sasrt_diag_split_tiles`) | `banjo_gpu_edram4_split_tiles` | a draw that overwrites part of a tile another view holds takes the tile without a transfer; the old owner keeps the rest, healed (set aside, ordinary transfer, put back) only if something needs it before the tile is overwritten whole; depth views without TRANSFER_DST heal by an import clipped to the rest |
| `sasrt_gpu_rect_split` | `banjo_gpu_rect_split` | a rectangle list of 2-8 rectangles is drawn one rectangle at a time |
| `sasrt_gpu_api_clear` (+ `sasrt_diag_clear_padding`) | `banjo_d3d_api_clear` | Direct3D's Clear as an operation: the native Clear puts markers around each rectangle's packets; a rectangle of a Clear of the whole surface that reaches its right edge is widened to the pitch, one that reaches its bottom edge to the end of the tile row, so the edge tiles are taken whole; drawn in the surface's own view |

`me_native_draw_extent_estimator.h` is banjo-nx's file as it is (this port's copy had no changes of its own). The
split tiles are banjo-nx's code with its hook points (the resolve synchronizes only what it copies; the EDRAM clears,
sa2-nx's colour-0 clear and the redirected clears drop or heal splits; the views holding a rest are kept like tile
owners: never retired, parked or swapped; the 10 s line `EDRAM mode4 split tiles`).

**Measured (PC, the console's settings `-SwitchConfig`, a race, 10 s windows; `sasrt_326` keys on, `sasrt_327` split
tiles off):**
- split tiles: 19,400 tiles taken without a transfer, 9,536 splits ended by a whole overwrite (their rest never
  moved), 9,864 healed (overwritten in part 4,470, depth cleared whole with its stencil kept 2,238, read by another
  view 1,798, cleared in part 1,358), 31,162 not taken (their rest was needed the last times);
- EDRAM operations: depth imports 25,300 -> 20,860 (-17.5 %), colour aliases 17,523 -> 16,688 (-4.8 %), exports the
  same; the PC GPU's EDRAM time unchanged within its noise (import 3.7, export 2.1, alias 4.1, nine-pass import 2.3 ms
  a Swap either way): half the splits are healed, and a heal costs the transfer plus two copies;
- rect split: never in a race (0 rectangle lists of 2-8 rectangles: this game's clears are not the L of two);
- the depth-only rule: 0 draws decided by it in a race.

**Checks:** 0 DIFFERENCE in every run; the poison mode (`sasrt_diag_split_tiles = 2`, `sasrt_329`: 207,582 rest
rectangles filled with magenta or a depth of 0.37) gives a correct race frame (no magenta, no depth error); verify mode
below.

**The Clear operation (`sasrt_gpu_api_clear`, banjo-nx's `banjo_d3d_api_clear`), ported later the same day.** I had
first left it out on the belief that this game's surfaces are whole tiles: the 1200, 1280, 1040, 640 and 320 of the
reports are pitches. The surfaces themselves (the resolves say so) are 1152x544 at a pitch of 1200, 576x272 at 640,
256x256 at 320 and the 1024x1024 shadow map at 1040, so each has a last tile column that holds surface pixels and
pitch padding. Direct3D clears a surface's whole tiles through a 4x alias of half the pitch and the partial edge
column at 1x as a rectangle (`sub_82CE5EC0`, the native `SplitDraw`); the renderer brought the rest of each edge tile
in from the tile's previous owner on every Clear. In the pair report that was Direct3D's own clear shaders (VS n1758,
PS n419) pulling one tile at a time: the shadow map's column 960-1024 (12,888 operations a 10 s) and the 256-wide
surface's 240-256 (2,548).

Here the native Clear (`sasrt_api_clears`, `sasrt_api_clear.cpp`) writes the markers itself: a type-3 NOP before each
rectangle's packets with the rectangle, the sizes of colour target 0 and the depth surface (the word at +36, as
Direct3D reads it) and the flags, and one after them. Verify mode's comparison of the native Clear leaves NOPs out, so
it checks the same packets as before. With `sasrt_api_clears` off (the CPU master off) there are no markers and no
widening. The ring (`WidenApiClear`, banjo-nx's code) widens a 1x rectangle of a Clear of the whole surface at the
surface's right edge to the pitch and at its bottom edge to the end of the tile row, for depth and colour target 0
only, and such a rectangle is drawn in the surface's own view (not redirected into the tile's previous owner).
`sasrt_diag_clear_padding = 1` fills the taken padding with magenta or a depth of 0.37 right after each widened
Clear: anything that read it would show.

**Measured** (PC, the console's settings, the same race; `sasrt_333` without it, `sasrt_335` with it; per 10 s):
2,100 markers, 1,800 edge rectangles widened (every 1x edge strip; the 1,800 alias interiors at half the pitch are
declined as Banjo's are). Depth imports 20,400 -> 3,576 (-82 %), transfer operations about 77,500 -> 53,700 (-31 %),
tiles moved 1,580,700 -> 1,546,966 (-2 %: they were one-tile operations); the depth resolves' transfers (about 1,280
operations) are gone too, the colour resolve's one tile a frame stays.
The PC's EDRAM GPU time (import + export + alias + nine-pass import) fell from about 10.9 to 9.3 ms a Swap.
The poison run (`sasrt_336`, `sasrt_diag_clear_padding = 1`): about 1,800 padding rectangles filled every 10 s,
three recorded race frames with no magenta pixel and normal shadows (a read of the shadow map's poisoned padding would
show as wrong shadows), 0 DIFFERENCE. Verify mode (`sasrt_337`, track 2.3): the native Clears compared as before
(13,068 clears among 1,998,229 native records), one difference: the native layer's open `DrawVertices` byte (the
section "The native-layer byte differences of `sasrt_315` and `sasrt_321`" above), not the Clear.

**Where this game's EDRAM traffic really is** (the same race): about 1.89 million tiles every 10 s, about 6,300 a
frame (banjo-nx: 23 to 176), and almost all of it whole surfaces read in another format: colour -> depth 716,000,
colour -> colour 597,000, depth -> colour 469,000 tiles per 10 s. Which draws pull them (banjo-nx's question; the pair
report now also lists the 8 pairs that move the most tiles, with each draw's slot `s0` = depth, `s1`-`s4` = colour
0-3, and its colour mask `cm`; `sasrt_332`, per 10 s = about 300 frames):

| Pair (base, format, pitch) | Tiles | The draw that pulls them |
|---|---|---|
| colour 1FE f0 -> depth 1FE | 152,490 | VS n1199, depth-only mode: depth test GEQUAL, stencil REPLACE where the depth test fails. It reads the depth the game wrote through a colour alias: a real read |
| colour 3FC f0 -> depth 3FC | 152,490 | Direct3D's Clear of the stencil alone (its clear shaders VS n1758 / PS n419, one rectangle over the whole surface: stencil 0, depth test off). The depth bits stay: a real read |
| colour 3FC f0 -> 4x depth 3FC | 152,490 | VS n1078, one rectangle, depth test NEVER, nothing written: **removed by `sasrt_gpu_skip_dead_draws` (below)** |
| colour 1FE f0 -> 4x depth 1FE | 152,490 | the same draw at the other surface: removed too |
| colour 000 pitch 1200 -> pitch 1280 | 152,490 | VS n1548, the first draw of the 1280x720 frame (16 triangles, no overwrite proof) |
| depth 000 (the 1040x1040 shadow map) -> colour 000 | 151,682 | the scene's first draws (VS n667 and n688, three render targets), no clear before them |
| colour 000 f5 -> colour 1FE f0 | 147,407 | VS n1771, a three-target pass (colour 1), 29 tiles a draw |
| colour 000 f5 -> colour 000 f0 | 126,477 | the same draw, colour 0 |

Apart from the two dead rectangles these are real reads (the depth restored through a colour alias) or the first
draws over a surface last used in another format, where only a proof that the whole frame gets covered (or banjo-nx's
third step: render targets kept per surface, EDRAM ownership only where the game really reuses content) would remove
the transfer. Neither exists yet. The pair with the most operations (12,800 a 10 s, one tile each) is Direct3D's
Clear of the shadow map (VS n1758 / PS n419 are its clear shaders): its 1x edge strip 960-1024 ends 16 pixels short
of the tile edge at the pitch of 1040. The Clear operation above takes those tiles whole now.

### Draws that can write nothing (2026-10-14, non-CPU group)

`sasrt_gpu_skip_dead_draws` (on; off: `configs/sasrt_test_dead_draws_off.toml`). The table above showed two whole
surface imports a frame for a draw that writes nothing. This renderer answers the game's occlusion queries on the CPU
(`EVENT_WRITE_ZPD`, a fixed count), so such a draw changes nothing at all, yet its EDRAM preparation moved its targets'
tiles into their views first. The key skips, before the EDRAM preparation (like Direct3D's null-shader draws), every
draw in EDRAM mode 4 that can write nothing:
- no colour: the depth-only EDRAM mode (no pixel shader runs), or in the colour mode no target that the pixel shader
  writes and the colour mask leaves on (the bound-range plan's own rule: any other target is not bound);
- no depth write (a depth test with depth write on), no stencil write (stencil off, or on both faces a write mask of 0
  or every op KEEP);
- no memory export by the vertex shader (the renderer emulates no pixel shader export).

Verify mode draws them as before and checks that the renderer's own write analysis publishes nothing for any of them
(a disagreement is a `DIFFERENCE:` line). The 10 s line `draws that can write nothing` counts them.

**Measured** (PC, the console's settings, the same race; `sasrt_332` without the key, `sasrt_333` with it): 40,000 to
52,000 draws skipped every 10 s (130-170 a frame; not broken down by kind yet), tiles moved 1,878,929 -> 1,580,700 every 10 s (-15.9 %), colour -> depth 713,554 -> 410,343, whole
surface colour -> depth runs 1,196 -> 600. The transfers did not move to a later draw. The PC's EDRAM import time fell
from 3.6-3.7 to 3.1-3.3 ms a Swap (its GPU is shared and noisy). Verify mode (`sasrt_334`, track 2.3, the console's
settings): 309,025 dead draws drawn and checked, none that the renderer's analysis would have written to; 0
differences in every other check.

### banjo-nx's step 4: the ring's per-draw cost (2026-10-15, CPU group; the user's request relayed by banjo-nx)

The user asked through banjo-nx for its steps 3 and 4 to be done here the same way, and then for the heavy scene
shaders. banjo-nx's step 4 is two exact ring items (its docs/d3d-native.md, "Step 4"): the sampler cache invalidated by
range, and 16-bit indices kept across frames in its persistent vertex arena.

**`sasrt_cpu_ring_texture_invalidate_range`** (banjo-nx's `banjo_ring_texture_invalidate_range`). A resolve that
changes what an address is sampled from (a new resolved texture, another swizzle, a parked image swapped in, new
content under a crop: `GetResolved`, `ResolvedWritten`) cleared the whole sampler cache. Now it clears only the entries
whose texture memory can overlap the resolved range: the fetch constant's base level and mips at 16 bytes a texel on
32x32 tiles, every layer (never smaller than the real footprint), against 16 bytes a texel of the resolved size, old
shape and new. The per-fetch table is scanned only over the slots filled since the last whole-cache clear (a list
kept as they are filled). The other whole-cache clears (an image prepared, a resolved texture retired) stay.
Verify mode prepares every entry the whole-cache rule would have cleared again and compares slot, heap, sampler and
size; a difference turns the rule off for the session.

Measured (PC, the console's settings, the race; `sasrt_335` before, `sasrt_338` with it; per 10 s): the per-fetch
table's misses 76,757 of 242,539 lookups (31.6 %, 73,145 of them by whole-cache clears) -> about 16,200 (6.7 %); about
3,600 resolves cleared about 15,200 entries instead of the whole cache; the ring's texture stage 0.43 -> 0.28-0.31 us
a draw. Verify mode (`sasrt_339`): 196,141 kept entries prepared again and compared, 0 differences; 0 differences in
every other check.

**`sasrt_cpu_ring_index_persistent`** (banjo-nx's `banjo_ring_index_persistent`), on its persistent arena
(`vertices_persistent.h`, banjo-nx's `banjo_vertices_persistent.h` as it is). A 16-bit index range whose bytes were the
same in three frames gets a block of the arena (64 MB, `sasrt_ring_vertex_persistent_mb`) with its converted indices
and their range; later draws bind the arena as the index buffer and convert and copy nothing. A block is used only
while its guest bytes are the ones it was made from: within a synchronization interval (the dedupe's rule), for
draws the game had already submitted when the bytes were last read (`sasrt_ring_vertex_persistent_submitted`: the ring
now counts its place in the stream, banjo-nx's `RingProgress`), and otherwise after fingerprinting the range again.
The first 4096 uses, one in 4096 after them and every one in verify mode are converted again and compared; a
difference turns the arena off for the session. One change from banjo-nx's order: the arena forgets its interval
before the index lookup (banjo-nx forgets in the vertex stage, after its index lookup, so the first draw after a
synchronization point could take an index block as proven by the interval that point ended).

Measured (PC, the race, `sasrt_342`, per 10 s): 587,625 draws took their indices from the arena, 1,228 MB neither
converted nor copied (about 4 MB a frame); 149,319 ranges fingerprinted again; 261 ranges put into the arena; it held
7,580 blocks in 15 of its 64 MB; 0 differences. Verify mode (`sasrt_343`, track 2.3): 795,306 uses converted again
and compared, 0 differences (and 192,338 kept sampler entries, 0 differences); 0 differences in every other check.

**`sasrt_cpu_ring_vertex_persistent`: ported, OFF.** banjo-nx's arena keeps one block per vertex window. This game
draws many overlapping windows of very large vertex buffers: by the containment report a race frame references about
130 MB of windows (per 10 s 9.9 GB copied as merged unions, 24.5 GB inside larger copies, 4.9 GB by the same-range
dedupe). With a block per window the 64 MB arena filled within a second of the race starting and gave up for the
session (`sasrt_340`), also with windows capped at 256 KB (`sasrt_ring_vertex_persistent_max_kb`, `sasrt_341`). A
cache across frames for this game has to keep whole vertex buffers (docs/plan.md, "a vertex cache across frames").
The code stays (the index half uses its arena); the vertex bindings now record each binding's buffer as well as its
offset, so arena, mirror and upload-buffer bindings mix without rebinding everything.

**Step 3 (banjo-nx: "measure your remaining EDRAM categories before investing").** With the Clear operation and the
dead-draw skip, this game still moves about 1.55 million tiles every 10 s, and they are real work: a depth the game
restores through a colour alias and reads with a depth test, and first draws over a surface last used in another
format (the table in "banjo-nx's EDRAM traffic items" above). The EDRAM draw memo already prepares 80-88 % of the
draws in constant time. A rewrite from tiles to surfaces would not remove those reinterpretations, so it is not done;
banjo-nx came to the same conclusion for its game. The PC's EDRAM GPU time is about 9.3 ms a frame now.

**`sasrt_diag_gpu_groups`** (banjo-nx's `banjo_diag_gpu_groups`, measurement only): the 10 s "GPU time by pass" report
splits every pass by the state of its draws (1: alpha test, blend, depth write, depth test, no colour write; 2: also by
pixel shader), 48 lines then. `configs/sasrt_test_gpu_groups.toml` turns it on for the console.

**The heavy scene shaders: the first table** (PC, the race, `sasrt_344`, mode 2; the PC's GPU is shared, so the times
rank rather than measure). Per frame: resolves (copies) 3.6 ms, the four EDRAM categories 5.7 ms; in the scene passes
PS n1349 1.35 ms (depth test and write, opaque), PS n1116 1.32 ms (depth test and write, no colour), PS n1538 2.3 ms
(blended, two states), PS n1635 1.0 ms, PS n1457 0.8 ms, PS n292 0.55, PS n1819 0.54, PS n1129 0.48, and Direct3D's
own clear shader PS n419 about 2 ms (its clears drawn as rectangles). Unlike banjo-nx's game (one cascade-shadow
material of about 400 statements at about 30 ms a frame), no single shader dominates here: PS n1349
(`ps_ad8d0da001d9af82`, `tools/shader_numbers.py`) is a G-buffer shader with 3 texture fetches and about 60 ALU
instructions writing 3 targets. The console's own table (the config above) decides where the GPU work goes next.

Offered by banjo-nx and **not ported** (2026-10-15): `banjo_gpu_early_alpha`, a build-time copy of an alpha-tested
pixel shader's alpha computation that discards whole failing quads before the rest of the shader (banjo-nx: -9 to
-10 % on its alpha-tested groups). In this table no group among the 48 listed has the alpha test on (0 of the 5,027 ms
of scene groups every 10 s), so it would have nothing to act on here; it needs a shader package rebuild too. To
revisit if the console's table shows alpha-tested groups (state 600xx with bit 1 set).

**`masseffect_native_vs_pruned_outputs` never worked here, until 2026-10-15** (banjo-nx's shader-size findings, item 5:
"check that every specialization constant the renderer passes is declared by your shaders"). The renderer passes
specialization constant 60 (the input locations the pipeline's pixel shader reads, from its SPIR-V) to every vertex
shader, but the translator never declared it: all 2,033 shaders declared constant 0 only, Vulkan ignores an undeclared
constant, and every vertex shader computed all 22 outputs whatever the pixel shader read. banjo-nx found the same in its
port. Fixed as banjo-nx did: `shader_common.h` declares `[[vk::constant_id(60)]] g_PsInputs` and `BANJO_PS_READS(L)`,
and the translator sets every output the pixel shader does not read to 0 at the vertex shader's exit (608 of the 609
vertex shaders; locations in `INTERPOLATORS` order, the pixel shader's input order too), so the math that only fed them
folds away when the pipeline is specialised. Exact by construction: an output set to 0 is one no stage reads. The
shader package was rebuilt (2,033 shaders, 0 failures; 63,262,128 bytes, the old one in `out/shaders_backup_1015`).
Offline, specialised as the driver does (banjo-nx's `tools/shader_size.sh` method, DXC `-Oconfig` with the constants
frozen and folded): 40 vertex shaders 19,716 -> 17,854 body instructions (-9.4 %) for a pixel shader reading TEXCOORD0-2,
a depth-only pipeline's vertex shader 317 -> 225 (-29 %).

**Over every shader** (the same offline method, all 2,033): vertex shaders 310,248 -> 285,228 instructions (-8.1 %)
for TEXCOORD0-2 pipelines and -21.2 % for depth-only ones; pixel shaders 1,883,564, untouched by this fix; all shaders
2,193,812 -> 2,168,792 (-1.1 %). The pixel shaders are 86 % of the code.

**Against Sonic Unleashed** (UnleashedRecomp-NX's built shader cache: 1,385 SMOL-V entries decoded with its own copy of
smol-v, then both games' SPIR-V specialised the same way: constant 0 = 0, frozen, folded, spirv-opt `-O`, body
instructions counted; scratch `compare_unleashed.py`, 2026-10-15):

| | Unleashed | sasrt-nx |
|---|---|---|
| Pixel shaders | 1,096 | 1,424 |
| median / mean | 1,620 / 1,492 | 992 / 956 |
| 90th percentile / heaviest | 2,005 / 2,542 | 1,541 / 3,699 |
| Vertex shaders | 289 | 609 |
| median / mean | 832 / 809 | 327 / 410 (constant 60 at "every output") |
| 90th percentile / heaviest | 1,176 / 1,325 | 492 / 5,370 |

This game's typical pixel shader is about 40 % smaller than Unleashed's; four exceed Unleashed's heaviest (the largest,
`ps_c8053b6370f39e60`, has 50 texture fetches). The GPU table's costliest pixel shaders are small: PS n1349 405, n1538
381, n1116 103, n1635 5, n1129 2,523 (Direct3D's clear shader n419: 6): their GPU time is the pixels they cover
(full-screen passes, the three-target G-buffer), not their length. The outliers are vertex shaders: the five largest
(3,687-5,370, four times Unleashed's heaviest) are the 16-fetch computed-index (bone palette / morph) shaders that
banjo-nx's item 4 halved in its game. These are SPIR-V counts, not the console's machine code (banjo-nx's shader.md
gives Unleashed's console figures: pixel shaders median 554 NAK instructions, heaviest 820-963).

Banjo-nx's other shader-size items, measured here: (1) HLSL 2021 short-circuits (`?:`, `&&`, `||` become branches that
NAK keeps): this game's heavy pixel shaders have none in their bodies; the 777 ternaries over all 2,033 shaders are
nearly all the 738 kill tests; the heavy shaders' `?:` / `&&` test only specialization constants, which the driver
folds. (3) Bool constants per pipeline: does not apply, no shader of this game tests a bool constant (0 of 2,033).
(4) Bone-palette fetches without branches: applies to the 24 vertex shaders with computed-index fetches, among them
the five largest shaders of the game. (2) Texture signs per fetch constant: applies to the 7,119 pixel shader fetches
in draws with a signed texture. Items 4 and 2 were ported the same evening and item 1 tried (below).

**Item 4 ported, item 1 tried and taken out (2026-10-15, evening).**

- **`sasrt_gpu_vfetch_block`** (on; off: `configs/sasrt_test_vfetch_block_off.toml`): a computed-index vertex fetch
  (`banjoVfetch`, the bone palettes and morph targets) read its words one by one, each behind a test and a branch
  (`banjoVfetchWord`: 0 when the index is outside the buffer). Now `banjoVfetchWords` loads the element's words with
  no branch: each at its index clamped into the buffer, replaced by 0 when the index is outside it, the same value the
  old test gave. An empty buffer still gets a readable address (the upload buffer's start, written by the renderer),
  where one word is loaded and thrown away. The old form stays in the package behind specialization constant 62
  (`g_OldForms` in `shader_common.h`, bit 0): constant 0 has no free bit in this port, and banjo-nx's 61 is its
  per-slot texture signs. Verify mode checks, on every draw that uses it, that each fetch buffer's address and last
  word lie inside the upload buffer or the memexport mirror.
  **What it touches:** 24 vertex shaders have computed-index fetches, but only 14 have real fetches: 16 fetches each
  of four floats (format 38, stride 16), so 64 word loads per vertex. The other 10 are the containers before Direct3D
  patched their fetch formats for a vertex declaration (format 0, stride 0, offset 0; the patched copies are the
  package's variants): their fetches read nothing in either form, and their modules did not change.
  **Measured** (the previous package against the new one, all 2,033 modules; only those 14 changed):

  | the 14 changed vertex shaders | before | after |
  |---|---|---|
  | instructions, specialised and optimised (`spirv-opt -O`, the Unleashed comparison's method) | 56,132 | 43,092 (-23.2 %) |
  | instructions, specialisation folding only (what the driver is handed) | 65,198 | 54,964 (-15.7 %) |
  | conditional branches | 4,002 | 1,986 (-50 %) |
  | largest shader (`vs_0dbcf812957c21ba`) | 5,370 instructions, 374 branches | 4,432, 230 |

  The off side of the A/B is the old form inside the new modules: offline it is larger than the previous package's
  code (63,514 instructions, 4,674 branches for the 14), because DXC shaped the code before knowing which form the
  pipeline takes. The A/B therefore favours the new form slightly; the honest "before" is the previous package's
  column above.
- **Item 1, `select()` / `and()` for the translator's `?:` and `&&`**: ported (the kill tests and predicate updates,
  each of banjo-nx's 12 sites), built, measured, and **taken out again**: 747 pixel shaders changed bytes but not one
  instruction or branch, specialised either way. DXC already writes an `OpSelect` for every form this game's shaders
  have: the operands are constants (`-1 : 1`, `0.0 : 1.0`) or one addition, which it evaluates unconditionally (the
  old package's kill test is `OpSelect %int %c %int_n1 %int_1`; the only branch is `clip`'s own discard, which both
  forms have). A key that changes nothing would only cost a console A/B run, so the translator is back to its previous
  form and those modules are byte-identical to the previous package's.
- **`sasrt_gpu_texture_signs_per_slot`** (item 2, ported at the user's request before the console test; on; off:
  `configs/sasrt_test_signs_per_slot_off.toml`). Every texture fetch tests its slot word for signs, a gamma curve,
  an integer width and an exponent bias (`masseffectApplyTextureSigns`, `masseffectApplyTextureBias`); that code is
  most of a heavy pixel shader (specialised with no texture tested, PS n1349 405 -> 198 instructions, ps_9041 n1129
  2,523 -> 487, every conditional branch gone). `sasrt_gpu_no_texture_signs` removes it only when no texture of the
  draw has any of those: **24-26 % of the draws** in a race. `sasrt_diag_texture_signs` (new, measurement only) counted
  the rest (`sasrt_347`, per 10 s): 74-76 % of the draws have such a texture (gamma albedo textures, the lighting
  volumes, FXAA's biased fetches), about 70 % of those also fetch textures without, and **60 % of their fetch
  registers** have none. The costliest scene shader, PS n1349 (the G-buffer shader), is such a draw every time.
  Now specialization constant 61 (banjo-nx's number; `g_SignSlots`, `BANJO_SLOT_SIGNS(r)`, `sN_Signs`) has a bit per
  fetch register, cleared by the renderer for registers 0-15 whose slot words have nothing above the heap slot, and
  each fetch skips both steps when its register's bit is clear: the path such a fetch takes at run time anyway. The
  bits live in the pipeline key's spare word (`fill`, always 0 until now, renamed `no_signs` as in banjo-nx), so
  prewarm records of earlier builds stay valid (0 = every fetch keeps its tests). Registers 16-31 keep their bits:
  the renderer writes no slot word for them, and their `sN` names alias the other heaps' words. Differences from
  banjo-nx's: this port's condition is bits 12-31 (signs, integer width and exponent bias), not only the signs, and
  its 1D fetches take the flag too (they apply both steps here). Verify mode checks every slot word of the draw
  against the bits.
  **Measured offline** (the new modules, constant 61 as the renderer would set it): PS n1349 with one of its three
  registers signed (register 1, its albedo) 405 -> 267 instructions and 12 -> 4 conditional branches; ps_9041 with one
  of its registers signed 2,523 -> 556. At the default (every bit set) a sample of 40 pixel shaders has exactly the
  previous package's counts (33,352 instructions both): pipelines without the key get the code they had.
  **On the PC** (`sasrt_348`, the race with the console's settings): per 10 s about 223,000 draws took the per-register
  form and 130,000 the per-draw bit; 293 pipelines in the map at the end of the race against 264 without the key
  (`sasrt_347`, +11 %: the per-register variants; the prewarm list covers them in later sessions); the picture as
  before. Verify mode (`sasrt_349`): both new checks ran (about 2,000 skinned and 500-800 per-register draws per
  10 s at verify's speed) and found nothing; the run's one `DIFFERENCE` is the native Direct3D layer's known
  `DrawIndexedVertices` byte (above, unexplained, unrelated to the renderer).
- **Package:** 2,033 shaders translated and compiled, 0 failures; 65,149,932 bytes (63,262,128 before: the old fetch
  form kept beside the new one, and the per-register tests).

### The renderer's GPU work

`masseffect_native_vs_pruned_outputs`, `_normalized_remap`, `_z_early`, `_ps_alpha_only`, `_no_ps_no_color`,
`_skip_invisibles`, `_skip_cleared_repeated`, `_pass_narrow_dependency`, `_pass_area_util`, `_zcull`, and sa2-nx's
`sa2_native_edram4_clear_color0`, `sa2_native_pass_narrow_end`, `sa2_native_constants_dedupe`: plain cvars of the
renderer, on in the code, set back to the previous path by `sasrt_noncpu_enhancements = false`.
`masseffect_native_pipelines_prewarm` (recreates the pipelines of earlier sessions at start, so the first race does not
stutter) is turned on by `app/sasrt_switch.toml`.

### The GPU round of 2026-11-08 (non-CPU group; Renut's renderer after the move to the ultimate base)

Fifteen pixel-identical GPU optimisations, each its own `sasrt_gpu_*` key (`app/src/renut_engine/gpu/sasrt_gpu_round.*`)
and in-run A/B target (90 + its number), counted in the 10 s `[sasrt gpu]` line: draws that can write nothing skipped,
depth decompressed only when written (and the barrier after it merged), plain fetches and 1x draws compiled without
their emulation code (constant 926, passes `plainfetch` and `onex`), the alpha test specialization, the face sign
without its reciprocal (constant 928), the gamma ramp copied once, the readback barriers merged, the memexport seeds,
fetch copies and readbacks and the 1x1 luminance readback on the 3D engine instead of the copy engine, buffer barriers
that keep the shader code cache. Two are off by default until a console run: tiled caching and depth decompressed
right before its read (Ryujinx emulates neither). Details, evidence and checks: `docs/gpu-round-1108.md`.

## Build-time: the codegen flavour (one NRO, optimised)

These cannot be switched at run time. The SD card gets one NRO, the optimised codegen: the user's rule of 2026-10-06
(relayed through sa2-nx) is no classic / optimised A/B pair of NROs any more. Build-time changes go into this build,
and features are compared through their keys and the premade configs. The PC tree is built in the same flavour, so the
PC runs test the code that ships.

- `tools\codegen.ps1` (default `-Flavor optimised`): copies `app/perf_overrides.toml` into `app/codegen_flavor.toml`
  (included by the manifest) and runs the post-codegen steps.
- `tools\codegen.ps1 -Flavor classic`: the generator's plain output, for diagnosis on the PC only (is a problem the
  codegen's?). `tools\win\package_switch.ps1` refuses a classic NRO (`tools/check_switch_build.py --flavour-only`).

`tools\win\build_switch_package.ps1` makes the console build: codegen if `app/generated` is not the optimised flavour,
the NRO, `tools/check_switch_build.py` (the flavour, the self-loops below, the NVK SDK's driver) and, when the checks
pass, the SD folder. Log: `out\switch_build.log`.

Both write `app/generated/codegen_flavor.txt`; the build puts it in the `[enhancements]` line. `tools/post_codegen.py`
runs the steps, and `app/CMakeLists.txt` appends it to the generator command the PC build re-runs by itself when an
input changes, so the steps cannot be dropped silently (futari-nx's finding).

The optimised flavour adds sa2-nx's set of codegen options (masseffect-nx's measured ones that need no per-function
marks): `cr_as_local`, `ctr_as_local`, `xer_as_local`, `reserved_as_local`, `skip_msr`, `dform_disp_split`,
`fctiwz_inline`. This game has no setjmp/longjmp, so the locals never need restoring after one.

Since 2026-10-07 (the codegen round for the game threads) it also has `non_volatile_as_local` and `elide_lr_stores`,
and the game code is compiled with `-fno-math-errno -fno-trapping-math` (masseffect-nx: `non_volatile_as_local`
+9 % frames per second; the "diet" with `elide_lr_stores` -10 % main thread). Static counts on the generated C++
(code generated with the previous options and `thunks.toml` in `out\nvl_old`, whose manifest is kept, against
`app\generated`; same game, same generator):

| | before | after |
|---|---|---|
| `ctx.r14`-`ctx.r31` uses | 669,839 | 1,586 (the SEH funclets, which keep ctx, and the calls handing registers to them) |
| `ctx.f14`-`ctx.f31` uses / `ctx.v14`-`v31`, `v64`-`v127` uses | 43,933 / 19,182 | 0 / 19,182 (kept, see below) |
| calls to the register save/restore helpers | 29,172 | 272 (the VMX ones, kept) |
| `ctx.lr = <return address>` stores before calls | 158,515 | 0 |

Why they are exact here:

- **Vector registers stay in ctx** (`non_volatile_vector_as_local = false`, an option added to this SDK on
  2026-10-07, ~08:20; banjo-nx's finding). `tools/read_before_write.py` used to take every vector instruction for a
  memory store, since each is written as `simde_mm_store_*(vD, ...)` into its destination register. So no vector
  register read before its write was ever reported, and its clean result covered the GPRs and FPRs only. Fixed, it
  finds 9 functions that read v29, v120 or v124-v127 on some path before writing them. All are uninitialized registers
  on rare or impossible paths: `sub_827772F0` and `sub_82E3D098`, the bounds of an empty list, add the caller's v126
  and v127; `sub_82C6CFF8` uses v126 when none of its three branches set it. On the 360 such a read gets whatever the
  caller chain left there, and with locals 0. Only ctx keeps that exact. So v14-v31 and v64-v127 stay in ctx in every
  function, with the `__savevmx_N` / `__restvmx_N` calls that preserve them. That is the pre-tonight code for vectors:
  19,182 uses, against the 713,772 GPR/FPR uses the round removed. The NROs packaged between 04:36 and 06:36 had the
  vector registers as locals.
- `non_volatile_as_local` keeps r14-r31 and f14-f31 (and, without the option above, v14-v31 and v64-v127) in C++
  locals that start at zero, and drops the calls to the save/restore helpers (the VMX ones stay with the option
  above). A function that reads one of them, or cr/ctr/xer, on some path before writing it
  would read zero: a fragment split off its owner needs `share_registers`. `tools/read_before_write.py` (flow-sensitive)
  on code generated with the option and no marks finds 3 of 134,918 functions, all false alarms checked by hand:
  `sub_82CBCB10` and `sub_82CBCEA0` (`xor r30,r30,r30`) and `sub_82D9F208` (`subfe r29,r29,r29`, CA - 1 whatever
  r29 held). The generator marks the SEH funclets itself (its funclet sweep): those 86 are the only functions that keep
  ctx, and all 31 calls to them hand the registers over (the line before each call copies the caller's locals into
  ctx).

  futari-nx's crash with this option (2026-10-07, 72 marks of its own) came from marked functions reached by an
  indirect call. The generator hands the registers over only around direct calls, not around
  `REX_CALL_INDIRECT_FUNC`. Here nothing can be reached that way: the funclets have no indirect entry (none is a
  jump-thunk target, through which this game's vtables and callbacks go). This SDK also never dispatches a guest
  exception to them: `RtlRaiseException` breaks on C++ exceptions, and `generate_exception_handlers` is off, so a
  fault inside a guest `__try` is fatal with or without the option. No function keeps a constant in v64-v127 across calls (banjo-nx's engine does), and no native hook reads
  `ctx.r14`-`r31` or `ctx.f14`-`f31`. The same check on the earlier flavour (cr, ctr and xer as locals) finds none
  either: banjo-nx's cr hazard (a fragment that starts with `bne cr6` on its caller's compare) does not occur here.
- The helpers are dropped by name, and 82 of their entries had lost it: `tools/thunk_table.py` declared every jump
  thunk target as a function, these included, and a CONFIG function replaces the generator's HELPER one under the name
  `sub_X` (30 GPR, 28 FPR and 24 VMX entries; sa2-nx and banjo-nx have all their names). The script now leaves them to
  the generator. Every helper call of the game is a direct `bl`/`b`, none goes through those thunks.
- `elide_lr_stores`: all 33,013 `mflr` results in the generated code are prologue saves (21,050 to the stack frame,
  the rest handed to the save helpers), the one `blrl` jumps to an explicit `mtlr r3`, and nothing in the SDK or the
  app reads the guest LR except the diagnostic `sasrt_d3d_trace`, whose "from" column now needs code generated
  without `elide_lr_stores`. The console profiler samples the host x30, not the guest LR. (The phrase "classic
  codegen" must not appear in a string of the app: `tools/check_switch_build.py` reads the flavour from the binary's
  strings, and a cvar description saying it failed the 05:14 package.)
- `-fno-math-errno -fno-trapping-math` (sasrt_recomp only): no errno check and library call after each `fsqrt`, and
  floating-point operations free to be scheduled as if they never trap. Values are unchanged; nothing reads errno or
  the host floating-point exception flags.

`fp_moves_modeless` (2026-10-07 ~06:10, sa2-nx's round 7, the generator option ported from its SDK). The 360's VMX
unit flushes denormals and its FPU does not, so the generator switches the host's flush mode around scalar float
instructions in VMX code. On AArch64 every switch is an `msr fpcr`, which the A57 serializes: sa2-nx's VMX-heavy game
thread spent 20-26 % of its console samples right after one, and this game's NRO had 29,792 of them.

With the option:
- Float moves (`lfd`/`stfd` forms, `stfiwx`, `fmr`, `fabs`, `fnabs`, `fneg`) switch nothing: only bits move.
- In VMX mode, `lfs`/`stfs` convert through `rex::ppc::SingleToDoubleAnyMode` / `DoubleToSingleAnyMode`, which give
  the IEEE result in either mode. Only a denormal single, or a result in the single denormal range, takes a cold path
  that clears the mode for that one instruction. That is 3,427 conversions in this game's code.
- `msr fpcr` instructions in the NRO: 29,792 -> 23,339 (-21.7 %; sa2-nx: -12 %). How many sat in hot loops, the
  console profile will say (samples right after an instruction 0xD51B44xx).
- Exact by construction: sa2-nx unit-tested both modes, and its lockstep frames stayed pixel-identical.

`non_argument_as_local` (2026-10-07 evening, sa2-nx's, with a vector rule of this port's own): r0, r2, r11, r12 and f0
become C++ locals of each recompiled function. MSVC uses r11, r12 and f0 as scratch everywhere, and this game also
loaded r11 before every call through a jump thunk:

| `ctx` uses in the generated code | before | after |
|---|---|---|
| r11 | 1,173,135 | 14,813 |
| r12 | 110,758 | 7,030 |
| f0 | 58,448 | 530 |
| r0 / r2 | 1,782 / 2 | 50 / 1 |
| ctr (with the thunk step below) | (3 per inlined thunk call) | 4,602 |
| v32-v63 | 119,216 | 119,216 (kept, see below) |

What is left is in the functions that keep these registers in `ctx` (below), the hand-overs around calls to them, and
the generator's publish of r11 and ctr around the 22,506 indirect calls. 119,846 of the 134,918 functions localize
them.

- **Why it was left out:** a value can no longer cross a call in these registers, so every place where one does had
  to be found. `tools/non_argument_audit.py` (sa2-nx's, whole program; here it first splits the inlined thunk calls
  into their statements) on code generated without the option, with the calls that never return named
  (`--noreturn=82C8D170,8240A2B0,824A0680,82438D50,82C94FE8,823DD260`: the throw path, KeBugCheck's and
  ExTerminateThread's jump thunks, `_CxxThrowException` and its thunk):
  - **read on entry:** the EH/SEH funclets (r12, the owner's frame; `share_registers` already, their owners hand it
    over), the `__save*`/`__rest*` helpers (r12/r11), the stack probe `sub_82C8EEC4` (the frame size in r12, called
    through its jump thunk `0x824A3E60`), 15 vector functions (below), a one-instruction gap fragment `sub_82CA79B4`
    that reads r2 and four helper copies at 0x8302A954-0x8302AA90 (none of the five is called or named anywhere);
  - **read after a call:** 58 callers of the stack probe go on with its r12 (`stwux r1,r1,r12`); one owner reads the
    r11 its `__finally` funclet loads (`sub_82CB5018` after `sub_82CB50E0`, `share_registers`: the generated
    copy-back takes it);
  - **r2:** written only by the CRT's context restore `sub_82CA77CC` (from a CONTEXT record; jump thunk `0x82441870`).
- **The generator:** `non_argument_as_local_keep` (sa2-nx's option, ported into this SDK): the stack probe, the
  context restore and their two thunks keep r0/r2/r11/r12/f0 in `ctx` and localize the rest; so do the save/restore
  helpers, by name (the VMX ones are still called here). A caller hands its locals over around a call to one of them
  and takes them back after a `bl` (`emit_call_handing_non_arguments`). `non_argument_vector_as_local = false` (a new
  option of this SDK) keeps v32-v63 in `ctx`: 15 functions read lanes of them they never wrote (vrlimi128 blends,
  vsldoi shift registers, element-wise operations on part of a register). The 360 gives them the caller's bytes, a
  local would give zeros, and `tools/vec_shiftout.py` (sa2-nx's prover) does not model their instructions
  (vlogefp128, vmrghh, vperm128). With both options off the generator's output is unchanged.
- **Checks on the generated code (with the option):** `tools/non_argument_audit.py --with-option`: every call to a
  function that keeps these registers in `ctx` hands over what the callee reads on entry (0 missing), no value is
  read after a call without its copy-back (0), and the only functions that read a localized register before writing
  it are the five uncalled ones above. `tools/read_before_write.py --volatile` lists the same uncalled ones.
- **The thunk step under the option** (`tools/thunk_calls.py`): the thunk's r11 is its own local, and the generator
  publishes it and ctr in `ctx` for the indirect call. Only a function that keeps r11 in `ctx` can read it there (41
  do: the helpers, the funclets, the keep list), and no function of this game reads `ctx.ctr` at all except to
  publish or restore it (ctr is a local everywhere with `ctr_as_local`; the step checks both on every run). None of
  the 41 is a thunk target, so all 127,349 inlined thunk calls and the 62,351 thunk bodies (the calls through
  vtables) are now the plain call `sub_target(ctx, base);`, which `tools/direct_calls.py` makes direct: no r11 store,
  no save, set and restore of `ctx.ctr` per call, and callees the compiler can inline. A target that reads one of
  them would get both published for the call, as the thunk does.
- **Checked (PC, verify mode, the console settings, everything else on):** tracks 2.3, 0.0 and 3.0 (`sasrt_270`-`272`),
  0 differences in every check; the native Direct3D layer compared 2.70 M, 2.01 M and 2.73 M calls with the original
  run on a device copy, 0 differences. The first run with the new code (`sasrt_269`) logged one native-layer
  difference, one byte of guest memory (`guest byte FF2DF501`, a drawing thread, late in the race), and it did not
  come back in the 7.4 M compared calls after it. Likely a race, not proven: the compared regions are the bound vertex
  shader object and its programs, every draw that loads a vertex binding writes the device's next fence into the
  shared object, and two threads draw. The message did not say which region; it now names the region, the byte
  before the call and the thread, to settle it if it comes back.
- **Size:** the PC executable 54.6 MB with the option alone, 47.3 MB with the plain thunk calls too.
- **Measured (PC, two runs of the same race of track 2.3 with the same in-run A/B, `sasrt_268` before and `sasrt_274`
  after; the second also has `sasrt_cpu_ring_identity_memo`; separate runs, so other projects' load adds noise):**
  all threads 20.53 -> 17.19 s of CPU per 10 s (-16 %); the game threads Main XThread 3.74 -> 2.60 s (-30 %),
  SlRenderer 2.37 -> 1.58 (-33 %), Model Instance Threads 1.08 -> 0.80 (-26 %), SlAnimManager#0 0.80 -> 0.60
  (-25 %), SlParticleThread#0 0.50 -> 0.36 (-28 %), AK::EventManager 1.08 -> 0.91 (-16 %); whole-process CPU per
  Swap in the race windows 97.5 -> 87.2 ms (-10.5 %). The ring thread spins at the PC's frame cap, so its CPU says
  little here. The PC build has no LTO; the console runs the same code with it.

Then four post-codegen steps:

- `tools/pch_no_volatile.py`: guest memory accessed without `volatile` (masseffect-nx: +15-20 % frames per second).
- `tools/thunk_calls.py` (this game's): nearly every call goes through a 16-byte `.xidata` jump thunk, which the
  generator writes as a load of the target into r11/ctr and a dispatch-table lookup with an indirect call. The step
  rewrites the 127,648 call sites of the 62,436 thunks whose target is a function of the module into what the thunk
  does: `ctx.r11 = target; ctx.ctr = target; sub_target(ctx, base);`, and the thunk bodies themselves into direct
  calls (for the calls through vtables). With `ctr_as_local` the generator hands ctr to the callee in `ctx.ctr` for
  the duration of the call and restores it afterwards; the rewritten call sites did the same
  (`{ const auto s_ctr = ctx.ctr; ctx.ctr = target; sub_target(ctx, base); ctx.ctr = s_ctr; }`). Since
  `non_argument_as_local` both are the plain call (above: no target reads `ctx.r11` or `ctx.ctr`). Exact: the thunk
  only sets r11 and ctr and branches without linking; the dispatch table entry of the target is `sub_target` itself,
  and a hook replaces that symbol. Thunks named in the sources and the thunks whose target is not a function start
  are left alone.
- `tools/direct_calls.py`: calls between unhooked functions become direct (`__imp__sub_X`): 219,814 calls, so the
  compiler can see through them.
- `tools/loop_barriers.py` (futari-nx's pass 3, required with the first step): a compiler memory barrier
  (`REX_LOOP_BARRIER()`) at each of the 29,058 loop headers (a label that a later `goto` of the same function jumps
  back to). Without `volatile`, GCC hoists a guest poll out of its loop and the loop becomes a branch to itself:
  futari-nx's console hung at boot that way (172 such loops; D3D's `while (device[11012] != 0) {}`), while clang on
  the PC had not done it. The barrier keeps every iteration's loads, including those of callees inlined into the loop;
  straight-line code keeps the plain loads. `tools/find_self_loops.py <elf>` counts the branch-to-self instructions of
  a Switch ELF: the classic build has 4 in recompiled functions, the game's own halts (`b .` in the PowerPC code of
  `sub_82B36C30`, `sub_82D4C500`, `sub_82D4D350`, `sub_82E687D8`); `tools/check_switch_build.py` fails a build with a
  self-branch in any other recompiled function, so such an NRO never reaches the SD folder.

The optimised PC build's executable is 62.9 MB against the classic one's 73.0 MB (47.3 MB since
`non_argument_as_local` and the plain thunk calls).

Added 2026-10-12 (described under "The CPU round of 2026-10-12" above): the generator options `fp_compares_modeless`
and `fp_mode_lookahead`, and two more post-codegen steps, `tools/guest_cas.py` (`REX_GUEST_CAS`) and
`tools/flush_mode_flow.py` (`REX_FLUSH_KNOWN_ON` / `_OFF`), both run by `tools/post_codegen.py` after the loop
barriers. The Switch build gained `SASRT_SWITCH_OMIT_FRAME_POINTER` and `SASRT_SWITCH_FLUSH_FLOW` (both on).

#### The Switch compiler set (2026-10-07, sa2-nx's: UnleashedRecomp-NX's without PGO, at -O3)

Build options of `app/CMakeLists.txt`, all on (the NRO is built with them; `-DSASRT_SWITCH_...=OFF` for diagnosis):

- **`SASRT_SWITCH_LTO`** (**OFF by default since 2026-10-19**, the user's rule: LTO for final builds only;
  `tools\win\build_switch.ps1 -Final` / `build_switch_package.ps1 -Final` turn it on, every other build is without
  it; without it, tiny leaves still inline across files through `tools/inline_leaves.py`'s copies): link-time
  optimisation of the recompiled game (`sasrt_recomp`) and the app (renderer, natives): `-flto -fno-fat-lto-objects`
  at compile, `-flto=N -flto-partition=balanced` at the link
  (`SASRT_SWITCH_LTO_JOBS`, 3). Calls between unhooked game functions are direct (`tools/direct_calls.py`, and the
  127,349 inlined jump-thunk calls since `non_argument_as_local`), so small game functions inline across files. The
  SDK libraries stay out, and so does the registration file (`-O0 -fno-lto`: GCC -O3 never finishes it). The link
  repeats `-ffp-contract=off -fno-strict-aliasing`; xxHash is built with `XXH_FORCE_MEMORY_ACCESS=0` (nfsmw-nx: its
  default reads break strict aliasing once inlined into a key builder). The whole-program stage peaks at about 13 GB;
  the LTRANS stage compiles 512 partitions, serially (about 20 minutes) unless lto-wrapper finds `make`:
  `tools/win/build_switch.ps1` appends devkitPro's MSYS2 make to PATH for that, and with 3 jobs the whole Switch build
  after a codegen took 10.5 minutes (26.1 serially). The NRO grew from 67.1 to 68.1 MB (cross-file inlining). In the
  recompiled functions of the ELF (against the 15:21 build, before the new codegen and LTO): 7,878,640 -> 8,296,881
  instructions (+5.3 %: inlined callees are copied into their callers, so static counts no longer measure the work)
  and 3,395,434 -> 3,267,907 loads/stores (-3.8 %). The console's profile is the measure (`tools/elf_codegen_stats.py`
  gives these counts).
- **`SASRT_SWITCH_IPA_PTA`:** `-fipa-pta` at compile and link (UnleashedRecomp-NX).
- **`SASRT_SWITCH_HOT_ORDER`:** the hottest functions first in .text (`app/hot_functions.ld`, `tools/hot_order.py`,
  nfsmw-nx's orden_funciones.ld; the A57 has a 48 KB instruction cache and a small TLB for a ~60 MB image). It starts
  with `KEEP (*(.crt0))`: nfsmw-nx's NRO did not boot when the ordering moved the start-up code off address 0. The
  first file is made from a PC profile (`--pc-profile`: the game functions keep their names on both platforms; 1,043
  functions, 976 of them game functions); a console profile (`--profile logs/rex/rex_profile_NNN.log out/nx/sasrt`, the
  ELF of the build that recorded it) replaces it when one exists.
- **`tools/check_switch_build.py`** runs on every NRO before packaging: the flavour string; branch-to-self loops in
  recompiled code only at the four known guest halts, or in a function that calls one (GCC may inline a halt into its
  caller under LTO); the SDK driver's Mesa string; `_start` at 0; no vector `fmla`/`fmls` in recompiled functions
  (the generated code has none, so any would be contraction that leaked past `-ffp-contract=off`).

Checked on PC (2026-10-06, `sasrt_087.log`): the scripted boot into a race plays the same scenes with the same
frames as the classic build (video sheets of `video_150s`), the log names the build "optimised codegen", and the only
error line is the third-party Vulkan layer message every run has. The whole process used 294.6 s of CPU over the
190 s run, against 320.0 s for the classic build (`sasrt_086.log`), on a PC shared with other work: indicative only.

Checked again when it became the only flavour (PC build of 2026-10-06 17:40, 63.1 MB; `tools\win\verify_natives.ps1`
on tracks 2.3 and 0.0, `sasrt_169.log` and `sasrt_170.log`): the log names the build "optimised codegen", the native
replacements and the renderer's checks found 0 differences, 0 draws were rejected, no shader was unidentified, and
the only error line is the third-party layer's. Swaps per 10 s in the race: 2.3 167-248 (the ring thread limits this
track on the PC; the classic verify runs had 175-296), 0.0 189-301.

Risk: a guest loop that polls memory with no call or atomic inside could have its load hoisted out of the loop now that
guest memory is not `volatile`. It did happen on the console in futari-nx (GCC, not clang), hence the loop barriers;
the optimised NROs built before them (2026-10-06 06:35 and 10:58) may hang and should not be tested. With one NRO
there is no classic build on the card to fall back on: the self-loop check guards the known way this fails, and a hang
it misses shows in the console CPU profile (the spinning thread's samples, mapped with `out/nx/sdcard_sasrt.map`).

## Correctness flags (not enhancements)

`-ffp-contract=off -fno-strict-aliasing` on the generated code and the app (GCC and Clang): GCC, devkitA64's compiler,
fuses a multiply and an add that the PowerPC code rounds separately, and the translated memory accesses are
type-punned. They are always on (banjo-nx's and futari-nx's finding).

**Texture fingerprints are full again (2026-10-07, sa2-nx's finding).** `masseffect_native_fingerprints_sampling`
used to default to 8: a stable texture was rechecked with a sample (the first and last 4 KB blocks plus 1 in 8) and
fully only on 1 recheck in 8. A change in the skipped blocks then went unseen until the next full recheck, many frames
later at the long intervals of a stable texture. sa2-nx's guard caught such a miss in 56 of its 58 PC runs. None was
caught in this game's 236 logs, but nothing rules one out, so the default is now 0 (always the full fingerprint). It
costs about 50 MB/s more hashing in a race (the C3 report's "unread" bytes), roughly 0.3-0.5 ms a frame on the
console.

**The reuse epoch and the command-buffer pages (2026-10-07, banjo-nx's finding; always on).** The same-range vertex
dedupe, `sasrt_cpu_vertex_containment` and the index cache reuse an earlier copy of a range by its address within a
"synchronization epoch". After the GPU's progress becomes visible to the game, the game may legally rewrite a range it
already drew. Two holes, both inherited from masseffect-nx:
- `g_synchronizations_ring`, the epoch, was never incremented anywhere (the comment said WAIT_REG_MEM). The epoch was
  in fact the whole upload buffer, a frame.
- Direct3D recycles its command-buffer segments by the ring's read pointer, with no fence. Data written inline there
  (DrawPrimitiveUP's vertices and indices, BeginVertices) can change between two draws of one frame.

Now:
- The ring increments the epoch, in stream order, at every point where the game can see the GPU's progress:
  `INTERRUPT`, `MEM_WRITE`, `COND_WRITE` when it writes, `REG_TO_MEM`, `EVENT_WRITE_SHD` (the Direct3D fences),
  `EVENT_WRITE_EXT`, `EVENT_WRITE_ZPD`, the end of a `WAIT_REG_MEM` on memory (the game may release the GPU after
  seeing it get there and rewriting what was drawn before; futari-nx bumps at every `WAIT_REG_MEM`) and the Swap. A
  `WAIT_REG_MEM` on a register polls the GPU's own state (`COHER_STATUS_HOST` after a resolve, set by the ring itself):
  the game neither releases it nor learns anything from it.
- A bitmap of 4 KB pages marks the memory of every indirect buffer the ring runs and of the ring itself. A vertex
  window or index range touching those pages is copied and never reused by address.
- The containment line counts both ("N reuse epochs; M windows (X MB) in command-buffer pages, never reused by
  address").

Before the fix, verify mode had compared 5.7 M dedupe reuses and 0.7 M containment reuses with guest memory on four
tracks with 0 differences: the holes were not hit on those routes, but nothing ruled them out. The savings measured
before the fix (the containment's 73 %, the in-run A/B of the round) were with frame-wide reuse; they are measured
again with it.

## Verification

PC runs of 2026-10-06 (native renderer, scripted boot into a race, `out/pc/logs/sasrt_07x.log`):

| Run | Keys | Result |
|---|---|---|
| 072 | defaults + `sasrt_cpu_gpu_wait_sleep` | 280-301 Swaps per 10 s after loading; the race stretch at 29.6 fps; same scene as before |
| 073 | every CPU key of the table on (deferred recording too), verify mode | `[verify]` 0 differences over 2.59 M identity, 465 k pairing, 79 k microcode, 644 k PM4-run and 70 k object checks; but stuck in the intro (4 Swaps per 10 s from 22 s) |
| 074 | verify mode, default keys | normal rates (283 / 190 / 251 / 300 / 301 Swaps per 10 s) |
| 075 | every CPU key on (deferred recording too), no verify | 201-207 Swaps per 10 s at boot: a third slower |
| 076 | the CPU keys without the three deferred-recording keys, no verify | normal rates (285 / 188 / 250 / 301 / 300) |
| 077 | deferred recording only, GPU wait sleep off | 196-237: deferred recording itself is slower here |
| 078 | `app/sasrt_switch.toml`'s set (no deferred recording), verify mode | 0 differences (2.82 M identity, 506 k pairing, 87 k microcode, 701 k PM4-run checks); again stuck in the intro at 4 Swaps per 10 s |
| 079-082 | bisection of 078 | the stall is `masseffect_native_fast_copy` checked on every copy (verify + fast copy: 4 Swaps per 10 s; verify + the other keys: normal) |
| 083 | 078 with the vertex copy check on its first 20,000 copies | 275 / 150 / 107 / 300 / 301 / 301 Swaps per 10 s; 0 differences over 5.18 M identity, 928 k pairing, 153 k microcode, 1.31 M PM4-run and 138 k object checks |

So:

- The fast paths agree with the original paths: no `DIFFERENCE` or `MISMATCH` in any run.
- Deferred recording is slower in this game on PC and stays off in `app/sasrt_switch.toml` (a console A/B can still
  try it).
- In verify mode every check runs on every use except the vertex copy check (`masseffect_native_fast_copy_verify`):
  it re-copies each copy with the plain loop into a new buffer and compares, and on every copy the ring stalled in the
  game's intro (about 54,000 draws a second; a race has about 35,000). `sasrt_cpu_verify` checks its first 20,000
  copies (normally 256).
