# SASRT GPU round 5: batch for RR6 (2026-11-09, 08:15) — pixel-identical items only

Round 5 also made pixel-changing cuts for SASRT (the user decides which stay); **none of them is in this batch**: every
file here had the cut code taken out (`files/`), and the C++ below is only the identical items' hunks.

Console-confirmed in SASRT's race (stock clocks, in-run A/B, 200 s from the start line):

| # | Key (default) | A/B | Generic? | Optimiser / DKSH? | Console | Port? |
|---|---|---|---|---|---|---|
| 51 | `sasrt_gpu_fetch_conversion_spec` (on) | 141 | Renut translator output (any game) | **yes**: pass `fetchconv`, constants 950-957 | **-3.30 ms** median (run B) | **yes** |
| 52 | `sasrt_gpu_fetch_exp_3d_spec` (on) | 142 | Renut (3D / cube fetches) | **yes**: pass `fetchconv`, constants 958-973 | -0.64 ms | **yes** |
| — | `tools/deko3d_variant_cache.py` key offsets | — | the tool | the DKSH cache | see below | **yes (a bug fix)** |
| 49, 50, 60, 63 | the EDRAM depth restore (SASRT's A393B1E0 copy) | 139, 140, 150, 153 | SASRT only | host shaders | -1.35, ~0, -1.12, -0.96 ms | no: inert without SASRT's depth restore |
| 53 | `sasrt_gpu_convert_vertex_pass` | 143 | Renut | host shader | flat | no |

## The variant cache tool read the pipeline list 4 bytes off (fix this first)

`tools/deko3d_variant_cache.py` read `fetch_types` from 192, `tess_kind` from 208, the plain-fetch word (constant 926) from
212 and the sasrt words from 216. `PipelineKey` (render/pipeline.h) has `reserved` at 184, `fetch_types` at 188,
`tess_kind` 204, `fetch_pad` 208 and `sasrt_words` from 212 (checked against SASRT's console list: 208 holds the
plain-fetch masks, 0x8000000N). So every specialised variant the tool built since round 1 got 926 and 932-944 from the
next word; the console compiled the ones it drew at run time and the SD cache kept them, which is why it still worked.
The fixed offsets are in `files/tools/deko3d_variant_cache.py` (`OFF_FETCH_TYPES, OFF_TESS_KIND, OFF_FETCH_PAD = 188, 204,
208`, `OFF_SASRT_WORDS = 212`), with list version 7.

## 51 / 52: a fetch's conversion words as constants of the draw

Renut's translated pixel shaders apply Xenos' per-channel signs, gamma and exponent adjust to every texture fetch from the
draw's words at run time (sampler bits 13-19, the 2D word's bits 20-25; the 3D / cube words' exponent from
`texture_indices[1]` / `[2]`), choosing among all the conversions with selects. Round 1's item 3
(`sasrt_gpu_plain_fetches`) drops the block where a fetch has none. Here fetch constants 0-7's words become constants of
the draw, so uam keeps only the conversions the draw's texture has: the same operations on the same values, the same
pixels. Unset constants compile byte-identical DKSH (checked on 9805DE9C, 3ECDED03, ED0A8D53). SASRT: G-buffer shader
9805DE9C 238 -> 167 TGSI instructions, ED0A8D53 (composite, 3D LUTs) 1072 -> 370.

- `render/pipeline.h`: `uint32_t sasrt_words[20];` (was 12; key 296 bytes). `files/.../render/pipeline.h`.
- `render/pipeline.cpp`: spec array 340; constants 950 + r (16-bit field, bit 15 = known), 958 + r / 966 + r (8-bit, bit 7 =
  known); list version 7 (a version 6 list converts); the listed-key filter clears [12]-[15] / [16]-[19] with each item
  off. `files/.../render/pipeline.cpp` (round 4's file plus exactly these).
- `tools/deko3d_glsl_opt.py`: pass `fetchconv` (after `plainfetch`), `files/tools/deko3d_glsl_opt.py`.
- `tools/deko3d_variant_cache.py`: 950-973 from the words, and each pipeline also with 51 / 52 off (their A/B halves).
- `render/draw.cpp` and `sasrt_gpu_round.*`: the hunks below.

### render/draw.cpp

`SasrtSpecWords` grows to 20 words:

```cpp
struct SasrtSpecWords {
  u32 w[20];
};
static_assert(sizeof(SasrtSpecWords::w) == sizeof(PipelineKey::sasrt_words));
```

At the end of `SasrtSpecWordsOf`, before `return s;`:

```cpp
  // sasrt-nx (2026-11-09, sasrt_gpu_fetch_conversion_spec; the fifth round): [12]-[15].
  if (ps_entry && On(sasrt::gpu_round::kFetchConvSpec)) {
    for (u32 bits = ps_entry->textureFetchMask & 0xFFu; bits; bits &= bits - 1) {
      const u32 r = u32(std::countr_zero(bits));
      const u32 sampler = sc.sampler_indices[r], word = sc.texture_indices[0][r];
      const u32 field = 0x8000u | ((sampler >> 16) & 15u) | ((sampler >> 13) & 7u) << 4 | ((word >> 20) & 63u) << 7;
      s.w[12 + r / 2] |= field << (16 * (r & 1));
    }
  }
  // sasrt-nx (2026-11-09, sasrt_gpu_fetch_exp_3d_spec): [16]-[19].
  if (ps_entry && On(sasrt::gpu_round::kFetchExpSpec)) {
    for (u32 bits = ps_entry->textureFetchMask & 0xFFu; bits; bits &= bits - 1) {
      const u32 r = u32(std::countr_zero(bits));
      s.w[16 + r / 4] |= (0x80u | ((sc.texture_indices[1][r] >> 20) & 63u)) << (8 * (r & 3));
      s.w[18 + r / 4] |= (0x80u | ((sc.texture_indices[2][r] >> 20) & 63u)) << (8 * (r & 3));
    }
  }
```

(`sc.sampler_indices[r]` is the deko3d sampler word: the slot in bits 20+, Xenos' sign / gamma bits at 13-19 as Renut
packs them; check RR6's tree packs them the same before porting.)

### sasrt_gpu_round.h / .cpp

After round 4's `kExportNoPointGs` (item 48), five entries keep RR6's A/B numbers equal to SASRT's (139-143). 49 and 50
have no code in RR6 (SASRT's EDRAM depth restore): define them as placeholders that do nothing, or port them with the
restore. 53 is optional (flat on the console).

```cpp
  /* the fifth round (2026-11-09, docs/gpu-round-1108.md "Round 5"): A/B 139 and up */                                     \
  X(kRestoreDirect, sasrt_gpu_depth_restore_direct, "SASRT only: the EDRAM depth restore in one pass") \
  X(kRestoreClear, sasrt_gpu_depth_restore_whole_clear, "SASRT only: the depth restore clears depth and stencil together") \
  X(kFetchConvSpec, sasrt_gpu_fetch_conversion_spec, "a non-plain fetch's sign, gamma and exponent words as constants of the draw (950-957)") \
  X(kFetchExpSpec, sasrt_gpu_fetch_exp_3d_spec, "a 3D or cube fetch's exponent adjust as a constant of the draw (958-973)") \
  X(kConvertVertexPass, sasrt_gpu_convert_vertex_pass, "exported stream conversions drawn as a vertex pass (flat: off)")
```

```cpp
REXCVAR_DEFINE_BOOL(sasrt_gpu_fetch_conversion_spec, true, "SASRT/GPU",
                    "deko3d renderer (fifth GPU round, item 51, A/B 141): a pixel shader's texture fetch applies Xenos' "
                    "signs, gamma and exponent adjust from the draw's words (SharedConstants: sampler bits 13-19, the 2D "
                    "texture word's bits 20-25) for each of the four channels, choosing among the conversions at run time; "
                    "item 3 (sasrt_gpu_plain_fetches) drops the block where a fetch constant has none of them. Here the "
                    "words of fetch constants 0-7 are constants of the draw (950-957, pass fetchconv), so the shader keeps "
                    "only the conversions the draw's texture has, on the channels that have them. The same operations on "
                    "the same values: the same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_fetch_exp_3d_spec, true, "SASRT/GPU",
                    "deko3d renderer (fifth GPU round, item 52, A/B 142): item 51 for the exponent adjust a 3D or cube fetch "
                    "reads from its own word (texture_indices[1] / [2] bits 20-25): constants 958-965 (3D) and 966-973 "
                    "(cube) for fetch constants 0-7 (pass fetchconv). Same values: the same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
```

(Placeholders for 49, 50, 53: `REXCVAR_DEFINE_BOOL(<key>, false, "SASRT/GPU", "SASRT only").lifecycle(kInitOnly)`.)

## After porting

Rebuild the DKSH cache with the fixed tool (`--sasrt-guess` as before); the variant count grows (51 / 52 make per-texture
variants of the pixel shaders: SASRT went from ~10.1 k to ~10.5 k). A race on the console compiles any it misses once
and the SD cache keeps them.

SASRT's own round 5 (cuts included) is in docs/gpu-round-1108.md "Round 5" once the round ends.
