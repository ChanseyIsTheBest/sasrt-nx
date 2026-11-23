# The machine-copy round, for the ultimate base (RR6 ports it there)

The user, 2026-11-11 ~09:20: "test all the final machine code optimisation stuff on console now so RR6 can implement
it and can hand it to blur"; then (relayed by the RR6 session, ~10:00): "send it to RR6 still for it to action but it
actions it for the ultimate base to be clear" — RR6 ports this into the **ultimate base**, not into rr6-nx. This is the
round of 2026-11-10 22:15 to 2026-11-11 ~08:30 in sasrt-nx
(docs/machine-copies-deferred.md has every result, audit and log). Below: what to take, in what order, how to switch
each part off, and what the console showed. Paths are sasrt-nx's; the generator tools are shared in spirit with
rr6-nx's copies of them, not byte-identical, so take the ideas with the diffs (docs/audit_roundA/, audit_batch2/,
audit_batch3/) rather than whole files.

## 1. Take first: fixes that help any port (no generator change)

| What | Where | Why |
|---|---|---|
| **The SDK profiler's 10 s report off the game's priority** (harmless, kept; the stutters were NOT the profiler) | sdk/src/ui/switch_perf.cpp (ProfilerMain, around the `Report(...)` call) | The report moved to priority 0x3B on core 3 for its duration (`svcSetThreadCoreMask(CUR_THREAD_HANDLE, 3, 1 << 3)`, back after; the 1 ms samples keep 0x2A). **The race's 200-470 ms frame every 10 s was the test bot's own screenshot** (sys-botbase `pixelPeek`, one every 10 s in tools/console_race.py's drive phase): run st_noshots (2026-11-11 10:28, the full profiler on, no screenshot while driving) had a worst frame a 10 s window of 110 ms (median) against 228-271 ms with the screenshots, and the user's own race without the bot 113 ms. Any port's console perf numbers taken with a screenshot every N seconds carry one ~250 ms stall per screenshot. |
| **The SDK's small helpers forced inline** | sdk/include/rex/ppc/diet_ops.h (`REX_SMALL_HELPER`), context.h (CRRegister::compare both forms, raw/set_raw, the flush-mode switches) | With any -Os unit (or a big hot function) GCC left `CRRegister::compare<>`, `disableFlushMode`, `SingleToDoublePure`, `QuietSingleBits`, `fctid`, `divw` out of line: 24,489 calls in bt1's NRO, and an out-of-line compare also writes the copy's CR local through memory. CMake `SASRT_FORCE_INLINE_HELPERS` (ON) / `REX_NO_FORCED_HELPERS` to undo; the option must sit before `include(generated/rexglue.cmake)` to reach the SDK's targets. |
| **No -Os cold shards** | app/CMakeLists.txt `SASRT_HOT_COLD_SHARDS` default OFF | Idea 58's -Os shards were the cause of the out-of-line helpers above. An existing build folder keeps its cached ON: `cmake -DSASRT_HOT_COLD_SHARDS=OFF` on each. |
| **Hand natives' guard repeats a difference** | app/src/hot/sasrt_hot_guest.cpp (`sasrt_hot_guard_repeat`, keep_orig, `g_range_check_depth`) | The CRT memcpy native switched itself off 5 s into a race on one byte another thread wrote between the guard's two runs. Now a difference is repeated (up to 3 passes); inputs changed by another thread = not repeated, native stays on; a range check nested in another's original runs unchecked. |
| **setFromMask NEON fast paths** | context.h, `setFromMask` for imm 0xF and 0xFFFF | `vshrq_n_s32 -> vmovn -> u64 test` / `vshrq_n_s8 -> vshrn_n_u16 #4`; exact for any imm (no `__builtin_constant_p`). |

## 2. Then: the generator ideas (each with its own switch)

All are post-codegen steps or tools/localize_native.py options; after taking them, run one PGO cycle (generate -> one
normal race of at most 5 minutes -> use; ninja does not track .gcda files, so build the use step clean or touch the
units).

| Idea | What it does | Switch (off) | Tool / runtime |
|---|---|---|---|
| 29 | Copies of the originals behind the app's hand hooks (the hooks' callees become copies too) | localize_native.py `Hooks` (without the RR6 renut_gpu_funcs.toml dependency) | localize_native.py |
| 47 | Dead link-register traffic in copies elided | CMake `SASRT_HOT_LR_ELIDE` | prelude macros REX_LR_* |
| 57 | Interleaved stvlx/stvrx pairs merged into one 16-byte store with a run-time overlap check | CMake `SASRT_HOT_MERGED_STORES` | REX_STV16 (also with SASRT_GEN_VEC_UNALIGNED=OFF) |
| 37 | Register write-backs no caller reads trimmed across copies (LiveOut from leaf_dead_stores' JSON; copy-list hooked calls count as known calls) | env `SASRT_LOCALIZE_LIVE_OUT=0` | tools/leaf_dead_stores.py writes out/leaf_live_out.json `{gen, live_out}`; localize_native.py checks the JSON's gen |
| 52 | Prefetch of the next node in pointer-chasing loops | env `SASRT_LOCALIZE_PREFETCH=0`, CMake `SASRT_HOT_PREFETCH` | REX_PREFETCH_GUEST |
| 34 | Members called with constant arguments forced inline (only `ctx.` registers not written again before the call, up to 4x the inline limit) | env `SASRT_LOCALIZE_CONST_ARGS=0` | localize_native.py |
| 60 | Straight counted loops without stores or calls drop REX_LOOP_BARRIER (the compiler hoists invariant guest loads) | env `SASRT_LOCALIZE_COUNTED_BARRIERS=0` | localize_native.py loop_info |
| 35 | The guard compares the stores made before an atomic or outside call stopped both forms (binary search per byte) | cvar `banjo_hot_guard_prefix` (instrumented builds) | banjo_hot_guest.cpp |
| 39 | Store cards batched in loops: a run marks its page once, at a page change and before every call | env `SASRT_LOCALIZE_CARD_RUNS=0`, CMake `SASRT_HOT_CARD_RUNS` | REX_CARD_RUN_DECL / REX_CARD_FLUSH; Renut checks cards at kicks; generated banjo_hot_options.h (REX_CARD_RUNS_GENERATED) |
| 31 (instead) | The store cards' r1-derived stack rule: stores through registers derived from r1 are the stack's, no card | env `SASRT_CARDS_STACK_DERIVED=0` | tools/store_cards.py `derived_from_r1`; STRAIGHT_END also stops at REX_LOOP_ / REX_LR_ |
| 43 B1 | Shuffles in f32 lanes (not the int domain) | `REX_SHUFFLE_INT_DOMAIN` | tools/pch_neon_shuffles.py |
| 43 B2 | dp_ps without the dup | `REX_SIMDE_DP_PS` | tools/pch_neon_shuffles.py |
| 43 B3 | vupkd3d (D3DCOLOR) through `vqtbx1q_u8` (704 sites here) | `REX_VUPKD3D_LANES` | tools/vupkd3d_neon.py (new) |
| 43 B4 | setFromMask movemask in NEON | `REX_SETFROMMASK_MOVEMASK` | context.h |
| 43 F3/F4 | vnmsubfp fused (`-(fma(a, b, -c))`, the 360's one rounding; the same -0 where a*b == c) and vlogefp as a NEON log2 estimate (exponent + degree-7 polynomial of the mantissa in [sqrt(0.5), sqrt(2)): ~1.2e-7 absolute, exact at powers of two; zero / denormals -inf, negatives NaN, +inf +inf, NaN kept; the 360's bound is 1/32): **ON (the user, 2026-11-11 ~10:00: "add these please")**. 2,572 vnmsubfp and 25 vlogefp sites here (the port called `log2f` four times a vlogefp) | the same two switches (vnmsubfp with `SASRT_VMX_FUSED_MADD`, vlogefp with `SASRT_VMX_FAST_ESTIMATES`) | tools/vmx_float_macros.py (REX_VNMSUBFP, REX_VLOGEFP; the default macros are the old expressions); the fuzz compares both (vlogefp by absolute error) |
| 43 F1/F2 | vrsqrtefp / vrefp as `frsqrte` / `frecpe` + two Newton steps, vmaddfp as one `fmla`: **ON (the user's decision, 2026-11-11: "keep all three on and tell ridge racer 6 to keep them on")** | CMake `SASRT_VMX_FAST_ESTIMATES`, `SASRT_VMX_FUSED_MADD` (both ON by default now; an existing build folder keeps a cached OFF: `cmake -DSASRT_VMX_FAST_ESTIMATES=ON -DSASRT_VMX_FUSED_MADD=ON`) | tools/vmx_float_macros.py (new); fuzz: cvar `sasrt_test_vmx_fuzz` |
| 46 | Census of write-once globals (8 ms sampler thread); freezing them in copies is **OFF**: unsound in general (a set-and-restore inside one call is invisible to the census) | cvar `sasrt_cpu_frozen_census`; env `SASRT_LOCALIZE_FROZEN=1` (measurements only) | tools/frozen_census.py, frozen_pick.py (new) |

Not worth taking (tested): 55 (a low-rate guard in shipping builds: +9.3 MB, ~+4 % CPU). Done by LTO + PGO already: 26,
59, 45. 51: the existing D-form split plus 60 cover it.

Two traps found on the way (both fixed here, check your copies):
- A background thread from a guest thread: `std::thread(...).detach()` threw `system_error` on the console. Use libnx
  `threadCreate` (StartBackground in banjo_hot_guest.cpp: `::Thread`, priority **0x3B**: 0x3F is refused for an
  application, core -2).
- Generator scans that track constants must stop at register writes made by macros (REX_LOOP_IN / OUT, REX_LR_READ),
  or they carry a stale value across them (batch 3's audit, finding 3).

## 3. What the console showed

Guard races (instrumented NROs, dense guard 4000 calls then 1 in 64, store-card verify on):

| Run | calls compared | differences | other |
|---|---|---|---|
| gv2 (round A) | 5,829,938 | 0 (20 differed once, not when repeated) | capture marks 0 misses |
| gv3 (batch 2) | 5,148,211 | 0 | idea 35: 5,070,584 prefixes equal, 6 not (other threads' counters); cards: 0 changed under clean cards in 30 reports |
| gv4 (batch 3) | 1,301,368 | 0 | cards: 0 changed under clean cards in 29 reports; 43 F1/F2 fuzz below |

43 F1/F2 fuzz on the console (64 M lanes each, flush mode on): vrsqrtefp 3 ulp max, vrefp 1 ulp, fused vmaddfp differs
in 2.4 % of lanes (one rounding instead of two; large only where a + b*c cancels to near 0). **The user's decision
(2026-11-11 ~09:45): all three ON, here and in RR6 (and from there Blur).** Why it is safe: the 360's vrsqrtefp / vrefp
are hardware estimates good to about 1/4096 (~2,000 ulp), and the game was written for that; the port computed them
exactly (`fsqrt` + `fdiv`, neither pipelined on the Cortex-A57: 32 of WaterThread's 207 samples in one function here);
the fast forms land within 1-3 ulp of exact, so they are not further from the 360 than the exact ones. Its vmaddfp
rounds once, as `fmla` does. Two details to keep: the fast vrsqrtefp keeps the estimate's own result where it is 0 or
infinite (`vbslq`; the Newton steps would make NaN from 0 x inf: +-0 -> +-inf, +inf -> +0), and the forms are
AArch64-only (the PC keeps the exact expressions). The macros come from tools/vmx_float_macros.py (a post-codegen step,
before localize_native.py, so the copies get them too); REX_VMX_FLOAT_HELPERS marks that the fast forms exist (the
fuzz test is gated on it).

Performance (CPU at the high clocks, where fps is capped, process CPU paired window by window): round A -3.8 %
(standard error 1.4 %) against bt1b; batch 2 against round A +0.7 % (noise); both ~2.5-3 % under bt1b. At the user's
handheld clocks (1020 / 460.8 / 1600), the final races of 2026-11-11 (Ocean View, the bot holding the accelerator, no
screenshot while driving: a sys-botbase screenshot stalls the game ~250 ms), 25 race windows each:

| Run | fps | GPU a frame | render thread | process CPU a frame | WaterThread |
|---|---|---|---|---|---|
| st_noshots: batch 3's final (fast forms off) | 26.42 | 34.13 ms | 25.94 ms | 87.8 ms | 7.49 ms |
| vmx5p: + the five fast VMX forms, a fresh PGO cycle | **27.05 (+2.4 %)** | 33.63 ms | 24.93 ms | 87.1 ms (-0.8 %) | 7.28 ms (-2.7 %) |
| fmt1: + the formats batch (section 5) | 26.91 (noise) | 33.89 ms | 24.97 ms | 86.8 ms | 7.28 ms |

Resolution the same in both (average 683-685 lines of 720, the 3D at ~0.95x of the game's 1152x544). Run-to-run spread
of one NRO is 1-2 %: the fps gain is small; the CPU gain sits where the vector maths is (WaterThread). The fast-forms build
compiled against the old profile was ~9 % slower on every thread: always a fresh PGO cycle after a post-codegen change.

The console fuzz of all five fast forms (fuzz5, 16 M random lanes each against the exact forms): vrsqrtefp 3 ulp,
vrefp 1 ulp, vmaddfp / vnmsubfp differ in 2.4 / 2.8 % of lanes (one rounding), vlogefp 7.6e-6 absolute at most (one
float step at log2 ~73; the 360's own bound 1/32). Special cases: vlogefp's are the denormal inputs (now -inf, as the
360's flush-to-zero VMX), vnmsubfp's are a NaN third operand (its sign is not flipped as the old XOR flipped it).

## 3b. Two lessons from the final races (2026-11-11 ~10:00-10:15)

- **A codegen change needs its own PGO cycle.** The fast-forms build (generated text changed in 177 files to add
  vnmsubfp / vlogefp) built against the earlier profile came out ~9 % slower in CPU on every thread, audio included
  (the size of PGO's own gain, +9.2 % fps): with `-Wno-coverage-mismatch` the compiler drops the profile silently where
  a function no longer matches. tools/win/pgo_cycle.ps1 (generate -> one normal race of at most 5 minutes -> use) after
  every post-codegen change, before any performance comparison.
- **`switch_profile_stacks = true` in the toml never turns the stack sampler on, on the console.** The profiler thread
  starts with the process and reads the key 8 s later (kStartDelayNs), but the game loads its toml ~66 s after launch
  (the NRO and asset pack load first): the key is still its default. Only logs/rex/stacks_profile.flag works. The same
  early start gives the profile file the previous session's number (ReportPath looks for the newest sasrt_NNN.log
  before the session's own exists: rex_profile_213.log for sasrt_214.log, overwriting the earlier one). Both are
  fixable by reading the key / naming the file at the first report instead of at the thread's start.

## 5. The formats batch (docs/360-precision-differences.md, the rows where the port kept more than the 360 at a speed cost)

The user, 2026-11-11 ~11:20: "implement everything on the 19 rows besides 78, 79 and 80", "useful for the ultimate base",
"turn it on by default ... as it's more accurate". Patch: docs/audit_formats/batch_formats.py (+ batch_formats_auditfix.py,
already folded in), diff docs/audit_formats/batch_formats.diff; one independent audit (its findings 1, 2, 3, 6, 7, 8
fixed: the drawn resolve copy and the blend skip take the new format, code 62's name, the per-draw lookup, format 12
following 3, the census key). Files: plume_render_interface_types.h (two formats: R10G10B10A2_UNORM, R11G11B10_FLOAT,
size / block width), plume_deko3d.cpp, plume_vulkan.cpp, plume_d3d12.cpp; Renut render/format.h, format.cpp,
surfaces.cpp, draw.cpp, textures.cpp, pipeline.cpp.

| Key | Default | What |
|---|---|---|
| renut_format_10bit_exact | ON | 2_10_10_10 targets and textures in host 10:10:10:2 (the console's own 32 bits, the same values) instead of 16 bits a channel; resolves follow (they take the target's host format) |
| renut_format_edram_as_variants | ON | the EDRAM colour formats 10 (2_10_10_10_AS_10_10_10_10) and 12 (2_10_10_10_FLOAT_AS_16_16_16_16) fell to 8-bit RGBA: now 10:10:10:2 and FP16 |
| renut_float32_point_filter | ON | 32-bit float textures point-sampled: the Xenos cannot filter them (Microsoft's XNA HiDef profile, "roughly Xbox 360 level", refuses filtering on all float formats and its Xbox 7e3 format is point-only; a 2006 Beyond3D post lists 32-bit float as "no filtering"); what the hardware does when a game asks for linear anyway is undocumented, most likely point |
| renut_format_7e3_rg11b10 | OFF | NOT exact: 7e3 targets as 11:11:10 float (half the bytes; no alpha, a mantissa bit or two less) |
| renut_depth_float_no_stencil | OFF | NOT safe as written (the audit: D24S8 and D24FS8 views share one target; PC stencil clears on a depth-only format): D24FS8 depth without a stencil plane |
| renut_diag_formats | ON | logging: the first target / texture of each format, the first stencil use of each depth target build, float textures asked for filtering |

Row 18 (CTX1 / DXT3A) not changed: no smaller host format holds them losslessly (DXT5A / DXN were BC4 / BC5 already).
SASRT itself has no 10-bit or 7e3 targets (its census: RGBA8, R32F and 16-bit fixed as FP16 colour targets; D24FS8 depth
with stencil used), so these are for the base; on SASRT the batch measured as noise and the picture is unchanged. Its one
effect here: an R32F texture the game samples with filtering is point-sampled now (the exposure readbacks unchanged).

## 4. Also new in this window (not machine copies; take if useful)

- **Renut's flash watch** (`sasrt_renut_diag_flash_watch`, on, logging only): every frame's GPU time and draw count
  against the last 31 frames' medians; a frame far under either is logged with its guest Swap. Made for the race's
  one-frame flashes (only the sky and sea drawn). video.cpp FlashWatch / NoteFrameDrawLocked, draw.cpp DrawStateLocked.
- Pacing keys tested and left off: P2 (`sasrt_pacing_input_slack`), P3 (`sasrt_pacing_queue_slack`, frames ahead 1 with
  queue-time late input; built, not yet raced), `sasrt_renut_split_draws`. The GPU-gap diagnostic line
  ("[latency] GPU waiting for work: ...") is cheap and was useful.
