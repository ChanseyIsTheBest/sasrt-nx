# CPU moonshot ideas (2026-11-12, an Opus agent's list, read-only research)

Ranked by expected payoff / effort. Measurements first: (a) the A57 PMU counters from user mode (needs Atmosphère's
`enable_user_pmu_access` system setting: the user's call), (b) one race window at the lowest dynamic resolution (CPU vs
GPU DRAM contention).

1. **FPSR-checked flush mode**: short scalar runs inside VMX-mode code stay in flush mode; `mrs fpsr` IDC|UFC at the end,
   redo on the cold path only when a denormal was flushed. FPCR writes measured 40-44 ns; ~43,600 switches a frame.
   2-4 %; exact; universal. Test: FPSR read/clear timing in the profiler header + census of short runs.
2. **Cross-register-file stack round trips forwarded in registers** (stw x4 + lvx, stfs + lvlx + vspltw, stfd->lwz,
   std->lfd, stvx->lwz/lfs): stores stay, loads take the stored values. 1-2.5 ms a frame; exact; universal.
3. **XMA decode cache** (packet hash + context state -> PCM), then AK onto core 3. Exact; needs a repeat-rate log.
4. **Shadow vtables**: read-only code-address words -> host function, one load per virtual call. 0.4-1.5 ms; exact.
5. **ctx / base pinned in host registers**, PPCContext reordered by heat (v32-v63 out of ldp range today). 0.5-2 %.
6. **MMU dirty tracking instead of store cards** (write-protect clean cached pages, fault once). Up to the cards-off
   measurement (guess 1-2.5 ms); exact; risks: memory type, 2 MB blocks, kernel writes.
7. **BOLT-style hot/cold packing** for the shared 2 MB L2. 0-3 %. Test: distinct 64-byte lines covering 90/99 % samples.
8. **Clang/LLVM for sasrt_recomp** (+ sample PGO from the console sampler). -2 % to +8 % of guest time.
9. **Memoised near-pure guest calls across frames** (guard-checked keys). 0-3 ms a frame.
10. **Zero-copy geometry** (guest physical memory as a deko3d block, decode in the vertex shader). Render thread -2-3 ms.
11. **D3D HLE at the draw level** (skip SlRenderer's PM4 build + Renut capture). 3-6 ms; months.
12. **SSA lifter to LLVM IR with alias scopes** (ctx / stack / rodata / heap regions). 5-15 % of guest; months.
13. **Guest memory as little-endian words (address ^3 / ^2)**. -1 % to +4 %; unaligned-access risk.

## Census of idea 2 (2026-11-12, tools/stack_roundtrip_census.py on the batch D tree + abD profile)

8,653 static round-trip sites in 2,439 functions (827 sites in 175 functions with console samples, holding 26 % of
guest samples). Kinds: lfd<-std 3,310, lwz<-stfd 1,065, lvx128<-4 stfs 675, lfs<-stvx 626, lfs<-stw 414, lvx128<-4 stw
413, lwz<-std 405, ld<-stvx 312, lwz<-stfs 274, ld<-2 stw 239. The certain stalls on the A57 (a wide load over several
narrower stores: no forwarding) are the vector loads over four 4-byte stores (~1,090 sites) and ld over two stw (~240);
same-size cross-file pairs (std->lfd, stfs->lwz) and loads contained in one store probably forward. The pass targets
the first group first: the stores stay, the load takes the stored values (exact while nothing else can write those
bytes in between: no call, no label, no store through an unknown base).

## Measurement for idea 1 (2026-11-12, tools/fpcr_cost.py on abD's profile)

Samples on an `msr fpcr` or the two instructions after it: 331 of 15,430 (2.15 % of all process samples, ~1.7 ms a
frame), 3,229 such writes in the 500 hottest functions. Concentrated: n_8260EAA8 37 (SlAnimManager's top), n_8274F568
30, the water step's hand native 8286C230 23, n_82610E10 20, n_8275E3D0 16, n_82E3C4D8 12, n_8275D5B8 11. Few
disable / enable pairs sit in clean straight runs (most cross blocks or calls), so the FPSR-checked form goes where
the samples are: those functions' switch sites first. The FPSR read / clear cost comes from the next profile header
(sdk/src/ui/switch_perf.cpp, 2026-11-12).

## Idea 1, what went in (batch CC2, 2026-11-12)

- FPSR costs, measured on the console (profile header): read 16.6 ns, write of zero 10.8 ns; an FPCR write that
  toggles the flush mode 44 ns. The host flush mask is FZ + FZ16 only (no default-NaN bit), so a scalar operation in
  flush mode with no denormal operand and no tiny result gives exactly the FPU-mode bits; nothing in the SDK reads the
  host FPSR except crash dumps.
- Part 1: `fp_mode_lookahead_run = 4` (generator default 2): runs of up to four scalar single operations between
  vector code take their any-mode forms instead of two FPCR writes (~90 cycles); an any-mode operation costs a few
  compares more than the plain one.
- Part 2: `fp_fused_single_any_mode = true` (new codegen option): fmadds / fmsubs / fnmadds / fnmsubs were "FPU only"
  and forced the switch however short the run; now they count as single operations and take exact any-mode forms
  (rex::ppc::FmaddSingleAnyMode etc., diet_ops.h). With no denormal operand the fused double result can only be
  changed by the mode when it is tiny, which flush mode returns as zero: a zero result with neither factor zero goes
  to the cold helper (a zero factor makes the result the addend, exactly), and the rounding to single is
  RoundToSingleAnyMode's. sdk/tests/fp_fused_any_mode_test.cpp (in tools/win/run_sdk_tests.ps1): 74,088 edge triples
  + 20 million random / near-cancelling triples, 160.6 million comparisons in both modes, 0 differences; the plain
  expressions differ between the modes in 1.48 million of them (negative control positive).
- The FPSR-checked run (redo on IDC | UFC) is left for runs the any-mode forms cannot take: it needs store-free
  straight runs (a redo after a store can read back its own first pass), and most hot switch pairs cross a store, a
  block or a call.

### Idea 1, first console reading (abCC2 against a same-session CC1 control abCC1r, 2026-11-12 20:00)

Flush-switch samples 2.18 % -> 1.77 % of the race (the same functions stay on top: 8260EAA8, the water step's hand
native 8286C230, 8274F568, 82610E10). But the hottest copy, the water step sub_828729E8, took 389 -> 474 samples:
the same three FPCR writes as before, more single-precision denormal checks (`tst x16, #0x7fffff; b.ne`) inside its
loop and vector spills around them (`ldr q23, [sp, #432]`). The any-mode forms cost more there than the switches they
were meant to save (the lookahead counts instructions up to the next branch, not iterations of a loop that already ran
in one mode). Pending the retrained CC2 measurement; if CC2 stays behind the control, the next batch reverts
fp_mode_lookahead_run to 2 and fp_fused_single_any_mode to false.
