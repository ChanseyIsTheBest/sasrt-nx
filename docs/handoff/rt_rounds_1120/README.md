# SASRT render-thread rounds 2-4 (2026-11-20): handoff for Banjo (the user: "Send all the render thread improvements to banjo please")

Three rounds of render-thread work on SASRT's Renut (deko3d) renderer, measured on the console in four-player split
screen at the user's clocks (1020 / 460.8 / 1600). Every item is pixel-identical (the same answers from the same inputs)
and has its own key; the code carries the key's name in a `sasrt-nx (2026-11-20, <key>; ...)` comment at each change,
so `grep -n "sasrt_rt2_\|sasrt_rt3_\|sasrt_rt4_"` finds them all.

- `files/` — the current SASRT sources the rounds touched (whole files; diff them against Banjo's, the comments mark
  SASRT's changes): render/draw.cpp, render/textures.cpp, render/surfaces.{cpp,h}, guest/command_buffers.{cpp,h},
  backend/render_thread.cpp, sasrt_gpu_round.{h,cpp} (the keys, A/B numbers 339-364, groups 400-403),
  banjo_renut_tuning.cpp, stage_census.h, host_batch.h, app/cmake/sasrt_renut_gpu.cmake, and the SDK's xmemory.{h,cpp}
  (one counter, below).
- `scripts/` — the patch scripts most items were applied with (old text -> new text, asserted unique; a few round-2 items
  were edited by hand, so the files are the reference), plus the measuring tools (split_race.py, still_ab.py,
  cmp_runs.py, rt_funcs.py, rt_pcs.py).
- `render-thread-ideas-1120.md` — the full record: the three 35-idea tables, what each became, every A/B.

## The headline, and the trap

**Standing still in 4P (four players on the start line, no input: the user's method), the build with rounds 2-4 against
the user's 11-19 build, bracketed (two runs of the old build around the new): render thread -12 % a frame, -10 % a draw,
fps 15.5 -> 16.7, GPU unchanged** — but only after a fresh PGO cycle. The first build with the rounds was *3.7 % slower*
than the old one: the PGO profile was trained on the old code, and with `-Wno-coverage-mismatch` GCC compiles every
function changed since with **no profile at all** (no hot/cold split, no branch weights) — and these rounds change the
hottest functions there are (FastDrawLocked, DrawStateLocked, PushFloatConstants, FillTextures, Replay). In-run A/Bs
cannot see this (both halves are the same binary). **Run a PGO cycle after porting any of this, before judging it.**

## Measuring

- Driving A/Bs are useless for 1 % items: one pair of halves is +-3-5 % (a no-op item "measured" -2 to -3 %).
- **Standing still** (scripts/split_race.py with `SPLIT_STILL=1 SPLIT_NO_SHOTS=1`; 5-6 s halves): +-1-2 % a pair;
  scripts/still_ab.py pairs halves of similar draw counts (within 10 %) and gives mean +- standard error per item.
- Whole builds: two still runs of A around one of B (scripts/cmp_runs.py on the 10 s lines), same clocks.

## The items

Rounds measured as groups (still, in-run): rounds 1-4 together -8 % a draw, rounds 2-4 -6 to -7.5 %, rounds 3-4 -5 %,
round 4 -2 to -3 %. Item by item they are mostly within noise; the group is the reliable number.

### Round 2 (A/B 339-351, keys `sasrt_rt2_*`) — the solid part (-2.8 % render thread in a 4P A/B on its own)

| key | where | what | for Banjo |
|---|---|---|---|
| slot_index | textures.cpp FindHostTextureBySlotLocked | a 256-entry memo by slot, each answer checked as the walk checks it (was one entry) | yes |
| spec_memo | draw.cpp SasrtSpecAnswersOf | the fast draw's FetchSpecWords / plain-fetch / clip / spec words kept while no shared-constant line, shader, target, instancing, sampler table or A/B half changed (verify under banjo_renut_fast_draw_verify) | yes where the spec words exist (banjo_gpu_fetch_spec + SASRT's spec words) |
| drop_throttle | draw.cpp DropReplacedRanges | over the stream cache's limit, every 4th frame (memory only) | yes |
| pages_tail | draw.cpp PagesClean | a range's last 1-7 pages in one masked NEON block | yes |
| color_alias_memo | surfaces.cpp ColorAliasesLocked | the list kept per surface until a target is built or retired (g_sasrt_table_epoch) | where the EDRAM depth restore is on |
| repeat_recorded_index | draw.cpp WholeRepeatHit | reads the replay's recorded index buffer (ReplayIndexBuffer) as WholeGeometryTry does; a correctness fix too | yes |
| held_export_bitmap | draw.cpp GetStreamSource | kept exports looked up only where a 64 KB granule bitmap says one may lie | memexport games |
| place_wait_unlocked | command_buffers.cpp QueueCapturedRunSlot | the same-frame place's wait lets go of State().mutex | split-screen places only (SASRT) |
| ring_prefetch | render_thread.cpp | the next ring item's narrowed delta prefetched to six lines | yes |
| readable_memo | draw.cpp GuestBytesReadable | 64 readable ranges kept while `rex::memory::g_page_access_generation` is unchanged — **SDK change**: xmemory.{h,cpp} raise it in Decommit, Release, Protect, Reset, Restore and AllocFixed without read access | yes (needs the SDK counter) |
| bind_layout_narrow | draw.cpp fast path | a layout change elsewhere rebinds the fast draw's targets only when its own left their bind layouts | measured no effect |
| texture_memo_two_way | draw.cpp TextureMemoSlot | 2,048 sets of two ways (same 4,096 entries), the older frame's way replaced | yes |
| repeat_ring | draw.cpp WholeGeometryTry | the repeat answer kept for the last four meshes of a kick | yes |

Also in round 2 (no key): `-fno-threadsafe-statics` for draw.cpp, command_buffers.cpp, ultimate.cpp, render_thread.cpp,
banjo_renut_tuning.cpp (app/cmake/sasrt_renut_gpu.cmake: every function-local static was a guard check); census::On
and host_batch CensusOn/VerifyOn latched inline (stage_census.h, host_batch.h); AbTargets under std::call_once.

### Round 3 (A/B 352-356, `sasrt_rt3_*`) — 402 as a group about neutral, except host packets in split screen

| key | where | what | for Banjo |
|---|---|---|---|
| words_owner_table | textures.cpp SasrtWordsViewOwnerLocked | the restore copy's words-view owner, a 256-entry table by slot | SASRT's restore only |
| surface_memo_256 | surfaces.cpp GetHostSurfaceLocked | the memo 256 entries (index >> 24), not 64 | yes |
| depth_bias_fields | draw.cpp fast path | no SetDrawDepthBias when the bias is bound and its packets' fields are unchanged | yes |
| place_spin | command_buffers.cpp (+ `sasrt_rt3_place_spin_us`, 400) | the place wait spins on the slot's new `ready` flag before sleeping | split-screen places only |
| host_packets_split | draw.cpp HostPacketsOn, command_buffers.cpp | host packets (banjo_renut_host_packets) while the screen is split; ~-4 % in 4P (short A/B) | split screen only |

### Round 4 (A/B 357-364, `sasrt_rt4_*`, group 403) — the third table's leftovers

| key | where | what | still A/B (mean +- se) | for Banjo |
|---|---|---|---|---|
| push_runs_merged | draw.cpp PushFloatConstants | two runs of pushed groups 1-2 groups apart pushed as one (the gap's device bytes; never over a literal) | -0.26 +- 0.42 % | yes |
| state_id_crc | draw.cpp RenderStateIdLocked | the slot by CRC32C (crc32cx) instead of 27 dependent multiplies | -0.78 +- 0.77 % | yes |
| pipeline_four_way | draw.cpp fast pipeline cache | four ways, not two | +0.74 +- 0.64 % — **OFF by default** | no |
| spec_key_skip | draw.cpp fast path | a spec-memo hit skips re-comparing the kept key's spec fields (a count of every key write guards it) | +0.09 +- 0.94 % | with spec_memo |
| stream_memo_two_way | draw.cpp EntryMemo | two ways (MRU first) | +0.46 +- 0.39 % — **OFF by default** | no |
| ring_lock_once | render_thread.cpp RunRing | State().mutex kept from one queued draw (QueuePrefetched's items) into the next published one, at most 8, never past the run | +1.07 +- 1.42 % (inconclusive) | try with care: holding it across a waiting item deadlocks (proposal 19) |
| inert_keeps_chain | draw.cpp DrawStateLocked | an inert / cull-both draw keeps the fast path's chain | never fires (0 counts) | no |
| export_reads_fast | draw.cpp FastDrawLocked | a draw whose only export reads are host-layout streams found on the GPU stays on the fast path (ConvertExportedStreamsLocked there, as the full path) | -1.16 +- 0.90 % | memexport games (N&B: yes) |

## Also in these files (not render thread, but generic)

- **The menus' one-frame flash** (`sasrt_resolve_alias_previous`, textures.cpp ResolvedAlias / ResolveTarget / Retire):
  two resolve destinations of different formats in the same memory (SASRT's menu: an RGBA8 and an FP16 1152x544 image
  on one page). The renderer kept one destination per page, so a read in the other format was made from guest memory
  the GPU never wrote. Each page now keeps its two earlier destinations; a read takes the one of its own description
  (SameData). Watch for "[flash] ... made from guest memory over resolve destination" lines in Banjo's logs.
  **Cleared (Banjo, 2026-11-21 06:46):** an apparent +14 % in N&B's draws a frame with the key on was Showdown
  Town's day/night cycle (carried across runs by the autosave; daytime draws 10-15 % more): every "high" run was a
  daytime one, the key's included. No effect found. On the 360 such a read gets the
  latest resolve's bytes reinterpreted; the key gives an earlier destination of the read's own description (possibly an
  older frame's), and off gives guest memory the GPU never wrote: neither is the 360's answer. Off by default anywhere
  but SASRT.
- Diagnostics: the light-volume trace names the bound colour / depth targets and the depth alias; every depth-alias
  decision in a trace window is logged ("[sasrt] depth alias:").

Questions to the SASRT session (main chat of D:\sonic transformed).
