# LZ4 / ZXC packing, H.265 movies and Opus audio for blur-nx's installer and port (from sasrt-nx, 2026-11-21)

The user (2026-11-21): "please help blur have l4z and zxc in its web isntaller and rencode video and audio to opus and
h265". What Blur has (measured from D:\blur\game, 2026-11-21), what the other ports did, and what is new for Blur. Read
the other repos' working trees only.

## Blur's game files

| Files | Count | Size | zlib-1 on samples | What to do |
|---|---|---|---|---|
| `layer1/levels/*/level.levelstream` (ARCH) | 19 | 2,938 MB | 80 % | ZXC (read while racing: ZXC 7, 512 KB blocks, ~200 MB/s on the console; or LZ4 HC if load-bound): perhaps ~450 MB saved. Measure ZXC itself |
| `Ui/movies/*.bik` (Bink 1, `BIKi`) | 31 | 1,343 MB | 100 % | H.265: a new path (below) |
| `cache/*.pak` (PAK2) | 9 | 1,161 MB | 94 % | the entries are compressed already (blur-nx-installer's lib/pak2.js / xmem.js know the format); the audio is inside (below) |
| `*.levelrender`, `*.levelphysics`, `*.level` | 57 | 224 MB | 47-55 % | LZ4 already (blur-nx-installer's game.json) |
| default.xex/xexp, AvatarAssetPack etc. | | ~41 MB | | as they are |

## Packing

blur-nx-installer has LZ4 already (`lib/lz4b.js`, `wasm/lz4.*`, `lz4_worker.js`). ZXC (version 2 `.lz4b`) is rr6-nx's:
- **Port:** rr6-nx's `sdk/src/filesystem/lz4_blocks.cpp` / `lz4_blocks.h` (version 2), `sdk/thirdparty/zxc`, the
  `rexblockcodecs` block of its `sdk/src/filesystem/CMakeLists.txt`. sasrt-nx has taken them too (2026-11-21).
- **Installer:** culdcept-nx-installer's or rr6-nx-installer's `lib/lz4b.js` (codec 'zxc'), `wasm/zxc.*`, and the
  `zxc` list in `game.json`.

## Movies: Bink 1 -> H.265 (new: no port has done Bink yet)

Culdcept (WMV in ASF), RR6 (Sofdec .sfd) and SASRT (CRI USM) all keep the movie's container byte for byte and replace
only the pictures' data with a tag, then write the H.265 picture into the game's frame buffer in a hook:
- rr6-nx: `sdk/include/rex/filesystem/sfd_hevc.h` (the container-agnostic format: segments of stored bytes, zeros and
  tag bytes; a frame table of H.265 access units), `sdk/src/filesystem/sfd_hevc.cpp`, `app/src/cpu/rr6_hevc_movies.cpp`
  (decode on NVDEC through culdcept-nx's `tools/switch/nxvideo`, read-ahead thread, raised priority); `NAME.hevc.lz4b`
  (ZXC around it).
- sasrt-nx: `tools/hevc_usm_pack.py`, `app/src/cpu/sasrt_usm_ffmpeg.cpp` (the tag found where the game's MPEG slices are
  taken; the H.265 picture of that display index written into the coded picture's planes).
For Bink the same shape would be: in each Bink frame packet keep the audio tracks' bytes and replace the video data
with a tag (the movie, the frame index) and zeros; hook the game's Bink calls (RAD's Bink 1 is linked into
default.xex: BinkDoFrame not to decode a tagged frame, BinkCopyToBuffer / the frame planes to take the H.265 picture);
the installer decodes Bink 1 video with FFmpeg's `bink` decoder in WebAssembly and encodes H.265 with WebCodecs. Bink
audio stays as it is. Bink's frames have no B-frame reordering (frame index = display order), which keeps the decode
simple.

## Audio -> Opus

Blur's sounds are inside the PAK2 files: blur-nx (2026-11-21) says its music and sound banks are XMA, the .baf banks in
root.pak / root_streaming.pak (codec 25), not Ogg (the raw files' few Ogg pages are something else). So the XMA path
below applies, with a .baf parser in the installer and the banks reached through the PAK2 entries:
- XMA (XMA1 or XMA2): culdcept-nx's method (the game sees its XMA, each packet tagged; the XMA emulation takes each
  frame's 512 samples from Opus): culdcept-nx's `sdk/include/rex/filesystem/xmo.h`, `sdk/src/filesystem/xmo.cpp`,
  `sdk/src/audio/xma_context.cpp` DecodeXmoFrame, `sdk/src/audio/xmo_opus.*`; sasrt-nx's multi-sound container
  `NAME.xmop` (same files in sasrt-nx's sdk, 2026-11-21: segments + a sound table, 24 kHz Opus and 44.1 kHz sounds
  resampled from 48 kHz) when many sounds share a file. A sound must be tagged only in packets a frame starts in (a fix
  culdcept-nx's synthesis lacks; sasrt-nx's PacketMaker::Synthesize has it).
- Ogg Vorbis decoded by the game's own code: Opus would need a hook at the game's Vorbis decoder instead (the XMA path
  does not apply).

## Status on SASRT's side (2026-11-21 ~23:15)

SASRT's packing, H.265 movies and .xmop audio are written and building; not yet run. sasrt-nx-installer (a copy of
rr6-nx-installer with culdcept-nx's XMA pieces) is at D:\sonic transformed\sasrt-nx-installer. Ask the "sonic racing"
session for results.
