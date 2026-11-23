# Third-party notices

This port is built on the work of other projects. Their licenses apply to their code and to the parts of this
repository derived from it. New code written for this port is copyright (c) 2026 NebadasSwifty and is under the license
of the folder it is in (see below).

## Projects this port is derived from

| Project | Used for | License |
|---|---|---|
| [NFSMW Recompiled](https://github.com/madelrandel-blip/NFSMW-Recompiled) by madelrandel-blip | The recompilation project this port started from: the structure of `app/` (application hooks, configuration, code generator setup) and the build and analysis scripts in `tools/` | GPL-3.0 |
| [ReXGlue SDK](https://github.com/rexglue/rexglue-sdk) v0.10.0 by Tom Clay, with portions from [Xenia](https://xenia.jp) (Ben Vanik and the Xenia contributors) | `sdk/`: code generator, Xbox 360 kernel and runtime, GPU command processing, XMA audio, virtual file system | BSD-3-Clause (`sdk/LICENSE`) |
| Horizon (Switch) layer of the SDK by StevenSND | `sdk/src/**/*_switch.*`, `sdk/src/ui/switch_*.cpp`, `sdk/src/input/switch/`, `sdk/src/audio/switch/`, `sdk/cmake/rexglue_switch.cmake`, `sdk/switch_compat/`: guest memory, exception handling, threading, input, audio, presentation, clocks | BSD-3-Clause (as part of the SDK) |
| Scripts and toolchain file by StevenSND | `tools/find_gaps.py`, `tools/read_before_write.py`, `tools/direct_calls.py`, `tools/fetch_thirdparty.py`, `tools/switch/cmake/switch-devkitA64.cmake`, adapted for this game | GPL-3.0 |
| [XenosRecomp](https://github.com/hedge-dev/XenosRecomp) by hedge-dev and contributors, with shader tooling and changes by StevenSND | `shaders/XenosRecomp`: Xenos microcode to HLSL translator; `shaders/tools`: the shader library tools | MIT (`shaders/LICENSE.md`) |
| [culdcept-nx](https://github.com/ChanseyIsTheBest/culdcept-nx) and [culdcept-nx-installer](https://github.com/ChanseyIsTheBest/culdcept-nx-installer) by ChanseyIsTheBest | The audio and movie re-encodes' method (2026-11-21): NAME.xmo (`sdk/include/rex/filesystem/xmo.h`, `sdk/src/filesystem/xmo.cpp`), the XMA emulation's Opus frames (`sdk/src/audio/xma_context.cpp` DecodeXmoFrame, `sdk/src/audio/xmo_opus.*`), `tools/switch/nxvideo` | GPL-3.0 |
| rr6-nx and rr6-nx-installer (Ridge Racer 6's Switch port) | The H.265 movies' container and reader (`sdk/include/rex/filesystem/sfd_hevc.h`, `sdk/src/filesystem/sfd_hevc.cpp`), the LZ4 / ZXC block files (`sdk/src/filesystem/lz4_blocks.cpp`), the lookup of re-encoded files (`sdk/src/filesystem/devices/host_path_*`), the H.265 decode, read-ahead and priority in `app/src/cpu/sasrt_usm_ffmpeg.cpp`, `tools/hevc_usm_pack.py` (from its `tools/hevc_sfd_pack.py`) | GPL-3.0 |
| [mesa-switch](https://github.com/danfromtico/mesa-switch) by danfromtico (with NaGaa95's updates), on top of [Mesa](https://mesa3d.org); the base of the Mesa patch is the work of StevenSND | The Vulkan driver (NVK) and shader compiler (NAK) for Horizon, linked into the NRO; `mesa/` holds the changes and the build scripts | MIT (Mesa's licenses per file) |

The Horizon (Switch) layer added to `sdk/` is under the SDK's BSD-3-Clause license, and the changes in `shaders/` and
`mesa/` under the licenses of those projects (MIT), so they can be reused by other ports. The rest of this repository
(`app/`, `tools/`, `tests/`, `installer/`, `docs/`) is GPL-3.0 (`LICENSE`).

## Libraries

Libraries used by the SDK, the NRO and the code generator. They are not stored in this repository except for the
files listed below: `tools/fetch_thirdparty.py` fetches them from ReXGlue SDK v0.10.0 (commit `c94f5ebdcb3c`) and its
submodules into `sdk/thirdparty`.

| Library | License |
|---|---|
| [FFmpeg](https://ffmpeg.org) (libavcodec, libavutil: the XMA audio decoder, the MPEG-1/2 video decoder for the game's USM movies, and, from a fork addition, a WMV3 decoder that Mass Effect does not use), from the FFmpeg submodule of ReXGlue SDK v0.10.0 | LGPL-2.1-or-later (configured without GPL parts) |
| [libmspack](https://www.cabextract.org.uk/libmspack/) by Stuart Caie (LZX decompression) | LGPL-2.1 |
| [LZ4](https://github.com/lz4/lz4) 1.10.0 by Yann Collet (`sdk/thirdparty/lz4/lz4.c`, stored here: the decoder of the game files packed as LZ4 blocks) | BSD-2-Clause |
| [ZXC](https://github.com/hellobertrand/zxc) 0.15.0 by Bertrand Lebonnois (`sdk/thirdparty/zxc`, stored here: the decoder of the game files packed as ZXC blocks), with [rapidhash](https://github.com/Nicoshev/rapidhash) by Nicolas De Carli | BSD-3-Clause; MIT |
| [libopus](https://opus-codec.org) 1.3 (devkitPro's `switch-libopus`, linked into the Switch build: the decoder of the sounds the installer re-encodes to Opus; a PC build loads the system's at run time) | BSD-3-Clause |
| [FFmpeg](https://ffmpeg.org) 7.1 as devkitPro's `switch-ffmpeg` builds it, with averne's nvtegra backend (in `tools/switch/nxvideo`, linked into the Switch build as one object whose only global symbols are `nxv_*`: the H.265 movies' decoder on the Switch's NVDEC, and its software decoder) | GPL (built with `--enable-gpl`); LGPL-2.1-or-later sources |
| [glslang](https://github.com/KhronosGroup/glslang) | BSD-3-Clause and others (see its LICENSE.txt) |
| [SPIRV-Tools](https://github.com/KhronosGroup/SPIRV-Tools) | Apache-2.0 |
| [SPIRV-Headers](https://github.com/KhronosGroup/SPIRV-Headers), [Vulkan-Headers](https://github.com/KhronosGroup/Vulkan-Headers) | MIT, Apache-2.0 |
| [Vulkan Memory Allocator](https://github.com/GPUOpen-LibrariesAndSDKs/VulkanMemoryAllocator) | MIT |
| [fmt](https://github.com/fmtlib/fmt), [spdlog](https://github.com/gabime/spdlog) | MIT |
| [xxHash](https://github.com/Cyan4973/xxHash) | BSD-2-Clause |
| [SIMDe](https://github.com/simd-everywhere/simde) | MIT |
| [toml++](https://github.com/marzer/tomlplusplus) | MIT |
| [Dear ImGui](https://github.com/ocornut/imgui) | MIT |
| [o1heap](https://github.com/pavel-kirienko/o1heap) | MIT |
| [utfcpp](https://github.com/nemtrif/utfcpp) | BSL-1.0 |
| [CLI11](https://github.com/CLIUtils/CLI11) | BSD-3-Clause |
| [aes_128](https://github.com/openluopworld/aes_128) by LuoPeng, [tiny-AES-c](https://github.com/kokke/tiny-AES-c) | see the license file of each in the fetched tree (`sdk/thirdparty/aes_128`, `sdk/thirdparty/tiny-aes-c`) |
| disruptorplus, the RenderDoc API header and the PowerPC disassembler (`disasm`) as shipped with ReXGlue SDK v0.10.0 | see the license file of each in the fetched tree |
| [libnx](https://github.com/switchbrew/libnx) and the devkitA64 runtime (newlib, libstdc++) | ISC; newlib and GCC runtime licenses |

Only for builds on a computer or for the tests, never in the Switch NRO: SDL3 (zlib), MoltenVK and the Vulkan loader
(Apache-2.0), Catch2 (BSL-1.0).

### FFmpeg and libmspack (LGPL)

This port modifies these files of the SDK's third-party tree; the modified copies are in `sdk/thirdparty`:

- `FFmpeg/libavcodec/fft_template.c` and `FFmpeg/libavcodec/mdct_template.c`
- `FFmpeg/config.h`, plus `FFmpeg/config_switch_aarch64.h`, `FFmpeg/config_masseffect_wmv3.h` and
  `FFmpeg/config_sasrt_usm.h` (new): the configuration for AArch64 Horizon, for a build that also contains the WMV3
  decoder, and (2026-11-19, included on every platform) the MPEG-1/2 video decoder
- `ffmpeg-overlay/codec_list.c`: the list of registered codecs (the XMA frames decoder, the WMA decoders, MP3, MPEG-1/2
  video and WMV3)
- `CMakeLists.txt`: builds the libraries for the Switch

The rest of FFmpeg and libmspack is the unmodified upstream source at the commits pinned by ReXGlue SDK v0.10.0.
Everything needed to rebuild and relink the NRO with a modified version of either library is in this repository and in
[docs/building.md](docs/building.md).

## Installer page

The installer page (`installer/`, part of this repository) runs WebAssembly builds of the shader translator and packer
from `shaders/` (the scanner includes its own LZO1X decoder) and, when it is built, [DirectXShaderCompiler](https://github.com/microsoft/DirectXShaderCompiler)
(University of Illinois/NCSA Open Source License, with LLVM's license terms). The WebAssembly build uses
[Emscripten](https://emscripten.org) (MIT and the University of Illinois/NCSA license).

## Trademarks

Mass Effect is a trademark of Electronic Arts Inc. Nintendo Switch is a trademark of Nintendo. Xbox 360 is a trademark of
Microsoft. This project is not affiliated with or endorsed by any of them.

## Release NSP forwarder and browser DXC

The NSP build downloads and compiles [Forwarder-Mod](https://github.com/Skywalker25/Forwarder-Mod)
(commit `9853bd9167d5a7f0c5fdf935864245c1fbcf8282`), derived from switchbrew/nx-hbloader
(ISC license), and [hacBrewPack](https://github.com/rlaphoenix/hacBrewPack)
(commit `745b16ecfc9ce055743067d200572204cb2aac6c`, GPL-2.0, with bundled mbedTLS).
The loader is adapted to modern libnx/npdmtool and configured for a 39-bit full application.
The exact adaptations are in `tools/build_nsp.sh`; upstream licenses stay in the source trees.

The browser installer reuses the DXC v2025.1 WASM compiler from
[StevensND/nfsmw-nx-installer](https://github.com/StevensND/nfsmw-nx-installer/tree/e7ec1b651321d752ea34b05bc61cc210543f44d6)
at a fixed commit with both artifact SHA-256 hashes checked in `installer/tools/fetch_dxc.sh`.
It contains DirectXShaderCompiler and LLVM under the University of Illinois/NCSA
Open Source License, SPIRV-Tools under Apache-2.0, and SPIRV-Headers under MIT.
Source: [Microsoft DirectXShaderCompiler](https://github.com/microsoft/DirectXShaderCompiler/tree/75a029d95e767f291885e081f71ed951acad0019).
The source rebuild workflow and wrapper are provided in `shaders/wasm/`.

- **The game menu's fonts** (Dear ImGui's `misc/fonts`, embedded in the build by `app/CMakeLists.txt`; the base's
  port 178): ProggyTiny by Tristan Grimmer (free, its licence: MIT-style); Roboto by Christian Robertson (Apache License
  2.0); Karla by Jonathan Pinhorn (SIL Open Font License 1.1); Cousine by Steve Matteson (Apache License 2.0). The
  default ("System") is the console's own shared font, read at run time, not shipped.

### tw2de_nx (the USM movie decoder)

`app/src/cpu/sasrt_usm_ffmpeg.cpp` (2026-11-19) is adapted from tw2de_nx's `app/src/cpu/tw2de_usm_ffmpeg.cpp`
(https://github.com/recomp-nx/tw2de_nx, 2026-11-12/13): the method of taking each picture's MPEG slices off CRI
Sofdec's stream joint and decoding them with FFmpeg, its header search, black pictures for incomplete ones, and the
plane order. This port's own part is the slice loop done natively (its slice decoder is a machine copy here) and the
addresses of this game's Sofdec.
