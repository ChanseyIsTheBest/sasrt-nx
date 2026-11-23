# The intro movie: dropped frames and stuttering audio (2026-11-09)

The user: "optimise the intro video so it stops dropping frames and it has stuttering audio".

## What the console showed

The user's intro run (sasrt_090, stock clocks: CPU 1020 MHz, GPU 460.8 MHz) and an intro-only run with the stack sampler
forced on (`logs/rex/stacks_profile.flag`, removed after; `out/console_runs/intro_movie/rex_profile_090.log`, the NRO
of `out/console_runs/dynres_up`):

- The intro (`Data\Movies\Drifting.usm`, CRI, 1280x720 at 30 fps) ran at 21-22 fps for its whole length: the game
  thread 36 ms from Swap to Swap, so each frame missed its 33.3 ms slot and waited for the next vblank (10-12 ms
  paced), 47 ms a frame on average.
- The movie's audio: in every 10 s window about 22 % of the audout buffers held only zeros (365-388 of 471-491 with
  any sound; a race: 471 of 471). audout never ran out of data ("requests without data 0"): the game's own mixer
  played silence, its movie voice not fed in time. The audio and the frame drops have one cause: the decoder behind.
- Threads (10 s windows of the intro): SlRenderer 62-68 % (the movie's own thread, the one that calls Swap), two
  decoder workers (unnamed XThreads) 35-39 % each, SlParticleThread 9-10 %, the main thread 7-8 %, the render thread
  9 %. No core full (CPU total about 190 % of the three game cores).
- SlRenderer's 30 ms of work a frame (its waits are the vblank and the workers): the decoder (the workers run the same
  functions: `sub_82EB23E0` 16-28 %, the bitstream decoder `sub_82EB6B78` 10-20 %, the PSFD00 section's functions
  `sub_8302xxxx` about 20 %) and the colour conversion `sub_82E7F918` (the hand-written native of 2026-10-21): 21 % of
  SlRenderer's running samples, about 6.3 ms a frame (7 cycles a pixel).

So SlRenderer's own work sets the frame: 4-5 ms less of it per frame and the movie keeps its 30 fps slots.

## The colour conversion: two keys

`sub_82E7F918` turns the decoded 4:2:0 planes into 3.7 MB of 32-bit pixels through five 256-entry tables and a clamp
table the game builds at start (`sub_82E7F7A0`: doubles from .rdata, `fmadd`, `fctiwz` truncation; BT.601: luma 1.164
and 256.5/2^20 ... chroma 1.596, 0.392, 0.813, 2.017, all times 2^20). The tables are not integer-linear (truncated
doubles), so the per-pixel lookups stay. The kernels moved to `app/src/hot/n_82E7F918_kernels.h` (no guest memory) so
the PC tests them:

- `sasrt_movie_colour_lanes` (on): `PairLanes`. The 2026-10-21 path stored each group's table words to small arrays
  and loaded them back as vectors (on the A57 a 16-byte load of bytes just written by 4-byte stores waits for those
  stores), and reduced the clamp range across lanes twice per 16 pixels. Now the words go straight into vector lanes
  and the range is checked once per row pair; a row pair with a group outside the clamp's straight part (indices below
  0 or above 767: only very bright saturated blue reaches it) is done again by the old path over the same outputs.
- `sasrt_movie_colour_helper` (on): a second thread converts row pairs too (chunks of 8 from one counter), on core 3
  where the four-core mode has it. Each call is a job of its own; the caller returns once every row pair is written,
  not waiting on a helper that has not woken.

`tools/test_yuv_kernels.cpp` (built with the PC's clang, `-I sdk/thirdparty/simde -I app/src`): the tables built as
the game builds them (indices -21..790, step at 256, straight part 0..767: the console's log line exactly), 4,000 row
pairs (a quarter random bytes, reaching every index; the rest picture-like) and 2,000 single groups against the scalar
table path: 0 bytes differ.

The decoder itself (`sub_82EB23E0`, `sub_82EB6B78`, PSFD00) is the next lever if this is not enough; `sub_82EB6B78`'s
machine copy was 13 % slower on the PC (2026-10-07) and stays out.

## Results on the console

Run movie_fix (17:49, five minutes without a press, the sampler on; `sasrt_movie_colour_lanes` and one helper on core
3): the intro 22-25 fps (was 21-22.5), Swap to Swap 33-35 ms (36), silent audio buffers about 11 % (22 %). Better, not
there. The profile: SlRenderer still about 6 ms a picture in the conversion and the helper (core 3, 5.5 % CPU) about
2.3 ms more: PairLanes no faster than PairNeon on the A57, whose one load pipe both fill (56 loads a group of 16
pixels). So the kernels became three, chosen by timing:

- `sasrt_movie_colour_kernel` (0: the fastest on the first picture, timed and logged; 1 PairNeon, 2 PairLanes, 3
  PairPacked). PairPacked makes 28 loads a group: each row's 8 luma bytes and each chroma plane's 4 bytes as one word,
  and each chroma byte's two terms by one 8-byte load from packed tables (ta, tb), unzipped into lanes.
- `sasrt_movie_colour_helpers` (2): a second helper on the game's cores besides the one on core 3.
- A log line every 300 pictures: the call's time and the share of row pairs the calling thread did.

`tools/test_yuv_kernels.cpp`: 12,000 row pairs (three kernels) and 2,000 groups (two kernels against the table path):
0 bytes differ.

Run movie_fix2 (18:14, five minutes without a press; kernel 0 and 2 helpers): the timing on the first picture, one
thread: PairNeon 8.53 ms, PairLanes 7.28 ms, PairPacked 6.10 ms (chosen). With the helpers a picture took 4.0-4.7 ms
(the calling thread 41 % of the row pairs). The intro: 25.5-29.3 fps (log windows; 27.6-31.3 in the profile's),
Swap to Swap 30-33 ms, silent audio buffers 0-5 % (22 % before the day's work). The core-3 helper ran 2.5 % CPU and
the other 8.8 %, both at the game threads' priority 0x3B: the caller waited about 1.6 ms a picture for their last
chunks. The decoder is now most of SlRenderer: `sub_82EB23E0` 18 % (about 3,600 guest instructions of byte unpacking:
coefficient decoding with float dequantisation; a hand-written exact copy is a large job), `sub_82EB6B78` 13 %.

Next build: the helpers at 0x2C (the render thread's) and chunks of 4 row pairs; kernel 4, PairPacked with each
64-byte output line zeroed in the cache before its stores (DC ZVA, when DCZID_EL0 allows 64-byte blocks), so the 3.7 MB
picture is not read from memory before being overwritten; the first picture's timing picks among the four.

Run movie_fix3 (18:36, five minutes without a press; helpers at 0x2C, chunks of 4, kernel 0 with kernel 4 offered):
the first picture's timing PairNeon 8.32, PairLanes 7.35, PairPacked 6.27, PairPacked with DC ZVA 7.51 ms (slower:
PairPacked chosen; kernel 4 stays a choice, never picked here). A picture 2.67-2.78 ms with the helpers (the caller 36 %
of the row pairs). The intro: 279-299 frames a 10 s window (28-30 fps; 205-215 in the morning), Swap to Swap 27-31 ms,
late frames 3-44 a window, and no silent audio buffer in any intro window (497-604 of 497-604 with sound; 22 % silent
in the morning). The NRO on the console since (out/console_runs/movie_fix3) has these and `sasrt_dynamic_up_one_step`.
