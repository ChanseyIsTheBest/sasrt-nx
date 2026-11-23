# LZ4 / ZXC packing, H.265 movies and Opus audio for vivapinata-nx's installer and port (from sasrt-nx, 2026-11-22)

The user (2026-11-22): "please help viva pinata have l4z and zxc in its web isntaller and rencode video and audio to
opus and h265 tell it to look at banjo since same developer". What Viva Pinata has (measured read-only from
D:\viva pinata\game\Beta), what the other ports did, and what is new for Viva. Read the other repos' working trees only.

**Start from banjo-nx (Rare's too, the same file kinds): `D:\Banjo kazooie port\banjo-nx-ult\docs\media-compression.md`**
and its installer `D:\Banjo kazooie port\banjo-nx-installer` (branch `media-pack`): it has done the packing, the
movies (WMV3 in ASF -> H.265, culdcept-nx's path) and the XACT wave bank music, end to end in Chromium and Ryujinx.

## Viva Pinata's game files (4.9 GB)

| Files | Count | Size | zlib-1 (sampled across each file) | What to do |
|---|---|---|---|---|
| `movie/*` (ASF, 30 26 B2 75) | 48 | 1,600 MB | ~100 % | H.265 as banjo-nx does: Banjo's 52 went to 37 % (1,155 -> 427 MiB) |
| `xwavebank/*`, `xwavebankloc/<16 languages>/*` (XACT 'DNBW') | 268 | 1,319 MB | ~100 % | Opus as sasrt-nx's `.xmop` (below): new |
| `bundles_packages/*.pkg` (00 00 00 01 ...) | 615 | 1,293 MB | 105 % | as they are (compressed already) |
| `debug/debug_pack.bin` (Rare's CAFF, "CAFF07.08.06.003") | 1 | 739 MB | ~80 % | LZ4 / ZXC: ~150 MB |
| `debug/debug_hash.bin`, `fontcachesbm/*`, `bundles/*.bnl` | | ~57 MB | 102-104 % | as they are |
| `debug/db_index.txt`, default.xex, ini, png | | ~6 MB | | as they are or packed |

So packing alone saves little here (the bundles are compressed, as banjo-nx's Bundle/4f are): ~150 MB, nearly all the
CAFF debug pack. The movies (~1 GB smaller) and the audio (several hundred MB) are the big parts.

## Packing (LZ4 and ZXC)

- **Port (sdk):** vivapinata-nx has the base's version 1 (LZ4) reader (`sdk/src/filesystem/lz4_blocks.cpp`) and
  `tools/lz4b_pack.py`. For ZXC: rr6-nx's `sdk/src/filesystem/lz4_blocks.cpp` / `include/rex/filesystem/lz4_blocks.h`
  (version 2 = ZXC blocks), `sdk/thirdparty/zxc`, the `rexblockcodecs` block of its `sdk/src/filesystem/CMakeLists.txt`,
  and its `sdk/src/filesystem/devices/host_path_*` lookup (NAME.lz4b answers for NAME; AnswerRank; VFS index version 2).
  sasrt-nx took exactly these on 2026-11-21 (Ryujinx: a 3.1 GB archive read from a 1.39 GB .lz4b, no errors).
- **Installer:** there is no vivapinata-nx installer yet. banjo-nx-installer is the one to copy (Rare's formats: its
  lib/stfs.js, xiso.js, lz4b.js, asf.js, movies.js, the packing worker; the CAFF and ASF first-byte rules in
  media-compression.md). For ZXC, rr6-nx-installer's / culdcept-nx-installer's `lib/lz4b.js` with `wasm/zxc.*` (pack()
  with codec 'zxc'): LZ4 HC 9, 256 KB blocks for what loads read; ZXC 7, 512 KB blocks for the rest.

## Movies (WMV3 in ASF -> H.265)

All 48 are WMV3 1280x720 (30 at 23.976 fps, 8 at 29.97, 6 at 59.94, 4 at 30), 28.0 minutes in all; audio WMA 2 stereo
(one WMA Pro 5.1, three without sound). The same as banjo-nx's movies, so its path applies:
- **Port:** banjo-nx-ult's `app/src/cpu/banjo_wmv_ffmpeg.cpp` (culdcept-nx's culdcept_wmv_ffmpeg.cpp: the XMedia WMV9
  wrapper's decode / get output / flush / destroy / GetData hooks; banjo-nx found N&B's by comparing its generated code
  with Culdcept's: the wrapper's offsets were the same). Viva Pinata is an older XDK, so check its wrapper the same way
  and find its addresses. `tools/switch/nxvideo` (FFmpeg 7.1 + nvtegra in one object, only `nxv_*` global; the CMake
  block: rr6-nx's `RR6_NXVIDEO`, sasrt-nx's `SASRT_NXVIDEO`); the SDK's FFmpeg with the WMV3 decoder on.
- **Installer:** banjo-nx-installer's movie_worker.js / lib/movies.js / lib/asf.js (culdcept-nx's): decoded by FFmpeg's
  WMV3 in WebAssembly, encoded by WebCodecs' H.265 at 35 % of the bitrate, a keyframe every 120 frames, written back
  into the ASF in the original muxer's packet layout (the XDK player paces by the packets' send times).
- **ZXC around them** (the user's rule, as for NiGHTS: "make sure ... ZXC compresses its videos"): the re-encoded ASF
  packed as `.lz4b` version 2 (ZXC 7, 512 KB blocks), NAME.lz4b, read through the generic lookup. Small (1-9 % on
  sasrt-nx's movies), kept.
- Traps (rr6-nx, banjo-nx): nxv_decode at priority 0x2C; frames read ahead on a libnx thread (threadCreate); Ryujinx
  has no H.265 NVDEC (test with the software decoder; banjo-nx's first NVDEC movie under Ryujinx gave empty pictures).

## Audio (XACT wave banks: all XMA -> Opus)

Measured (parser: banjo-nx-ult's tools/xwb_opcm_pack.py's, fixed for XACT 2, see below):

| Kind | Sounds | Size |
|---|---|---|
| XMA mono 22,050 Hz (voices: xwavebankloc's 16 languages, and effects) | 23,944 | 1,032.6 MB |
| XMA stereo 44,100 Hz (music) | 239 | 256.1 MB |
| XMA 4 channels 44,100 Hz | 4 | 21.4 MB |
| XMA mono 44.1 / 32 kHz, stereo 22 kHz | 55 | 0.7 MB |

No PCM at all, so banjo-nx's `.opcm` (raw PCM ranges as Opus) does not apply. What applies is sasrt-nx's **`.xmop`**
(SASRT's Wwise packages: many XMA sounds in one file): the game keeps reading its own XMA bytes, each sound's packets
carry a 72-bit tag in their frames' bits, and the SDK's XMA emulation takes a tagged frame's 512 samples from the
sound's Opus instead of decoding XMA (culdcept-nx's `.xmo` method, one file a sound; sasrt-nx's `.xmop`, many):
- **Port:** sasrt-nx's `sdk/include/rex/filesystem/xmo.h` (the format spec: segments of stored bytes / zeros /
  synthesized packets, a sound table, the tag), `sdk/src/filesystem/xmo.cpp`, `sdk/src/audio/xma_context.cpp` +
  `include/rex/audio/xma/context.h` (culdcept-nx's, DecodeXmoFrame: 48 / 24 kHz Opus decoded at its rate, a 44.1 kHz
  sound from 48 kHz Opus through a 16-tap polyphase 160/147 resampler), `sdk/src/audio/xmo_opus.*`, libopus (devkitPro's
  switch-libopus), the host_path lookup of NAME.xmop. **Viva's 22,050 Hz sounds:** Opus has no 22.05 kHz; make them at
  24 kHz and resample 24,000 -> 22,050, the same 160/147 ratio as 48,000 -> 44,100 (one more rate case in DecodeXmoFrame).
- **Installer:** sasrt-nx-installer's `lib/xmop.js` (the writer) with culdcept-nx-installer's XMA pieces (FFmpeg's XMA
  frames decoded in order, the frame table, the tag bits) and a new XACT reader instead of SASRT's Wwise one.
- **The XACT 2 wave bank (versions 38-40 here; banjo-nx's are 42-46):** big-endian 'DNBW', the version, and then the
  five segments (offset, length) from byte 8 (XACT 3 has a header version word first, segments from byte 12): bank data
  (flags, entry count, name[64], entry meta size 24, name size 64, alignment 2048), entry meta (24 bytes a sound: flags /
  duration, the format word, play offset and length in the wave data, loop start and length), seek tables, names, wave
  data. The format word read big-endian (banjo-nx's finding): tag 2 bits (1 = XMA), channels 3, rate 18, block align 8,
  bits 1. The XMA sounds are whole 2048-byte packets; check whether they are XMA1 or XMA2 (the packet headers differ
  slightly; FFmpeg decodes both) and how the 4-channel ones are laid out (likely 2 streams: keep them as XMA if it
  does not fit, as sasrt-nx keeps any sound whose Opus is not smaller).
- **Sound ids:** sasrt-nx's are 0x5A000000 | the package's place among the sorted paths << 16 | the sound's index;
  Viva needs its own (268 banks, up to some thousands of sounds each: check the counts fit 16 bits).
- What sasrt-nx's audio became: music (XMA2 48 kHz stereo 240 kbit/s -> Opus 128) 320.7 -> 173.5 MB; voices (44.1 kHz)
  80.6 -> 31.5 MB; all five language packages 187.6 -> 77.6 MB.
- The traps sasrt-nx found: tag only the packets a frame starts in (a packet no frame starts in has no tag bits;
  culdcept-nx's .xmo tagged a sound's last packet anyway, fixed in its 1.0.1); a sound with fewer than 72 tag bits in a
  packet a frame starts in stays XMA.

## What to copy from (2026-11-22)

- banjo-nx: `D:\Banjo kazooie port\banjo-nx-ult\docs\media-compression.md`, `app/src/cpu/banjo_wmv_ffmpeg.cpp`,
  `tools/hevc_movie.py`, `tools/pack_game_root.py` (it now refuses a linked game_root: pack a copy, never the master),
  `tools/xwb_opcm_pack.py`; `D:\Banjo kazooie port\banjo-nx-installer` (branch media-pack).
- sasrt-nx: `D:\sonic transformed\sasrt-nx\docs\media-compression-1121.md`, the files named above, and
  `D:\sonic transformed\sasrt-nx-installer` (lib/xmop.js and the XMA pieces).
- culdcept-nx (D:\culdceptsaga): the .xmo method and the movie path's origin.
Ask the "sonic racing" session (sasrt-nx) for anything about .xmop, and the banjo session about the movies.
