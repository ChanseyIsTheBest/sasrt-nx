# Optimising game functions (sasrt-nx)

How this port turns hot recompiled game functions into faster native code, and what was done on 2026-11-08. The method is
katamari-nx's `docs/optimising-functions.md` (Beautiful Katamari), which took it from banjo-nx (the localizer and the
guard), bejeweled3-nx (the bulk list and the direct dispatch) and sa2-nx (the localized copies and the first hand-written
natives, themselves from masseffect-nx). All GPL-3.0, the same project family; the files keep their banjo names.

There are two tracks, and both keep one rule: **a replacement leaves every guest byte and every register exactly as the
recompiled original leaves them**. The guard checks that on every port that runs it.

- **The machine track** turns a recompiled function into a *localized copy*: the function's own statements with its
  registers in C++ locals, its small callees inlined as copies of their own, and only the registers a call can reach
  handed over around it. Made by `tools/localize_native.py`, for every function the console profile caught.
- **The hand track** puts a *hand-written native* in front of a copy, where the samples show a cost a rewrite can remove.
  The native returns false to decline a call it does not cover, and the copy runs instead.

## Files

| What | Where |
|---|---|
| the localizer (katamari-nx's, paths for this tree) | `tools/localize_native.py` (sa2-nx's old one kept as `tools/localize_native_sa2.py`) |
| the bulk list from a console profile | `tools/switch_hot_bulk.py` (reads the NRO's link map, the archived ELF is stripped) |
| the hot instructions inside one function | `tools/switch_hot_pcs.py PROFILE MAP ELF name` |
| a profile by thread and kind of code | `tools/profile_breakdown.py PROFILE --map MAP` |
| the hand-picked list (each its own hook) | `app/src/cpu/hot/localized.txt` |
| the bulk list (twelve shards) | `app/src/cpu/hot/localized_bulk.txt` |
| the hand-written natives | `app/src/cpu/hot/hand.txt`, the code in `app/src/cpu/hot/banjo_hand_natives.h` |
| the hooks and the guard | `app/src/cpu/banjo_hot_guest.cpp`, `banjo_hot_guest.h`, `banjo_hot_common.h`, `banjo_hot_shard_<k>.cpp` |
| the copies (generated) | `app/generated/hot/n_<address>.h`, `banjo_hot_list.inc`, `banjo_hot_bulk_<k>.inc` |

The old system stays for what it still does: `app/src/hot/sasrt_hot_guest.cpp` hooks the C runtime's memcpy, memset and
memmove, the two Direct3D float-constant writers and the movie colour conversion with their own range guard. Its slots in
`PPCContext::host_counters` are the first 8 (`sasrt::hot::kCtxSlots`), the new list's hooks take 8 to 59
(`tools/localize_native.py` `SLOT_BASE`), the bulk hooks share one counter each, and slot 63 is the native Direct3D layer's.
`app/src/hot/localized.txt` and `app/generated/hot/hooks.inc` are no longer used.

## Making the copies

`tools/post_codegen.py` runs the localizer after every codegen, where katamari-nx runs it (after `flush_hoist.py`, before
the late steps), with `--list --bulk`. It also reads the late steps' forms (`r1l`, `REX_INL`, store cards), so on a
processed tree it can run by itself:

```bash
python tools/switch_hot_bulk.py out/console_runs/prof_stock/rex_profile_008.log out/builds/nro_1108_0904/sasrt.map --write app/src/cpu/hot/localized_bulk.txt --min-samples 1
```

```bash
python tools/direct_calls.py --redo --gen app/generated/default
```

```bash
python tools/localize_native.py --list --bulk
```

The second step matters: the generated code calls an unhooked function through `__imp__sub_X` (inlinable, and past any
hook). `tools/direct_calls.py` reads the lists (they are `.txt` files under `app/src`) and sends the callers of every listed
function through its hook. Without it, the first PC run reached only 21 of the 694 bulk copies.

What stays out of the bulk list (`switch_hot_bulk.py` says how many of each): tiny leaves (12 guest instructions or fewer,
the generator inlines them), functions an app or SDK source names (their own hooks), functions with an atomic
compare-and-swap, the global lock, setjmp or a host call inside (the guard's roll-back would be visible to other threads),
the threaded dispatch of `sub_82EB6B78`, and forms of raw guest access the tool does not record.

## The changes this port made to katamari-nx's localizer

- **Paths and keys.** The tree is `app/generated/default/sasrt_recomp.N.cpp`, the image `out/default_image.bin`, the
  function table `sasrt_init.cpp`; each copy's key is `sasrt_cpu_native_sub_<address>`. The configuration files read for
  hooks are those `tools/direct_calls.py` reads, **not** `app/thunks.toml`: it names every thunk's target, and with it 290
  of the profile's functions were left out as "hooked".
- **Hand-written natives in front of a real call** (`hand.txt` `reads=`). The stack cookie check `sub_82C92CC8` ends every
  function with a stack buffer; its failure path reaches an indirect call, so no copy could take it in, and 73 copies made
  a real call to it, storing and reloading every register (and the guard could never compare them). With `reads=r3` the
  native stands in front of that call: r3 is stored, the native answers the equal path, and only a declined call makes the
  real call with the full hand-over. The original statements' logged form asks the native too (it writes nothing when it
  answers), so the guard compares those copies now.
- **Proven-dead write-backs are not compared.** `tools/leaf_dead_stores.py` proves some leaf write-backs are read by no
  caller and compiles them out (`REX_LEAF_DEAD_R` / `_F`); the copy, made from the ctx form, still writes them. The guard
  reported seven such copies as different (`sub_82610038`'s r9: the copy's value, the original's left as it came). Those
  registers are now in each hook's skip set.
- **Merged vector stores** (`merge_vector_stores`; switch back `SASRT_HOT_MERGED_STORES=OFF` in CMake). In the copies'
  running form only (the original statements' logged form keeps the original stores, so the guard compares against
  them): an stvlx / stvrx pair of one vector at ea and ea + 16 becomes one 16-byte store, and four stvewx of one vector at
  ea, ea + 4, ea + 8, ea + 12 (each the lane its address selects) become one 16-byte store of the four words. The same
  bytes and the same store-card marks; the offsets are checked at run time and anything else stores as before.

## The hand track

### The gate

katamari-nx's gate: a console profile shows the function; it is in the thread that limits the frame rate; at least 2 % of
that thread; it already runs as a machine copy; and the samples show a cost a rewrite removes. The guide says a user's
request for functions from console data satisfies the first four, and condition 5 still decides.

The race at stock clocks is GPU-bound (the user's own breakdown request of 2026-11-08: GPU 55-60 ms a frame, CPU 174 % of
300 %), so condition 2 fails for every CPU function. The user asked for the CPU work anyway ("hand optimise the top 10
functions and machine optimise the rest"), so the top ten guest functions of the stock-clock profile were taken as asked,
and condition 5 decided each one.

### The ten (rex_profile_008, the 9:04 NRO; ranked over the race window, reports 12-26, as in the CPU breakdown)

| rank | function | thread | samples | what the samples show | result |
|---|---|---|---|---|---|
| 1 | `sub_8286C230` water step | WaterThread | 207 | ~70 in four misaligned vector stores a step (vperm, four stvewx: a stack spill and a lane load, swap, store and card mark each); 32 in a square-root / divide chain | **native** `sasrt_hand_water_step`: each group as one 16-byte store |
| 2 | `sub_82872180` water table lookup | WaterThread | 143 | 22 on its two `msr fpcr` and the branch after them; the rest stack round trips | **native** `sasrt_hand_water_table`: no mode switch, no stack round trip |
| 3 | `sub_828729E8` | WaterThread | 82 | stores of vector registers to the context and horizontal adds | **declined**: the machine copy keeps the registers in locals (the cost the samples show); the rest is arithmetic. Its copy now inlines the native of rank 2 |
| 4 | `sub_827168E0` | AK::EventManager | 75 | single-precision multiply-adds and their two conversions each | **declined**: the double rounding of the exact form is the arithmetic itself |
| 5 | `sub_825E0F28` | Main XThread | 59+ | | **not a copy**: an atomic compare-and-swap (lwarx / stwcx.) |
| 6 | `sub_82720840` audio resampler | AK::EventManager | 64 | 20 in the stvlx / stvrx byte-piece helpers of each step's unaligned store | **native** `sasrt_hand_resampler`: one 16-byte store |
| 7 | `sub_82754EC0` | Main XThread | 53+ | | **not a copy**: atomics |
| 8 | `sub_82748550` | SlRenderer, Model Instance | 101 | vector multiply / add chains | **declined**: arithmetic |
| 9 | `sub_827C56C8` | SlAnimManager | 66 | 7 on an `msr fpcr`; quaternion-to-matrix arithmetic | **declined for now**: the mode switch is 11 % of it; a mode-free form needs a range proof over 25 scalar steps |
| 10 | `sub_8279AFE0` | SlRenderer | 51 | 17 right after a recursive call | **declined**: nothing local to remove |

Below them: `sub_827506C0` (atomics, not a copy); `sub_8278E170` (its cost is its calls to the Direct3D constant writers,
which the old natives already handle); `sub_827760E0`; and `sub_8279A888`, the bounding sphere fit, which is a **native**
(`sasrt_hand_sphere_fit`): 17 of its 57 samples were on two `msr fpcr` per point, and its distance loop now keeps the vector
mode, computing each point's square root and add with the FPU mode's result (`detail::Sqrts`, `detail::Fadds`: exact, a
cold path with the mode cleared for an operand or result in the denormal range).

The fifth native, `sasrt_hand_cookie_check` (`sub_82C92CC8`), is not in the ten by its own samples; it is what lets 73
copies run without a real call at their end, and what lets the guard compare them.

So **five hand-written natives**: four of the profile's top ten passed condition 5 (ranks 1, 2 and 6, plus the sphere fit
from rank 14), and the cookie check. The others are recorded above with the reason, as the guide asks.

### How the natives are written

Three of them (`sub_8286C230`, `sub_82720840`, `sub_8279A888`) are the machine copy's own statements (the localizer's
`f_sub_<address>` text, registers in locals) with the hot part rewritten: the generator scripts that made them are named in
each native's comment. That keeps everything outside the change identical to the copy by construction. `sub_82872180` and
`sub_82C92CC8` are written out by hand. Each writes back every register its processed original writes back (`hand.txt`
`exact=` lists all of them), so the guard compares every register.

## Checking

| run | what | result |
|---|---|---|
| PC, `sasrt_710` | first bulk build, guard dense (4000 calls a thread, then 1 in 64) | 9 differences: 7 dead write-backs (fixed: skip set), 2 from the first cut of `reads=` (fixed: its dirty registers), 1 not understood (`sub_82742DD8`: off in the bulk list) |
| PC, `sasrt_711` | 23 listed + 939 bulk copies, five natives | 841 hooks reached (819 bulk), 4,828,068 calls compared, **0 differences**; the natives: water step 13,036, water table 272,954, sphere fit 4,063, resampler 5,187, cookie check 60,426 compared |

| PC, `sasrt_712` | the same with the merged vector stores | 841 hooks reached, 4,822,608 calls compared, **0 differences** |
| Ryujinx, `hot_verify1` (NRO 10:25, 460 s) | five natives, dense guard; the run ended in the menus | 468 hooks reached, 2,500,853 calls compared, **0 differences** |
| Ryujinx, `hot_verify2` (NRO 10:36, 620 s, `race_ryujinx_slow.txt`) | merged stores; reached the race | 869 hooks reached (847 bulk), 6,779,144 calls compared, **0 differences**; water step 17,690, water table 472,748, sphere fit 4,108, resampler 8,082, cookie check 96,185 compared |

A test toml with the dense guard: `tools/make_renut_test_configs.py` `sasrt_hot_verify`; the bulk copies and the natives
off: `sasrt_hot_off`.

## What it did on the console (2026-11-08, stock clocks, the first race)

Two runs of the 10:36 NRO (direct dispatch, no guard), driven over the LAN with the user's go-ahead
(`out/console_runs/hot_1040`, `hot_ab`):

- **The code mix moved as intended.** Race window, all threads: generated code fell from 56.6 % of the busy samples to
  14.8 %, machine copies rose from 4.8 % to 42.1 %, hand-written natives from 1.5 % to 5.3 %. In WaterThread the two
  natives are 29.1 % and 15.5 % of its samples (their originals were 31.4 % and 21.0 %).
- **The CPU time did not measurably drop.** The in-run A/B (`banjo_renut_ab_target = 70`: every copy's hook sends its
  calls to the generated original in the off half; 4 s halves, 140 s of race each) measured all threads' CPU at 97.1 ms a
  frame with the copies and 96.8 ms without, 17.7 and 17.9 fps (GPU-bound, 55 ms of GPU a frame either way). The halves
  scatter from 17 to 178 ms, so a difference under about 15 ms a frame would not show. The per-thread profile (rex_profile_009
  against the morning's 008, different stretches of the race) agrees: WaterThread 14.1 % against 14.2 %, Main XThread 47.7 %
  against 44.2 %.
- **What it costs:** the NRO grew from 61.9 MB to 74.4 MB (about 13 KB a copy).

So the machine track and the natives are exact (every guard run above) but, on this game's race, not a CPU saving the
console can measure; the A57's time in this game goes to the arithmetic the exact forms need, which a copy keeps. They stay
on (a base for further hand work, as katamari-nx keeps its copies); `banjo_cpu_native_bulk = false` and the natives' keys
take them out, and `sasrt_hot_off.toml` is the A/B half.

## Machine copies in place (since 2026-11-11)

The shipping builds no longer hook the copies: the copies are compiled **in place** of the generated functions. Same list,
same copies, same code; only how they are reached changes.

**So the PC keeps hooks for the guarded verify, and the console runs the hook-free form.** The guard, the dense checks and every verify run use a hooked build (guard forms kept) on the PC or in Ryujinx; the console only ever gets the in-place (hook-free) NRO, for performance races, PGO training and picture checks.
 (Base handoff with the patch scripts:
`docs/handoff/inplace_copies.md`; the cross-port guide: `docs/hand-and-machine-optimising-guide.md` section 2.3.)

- **What changes.** CMake `SASRT_HOT_IN_PLACE` ON (`build_switch.ps1 -InPlace`): each copy's hook macro
  (`BANJO_HOT_HOOK_EX`, `app/src/cpu/banjo_hot_guest.h`) becomes a bare redirect: the generated function's own symbol
  (`REX_HOOK_RAW(SYM)`) runs the copy's `Native` directly (`if constexpr (DEFAULT) n_ID::Native(ctx, base); else
  __imp__SYM(ctx, base);`). No state byte, no guard, no per-copy run-time key, no in-run A/B 70. `Native` loses its
  `[[gnu::noinline]]` (`BANJO_HOT_NATIVE_SPEC`, which `tools/localize_native.py` emits), so LTO can inline a copy into its
  callers, and the originals nothing names any more are dropped. It implies `BANJO_HOT_GUARD_FORMS=0`.
- **Why.** Hooked copies were about neutral (above): the hook blocked inlining into callers, kept two versions of each
  function, and split the PGO counts between them. In place (console, handheld 1020 / 460.8 / 1600, each build with its
  own PGO + LTO): process CPU -2.0 %, game thread -4.1 %, AK -6.7 %, Model Instance -4.8 %, render thread busy -2.1 %,
  NRO -4.1 MB (runs abH / abI).
- **Building.** In-place builds have their own folders and their own PGO profile, because the code differs:
  `pgo_cycle.ps1 -Step generate -InPlace` (`out\nx-inplace-gen`), one training race on the console, then
  `pgo_cycle.ps1 -Step use -InPlace -Streams <folder>` (`out\nx-inplace`, profile in `pgo-inplace/`). Any change to the
  list or to a post-codegen step changes generated text: run the whole cycle again.
- **Verifying.** In-place builds have no guard, so the guard runs on the **hooked** build of the same tree (the copies'
  code is identical): `pgo_cycle.ps1 -Step generate` (hooked, `out\nx-pgo-gen`, guard forms kept) and
  `tools/win/ryujinx_run.ps1 -Nro out\nx-pgo-gen\sasrt.nro -Set 'banjo_hot_guard_calls=4000;banjo_hot_guard_period=64'
  -InputScript tools\win\input\race_ryujinx_slow.txt -Seconds 620`. Guard runs go to Ryujinx or the PC, never the
  console. Add `banjo_renut_fast_draw_verify=true` when the batch also touches the renderer.
- **Keys.** In place, `sasrt_cpu_native_sub_<address>` and `banjo_cpu_native_bulk` are still defined (tomls load) but
  do nothing; to take a copy out, mark it `off` in its list and rebuild.

### Later lessons (2026-11-12)

- **Refresh the bulk list from a recent profile.** 69 hot functions (4.6 % of all busy samples in the race) were
  missing from `localized_bulk.txt` because it came from the 2026-11-08 profile. `tools/localize_native.py --survey`
  says which candidates a copy can take; the batch C round took all 69 and the guard found nothing.
- **`reads=` on a hand native that copies call in a loop.** A copy that calls a function with a hand native but no
  `reads=` in `hand.txt` treats it as reach unknown and stores every register before each call: about 48 in the
  water loops (`sub_828729E8`, `sub_828703E0` calling `sub_82872180`). With `reads=r1,r3,r4,r5,v1` the copy stores only
  what the native reads, and syncs everything only when it declines: WaterThread -6.3 %. List in `reads=` every register
  the native reads, plus any register the original writes that the native leaves alone (here `v1`), so the load-back
  after the call reads a current value.
- **PGO training must reach the race.** The instrumented NRO loads slower: with 40 s of menu presses the race intro
  ("A CONTINUE") waited for A for the whole drive, and the profile was the intro's. Train (and measure) with
  `console_race.py OUT menus 75`, and check that `drive_020.jpg` shows the race HUD (LAP 1) before using a stream.
- **The hand-overs at a copy's real calls and its return write-backs follow whole-program liveness**
  (`tools/reg_liveness.py`, docs/calling-convention-plan.md). The first version (callee UE + liveness after the call)
  saved almost nothing: the hottest copies are reached through vtables, and a function whose address is taken had
  LiveOut = everything, so every volatile register stayed live to its exit and through each call before it. What
  paid: the convention's exit bound (a function reached only through image pointers returns to a caller that reads no
  volatile register but the results) and counting a taken copy's hooked direct calls as known.
- **Check what `leaf_dead_stores.address_taken` calls "named".** It scans every app/*.txt and app/src file for
  function addresses. A stale copy list (app/src/hot/localized.txt, unused since 2026-11-08) and the generator's
  app/indirect_promotions.txt made the hottest copies "named in an app source", i.e. maybe called by C++ that reads
  anything: unknown calls, LiveOut everything. Print the reason histogram for the listed copies before trusting LiveOut.
- **The guard cannot see a pass that also rewrites the original statements** (stack_forward.py, the any-mode forms):
  copy and original change together. Such a pass needs its own self-check in the hooked build (REX_STACK_FWD_VERIFY
  compares each forwarded load with the real one) or a unit test against the plain form (fp_fused_any_mode_test).
- **Count ctx accesses only while x0 is ctx.** A profile tool that treats every `[x0, #n]` as a context access
  over-counts: x0 is ctx only until its first write or call. ctx_traffic.py's first figure (17.1 % of guest samples)
  was 13.7 %.

## Keys

| key | default | what |
|---|---|---|
| `sasrt_cpu_native_sub_<address>` | on (off where the list says `off`) | each localized copy (hooked builds only; in place they do nothing) |
| `banjo_cpu_native_bulk` | on | all bulk copies |
| `banjo_hot_guard_calls`, `banjo_hot_guard_period` | 64, 4096 | the guard: the first N calls of each thread, then one in P; both 0 is the direct dispatch (no guard, no counter) |
| `banjo_hot_count` | off | PC measurement: block counts for `tools/hot_arm_compare.py` |
| `sasrt_hand_cookie_check`, `sasrt_hand_water_table`, `sasrt_hand_sphere_fit`, `sasrt_hand_resampler`, `sasrt_hand_water_step` | on | each hand-written native, in every copy that contains it |
| CMake `SASRT_HOT_MERGED_STORES` | ON | the merged vector stores in the copies |
| CMake `SASRT_HOT_IN_PLACE` | ON in the shipping builds (`build_switch.ps1 -InPlace`) | the copies compiled in place of the generated functions (no hooks, no guard) |

## What to do next

- A console profile of the new NRO at stock clocks (the same race), read with this document's tools, for what the copies
  and natives changed on the A57.
- The merged stores catch only adjacent groups (20 pairs and 13 quads in 10 copies); most occurrences interleave the
  stores of several vectors. A pass that proves the interleaved stores disjoint would take many more.
- `sub_827C56C8`'s mode switch, with a range proof of its scalar block.
- 120 of the 939 bulk copies were not reached by the PC race; a run through the menus and other tracks would check them.
