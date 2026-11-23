ROOT = r'D:/sonic transformed/sasrt-nx/app/src/renut_engine/gpu/'


def edit(path, old, new, count=1):
    p = ROOT + path
    s = open(p, encoding='utf-8').read()
    assert s.count(old) == count, (path, s.count(old), old[:80])
    s = s.replace(old, new)
    open(p, 'w', encoding='utf-8').write(s)


# 1. the helper: every stream with a pending export window is one the host layout reads, found on the GPU (as
# DrawNeedsExportFlush's stream part decides "no wait"); placed after FastExportReads (FindExportedStream is above it)
edit('render/draw.cpp', '''bool FastExportReads(const GuestDevice &device, const DrawCall &call, const ShaderRecord &vs,
                     const VertexDeclarationRecord &declaration, const TextureFetch *fetches, u32 texture_mask,
                     bool streams, bool fetch, bool index, bool textures) {''', '''// sasrt-nx (2026-11-20, sasrt_rt4_export_reads_fast; the third table's #34, the first's #16): whether every vertex stream
// of the draw that meets a pending memexport window is one the host layout reads and whose window FindExportedStream
// finds on the GPU (DrawNeedsExportFlush's stream part: then no wait, ConvertExportedStreamsLocked converts it). A stream
// read only by vfetchBound (no host input) is not: the fast path's fetch data does not take export windows.
bool SasrtExportStreamsOnGpu(const GuestDevice &device, const DrawCall &call, const ShaderRecord &vs,
                             const u32 *shader_strides, const VertexDeclarationRecord &declaration) {
  for (u32 k = 0; k < declaration.stream_count; ++k) {
    const u32 stream = declaration.stream_order[k];
    if (stream == 0 && call.up_vertices)
      continue;
    const u32 fetch_index = d3d::kFirstVertexFetchIndex + d3d::StreamFetchIndex(stream);
    if (!PendingExportSlotsMemo(kExportAnswerFetch + ((fetch_index - 64) & 31),
                                device.VertexFetchWord(fetch_index, 0) & ~3u,
                                device.VertexFetchWord(fetch_index, 1) & 0x3FFFFFCu))
      continue;
    ExportedStream exported;
    if (!declaration.layout.streams[stream].used ||
        !FindExportedStream(device, call, vs, shader_strides, declaration, stream, exported))
      return false;
  }
  return true;
}

bool FastExportReads(const GuestDevice &device, const DrawCall &call, const ShaderRecord &vs,
                     const VertexDeclarationRecord &declaration, const TextureFetch *fetches, u32 texture_mask,
                     bool streams, bool fetch, bool index, bool textures) {''')

# 2. the check: other kinds of read as before; a stream read of windows on the GPU stays on the fast path
edit('render/draw.cpp', '''  if ((check_streams || check_fetch || check_index || check_textures) &&
      FastExportReads(device, call, *vs, *declaration, fetches, texture_mask, check_streams, check_fetch, check_index,
                      check_textures))
    return FastMiss(kFastExportRead);''', '''  // sasrt-nx (2026-11-20, sasrt_rt4_export_reads_fast; the third table's #34): with the key, the stream reads asked
  // apart: a draw whose only export reads are vertex streams the host layout reads from windows found on the GPU (the
  // 4P race's "export read" draws, 93 a frame to the full path) has them converted here as DrawStateLocked does
  // (ConvertExportedStreamsLocked before the streams are bound); not for whole-buffer geometry (WholeGeometryLocked
  // took copies: the full path does not convert those either). Fetch, index and texture reads go the full way as before.
  bool export_streams = false;
  if (check_streams || check_fetch || check_index || check_textures) {
    if (!sasrt::gpu_round::On(sasrt::gpu_round::kRt4ExportReadsFast)) {
      if (FastExportReads(device, call, *vs, *declaration, fetches, texture_mask, check_streams, check_fetch,
                          check_index, check_textures))
        return FastMiss(kFastExportRead);
    } else {
      if ((check_fetch || check_index || check_textures) &&
          FastExportReads(device, call, *vs, *declaration, fetches, texture_mask, false, check_fetch, check_index,
                          check_textures))
        return FastMiss(kFastExportRead);
      if (check_streams &&
          FastExportReads(device, call, *vs, *declaration, fetches, texture_mask, true, false, false, false)) {
        if (whole || !SasrtExportStreamsOnGpu(device, call, *vs, shader_strides, *declaration))
          return FastMiss(kFastExportRead);
        export_streams = true;
      }
    }
  }''')

# 3. the conversion, after the pushed-buffer check (the draw is the fast path's from there): its streams for BindStreams
edit('render/draw.cpp', '''#if defined(PLUME_DEKO3D)
  if (!banjo::renut_gpu::PushConstantsOn() || !EnsurePushedBuffers())
    return FastMiss(kFastPushed);
#else
  return FastMiss(kFastPushed);
#endif''', '''#if defined(PLUME_DEKO3D)
  if (!banjo::renut_gpu::PushConstantsOn() || !EnsurePushedBuffers())
    return FastMiss(kFastPushed);
#else
  return FastMiss(kFastPushed);
#endif
  // sasrt-nx (2026-11-20, sasrt_rt4_export_reads_fast): the export windows' streams converted (their compute work and
  // barriers recorded now; the bound pipeline and framebuffer are forgotten by it, so the binds below are made again).
  GpuStreams export_gpu_streams;
  if (export_streams) {
    if (!ConvertExportedStreamsLocked(s, device, call, *vs, shader_strides, *declaration, geometry, export_gpu_streams))
      return FastMiss(kFastExportRead);
    sasrt::gpu_round::Count(sasrt::gpu_round::kRt4ExportReadsFast);
  }''')

# 4. the bind with them
edit('render/draw.cpp', '''  if (whole ? !BindWholeStreams(declaration->layout, whole_copies, base_draw ? 0u : geometry.whole_base)
            : !BindStreams(device, call, *vs, shader_strides, declaration->layout,
                           declaration->layout_hash ^ declaration->sasrt_stream_salt, geometry,
                           GpuStreams{}, nullptr))
    return -1;''', '''  if (whole ? !BindWholeStreams(declaration->layout, whole_copies, base_draw ? 0u : geometry.whole_base)
            : !BindStreams(device, call, *vs, shader_strides, declaration->layout,
                           declaration->layout_hash ^ declaration->sasrt_stream_salt, geometry,
                           export_gpu_streams, nullptr))  // sasrt-nx (2026-11-20): empty but for #34's
    return -1;''')

# 5. its stream answer not kept (the next draw checks its streams again)
edit('render/draw.cpp', '''    f.export_streams_ok = !call.up_vertices;  // stream 0 was not checked for a Draw*UP draw''',
     '''    f.export_streams_ok = !call.up_vertices && !export_streams;  // stream 0 was not checked for a Draw*UP draw''')
print('ok')
