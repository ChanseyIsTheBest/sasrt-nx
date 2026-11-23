# LZ4 / ZXC packing, H.265 movies and Opus audio for banjo-nx's installer and port (from sasrt-nx, 2026-11-21)

The user (2026-11-21): "please help banjo have l4z and zxc in its web isntaller and rencode video and audio to opus and
h265". What N&B has, what to take from where, and what SASRT is doing the same way. Read the other repos' working
trees only (rr6-nx and culdcept-nx: uncommitted work in places).

## N&B's game files (D:\Banjo kazooie port\game, measured 2026-11-21)

| Files (first 4 bytes) | Count | Size | zlib-1 on samples | What to do |
|---|---|---|---|---|
| `Bundle/50/*` (43 8C B4 7C) | 151 | 3,285 MB | 62 % | LZ4 (read at load) or ZXC: about 1.2 GB saved. One of them, `Bundle/50/685374` (820 MB), holds the XACT wave banks (below) |
| `Bundle/4f/*` (0F F5 12 ED) | 142 | 1,339 MB | 105 % | as they are (already compressed) |
| `Debug/**` (30 26 B2 75: ASF) | 52 | 1,211 MB | 104 % | the WMV movies: H.265 as culdcept-nx does (below), ~35 % of their video bitrate: about 750 MB saved |
| CAFF (`CAFF07.08.06.003`) | 1,614 | 666 MB | 54 % | LZ4 or ZXC: about 300 MB saved |
| default.xex, fonts, `$SystemUpdate` | | ~75 MB | | as they are (the xex: the NRO loads it itself) |

## Packing (LZ4 and ZXC)

- **Port (sdk):** rr6-nx's `sdk/src/filesystem/lz4_blocks.cpp` and `sdk/include/rex/filesystem/lz4_blocks.h` (version 1
  LZ4 blocks, version 2 ZXC blocks; identical in culdcept-nx), `sdk/thirdparty/zxc` and `sdk/thirdparty/lz4`, and the
  `rexblockcodecs` block of rr6-nx's `sdk/src/filesystem/CMakeLists.txt`. The lookup (NAME.lz4b answers for NAME):
  `sdk/src/filesystem/devices/host_path_entry.cpp` / `host_path_device.cpp` / `host_path_index.cpp` (index version 2,
  AnswerRank). sasrt-nx took exactly these on 2026-11-21 (its `sdk/` has them now, with .xmo / .xmop beside .hevc).
- **Installer:** culdcept-nx-installer's `lib/lz4b.js`, `wasm/lz4.*` and `wasm/zxc.*`, `pack_worker.js`, and
  `game.json`'s `lz4` / `zxc` lists (README "Packing": LZ4 HC 9 in 256 KB blocks for files read at load time, ZXC 7 in
  512 KB blocks for the rest).

## Movies (WMV in ASF -> H.265)

N&B's movies are WMV in ASF, as Culdcept Saga's are, so culdcept-nx's path applies as it is:
- **Installer:** culdcept-nx-installer's `lib/asf.js`, `wasm/wmv3` (FFmpeg's WMV3 decoder in WebAssembly),
  `movie_worker.js`, the `movies` option of `game.json` (fraction 0.35, keyframe every 120); the browser's H.265 encoder
  (WebCodecs). The movie stays an ASF file with H.265 frames.
- **Port:** culdcept-nx's `app/src/cpu/culdcept_wmv_ffmpeg.cpp` (the WMV hook and its H.265 path) and
  `tools/switch/nxvideo` (FFmpeg 7.1 + nvtegra in one object, only `nxv_*` global; the CMake block is in rr6-nx's
  `app/CMakeLists.txt`, `RR6_NXVIDEO`). devkitPro's `switch-ffmpeg` (with nvtegra) and `switch-libopus` are installed
  on this PC.
- rr6-nx's traps (its `docs/opus-h265-handoff-sasrt.md`): decode at priority 0x2C, frames read ahead on a libnx thread
  (`threadCreate`, not std::thread), Ryujinx has no H.265 NVDEC (test with the software decoder), and a new
  `REX_HOOK_RAW` needs `tools/direct_calls.py --redo`. RR6 also packs each re-encoded movie as ZXC (`NAME.hevc.lz4b`):
  the container's other bytes (audio, headers) compress by about a tenth.

## Audio (XACT wave banks -> Opus)

N&B's sounds are XACT wave banks (big-endian), 420 of them inside `Bundle/50/685374` and one in `Bundle/4f/3e5515`
(XACT version 43/42; 24-byte entries). How many are XMA and how many PCM / ADPCM I could not read reliably in a quick
pass (the 360's bit-field order in the entries' format word); that is the first thing to establish.

- XMA sounds can go to Opus the way culdcept-nx does it: the game sees its XMA as it was, each packet carrying a tag,
  and the XMA emulation takes each frame's 512 samples from the sound's Opus. culdcept-nx's own format (`.xmo`) is one
  XMA file per sound; N&B's sounds are many to a container, as SASRT's are (Wwise packages).
- **SASRT's multi-sound format, `NAME.xmop`** (2026-11-21): `sasrt-nx/sdk/include/rex/filesystem/xmo.h` (the format:
  segments of stored bytes, zeros or a sound's synthesized packets, and a sound table), `sdk/src/filesystem/xmo.cpp`
  (the reader, culdcept-nx's .xmo plus the package, `.xmop.lz4b` too), `sdk/src/audio/xma_context.cpp`
  `DecodeXmoFrame` and `sdk/src/audio/xmo_opus.*` (culdcept-nx's, plus 24 kHz Opus and 44.1 kHz sounds resampled from
  48 kHz Opus). It is container-agnostic: only the installer's parser is SASRT's (AKPK); N&B's would parse wave banks.
  The installer side is being built now in `D:\sonic transformed\sasrt-nx-installer` (its xmop writer and the XMA2
  walk/decode in WebAssembly). XACT's XMA is XMA2 too (2048-byte packets), so the same walk should apply.
- PCM or ADPCM entries are not XMA: they stay as they are (packing may still shrink them).

## Status on SASRT's side (2026-11-21 ~23:00)

All of the above is written into sasrt-nx's sdk/app and its first Switch build is compiling; nothing is tested yet (the
movies on Ryujinx with the software decoder next, then the console). Ask me (the "sonic racing" session) for the
results or the files.
