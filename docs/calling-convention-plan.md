# Removing the guest calling convention (the "cc" / ctx moonshot): measurements and plan

sasrt-nx, 2026-11-12. The user: "start on the ccx stuff" (Blur takes value profiling and -fipa-reorder-for-locality).

## What it is

Every recompiled guest function takes `PPCContext &ctx`: the 360's registers live in memory, and calls hand arguments,
results and saved registers through it. Machine copies keep registers in C++ locals *inside* a function, but at every
call a copy still stores the registers the callee may read and reloads those it may change; at entry it loads what it
uses, at exit it writes back what it changed (minus LiveOut-dead registers, idea 37). The moonshot: native signatures
(arguments and results in machine registers) where whole-program analysis proves them, `ctx` only at indirect calls,
hooks and kernel entries.

## The ceiling, measured (2026-11-12)

`ctx_traffic.py` (scratchpad; to move into tools/): console race profile + the same build's map and ELF; guest code =
sub_XXXXXXXX sections (in-place copies, generated code), the copies' n_ forms, hand natives; a sample counts as ctx
traffic when its instruction is a load/store whose base register holds ctx (x0, or what the prologue copied x0 to).

| | SASRT (abD, rex_profile_240) | Blur (2026-11-12_ab_base, build 07:18) |
|---|---|---|
| guest code, share of all samples | 59.9 % | 63.8 % |
| loads/stores, share of guest samples | 75.8 % | 65.1 % |
| ctx loads/stores, share of guest samples | 17.1 % | 11.7 % |
| **ceiling, share of process CPU** | **~10 %** | **~7.5 %** |

SASRT's ctx samples by field (context offsets from the compiler: r3 at 0 ... r31 248, lr 256, ctr 264, xer 272, cr0-7
292-323, fpscr 324, f0-f31 336-591, v0-v127 592-2639):

| | loads | stores |
|---|---|---|
| GPR r3-r10 (arguments) | 216 | 202 |
| GPR r14-r31 (saved) | 139 | 6 |
| GPR r1/r2/r13 | 103 | 59 |
| GPR r0/r11/r12 | 57 | 4 |
| VR v32-v63 (scratch) | 66 | 214 |
| VR v2-v13 (arguments) | 27 | 129 |
| VR v0-v1 | 3 | 22 |
| VR v14-v31, v64-v127 (saved) | 18 | 34 |
| FPR | 32 | 69 |
| fpscr / CR / lr, ctr, xer | 88 | 6 |

(1,520 ctx samples of 15,430; per-function: 828729E8, 8279AFE0, 82754EC0, 827506C0, 8278E170 lead.)

**Correction (2026-11-12 16:15):** the first ctx_traffic.py counted every access through x0 as ctx, but x0 holds
ctx only until its first write or call; after that it is mostly a guest-memory pointer. Fixed (tools/ctx_traffic.py):
SASRT abCC1 has 1,215 ctx samples = **13.7 % of guest samples, 7.9 % of all process samples** (the table's 17.1 % /
~10 % were overstated by ~20 %). Blur's 11.7 % / ~7.5 % came from the same tool and is likely overstated the same way.

**v1 is an argument and the result register (2026-11-12 16:30).** The plan's convention table (v0-v1 scratch, v2-v13
arguments) is the standard AltiVec ABI; this game's code passes the first vector argument and returns vector results
in v1 (census: 173 functions read v1 on entry, v2 57, v3 17; pointer-reached functions: v1 100, v2 40, v3 8, none v0
or v32-v63; v1 the vector most read after calls). Stage 1 (abCC1) treated v1 as scratch; fixed in reg_liveness.py
before batch CC2 was built: scratch = v0 + v32-v63, exit-dead vectors = v0, v5-v13, v32-v63. The direct-call census
also showed the compiler relying on callees leaving volatile registers alone at ~2 % of direct calls (1,857 of 110,802
sites), so no "volatile registers are dead after every call" assumption for direct callees: their LiveOut stays what
their callers read.

Entry census of the 45,146 pointer-reached functions (registers read before written, 2026-11-12): r3 16,461, r1 7,149,
r4 5,896, r5 1,425, r6 302, r7 86, r8 77, r9 17, r10 15; f1 500, f2 96, f3 56, f4 31, f5-f10 a few; v1 100, v2 40,
v3 8; also r12 55 and r0 19 (so those two stay in the indirect-call bound); r13 322 and saved registers (to save
them). None read r11, f0, v0 or v32-v63.

## Stages (each exact, each guarded; stop when a stage stops paying)

1. **Scratch registers not handed to calls that cannot read them** (ceiling ~240 samples, ~1.5 % of process CPU:
   the v32-v63 / v0-v1 / r0 / r11 / r12 / f0 stores). At a call whose reach is unknown *only* because of indirect calls
   in its tree (no hooks, kernel imports, host functions, setjmp), the standard calling convention bounds what the
   unknown part reads on entry: arguments (r3-r10, f1-f13, v2-v13), r1/r2/r13 and saved registers, never the scratch
   ones (a target reached through a pointer must follow it: its callers are unknown to the 360 compiler too, LTCG
   included). Skip storing a scratch register R before such a call when the callee tree's known part does not mention
   R **and R is dead after the call in the copy** (no read before a write on any path, and not written back at exit:
   LiveOut). The second condition is what keeps the guard exact: the original and the copy then differ only in
   registers nothing reads. Needs: (a) Reach with an "all but the scratch set" bound for indirect-only trees, (b) a
   per-call-site liveness pass over the copy's text (labels / gotos; ro_constants_cfg.py has a CFG builder to reuse).
2. **Native arguments for closed call trees.** For callees whose whole tree is known (no indirect calls, hooks,
   kernel imports), pass the registers the callee reads (from Reach) as C++ arguments and return what it changes,
   instead of through ctx: the copy tool already inlines small closure members; this extends it to real calls of
   other copies (a second entry point `n_X::Args(...)` next to the ctx one, which stays for indirect callers, hooks
   and the guard). Ceiling: most of the 418 argument-register samples + part of r1/r13 (~2.5-3 %).
3. **Saved registers kept local across calls** (r14-r31, v64-v127, f14-f31): whole-program proof that a callee tree
   restores each one it writes (r1_preserve.py does it for r1 today; generalise it). Then no store before / reload
   after for those. Ceiling ~1 %.
4. Only then: signatures program-wide (the generator itself), if 1-3 paid.

## Risks (and the answer for each)

- Indirect targets with non-standard conventions: only functions reached through pointers are bounded by the standard
  convention (stage 1); direct callees are always analysed, never assumed.
- Hooks (app / SDK C++ replacements) read ctx as they please: a tree with a hook stays "unknown" unless the hook
  declares its reads (hand.txt reads=).
- setjmp/longjmp, exceptions: trees with them stay "unknown" (Reach already does this).
- The guard: stage 1's liveness condition keeps every compared register equal; stage 2 keeps the ctx entry point, so
  the guard and indirect callers use it unchanged.
- Host stack (thread stacks are small: 6-38 KB deepest sampled): stage 2's arguments are machine registers, not stack;
  watch the frame sizes of the copies with many locals.
- Every change is a post-codegen / copy-tool change: one PGO cycle each, and the guard (Ryujinx / PC, never the console:
  "the PC keeps hooks for the guarded verify, the console runs the hook-free form").

## Progress (2026-11-12, during the 12-hour run)

**Stage 1 (abCC1, measured):** `tools/reg_liveness.py` (whole-program UE / LiveOut with the vector registers, per
direct call site: what the callee does not read before writing it and nothing reads after the call) and
`localize_native.py` leaving those stores out of a real call's hand-over: 1,477 stores at 841 calls, LiveOut-dropped
return write-backs 2,249 -> 2,758. Console: 28.42 -> 28.48 fps, process CPU 80.45 -> 80.07 ms (noise); ctx samples 17.1
-> 16.8 % of guest; vector stores 399 -> 391 samples. Guard: 0 differences beyond the known NaN sign.

Why so little: what was left was not "the callee might read it" but "the caller's caller might read it". A function
whose address is taken (vtables) had LiveOut = everything, so every scratch / volatile register stayed live to its exit
and through every call before it. And indirect / promoted calls stored every dirty register.

**Batch CC2 adds (all exact under the convention, the same assumption stage 1 already made at entries):**

- 1b: a call through an app / SDK hook or of a kernel import reads no scratch vector either (HOOK_USE).
- 1c: the exit side. A function entered through a pointer (or by no direct call) returns to a caller that follows the
  convention, which reads no volatile register after the return except results: v0, v5-v13, v32-v63, r0, r5-r12,
  f0, f5-f13 are dead at its exit (r3/r4, f1-f4, v1-v4 kept as results with a margin). A function with direct callers
  also gets what they read. `localize_native.py`'s return write-backs and the guard's skip set use this LiveOut for
  r/f too (dropped when either leaf_dead_stores.py's or reg_liveness's LiveOut finds it dead; the per-call-site skips
  use the same LiveOut, so the copy and the guard agree).
  Guard rail: an indirect call / jump of a *constant* target (lis + addi / ori -> mtctr -> bctr(l): 48 to parsed
  functions; the other 467 of the 515 point into the middle of functions, exception funclet trampolines) counts as an
  unknown direct call of that target: its LiveOut stays everything. Census of the ~1,120 unresolved bctr: 602 load the
  target at a constant offset (virtual tail calls), 515 constant, 3 indexed table loads, 2 other.
- 1d: an indirect call (and a promoted call's fallback) leaves out the scratch vectors dead after it (12,562 sites).
- Which "taken" functions get the exit bound: only those whose every reference is an image pointer (a data word:
  vtables, tables; a lis pair: an address built in guest code; also the generator's own promotion list and the copy
  list unused since 2026-11-08). A function named in an app source (hooks, hand natives, tomls), the entry point, or one
  a named (unparsed) function calls can be called by C++ that reads anything after it: LiveOut stays everything. A
  function with no direct caller and no reference at all also stays everything (reached some unknown way).
- Copies reached through image pointers count as known at their direct calls too (leaf_dead_stores.py excluded every
  taken copy): the copy reads and writes what its original does. Before this the hottest copies (827506C0, 82754EC0,
  825E0F28, 8278E170 ...) all had LiveOut = everything, because the dead copy list app/src/hot/localized.txt "named"
  them and so made their hooked calls unknown.

Where the ctx samples sit (abCC1, tools: scratchpad ctx_where.py, by machine position): stores in the body 32 %, loads
in the body 28 %, loads at entry 14 %, stores right before a call 10 %, loads right after a call 9 %, stores right
before a return 7 %. GCC sinks the entry loads to their first use and hoists the return write-backs, so "body" is
mostly entry loads and exit write-backs: the top function (sub_828729E8, 47 registers written back) is almost all
write-backs of f2-f13 and scratch vectors, which 1c removes. Stage 2 (arguments at calls) reaches only the ~19 % at
call boundaries: it is behind stage 3-like exit / entry work in value.

## CC3 (2026-11-12 evening): what was tried

- **Item 2, argument registers after an indirect call are garbage** (r5-r10, f5-f13, v5-v13 not written since a
  call the compiler could not know): exact under the convention, census clean (9 promoted sites whose target "reads"
  one are varargs spills, kept by the rule), but nearly a no-op: 2,608 indirect sites, +103 general register-sites of
  1.72 M. The stronger form (also after a direct call, what its tree may write and the caller does not read) +1 %, and
  neither moved the hot copies' LiveOut. Dropped (the hot chains run through direct calls followed by known calls,
  whose UE legitimately includes arguments, and through recursive pairs like 825E6AC0 <-> 8241D040).
- **Traps read only their operands** (and r3 / r4 for the service traps' debug string): ppc_trap (the generated pch)
  only logs and continues, but leaf_dead_stores.py's defuse said a tw / td trap reads EVERY register, so every function
  with a divide-by-zero check had UE = everything, scratch vectors included. Fixed in reg_liveness.defuse (TRAP_USE,
  SASRT_REG_LIVENESS_TRAP_ALL=1 restores ALL): indirect sites with skippable scratch vectors 12,076 -> 21,404, vector
  register-sites 7.24 M -> 9.18 M, 8256ADC0's LiveOut 190 -> 162 bits. Exact (the copy and the original both call the
  logging trap). In cycle A. Universal: leaf_dead_stores.py's own rule (the generated tree's dead leaf write-backs) has
  the same over-caution in every port.

## Saved registers across real calls (sized 2026-11-12, parked)

The idea: under the convention every callee restores r14-r31, f14-f31, v14-v31, v64-v127, so a copy need not store
them before a real call nor reload them after. Sized on the CC2 copies: saved registers are 6 % of the (sample-weighted)
stores before real calls and 9 % of the reloads after them; with the corrected profile's ~210 samples at call
boundaries that is ~0.2 % of CPU. And not free: ~61 functions really use an incoming saved register (several at
unaligned addresses: function chunks / funclets that continue their parent's frame), so the stores need a per-callee
"saved use" analysis, and the reloads a runtime check in the hooked build. Census tools: scratchpad
saved_use_census.py, nonpreserving_census.py (the second needs the save helpers recognised: in this tree they are plain
sub_82C8xxxx calls). Parked unless a profile shows more saved-register traffic.

## Estimates

Realistic capture of the ceiling: half to two thirds. SASRT ~5-6 % of process CPU (GPU-bound: headroom, small fps);
Blur ~4-5 % (CPU-bound at 18-21 fps: roughly +3-5 % fps). Stage 1 alone: ~1-1.5 %.
