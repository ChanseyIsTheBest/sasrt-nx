# LZ4 / ZXC packing, H.265 movies and Opus audio for kameo-nx's installer and port (from sasrt-nx, 2026-11-22)

The user (2026-11-22): "Could you help kameo with l4z/zxc and rencoding video and audio". What Kameo has (measured
read-only from D:\kameo\game, the 5.4 GB folder), what the other ports did, and what is new for Kameo. Read the other
repos' working trees only.

Kameo is Rare's, like banjo-nx (N&B) and vivapinata-nx (Viva Pinata), both of which did this on 2026-11-21/22: their
notes are the nearest models for the audio and the packing (banjo-nx-ult/docs/media-compression.md; vivapinata-nx
commit 7bc7eb64). Kameo's movies are **Bink**, not WMV: **blur-nx has done Bink 1 -> H.265** (its 1.0.1, console-run;
the user, 2026-11-22: "Blur is bink"): start the movies from `D:/blur/blur-nx` (below).

## Kameo's game files (5.4 GB)

| Files | Count | Size | zlib-1 (six 2 MB slices of each) | What to do |
|---|---|---|---|---|
| `fmv/*.bik` (Bink 1, "BIKi") | 64 | 2,509 MB | | H.265 (below): new. Video 2,360 MB, Bink audio 149 MB (5.9 %) |
| `audio/*.xwb`, `<language>/*.xwb` (XACT, version 23) | 200 | 1,392 MB | | Opus as sasrt-nx's / vivapinata-nx's `.xmop` (below) |
| `*.lvl` | 68 | 1,554 MB | 105 % | as they are (compressed already) |
| `*.plf` | 112 | 50 MB | 59 % | LZ4 / ZXC: ~20 MB |
| `*.mdl` | 13 | 11 MB | 105 % | as they are |
| `*.str` | 9 | 4 MB | 44 % | LZ4 / ZXC |
| default.xex / .xexp, ssf, kad, xgs, bin | | ~6 MB | | as they are |

So packing saves little (~25 MB); the movies (1.5 GB or more smaller) and the audio (hundreds of MB) are the parts that
matter. Pack the re-encoded movies with ZXC too (the user's rule for every port: small, kept).

## What it would save (estimate, 2026-11-22; nothing encoded yet)

| Part | Now | After | Saved | From |
|---|---|---|---|---|
| Movies (64 Bink 1) | 2,509 MB | ~670 MB | ~1.8 GB | blur-nx's tools/bik_hevc_pack.py default `--fraction 0.22` (H.265 at 22 % of the source's bitrate) on the 2,360 MB of Bink video = ~520 MB, plus the 149 MB of Bink audio tracks stored as they are; ZXC around them a few % more (1-9 % on sasrt-nx's .hevc) |
| Audio (200 XACT banks, XMA1) | 1,392 MB | ~540-860 MB | ~0.5-0.85 GB | the other ports' Opus results: sasrt-nx's 44.1 kHz voices kept 39 % (80.6 -> 31.5 MB), its music 54 %, vivapinata-nx's XACT 2 banks 62 % (1,318 -> 813 MB); Kameo's look like ~108 kbit/s mono / ~200 kbit/s stereo XMA at 44.1 kHz (if the XACT 1 reading of the format word holds) |
| Packing (LZ4 / ZXC) | .plf 50 MB, .str 4 MB | | ~25 MB | zlib-1 samples 59 % / 44 %; the .lvl (1,554 MB), .mdl and xex are compressed already |
| **All** | **5.4 GB** | **~2.8-3.1 GB** | **~2.4-2.7 GB (about half)** | |

The movies are both the largest and the surest part (blur-nx's path is console-run on the same Bink 1); the audio's
range depends on the bitrates chosen (sasrt-nx: music 128 kbit/s stereo) and on how many sounds stay XMA (a sound whose
Opus is not smaller, or with too few tag bits).

## Packing (LZ4 and ZXC)

- **Port (sdk):** kameo-nx's SDK has no `.lz4b` reader yet (sdk/src/filesystem has no lz4_blocks.cpp). Take rr6-nx's
  `sdk/src/filesystem/lz4_blocks.cpp`, `include/rex/filesystem/lz4_blocks.h` (version 1 LZ4, version 2 ZXC blocks),
  `sdk/thirdparty/lz4`, `sdk/thirdparty/zxc`, the `rexblockcodecs` block of its `sdk/src/filesystem/CMakeLists.txt`,
  and its `sdk/src/filesystem/devices/host_path_*` (NAME.lz4b answers for NAME; AnswerRank; VFS index version 2).
  sasrt-nx took exactly these on 2026-11-21 (Ryujinx: a 3.1 GB archive read from a 1.39 GB .lz4b, no errors).
- **Installer:** kameo-nx-installer has no lib/lz4b.js. rr6-nx-installer's / culdcept-nx-installer's `lib/lz4b.js` and
  `wasm/lz4.*`, `wasm/zxc.*`, the packing worker: LZ4 HC 9, 256 KB blocks for what loads read, ZXC 7, 512 KB blocks for
  the rest. Banjo's rules for what to skip by first bytes (compressed bundles, the xex) carry over; here the .lvl, .mdl.
  vivapinata-nx's note: the Claude app's built-in browser refuses nested workers (test in Chrome or Edge).

## Movies (Bink 1 -> H.265): blur-nx's path

All 64 are Bink 1 ("BIKi"), 66.5 minutes: 37 at 720x480 (29.97 fps), 27 at 1280x720 (29.97); each with 2 to 12 Bink
audio tracks (mono 44.1 kHz binkaudio_dct: the language tracks). kameo-nx plays them through the game's own
recompiled Bink library (its GPU blit: kameo-notes.md's Bink shaders vs_2180EAECD26216DB / ps_9F19B02671FA1600 /
ps_0A24E04301CCDBB8).

**blur-nx's Bink path (Blur's movies are Bink 1 too, played the same way):** `D:/blur/blur-nx/app/src/cpu/
blur_bink_hevc.cpp` (keys blur_hevc_movies / _nvdec / _log / _decode_priority), `tools/bik_hevc_pack.py`, and the
installer's `D:/blur/blur-nx-installer/lib/biks.js` (with lib/xmop.js, audio.js, resample.js: Blur took
.xmop for its audio too). NAME.bik.hevc (rr6-nx's sfd_hevc container, which is
container-agnostic: segments of stored bytes, zeros and tag bytes): the game sees NAME.bik as it was, but each frame's
video data is zero except a 10-byte tag at its start. The hook is Bink 1's video decode (in Blur sub_82AFF648, called
from BinkDoFrame's worker with the frame buffers, the video data and its end): with tagged data it decodes nothing,
writes the H.265 picture of the tag's frame into the plane set Bink would have decoded into (Y, then U into cB and V
into cR; it decodes from set FrameNum into FrameNum ^ 1 when that set has a Y buffer), marks the written rows' store
cards so the renderer takes them again, and returns 0. **Blur's console trap:** by the time the video decode runs,
Bink has byte-swapped the frame's packet in 32-bit words (its bit reader's order), so the tag must be read back through
that swap (blur's FindTag; two green console runs before it was found). Kameo's Bink is an older RAD build (2005):
find its BinkDoFrame / video decode by the same shape (blur-nx's comment lists the calls) and check the
BINKFRAMEBUFFERS layout. Kameo also has 720x480 movies (Blur's are 1280x720 only).

The general design (the same as blur-nx's, and sasrt-nx's CRI USM path before it):
- **The file** (as rr6-nx's RXSFDH01 `.sfd.hevc` / sasrt-nx's `.usm.hevc`, sdk/include/rex/filesystem/sfd_hevc.h): the
  game sees its .bik byte for byte, but each frame's video data is a small tag (movie id, frame index) and zeros;
  the header, the frame index and the audio packets are stored as they were (a Bink frame: per audio track a u32 size
  and its packet, then the video data), so offsets and the audio do not change. The H.265 frames are stored beside them
  (Bink 1 has no B frames: decode order = display order, simpler than SASRT's MPEG-1, which needed a 5-picture cache).
  On disk it is the stored bytes + the H.265: the zeros cost nothing.
- **The port:** a hook at the game's Bink video decode (the function that decodes one frame's video data into Bink's
  YUV planes, under BinkDoFrame): find the tag, take that frame's picture from H.265 (culdcept-nx's
  `tools/switch/nxvideo`: FFmpeg 7.1 + nvtegra on NVDEC; the CMake block as rr6-nx's `RR6_NXVIDEO` / sasrt-nx's
  `SASRT_NXVIDEO`) and write its planes where Bink's would go, so the game's blit and BinkGetFrameBuffers stay as they
  are. sasrt-nx's `app/src/cpu/sasrt_usm_ffmpeg.cpp` (FindHevcTag, the read-ahead thread, HevcDecoder, the keys
  sasrt_hevc_movies / _nvdec / _decode_priority / _log) is the code to copy the shape from.
- **Installer / PC tool:** FFmpeg decodes Bink 1 (`binkvideo`; `--enable-decoder=bink` in the WebAssembly build, as
  culdcept-nx's wasm/wmv3 is built for WMV3), WebCodecs' H.265 encodes it (banjo-nx's and culdcept-nx's movie workers:
  35 % of the source's bitrate there; Bink 1 is far less efficient than WMV3, so a lower share should hold: measure
  PSNR as sasrt-nx's tools/hevc_usm_pack.py `--check` does). Keep the Bink audio tracks as they are (149 MB); Opus for
  them would need a second hook in Bink's audio decode, for 5.9 % of the movies.
- rr6-nx's traps: nxv_decode at priority 0x2C; frames read ahead on a libnx thread (threadCreate, not std::thread);
  Ryujinx has no H.265 NVDEC (test with the software decoder; banjo-nx's first NVDEC movie under Ryujinx gave empty
  pictures).

## Audio (XACT version 23, all XMA1 -> Opus)

Measured over the 200 banks (46,810 sounds; the most in one bank 906):
- **Every sound is XMA**, whole 2048-byte packets. Kameo's banks are XACT version 23 (vgmstream lists Kameo as v23,
  XACT 2.0); like Viva's 38-40 the five segments start at byte 8 (bank data, entry meta of 24 bytes, seek tables,
  names, wave data). **The format word is not XACT 3's layout:** read as XACT 3's (tag 2 bits, channels 3, rate 18)
  46,555 sounds look like "tag 3, 0 channels, 22,050 Hz". Read as XACT 1's (format 1 bit, channels 3, rate 27) the same
  words are XMA mono 44,100 Hz (0x800AC443) and XMA stereo 44,100 Hz (0x800AC445, 255 sounds, the music: D_AirShip's
  ...), which fits the durations (~108 kbit/s mono, ~200 kbit/s stereo). Confirm with one decode at each rate before
  trusting either (the game's own XACT reader in the generated code settles it).
- **XMA1, not XMA2** (a 2005 launch title): the packet header's first frame offset and skip are where XMA2 has them
  (bits 26-12 and the low 11), so `.xmop`'s tag-bit walk (XmoTagBits) applies; the installer decodes with FFmpeg's
  `xma1` decoder (not `xma2`). kameo-nx's XMA emulation already plays them.
- **The method:** sasrt-nx's `.xmop` (the game keeps its XMA; each sound's packets carry a 72-bit tag; the SDK's XMA
  emulation takes a tagged frame's 512 samples from Opus): sasrt-nx's `sdk/include/rex/filesystem/xmo.h` (the spec),
  `sdk/src/filesystem/xmo.cpp`, `sdk/src/audio/xma_context.cpp` + `include/rex/audio/xma/context.h` (culdcept-nx's
  DecodeXmoFrame: 44.1 kHz sounds from 48 kHz Opus through a 16-tap polyphase 160/147 resampler), `sdk/src/audio/
  xmo_opus.*`, libopus (switch-libopus), the host_path lookup of NAME.xmop. vivapinata-nx did it for XACT 2 banks the
  same day (1,318 -> 813 MB, 24,158 of 24,391 sounds as Opus; ids 0x56000000 | bank << 12 | sound): its XACT reader
  is the one to start from. Installer: sasrt-nx-installer's lib/xmop.js, culdcept-nx-installer's XMA pieces, Viva's
  XACT reader. The traps: tag only the packets a frame starts in; a sound with fewer than 72 tag bits in such a packet
  stays XMA.
- What sasrt-nx's audio became for scale: music (XMA2 48 kHz stereo 240 kbit/s -> Opus 128) 320.7 -> 173.5 MB;
  voices 80.6 -> 31.5 MB.

## What to copy from (2026-11-22)

- sasrt-nx: `D:\sonic transformed\sasrt-nx\docs\media-compression-1121.md`, the files named above,
  `tools/hevc_usm_pack.py` (USM demux + packer + PSNR check: the shape of a .bik packer), and
  `D:\sonic transformed\sasrt-nx-installer`.
- banjo-nx: `D:\Banjo kazooie port\banjo-nx-ult\docs\media-compression.md`, `tools/pack_game_root.py` (it refuses a
  linked game_root: pack a copy, never the master); `D:\Banjo kazooie port\banjo-nx-installer` (branch media-pack).
- vivapinata-nx: `D:\viva pinata\vivapinata-nx` (commit 7bc7eb64: the XACT 2 .xmop).
- rr6-nx: the SDK's .lz4b / ZXC / host_path pieces, sfd_hevc; culdcept-nx (D:\culdceptsaga): .xmo, nxvideo.
Ask the "sonic racing" session (sasrt-nx) about .xmop and the USM-style movie hook.
