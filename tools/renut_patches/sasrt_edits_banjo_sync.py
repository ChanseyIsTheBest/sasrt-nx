"""This port's EDITS after the banjo-nx sync of 2026-10-29 (tools/renut_from_sa2.py; docs/deko3d-renderer.md "Banjo sync
2026-10-29"): the source tree became banjo-nx 894d3256 merged three-way with sa2-nx's retargeting
(out/renut_sources/sa2_banjo). Applied by sasrt_edits.py at its end:

  - REANCHORED: entries whose text banjo-nx's rewrite moved or changed, given the same change on the new text (by
    index, with the first line of the old text each was written for, so a reordered list is caught);
  - DROPPED: entries banjo-nx's own work now does (its stream cache pressure and no-hash-at-the-cap, its packed vertex
    component tables, its measured defaults), entries merged into another entry here, and layout-log diagnostics of the
    octopus hunt (sasrt_renut_diag_layout_log, 2026-10-21) whose places banjo-nx rewrote;
  - ADDED: this port's draw-path changes for banjo-nx's fast path (render/draw.cpp FastDrawLocked, which most draws take
    on deko3d and which re-does DrawStateLocked's steps itself): the baked fetches' declaration and stream salt, the
    depth remap and g_RtScale words, the EDRAM depth restore's write sequence and check, and the exponent adjust's
    per-bind copy kept out of banjo-nx's texture memo.
"""


def _strip_last_lines(text, n):
    lines = text.split('\n')
    assert lines[-1] == '', 'an entry ends in a newline'
    return '\n'.join(lines[:-1 - n]) + '\n'


def _dedent(text, by):
    out = []
    for line in text.split('\n'):
        assert not line or line.startswith(' ' * by), line
        out.append(line[by:])
    return '\n'.join(out)


def apply(EDITS):
    orig = {i: e for i, e in enumerate(EDITS)}

    def first(i):
        return orig[i][1].strip().split('\n')[0]

    # BindingWords (banjo-nx 2026-10-26 moved the slot's words there; the memo and the texture objects keep its answer):
    # this port's signs (#132), 3D/cube scale (#130) and 2D exponent adjust (#88) as they were chained, dedented to
    # the function's level.
    signs = _strip_last_lines(orig[132][2], 1)
    nd_scale = _strip_last_lines(orig[130][2], 2)
    exp_adjust = _strip_last_lines(orig[88][2], 2)
    words = _dedent(signs + nd_scale + exp_adjust, 2)
    volatile_old = ('      index = scaled | binding.scale.code << kResolutionScaleShift;\n')
    assert words.count(volatile_old) == 1
    words = words.replace(volatile_old,
                          '    {\n'
                          '      index = scaled | binding.scale.code << kResolutionScaleShift;\n'
                          '      g_sasrt_words_volatile = true;  // sasrt-nx (2026-10-29): a per-bind copy (FillTextures)\n'
                          '    }\n')
    words = words.replace('    if (scaled != kInvalidDescriptor)\n    {\n', '    if (scaled != kInvalidDescriptor) {\n')

    reanchored = {
        16: ('} // namespace',
             'ShaderRecord *FindShaderLocked(u32 shader_va, RecordKind kind) {\n',
             orig[16][2].split('namespace renut::gpu {\n\n', 1)[1].rsplit('ShaderRecord *FindShaderLocked(', 1)[0] +
             'ShaderRecord *FindShaderLocked(u32 shader_va, RecordKind kind) {\n'),
        # banjo-nx's Op keeps a draw's first two lines; the surfaces go after its Run and sort fields (not read by a
        # draw's own lines).
        25: ('// Run', '  // Run\n  u32 command_buffer = 0;\n', orig[25][2][:-len('};\n')]),
        26: ('op.state = CopyState(buffer, bytes, op.plain_dirty, op.vs_dirty, op.ps_dirty);',
             '    op.resources = FinishResources(buffer, plan);\n  *out_buffer = &buffer;\n',
             '    op.resources = FinishResources(buffer, plan);\n' + orig[26][2].split('\n', 1)[1]),
        27: ('for (const Op &op : buffer.ops) {',
             '    ApplyState(state, buffer.arena.data() + op.state, op.plain_dirty, op.vs_dirty, op.ps_dirty, groups);\n',
             '    ApplyState(state, buffer.arena.data() + op.state, op.plain_dirty, op.vs_dirty, op.ps_dirty, groups);\n'
             '    SetReplaySurfaceOverridesLocked(op.surface_va, op.surface_desc, op.surfaces);  // sasrt-nx\n'),
        # ClearTargets (banjo-nx 2026-10-28: banjo_renut_clear_repeat): the depth views of the same EDRAM after the
        # target's own clear, sent or repeated.
        50: ('cmd->clearDepthStencil((flags & 0x10) != 0, (flags & 0x20) != 0, depth, stencil & 0xFF,',
             '    if (repeat)\n      ++g_clear_repeats;\n    else\n'
             '      cmd->clearDepthStencil(zc, sc, depth, stencil & 0xFF, &host_rect, 1);\n',
             '    if (repeat)\n      ++g_clear_repeats;\n    else\n'
             '      cmd->clearDepthStencil(zc, sc, depth, stencil & 0xFF, &host_rect, 1);\n' +
             orig[50][2].split('&host_rect, 1);\n', 1)[1].rsplit('  }\n', 1)[0]),
        # banjo-nx's OpCall (64 bytes, full) has no room for DrawCall::up_index_offset: the indices are an arena offset
        # like the vertices', so CallOf gives the draw its pointer.
        61: ('if (op.up_indices != kNone)',
             '  op->call.up_vertices = u32(Reserve(*buffer, bytes));  // (Begin*Vertices draws have no indices)\n',
             '  op->call.up_vertices = u32(Reserve(*buffer, bytes));  // (Begin*Vertices draws have no indices)\n'
             '  // sasrt-nx (2026-10-20, D3DDevice_BeginIndexedVertices; 2026-10-29 for banjo-nx\'s OpCall): the indices\n'
             '  // follow the vertices in the one deferred copy, from DrawCall::up_index_offset.\n'
             '  if (call.up_index_offset)\n'
             '    op->call.up_indices = op->call.up_vertices + call.up_index_offset;\n'),
        # banjo-nx's persistent shared constants push only the lines marked changed (SetShared).
        65: ('std::memcpy(sc.pixel_origin, viewport.pixel_origin, sizeof(sc.pixel_origin));  // Renut upstream 574b488',
             '  SetShared(sc, sc.pixel_origin, viewport.pixel_origin);  // Renut upstream 574b488\n',
             '  SetShared(sc, sc.pixel_origin, viewport.pixel_origin);  // Renut upstream 574b488\n'
             '  SetShared(sc, sc.depth_remap, viewport.depth_remap);  // sasrt-nx\n'),
        68: ('RGPU_WARN("Draw binds a depth target smaller than its colour target: colour {:08X} {}x{}, depth {:08X} {}x{}",',
             '  t.guest_width = d3d::SurfaceWidth(first->size_word);\n'
             '  t.guest_height = d3d::SurfaceHeight(first->size_word);\n'
             '  return true;\n}\n',
             '  t.guest_width = d3d::SurfaceWidth(first->size_word);\n'
             '  t.guest_height = d3d::SurfaceHeight(first->size_word);\n'
             '  // sasrt-nx (2026-10-20): the draw area is what every bound target covers (a pixel past a smaller depth\n'
             '  // target\'s edge is undefined on D3D12 and a "ZT width violation" GPU exception on Maxwell).\n'
             '  for (uint32_t i = 1; i < t.color_count; ++i) {\n'
             '    t.width = std::min(t.width, t.colors[i]->width);\n'
             '    t.height = std::min(t.height, t.colors[i]->height);\n'
             '  }\n'
             '  if (t.depth && t.color_count) {\n'
             '    t.width = std::min(t.width, t.depth->width);\n'
             '    t.height = std::min(t.height, t.depth->height);\n'
             '  }\n'
             '  return true;\n}\n'),
        # (#124, the fixed16 clear, merged here: the same lines.)
        76: ('++t.colors[i]->writes;  // banjo-nx (banjo_renut_resolve_skip)',
             '    ++c->writes;  // banjo-nx (banjo_renut_resolve_skip)\n'
             '    g_clears_whole += is_whole;\n'
             '    if (repeat)\n'
             '      ++g_clear_repeats;\n'
             '    else\n'
             '      cmd->clearColor(i, clear_color, &host_rect, 1);\n',
             '    ++c->writes;  // banjo-nx (banjo_renut_resolve_skip)\n'
             '    c->write_seq = ++g_surface_write_seq;  // sasrt-nx: the EDRAM depth restore\n'
             '    g_clears_whole += is_whole;\n'
             '    if (repeat)\n'
             '      ++g_clear_repeats;\n'
             '    else if (c->sasrt_fixed16 && REXCVAR_GET(sasrt_renut_fixed16_scale))  // sasrt-nx: held normalized\n'
             '      cmd->clearColor(i, plume::RenderColor(color[0] / 32.0f, color[1] / 32.0f, color[2] / 32.0f, color[3] / 32.0f),\n'
             '                      &host_rect, 1);\n'
             '    else\n'
             '      cmd->clearColor(i, clear_color, &host_rect, 1);\n'),
        77: ('++t.depth->writes;  // banjo-nx (banjo_renut_resolve_skip)',
             '    ++d->writes;  // banjo-nx (banjo_renut_resolve_skip)\n',
             '    ++d->writes;  // banjo-nx (banjo_renut_resolve_skip)\n'
             '    d->write_seq = ++g_surface_write_seq;  // sasrt-nx: the EDRAM depth restore\n'),
        # (#130, #132 and #133 merged here.)
        88: ('sc.texture_indices[dim][r] = index;',
             '      index |= kStackedLayerWrapBit;\n'
             '  }\n'
             '  sampler = SamplerWord(SamplerSlotLocked(fetch, binding.lod_scale));\n'
             '}\n',
             '      index |= kStackedLayerWrapBit;\n'
             '  }\n'
             '  g_sasrt_words_volatile = false;\n' +
             words +
             '  sampler = SamplerWord(SamplerSlotLocked(fetch, binding.lod_scale));\n'
             '  if (IsDeko3D())  // sasrt-nx: the signs\' flags (above), below the sampler id\'s bit 20\n'
             '    sampler |= sasrt_sign_flags;\n'
             '}\n'),
        102: ('std::memcpy(sc.depth_remap, viewport.depth_remap, sizeof(sc.depth_remap));  // sasrt-nx',
              '  SetShared(sc, sc.depth_remap, viewport.depth_remap);  // sasrt-nx\n',
              '  SetShared(sc, sc.depth_remap, viewport.depth_remap);  // sasrt-nx\n' + orig[102][2].split('\n', 1)[1]),
        123: ('std::memcpy(sc.depth_remap, viewport.depth_remap, sizeof(sc.depth_remap));  // sasrt-nx',
              '  SetShared(sc, sc.depth_remap, viewport.depth_remap);  // sasrt-nx\n',
              '  SetShared(sc, sc.depth_remap, viewport.depth_remap);  // sasrt-nx\n'
              '  SasrtSetRtScale(sc, targets);  // sasrt-nx (2026-10-20): g_RtScale (sasrt_renut_fixed16_scale)\n'),
        125: ('++alias->writes;  // banjo-nx (banjo_renut_resolve_skip)',
              '    ++alias->writes;  // banjo-nx (banjo_renut_resolve_skip)\n'
              '    alias->clear_known = false;  // banjo-nx (banjo_renut_clear_repeat): not followed through aliases\n'
              '    cmd->clearColor(0, clear_color, &alias_host, 1);\n',
              '    ++alias->writes;  // banjo-nx (banjo_renut_resolve_skip)\n'
              '    alias->clear_known = false;  // banjo-nx (banjo_renut_clear_repeat): not followed through aliases\n'
              '    if (alias->sasrt_fixed16 && REXCVAR_GET(sasrt_renut_fixed16_scale))  // sasrt-nx: held normalized\n'
              '      cmd->clearColor(0, plume::RenderColor(color[0] / 32.0f, color[1] / 32.0f, color[2] / 32.0f, color[3] / 32.0f),\n'
              '                      &alias_host, 1);\n'
              '    else\n'
              '      cmd->clearColor(0, clear_color, &alias_host, 1);\n'),
        182: ('SetReplaySurfaceOverridesLocked(nullptr, nullptr, 0);  // sasrt-nx',
              '  SetReplaySurfaceOverridesLocked(nullptr, nullptr, 0);  // sasrt-nx\n',
              '  SetReplaySurfaceOverridesLocked(nullptr, nullptr, 0);  // sasrt-nx\n'
              '  SetReplayIndexBufferLocked(0, nullptr);  // sasrt-nx (2026-10-21)\n'),
        193: ('// PRING CDevice::KickOff() [0x82210AB0]: hand the ring to the GPU. Nothing',
              '// PRING CDevice::KickOff() [0x821DFFF0]: hand the ring to the GPU. Nothing',
              orig[193][2].replace('[0x82210AB0]', '[0x821DFFF0]')),
        223: ('DrawStateLocked(state, call, &constants);',
              '      DrawStateLocked(state, call, &constants);\n      g_draw_slot_extents = nullptr;\n',
              '      if (op.sasrt_streams.count)  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams)\n'
              '        SasrtCheckStreams(op.sasrt_streams, true);\n'
              '      DrawStateLocked(state, call, &constants);\n      g_draw_slot_extents = nullptr;\n'),
        228: ('if (op.sasrt_streams.count)  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams)',
              '      if (op.sasrt_streams.count)  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams)\n'
              '        SasrtCheckStreams(op.sasrt_streams, true);\n'
              '      DrawStateLocked(state, call, &constants);\n      g_draw_slot_extents = nullptr;\n',
              orig[228][2][:-len('      break;\n')] + '      g_draw_slot_extents = nullptr;\n'),
        238: ('g_stream_fills.clear();',
              '  g_stream_fills.clear();\n  g_fill_elements.clear();\n'
              '  ++g_queued_generation;  // banjo-nx (2026-10-19): the table emptied\n',
              '  g_stream_fills.clear();\n  g_fill_elements.clear();\n'
              '  SasrtClearKickHashes();  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams)\n'
              '  ++g_queued_generation;  // banjo-nx (2026-10-19): the table emptied\n'),
        # banjo-nx laid out ShaderRecord's lines (2026-10-28): this port's fields at its end.
        287: ('bool fetch_declaration_built = false;',
              '  std::mutex host_mutex;  // building host\n',
              orig[287][2].split('\n', 1)[1] + '  std::mutex host_mutex;  // building host\n'),
        292: ('return false;',
              '  // banjo-nx (2026-10-23, render-thread round): what this draw reads in guest memory and in the memos keyed by its\n',
              '  if (static const bool sasrt_baked = REXCVAR_GET(sasrt_renut_baked_fetches); sasrt_baked && vs->entry)\n'
              '    declaration = SasrtBakedDeclarationLocked(*vs, declaration);  // sasrt-nx (2026-10-21)\n'
              '  // banjo-nx (2026-10-23, render-thread round): what this draw reads in guest memory and in the memos keyed by its\n'),
        # Both draw paths' BindStreams calls (one entry: the same text twice).
        293: ('declaration->layout_hash, geometry, gpu_streams)) {',
              '!BindStreams(device, call, *vs, shader_strides, declaration->layout, declaration->layout_hash, geometry,\n',
              '!BindStreams(device, call, *vs, shader_strides, declaration->layout,\n'
              '                           declaration->layout_hash ^ declaration->sasrt_stream_salt, geometry,\n'),
    }
    dropped = {
        124, 130, 132, 133,  # merged into 76 and 88 above
        145, 146,  # sa2-nx's chain reuse / inline compare keys: banjo-nx's (banjo_renut_*, its console defaults)
        208,  # 8_8_8_8 / 2_10_10_10 expand tables: banjo-nx's PackedComponentTables (vertex_format.cpp)
        209, 210, 211, 212, 213,  # sasrt_renut_stream_cache_follow: banjo_renut_stream_cache_pressure, no hash at the cap
        232, 237, 247,  # sasrt_renut_diag_late_streams at the conversion: banjo-nx rewrote the fill loop
        270, 272, 273, 282, 284,  # sasrt_renut_diag_layout_log (the octopus hunt, solved 2026-10-21)
    }
    for i, (want_first, old, new) in reanchored.items():
        assert first(i).startswith(want_first), (i, first(i), want_first)
        EDITS[i] = (orig[i][0], old, new)
    added = [
        ('render/draw.cpp',
         'void BindingWords(const TextureBinding &binding, const TextureFetch &fetch, u32 &dim, u32 &index, u32 &sampler) {\n',
         '// sasrt-nx (2026-10-29): the last BindingWords gave words of a per-bind copy (the exponent adjust\'s): FillTextures\n'
         '// keeps them out of the memo, its slots\' last answers and the texture objects.\n'
         'bool g_sasrt_words_volatile = false;\n'
         'uint32_t ExpAdjustedSlotLocked(uint32_t source_slot, int exp_adjust, uint32_t width, uint32_t height);\n'
         'void BindingWords(const TextureBinding &binding, const TextureFetch &fetch, u32 &dim, u32 &index, u32 &sampler) {\n'),
        # SharedConstants: banjo-nx's 1352 words ([0] the fur's skin mode, [1] the internal heights: written at every
        # draw) are this port's g_DepthRemap (#62). Theirs go after g_RtScale, which no shader of this port reads; the
        # block to 1424 bytes, 22 lines and the 16-byte tail PushSharedConstants' line compare takes.
        ('render/draw.cpp',
         '  float rt_scale[4];\n'
         '};\n',
         '  float rt_scale[4];\n'
         '  // 1376, sasrt-nx (2026-10-29, the banjo-nx sync): banjo-nx\'s 1352 words (its skin mode, its internal heights),\n'
         '  // which this port\'s shaders never read; then padding to 22 lines and a 16-byte tail.\n'
         '  float pad_1352[2];\n'
         '  float pad_1384[10];\n'
         '};\n'),
        ('render/draw.cpp',
         'static_assert(sizeof(SharedConstants) == 1376);\n',
         'static_assert(offsetof(SharedConstants, pad_1352) == 1376);\n'
         'static_assert(sizeof(SharedConstants) == 1424);\n'),
        ('render/draw.cpp',
         'static_assert(kSharedLines == 22);\n',
         'static_assert(kSharedLines == 23);  // sasrt-nx (2026-10-29): 1424 bytes, 22 lines and the 16-byte tail\n'),
        ('render/upload_ring.h',
         'constexpr uint32_t kSharedConstantsUboBytes = 1376;',
         'constexpr uint32_t kSharedConstantsUboBytes = 1424;  // sasrt-nx (2026-10-29): + banjo-nx\'s two words, to a 16-byte tail;'),
        # Banjo-nx's chain reuse and fast path keep a draw's targets while the device's target words and the surface
        # epoch hold. This port's GatherTargets reads two things more: the destination packet (each slot's EDRAM view,
        # SetSurfaceViewLocked) and, in a replay, the surfaces' headers as recorded (SetReplaySurfaceOverridesLocked).
        # The PC verify run of 2026-10-29 (banjo_renut_chain_reuse_verify: "the reused targets differ") at the menus'
        # re-pointed 831C385C.
        ('render/surfaces.cpp',
         'void SetReplaySurfaceOverridesLocked(const u32 *surface_va, const d3d::SurfaceDesc *desc, u32 count) {\n'
         '  g_override_count = count < 5 ? count : 5;\n'
         '  for (u32 i = 0; i < g_override_count; ++i) {\n',
         'void SetReplaySurfaceOverridesLocked(const u32 *surface_va, const d3d::SurfaceDesc *desc, u32 count) {\n'
         '  count = count < 5 ? count : 5;\n'
         '  // sasrt-nx (2026-10-29, the banjo-nx sync): other overrides are other targets for the same device words: the\n'
         '  // surface epoch moves, which banjo-nx\'s chain reuse and fast path keep targets by.\n'
         '  bool same = count == g_override_count;\n'
         '  for (u32 i = 0; i < count && same; ++i)\n'
         '    same = g_override_va[i] == surface_va[i] && std::memcmp(&g_override_desc[i], &desc[i], sizeof(desc[i])) == 0;\n'
         '  if (same)\n'
         '    return;\n'
         '  ++g_surface_epoch;\n'
         '  g_override_count = count;\n'
         '  for (u32 i = 0; i < g_override_count; ++i) {\n'),
        ('render/draw.cpp',
         '      (!(chain.fields & kFieldTargets) || target_words_same()) && g_targets_reuse.epoch == SurfaceEpochLocked()) {\n',
         '      (!(chain.fields & kFieldTargets) || target_words_same()) && g_targets_reuse.epoch == SurfaceEpochLocked() &&\n'
         '      !(chain.fields & kFieldDest)) {  // sasrt-nx (2026-10-29): GatherTargets reads the destination packet\'s views\n'),
        ('render/draw.cpp',
         '  const bool targets_changed = (fields & kFieldTargets) || f.surface_epoch != SurfaceEpochLocked() ||\n',
         '  // sasrt-nx (2026-10-29): GatherTargets reads the destination packet too (each slot\'s EDRAM view).\n'
         '  const bool targets_changed = (fields & (kFieldTargets | kFieldDest)) || f.surface_epoch != SurfaceEpochLocked() ||\n'),
        # sasrt_renut_capture_recorded_streams (2026-10-21): an op's Draw*UP data by banjo-nx's OpCall (arena offsets,
        # kNoUp; BeginIndexedVertices' indices among them since #61).
        ('guest/command_buffers.cpp',
         '            if (op.up_indices != kNone || (op.call.up_index_offset && op.up_vertices != kNone)) {  // as Replay\n'
         '              is32 = op.call.up_indices_32;\n'
         '              endian = is32 ? 2 : 1;\n'
         '              src = buffer->arena.data() +\n'
         '                    (op.up_indices != kNone ? op.up_indices : op.up_vertices + op.call.up_index_offset) +\n'
         '                    size_t(op.call.start_index) * (is32 ? 4 : 2);\n',
         '            if (op.call.up_indices != kNoUp) {  // as Replay (CallOf)\n'
         '              is32 = op.call.up_indices_32;\n'
         '              endian = is32 ? 2 : 1;\n'
         '              src = buffer->arena.data() + op.call.up_indices + size_t(op.call.start_index) * (is32 ? 4 : 2);\n'),
        ('guest/command_buffers.cpp',
         '          if (op.sasrt_ranges.stream[i] == 0 && op.up_vertices != kNone)\n',
         '          if (op.sasrt_ranges.stream[i] == 0 && op.call.up_vertices != kNoUp)\n'),
        ('guest/command_buffers.cpp',
         '        if (op.call.indexed && op.up_indices == kNone && op.ib_va) {\n',
         '        if (op.call.indexed && op.call.up_indices == kNoUp && op.ib_va) {\n'),
        # sasrt_renut_diag_vertex_formats (2026-10-21): banjo-nx's ConvertVertices takes the elements, not the stream.
        ('render/vertex_format.cpp',
         'void SasrtCountConversion(const HostVertexStream &stream, u32 guest_stride, u32 count, bool whole) {\n',
         'void SasrtCountConversion(std::span<const HostVertexElement> elements, u32 guest_stride, u32 count, bool whole) {\n'),
        ('render/vertex_format.cpp',
         '    for (const HostVertexElement &e : stream.elements) {\n'
         '      if (e.conversion != ElementConversion::ExpandFloat) {\n',
         '    for (const HostVertexElement &e : elements) {\n'
         '      if (e.conversion != ElementConversion::ExpandFloat) {\n'),
        ('render/vertex_format.cpp',
         '    SasrtCountConversion(stream, guest_stride, vertex_count, copy_only && same_layout);\n',
         '    SasrtCountConversion(stream_elements, guest_stride, vertex_count, copy_only && same_layout);\n'),
        ('render/draw.cpp',
         '    BindingWords(binding, fetch, dim, index, sampler);\n'
         '    SetSlotWords(sc, r, dim, index, sampler);  // banjo-nx (2026-10-26)\n'
         '    if (memo) {\n',
         '    BindingWords(binding, fetch, dim, index, sampler);\n'
         '    SetSlotWords(sc, r, dim, index, sampler);  // banjo-nx (2026-10-26)\n'
         '    // sasrt-nx (2026-10-29): words of a per-bind copy (ExpAdjustedSlotLocked) are not kept: the copy is made again\n'
         '    // at the next bind, as before banjo-nx\'s memo answers.\n'
         '    const bool sasrt_volatile = g_sasrt_words_volatile;\n'
         '    if (sasrt_volatile && all_memo)\n'
         '      *all_memo = false;\n'
         '    if (memo && !sasrt_volatile) {\n'),
        # FastDrawLocked: the declaration as DrawStateLocked takes it.
        ('render/draw.cpp',
         '      declaration = &NoDeclaration();\n'
         '    }\n'
         '    if (!declaration)\n'
         '      return FastMiss(kFastDecl);\n'
         '  }\n',
         '      declaration = &NoDeclaration();\n'
         '    }\n'
         '    if (!declaration)\n'
         '      return FastMiss(kFastDecl);\n'
         '    // sasrt-nx (2026-10-29): sasrt_renut_baked_fetches, as DrawStateLocked\n'
         '    if (static const bool sasrt_baked = REXCVAR_GET(sasrt_renut_baked_fetches); sasrt_baked && vs->entry)\n'
         '      declaration = SasrtBakedDeclarationLocked(*vs, declaration);\n'
         '  }\n'),
        # The streams' keys with the baked declaration's salt (its converted data differs; the input layout is the same):
        # both paths' whole copies and DrawStateLocked's stream keys, as BindStreams (#293).
        ('render/draw.cpp',
         '                                         declaration->layout_hash, geometry, whole_copies);\n',
         '                                         declaration->layout_hash ^ declaration->sasrt_stream_salt, geometry,\n'
         '                                         whole_copies);\n'),
        ('render/draw.cpp',
         '            : DrawStreamKeys(device, call, *vs, shader_strides, declaration->layout, declaration->layout_hash, geometry,\n',
         '            : DrawStreamKeys(device, call, *vs, shader_strides, declaration->layout,\n'
         '                             declaration->layout_hash ^ declaration->sasrt_stream_salt, geometry,\n'),
        # g_RtScale for both paths (#123).
        ('render/draw.cpp',
         'int FastDrawLocked(const u8 *device_state, const DrawCall &call, const ReplayConstants *replay) {\n',
         '// sasrt-nx (2026-10-20, sasrt_renut_fixed16_scale; 2026-10-29 one helper for both draw paths): g_RtScale, 1/32 for\n'
         '// a target held normalized (HostSurface::sasrt_fixed16), else 1.\n'
         'void SasrtSetRtScale(SharedConstants &sc, const Targets &targets) {\n'
         '  const bool scale = REXCVAR_GET(sasrt_renut_fixed16_scale);\n'
         '  float rt[4];\n'
         '  for (uint32_t i = 0; i < 4; ++i)\n'
         '    rt[i] = scale && i < targets.color_count && targets.colors[i] && targets.colors[i]->sasrt_fixed16 ? 1.0f / 32.0f\n'
         '                                                                                                 : 1.0f;\n'
         '  SetShared(sc, sc.rt_scale, rt);\n'
         '}\n'
         '}  // namespace\n'
         '// sasrt-nx (2026-10-21, sasrt_renut_baked_fetches): further down (renut::gpu, outside this namespace).\n'
         'const VertexDeclarationRecord *SasrtBakedDeclarationLocked(ShaderRecord &vs,\n'
         '                                                           const VertexDeclarationRecord *declaration);\n'
         'namespace {\n'
         '\n'
         'int FastDrawLocked(const u8 *device_state, const DrawCall &call, const ReplayConstants *replay) {\n'),
        # FastDrawLocked: the depth remap and g_RtScale words, as DrawStateLocked (#65, #123).
        ('render/draw.cpp',
         '    SetShared(sc, sc.pixel_origin, viewport.pixel_origin);\n'
         '    if (targets_changed) {  // with the targets (DrawStateLocked sets them at every draw)\n',
         '    SetShared(sc, sc.pixel_origin, viewport.pixel_origin);\n'
         '    SetShared(sc, sc.depth_remap, viewport.depth_remap);  // sasrt-nx (2026-10-29): as DrawStateLocked\n'
         '    if (targets_changed) {  // with the targets (DrawStateLocked sets them at every draw)\n'
         '      SasrtSetRtScale(sc, targets);  // sasrt-nx (2026-10-29): g_RtScale, as DrawStateLocked\n'),
        # FastDrawLocked: the depth target's write sequence, as DrawStateLocked (#75).
        ('render/draw.cpp',
         '    if (((dc & 2) && (dc & 4)) || ((dc & 1) && ((f.kp_hot.stencil_ref_mask >> 16) & 0xFF) != 0))\n'
         '      ++targets.depth->writes;\n',
         '    if (((dc & 2) && (dc & 4)) || ((dc & 1) && ((f.kp_hot.stencil_ref_mask >> 16) & 0xFF) != 0)) {\n'
         '      ++targets.depth->writes;\n'
         '      targets.depth->write_seq = ++g_surface_write_seq;  // sasrt-nx: the EDRAM depth restore\n'
         '    }\n'),
        # The EDRAM depth restore (GatherTargets, #80) for the fast path's kept targets: checked again only when another
        # writer moved the surfaces' write sequence since the last draw (its check walks every surface twice).
        ('render/draw.cpp',
         '  bool fetch_kept_pool = false;\n'
         '};\n',
         '  bool fetch_kept_pool = false;\n'
         '  // sasrt-nx (2026-10-29): g_surface_write_seq after the last draw (the EDRAM depth restore, FastDrawLocked).\n'
         '  uint64_t sasrt_write_seq = 0;\n'
         '};\n'),
        ('render/draw.cpp',
         '  const Targets &targets = targets_changed ? gathered : f.targets;\n',
         '  const Targets &targets = targets_changed ? gathered : f.targets;\n'
         '  // sasrt-nx (2026-10-29): the EDRAM depth restore (GatherTargets does it for gathered targets) for kept ones too,\n'
         '  // when another writer (a clear, a resolve, a draw of DrawStateLocked) moved the write sequence since.\n'
         '  if (!targets_changed && targets.depth && g_surface_write_seq != f.sasrt_write_seq &&\n'
         '      REXCVAR_GET(sasrt_renut_depth_restore)) {\n'
         '    if (HostSurface *color = DepthRestoreSourceLocked(targets.depth))\n'
         '      RestoreDepthFromColorLocked(targets.depth, color);\n'
         '  }\n'),
        ('render/draw.cpp',
         '  ++g_fast_draws;\n',
         '  f.sasrt_write_seq = g_surface_write_seq;  // sasrt-nx (2026-10-29): the EDRAM depth restore\n'
         '  ++g_fast_draws;\n'),
        ('render/draw.cpp',
         '  f.targets = targets;\n'
         '  f.surface_epoch = SurfaceEpochLocked();\n'
         '  f.viewport = viewport;\n',
         '  f.targets = targets;\n'
         '  f.surface_epoch = SurfaceEpochLocked();\n'
         '  f.viewport = viewport;\n'
         '  f.sasrt_write_seq = g_surface_write_seq;  // sasrt-nx (2026-10-29): the EDRAM depth restore (FastDrawLocked)\n'),
    ]
    kept = [e for i, e in enumerate(EDITS) if i not in dropped]
    return kept + added
