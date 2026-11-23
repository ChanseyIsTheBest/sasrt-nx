# Machine copies in place (sasrt-nx, 2026-11-11), for the ultimate base

## What it is

CMake `SASRT_HOT_IN_PLACE` (OFF: the hooked copies as before). ON:
- each copy's hook (`BANJO_HOT_HOOK_EX`) becomes a bare redirect: the generated function's symbol (`REX_HOOK_RAW(SYM)`) IS
  the copy's `Native` (`if constexpr (DEFAULT) n_ID::Native(ctx, base); else __imp__SYM(ctx, base);`): no state byte, no
  guard, no run-time key (the key is still defined so tomls load; a copy marked off in the list keeps the original), no
  in-run A/B 70;
- `Native` loses its `[[gnu::noinline]]` (`BANJO_HOT_NATIVE_SPEC`, emitted by localize_native.py, defined in
  banjo_hot_guest.h with a fallback in each header): GCC / LTO may inline a copy into its callers;
- the originals lose their last reference and LTO drops what nothing else names;
- implies `BANJO_HOT_GUARD_FORMS=0` (the guard is a verify build's: switch OFF).
- Generator: one change (the Native spec macro); the list, the copies and their code are the same in both builds, so a
  guard build of the hooked form verifies the in-place one's code.
- Build scripts: `build_switch.ps1 -InPlace` (out\nx-inplace / out\nx-inplace-gen, SASRT_PGO_DIR = pgo-inplace/) and
  `pgo_cycle.ps1 -InPlace` (each form has its own PGO profile: the code differs).
- Not done (looked at and dropped): adding back the small functions idea 30 leaves out. The race profile shows plain
  generated code at 0 % of samples: those small functions are already inlined into their callers by LTO.

Patch scripts (sasrt-nx paths, idempotent, assert every anchor): `inplace_copies.py` (CMake option, banjo_hot_guest.h,
localize_native.py), `inplace_scripts.py` (build_switch.ps1 / pgo_cycle.ps1 -InPlace).

## Numbers (console, handheld 1020/460.8/1600, the same race, stack sampling on, each with its own PGO + LTO)

| | hooked | in place | change |
|---|---|---|---|
| process CPU a frame | 84.72 ms | 82.99 ms | -2.0 % |
| game thread (Main XThread) | 22.99 ms | 22.04 ms | -4.1 % |
| AK::EventManager / Model Instance / SlAnimManager | 4.03 / 4.11 / 2.50 ms | 3.77 / 3.92 / 2.39 ms | -6.7 / -4.8 / -4.4 % |
| WaterThread (mostly hand natives) | 7.04 ms | 7.23 ms | +2.8 % (noise) |
| render thread busy | 24.22 ms | 23.71 ms | -2.1 % |
| fps (GPU-bound) | 27.50 | 27.59 | +0.3 % |
| average 3D height (dynamic resolution) | 690 lines | 694 lines | |
| NRO | 75.7 MB | 71.6 MB | -4.1 MB |

One race pair; run-to-run noise on process CPU is about +-2 %, so the game thread's -4 % is the firmest number. No
crash, no difference lines, the picture as before.
