# Link-time and profile-guided optimisation of the Switch build (2026-11-09)

The user: "PGO + LTO, and make sure the SDK gets it too, not only the game code; look at the ultimate base and Ridge
Racer 6". From rr6-nx's and renut-ultimate's set (banjo-nx's, from sa2-nx; credit those ports): app/CMakeLists.txt,
app/src/sasrt_pgo.cpp, tools/pgo_merge.py, tools/pgo_summary.py, sdk/CMakeLists.txt (`REXGLUE_OUTPUT_IN_BUILD`).

## What is optimised

`SASRT_SWITCH_LTO` (the user's rule: final builds only) and `SASRT_PGO` act on the same targets:

- the recompiled game (`sasrt_recomp`) and the app (`sasrt`: the natives, the localized copies and their guard);
- Renut's renderer (`sasrt_renut_gpu`, its objects) and plume (`plume`) — before 2026-11-09 the LTO left both out;
- with `SASRT_SWITCH_SDK_OPT` (on), the SDK runtime (`rexruntime`: kernel calls, threads, the audio driver) and FFmpeg
  (`libavcodec`, `libavutil`: XMA decoding), their C and C++ only. This needs the SDK's libraries built in each build
  folder (`REXGLUE_OUTPUT_IN_BUILD`, set by the app for the Switch): they used to be shared in `sdk/out/switch-arm64`,
  which every build folder overwrote, so they could not carry one folder's options.

Also from rr6-nx: `-mno-outline-atomics` everywhere (`SASRT_SWITCH_OUTLINE_ATOMICS` OFF): GCC's default calls helpers
that test for LSE atomics at run time; the A57 has none, so every atomic was a call before the same exclusive-load /
exclusive-store loop that is now inline.

## The three steps

1. **Instrumented build:** `tools\win\build_switch.ps1 -Pgo generate -Build out\nx` (or the default folder
   `out\nx-pgo-gen`; D: had 11 GB free on 2026-11-09 and a build folder takes 17 GB, so the everyday folder was used:
   it rebuilds in place). No LTO needed: GCC adds its counters before the interprocedural passes, so only the sources
   and compile options must match. The NRO (112 MB) streams every object's counts to `pgo/sasrt_pgo_<N>.stream` next to
   the NRO every 2 minutes, when the game loses focus (HOME) and at exit (`src/sasrt_pgo.cpp`).
2. **One race** on the console (the user: "just one race, a normal run, not more than 5 minutes"), then on the PC:
   `python tools/pgo_merge.py <folder with the streams>`: every session's counts into one `.gcda` per object in `pgo/`
   at the root (gcov-tool merge-stream; the streams name this PC's profile folder: merge here).
3. **Optimised build:** `tools\win\build_switch.ps1 -Pgo use -Final -Build out\nx` (PGO and LTO). Code the session did
   not run is compiled as without a profile (`-fprofile-partial-training`); functions changed since keep none.

A source change after step 1 loses that function's profile (a mismatch warning, not an error); a codegen re-run
(new game code) needs a new profile.

**A new profile in a folder already built with `-Pgo use` rebuilds nothing** (2026-11-10): Ninja does not track the
`.gcda` files, so step 3 recompiled only the two sources changed since and linked the old objects (the same NRO size to
the byte). Clean first: `cmake --build out
x --target clean`, then step 3 (a full rebuild, about an hour with LTO).
Merge into an empty `pgo/` (the merge adds to what is there): move the old profile aside (`pgo_1109/`).

## The first profile and its result (2026-11-09)

The instrumented NRO (112 MB) ran one race at 13:22 (the shipping toml): one 9 MB stream, merged into 417 `.gcda`
files: the game code 178, Renut's renderer 47, plume 4, the SDK runtime 93, FFmpeg 49, the app 42. The optimised NRO
(PGO + LTO over all of them, `-fipa-pta`) passed tools/check_switch_build.py (the one self-branch in game code is the
game's own halt, sub_82E687D8, as in every build).

Console, the race from the start line, stock clocks, the stack sampler off and 720 lines pinned in both (run P9 against
P7, the same settings and the same code but for PGO + LTO and the render-thread items of P8):

| | P7 (no PGO / LTO) | P9 (PGO + LTO) |
|---|---|---|
| fps | 25.74 | **28.12** (+9.2 %) |
| frame | 38.8 ms | 35.6 ms |
| render thread | 30.9 ms | **24.6 ms** |
| game thread, Swap to Swap | 29.8 ms | **24.6 ms** |
| GPU | 33.4 ms | 33.5 ms (now the limit) |
| frames late | 30 % | 13 % |
| worst frame of a 10 s window (median) | 67 ms | 53 ms (no window with one over 80 ms) |
