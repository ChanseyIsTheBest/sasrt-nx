# CPU moonshots, part 2: twenty more (2026-11-12, an Opus agent's list, read-only research)

Twenty ideas that are not in docs/cpu-moonshots-1112.md (its 13), docs/calling-convention-plan.md (the cc stages),
the machine-copy ideas 26-60 (docs/machine-copies-deferred.md), Blur's VS passes, value profiling or
-fipa-reorder-for-locality. Where one touches a listed idea, its entry says how it differs. Nothing was changed in the
tree. The only new file is this document; the census scripts are in the session scratchpad (paths at the end).

## What the ideas are measured against (abCC2: rex_profile_245 with the same build's out/nx-inplace map and ELF)

Race reports 10-31, 14,056 samples. Busy samples by kind: guest copies and hand natives 54.9 %, generated guest code
10.3 %, Renut / plume / deko3d 21.0 %, host sync (libnx mutexes, condvars, PosixEvent, WaitMultiple) 2.9 %, FFmpeg / XMA
2.0 %, malloc / free / new 0.9 %, Rtl critical sections 0.8 %, kernel exports / XObject 0.7 %, RTTI (`__dynamic_cast`)
0.4 %, armDCacheClean 0.6 %, unknown PCs 3.5 %.

Which instruction the samples sit on, in the 414 hottest guest functions (8,487 samples; the A57 sample lands on the
oldest instruction not yet retired, so a load waiting for its data collects them):

| class | share of guest samples | | class | share |
|---|---|---|---|---|
| load, GPR, `[xN, #imm]` (guest heap through a pointer) | 24.7 % | | store, GPR / vector, other | 9.2 % |
| load `[base, wN, uxtw]` (guest address in the mode) | 16.8 % | | store `[base, wN, uxtw]` | 3.7 % |
| integer / SIMD ALU | 8.0 % | | stack `[sp]` traffic (spills: q 4.2 %, x/w 4.2 %) | 8.4 % |
| ctx loads `[x0, #...]` | 6.6 % | | rev (the swap itself) | 0.9 % |
| moves / permutes (`mov`, `fmov`, `tbl`, `dup`) | 6.4 % | | msr/mrs | 0.9 % |
| vector / FP loads, other | 5.6 % | | atomics / barriers | 0.7 % |
| FP / SIMD arithmetic | 5.5 % | | branches | 1.1 % |

Windows (share of ALL process samples): host atomic / barrier + the next two instructions 2.71 % (libnx mutexUnlock 97,
mutexLock 76, RtlEnterCriticalSection 44, RtlLeaveCriticalSection 31, mutexTryLock 13); a guest load followed by its
`rev` 2.23 %; `msr fpcr` + next two 1.86 %; the store-card mark (`strb wzr`) + next one 1.61 % (0.75 % on the store
itself; 13,528 marks in the 450 hottest functions); guest atomic / barrier + next two 1.59 % (n_82754EC0 34, sub_82783D88
29, n_827506C0 27); `blr` and `fdiv/fsqrt` windows under 0.1 % each.

So the process is memory-bound: about 60 % of guest samples are on loads, almost all of them guest heap, and ctx is a
tenth of that. Several ideas below are about the memory system, not the instruction count.

---

## A. Threads, the kernel layer and the host runtime

### 1. Hard affinity for the frame-critical game threads

Pin Main XThread and SlRenderer to their own cores (say 0 and 2; Renut's render thread stays pinned on 1, the XMA
Decoder on 3), one priority step above the other game threads (0x3A against 0x3B) so that a floating thread that lands
on a pinned core yields to its owner instead of holding it. The rest keep mask 0x7. A key with a list of
`name:core` pairs; the SDK already has RexSwitchPinCurrentThreadToCore (sdk/src/core/threading_switch.cpp). Add a
migrations-per-second line per thread to the 10 s report (RexSwitchCurrentCore read at each return from a kernel wait).

- **Why on the A57:** every core has its own 32 KB 2-way L1D, 48 KB L1I, TLBs and branch predictor; a migration
  refills them from the shared 2 MB L2 or from DRAM. The port has the measurement already: un-pinning the render thread
  (lat1, in-run A/B 2) took it from 22.7 to 26.8 ms a frame (+18 %) and the fps from 24.7 to 23.5. The SDK's own note
  says a preferred core alone does not stop the migrations (0.24 per loop). Main XThread (mask 0x7, preferred core -1)
  and SlRenderer, which works about 36 % of the time and wakes several times a frame, are the threads with the most
  wake-ups landing on a cold core. The latency round tried the priority step alone (lat3: no gain) and un-pinning; it
  never pinned the game threads.
- **Ceiling / expected:** if Main and SlRenderer (37 ms a frame together) recover a third to a half of what the render
  thread lost un-pinned, 2-3 ms; with WaterThread and Model Instance steadier, 4-5 ms (5-6 % of process CPU).
  Realistic 1.5-3 %.
- **Exactness:** guest semantics untouched (scheduling only; the game is nondeterministic across runs already).
  Verify with paired race windows (perfab), the migrations line, the slow-frame log and the audio.
- **Difficulty / risks:** 2-4 days. A pinned thread whose core is held by another pinned or higher-priority thread
  waits (hence the priority step, and no pin on core 3: the P5/P6 silences and stutters). Model Instance's hand-offs
  with SlRenderer decide whether it shares SlRenderer's core or floats; try both.
- **Scope:** universal mechanism (the SDK, by thread name); the thread list is per game.

### 2. The kernel's dispatcher objects on Horizon's address arbiter (guest-memory futexes)

KEVENT, KSEMAPHORE, KMUTANT and KTIMER headers (DISPATCHER_HEADER: type, SignalState, wait list) live in guest memory.
Today each wait or signal looks the guest object up (ObjectTable, XObject::GetNativeObject with a `__dynamic_cast`),
locks a host mutex, waits on a host condition variable and allocates its wait vectors (`_Znwm` under newlib's malloc
lock inside rex::thread::WaitMultiple, XObject::WaitMultiple and the KeWait* exports, from the stacks). Instead: keep the
authoritative state in the guest header's SignalState word (host atomics on the big-endian word: equality compares do
not care about byte order), park waiters with svcWaitForAddress (ArbitrationType_WaitIfEqual / WaitIfLessThan) and
wake them with svcSignalToAddress (SignalType_Signal / SignalAndModifyByWaitingCountIfEqual). Multi-object waits
(WaitAny / WaitAll, timeouts, alertable waits) use a parking lot: a striped host table keyed by the object's guest
address, one intrusive wait node per thread (no allocation), each waiter parked on its own thread word. Handle-based
calls (Nt*) keep the ObjectTable but through a lock-free per-handle cache.

- **Why on the A57:** the costs are uncontended-but-shared cache lines and acquire/release pairs, which this core pays
  dearly for (host atomic windows 2.71 % of all samples). Per second in a race: ~25,000 ObjectTable lookups (330-340
  contended), ~1,080 parked WaitMultiple, 520-550 critical-section host waits, ~18,900 signals with nobody waiting.
- **Ceiling / expected:** host sync 2.9 % + kernel exports 0.7 % + RTTI 0.4 % + part of the critical sections and of
  malloc: ~4 % of busy samples, minus what is Renut's own locking (idea 15) and FFmpeg's: ceiling ~3 %. Realistic
  1-1.5 %, more in the latency of the wake-ups.
- **Exactness:** the guest sees the same state transitions (SignalState values, auto/manual reset, semaphore limits,
  mutant ownership and recursion, WaitAll atomicity, return codes); wake order moves from the host condition
  variable's to FIFO, which is closer to the 360's. Verify by differential tests in sdk/tests: random operation
  sequences through the old and the new implementation, single-threaded (states and return values equal) and
  multi-threaded (invariants: no lost wake, no double acquire); then races on Ryujinx and the console.
- **Difficulty / risks:** 2-4 weeks. Objects the kernel creates on its own (not in guest memory) keep the old path;
  APCs and alertable waits; timeouts against the guest clock; objects freed and reused by the game while a waiter is
  parked (the parking lot must key on address and generation).
- **Scope:** universal (the SDK's kernel layer, every ReXGlue port).

### 3. A thread-caching allocator for the whole process

Newlib's malloc has one recursive lock (rmutexLock), and it shows twice: as busy samples in malloc/free (XMA Decoder
8.4 % of its samples, Audio Worker 16 %, TimerQueue, the render thread 0.6 %) and as the leaf of 531 sampled stacks,
most of them threads blocked on that lock. Replace malloc / free / memalign / operator new / delete with a per-thread-cache
allocator (rpmalloc- or mimalloc-style, over a large reserved block from the heap, size classes, thread-local free
lists with batched remote frees), and take the remaining hot allocations off the paths: the wait vectors of idea 2,
TimerQueue's per-timer nodes, FFmpeg's frames (a get_buffer2 from a pool instead of av_frame_unref / ff_get_buffer
through malloc).

- **Why on the A57:** the lock is a cache line every allocating thread on every core writes, through LL/SC pairs.
- **Ceiling / expected:** ~1.2 % busy; realistic 0.4-0.8 %, plus fewer stalls of the threads that wait on the lock.
- **Exactness:** host only; no guest semantics. Verify by long races with the memory governor's logs (footprint),
  Ryujinx runs, and the allocator's own debug checks in a test build.
- **Difficulty / risks:** 1-2 weeks. Footprint and fragmentation (docked memory is tight: the governor), alignment
  promises (memalign callers), thread exit with cached blocks, libnx / newlib internals that call `_malloc_r` with a
  reent pointer, and the `--wrap` rules of the SDK libraries in LTO.
- **Scope:** universal.

### 4. Per-thread store-card logs instead of one shared card table

Today a guest store outside the stack also writes 0 to its page's card (`strb wzr` into the first MB of the window);
the render thread sets cards back to 1 as it proves pages (PagesClean). With idea 39's card runs a copy marks a page
once per run, but every mark still writes a line that other cores also write. Instead, each guest thread appends the
page numbers of its runs to its own small log (a thread-private ring in host memory, de-duplicated by the run logic
that exists), published at the same points the card runs flush today (calls, fences, returns, CAS); the render thread
drains every thread's log into its page serials when it checks cards at a kick. Host writers (HLE, memcpy natives) keep
marking cards; PagesClean reads both.

- **Why on the A57:** 0.75 % of all samples sit on the card store itself: a store collects samples on this core only
  when the store buffer is full, which points at RFO misses on card lines that several cores write (64 cards per line
  cover 256 KB of guest memory, written by Main, SlRenderer, Model Instance, the anim and particle threads, and reset by
  the render thread).
- **Ceiling / expected:** 1.6 % (the mark and the instruction after it); realistic 0.3-0.7 %.
- **Exactness:** the render thread gets the same set of written pages, at the same synchronisation points as now (the
  card runs already defer marks to the flush points). A conditional mark (`if (card) card = 0`, HotSpot's
  UseCondCardMark) looks cheaper but races with the render thread's reset on a weakly ordered core: a mark skipped on a
  stale 0 loses a write. Verify with banjo_renut_store_cards_verify (every proven range hashed) on Ryujinx, then races.
- **Difficulty / risks:** ~2 weeks. Log overflow (fall back to marking the card), threads the render thread does not
  know (register at thread creation), the hand natives (convert them too, or leave them marking).
- **Scope:** universal (every port with store cards: banjo-nx's design). Different from moonshot 6 (MMU dirty
  tracking): no page protection, no faults.

### 5. A lock-free single-producer draw queue (POD records, no std::function, no per-draw mutex)

Each queued draw goes from SlRenderer (or Model Instance) to the render thread through render_thread::Push: a
`std::function` per item under a pthread mutex, a condition variable to wake the consumer, and the QueueCapture lambda
on the other side. Replace it with one SPSC ring per producer of fixed-size records (the DrawCapture pointer, the call,
the kind), a release store of the tail and an acquire load on the other side, and a wake only when the consumer is
parked (idea 2's address arbiter on a futex word).

- **Why on the A57:** SlRenderer spends 4.1 % of its samples in host sync, and the render thread 3.8 % in the
  QueueCapture handler; the mutex line and the queue's nodes move between cores 1 and 0/2 at ~1,000+ draws a frame.
- **Ceiling / expected:** ~1.5 %; realistic 0.4-0.8 %. (The address wait tried in lat4/lat5 replaced the sleep, not
  the per-item lock and closure.)
- **Exactness:** the same draws in the same order. Verify with the fast-draw verify mode and the frame hashes.
- **Difficulty / risks:** 1-2 weeks. Begin*Vertices draws are queued later than they are captured (the deferred
  chain's ordering under g_delta.mutex must survive); two producers (two drawing devices) need two rings merged in
  sequence order.
- **Scope:** every Renut port.

---

## B. Guest code generation (exact, guard-checked)

### 6. Guest atomics at the guest's own memory order

The generated code turns `lwarx; ...; stwcx.` into a plain load (`reserved`) and RexGuestCas, a strong
`__atomic_compare_exchange_n(..., SEQ_CST, SEQ_CST)`: on the A57 (no LSE) an `ldaxr / cmp / stlxr` loop with acquire
and release semantics, followed by the g_rex_atomic_legacy_barrier byte test (in n_82754EC0: `ldrb w1, [x27, #3936];
cbnz` after every `stlxr`) and preceded by a card store (REX_GUEST_CAS_C). 8,546 sites in the generated tree. The game's barriers are separate: `lwsync` (468 sites)
is `atomic_thread_fence(acq_rel)`, `sync` (33) seq_cst, both a `dmb ish`; the game has no `isync`. Proposal: relaxed
weak CAS (`ldxr / cmp / stxr`, one attempt: stwcx. may fail spuriously too, and the guest's own `bne` retries), the
lwarx value taken from that `ldxr` where the pattern is a recognised idiom (`lwarx; ALU; stwcx.; bne-`), the legacy
byte test compiled out in shipping (idea 12), barriers left exactly where the guest put them.

- **Why on the A57:** the samples sit on the instructions right after `ldaxr` / `stlxr` (1.59 % of all samples in the
  windows); an acquire load holds later loads and a release store waits for every earlier access, which on this
  memory-bound code means waiting for outstanding misses.
- **Ceiling / expected:** ~1.6 %; realistic 0.5-1 %.
- **Exactness:** the Power ISA orders nothing around lwarx / stwcx. beyond the one location; the guest's ordering comes
  only from its lwsync / sync, which keep their full `dmb ish`; ARMv8 is other-multi-copy-atomic, stronger than Power,
  so no guest-forbidden outcome becomes possible. The success condition (value unchanged) is today's. Verify with
  litmus tests compiled through the same macros (MP+lwsync, SB+sync, LB, 2+2W, IRIW, with and without the barriers),
  10^7 runs each on the console and in Ryujinx, forbidden outcomes 0; the guard's prefix compare of the atomic copies
  (idea 35); a census that every lwsync/sync still compiles to a `dmb`.
- **Difficulty / risks:** ~1 week. Host code that reads guest words written by guest atomics and relied, without
  saying so, on the CAS being a full barrier (audit the SDK's HLE readers: critical-section and XAudio fields).
- **Scope:** universal.

### 7. Flush-mode scheduling: group the VMX and FPU instructions, split loops by mode

flush_mode_flow.py and flush_hoist.py remove checks; nothing moves instructions. Within a straight-line block,
partition the statements into flush-on (VMX float), flush-off (FPU, including lfs / stfs, whose conversions see the
mode) and neutral (integer, address, vector integer and permutes), then list-schedule so that each mode's
statements are contiguous: k alternations become at most two switches. In loops whose body alternates (the water step
copy sub_828729E8 keeps three FPCR writes an iteration, abCC2), fission the loop into a VMX loop and an FPU loop when no
dependence cycle crosses the two (registers: trivial; guest memory: disjointness from the loop's address recurrences, or
a run-time overlap check that versions the loop), so the switches are two a loop instead of two an iteration. Keep the
cached mode word in a copy-local (like REX_R1_LOCAL) so the checks stop loading `ctx.fpscr` (the `ldr w1, [x0, #324]`
in the copies' prologues).

- **Why on the A57:** a toggling `msr fpcr` costs 44 ns (profile header), ~43,600 a frame; the windows are 1.86 % of
  all samples, concentrated in n_8260EAA8, the water step's native, n_8274F568, n_82610E10. Idea 1 of part 1 (any-mode
  forms) tried to make the minority side mode-free and lost in the water loop; this moves the code instead.
- **Ceiling / expected:** ~1.9 % plus the mode-word loads (~0.3 %); realistic 0.5-1 %.
- **Exactness:** FP operations do not touch memory, the port models no FPSCR sticky bits (only rounding and flush),
  exceptions are masked: reordering independent statements changes nothing observable. Do it in the copies' running
  form only, so the guard (Ryujinx / PC, original statements in order) compares it; count the toggles with the PC's
  flush-write census before and after.
- **Difficulty / risks:** 3-4 weeks (a dependence graph over the copies' text; loop fission needs the loop's induction
  recurrences, which loop_locals.py and the counted-loop rule already find). Register pressure grows when a mode's
  values are kept live longer; cap the motion distance.
- **Scope:** universal.

### 8. Software prefetch from address traces (stride and indirect, Ainsworth-Jones style)

Idea 52 put prefetches only after loop-carried self-loads (`p = p->next`: 240-252 sites). The census says 41.5 % of guest
samples are heap loads; many sit in loops of the form `for i: f(list[i])` (sub_8255AF18, 3.1 % of Main: `lwzx r3,
r11, r29` then a call that dereferences it) or strided walks over arrays of structures. Step 1: a trace mode in the
hooked PC build records (pc, ea) for the ~200 most-sampled loads of the console profile; a script classifies each
stream (constant stride, indirect through a strided index, chain, random) and measures the iteration time from the
samples. Step 2: localize_native.py inserts `REX_PREFETCH_GUEST` k iterations ahead: `prfm` on `base + stride*(i+k)`,
and for the indirect form a bounded load of `list[i+k]` (only when `i + k` is inside the loop's known count) followed by
a `prfm` on what it points at, plus its vtable word.

- **Why on the A57:** one load pipeline, a small out-of-order window that cannot cover a DRAM miss (~150-250 ns at 1600
  MHz memory, longer while the GPU-bound frame keeps DRAM busy), and a hardware prefetcher that follows strides but not
  indirections.
- **Ceiling / expected:** heap-load samples are ~30 % of process samples; if a third of those are misses in loops that
  can be predicted, ~5 %. Realistic 1-2 %.
- **Exactness:** `prfm` cannot fault and has no semantics; the extra index load stays inside the array the loop reads
  anyway. The guard is unaffected; the console A/B decides.
- **Difficulty / risks:** 3-5 weeks. Wrong distances waste load-port slots; loops with calls need the distance in
  calls, not instructions. User PMU access (Atmosphère's setting, the user's call) would rank the loads by real L2
  refills instead of by samples.
- **Scope:** universal tool; the traces are per game.

### 9. Callee side-effect summaries: reuse guest loads across calls

Every real call in a copy is a full barrier for guest memory: GCC cannot know what `__imp__sub_X(ctx, base)` writes,
so `this->field` loaded before the call is loaded again after it. A whole-program pass over the PPC code (Reach and
reg_liveness.py already walk the call graph) computes for each function the memory it may write: its own and its
callees' frames (r1-relative below the caller's r1), globals at known addresses (the lis / addi constants
ro_constants.py follows), "through pointer arguments", or "anything"; and whether it contains a sync, an atomic, a
kernel call or an indirect call. In a copy, a guest load after a call to a summarised callee whose write set provably
excludes the location (same base register, unchanged; a location outside the callee's sets) takes the value loaded
before the call.

- **Why on the A57:** the reload is another L1 access on the one load pipeline, and after a deep call often an L1
  miss; MSVC reloaded these values because it lacked the same whole-program knowledge.
- **Ceiling / expected:** a census first (reloads after calls of the same base register and displacement, weighted by
  the profile). Guess 1-3 %; realistic 0.5-1 %.
- **Exactness:** single-threaded the original and the copy load the same value (the guard compares them on Ryujinx /
  PC); with other threads, reading the earlier value is an interleaving the original also allowed, as long as the callee
  has no synchronisation (the summary's rule). A self-check like REX_STACK_FWD_VERIFY (the hooked build reloads and
  compares) catches an unsound summary.
- **Difficulty / risks:** 3-4 weeks. Stores through pointers the analysis cannot bound make most non-leaf callees
  "anything": the win is in leaf getters, math helpers and small utility calls, so measure the census first.
- **Scope:** universal. Narrower than moonshot 12 (the SSA lifter's alias scopes): no new IR, only summaries.

### 10. Frame-pointer-free copies, with CFI unwinding in the sampler

The generated game code is compiled with -fomit-frame-pointer (measured: -1.4 % instructions, -1.8 % loads, -1.7 %
stores), but the copies are compiled in the app target, which keeps the x29 chain: n_82754EC0 starts with
`stp x29, x30, [sp, #-160]!; mov x29, sp`, and the ELF's text from 0x400000 to 0x1400000 has 5,773 `mov x29, sp`. Compile the shards
(banjo_hot_shard_*.cpp, banjo_hot_guest.cpp) with -fomit-frame-pointer too, and give the stack sampler
(sdk/src/ui/switch_perf.cpp, which walks x29) an unwinder over .eh_frame (-fasynchronous-unwind-tables on those files),
so the profiles keep their caller chains.

- **Why on the A57:** x29 back as a callee-saved register in the functions that are 55 % of the samples and short of
  registers (8.4 % of guest samples are stack spills and fills), and two instructions less a non-leaf call.
- **Ceiling / expected:** the game code's measurement applied to the copies' share: ~0.8-1 %; realistic 0.4-0.8 %.
- **Exactness:** no semantic change. Check the sampler's chains against an x29 build on the same race.
- **Difficulty / risks:** 3 days for the flag, about a week for a robust unwinder (LTO / PGO hot-cold split parts,
  leaf functions, the 1 ms budget of the sampler).
- **Scope:** universal.

### 11. The guest window at a constant address: no base register, no extended add

Every guest access computes `base + (u64)(u32)r + d`: `add xN, x19, wM, uxtw` (or a `[x19, wM, uxtw]` addressing mode),
with `base` kept in a callee-saved register in every function and passed in x1 at every call (`mov x1, x19` before each
`bl`). If the 4 GB window sits at a virtual address that is a valid AArch64 logical immediate (a 4 GB-aligned single run
of ones, such as 0x10_0000_0000), `REX_ADDR_D` can be written `(u8*)(((u64)(u32)r) | K) + d`: one `orr` immediate,
nothing to keep in a register, nothing to pass. The address is chosen at start-up (a free, aligned range at one of a
few candidate addresses) and patched into the code where banjo_code_blocks already copies .text into heap memory before
it is mapped executable (the `orr` immediates written with a marker value at build time).

- **Why on the A57:** the optimisation guide gives arithmetic with an extended register two cycles on the single M
  pipeline, a logical immediate one cycle on either I pipeline (confirm with a microbenchmark in the profile header, as
  for the FPCR); on a pointer chase (`ldr; rev; add-uxtw; ldr`) that is a cycle of four extra; and one register more in
  every copy. `add x` alone is 3 % of guest samples.
- **Ceiling / expected:** ~1.5 %; realistic 0.3-0.8 %. Not moonshot 5 of part 1 (base pinned in a fixed register):
  here there is no register at all.
- **Exactness:** address arithmetic only (the dform split's wrap caveat is unchanged). The PC build keeps the register
  form.
- **Difficulty / risks:** 2-3 weeks. Horizon's address-space layout: svcMapMemory wants its destination in the alias
  region, whose base is randomised, so a fixed VA may not be free in every launch (needs a fall-back chosen at start,
  hence the patching); patching code bytes before mapping them executable; check_switch_build.py needs a rule for the
  marker.
- **Scope:** universal (the pch's macros and the SDK's window set-up).

### 12. Exact vectorisation of scalar FPU loops across iterations (lane = iteration)

GCC cannot vectorise the guest's scalar float loops (big-endian loads, ctx / CR plumbing, unknown aliasing). A copy-level
pass recognises loops whose iterations are independent (different output addresses by the induction variable, no
loop-carried float register) and rewrites them so that each NEON lane runs one iteration with the same operations in
the same order: `fadds` / `fmuls` as `.4s` single operations (exact, the single_floats.py argument), `fmadd` / `fmadds`
as `.2d` fused `fmla` then `fcvtn` (the same double rounding), loads as `ld1` + `rev32` or gathers, a run-time overlap
check against the loop's stores, a scalar tail.

- **Why on the A57:** two F pipelines that the scalar code uses one lane of; fewer load-pipeline operations for
  contiguous fields.
- **Candidates:** SlAnimManager (n_8260EAA8, n_82610E10, n_82610588: two thirds of an 8.3 % thread; per-bone work is
  independent), AK's single multiply-add chains (n_827168E0, declined as a hand native because the double rounding is the
  arithmetic: this keeps it and widens it), particles (n_8275D5B8, n_8275E3D0). A census of qualifying loops comes first.
- **Ceiling / expected:** ~2 %; realistic 0.3-0.8 % (structure loads are several micro-ops on this core, which eats
  into the gain).
- **Exactness:** element-wise the same IEEE operations under the same FPCR (FZ off for FPU code), the same NaN rules
  in vector and scalar AArch64 (default-NaN off). Unit tests per rewritten loop against the scalar copy on random and
  edge inputs (as fp_fused_any_mode_test), then the guard.
- **Difficulty / risks:** 6-8 weeks. Few loops may qualify; the any-mode and flush-mode plumbing inside them.
- **Scope:** universal tool.

### 13. SMT-verified superoptimisation of the hottest guest idioms

The 360 compiler's idioms (rlwinm / rlwimi bit fields, cntlzw booleans, CR logic and mfcr / mtcrf, carry chains, sign
extensions, `xer.ca` materialisation) are emitted as literal C++, and GCC does not always see through them. Take the
hottest 3-8 instruction windows of the copies' ARM code (sampled), map them back to their PPC sequences, and search
shorter AArch64 forms for the PPC sequence (enumerative search up to ~4 instructions, equivalence proven by an SMT
solver over all 2^64 inputs, as Souper / Alive2 do), emitted as REX_ macros by a post-codegen pass.

- **Why on the A57:** integer ALU and moves are 14 % of guest samples; a register move takes an issue slot and a
  cycle here (no zero-latency move elimination that the optimisation guide documents), and multi-cycle integer work
  shares one M pipeline.
- **Ceiling / expected:** ~1 %; realistic 0.3-0.6 %.
- **Exactness:** every rule proven equivalent by the solver; unit tests on edge values in sdk/tests; the guard sees only
  rewrites applied to the copies' running form.
- **Difficulty / risks:** 3-4 weeks. The gain may sit in register moves the allocator makes, which no idiom rule
  reaches.
- **Scope:** universal (the rules are about the PPC compiler's output, not the game).

---

## C. The memory system

### 14. A run-ahead helper thread on the system core (prefetching p-slices)

Core 3 runs the XMA Decoder and the system and is idle about half the time. A helper thread there runs, a little
ahead of the main thread, only the address-generating slice of its hottest traversals (the scene and object walks of
n_82754EC0, n_825E0F28, sub_8255AF18's list): the loads that produce pointers, nothing that stores, every pointer
range-checked against the guest heap's mapped ranges before it is followed. Its loads warm the shared L2 for the main
thread. It is triggered at the start of each traversal (a per-frame sequence number in host memory) and gives up after
a fixed budget.

- **Why on the A57:** a shared 16-way 2 MB L2 that all four cores fill and read; an idle core; DRAM misses the main
  thread cannot overlap by itself (pointer chases).
- **Ceiling / expected:** Main's heap-load samples are ~40 % of 22 ms; if half are DRAM misses and the helper hides a
  quarter of them: ~1-2 ms (1.5-2.5 %). Realistic 0.5-1 %.
- **Exactness:** the helper only reads guest memory and writes nothing guest-visible; a slice that runs wrong just
  prefetches useless lines. No guard needed; A/B on the console.
- **Difficulty / risks:** 6-8 weeks (slices extracted from the copies' text by a tool). The system core is shared with
  the OS (the P5/P6 lessons: lowest priority, strict budget); reading freed or remapped memory needs the range check or
  the SDK's fault handler; L2 pollution if the helper runs too far ahead.
- **Scope:** universal mechanism, per-game slices.

### 15. Host streams out of the shared L2, and per-thread L1 colouring

The upload ring is written at 64-70 MB a second (armDCacheClean 778-1,117 calls, 14-20 ms a second) and cleaned with
`dc cvac`, which leaves the lines valid in the L2 (banjo-nx's choice, to keep them for the ring's next pass): about 2.3 MB
a frame, the size of the whole L2, plus ConvertVertices' reads of guest vertex data and the capture copies. Measure,
then pick per stream: write-once streams (converted vertices, pushed constants) into a CpuUncached (write-combining)
block, with the CPU-side shadows the compares need; or `dc civac` at publish so the lines leave the L2; non-temporal
loads (`ldnp`, `prfm pldl1strm`) for the vertex reads. Also colour the per-thread hot regions: host stacks come from a
pool of 16 MB stacks (MB-aligned tops), guest stacks are page-aligned, the context is 64-byte aligned inside
ThreadState: in a 2-way 32 KB L1D (16 KB a way) the tops of the guest and host stacks fall in the same sets; offset each
thread's tops by a per-thread colour.

- **Why on the A57:** 2-way L1D, one L2 for four cores; the game threads' heap loads (above) are what the render
  thread's streams evict.
- **Ceiling / expected:** 1-3 %; realistic 0.3-1 %. Whether the A57 honours the non-temporal hints and how write
  combining compares with cached writes plus a clean must be measured (banjo-nx measured the render thread only; the
  cost of the pollution shows on the other threads).
- **Exactness:** data unchanged (cache maintenance and memory types only; the GPU reads after its fence as now).
- **Difficulty / risks:** ~1 week. Reads from write-combining memory are very slow (every compare needs its shadow);
  `civac` may cost more than `cvac`. User PMU access would turn the guesswork into L2 refill counts per thread.
- **Scope:** universal (plume / Renut and the SDK's thread set-up).

---

## D. The renderer (host code)

### 16. The shipping configuration compiled in (partial evaluation of the keys)

Renut has 502 cvars, the app 754 in all; 287 are read as function-local `static const` (a guard-byte check at every
use) and the hot functions test latched globals: FastDrawLocked (42,340 bytes, 10,585 instructions, 14.6 % of the render
thread) has 532 `adrp` and 50 `adrp; ldrb; tbz/cbnz` key tests, and loads keys into stack slots it re-reads. Generate a
header from the shipping toml that makes every key the toml sets, and every key no premade test config changes, a
`constexpr`; GCC then folds the branches and drops the dead features, and the hot functions shrink (FastDrawLocked alone
is most of the 48 KB L1I). Keys a test config or the in-run A/B uses stay dynamic.

- **Why on the A57:** fewer instructions, fewer loads on the load pipeline, and code that fits the L1I.
- **Ceiling / expected:** the host renderer is ~21 % of samples; key tests and dead paths maybe 5 % of its
  instructions, plus the I-cache: ~1.5 %. Realistic 0.4-1 %. Also folds g_rex_atomic_legacy_barrier (idea 6) and the
  copies' keys.
- **Exactness:** the same behaviour for the shipping toml by construction; verify with fast-draw verify and frame
  hashes.
- **Difficulty / risks:** ~1 week. Conflicts with "one NRO, compare by config" for every frozen key: freeze only keys
  that are settled, and have the start-up log say which keys are frozen (a toml that sets one is reported).
- **Scope:** every Renut port.

### 17. Per-shader-record draw plans (partial evaluation of the per-draw interpreters)

The render thread interprets the same shader records again at every draw: which fetch slots the pair uses, which
constant lines to compare and push, which vertex elements to convert with which converter, the export, skin-once and
fur flags (FastDrawLocked, FillTextures, PushFloatConstants 4.3 %, PrepareGeometry, BindStreams, ConvertVertices 2.8 %,
GetStreamSource). At a pipeline key's first draw, compile a dense plan: the exact slot list, the constant line ranges,
the stream list with a converter function pointer per element, the flags pre-decided; the draw then runs the plan. For
the pairs that cover most draws (a census from the harvested shader set: 1,982 shaders), generate specialised C++ at
build time and compile it with PGO; the rest use the plan.

- **Why on the A57:** fewer branches and loads per draw, less code per draw in the L1I.
- **Ceiling / expected:** those functions are ~30 % of the render thread (~6 ms, ~7 % of process); a quarter of their
  work: ~2 %. Realistic 0.7-1.2 %.
- **Exactness:** a verify key runs both forms and compares the emitted command words per draw (as
  banjo_renut_fast_draw_verify does).
- **Difficulty / risks:** 4-6 weeks. Plans must be invalidated with what they assume (shader patching, recorded binds,
  memexport); a plan cache's own lookup must cost less than what it saves. Not banjo-nx's rejected cross-frame recording
  cache: a plan is keyed by content (the shader pair), not by the draw's place in the frame.
- **Scope:** every Renut port.

### 18. Draws processed in cohorts (the render thread inside the 48 KB L1I)

A draw passes through FastDrawLocked (42 KB) and some twenty helpers before the next draw starts, so the render
thread's hot code per draw is several times the L1I, and its profile is flat (FastDrawLocked's hottest 64-byte windows
hold 2-3 % of its 396 samples each in abCC2; banjo-nx found no line above 2 % in its own). Process the
draws of a kick in cohorts of 8-16, stage by stage: apply the cohort's deltas and snapshot what each draw consults,
then resolve geometry for all of them, then textures, then constants, then emit the commands in order. Each stage's
code stays in the L1I across the cohort, and stage n can prefetch the data stage n+1 reads for the next draws.

- **Why on the A57:** a 48 KB 3-way L1I and a shared L2 that also holds the data; the A57's front end stalls on every
  L1I miss.
- **Ceiling / expected:** if L1I refills are 15-20 % of the render thread, halving them is ~2 ms (2.5 % of process).
  Realistic 0.5-1.5 %. Measure first: user PMU L1I refills, or the cheap proxy of idea 16's smaller code.
- **Exactness:** the same commands in the same order. A cohort ends at anything one draw's resolution can change for a
  later one: a target change, a resolve, an EDRAM restore, a memexport, a kick. Verify with per-kick command hashes,
  cohorts on and off.
- **Difficulty / risks:** 4-6 weeks; the render thread's state is written by lookups as they go (memos, caches,
  evictions), and each needs to be safe to run ahead of the previous draw's emission.
- **Scope:** every Renut port.

---

## E. Toolchain and run-time compilation

### 19. Console-in-the-loop compiler autotuning

The flags are sa2-nx's and UnleashedRecomp-NX's choices for other code. This code is unusual: huge functions (copies of
6-13 KB, FastDrawLocked's 42 KB) that GCC's large-function limits keep from inlining further, 64+ live vector values,
`-mtune=cortex-a57`'s cost tables. Tune with the console in the loop: knobs that act after the profile is read keep the
PGO profile valid (IPA inline params, `large-function-insns` / `-growth`, `max-unrolled-insns`, `-fsched-pressure`,
`-fschedule-insns`, `-fira-region`, `-fira-loop-pressure`, `-flive-range-shrinkage`, `-falign-loops/-jumps/-functions`,
`-mtune=cortex-a72` and `generic-armv8-a` tables, `-moverride=tune=` fields), so each trial is an LTO link and one race;
a Bayesian or successive-halving search over 30-40 trials, paired race windows as the objective, per target
(sasrt_recomp, the shards, Renut).

- **Why on the A57:** GCC's scheduling and RA choices for this core were tuned on ordinary code, not on this.
- **Ceiling / expected:** 2-4 % (flag tuning on embedded cores reports 3-10 %); realistic 1-2 %.
- **Exactness:** only flags that keep the FP semantics (-ffp-contract=off, no -ffast-math family) and the port's rules
  (-mearly-ra=none); every winner gets the dense guard on Ryujinx and the PC checks, because the GCC precedent is real
  (-mearly-ra's miscompile).
- **Difficulty / risks:** 1-2 weeks of work and 2-3 days of machine and console time; run-to-run noise (±2 % on process
  CPU) needs pooled windows; a flag that changes early inlining invalidates the profile (cycle it).
- **Scope:** universal method; the winning set may be per game.

### 20. A copy-and-patch trace JIT over the AOT code (the long shot)

libnx can make JIT code memory (jitCreate) under Atmosphère. Record hot traces at run time (paths through several
functions, with the indirect targets and the guest values they meet), compile each trace by copy-and-patch: stencils
built at build time by GCC from the generator's own macros (so each PPC instruction's semantics are the AOT code's), holes
for constants, registers pinned by a trace-wide convention so that a trace keeps guest registers in host registers
across the calls it contains (what the cc stages can only do where the static call graph is closed), and guards on
every assumption: the indirect target, the value, the page (write-protected; a write deoptimises the trace before it
lands). Start with the call chains that carry the ctx samples at call boundaries.

- **Why on the A57:** ctx traffic is 13.7 % of guest samples and ~19 % of it sits at call boundaries; 45,146 functions
  are reached through pointers, which no static stage can join.
- **Ceiling / expected:** ~8 %; realistic 1-3 %, with a wide spread.
- **Exactness:** guards make the specialisations exact; the stencils make the instruction semantics the AOT's. Verify
  with the guard's machinery (trace and AOT run from the same inputs, registers and stores compared).
- **Difficulty / risks:** months. A second code generator to keep exact; trace compilation time on a busy console;
  deoptimisation in the middle of a trace; debugging JIT code with the console sampler.
- **Scope:** universal.

---

## Ranked (best expected value first: realistic capture against effort and risk)

| Rank | Idea | Realistic | Ceiling | Effort | Exact | Scope |
|---|---|---|---|---|---|---|
| 1 | 1. Pin Main XThread and SlRenderer (+1 priority) | 1.5-3 % | 5-6 % | days | yes (scheduling) | universal mechanism |
| 2 | 6. Guest atomics at the guest's own order | 0.5-1 % | 1.6 % | 1 week | yes (Power model) | universal |
| 3 | 10. Frame-pointer-free copies + CFI sampler | 0.4-0.8 % | 1 % | days | yes | universal |
| 4 | 19. Console-in-the-loop autotuning | 1-2 % | 2-4 % | 1-2 weeks + machine time | yes (FP-safe flags, guarded) | universal |
| 5 | 2. Dispatcher objects on the address arbiter | 1-1.5 % | 3 % | 2-4 weeks | yes (differential tests) | universal |
| 6 | 16. Shipping keys compiled in | 0.4-1 % | 1.5 % | 1 week | yes (shipping toml) | Renut ports |
| 7 | 8. Address-trace-guided prefetch | 1-2 % | 5 % | 3-5 weeks | yes (hints) | universal |
| 8 | 7. Flush-mode scheduling and loop fission | 0.5-1 % | 2.2 % | 3-4 weeks | yes (guarded) | universal |
| 9 | 17. Per-shader-record draw plans | 0.7-1.2 % | 2 % | 4-6 weeks | yes (verify key) | Renut ports |
| 10 | 3. Thread-caching allocator | 0.4-0.8 % | 1.2 % | 1-2 weeks | host only | universal |
| 11 | 5. Lock-free draw queue | 0.4-0.8 % | 1.5 % | 1-2 weeks | yes | Renut ports |
| 12 | 4. Per-thread store-card logs | 0.3-0.7 % | 1.6 % | 2 weeks | yes (cards verify) | universal |
| 13 | 18. Draws in cohorts (L1I) | 0.5-1.5 % | 2.5 % | 4-6 weeks | yes (command hashes) | Renut ports |
| 14 | 9. Callee side-effect summaries | 0.5-1 % | 1-3 % | 3-4 weeks | yes (guard + self-check) | universal |
| 15 | 15. Host streams out of the L2, L1 colouring | 0.3-1 % | 1-3 % | 1 week | yes | universal |
| 16 | 11. Guest window at a constant address | 0.3-0.8 % | 1.5 % | 2-3 weeks | yes | universal |
| 17 | 12. Lane = iteration vectorisation | 0.3-0.8 % | 2 % | 6-8 weeks | yes (unit tests + guard) | universal |
| 18 | 14. Run-ahead helper on core 3 | 0.5-1 % | 1.5-2.5 % | 6-8 weeks | yes (reads only) | universal mechanism |
| 19 | 13. SMT-verified idioms | 0.3-0.6 % | 1 % | 3-4 weeks | yes (proofs) | universal |
| 20 | 20. Copy-and-patch trace JIT | 1-3 % | 8 % | months | yes (guards) | universal |

The captures overlap (2, 3 and 5 share the lock costs; 16, 17 and 18 share the render thread's code; 8 and 14 share the
misses) and do not add up. Measurements that would sharpen most of them at once: user PMU access (L1I / L1D / L2 refills
and stall cycles per PC: the user's call), the census of idea 9, and a migrations-per-second line per thread.

Census scripts used (session scratchpad <scratchpad>,
not in tools/; each takes PROFILE MAP [ELF]): insn_class_census.py (samples by instruction class and the windows),
insn_ops.py (by opcode), insn_cards.py (card marks), cat_samples.py (busy samples by function kind), busy_callers.py and
callers_of.py (callers of the locks and malloc, from the stacks). Run on out/console_runs/abCC2/rex_profile_245.log with
out/nx-inplace/sasrt.map and sasrt.stripped.elf (the same build).

## Audit (2026-11-12)

An independent, read-only audit of the twenty ideas above (another agent; nothing else in the tree was changed). Evidence
is file:line in this repository unless another port is named; the machine code is out/nx-inplace/sasrt.stripped.elf and
sasrt.map (the abCC2 build of 19:31). Estimates are shares of process CPU (~80 ms a frame over four cores: 1 % is about
0.8 ms a frame). CONFIRMED / WRONG / UNVERIFIED refer to the doc's factual claims.

### Per-idea checks

**1. Pin Main XThread and SlRenderer.**
- CONFIRMED: the render thread is pinned (banjo_ring_core, app/src/renut_engine/gpu/banjo_renut_tuning.cpp:2148-2153);
  the XMA Decoder is alone on core 3 (app/sasrt_switch.toml:110); RexSwitchPinCurrentThreadToCore exists
  (sdk/src/core/threading_switch.cpp:348-373, the 0.24-migrations note at :341); multi-core masks lose core 3 in the
  wrap (threading_switch.cpp:481-490), so game threads run on 0x7; lat1 and lat3 as quoted
  (docs/render-thread-round-1109.md:621-624). UNVERIFIED: Main's preferred core -1 (no log read).
- WRONG: "it never pinned the game threads". The latency round pinned WaterThread to core 3 (lat1: stutters, vertex
  explosions) and runs P2/P5/P6 pinned Model Instance, the Wwise threads and the Audio Worker there (toml:110). The exact
  layout proposed (Main alone on core 0, the other game threads on 1-2) is sa2-nx's `sa2_renut_core_layout`, already
  wired here (app/src/renut_engine/gpu/d3d/hooks/device.cpp:897-918) but stubbed
  (app/src/renut_engine/sasrt_compat/sasrt_store_cards.cpp:5-8) because banjo-nx's Ryujinx runs hung the first Swap 4
  times in 12 (banjo-nx docs/renut-cpu-work-from-sa2.md:97-106); sa2-nx fixed the hang by having each thread apply its
  own mask at its next wait (sa2-nx docs/renut-renderer.md:416-422). Also, shipping already runs Model Instance at 0x3A
  (toml:420-421), so Main and SlRenderer at 0x3A are not "one step above the others", they tie with the recording
  worker.
- The mechanism is wrong. The ceiling extrapolates lat1's +4.1 ms for the un-pinned render thread, but that loss is not
  cache refills. Refilling a 32 KB L1D and a 48 KB L1I from the L2 costs about 10-25 us, so ten migrations a frame
  between Main and SlRenderer would be about 0.2 ms (0.3 %). The render thread lost scheduling, not cache: it runs at
  0x2C and preempts whatever it lands on. Pinning the game threads does not get that back.
- Exact: no guest semantics change, but timing does: late WaterThread vertex data (the lat1 explosions), audio
  starvation (P5), and with Main/SlRenderer above Model Instance a longer same-frame wait (lat10-13: Model Instance's
  boost was worth 0.7 ms a frame). Constraints: none broken.
- Estimate 0-0.5 %, 1-2 days (sa2-nx's self-applied layout plus a migrations counter); mechanism universal.

**2. Dispatcher objects on the address arbiter.**
- CONFIRMED: every native-object lookup takes the process-wide recursive mutex (sdk/src/system/xobject.cpp:514;
  sdk/src/system/util/object_table.cpp:279-290, whose kObjLookup / kObjBlocked counters are the 25,000 / 330 figures);
  the wait vectors are allocated (xobject.cpp:385; sdk/src/core/threading_posix.cpp:2058, and :2084 copies the vector
  again on every alertable retry; sdk/src/kernel/xboxkrnl/xboxkrnl_threading.cpp:876, 902). The `__dynamic_cast` is
  real but sits in rex::thread::Wait / SignalAndWait / WaitMultiple (threading_posix.cpp:1987, 2023-2024, 2061), not
  in GetNativeObject (a reinterpret_cast: sdk/include/rex/system/xobject.h:390-393).
- Partly WRONG: "waits on a host condition variable". Events already sleep on svcWaitForAddress
  (`thread_event_address_wait`, toml:288; sdk/src/core/address_event_core.h; threading_switch.cpp:661-669). Signals
  with no waiter make no syscall (`thread_signal_skip_idle`, toml:284). Critical sections take their owner from the
  PCR (toml:291). Semaphores and mutants still use the condition variable.
- WRONG, and it matters for the design: ArbitrationType_WaitIfLessThan and SignalType_SignalAndModifyByWaitingCountIfEqual
  (and ...IncrementIfEqual) compare or change the word as a host little-endian s32. On a big-endian SignalState only
  WaitIfEqual and plain Signal are byte-order-free. A semaphore count in the guest header therefore cannot use the
  kernel's counting forms: it needs either a host-endian shadow word (then the header is not the one authority) or
  equality-only waits with the count changed by a host CAS.
- New: the guest-authoritative header is new; the address-wait half is done for events. Exact: reachable with the
  differential tests proposed, plus the code Xenia's comment warns about (the XDK inlines some KeInitialize*:
  xobject.cpp:505-512) and objects freed and reused while a waiter is parked.
- Estimate: full 0.4-0.8 % in 3-5 weeks. The exact host-only part is 0.2-0.4 % in 2-4 days: static_cast, fixed arrays
  of 64 (MAXIMUM_WAIT_OBJECTS), and a lock-free header-to-object cache in place of the global spin. Universal (SDK).

**3. Thread-caching allocator.** CONFIRMED: newlib's malloc, not wrapped (sdk/cmake/rexglue_switch.cmake:80-85 has no
malloc wrap). UNVERIFIED: its single recursive lock (newlib/libnx's design, not checked in this tree), the 0.9 % and
the per-thread shares (profile). The wait vectors are hot allocations (see 2); TimerQueue and FFmpeg are UNVERIFIED.
New (no doc covers allocators). Host only, but the memory report reads `mallinfo` (app/src/renut_engine/gpu/backend/
memory_report.cpp, backend.cpp, surfaces.cpp; threading_switch.cpp:407), so a new allocator must report the same
figures or the governor goes blind; libnx thread blocks come from memalign(0x1000). Estimate 0.2-0.4 %, most of it from
taking the few hot allocations off their paths (2's arrays, an FFmpeg get_buffer2 pool) in days, not weeks.
Universal.

**4. Per-thread store-card logs.**
- CONFIRMED: a card is the byte at the page number in the window's first MB (app/generated/default/sasrt_pch.h:644-665;
  runs in app/src/cpu/banjo_hot_prelude.h:11-34); 64 cards a line (arithmetic); the render thread resets them, four
  views per physical page (app/src/renut_engine/gpu/render/draw.cpp:1872-1945).
- WRONG as argued: "a conditional mark races with the reset and loses a write". PagesClean stamps a page whose card it
  reads as 0 with the current interval, and a copy proven in that interval is hashed again in the next one
  (draw.cpp:1805-1811, 1937-1945). So a write whose mark was skipped on the 0 being consumed is caught by the same
  second hash that catches an unconditional mark landing just before the reset. Two conditions: the card must be read
  with a relaxed atomic load (not a plain load GCC may reuse), and the argument needs writing down. With that, it is the
  one-day experiment: while its cards are 0 the line stays Shared and no write forces an ownership transfer.
- The first measurement was never made: round 11-11's item 4 (a REX_STORE_CARDS_OFF CPU-only build) has no result in
  docs/. New (card runs, idea 39, are done: docs/machine-copies-deferred.md:51, 139). Exact as the doc says, plus thread
  exit (drain a log before its thread's records go).
- Estimate 0.2-0.5 %: the conditional mark in about a day plus a PGO cycle (the copies' CFG changes), the logs in about
  2 weeks. Universal to card ports.

**5. Lock-free draw queue.** CONFIRMED: a std::function per item under g_mutex
(app/src/renut_engine/gpu/backend/render_thread.cpp:107-111, 485-505). Missed: the consumer takes the whole queue
under one lock (a vector swap, :383-398), wakes are batched and skipped while the render thread is busy (:503-507), and
the one-pointer lambda is stored inline (no allocation). The render thread's 3.8 % "in the QueueCapture handler" is the
draw itself (overrides, DrawStateLocked: app/src/renut_engine/gpu/backend/queued.cpp:889-930), which no queue change
removes. Already tried in part (lat4/lat5). Estimate 0.05-0.2 %: drop (at most, push in small batches per lock).

**6. Guest atomics at the guest's own order.**
- CONFIRMED: RexGuestCas is SEQ_CST plus the legacy byte test (sasrt_pch.h:162-181); 8,546 sites; n_82754EC0 at
  0x705d4-0x705f4: `strb wzr` (the card), `ldaxr / cmp / stlxr / cbnz`, `ldrb w2, [x27, #3936]; cbnz`; lwsync (468) is
  an acq_rel fence; sync (33); no isync in the generated tree. Missed: eieio (56 sites) is a seq_cst fence too. Whole-ELF
  census: 8,444 `ldaxr w`, 8,501 `stlxr w`, 8,542 `dmb ish` (mostly the cold legacy-barrier stubs, one per site), 181
  `ldxr w`. lwarx is a plain load into `reserved` (e.g. sasrt_recomp.1*.cpp), so success is value equality (ABA) today
  and stays so. The doc's "idea 12" for compiling the byte test out means idea 16.
- The reasoning holds under the Power model. lwarx/stwcx. order nothing beyond their own location. The game's ordering
  comes from lwsync/sync/eieio, which stay `dmb ish`. That is stronger than lwsync (it also orders store-to-load) and
  cumulative on an other-multi-copy-atomic ARMv8. A single-attempt weak CAS fails spuriously only where stwcx. may
  too, and the guest's bne retries.
- One effect the doc does not mention: a relaxed CAS is no longer a compiler barrier for the plain guest accesses
  (REX_GUEST_VOLATILE is empty), so GCC may move ones it can prove disjoint (same base, other displacement) across it.
  Power hardware already allows the same reordering, and loop_barriers.py's header barrier (pch:153-160) still stops
  hoisting out of spin loops. A card mark may now become visible after the CAS store; PagesClean's interval protocol
  tolerates that (see 4).
- Concrete risks: (a) latent game races that the in-order Xenon tolerated in practice and today's acquire/release
  exclusives hide, exposed by the out-of-order A57 at 8,546 sites; they would be rare, nondeterministic and invisible
  to the single-threaded guard. (b) Host readers of guest words, as the doc says. (c) The "value from ldxr" form needs
  inline asm with the byte swap inside the exclusive pair and no memory access between ldxr and stxr.
- WRONG plan: litmus tests in Ryujinx prove nothing. Ryujinx runs on the user's x86-64 PC, so its guest accesses get
  x86's strong (TSO) ordering. Only the console can show ARM reorderings, and a short litmus NRO is not a guard run, so
  it is allowed there (coordinated with RR6).
- Gain: most samples after `stlxr` are probably the exclusive store waiting for its cache line (a coherence miss), which
  relaxed ordering does not remove. Estimate 0.1-0.5 %, about 1 week. Universal.

**7. Flush-mode scheduling.** CONFIRMED: no tool moves statements (flush_mode_flow.py and flush_hoist.py only remove
checks); the water step's three FPCR writes per iteration and 44 ns per toggle (docs/cpu-moonshots-1112.md); the
prologue's `ldr w1, [x0, #324]` (n_82754EC0 at 0x70568); no FPSCR sticky bits are modelled, only rounding and flush
(sdk/include/rex/ppc/context.h:195-260). New: part 1's idea 1 changed instruction forms instead and was reverted
(fp_mode_lookahead_run = 2, fp_fused_single_any_mode = false). Exact if calls, rounding-mode writes, CAS and fences are
barriers, and lfs/stfs/VMX memory operations moved across guest stores have alias proofs; loop fission is the hard,
memory-dependence part. Estimate 0.3-0.8 % (the windows were 1.77 % after CC2, mostly in four functions). Cheaper
first: hand-schedule those four (sub_828729E8/8286C230, n_8260EAA8, n_8274F568, n_82610E10), 2-4 days, guarded;
build the tool only if that pays. Universal.

**8. Trace-guided prefetch.** CONFIRMED: idea 52 put 240-252 prefetches only after loop-carried self-loads, and its
first rule (1,026 sites) had no lead time (docs/machine-copies-deferred.md:146-149, 279): the same distance problem
applies here. UNVERIFIED: sub_8255AF18's loop and the A57 prefetcher's behaviour. New (extends 52). Exact: prfm cannot
fault, but the bounded `list[i+k]` load can, so it must stay inside mapped guest memory. PMU access is the user's
call. PC traces need the console's heap layout, which may differ. Estimate 0.2-1 %, 3-5 weeks; universal tool.

**9. Callee side-effect summaries.** CONFIRMED in effect: even with LTO and ipa-modref every guest access is
`base + offset` through the base argument, so "writes through argument 1" covers the whole window. The tools named
exist (tools/reg_liveness.py, ro_constants.py). New (idea 60 is loop-invariant loads; idea 46's frozen globals were
unsound: docs/machine-copies-deferred.md:49). Exact as argued: reusing a load is a load satisfied early, which is
allowed with no fence between and no store by the same thread. Summaries must count hooks and imports (the memcpy
native, HLE writes) as "anything". Estimate 0.1-0.5 % until the census says more; the census takes 1-2 days.
Universal.

**10. Frame-pointer-free copies.** CONFIRMED: only sasrt_recomp gets -fomit-frame-pointer (app/CMakeLists.txt:543-548).
In place, the copies are compiled in the app target `sasrt` under the generated symbols (app/CMakeLists.txt:322-329).
n_82754EC0 starts `stp x29, x30, [sp, #-160]!; mov x29, sp` (ELF 0x70540). 885 of the 1,074 copies named in sasrt.map
set x29 in their first 12 instructions. The ELF has 18,336 `mov x29, sp` (5,773 in 0x400000-0x1400000, as the doc
says, though most copies sit below 0x400000). The sampler walks x29 (sdk/src/ui/switch_perf.cpp:17, 180, 1118). Minor:
it saves one instruction a non-leaf call, not two (x30 is still saved). New for the copies (game code: docs/
enhancements.md:839-845). Exact. Estimate 0.2-0.5 %, hours: one compile option on the shard sources and
banjo_hot_guest.cpp (and the hand natives). The PGO profile should stay valid, because the frame pointer is decided
after the profile is read; check the build log for coverage mismatches. The sampler's chains will end at copies, as
they end at game code today; an .eh_frame unwinder is needed only if the stack-based tools depend on those chains.
Universal to ports with copies.

**11. Guest window at a constant address.** CONFIRMED: REX_ADDR_D is `base + (u32)r + d` (sasrt_pch.h:694); code
blocks copy the text and remap it at the same address (sdk/src/ui/switch_code_blocks.cpp:9-35). UNVERIFIED by
microbenchmark: the guide's two cycles on M for an extended add. WRONG, and it decides the idea: the indexed form
`[x19, wN, uxtw]` (16.8 % of guest samples) is one instruction today and would become `orr` plus `ldr`, or need the
base in a register again. Also, code blocks do not run on the emulator (CodeStatic: switch_code_blocks.cpp:29-30), so
the patched code could not run in Ryujinx, where the guard runs. Estimate -0.3 to +0.3 %: drop.

**12. Lane = iteration vectorisation.** CONFIRMED in principle: double rounding is harmless for + - * /; the port's
fmadds (a fused double, then rounding to single) is the same operation in `.2d`; AArch64 scalar and Advanced SIMD share
FPCR.FZ/DN. But the named SlAnimManager functions are the top FPCR-switch sites, so they already mix VMX and FPU code;
`.2d` halves the width; the A57 has no gathers. Estimate 0-0.3 %, 6-8 weeks: drop, unless a census finds qualifying
loops holding 2 % of samples or more.

**13. SMT-verified idioms.** CONFIRMED: the A57 has no move elimination. The 6.4 % of "moves" include fmov, tbl and
dup, not only register copies, and the gain sits mostly in register-allocator moves and LTO-inlined code, which rules
on PPC windows do not reach. Estimate 0-0.2 %: drop.

**14. Run-ahead helper on core 3.** CONFIRMED that core 3 was about half idle on 11-10, but it now also runs the
shader compiles, prebuild workers and ring cleaner (toml:113; app/src/renut_engine/gpu/backend/video.cpp:584-603). Its
record: Model Instance there cost 2 fps (P2), the audio threads went silent (P5) (toml:110). In the latency round the
user did not choose "11 (helpers on core 3)". Exact only if the helper never reads an unmapped or MMIO-backed guest
page (a real fault). Estimate -0.5 to +0.5 %, 6-8 weeks: drop.

**15. Host streams and L1 colouring.** CONFIRMED: the ring is cleaned with `dc cvac` by design
(app/thirdparty/plume/plume_deko3d.cpp:598-602). Missed: write-combined memory was already measured and rejected (the
A57 wrote 5,251 MB/s cached against 2,506 write-combined: banjo_renut_tuning.cpp:657-662), and the clean already runs on
core 3 (video.cpp:584-603). WRONG: "16 MB stacks": shipping is `switch_guest_stack_mb = 4` (toml:125). Not established:
"the tops fall in the same sets". The A57's L1D is physically indexed (TRM), so with 4 KB pages a virtual offset fixes
only set bits 6-11; the claim holds only if the heap is mapped in 2 MB blocks. PPCContext is alignas(0x40)
(context.h:284). Estimate 0-0.4 %. Keep two cheap A/Bs: `civac` instead of `cvac` in the cleaner and in unmap, and a
per-thread 0-15 KB offset of the host stack top. Drop the rest.

**16. The shipping keys compiled in.** CONFIRMED: 502 cvars in Renut (751 in app/src); REXCVAR_GET returns a
function-local static (sdk/include/rex/cvar.h:343, 356-360); 293 `static const ... = REXCVAR_GET` reads in app/src and
sdk/src. There are 225 `ldarb` in the whole ELF, so guard-byte checks are fewer than the doc implies. UNVERIFIED:
FastDrawLocked's size and adrp counts (a local symbol, absent from sasrt.map). PGO already moves dead features' blocks
to .text.unlikely, so the L1I part is smaller than claimed. Constraint: "one NRO, compare by config", as the doc says.
Estimate 0.2-0.5 %, about a week: later, settled keys only, with the frozen keys logged.

**17. Per-shader-record draw plans.** Overlaps the renderer's many memos and skips: banjo_renut_pipeline_memo,
_chain_reuse, _convert_reuse, _fetch_slots_skip, _texture_slot_skip, sasrt_cpu_ring_identity_memo and
sasrt_cpu_ring_bound_plan_memo (toml:262-265). FastDrawLocked is itself banjo-nx's epoch-skipping fast path. Failure
mode: a plan not invalidated by shader patching or a recorded bind gives wrong constants, i.e. wrong pixels (the
verify key catches it on the PC). Estimate 0.3-0.8 %, 4-6 weeks: defer.

**18. Draws in cohorts.** No L1I evidence: a flat profile is also what a data-bound function looks like. Every memo,
cache and eviction must be safe to run ahead (an eviction for draw i+1 while draw i still needs the resource).
Estimate 0-1 %, 4-6 weeks: defer until PMU L1I refills (the user's call) or idea 16's smaller code show a need.

**19. Console-in-the-loop autotuning.** Each trial is a -Final PGO + LTO build (about an hour: docs/pgo-lto.md) on the
user's shared, busy PC, plus console races with a same-session control (the console ran 2.5 % slower after a reboot:
the cc-moonshot notes). With ±2 % noise against a 1-2 % target, each trial needs several races. CONFIRMED: the
-mearly-ra precedent (docs/enhancements.md:1063-1100). Rework into 5-8 hand-picked trials (inline and large-function
limits for the copies' files, -fsched-pressure, -falign-loops), each guarded. Estimate 0.3-1 %.

**20. Copy-and-patch trace JIT.** Months of work, and a second code generator to keep exact. ctx at call boundaries is
only ~19 % of the ctx samples (about 1.5 % of process), which is the target. Drop for now.

### Verdicts and corrected estimates

| # | Idea | Verdict | Doc's realistic | Audit's realistic | Effort | Reason |
|---|---|---|---|---|---|---|
| 1 | Pin Main + SlRenderer | rework | 1.5-3 % | 0-0.5 % | 1-2 days | sa2-nx's layout, stubbed here; migrations are cheap; measure them first, no new priority step (lat3; Model Instance is already 0x3A) |
| 2 | Dispatchers on the arbiter | rework | 1-1.5 % | 0.2-0.4 % (host part), 0.4-0.8 % (full) | 2-4 days / 3-5 weeks | events already wait on addresses; counting arbitration types break on big-endian words; do RTTI, vectors and a lock-free lookup first |
| 3 | Thread-caching allocator | rework | 0.4-0.8 % | 0.2-0.4 % | days | take the hot allocations off their paths; a new malloc must keep mallinfo's figures |
| 4 | Per-thread card logs | rework | 0.3-0.7 % | 0.2-0.5 % | 1 day + a cycle / 2 weeks | measure cards off first; the conditional mark is not ruled out by the protocol |
| 5 | Lock-free draw queue | drop | 0.4-0.8 % | 0.05-0.2 % | - | already batched; the 3.8 % is the draw's own work |
| 6 | Guest atomics relaxed | keep, gated | 0.5-1 % | 0.1-0.5 % | 1 week | exact under the Power model; gain unproven; microbenchmark first; litmus on the console only |
| 7 | Flush-mode scheduling | rework | 0.5-1 % | 0.3-0.8 % | 2-4 days by hand | four functions hold the windows; hand-schedule them, build the tool later |
| 8 | Trace-guided prefetch | keep, later | 1-2 % | 0.2-1 % | 3-5 weeks | plausible; needs lead-time tracing and ideally PMU |
| 9 | Callee summaries | keep, census first | 0.5-1 % | 0.1-0.5 % | 1-2 days (census) | build only if reloads after leaf calls carry samples |
| 10 | Frame-pointer-free copies | keep, first | 0.4-0.8 % | 0.2-0.5 % | hours | the cheapest exact item; the profile stays valid |
| 11 | Constant window address | drop | 0.3-0.8 % | -0.3 to +0.3 % | - | the one-instruction indexed form becomes two; no emulator path |
| 12 | Lane = iteration | drop | 0.3-0.8 % | 0-0.3 % | - | few loops; the candidates mix VMX and FPU modes |
| 13 | SMT idioms | drop | 0.3-0.6 % | 0-0.2 % | - | the moves come from the register allocator |
| 14 | Run-ahead helper | drop | 0.5-1 % | -0.5 to +0.5 % | - | core 3's record (P2, P5); the user did not pick helpers on core 3 |
| 15 | Streams, colouring | rework | 0.3-1 % | 0-0.4 % | 1-2 days | two cheap A/Bs; write-combined already measured and rejected |
| 16 | Keys compiled in | keep, later | 0.4-1 % | 0.2-0.5 % | 1 week | PGO already splits cold code; settled keys only (compare by config) |
| 17 | Draw plans | defer | 0.7-1.2 % | 0.3-0.8 % | 4-6 weeks | overlaps the existing memos |
| 18 | Cohorts | defer | 0.5-1.5 % | 0-1 % | 4-6 weeks | no L1I evidence |
| 19 | Autotuning | rework | 1-2 % | 0.3-1 % | 5-8 trials | noise against one-hour LTO trials on a shared PC |
| 20 | Trace JIT | drop | 1-3 % | - | months | - |

Everything kept or reworked, done, is about 2-4 % of process CPU (overlaps not added twice). The doc's figures would
give more than twice that.

### The top 5 to try first, in order

1. **Idea 10, frame-pointer-free copies.** First step: give the copy sources (app/src/cpu/banjo_hot_shard_*.cpp,
   banjo_hot_guest.cpp, the hand natives) `-fomit-frame-pointer` through a per-source compile option. Rebuild with
   `pgo_cycle.ps1 -InPlace -Step use` on the current pgo-inplace profile, check for coverage mismatches, count
   `mov x29, sp` in the copies (885 of 1,074 now), then A/B against a same-session control.
2. **Idea 2, the host-only part.** First step: use static_cast<PosixWaitHandle*> (the only WaitHandle on POSIX) in
   threading_posix.cpp:1987/2023/2061, fixed arrays of 64 instead of the vectors (xobject.cpp:385,
   threading_posix.cpp:2058/2084, xboxkrnl_threading.cpp:876/902), then a lock-free header-to-object cache so that
   GetNativeObject skips the global spin (xobject.cpp:514). Watch kObjLookup / kObjBlocked in the 10 s report; guard
   and races as usual. Universal: hand it to RR6.
3. **Idea 4, measured first.** First step: the REX_STORE_CARDS_OFF CPU-only build planned on 11-11 (game threads' CPU
   with and without cards, ignoring the render thread). If the game threads gain 1 % or more, put the conditional mark
   in the copies' REX_CARD / REX_CARD_FLUSH (banjo_hot_prelude.h: a relaxed atomic load, store only when non-zero) and
   run banjo_renut_store_cards_verify on the PC. Build the per-thread logs only if both say so.
4. **Idea 7, by hand.** First step: the PC's flush-write census (kCensusFlushWrite) for each of sub_828729E8 / 8286C230,
   n_8260EAA8, n_8274F568 and n_82610E10, in writes per call. Then hand-schedule the water step's loop so each mode's
   statements are contiguous (exact: same operations in each mode, guarded on Ryujinx).
5. **Idea 6, gated by a microbenchmark.** First step: time an exclusive pair in the profile header, as was done for the
   FPCR: `ldaxr/stlxr` against `ldxr/stxr` on an L1-resident line, with and without outstanding misses. In the same
   build, compile out the legacy byte test (a settled key). Go to the relaxed CAS only if the pair saves about 10 ns or
   more under misses, and run the litmus tests on the console only.

In the same batch, as measurements only: idea 1's migrations-per-second line (RexSwitchCurrentCore at each wait
return), idea 15's `civac` A/B and stack-top colour, idea 9's reload census, and a malloc callers census for idea 3.

### Where the author was wrong in a way that matters

- **Idea 1 (ranked first).** It misses the existing layout and its history (sa2-nx's `sa2_renut_core_layout`, stubbed
  here after banjo-nx's Ryujinx hangs). Its gain rests on a mechanism (cache refills after migrations) worth about
  0.3 %, and its priority step was measured with no gain (lat3) and would tie with the shipping Model Instance boost.
  The first slot of the ranking went to the idea with the weakest evidence.
- **Idea 2.** The arbiter's counting forms do not work on big-endian guest words, and the event address waits are
  already shipped.
- **Idea 4.** It rules out the conditional card mark with a race the interval protocol already covers, which pushes a
  one-day experiment towards a two-week redesign. The cards-off measurement planned on 11-11 should come first.
- **Idea 5.** It counts the draw's own work (QueueCapture's body) as queue overhead; the queue is already batched.
- **Idea 6.** Litmus tests in Ryujinx cannot show ARM reorderings (the host is x86 with TSO). eieio is missing from the
  fence count. The gain assumes the stall after stlxr comes from ordering rather than from the exclusive store's
  coherence miss.
- **Idea 11.** The most common addressing form gets longer, and the patched code cannot run on the emulator.
- **Idea 15.** Write-combined memory was already measured and rejected; the stacks are 4 MB, not 16 MB; the L1D is
  physically indexed.
- Process: the census scripts behind every figure in the doc (insn_class_census.py, insn_ops.py, insn_cards.py,
  cat_samples.py, busy_callers.py, callers_of.py) exist only in the session scratchpad. Copy them into tools/ before
  the session ends, or the figures cannot be reproduced.

## Progress on the top 5 (2026-11-12 / 13)

- **1, frame-pointer-free copies: done, in cycle B** (app/CMakeLists.txt, inside SASRT_SWITCH_OMIT_FRAME_POINTER: the
  SASRT_HOT_SOURCES get `-fomit-frame-pointer`). The copies lose their x29 frame (825E0F28: 0x1200 -> 0x11c0 bytes, the
  same body). Cycle B measured 1.4 % slower than the A control, but the cause was its profile, not the flag: the
  training folder (a reused name, pgotrain_B) still held an 11-11 stream from another build, both were merged, gcov-tool
  skipped 383 functions on cfg_checksum mismatches and about 90 copies lost GCC's hot status (628 -> 536 in .text.hot).
  tools/pgo_merge.py now stops on more than one stream and on a stream older than the instrumented NRO. Kept; measured
  again in cycle C.
- **2, the host wait functions: (a) and (b) done, for cycle C.** WaitHandle::posix_wait_impl() instead of the
  __dynamic_cast cross-cast in Wait / SignalAndWait / WaitMultiple; WaitMultiple's per-thread buffers (no heap vector
  per call, no copy per alertable retry). Same results (a handle with no POSIX wait handle still gives kFailed). (c), the
  lock-free object cache for GetNativeObject: parked. Cycle B's race does 17-25 K ObjectTable lookups a second, 1.5 %
  contended (250-410 a second), about 0.1-0.4 % of one core in all.
- **3, the store-cards-off ceiling build:** not started; the audit's estimate for what it could unlock (the conditional
  mark) is 0.2-0.5 %, and a fair ceiling needs two builds without PGO (cards off changes every copy's CFG, so a PGO
  build would lose the copies' profile). Behind the cycles.
- **4, the flush functions by hand:** sized only. The water step's loop (n_828729E8) enables flush mode twice an
  iteration, around its calls of the hand natives n_82872180 and n_8286C230 (app/src/cpu/hot/banjo_hand_natives.h),
  which already compute in whichever mode they are called in and switch only when needed. What is left needs the PC's
  per-function flush-write census before any hand scheduling.
- **5, the exclusive-pair timing:** in cycle C's profile header (relaxed ldxr/stxr against ldaxr/stlxr, cache-resident).

## Next: Blur's CG-13 as an A/B (cycle D, 2026-11-13)

Blur (docs/codegen-ideas-3.md CG-13, base port 123, off there by default) runs all guest float code in the flush mode:
no `msr fpcr` after a thread's first, the any-mode helpers as plain operations. NOT bit-exact (the Xenon's scalar FPU
keeps denormals; Blur's PC census: 1,300-3,700 any-mode cold paths and 2,800-6,900 FPU regions with a denormal a
second). Blur's console ABBA: +4.6 % fps (22.10 against 21.13, CPU-bound), CPU 155 -> 147 ms a frame. It makes
idea 1 (the lookahead) moot, so it goes first. Ported as a switch, default OFF: CMake SASRT_FPCR_ONE_MODE
(scratchpad cg13_port.py: rex/ppc/context.h, rex/ppc/diet_ops.h, app/CMakeLists.txt), built with
`pgo_cycle.ps1 -OneMode` in its own folders (out\nx-onemode-gen, out\nx-onemode) and profile (pgo-onemode/), so the
cycle C build and profile stay as they are. Measured against cycle C in the same session; shipping it is the user's
call (not exact).
Sized on cycle C's race (tools/census_1112/insn_class_census.py, c1113_C rex_profile_256, 14,161 samples): guest
`msr fpcr` + the next 2 instructions = 2.05 % of all samples (the write itself 85 samples); guest atomic / barrier
windows 1.96 %, host 2.80 % (libnx mutexLock / mutexUnlock 163, RtlEnter / LeaveCriticalSection 94). CG-13 takes the
first (all but a thread's first switch) and the any-mode helpers' denormal checks: about 2-3 % of process CPU expected.
