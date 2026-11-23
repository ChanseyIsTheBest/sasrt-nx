# Machine copies: the 2026-11-10 batch (ideas 26-65)

The user (2026-11-10 evening): "implement all the ideas ... in one big batch and test at the end and bisect for any
issues", then "after you implement in one big batch do an audit of the implementation then test". The ideas were
three lists of ten (26-35, 36-45, 46-55) and one more (56-65) for the localized copies ("machine copies":
`tools/localize_native.py`, `app/src/cpu/hot/localized_bulk.txt`, the shards `app/src/cpu/banjo_hot_shard_<k>.cpp`).
Context and the measurements before the batch: docs/render-thread-round-1109.md, "Machine copies for everything the
profiler caught".

## What the measurements before the batch said

On the retrained PGO build (cp3: 1,871 copies, the recording marks on) against the old build (lat12), per game frame,
all threads (stack samples): **today's 878 new copies 0.231 -> 0.396 (+71 %)**, the 992 older ones -6 %, the rest -2 to
-12 %; the same NRO with the new copies switched off by their keys (cp4) was worse still in total (2.473 against cp3's
2.433 and lat12's 2.364). By size: copies of **fewer than 40 guest instructions 0.049 -> 0.142 (+188 %)**, 40-99 +65 %,
100-299 +39 %, 300+ +31 % (a copy also absorbs its inlined callees, so the bigger ones' rise is partly that). A small
function as a copy loses: behind its hook its callers no longer inline it (LTO did), and every call hands the registers
over. And a hook whose copy is off is the worst case (the hook stays, the inlining is still gone).

## Implemented (each its own switch, for the bisect)

| Idea | What | Switch |
|---|---|---|
| 27 | The guard's two logged forms of every copy (about two thirds of the copies' code) made only for a guard / verify build; without them every hook calls its copy directly | CMake `SASRT_HOT_GUARD_FORMS` (build_switch.ps1: OFF with `-Final`, `-GuardForms` keeps them); `BANJO_HOT_GUARD_FORMS` |
| 28 | `tools/win/pgo_cycle.ps1`: the PGO session in two commands, with both of today's traps built in (the old profile moved aside before the merge; the optimised folder cleaned before its build) | - |
| 30 | `tools/switch_hot_bulk.py --min-instructions 40 --small-keep-samples 50`: functions under 40 guest instructions stay out unless very hot, and `--merge` takes the list's own such lines out (651 removed: 297 of the older copies, 354 of today's; 18 added from cp3/cp4's profiles): 1,871 -> 1,238 copies | `--min-instructions 0` restores the old selection |
| 33 | A hot copy (20 or more console samples on its list line) takes twice the callees into its closure (12,000 lines, members up to 2,400) | env `SASRT_HOT_CLOSURE_SAMPLES` (0: off) |
| 41 | Time-base reads (`REX_QUERY_TIMEBASE`, mftb) in copies, like the atomics: the running form reads the clock, the guard's forms stop before it | part of `SASRT_LOCALIZE_ATOMICS` (0: refused again) |
| 58 | The bulk copies with 3 or more console samples in shards 0-5, the rest in shards 6-11, compiled for size (`-Os`) | CMake `SASRT_HOT_COLD_SHARDS`; env `SASRT_HOT_SAMPLES` |
| (24b) | The game's own draws (SlRenderer's `CaptureDelta`, 9 % of that thread): the title device gets a mark slot and a delta compares only the chunks marked or tagged since the chain's last draw, a whole compare every 32nd as the net | `sasrt_capture_marks`, `sasrt_capture_marks_check` (1: verify) |
| (atomics) | `localize_native.py` copies functions with guest atomics (earlier today; sent to RR6 and Blur) | env `SASRT_LOCALIZE_ATOMICS` |

## Already done by the existing passes (checked, nothing to add)

- 32 (hot layout), 53 (cold blocks out of huge functions), 62 (branch hints): PGO with a fresh profile does them
  (`.text.hot` / `.text.unlikely`, block probabilities).
- 36 (indirect calls promoted in copies): `indirect_calls.py` promotes them in the generated tree before the copies are
  made (223 sites), so the copies have them.
- 38 (paired byte swaps), 48 (condition-register liveness), 49 (dead carries), 56 (entry loads of registers written
  before read): in a copy these are locals (`cr0`, `xer`, `l_rN` from a `__restrict` context): the compiler drops the
  dead ones itself.
- 40 (critical sections): already raw exports with the owner from the context and a spin before the kernel
  (sa2-nx's second CPU round; `xboxkrnl_rtl.cpp`); the 1 % left is the lock's real work and contention.
- 42 (menus and loading): the bulk tool reads every 10 s report of a profile, the menus and loads included.
- 44 (flush-mode checks): `flush_mode_flow.py` / `flush_hoist.py` run before the copies, and on the Switch
  `REX_FLUSH_KNOWN_ON/OFF` compile to nothing.
- 50 (single-precision chains): `single_floats.py` runs before the copies.
- 61 (unaligned vector load pairs): none in the copies (no lvlx / lvrx in the game's hot code).
- 63 (the trap's register hand-over on the cold path): already inside the trap's branch (`{ if (s.Open()) return;
  ctx.r3 = l_r3; ppc_trap(...); }`).
- 64 (constant-size memcpy / memset inline): `inline_memcalls.py` inlines 1-64 byte constant ones before the copies.

## Not done tonight, and why

- 26 (copies calling copies directly), 29 (copies of the originals behind the app's hooks), 37 (dead write-backs across
  copies), 59 (call-graph sharding): each changes how copies link to each other or to the app's hooks; after the size
  rule (30) most of the measured loss is gone, and these are their own session.
- 57 (stvlx / stvrx merging): the pairs are not adjacent in this game's code (several stvlx, then several stvrx), so
  merging means reordering stores, safe only with a run-time overlap check.
- 31 (the guest stack in locals), 34 (constant-argument clones), 43 (NEON idioms), 46 (frozen globals), 51 (alias
  proofs), 60 (invariant loads out of loops): each needs a new analysis with its own proofs.
- 35 (verifying the atomic copies end to end), 45 (unroll from counts), 65 (the hand natives' declines): need the PC's
  counting form (banjo_hot_count) or a PC guard mode first.
- 39 (store-card batching): Renut's cached copies depend on every card; needs its own proof.
- 47 (link-register traffic): `lr_preserve.py` already rewrites the proven cases in the tree the copies are made from.
- 52 (prefetch), 54 (a cross-port XDK native library): measurement first / a base-level project.
- 55 (a low-rate guard in shipping) conflicts with 27 (the guard needs the forms 27 leaves out); 27 chosen.

## The audit (2026-11-10 ~21:30, an independent review of docs/audit_1110/batch.diff)

Ten findings; the fixes (docs/audit_1110/audit_fixes.py) went in before the batch's builds compiled the files:

| # | Finding | Fix |
|---|---|---|
| 1 | The chain's deltas did not cover what a resolve's path changes untagged (tv1: fetch chunks 0, 1, 11 before resolves; NewOp compares everything at a resolve, the chain did not): the first check would have dropped the marks | QueueResolve sets `g_capture_next_whole`: the chain's next delta compares every chunk |
| 2 | localize_native.py's index cache ignored `SASRT_LOCALIZE_ATOMICS`: with a warm cache and the switch off, atomic functions would be copied without their stops (a guarded call would do a CAS four times) | the cache key is `<format>-atomics<0/1>` |
| 3 | A whole capture of the chain's device (ClearPending, with `sa2_renut_deferred_chain` off) cleared the dirty tags without passing their chunks on | their chunks go with the chain's next delta (`g_capture_cleared_tags`) |
| 4 | The title device's marks are not atomic (a setter on another thread between the delta's read and clear could be lost) | not changed: the periodic whole check is the net (32nd delta; a miss turns the marks off) |
| 5 | switch_hot_bulk.py `--merge`: a pruned function could not come back even with 50+ samples in a new profile | `have` taken after the prune |
| 6 | Two thread-safe statics read per draw in CaptureDelta | not changed (two acquire loads a draw, about 3 us a frame) |
| 7 | The capture marks' counters were never reported | in the 10 s "device snapshots" line |
| 8 | NewOp's untagged chunks were gated on `sasrt_record_device_slots`, not on the device having a slot | gated on `tracked` |
| 9 | switch_hot_bulk.py's `raw_ok` did not know the atomic forms (a carded raw form plus atomics left a function out) | the atomic forms accepted there too |
| 10 | pgo_cycle.ps1: a streams folder inside pgo/ would be moved aside; two runs in one minute | refused; the aside folder named to the second |

Checked and found correct by the audit: every atomic / time-base form in the tree matched; unmatched raw forms still
refused; the stop paths' returns; store cards inside the braces; the guard forms' null pointers never reached (InitHook
gives kDirect); the PowerShell cache logic; the shard regex and `-Os` ordering; closure options; the size unit; the
delta-to-mark mapping (i - 18), the delta's ascending order, tags read before the clear; the rebase and the check;
the NewOp chunks 26 / 27 / 58. Also noted: `banjo_renut_snapshot_deltas_narrow` is off here (deltas compare all 77
chunks, 0-17 always).

## The batch's tests (instrumented build of 21:30, guard forms on)

- **gv1** (the dense guard: banjo_hot_guard_calls 4000, period 64; the batch's keys on): **1,927,100 calls compared, 0
  differences** (7 differed once and not when repeated; the memcpy native's one-time line again); 954 of the 1,236 bulk
  copies reached; 0 fence timeouts. The recording marks held (0 chunks without a mark). The capture marks dropped
  themselves at 21:34 (their net working): title device chunk 75 (+0x32C0) changed without a mark.
- **tv3** (every delta compared whole, the misses logged once each): three chunks of the title device change without a
  tag: 19 (+0x4C0, a fetch constant), 72 (+0x3200: the index buffer, render target and depth pointers) and 75 (+0x32C0:
  the texture pointers of slots 18-25), about 1 % of the deltas; the recording devices 0 again. The three go into the
  chunks every delta compares (mark bits 1, 54, 57).
- **pgotrain2** (the PGO session of the batch, 21:50; the batch's keys on): the capture marks held all race: about
  123,000 deltas a 10 s window from the marks, 36.7 chunks compared a delta of 77 (chunks 0-17 always: the narrow deltas
  are off here), 0 changed without a mark; the recording marks 0 too. The session's stream (sasrt_pgo_6; 4 and 5 were
  gv1's and tv3's, left out) merged by `tools/win/pgo_cycle.ps1 -Step use`, which moved the old profile aside, cleaned
  out\nx and built it (guard forms OFF).
