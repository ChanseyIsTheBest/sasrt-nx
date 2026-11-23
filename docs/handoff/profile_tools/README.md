# Profile tools for the base (sasrt-nx, 2026-11-11)

The three tools the optimising guide (docs/hand-and-machine-optimising-guide.md) uses to read a console profile
(`logs/rex/rex_profile_NNN.log`, written by the SDK's sampler with `stacks_profile.flag`) against the link map of the SAME
build. Copied as they are in sasrt-nx; Python 3, no packages beyond the standard library (switch_hot_pcs.py also calls
devkitA64's objdump).

| Tool | Gives |
|---|---|
| `profile_breakdown.py PROFILE --map MAP [--from-report N] [--to-report M] [--top 12] [--min-cpu 1]` | per thread: CPU, pinning, and the split hand / machine / generated / renderer / runtime; each thread's hottest functions; the hottest guest functions of all threads |
| `switch_hot_functions.py PROFILE [--map MAP] [--top 40] [--thread NAME]` | the hottest functions (imported by profile_breakdown.py as `shf`) |
| `switch_hot_pcs.py PROFILE MAP ELF "section substring" [from_report] [windows] [win_bytes]` | the hottest instruction windows inside one function, disassembled: what decides whether a hand native can remove the cost |

## What is sasrt-nx's own (adapt per port)

- `switch_hot_functions.py`, `module_of()`: the CMake targets' object folders: `sasrt_recomp.dir` (the generated game
  code: "default"), `sasrt.dir/src/me/` (renderer), `sasrt.dir/` (the app: copies and natives). A port's names are
  `<port>_recomp.dir` / `<port>.dir`.
- `switch_hot_functions.py`, the `--map` default: `out/nx/sasrt.map`.
- `profile_breakdown.py`, `kind()`: the native-name markers (`sasrt3hot`, `banjo4hand`, `hot::`) and the renderer object
  regex (`RENDERER_OBJ`, includes `sasrt_renut`); `machine_and_hand()` reads `app/src/cpu/hot/localized.txt`,
  `localized_bulk.txt`, `hand.txt` and `app/src/hot/n_*.h`.
- With LTO the objects are `ltrans` partitions, so renderer and runtime cannot be told apart by object (both show as
  runtime); guest copies and natives are still classified by symbol name.
