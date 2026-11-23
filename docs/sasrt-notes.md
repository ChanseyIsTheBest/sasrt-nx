# Notes on the game's code

Addresses are guest addresses in `default.xex` (title `5345085D`, version 0.0.0.2, image `0x82000000`+`0x15E0000`)
unless they say otherwise. Every entry says how it was found, so it can be checked again after a new code generation.

## The game files

| | |
|---|---|
| Package | Games on Demand (`5345085D/00007000/97A9A171AADA666596EA`, SVOD volume, 30 data files, 4,971,413,504 bytes), classic (XSF) layout: data block 0 is partition sector 0 |
| Integrity | `tools/god_extract.py` checks the whole SHA-1 chain: header root hash -> each data file's master table (entry 203 hashes the next file's master) -> level-0 tables -> every 4 KB data block. All 1,207,773 data blocks match (2026-10-05) |
| Disc contents | 22 files: `default.xex` (19.8 MB), `Data/{Frontend,GameAssets,GameData}.M00` + `.toc` (3.5 GB of archives), `Data/sound/*.pck` (Wwise: `SoundBanks.pck`, `Streams{Eng,Fra,Ger,Ita,Spa,Multi}.pck`), `Data/Movies/*.usm` (CRI Sofdec), `AvatarAssetPack`, `nxeart`, `$SystemUpdate/` |
| DLC | "Bonus Pack" (`00000002/2125BED78BDCE2760AA1FBA35A3A4A5FA4F5C2A153`, STFS): a single `dlcfile.txt` = `DLC_METALSONICOUTRUN_VALID`. Metal Sonic, his car and Outrun Bay are on the disc; the package only unlocks them |

## default.xex

| | |
|---|---|
| Original PE name | `ASN_Xb360_10.exe`, built 2012-10-12 |
| XDK | 2.0.21119 (D3D9, XGRAPHC, XAUDIO2, XMCORE, XAVATAR, XPARTY, XHV2, XMP, XONLINE, XNET) |
| Entry point | `0x824679C0` |
| Imports | `xam.xex` (384 records) and `xboxkrnl.exe` (381 records): 375 functions; no other module |
| TLS | 64 slots, initialised data at `0x83366000` (597 bytes) |
| Sections | `.rdata` `0x82000400`, `.pdata` `0x82360000` (33,273 entries), **`.xidata` `0x823B0000` (code, 1.3 MB)**, `.text` `0x824ED000` (11.8 MB), **`PSFD00` `0x83024000` (code, 32 KB)**, `.data` `0x83030000`, `.tls`, `.XBMOVIE`, `.idata`, `.XBLD`, `.reloc` (zeroed in the loaded image) |

### The thunk table (`.xidata`)

`.xidata` (`0x823B0010`-`0x824A56C0`) is a table of **62,826 jump thunks** of 16 bytes, `lis r11,hi / addi r11,r11,lo /
mtctr r11 / bctr`, to 61,509 distinct functions; then 64 KB of zeros, then the 375 XEX import thunks
(`0x824B56C0`-). The PE header lists `.xidata` as data directory 7 (architecture). Most code goes through it: 122,106
`bl` and 8,853 `b` from `.text` land on a thunk, and 34,399 words of the image (vtables, callback tables) hold thunk
addresses. Found 2026-10-05 by scanning the loaded image (`REXGLUE_DUMP_IMAGE`).

What the generator needed for it (`tools/thunk_table.py` writes `app/thunks.toml`):

- **Every thunk is a function** (`size = 16`). Discovery registers only `bl` targets and GapFill does not split the
  table at `bctr`, so the first codegen failed with 4,020 "target not in any function" (all `b` from `.text` into
  1,429 thunks) and every thunk reached only through a vtable would have stopped the game at its first virtual call.
- **Every thunk target is a function.** A thunk's `bctr` goes to an address built with `lis/addi`, which discovery
  does not follow. 34,241 targets in `.text`/`PSFD00` have no `.pdata` entry (leaf functions); three were not found
  by GapFill either (`sub_82964A08` and `sub_82964B40`: leaves right after a function whose last block ends in a `b`,
  so GapFill's segment began inside that function and was dropped; `0x82C8F378`: an entry of the CRT copy routines).
  All are declared, without a size.
- One thunk, `0x82481B00`, jumps into `.data` (`0x8316E6B4`, plain data). Nothing references it (no branch, no data
  word): a stale entry, left out.

Speed note for the Switch: every call through a thunk is an extra function plus a function-table lookup. Calls whose
thunk target is known can become direct calls in the generator (to do in the optimisation stage).

### `PSFD00`

32 KB of code: 35 game functions, then a second copy of the CRT's register save/restore helpers (`__savegprlr_14`
`0x8302A954`, `__restgprlr_14` `0x8302A9A4`, `__savefpr_14` `0x8302A9F8`, `__restfpr_14` `0x8302AA44`, and VMX helpers
at `0x8302AA90`, `0x8302AC00`, `0x8302AC94`, `0x8302AE04`). The VMX copies use encodings the disassembler does not
know (`0x100B670B`, `0x100B630B`, `0x11CB670F`, `0x11CB630F` where the `.text` copies have `stvx128`/`lvx128`
`0x100B61CB`/`0x100B60CB`): the 64 "Unable to decode instruction" warnings of every codegen. **Nothing calls them**
(no branch into `0x8302A954`-`0x8302AE98`; the only words pointing there are their own `.pdata` records), and the
game's code uses the `.text` helpers (`0x82C8E810`-`0x82C8ECAC`, detected by the SDK). Harmless.

## SDK changes the game needed (2026-10-05)

| Change | Why |
|---|---|
| `FunctionGraph::notifyFunctionAdded` visits only the functions with an unresolved jump to the new entry (index `unresolvedJumpSources_`) | it walked every function for every added one; with ~135K functions GapFill ran for over half an hour without finishing. Exact same result (unresolved jumps are only made in `addUnresolvedJumpToFunction`) |
| `cleanupAbsorbedGapFills` finds containing functions through a sorted span list | it tested every function for every gap fill (quadratic) |
| `validateConfigBoundaries` uses a sorted entry list | it walked every function for each of the 62,826 declared thunks |
| `ldbrx` / `stdbrx` (33 each, around `0x827907C4`) and `vavguw` (`0x827EAE70`) implemented | the generator emitted `REX_UNIMPLEMENTED` for them |
| The "Unexpected float16_4 pack" warning no longer fires for pack mode 3 with shift 0-2 | same permute as pack mode 2 (Xenia's `vpkd3d128` tables: guest words 2-s and 3-s); the game's 20 sites (`0x82D1F7CC`-`0x82D20358`) are pack 3 / shift 2, which the existing code already placed right |

Codegen now takes about 30 s.

## Missed-code sweeps before the first boot (2026-10-05)

**Functions reached only by pointer.** `tools/pointer_fixpoint.py` (adapted: the scratch codegen keeps `thunks.toml`):
56,938 gaps between functions, of which 56,417 are zero padding; 411 candidates (data words or `lis/addi` constants
landing in a gap). Accepted by the tool's rules: 6, all left out after review: `0x824B675C` is the `bctr` of an XEX
import thunk; `0x8250E194`, `0x8250E1A4`, `0x8250E1B0`, `0x82F10F04`, `0x82F10F18` are SEH funclets (next to the
`mr r8,r8` markers of `__try` blocks, pointers from `.rdata` scope tables, they run on the parent's frame `r31`),
reachable only when an exception is dispatched. Rejected: 404 "no code" (375 are the import thunks, reached through
`.xidata` thunks, registered by the generator as imports; the rest point at padding), 1 fragment (`0x82A09FA0`: reads
`r11` at entry). Fixpoint: nothing to add.

**Other code pointers.** `tools/pointer_audit.py`: no vtable-like pointer to an unregistered address. 4 addresses built
in code that are not function starts: `0x82C91A00` and `0x82CA1228` (EH continuations: they read the parent's `r31`),
`0x82F10F18` (the SEH funclet above), and `0x82CA7974`, which `sub_82CA7910` passes as the target IP to
`RtlUnwind` (the CRT's global unwind): the SDK's `RtlUnwind` is a stub that returns, which lands on the same
instruction. The rest: 181 jump table targets, 174 SEH scope records, 45 C++ EH state-map entries, 173 data values
that happen to fall in the code range (round numbers like `0x83000100`, pointers into padding).

**Jump tables.** `tools/switch_check.py` over `.text` and `PSFD00`: 181 tables (145 absolute, 25 byte, 11 halfword),
none truncated, none missed. One "wrong targets": `sub_82CEC5F8`'s byte table `0x822F76E8` is bounded only by a 6-bit
mask (64 cases) but has 12 entries, followed by the strings "LineTexture", "ArrayTexture", ...; declared with its 12
entries in `overrides.toml`. Three bctrs with a table-like load are calls through function-pointer tables in `.data`
(`0x826103A0`: table `0x8305AD44`; `0x82B6654C`: 32-byte records at `0x8314DEDC`; `0x83025598`: a table built at run
time), rightly indirect calls; every non-null entry of the two static tables is a registered thunk.

**setjmp / longjmp.** None. No function stores `r1` into a structure (`stw`/`std r1,d(rX)`, `rX` != `r1`); the only
one that loads `r1` from one is `sub_82CA77CC`, a CONTEXT restore of the SEH unwinder (loads `f14`-`f31`, `r14`-`r31`,
CR, CTR, `r2`, `r1` from `r4`, returns to `r3`), which runs only while an exception is dispatched.

**C++ exceptions.** The constant `0xE06D7363` is built in 9 EH-runtime functions; the throw function
(`sub_82C94DD0`, thunk `0x82499B60`) has 2 call sites. Throws are rare in this game; the SDK cannot dispatch one
(see sa2-nx's notes), so a throw would stop the game.

## Direct3D (XDK 2.0.21119, statically linked)

Found by matching against Sonic Adventure 2's named functions (XDK 2.0.21076; `tools/ref/sa2_d3d_names.toml`): the
token sequence (opcodes and registers) of each SA2 function compared with every function of this game that starts
with the same 10 tokens. All but four have an identical sequence (ratio 1.00); `tools/listing_diff.py` then shows that
only global addresses differ, so the device and shader object layouts are SA2's (bound vertex shader at device
`+13072`, pixel shader at `+13068`).

| Function | This game | SA2 |
|---|---|---|
| `D3DDevice_Swap` | `sub_82CD9AE8` (also the only caller of `VdSwap`, through thunk `0x823E6B80` at `0x82CD9E70`) | `sub_82558E98` |
| draw-time shader load | `sub_82CE27D8` | `sub_82556A60` |
| `D3DDevice_DrawVertices` | `sub_82CD18D0` | `sub_82565C60` |
| `D3DDevice_DrawIndexedVertices` | `sub_82CD1DB8` | `sub_82566078` |
| `D3DDevice_DrawVerticesUP` | `sub_82CD1168` | `sub_82565C18` |
| `D3DDevice_BeginVertices` | `sub_82CD0BB8` | `sub_82565758` |
| `D3DDevice_CreateVertexShader` | `sub_82CC64E8` | `sub_8255E750` |
| `D3DDevice_CreatePixelShader` | `sub_82CC61F0` | `sub_8255E568` |
| `D3DDevice_CreateVertexDeclaration` | `sub_82CC2F40` | `sub_8255E198` |
| `D3DDevice_SetShaderGPRAllocation` | `sub_82CC3430` | `sub_8255E218` |
| `D3DDevice_Clear` | `sub_82CE71B0` | `sub_82563AB0` |
| `D3DDevice_Resolve` | `sub_82CDB7C8` | `sub_825645A0` |
| `D3DDevice_BeginTiling` / `EndTiling` | `sub_82CE7868` / `sub_82CE8098` | `sub_825576D0` / `sub_82557A40` |
| `D3DDevice_CreateTexture` / `CreateSurface` | `sub_82CD7978` / `sub_82CD7AD8` | `sub_82548DF8` / `sub_82548F18` |
| `D3DDevice_CreateVertexBuffer` / `CreateIndexBuffer` | `sub_82CE3D90` / `sub_82CE3F80` | `sub_82549730` / `sub_82549808` |
| `D3DDevice_SetRingBufferParameters` | `sub_82CDFE60` | `sub_8254EF40` |
| `D3DDevice_BlockUntilIdle` | `sub_82CDFB60` | `sub_8254EE70` |
| `D3DDevice_SetScreenExtentQueryMode` | `sub_82CF25B8` | `sub_82553490` |
| `D3DDevice_SetGammaRamp` | `sub_82CCEB38` or `sub_82CCEA20` (same shape) | `sub_825527D8` |
| `Direct3D_CreateDevice` | `sub_82CD4448` | `sub_8254FC10` |
| ring kick-off (`CP_RB_WPTR`) | `sub_82CDE200` | `sub_8254DC00` |
| interrupt callback | `sub_82CDD388` | `sub_8254D420` |
| flip (`D1GRPH_PRIMARY_SURFACE_ADDRESS`) | `sub_82CD8850` | `sub_82557FC0` |
| display setup | `sub_82CD89B8` | `sub_825580F0` |
| `D3DResource_AddRef` / `Release` / `GetType` / `Destroy` | `sub_82CE3C80` / `sub_82CE4F38` / `sub_82CE35A8` / `sub_82CE4C08` | |
| `D3DIndexBuffer_Lock` / `D3DVertexBuffer_Lock` / `D3DSurface_LockRect` | `sub_82CE4320` / `sub_82CE57A0` / `sub_82CD7D08` | |

## The native renderer: what this game needed (stage 4, 2026-10-06)

The frame of a race, from `banjo_trace_frame_s` with `MASSEFFECT_TRACE_ALL_DRAWS=1`:

1. Shadow cascades: depth at base 0, pitch 1040, resolved as one 1024x3072 `k_24_8_FLOAT` atlas in three strips
   (`091B1000`, then `095B1000` = row 1024 and `099B1000` = row 2048 of the same texture; the renderer's partial
   resolve search places them).
2. G-buffer: three 8888 MRTs at bases 0 / 510 / 1020 and depth `D24FS8` at 1530, 1152x544, reversed Z (`GEQUAL`);
   resolved to `07D0D000`, `07845000`, `075E1000` and the depth to `07119000`.
3. Depth restore into EDRAM, twice (bases 510 and 1020): a rectangle (VS n131 / PS n159) samples the depth resolve
   as `k_8_8_8_8`, swaps the two 40-pixel columns of every 80-pixel tile and writes the raw words into a color target
   whose tiles alias the depth target of the next pass (color base = depth base). Then a 4x MSAA depth-only draw with
   `ZFUNC NEVER` over the same tiles.
4. Light volumes (stencil marking, then lit) into 8888 at base 0 with depth 510; resolved to `0737D000`.
5. HDR scene: `k_16_16_16_16` (16-bit fixed point, -32..32) at base 0 (64 bpp: tiles 0-1019) with depth 1020:
   composition of the G-buffer and lights, then the forward pass (water, sky, effects), resolved as
   `k_16_16_16_16_FLOAT`; bloom read back as `k_16_16_16_16_EXPAND`.
6. Luminance: `k_32_FLOAT` 64 -> 16 -> 4 -> 1, the adapted value in a second render target (`copy_src_select` 1).
7. Tonemap into 1280x720 8888.

What the renderer needed for it:

| Change | Where |
|---|---|
| `k_16_16_16_16` / `k_16_16` render targets (host RGBA16F / RG16F) and their clear value (signed 16-bit fixed, `0x7FFF` = 32) | `me_formats_color.h` |
| Pixel shader outputs into those targets clamped to [-32, 32] like the hardware (`kSpecTargetFixed16`); without it FP16 overflowed to Inf in the luminance chain and the race was overexposed | `masseffect_native_draws.cpp`, `LimitOutputs7e3` |
| `k_16_EXPAND`, `k_16_16_EXPAND`, `k_16_16_16_16_EXPAND` textures (FP16 data) | `masseffect_native_draws.cpp`, texture table |
| Vertex positions 2-4 (`USAGE_LOCATIONS`), duplicate vertex inputs, 1D texture descriptor indexes | `shaders/XenosRecomp/shader_recompiler.cpp` |
| Direct3D's own rectangle shaders read `SV_VertexID`: the rectangle expansion reuses that input instead of rejecting the draw (the depth restore was dropped: the sky was noise) | `me_rectangle_spirv.h` |
| A depth resolve fetched as `k_8_8_8_8` reads its raw words: an RGBA8 image of `20e4 depth << 8 | stencil`, made from the depth target at the resolve (`me_depth_resolve_words.comp`, with its stencil) or from the R32 resolve at the first fetch (`me_resolved_depth_words.comp`, stencil 0); `ResolvedDepthWords` | `masseffect_native_targets.cpp`, `masseffect_native_draws.cpp` |
| Reverse-subtract blending (`BlendOp` 4) mapped to `VK_BLEND_OP_REVERSE_SUBTRACT` (it was SUBTRACT); the texel size of 8- and 16-bit resolves in their tiled address (banjo-nx's findings) | `masseffect_native_draws.cpp`, `masseffect_native_targets.cpp` |

Diagnostics added: `sasrt_debug_dump_s` with `_vs` / `_ps` / `_base` / `_after` dumps the images of chosen draws to
`dumps/` (`tools/depth_dump_check.py` reads the depth-restore chain); `tools/win/cvar_sweep_race.ps1` scores renderer
switches by the share of race frames that show only the sea.

### The depth restore's pixel shader (three fixes)

Before them, 52 of 60 sampled race frames showed only the sea (`cvar_sweep_race.ps1` baseline in
`out/sweep_race1.txt`), and none of the renderer switches the sweep tried changed that much (50-58 of 60): the
restored depth was wrong, so the forward pass was clipped against garbage. The restore's pixel shader (Direct3D's
own: n159, wrapped as `ps_a393b1e0f77e8311`) has no interpolated input. It reads its pixel position from r0, which
the hardware fills itself (parameter generation: `SQ_PROGRAM_CNTL` bit 18 set, `SQ_CONTEXT_MISC` bits 8-15 name the
register, 0 here), and it fetches the words with unnormalized coordinates. Three things were wrong:

1. Parameter generation. The recompiler's register linking (banjo-nx: pixel-shader input N = vertex-shader output N)
   gave r0 the vertex shader's output 0. Now spec-constant bits 2-6 (on, register) make that register
   `(pixel position - 0.5)` with x negated on back faces (`kSpecParamGen` in `masseffect_native_draws.cpp`; the
   `interpolatorCount == 0` registers in `shader_recompiler.cpp`).
2. Unnormalized coordinates. XenosRecomp ignored the fetch's `UnnormalizedTextureCoords`, so the pixel indexes
   were read as normalized coordinates, far outside the texture. `tfetch2DDenorm`
   (`shader_common.h`) scales them by the inverse texture size.
3. Texel edges. An integer coordinate times 1/size lands exactly on a texel edge, where rounding may pick either
   neighbour. The coordinate now gets 1/1024 of a texel, far below one texel; the hardware reads texel floor(c).

After the three fixes, the race renders with its scenery, and the restored words match the depth resolve (see the
check below).

### Memory export: the GPU skins the drivers

The characters are skinned by vertex shaders that export to memory (memexport). Direct3D draws a point list, one
point per vertex. Its vertex shader skins each vertex with the bone palette of fetch constant 90 (64-byte rows,
`k_32_32_32_32_FLOAT`, indexed by the blend indices), then exports the result (`k_32_FLOAT` x 3 per vertex) into
Direct3D's dynamic vertex ring. The character's own draw then reads that range as its vertex buffer. In a race that
is about 30 exported streams a frame (`sasrt_069.log`: 8,984 streams written between 04:40:51 and 04:41:01).

The port is banjo-nx's. XenosRecomp maps registers 32-37 to eA and eM0-eM4. The renderer keeps a 32 MB host-order
mirror buffer, redirects vertex fetches of an exported range to it, and puts barriers between an export and its
readers. This game needed three more things:

- Mirror validity. The CPU reuses the ring for ordinary vertices once the GPU is past it. A mirror therefore stands
  for its range only while the guest memory under it is unchanged since the export: a sampled fingerprint, checked
  once a frame. Without the check, ordinary geometry later written to the same addresses was drawn with old skinned
  characters. In `sasrt_069.log`, 164,634 reads of rewritten ranges went to guest memory instead.
- Barriers only where they are needed. The pass breaks before a draw that reads an export made since the last
  barrier (read after write), and before an export into a mirror read since then (write after read). Breaking after
  every export cost a third of the race's frame rate.
- Indexed fetches in shaders with an element table. The skinning shader declares its vertex elements but reads the
  bone palette at an address computed from the blend indices: a `vfetch` whose source is not `r0.x` as the shader
  received it. The recompiler routed such fetches through `banjoVfetch` only for register-linked shaders. Declared
  as plain inputs, every vertex read the palette's first rows and every exported mesh exploded. Now
  `classifyIndexedVertexFetches` (`shader_recompiler.cpp`) and `IndexedVertexFetches`
  (`masseffect_native_shaders.cpp`) handle them in both kinds of shader.

Still open: the renderer places one barrier per export (110,580 barriers for 110,693 streams at 04:41:01), so the
shadow pass is split once per character. This PC still holds 30 frames per second in a race. On the Switch, each
split stores and reloads the shadow depth, so hoisting the exports ahead of the pass is a GPU optimization to try.

### Compile-time shader changes, and the generated code's floating point

From banjo-nx:

- Gamma, signs and input remapping are computed with selects instead of branches.
- The uniform-buffer path and the inverse texture sizes are always on (`MASSEFFECT_UBO`; `inv_tex_size` forced),
  so the variants without them no longer exist.

From futari-nx and banjo-nx: the generated code is compiled with `-ffp-contract=off -fno-strict-aliasing` under GCC
and Clang (`app/CMakeLists.txt`):

- `-ffp-contract=off`: the PowerPC code rounds a separate multiply and add twice. GCC, which is devkitA64's
  compiler, would fuse them across statements, and the results would differ from the 360's.
- `-fno-strict-aliasing`: the translated memory accesses are type-punned.

### Against the emulated GPU: differences judged legitimate, and the open ones

- Clouds in races: the native renderer draws them, but the emulated GPU does not. Judged a defect of the reference,
  probably its lossy `D24FS8` transfers, since clouds are depth-tested against the restored depth.
- The purple glow on the loop in the race: also present in the emulated GPU's intro movie of the same track.
- The flat cyan sky (13 consecutive frames of 150 on the first race's uphill ramp, 04:37 build) was not a camera
  angle: the emulated GPU shows the blue gradient sky with clouds there (`emu_150s`, frame 30). It no longer happens
  with the current build (full-resolution capture of 08:15, same spot, blue sky; 0 flat-cyan frames of 150). Which
  later change fixed it was not bisected; the EDRAM changes (null-draw skip, clear alias) are the likely ones.
  Comparison image: `out/visual_issues/issue1_flat_cyan_sky_compare.png`.
- Specks (fixed, see "FXAA 360 and the texture exponent bias" below). One-pixel bright white/cyan dots along the
  car's silhouette edges and speckle on the dark ground under the rear bumper and wheels; the emulated GPU showed
  clean edges (`out/visual_issues/issue2_specks_compare.png`; after the fix:
  `out/visual_issues/specks_fixed_fxaa_bias_car_zoom.png`).

### Shader package: every track's shaders (2026-10-06)

The package was built from what the boot, the menus and the first World Tour race (Ocean View) drew: 250 shaders.
With the 100% save (`out\pc\user_100`, the user's save as the PC user data root) the other tracks showed how little
that was: in about 50 s of a Single Race, Samba Studios had 11,988 shader loads the package could not identify and
the second cup's second track 98,916, and the renderer skips the draws of a shader it cannot identify.

The game's shaders are objects (DumpBoundShader's layout) in each track's package, all loaded with the track, so:

- `sasrt_dump_shaders_scan_s = N` (with `sasrt_dump_shaders`; PC only): every N seconds the draw-time hook looks
  through guest memory for shader objects and dumps the containers of those not drawn yet (objects already drawn are
  left to the draw-time dump, which saw them before Direct3D patched their fetches). One visit to a track gives all
  its shaders: 8,555 objects in memory in an Ocean View race, 4,555 in the menus. Only committed, readable regions of
  the guest heaps are read: freed physical memory is decommitted on the host, and a first version that read the raw
  physical arena faulted.
- `tools\win\track_tests.ps1 -Mode harvest`: all 20 tracks (Career > Single Race > cup > track, the 100% save), each
  until the race has run for a while, with the scan, the dumps and MASSEFFECT_SHADER_DISCOVERY on
  (`out\pc\shaders_discovery_tracks`). 2.6 minutes a track.
- `tools\win\rebuild_shader_package.ps1` (or its steps by hand): `make_vertex_variants.py` over both discovery
  folders, then `wrap_discovered.py`, then `build_shader_library.sh out/pc/shaders out/pc/shaders_extra
  out/pc/shaders_variants_made/repaired out/pc/shaders_wrapped`. Of the 72 "variants" the harvest's discoveries gave,
  51 were byte-identical to harvested containers (shaders that were simply missing, unpatched); they were moved to
  `shaders_variants_made/duplicates` so that the package has no two entries with the same container.

Result: 238 -> 1,957 dumped containers; package 250 -> 1,982 shaders (all translated and compiled, none failed),
3.8 MB -> 57 MB plus a 4 MB index. Only the index is kept in memory (`masseffect_shaders_index`); each shader's
SPIR-V is read from the package on first use, so the size matters little on the Switch. D3D-patched vertex shaders
need no harvest of their own: the library's masked-fetch matcher identifies a rewritten variant by its container.

### Track tests: the native renderer on every track (2026-10-06)

`tools\win\track_tests.ps1 -Mode test`: Single Race on a track with the 100% save, a 1280x720 capture of the start
and about 60 s of racing (every 12th frame), once with the native renderer and once with the emulated GPU. The
emulated GPU loads slower, so on two tracks the scripted presses landed in the loading screen and its capture is the
track's intro flyover (Temple Trouble, the Samba de Amigo town); the user said the intro is reference enough.
`tools/compare_tracks.py` makes a native-above-emulated sheet per track (`out\pc\captures\tracks\compare\`) with the
mean luminance, the share of blown-out pixels and the speck count; `tools/track_overview.py` makes the overviews
(`overview_paired.png`, `overview_native.png`).

All 20 tracks, native renderer, after the shader harvest and the fixes above: 0 unidentified shaders and 0 rejected
draws on every track. Native against emulated on 10 of them (Ocean View, Dragon Canyon, Temple Trouble, Rogue's
Landing, Dream Valley, the neon city 2.2, Graveyard Gig, the sci-fi corridors 3.2, the Samba de Amigo town 4.0, the
casino 4.2): the same scenery, lighting, sky, water, effects and HUD; mean luminance 6-21 % apart (a rough check:
the two runs race differently, so the sampled frames show different moments; the native image is slightly more
contrasted), blown-out pixels 0.3-4 % in both. The other 10 (Samba Studios, Carrier Zone, 1.1,
1.2, 2.1, 2.3, 3.1, 3.3, 4.1, 4.3) render completely (`overview_native.png`).

Found and fixed on the way:

- Dream Valley (2.0) stayed white for the whole race, with garbage in the top rows, when the intro was skipped: at
  that transition 8 draws and 8 copies were rejected because a lazy stencil fetch had to read tiles a 64-bit
  fixed-point color target (k_16_16_16_16, the HDR scene at base 0) had written since, which the host holds as FP16
  and cannot reinterpret (only k_16_16_16_16_FLOAT has a raw view); the luminance chain never recovered. The draw now
  keeps the depth image's own stencil (`sasrt_native_stencil_keep_64bpp`, default on; on the hardware those bits
  would be leftover color the game cannot rely on): the same skip gives a normal race, 22 fetches kept, no rejection.
  Without the skip the intro had rendered correctly all along.
- The rejected-draw warning now names the draw (number, VS/PS, render targets, depth control, mode).

Frame rate (10 s reports of the native runs, on a PC shared with other projects): most tracks 30 frames a second;
2.1 24-29, 4.1 19-29, 4.3 25-30, 2.3 15-19 and 3.1 17-20. On 2.3 the GPU is not saturated (the listed passes add up
to about 4.5 s of 10) while the game issues about 2,400 draws a frame: the heavy tracks are bound by draw submission,
the place to look first for Switch performance.

### FXAA 360 and the texture exponent bias (the specks, fixed 2026-10-06)

The specks were not depth or lighting. At 6x zoom every depth edge of a race frame had a crisp one-pixel bright
outline on both sides (foliage against the sky: bright yellow-green inside, light blue outside), and the same
brightening on edges inside noisy textures (the gravel behind the wheels, the Ocean View ruins' stonework).

The frame trace shows the last full-screen pass before the HUD: one draw into the 1280x720 output that samples the
tonemapped 1152x544 image (`07D0D000`) three times. Its pixel shader (`ps_6c215354c35798b8`) is FXAA 3 for the 360:
the samplers are `tex`, `fxaaConsole360TexExpBiasNegOne` and `fxaaConsole360TexExpBiasNegTwo`, the same image with
the fetch constant's exponent bias (dword 3, bits 13-18) at 0, -1 and -2, so the hardware returns it scaled by 1, 1/2
and 1/4. The shader adds two -1 fetches to get their average (`r1 = r4 + r1` in the HLSL) and two -2 fetches plus
half of that for the four-tap result. The renderer ignored the exponent bias, so on every pixel FXAA treated as an
edge the output was twice the right value; the pixels it leaves alone were unchanged. The emulated GPU applies the
bias, hence its clean edges. (Ruled out first: the tfetch instructions' own filter overrides; all 4,511 texture
fetches in 1,298 dumped shaders use the fetch constant's filters, `tools/fetch_filters.py`.)

Fix: the renderer passes each texture slot's exponent bias in bits 18-23 of the slot's descriptor index (the heap
slot is below 4096; the remapped signs stay in 24-31) and the tfetch helpers of `shader_common.h` scale the result
by 2^bias after the signs (`masseffectApplyTextureBias`); key `sasrt_native_texture_exp_bias`, default on. The
renderer and the package go together: a package built with the older `shader_common.h` would take the bias bits as
part of the slot. The same change masks the slot in `tfetch1D`, which used the whole index (a signed 1D texture read
past the heap). The biases the game uses, logged once each: -1 and -2 (FXAA) and -10.

The -10 led to the texture number format, which the renderer ignores as well. The tracks' global-illumination pass
(`ps_ed0a8d53da14a749`: `gGILight0`-`2`, 32x8x32 volumes, k_16_16_16_16, unsigned) fetches its volumes with the
fetch constant's number format set to integer (dword 3 bit 0) and a bias of -10: on the hardware that should be the
raw 16-bit integers times 2^-10, 0-64, which the shader recentres by its literal -32 (`c254.y = 0xC2000000`). The host
image is UNORM (0-1), so the coefficients come out near -32 and the GI adds nothing. The emulated GPU does the same:
it applies the exponent bias (`dxbc_translator_fetch.cpp`) but ignores a texture's number format. The renderer can
scale an integer-format texture by 2^bits - 1 before the bias (component width in bits 12-16 of the index, so the
slot is bits 0-11; `IntegerTextureBits`: 8-bit, 16-bit and 4_4_4_4 formats; key `sasrt_native_texture_integer`), but
with it the GI lights the Ocean View start with noisy purple and magenta fringes where the emulated GPU's shadows are
neutral grey: the volumes' 3D data is probably not decoded right (3D tiling or endianness), so the key is off by
default and the native renderer matches the emulated GPU. Open: decode the GI volumes and compare with real
hardware footage before turning it on. **2026-10-21: done for Renut** (`sasrt_renut_texture_int_format` on, docs/
enhancements.md): PS3 footage of the intro flyover shows the start gate's pillars light grey where the normalized
reading drew them black, and Renut's integer reading (linear 8in16, the volumes as the guest stores them) matches it;
the user judged the race accurate. The other textures with the integer flag are float formats (k_24_8_FLOAT,
k_16_16_16_16_FLOAT and _EXPAND, k_32_FLOAT), where it does nothing.

Measured (`tools\win\fxaa_ab.ps1`: the same Ocean View Single Race with the key off and on, 200 frames each,
`tools/speck_score.py`): isolated bright pixels per frame, mean 266.6 -> 9.4, median 294 -> 8, maximum 1,062 -> 32.
