# sasrt-nx (2026-11-11 ~11:20, the user: "implement everything on the 19 rows besides 78, 79 and 80 ... in one big
# batch"; "fix the 10-bit or 7e3 formats ... useful for the ultimate base"; "turn it on by default ... as it's more
# accurate"). docs/360-precision-differences.md. Rows 1-3: done earlier (tools/vmx_float_macros.py). This batch:
#   rows 6, 8, 10, 74, 93  renut_format_10bit_exact (ON): 2_10_10_10 targets / textures as host 10:10:10:2 (the console's
#                          own 32-bit layout) instead of 16 bits a channel; resolves follow (they take the target's format)
#   (found on the way)     renut_format_edram_as_variants (ON): target formats 10 / 12 fell to 8-bit RGBA
#   rows 7, 66, 73, 95, 96 renut_format_7e3_rg11b10 (OFF, not exact: no alpha, a mantissa bit or two less)
#   row 26                 renut_depth_float_no_stencil (OFF, a speed trade: breaks stencil use; logged)
#   row 38                 renut_float32_point_filter (ON): 32-bit float textures point-sampled, as the Xenos does
#   (diagnostic)           renut_diag_formats (ON, logging): the formats a session makes, and stencil use on depth
# Row 18 (CTX1 / DXT3A): no smaller host format holds them losslessly (DXT5A / DXN are already BC4 / BC5): not changed.
# Idempotent; asserts every anchor once.
R = 'D:/sonic transformed/sasrt-nx/'
MARK = 'renut_format_10bit_exact'


def patch(path, edits, mark=MARK):
    b = open(R + path, 'rb').read()
    crlf = b'\r\n' in b
    s = b.decode('utf-8').replace('\r\n', '\n')
    if mark in s:
        print('already patched:', path)
        return
    for old, new in edits:
        assert s.count(old) == 1, (path, old[:80], s.count(old))
        s = s.replace(old, new)
    open(R + path, 'wb').write((s.replace('\n', '\r\n') if crlf else s).encode('utf-8'))
    print('patched:', path)


PLUME_MARK = 'R10G10B10A2_UNORM'
# ---- plume: two formats --------------------------------------------------------------------------------------------
patch('app/thirdparty/plume/plume_render_interface_types.h', [
    ('''        D24_UNORM_S8_UINT,
        MAX
    };''', '''        D24_UNORM_S8_UINT,
        // sasrt-nx (2026-11-11, renut_format_10bit_exact): 10:10:10:2 unorm, R in bits 0-9 ... A in 30-31 (the Xenos
        // 2_10_10_10's own 32-bit layout; deko3d RGB10A2, Vulkan A2B10G10R10_PACK32, D3D12 R10G10B10A2).
        R10G10B10A2_UNORM,
        // sasrt-nx (2026-11-11, renut_format_7e3_rg11b10): 11:11:10 unsigned float, no alpha (deko3d RG11B10).
        R11G11B10_FLOAT,
        MAX
    };'''),
    ('''        case RenderFormat::D24_UNORM_S8_UINT:
            return 4;''', '''        case RenderFormat::D24_UNORM_S8_UINT:
        case RenderFormat::R10G10B10A2_UNORM:  // sasrt-nx (2026-11-11)
        case RenderFormat::R11G11B10_FLOAT:    // sasrt-nx (2026-11-11)
            return 4;'''),
    ('''        case RenderFormat::D24_UNORM_S8_UINT:
        case RenderFormat::R32_FLOAT:''', '''        case RenderFormat::D24_UNORM_S8_UINT:
        case RenderFormat::R10G10B10A2_UNORM:  // sasrt-nx (2026-11-11)
        case RenderFormat::R11G11B10_FLOAT:    // sasrt-nx (2026-11-11)
        case RenderFormat::R32_FLOAT:'''),
], mark=PLUME_MARK)
patch('app/thirdparty/plume/plume_deko3d.cpp', [
    ('''        case RenderFormat::D24_UNORM_S8_UINT: return DkImageFormat_Z24S8;  // banjo-nx (2026-10-19)''',
     '''        case RenderFormat::D24_UNORM_S8_UINT: return DkImageFormat_Z24S8;  // banjo-nx (2026-10-19)
        case RenderFormat::R10G10B10A2_UNORM: return DkImageFormat_RGB10A2_Unorm;  // sasrt-nx (2026-11-11)
        case RenderFormat::R11G11B10_FLOAT: return DkImageFormat_RG11B10_Float;    // sasrt-nx (2026-11-11)'''),
], mark=PLUME_MARK)
patch('app/thirdparty/plume/plume_vulkan.cpp', [
    ('''        case RenderFormat::D24_UNORM_S8_UINT:  // banjo-nx (2026-10-19)
            return VK_FORMAT_D24_UNORM_S8_UINT;''', '''        case RenderFormat::D24_UNORM_S8_UINT:  // banjo-nx (2026-10-19)
            return VK_FORMAT_D24_UNORM_S8_UINT;
        case RenderFormat::R10G10B10A2_UNORM:  // sasrt-nx (2026-11-11)
            return VK_FORMAT_A2B10G10R10_UNORM_PACK32;
        case RenderFormat::R11G11B10_FLOAT:  // sasrt-nx (2026-11-11)
            return VK_FORMAT_B10G11R11_UFLOAT_PACK32;'''),
], mark=PLUME_MARK)
patch('app/thirdparty/plume/plume_d3d12.cpp', [
    ('''        case RenderFormat::D24_UNORM_S8_UINT:  // banjo-nx (2026-10-19): typeless, as above
            return DXGI_FORMAT_R24G8_TYPELESS;''', '''        case RenderFormat::D24_UNORM_S8_UINT:  // banjo-nx (2026-10-19): typeless, as above
            return DXGI_FORMAT_R24G8_TYPELESS;
        case RenderFormat::R10G10B10A2_UNORM:  // sasrt-nx (2026-11-11)
            return DXGI_FORMAT_R10G10B10A2_UNORM;
        case RenderFormat::R11G11B10_FLOAT:  // sasrt-nx (2026-11-11)
            return DXGI_FORMAT_R11G11B10_FLOAT;'''),
], mark=PLUME_MARK)

# ---- Renut: format.h / format.cpp ------------------------------------------------------------------------------------
patch('app/src/renut_engine/gpu/render/format.h', [
    ('''  Fmt16_16_16_16_Float = 7,
  Fmt32_Float = 14,''', '''  Fmt16_16_16_16_Float = 7,
  // sasrt-nx (2026-11-11, renut_format_edram_as_variants): the two EDRAM formats that fell to 8-bit RGBA before.
  Fmt2_10_10_10_As10_10_10_10 = 10,
  Fmt2_10_10_10_Float_As16_16_16_16 = 12,
  Fmt32_Float = 14,'''),
    ('''plume::RenderFormat ColorTargetFormat(GpuColorFormat format);''',
     '''plume::RenderFormat ColorTargetFormat(GpuColorFormat format);
// sasrt-nx (2026-11-11, docs/360-precision-differences.md; format.cpp's keys, renut_format_10bit_exact and the others):
bool Format10BitExactOn();
bool Float32PointFilterOn();
bool DepthFloatNoStencilOn();
bool DiagFormatsOn();
bool IsFloat32TextureFormat(GpuTextureFormat format);
const char *GpuTextureFormatName(u32 format);  // for the logs'''),
])
patch('app/src/renut_engine/gpu/render/format.cpp', [
    ('''REXCVAR_DECLARE(bool, sasrt_renut_fixed16_float);  // sasrt-nx (2026-11-08): renut-ultimate's now (gpu/ultimate.cpp)''',
     '''REXCVAR_DECLARE(bool, sasrt_renut_fixed16_float);  // sasrt-nx (2026-11-08): renut-ultimate's now (gpu/ultimate.cpp)

// sasrt-nx (2026-11-11, the user: "implement everything on the 19 rows", "useful for the ultimate base", "turn it on by
// default ... as it's more accurate"; docs/360-precision-differences.md): where the renderer kept more than the Xenos
// did at a speed cost. Universal (any game's targets and textures of these formats).
REXCVAR_DEFINE_BOOL(renut_format_10bit_exact, true, "Renut/Formats",
                    "Xenos 2_10_10_10 render targets and textures in the host's 10:10:10:2 format (the console's own 32 "
                    "bits a pixel, the same values) instead of 16 bits a channel; their resolves follow. Off: 16 bits a "
                    "channel, as before")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(renut_format_edram_as_variants, true, "Renut/Formats",
                    "The Xenos target formats 2_10_10_10_AS_10_10_10_10 and 2_10_10_10_FLOAT_AS_16_16_16_16 as 10:10:10:2 "
                    "(16 bits a channel without renut_format_10bit_exact) and FP16; off: 8-bit RGBA, as before (less "
                    "than the console keeps)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(renut_format_7e3_rg11b10, false, "Renut/Formats",
                    "NOT exact: Xenos 7e3 targets (2_10_10_10_FLOAT) as 11:11:10 float, half FP16's bytes. No alpha (the "
                    "7e3's 2 bits read as 1) and one mantissa bit less on red and green, two on blue; more range. Off: "
                    "FP16")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(renut_depth_float_no_stencil, false, "Renut/Formats",
                    "A speed trade: Xenos float depth targets (D24FS8) as 32-bit float depth without a stencil plane "
                    "(half the bytes of D32F_S8). Stencil on them then does nothing: the first uses are logged "
                    "(renut_diag_formats). Off: D32F with stencil")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(renut_float32_point_filter, true, "Renut/Formats",
                    "32-bit float textures point-sampled whatever the sampler asks, as the Xenos (which cannot filter "
                    "them) samples them; off: filtered linearly when asked")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(renut_diag_formats, true, "Renut/Formats",
                    "Diagnostic, logging only: the first targets and textures of each format a session makes (guest and "
                    "host formats), the first stencil use on each depth target, the first float textures asked for "
                    "linear filtering")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);'''),
    ('''namespace renut::gpu {

plume::RenderFormat ColorTargetFormat(GpuColorFormat format) {
  switch (format) {
  case GpuColorFormat::Fmt8_8_8_8:
  case GpuColorFormat::Fmt8_8_8_8_Gamma:
    return plume::RenderFormat::R8G8B8A8_UNORM;
  case GpuColorFormat::Fmt2_10_10_10:
    return plume::RenderFormat::R16G16B16A16_UNORM;
  case GpuColorFormat::Fmt2_10_10_10_Float:
  case GpuColorFormat::Fmt16_16_16_16_Float:
    return plume::RenderFormat::R16G16B16A16_FLOAT;''', '''namespace renut::gpu {

bool Format10BitExactOn() {
  static const bool on = REXCVAR_GET(renut_format_10bit_exact);
  return on;
}
bool Float32PointFilterOn() {
  static const bool on = REXCVAR_GET(renut_float32_point_filter);
  return on;
}
bool DepthFloatNoStencilOn() {
  static const bool on = REXCVAR_GET(renut_depth_float_no_stencil);
  return on;
}
bool DiagFormatsOn() {
  static const bool on = REXCVAR_GET(renut_diag_formats);
  return on;
}
bool IsFloat32TextureFormat(GpuTextureFormat format) {
  return format == GpuTextureFormat::Fmt32_Float || format == GpuTextureFormat::Fmt32_32_Float ||
         format == GpuTextureFormat::Fmt32_32_32_32_Float || format == GpuTextureFormat::Fmt32_32_32_Float;
}
const char *GpuTextureFormatName(u32 format) {
  switch (format & 0x3F) {
  case 2: return "8";
  case 6: return "8_8_8_8";
  case 7: return "2_10_10_10";
  case 10: return "8_8";
  case 18: return "DXT1";
  case 19: return "DXT2_3";
  case 20: return "DXT4_5";
  case 22: return "24_8 (D24S8)";
  case 23: return "24_8_FLOAT (D24FS8)";
  case 25: return "16_16";
  case 26: return "16_16_16_16";
  case 31: return "16_16_FLOAT";
  case 32: return "16_16_16_16_FLOAT";
  case 36: return "32_FLOAT";
  case 37: return "32_32_FLOAT";
  case 38: return "32_32_32_32_FLOAT";
  case 49: return "DXN";
  case 54: return "2_10_10_10_AS_16_16_16_16";
  case 58: return "DXT3A";
  case 59: return "DXT5A";
  case 60: return "CTX1";
  case 57: return "32_32_32_FLOAT";
  case 62: return "8_8_8_8_GAMMA_EDRAM";
  case 63: return "2_10_10_10_FLOAT (7e3)";
  default: return "?";
  }
}

plume::RenderFormat ColorTargetFormat(GpuColorFormat format) {
  static const bool fp10_packed = REXCVAR_GET(renut_format_7e3_rg11b10);
  static const bool as_variants = REXCVAR_GET(renut_format_edram_as_variants);
  switch (format) {
  case GpuColorFormat::Fmt8_8_8_8:
  case GpuColorFormat::Fmt8_8_8_8_Gamma:
    return plume::RenderFormat::R8G8B8A8_UNORM;
  // sasrt-nx (2026-11-11, renut_format_10bit_exact): the console's own 32 bits; 16 bits a channel before.
  case GpuColorFormat::Fmt2_10_10_10:
    return Format10BitExactOn() ? plume::RenderFormat::R10G10B10A2_UNORM : plume::RenderFormat::R16G16B16A16_UNORM;
  // sasrt-nx (2026-11-11, renut_format_7e3_rg11b10, NOT exact, off): 7e3 in 32 bits without alpha.
  case GpuColorFormat::Fmt2_10_10_10_Float:
    return fp10_packed ? plume::RenderFormat::R11G11B10_FLOAT : plume::RenderFormat::R16G16B16A16_FLOAT;
  case GpuColorFormat::Fmt16_16_16_16_Float:
    return plume::RenderFormat::R16G16B16A16_FLOAT;
  // sasrt-nx (2026-11-11, renut_format_edram_as_variants): these two fell to the default (8-bit RGBA) before.
  case GpuColorFormat::Fmt2_10_10_10_As10_10_10_10:
    if (!as_variants)
      return plume::RenderFormat::R8G8B8A8_UNORM;
    return Format10BitExactOn() ? plume::RenderFormat::R10G10B10A2_UNORM : plume::RenderFormat::R16G16B16A16_UNORM;
  case GpuColorFormat::Fmt2_10_10_10_Float_As16_16_16_16:  // (audit finding 7: as format 3, one storage format)
    if (!as_variants)
      return plume::RenderFormat::R8G8B8A8_UNORM;
    return fp10_packed ? plume::RenderFormat::R11G11B10_FLOAT : plume::RenderFormat::R16G16B16A16_FLOAT;'''),
    ('''  case T::Fmt2_10_10_10:
  case T::Fmt2_10_10_10_As16_16_16_16:
    return expand(F::R16G16B16A16_UNORM, C::R10G10B10A2, 4, 8);''', '''  // sasrt-nx (2026-11-11, renut_format_10bit_exact): 2_10_10_10 copied as it is into 10:10:10:2 (X in bits 0-9 is the
  // host's R, as the expansion below read it); the _AS_16_16_16_16 form (filtered at 16 bits on the console) keeps 16.
  case T::Fmt2_10_10_10:
    if (Format10BitExactOn())
      return plain(F::R10G10B10A2_UNORM, 4);
    return expand(F::R16G16B16A16_UNORM, C::R10G10B10A2, 4, 8);
  case T::Fmt2_10_10_10_As16_16_16_16:
    return expand(F::R16G16B16A16_UNORM, C::R10G10B10A2, 4, 8);'''),
])

# ---- surfaces.cpp: row 26 and the target census -----------------------------------------------------------------------
patch('app/src/renut_engine/gpu/render/surfaces.cpp', [
    ('''    if (surface.format != DepthTargetFormat()) {
      static uint32_t logged = 0;
      if (logged++ < 16)
        RGPU_INFO("Depth target {:08X}: {}x{} x{} samples, 24-bit unorm depth with stencil (banjo_deko3d_depth24)",
                  surface.guest_va, surface.width, surface.height, u32(surface.samples));
    }
  } else {
    surface.format = SurfaceColorFormat(desc);
  }''', '''    // sasrt-nx (2026-11-11, renut_depth_float_no_stencil, a speed trade, off; docs/360-precision-differences.md row 26):
    // any float depth target (D24FS8) without a stencil plane, as the shadow rule above does for the shadow maps.
    if (DepthFloatNoStencilOn() && surface.format == plume::RenderFormat::D32_FLOAT_S8_UINT &&
        (surface.format_word & 0x3F) == u32(GpuTextureFormat::Fmt24_8_Float)) {
      surface.format = plume::RenderFormat::D32_FLOAT;
      static uint32_t logged = 0;
      if (logged++ < 8)
        RGPU_INFO("[formats] depth target {:08X} {}x{} made D32F without stencil (renut_depth_float_no_stencil)",
                  surface.guest_va, surface.width, surface.height);
    }
    if (surface.format == plume::RenderFormat::D24_UNORM_S8_UINT) {  // sasrt-nx (2026-11-11): only that format's line
      static uint32_t logged = 0;
      if (logged++ < 16)
        RGPU_INFO("Depth target {:08X}: {}x{} x{} samples, 24-bit unorm depth with stencil (banjo_deko3d_depth24)",
                  surface.guest_va, surface.width, surface.height, u32(surface.samples));
    }
  } else {
    surface.format = SurfaceColorFormat(desc);
  }
  // sasrt-nx (2026-11-11, renut_diag_formats): the first target of each guest format / host format / size.
  if (DiagFormatsOn()) {
    static std::vector<uint64_t> seen;
    const uint32_t colour_format = (u32(desc.ColorInfo) >> 16) & 0xF;
    const uint64_t key = uint64_t(surface.depth) << 63 | uint64_t(surface.format_word & 0x3F) << 50 |
                         uint64_t(colour_format) << 46 | uint64_t(surface.format) << 32;  // (audit finding 8: no size)
    if (seen.size() < 96 && std::find(seen.begin(), seen.end(), key) == seen.end()) {
      seen.push_back(key);
      RGPU_INFO("[formats] {} target {}x{}: guest format {} ({}), EDRAM colour format {}, host format {}",
                surface.depth ? "depth" : "colour", surface.width, surface.height, surface.format_word & 0x3F,
                GpuTextureFormatName(surface.format_word), surface.depth ? -1 : int(colour_format),
                int(surface.format));
    }
  }'''),
], mark='renut_depth_float_no_stencil')

# ---- draw.cpp: the stencil census ------------------------------------------------------------------------------------
patch('app/src/renut_engine/gpu/render/draw.cpp', [
    ('''void SasrtWarnStencilOnD32f(const HostSurface *d) {
  if (d && d->depth && d->format == plume::RenderFormat::D32_FLOAT) {''', '''void SasrtWarnStencilOnD32f(const HostSurface *d, bool clear = false, bool first = false) {
  // sasrt-nx (2026-11-11, renut_diag_formats; renut_depth_float_no_stencil's question): the first stencil use of each
  // target build ('first': its stencil_used was still false; audit finding 6: no lookup on every stencil draw).
  if (first && d && d->depth && DiagFormatsOn()) {
    static uint32_t logged = 0;
    if (logged++ < 48)
      RGPU_INFO("[formats] stencil {} on depth target {:08X} {}x{} (guest format {}, host format {})",
                clear ? "cleared" : "used by a draw", d->guest_va, d->width, d->height,
                GpuTextureFormatName(d->format_word), int(d->format));
  }
  if (d && d->depth && d->format == plume::RenderFormat::D32_FLOAT) {'''),
    ('''  if (t.depth && (flags & 0x20)) {
    t.depth->stencil_used = true;
    SasrtWarnStencilOnD32f(t.depth);  // sasrt-nx (2026-11-08, sasrt_gpu_exp_shadow_d32f)''',
     '''  if (t.depth && (flags & 0x20)) {
    const bool first_stencil = !t.depth->stencil_used;  // sasrt-nx (2026-11-11, renut_diag_formats)
    t.depth->stencil_used = true;
    SasrtWarnStencilOnD32f(t.depth, true, first_stencil);  // sasrt-nx (2026-11-08; 2026-11-11: a clear)'''),
], mark='renut_diag_formats; renut_depth_float_no_stencil')

# ---- textures.cpp: row 38 and the texture census -----------------------------------------------------------------------
patch('app/src/renut_engine/gpu/render/textures.cpp', [
    ('''  t.guest_format = fetch.Format();
  t.info = GetTextureFormatInfo(fetch.Format(), AllSigned(fetch));''', '''  t.guest_format = fetch.Format();
  t.info = GetTextureFormatInfo(fetch.Format(), AllSigned(fetch));
  // sasrt-nx (2026-11-11, renut_diag_formats): the first texture of each guest format / host format.
  if (DiagFormatsOn()) {
    static std::vector<uint32_t> seen;
    const plume::RenderFormat host = render_target ? rt_format : t.info.host;  // a resolve destination's: the target's
    const uint32_t key = u32(fetch.Format()) << 16 | u32(host) << 1 | (render_target ? 1u : 0u);
    if (seen.size() < 96 && std::find(seen.begin(), seen.end(), key) == seen.end()) {
      seen.push_back(key);
      RGPU_INFO("[formats] first {} of guest format {} ({}): host format {}, {}x{}",
                render_target ? "resolve destination" : "texture", u32(fetch.Format()), GpuTextureFormatName(u32(fetch.Format())),
                int(host), width, height);
    }
  }'''),
    ('''    uint32_t cuts = 0;  // sasrt-nx (2026-11-09): sasrt::gpu_round::SamplerCutBits
    uint32_t slot = 0;
  };''', '''    uint32_t cuts = 0;  // sasrt-nx (2026-11-09): sasrt::gpu_round::SamplerCutBits
    bool f32_point = false;  // sasrt-nx (2026-11-11, renut_float32_point_filter): the format is not in the words
    uint32_t slot = 0;
  };'''),
    ('''  const u32 words[4] = {fetch.dword[0], fetch.dword[3], fetch.dword[4], fetch.dword[5]};
  Memo &entry = memo[(words[0] * 0x9E3779B1u ^ words[1] * 0x85EBCA6Bu ^ words[2] * 0xC2B2AE35u ^
                      words[3] ^ lod_scale.code * 0x27D4EB2Fu) >> 24];
  if (entry.valid && entry.lod_scale == lod_scale && entry.min_anisotropy == min_anisotropy && entry.cuts == cuts &&
      std::memcmp(entry.words, words, sizeof(words)) == 0)
    return entry.slot;''', '''  const u32 words[4] = {fetch.dword[0], fetch.dword[3], fetch.dword[4], fetch.dword[5]};
  const bool f32_point = Float32PointFilterOn() && IsFloat32TextureFormat(fetch.Format());  // sasrt-nx (2026-11-11)
  Memo &entry = memo[(words[0] * 0x9E3779B1u ^ words[1] * 0x85EBCA6Bu ^ words[2] * 0xC2B2AE35u ^
                      words[3] ^ lod_scale.code * 0x27D4EB2Fu ^ (f32_point ? 0x5BD1E995u : 0u)) >> 24];
  if (entry.valid && entry.lod_scale == lod_scale && entry.min_anisotropy == min_anisotropy && entry.cuts == cuts &&
      entry.f32_point == f32_point && std::memcmp(entry.words, words, sizeof(words)) == 0)
    return entry.slot;'''),
    ('''  entry.cuts = cuts;
  entry.slot = slot;''', '''  entry.cuts = cuts;
  entry.f32_point = f32_point;
  entry.slot = slot;'''),
    ('''  desc.minLOD = float(fetch.MinMipLevel());
  desc.maxLOD = fetch.MipFilter() == TextureFilter::BaseMap ? float(fetch.MinMipLevel())
                                                            : float(fetch.MaxMipLevel());''', '''  // sasrt-nx (2026-11-11, renut_float32_point_filter; docs/360-precision-differences.md row 38): the Xenos cannot filter
  // 32-bit float textures and point-samples them whatever the sampler asks; the host filtered them when asked.
  if (Float32PointFilterOn() && IsFloat32TextureFormat(fetch.Format())) {
    const bool asked = desc.minFilter == plume::RenderFilter::LINEAR || desc.magFilter == plume::RenderFilter::LINEAR ||
                       desc.mipmapMode == plume::RenderMipmapMode::LINEAR || desc.anisotropyEnabled;
    if (asked && DiagFormatsOn()) {
      static uint32_t logged = 0;
      if (logged++ < 8)
        RGPU_INFO("[formats] a 32-bit float texture (guest format {}) asked for filtering: point-sampled "
                  "(renut_float32_point_filter)", u32(fetch.Format()));
    }
    desc.minFilter = plume::RenderFilter::NEAREST;
    desc.magFilter = plume::RenderFilter::NEAREST;
    desc.mipmapMode = plume::RenderMipmapMode::NEAREST;
    desc.anisotropyEnabled = false;
    desc.maxAnisotropy = 1;
  }
  desc.minLOD = float(fetch.MinMipLevel());
  desc.maxLOD = fetch.MipFilter() == TextureFilter::BaseMap ? float(fetch.MinMipLevel())
                                                            : float(fetch.MaxMipLevel());'''),
], mark='renut_float32_point_filter')
# ---- the audit's findings 1, 2, 6 (draw sites) and 8 (format.h comment) ---------------------------------------------
patch('app/src/renut_engine/gpu/render/draw.cpp', [
    # audit finding 1: the drawn resolve copy takes the new formats (a texel load gives them back exactly)
    ('''  case plume::RenderFormat::R16G16B16A16_UNORM:
  case plume::RenderFormat::R16G16B16A16_FLOAT:
  case plume::RenderFormat::R16G16_UNORM:''', '''  case plume::RenderFormat::R16G16B16A16_UNORM:
  case plume::RenderFormat::R10G10B10A2_UNORM:  // sasrt-nx (2026-11-11, renut_format_10bit_exact; audit finding 1)
  case plume::RenderFormat::R11G11B10_FLOAT:    // sasrt-nx (2026-11-11, renut_format_7e3_rg11b10)
  case plume::RenderFormat::R16G16B16A16_FLOAT:
  case plume::RenderFormat::R16G16_UNORM:'''),
    ('''    if (dc & 1) {
      targets.depth->stencil_used = true;
      SasrtWarnStencilOnD32f(targets.depth);  // sasrt-nx (2026-11-08, sasrt_gpu_exp_shadow_d32f)''', '''    if (dc & 1) {
      const bool first_stencil = !targets.depth->stencil_used;  // sasrt-nx (2026-11-11, renut_diag_formats)
      targets.depth->stencil_used = true;
      SasrtWarnStencilOnD32f(targets.depth, false, first_stencil);  // sasrt-nx (2026-11-08, sasrt_gpu_exp_shadow_d32f)'''),
    ('''    if (dc & 1) {
      targets.depth->stencil_used = true;  // banjo-nx (2026-10-19, banjo_deko3d_depth_handover)
      SasrtWarnStencilOnD32f(targets.depth);  // sasrt-nx (2026-11-08, sasrt_gpu_exp_shadow_d32f)''', '''    if (dc & 1) {
      const bool first_stencil = !targets.depth->stencil_used;  // sasrt-nx (2026-11-11, renut_diag_formats)
      targets.depth->stencil_used = true;  // banjo-nx (2026-10-19, banjo_deko3d_depth_handover)
      SasrtWarnStencilOnD32f(targets.depth, false, first_stencil);  // sasrt-nx (2026-11-08, sasrt_gpu_exp_shadow_d32f)'''),
], mark='audit finding 1')
patch('app/src/renut_engine/gpu/render/pipeline.cpp', [
    # audit finding 2: 10:10:10:2 clamps as the other UNORM targets do, so the blend skip holds for it
    ('''  case plume::RenderFormat::R16G16B16A16_UNORM:
  case plume::RenderFormat::R8G8_UNORM:
  case plume::RenderFormat::R8_UNORM:''', '''  case plume::RenderFormat::R16G16B16A16_UNORM:
  case plume::RenderFormat::R10G10B10A2_UNORM:  // sasrt-nx (2026-11-11, renut_format_10bit_exact; audit finding 2)
  case plume::RenderFormat::R8G8_UNORM:
  case plume::RenderFormat::R8_UNORM:'''),
    ('''  case F::R32G32_FLOAT:
    return 0x3;
  default:
    return 0xF;''', '''  case F::R32G32_FLOAT:
    return 0x3;
  case F::R11G11B10_FLOAT:  // sasrt-nx (2026-11-11, renut_format_7e3_rg11b10; audit finding 2): no alpha
    return 0x7;
  default:
    return 0xF;'''),
], mark='audit finding 2')
patch('app/src/renut_engine/gpu/render/format.h', [
    ('''  R10G10B10A2,   // expanded to RGBA16 UNORM (plume has no 10:10:10:2 format)''',
     '''  R10G10B10A2,   // expanded to RGBA16 UNORM (the _AS_16_16_16_16 form, and renut_format_10bit_exact off; on, 2_10_10_10
                 // is copied as it is into R10G10B10A2_UNORM; audit finding 8)'''),
], mark='audit finding 8')
print('batch_formats: done')
