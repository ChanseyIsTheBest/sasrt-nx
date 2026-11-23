# sasrt-nx handoff for the ultimate base, 2026-11-13

Everything sasrt-nx made since batch CC2 (base port 121), the pgo_merge guard (122) and the plume bug (129) that the base
does not have yet. Every code item is exact and off-the-shelf for any game unless it says otherwise; paths are this
port's (D:\sonic transformed\sasrt-nx). Measured on the console, handheld 1020 / 460.8 / 1600, Ocean View, same-session
controls (docs/handoff/batch_cc2/README.md, docs/resolve-project-1112.md, docs/ultimate-base.md).

## 1. R2: a resolve destination's depth-words probe kept across a remake (GPU, exact; recommended)

`app/src/renut_engine/gpu/render/textures.cpp`: key `sasrt_gpu_words_probe_kept` (default on, kInitOnly), the block
"resolve project R2" in the resolve-destination remake (search `carry_words`). A destination made again at the same guest
address and host format (a dynamic-resolution step changes its scale / size) keeps `words_wanted` and `words_probe`.
Before, each remake started the 300-resolve words probe again, so a destination whose words nothing reads (SASRT's
shadow atlas) drew the RGBA8 words output in about half its resolves. A late reader is served exactly as before
(EnsureDepthWordsLocked: drawn again from an unchanged source, else counted stale and written from then on).
Result: the atlas wrote words in 300 of 24,954 resolves of a race (before: 11,946 of 24,138); +0.9 % 3D resolution under
dynamic resolution (the GPU saving shows as resolution, not ms). Any game with dynamic resolution and a depth resolve
destination whose words are unread gains the same.

## 2. Diagnostics (off by default; how the GPU findings below were made)

- **R1, depth words by destination** (`render/draw.cpp` GpuCensusDepthWords / GpuCensusDepthWordsRead, the
  `renut_diag_gpu_census` line's "depth resolve words by destination (R1)" field): per destination, resolves with and
  without words, and how often the words were read by a fetch or the restore.
- **Resolve split and clear labels** (`render/draw.cpp`, key `sasrt_gpu_diag_resolve_split`, with
  banjo_renut_diag_gpu_shaders + sasrt_gpu_diag_profile_vs): each resolve's GPU time in parts (barriers / draw / after /
  after the move to shader read) with its resolves a frame, in DrawResolveCopy, ResolveFixed16Locked and ResolveDepth;
  every depth clear under its own "clears | depth WxH" label. The labels resolve 0.1 ms differences between whole races;
  the in-run A/B with 4 s halves has a ~2 ms GPU noise floor in a race (a target that never acted showed -2.35 ms).
- **Exclusive-pair timing** (`sdk/src/ui/switch_perf.cpp`, the profile header's FPCR line): one ldxr/stxr and one
  ldaxr/stlxr increment on a cache-resident word. A57 handheld: 17.6 vs 26.4 ns.

## 3. Wait functions without __dynamic_cast (CPU, exact; optional)

`sdk/include/rex/thread.h` WaitHandle::posix_wait_impl() and `sdk/src/core/threading_posix.cpp` AsPosixWaitHandle: the
POSIX Wait / SignalAndWait / WaitMultiple cast the handle through a virtual accessor instead of dynamic_cast (which
walked the type info on every wait). The base's port 59 already has the heap-free WaitMultiple; this is the cast only.
No measurable change in SASRT (the estimate was at most 0.2-0.4 %).

## 4. tools/ult_port_sync.py (a tool for any port)

A per-commit three-way sync from the base: for each port commit and each file it changes, git merge-file of the port's
file with the base's file before and after that commit, so exactly that port's change comes in and the port's own work
stays; new files copied, Katamari / docs / dist skipped, per-XDK files and renamed files listed for a hand port; line
ends kept. SASRT took ports 45-129 with it (130 files; 136 conflict blocks resolved by hand). Usage in its docstring.

## 5. Feedback on base ports, from SASRT's sync (no change asked; for the off-by-default list's notes)

- Port 76's key 215 (blur_renut_stack_surface_headers) and port 101 (dishonored_renut_vertex_readable_check) together
  cost SASRT's render thread ~0.4 ms a frame (19.65 -> 19.23 with both off; process CPU -1.3 %): 215 adds a header
  capture per queued op where a port already captures its surfaces, 101 a heap lock and page walk per converted stream.
  SASRT turns both off in its toml. A game that needs neither may want the same.
- Port 100 (invariant gl_Position) is worth ~3 ms of GPU a frame to SASRT (tested 2026-11-13, batch G: a package
  without it drew a fixed-720 race at 38.2 ms against 34.1; a few pixel shaders shaded several times the pixels: the
  depth pre-pass and the colour pass no longer made the same depth, so the early depth test stopped rejecting). An
  earlier version of this note suspected it of costing 1-4 lines: wrong. Port 99 (earlykill) off measured within the
  noise (+0.3 ms whole race, -0.04 in the label sums); port 120's XMA kick made no difference here.
- deko3d's depth clears are full-bandwidth writes on this hardware whatever the image's state: a fresh compressed image
  or a depth-and-stencil clear instead of depth-only both left a 1024x1024 D24S8 clear at ~0.22 ms. No fast-clear win.
- With a new shader package, a port's DKSH cache built from pipeline lists lacks the specialised variants a console
  compiles at run time; the first races compile them on core 3 (SASRT: 95 compiles, +8 ms of process CPU in that race,
  gone after two races). Measure after warm-up runs.

## Not for the base

CG-13 ON by default (the user's choice for SASRT only; the base keeps it off), SASRT's toml settings, the copies'
frame-pointer revert (the base never took that), SASRT's own A/B renumbering.
