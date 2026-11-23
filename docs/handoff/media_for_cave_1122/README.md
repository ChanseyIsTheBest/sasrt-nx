# LZ4 / ZXC packing, Opus audio and H.265 movies for the three Cave ports (from sasrt-nx, 2026-11-22)

The user (2026-11-22, to the sasrt-nx "sonic racing" session): "Wake up the mushimesama session and send it all the
compression information please about all three games". The three: **Mushihimesama Futari** (futari-nx, its DLC),
**Guwange** (guwange-nx) and **Ketsui: Kizuna Jigoku Tachi** (ketsui-nx), all under D:\mushihemesama. What each game
folder holds, what it would save (measured read-only on 2026-11-22), and where the code to copy lives in the other
ports. Read the other repos' working trees only.

None of the three ports or installers has any of this yet. Their SDKs' `sdk/src/filesystem` have no `lz4_blocks.cpp`,
`opus_pcm.cpp` or `xmo.cpp`. Their installers' `lib/` have no `lz4b.js`, `opcm.js` or `xmo.js`. The three come from
one lineage (futari-nx's SDK and installer), so each piece can be done once and copied into the other two.

## The savings

The packing figures are measured: LZ4 HC 9 in 256 KB blocks and ZXC 7 in 512 KB blocks, every file over 64 KB, with
the installers' rule that a file packing to 95 % or more is kept as it is. Two measurements were run:
- with sasrt-nx-installer's own `wasm/lz4.mjs` and `wasm/zxc.mjs` in memory (scratch script zxc_measure.mjs), and with
  Python's lz4 for LZ4;
- Guwange also with the installer's packer, `test/pack_node.mjs --codec zxc`.
The audio and movie figures are **estimates** from the other ports' results. The best codec is used for each kind of
file.

| Game | Folder | Now | After | Saved | Where it comes from |
|---|---|---|---|---|---|
| **Ketsui** | ketsui-src/game | 841 MB | **~170 MB** | **~670 MB (80 %)** | its textures pack to 13 % with LZ4 (742 -> 99 MB); music XMA2 -> Opus |
| **Mushihimesama Futari** | game | 810 MB | **~525 MB** | **~285 MB (35 %)** | its music is raw PCM (189 MB -> ~17 MB as Opus); packing ~113 MB with ZXC |
| Futari DLC | dlc/00000002 | 263 MB | ~216 MB | ~46 MB | packing only (ZXC; LZ4 ~30 MB) |
| **Guwange** | guwange-src/game | 107 MB | **78 MB** | **29 MB (27 %)** | packing only, ZXC (its ROMs) |
| **All** | | **~2.0 GB** | **~0.99 GB** | **~1.03 GB (about half)** | |

Earlier figures that used LZ4 alone said Futari ~560 MB and its DLC ~233 MB. ZXC packs Futari's archives smaller
(80 % against 87 %).

## Ketsui (841 MB -> ~170 MB)

| Files | Count | Size | Packed (measured) | What to do |
|---|---|---|---|---|
| `Data/Graphics/**/*.tex`, `Data/cg/*.tex` (uncompressed textures; 194 in Graphics/Gallery) | 213 | 741.7 MB | LZ4 99.2 MB (13.4 %), ZXC 109.7 MB (14.8 %) | pack with **LZ4**: most of Ketsui's saving |
| `Data/sd/MOD/*.xma` (RIFF WAVE, XMA2: fmt 0x0166, 48 kHz stereo, ~197 kbit/s) | 40 | 62.8 MB | (zlib 104 %) | Opus: ~41 MB **(estimate)** |
| `Data/Graphics/5pb.wmv`, `title.wmv` (WMV3 1280x720, 18 s together) | 2 | 7.1 MB | | H.265: ~2.5 MB **(estimate)**; optional |
| `Data/*.ttf` | 1 | 3.1 MB | ZXC 1.7 MB (53 %), LZ4 2.0 MB | pack |
| `Data/*.rom` | 2 | 2.6 MB | ZXC 2.0 MB (78 %), LZ4 2.2 MB | pack |
| default.xex (14.9 MB), `$SystemUpdate` (7.6 MB), nxeart (1.1 MB) | | 23.6 MB | 91-100 % | as they are |

Order: **1. packing** (~640 MB of the 670, and it needs no audio work); **2. the music** (~22 MB);
**3. the movies** (~4.6 MB, last or never).

**The textures want LZ4, not ZXC.** They are mostly runs of zeros and repeats, and LZ4 HC 9 beats ZXC 7 on them:
99.2 against 109.7 MB. LZ4 also decodes ~3x faster. The other files are smaller with ZXC, but they are only ~7 MB.

- **The music: one XMA2 file a track.** That is culdcept-nx's `.xmo` case (one XMA file -> NAME.xmo, the game reads
  NAME as it was, each packet tagged, the frames' samples from Opus). **But culdcept-nx's installer writer takes XMA1
  only**: `culdcept-nx-installer/lib/xmo.js` refuses anything else ("'-3': 'not XMA1'"). Ketsui's files are XMA2
  (WAVEFORMATEX tag 0x0166, a 52-byte XMA2WAVEFORMATEX fmt chunk, one stereo stream).
  - The packets and frames are the same in XMA1 and XMA2. Only the fmt chunk differs: XMA2's has the block count, the
    loop and the bytes-per-block fields.
  - So the change is in the RIFF reader (take fmt 0x0166, check one stream) and in the decode: FFmpeg's `xma2` decoder
    in place of `xma1`, or `xma1` with the packets as they are.
  - sasrt-nx's music is XMA2 48 kHz stereo too (in Wwise packages): its `.xmop` (sdk/include/rex/filesystem/xmo.h)
    has the same packet and tag walk. culdcept-nx's `DecodeXmoFrame` in the SDK's xma_context.cpp does not care which
    XMA it was.
  - Check by decoding one track both ways and comparing the PCM, then one in-game run.
  - For scale: sasrt-nx's XMA2 48 kHz stereo music at ~240 kbit/s became 54 % of its size as Opus 128
    (320.7 -> 173.5 MB). Ketsui's 197 kbit/s tracks at Opus 128 would be ~65 % (~41 MB).
- **The movies:** the XDK's XMV / WMV9 player (ketsui-nx's renderer already names IXMediaXmvPlayer). banjo-nx and
  culdcept-nx hook the XMedia WMV9 wrapper (banjo-nx-ult `app/src/cpu/banjo_wmv_ffmpeg.cpp`, from culdcept-nx's
  culdcept_wmv_ffmpeg.cpp; banjo-nx found its addresses by comparing its generated code with Culdcept's). It needs
  culdcept-nx's `tools/switch/nxvideo` (FFmpeg 7.1 + nvtegra), the installer's movie worker and a hook found for this
  game. All of that saves about 4.6 MB here, so it is the last item, and it can be skipped.

## Mushihimesama Futari (810 MB -> ~525 MB) and its DLC (263 MB -> ~216 MB)

| Files | Count | Size | Packed (measured) | What to do |
|---|---|---|---|---|
| `media/Sound/BGM.xwb` (XACT 3, version 46: 13 sounds, PCM 16-bit big-endian, 48 kHz stereo, 15.9 minutes) | 1 | 174.3 MB of PCM | | Opus as `.opcm`: ~15 MB **(estimate)** |
| `media/Sound/SYS_BGM.xwb` (1 sound, the same PCM) | 1 | 14.7 MB | | `.opcm`: ~1.2 MB **(estimate)** |
| `SE.xwb`, `SYS_SE.xwb`, `VOICE.xwb` (WMA already; 3 PCM effects, 0.1 MB) | 3 | 4.3 MB | | as they are |
| `media/Rom/cg_v102hi.bin`, `cg_v154hi.bin`, `cg_v102.bin`, `cg_v154.bin` (gallery art, "CXCG" archives) and `media/wall/wp01-13.bin` | 17 | 561.1 MB | ZXC 449.9 MB (80.2 %), LZ4 486.2 MB (86.6 %) | pack, ZXC |
| `AvatarAssetPack`, `nxeart` | 2 | 14.8 MB | ZXC 12.9 MB (87.5 %), LZ4 13.0 MB | pack |
| `media/Module/*.xex` (8), default.xex, `$SystemUpdate`, `media/motion/*.lzx` (11) | | 41 MB | 99-100 % | as they are |
| DLC `dlc/00000002/*.bin` | 4 | 262.7 MB | ZXC 216.4 MB (82.4 %), LZ4 233.1 MB (88.7 %) | pack, ZXC |

Order: **1. the music** (~172 MB); **2. packing**: ~113 MB for the game with ZXC (~77 MB with LZ4), ~46 MB for the
DLC with ZXC (~30 MB with LZ4). Futari has no movie files. With ZXC the game comes to **~525 MB** and the DLC to
**~216 MB** (the table at the top uses the LZ4 figures).

- **The music: raw PCM inside XACT wave banks** is exactly banjo-nx's case, done and Ryujinx-run (N&B's music,
  819.5 -> ~360 MB). It uses rr6-nx's **`.opcm`** format:
  - NAME.opcm is NAME with its PCM ranges kept as 48 kHz Opus and every other byte stored.
  - The SDK: rr6-nx's `sdk/include/rex/filesystem/opus_pcm.h`, `sdk/src/filesystem/opus_pcm.cpp`, `opus_decoder.*`,
    and the host_path lookup (NAME.opcm before NAME before NAME.lz4b). Console-tested in rr6-nx on 2026-11-21.
  - The tools: banjo-nx-ult's `tools/xwb_opcm_pack.py` (FFmpeg's libopus), and the installer's `lib/opcm.js`
    (rr6-nx-installer's) with banjo-nx-installer's XACT wave bank finder.
  - Banjo's banks are XACT 3 versions 42-46 with big-endian 16-bit PCM. Futari's are version 46 with big-endian 16-bit
    PCM (checked: sample-to-sample steps ~2,100 read big-endian, ~22,400 little-endian), so the finder should take them
    unchanged.
  - Futari's music is already 48 kHz: no resampling.
- **The packing:** the gallery archives look compressed already (zlib samples 95-97 %), but whole-file runs still take
  20 % off with ZXC (13 % with LZ4); the wallpapers pack better. The gallery art is read when the gallery opens, so
  ZXC (smaller) suits it, and the DLC's bins the same. Use LZ4 for anything read during play.

## Guwange (107 MB -> 78 MB)

Measured with sasrt-nx-installer's own packer (ZXC 7 in 512 KB blocks against LZ4 HC 9 in 256 KB blocks):

| File | Size | ZXC | LZ4 HC |
|---|---|---|---|
| `game_res/rom/gs001.bin` | 24.0 MB | 5.6 MB (23.5 %) | 5.7 MB |
| `game_res/rom/gb001-003.bin` | 16.0 MB | 8.7 MB | 9.0 MB |
| `game_res/rom/gp001-002.bin` | 2.0 MB | 0.9 MB | 1.0 MB |
| `res/DSD000.bin`, `DSD100.bin`, `DSD200.bin` | 32.0 MB | 29.7 MB (92-93 %) | 30.6 MB (95.5 % for DSD200: kept as it is by the 95 % rule) |
| `module/*.dll` (4 game modes: encrypted / compressed XEX2 modules) | 30.8 MB | 100 % | 100 % |
| default.xex | 2.4 MB | as it is | as it is |
| **All** | **107 MB** | **78 MB** | **79 MB** |

- **Packing is the only saving.** Guwange has no movies and no separate audio files: its sound is inside the arcade
  ROMs, which the emulated hardware reads directly. They can only be packed, never re-encoded.
- **The DLLs:** the four game-mode DLLs share no 64 KB block with each other, so neither packing nor deduplication
  helps. Copy them as they are, like default.xex.
- ZXC beats LZ4 by ~1 MB here, mostly on the DSD files. The ROMs load at a mode's start, so ZXC for all of it is fine.

## How: packing (`.lz4b` versions 1 and 2)

- **The format** (rr6-nx's `lz4_blocks.h` has the spec): NAME.lz4b answers for NAME, with NAME's size, and a plain
  NAME next to it wins. It is little-endian:
  - a 32-byte header: "RXLZ4BLK", the version (1 = LZ4 blocks, 2 = ZXC blocks), the block size, the held file's size,
    the block count;
  - the blocks back to back (a block whose stored size equals its length is stored as it is);
  - a u32 index of the stored sizes;
  - a 16-byte footer: the index's offset and "RXLZ4END".
  A read decompresses only the blocks it covers.
  - The installers use LZ4 HC 9 in 256 KB blocks for what loads read (~590 MB/s to decode on the console), and ZXC 7
    in 512 KB blocks for the rest (~200 MB/s).
  - ZXC usually comes out smaller: Banjo 72.4 % against LZ4's 74.2 %; Futari's bins 80 % against 87 %. Not always:
    Ketsui's textures are 14.8 % with ZXC against 13.4 % with LZ4. Measure each kind of file and pick per kind, as
    `codecFor` does.
- **Port (SDK):** take rr6-nx's pieces (sasrt-nx took exactly these on 2026-11-21; Ryujinx read a 3.1 GB archive from a
  1.39 GB .lz4b with no errors):
  - `D:\ridge racer 6\rr6-nx\sdk\src\filesystem\lz4_blocks.cpp` and `sdk\include\rex\filesystem\lz4_blocks.h`;
  - `sdk/thirdparty/lz4`, `sdk/thirdparty/zxc`;
  - the `rexblockcodecs` block of its `sdk/src/filesystem/CMakeLists.txt`;
  - its `sdk/src/filesystem/devices/host_path_*`: the lookup, AnswerRank, the VFS index version 2.
  The ultimate base is taking the same SDK pieces from rr6-nx now ("part 4", 2026-11-22), so a later base sync would
  bring them too.
- **Installer:** rr6-nx-installer's (or culdcept-nx-installer's) `lib/lz4b.js`, `wasm/lz4.*`, `wasm/zxc.*` and the
  packing worker. CODECS: lz4 version 1, 256 KB blocks, level 9; zxc version 2, 512 KB blocks, level 7. `codecFor`
  picks a codec per file, or null to copy it.
  - sasrt-nx-installer's `test/pack_node.mjs` packs files the way the page does, for test runs:
    `node test/pack_node.mjs OUT --codec zxc FILES`.
  - Test the page in Chrome or Edge: the Claude app's built-in browser refuses nested workers (vivapinata-nx's note).
  - Never pack a linked game folder in place: pack a copy (banjo-nx's tools/pack_game_root.py refuses a link).

## How: audio

- **Raw PCM in XACT banks -> `.opcm`** (Futari): rr6-nx's format, banjo-nx's XACT tools (above).
  `D:\Banjo kazooie port\banjo-nx-ult\docs\media-compression.md` has the whole run, including the open time to trim
  (0.8-1.1 s for the tables of a 500 MB bank).
- **One XMA file -> `.xmo`** (Ketsui): culdcept-nx's.
  - The spec is `D:\culdceptsaga\culdcept-nx\sdk\include\rex\filesystem\xmo.h`; the code is `sdk/src/filesystem/xmo.cpp`
    and the SDK's `sdk/src/audio/xma_context.cpp` (XmaContext::DecodeXmoFrame); also `tools/xmo_compare.py` and
    `tools/test_xmo.cpp`.
  - The installer side is `culdcept-nx-installer/lib/xmo.js` and `audio.js`; it is XMA1-only, see Ketsui above.
  - libopus is devkitPro's switch-libopus.
  - The traps sasrt-nx found:
    - tag only the packets a frame starts in (culdcept-nx's 1.0.1 has the fix);
    - a file with fewer than 72 tag bits in such a packet stays XMA.
- **Many XMA sounds in one package -> `.xmop`**: sasrt-nx's, used by vivapinata-nx and kameo-nx for XACT banks. Not
  needed here (no XMA wave banks in these three), but it is the XMA2 precedent.

## How: movies (Ketsui only, optional)

- WMV3 -> H.265 in the same ASF, the original packet layout kept: culdcept-nx's / banjo-nx's path.
  - The installer: banjo-nx-installer's movie_worker.js, `lib/movies.js` and `lib/asf.js`. FFmpeg's WMV3 decodes in
    WebAssembly; WebCodecs' H.265 encodes at 35 % of the bitrate, a keyframe every 120 frames.
  - The port: the XMedia WMV9 hook and `tools/switch/nxvideo`.
  - The re-encoded file packed with ZXC as well (the user's rule for every port).
- rr6-nx's traps:
  - nxv_decode at priority 0x2C;
  - frames read ahead on a libnx thread (threadCreate);
  - Ryujinx has no H.265 NVDEC, so test with the software decoder.

## What to copy from (2026-11-22)

- rr6-nx (`D:\ridge racer 6\rr6-nx`, `rr6-nx-installer`): lz4_blocks, opus_pcm / opus_decoder, host_path_*,
  lib/lz4b.js, lib/opcm.js.
- banjo-nx (`D:\Banjo kazooie port\banjo-nx-ult`, `banjo-nx-installer` branch media-pack): docs/media-compression.md,
  tools/xwb_opcm_pack.py, tools/pack_game_root.py, the XACT finder, the movie path.
- culdcept-nx (`D:\culdceptsaga\culdcept-nx`, `culdcept-nx-installer`): .xmo, nxvideo, the WMV9 hook's origin.
- sasrt-nx (`D:\sonic transformed\sasrt-nx`, `sasrt-nx-installer`): docs/media-compression-1121.md, .xmop (XMA2),
  test/pack_node.mjs.

Questions: the "sonic racing" session (sasrt-nx) for packing and the XMA tags, the banjo session for `.opcm` in XACT
banks and the movies.
