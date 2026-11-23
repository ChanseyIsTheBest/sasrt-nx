# The deferred machine-copy ideas: the 72-hour round (from 2026-11-10 22:15)

The user: "work nonstop on all the deferred ideas for 72 hours or until they are all implemented, audited and
tested". The ideas and why they were deferred: docs/machine-copies-1110.md ("Not done tonight"). Order: easiest first
(the user asked for them sorted by difficulty). Each: its own key or build switch; an independent audit of its diff;
the guard on the console (an instrumented NRO keeps the guard forms); a PGO session when the generated code changed
(tools/win/pgo_cycle.ps1); a performance race against the baseline; a bisect by key / switch when something regresses.

Baseline: the 2026-11-10 batch's optimised NRO (run bt1, 22:32).

| Run | fps | GPU | render thread | recording | render-thread wait | game thread a frame | all threads a frame |
|---|---|---|---|---|---|---|---|
| lat12 (before the copies of 2026-11-10) | 25.26 | 34.08 ms | 27.70 ms | 4.64 ms | 3.98 ms | 0.604 | 2.364 |
| cp3 (1,871 copies, retrained) | 25.46 | 34.53 ms | 26.73 ms | 3.86 ms | 3.64 ms | 0.676 | 2.433 |
| **bt1 (the batch: 1,236 copies, guard forms out, -Os cold shards, capture marks)** | **25.55** | 33.89 ms | **25.63 ms** | 3.94 ms | **3.00 ms** | 0.681 | 2.379 |

(Samples a frame: the SDK's stack sampler, every thread, divided by the game frames of the profile's windows.) bt1: 0
fence timeouts, the capture marks held (201,464 deltas from marks, 36.9 chunks of 77 compared a delta, 0 misses), NRO
74.2 MB (85.6 before), CPU 262 % of 400. By group against lat12: today's added copies 0.231 -> 0.302 (+31 %, was +71 %
in cp3), the older copies -5 %, the rest of the guest +27 % (the 297 older small copies pruned by idea 30 count here
now), the host -4 %.

**What bt1 still showed (fixed in round A):** the game thread +13 % against lat12, and the profile's out-of-line
`rex::ppc::CRRegister::compare<unsigned/int>` and `FPSCRRegister::disableFlushMode` (0.0145 a frame on the game thread,
0 in lat12). The NRO's disassembly: 24,489 calls of those helpers, 23,987 of them from 699 of the 731 copies in the
-Os cold shards (idea 58) and 502 from 18 big hot copies; every cold-shard copy also called SingleToDoublePure (1,249),
QuietSingleBits (962), the flush-mode switches (3,800), fctid, divw. The generated tree inlines all of them (0 calls).
An out-of-line compare also writes the copy's condition-register local through memory. And the CRT memcpy native
(sub_82C8EEF0, a hand-written one) switched itself off five seconds into the race on one byte of a 60-byte copy from
the game image (another thread writing the source between the guard's two runs): the generated memcpy then took 108
samples (the game thread's and the sound thread's top plain function).

| Rank | Idea | Status | Key / switch | Audit | Guard | Perf |
|---|---|---|---|---|---|---|
| 1 | 55 low-rate guard in shipping | tested (r55): not worth shipping | -GuardForms build + banjo_hot_guard_period | - | r55: 0 differences | +9.3 MB, ~+4 % CPU |
| 2 | 59 shards by call graph | done by LTO (evidence below) | - | - | - | - |
| 3 | 26 copies call copies directly | done by LTO (evidence below) | - | - | - | - |
| 4 | 29 copies of the originals behind the app's hooks | implemented (round A) | localize_native.Hooks | done | | |
| 5 | 47 dead link-register traffic in copies | implemented (round A) | CMake SASRT_HOT_LR_ELIDE | done (risk noted) | | |
| (A1) | bt1's fix: the SDK's small helpers forced inline | implemented (round A) | CMake SASRT_FORCE_INLINE_HELPERS (REX_NO_FORCED_HELPERS) | done, fixed | | |
| (A2) | bt1's fix: idea 58's -Os cold shards off | default OFF (round A) | CMake SASRT_HOT_COLD_SHARDS | done, fixed (cache) | - | |
| (A3) | bt1's fix: the hand natives' guard repeats a difference | implemented (round A) | sasrt_hot_guard_repeat | done, fixed | | |
| 6 | 57 interleaved stvlx/stvrx merge (run-time overlap check) | implemented (round A): the existing merge made to fire | CMake SASRT_HOT_MERGED_STORES | done, redone | | |
| 7 | 52 prefetch in pointer-chasing loops | implemented (batch 2) | env SASRT_LOCALIZE_PREFETCH, CMake SASRT_HOT_PREFETCH | | | |
| 8 | 45 unroll the hottest loops from counts | done by PGO (evidence below) | - | - | - | - |
| 9 | 37 dead register write-backs across copies | implemented (round A) | env SASRT_LOCALIZE_LIVE_OUT, SASRT_LIVE_OUT_LISTS_NAMED | done, fixed | | |
| 10 | 34 constant-argument clones | implemented (batch 2) | env SASRT_LOCALIZE_CONST_ARGS | | | |
| 11 | 60 invariant guest loads out of loops | implemented (batch 2) | env SASRT_LOCALIZE_COUNTED_BARRIERS | | | |
| 12 | 46 write-once globals frozen (entry check) | census done; part 2 implemented, OFF after its audit (unsound in general; the sound subset is idea 60) | sasrt_cpu_frozen_census; env SASRT_LOCALIZE_FROZEN, CMake SASRT_HOT_FROZEN | | | |
| 13 | 35 the atomic copies verified end to end | implemented (batch 2) | banjo_hot_guard_prefix | done, fixed | gv3: 5.07 M prefixes equal, 6 not; gv4: 1.92 M, 1 not | |
| 14 | 39 store cards batched in loops | implemented (batch 2) | env SASRT_LOCALIZE_CARD_RUNS, CMake SASRT_HOT_CARD_RUNS | done, fixed | gv3: verify 0 misses | |
| 15 | 51 guest accesses proven apart | covered by the existing D-form split + idea 60 (evidence below) | - | - | - | - |
| 16 | 43 NEON idioms (bit moves first, then float ones with fuzz tests) | bit moves B1-B4 implemented (batch 2); float F1/F2 batch 3 | REX_SHUFFLE_INT_DOMAIN, REX_SIMDE_DP_PS, REX_VUPKD3D_LANES, REX_SETFROMMASK_MOVEMASK | | | |
| 17 | 31 the guest stack in locals | to do | | | | |

## Log

### Round A (2026-11-10 22:15-)

- **26 and 59, already done by LTO.** In the batch's NRO (bt1's build) the copy of sub_823DA880 calls sub_82517690,
  which has a copy of its own: its machine code branches straight to `n_82517690::Native` (`b 0x4381f0`) or, with that
  copy switched off, to the original (`b 0xac4e0`). LTO inlined the callee's hook (the per-copy key and the kill switch)
  into the caller, and the shards do not matter to LTO's inlining. What is left of a call between copies is the
  registers handed over through the context, which the callee reads there.
- **29.** The hooked-classified functions were 1.0 % of the race's samples (19 functions, cp3). Most of them are not
  hooked at all: they are only named in app/config/renut_gpu_funcs.toml, this game's map of Direct3D's names (342
  functions; no code hooks through it; tools/direct_calls.py does not read it). localize_native.Hooks no longer reads
  it; a function a source really hooks (D3DDevice_Resolve's census hook, the memcpy native) is still found in the
  source.
- **47.** CMake SASRT_HOT_LR_ELIDE: the shards compiled with frame_traffic.py's opt-in REX_LR_MOVES_ELIDE (the link
  register's dead moves: 2,354 writes and 1,988 reads in the copies); the generated tree keeps them, and the
  non-volatile saves (sa2-nx's blue-tint finding) stay in both.
- **29, measured selection.** switch_hot_bulk.py on bt1's profile with the toml out of Hooks: 6 functions join the
  list (1,236 -> 1,242 copies), among them sub_827506C0 (119 samples: the top plain function of SlRenderer and Model
  Instance) and sub_8274FEE8 (43). Still left out as "a source mentions it": sub_82CDB7C8, 82CCB540, 82CE1310, 82CE7038,
  82CD11C0 (the draw / clear / census / system hooks: real hooks) and sub_82C8EEF0 (the memcpy native; A3 below).
- **A1 (forced inline).** `REX_SMALL_HELPER` (`[[gnu::always_inline]] inline`, as memcalls.h's helpers) on
  CRRegister::compare (both), raw / set_raw, the four flush-mode switches and the two tests, fctiwz, fctid, the four
  integer divisions, SingleToDoublePure, QuietSingleBits. The any-mode and slow float helpers stay out of line (they are
  in the generated tree too: CompareAnyMode 743 calls there, MulSingleAnyMode 456).
- **A2 (-Os off).** With PGO the compiler already optimises for size the functions and blocks the profile finds cold;
  -Os overrode the profile in 731 copies, most of which are called often but cheaply (fewer than 3 samples each).
- **A3 (memcpy guard).** `CheckRanges` (app/src/hot/sasrt_hot_guest.cpp) makes a difference again from the same
  inputs (ranges back to their contents before the call, the registers and the FPU mode to the inputs; native, roll
  back, original for real), up to three passes, as the bulk copies' guard does; one that does not repeat is counted and
  logged ("did not repeat"), and the native stays on.
- **37.** A copy wrote back at every return each volatile register it changed (21,734 write-backs over the 1,242
  copies). tools/leaf_dead_stores.py already computes every function's LiveOut over the whole program (the registers any
  caller can read after it returns; no ABI assumption). But it counted the copies' own lists (app/src/cpu/hot/
  localized.txt, localized_bulk.txt) as "an address named in the port's sources": every listed function was "everything
  live" (1,244 of them in this run), so a function lost its dead write-backs, and dead_ctx_defs.py's dead definitions, when
  it became a copy, and the generated tree changed with the list (part of why a list change made the PGO profile stale).
  Now: the lists do not count (SASRT_LIVE_OUT_LISTS_NAMED=1: as before); leaf_dead_stores.py writes the LiveOut to
  out/leaf_live_out.json; localize_native.py writes back at a return only the volatile registers in it (r1, r2, r3, r13,
  f1 and the non-volatile ones always), and the guard skips the ones left out (SASRT_LOCALIZE_LIVE_OUT=0: off).
- **57.** In this game's copies the stvlx / stvrx pairs are adjacent, not interleaved: 8 pairs of one vector (all in
  sub_82720378's loop, `stvlx v, E` then `stvrx v, E + r8` with r8 = 16 before the loop); the other 95 stvrx stand alone.
  The pair becomes one 16-byte store when the second address is the first + 16 at run time (`REX_STV16`,
  rex::ppc::StoreVector16), the original pair otherwise; tools/store_cards.py's REX_STV16_C marks the pages of ea and
  ea + 15. Small (sub_82720378: 10 samples), but the general form for any later list.
- **Process note (2026-11-10 23:00).** Two post_codegen runs overlapped for ten minutes (a shell `&` that was not killed
  when the tool call ended, then the tracked run): dead_ctx_defs.py's restore check failed. Both stopped by process id,
  and the tree regenerated from a fresh codegen (tools/codegen.ps1) with ideas 37 and 57 applied.
- **45, already done by PGO.** The optimised build uses plain `-fprofile-use` (app/CMakeLists.txt, SASRT_PGO=use) and
  nothing turns its loop options back off: with a profile GCC enables `-funroll-loops`, `-fpeel-loops`,
  `-funswitch-loops`, `-fsplit-loops`, `-ftracer` and `-fpredictive-commoning`, and unrolls or peels a loop by its
  profiled trip count (GCC manual, -fprofile-use). The Counting form's block counts would give the tool the same
  numbers the profile already gives the compiler, after inlining.
- **34, not done by the compiler.** The same flag enables `-fipa-cp-clone`, but the batch's NRO has 1 `.constprop`
  clone among the copies' functions (466 `.isra` ones): a copy's arguments travel in the context (memory), which
  IPA-CP does not follow. Left for batch 2.

### Round A's audits (2026-11-10 23:00-23:40: docs/audit_roundA/roundA.diff and ideas37_57.diff, two independent reviews)

| # | Finding | What was done |
|---|---|---|
| 1.1 | The new OFF default of SASRT_HOT_COLD_SHARDS does not reach the existing build folders (their caches hold ON) | `cmake -DSASRT_HOT_COLD_SHARDS=OFF` on out
x and out
x-pgo-gen |
| 1.2 | The old profile does not fit the changed shards | the PGO cycle runs again (planned) |
| 1.3 | The memcpy guard's repeat could roll back another thread's write made after the original ran | the ranges are kept after each run of the original; a repeat whose ranges changed since stops (not repeated, memory left as it is) |
| 1.4 | A range check inside another's original (memmove's calls memcpy) shares the thread's buffers | a nested check runs unchecked (thread depth counter) |
| 1.5 | The LR elision has no frame-exact test in this port | no lockstep proof is possible here (identical runs already diverge: docs/enhancements.md); the recompiled code stores `ctx.lr` (not the hardware's return address) in that slot today, so only a game read of an uninitialised stack word over the slot can see it; kept ON, the races' screenshots are the visual check |
| 1.6 | REX_NO_FORCED_HELPERS did not reach the SDK's targets | the option moved before generated/rexglue.cmake |
| 1.7 | The option text: the 23 copies of localized.txt are not elided | reworded |
| 1.8 | The not-repeated count was never reported | in the "N checks, no difference" line |
| 2.1, 2.2, 2.3, 2.7, 2.8, 2.9 | Idea 57's new merge: REX_STV16 missing for the 23 copies and with SASRT_GEN_VEC_UNALIGNED=OFF, no Straight() check (the PC's physical-view boundary), the loop locals' registers (ll_v) not matched; and the existing merge (MS_PAIR / MS_QUAD, 2026-11-08, with Straight() and its CMake switch) never fired: it matched only the store-card forms, which post_codegen.py takes out before the copies are made | the new merge taken out again; the existing one now matches the plain forms (the pair and the stvewx quad), so it fires |
| 2.4 | Idea 37's guard skip set included every member's dropped register, hiding a wrong LiveOut | only the registers dead after the root returns |
| 2.5 | Listed roots stayed "everything live": their calls are hooked sub_X calls (tools/direct_calls.py), which leaf_dead_stores.py counted as unknown | a call through a copy's hook counts as a call of the original (for the listed functions nothing else names or hooks) |
| 2.6 | The JSON's tree was not checked (a scratch run, or the classic flavour, would use another tree's LiveOut) | the JSON names its tree; localize_native.py uses only this tree's; the classic flavour turns idea 37 off |

### Batch 2 (2026-11-11 00:30-; the user: "implementations in large batches like 6 or 7 per batch")

Written while round A's instrumented build ran: the generator (tools/localize_native.py) changed at once, the app's
files staged (scratchpad idea39_app.py with idea 52's macro, idea35_app.py) for after round A's builds. A dry run of the
generator into a scratch folder (the build's inputs untouched): 240 prefetches, 255 barriers left out, 5 members forced
inline, the card runs written.

- **39, store-card runs.** A copy's function keeps the page of its current run of stores (`REX_CARD_RUN_DECL`) and
  marks a page's card when the run moves to another page, and the pending page before every call (a copy's callee
  included), compare-and-swap, fence and return, and at the end (`REX_CARD_FLUSH`). Every store's page is still marked
  before the function's next synchronisation; Renut checks the cards at a kick, which the game reaches through a call.
  A compare-and-swap marks its own page at once. Only the bulk shards (app/src/cpu/banjo_hot_prelude.h); the
  hand-written natives keep marking at each store. Test: banjo_renut_store_cards_verify (every copy the cards prove is
  hashed too) on the guard race.
- **52, prefetch in pointer-chasing loops.** In a loop, a pointer the loop carries (its only definitions in the loop
  are its own loads: `p = p->next`) is followed by `REX_PREFETCH_GUEST(p)` (a hint, cannot fault). The first rule
  (any self-load in a loop) found 1,026, most of them `r11 = *(r11 + 16)` after `r11 = *(r24 + 352)`, used at once:
  no lead time; the loop-carried rule leaves 240.
- **60, invariant loads out of loops.** The real obstacle is tools/loop_barriers.py's barrier at every loop header
  (against hoisted polls: a thread spinning forever), which also keeps every invariant guest load in the loop. A
  straight counted loop (back only through `bdnz`, nothing else writes ctr, no other branch, return or call) cannot
  spin on memory: its barrier is left out of the running form (255 in the copies; 157 in 69 copies by the first count,
  among them WaterThread's sub_8286C230 and the audio resampler sub_82720840). The compiler's alias analysis then
  hoists what it can prove.
- **34, constant-argument clones.** Of the 9,412 calls between copies' functions, 5,413 go to members forced inline
  (a constant reaches them there); 25 others pass a literal in an argument register (10 callee / constant pairs, 8
  copies, 43 samples). A member called with a literal is forced inline too when at most 3 calls reach it: 5 members.
- **35, the atomic copies verified.** The guard's logged forms stop at an atomic (and at any call outside the copy):
  such a call was "not comparable". When both forms stopped, the bytes each wrote before its stop are compared
  (counted in the [hot] summary; a difference logged, not acted on, since a hand-written native in front of a callee
  can make the two forms stop at different points).
- **46, part 1 (the census).** tools/frozen_census.py: the copies' loads at a known address (the `lis` / `addi` / `ori`
  constants tools/ro_constants.py follows) in the image's writable data: 3,819 loads of 510 globals in 597 copies (3,941
  console samples; the game thread's top function sub_825E0F28 among them). With sasrt_cpu_frozen_census a thread
  samples them every 8 ms and lists, at 240 s, each one's changes and the time of its last; part 2 (batch 3) builds the
  ones the race never changes into their copies behind an entry check.

### Batch 2's audit (2026-11-11 ~01:30, an independent review of docs/audit_batch2/)

| # | Finding | What was done |
|---|---|---|
| 1 | The card flush stored even with nothing pending (the sentinel's byte): new stores to one line from every thread at the 1,100 calls and 1,300 returns of the 764 store-less functions; a CAS flushed twice | REX_CARD marks nothing while nothing is pending, REX_CARD_FLUSH only a pending page (a store-less function's flushes compile to nothing); the CAS's extra flush taken out |
| 2 | Copies written without the runs but shards compiled with SASRT_HOT_CARD_RUNS: `rex_card_run` undeclared | the generator writes app/generated/hot/banjo_hot_options.h (REX_CARD_RUNS_GENERATED); the prelude uses the runs only with it |
| 3 | The original statements' form's comment | corrected (it runs only in the guard's rolled-back pass) |
| 4 | On x86 the old page's mark lands after the new page's first store | not changed (the PC only; ARM never ordered them; the marks still come before the next synchronisation) |
| 5 | The barrier search could take a second label's barrier (an enclosing polling loop's) | only the label's own next line |
| 6 | Idea 34: no size cap; a literal in the caller's own local; a write between the literal and the call | only `ctx.` registers, not written again before the call, members up to 4x the inline limit, the inline=0 opt-out honoured |
| 7 | Idea 35's prefix compare was quadratic | a binary search per byte |
| 8 | Idea 35's buffers never shrank; the hand-picked hooks missing from the sums; a moved comment | trimmed after 256 KB; summed for every hook; the comment kept on its line |
| 9 | The census read only the root's running form (members' f_ forms lie between the o_ forms) | every running form read: 3,819 loads of 510 globals (1,280 of 460 before) |
| 10 | The census forgot a register only at a line starting with it | any write of it, a call, a brace or a macro write forgets (as ro_constants.py) |
| 11 | frozen_census.inc missing (the classic flavour) broke the build | `__has_include` |
| 12 | Small: the doc named a file that does not exist; the cvar inside the namespace | fixed (the cvar beside the others) |
| 13 | Idea 52: loop locals (ll_rN) not found | the source pattern takes them |
| 14 | The patch scripts were not idempotent | one script (batch2_app.py) that leaves a patched file alone |

### Batch 3, research for 43 (NEON idioms; 2026-11-11 ~02:00, a read-only study of bt1's disassembly: 753 hot copies,
### weight = console samples x sites; micro-tests with devkitA64 GCC 16.1 and the project's flags)

Exact by construction (bit moves), for batch 3:
- **B1 (the one worth most, ~0.6 % of the copies' weighted instructions):** a vspltw splat feeding vmulfp / vmaddfp.
  The pch's simde_mm_shuffle_epi32 override shuffles in the integer domain, so GCC never forms `fmul v, v, v.s[k]`:
  3,452 `dup` -> `fmul` pairs in the hot copies (38 in sub_825E0F28). Shuffling in the float domain gives the
  by-element multiply (a lane copy has no float semantics; GCC already puts the splat second, so even two-NaN payloads
  are the same). Where: tools/pch_neon_shuffles.py's block (needs replace logic: it stops when its marker is there).
- **B2:** vmsum3fp128 / vmsum4fp128 (simde_mm_dp_ps 0xEF / 0xFF): the second `faddp` already holds the sum in every
  lane; the trailing `dup` goes with a `vpaddq_f32` form (672 in the hot copies).
- **B3:** vupkd3d128 type 0 written lane by lane through GPRs inside WaterThread's inner loop (sub_8286C230: 7
  instructions, two GPR-to-SIMD moves, every iteration): one `tbx` over a 1.0f vector (bytes 1-3 kept: 00 80 3F).
  Where: the generator (sdk/src/codegen/builders/vector.cpp:1403) or a post-codegen rewrite before the copies.
- **B4:** cr6 from vcmp*. (CRRegister::setFromMask): `cmlt #0` + `xtn` + `umov` + compares instead of shifts, `addv`
  and a constant (182 in the hot copies). sdk/include/rex/ppc/context.h.
- B5 (small): a single stvewx through the stack; vslw's redundant compare.

Not exact (each its own key, off by default: they change results; fuzz tests first):
- **F1:** vrsqrtefp / vrefp are done exactly today (`fsqrt` + `fdiv`, both unpipelined on the A57; 32 of
  sub_8286C230's 207 samples): `frsqrte` / `frecpe` with Newton steps (the 360's instruction is itself an estimate).
  Fuzz: all 2^32 inputs with FPCR.FZ, the ulp error and the special cases.
- **F2:** vmaddfp / vnmsubfp unfused (`fmul` + `fadd`, -ffp-contract=off): FMLA (AltiVec rounds once, so closer to
  the hardware, but not the port's current results). Fuzz against fmaf and the current form.

Ruled out with evidence: REX_BSWAP128 (one `tbl`), vsel (GCC forms bsl/bit/bif), vrlimi128 / vmrg* / vpermwi128 /
vcmp* / REX_VPERM1 (single instructions already), the out-of-line VMX helpers (only in 1-2 sample copies). The 21,731
q-register stack transfers (3.2 % weighted) are register pressure from up to 64 vector locals, not an idiom.

### Pacing (the user, 2026-11-11 ~00:00: "modify the game to fix pacing to remove latency", alongside the copies)

- Found: triple buffering is on (3 swapchain images), fixed vsync with PaceSwap sleeping on the Swap's thread, the
  game zero frames ahead; bt1's ~72 ms input -> display = ~36 ms input -> present + ~37 ms present -> display (the
  frame queued behind the previous frame's ~34 ms of GPU work). banjo-nx's `banjo_deko3d_latency_trim` (off here,
  never tried in this port) targets exactly that queue.
- **lt1 (01:00, bt1's NRO + banjo_deko3d_latency_trim): not comparable.** 29.74 fps, GPU 15.7 ms, render thread
  12.0 ms, input -> display 54.2 ms; trim held back 5 of 301 frames. CPU and GPU ran ~2x faster than in bt1 with the
  same NRO in handheld mode: the console was rebooted at ~23:50 (the SD card out for the user's copy), which drops a
  temporary sys-clk override; the clocks are the user's to set. The perf races (lt1, round A) wait for the user's
  1020/460/1600 again, or are paired with a baseline run at the same clocks.

### Round A's guard race (gv2, 2026-11-11 01:07, the instrumented NRO, dense guard: 4000 calls, then 1 in 64)

- **5,829,938 calls compared, 0 differences** (20 differed once and not when repeated); 1,128 of the 1,242 bulk copies
  reached (gv1: 1.93 M calls, 954 copies); 0 fence timeouts, 0 empty screenshots.
- A3 seen working: the memcpy native's check differed once inside a 128-byte copy, did not repeat ("another thread
  changed the inputs"), and the native stayed on (in bt1 it switched itself off for the rest of the run).
- The capture marks held (203,070 deltas from marks, 37.5 chunks a delta, 0 misses); the recording marks too.
- Run at the clocks the console has had since its reboot at ~23:50 (not the user's 1020/460/1600; see Pacing): the
  guard compares results, so the clocks do not matter to it.

### 43's bit moves join batch 2 (2026-11-11 ~01:20)

B1 and B2 are in tools/pch_neon_shuffles.py (the shuffle in the float lanes; the dot product without its `dup`; the tool
now replaces an older block of its own), B3 is tools/vupkd3d_neon.py (709 sites in 171 files; post_codegen.py runs it
before the copies), B4 is staged (scratch batch3_app.py: cr6 from vcmp* in sdk/include/rex/ppc/context.h). The tools
run with batch 2's post_codegen, so batch 2's build carries them; each has its own macro to switch it back. The float
ones (F1 estimates, F2 fused multiply-add: macros whose default is today's expression, the fast forms behind off-by-
default keys, a fuzz test on the console itself since x86 cannot reproduce NEON's estimates) are batch 3's.
- **bt1b (01:25, bt1's NRO and toml at the clocks since the reboot): the same-clock baseline.** 29.74 fps (298 of
  600 refreshes with a new image), GPU 15.72 ms, render thread 12.18 ms, input -> display 56.4 ms. **lt1 against it:**
  29.74 fps, input -> display 54.2 ms (-2.2 ms), input -> GPU done 64.7 against 65.1 ms; the trim held back 5 of 301
  frames: where the GPU is not the limit it has nothing to trim. It needs the user's GPU-bound handheld clocks.
- **P2, the pacing sleep as late input's slack (staged: scratch pacing_p2_app.py, `sasrt_pacing_input_slack`, off).**
  bt1b's game thread worked 11.34 ms a frame and then slept 21.99 ms in PaceSwap (fixed vsync) before its present,
  and read its controller right after the previous release: every frame's input ~33 ms old at its present. Late input
  (`banjo_late_input`) delays a frame's first controller read by the least slack of the last 16 frames less 2 ms, but
  counted only the wait for the render thread: "delayed 0.0 ms on average". With the key the pacing sleep is slack too
  (PaceSwap notes it, QueueFrame adds it to the frame's slack): the read moves towards the end of the sleep, the sleep
  shrinks to the margin, the frame still reaches its slot. Expected at these clocks: ~20 ms less input -> display, the
  same frames.

### Round A's performance race (rA1, 01:45; against bt1b at the same clocks)

**The clocks since the reboot, from the profile's header: CPU 2397 MHz, GPU 1228.8 MHz, memory 2733 MHz** (bt1 and
every earlier race: 1020 / 460.8 / 1600). Both runs below at those; the user's handheld 1020/460/1600 is theirs to set
again.

| Run | fps | GPU | render thread | input -> display | Main | SlRenderer | WaterThread | Model Instance | AK::EventManager | game threads |
|---|---|---|---|---|---|---|---|---|---|---|
| bt1b (bt1's NRO) | 29.74 | 15.72 ms | 12.18 ms | 56.4 ms | 42.9 % | 26.8 % | 10.5 % | 6.7 % | 6.4 % | 93.3 % |
| **rA1 (round A)** | 29.73 | 15.57 ms | 12.44 ms | 48.8 ms | 41.1 % | 25.9 % | 11.0 % | 6.2 % | 5.8 % | **90.0 % (-3.5 %)** |

(CPU % = the profile's samples a thread took of the run's time; the same frames: 7,461 and 7,456.) The plain guest
share fell where round A aimed: Model Instance 15 % -> 2 % of its samples (idea 29: sub_827506C0 and sub_8274FEE8 are
copies now), Main 11 % -> 7 %, SlRenderer 12 % -> 6 %; the engine share on Main 4 % -> 2 %. 0 fence timeouts, 0 empty
shots. No regression to bisect. The frame rate is at the 30 fps cap at these clocks, so fps cannot show the gain.

### Batch 2 generated, batch 3 started (2026-11-11 02:10)

- Batch 2's post_codegen (01:50, 14 min): 704 vupkd3d128 sites as one lookup (B3), the pch's float-lane shuffle and dot
  product (B1, B2), 2,221 write-backs left out (37), 252 prefetches (52), 344 counted loops' barriers left out (60),
  5 members forced inline (34), 20 pairs and 24 quads merged (57), 1,242 copies, the census list of 510 globals (46).
  The app patches (batch2_app.py, batch3_app.py's B4, pacing_p2_app.py) applied before it. Its instrumented build
  runs (pgo_cycle -Step generate); then gv3 (dense guard, banjo_renut_store_cards_verify, sasrt_cpu_frozen_census),
  training, the optimised build, the performance race against rA1 (and P2 with sasrt_pacing_input_slack in an A/B).
- **43 F1 / F2 (batch 3):** tools/vmx_float_macros.py writes vrsqrtefp, vrefp and vmaddfp as macros (1,052, 270 and
  7,633 sites) whose default is today's expression; CMake SASRT_VMX_FAST_ESTIMATES (`frsqrte` / `frecpe` and two Newton
  steps) and SASRT_VMX_FUSED_MADD (`fmla`), both off. The fuzz test (`sasrt_test_vmx_fuzz` = N million lanes; staged in
  scratch batch3_app.py) runs each fast form against the exact one on the console with the flush mode on and logs the
  largest ulp difference and the special cases that differ.

### gv3 (02:22): the census thread terminated the game at its start; fixed

- Batch 2's instrumented NRO with gv3's keys ended back on the Home menu twice; its log stopped at ~9 KB. Ryujinx
  (tools/win/ryujinx_run.ps1, 90 s, the same keys) caught a guest Break with the stack InitHook -> std::call_once ->
  `std::thread::detach` -> `__cxa_throw` -> terminate: idea 46's census thread, a std::thread started from a guest
  thread (the SDK's Horizon threads), which this C library refuses (masseffect_deferred_recording.cpp found the same for
  a pthread). Started now as a libnx thread on the Switch (`StartBackground`, lowest priority, any core), std::thread on
  the PC; the staged fuzz test uses the same.
- **Idea 31's research (a read-only study of the 1,241 bulk copies):** 27.7 % of the copies' memory accesses are on the
  guest stack, but the heavy frames hand their slots' addresses to callees (4,185 of 5,980 frame addresses escape; 2,117
  of 8,600 calls pass r1); a provable rule (static frame, slots below the entry r1, constant displacements or contained
  pointers, no escape, write-back at returns so stale reads see the same bytes) covers ~5 % of the stack traffic, under
  1 % of the copies' CPU, mostly one leaf loop (sub_8275E3D0). Not worth a general pass. Taken instead (batch 3): the
  store cards treating r1-derived registers as stack (10 % of stack stores mark a card today), and forwarding the
  scalar <-> vector transfers that go through the stack (392 + 257 sites, mostly in loops).
- **Batch 3, from idea 31's research: the store cards' stack test follows r1-derived registers** (tools/store_cards.py
  `derived_from_r1`, env SASRT_CARDS_STACK_DERIVED=0 off): an `ea` from one register that an earlier line of the same
  straight line set to r1 plus a constant is a stack address, so the store keeps no card (as every r1-relative store
  already does). Tested on the three shapes (derived: stack; reloaded from memory, or past a label: not known).
- The fixed instrumented NRO ran 100 s in Ryujinx with gv3's keys (no exception; copies reached and compared), then
  gv3 on the console (02:39).

### Batch 2's guard race (gv3, 02:39; the fixed instrumented NRO; dense guard, store-card verify, census on)

- **5,148,211 calls compared, 0 differences** (20 differed once and not when repeated); 1,114 of the 1,242 bulk copies
  reached; 0 fence timeouts, 0 empty shots; the capture marks held (0 misses).
- **Idea 35:** of the 5,070,596 calls not comparable (an atomic or an outside call stopped both forms), 5,070,584 were
  compared on the stores before the stop and were the same; 6 were not (sub_82DFC2B8, sub_828D4108, sub_828F1560 ...:
  one byte each, off by one or one bit: another thread changing a counter between the two runs, which the prefix
  compare does not repeat). Logged, not acted on, as designed.
- **Idea 39:** `banjo_renut_store_cards_verify` (every copy the cards prove hashed too): **0 changed under clean
  cards** in all 30 reports, over 6,814,496 copies proven by their cards: the copies' card runs miss nothing.
- **Idea 46:** the census thread was refused ("a background thread could not be started"): priority 0x3F is outside
  an application's range; 0x3B now (the app's own lowest). The census runs with the optimised build.

### 51: what was already there (2026-11-11 03:00)

On the Switch the D-form accesses are already `base + (uint64_t)(u32)(reg) + (int64_t)(disp)` (the Mass Effect diet's
`dform_disp_split`, sasrt_pch.h): two accesses through the same register with different displacements are one pointer
plus two constants, which GCC tells apart by itself (the stack research saw it forward a same-block store to a load in
sub_8275D5B8). What hid that in loops was tools/loop_barriers.py's barrier, which idea 60 now leaves out of straight
counted loops; and where accesses go through different registers, the vectorizer's run-time alias checks (on with
-fprofile-use) version the loops it vectorizes. What stays unproven is accesses through unrelated registers outside
those loops: real unknowns, which only a run-time check per pair could separate. Nothing added for 51.

### Batch 2's performance race (b2, 03:18; the clocks since the reboot, as rA1)

| Run | fps | GPU | input -> display | Main | SlRenderer | WaterThread | Model Instance | AK::EventManager | game threads |
|---|---|---|---|---|---|---|---|---|---|
| bt1b | 29.74 | 15.72 ms | 56.4 ms | 42.9 % | 26.8 % | 10.5 % | 6.7 % | 6.4 % | 93.3 % |
| rA1 | 29.73 | 15.57 ms | 48.8 ms | 41.1 % | 25.9 % | 11.0 % | 6.2 % | 5.8 % | 90.0 % |
| b2 | 29.74 | 15.73 ms | 54.0 ms | 42.4 % | 26.6 % | 10.8 % | 6.6 % | 6.1 % | 92.5 % |

The windows' process CPU paired by race time (the same track and input, 27 windows each): bt1b -> rA1 **-3.8 %**
(standard error 1.4 %: real), rA1 -> b2 **+2.2 %** (standard error 1.0 %: likely real), bt1b -> b2 -1.7 %. So batch 2
gives back about 2 % of round A's gain. A switch-level bisect needs a full PGO cycle per switch (a flipped switch
changes the copies' code, and a changed function keeps no profile), so the runs are repeated first (b2, rA1) to make
sure before bisecting.
- **P2 tested (b2p2, 03:26; batch 2's NRO with `sasrt_pacing_input_slack`): worse; stays off.** 25.10 fps against
  29.74, 44.6 frames late a 10 s window (53 in a typical one), input -> display 58.3 ms against b2's 54.0. Late input
  did move the controller read (20.9 ms on average, 0.0 without the key), but the game thread's frame work varies
  (11.5 ms on average, up to 21.5 ms in b2) and the read is on another thread than the Swap's pacing (the delay
  shifts the game thread, whose hand-over then reaches SlRenderer late): a long frame after a late read misses its
  33.3 ms slot and shows at 50 ms (Swap to Swap up to 69.6 ms). A next form would take the delay from the slack less
  the recent spread of the frame work, and measure the slack on the reading thread; left for the pacing work.
- **46's census (b2census, 03:34; batch 2's NRO, sasrt_cpu_frozen_census):** 510 globals sampled every 8 ms for 300 s
  (35,485 samples): 249 never changed, 155 last changed in the first 50 s and 45 by 100 s (loading, before the race),
  1 + 3 later, 57 still changing while racing (45 changed in the last 10 s). **449 of the 510 stay the same through
  the race**: the candidates for part 2 (a copy with the values built in, behind an entry check that falls back to
  the plain copy when one differs; another track or mode that writes one only takes the fallback).
- **The repeats (b2r 03:41, rA1r 03:49): no regression to bisect.** Process CPU over the race windows: round A 121.6 and
  123.4 %, batch 2 124.3 and 123.0 %, bt1b 126.5 %. Pooled window by window, batch 2 against round A **+0.7 %
  (standard error 2.0 %)**: noise; the first pair's +2.2 % was run-to-run spread (the same NRO twice: b2 -> b2r -1.0 %,
  rA1 -> rA1r +1.8 %). Both batches ~2.5-3 % under bt1b. At these clocks the frame rate is capped (29.7 fps), so only
  CPU time can show a gain; the user's 1020/460/1600 would show more.

### 55, tested (r55, 03:58): batch 2's sources and profile, -Final -GuardForms (out
x-forms), guard at 1 call in 2^20

84.8 MB against batch 2's 75.5 MB (the guard forms: +9.3 MB, +12 %). Over the race the guard checked 734 calls and
compared 804 more up to their stop (idea 35), 0 differences; process CPU +4.1 % against batch 2's two runs (window by
window; standard error 3.7 %). A guard in shipping checks ~1,500 calls a race for that size and likely a few percent of
CPU: not worth it. Shipping keeps idea 27's choice (no guard forms); the dense guard in the instrumented builds stays
the copies' check (gv1-gv3: 13 M calls compared, 0 differences).

### Batch 3 (2026-11-11 04:10-): 46 part 2, 43 F1/F2 with the console fuzz test, the store cards' r1-derived stack

- **46 part 2.** tools/frozen_pick.py turned the census into app/src/cpu/hot/frozen.txt (449 globals). Where they
  are loaded: 264 sites inside loops (70 copies) and 3,356 outside; a load outside a loop costs what an entry check
  costs, so only loops are frozen. localize_native.py's `freeze_loops`: in a copy's root running form, a known-address
  load of a listed global inside a loop becomes `rex_frozen_ok ? value : load`, and the function starts with one check
  of those globals (`rex_frozen_ok`, false with REX_FROZEN_ON 0); the compiler's loop unswitching makes the frozen
  loop. The dry run: 66 loads in 21 copies (the root functions only, the address proven on one straight line).
- **43 F1/F2** and the fuzz test (`sasrt_test_vmx_fuzz`), the store cards' r1-derived stack: above.
- Audit: docs/audit_batch3/ (running).

### Batch 3's audit (2026-11-11 ~04:40, docs/audit_batch3/): 12 findings

| # | Finding | What was done |
|---|---|---|
| 1, 2 | Frozen loops: the entry check proves the values only at the call's start; 43 of the 449 globals are stored by copies, a set-and-restore inside one call is invisible to an 8 ms census, 62 frozen loads sit in loops with real calls (the guard stops there), and a polling loop on a frozen value could spin forever | **freezing OFF by default** (SASRT_LOCALIZE_FROZEN=1 for measurements). The sound subset (counted loops without stores or calls) is exactly where idea 60 already lets the compiler hoist the load: idea 46 ends as the census plus this evidence |
| 3 | The constant trackers missed register writes made by macros (REX_LOOP_IN / OUT, REX_LR_READ) | both scans stop at them |
| 4 | REX_FROZEN_ON defined only by the staged patch | moot with freezing off; the patch defines it |
| 5 | The fast vrsqrtefp gave NaN for +-0, +inf and flushed denormals (0 x inf in the Newton step) | the estimate's own result kept where it is 0 or infinite (`vbslq`) |
| 6 | vrefp below 2^-128 with FZ off | not changed (VMX code runs with FZ on) |
| 7, 8 | The fuzz gated on REX_VRSQRTEFP; no "memory" clobber on `msr fpcr`; external linkage | gated on REX_VMX_FLOAT_HELPERS (defined with the fast forms); clobbers; an anonymous namespace |
| 9 | vmx_float_macros.py's docstring promised a --restore | corrected (no restore needed: the defaults are the expressions) |
| 10 | `__builtin_constant_p` in setFromMask | taken out (`imm == 0xF` alone is exact) |
| 11, 12 | r1l mirrors and float globals not covered | not changed (they only miss savings) |

### Pacing for fewer drops (the user, 2026-11-11 ~04:28: "fix the pacing so things present faster so less fps drops")

At the user's clocks again (1020 / 460.8 / 1600, confirmed in the profiles from b2c on). The GPU needs ~34.5 ms a frame
against the 33.3 ms slot, and was busy only 86.7 % (bt1) / 88.6 % (b2c) of the race: the idle ~4 ms a frame is the
bubble to remove (at 100 % busy the GPU's own ceiling is ~29 fps; today 25.8).

| Run | Keys | fps | GPU a frame | GPU busy | render thread |
|---|---|---|---|---|---|
| bt1 | (bt1's NRO) | 25.55 | 33.89 ms | 86.7 % | 25.63 ms |
| b2c | batch 2's NRO, shipping | 25.83 | 34.50 ms | 88.6 % | 26.37 ms |
| pa | + sasrt_pacing_on_display | 26.02 (paired +0.16, se 0.32) | 33.78 ms | 88.0 % | 24.95 ms |

pa: the display paces (swap interval 2), the Swap no longer sleeps, but the GPU is no busier: with
sasrt_renut_frames_ahead 0 the game still waits for the render thread to finish each frame, so the next frame's work
does not reach the GPU sooner. Next: pb (display pacing + one frame ahead), pc (one frame ahead only).
- **The diagnostic (05:00):** `GpuGapReport` (backend/video.cpp; a "[latency] GPU waiting for work" line every 10 s)
  splits the GPU's idle, from the frame's own list timestamps, into "inside frames" (between a frame's lists) and
  "between frames". **d0 (05:05, batch 2 + the diagnostic, shipping keys):** the GPU waits **1.3-7 ms a frame inside
  frames** (between the frame's 3 lists) and only **0.3-0.8 ms between frames** (a few single stalls of 150-300 ms aside),
  and the windows with the most inside-frame waiting (5-7 ms) are the ones with the fewest frames (233-252 against
  276-281). The bubble is the lists' granularity: a list ends only at the game's kicks (three a frame), so the GPU
  finishes one part and waits while the render thread builds the whole next part.
- **The fix: `sasrt_renut_split_draws` (N; 0 off).** DrawStateLocked ends the open list after N draws, between two
  draws, the way a kick ends it (the fills flushed, then KickLocked; with eager kicks each list goes to the GPU at once),
  so the GPU starts on a part as soon as N draws of it are recorded. Same commands in the same order. kKickLists 6 -> 16
  (room for the extra lists). Building; then a race with N = 120 against d0.
- **pb (05:15, the diagnostic NRO + sasrt_pacing_on_display + sasrt_renut_frames_ahead 1):** **27.78 fps against d0's
  25.74 (+7.9 %)**, GPU busy 92.7 % (87.5), the GPU's idle inside frames 0.97 ms a frame (3.79), between frames 1.42
  (1.62), render thread 23.82 ms (26.16). The screenshots (start, lap 2, the lap 3 boat) show the skinned models whole
  (October's one-frame-ahead "explosions" not seen in this race), no new warnings (5 against 7). **The cost: input ->
  GPU done ~96 ms against ~60 ms (+36 ms, one frame).** The draw-count split aims at the same idle without the frame
  ahead.
- **s120 (05:30, the split build, sasrt_renut_split_draws 120, otherwise shipping): worse; the key stays 0.** 23.66 fps
  against d0's 25.74 (paired -2.07, standard error 0.51); 10.4 lists a frame, but the render thread 30.08 ms (26.16)
  and the GPU's idle inside frames 5.45 ms (3.79). Each split costs the render thread a kick's work (the fills, the ring
  cleaner's wait, a list's start), and the idle is not the lists' size: the render thread is slower than the GPU in
  parts of the frame, and with no frame ahead nothing covers them (pb's frame ahead does: 0.97 ms with the same 3
  lists).
- Next: pbt = pb + banjo_deko3d_latency_trim (banjo-nx's answer to a frame ahead's latency: after a present the render
  thread waits until the GPU has only the frame's last part left, so the next frame starts just in time).
- **pbt (05:37, pb + banjo_deko3d_latency_trim):** 27.66 fps, input -> GPU done ~96 ms: the trim held back 408 of
  8,271 frames and backed off 119 times; no latency back. In pb the frame waits ~48 ms from Swap to present (the queue
  behind the render thread), while late input delayed the controller read only 3-4 ms (the least slack of 16 frames).
- **The user's choice (05:50): "Keep low lag"** - sasrt_renut_frames_ahead stays 0; fps from elsewhere (the GPU's
  work, or a lower dynamic-resolution budget).
- **db32 (06:09, banjo_renut_dynamic_gpu_ms 32 instead of 34.5):** 26.49 fps against d0's 25.74 (+0.75), 42.0 late a
  10 s window (50.4), GPU 31.74 ms (33.96), average 3D height 663 lines against 683 (-3 %; most time at 666, 630, 648).
  Less than the GPU model predicted (~28 fps), because the render thread's slow parts (the GPU's idle inside frames)
  limit the frame too.
- **db31 (06:16, budget 31):** 26.40 fps (no more than 32's 26.49), 38.7 late, GPU 30.71 ms, height 651 (-5 %); the
  GPU's idle inside frames grows as its work falls (3.73 -> 5.10 -> 5.94 ms a frame): below ~32 ms the GPU is no longer
  the limit.
- **What limits the frame at zero frames ahead (db31's profile, the ELF's symbols):** Renut's render thread (52 % of a
  core) waits half its samples (`__syscall_cond_wait`) for the game's commands; its work is DrawStateLocked 12.6 %,
  FastDrawLocked 8.9 %, the capture / run-slot jobs 7.6 %. So the GPU's idle inside frames is the producer: the game's
  render thread SlRenderer (and Model Instance's recording) making the frame's commands slower than the GPU runs them
  in parts of the frame. More fps at low lag = a faster SlRenderer (its guest code: the copies; its Direct3D hooks).
- **SlRenderer in db31 (the ELF's symbols): 41.7 % CPU, of its samples 35.1 % in `__syscall_nanosleep` (PaceSwap's
  sleep) and 22.5 % in `__syscall_cond_wait` (QueueFrame's wait for the render thread) + 6.2 % event waits: it works only
  ~36 % of the time** (its copies sub_8279AFE0 4.3 %, sub_827506C0 3.6 %, QueueDraw 4.4 %). Neither the render thread
  nor SlRenderer is saturated: at zero frames ahead they take turns (SlRenderer may start frame N+1 only when the render
  thread has done N), and the GPU waits in the gaps.
- **Plan P3 (frames ahead with late input on the queue time):** with sasrt_renut_frames_ahead 1 (pb: 27.78 fps) the
  frame waited ~48 ms from Swap to present: the extra lag is the queue. Delay the game's controller read by the queue
  time (Swap to the render thread starting the frame), measured per frame, its least over 16 frames less a margin of
  several ms of queue left so the GPU never runs dry: expected ~70 ms input -> GPU done with most of pb's fps.
- **db32r (07:07, a repeat of the 32 ms budget):** 26.12 fps. Against the two baselines at these clocks (d0 25.74, b2c
  25.83), window by window: db32 +0.56 (standard error 0.33), db32r +0.27 (0.42), db31 +0.47 (0.44): **the lower budget
  is worth ~+0.4 fps (+1.5 %), near the noise, for 3-5 % less resolution**. Not recommended as a default; the frame is
  limited by the render threads taking turns at zero frames ahead (P3 next).

### Batch 3's guard race (gv4, 07:19; the instrumented NRO, dense guard, store-card verify, sasrt_test_vmx_fuzz 64)

- **1,301,368 calls compared, 0 differences** (2 differed once and not when repeated); 1,916,606 not comparable, of them
  1,916,600 with the same stores before the stop (idea 35), 1 not; 549 of the 1,242 bulk copies reached (the fuzz
  thread's 192 M lanes took CPU during the race). Capture marks: 0 misses.
- **The store cards' r1-derived stack rule:** `verify: 0 changed under clean cards` in all 29 reports.
- **43 F1 / F2, fuzzed on the console (64 M lanes each, the flush mode on):**

| Fast form | lanes that differ | the largest difference | special cases (NaN / infinity / sign) |
|---|---|---|---|
| vrsqrtefp (`frsqrte` + 2 Newton steps) | 20.3 % | 3 ulp | 125,112 (0.2 %) |
| vrefp (`frecpe` + 2 Newton steps) | 32.3 % | 1 ulp | 249,872 (0.4 %) |
| vmaddfp fused (`fmla`) | 2.4 % | 16 M ulp (cancellation: a + b*c near 0) | 8,480 |

  The 360's own vrsqrtefp / vrefp are estimates to about 1/4096 (~2,000 ulp), and its vmaddfp rounds once: the fast
  forms are closer to the console's hardware than the exact ones are far from it. They change results, so they stay off
  (SASRT_VMX_FAST_ESTIMATES, SASRT_VMX_FUSED_MADD) per the user's rule for pixel-changing items; the special cases
  include NaN sign differences, which the fuzz counts as special.
