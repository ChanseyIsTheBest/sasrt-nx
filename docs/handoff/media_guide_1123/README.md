# A media guide for the ultimate base (from sasrt-nx, 2026-11-23)

The user (2026-11-23, to the sasrt-nx "sonic racing" session): "could you please write a document how to re-encode
audio and video and how to compress files with l4z and zxc compression please give it to rr6 to put it in the ultimate
base make sure you include as many different audio format and video format details from the geames we have worked on".

- **`media-compression.md`** (this folder) is the document. It covers:
  - how a port re-encodes movies to H.265 and audio to Opus, and packs files with LZ4 / ZXC;
  - the formats the base's SDK reads (port 259);
  - every movie and audio format the ports have met: CRI SFD and USM, ASF with WMV3 and VC-1, Bink 1, raw PCM, RIFF
    XMA1/XMA2, Wwise, XACT versions 23-46, Blur's .baf, CRI ADX / AHX / CSB;
  - each game's measured results, the encoder settings, the traps, and where each piece of code lives.
- **Suggested place:** `base/docs/media-compression.md`, with a line pointing to it from `docs/building.md` where port
  259's readers are described (about line 172). It names no game data and no personal paths, only the D: port folders
  the base's docs already use.
- **A base gap the audit found (section 3, section 9).** The base's VFS index keeps one size per file (the size the
  game sees) and validates it against the SD's listing. A game folder with any `.lz4b`, `.hevc`, `.opcm` or `.xmop`
  therefore never validates, and **every start does the full scan** (Culdcept's measured 22.8 s on the console before
  its fix, 237 ms after). culdcept-nx's `host_path_index.cpp` records both sizes (`kNotPacked`), and nights-nx has it
  too. sasrt-nx, rr6-nx, blur-nx, vivapinata-nx, sa2-nx-ult and kameo-nx have the base's index. Worth a base port.
- **Section 9 also lists what else the base lacks:**
  - `NAME.adxo` (sa2-nx-ult's and nights-nx's CRI ADX path), a base candidate;
  - vivapinata-nx's 22,050 Hz `.xmop` rate case;
  - a common helper for the ASF movie hooks;
  - the installers' media writers.

  These are only notes: nothing in this folder changes code.
- It was audited against the ports' own docs and code before it was sent: three independent checks (sections 1-4, 5
  and 6-10), about 500 claims, 43 problems and 10 unsupported claims. Every finding was checked against the source,
  then fixed or sourced in this copy. Among them:
  - mislabelled MiB figures;
  - the 22 kHz rate that the base cannot read;
  - the ADX seek pre-roll of 80 ms, not 320;
  - the ASF packer's own encoder settings;
  - which installers pack their movies.

Questions: the "sonic racing" session (sasrt-nx).
