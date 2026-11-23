# The thread-latency round (SASRT, 2026-11-10 afternoon): what helps the base

For RR6 and the ultimate base, one batch at the end of the round (the user: "send in one large batch at the end when
everything is tested and confirmed"). SASRT's round: docs/render-thread-round-1109.md, "The thread-latency round".
Console: handheld 1020/460/1600, Ocean View, PGO + LTO builds.

## 1. The recording hook: halo3-nx's inherit scan only where it is read (code, confirmed)

`NoteSetWords` (halo3-nx, 2026-11-03) compares 936 device words with the device at the buffer's Begin at every recorded
op, a word and a branch at a time, and BeginCommandBuffer copies the whole 12.7 KB device for it. Its bits are read only
by `BuildInheritRuns`, with `banjo_renut_replay_inherits`. The base runs it unconditionally (checked 2026-11-10:
`command_buffers.cpp` line ~1917 `NoteSetWords(buffer, set, bytes)` and ~2959 the Begin copy).

In SASRT (inherits off) it was 54 % of NewOp's samples and NewOp 43 % of the recording thread. With the gate the
recording thread fell from 18.2 % to 13.7-14.0 % of a core (runs lat4 -> lat6, wg2; NewOp and its parts 44 % -> ~24 % of
the thread). The render thread's wait for the same-frame recording is the recording itself (run wg2: the render thread
waits 2.3-7.3 ms at the place, the recording takes 2.6-7.2 ms Begin to End), so a faster recording shortens that wait.
Pixel-identical by construction (the bits are unread with the inherits off). Confirmation race on the final build (lat10, shipping settings): 25.38 fps against 25.05 before the round (lat2), render thread 27.3 ms a frame against 28.5, input -> display 63.9 ms against 67.3, recording thread 14.2 % of a core, 0 fence timeouts, 0 errors. fps did not move beyond the race's noise
(lat8's in-run A/B: the 10 s halves alias with lap sections).

- `sasrt_record_inherit_scan_gate` (on): with `banjo_renut_replay_inherits` off, NewOp leaves out the scan and Begin
  leaves out the image copy.
- `sasrt_record_inherit_scan_wide` (on): where the inherits are on (Halo 3 and others), the scan compares 16 bytes a
  step (two 8-byte XORs and one test for an unchanged step) and sets the four words' bits from the differing halves:
  the same bits (host test `files/test_inherit_scan.cpp`: 200,000 random devices with 0-40 changed bytes and pre-set
  bits, 0 mismatches; build line at its top). Not console-tested (SASRT has the inherits off).

`files/inherit_scan.patch`: made on the base's own `command_buffers.cpp` (4 hunks; apply with `patch -p1 -l`, the file
is CRLF). SASRT's own copy also has an in-run A/B (201) in `InheritWordsKept`; the patch leaves it out (the base's A/B
numbers are its own).

## 2. A wait graph (diagnostic, off)

`rex_wait_graph` (Kernel, off): every guest wait (XObject::Wait / WaitMultiple) timed per waiting thread and object,
every XEvent Set/Pulse, XSemaphore release and XMutant release counted per object and signalling thread; every 10 s a
`[waits]` line per thread with its four largest waits and the top three signallers of each. Threads blocked for more
than 90 % of the window are left out (they wait for work; the idle audio and file threads filled the ten lines in the
first run). Off: one load of a static bool per wait and per signal. On, it takes a mutex per wait (a diagnostic).

What it showed in SASRT (run wg2): Main XThread and SlRenderer hand frames to each other (Main waits on a semaphore only
SlRenderer releases, 65-200 ms a second; SlRenderer on Main's, 6-58 ms a second), SlRenderer waits 1.2-2.5 ms a frame on
the WaterThreads it starts, and the recording worker waits on SlRenderer's semaphore. Host-side waits (our pacing,
QueueFrame) are not guest waits and are not in it.

`files/wait_graph.patch`: made on the base's own SDK files (xobject.cpp/.h, xevent.cpp, xsemaphore.cpp, xmutant.cpp,
xthread.h's `short_name()`; 9 hunks, additions only; `patch -p1 -l`). It keeps the base's port 59 WaitMultiple
(inline handles), which SASRT does not have.

## 3. Findings (no code)

- **Late input misreads a pacing change.** `banjo_late_input` takes the Swap's wait in QueueFrame for slack. When
  something moves the frame's wait into QueueFrame (the display pacing below; relaxed vsync, where late frames go at
  once and the game thread then waits on the render thread), the delay grows (12-15 ms a frame, 25 ms in the morning's
  relaxed run) and holds the game's main thread back. SASRT's display-pacing A/B lost 2.0 fps with late input on and
  0.6 without (runs lat6, lat7). In a game whose Swap thread is not its input thread (SASRT: SlRenderer swaps, Main XThread
  reads the pad) the slack is not the main thread's. Anyone testing relaxed vsync or another pacing: A/B it with
  late input off too.
- **Relaxed vsync without late input** (SASRT's A/B 203, 4 s halves, run lat9): relaxed 25.70 fps, fixed 25.33. Level
  within the noise: SASRT's earlier -4 fps for relaxed vsync was late input's.
- **The display as the pacer** (`sasrt_pacing_on_display`, SASRT only, off): swap interval 2 on the swapchain and no
  CPU sleep at the Swap: no faster (-0.6 fps without late input) and input -> display 75 ms against 67.
- **No gain** (each its own key, off, in SASRT only): Main XThread + SlRenderer one priority above the workers (0x3A;
  lat3), the render thread's queue on an address instead of the condition variable (lat4) and a 50 us spin before
  it sleeps (lat5), WaterThread on core 3 (stutters and late vertex data), the render thread un-pinned.
- **Kept, config only:** the shader compiles, prebuild workers and ring cleaner on core 3
  (`banjo_system_core_compiles = true`), which other ports already run.
