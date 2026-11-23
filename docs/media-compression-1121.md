# Smaller game files: LZ4 / ZXC, H.265 movies, Opus audio (2026-11-21)

The user (2026-11-21): "please compress all the videos and audio", "you can take them from culdcept directly its fine
as well as ridge racer 6", "also want you to copy culdcept saga web installer for encoding audio and video please and
compressing files with ZXC and L4Z". The port reads three kinds of re-made files beside (or in place of) the game's,
and sasrt-nx-installer (D:\sonic transformed\sasrt-nx-installer, a copy of rr6-nx-installer with culdcept-nx's XMA
pieces) makes them from the user's own game folder in the browser.

## What the game folder becomes (sasrt-nx-installer's node test on assets/game_root)

| File | Before | After | As |
|---|---|---|---|
| Data/GameAssets.M00 | 3,129.5 MB | 1,390.2 MB | `.lz4b` v1 (LZ4 HC 9, 256 KB blocks: read at load time) |
| Data/Frontend.M00 | 400.1 MB | 272.2 MB | `.lz4b` v1 |
| Data/GameData.M00 | 3.0 MB | 0.33 MB | `.lz4b` v1 |
| AvatarAssetPack, nxeart | 14.5 MB | 13.0 MB | `.lz4b` v2 (ZXC 7, 512 KB blocks) |
| Data/Movies/credits.usm | 426.3 MB | 160.0 MB | `.usm.hevc` (H.265, 35 % of the MPEG-1 bitrate; PSNR mean 42.1 dB, min 34.6) |
| Data/Movies/Drifting.usm | 179.7 MB | 65.6 MB | `.usm.hevc.lz4b` (PSNR mean 49.8, min 42.1) |
| Data/Movies/Gameclear.usm | 29.9 MB | 9.6 MB | `.usm.hevc.lz4b` (44.8 / 42.2) |
| Data/Movies/Logos.usm | 13.5 MB | 3.2 MB | `.usm.hevc.lz4b` (66.1 / 49.3) |
| Data/sound/StreamsMulti.pck | 320.7 MB | 173.5 MB | `.pck.xmop` (music: XMA2 48 kHz stereo 240 kbit/s -> Opus 128) |
| Data/sound/SoundBanks.pck | 129.3 MB | 113.1 MB | `.pck.xmop` (1,168 of 1,170 XMA sounds; its 98 MB of PCM stays) |
| Data/sound/StreamsEng.pck | 80.6 MB | 31.5 MB | `.pck.xmop` (44.1 kHz voices: Opus at 48 kHz, resampled back by the port) |
| Data/sound/Streams{Fra,Ger,Ita,Spa}.pck | 187.6 MB | 77.6 MB | `.pck.xmop` |
| default.xex, the .toc files | | | as they are |
| **All** | **4.7 GB** | **2.2 GB** | |

(credits.usm.hevc from tools/hevc_usm_pack.py; the installer packs it as `.hevc.lz4b` too. ZXC saves 1-9 % on SASRT's
`.hevc` files (Drifting 1.4 %, Gameclear 1.7 %, Logos 9 %) and under 5 % on the `.xmop` ones, which are left unpacked.
The user, 2026-11-21: keep the movies ZXC-packed.)

## The formats and the port's readers

- **`.lz4b`** (rr6-nx's, `sdk/include/rex/filesystem/lz4_blocks.h`): version 1 LZ4 blocks, version 2 ZXC blocks;
  `sdk/thirdparty/lz4`, `sdk/thirdparty/zxc` (`rexblockcodecs`).
- **`.usm.hevc`** (rr6-nx's RXSFDH01, `sdk/include/rex/filesystem/sfd_hevc.h`): the USM byte for byte but each
  picture's slice data (one slice header, a 10-byte tag: movie id and display index, zeros); the H.265 frames in
  display order. `app/src/cpu/sasrt_usm_ffmpeg.cpp`: the native slice loop takes the tagged slice; FinishPicture finds
  the tag and writes the H.265 picture of that index into the coded picture's planes, decoding forward and keeping up
  to 5 pictures for the B pictures MPEG asks for out of order (rr6-nx's decoder: culdcept-nx's nxvideo on NVDEC, a
  libnx read-ahead thread of 45 frames, nxv_decode at priority 0x2C). Keys: `sasrt_hevc_movies`, `sasrt_hevc_nvdec`
  (false on Ryujinx: no H.265 NVDEC there), `sasrt_hevc_decode_priority`, `sasrt_hevc_log`.
- **`.pck.xmop`** (new, `sdk/include/rex/filesystem/xmo.h`): a Wwise package with its XMA2 sounds in Opus: segments
  (stored bytes, zeros, a sound's synthesized packets) and a sound table; each sound's packets carry culdcept-nx's
  72-bit tag (sound id, packet index) in packets a frame starts in (a fix over culdcept-nx's .xmo, whose synthesis also
  tagged a sound's last packet when no frame starts in it). `sdk/src/filesystem/xmo.cpp` reads it (and culdcept-nx's
  `.xmo`); `sdk/src/audio/xma_context.cpp` DecodeXmoFrame (culdcept-nx's) takes a tagged frame's 512 samples from the
  sound's Opus: 48 kHz and 24 kHz Opus decoded at their own rate, 44.1 kHz sounds from 48 kHz Opus through a 16-tap
  polyphase resampler. Sound ids: 0x5A000000 | the package's place among the sorted .pck paths << 16 | the sound's index.
- **The lookup** (rr6-nx's, `sdk/src/filesystem/devices/host_path_*`): NAME.hevc[.lz4b], NAME.xmop[.lz4b] and NAME.xmo
  answer for NAME before NAME itself and NAME.lz4b; a plain NAME next to them wins (the VFS index version 2).

## Status

- Switch build `sasrt_m1` (out/console_runs/c1121_media_build): built, warning-free in the new code.
- **Ryujinx, run media1 (2026-11-22 00:01, out/ryujinx/media1.log; the SD's game_root junction pointed at
  out/installer_test/game_root by scratchpad ryu_media.ps1, `sasrt_hevc_nvdec = false`):** the .lz4b archives read
  (GameAssets 1,390 of 3,130 MB, LZ4; the movies' ZXC); Logos.usm.hevc played whole from H.265 (345 pictures, all
  through the read-ahead; FFmpeg 7.1's software decoder in nxvideo, ~53 ms a picture under emulation), Drifting opened;
  the three .xmop packages the game opened (StreamsEng, StreamsMulti, SoundBanks) registered their sounds and 38 sounds
  played from Opus (48 kHz, 24 kHz, and StreamsEng's 44.1 kHz voices resampled from 48 kHz Opus); 0 [xmo] / [hevc] /
  [lz4b] warnings. The input script reached menus and the attract mode, not a race.
- **Ryujinx, run media2 (00:15, race_ryujinx_slow.txt, 480 s):** through the menus into a race (1,400-1,700 draws a
  frame); sounds from Opus in all three packages at every rate (SoundBanks 24/48 kHz mono and stereo, StreamsEng's
  voices 24/44.1/48 kHz, StreamsMulti's music 48 kHz), 0 [xmo] / [hevc] / [lz4b] warnings, no Opus errors, the run to
  its end.
- **Build m2** (2026-11-22 01:01: the packet tag only where a frame starts; sasrt_m2.nro) **and Ryujinx run media3**
  (01:02, the same race): the same results, 0 warnings; Logos whole and Drifting's first 300 pictures from H.265.
- vivapinata-nx (2026-11-22) took .xmop for its XACT 2 wave banks (1,318 -> 813 MB, 24,158 of 24,391 sounds as Opus;
  22,050 Hz sounds from 24 kHz Opus through the same 160/147 resampler; its ids 0x56000000 | bank << 12 | sound). Its
  note for this installer: the Claude app's built-in browser refuses nested workers, so the pack_worker pool cannot run
  there end to end: test in Chrome or Edge.
- Next: the console when the user allows
  (NVDEC timing, load times, the audio heard), and sasrt-nx-installer in a real browser (WebCodecs H.265 and Opus,
  Opus at 24 kHz).
