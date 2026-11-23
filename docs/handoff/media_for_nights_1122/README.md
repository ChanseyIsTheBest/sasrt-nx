# LZ4 / ZXC packing, H.265 movies and Opus audio for nights-nx's installer and port (from sasrt-nx, 2026-11-22)

The user (2026-11-22): "please help nights into dreams have l4z and zxc in its web isntaller and rencode video and
audio to opus and h265". What NiGHTS has (measured from D:\nights\game), what the other ports did, and what is new for
NiGHTS. Read the other repos' working trees only.

## NiGHTS's game files (2,141 MB)

| Files | Count | Size | zlib-1 on samples | What to do |
|---|---|---|---|---|
| `cse/**/*.ddm` (DDM) | 196 | 748 MB | 20 % | ZXC 7 / LZ4: ~600 MB saved |
| `afs/*.wmv` (ASF) | 22 | 540 MB | 102 % | H.265 as culdcept-nx does (below): ~350 MB saved |
| `afs/*.adx` (CRI ADX) | 214 | ~450 MB | 105 % | Opus: new (below) |
| `afs/*.BIN` (several kinds) | ~370 | ~290 MB | 24-48 % | ZXC / LZ4: ~170 MB saved |
| `afs/*.csb` (`@UTF`, CRI sound banks) | 22 | 65 MB | 101 % | audio inside (CRI; check their codec) |
| `cse/**/*.csa` (DBLK) | 1,690 | 8 MB | 10 % | ZXC / LZ4 (small files: maybe not worth a block container each) |
| `afs/*.dat`, xex, dds, png etc. | | ~25 MB | | as they are or packed |

## Packing (LZ4 and ZXC)

- **Port (sdk):** rr6-nx's `sdk/src/filesystem/lz4_blocks.cpp` / `include/rex/filesystem/lz4_blocks.h` (version 1
  LZ4 blocks, version 2 ZXC blocks), `sdk/thirdparty/lz4`, `sdk/thirdparty/zxc`, the `rexblockcodecs` block of its
  `sdk/src/filesystem/CMakeLists.txt`; the lookup in `sdk/src/filesystem/devices/host_path_*` (NAME.lz4b answers for
  NAME; AnswerRank; index version 2). sasrt-nx took exactly these on 2026-11-21 and they ran in Ryujinx on 2026-11-22
  (a 3.1 GB archive read from a 1.39 GB .lz4b, no errors).
- **Installer:** culdcept-nx-installer's / rr6-nx-installer's `lib/lz4b.js`, `wasm/lz4.*`, `wasm/zxc.*`, the packing
  worker and `game.json`'s `lz4` / `zxc` lists (LZ4 HC 9, 256 KB blocks for what loads read; ZXC 7, 512 KB blocks for
  the rest). nights-nx-installer has neither yet (lib: lzx.js, stfs.js, ... no lz4b.js).

## Findings from nights-nx (2026-11-22, after this handoff)

- **The movies are VC-1 advanced profile (fourcc WVC1), not Culdcept's WMV3**: B pictures, 29.97 fps, WMA Pro audio.
  Culdcept's hooks apply to NiGHTS's later XDK player build (decode sub_82453B20, output sub_82453B80, flush
  sub_82453A18, destroy sub_82453A70, GetData sub_82453758) with other statuses (no more output = 2, not 9; GetData's
  last chunk = 6, not 10); FFmpeg needs ff_vc1_decoder registered (and the installer's wasm `--enable-decoder=vc1`);
  for the B pictures: show the newest picture FFmpeg has given, drain a movie's first frame on its own, no picture for a
  1-byte skipped frame. FFmpeg then matched the game's decoder picture for picture on 4 movies (PC).
- **ADX: SA2's way applies unchanged**: NiGHTS's ADXT 11.39 step sub_823BAB70 is SA2's sub_828C2948 instruction for
  instruction; all 214 .adx are real ADX (encoding 3); 450 -> 143 MB at 128 kbit/s, lag 0; the PC run played the title
  and stage music from .adxo.
- **LZ4 vs ZXC** on the 1,093 MB of packable files: LZ4 HC 9 330 MB, ZXC 7 312 MB (ZXC smaller on .ddm/.bin/.csb/.dat);
  the PC ran the game from the packed folder into Spring Valley.

## Movies (WMV in ASF -> H.265)

(Written before the findings above: NiGHTS's are VC-1, see there.) culdcept-nx's path:
- **Installer:** culdcept-nx-installer's `lib/asf.js`, `wasm/wmv3` (FFmpeg's WMV3 decoder in WebAssembly),
  `movie_worker.js`, `game.json`'s `movies` (fraction 0.35, keyframe every 120); WebCodecs' H.265 encoder.
- **Port:** culdcept-nx's `app/src/cpu/culdcept_wmv_ffmpeg.cpp` (its H.265 path) and `tools/switch/nxvideo`
  (FFmpeg 7.1 + nvtegra in one object, only `nxv_*` global; the CMake block: rr6-nx's `app/CMakeLists.txt`
  `RR6_NXVIDEO`, sasrt-nx's `SASRT_NXVIDEO`). devkitPro's `switch-ffmpeg` with nvtegra is installed on this PC.
- rr6-nx's traps: nxv_decode at priority 0x2C; frames read ahead on a libnx thread (`threadCreate`, not std::thread);
  Ryujinx has no H.265 NVDEC (test with the software decoder); `tools/direct_calls.py --redo` after a new hook.
  sasrt-nx's movies ran in Ryujinx on 2026-11-22 (all 345 pictures of its intro from H.265, through the read-ahead).
- **ZXC around the re-encoded movies** (the user, 2026-11-22: "also make sure nights ZXC compresses its videos"):
  after the re-encode, the movie (an ASF with H.265 frames, as culdcept-nx writes it) packed as `.lz4b` version 2 (ZXC
  7, 512 KB blocks): NAME.wmv.lz4b, read through the port's generic .lz4b lookup (rr6-nx-installer's worker.js does the
  same for its .hevc: lib/lz4b.js pack() with codec 'zxc'). Small savings (SASRT 1-9 %, RR6 about a tenth), kept.

## Audio (CRI ADX -> Opus)

**Start from Sonic Adventure 2's port, which has done it (the user, 2026-11-22: "look at sonic adventure 2 and ridge
racer 6 since they have adx audio"):** sa2-nx-ult (D:\sonic adventure 2\sa2-nx-ult) `docs/opus-h265.md` "The audio:
NAME.adxo": `sdk/include/rex/filesystem/adx_opus.h` (rr6-nx's segment layout with runs of tagged ADX blocks),
`app/src/sa2_adx_opus.cpp` (the hook at ADXT 11.35's block decode, sub_828C2948: each tagged block's 32 samples from
the Opus, resampled to the stream's rate), `tools/adx_opus_pack.mjs` + `tools/adx_opus_lib.mjs` (shared with the
installer; ADX decoded as the game does). rr6-nx's `docs/opus-h265-handoff-sa2.md` has the ADX notes (what Opus saves
on ADX). The two ideas below were written before that pointer; SA2's hook is way 2, proven.

The XMA method (culdcept-nx's `.xmo`, sasrt-nx's `.xmop`: the game sees its XMA, each packet tagged, the XMA emulation
takes the samples from Opus) does not apply: ADX is decoded by CRI's library in the game's own code, not by an emulated
decoder. Two ways:
1. **Synthesize the ADX on read** (no game hook): NAME.adx.opus (or such) holds the ADX header as it was and the Opus;
   the port's file handle decodes the Opus and *encodes* ADX blocks (18 bytes = 32 samples a channel, 4-bit ADPCM with
   the header's coefficients) as the game reads them, so the game reads a valid ADX of the original size, its loops
   and timing untouched. ADX encoding is a few multiply-adds a sample; the cost is the Opus decode. Deterministic given
   the same Opus decoder, so block-by-block random reads work (decode from a pre-roll before the block, as
   culdcept-nx's DecodeXmoFrame does with 320 ms). Quality: Opus then ADPCM (the ADX's own quantization again).
2. **Hook CRI's ADX decoder** (the ADX library's block decode in the game's code): tag the ADX blocks as the XMA paths
   do and give the decoder PCM from Opus. Exact PCM, but a hook per decode path (ADX, and whatever .csb banks use).
rr6-nx's `.opcm` (its music was raw PCM: `sdk/include/rex/filesystem/opus_pcm.h`, NAME.opcm synthesizes the PCM from
Opus on read) is the closest model for way 1: the same synthesize-on-read handle, with an ADX encoder after the Opus
decode. Check the .csb banks' codec too (CRI cue sheets: ADX / AHX inside, possibly the same).

ADX at 48 kHz stereo is ~384 kbit/s (4 bits a sample): Opus at 96-128 kbit/s would cut the ~515 MB of ADX + CSB to
roughly a third.

## What sasrt-nx has to copy from (2026-11-22)

`D:\sonic transformed\sasrt-nx\docs\media-compression-1121.md` (the formats, the results, the Ryujinx runs);
sasrt-nx-installer at `D:\sonic transformed\sasrt-nx-installer` (rr6-nx-installer + culdcept-nx's XMA pieces + a USM
and Wwise reader). Ask the "sonic racing" session for anything.
