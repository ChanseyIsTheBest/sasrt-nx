# sasrt-nx

An unofficial native port of the Xbox 360 version of **Sonic & All-Stars Racing Transformed** (title `5345085D`), first
to Windows PC and then to the Nintendo Switch, by static recompilation with [ReXGlue](https://github.com/rexglue/rexglue-sdk).

The PowerPC code of the game's `default.xex` is translated to C++ ahead of time and compiled for the target. No emulator,
no interpreter, no JIT. The method, the SDK fork (ReXGlue 0.10.0 with a Horizon layer), the tools and the native
renderer come from [sa2-nx](https://github.com/ChanseyIsTheBest/sa2-nx), which took them from
[nfsmw-nx](https://github.com/StevensND/nfsmw-nx), [masseffect-nx](https://github.com/nebadasSwifty/masseffect-nx) and
banjo-nx; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

**This repository contains no game files and no code made from them.** You need your own copy of the game: the Games on
Demand package `5345085D/00007000/97A9A171AADA666596EA` with its `.data` folder (or a disc image), and optionally the
"Bonus Pack" DLC package `5345085D/00000002/2125BED78BDCE2760AA1FBA35A3A4A5FA4F5C2A153`. Everything made from them
(`assets/`, `app/generated/`, `app/thunks.toml`) is git-ignored.

See [docs/plan.md](docs/plan.md) for the stages and their state, and [docs/sasrt-notes.md](docs/sasrt-notes.md) for
what was found in the game's code, each finding with its evidence.

## Playing it on the Switch (1.0.0)

**Version 1.0.0** by ChanseyIsTheBest. Make the Switch package from your own copy of the game with the web installer:
**https://chanseyisthebest.github.io/sasrt-nx-installer/** (source: [sasrt-nx-installer](https://github.com/ChanseyIsTheBest/sasrt-nx-installer)).
It runs in your browser: it reads the disc image, the Games on Demand package or the extracted folder, makes the game's
shaders for the Switch from your files (translated and compiled in the browser), re-encodes the movies to H.265 and the
sounds to Opus, packs the archives, and downloads `sasrt-nx.zip` to extract to the root of the SD card. The NRO is in
[the 1.0.0 release](https://github.com/ChanseyIsTheBest/sasrt-nx/releases/tag/v1.0.0) and in the installer.

What the release does, in short:

- Single player, story mode and split screen for 2 to 4 players; the Bonus Pack DLC when you add it to the installer.
- A Renut renderer on deko3d (the Switch's own GPU API) with dynamic resolution; 30 fps cap by default (the game's own
  pace), adjustable up to 60 in the game's menu.
- Four CPU cores when started from a Sphaira forwarder (see the installer's page).
- Every log off but the crash report (`switch/sasrt-nx/logs/rex/rex_crash.log`); for a bug report set
  `log_level = "info"` at the top of `switch/sasrt-nx/sasrt.toml`.

## Building on Windows

Needs: VS 2022 Build Tools (MSVC libraries + Windows SDK), LLVM clang 20 (portable is fine; by default `..\_tools\llvm`),
Python 3, Git. CMake and Ninja come from the VS Build Tools. Paths can be overridden, see `tools/win/env.ps1`.

```powershell
# 1. Extract your game (checks every SHA-1 of the package; ~4.7 GB). A disc image: tools\extract_iso.py instead.
python tools\god_extract.py "<...>\5345085D\00007000\97A9A171AADA666596EA"
#    The DLC (optional): copy its package file into out\pc\dlc\ after the build; the game installs it at start.

# 2. Third-party sources of the SDK (only the files this fork changed are kept in sdk/thirdparty)
python tools\fetch_thirdparty.py

# 3. Build the code generator
powershell -File tools\win\run.ps1 out\host_configure.log "cmake -S sdk -B out/host -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DREXGLUE_USE_VULKAN=OFF"
powershell -File tools\win\run.ps1 out\host_build.log "cmake --build out/host --target rexglue"

# 4. Translate the game to C++: the first run also writes the loaded image (REXGLUE_DUMP_IMAGE), from which
#    tools\thunk_table.py makes app\thunks.toml; then translate again with it.
$env:REXGLUE_DUMP_IMAGE = "$PWD\out\default_image.bin"; powershell -File tools\codegen.ps1
python tools\thunk_table.py
powershell -File tools\codegen.ps1

# 5. Build the game
powershell -File tools\win\run.ps1 out\pc_configure.log "cmake --preset win-pc -S app"
powershell -File tools\win\run.ps1 out\pc_build.log "cmake --build out/pc"

# 6. Run it for 45 s (muted, minimized) and show the end of the log
powershell -File tools\win\boot_test.ps1
```

(The first codegen of step 4 fails validation with "target not in any function" errors until `thunks.toml` exists:
that is expected, the image dump is written before the analysis.)

`out\pc\sasrt.toml` holds the settings. It starts **muted and minimized** by default (`audio_mute`,
`window_start_minimized`), so test runs stay out of the way; set both to `false` to play.

## License

GPL-3.0 (see [LICENSE](LICENSE)), like the ports it builds on. The SDK keeps its BSD-3-Clause license.
No affiliation with SEGA, Sumo Digital or Microsoft.
