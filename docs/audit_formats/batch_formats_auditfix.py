# The audit's fixes (2026-11-11 ~11:25, one agent's review of docs/audit_formats/batch_formats.diff), applied to the
# staged script batch_formats.py itself (not yet run on the tree), plus new patch() calls appended to it.
p = '<scratchpad>/batch_formats.py'
s = open(p, encoding='utf-8').read()
if 'audit finding 1' in s:
    raise SystemExit('already done')


def rep(old, new):
    global s
    assert s.count(old) == 1, (old[:90], s.count(old))
    s = s.replace(old, new)


# Finding 3: code 62 is 8_8_8_8_GAMMA_EDRAM; 57 (32_32_32_FLOAT) named.
rep('''  case 62: return "2_10_10_10_FLOAT_AS_16 (7e3)";''', '''  case 57: return "32_32_32_FLOAT";
  case 62: return "8_8_8_8_GAMMA_EDRAM";''')
# Finding 7: colour format 12 follows format 3 under the 11:11:10 option (one storage format for both, as xenia's).
rep('''  case GpuColorFormat::Fmt2_10_10_10_Float_As16_16_16_16:
    return as_variants ? plume::RenderFormat::R16G16B16A16_FLOAT : plume::RenderFormat::R8G8B8A8_UNORM;''',
    '''  case GpuColorFormat::Fmt2_10_10_10_Float_As16_16_16_16:  // (audit finding 7: as format 3, one storage format)
    if (!as_variants)
      return plume::RenderFormat::R8G8B8A8_UNORM;
    return fp10_packed ? plume::RenderFormat::R11G11B10_FLOAT : plume::RenderFormat::R16G16B16A16_FLOAT;''')
# Finding 8: the target census keyed by format alone (sizes still logged); Create's census uses its own width/height.
rep('''    const uint64_t key = uint64_t(surface.depth) << 63 | uint64_t(surface.format_word & 0x3F) << 50 |
                         uint64_t(colour_format) << 46 | uint64_t(surface.format) << 32 | uint64_t(surface.width) << 16 |
                         uint64_t(surface.height);''', '''    const uint64_t key = uint64_t(surface.depth) << 63 | uint64_t(surface.format_word & 0x3F) << 50 |
                         uint64_t(colour_format) << 46 | uint64_t(surface.format) << 32;  // (audit finding 8: no size)''')
rep('''      u32 w, h, d;
      fetch.Size(w, h, d);
      RGPU_INFO("[formats] first {} of guest format {} ({}): host format {}, {}x{}",''', '''      RGPU_INFO("[formats] first {} of guest format {} ({}): host format {}, {}x{}",''')
rep('''                int(host), w, h);''', '''                int(host), width, height);''')
# Finding 6: the stencil census once per target build (stencil_used's first setting), no per-draw lookup.
rep('''void SasrtWarnStencilOnD32f(const HostSurface *d, bool clear = false) {
  // sasrt-nx (2026-11-11, renut_diag_formats; renut_depth_float_no_stencil's question): the first stencil use, by a draw
  // and by a clear, on each depth target.
  if (d && d->depth && DiagFormatsOn()) {
    static std::vector<uint64_t> seen;
    const uint64_t key = uint64_t(d->guest_va) << 1 | (clear ? 1u : 0u);
    if (seen.size() < 32 && std::find(seen.begin(), seen.end(), key) == seen.end()) {
      seen.push_back(key);
      RGPU_INFO("[formats] stencil {} on depth target {:08X} {}x{} (guest format {}, host format {})",
                clear ? "cleared" : "used by a draw", d->guest_va, d->width, d->height,
                GpuTextureFormatName(d->format_word), int(d->format));
    }
  }''', '''void SasrtWarnStencilOnD32f(const HostSurface *d, bool clear = false, bool first = false) {
  // sasrt-nx (2026-11-11, renut_diag_formats; renut_depth_float_no_stencil's question): the first stencil use of each
  // target build ('first': its stencil_used was still false; audit finding 6: no lookup on every stencil draw).
  if (first && d && d->depth && DiagFormatsOn()) {
    static uint32_t logged = 0;
    if (logged++ < 48)
      RGPU_INFO("[formats] stencil {} on depth target {:08X} {}x{} (guest format {}, host format {})",
                clear ? "cleared" : "used by a draw", d->guest_va, d->width, d->height,
                GpuTextureFormatName(d->format_word), int(d->format));
  }''')
rep('''    SasrtWarnStencilOnD32f(t.depth, true);  // sasrt-nx (2026-11-08, sasrt_gpu_exp_shadow_d32f; 2026-11-11: a clear)''',
    '''    SasrtWarnStencilOnD32f(t.depth, true, first_stencil);  // sasrt-nx (2026-11-08; 2026-11-11: a clear)''')
rep('''  if (t.depth && (flags & 0x20)) {
    t.depth->stencil_used = true;
    SasrtWarnStencilOnD32f(t.depth, true, first_stencil);''', '''  if (t.depth && (flags & 0x20)) {
    const bool first_stencil = !t.depth->stencil_used;  // sasrt-nx (2026-11-11, renut_diag_formats)
    t.depth->stencil_used = true;
    SasrtWarnStencilOnD32f(t.depth, true, first_stencil);''')
# The two draw call sites, findings 1 and 2, and the format.h comment: new patch() calls after the textures.cpp one.
rep('''print('batch_formats: done')''', '''# ---- the audit's findings 1, 2, 6 (draw sites) and 8 (format.h comment) ---------------------------------------------
patch('app/src/renut_engine/gpu/render/draw.cpp', [
    # audit finding 1: the drawn resolve copy takes the new formats (a texel load gives them back exactly)
    (\'\'\'  case plume::RenderFormat::R16G16B16A16_UNORM:
  case plume::RenderFormat::R16G16B16A16_FLOAT:
  case plume::RenderFormat::R16G16_UNORM:\'\'\', \'\'\'  case plume::RenderFormat::R16G16B16A16_UNORM:
  case plume::RenderFormat::R10G10B10A2_UNORM:  // sasrt-nx (2026-11-11, renut_format_10bit_exact; audit finding 1)
  case plume::RenderFormat::R11G11B10_FLOAT:    // sasrt-nx (2026-11-11, renut_format_7e3_rg11b10)
  case plume::RenderFormat::R16G16B16A16_FLOAT:
  case plume::RenderFormat::R16G16_UNORM:\'\'\'),
    (\'\'\'    if (dc & 1) {
      targets.depth->stencil_used = true;
      SasrtWarnStencilOnD32f(targets.depth);  // sasrt-nx (2026-11-08, sasrt_gpu_exp_shadow_d32f)\'\'\', \'\'\'    if (dc & 1) {
      const bool first_stencil = !targets.depth->stencil_used;  // sasrt-nx (2026-11-11, renut_diag_formats)
      targets.depth->stencil_used = true;
      SasrtWarnStencilOnD32f(targets.depth, false, first_stencil);  // sasrt-nx (2026-11-08, sasrt_gpu_exp_shadow_d32f)\'\'\'),
    (\'\'\'    if (dc & 1) {
      targets.depth->stencil_used = true;  // banjo-nx (2026-10-19, banjo_deko3d_depth_handover)
      SasrtWarnStencilOnD32f(targets.depth);  // sasrt-nx (2026-11-08, sasrt_gpu_exp_shadow_d32f)\'\'\', \'\'\'    if (dc & 1) {
      const bool first_stencil = !targets.depth->stencil_used;  // sasrt-nx (2026-11-11, renut_diag_formats)
      targets.depth->stencil_used = true;  // banjo-nx (2026-10-19, banjo_deko3d_depth_handover)
      SasrtWarnStencilOnD32f(targets.depth, false, first_stencil);  // sasrt-nx (2026-11-08, sasrt_gpu_exp_shadow_d32f)\'\'\'),
], mark='audit finding 1')
patch('app/src/renut_engine/gpu/render/pipeline.cpp', [
    # audit finding 2: 10:10:10:2 clamps as the other UNORM targets do, so the blend skip holds for it
    (\'\'\'  case plume::RenderFormat::R16G16B16A16_UNORM:
  case plume::RenderFormat::R8G8_UNORM:
  case plume::RenderFormat::R8_UNORM:\'\'\', \'\'\'  case plume::RenderFormat::R16G16B16A16_UNORM:
  case plume::RenderFormat::R10G10B10A2_UNORM:  // sasrt-nx (2026-11-11, renut_format_10bit_exact; audit finding 2)
  case plume::RenderFormat::R8G8_UNORM:
  case plume::RenderFormat::R8_UNORM:\'\'\'),
    (\'\'\'  case F::R32G32_FLOAT:
    return 0x3;
  default:
    return 0xF;\'\'\', \'\'\'  case F::R32G32_FLOAT:
    return 0x3;
  case F::R11G11B10_FLOAT:  // sasrt-nx (2026-11-11, renut_format_7e3_rg11b10; audit finding 2): no alpha
    return 0x7;
  default:
    return 0xF;\'\'\'),
], mark='audit finding 2')
patch('app/src/renut_engine/gpu/render/format.h', [
    (\'\'\'  R10G10B10A2,   // expanded to RGBA16 UNORM (plume has no 10:10:10:2 format)\'\'\',
     \'\'\'  R10G10B10A2,   // expanded to RGBA16 UNORM (the _AS_16_16_16_16 form, and renut_format_10bit_exact off; on, 2_10_10_10
                 // is copied as it is into R10G10B10A2_UNORM; audit finding 8)\'\'\'),
], mark='audit finding 8')
print('batch_formats: done')''')
open(p, 'w', encoding='utf-8').write(s)
print('auditfix applied to the staged script')
