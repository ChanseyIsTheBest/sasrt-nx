# Where the port is more precise than a real Xbox 360

The user's question, 2026-11-11: ways the port is "too precise" against the actual console, with a confidence column
and whether each applies to every 360 game (the shared recompiler, Renut, the SDK or the Switch's hardware) or only to
SASRT. **High** = checked in this port's code or logs on 2026-11-11; the rest are from the 360's known hardware
behaviour and inference about the port. "follows #N" marks a consequence of an earlier row.

| # | Area | Xbox 360 | Port today | Confidence | Universal? | Speed of the extra accuracy (against matching the 360) |
|---|---|---|---|---|---|---|
| 1 | `vrsqrtefp` (vector 1/√x) | ~12-bit estimate | exact √ + divide (fast form on, 2026-11-11) | High | Yes | Slower (CPU): about 1 ms a frame on WaterThread here (one function spent 32 of its 207 samples on it); fast form now on, A/B pending |
| 2 | `vrefp` (vector 1/x) | ~12-bit estimate | exact divide (fast form on) | High | Yes | Slower (CPU), small (same kind as 1, fewer sites) |
| 3 | `vlogefp` (vector log₂) | rough estimate (spec: within 1/32) | exact `log2f` ×4 (fast form on) | High | Yes | Slower (CPU), tiny here (25 sites, four library calls each); fast form now on |
| 4 | `fres` (scalar 1/x) | estimate | exact double divide | High | Yes (SASRT never uses it) | Free here (never used); a small CPU cost in games that use it |
| 5 | `frsqrte` (scalar 1/√x) | estimate | exact √ + divide | High | Yes (SASRT never uses it) | Free here (never used); a small CPU cost in games that use it |
| 6 | 10-bit colour targets | 32 bits per pixel | 64 bits per pixel (16-bit unorm) | High | Yes | Slower (GPU): double the memory traffic on these targets; an exact 32-bit match exists, halving it. Est. 1-5 % GPU where used (which SASRT targets use it: not checked yet) |
| 7 | 7e3 HDR float targets | 10-bit floats, 32 bits per pixel | 16-bit floats, 64 bits per pixel | High | Yes | Slower (GPU): double the memory traffic; no exact 32-bit match (11:11:10 float has no alpha, less blue precision). Est. 2-8 % GPU in HDR-heavy games |
| 8 | Blending into 6 / 7 | 10-bit precision | 16-bit precision | High | Yes | Part of 6 / 7 (64-bit blending runs at half rate on this GPU) |
| 9 | Shadow-map depth | 24-bit | 32-bit float | High | No (SASRT key) | Free (32 bits a pixel either way) |
| 10 | Copies / resolves of 6 / 7 | keep 10 bits | keep 16 bits | Medium | Yes | Slower (GPU): part of the 7.2 ms a frame SASRT spends on resolves and depth resolves; up to ~1-2 ms if those copies are 16-bit (est.) |
| 11 | Depth resolves read as data | 24-bit integer words | read through a float target | Medium | Mostly | Free to small |
| 12 | 16-bit fixed-point targets | fixed −32…32 | 16-bit float (mixed: finer near 0, coarser near ±32) | Medium | No (SASRT key) | Free (16 bits a channel either way) |
| 13 | Gamma for `_GAMMA` targets | piecewise-linear approximation | probably the exact curve | Medium-low | Yes | Free; copying the 360's piecewise curve would cost a few more shader instructions |
| 14 | Bilinear filter weights | coarser sub-texel fractions | 8-bit fractions | Low-medium | Yes | Free (the hardware does it either way) |
| 15 | Anisotropic filtering | the 360's quality at the game's ratio | the Switch GPU's higher quality | Low-medium | Yes | Free (the hardware does it either way) |
| 16 | DXT1/3/5 decoding | the 360's interpolation rounding | more precise BC decoding | Low-medium | Yes | Free (the hardware does it either way) |
| 17 | DXN / DXT5A (BC5 / BC4) | about 8-bit decode | higher-precision decode | Low-medium | Yes | Free (the hardware does it either way) |
| 18 | 360-only formats (CTX1 etc.) | the 360's decode precision | expanded into wider formats | Low-medium | Yes | Slower where used: a 4-bit-a-pixel format expanded to 16 bits is 4x the memory and traffic for those textures (game-dependent) |
| 19 | Render-backend dithering | dithers some low-precision writes | probably not reproduced | Low-medium | Yes | Free; reproducing the 360's dither would cost a little |
| 20 | XMA audio decoder | fixed-point hardware | software decoder in float | Medium-low | Yes | Free (software decoding either way) |
| 21 | Mip / LOD selection | lower-precision LOD maths | finer LOD fraction | Low | Yes | Free (the hardware does it either way) |
| 22 | Shader RCP / RSQ (IEEE forms) | Xenos approximations | the Switch GPU's units, likely a bit closer to exact | Low | Yes | Free (the hardware does it either way) |
| 23 | Varying interpolation | possibly reduced precision | full 32-bit float | Low | Yes | Free (the hardware does it either way) |
| 24 | Rasterisation sub-pixel precision | coarser snapping | finer | Low | Yes | Free (the hardware does it either way) |
| 25 | HDR exposure readback | through a lower-precision target | full float values | Low | No (SASRT readback) | Free |
| 26 | Depth buffers (D24S8, 20e4 float D24FS8) | 24-bit | 32-bit float by default (SASRT uses the 24-bit option for most) | Medium | Yes (renderer default) | Slower where used: 32-bit float depth with stencil is 64 bits a pixel on this GPU against 32 for 24-bit; est. 2-6 % GPU in depth-heavy games (SASRT uses the 24-bit option) |
| 27 | Depth bias / polygon offset | in 24-bit depth units | in 32-bit float units | Low-medium | Yes | Free (the hardware does it either way) |
| 28 | Display gamma ramp (SetGammaRamp / PWL) | 10-bit hardware ramp | applied in a float shader | Medium | Yes | Free (one pass at present) |
| 29 | `_GAMMA` textures (degamma on fetch) | piecewise-linear approximation | exact curve in the shader | Medium-low | Yes | Free; the piecewise curve would cost slightly more |
| 30 | Filtering gamma textures | filtered in gamma space | possibly filtered after linearising | Low | Yes | Free (the hardware does it either way) |
| 31 | MSAA resolve averaging | at the target's precision | averaged in float | Low-medium | Yes (MSAA games) | Free (the hardware does it either way) |
| 32 | Resolve format conversion | EDRAM resolve hardware rounding | a float shader, round to nearest | Low-medium | Yes | Free (the hardware does it either way) |
| 33 | Alpha-to-coverage | dithered coverage patterns | hardware dither off by default, so smoother edges | Medium | Yes | Free; the 360's dither pattern would cost a little |
| 34 | Alpha test | 8-bit alpha reference | compared in float | Low | Yes | Free (the hardware does it either way) |
| 35 | Shader RECIP_FF / RECIPSQ_FF | "fixed-function" approximations | emitted as exact divides | Medium-low | Yes | Free (the hardware does it either way) |
| 36 | Shader EXP / LOG variants | Xenos approximations | the Switch GPU's `exp2` / `log2` | Low | Yes | Free (the hardware does it either way) |
| 37 | Shader SIN / COS | limited range and precision | the Switch GPU's units | Low | Yes | Free (the hardware does it either way) |
| 38 | 32-bit float textures | Xenos can't filter them (point only) | filtered linearly if the sampler asks | Low-medium | Yes | Slower, tiny: 32-bit float textures filter at half rate |
| 39 | 16-bit textures (normalised or float) | reduced-precision filtering | full-precision filtering | Low | Yes | Free (the hardware does it either way) |
| 40 | Texel addressing on large textures | coarser sub-texel steps | finer | Low | Yes | Free (the hardware does it either way) |
| 41 | `vexptefp` (vector 2^x) | the spec allows a very rough estimate | the generator's ~12-bit estimate | Medium-low | Yes | Free (the hardware does it either way) |
| 42 | `vpkd3d128` packing (float → half / 10-bit) | possibly truncates | rounds to nearest | Low | Yes | Free (the hardware does it either way) |
| 43 | memexport output | written in the declared narrow format | converted host streams may keep more precision | Low | Yes (memexport games) | Free to small (wider streams where kept) |
| 44 | XMV / WMV video | the console's decoder and colour conversion | software decode in float | Medium-low | Yes (XMV games; not SASRT) | Free (the hardware does it either way) |
| 45 | Audio mixing | 16-bit stages in places | 32-bit float throughout | Low-medium | Yes | Free (the hardware does it either way) |
| 46 | Audio resampling | hardware sample-rate converter | software resampler | Low | Yes | Free (the hardware does it either way) |
| 47 | XMA output word length | 16-bit PCM | float into the mixer | Medium-low | Yes | Free (the hardware does it either way) |
| 48 | Hardware shadow-compare (PCF) weights | Xenos weights | 8-bit weights | Low | Yes | Free (the hardware does it either way) |
| 49 | 7e3 target maximum | clamps near 31.9 | 16-bit float keeps up to 65504 | Medium | Yes | Free; clamping like the 360 would add a little shader work |
| 50 | 7e3 targets are unsigned | negative values become 0 | 16-bit float keeps negatives | Medium | Yes | Free; clamping like the 360 would add a little shader work |
| 51 | Scalar FPU non-IEEE mode (FPSCR NI) | flushes scalar denormals when a game sets it | scalar code always keeps denormals | Medium-low | Yes | Free (this CPU handles tiny numbers at full speed) |
| 52 | VMX NaN results | substitutes its default NaN in places | the ARM keeps NaN payloads | Low | Yes | Free (the hardware does it either way) |
| 53 | Float → 8-bit target writes | may truncate | rounds to nearest | Low-medium | Yes | Free (the hardware does it either way) |
| 54 | Blending into 8-bit targets | limited internal blend precision | higher internal precision, then rounded | Low-medium | Yes | Free (the hardware does it either way) |
| 55 | Blending into `_GAMMA` targets | in gamma space through the PWL curve | depends on the target-gamma path | Low | Yes | Free (the hardware does it either way) |
| 56 | Viewport transform | fixed-point | float | Low | Yes | Free (the hardware does it either way) |
| 57 | Clipping / guard band | fixed-point guard band | float clipping | Low | Yes | Free (the hardware does it either way) |
| 58 | Depth clamp / near-far | fixed-point | float | Low | Yes | Free (the hardware does it either way) |
| 59 | Trilinear mip blend weights | coarser | finer | Low | Yes | Free (the hardware does it either way) |
| 60 | LOD bias / min-max LOD clamps | fixed-point steps | finer steps | Low | Yes | Free (the hardware does it either way) |
| 61 | Texture border colour | about 8-bit | float | Low | Yes | Free (the hardware does it either way) |
| 62 | Cubemap face seams | no filtering across faces | seamless filtering if the sampler enables it | Medium-low | Yes | Free (the hardware does it either way) |
| 63 | Large texture coordinates (wrap) | fixed-point wrap, shimmer at large UVs | float wrap | Low | Yes | Free (the hardware does it either way) |
| 64 | Point-sampling texel selection | coarser rounding | finer | Low | Yes | Free (the hardware does it either way) |
| 65 | Filtered result of 8-bit textures | returned at about 8-bit precision | returned at higher precision | Low-medium | Yes | Free (the hardware does it either way) |
| 66 | Filtering 7e3 data | 10-bit float | 16-bit float (follows #7, #10) | Medium | Yes | Part of 7 (64-bit texels filter at half rate) |
| 67 | YUV textures (e.g. Y1_Cr_Y0_Cb) | hardware YUV sampling | converted to RGB in float | Medium-low | Yes | Free (the hardware does it either way) |
| 68 | Vertex texture fetch | reduced precision | full | Low | Yes | Free (the hardware does it either way) |
| 69 | Shader MAD | likely rounded twice | the host compiler fuses it (one rounding) | Medium-low | Yes | Free (the hardware does it either way) |
| 70 | Shader dot products | rounded per step | fused accumulation | Low | Yes | Free (the hardware does it either way) |
| 71 | Shader `_CLAMP` variants (RCP / RSQ / LOG) | clamped approximations | exact forms | Low | Yes | Free (the hardware does it either way) |
| 72 | Derivatives (ddx / ddy) | coarse, per 2×2 quad | possibly finer | Low | Yes | Free (the hardware does it either way) |
| 73 | HDR bloom / downsample chains | 7e3 | 16-bit float (follows #7) | Medium | Yes (7e3 games) | Part of 7 |
| 74 | G-buffer normals / velocity in 10-bit formats | 10 bits | 16 bits (follows #6) | Medium | Yes | Part of 6 |
| 75 | Depth-based effects (DOF, SSAO, fog) | 24-bit depth | float depth (follows #11, #26) | Medium-low | Yes | Free (the cost is in 26 where it applies) |
| 76 | Z-fighting | 24-bit depth | less with 32-bit float depth (follows #26) | Medium-low | Yes (renderer default) | Free (the cost is in 26 where it applies) |
| 77 | Half-resolution copies (resolve downscale) | box filter at target precision | in float | Low | Yes | Free (the hardware does it either way) |
| 78 | Docked internal resolution | this game's race at 1152×544 | up to 1.5× (1728×816) | High | Yes (renderer option) | Slower by design: up to 2.25x the pixel work docked; dynamic resolution trades it against the frame budget |
| 79 | HUD / menus | 720p | drawn at display resolution (1080p docked) | High | Yes (renderer option) | Slower, small: the HUD at 1080p docked (est. under 1 % GPU) |
| 80 | Anti-aliasing | the game's FXAA | SMAA | High | Partly (SMAA is the renderer's; replacing FXAA is SASRT's) | Slower: SMAA's two passes measured 1.2 ms a frame here (~3.5 % of the GPU), against the game's cheaper FXAA |
| 81 | 16-bit fixed targets' range | clamps at ±32 | 16-bit float range | Medium | No (SASRT key) | Free (the hardware does it either way) |
| 82 | Display upscale | the 360's hardware scaler, fixed-point | float shader | Low | Yes | Free (the hardware does it either way) |
| 83 | Shadow PCF compare | 24-bit compare | float compare (follows #9) | High | No | Free (as 9) |
| 84 | Tessellator (games that use it) | fixed-point tessellation factors | float | Low | Yes (few games) | Free (the hardware does it either way) |
| 85 | Point sprite sizes | fixed-point | float | Low | Yes | Free (the hardware does it either way) |
| 86 | Anisotropy on cube / volume textures | not supported | the host GPU may apply it | Low | Yes | Free (the hardware does it either way) |
| 87 | XMA loop points | block granularity | sample-accurate | Low | Yes | Free (the hardware does it either way) |
| 88 | Audio pitch / resampling ratio | fixed-point step | float ratio | Low | Yes | Free (the hardware does it either way) |
| 89 | Audio volume / panning | fixed-point in places | float | Low | Yes | Free (the hardware does it either way) |
| 90 | Audio headroom | 16-bit stages can clip | the float mixer doesn't clip until the output | Low-medium | Yes | Free (the hardware does it either way) |
| 91 | Luminance / exposure readbacks in general | through narrow targets | full float (generalises #25) | Low | Yes | Free (the hardware does it either way) |
| 92 | Resolve exponent bias (scaled copies) | fixed-point | float | Low | Yes | Free (the hardware does it either way) |
| 93 | Clear colours of 10-bit / 7e3 targets | quantised to 10 bits | 16 bits (follows #6, #7) | Medium | Yes | Part of 6 / 7 (clears are compressed: near free) |
| 94 | Blend factor constant on float targets | 8-bit packed | float | Low | Yes | Free (the hardware does it either way) |
| 95 | Particles / fog blended over 7e3 targets | 10-bit blend | 16-bit (follows #8) | Medium | Yes (7e3 games) | Part of 7 |
| 96 | Reflection / environment targets in 7e3 | 10-bit float | 16-bit float (follows #7) | Medium | Yes (7e3 games) | Part of 7 |
| 97 | Chroma upsampling of YUV video / textures | the 360's hardware | bilinear in float | Low | Yes | Free (the hardware does it either way) |
| 98 | Mip selection for anisotropic samples | coarse | finer | Low | Yes | Free (the hardware does it either way) |

**The speed column** says what the port's extra accuracy costs against doing what the 360 does: "Slower" = matching the
360 would be faster (by about the amount given; estimates unless marked measured), "Free" = no difference (the hardware
does it at the same cost, or matching the 360 would itself cost extra work). 79 of the 98 rows are free; 19 cost speed.

The ones worth acting on (universal, with a real payoff): **6-8, 10, 49, 50** (the 360's 32-bit target formats stored
at 64 bits: double the memory traffic on a GPU-bound game, and 49 / 50 are behaviour differences, not only precision);
**1-3, 41** (done or easy; 1-3 are in the build being profiled); **28, 33, 35** (medium confidence, cheap to check).
Past about row 75 the list is mostly consequences of earlier rows or low-confidence guesses; it stops at 98 rather than
repeat rows.

## Implemented (2026-11-11, the formats batch; docs/machine-copies-handoff-rr6.md section 5)

- Rows 1-3 (and vnmsubfp, which the 360 also fuses): the fast VMX forms, ON. Console fuzz passed; +2.4 % fps, WaterThread -2.7 %.
- Rows 6, 8, 10, 74, 93: renut_format_10bit_exact, ON (exact). Also the EDRAM formats 10 / 12 that fell to 8-bit (less than
  the 360 kept): renut_format_edram_as_variants, ON.
- Row 38: renut_float32_point_filter, ON. The premise checked (2026-11-11 ~12:15): Microsoft's XNA HiDef profile, built
  around "roughly Xbox 360 level capabilities", refuses filtering on every floating-point texture format (its developer's
  post "Reach vs. HiDef"; the framework throws for linear on Single / Vector2), and its Xbox-only 7e3 HdrBlendable format
  "only supports point sampling"; a Beyond3D forum post (2006) lists 32-bit-per-component float textures as "no
  filtering" on Xenos. Not found: what the hardware does when a native game sets linear anyway (most likely point). SASRT
  samples its R32F luminance textures (1x1, 64x64) with linear set; the exposure readbacks were unchanged with the change.
- Rows 7, 66, 73, 95, 96: renut_format_7e3_rg11b10, OFF: no exact 32-bit host form of 7e3 with blending; 11:11:10 loses
  the alpha and a mantissa bit or two (less faithful than both the 360 and FP16).
- Row 26: renut_depth_float_no_stencil, OFF: not safe as written, and SASRT uses stencil on its main float depth (census).
- Row 18: not changed (no smaller lossless host format).
- SASRT's own census: no 10-bit or 7e3 targets, so the batch is for the base; on SASRT it measured as noise.
- Found the other way: SASRT's main depth is the 360's 24-bit float depth (D24FS8), kept as 32-bit float with stencil
  (more precise, 64 bits a pixel); the shadow maps are 32-bit float without stencil.
