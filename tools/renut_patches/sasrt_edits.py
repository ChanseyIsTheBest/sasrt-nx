"""This port's edits to banjo-nx's Renut tree, applied by tools/renut_gpu_retarget.py after the address rewrite.

Each entry is (file under app/src/renut_engine/gpu, the text in banjo-nx's tree, this port's text). An entry whose
text is no longer in banjo-nx's tree is reported (banjo-nx changed it; look at it again). Guest globals: this game's
addresses of the Direct3D data N&B's were (found through the mapped function pairs: tools/renut_gpu_retarget.py's
docstring, docs/deko3d-renderer.md).
"""

EDITS = [
    # The boot key: sasrt_renderer (the user's rule: this port's keys are its own).
    ('banjo_renut_select.cpp',
     'REXCVAR_DEFINE_STRING(banjo_renderer, "native", "Banjo",',
     'REXCVAR_DEFINE_STRING(sasrt_renderer, "native", "SASRT",'),
    ('banjo_renut_select.cpp',
     '"Renderer, chosen at boot. native = banjo-nx\'s own native renderer (the default; the exact "\n'
     '                      "reference, with every banjo_* GPU and ring key). renut = Renut\'s Direct3D-level renderer "\n'
     '                      "(github.com/masterspike52/reNut): N&B\'s Direct3D runs natively through plume, with no PM4 and no "\n'
     '                      "EDRAM tile model; its own renut_* keys apply")',
     '"Renderer, chosen at boot. native = this port\'s PM4 ring renderer (the default; the reference, "\n'
     '                      "with every masseffect_* / sasrt_gpu_* key). renut = Renut\'s Direct3D-level renderer "\n'
     '                      "(github.com/masterspike52/reNut, via banjo-nx): the game\'s Direct3D runs natively through plume "\n'
     '                      "(Vulkan on the PC, deko3d on the Switch), with no PM4 ring and no EDRAM emulation; its own "\n'
     '                      "renut_* keys apply")'),
    ('banjo_renut_select.cpp',
     'REXCVAR_GET(banjo_renderer) == "renut"',
     'REXCVAR_GET(sasrt_renderer) == "renut"'),

    # Direct3D's state tables ({getter, setter, default} per state; D3D_InitializeApiState sub_82CF75F0 loads them).
    ('d3d/d3d_native_state.cpp',
     'constexpr u32 kRenderStateTable = 0x82E506F0;',
     'constexpr u32 kRenderStateTable = 0x831702C0;  // sasrt-nx (N&B 0x82E506F0)'),
    ('d3d/d3d_native_state.cpp',
     'constexpr u32 kSamplerStateTable = 0x82E50BD0;',
     'constexpr u32 kSamplerStateTable = 0x83170780;  // sasrt-nx (N&B 0x82E50BD0)'),
    # The GPU format table (D3D_FindTextureSize, D3D_GetLevelLayout, D3D_Lock*Surface and 6 more read it).
    ('d3d/d3d_native_state.cpp',
     'constexpr u32 kFormatTable = 0x820052F8;',
     'constexpr u32 kFormatTable = 0x822F7088;  // sasrt-nx (N&B 0x820052F8)'),
    ('d3d/hooks/resource.cpp',
     'constexpr u32 kFormatTable = 0x820052F8;',
     'constexpr u32 kFormatTable = 0x822F7088;  // sasrt-nx (N&B 0x820052F8)'),
    # The export workaround switches: N&B's globals (dword_82FAD204/208); none found in this game: 0, the hardware
    # workarounds apply (as with N&B's defaults).
    ('d3d/d3d_native_state.cpp',
     '  if (GuestWord(kSkipExportNanVertex))',
     '  if (false)  // sasrt-nx: N&B\'s switch (kSkipExportNanVertex); this game has none'),
    ('d3d/d3d_native_state.cpp',
     '  if (GuestWord(kSkipExport512Pixels))',
     '  if (false)  // sasrt-nx: N&B\'s switch (kSkipExport512Pixels); this game has none'),
    # The kernel's VdGlobalDevice import slot (this game: 0x83370CA8, 0x83370CAC for a type-2 device).
    ('d3d/hooks/device.cpp',
     'constexpr u32 kVdGlobalDeviceImportSlot = 0x820007FC;',
     'constexpr u32 kVdGlobalDeviceImportSlot = 0x83370CA8;  // sasrt-nx (N&B 0x820007FC)'),
    # The device's global qword (21119: copied by the type-2 init sub_82CF7E08 to +11008; layout: sasrt_renut_layout.h).
    ('d3d/hooks/device.cpp',
     'constexpr u32 kGlobalQwordVa = 0x82F39B38;',
     'constexpr u32 kGlobalQwordVa = 0x831709B8;  // sasrt-nx (N&B 0x82F39B38)'),
    # D3DDevice_GetDeviceCaps' constant D3DCAPS9 (sub_82CF1420).
    ('d3d/hooks/device.cpp',
     'constexpr u32 kDeviceCapsVa = 0x82183B00;  // N&B\'s constant D3DCAPS9',
     'constexpr u32 kDeviceCapsVa = 0x822F7E18;  // sasrt-nx: this game\'s constant D3DCAPS9 (N&B 0x82183B00)'),
    # D3DVIEWPORT9 {0, 0, 0xFFFF, 0xFFFF, 0.0, 1.0} (D3D_SetSurfaceInfo sub_82CCF418, EndTiling).
    ('d3d/hooks/draw.cpp',
     'constexpr u32 kFullViewport = 0x820018DC;',
     'constexpr u32 kFullViewport = 0x822F6C50;  // sasrt-nx (N&B 0x820018DC)'),
    # The word set while a depth surface owns the HiZ memory (CreateSurface, Destroy, the surface header).
    ('d3d/hooks/resource.cpp',
     'constexpr u32 kHiZOwnerVa = 0x82FA36C8;',
     'constexpr u32 kHiZOwnerVa = 0x831FE570;  // sasrt-nx (N&B 0x82FA36C8)'),
    # N&B's XPhysicalAlloc switch (a game global): none in this game.
    ('d3d/hooks/resource.cpp',
     '  if (const auto *no_large_pages = GuestPtr<const be_u32>(kGameNoLargePagesVa); u32(*no_large_pages))',
     '  if (false)  // sasrt-nx: N&B\'s game switch (kGameNoLargePagesVa); this game has none'),
]

# A shader object the game never registered (XGRegister*Shader): this game keeps static shader objects in its image's
# data (0x83xxxxxx, sasrt_me_hooks.cpp's DumpBoundShader notes). It is registered at its first draw, on the render
# thread under State().mutex as the queued registration would be, from the same container (the object's virtual part
# and the physical part it points at).
EDITS += [
    ('d3d/hooks/shader.cpp',
     '    if (!record) {\n'
     '      auto it = g_guest_shaders.find(shader_va);\n'
     '      record = it != g_guest_shaders.end() && it->second->kind == kind ? it->second.get() : nullptr;\n'
     '    }\n'
     '    found = {shader_va, record};',
     '    if (!record) {\n'
     '      auto it = g_guest_shaders.find(shader_va);\n'
     '      record = it != g_guest_shaders.end() && it->second->kind == kind ? it->second.get() : nullptr;\n'
     '    }\n'
     '    if (!record)\n'
     '      record = SasrtLazyGuestShaderLocked(shader_va, kind);  // sasrt-nx\n'
     '    found = {shader_va, record};'),
    ('d3d/hooks/shader.cpp',
     '} // namespace\n\nnamespace renut::gpu {\n\nShaderRecord *FindShaderLocked(',
     '} // namespace\n\nnamespace renut::gpu {\n\n'
     '// sasrt-nx (2026-10-20): a shader object the game never registered (static objects in the image\'s data), from its\n'
     '// own container at its first draw. Render thread, State().mutex (as the queued registration of\n'
     '// RegisterGuestShader runs).\n'
     'static ShaderRecord *SasrtLazyGuestShaderLocked(u32 shader_va, RecordKind kind) {\n'
     '  const bool pixel = kind == RecordKind::PixelShader;\n'
     '  const auto *words = GuestPtr<const be_u32>(shader_va);\n'
     '  if (!words || (u32(words[0]) & 0xFF) != (pixel ? 7u : 6u))\n'
     '    return nullptr;\n'
     '  const u32 container_va = shader_va + (pixel ? kPixelShaderContainer : kVertexShaderContainer);\n'
     '  const u32 physical_va = u32(words[(pixel ? kPixelShaderPhysical : kVertexShaderPhysical) / 4]);\n'
     '  const auto *header = GuestPtr<const d3d::ShaderContainer>(container_va);\n'
     '  const u8 *physical = physical_va < 0x20000000u ? GuestPhysicalPtr<const u8>(physical_va)\n'
     '                                                 : GuestPtr<const u8>(physical_va);\n'
     '  if (!header || !physical || !physical_va)\n'
     '    return nullptr;\n'
     '  const u32 flags = header->flags;\n'
     '  const u32 virtual_size = header->virtualSize;\n'
     '  const u32 physical_size = header->physicalSize;\n'
     '  if ((flags & 0xFFFFFF00u) != 0x102A1100u || ((flags & 1) != 0) == pixel ||\n'
     '      virtual_size < sizeof(d3d::ShaderContainer) || virtual_size > 0x10000 || physical_size == 0 ||\n'
     '      physical_size > 0x100000)\n'
     '    return nullptr;\n'
     '  std::vector<uint8_t> container(size_t(virtual_size) + physical_size);\n'
     '  std::memcpy(container.data(), header, virtual_size);\n'
     '  std::memcpy(container.data() + virtual_size, physical, physical_size);\n'
     '  const uint64_t hash = HashShaderContainer(container.data());\n'
     '  if (!FindShaderEntry(hash))\n'
     '    CaptureMissingShader(container.data(), pixel, hash);\n'
     '  auto &shader = g_guest_shaders[shader_va];\n'
     '  shader = std::make_unique<ShaderRecord>();\n'
     '  shader->kind = kind;\n'
     '  shader->self_va = shader_va;\n'
     '  shader->hash = hash;\n'
     '  shader->entry = FindShaderEntry(hash);\n'
     '  PipelineShaderLoaded(shader->entry);\n'
     '  static std::atomic<uint32_t> logged{0};\n'
     '  if (logged.fetch_add(1, std::memory_order_relaxed) < 16)\n'
     '    RGPU_INFO("{} shader object {:08X} registered at its first draw ({:016X}{})", pixel ? "pixel" : "vertex",\n'
     '              shader_va, hash, shader->entry ? "" : ", not in the shader cache");\n'
     '  return shader.get();\n'
     '}\n\n'
     'ShaderRecord *FindShaderLocked('),
]

EDITS += [('d3d/hooks/shader.cpp', '#include <cstring>\n', '#include <atomic>\n#include <cstring>\n')]

# Vertex declarations the game builds in place (its sub_82CC2E20, without D3DDevice_CreateVertexDeclaration: the first
# PC boot dropped draws with "vertex declaration B5640F00 is not one the renderer knows"): registered from the object
# at its first draw. The object, as sub_82CC2E20 writes it: Common 0x00100005, the element count at +24 (D3DDECL_END
# not counted), the D3DVERTEXELEMENT9s (12 bytes each) from +52.
EDITS += [
    ('d3d/hooks/shader.cpp',
     'const VertexDeclarationRecord *FindGuestDeclarationLocked(u32 declaration_va) {\n'
     '  auto it = g_guest_declarations.find(declaration_va);\n'
     '  return it != g_guest_declarations.end() ? it->second.get() : nullptr;\n'
     '}\n',
     'void BuildDeclarationLayout(VertexDeclarationRecord &declaration);\n\n'
     'const VertexDeclarationRecord *FindGuestDeclarationLocked(u32 declaration_va) {\n'
     '  auto it = g_guest_declarations.find(declaration_va);\n'
     '  if (it != g_guest_declarations.end())\n'
     '    return it->second.get();\n'
     '  // sasrt-nx: a declaration built in place (sub_82CC2E20\'s layout), from the object at its first draw.\n'
     '  const auto *words = declaration_va ? GuestPtr<const be_u32>(declaration_va) : nullptr;\n'
     '  if (!words || u32(words[0]) != 0x00100005u)\n'
     '    return nullptr;\n'
     '  const u32 count = words[6];\n'
     '  if (!count || count > 64)\n'
     '    return nullptr;\n'
     '  const auto *elements = GuestPtr<const GuestVertexElement>(declaration_va + 52);\n'
     '  if (!elements)\n'
     '    return nullptr;\n'
     '  auto declaration = std::make_unique<VertexDeclarationRecord>();\n'
     '  declaration->x360.resource.Common = u32(d3d::ResourceType::VertexDeclaration);\n'
     '  declaration->self_va = declaration_va;\n'
     '  for (u32 i = 0; i < count; ++i)\n'
     '    declaration->elements.push_back(elements[i]);\n'
     '  BuildDeclarationLayout(*declaration);\n'
     '  const VertexDeclarationRecord *result = declaration.get();\n'
     '  g_guest_declarations[declaration_va] = std::move(declaration);\n'
     '  return result;\n'
     '}\n'),
]

# Textures the game sets without D3DDevice_SetTexture: its fetch constant in the device's shadow (+1152), but no
# texture object in the device's slot (+12920). The second PC boot's [texdiag]: every logo, movie and menu texture came
# that way (texture 00000000, valid fetch constants), and Renut bound its null texture (white) for each. The texture
# of the fetch constant itself, then, keyed by its base address (odd: never a texture header's address); a resolve
# into that memory is found by the same base page (ResolvedAlias).
EDITS += [
    ('render/textures.cpp',
     '  if (!texture_va)\n'
     '    return binding;\n'
     '  const auto *header = GuestPtr<const d3d::BaseTexture>(texture_va);\n'
     '  if (!header)\n'
     '    return binding;\n'
     '  TextureFetch fetch = TextureFetch::FromHeader(header->Format);\n',
     '  if (!texture_va) {\n'
     '    // sasrt-nx (2026-10-20): a fetch constant set without SetTexture: its own texture, keyed by its base address.\n'
     '    if (!device_fetch.IsTexture())\n'
     '      return binding;\n'
     '    texture_va = 1u | (u32(device_fetch.BasePage()) << 12);\n'
     '  }\n'
     '  const auto *header = (texture_va & 1u) ? nullptr : GuestPtr<const d3d::BaseTexture>(texture_va);\n'
     '  if (!header && !(texture_va & 1u))\n'
     '    return binding;\n'
     '  TextureFetch fetch = header ? TextureFetch::FromHeader(header->Format) : device_fetch;\n'),
]

# Render targets as the game re-points them (2026-10-20). This game rewrites the headers of its D3DSurfaces in place
# all through a frame: one surface object (831C385C) is a 1152x544 16-bit float target in one pass and a 1280x720
# 8888 one in the next, over the same EDRAM. On the 360 the EDRAM keeps its contents whatever header describes it, and
# the GPU reads the header's values when the packets were written, not when they run. Renut read the header at the
# draw, and when a surface was re-pointed it retired the host image of its old view if no other surface used it. Two
# changes:
#   - a re-pointed surface leaves the image of its old view alive (as the EDRAM bytes are): the view keeps its target;
#   - a recorded command buffer keeps, with each op, the headers of the render targets and depth surface bound then
#     (the recording device's), and its replay binds those (ReplaySurfaceOverride), on the render thread: the worker
#     thread's recorded draws went to whatever view the title device's thread had set at their replay.
EDITS += [
    ('render/surfaces.h',
     '#include "renut_engine/gpu/render/render_scale.h"\n',
     '#include "renut_engine/gpu/d3d/d3d.h"  // sasrt-nx: d3d::SurfaceDesc\n'
     '#include "renut_engine/gpu/render/render_scale.h"\n'),
    ('render/surfaces.h',
     'HostSurface *GetHostSurfaceLocked(u32 surface_va);\n',
     'HostSurface *GetHostSurfaceLocked(u32 surface_va);\n\n'
     '// sasrt-nx (2026-10-20): while a recorded command buffer op replays (guest/command_buffers.cpp), the surfaces it\n'
     '// recorded take their headers as they were then; render thread, State().mutex. 0 surfaces ends it.\n'
     'void SetReplaySurfaceOverridesLocked(const u32 *surface_va, const d3d::SurfaceDesc *desc, u32 count);\n'),
    ('render/surfaces.cpp',
     'HostSurface *GetHostSurfaceSlow(u32 surface_va, const d3d::SurfaceDesc *desc);\n',
     'HostSurface *GetHostSurfaceSlow(u32 surface_va, const d3d::SurfaceDesc *desc);\n\n'
     '// sasrt-nx (2026-10-20): the recorded headers of the op replaying now (SetReplaySurfaceOverridesLocked).\n'
     'u32 g_override_va[5] = {};\n'
     'd3d::SurfaceDesc g_override_desc[5] = {};\n'
     'u32 g_override_count = 0;\n'
     'bool g_override_active = false;\n\n'
     'void SetReplaySurfaceOverridesLocked(const u32 *surface_va, const d3d::SurfaceDesc *desc, u32 count) {\n'
     '  g_override_count = count < 5 ? count : 5;\n'
     '  for (u32 i = 0; i < g_override_count; ++i) {\n'
     '    g_override_va[i] = surface_va[i];\n'
     '    g_override_desc[i] = desc[i];\n'
     '  }\n'
     '}\n\n'
     'const d3d::SurfaceDesc *ReplaySurfaceOverride(u32 surface_va) {\n'
     '  for (u32 i = 0; i < g_override_count; ++i)\n'
     '    if (g_override_va[i] == surface_va)\n'
     '      return &g_override_desc[i];\n'
     '  return nullptr;\n'
     '}\n'),
    ('render/surfaces.cpp',
     '  const auto *desc = GuestPtr<const d3d::SurfaceDesc>(surface_va + sizeof(d3d::Resource));\n'
     '  if (!desc)\n'
     '    return nullptr;\n',
     '  const auto *desc = GuestPtr<const d3d::SurfaceDesc>(surface_va + sizeof(d3d::Resource));\n'
     '  if (!desc)\n'
     '    return nullptr;\n'
     '  // sasrt-nx: a replayed op\'s surface, with its header as it was recorded.\n'
     '  const d3d::SurfaceDesc *recorded = ReplaySurfaceOverride(surface_va);\n'
     '  if (recorded)\n'
     '    desc = recorded;\n'
     '  g_override_active = recorded != nullptr;\n'),
    ('render/surfaces.cpp',
     '  const uint64_t key = TargetKey(*desc, depth, format, scale);\n'
     '  auto [bound, first_use] = g_surface_keys.try_emplace(surface_va, key);\n'
     '  if (first_use) {\n'
     '    ++g_target_users[key];\n'
     '    ++g_surface_epoch;\n'
     '  } else if (bound->second != key) {\n'
     '    ++g_surface_epoch;\n'
     '    // The header was rewritten (or the VA reused without Destroy reaching\n'
     '    // us): the surface is a view of other EDRAM now.\n'
     '    UnuseTarget(bound->second);\n'
     '    bound->second = key;\n'
     '    ++g_target_users[key];\n'
     '  }\n',
     '  const uint64_t key = TargetKey(*desc, depth, format, scale);\n'
     '  if (g_override_active) {\n'
     '    // sasrt-nx: a replayed op\'s view; the surface\'s own binding (the title device\'s now) is left as it is, and\n'
     '    // the view\'s target stays (one user for good).\n'
     '    if (!g_targets.count(key))\n'
     '      ++g_target_users[key];\n'
     '  } else {\n'
     '  auto [bound, first_use] = g_surface_keys.try_emplace(surface_va, key);\n'
     '  if (first_use) {\n'
     '    ++g_target_users[key];\n'
     '    ++g_surface_epoch;\n'
     '  } else if (bound->second != key) {\n'
     '    ++g_surface_epoch;\n'
     '    // The header was rewritten (or the VA reused without Destroy reaching\n'
     '    // us): the surface is a view of other EDRAM now. sasrt-nx: the old view keeps its target (the EDRAM keeps\n'
     '    // its bytes whatever header describes it; this game re-points surfaces all through a frame).\n'
     '    bound->second = key;\n'
     '    ++g_target_users[key];\n'
     '  }\n'
     '  }\n'),
    ('guest/command_buffers.cpp',
     '  // Run\n  u32 command_buffer = 0;\n};\n',
     '  // Run\n  u32 command_buffer = 0;\n\n'
     '  // sasrt-nx (2026-10-20): the render targets and depth surface bound when recorded, with their headers then\n'
     '  // (the game re-points surfaces before the replay).\n'
     '  u32 surfaces = 0;\n'
     '  u32 surface_va[5] = {};\n'
     '  d3d::SurfaceDesc surface_desc[5] = {};\n};\n'),
    ('guest/command_buffers.cpp',
     '  op.state = CopyState(buffer, bytes, op.plain_dirty, op.vs_dirty, op.ps_dirty);\n'
     '  *out_buffer = &buffer;\n',
     '  op.state = CopyState(buffer, bytes, op.plain_dirty, op.vs_dirty, op.ps_dirty);\n'
     '  // sasrt-nx: the bound surfaces\' headers as they are now (render targets 0-3, then depth).\n'
     '  for (u32 i = 0; i < 5; ++i) {\n'
     '    const u32 offset = i < 4 ? d3d::kDeviceOffsetRenderTargets + i * 4 : d3d::kDeviceOffsetDepthStencil;\n'
     '    const u32 surface = u32(*reinterpret_cast<const be_u32 *>(bytes + offset));\n'
     '    const auto *desc = surface ? GuestPtr<const d3d::SurfaceDesc>(surface + sizeof(d3d::Resource)) : nullptr;\n'
     '    if (!desc)\n'
     '      continue;\n'
     '    op.surface_va[op.surfaces] = surface;\n'
     '    op.surface_desc[op.surfaces] = *desc;\n'
     '    ++op.surfaces;\n'
     '  }\n'
     '  *out_buffer = &buffer;\n'),
    ('guest/command_buffers.cpp',
     '  for (const Op &op : buffer.ops) {\n'
     '    ApplyState(state, buffer.arena.data() + op.state, op.plain_dirty, op.vs_dirty, op.ps_dirty);\n',
     '  for (const Op &op : buffer.ops) {\n'
     '    ApplyState(state, buffer.arena.data() + op.state, op.plain_dirty, op.vs_dirty, op.ps_dirty);\n'
     '    SetReplaySurfaceOverridesLocked(op.surface_va, op.surface_desc, op.surfaces);  // sasrt-nx\n'),
    ('guest/command_buffers.cpp',
     '  SetReplayPredicationLocked(previous_predication);\n',
     '  SetReplayPredicationLocked(previous_predication);\n'
     '  SetReplaySurfaceOverridesLocked(nullptr, nullptr, 0);  // sasrt-nx\n'),
    ('guest/command_buffers.cpp',
     '#include "renut_engine/gpu/banjo_renut_tuning.h"\n',
     '#include "renut_engine/gpu/banjo_renut_tuning.h"\n#include "renut_engine/gpu/render/surfaces.h"\n'),
]

# The EDRAM view of a bound render target as the GPU sees it (2026-10-20): RB_SURFACE_INFO (pitch, samples) and
# RB_COLOR0-3_INFO / RB_DEPTH_INFO (EDRAM base, format) from the device's destination packet (+0x2880), which Direct3D
# wrote at SetRenderTarget, instead of the surface header read at the draw. This game rewrites bound surfaces'
# headers in place: a G-buffer target's header read 32x1 by its resolve, another decoded as 4065x9985. The header's
# size still sizes the target (a smaller one never shrinks it). A recorded op's state snapshot holds its packet, so a
# replay gets the recording device's views.
EDITS += [
    ('render/surfaces.h',
     'void SetReplaySurfaceOverridesLocked(const u32 *surface_va, const d3d::SurfaceDesc *desc, u32 count);\n',
     'void SetReplaySurfaceOverridesLocked(const u32 *surface_va, const d3d::SurfaceDesc *desc, u32 count);\n'
     '// sasrt-nx (2026-10-20): the next GetHostSurfaceLocked takes this EDRAM view (RB_SURFACE_INFO and the slot\'s\n'
     '// RB_COLOR*_INFO / RB_DEPTH_INFO, from the device\'s destination packet) over the header\'s.\n'
     'void SetSurfaceViewLocked(u32 surface_info, u32 view_info, bool depth);\n'),
    ('render/surfaces.cpp',
     'const d3d::SurfaceDesc *ReplaySurfaceOverride(u32 surface_va) {\n',
     'bool g_view_pending = false;\n'
     'u32 g_view_surface_info = 0, g_view_info = 0;\n'
     'bool g_view_depth = false;\n\n'
     'void SetSurfaceViewLocked(u32 surface_info, u32 view_info, bool depth) {\n'
     '  g_view_pending = true;\n'
     '  g_view_surface_info = surface_info;\n'
     '  g_view_info = view_info;\n'
     '  g_view_depth = depth;\n'
     '}\n\n'
     'const d3d::SurfaceDesc *ReplaySurfaceOverride(u32 surface_va) {\n'),
    ('render/surfaces.cpp',
     '  g_override_active = recorded != nullptr;\n',
     '  g_override_active = recorded != nullptr;\n'
     '  // sasrt-nx: the slot\'s EDRAM view from the destination packet (SetSurfaceViewLocked), for this lookup only.\n'
     '  d3d::SurfaceDesc view_desc;\n'
     '  const bool view = g_view_pending;\n'
     '  g_view_pending = false;\n'
     '  if (view) {\n'
     '    view_desc = *desc;\n'
     '    view_desc.SurfaceInfo = g_view_surface_info;\n'
     '    view_desc.ColorInfo = g_view_info;\n'
     '    if (g_view_depth) {\n'
     '      // The packet\'s depth format, whatever the header says (it may be re-pointed): D24FS8, the 20e4 float\n'
     '      // depth, by RB_DEPTH_INFO bit 16, else D24S8 (2026-10-20: this game\'s scene depth is float; a D24S8\n'
     '      // header over it made the depth words unorm, which the lighting read as floats).\n'
     '      view_desc.Format = (u32(view_desc.Format) & ~0x3Fu) | ((g_view_info >> 16) & 1 ? 23u : 22u);\n'
     '    } else if (d3d::IsDepthFormat(view_desc.Format)) {\n'
     '      // A depth header re-pointed to a colour view: 8888.\n'
     '      view_desc.Format = (u32(view_desc.Format) & ~0x3Fu) | 6u;\n'
     '    }\n'
     '    desc = &view_desc;\n'
     '    g_override_active = true;  // the surface\'s own binding is left alone (a view, not a re-point)\n'
     '  }\n'),
    ('render/surfaces.cpp',
     '  const bool memo = banjo::renut_gpu::CpuMemosOn();\n'
     '  SurfaceMemo &m',
     '  const bool memo = banjo::renut_gpu::CpuMemosOn() && !view;  // sasrt-nx: the memo knows no EDRAM base\n'
     '  SurfaceMemo &m'),
    ('render/draw.cpp',
     '    HostSurface *surface = GetHostSurfaceLocked(va);\n',
     '    {  // sasrt-nx: the slot\'s EDRAM view from the destination packet\n'
     '      const d3d::DestinationPacket &p = device.dev().m_DestinationPacket;\n'
     '      const u32 info = i == 0 ? u32(p.Color0Info) : i == 1 ? u32(p.Color1Info) : i == 2 ? u32(p.Color2Info)\n'
     '                                                                                    : u32(p.Color3Info);\n'
     '      SetSurfaceViewLocked(u32(p.SurfaceInfo), info, false);\n'
     '    }\n'
     '    HostSurface *surface = GetHostSurfaceLocked(va);\n'),
    ('render/draw.cpp',
     '  HostSurface *depth = GetHostSurfaceLocked(device.U32(d3d::kDeviceOffsetDepthStencil));\n',
     '  if (device.U32(d3d::kDeviceOffsetDepthStencil))  // sasrt-nx: the destination packet\'s depth view\n'
     '    SetSurfaceViewLocked(u32(device.dev().m_DestinationPacket.SurfaceInfo),\n'
     '                         u32(device.dev().m_DestinationPacket.DepthInfo), true);\n'
     '  HostSurface *depth = GetHostSurfaceLocked(device.U32(d3d::kDeviceOffsetDepthStencil));\n'),
    ('render/draw.cpp',
     '  HostSurface *surface = GetHostSurfaceLocked(source_va);\n',
     '  if (source_va) {  // sasrt-nx: the destination packet\'s view of the resolve source\n'
     '    const d3d::DestinationPacket &p = device.dev().m_DestinationPacket;\n'
     '    const u32 info = source == 4 ? u32(p.DepthInfo) : source == 0 ? u32(p.Color0Info)\n'
     '                     : source == 1 ? u32(p.Color1Info) : source == 2 ? u32(p.Color2Info) : u32(p.Color3Info);\n'
     '    SetSurfaceViewLocked(u32(p.SurfaceInfo), info, source == 4);\n'
     '  }\n'
     '  HostSurface *surface = GetHostSurfaceLocked(source_va);\n'),
]

# Surface headers when a draw, clear or resolve is queued (2026-10-20). Renut snapshots the device at the call and
# runs the work later on its render thread, which read the bound surfaces' headers then; this game's thread has
# re-pointed them by then (a G-buffer target's header read 1200x544 at its resolve, others 32x1 or 4065x9985). The
# headers are captured with the device snapshot and the render thread takes those (ReplaySurfaceOverride, as for a
# recorded command buffer's ops).
EDITS += [
    ('backend/queued.cpp',
     '  d3d::TextureFetchConstant dest_format{};\n',
     '  d3d::TextureFetchConstant dest_format{};\n'
     '  // sasrt-nx: the bound surfaces\' headers at the call (render targets 0-3, then depth).\n'
     '  u32 surfaces = 0;\n'
     '  u32 surface_va[5] = {};\n'
     '  d3d::SurfaceDesc surface_desc[5] = {};\n'),
    ('backend/queued.cpp',
     'void QueueCapture(DrawCapture *capture) {\n',
     '// sasrt-nx: the headers of the surfaces the device binds, as they are now (from the device itself: a snapshot-delta\n'
     '// capture holds only the bytes that changed).\n'
     'void CaptureSurfaces(DrawCapture *c, const u8 *bytes) {\n'
     '  c->surfaces = 0;\n'
     '  if (!bytes)\n'
     '    return;\n'
     '  for (u32 i = 0; i < 5; ++i) {\n'
     '    const u32 offset = i < 4 ? d3d::kDeviceOffsetRenderTargets + i * 4 : d3d::kDeviceOffsetDepthStencil;\n'
     '    const u32 surface = u32(*reinterpret_cast<const be_u32 *>(bytes + offset));\n'
     '    const auto *desc = surface ? GuestPtr<const d3d::SurfaceDesc>(surface + sizeof(d3d::Resource)) : nullptr;\n'
     '    if (!desc)\n'
     '      continue;\n'
     '    c->surface_va[c->surfaces] = surface;\n'
     '    c->surface_desc[c->surfaces] = *desc;\n'
     '    ++c->surfaces;\n'
     '  }\n'
     '}\n\n'
     'void QueueCapture(DrawCapture *capture) {\n'),
    ('backend/queued.cpp',
     '    const u8 *device = DeviceForDraw(*capture);\n',
     '    const u8 *device = DeviceForDraw(*capture);\n'
     '    SetReplaySurfaceOverridesLocked(capture->surface_va, capture->surface_desc, capture->surfaces);  // sasrt-nx\n'),
    ('backend/queued.cpp',
     '    g_chain_hint = {};  // sa2-nx: only for the draw itself\n',
     '    SetReplaySurfaceOverridesLocked(nullptr, nullptr, 0);  // sasrt-nx\n'
     '    g_chain_hint = {};  // sa2-nx: only for the draw itself\n'),
    ('backend/queued.cpp',
     '  capture->call = call;\n',
     '  capture->call = call;\n'
     '  CaptureSurfaces(capture, reinterpret_cast<const u8 *>(device));  // sasrt-nx\n'),
    ('backend/queued.cpp',
     '  args->state.assign(device, device + d3d::kDeviceSnapshotSize);\n',
     '  args->state.assign(device, device + d3d::kDeviceSnapshotSize);\n'
     '  CaptureSurfaces(args, args->state.data());  // sasrt-nx\n'),
    ('backend/queued.cpp',
     '    ClearStateLocked(args->state.data()',
     '    SetReplaySurfaceOverridesLocked(args->surface_va, args->surface_desc, args->surfaces);  // sasrt-nx\n'
     '    ClearStateLocked(args->state.data()'),
    ('backend/queued.cpp',
     '    ResolveStateLocked(args->state.data()',
     '    SetReplaySurfaceOverridesLocked(args->surface_va, args->surface_desc, args->surfaces);  // sasrt-nx\n'
     '    ResolveStateLocked(args->state.data()'),
    ('backend/queued.cpp',
     '    g_capture_pool.Give(args, true);\n',
     '    SetReplaySurfaceOverridesLocked(nullptr, nullptr, 0);  // sasrt-nx\n'
     '    g_capture_pool.Give(args, true);\n'),
    ('backend/queued.cpp',
     '#include "renut_engine/gpu/banjo_renut_tuning.h"\n',
     '#include "renut_engine/gpu/banjo_renut_tuning.h"\n#include "renut_engine/gpu/render/surfaces.h"\n'),
]

# Clears through every view of the EDRAM they write (2026-10-20). This game draws into one EDRAM range through views
# of other sizes, pitches and formats in a frame (the G-buffer at 1152x544, an HDR view of it, a 576x272 4x MSAA depth
# alias, the 1280x720 output): one host target each in Renut. A clear writes the EDRAM on the console, which every
# view then reads; here only the cleared view's target was cleared (and its same-pitch colour aliases), so the output
# target's depth kept the frames before and the composite failed its depth test: the menus' moving UI left trails.
# A clear now reaches every target of the same kind (colour, or depth) at the same EDRAM base, over the same rect
# (clipped to it).
EDITS += [
    ('render/surfaces.h',
     'void ColorAliasesLocked(const HostSurface *surface, std::vector<HostSurface *> &out);\n',
     'void ColorAliasesLocked(const HostSurface *surface, std::vector<HostSurface *> &out);\n'
     '// sasrt-nx (2026-10-20): every other target of the same kind (colour or depth) at the surface\'s EDRAM base, any\n'
     '// pitch, samples or format.\n'
     'void EdramAliasesLocked(const HostSurface *surface, std::vector<HostSurface *> &out);\n'),
    ('render/surfaces.cpp',
     'void ColorAliasesLocked(const HostSurface *surface, std::vector<HostSurface *> &out) {\n',
     'void EdramAliasesLocked(const HostSurface *surface, std::vector<HostSurface *> &out) {\n'
     '  out.clear();\n'
     '  if (!surface)\n'
     '    return;\n'
     '  uint64_t own = 0;\n'
     '  bool found = false;\n'
     '  for (const auto &[key, target] : g_targets) {\n'
     '    if (target.get() == surface) {\n'
     '      own = key;\n'
     '      found = true;\n'
     '      break;\n'
     '    }\n'
     '  }\n'
     '  if (!found)\n'
     '    return;\n'
     '  for (const auto &[key, target] : g_targets) {\n'
     '    if (target && target.get() != surface && target->texture && target->depth == surface->depth &&\n'
     '        (key & 0xFFF) == (own & 0xFFF))\n'
     '      out.push_back(target.get());\n'
     '  }\n'
     '}\n\n'
     'void ColorAliasesLocked(const HostSurface *surface, std::vector<HostSurface *> &out) {\n'),
    ('render/draw.cpp',
     '    ColorAliasesLocked(t.colors[i], found);\n',
     '    EdramAliasesLocked(t.colors[i], found);  // sasrt-nx: every view at the EDRAM base (ColorAliasesLocked\'s superset)\n'),
    ('render/draw.cpp',
     '    cmd->clearDepthStencil((flags & 0x10) != 0, (flags & 0x20) != 0, depth, stencil & 0xFF,\n'
     '                           &host_rect, 1);\n'
     '  }\n',
     '    cmd->clearDepthStencil((flags & 0x10) != 0, (flags & 0x20) != 0, depth, stencil & 0xFF,\n'
     '                           &host_rect, 1);\n'
     '    // sasrt-nx: the other depth views of the same EDRAM.\n'
     '    static std::vector<HostSurface *> depth_aliases;\n'
     '    EdramAliasesLocked(t.depth, depth_aliases);\n'
     '    for (HostSurface *alias : depth_aliases) {\n'
     '      Targets a;\n'
     '      a.depth = alias;\n'
     '      a.width = alias->width;\n'
     '      a.height = alias->height;\n'
     '      a.scale = alias->scale;\n'
     '      const plume::RenderRect alias_rect(\n'
     '          std::min(rect.left, int32_t(alias->width)), std::min(rect.top, int32_t(alias->height)),\n'
     '          std::min(rect.right, int32_t(alias->width)), std::min(rect.bottom, int32_t(alias->height)));\n'
     '      if (alias_rect.right <= alias_rect.left || alias_rect.bottom <= alias_rect.top || !BindTargets(a))\n'
     '        continue;\n'
     '      const plume::RenderRect alias_host = ScaleRect(alias_rect, a.scale);\n'
     '      ++alias->writes;\n'
     '      cmd->clearDepthStencil((flags & 0x10) != 0, (flags & 0x20) != 0, depth, stencil & 0xFF, &alias_host, 1);\n'
     '    }\n'
     '    if (!depth_aliases.empty() && !BindTargets(t))  // the cleared targets again, for what follows\n'
     '      return;\n'
     '  }\n'),
]

# The video scaler (2026-10-20): this game renders below 720p (1152x544 in its menus and races) and the Xbox 360's
# scaler stretches the front buffer's resolved region to the screen at scan-out. Renut scanned out the whole front
# buffer texture: the frame sat in its top left at 1:1, older content around it. The region a colour resolve last
# wrote into a texture (from its origin) is kept, and the present scans out that region of the front buffer.
EDITS += [
    ('render/textures.h',
     '  uint32_t depth = 1;       // 3D depth, or array slices (6 for cubes)\n',
     '  uint32_t depth = 1;       // 3D depth, or array slices (6 for cubes)\n'
     '  // sasrt-nx (2026-10-20): the extent the last colour resolve wrote, from (0, 0) (guest pixels; 0 = none).\n'
     '  uint32_t sasrt_resolved_w = 0, sasrt_resolved_h = 0;\n'),
    ('render/draw.cpp',
     '      } else if (fits) {\n'
     '        dest->resolve_signature = sig;\n',
     '      } else if (fits) {\n'
     '        dest->resolve_signature = sig;\n'
     '        dest->sasrt_resolved_w = uint32_t(dest_x + (src.x2 - src.x1));  // sasrt-nx: the video scaler\'s region\n'
     '        dest->sasrt_resolved_h = uint32_t(dest_y + (src.y2 - src.y1));\n'),
    ('render/draw.cpp',
     '  image.source_width = texture->scale.Size(texture->width);\n'
     '  image.source_height = texture->scale.Size(texture->height);\n',
     '  image.source_width = texture->scale.Size(texture->width);\n'
     '  image.source_height = texture->scale.Size(texture->height);\n'
     '  // sasrt-nx: the region the game resolved into it (the 360\'s scaler stretches that to the screen).\n'
     '  if (texture->sasrt_resolved_w && texture->sasrt_resolved_h && texture->sasrt_resolved_w <= texture->width &&\n'
     '      texture->sasrt_resolved_h <= texture->height) {\n'
     '    image.source_width = texture->scale.Size(texture->sasrt_resolved_w);\n'
     '    image.source_height = texture->scale.Size(texture->sasrt_resolved_h);\n'
     '  }\n'),
]

# The title device's GPU event / query pools (SA2's sub_8254F530, this game's sub_82CD37D8: +24424 8 KB physical,
# +24432, +24448, +24452), which the hardware path (sub_82CF84C0) allocates and sa2-nx's creation leaves out: this game
# issues GPU events through them (sub_82CEEB48, called from its frame code) where SA2 does not. The first PC boot
# wrote through the null +24448. In sa2-nx's text (SA2's addresses; tools/renut_from_sa2.py maps them after).
EDITS += [
    ('d3d/hooks/device.cpp',
     'REX_EXTERN(__imp__sub_8255C150);  // D3D::InitializeApiState (CDevice*)\n',
     'REX_EXTERN(__imp__sub_8255C150);  // D3D::InitializeApiState (CDevice*)\n'
     'REX_EXTERN(__imp__sub_8254F530);  // sasrt-nx: the GPU event / query pools of the hardware path (CDevice*)\n'),
    ('d3d/hooks/device.cpp',
     '    __imp__sub_8255C150(ctx, base);\n',
     '    __imp__sub_8255C150(ctx, base);\n'
     '    // sasrt-nx: the event / query pools the hardware path allocates (this game uses them; SA2 does not).\n'
     '    ctx.r3.u64 = device_va;\n'
     '    __imp__sub_8254F530(ctx, base);\n'
     '    if (!ctx.r3.u32)\n'
     '      RGPU_ERROR("Direct3D_CreateDevice: the event pools (sub_8254F530) failed");\n'),
]

# Guest memory for Renut's own blocks (the record heap, the ring sink, the device block, the vertex scratch). This game
# fills the guest's physical memory at boot: the first PC boot stopped at the ring sink's 4 MB ("BaseHeap::Alloc failed
# to find contiguous range") after the 64 MB record heap. In the hybrid route the game's own Direct3D creates its
# resources, so the record heap holds little: 8 MB. And a block the physical heap cannot give comes from the 64 KB-page
# virtual heap (0x40000000-0x7FFFFFFF, mapped 1:1 like the rest): nothing reads these blocks through a physical address
# but the ring's packets, which go to the sink unread.
EDITS += [
    ('guest/guest_records.cpp',
     'constexpr u32 kHeapSize = 64u << 20;',
     'constexpr u32 kHeapSize = 8u << 20;  // sasrt-nx: 8 MB (N&B 64 MB; the hybrid route creates few records)'),
    ('guest/guest_records.cpp',
     '                   &guest_va)) {\n'
     '    RGPU_ERROR("Reserving {} bytes of guest physical memory failed", size);\n'
     '    return 0;\n'
     '  }',
     '                   &guest_va)) {\n'
     '    // sasrt-nx: the 64 KB-page virtual heap when the physical one is full (this game\'s is, from its boot on).\n'
     '    rex::memory::BaseHeap *virtual_heap = REX_KERNEL_MEMORY()->LookupHeapByType(false, 64u * 1024u);\n'
     '    if (!virtual_heap ||\n'
     '        !virtual_heap->Alloc(size, 64u * 1024u,\n'
     '                             rex::memory::kMemoryAllocationReserve | rex::memory::kMemoryAllocationCommit,\n'
     '                             rex::memory::kMemoryProtectRead | rex::memory::kMemoryProtectWrite, true,\n'
     '                             &guest_va)) {\n'
     '      RGPU_ERROR("Reserving {} bytes of guest physical or virtual memory failed", size);\n'
     '      return 0;\n'
     '    }\n'
     '    RGPU_INFO("{} bytes of guest memory at {:08X} (virtual heap: the physical one is full)", size, guest_va);\n'
     '  }'),
]

# A raw hook at an address this port hooks too (BANJO_RENUT_HOOK_RAW_SHARED): its body may call the original, which
# the plain RAW form declares and this one did not.
EDITS += [
    ('banjo_renut_select.h',
     '#define BANJO_RENUT_HOOK_RAW_SHARED(subroutine) \\\n'
     '  extern "C" void renut_native_##subroutine([[maybe_unused]] PPCContext& __restrict ctx, uint8_t* base)',
     '#define BANJO_RENUT_HOOK_RAW_SHARED(subroutine) \\\n'
     '  REX_EXTERN(__imp__##subroutine);             \\\n'
     '  extern "C" void renut_native_##subroutine([[maybe_unused]] PPCContext& __restrict ctx, uint8_t* base)'),
]

# D3DDevice_BeginIndexedVertices (sub_82CD11C0, renut_engine/sasrt_renut_hooks.cpp): SA2 never calls it, so its Renut
# has no hook; this game's post-processing draws every pass with it. The hook defers one copy of the draw's vertices
# and then its indices (BeginVertices' deferred path); the draw finds its indices at up_index_offset in that copy.
EDITS += [
    ('render/draw.h',
     '  const u8 *up_indices = nullptr;\n'
     '  bool up_indices_32 = false;\n'
     '};',
     '  const u8 *up_indices = nullptr;\n'
     '  bool up_indices_32 = false;\n'
     '  // sasrt-nx (2026-10-20, D3DDevice_BeginIndexedVertices): the indices follow the vertices in the one deferred\n'
     '  // copy, from this offset (0: none there).\n'
     '  u32 up_index_offset = 0;\n'
     '};'),
    ('backend/queued.cpp',
     '    if (!capture->indices.empty())\n'
     '      call.up_indices = capture->indices.data();\n',
     '    if (!capture->indices.empty())\n'
     '      call.up_indices = capture->indices.data();\n'
     '    if (call.up_index_offset && call.up_vertices)  // sasrt-nx: BeginIndexedVertices\n'
     '      call.up_indices = call.up_vertices + call.up_index_offset;\n'),
    ('guest/command_buffers.cpp',
     '      if (op.up_indices != kNone)\n'
     '        call.up_indices = buffer.arena.data() + op.up_indices;\n',
     '      if (op.up_indices != kNone)\n'
     '        call.up_indices = buffer.arena.data() + op.up_indices;\n'
     '      if (call.up_index_offset && call.up_vertices)  // sasrt-nx: BeginIndexedVertices\n'
     '        call.up_indices = call.up_vertices + call.up_index_offset;\n'),
]

# The game's reverse depth: its viewport runs MinZ 1 to MaxZ 0 (zscale -1, zoffset 1), which Vulkan and deko3d take as
# a backwards host depth range and D3D12 does not (every depth-tested draw was lost on the PC: the 3D scene stayed
# empty). Where the back end cannot (all but deko3d, whose package predates the shader side), the host viewport spans
# 0-1 and the vertex shaders write z * zscale + w * zoffset, the guest's depth itself (g_DepthRemap in
# app/thirdparty/reblue-XenosRecomp/XenosRecomp/shader_common.h, 1352, which was padding).
EDITS += [
    ('render/draw.cpp',
     '  float pad_1352[2];\n',
     '  // 1352, sasrt-nx (2026-10-20; was padding): g_DepthRemap, a backwards depth range done in the vertex shader\n'
     '  // (z * [0] + w * [1]); [0] = 0: off. See ComputeViewportSlow.\n'
     '  float depth_remap[2];\n'),
    ('render/draw.cpp',
     '  float pixel_origin[2] = {0.0f, 0.0f};\n'
     '};',
     '  float pixel_origin[2] = {0.0f, 0.0f};\n'
     '  // sasrt-nx (2026-10-20): SharedConstants::depth_remap.\n'
     '  float depth_remap[2] = {0.0f, 0.0f};\n'
     '};'),
    ('render/draw.cpp',
     '    vs.viewport = plume::RenderViewport(xo + pixel_center - xs, yo + pixel_center + ys, 2.0f * xs, -2.0f * ys,\n'
     '                                        min_z, max_z);\n',
     '    vs.viewport = plume::RenderViewport(xo + pixel_center - xs, yo + pixel_center + ys, 2.0f * xs, -2.0f * ys,\n'
     '                                        min_z, max_z);\n'
     '    // sasrt-nx (2026-10-20): a backwards depth range (this game\'s reverse depth, MinZ 1 to MaxZ 0) on a back end\n'
     '    // that cannot take one (D3D12): 0-1 here, and the vertex shader writes the guest\'s depth (g_DepthRemap).\n'
     '    if (min_z > max_z && !IsDeko3D()) {\n'
     '      vs.viewport.minDepth = 0.0f;\n'
     '      vs.viewport.maxDepth = 1.0f;\n'
     '      vs.depth_remap[0] = zs;\n'
     '      vs.depth_remap[1] = zo;\n'
     '    }\n'),
    ('render/draw.cpp',
     '  std::memcpy(sc.pixel_origin, viewport.pixel_origin, sizeof(sc.pixel_origin));  // Renut upstream 574b488\n',
     '  std::memcpy(sc.pixel_origin, viewport.pixel_origin, sizeof(sc.pixel_origin));  // Renut upstream 574b488\n'
     '  std::memcpy(sc.depth_remap, viewport.depth_remap, sizeof(sc.depth_remap));  // sasrt-nx\n'),
]

# The 16-bit _EXPAND texture formats (k_16_EXPAND 27, k_16_16_EXPAND 28, k_16_16_16_16_EXPAND 29: the XDK's
# D3DFMT_*16F_EXPAND) are 16-bit floats, as k_16_FLOAT 30 / 31 / 32 (Xenia maps them to the float host formats too).
# This game resolves its HDR scene as k_16_16_16_16_FLOAT and its tone map samples it as k_16_16_16_16_EXPAND: Renut
# read them as UNORM and, the formats differing, took the texture from guest memory instead of the resolve.
EDITS += [
    ('render/format.cpp',
     '  case T::Fmt16:\n'
     '  case T::Fmt16_Expand:\n'
     '    return plain(is_signed ? F::R16_SNORM : F::R16_UNORM, 2);\n'
     '  case T::Fmt16_16:\n'
     '  case T::Fmt16_16_Expand:\n'
     '    return plain(is_signed ? F::R16G16_SNORM : F::R16G16_UNORM, 4);\n'
     '  case T::Fmt16_16_16_16:\n'
     '  case T::Fmt16_16_16_16_Expand:\n'
     '    return plain(is_signed ? F::R16G16B16A16_SNORM : F::R16G16B16A16_UNORM, 8);\n',
     '  case T::Fmt16:\n'
     '    return plain(is_signed ? F::R16_SNORM : F::R16_UNORM, 2);\n'
     '  case T::Fmt16_16:\n'
     '    return plain(is_signed ? F::R16G16_SNORM : F::R16G16_UNORM, 4);\n'
     '  case T::Fmt16_16_16_16:\n'
     '    return plain(is_signed ? F::R16G16B16A16_SNORM : F::R16G16B16A16_UNORM, 8);\n'
     '  // sasrt-nx (2026-10-20): the _EXPAND formats are 16-bit floats (D3DFMT_*16F_EXPAND).\n'
     '  case T::Fmt16_Expand:\n'
     '    return plain(F::R16_FLOAT, 2);\n'
     '  case T::Fmt16_16_Expand:\n'
     '    return plain(F::R16G16_FLOAT, 4);\n'
     '  case T::Fmt16_16_16_16_Expand:\n'
     '    return plain(F::R16G16B16A16_FLOAT, 8);\n'),
    ('render/textures.cpp',
     'bool SameData(const u32 a[6], const u32 b[6]) {\n'
     '  constexpr u32 kDimensionMask = 0x600u;  // fetch dword 5 bits 9-10\n'
     '  return a[1] == b[1] && a[2] == b[2] && (a[5] & kDimensionMask) == (b[5] & kDimensionMask);\n'
     '}\n',
     'bool SameData(const u32 a[6], const u32 b[6]) {\n'
     '  constexpr u32 kDimensionMask = 0x600u;  // fetch dword 5 bits 9-10\n'
     '  // sasrt-nx (2026-10-20): k_16*_EXPAND (27-29) holds the same 16-bit floats as k_16*_FLOAT (30-32).\n'
     '  const auto data_word = [](u32 w) {\n'
     '    const u32 format = w & 0x3Fu;\n'
     '    return (format >= 27 && format <= 29) ? (w & ~0x3Fu) | (format + 3) : w;\n'
     '  };\n'
     '  return data_word(a[1]) == data_word(b[1]) && a[2] == b[2] &&\n'
     '         (a[5] & kDimensionMask) == (b[5] & kDimensionMask);\n'
     '}\n'),
]

# sa2-nx's report (2026-10-20): the draw area followed the first colour target, and a smaller depth target bound with it
# is undefined on D3D12 and a "ZT width violation" GPU exception on Maxwell. This game binds a 288x256 colour target
# with a 256x256 depth target every frame (its first pass). The extent (scissor, clears, screen-space mapping) is now
# what every bound target covers.
EDITS += [
    ('render/draw.cpp',
     '      RGPU_WARN("Draw binds a depth target smaller than its colour target: colour {:08X} {}x{}, depth {:08X} {}x{}",\n'
     '                t.colors[0]->guest_va, t.width, t.height, t.depth->guest_va, t.depth->width, t.depth->height);\n'
     '  }\n',
     '      RGPU_WARN("Draw binds a depth target smaller than its colour target: colour {:08X} {}x{}, depth {:08X} {}x{}",\n'
     '                t.colors[0]->guest_va, t.width, t.height, t.depth->guest_va, t.depth->width, t.depth->height);\n'
     '  }\n'
     '  // sasrt-nx (2026-10-20): the draw area is what every bound target covers (sa2-nx\'s report above).\n'
     '  for (uint32_t i = 1; i < t.color_count; ++i) {\n'
     '    t.width = std::min(t.width, t.colors[i]->width);\n'
     '    t.height = std::min(t.height, t.colors[i]->height);\n'
     '  }\n'
     '  if (t.depth && t.color_count) {\n'
     '    t.width = std::min(t.width, t.depth->width);\n'
     '    t.height = std::min(t.height, t.depth->height);\n'
     '  }\n'),
]

# banjo-nx's deko3d shader optimisations of 2026-10-19/20 (the user's request: banjo-nx's shader and render-thread
# optimisations): banjo_renut_tuning.*, render/pipeline.cpp and three more come from banjo-nx's tree
# (tools/renut_from_sa2.py FROM_BANJO); the rest of them here.
EDITS += [
    # sa2-nx's finding of 2026-10-20 kept: with the alpha function as a constant, SA2's textures sampled as if at their
    # smallest mip in Ryujinx (only with it on; bisected to the alpha pass). Off until a console says otherwise.
    ('banjo_renut_tuning.cpp',
     'REXCVAR_DEFINE_BOOL(banjo_deko3d_alpha_spec, true, "Banjo/Enhancements",',
     'REXCVAR_DEFINE_BOOL(banjo_deko3d_alpha_spec, false, "Banjo/Enhancements",  // sasrt-nx: off, as sa2-nx'),
    # (banjo-nx's fetch alignment count and A/B pipeline keys in render/draw.cpp: in sa2-nx's tree since 2026-10-20.)
]

# (uam's flag 1024 crashed on this game's skinning shader until banjo-nx's checkSplitLoad fix of 2026-10-20 06:06: on.)

# The EDRAM depth restore (2026-10-20): appended to tools/renut_patches/sasrt_edits.py.
# This game restores its scene depth for its light pass and its HDR pass by drawing the resolved depth words (an 8_8_8_8
# view of its depth resolve) as colour into the EDRAM where that pass's depth buffer sits (draws 1304 and 1333 of a race
# frame), then binding the same EDRAM as depth: on the console those bits are the depth. Renut keeps a target per
# surface, so the depth buffers of both passes held nothing (no lighting, the HDR pass's depth tests wrong: the race was
# one fog colour). When a depth target is bound over the EDRAM base and pitch a 32-bit colour target wrote after it,
# that colour target's words become its depth (shaders/host/depth_restore_ps.hlsl, tools/renut_patches/extra).
EDITS += [
    ('gpu.cmake',
     '    renut_host_shader(${TARGET} depth_resolve_ms_ps ps_6_0)\n',
     '    renut_host_shader(${TARGET} depth_resolve_ms_ps ps_6_0)\n'
     '    renut_host_shader(${TARGET} depth_restore_ps ps_6_0)  # sasrt-nx (2026-10-20): the EDRAM depth restore\n'),
    ('render/surfaces.h',
     '  // depth, a depth write or stencil writes) and every clear of it; part of a resolve\'s signature.\n'
     '  uint64_t writes = 0;\n',
     '  // depth, a depth write or stencil writes) and every clear of it; part of a resolve\'s signature.\n'
     '  uint64_t writes = 0;\n'
     '  // sasrt-nx (2026-10-20, the EDRAM depth restore): g_surface_write_seq at this surface\'s last write, and for a\n'
     '  // depth surface the colour surface\'s write it was last restored from (RestoreDepthFromColorLocked).\n'
     '  uint64_t write_seq = 0;\n'
     '  uint64_t restored_from_seq = 0;\n'),
    ('render/surfaces.h',
     'HostSurface *SurfaceByGenerationLocked(uint64_t generation);\n',
     'HostSurface *SurfaceByGenerationLocked(uint64_t generation);\n'
     '\n'
     '// sasrt-nx (2026-10-20, the EDRAM depth restore): the order of surface writes (HostSurface::write_seq), and the\n'
     '// single-sample 32-bit colour target over the EDRAM base and pitch of depth target \'depth\' written after both its\n'
     '// own last write and the write it was last restored from, or nullptr.\n'
     'extern uint64_t g_surface_write_seq;\n'
     'HostSurface *DepthRestoreSourceLocked(const HostSurface *depth);\n'),
    ('render/surfaces.cpp',
     'HostSurface *SurfaceByGenerationLocked(uint64_t generation) {\n',
     'uint64_t g_surface_write_seq = 0;  // sasrt-nx (2026-10-20)\n'
     '\n'
     'HostSurface *DepthRestoreSourceLocked(const HostSurface *depth) {\n'
     '  if (!depth || !depth->depth || depth->samples != plume::RenderSampleCount::COUNT_1)\n'
     '    return nullptr;\n'
     '  uint64_t own = 0;\n'
     '  bool found = false;\n'
     '  for (const auto &[key, target] : g_targets) {\n'
     '    if (target.get() == depth) {\n'
     '      own = key;\n'
     '      found = true;\n'
     '      break;\n'
     '    }\n'
     '  }\n'
     '  if (!found)\n'
     '    return nullptr;\n'
     '  // TargetKey: the EDRAM base in bits 0-11, the pitch in 12-25.\n'
     '  constexpr uint64_t kBaseAndPitch = 0x3FFFFFFull;\n'
     '  HostSurface *best = nullptr;\n'
     '  for (const auto &[key, target] : g_targets) {\n'
     '    HostSurface *c = target.get();\n'
     '    if (!c || c->depth || !c->texture || (key & kBaseAndPitch) != (own & kBaseAndPitch) ||\n'
     '        c->samples != plume::RenderSampleCount::COUNT_1 || c->scale != depth->scale ||\n'
     '        (c->format != plume::RenderFormat::R8G8B8A8_UNORM && c->format != plume::RenderFormat::B8G8R8A8_UNORM))\n'
     '      continue;\n'
     '    if (c->write_seq <= depth->write_seq || c->write_seq <= depth->restored_from_seq)\n'
     '      continue;\n'
     '    if (!best || c->write_seq > best->write_seq)\n'
     '      best = c;\n'
     '  }\n'
     '  return best;\n'
     '}\n'
     '\n'
     'HostSurface *SurfaceByGenerationLocked(uint64_t generation) {\n'),
    # The writes, ordered.
    ('render/draw.cpp',
     '      ++targets.colors[i]->writes;\n'
     '  if (targets.depth) {\n',
     '    {\n'
     '      ++targets.colors[i]->writes;\n'
     '      targets.colors[i]->write_seq = ++g_surface_write_seq;  // sasrt-nx: the EDRAM depth restore\n'
     '    }\n'
     '  if (targets.depth) {\n'),
    ('render/draw.cpp',
     '    if (depth_writes || stencil_writes)\n'
     '      ++targets.depth->writes;\n',
     '    if (depth_writes || stencil_writes) {\n'
     '      ++targets.depth->writes;\n'
     '      targets.depth->write_seq = ++g_surface_write_seq;  // sasrt-nx: the EDRAM depth restore\n'
     '    }\n'),
    ('render/draw.cpp',
     '    ++t.colors[i]->writes;  // banjo-nx (banjo_renut_resolve_skip)\n',
     '    ++t.colors[i]->writes;  // banjo-nx (banjo_renut_resolve_skip)\n'
     '    t.colors[i]->write_seq = ++g_surface_write_seq;  // sasrt-nx: the EDRAM depth restore\n'),
    ('render/draw.cpp',
     '    ++t.depth->writes;  // banjo-nx (banjo_renut_resolve_skip)\n',
     '    ++t.depth->writes;  // banjo-nx (banjo_renut_resolve_skip)\n'
     '    t.depth->write_seq = ++g_surface_write_seq;  // sasrt-nx: the EDRAM depth restore\n'),
    # The shader blobs, the key, the pass.
    ('render/draw.cpp',
     '#include "renut_engine/gpu/banjo_renut_record.h"  // banjo-nx (package 28b)\n',
     '#include "renut_engine/gpu/banjo_renut_record.h"  // banjo-nx (package 28b)\n'
     '// sasrt-nx (2026-10-20): the EDRAM depth restore\'s pixel shader (shaders/host/depth_restore_ps.hlsl).\n'
     '#include "host_shaders/depth_restore_ps.spirv.h"\n'
     '#if defined(PLUME_DEKO3D)\n'
     '#include "host_shaders/depth_restore_ps.deko3d.h"\n'
     '#endif\n'
     '#if defined(_WIN32)\n'
     '#include "host_shaders/depth_restore_ps.dxil.h"\n'
     '#endif\n'),
    ('render/draw.cpp',
     'bool GatherTargets(const GuestDevice &device, Targets &t) {\n',
     'bool RestoreDepthFromColorLocked(HostSurface *depth, HostSurface *color);\n'
     '\n'
     'bool GatherTargets(const GuestDevice &device, Targets &t) {\n'),
    # The trigger: every bind of targets (draws, clears) goes through GatherTargets, before anything is recorded for it.
    ('render/draw.cpp',
     '    t.height = std::min(t.height, t.depth->height);\n'
     '  }\n'
     '  return true;\n'
     '}\n',
     '    t.height = std::min(t.height, t.depth->height);\n'
     '  }\n'
     '  if (t.depth && REXCVAR_GET(sasrt_renut_depth_restore)) {  // sasrt-nx (2026-10-20): the EDRAM depth restore\n'
     '    if (HostSurface *color = DepthRestoreSourceLocked(t.depth))\n'
     '      RestoreDepthFromColorLocked(t.depth, color);\n'
     '  }\n'
     '  return true;\n'
     '}\n'),
    ('render/draw.cpp',
     'bool ResolveDepth(HostSurface *surface, HostTexture *dest, const ClearRect &src, i32 dest_x,\n'
     '                  i32 dest_y, bool words = true) {\n',
     '// sasrt-nx (2026-10-20): the EDRAM depth restore (see DepthRestoreSourceLocked): the depth of \'depth\' from the words\n'
     '// \'color\' holds over the same EDRAM, its stencil 0 (the game\'s restores copy a depth whose stencil it cleared).\n'
     'bool RestoreDepthFromColorLocked(HostSurface *depth, HostSurface *color) {\n'
     '  auto &s = State();\n'
     '  static std::unique_ptr<plume::RenderShader> ps;\n'
     '  static bool ps_tried = false;\n'
     '  if (!ps_tried) {\n'
     '    ps_tried = true;\n'
     '    ps = CreateHostShader(s.device.get(), RENUT_HOST_SHADER(depth_restore_ps), "depth_restore_ps");\n'
     '  }\n'
     '  struct Entry {\n'
     '    plume::RenderFormat format = plume::RenderFormat::UNKNOWN;\n'
     '    std::unique_ptr<plume::RenderPipeline> pipeline;\n'
     '  };\n'
     '  static Entry pipelines[4];\n'
     '  plume::RenderPipeline *pipeline = nullptr;\n'
     '  for (Entry &e : pipelines) {\n'
     '    if (e.pipeline && e.format == depth->format) {\n'
     '      pipeline = e.pipeline.get();\n'
     '      break;\n'
     '    }\n'
     '    if (!e.pipeline && ps && s.present_vs) {\n'
     '      plume::RenderGraphicsPipelineDesc desc;\n'
     '      desc.pipelineLayout = s.utility_layout.get();\n'
     '      desc.vertexShader = s.present_vs.get();\n'
     '      desc.pixelShader = ps.get();\n'
     '      desc.primitiveTopology = plume::RenderPrimitiveTopology::TRIANGLE_LIST;\n'
     '      desc.cullMode = plume::RenderCullMode::NONE;\n'
     '      desc.renderTargetCount = 0;\n'
     '      desc.depthTargetFormat = depth->format;\n'
     '      desc.depthEnabled = true;\n'
     '      desc.depthWriteEnabled = true;\n'
     '      desc.depthFunction = plume::RenderComparisonFunction::ALWAYS;\n'
     '      e.pipeline = s.device->createGraphicsPipeline(desc);\n'
     '      e.format = depth->format;\n'
     '      if (e.pipeline)\n'
     '        e.pipeline->setName("sasrt depth restore");\n'
     '      pipeline = e.pipeline.get();\n'
     '      break;\n'
     '    }\n'
     '  }\n'
     '  const uint32_t slot = SurfaceSampleSlotLocked(color);\n'
     '  plume::RenderFramebuffer *framebuffer = GetFramebufferLocked(nullptr, 0, depth);\n'
     '  {\n'
     '    static uint32_t logged = 0;\n'
     '    if (logged++ < 8)\n'
     '      RGPU_INFO("[sasrt] EDRAM depth restore: depth {:08X} {}x{} gen {} from colour {:08X} {}x{} gen {} ({})",\n'
     '                depth->guest_va, depth->width, depth->height, depth->generation, color->guest_va, color->width,\n'
     '                color->height, color->generation,\n'
     '                pipeline && slot != kInvalidDescriptor && framebuffer ? "drawn" : "not possible");\n'
     '  }\n'
     '  depth->restored_from_seq = color->write_seq;\n'
     '  if (!pipeline || slot == kInvalidDescriptor || !framebuffer)\n'
     '    return false;\n'
     '  plume::RenderCommandList *cmd = s.command_list;\n'
     '  TransitionSurfaceLocked(color, plume::RenderTextureLayout::SHADER_READ);\n'
     '  TransitionSurfaceLocked(depth, plume::RenderTextureLayout::DEPTH_WRITE);\n'
     '  cmd->setFramebuffer(framebuffer);\n'
     '  const uint32_t w = depth->scale.Size(std::min(depth->width, color->width));\n'
     '  const uint32_t h = depth->scale.Size(std::min(depth->height, color->height));\n'
     '  cmd->setViewports(plume::RenderViewport(0.0f, 0.0f, float(w), float(h), 0.0f, 1.0f));\n'
     '  cmd->setScissors(plume::RenderRect(0, 0, int32_t(w), int32_t(h)));\n'
     '  cmd->clearDepthStencil(false, true, 0.0f, 0, nullptr, 0);\n'
     '  cmd->setGraphicsPipelineLayout(s.utility_layout.get());\n'
     '  cmd->setPipeline(pipeline);\n'
     '  cmd->setGraphicsDescriptorSet(s.texture_set.get(), 0);\n'
     '  cmd->setGraphicsDescriptorSet(s.sampler_set.get(), 1);\n'
     '  UtilityPush push{};\n'
     '  push.scale[0] = push.scale[1] = 1.0f;\n'
     '  push.texture_index = slot;\n'
     '  push.sampler_index = kPointClampSamplerSlot;\n'
     '  push.param0 = GpuTextureFormat(depth->format_word & 0x3F) == GpuTextureFormat::Fmt24_8_Float ? 1.0f : 0.0f;\n'
     '  cmd->setGraphicsPushConstants(0, &push, 0, sizeof(push));\n'
     '  cmd->drawInstanced(3, 1, 0, 0);\n'
     '  ++depth->writes;\n'
     '  depth->write_seq = ++g_surface_write_seq;\n'
     '  // The draw path binds its own layout, pipeline, targets and viewport again.\n'
     '  g_bound.framebuffer = nullptr;\n'
     '  g_bound.pipeline = nullptr;\n'
     '  g_bound.layout = false;\n'
     '  g_bound.viewport_set = false;\n'
     '  return true;\n'
     '}\n'
     '\n'
     'bool ResolveDepth(HostSurface *surface, HostTexture *dest, const ClearRect &src, i32 dest_x,\n'
     '                  i32 dest_y, bool words = true) {\n'),
    ('render/draw.cpp',
     'REXCVAR_DEFINE_INT32(banjo_renut_diag_draw_log_s, 0, "Banjo/Renut",\n',
     '// sasrt-nx (2026-10-20): RestoreDepthFromColorLocked.\n'
     'REXCVAR_DEFINE_BOOL(sasrt_renut_depth_restore, true, "SASRT",\n'
     '                    "The EDRAM depth restore: a depth target bound over the EDRAM a 32-bit colour target wrote "\n'
     '                    "after it takes that target\'s words as its depth, as the console\'s EDRAM gives them (this "\n'
     '                    "game restores its scene depth for its light and HDR passes that way). Off: the depth target "\n'
     '                    "keeps its own content (no lighting, the HDR pass\'s depth tests wrong)");\n'
     'REXCVAR_DEFINE_INT32(banjo_renut_diag_draw_log_s, 0, "Banjo/Renut",\n'),
]

# A diagnostic (2026-10-20): banjo_renut_diag_show_texture = "g<N>" shows the render target of generation N (the [sasrt]
# depth restore line and the draw log name them) instead of a texture.
EDITS += [
    ('backend/present.cpp',
     '  static const u32 va = [] {\n'
     '    const std::string v = REXCVAR_GET(banjo_renut_diag_show_texture);\n'
     '    return v.empty() ? 0u : u32(std::strtoul(v.c_str(), nullptr, 16));\n'
     '  }();\n'
     '  if (!va)\n'
     '    return false;\n',
     '  static const u32 va = [] {\n'
     '    const std::string v = REXCVAR_GET(banjo_renut_diag_show_texture);\n'
     '    return v.empty() || v[0] == \'g\' ? 0u : u32(std::strtoul(v.c_str(), nullptr, 16));\n'
     '  }();\n'
     '  static const u32 generation = [] {  // sasrt-nx (2026-10-20): "g<N>", a render target by generation\n'
     '    const std::string v = REXCVAR_GET(banjo_renut_diag_show_texture);\n'
     '    return !v.empty() && v[0] == \'g\' ? u32(std::strtoul(v.c_str() + 1, nullptr, 10)) : 0u;\n'
     '  }();\n'
     '  if (generation) {\n'
     '    HostSurface *surface = SurfaceByGenerationLocked(generation);\n'
     '    const uint32_t slot = SurfaceSampleSlotLocked(surface);\n'
     '    if (!surface || surface->depth || slot == kInvalidDescriptor)\n'
     '      return false;\n'
     '    out.texture = surface->texture.get();\n'
     '    out.layout = &surface->layout;\n'
     '    out.descriptor = slot;\n'
     '    out.width = surface->scale.Size(surface->width);\n'
     '    out.height = surface->scale.Size(surface->height);\n'
     '    out.gamma = float(REXCVAR_GET(banjo_renut_diag_show_gamma));\n'
     '    return true;\n'
     '  }\n'
     '  if (!va)\n'
     '    return false;\n'),
]
EDITS += [
    ('backend/present.cpp',
     '#include "renut_engine/gpu/render/draw.h"\n',
     '#include "renut_engine/gpu/render/draw.h"\n'
     '#include "renut_engine/gpu/render/surfaces.h"  // sasrt-nx: banjo_renut_diag_show_texture "g<N>"\n'),
]

# The texture exponent adjust (2026-10-20): a texture fetch constant's dword 3 bits 13-18 (signed) scale what the fetch
# returns by 2^adjust on the console. This game's FXAA (ps 6C215354C35798B8, the Xbox 360 FXAA) reads its input through
# two more headers with -1 and -2 (fxaaConsole360TexExpBiasNegOne / NegTwo); Renut ignored the adjust, so its blends were
# 2 and 4 times too bright: a white outline on every edge and sparkles on the track (a RenderDoc capture of the PC's
# D3D12: clean before the FXAA draw, outlined after it). Host samplers cannot scale, and a multiply in every texture
# fetch of every shader would cost every draw on the Switch: a fetch with an adjust reads a copy of the texture's base
# level times 2^adjust instead (shaders/host/exp_scale_ps.hlsl, tools/renut_patches/extra), made once per frame and
# texture epoch for each source; nothing changes for other fetches.
EDITS += [
    ('gpu.cmake',
     '    renut_host_shader(${TARGET} depth_restore_ps ps_6_0)  # sasrt-nx (2026-10-20): the EDRAM depth restore\n',
     '    renut_host_shader(${TARGET} depth_restore_ps ps_6_0)  # sasrt-nx (2026-10-20): the EDRAM depth restore\n'
     '    renut_host_shader(${TARGET} exp_scale_ps ps_6_0)  # sasrt-nx (2026-10-20): the texture exponent adjust\n'),
    ('render/draw.cpp',
     '#include "host_shaders/depth_restore_ps.dxil.h"\n'
     '#endif\n',
     '#include "host_shaders/depth_restore_ps.dxil.h"\n'
     '#endif\n'
     '// sasrt-nx (2026-10-20): the texture exponent adjust\'s copy (shaders/host/exp_scale_ps.hlsl).\n'
     '#include "host_shaders/exp_scale_ps.spirv.h"\n'
     '#if defined(PLUME_DEKO3D)\n'
     '#include "host_shaders/exp_scale_ps.deko3d.h"\n'
     '#endif\n'
     '#if defined(_WIN32)\n'
     '#include "host_shaders/exp_scale_ps.dxil.h"\n'
     '#endif\n'),
    ('render/draw.cpp',
     'void FillTextures(const GuestDevice &device, u32 fetch_mask, SharedConstants &sc, BindEffects *slot_fx = nullptr,\n',
     'uint32_t ExpAdjustedSlotLocked(uint32_t source_slot, int exp_adjust, uint32_t width, uint32_t height);\n'
     '\n'
     'void FillTextures(const GuestDevice &device, u32 fetch_mask, SharedConstants &sc, BindEffects *slot_fx = nullptr,\n'),
    ('render/draw.cpp',
     '    sc.texture_indices[dim][r] = index;\n'
     '    sc.sampler_indices[r] = SamplerWord(SamplerSlotLocked(fetch, binding.lod_scale));\n',
     '    // sasrt-nx (2026-10-20): the fetch constant\'s exponent adjust (ExpAdjustedSlotLocked), 2D fetches.\n'
     '    if (const int exp_adjust = int(i32(fetch.dword[3] << 13) >> 26);\n'
     '        exp_adjust != 0 && dim == 0 && !binding.stacked && REXCVAR_GET(sasrt_renut_texture_exp_adjust)) {\n'
     '      u32 w = 0, h = 0, d = 0;\n'
     '      fetch.Size(w, h, d);\n'
     '      const uint32_t scaled =\n'
     '          ExpAdjustedSlotLocked(binding.slot, exp_adjust, binding.scale.Size(w), binding.scale.Size(h));\n'
     '      if (scaled != kInvalidDescriptor)\n'
     '        index = scaled | binding.scale.code << kResolutionScaleShift;\n'
     '    }\n'
     '    sc.texture_indices[dim][r] = index;\n'
     '    sc.sampler_indices[r] = SamplerWord(SamplerSlotLocked(fetch, binding.lod_scale));\n'),
    ('render/draw.cpp',
     'bool ResolveDepth(HostSurface *surface, HostTexture *dest, const ClearRect &src, i32 dest_x,\n'
     '                  i32 dest_y, bool words = true) {\n',
     '// sasrt-nx (2026-10-20): the slot of a copy of the 2D texture at \'source_slot\' (its base level, \'width\' x \'height\'\n'
     '// host texels) times 2^exp_adjust, for a fetch constant with that exponent adjust (FillTextures), or\n'
     '// kInvalidDescriptor. 16-bit float, so a scale down keeps the source\'s bits. Made again at the first bind of each\n'
     '// frame and texture epoch (a resolve into the source bumps the epoch).\n'
     'uint32_t ExpAdjustedSlotLocked(uint32_t source_slot, int exp_adjust, uint32_t width, uint32_t height) {\n'
     '  auto &s = State();\n'
     '  constexpr plume::RenderFormat kFormat = plume::RenderFormat::R16G16B16A16_FLOAT;\n'
     '  static std::unique_ptr<plume::RenderShader> ps;\n'
     '  static std::unique_ptr<plume::RenderPipeline> pipeline;\n'
     '  static bool tried = false;\n'
     '  if (!tried) {\n'
     '    tried = true;\n'
     '    ps = CreateHostShader(s.device.get(), RENUT_HOST_SHADER(exp_scale_ps), "exp_scale_ps");\n'
     '    if (ps && s.present_vs) {\n'
     '      plume::RenderGraphicsPipelineDesc desc;\n'
     '      desc.pipelineLayout = s.utility_layout.get();\n'
     '      desc.vertexShader = s.present_vs.get();\n'
     '      desc.pixelShader = ps.get();\n'
     '      desc.primitiveTopology = plume::RenderPrimitiveTopology::TRIANGLE_LIST;\n'
     '      desc.cullMode = plume::RenderCullMode::NONE;\n'
     '      desc.renderTargetCount = 1;\n'
     '      desc.renderTargetFormat[0] = kFormat;\n'
     '      desc.renderTargetBlend[0] = plume::RenderBlendDesc::Copy();\n'
     '      desc.depthTargetFormat = plume::RenderFormat::UNKNOWN;\n'
     '      pipeline = s.device->createGraphicsPipeline(desc);\n'
     '      if (pipeline)\n'
     '        pipeline->setName("sasrt texture exponent adjust");\n'
     '    }\n'
     '    RGPU_INFO("[sasrt] texture exponent adjust: copy pipeline {}", pipeline ? "ready" : "NOT available");\n'
     '  }\n'
     '  if (!pipeline || source_slot == kInvalidDescriptor || !width || !height || exp_adjust < -31 || exp_adjust > 31)\n'
     '    return kInvalidDescriptor;\n'
     '  struct Copy {\n'
     '    HostTexture target;\n'
     '    std::unique_ptr<plume::RenderFramebuffer> framebuffer;\n'
     '    std::unique_ptr<plume::RenderTextureView> view;\n'
     '    uint32_t slot = kInvalidDescriptor;\n'
     '    uint32_t source = kInvalidDescriptor;  // the slot it was made from last\n'
     '    uint64_t frame = UINT64_MAX;\n'
     '    uint64_t epoch = UINT64_MAX;\n'
     '  };\n'
     '  static std::unordered_map<uint64_t, std::unique_ptr<Copy>> copies;\n'
     '  // One copy per adjust and size, made again from whichever source a bind names (not one per source: the source\'s\n'
     '  // slot changes from frame to frame on deko3d, and a copy per slot grew to 32 FP16 1152x544 images, 160 MB, until\n'
     '  // the image heap ran out in Ryujinx). The draws read each copy in order with its remakes.\n'
     '  const uint64_t key = uint64_t(exp_adjust & 63) << 32 | uint64_t(width) << 16 | height;\n'
     '  auto &entry = copies[key];\n'
     '  if (!entry) {\n'
     '    // Two in practice (this game\'s FXAA); sizes no longer used go after a while.\n'
     '    if (copies.size() > 8) {\n'
     '      for (auto it = copies.begin(); it != copies.end();) {\n'
     '        if (it->second && it->second->frame + 60 < TextureFrameLocked()) {\n'
     '          Copy &old = *it->second;\n'
     '          if (old.slot != kInvalidDescriptor)\n'
     '            Video::FreeTextureSlotLocked(old.slot);\n'
     '          Video::RetireLocked(std::move(old.target.texture));\n'
     '          it = copies.erase(it);\n'
     '        } else {\n'
     '          ++it;\n'
     '        }\n'
     '      }\n'
     '    }\n'
     '    auto copy = std::make_unique<Copy>();\n'
     '    HostTexture &t = copy->target;\n'
     '    plume::RenderTextureDesc desc = plume::RenderTextureDesc::Texture2D(width, height, 1, kFormat);\n'
     '    desc.flags |= plume::RenderTextureFlag::RENDER_TARGET;\n'
     '    t.texture = s.device->createTexture(desc);\n'
     '    if (!t.texture)\n'
     '      return kInvalidDescriptor;\n'
     '    t.texture->setName("sasrt exponent adjust copy");\n'
     '    t.host_format = kFormat;\n'
     '    t.width = t.alloc_width = width;\n'
     '    t.height = t.alloc_height = height;\n'
     '    const plume::RenderTexture *targets[] = {t.texture.get()};\n'
     '    copy->framebuffer = s.device->createFramebuffer(plume::RenderFramebufferDesc(targets, 1));\n'
     '    copy->view = t.texture->createTextureView(plume::RenderTextureViewDesc::Texture2D(kFormat));\n'
     '    if (!copy->framebuffer || !copy->view)\n'
     '      return kInvalidDescriptor;\n'
     '    copy->slot = Video::AllocateTextureSlotLocked();\n'
     '    if (copy->slot == kInvalidDescriptor)\n'
     '      return kInvalidDescriptor;\n'
     '    Video::SetTextureSlotLocked(copy->slot, t.texture.get(), copy->view.get());\n'
     '    static uint32_t logged = 0;\n'
     '    if (logged++ < 8)\n'
     '      RGPU_INFO("[sasrt] texture exponent adjust {}: a {}x{} copy (first from slot {})", exp_adjust, width,\n'
     '                height, source_slot);\n'
     '    entry = std::move(copy);\n'
     '  }\n'
     '  Copy &c = *entry;\n'
     '  if (c.source == source_slot && c.frame == TextureFrameLocked() && c.epoch == g_texture_epoch)\n'
     '    return c.slot;\n'
     '  c.source = source_slot;\n'
     '  c.frame = TextureFrameLocked();\n'
     '  c.epoch = g_texture_epoch;\n'
     '  plume::RenderCommandList *cmd = s.command_list;\n'
     '  TransitionTextureLocked(&c.target, plume::RenderTextureLayout::COLOR_WRITE);\n'
     '  cmd->setFramebuffer(c.framebuffer.get());\n'
     '  cmd->setViewports(plume::RenderViewport(0.0f, 0.0f, float(width), float(height), 0.0f, 1.0f));\n'
     '  cmd->setScissors(plume::RenderRect(0, 0, int32_t(width), int32_t(height)));\n'
     '  cmd->setGraphicsPipelineLayout(s.utility_layout.get());\n'
     '  cmd->setPipeline(pipeline.get());\n'
     '  cmd->setGraphicsDescriptorSet(s.texture_set.get(), 0);\n'
     '  cmd->setGraphicsDescriptorSet(s.sampler_set.get(), 1);\n'
     '  UtilityPush push{};\n'
     '  push.scale[0] = push.scale[1] = 1.0f;\n'
     '  push.texture_index = source_slot;\n'
     '  push.sampler_index = kPointClampSamplerSlot;\n'
     '  push.param0 = std::ldexp(1.0f, exp_adjust);\n'
     '  cmd->setGraphicsPushConstants(0, &push, 0, sizeof(push));\n'
     '  cmd->drawInstanced(3, 1, 0, 0);\n'
     '  TransitionTextureLocked(&c.target, plume::RenderTextureLayout::SHADER_READ);\n'
     '  // The draw path binds its own layout, pipeline, targets and viewport again.\n'
     '  g_bound.framebuffer = nullptr;\n'
     '  g_bound.pipeline = nullptr;\n'
     '  g_bound.layout = false;\n'
     '  g_bound.viewport_set = false;\n'
     '  return c.slot;\n'
     '}\n'
     '\n'
     'bool ResolveDepth(HostSurface *surface, HostTexture *dest, const ClearRect &src, i32 dest_x,\n'
     '                  i32 dest_y, bool words = true) {\n'),
    ('render/draw.cpp',
     '// sasrt-nx (2026-10-20): RestoreDepthFromColorLocked.\n',
     '// sasrt-nx (2026-10-20): ExpAdjustedSlotLocked.\n'
     'REXCVAR_DEFINE_BOOL(sasrt_renut_texture_exp_adjust, true, "SASRT",\n'
     '                    "A texture fetch constant\'s exponent adjust: a fetch with one reads a copy of the texture "\n'
     '                    "times 2^adjust, as the console\'s fetch scales its result (this game\'s FXAA reads its input "\n'
     '                    "with -1 and -2). Off: the adjust is ignored (white outlines on every edge after the FXAA)");\n'
     '// sasrt-nx (2026-10-20): RestoreDepthFromColorLocked.\n'),
]

# The 16-bit fixed-point render targets (2026-10-20): Xenos k_16_16 / k_16_16_16_16 targets are signed fixed point over
# -32..32 (steps of 1/1024), not -1..1. This game draws its 1152x544 HDR scene into k_16_16_16_16 (and resolves it to
# k_16_16_16_16_FLOAT textures, its bloom and average-luminance chain); Renut's R16G16B16A16_SNORM clipped every value
# above 1.0, so the bright pass and the luminance average saw a scene with no highlights and the auto exposure lifted
# the frame into a washed-out white (the track white instead of sand, Sonic's car pale blue). This port's native
# renderer stores them as FP16 (me_formats_color.h); so does Renut's renderer now.
EDITS += [
    ('render/format.cpp',
     '  case GpuColorFormat::Fmt16_16:\n'
     '    return plume::RenderFormat::R16G16_SNORM;\n'
     '  case GpuColorFormat::Fmt16_16_16_16:\n'
     '    return plume::RenderFormat::R16G16B16A16_SNORM;\n',
     '  // sasrt-nx (2026-10-20, sasrt_renut_fixed16_float): Xenos\' 16-bit fixed-point targets span -32..32; FP16 holds\n'
     '  // that range (the game\'s HDR scene), SNORM clipped it at 1.\n'
     '  case GpuColorFormat::Fmt16_16:\n'
     '    return REXCVAR_GET(sasrt_renut_fixed16_float) ? plume::RenderFormat::R16G16_FLOAT\n'
     '                                                  : plume::RenderFormat::R16G16_SNORM;\n'
     '  case GpuColorFormat::Fmt16_16_16_16:\n'
     '    return REXCVAR_GET(sasrt_renut_fixed16_float) ? plume::RenderFormat::R16G16B16A16_FLOAT\n'
     '                                                  : plume::RenderFormat::R16G16B16A16_SNORM;\n'),
    ('render/format.cpp',
     '#include <cstring>\n'
     '\n'
     'namespace renut::gpu {\n',
     '#include <cstring>\n'
     '\n'
     '#include <rex/cvar.h>\n'
     '\n'
     '// sasrt-nx (2026-10-20): ColorTargetFormat.\n'
     'REXCVAR_DEFINE_BOOL(sasrt_renut_fixed16_float, true, "SASRT",\n'
     '                    "Renut\'s renderer: Xenos\' 16-bit fixed-point render targets (k_16_16, k_16_16_16_16; -32..32) "\n'
     '                    "as FP16, as this port\'s native renderer stores them. Off: SNORM, which clips at 1 (this "\n'
     '                    "game\'s HDR scene: no highlights, the auto exposure washes the frame out)")\n'
     '    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\n'
     '\n'
     'namespace renut::gpu {\n'),
]

# The deko3d memory budget (2026-10-20): Renut's QueryGpuMemory reports no budget on deko3d (0), and
# EvictColdTexturesLocked returns at once without one, so banjo_renut_memory_policy never released a texture on the
# Switch: the image heap grew chunk by chunk through a race (512 MB of images, 955 MB of deko3d memory in all) until a
# 64 MB chunk could not be had and deko3d aborted (Ryujinx, 2026-10-20, a race of the native deko3d renderer). A budget
# for what the back end allocates makes the reserve rule work: cold textures go while less than
# banjo_renut_textures_reserve_mb of it is left.
EDITS += [
    ('backend/backend.cpp',
     '    usage.local_used = st.imageBytes + st.bufferBytes + st.codeBytes + st.commandBytes;\n'
     '    usage.local_budget = 0;\n',
     '    usage.local_used = st.imageBytes + st.bufferBytes + st.codeBytes + st.commandBytes;\n'
     '    // sasrt-nx (2026-10-20): a budget, so the texture reserve rule (banjo_renut_memory_policy) can act.\n'
     '    usage.local_budget = uint64_t(REXCVAR_GET(sasrt_renut_deko3d_budget_mb)) << 20;\n'),
    ('backend/backend.cpp',
     'REXCVAR_DEFINE_BOOL(renut_gpu_dred, false, "Nuts&Bolts/Graphics",\n',
     '// sasrt-nx (2026-10-20): QueryGpuMemory on deko3d.\n'
     'REXCVAR_DEFINE_INT32(sasrt_renut_deko3d_budget_mb, 1024, "SASRT",\n'
     '                     "Renut\'s renderer on deko3d: the memory budget (MB) of what the back end allocates (images, "\n'
     '                     "buffers, shader code, command memory), against which banjo_renut_memory_policy releases cold "\n'
     '                     "textures once less than banjo_renut_textures_reserve_mb is left. 0: none (Renut\'s; nothing is "\n'
     '                     "released, and a race filled the image heap until deko3d aborted)")\n'
     '    .range(0, 4096);\n'
     'REXCVAR_DEFINE_BOOL(renut_gpu_dred, false, "Nuts&Bolts/Graphics",\n'),
]

# Diagnostics (2026-10-20): the render targets' generations logged as they are made (the first 96), and
# banjo_renut_diag_show_texture = "g<N>,<M>,..." showing each listed generation in turn, 5 s apiece, so one run (the
# slow Ryujinx one) records several stages of the frame.
EDITS += [
    ('render/surfaces.cpp',
     '  RGPU_DEBUG("Surface {:08X}: {}x{} (x{:.3g} scale) {} format {} x{} samples", surface.guest_va,\n'
     '             surface.width, surface.height, surface.scale.Factor(), surface.depth ? "depth" : "color",\n'
     '             u32(surface.format), u32(surface.samples));\n',
     '  {\n'
     '    static uint32_t logged = 0;  // sasrt-nx (2026-10-20): the generations banjo_renut_diag_show_texture "g<N>" takes\n'
     '    if (logged++ < 96)\n'
     '      RGPU_INFO("[surface] gen {}: {:08X} {}x{} (x{:.3g}) {} format {} x{} samples, ColorInfo {:08X}",\n'
     '                surface.generation, surface.guest_va, surface.width, surface.height, surface.scale.Factor(),\n'
     '                surface.depth ? "depth" : "color", u32(surface.format), u32(surface.samples),\n'
     '                u32(desc.ColorInfo));\n'
     '  }\n'),
    ('backend/present.cpp',
     '  static const u32 generation = [] {  // sasrt-nx (2026-10-20): "g<N>", a render target by generation\n'
     '    const std::string v = REXCVAR_GET(banjo_renut_diag_show_texture);\n'
     '    return !v.empty() && v[0] == \'g\' ? u32(std::strtoul(v.c_str() + 1, nullptr, 10)) : 0u;\n'
     '  }();\n',
     '  // sasrt-nx (2026-10-20): "g<N>", a render target by generation; "g<N>,<M>,...": each in turn, 5 s apiece.\n'
     '  static const std::vector<u32> generations = [] {\n'
     '    std::vector<u32> list;\n'
     '    const std::string v = REXCVAR_GET(banjo_renut_diag_show_texture);\n'
     '    if (!v.empty() && v[0] == \'g\') {\n'
     '      const char *p = v.c_str() + 1;\n'
     '      while (*p) {\n'
     '        char *end = nullptr;\n'
     '        const unsigned long n = std::strtoul(p, &end, 10);\n'
     '        if (end == p)\n'
     '          break;\n'
     '        list.push_back(u32(n));\n'
     '        p = *end == \',\' ? end + 1 : end;\n'
     '      }\n'
     '    }\n'
     '    return list;\n'
     '  }();\n'
     '  static const auto shown_since = std::chrono::steady_clock::now();\n'
     '  const u32 generation =\n'
     '      generations.empty() ? 0u\n'
     '                          : generations[size_t(std::chrono::duration_cast<std::chrono::seconds>(\n'
     '                                                   std::chrono::steady_clock::now() - shown_since)\n'
     '                                                   .count() / 5) %\n'
     '                                       generations.size()];\n'),
]

# New render targets cleared on deko3d (2026-10-20): deko3d images come from memory nobody cleared (banjo-nx's notes;
# Vulkan's and D3D12's come zeroed in practice), so a pass reading a target before anything drew all of it reads
# whatever image lived there before. On the PC every stage of this game's frame was right; on deko3d (Ryujinx) the HDR
# scene was right (banjo_renut_diag_show_texture "g11") while the frame after the post chain came out in bands of false
# colour that changed from run to run. A new colour target is cleared to 0 once, as the PC back ends give it.
EDITS += [
    ('render/surfaces.cpp',
     '                u32(desc.ColorInfo));\n'
     '  }\n'
     '  return true;\n'
     '}\n',
     '                u32(desc.ColorInfo));\n'
     '  }\n'
     '  // sasrt-nx (2026-10-20, sasrt_renut_deko3d_clear_new): a new colour target starts at 0 on deko3d too.\n'
     '  if (IsDeko3D() && !surface.depth && REXCVAR_GET(sasrt_renut_deko3d_clear_new)) {\n'
     '    if (plume::RenderCommandList *cmd = Video::CommandListLocked()) {\n'
     '      HostSurface *self = &surface;\n'
     '      if (plume::RenderFramebuffer *fb = GetFramebufferLocked(&self, 1, nullptr)) {\n'
     '        TransitionSurfaceLocked(self, plume::RenderTextureLayout::COLOR_WRITE);\n'
     '        cmd->setFramebuffer(fb);\n'
     '        cmd->clearColor(0, plume::RenderColor(0.0f, 0.0f, 0.0f, 0.0f));\n'
     '        SasrtForgetBoundTargetsLocked();  // the draw binds its own targets again\n'
     '      }\n'
     '    }\n'
     '  }\n'
     '  return true;\n'
     '}\n'),
    ('render/surfaces.cpp',
     'uint64_t g_surface_write_seq = 0;  // sasrt-nx (2026-10-20)\n',
     'uint64_t g_surface_write_seq = 0;  // sasrt-nx (2026-10-20)\n'),
    ('render/surfaces.cpp',
     'namespace renut::gpu {\n'
     '\n'
     'namespace {\n',
     'namespace renut::gpu {\n'
     '\n'
     'void SasrtForgetBoundTargetsLocked();  // sasrt-nx (2026-10-20): render/draw.cpp\n'
     '\n'
     'namespace {\n'),
    ('render/draw.cpp',
     'bool DrawStateLocked(const u8 *device_state, const DrawCall &call, const ReplayConstants *replay) {\n',
     '// sasrt-nx (2026-10-20): for passes recorded outside the draw path (surfaces.cpp: a new target\'s clear on deko3d).\n'
     'void SasrtForgetBoundTargetsLocked() {\n'
     '  g_bound.framebuffer = nullptr;\n'
     '  g_bound.viewport_set = false;\n'
     '}\n'
     '\n'
     'bool DrawStateLocked(const u8 *device_state, const DrawCall &call, const ReplayConstants *replay) {\n'),
]
EDITS += [
    ('render/surfaces.cpp',
     '    .allowed({"480p", "720p", "1080p", "1440p", "4K"});\n',
     '    .allowed({"480p", "720p", "1080p", "1440p", "4K"});\n'
     '// sasrt-nx (2026-10-20): BuildTarget.\n'
     'REXCVAR_DEFINE_BOOL(sasrt_renut_deko3d_clear_new, true, "SASRT",\n'
     '                    "Renut\'s renderer on deko3d: a new colour render target is cleared to 0 once, as the PC back "\n'
     '                    "ends give it (deko3d images come uncleared: a pass reading what was never drawn read another "\n'
     '                    "image\'s leftovers)");\n'),
]

# A diagnostic (2026-10-20): banjo_renut_diag_show_texture = "p<pixel shader hash>:<slot>[,<slot>...]" shows the textures
# the last draw with that pixel shader bound at those Xenos fetch slots, each in turn (5 s apiece): what a pass read,
# on the console's back end too (deko3d, where RenderDoc cannot reach).
EDITS += [
    ('render/draw.cpp',
     '  std::memcpy(sc.depth_remap, viewport.depth_remap, sizeof(sc.depth_remap));  // sasrt-nx\n',
     '  std::memcpy(sc.depth_remap, viewport.depth_remap, sizeof(sc.depth_remap));  // sasrt-nx\n'
     '  if (ps && ps->entry && g_sasrt_diag_ps_hash && ps->entry->hash == g_sasrt_diag_ps_hash) {  // sasrt-nx: banjo_renut_diag_show_texture "p" (the cache hash, as the pipelines are named)\n'
     '    for (u32 r = 0; r < 32; ++r)\n'
     '      g_sasrt_diag_ps_textures[r] = sc.texture_indices[0][r] & 0x1FFFu;  // the 2D descriptor slot it bound\n'
     '  }\n'),
    ('render/draw.cpp',
     'void SasrtForgetBoundTargetsLocked() {\n',
     '// sasrt-nx (2026-10-20): banjo_renut_diag_show_texture "p<hash>:<slots>" (backend/present.cpp): the texture headers the\n'
     '// last draw with that pixel shader had at each fetch slot.\n'
     'uint64_t g_sasrt_diag_ps_hash = 0;\n'
     'u32 g_sasrt_diag_ps_textures[32] = {};\n'
     '\n'
     'void SasrtForgetBoundTargetsLocked() {\n'),
    ('backend/present.cpp',
     'namespace renut::gpu {\n'
     '\n'
     'namespace {\n',
     'namespace renut::gpu {\n'
     '\n'
     'extern uint64_t g_sasrt_diag_ps_hash;  // sasrt-nx (2026-10-20): render/draw.cpp\n'
     'extern u32 g_sasrt_diag_ps_textures[32];\n'
     '\n'
     'namespace {\n'),
    ('backend/present.cpp',
     'bool DiagTextureImageLocked(PresentImage &out) {\n',
     'bool DiagTextureImageLocked(PresentImage &out) {\n'
     '  // sasrt-nx (2026-10-20): "p<hash>:<slot>,<slot>...": the textures a pixel shader\'s last draw bound there, 5 s apiece.\n'
     '  static const std::vector<u32> ps_slots = [] {\n'
     '    std::vector<u32> list;\n'
     '    const std::string v = REXCVAR_GET(banjo_renut_diag_show_texture);\n'
     '    if (!v.empty() && v[0] == \'p\') {\n'
     '      char *end = nullptr;\n'
     '      g_sasrt_diag_ps_hash = std::strtoull(v.c_str() + 1, &end, 16);\n'
     '      const char *p = end && *end == \':\' ? end + 1 : "";\n'
     '      while (*p) {\n'
     '        char *e = nullptr;\n'
     '        const unsigned long n = std::strtoul(p, &e, 10);\n'
     '        if (e == p)\n'
     '          break;\n'
     '        list.push_back(u32(n) & 31u);\n'
     '        p = *e == \',\' ? e + 1 : e;\n'
     '      }\n'
     '    }\n'
     '    return list;\n'
     '  }();\n'
     '  if (!ps_slots.empty()) {\n'
     '    static const auto since = std::chrono::steady_clock::now();\n'
     '    const u32 slot = ps_slots[size_t(std::chrono::duration_cast<std::chrono::seconds>(\n'
     '                                         std::chrono::steady_clock::now() - since).count() / 5) % ps_slots.size()];\n'
     '    HostTexture *t = g_sasrt_diag_ps_textures[slot] ? FindHostTextureLocked(g_sasrt_diag_ps_textures[slot]) : nullptr;\n'
     '    if (!t || !t->texture || t->slot == UINT32_MAX || t->slot == kInvalidDescriptor ||\n'
     '        t->dimension != TextureDimension::Tex2D || t->stacked)\n'
     '      return false;\n'
     '    out.texture = t->texture.get();\n'
     '    out.layout = &t->layout;\n'
     '    out.descriptor = t->slot;\n'
     '    out.width = t->alloc_width;\n'
     '    out.height = t->alloc_height;\n'
     '    out.gamma = float(REXCVAR_GET(banjo_renut_diag_show_gamma));\n'
     '    return true;\n'
     '  }\n'),
]

# The "p" viewer by descriptor slot (2026-10-20): the textures a pass samples are often resolve destinations reached
# through another header over the same memory, which FindHostTextureLocked (by header address) does not find. The draw
# keeps the descriptor slots it bound, and the viewer finds the host texture that owns the slot.
EDITS += [
    ('render/textures.h',
     'HostTexture *FindHostTextureLocked(u32 texture_va);\n',
     'HostTexture *FindHostTextureLocked(u32 texture_va);\n'
     '// sasrt-nx (2026-10-20, banjo_renut_diag_show_texture "p"): the host texture whose view is at bindless slot \'slot\'\n'
     '// (its own, a swizzle view, level 0, its depth words or a view of them), or nullptr. A diagnostic: a walk of them all.\n'
     'HostTexture *FindHostTextureBySlotLocked(uint32_t slot);\n'),
    ('render/textures.cpp',
     'HostTexture *FindHostTextureLocked(u32 texture_va) {\n',
     'HostTexture *FindHostTextureBySlotLocked(uint32_t slot) {\n'
     '  for (const auto &[va, owned] : g_textures) {\n'
     '    HostTexture *t = owned.get();\n'
     '    if (!t)\n'
     '      continue;\n'
     '    if (t->slot == slot || t->level0_slot == slot)\n'
     '      return t;\n'
     '    for (const auto &v : t->swizzle_views)\n'
     '      if (v.slot == slot)\n'
     '        return t;\n'
     '    if (t->words && t->words->slot == slot)\n'
     '      return t->words.get();\n'
     '    for (const auto &v : t->words_views)\n'
     '      if (v.slot == slot)\n'
     '        return t->words.get() ? t->words.get() : t;\n'
     '  }\n'
     '  return nullptr;\n'
     '}\n'
     '\n'
     'HostTexture *FindHostTextureLocked(u32 texture_va) {\n'),
    ('backend/present.cpp',
     '    HostTexture *t = g_sasrt_diag_ps_textures[slot] ? FindHostTextureLocked(g_sasrt_diag_ps_textures[slot]) : nullptr;\n'
     '    if (!t || !t->texture || t->slot == UINT32_MAX || t->slot == kInvalidDescriptor ||\n'
     '        t->dimension != TextureDimension::Tex2D || t->stacked)\n'
     '      return false;\n'
     '    out.texture = t->texture.get();\n'
     '    out.layout = &t->layout;\n'
     '    out.descriptor = t->slot;\n',
     '    const uint32_t descriptor = g_sasrt_diag_ps_textures[slot];\n'
     '    HostTexture *t = descriptor ? FindHostTextureBySlotLocked(descriptor) : nullptr;\n'
     '    {\n'
     '      static uint32_t logged = 0, last_slot = UINT32_MAX, last_descriptor = UINT32_MAX;\n'
     '      if ((slot != last_slot || descriptor != last_descriptor) && logged++ < 48 && ((last_slot = slot), (last_descriptor = descriptor), true))\n'
     '        RGPU_INFO("[sasrt] diag show: fetch slot {} -> descriptor {} -> {}", slot, descriptor,\n'
     '                  t ? fmt::format("{}x{} format {} guest {:08X}", t->alloc_width, t->alloc_height,\n'
     '                                  int(t->host_format), t->guest_va)\n'
     '                    : std::string("no texture"));\n'
     '    }\n'
     '    if (!t || !t->texture)\n'
     '      return false;\n'
     '    out.texture = t->texture.get();\n'
     '    out.layout = &t->layout;\n'
     '    out.descriptor = descriptor;\n'),
]

# Volume textures as 2D arrays on deko3d (2026-10-20, sasrt_renut_deko3d_volume_as_array): on deko3d alone the frame
# came out of the tonemap pass (ps 2414CA963766CE4E) in bands of false colour, while every input but the 3D colour
# grading LUT checked out on deko3d (banjo_renut_diag_show_texture "p...": the HDR scene, the bloom). A single-level
# volume texture becomes a 2D array of its depth slices there, read with the 3D untiling and copied slice by slice: the
# shaders' stacked path (tfetchStacked: the two layers around the coordinate, filtered between as the volume filter
# says) samples it, through the 2D array view plume's deko3d back end now makes, so no deko3d 3D image is involved.
EDITS += [
    ('render/textures.h',
     '  // the shaders fetch it with 3D fetches (dimension k3D).\n'
     '  bool stacked = false;\n',
     '  // the shaders fetch it with 3D fetches (dimension k3D).\n'
     '  bool stacked = false;\n'
     '  // sasrt-nx (2026-10-20, sasrt_renut_deko3d_volume_as_array): a volume texture held as a stacked 2D array of its\n'
     '  // depth slices (stacked is set too).\n'
     '  bool sasrt_volume_as_array = false;\n'),
    ('render/textures.cpp',
     '#include "renut_engine/gpu/backend/video.h"\n',
     '#include "renut_engine/gpu/backend/video.h"\n'
     '\n'
     '#include <rex/cvar.h>\n'
     '\n'
     '// sasrt-nx (2026-10-20): Create and Upload.\n'
     'REXCVAR_DEFINE_BOOL(sasrt_renut_deko3d_volume_as_array, true, "SASRT",\n'
     '                    "Renut\'s renderer on deko3d: a single-level volume (3D) texture is held as a 2D array of its "\n'
     '                    "slices and sampled through the shaders\' stacked path (this game\'s colour grading LUT), not as "\n'
     '                    "a deko3d 3D image. Off: a 3D image")\n'
     '    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\n'),
    ('render/textures.cpp',
     '  t.stacked = fetch.Dimension() == TextureDimension::Tex2D && fetch.Stacked();\n',
     '  t.stacked = fetch.Dimension() == TextureDimension::Tex2D && fetch.Stacked();\n'
     '  // sasrt-nx (2026-10-20, sasrt_renut_deko3d_volume_as_array): see the key.\n'
     '  t.sasrt_volume_as_array = IsDeko3D() && !render_target && fetch.Dimension() == TextureDimension::Tex3D &&\n'
     '                            t.mip_levels == 1 && t.depth >= 2 && REXCVAR_GET(sasrt_renut_deko3d_volume_as_array);\n'
     '  if (t.sasrt_volume_as_array)\n'
     '    t.stacked = true;\n'),
    ('render/textures.cpp',
     '      if (vulkan && d > 1 && copy_h != blocks_h * bs) {\n',
     '      if (t.sasrt_volume_as_array) {\n'
     '        // sasrt-nx (2026-10-20): each depth slice of the volume into its own array layer.\n'
     '        for (uint32_t z = 0; z < d; ++z) {\n'
     '          cmd->copyTextureRegion(\n'
     '              plume::RenderTextureCopyLocation::Subresource(t.texture.get(), level, z),\n'
     '              plume::RenderTextureCopyLocation::PlacedFootprint(\n'
     '                  staging.ref.ref, t.info.host, copy_w, copy_h, 1, row_texels,\n'
     '                  staging.ref.offset + uint64_t(z) * slice_pitch),\n'
     '              0, 0, 0, nullptr);\n'
     '        }\n'
     '      } else if (vulkan && d > 1 && copy_h != blocks_h * bs) {\n'),
]

# The 16-bit fixed-point targets' range (2026-10-20, sasrt_renut_fixed16_clamp): Xenos k_16_16 / k_16_16_16_16 targets
# store -32..32, so a value a shader writes past it reads back clamped. Held as FP16 (sasrt_renut_fixed16_float), this
# game's HDR scene kept its specular highlights at hundreds and more: the bloom and the average luminance took them in,
# and the frame came out brighter and paler than the emulated Xenos GPU's (the car pale cyan instead of deep blue, the
# track's red patterns salmon, a haze over the scene). Every pass reads that scene through its resolves, so the resolve
# of such a target is drawn with the clamp (shaders/host/resolve_clamp_ps.hlsl, tools/renut_patches/extra), as this
# port's native renderer clamps its outputs (kSpecTargetFixed16).
EDITS += [
    ('gpu.cmake',
     '    renut_host_shader(${TARGET} exp_scale_ps ps_6_0)  # sasrt-nx (2026-10-20): the texture exponent adjust\n',
     '    renut_host_shader(${TARGET} exp_scale_ps ps_6_0)  # sasrt-nx (2026-10-20): the texture exponent adjust\n'
     '    renut_host_shader(${TARGET} resolve_clamp_ps ps_6_0)  # sasrt-nx (2026-10-20): the fixed-point range\n'),
    ('render/draw.cpp',
     '#include "host_shaders/exp_scale_ps.dxil.h"\n'
     '#endif\n',
     '#include "host_shaders/exp_scale_ps.dxil.h"\n'
     '#endif\n'
     '// sasrt-nx (2026-10-20): the fixed-point targets\' resolves (shaders/host/resolve_clamp_ps.hlsl).\n'
     '#include "host_shaders/resolve_clamp_ps.spirv.h"\n'
     '#if defined(PLUME_DEKO3D)\n'
     '#include "host_shaders/resolve_clamp_ps.deko3d.h"\n'
     '#endif\n'
     '#if defined(_WIN32)\n'
     '#include "host_shaders/resolve_clamp_ps.dxil.h"\n'
     '#endif\n'),
    ('render/surfaces.h',
     '  bool depth = false;\n'
     '  plume::RenderFormat format = plume::RenderFormat::UNKNOWN;\n',
     '  bool depth = false;\n'
     '  // sasrt-nx (2026-10-20): a Xenos 16-bit fixed-point colour target (k_16_16, k_16_16_16_16; -32..32).\n'
     '  bool sasrt_fixed16 = false;\n'
     '  plume::RenderFormat format = plume::RenderFormat::UNKNOWN;\n'),
    ('render/surfaces.cpp',
     '  surface.depth = d3d::IsDepthFormat(surface.format_word);\n',
     '  surface.depth = d3d::IsDepthFormat(surface.format_word);\n'
     '  surface.sasrt_fixed16 = !surface.depth && (((u32(desc.ColorInfo) >> 16) & 0xF) == 4u ||\n'
     '                                             ((u32(desc.ColorInfo) >> 16) & 0xF) == 5u);  // sasrt-nx (2026-10-20)\n'),
    ('render/draw.cpp',
     'bool DrawResolveCopy(HostSurface *surface, HostTexture *dest, const plume::RenderRect &rect, uint32_t host_x,\n',
     '// sasrt-nx (2026-10-20, sasrt_renut_fixed16_clamp): a resolve of a 16-bit fixed-point target, drawn with the\n'
     '// console\'s -32..32 (shaders/host/resolve_clamp_ps.hlsl); as DrawResolveCopy otherwise, on every back end.\n'
     'bool ResolveFixed16Locked(HostSurface *surface, HostTexture *dest, const plume::RenderRect &rect, uint32_t host_x,\n'
     '                          uint32_t host_y) {\n'
     '  auto &s = State();\n'
     '  if (!dest->texture || !dest->render_target || dest->host_format != surface->format ||\n'
     '      dest->dimension != TextureDimension::Tex2D || dest->stacked || !s.present_vs)\n'
     '    return false;\n'
     '  static std::unique_ptr<plume::RenderShader> ps;\n'
     '  static bool ps_tried = false;\n'
     '  if (!ps_tried) {\n'
     '    ps_tried = true;\n'
     '    ps = CreateHostShader(s.device.get(), RENUT_HOST_SHADER(resolve_clamp_ps), "resolve_clamp_ps");\n'
     '  }\n'
     '  if (!ps)\n'
     '    return false;\n'
     '  static std::unordered_map<uint32_t, std::unique_ptr<plume::RenderPipeline>> pipelines;\n'
     '  auto &pipeline = pipelines[uint32_t(surface->format)];\n'
     '  if (!pipeline) {\n'
     '    plume::RenderGraphicsPipelineDesc desc;\n'
     '    desc.pipelineLayout = s.utility_layout.get();\n'
     '    desc.vertexShader = s.present_vs.get();\n'
     '    desc.pixelShader = ps.get();\n'
     '    desc.primitiveTopology = plume::RenderPrimitiveTopology::TRIANGLE_LIST;\n'
     '    desc.cullMode = plume::RenderCullMode::NONE;\n'
     '    desc.renderTargetCount = 1;\n'
     '    desc.renderTargetFormat[0] = surface->format;\n'
     '    desc.renderTargetBlend[0] = plume::RenderBlendDesc::Copy();\n'
     '    desc.depthTargetFormat = plume::RenderFormat::UNKNOWN;\n'
     '    pipeline = s.device->createGraphicsPipeline(desc);\n'
     '    if (!pipeline)\n'
     '      return false;\n'
     '    pipeline->setName("sasrt fixed-point resolve");\n'
     '  }\n'
     '  const uint32_t source_slot = SurfaceSampleSlotLocked(surface);\n'
     '  if (source_slot == kInvalidDescriptor)\n'
     '    return false;\n'
     '  if (!dest->copy_framebuffer) {\n'
     '    const plume::RenderTexture *targets[] = {dest->texture.get()};\n'
     '    dest->copy_framebuffer = s.device->createFramebuffer(plume::RenderFramebufferDesc(targets, 1));\n'
     '    if (!dest->copy_framebuffer)\n'
     '      return false;\n'
     '  }\n'
     '  plume::RenderCommandList *cmd = s.command_list;\n'
     '  TransitionSurfaceLocked(surface, plume::RenderTextureLayout::SHADER_READ);\n'
     '  TransitionTextureLocked(dest, plume::RenderTextureLayout::COLOR_WRITE);\n'
     '  cmd->setFramebuffer(dest->copy_framebuffer.get());\n'
     '  cmd->setViewports(plume::RenderViewport(0.0f, 0.0f, float(dest->alloc_width), float(dest->alloc_height)));\n'
     '  cmd->setScissors(plume::RenderRect(int32_t(host_x), int32_t(host_y), int32_t(host_x) + (rect.right - rect.left),\n'
     '                                     int32_t(host_y) + (rect.bottom - rect.top)));\n'
     '  cmd->setGraphicsPipelineLayout(s.utility_layout.get());\n'
     '  cmd->setPipeline(pipeline.get());\n'
     '  cmd->setGraphicsDescriptorSet(s.texture_set.get(), 0);\n'
     '  cmd->setGraphicsDescriptorSet(s.sampler_set.get(), 1);\n'
     '  UtilityPush push{};\n'
     '  push.scale[0] = push.scale[1] = 1.0f;\n'
     '  push.translate[0] = float(rect.left - int32_t(host_x));\n'
     '  push.translate[1] = float(rect.top - int32_t(host_y));\n'
     '  push.texture_index = source_slot;\n'
     '  push.sampler_index = kPointClampSamplerSlot;\n'
     '  cmd->setGraphicsPushConstants(0, &push, 0, sizeof(push));\n'
     '  cmd->drawInstanced(3, 1, 0, 0);\n'
     '  // The draw path binds its own layout, pipeline, targets and viewport again.\n'
     '  g_bound.framebuffer = nullptr;\n'
     '  g_bound.pipeline = nullptr;\n'
     '  g_bound.layout = false;\n'
     '  g_bound.viewport_set = false;\n'
     '  return true;\n'
     '}\n'
     '\n'
     'bool DrawResolveCopy(HostSurface *surface, HostTexture *dest, const plume::RenderRect &rect, uint32_t host_x,\n'),
    ('render/draw.cpp',
     '        } else if (IsDeko3D() && banjo::renut_gpu::DrawResolvesOn() && slice == 0 && z == 0 &&\n',
     '        } else if (surface->sasrt_fixed16 && slice == 0 && z == 0 && REXCVAR_GET(sasrt_renut_fixed16_clamp) &&\n'
     '                   ResolveFixed16Locked(surface, dest, rect, host_x, host_y)) {\n'
     '          // sasrt-nx (2026-10-20): drawn with the fixed-point range.\n'
     '        } else if (IsDeko3D() && banjo::renut_gpu::DrawResolvesOn() && slice == 0 && z == 0 &&\n'),
    ('render/draw.cpp',
     '// sasrt-nx (2026-10-20): ExpAdjustedSlotLocked.\n',
     '// sasrt-nx (2026-10-20): ResolveFixed16Locked.\n'
     'REXCVAR_DEFINE_BOOL(sasrt_renut_fixed16_clamp, true, "SASRT",\n'
     '                    "Renut\'s renderer: a resolve of a 16-bit fixed-point target (k_16_16, k_16_16_16_16, held as "\n'
     '                    "FP16) clamps to -32..32, the range the console stores (this game\'s HDR scene: off, its "\n'
     '                    "highlights feed the bloom and the exposure unclamped and the frame comes out pale and hazy)");\n'
     '// sasrt-nx (2026-10-20): ExpAdjustedSlotLocked.\n'),
]

# The 16-bit fixed-point targets held normalized (2026-10-20, sasrt_renut_fixed16_scale, OFF by default: the emulated
# GPU's exact ROV path blends as Renut does without it, the waterfalls of the menus' islands shown): the emulated GPU's
# host-render-target path (its default) holds k_16_16 / k_16_16_16_16 targets as -1..1 with the shaders' outputs
# divided by 32, so a blend with the source alpha uses alpha/32: the menu's ocean layer (alpha 0.97) tints the cloud
# sea at 3 % there, at 97 % with ROV and in Renut (RenderDoc captures, the same menu frame: every input of the tonemap
# the same but its HDR texture, and in that only the pixels under such blended draws; waterfalls, the race's haze).
# With the key Renut's shaders scale those targets' outputs by 1/32 too (XenosRecomp, shader_common.h g_RtScale),
# their clears with them, and their resolves multiply by 32 (shaders/host/resolve_clamp_ps.hlsl).
EDITS += [
    ('render/draw.cpp',
     '  // (z * [0] + w * [1]); [0] = 0: off. See ComputeViewportSlow.\n'
     '  float depth_remap[2];\n'
     '};\n',
     '  // (z * [0] + w * [1]); [0] = 0: off. See ComputeViewportSlow.\n'
     '  float depth_remap[2];\n'
     '  // 1360, sasrt-nx (2026-10-20): g_RtScale, each colour target\'s output factor (1/32: a 16-bit fixed-point target\n'
     '  // held normalized, sasrt_renut_fixed16_scale; else 1).\n'
     '  float rt_scale[4];\n'
     '};\n'),
    ('render/draw.cpp',
     'static_assert(sizeof(SharedConstants) == 1360);\n',
     'static_assert(offsetof(SharedConstants, rt_scale) == 1360);\n'
     'static_assert(sizeof(SharedConstants) == 1376);\n'),
    ('render/upload_ring.h',
     'constexpr uint32_t kSharedConstantsUboBytes = 1360;',
     'constexpr uint32_t kSharedConstantsUboBytes = 1376;  // sasrt-nx (2026-10-20): + rt_scale;'),
    ('render/draw.cpp',
     '  std::memcpy(sc.depth_remap, viewport.depth_remap, sizeof(sc.depth_remap));  // sasrt-nx\n',
     '  std::memcpy(sc.depth_remap, viewport.depth_remap, sizeof(sc.depth_remap));  // sasrt-nx\n'
     '  {  // sasrt-nx (2026-10-20): g_RtScale (sasrt_renut_fixed16_scale)\n'
     '    const bool scale = REXCVAR_GET(sasrt_renut_fixed16_scale);\n'
     '    for (uint32_t i = 0; i < 4; ++i)\n'
     '      sc.rt_scale[i] = scale && i < targets.color_count && targets.colors[i] && targets.colors[i]->sasrt_fixed16\n'
     '                           ? 1.0f / 32.0f\n'
     '                           : 1.0f;\n'
     '  }\n'),
    ('render/draw.cpp',
     '    t.colors[i]->write_seq = ++g_surface_write_seq;  // sasrt-nx: the EDRAM depth restore\n'
     '    cmd->clearColor(i, clear_color, &host_rect, 1);\n',
     '    t.colors[i]->write_seq = ++g_surface_write_seq;  // sasrt-nx: the EDRAM depth restore\n'
     '    if (t.colors[i]->sasrt_fixed16 && REXCVAR_GET(sasrt_renut_fixed16_scale))  // sasrt-nx: held normalized\n'
     '      cmd->clearColor(i, plume::RenderColor(color[0] / 32.0f, color[1] / 32.0f, color[2] / 32.0f, color[3] / 32.0f),\n'
     '                      &host_rect, 1);\n'
     '    else\n'
     '      cmd->clearColor(i, clear_color, &host_rect, 1);\n'),
    ('render/draw.cpp',
     '    ++alias->writes;  // banjo-nx (banjo_renut_resolve_skip)\n'
     '    cmd->clearColor(0, clear_color, &alias_host, 1);\n',
     '    ++alias->writes;  // banjo-nx (banjo_renut_resolve_skip)\n'
     '    if (alias->sasrt_fixed16 && REXCVAR_GET(sasrt_renut_fixed16_scale))  // sasrt-nx: held normalized\n'
     '      cmd->clearColor(0, plume::RenderColor(color[0] / 32.0f, color[1] / 32.0f, color[2] / 32.0f, color[3] / 32.0f),\n'
     '                      &alias_host, 1);\n'
     '    else\n'
     '      cmd->clearColor(0, clear_color, &alias_host, 1);\n'),
    ('render/draw.cpp',
     '  push.translate[0] = float(rect.left - int32_t(host_x));\n'
     '  push.translate[1] = float(rect.top - int32_t(host_y));\n'
     '  push.texture_index = source_slot;\n'
     '  push.sampler_index = kPointClampSamplerSlot;\n'
     '  cmd->setGraphicsPushConstants(0, &push, 0, sizeof(push));\n'
     '  cmd->drawInstanced(3, 1, 0, 0);\n'
     '  // The draw path binds its own layout, pipeline, targets and viewport again.\n'
     '  g_bound.framebuffer = nullptr;\n'
     '  g_bound.pipeline = nullptr;\n'
     '  g_bound.layout = false;\n'
     '  g_bound.viewport_set = false;\n'
     '  return true;\n'
     '}\n'
     '\n'
     'bool DrawResolveCopy(',
     '  push.translate[0] = float(rect.left - int32_t(host_x));\n'
     '  push.translate[1] = float(rect.top - int32_t(host_y));\n'
     '  push.texture_index = source_slot;\n'
     '  push.sampler_index = kPointClampSamplerSlot;\n'
     '  // sasrt-nx: a target held normalized (sasrt_renut_fixed16_scale) back to its -32..32.\n'
     '  push.param0 = REXCVAR_GET(sasrt_renut_fixed16_scale) ? 32.0f : 1.0f;\n'
     '  cmd->setGraphicsPushConstants(0, &push, 0, sizeof(push));\n'
     '  cmd->drawInstanced(3, 1, 0, 0);\n'
     '  // The draw path binds its own layout, pipeline, targets and viewport again.\n'
     '  g_bound.framebuffer = nullptr;\n'
     '  g_bound.pipeline = nullptr;\n'
     '  g_bound.layout = false;\n'
     '  g_bound.viewport_set = false;\n'
     '  return true;\n'
     '}\n'
     '\n'
     'bool DrawResolveCopy('),
    ('render/draw.cpp',
     '        } else if (surface->sasrt_fixed16 && slice == 0 && z == 0 && REXCVAR_GET(sasrt_renut_fixed16_clamp) &&\n',
     '        } else if (surface->sasrt_fixed16 && slice == 0 && z == 0 &&\n'
     '                   (REXCVAR_GET(sasrt_renut_fixed16_clamp) || REXCVAR_GET(sasrt_renut_fixed16_scale)) &&\n'),
    ('render/draw.cpp',
     '// sasrt-nx (2026-10-20): ResolveFixed16Locked.\n',
     '// sasrt-nx (2026-10-20): SharedConstants::rt_scale, ClearTargets and ResolveFixed16Locked.\n'
     'REXCVAR_DEFINE_BOOL(sasrt_renut_fixed16_scale, false, "SASRT",\n'
     '                    "Renut\'s renderer: a 16-bit fixed-point target (k_16_16, k_16_16_16_16) held as -1..1, its "\n'
     '                    "outputs and clears divided by 32 and its resolves multiplied back, as the emulated GPU\'s fast "\n'
     '                    "path (host render targets) holds it: blends with the source alpha then use alpha/32, which "\n'
     '                    "hides this game\'s waterfalls and thins its haze. Off (the default): blended at -32..32 as the "\n'
     '                    "emulated GPU\'s exact path (render_target_path_d3d12 = rov) does. Needs the shader cache "\n'
     '                    "built with g_RtScale")\n'
     '    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\n'
     '// sasrt-nx (2026-10-20): ResolveFixed16Locked.\n'),
]

# A cube, volume or stacked fetch's scale (2026-10-20, sasrt_renut_texture_exp_adjust and sasrt_renut_texture_int_format):
# ExpAdjustedSlotLocked copies 2D textures scaled, the others had nothing, and the fetch constant's integer number
# format (dword 3 bit 0: a normalized format reads as its integer) nothing anywhere. The race's lighting volume
# (32x8x32 k_16_16_16_16, unsigned, integer, exponent -10) is the one such fetch. The emulated GPU applies the exponent
# adjust to every fetch and reads integer-format textures normalized (its texture cache: "if any game is seen using
# num_format 1 for fixed-point formats, add ... multipliers"), so the integer reading is a key, off: on, the volume
# reads up to 64 and tints the track grey-blue against the emulated GPU's warm beige (A/B of 2026-10-20, video_140s
# against video_142s and the ROV reference video_330s). Those fetches carry their scale as a power of two in their
# descriptor index (bits 20-25, signed; the slot is below bit 13: kTextureDescriptorCount is 8192): the exponent
# adjust, plus 16 (8) for a 16-bit (8-bit) normalized format read as integers with the key (2^16 for 65535: 1.5e-5
# off; 2^8 for 255: 0.4 % off), 15 (7) signed; the shaders scale what they fetch (shader_common.h renutExpScale).
EDITS += [
    ('render/draw.cpp',
     'REXCVAR_DEFINE_BOOL(sasrt_renut_texture_exp_adjust, true, "SASRT",\n',
     '// sasrt-nx (2026-10-20): the descriptor index\'s scale of a 3D, cube or stacked fetch (FillTextures).\n'
     'REXCVAR_DEFINE_BOOL(sasrt_renut_texture_int_format, false, "SASRT",\n'
     '                    "Renut\'s renderer: a 3D, cube or stacked fetch whose fetch constant asks for the integer number "\n'
     '                    "format reads a 16- or 8-bit normalized texture as its integers (0..65535, 0..255). Off (the "\n'
     '                    "default): normalized, as the emulated GPU reads it (on, this game\'s race lighting volume tints "\n'
     '                    "the track grey-blue against the emulated GPU\'s warm beige, both its paths)")\n'
     '    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\n'
     'REXCVAR_DEFINE_BOOL(sasrt_renut_texture_exp_adjust, true, "SASRT",\n'),
    ('render/draw.cpp',
     '    // sasrt-nx (2026-10-20): the fetch constant\'s exponent adjust (ExpAdjustedSlotLocked), 2D fetches.\n'
     '    if (const int exp_adjust = int(i32(fetch.dword[3] << 13) >> 26);\n',
     '    // sasrt-nx (2026-10-20): a 3D, cube or stacked fetch\'s scale as a power of two in the descriptor index (bits\n'
     '    // 20-25, signed; shader_common.h renutExpScale): the fetch constant\'s exponent adjust, plus the range of an\n'
     '    // integer number format (a 16- or 8-bit normalized format read as its integers).\n'
     '    if (dim != 0 || binding.stacked) {\n'
     '      int nd_scale = REXCVAR_GET(sasrt_renut_texture_exp_adjust) ? int(i32(fetch.dword[3] << 13) >> 26) : 0;\n'
     '      if ((fetch.dword[3] & 1u) && REXCVAR_GET(sasrt_renut_texture_int_format)) {\n'
     '        const u32 format = fetch.dword[1] & 63u;\n'
     '        const bool sign = ((fetch.dword[0] >> 2) & 3u) == 1u;  // the first component signed\n'
     '        if (format == 24 || format == 25 || format == 26)  // k_16, k_16_16, k_16_16_16_16\n'
     '          nd_scale += sign ? 15 : 16;\n'
     '        else if (format == 2 || format == 6 || format == 10)  // k_8, k_8_8_8_8, k_8_8\n'
     '          nd_scale += sign ? 7 : 8;\n'
     '      }\n'
     '      nd_scale = std::max(-32, std::min(31, nd_scale));\n'
     '      if (nd_scale != 0) {\n'
     '        static_assert(kTextureDescriptorCount <= (1u << 13), "the slot must stay below bit 13");\n'
     '        index |= u32(nd_scale & 63) << 20;\n'
     '        static int s_logged = 0;\n'
     '        if (s_logged < 4) {\n'
     '          ++s_logged;\n'
     '          u32 w = 0, h = 0, d = 0;\n'
     '          fetch.Size(w, h, d);\n'
     '          RGPU_INFO("[sasrt] texture scale 2^{} in the shader: dim {} stacked {} {}x{}x{} fetch {:08X} {:08X} {:08X} "\n'
     '                    "{:08X}", nd_scale, dim, binding.stacked, w, h, d, fetch.dword[0], fetch.dword[1], fetch.dword[2],\n'
     '                    fetch.dword[3]);\n'
     '        }\n'
     '      }\n'
     '    }\n'
     '    // sasrt-nx (2026-10-20): the fetch constant\'s exponent adjust (ExpAdjustedSlotLocked), 2D fetches.\n'
     '    if (const int exp_adjust = int(i32(fetch.dword[3] << 13) >> 26);\n'),
]

# The fetch constant's gamma and biased signs (2026-10-20, sasrt_renut_texture_signs): Renut took a texture's signs as
# all signed or not (its host format), and read gamma (TextureSign 3: Xenos' piecewise-linear gamma) and unsigned
# biased (TextureSign 2: 2x - 1) components as plain unsigned ones. The descriptor index carries them per result
# component (through the fetch constant's swizzle: bits 16-19 gamma, 13-15 biased X-Z), and the translator wraps every
# texture fetch in shader_common.h's renutSigns, which applies them after filtering as the emulated GPU does.
EDITS += [
    ('render/draw.cpp',
     'REXCVAR_DEFINE_BOOL(sasrt_renut_texture_int_format, false, "SASRT",\n',
     'REXCVAR_DEFINE_BOOL(sasrt_renut_texture_signs, true, "SASRT",\n'
     '                    "Renut\'s renderer: a texture component the fetch constant marks gamma reads through Xenos\' "\n'
     '                    "piecewise-linear gamma to linear, and one marked unsigned biased as 2x - 1, in the shader after "\n'
     '                    "filtering, as the emulated GPU does")\n'
     '    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\n'
     'REXCVAR_DEFINE_BOOL(sasrt_renut_texture_int_format, false, "SASRT",\n'),
    ('render/draw.cpp',
     '    // sasrt-nx (2026-10-20): a 3D, cube or stacked fetch\'s scale as a power of two in the descriptor index (bits\n',
     '    // sasrt-nx (2026-10-20): the fetch constant\'s gamma and biased signs per result component (through its swizzle),\n'
     '    // bits 16-19 gamma, 13-15 biased X-Z (shader_common.h renutSigns): in the texture word, or on deko3d in the\n'
     '    // sampler word (below, after the sampler), whose texture word\'s low 20 bits are the handle\'s image id.\n'
     '    u32 sasrt_sign_flags = 0;\n'
     '    if (REXCVAR_GET(sasrt_renut_texture_signs) && (fetch.dword[0] & 0x3FCu)) {\n'
     '      static_assert(kTextureDescriptorCount <= (1u << 13), "the slot must stay below bit 13");\n'
     '      const u32 swizzle = (fetch.dword[3] >> 1) & 0xFFFu;\n'
     '      u32 gamma = 0, biased = 0;\n'
     '      for (u32 c = 0; c < 4; ++c) {\n'
     '        const u32 source = (swizzle >> (c * 3)) & 7u;\n'
     '        if (source >= 4)\n'
     '          continue;\n'
     '        const TextureSign sign = fetch.Sign(source);\n'
     '        if (sign == TextureSign::Gamma)\n'
     '          gamma |= 1u << c;\n'
     '        else if (sign == TextureSign::Biased && c < 3)\n'
     '          biased |= 1u << c;\n'
     '      }\n'
     '      sasrt_sign_flags = gamma << 16 | biased << 13;\n'
     '      if (!IsDeko3D())\n'
     '        index |= sasrt_sign_flags;\n'
     '      static int s_logged = 0;\n'
     '      if ((gamma | biased) && s_logged < 8) {\n'
     '        ++s_logged;\n'
     '        u32 w = 0, h = 0, d = 0;\n'
     '        fetch.Size(w, h, d);\n'
     '        RGPU_INFO("[sasrt] texture signs in the shader: gamma {:X} biased {:X}: dim {} {}x{}x{} format {} fetch {:08X} "\n'
     '                  "{:08X}", gamma, biased, dim, w, h, d, fetch.dword[1] & 63u, fetch.dword[0], fetch.dword[3]);\n'
     '      }\n'
     '    }\n'
     '    // sasrt-nx (2026-10-20): a 3D, cube or stacked fetch\'s scale as a power of two in the descriptor index (bits\n'),
    ('render/draw.cpp',
     '    sc.texture_indices[dim][r] = index;\n'
     '    sc.sampler_indices[r] = SamplerWord(SamplerSlotLocked(fetch, binding.lod_scale));\n',
     '    sc.texture_indices[dim][r] = index;\n'
     '    sc.sampler_indices[r] = SamplerWord(SamplerSlotLocked(fetch, binding.lod_scale));\n'
     '    if (IsDeko3D())  // sasrt-nx: the signs\' flags (above), below the sampler id\'s bit 20\n'
     '      sc.sampler_indices[r] |= sasrt_sign_flags;\n'),
]

# RenderDoc's device pointer for a Vulkan capture (2026-10-20, a diagnostic for src/sasrt_renderdoc.cpp): with the window
# minimised nothing is presented, and RenderDoc's Vulkan StartFrameCapture(nullptr, nullptr) then fails ("capture ended
# (failed)"); the instance's dispatch pointer (RENDERDOC_DEVICEPOINTER_FROM_VKINSTANCE) names the device.
EDITS += [
    ('backend/backend.cpp',
     '#include <plume_vulkan.h>\n',
     '#include <plume_vulkan.h>\n'
     '#include "renut_engine/gpu/backend/video.h"  // sasrt-nx: SasrtRenderDocDevicePointer\n'),
    ('backend/backend.cpp',
     '    shader->setName(name);\n'
     '  return shader;\n'
     '}\n'
     '\n'
     '} // namespace renut::gpu\n',
     '    shader->setName(name);\n'
     '  return shader;\n'
     '}\n'
     '\n'
     '// sasrt-nx (2026-10-20, a diagnostic): RenderDoc\'s device for StartFrameCapture / EndFrameCapture on Vulkan\n'
     '// (src/sasrt_renderdoc.cpp): the instance\'s dispatch pointer, RENDERDOC_DEVICEPOINTER_FROM_VKINSTANCE. Null on the\n'
     '// other back ends (RenderDoc takes the one device there).\n'
     'void *SasrtRenderDocDevicePointer() {\n'
     '  if (!IsVulkan())\n'
     '    return nullptr;\n'
     '  auto *device = static_cast<plume::VulkanDevice *>(Video::Device());\n'
     '  if (!device || !device->renderInterface || !device->renderInterface->instance)\n'
     '    return nullptr;\n'
     '  return *reinterpret_cast<void **>(device->renderInterface->instance);\n'
     '}\n'
     '\n'
     '} // namespace renut::gpu\n'),
]

# A cap on one frame's upload ring (2026-10-20, sasrt_renut_ring_frame_cap_mb): the ring of a frame slot only grows
# (32 MB chunks) until the slot comes round again, and the console crashed in its first run on hardware while the game
# loaded its menus: a 1.4 s frame without a Swap uploaded about 640 MB, the deko3d blocks reached 988 MB, and the next
# image heap chunk could not be made ("image heap: chunk 4 of 64 MiB", then nothing). Ryujinx spread the same load over
# many slow frames. Now a draw that finds the frame's ring past the cap ends the frame for the renderer first: the list
# goes to the GPU and recording moves to the other slot (detail::SubmitAndAdvance, as a minimised window's present
# does), whose fence is waited and whose ring is reused. At a draw's start nothing of it is in the ring yet.
EDITS += [
    ('render/upload_ring.h',
     '  uint64_t Bytes() const;\n',
     '  uint64_t Bytes() const;\n'
     '  // sasrt-nx (2026-10-20, sasrt_renut_ring_frame_cap_mb): the bytes this frame has used (whole chunks before the\n'
     '  // current one, and the current one up to the next allocation).\n'
     '  uint64_t UsedBytes() const;\n'),
    ('render/upload_ring.cpp',
     'uint64_t UploadRing::Bytes() const {\n',
     'uint64_t UploadRing::UsedBytes() const {\n'
     '  uint64_t bytes = offset_;\n'
     '  for (size_t i = 0; i < current_ && i < chunks_.size(); ++i)\n'
     '    bytes += chunks_[i].size;\n'
     '  return bytes;\n'
     '}\n'
     '\n'
     'uint64_t UploadRing::Bytes() const {\n'),
    ('render/draw.cpp',
     '  if (!Video::EnsureCommandListLocked())\n'
     '    return false;\n'
     '  SyncBound(s);\n'
     '\n'
     '  plume::RenderShader *host_vs = GetHostShader(vs);\n',
     '  // sasrt-nx (2026-10-20, sasrt_renut_ring_frame_cap_mb): a frame past the cap ends here for the renderer (the\n'
     '  // draw has nothing in the ring yet; the per-list state starts again with the next list).\n'
     '  if (const int32_t cap_mb = REXCVAR_GET(sasrt_renut_ring_frame_cap_mb);\n'
     '      cap_mb > 0 && s.list_open && s.uploads[s.frame].UsedBytes() > (uint64_t(cap_mb) << 20)) {\n'
     '    static uint32_t s_logged = 0;\n'
     '    if (s_logged < 8) {\n'
     '      ++s_logged;\n'
     '      RGPU_INFO("[sasrt] frame upload ring past {} MB ({} MB used): the frame ends here for the renderer "\n'
     '                "(sasrt_renut_ring_frame_cap_mb)", cap_mb, s.uploads[s.frame].UsedBytes() >> 20);\n'
     '    }\n'
     '    detail::SubmitAndAdvance(s, nullptr, nullptr);\n'
     '  }\n'
     '  if (!Video::EnsureCommandListLocked())\n'
     '    return false;\n'
     '  SyncBound(s);\n'
     '\n'
     '  plume::RenderShader *host_vs = GetHostShader(vs);\n'),
    ('render/draw.cpp',
     'REXCVAR_DEFINE_BOOL(sasrt_renut_texture_signs, true, "SASRT",\n',
     'REXCVAR_DEFINE_INT32(sasrt_renut_ring_frame_cap_mb, 96, "SASRT",\n'
     '                     "Renut\'s renderer: a frame that has used this many MB of its upload ring ends for the renderer "\n'
     '                     "at its next draw (submitted, recording moves to the other frame slot, whose ring is reused "\n'
     '                     "once the GPU is done with it), so a long frame that uploads a lot (the game\'s menu load: "\n'
     '                     "640 MB in one frame, the console out of GPU memory) cannot grow the ring without bound. 0: off")\n'
     '    .range(0, 4096);\n'
     'REXCVAR_DEFINE_BOOL(sasrt_renut_texture_signs, true, "SASRT",\n'),
]

# A diagnostic (2026-10-20, sasrt_renut_diag_sync_frames): every frame waits for the GPU to finish it before the next
# is recorded, which takes every hazard of work still in flight out (exploding polygons and a black ground on the
# console and on the PC's D3D12, both with slow GPU frames; none on the PC's Vulkan, 3 ms GPU frames).
EDITS += [
    ('backend/present.cpp',
     'REXCVAR_DEFINE_BOOL(banjo_renut_capture_raw, false, "Banjo/Renut",\n',
     'REXCVAR_DEFINE_BOOL(sasrt_renut_diag_sync_frames, false, "SASRT",\n'
     '                    "Diagnostic: each frame waits for the GPU to finish it at its present (no frames in flight). "\n'
     '                    "Slower; tells whether a fault comes from work still running on the GPU");\n'
     'REXCVAR_DEFINE_BOOL(banjo_renut_capture_raw, false, "Banjo/Renut",\n'),
    ('backend/present.cpp',
     '  if (s.swap_framebuffers.empty()) {\n'
     '    // Minimized or failed resize: keep the frame ring moving without a present.\n'
     '    if (s.list_open)\n'
     '      detail::SubmitAndAdvance(s, nullptr, nullptr);\n'
     '    return;\n'
     '  }\n',
     '  if (s.swap_framebuffers.empty()) {\n'
     '    // Minimized or failed resize: keep the frame ring moving without a present.\n'
     '    if (s.list_open)\n'
     '      detail::SubmitAndAdvance(s, nullptr, nullptr);\n'
     '    if (REXCVAR_GET(sasrt_renut_diag_sync_frames))  // sasrt-nx: a diagnostic\n'
     '      detail::WaitAllSubmitted(s);\n'
     '    return;\n'
     '  }\n'),
    ('backend/present.cpp',
     '  detail::SubmitAndAdvance(s, acquire, present_semaphore);\n',
     '  detail::SubmitAndAdvance(s, acquire, present_semaphore);\n'
     '  if (REXCVAR_GET(sasrt_renut_diag_sync_frames))  // sasrt-nx: a diagnostic\n'
     '    detail::WaitAllSubmitted(s);\n'),
]

# Defaults after the refresh to sa2-nx's and banjo-nx's trees of 2026-10-20 evening (the user: take banjo-nx's CPU and
# GPU work). banjo-nx measured these on its console (its message of 2026-10-20): chain reuse and the inline line compare
# cost its render thread more than they saved, and the core layout (sa2-nx's thread pinning at the first Swap) hung the
# first Swap in Ryujinx 4 runs of 12. The narrow delta compare skips a range of device bytes the render thread does not
# read, measured per game (N&B 10880-11775): off until this game's is derived. sa2-nx's MSAA (2x by default there) is an
# enhancement this game never had: the console's GPU is the limit already (25 ms a frame in a race). Eager kicks on, as
# banjo-nx's tomls have them.
EDITS += [
    ('render/surfaces.cpp',
     'REXCVAR_DEFINE_INT32(sa2_renut_msaa, 2, "SA2/Renderer",\n',
     'REXCVAR_DEFINE_INT32(sa2_renut_msaa, 0, "SA2/Renderer",  // sasrt-nx: off (2026-10-20)\n'),
    ('d3d/hooks/device.cpp',
     'REXCVAR_DEFINE_BOOL(sa2_renut_core_layout, true, "SA2/Renderer",\n',
     'REXCVAR_DEFINE_BOOL(sa2_renut_core_layout, false, "SA2/Renderer",  // sasrt-nx: off (banjo-nx\'s measurement)\n'),
    ('render/draw.cpp',
     'REXCVAR_DEFINE_BOOL(sa2_renut_chain_reuse, true, "SA2/Renderer",\n',
     'REXCVAR_DEFINE_BOOL(sa2_renut_chain_reuse, false, "SA2/Renderer",  // sasrt-nx: off (banjo-nx\'s measurement)\n'),
    ('render/draw.cpp',
     'REXCVAR_DEFINE_BOOL(sa2_renut_inline_line_compare, true, "SA2/Renderer",\n',
     'REXCVAR_DEFINE_BOOL(sa2_renut_inline_line_compare, false, "SA2/Renderer",  // sasrt-nx: off (banjo-nx\'s measurement)\n'),
    ('backend/queued.cpp',
     'REXCVAR_DEFINE_BOOL(sa2_renut_snapshot_deltas_narrow, true, "SA2/Renderer",\n',
     'REXCVAR_DEFINE_BOOL(sa2_renut_snapshot_deltas_narrow, false, "SA2/Renderer",  // sasrt-nx: off until derived for this game\n'),
    ('banjo_renut_tuning.cpp',
     'REXCVAR_DEFINE_BOOL(banjo_deko3d_eager_kicks, false, "Banjo/Enhancements",\n',
     'REXCVAR_DEFINE_BOOL(banjo_deko3d_eager_kicks, true, "Banjo/Enhancements",  // sasrt-nx: on, as banjo-nx\'s tomls\n'),
]

# A diagnostic (2026-10-20, sasrt_renut_diag_no_frames_ahead; banjo-nx's split test): the game waits at its Swap until
# the render thread has processed the frame (no frame ahead), while the GPU keeps two frames in flight. With
# sasrt_renut_diag_sync_frames (the GPU waited every frame) the glitches went, but that also held the game back; this
# separates a late read of guest memory by the render thread (clean with this key) from a hazard on the GPU (not).
EDITS += [
    ('backend/render_thread.cpp',
     'REXCVAR_DEFINE_BOOL(sa2_renut_done_notify_waiters, true, "SA2/Renderer",\n',
     'REXCVAR_DEFINE_BOOL(sasrt_renut_diag_no_frames_ahead, false, "SASRT",\n'
     '                    "Diagnostic: the game waits at its Swap until the render thread has processed the frame (no "\n'
     '                    "frame ahead; the GPU still has two in flight): a fault this clears is a late read of guest "\n'
     '                    "memory")\n'
     '    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\n'
     'REXCVAR_DEFINE_BOOL(sa2_renut_done_notify_waiters, true, "SA2/Renderer",\n'),
    ('backend/render_thread.cpp',
     '    return !g_running || g_stopping || g_frames_queued - g_frames_done <= kMaxFramesAhead;\n',
     '    static const uint64_t ahead = REXCVAR_GET(sasrt_renut_diag_no_frames_ahead) ? 0 : kMaxFramesAhead;  // sasrt-nx\n'
     '    return !g_running || g_stopping || g_frames_queued - g_frames_done <= ahead;\n'),
]

# After the refresh to sa2-nx's and banjo-nx's trees of 2026-10-20 evening:
# - the store cards: since 2026-10-21 this port has them too (tools/store_cards.py after the other post-codegen steps,
#   the SDK's card table in the guest window's first MB, the natives' Card in app/src/hot/sasrt_hot_common.h;
#   g_banjo_store_cards in app/src/hot/sasrt_hot_guest.cpp): the memexport write-back marks them as banjo-nx's does.
# - banjo-nx's textures.cpp reads the fetch constant's exponent adjust through TextureFetch::ExpAdjust (its
#   texture_layout.h; sa2-nx's has not got it).
EDITS += [
    ('render/texture_layout.h',
     '  TextureSign Sign(u32 component) const {\n',
     '  // banjo-nx (2026-10-20): the exponent adjust, dword 3 bits 13-18 (signed): the fetch result times 2^adjust.\n'
     '  int ExpAdjust() const { return int32_t(dword[3] << 13) >> 26; }\n'
     '  TextureSign Sign(u32 component) const {\n'),
]

# banjo-nx's count of binds with a fetch exponent adjust (2026-10-20) says Renut does not apply it: banjo-nx's renderer
# does not; this port's does (draw.cpp: ExpAdjustedSlotLocked for 2D, the descriptor index's scale otherwise).
EDITS += [
    ('banjo_renut_tuning.cpp',
     '    REXLOG_WARN("[renut] exponent adjust: {} texture binds with a fetch exponent adjust ({} negative, {} positive), "\n'
     '                "which Renut does not apply (the sampled values are 2^adjust too large or small)", n, neg, pos);\n',
     '    REXLOG_INFO("[renut] exponent adjust: {} texture binds with a fetch exponent adjust ({} negative, {} positive), "\n'
     '                "applied (sasrt-nx: draw.cpp, sasrt_renut_texture_exp_adjust)", n, neg, pos);\n'),
]

# Sonic's body missing from his car in Ryujinx only (2026-10-20, RenderDoc of Ryujinx, docs/deko3d-renderer.md): his
# vertices are GPU-skinned by memexport and reach his draws through stream_convert_cs, which read the export buffer as
# g_Buffers[g_Push.source]. uam addresses an element of a storage buffer array picked at run time through a computed
# constant buffer offset, which Ryujinx's shader translator cannot follow back to a binding: it guessed two unrelated
# constant buffer words as the buffer's address, so every load read 0 and the converted streams stayed zero (his body
# collapsed to a point). The console reads the address itself. Constant indices on deko3d.
EDITS += [
    ('shaders/host/stream_convert_cs.hlsl',
     'uint LoadSource(uint address)\n'
     '{\n'
     '    return g_Buffers[g_Push.source].Load(address);\n'
     '}\n',
     'uint LoadSource(uint address)\n'
     '{\n'
     '#ifdef BANJO_DEKO3D\n'
     '    // sasrt-nx (2026-10-20): constant indices (kFramesInFlight 2 export buffers). uam reaches an element picked at\n'
     '    // run time through a computed constant buffer offset, which Ryujinx cannot trace: its loads read 0 there.\n'
     '    [branch] if (g_Push.source == 0)\n'
     '        return g_Buffers[0].Load(address);\n'
     '    return g_Buffers[1].Load(address);\n'
     '#else\n'
     '    return g_Buffers[g_Push.source].Load(address);\n'
     '#endif\n'
     '}\n'),
]

# sasrt_renut_diag_convert_check (2026-10-20, Sonic missing in Ryujinx): the stream conversions of the draws of one vertex
# shader (hex hash), checked once the GPU has done them: when their frame slot's fence is waited, the export words a job
# read and the words it wrote are logged side by side ([convertcheck]; deko3d only, whose buffers the CPU can read).
EDITS += [
    ('render/draw.cpp',
     'REXCVAR_DEFINE_INT32(sasrt_renut_ring_frame_cap_mb, 96, "SASRT",\n',
     'REXCVAR_DEFINE_STRING(sasrt_renut_diag_convert_check, "", "SASRT",\n'
     '                      "Diagnostic (deko3d): the GPU stream conversions of the draws with this vertex shader (hex "\n'
     '                      "hash), checked when the GPU is done: export words read and words written ([convertcheck])");\n'
     'REXCVAR_DEFINE_INT32(sasrt_renut_ring_frame_cap_mb, 96, "SASRT",\n'),
    ('render/draw.cpp',
     'bool ConvertExportedStreamsLocked(VideoState &s, const GuestDevice &device, const DrawCall &call,\n',
     '// sasrt-nx (2026-10-20, sasrt_renut_diag_convert_check): up to four jobs a frame slot, logged when the slot\'s fence\n'
     '// has been waited (detail::CompleteMemExportsLocked).\n'
     'struct SasrtConvertCheck {\n'
     '  uint64_t vs;\n'
     '  StreamConvertPush push;\n'
     '  const plume::RenderBuffer *dest;\n'
     '  u32 seed[6];  // guest memory at the stream\'s first vertex when the job was recorded (the export\'s seed)\n'
     '};\n'
     'std::vector<SasrtConvertCheck> g_convert_checks[kFramesInFlight];\n'
     '// The jobs\' converted words as the GPU wrote them, copied by the GPU after each recorded dispatch (32 bytes a job).\n'
     'std::unique_ptr<plume::RenderBuffer> g_convert_check_readback[kFramesInFlight];\n'
     '\n'
     'uint64_t SasrtConvertCheckVs() {\n'
     '  static const uint64_t want = [] {\n'
     '    const std::string v = REXCVAR_GET(sasrt_renut_diag_convert_check);\n'
     '    return v.empty() ? 0ull : uint64_t(std::strtoull(v.c_str(), nullptr, 16));\n'
     '  }();\n'
     '  return want;\n'
     '}\n'
     '\n'
     'void SasrtConvertCheckRecord(VideoState &s, uint64_t vs, const StreamConvertPush &push, plume::RenderBuffer *dest,\n'
     '                             const u8 *guest) {\n'
     '  const u32 slot = s.frame;\n'
     '  if (!IsDeko3D() || !SasrtConvertCheckVs() || vs != SasrtConvertCheckVs() || g_convert_checks[slot].size() >= 4)\n'
     '    return;\n'
     '  auto &rb = g_convert_check_readback[slot];\n'
     '  if (!rb) {\n'
     '    rb = s.device->createBuffer(plume::RenderBufferDesc::ReadbackBuffer(512));\n'
     '    if (!rb)\n'
     '      return;\n'
     '  }\n'
     '  SasrtConvertCheck c{vs, push, dest, {}};\n'
     '  if (guest)\n'
     '    std::memcpy(c.seed, guest, sizeof(c.seed));\n'
     '  plume::RenderCommandList *cmd = s.command_list;\n'
     '  cmd->barriers(plume::RenderBarrierStage::COPY, plume::RenderBufferBarrier(dest, plume::RenderBufferAccess::READ));\n'
     '  cmd->copyBufferRegion(plume::RenderBufferReference(rb.get(), g_convert_checks[slot].size() * 64),\n'
     '                        plume::RenderBufferReference(dest, push.dest_offset), 24);\n'
     '  cmd->barriers(plume::RenderBarrierStage::COMPUTE, plume::RenderBufferBarrier(dest, plume::RenderBufferAccess::WRITE));\n'
     '  g_convert_checks[slot].push_back(c);\n'
     '}\n'
     '\n'
     'void SasrtConvertCheckLog(u32 slot) {\n'
     '  auto &checks = g_convert_checks[slot];\n'
     '  if (checks.empty())\n'
     '    return;\n'
     '  static u32 rounds = 0;\n'
     '  auto &s = State();\n'
     '  if (IsDeko3D() && (rounds < 12 || rounds % 30 == 0)) {\n'
     '    auto words = [](const plume::RenderBuffer *b, uint64_t offset, u32 n) {\n'
     '      std::string out;\n'
     '      const u8 *p = b ? static_cast<const u8 *>(const_cast<plume::RenderBuffer *>(b)->map()) : nullptr;\n'
     '      if (!p)\n'
     '        return std::string("(no buffer)");\n'
     '      for (u32 i = 0; i < n; ++i) {\n'
     '        u32 w;\n'
     '        std::memcpy(&w, p + offset + i * 4, 4);\n'
     '        out += fmt::format("{:08X} ", w);\n'
     '      }\n'
     '      return out;\n'
     '    };\n'
     '    for (const SasrtConvertCheck &c : checks) {\n'
     '      const StreamConvertPush &p = c.push;\n'
     '      const plume::RenderBuffer *src = p.source < kFramesInFlight ? s.memexport_buffer[p.source].get() : nullptr;\n'
     '      const plume::RenderBuffer *rb = p.source < kFramesInFlight ? s.memexport_readback[p.source].get() : nullptr;\n'
     '      const bool dest_live = c.dest == s.exported_streams[slot].get();\n'
     '      std::string seed;\n'
     '      for (u32 w : c.seed)\n'
     '        seed += fmt::format("{:08X} ", w);\n'
     '      const u32 k = u32(&c - checks.data());\n'
     '      // seed: guest memory before the export; export: the window as the CPU maps it; readback: the window as the GPU\n'
     '      // copied it after the export draw (FinishMemExportLocked); converted: the stream buffer as the CPU maps it;\n'
     '      // gpu copy: the converted words as the GPU copied them right after the dispatch.\n'
     '      RGPU_INFO("[convertcheck] slot {} vs {:016X}: export slot {} +0x{:X} -> stream +0x{:X}{}, {} vertices, "\n'
     '                "guest stride {} host stride {} words, {} elements (first {:08X} {:08X}): seed {}| export {}| "\n'
     '                "readback {}| converted {}| gpu copy {}| before the dispatch {}",\n'
     '                slot, c.vs, p.source, p.source_offset, p.dest_offset, dest_live ? "" : " (buffer replaced since)",\n'
     '                p.vertices, p.guest_stride_words, p.host_stride_words, p.element_count, p.elements[0],\n'
     '                p.elements[1], seed, words(src, p.source_offset, 6), words(rb, p.source_offset, 6),\n'
     '                dest_live ? words(c.dest, p.dest_offset, 6) : "-", words(g_convert_check_readback[slot].get(), k * 64, 6),\n'
     '                words(g_convert_check_readback[slot].get(), k * 64 + 32, 6));\n'
     '    }\n'
     '  }\n'
     '  ++rounds;\n'
     '  checks.clear();\n'
     '}\n'
     '\n'
     'bool ConvertExportedStreamsLocked(VideoState &s, const GuestDevice &device, const DrawCall &call,\n'),
    ('render/draw.cpp',
     '    cmd->dispatch((job.count * job.src.element_count + 63) / 64, 1, 1);\n',
     '    cmd->dispatch((job.count * job.src.element_count + 63) / 64, 1, 1);\n'
     '    // sasrt-nx: sasrt_renut_diag_convert_check (the stream\'s guest words: the export\'s seed until it completes)\n'
     '    SasrtConvertCheckRecord(s, vs.hash, push, dest, GuestPhysicalPtr<const u8>(\n'
     '        (device.VertexFetchWord(d3d::kFirstVertexFetchIndex + d3d::StreamFetchIndex(job.stream), 0) & ~3u) +\n'
     '        job.first * job.src.stride));\n'),
    ('render/draw.cpp',
     'void CompleteMemExportsLocked(uint32_t slot) {\n'
     '  SlotExports &exports = g_exports[slot];\n',
     'void CompleteMemExportsLocked(uint32_t slot) {\n'
     '  SasrtConvertCheckLog(slot);  // sasrt-nx: sasrt_renut_diag_convert_check (the slot\'s GPU work is done)\n'
     '  SlotExports &exports = g_exports[slot];\n'),
]

# sasrt_renut_diag_convert_check, second stage (2026-10-20 23:55: Ryujinx's GPU copy after the dispatch still reads
# zero while the export window holds the skinned vertices): a checked job's stream words are filled with 5A5A5A5A
# first, and its push constants carry pad 0xD1A60001, for which the shader writes what it sees instead of converting
# (a marker with the element count, the vertex count, the source offset, the source's first word through LoadSource
# and through each export buffer binding). The pattern left = nothing stored; the marker = push constants and stores
# work, and the loads show.
EDITS += [
    # (2026-10-21) the probe sits after the address computation now (thread 0: marker, the first element word through a
    # run-time index, the layout used; thread 5: its vertex, its source offset from the job's, the word it loads).
    ('shaders/host/stream_convert_cs.hlsl',
     '    const uint dst = g_Push.destOffset + (vertex * g_Push.hostStrideWords + hostOffset) * 4;\n',
     '    const uint dst = g_Push.destOffset + (vertex * g_Push.hostStrideWords + hostOffset) * 4;\n'
     '#ifdef BANJO_DEKO3D\n'
     '    // sasrt-nx (2026-10-21, sasrt_renut_diag_convert_check "<hash>:probe"): a checked job reports what the\n'
     '    // conversion computes instead of converting.\n'
     '    if (g_Push.pad == 0xD1A60001u)\n'
     '    {\n'
     '        if (id.x == 0)\n'
     '        {\n'
     '            g_Buffers[kStreamBuffer].Store(g_Push.destOffset, 0xABCD0000u | count);\n'
     '            g_Buffers[kStreamBuffer].Store(g_Push.destOffset + 4, g_Push.elements[(id.x + g_Push.vertices) >> 30].x);\n'
     '            g_Buffers[kStreamBuffer].Store(g_Push.destOffset + 8, layout);\n'
     '        }\n'
     '        if (id.x == 5)\n'
     '        {\n'
     '            g_Buffers[kStreamBuffer].Store(g_Push.destOffset + 12, vertex);\n'
     '            g_Buffers[kStreamBuffer].Store(g_Push.destOffset + 16, src - g_Push.sourceOffset);\n'
     '            g_Buffers[kStreamBuffer].Store(g_Push.destOffset + 20, SwapWord(LoadSource(src), endian));\n'
     '        }\n'
     '        return;\n'
     '    }\n'
     '#endif\n'),
    ('render/draw.cpp',
     'void SasrtConvertCheckLog(u32 slot) {\n',
     '// Whether this job is checked (before its dispatch): its stream words get the 5A5A5A5A pattern first.\n'
     '// (2026-10-21) "<hash>:big": only jobs of 1000 vertices or more (Sonic\'s body is 1361).\n'
     'bool SasrtConvertCheckWants(VideoState &s, uint64_t vs, plume::RenderBuffer *dest, u32 dest_offset, u32 vertices) {\n'
     '  if (!IsDeko3D() || !SasrtConvertCheckVs() || vs != SasrtConvertCheckVs() || g_convert_checks[s.frame].size() >= 4)\n'
     '    return false;\n'
     '  static const bool big = REXCVAR_GET(sasrt_renut_diag_convert_check).find(":big") != std::string::npos;\n'
     '  if (big && vertices < 1000)\n'
     '    return false;\n'
     '  UploadAllocation fill = Video::UploadsLocked().Allocate(24, 256);\n'
     '  if (!fill)\n'
     '    return false;\n'
     '  std::memset(fill.cpu, 0x5A, 24);\n'
     '  plume::RenderCommandList *cmd = s.command_list;\n'
     '  cmd->barriers(plume::RenderBarrierStage::COPY, plume::RenderBufferBarrier(dest, plume::RenderBufferAccess::WRITE));\n'
     '  cmd->copyBufferRegion(plume::RenderBufferReference(dest, dest_offset), fill.ref, 24);\n'
     '  // (2026-10-21) the filled words as the GPU has them before the dispatch, at the job\'s +32 in the readback.\n'
     '  auto &rb = g_convert_check_readback[s.frame];\n'
     '  if (!rb)\n'
     '    rb = s.device->createBuffer(plume::RenderBufferDesc::ReadbackBuffer(512));\n'
     '  if (rb) {\n'
     '    cmd->barriers(plume::RenderBarrierStage::COPY, plume::RenderBufferBarrier(dest, plume::RenderBufferAccess::READ));\n'
     '    cmd->copyBufferRegion(plume::RenderBufferReference(rb.get(), g_convert_checks[s.frame].size() * 64 + 32),\n'
     '                          plume::RenderBufferReference(dest, dest_offset), 24);\n'
     '  }\n'
     '  cmd->barriers(plume::RenderBarrierStage::COMPUTE, plume::RenderBufferBarrier(dest, plume::RenderBufferAccess::WRITE));\n'
     '  return true;\n'
     '}\n'
     '\n'
     'void SasrtConvertCheckLog(u32 slot) {\n'),
    ('render/draw.cpp',
     '    cmd->setComputePushConstants(0, &push, 0, sizeof(push));  // banjo-nx: the size (the record worker copies it)\n'
     '    cmd->dispatch((job.count * job.src.element_count + 63) / 64, 1, 1);\n',
     '    // sasrt-nx: sasrt_renut_diag_convert_check: a checked job is converted as always and its words checked, or with\n'
     '    // "<hash>:probe" reports what the shader sees instead (pad 0xD1A60001).\n'
     '    const bool sasrt_checked = SasrtConvertCheckWants(s, vs.hash, dest, push.dest_offset, push.vertices);\n'
     '    static const bool sasrt_probe =\n'
     '        REXCVAR_GET(sasrt_renut_diag_convert_check).find(":probe") != std::string::npos;\n'
     '    if (sasrt_checked && sasrt_probe)\n'
     '      push.pad = 0xD1A60001u;\n'
     '    cmd->setComputePushConstants(0, &push, 0, sizeof(push));  // banjo-nx: the size (the record worker copies it)\n'
     '    cmd->dispatch((job.count * job.src.element_count + 63) / 64, 1, 1);\n'),
    ('render/draw.cpp',
     '    SasrtConvertCheckRecord(s, vs.hash, push, dest, GuestPhysicalPtr<const u8>(\n',
     '    if (sasrt_checked)\n'
     '    SasrtConvertCheckRecord(s, vs.hash, push, dest, GuestPhysicalPtr<const u8>(\n'),
]

# sasrt_renut_diag_writeback_check (2026-10-20, Sonic missing in Ryujinx): the guest memory an export's write-back filled
# (detail::CompleteMemExportsLocked) compared with what the next export of the same memory finds there (its seed): in
# Ryujinx the seeds read zero although the write-backs held the skinned vertices ([writeback]).
EDITS += [
    ('render/draw.cpp',
     'REXCVAR_DEFINE_STRING(sasrt_renut_diag_convert_check, "", "SASRT",\n',
     'REXCVAR_DEFINE_BOOL(sasrt_renut_diag_writeback_check, false, "SASRT",\n'
     '                    "Diagnostic: the guest memory each memexport write-back filled, compared with what the next "\n'
     '                    "export of that memory finds there ([writeback])");\n'
     'REXCVAR_DEFINE_STRING(sasrt_renut_diag_convert_check, "", "SASRT",\n'),
    ('render/draw.cpp',
     'bool PrepareMemExportLocked(VideoState &s, const MemExportStream *streams, u32 count,\n',
     '// sasrt-nx (2026-10-20, sasrt_renut_diag_writeback_check): the first words of each write-back, by guest address.\n'
     'struct SasrtWriteback {\n'
     '  u32 words[4];\n'
     '};\n'
     'std::unordered_map<u32, SasrtWriteback> g_sasrt_writebacks;\n'
     '\n'
     'bool SasrtWritebackOn() {\n'
     '  static const bool on = REXCVAR_GET(sasrt_renut_diag_writeback_check);\n'
     '  return on;\n'
     '}\n'
     '\n'
     'void SasrtWritebackNote(u32 base, const u8 *written, u32 size) {\n'
     '  if (!SasrtWritebackOn() || size < 16)\n'
     '    return;\n'
     '  if (g_sasrt_writebacks.size() > 4096)\n'
     '    g_sasrt_writebacks.clear();\n'
     '  std::memcpy(g_sasrt_writebacks[base].words, written, 16);\n'
     '}\n'
     '\n'
     'void SasrtWritebackCompare(u32 base, const u8 *guest, u32 size) {\n'
     '  if (!SasrtWritebackOn() || size < 16)\n'
     '    return;\n'
     '  const auto it = g_sasrt_writebacks.find(base);\n'
     '  if (it == g_sasrt_writebacks.end())\n'
     '    return;\n'
     '  static u32 same = 0, differ = 0, logged = 0;\n'
     '  u32 g[4];\n'
     '  std::memcpy(g, guest, 16);\n'
     '  const u32 *w = it->second.words;\n'
     '  const bool equal = std::memcmp(w, g, 16) == 0;\n'
     '  (equal ? same : differ)++;\n'
     '  if (logged < 24 || (same + differ) % 500 == 0) {\n'
     '    ++logged;\n'
     '    RGPU_INFO("[writeback] base {:08X} size {}: wrote {:08X} {:08X} {:08X} {:08X}, the next export finds "\n'
     '              "{:08X} {:08X} {:08X} {:08X} ({}; {} same, {} differ so far)",\n'
     '              base, size, w[0], w[1], w[2], w[3], g[0], g[1], g[2], g[3], equal ? "same" : "DIFFERENT", same, differ);\n'
     '  }\n'
     '}\n'
     '\n'
     'bool PrepareMemExportLocked(VideoState &s, const MemExportStream *streams, u32 count,\n'),
    ('render/draw.cpp',
     '    std::memcpy(seed.cpu, guest, streams[i].size);\n',
     '    SasrtWritebackCompare(streams[i].base, guest, streams[i].size);  // sasrt-nx: sasrt_renut_diag_writeback_check\n'
     '    std::memcpy(seed.cpu, guest, streams[i].size);\n'),
    ('render/draw.cpp',
     '        std::memcpy(guest, data + p.offset, p.size);\n',
     '        std::memcpy(guest, data + p.offset, p.size);\n'
     '        SasrtWritebackNote(p.base, guest, p.size);  // sasrt-nx: sasrt_renut_diag_writeback_check\n'),
]

# The second cause (2026-10-21, Ryujinx run deko44's probe: push constants, loads and stores of stream_convert_cs all
# work, the conversion still writes nothing): the element pair was read as g_Push.elements[element >> 1], a constant
# buffer array indexed at run time; constant indices on deko3d, as LoadSource.
EDITS += [
    ('shaders/host/stream_convert_cs.hlsl',
     '    const uint4 pair = g_Push.elements[element >> 1];\n',
     '#ifdef BANJO_DEKO3D\n'
     '    // sasrt-nx (2026-10-21): constant indices, as LoadSource (Ryujinx).\n'
     '    const uint pairIndex = element >> 1;\n'
     '    uint4 pair = g_Push.elements[0];\n'
     '    [flatten] if (pairIndex == 1) pair = g_Push.elements[1];\n'
     '    [flatten] if (pairIndex == 2) pair = g_Push.elements[2];\n'
     '    [flatten] if (pairIndex == 3) pair = g_Push.elements[3];\n'
     '#else\n'
     '    const uint4 pair = g_Push.elements[element >> 1];\n'
     '#endif\n'),
]

# The cause of the zero streams (2026-10-21, Ryujinx run deko47's probe: push constants, the element words, the vertex,
# the source offset and a load at it are all right in stream_convert_cs, and the pattern a checked job's words were
# filled with is there before its dispatch; the conversion itself still stores zero): the loads in loops. uam advances
# such a load's address from one iteration to the next, which Ryujinx's translator cannot trace to the buffer (its
# loads read 0; the stores, whose base it does find, still land). Unrolled on deko3d: every load at the buffer's base
# plus an offset, as the probe's loads that read right.
EDITS += [
    ('shaders/host/stream_convert_cs.hlsl',
     '        for (uint i = 0; i < words; ++i)\n'
     '            g_Buffers[kStreamBuffer].Store(dst + i * 4, SwapWord(LoadSource(src + i * 4), endian));\n',
     '#ifdef BANJO_DEKO3D\n'
     '        // sasrt-nx (2026-10-21): unrolled (Ryujinx cannot trace a load whose address a loop advances).\n'
     '        [branch] if (words > 0) g_Buffers[kStreamBuffer].Store(dst, SwapWord(LoadSource(src), endian));\n'
     '        [branch] if (words > 1) g_Buffers[kStreamBuffer].Store(dst + 4, SwapWord(LoadSource(src + 4), endian));\n'
     '        [branch] if (words > 2) g_Buffers[kStreamBuffer].Store(dst + 8, SwapWord(LoadSource(src + 8), endian));\n'
     '        [branch] if (words > 3) g_Buffers[kStreamBuffer].Store(dst + 12, SwapWord(LoadSource(src + 12), endian));\n'
     '        [branch] if (words > 4) g_Buffers[kStreamBuffer].Store(dst + 16, SwapWord(LoadSource(src + 16), endian));\n'
     '        [branch] if (words > 5) g_Buffers[kStreamBuffer].Store(dst + 20, SwapWord(LoadSource(src + 20), endian));\n'
     '        [branch] if (words > 6) g_Buffers[kStreamBuffer].Store(dst + 24, SwapWord(LoadSource(src + 24), endian));\n'
     '#else\n'
     '        for (uint i = 0; i < words; ++i)\n'
     '            g_Buffers[kStreamBuffer].Store(dst + i * 4, SwapWord(LoadSource(src + i * 4), endian));\n'
     '#endif\n'),
    ('shaders/host/stream_convert_cs.hlsl',
     '        for (uint i = 0; i < components; ++i)\n'
     '            c[i] = DecodeComponent(i == 0 ? w0 : SwapWord(LoadSource(src + i * 4), endian), 0, 32,\n'
     '                                   isSigned, isInteger);\n',
     '#ifdef BANJO_DEKO3D\n'
     '        // sasrt-nx (2026-10-21): unrolled, as Copy32\'s (Ryujinx).\n'
     '        c[0] = DecodeComponent(w0, 0, 32, isSigned, isInteger);\n'
     '        [branch] if (components > 1)\n'
     '            c[1] = DecodeComponent(SwapWord(LoadSource(src + 4), endian), 0, 32, isSigned, isInteger);\n'
     '        [branch] if (components > 2)\n'
     '            c[2] = DecodeComponent(SwapWord(LoadSource(src + 8), endian), 0, 32, isSigned, isInteger);\n'
     '        [branch] if (components > 3)\n'
     '            c[3] = DecodeComponent(SwapWord(LoadSource(src + 12), endian), 0, 32, isSigned, isInteger);\n'
     '#else\n'
     '        for (uint i = 0; i < components; ++i)\n'
     '            c[i] = DecodeComponent(i == 0 ? w0 : SwapWord(LoadSource(src + i * 4), endian), 0, 32,\n'
     '                                   isSigned, isInteger);\n'
     '#endif\n'),
    ('shaders/host/stream_convert_cs.hlsl',
     '        for (uint i = 0; i < components; ++i)\n'
     '            c[i] = asfloat(i == 0 ? w0 : SwapWord(LoadSource(src + i * 4), endian));\n',
     '#ifdef BANJO_DEKO3D\n'
     '        // sasrt-nx (2026-10-21): unrolled, as Copy32\'s (Ryujinx).\n'
     '        c[0] = asfloat(w0);\n'
     '        [branch] if (components > 1) c[1] = asfloat(SwapWord(LoadSource(src + 4), endian));\n'
     '        [branch] if (components > 2) c[2] = asfloat(SwapWord(LoadSource(src + 8), endian));\n'
     '        [branch] if (components > 3) c[3] = asfloat(SwapWord(LoadSource(src + 12), endian));\n'
     '#else\n'
     '        for (uint i = 0; i < components; ++i)\n'
     '            c[i] = asfloat(i == 0 ? w0 : SwapWord(LoadSource(src + i * 4), endian));\n'
     '#endif\n'),
]

# sasrt_renut_diag_render_delay_ms (2026-10-21, the console's sky and "ocean" glitches): each frame's work on Renut's
# render thread waits this long first, so the PC's render thread lags behind the game as the console's does (about
# 50 ms a frame there), for faults that only show with that lag.
EDITS += [
    ('backend/render_thread.cpp',
     'REXCVAR_DEFINE_BOOL(sasrt_renut_diag_no_frames_ahead, false, "SASRT",\n',
     'REXCVAR_DEFINE_INT32(sasrt_renut_diag_render_delay_ms, 0, "SASRT",\n'
     '                     "Diagnostic: each frame\'s work on Renut\'s render thread waits this long first, so the PC lags "\n'
     '                     "behind the game as the console does (its render thread takes about 50 ms a frame)")\n'
     '    .range(0, 500)\n'
     '    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\n'
     'REXCVAR_DEFINE_BOOL(sasrt_renut_diag_no_frames_ahead, false, "SASRT",\n'),
    ('backend/render_thread.cpp',
     '  QueueUnlocked([work = std::move(work)] {\n'
     '    work();\n',
     '  QueueUnlocked([work = std::move(work)] {\n'
     '    // sasrt-nx: sasrt_renut_diag_render_delay_ms (console-like render thread lag on the PC)\n'
     '    if (static const int32_t delay = REXCVAR_GET(sasrt_renut_diag_render_delay_ms); delay > 0)\n'
     '      std::this_thread::sleep_for(std::chrono::milliseconds(delay));\n'
     '    work();\n'),
]

# The console's sky and "ghost" faults (2026-10-21; reproduced on the PC with sasrt_renut_diag_render_delay_ms, the
# render thread lagging behind the game as on the console): a draw's device is captured when the game makes it, but the
# index buffer it binds is a pointer to the game's D3DIndexBuffer object, which the replay read as it is NOW: a game
# that points one index buffer header at another frame's data (dynamic geometry) before the render thread has drawn
# the draw gave it the next frame's indices (stretched triangles, a sky in pieces). The object (32 bytes) is copied with
# the draw now (with the surface headers: CaptureSurfaces; the recorded command buffers' ops too), and the replay reads
# that copy (SetReplayIndexBufferLocked / ReplayIndexBuffer, render/surfaces.cpp). On the 360 the index buffer's
# address goes into the command stream when the draw is made, so the copy is what the GPU read.
EDITS += [
    ('render/surfaces.h',
     'void SetReplaySurfaceOverridesLocked(const u32 *surface_va, const d3d::SurfaceDesc *desc, u32 count);\n',
     'void SetReplaySurfaceOverridesLocked(const u32 *surface_va, const d3d::SurfaceDesc *desc, u32 count);\n'
     '// sasrt-nx (2026-10-21): the index buffer object the replaying draw bound, as it was when the draw was made (0 /\n'
     '// nullptr: none kept, the object is read as it is now), and the object a draw reads for a bound index buffer.\n'
     'void SetReplayIndexBufferLocked(u32 ib_va, const d3d::IndexBuffer *ib);\n'
     'const d3d::IndexBuffer *ReplayIndexBuffer(u32 ib_va);\n'),
    ('render/surfaces.cpp',
     'void SetReplaySurfaceOverridesLocked(const u32 *surface_va, const d3d::SurfaceDesc *desc, u32 count) {\n',
     '// sasrt-nx (2026-10-21): the replaying draw\'s index buffer object as it was when the draw was made.\n'
     'u32 g_replay_ib_va = 0;\n'
     'd3d::IndexBuffer g_replay_ib{};\n'
     '\n'
     'void SetReplayIndexBufferLocked(u32 ib_va, const d3d::IndexBuffer *ib) {\n'
     '  g_replay_ib_va = ib ? ib_va : 0;\n'
     '  if (g_replay_ib_va)\n'
     '    std::memcpy(&g_replay_ib, ib, sizeof(g_replay_ib));\n'
     '}\n'
     '\n'
     'const d3d::IndexBuffer *ReplayIndexBuffer(u32 ib_va) {\n'
     '  if (ib_va && ib_va == g_replay_ib_va) {\n'
     '    // How often the game had changed the object by the time the draw replayed (what the copy avoids).\n'
     '    static uint64_t replays = 0, changed = 0;\n'
     '    ++replays;\n'
     '    if (const auto *live = GuestPtr<const d3d::IndexBuffer>(ib_va);\n'
     '        live && (live->Address != g_replay_ib.Address || live->Size != g_replay_ib.Size)) {\n'
     '      if (++changed <= 16 || changed % 1000 == 0)\n'
     '        RGPU_INFO("[ib] index buffer {:08X} changed since its draw was made: address {:08X} size {} then, "\n'
     '                  "{:08X} {} now ({} of {} replays)", ib_va, u32(g_replay_ib.Address), u32(g_replay_ib.Size),\n'
     '                  u32(live->Address), u32(live->Size), changed, replays);\n'
     '    }\n'
     '    return &g_replay_ib;\n'
     '  }\n'
     '  return ib_va ? GuestPtr<const d3d::IndexBuffer>(ib_va) : nullptr;\n'
     '}\n'
     '\n'
     'void SetReplaySurfaceOverridesLocked(const u32 *surface_va, const d3d::SurfaceDesc *desc, u32 count) {\n'),
    ('render/draw.cpp',
     'GuestPtr<const d3d::IndexBuffer>(device.U32(d3d::kDeviceOffsetIndexBuffer))',
     'ReplayIndexBuffer(device.U32(d3d::kDeviceOffsetIndexBuffer))'),
    # The queued draws, clears and resolves.
    ('backend/queued.cpp',
     '  d3d::SurfaceDesc surface_desc[5] = {};\n',
     '  d3d::SurfaceDesc surface_desc[5] = {};\n'
     '  u32 ib_va = 0;          // sasrt-nx (2026-10-21): the bound index buffer object, as it was (CaptureSurfaces)\n'
     '  d3d::IndexBuffer ib{};\n'),
    ('backend/queued.cpp',
     '  c->surfaces = 0;\n'
     '  if (!bytes)\n'
     '    return;\n',
     '  c->surfaces = 0;\n'
     '  c->ib_va = 0;\n'
     '  if (!bytes)\n'
     '    return;\n'
     '  // sasrt-nx (2026-10-21): the bound index buffer object too (ReplayIndexBuffer).\n'
     '  if (const u32 ib = u32(*reinterpret_cast<const be_u32 *>(bytes + d3d::kDeviceOffsetIndexBuffer))) {\n'
     '    if (const auto *object = GuestPtr<const d3d::IndexBuffer>(ib)) {\n'
     '      std::memcpy(&c->ib, object, sizeof(c->ib));\n'
     '      c->ib_va = ib;\n'
     '    }\n'
     '  }\n'),
    ('backend/queued.cpp',
     '    SetReplaySurfaceOverridesLocked(capture->surface_va, capture->surface_desc, capture->surfaces);  // sasrt-nx\n',
     '    SetReplaySurfaceOverridesLocked(capture->surface_va, capture->surface_desc, capture->surfaces);  // sasrt-nx\n'
     '    SetReplayIndexBufferLocked(capture->ib_va, &capture->ib);  // sasrt-nx (2026-10-21)\n'),
    ('backend/queued.cpp',
     '    SetReplaySurfaceOverridesLocked(nullptr, nullptr, 0);  // sasrt-nx\n',
     '    SetReplaySurfaceOverridesLocked(nullptr, nullptr, 0);  // sasrt-nx\n'
     '    SetReplayIndexBufferLocked(0, nullptr);  // sasrt-nx (2026-10-21)\n'),
    # The recorded command buffers' ops.
    ('guest/command_buffers.cpp',
     '  d3d::SurfaceDesc surface_desc[5] = {};\n',
     '  d3d::SurfaceDesc surface_desc[5] = {};\n'
     '  u32 ib_va = 0;          // sasrt-nx (2026-10-21): the bound index buffer object as recorded (ReplayIndexBuffer)\n'
     '  d3d::IndexBuffer ib{};\n'),
    ('guest/command_buffers.cpp',
     '    op.surface_desc[op.surfaces] = *desc;\n'
     '    ++op.surfaces;\n'
     '  }\n',
     '    op.surface_desc[op.surfaces] = *desc;\n'
     '    ++op.surfaces;\n'
     '  }\n'
     '  // sasrt-nx (2026-10-21): the bound index buffer object as it is now (ReplayIndexBuffer).\n'
     '  if (const u32 ib = u32(*reinterpret_cast<const be_u32 *>(bytes + d3d::kDeviceOffsetIndexBuffer))) {\n'
     '    if (const auto *object = GuestPtr<const d3d::IndexBuffer>(ib)) {\n'
     '      std::memcpy(&op.ib, object, sizeof(op.ib));\n'
     '      op.ib_va = ib;\n'
     '    }\n'
     '  }\n'),
    ('guest/command_buffers.cpp',
     '    SetReplaySurfaceOverridesLocked(op.surface_va, op.surface_desc, op.surfaces);  // sasrt-nx\n',
     '    SetReplaySurfaceOverridesLocked(op.surface_va, op.surface_desc, op.surfaces);  // sasrt-nx\n'
     '    SetReplayIndexBufferLocked(op.ib_va, &op.ib);  // sasrt-nx (2026-10-21)\n'),
    ('guest/command_buffers.cpp',
     '  SetReplaySurfaceOverridesLocked(nullptr, nullptr, 0);  // sasrt-nx\n}\n',
     '  SetReplaySurfaceOverridesLocked(nullptr, nullptr, 0);  // sasrt-nx\n'
     '  SetReplayIndexBufferLocked(0, nullptr);  // sasrt-nx (2026-10-21)\n}\n'),
]

# sasrt_renut_diag_fence_exports (2026-10-21, the "ocean" frames): a game fence completes when the render thread has read
# the batch (KickFence), but memexport results reach guest memory only once the GPU has finished the frame (at the
# slot's wait); only draws wait for them. On the 360 a fence means the GPU is done, results written. A test: before a
# fence completes, the render thread waits for every pending export and writes it back (slow: a GPU wait at fences).
EDITS += [
    ('render/draw.cpp',
     'void ReleaseCacheCopiesLocked(uint32_t slot) {\n',
     '// sasrt-nx (2026-10-21, sasrt_renut_diag_fence_exports): every pending export in guest memory now.\n'
     'void SasrtFlushAllExportsLocked() {\n'
     '  if (AnyPendingExports())\n'
     '    WaitForExportsLocked((1u << kFramesInFlight) - 1u);\n'
     '}\n'
     '\n'
     'void ReleaseCacheCopiesLocked(uint32_t slot) {\n'),
    ('backend/render_thread.cpp',
     'REXCVAR_DEFINE_INT32(sasrt_renut_diag_render_delay_ms, 0, "SASRT",\n',
     'REXCVAR_DEFINE_BOOL(sasrt_renut_diag_fence_exports, false, "SASRT",\n'
     '                    "Diagnostic: a game fence completes only once every pending memexport result is in guest "\n'
     '                    "memory (the render thread waits for the GPU at fences): the game\'s CPU reads of exported data "\n'
     '                    "then see what the 360 would show it")\n'
     '    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\n'
     'REXCVAR_DEFINE_INT32(sasrt_renut_diag_render_delay_ms, 0, "SASRT",\n'),
    ('backend/render_thread.cpp',
     'void QueueFenceCompletion(u32 completion_va, u32 fence, uint64_t after_callback) {\n'
     '  QueueUnlocked([completion_va, fence, after_callback] {\n',
     'void QueueFenceCompletion(u32 completion_va, u32 fence, uint64_t after_callback) {\n'
     '  QueueUnlocked([completion_va, fence, after_callback] {\n'
     '    // sasrt-nx: sasrt_renut_diag_fence_exports (the exports written back before the game hears of the fence)\n'
     '    if (static const bool exports = REXCVAR_GET(sasrt_renut_diag_fence_exports); exports)\n'
     '      ::renut::gpu::detail::SasrtFlushAllExportsLocked();\n'),
    ('backend/render_thread.cpp',
     'namespace renut::gpu::render_thread {\n',
     'namespace renut::gpu::detail {\n'
     'void SasrtFlushAllExportsLocked();  // sasrt-nx (2026-10-21): render/draw.cpp\n'
     '}  // namespace renut::gpu::detail\n'
     '\n'
     'namespace renut::gpu::render_thread {\n'),
]

# sasrt_renut_diag_trace_window (2026-10-21, the "ocean" frames: two in a row every 126 game frames, on every back end and
# without any lag): banjo_renut_diag_resolve_trace's "[trace]" lines for every frame of a window ("<seconds>,<frames>"),
# numbered, so a normal frame and a flashing one can be compared pass by pass.
EDITS += [
    ('banjo_renut_tuning.cpp',
     'REXCVAR_DEFINE_BOOL(banjo_renut_diag_resolve_trace, false, "Banjo/Diagnostics",\n',
     'REXCVAR_DEFINE_STRING(sasrt_renut_diag_trace_window, "", "SASRT",\n'
     '                      "Diagnostic: banjo_renut_diag_resolve_trace\'s [trace] lines for every frame of a window, "\n'
     '                      "\\"<seconds after start>,<frames>\\" (the key on its own: one frame every 30 s)");\n'
     'REXCVAR_DEFINE_BOOL(banjo_renut_diag_resolve_trace, false, "Banjo/Diagnostics",\n'),
    ('banjo_renut_tuning.cpp',
     '  const auto now = std::chrono::steady_clock::now();\n'
     '  if (g_trace_frame.load(std::memory_order_relaxed)) {\n',
     '  const auto now = std::chrono::steady_clock::now();\n'
     '  // sasrt-nx (2026-10-21): sasrt_renut_diag_trace_window: every frame of the window.\n'
     '  static const auto window = [] {\n'
     '    std::pair<int, int> w{0, 0};\n'
     '    const std::string v = REXCVAR_GET(sasrt_renut_diag_trace_window);\n'
     '    if (const size_t comma = v.find(\',\'); comma != std::string::npos) {\n'
     '      w.first = std::atoi(v.substr(0, comma).c_str());\n'
     '      w.second = std::atoi(v.substr(comma + 1).c_str());\n'
     '    }\n'
     '    return w;\n'
     '  }();\n'
     '  if (window.second > 0) {\n'
     '    static const auto started = now;\n'
     '    static int traced = 0;\n'
     '    if (g_trace_frame.load(std::memory_order_relaxed))\n'
     '      REXLOG_INFO("[trace] frame end");\n'
     '    const bool on = now - started >= std::chrono::seconds(window.first) && traced < window.second;\n'
     '    g_trace_frame.store(on, std::memory_order_relaxed);\n'
     '    if (on)\n'
     '      REXLOG_INFO("[trace] frame start ({} of the window)", ++traced);\n'
     '    return;\n'
     '  }\n'
     '  if (g_trace_frame.load(std::memory_order_relaxed)) {\n'),
]

# The "ocean" frames (2026-10-21, sasrt_renut_diag_trace_window): in the frames that flash, the scene's main pass, the
# one a worker device's recorded command buffer draws (302 draws a frame, behind a 16x16 resolve of the worker's
# surface 4009C8EC), had ONE draw: only the sky, the sea and the far island were left, under the HUD. This game runs its
# recorded buffers by splicing them into a composed buffer (sub_82CEF770) that a later ring submission sends
# (sub_82CDE200); the hooks noted the buffers' addresses at the splice and Renut captured their recordings at the
# submission, by which time a worker could have begun recording the next frame's into the same D3DCommandBuffer
# (BeginRecording clears it): the run replayed that new, nearly empty recording. On the 360 the spliced packets point at
# the recording as it was (its segments stay until the GPU has run them). The recordings are captured at the splice now
# (CaptureCommandBufferRun) and that capture is replayed at the submission (QueueCapturedRun).
EDITS += [
    ('guest/command_buffers.h',
     'void QueueRunCommandBuffer(u32 device_va, u32 command_buffer_va);\n',
     'void QueueRunCommandBuffer(u32 device_va, u32 command_buffer_va);\n'
     '\n'
     '// sasrt-nx (2026-10-21): a buffer\'s recording (and those it runs) as it is now, for a run queued later\n'
     '// (QueueCapturedRun): what a composed command buffer\'s splice points at (sasrt_renut_hooks.cpp).\n'
     'struct CapturedRun;\n'
     'std::shared_ptr<CapturedRun> CaptureCommandBufferRun(u32 command_buffer_va);\n'
     '// QueueRunCommandBuffer with the recording captured before (null: as it is now).\n'
     'void QueueCapturedRun(u32 device_va, u32 command_buffer_va, std::shared_ptr<CapturedRun> captured);\n'),
    ('guest/command_buffers.cpp',
     'void ReleaseCommandBuffer(u32 command_buffer_va) {\n',
     '// sasrt-nx (2026-10-21): recordings captured ahead of their run (command_buffers.h).\n'
     'struct CapturedRun {\n'
     '  BufferSet buffers;\n'
     '};\n'
     '\n'
     'std::shared_ptr<CapturedRun> CaptureCommandBufferRun(u32 command_buffer_va) {\n'
     '  auto captured = std::make_shared<CapturedRun>();\n'
     '  std::lock_guard lock(g_record_mutex);\n'
     '  CaptureBuffers(command_buffer_va, 0, captured->buffers);\n'
     '  return captured;\n'
     '}\n'
     '\n'
     'void QueueCapturedRun(u32 device_va, u32 command_buffer_va, std::shared_ptr<CapturedRun> captured) {\n'
     '  if (!captured) {\n'
     '    QueueRunCommandBuffer(device_va, command_buffer_va);\n'
     '    return;\n'
     '  }\n'
     '  FlushDeferredVertices(device_va);\n'
     '  const u8 *device = GuestPtr<const u8>(device_va);\n'
     '  if (!device)\n'
     '    return;\n'
     '  struct Run {\n'
     '    std::vector<u8> running;  // the running device, whose constants the buffer inherits\n'
     '    std::shared_ptr<CapturedRun> captured;\n'
     '  };\n'
     '  auto run = std::make_shared<Run>();\n'
     '  run->running.assign(device, device + d3d::kDeviceSnapshotSize);\n'
     '  run->captured = std::move(captured);\n'
     '  render_thread::Queue([run, command_buffer_va] {\n'
     '    const u8 *running = run->running.data();\n'
     '    Replay(running, run->captured->buffers, command_buffer_va, 0, Predication(running));\n'
     '  });\n'
     '}\n'
     '\n'
     'void ReleaseCommandBuffer(u32 command_buffer_va) {\n'),
]
EDITS += [
    ('guest/command_buffers.h',
     '#include <rex/types.h>\n',
     '#include <memory>  // sasrt-nx (2026-10-21): CaptureCommandBufferRun\n'
     '\n'
     '#include <rex/types.h>\n'),
]

# The "ocean" frames' cause (2026-10-21): about every 63 frames the game sends a composed command buffer to the GPU by
# writing its indirect-buffer packet into the device's ring (not through sub_82CDE200, which the hooks see), and
# Renut's ring is a sink rewound at every kick without being read: that composed buffer's recorded buffers (a worker's
# scene pass) never ran, and the frame showed the sky and the sea under the HUD. Before a rewind, the ring's words since
# the last one are searched for the segments of composed buffers still waiting (SasrtScanRingForComposed,
# app/src/renut_engine/sasrt_renut_hooks.cpp), whose recorded buffers then run there, in the ring's order.
EDITS += [
    ('d3d/hooks/device.cpp',
     'u32 KickOff_hook(u32 device_va) {\n'
     '  auto *device = GuestPtr<d3d::Device>(device_va);\n'
     '  if (!device)\n'
     '    return 0;\n'
     '  if (!IsRecordingCommandBuffer(device_va)) {\n',
     'u32 KickOff_hook(u32 device_va) {\n'
     '  auto *device = GuestPtr<d3d::Device>(device_va);\n'
     '  if (!device)\n'
     '    return 0;\n'
     '  if (!IsRecordingCommandBuffer(device_va)) {\n'
     '    SasrtScanRing(device_va);  // sasrt-nx (2026-10-21): composed buffers sent through the ring\n'),
    ('d3d/hooks/device.cpp',
     '// PRING CDevice::KickOff() [0x82210AB0]: hand the ring to the GPU. Nothing\n',
     '// sasrt-nx (2026-10-21): the ring\'s words since its last rewind, searched for composed command buffers (their\n'
     '// recorded buffers run here): app/src/renut_engine/sasrt_renut_hooks.cpp.\n'
     'void SasrtScanRing(u32 device_va) {\n'
     '  const native::Device d = native::DeviceAt(device_va);\n'
     '  if (d && g_ring_sink)\n'
     '    ::SasrtScanRingForComposed(device_va, g_ring_sink, d.W(native::off::Ring));\n'
     '}\n'
     '\n'
     '// PRING CDevice::KickOff() [0x82210AB0]: hand the ring to the GPU. Nothing\n'),
    ('d3d/hooks/device.cpp',
     '  if (!IsRecordingCommandBuffer(device_va))\n'
     '    KickDevice(device, device_va);\n'
     '  native::RewindRing(native::DeviceAt(device_va));\n'
     '}\n',
     '  if (!IsRecordingCommandBuffer(device_va)) {\n'
     '    SasrtScanRing(device_va);  // sasrt-nx (2026-10-21)\n'
     '    KickDevice(device, device_va);\n'
     '  }\n'
     '  native::RewindRing(native::DeviceAt(device_va));\n'
     '}\n'),
    ('d3d/hooks/device.cpp',
     '  if (d.W(native::off::Ring) + count * 4 > d.W(native::off::RingLimit))\n'
     '    native::RewindRing(d);\n',
     '  if (d.W(native::off::Ring) + count * 4 > d.W(native::off::RingLimit)) {\n'
     '    if (!IsRecordingCommandBuffer(device_va))\n'
     '      SasrtScanRing(device_va);  // sasrt-nx (2026-10-21)\n'
     '    native::RewindRing(d);\n'
     '  }\n'),
    ('d3d/hooks/device.cpp',
     'u32 g_ring_sink = 0;\n',
     'u32 g_ring_sink = 0;\n'),
]
EDITS += [
    ('d3d/hooks/device.cpp',
     '// Kernel exports the device code uses.\n'
     'REX_IMPORT(__imp__rex_GetCurrentThreadId, GuestGetCurrentThreadId, u32());\n',
     '// sasrt-nx (2026-10-21): composed command buffers sent through the ring (app/src/renut_engine/sasrt_renut_hooks.cpp).\n'
     'void SasrtScanRingForComposed(u32 device_va, u32 begin, u32 end);\n'
     '\n'
     '// Kernel exports the device code uses.\n'
     'REX_IMPORT(__imp__rex_GetCurrentThreadId, GuestGetCurrentThreadId, u32());\n'),
]

# sasrt-nx (2026-10-21, the console's ~217 texture uploads a frame): every 300 frames, the uploads by kind ([sasrt]
# texture uploads), to see which kind the console spends its uploads (and their full barriers) on.
EDITS += [
    ('render/textures.cpp',
     'bool Upload(HostTexture &t, const TextureFetch &fetch, bool defer_read) {\n',
     '// sasrt-nx (2026-10-21): the uploads by kind since the last report (AdvanceTextureFrameLocked).\n'
     'uint64_t g_sasrt_uploads[5] = {};  // first, dynamic, lock-driven, gpu-written, other\n'
     '\n'
     'bool Upload(HostTexture &t, const TextureFetch &fetch, bool defer_read) {\n'
     '  ++g_sasrt_uploads[!t.uploaded ? 0 : t.dynamic ? 1 : t.lock_driven ? 2 : t.gpu_written ? 3 : 4];\n'),
    ('render/textures.cpp',
     'void AdvanceTextureFrameLocked() {\n'
     '  ++g_frame;\n',
     'void AdvanceTextureFrameLocked() {\n'
     '  ++g_frame;\n'
     '  if (g_frame % 300 == 0) {  // sasrt-nx (2026-10-21)\n'
     '    RGPU_INFO("[sasrt] texture uploads in the last 300 frames: {} first, {} dynamic, {} lock-driven, {} over GPU-written "\n'
     '              "memory, {} other (a changed hash)", g_sasrt_uploads[0], g_sasrt_uploads[1], g_sasrt_uploads[2],\n'
     '              g_sasrt_uploads[3], g_sasrt_uploads[4]);\n'
     '    std::memset(g_sasrt_uploads, 0, sizeof(g_sasrt_uploads));\n'
     '  }\n'),
]

# sasrt-nx (2026-10-21, diagnostics): the host textures retired because their header was bound with other data
# (BindTextureLocked): every texture upload in a PC race was a first upload (9-37 new textures a frame).
EDITS += [
    ('render/textures.cpp',
     '                  desc[3], desc[4], desc[5]);\n'
     '    }\n'
     '    Retire(*slot);\n'
     '    slot.reset();\n'
     '  }\n',
     '                  desc[3], desc[4], desc[5]);\n'
     '    }\n'
     '    {  // sasrt-nx (2026-10-21, diagnostics)\n'
     '      static uint32_t logged = 0;\n'
     '      static uint64_t retired = 0;\n'
     '      ++retired;\n'
     '      if (logged++ < 40 || retired % 5000 == 0)\n'
     '        RGPU_INFO("[sasrt] texture {:08X} bound with other data: retired and made again ({} so far; same data {}; "\n'
     '                  "dwords 0 3 4 5 {:08X} {:08X} {:08X} {:08X} -> {:08X} {:08X} {:08X} {:08X})", texture_va, retired,\n'
     '                  SameData(slot->desc, desc), slot->desc[0], slot->desc[3], slot->desc[4], slot->desc[5], desc[0],\n'
     '                  desc[3], desc[4], desc[5]);\n'
     '    }\n'
     '    Retire(*slot);\n'
     '    slot.reset();\n'
     '  }\n'),
]

# sasrt-nx (2026-10-21, sasrt_renut_texture_keep_on_signs): SASRT samples the same texture memory both with gamma signs
# (fetch dword 0 0x..FE) and without (0x..02), through fetch constants set without SetTexture (header-less keys,
# texture_va bit 0). BindTextureLocked compared the whole data description, dword 0's signs included, and retired and
# made the texture again at every such switch: ~1000 retires a second in a PC race, every texture upload a first one
# (9-37 a frame; ~217 a frame on the console). Signs are applied per bind (draw.cpp, sasrt_renut_texture_signs); Create
# only asks whether all four are signed (the format's signed variant). Kept when only the signs differ and both or
# neither are all signed.
EDITS += [
    ('render/textures.cpp',
     '                    "a deko3d 3D image. Off: a 3D image")\n'
     '    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\n',
     '                    "a deko3d 3D image. Off: a 3D image")\n'
     '    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\n'
     'REXCVAR_DEFINE_BOOL(sasrt_renut_texture_keep_on_signs, true, "SASRT",\n'
     '                    "Renut\'s renderer: a texture bound through a fetch constant that differs from the one it was "\n'
     '                    "made with only in the component signs (gamma, biased, unsigned; not all-signed against not) "\n'
     '                    "is kept. The signs are applied when sampling. Off: retired and made and uploaded again (this "\n'
     '                    "game switches one texture between gamma and plain signs many times a frame)");\n'),
    ('render/textures.cpp',
     '         (a[5] & kDimensionMask) == (b[5] & kDimensionMask);\n'
     '}\n',
     '         (a[5] & kDimensionMask) == (b[5] & kDimensionMask);\n'
     '}\n'
     '\n'
     '// sasrt-nx (2026-10-21, sasrt_renut_texture_keep_on_signs): two descriptions that differ only in the component signs\n'
     '// (dword 0 bits 2-9), both or neither all signed (the only part of the signs Create uses: AllSigned).\n'
     'bool SasrtSignsOnly(const u32 a[6], const u32 b[6]) {\n'
     '  constexpr u32 kSigns = 0x3FCu;\n'
     '  if (((a[0] ^ b[0]) & ~kSigns) != 0 || std::memcmp(a + 1, b + 1, 5 * sizeof(u32)) != 0)\n'
     '    return false;\n'
     '  const auto all_signed = [](u32 w) { return (w & kSigns) == 0x154u; };  // TextureSign::Signed (1) in all four\n'
     '  return all_signed(a[0]) == all_signed(b[0]) && REXCVAR_GET(sasrt_renut_texture_keep_on_signs);\n'
     '}\n'),
    ('render/textures.cpp',
     '      !(slot->gpu_written && SameData(slot->desc, desc))) {\n',
     '      !(slot->gpu_written && SameData(slot->desc, desc)) && !SasrtSignsOnly(slot->desc, desc)) {\n'),
]

# sasrt-nx (2026-10-21, diagnostics, sasrt_renut_diag_vertex_formats): what the CPU vertex conversion converts (the
# console's render thread spent 29% in ConvertVertices / ExpandElement in a race).
EDITS += [
    ('render/vertex_format.cpp',
     '#include <arm_neon.h>\n'
     '#endif\n',
     '#include <arm_neon.h>\n'
     '#endif\n'
     '\n'
     '#include <chrono>\n'
     '#include <mutex>\n'
     '#include <string>\n'
     '\n'
     '#include <fmt/format.h>\n'
     '#include <rex/cvar.h>\n'
     '\n'
     'REXCVAR_DEFINE_BOOL(sasrt_renut_diag_vertex_formats, false, "SASRT",\n'
     '                    "Diagnostics: every 10 s, the vertex data Renut\'s renderer converted on the CPU: whole streams "\n'
     '                    "and elements endian-swapped, and elements expanded to floats by format")\n'
     '    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\n'
     '\n'
     'namespace renut::gpu {\n'
     'namespace {\n'
     '\n'
     '// sasrt-nx (2026-10-21, sasrt_renut_diag_vertex_formats).\n'
     'struct SasrtConvertStats {\n'
     '  uint64_t expand_vertices[64][8] = {};  // [format][signed | integer << 1 | native swizzle << 2]\n'
     '  uint64_t copy_bytes = 0, swap_all_bytes = 0, calls = 0;\n'
     '  int64_t next_ms = 0;\n'
     '  std::mutex mutex;\n'
     '};\n'
     'SasrtConvertStats g_sasrt_convert;\n'
     '\n'
     'void SasrtCountConversion(const HostVertexStream &stream, u32 guest_stride, u32 count, bool whole) {\n'
     '  std::lock_guard lock(g_sasrt_convert.mutex);\n'
     '  SasrtConvertStats &s = g_sasrt_convert;\n'
     '  ++s.calls;\n'
     '  if (whole) {\n'
     '    s.swap_all_bytes += uint64_t(count) * guest_stride;\n'
     '  } else {\n'
     '    for (const HostVertexElement &e : stream.elements) {\n'
     '      if (e.conversion != ElementConversion::ExpandFloat) {\n'
     '        s.copy_bytes += uint64_t(count) * e.host_size;\n'
     '        continue;\n'
     '      }\n'
     '      bool native = true;\n'
     '      for (u32 i = 0; i < 4; ++i)\n'
     '        native &= e.type.swizzle[i] == i || e.type.swizzle[i] >= 4;\n'
     '      s.expand_vertices[e.type.format & 63][(e.type.is_signed ? 1 : 0) | (e.type.is_integer ? 2 : 0) |\n'
     '                                            (native ? 4 : 0)] += count;\n'
     '    }\n'
     '  }\n'
     '  const int64_t now = std::chrono::duration_cast<std::chrono::milliseconds>(\n'
     '                          std::chrono::steady_clock::now().time_since_epoch()).count();\n'
     '  if (!s.next_ms)\n'
     '    s.next_ms = now + 10000;\n'
     '  if (now < s.next_ms)\n'
     '    return;\n'
     '  s.next_ms = now + 10000;\n'
     '  std::string text;\n'
     '  for (u32 f = 0; f < 64; ++f) {\n'
     '    for (u32 k = 0; k < 8; ++k) {\n'
     '      if (s.expand_vertices[f][k])\n'
     '        text += fmt::format(" | format {}{}{}{}: {} vertices", f, k & 1 ? " signed" : "", k & 2 ? " integer" : "",\n'
     '                            k & 4 ? "" : " swizzled", s.expand_vertices[f][k]);\n'
     '    }\n'
     '  }\n'
     '  RGPU_INFO("[sasrt] vertex conversion in 10 s: {} calls; whole streams swapped {:.1f} MB, elements swapped "\n'
     '            "{:.1f} MB; expanded to floats{}", s.calls, s.swap_all_bytes / 1048576.0, s.copy_bytes / 1048576.0,\n'
     '            text.empty() ? std::string(": none") : text);\n'
     '  std::memset(s.expand_vertices, 0, sizeof(s.expand_vertices));\n'
     '  s.copy_bytes = s.swap_all_bytes = s.calls = 0;\n'
     '}\n'
     '\n'
     '}  // namespace\n'
     '}  // namespace renut::gpu\n'),
    ('render/vertex_format.cpp',
     '  constexpr u32 kSwapHalves = 3;\n',
     '  constexpr u32 kSwapHalves = 3;\n'
     '  static const bool sasrt_count = REXCVAR_GET(sasrt_renut_diag_vertex_formats);  // sasrt-nx (2026-10-21)\n'
     '  if (sasrt_count)\n'
     '    SasrtCountConversion(stream, guest_stride, vertex_count, copy_only && same_layout);\n'),
]

# sasrt-nx (2026-10-21, sasrt_renut_vertex_expand_tables): SASRT's vertices carry 2_10_10_10 signed normals (and
# UBYTE4 blend indices) that no host vertex format reads (plume has no 10:10:10:2 format; D3D12 no SNORM one): the
# CPU expands them to floats, ~140k vertices a frame in a race, each component through DecodeComponent (branches on
# the type and a float division). The console's render thread spent 29% in ConvertVertices / ExpandElement. The
# components now come from tables DecodeComponent itself filled (the same floats, bit for bit), in a straight loop
# for the XYZW and XYZ1 swizzles. sasrt_renut_diag_vertex_expand_verify compares every expanded vertex with the old
# path.
EDITS += [
    ('render/vertex_format.cpp',
     '// sasrt-nx (2026-10-21, sasrt_renut_diag_vertex_formats).\n',
     'REXCVAR_DEFINE_BOOL(sasrt_renut_vertex_expand_tables, true, "SASRT",\n'
     '                    "Renut\'s renderer: 8-bit and 2_10_10_10 vertex elements the host cannot read (this game\'s "\n'
     '                    "packed normals and blend indices) are expanded to floats from tables of the decoded "\n'
     '                    "components (the same floats), not decoded component by component. Off: the decoder")\n'
     '    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\n'
     'REXCVAR_DEFINE_BOOL(sasrt_renut_test_keep_swapped_halves, false, "SASRT",\n'
     '                    "A test: 16-bit vertex elements whose bound swizzle exchanges each pair (FLOAT16, SHORT) are "\n'
     '                    "given to the shader as the stream\'s 8in32 fetch leaves them, not swapped back on the CPU")\n'
     '    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\n'
     'REXCVAR_DEFINE_BOOL(sasrt_renut_test_ubyte4_reverse, false, "SASRT",\n'
     '                    "A test: unsigned integer 8:8:8:8 vertex elements (UBYTE4 blend indices) expanded with their "\n'
     '                    "components in the other order (w z y x)")\n'
     '    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\n'
     'REXCVAR_DEFINE_BOOL(sasrt_renut_diag_vertex_expand_verify, false, "SASRT",\n'
     '                    "Diagnostics for sasrt_renut_vertex_expand_tables: every vertex expanded from the tables is "\n'
     '                    "expanded again by the decoder and compared (a [sasrt] line per million vertices)")\n'
     '    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\n'
     '\n'
     '// sasrt-nx (2026-10-21, sasrt_renut_diag_vertex_formats).\n'),
    ('render/vertex_format.cpp',
     '// Decodes an element\'s components with the format and endian mode fixed for\n'
     '// the whole loop.',
     '// sasrt-nx (2026-10-21, sasrt_renut_vertex_expand_tables): the decoded components of 8-, 10- and 2-bit fields for\n'
     '// each of signed / integer, filled by DecodeComponent.\n'
     'struct SasrtComponentTables {\n'
     '  float c8[256];\n'
     '  float c10[1024];\n'
     '  float c2[4];\n'
     '};\n'
     '\n'
     'const SasrtComponentTables &SasrtTables(const DeclType &type) {\n'
     '  static const SasrtComponentTables *const tables = [] {\n'
     '    auto *t = new SasrtComponentTables[4];\n'
     '    for (u32 k = 0; k < 4; ++k) {\n'
     '      DeclType d;\n'
     '      d.is_signed = (k & 1) != 0;\n'
     '      d.is_integer = (k & 2) != 0;\n'
     '      for (u32 i = 0; i < 256; ++i)\n'
     '        t[k].c8[i] = DecodeComponent(i, 0, 8, d);\n'
     '      for (u32 i = 0; i < 1024; ++i)\n'
     '        t[k].c10[i] = DecodeComponent(i, 0, 10, d);\n'
     '      for (u32 i = 0; i < 4; ++i)\n'
     '        t[k].c2[i] = DecodeComponent(i, 0, 2, d);\n'
     '    }\n'
     '    return t;\n'
     '  }();\n'
     '  return tables[(type.is_signed ? 1 : 0) | (type.is_integer ? 2 : 0)];\n'
     '}\n'
     '\n'
     'bool SasrtExpandTablesOn() {\n'
     '  static const bool on = REXCVAR_GET(sasrt_renut_vertex_expand_tables);\n'
     '  return on;\n'
     '}\n'
     '\n'
     '// A packed element (one guest word, four components) expanded by \'lookup\' (the word after the endian swap, and\n'
     '// the four components out): ExpandLoop\'s result, with a straight loop for the swizzles XYZW and XYZ1.\n'
     'template <u32 kEndian, typename Lookup>\n'
     'void SasrtExpandPacked(const u8 *src, u32 src_stride, u8 *dst, u32 dst_stride, u32 count, const u8 swizzle[4],\n'
     '                       Lookup lookup) {\n'
     '  u8 pick[4];\n'
     '  for (u32 i = 0; i < 4; ++i)\n'
     '    pick[i] = swizzle[i] < 6 ? swizzle[i] : 4;  // ExpandLoop\'s\n'
     '  const bool xyz = pick[0] == 0 && pick[1] == 1 && pick[2] == 2;\n'
     '  if (xyz && (pick[3] == 3 || pick[3] == 5)) {\n'
     '    const bool one = pick[3] == 5;\n'
     '    for (u32 v = 0; v < count; ++v, src += src_stride, dst += dst_stride) {\n'
     '      float out[4];\n'
     '      lookup(LoadGuestWord<kEndian>(src), out);\n'
     '      if (one)\n'
     '        out[3] = 1.0f;\n'
     '      std::memcpy(dst, out, sizeof(out));\n'
     '    }\n'
     '    return;\n'
     '  }\n'
     '  ExpandLoop(src, src_stride, dst, dst_stride, count, swizzle,\n'
     '             [&](const u8 *p, float c[6]) { lookup(LoadGuestWord<kEndian>(p), c); });\n'
     '}\n'
     '\n'
     '// sasrt_renut_diag_vertex_expand_verify: the vertices expanded again by \'decode\' (ExpandLoop) and compared.\n'
     'template <typename Decode>\n'
     'void SasrtVerifyExpand(const u8 *src, u32 src_stride, const u8 *dst, u32 dst_stride, u32 count,\n'
     '                       const u8 swizzle[4], u32 format, Decode decode) {\n'
     '  static const bool on = REXCVAR_GET(sasrt_renut_diag_vertex_expand_verify);\n'
     '  if (!on || !count)\n'
     '    return;\n'
     '  std::vector<u8> ref(size_t(count) * 16);\n'
     '  ExpandLoop(src, src_stride, ref.data(), 16, count, swizzle, decode);\n'
     '  static std::mutex mutex;\n'
     '  static uint64_t checked = 0, differ = 0, next_report = 1000000;\n'
     '  std::lock_guard lock(mutex);\n'
     '  for (u32 v = 0; v < count; ++v) {\n'
     '    if (std::memcmp(ref.data() + size_t(v) * 16, dst + size_t(v) * dst_stride, 16) != 0 && differ++ < 16) {\n'
     '      float a[4], b[4];\n'
     '      std::memcpy(a, ref.data() + size_t(v) * 16, 16);\n'
     '      std::memcpy(b, dst + size_t(v) * dst_stride, 16);\n'
     '      RGPU_WARN("[sasrt] vertex expand tables: format {} vertex differs: {} {} {} {} (decoder) vs {} {} {} {}",\n'
     '                format, a[0], a[1], a[2], a[3], b[0], b[1], b[2], b[3]);\n'
     '    }\n'
     '  }\n'
     '  checked += count;\n'
     '  if (checked >= next_report) {\n'
     '    next_report = checked + 1000000;\n'
     '    RGPU_INFO("[sasrt] vertex expand tables verify: {} vertices compared, {} differ", checked, differ);\n'
     '  }\n'
     '}\n'
     '\n'
     '// Decodes an element\'s components with the format and endian mode fixed for\n'
     '// the whole loop.'),
    ('render/vertex_format.cpp',
     '  case k8_8_8_8:\n'
     '    expand([&](const u8 *p, float c[6]) {\n'
     '      const u32 w = word(p, 0);\n'
     '      for (u32 i = 0; i < 4; ++i)\n'
     '        c[i] = DecodeComponent(w, i * 8, 8, type);\n'
     '    });\n'
     '    break;\n'
     '  case k2_10_10_10:\n'
     '    expand([&](const u8 *p, float c[6]) {\n'
     '      const u32 w = word(p, 0);\n'
     '      c[0] = DecodeComponent(w, 0, 10, type);\n'
     '      c[1] = DecodeComponent(w, 10, 10, type);\n'
     '      c[2] = DecodeComponent(w, 20, 10, type);\n'
     '      c[3] = DecodeComponent(w, 30, 2, type);\n'
     '    });\n'
     '    break;\n',
     '  case k8_8_8_8: {\n'
     '    const auto decode = [&](const u8 *p, float c[6]) {\n'
     '      const u32 w = word(p, 0);\n'
     '      for (u32 i = 0; i < 4; ++i)\n'
     '        c[i] = DecodeComponent(w, i * 8, 8, type);\n'
     '    };\n'
     '    static const bool sasrt_ubyte4_reverse = REXCVAR_GET(sasrt_renut_test_ubyte4_reverse);  // sasrt-nx (a test)\n'
     '    if (SasrtExpandTablesOn() && sasrt_ubyte4_reverse && type.is_integer && !type.is_signed) {\n'
     '      const float *c8 = SasrtTables(type).c8;\n'
     '      SasrtExpandPacked<kEndian>(src, src_stride, dst, dst_stride, count, type.swizzle, [c8](u32 w, float *c) {\n'
     '        c[0] = c8[w >> 24];  // w z y x\n'
     '        c[1] = c8[(w >> 16) & 0xFFu];\n'
     '        c[2] = c8[(w >> 8) & 0xFFu];\n'
     '        c[3] = c8[w & 0xFFu];\n'
     '      });\n'
     '    } else if (SasrtExpandTablesOn()) {  // sasrt-nx (2026-10-21, sasrt_renut_vertex_expand_tables)\n'
     '      const float *c8 = SasrtTables(type).c8;\n'
     '      SasrtExpandPacked<kEndian>(src, src_stride, dst, dst_stride, count, type.swizzle, [c8](u32 w, float *c) {\n'
     '        c[0] = c8[w & 0xFFu];\n'
     '        c[1] = c8[(w >> 8) & 0xFFu];\n'
     '        c[2] = c8[(w >> 16) & 0xFFu];\n'
     '        c[3] = c8[w >> 24];\n'
     '      });\n'
     '      SasrtVerifyExpand(src, src_stride, dst, dst_stride, count, type.swizzle, type.format, decode);\n'
     '    } else {\n'
     '      expand(decode);\n'
     '    }\n'
     '    break;\n'
     '  }\n'
     '  case k2_10_10_10: {\n'
     '    const auto decode = [&](const u8 *p, float c[6]) {\n'
     '      const u32 w = word(p, 0);\n'
     '      c[0] = DecodeComponent(w, 0, 10, type);\n'
     '      c[1] = DecodeComponent(w, 10, 10, type);\n'
     '      c[2] = DecodeComponent(w, 20, 10, type);\n'
     '      c[3] = DecodeComponent(w, 30, 2, type);\n'
     '    };\n'
     '    if (SasrtExpandTablesOn()) {  // sasrt-nx (2026-10-21, sasrt_renut_vertex_expand_tables)\n'
     '      const SasrtComponentTables &t = SasrtTables(type);\n'
     '      const float *c10 = t.c10, *c2 = t.c2;\n'
     '      SasrtExpandPacked<kEndian>(src, src_stride, dst, dst_stride, count, type.swizzle,\n'
     '                                 [c10, c2](u32 w, float *c) {\n'
     '                                   c[0] = c10[w & 0x3FFu];\n'
     '                                   c[1] = c10[(w >> 10) & 0x3FFu];\n'
     '                                   c[2] = c10[(w >> 20) & 0x3FFu];\n'
     '                                   c[3] = c2[w >> 30];\n'
     '                                 });\n'
     '      SasrtVerifyExpand(src, src_stride, dst, dst_stride, count, type.swizzle, type.format, decode);\n'
     '    } else {\n'
     '      expand(decode);\n'
     '    }\n'
     '    break;\n'
     '  }\n'),
]

# sasrt-nx (2026-10-21, sasrt_renut_stream_cache_follow): on the Switch banjo_renut_memory_policy holds the converted
# stream cache (vertex streams and index ranges) to 128 MB, which the console's log showed full from the first race on
# (the PC's race fills ~490 MB). Full, the cache only lost copies idle for 20 s, so the geometry of the track ahead was
# never cached: converted on every draw, and hashed at every flush by TrackConvertedStream / TrackIndices only for the
# copy to be refused for room (the console's render thread: 27% PmullHash, 29% vertex conversion). Now a stream or
# range that has no room is not hashed, and while the cache is full, copies no draw read in the last 60 frames go at
# the 60-frame cleanup: the cache follows what is drawn.
EDITS += [
    ('render/draw.cpp',
     'REXCVAR_DEFINE_BOOL(sasrt_renut_texture_signs, true, "SASRT",\n',
     'REXCVAR_DEFINE_BOOL(sasrt_renut_stream_cache_follow, true, "SASRT",\n'
     '                    "Renut\'s renderer: when the converted stream cache (vertex streams, index ranges) is full, "\n'
     '                    "a stream that has no room is not hashed for it, and copies no draw read in the last 60 "\n'
     '                    "frames go, so the cache holds what is drawn now (the console\'s 128 MB filled in the first "\n'
     '                    "race). Off: full, it keeps its copies until they are idle banjo_renut_stream_cache_idle_s")\n'
     '    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\n'
     'REXCVAR_DEFINE_BOOL(sasrt_renut_texture_signs, true, "SASRT",\n'),
    ('render/draw.cpp',
     'uint64_t g_stream_cache_bytes = 0;\n',
     'uint64_t g_stream_cache_bytes = 0;\n'
     '// sasrt-nx (2026-10-21, sasrt_renut_stream_cache_follow): the cache was full since the last cleanup; what it refused.\n'
     'bool g_sasrt_cache_full = false;\n'
     'uint64_t g_sasrt_cache_refused = 0, g_sasrt_cache_refused_bytes = 0;\n'
     'bool SasrtCacheFollowOn() {\n'
     '  static const bool on = REXCVAR_GET(sasrt_renut_stream_cache_follow);\n'
     '  return on;\n'
     '}\n'
     '// True (and the refusal counted) when a copy of \'bytes\' has no room in the cache.\n'
     'bool SasrtCacheNoRoom(uint64_t bytes);\n'),
    ('render/draw.cpp',
     '  if (c.dynamic || c.copy)\n'
     '    return;\n'
     '  const uint64_t hash = HashGuestStream(f.key);\n',
     '  if (c.dynamic || c.copy)\n'
     '    return;\n'
     '  if (SasrtCacheNoRoom(uint64_t(f.count) * f.stream.host_stride))  // sasrt-nx: sasrt_renut_stream_cache_follow\n'
     '    return;\n'
     '  const uint64_t hash = HashGuestStream(f.key);\n'),
    ('render/draw.cpp',
     '  c.checked_frame = g_stream_cache_frame;\n'
     '  const uint64_t hash = HashIndices(key);\n',
     '  c.checked_frame = g_stream_cache_frame;\n'
     '  if (SasrtCacheNoRoom(uint64_t(g_indices.size()) * (max_index > 0xFFFE ? 4 : 2)))  // sasrt-nx\n'
     '    return;\n'
     '  const uint64_t hash = HashIndices(key);\n'),
    ('render/draw.cpp',
     '    DropCachedIndices(entry.second);\n'
     '    return true;\n'
     '  });\n'
     '}\n',
     '    DropCachedIndices(entry.second);\n'
     '    return true;\n'
     '  });\n'
     '  // sasrt-nx (2026-10-21, sasrt_renut_stream_cache_follow): full since the last cleanup: the copies no draw read in\n'
     '  // the last 60 frames go (their entries with them: a stream drawn again starts counting its stable flushes anew).\n'
     '  if (SasrtCacheFollowOn() && g_sasrt_cache_full) {\n'
     '    constexpr uint64_t kRecentFrames = 60;\n'
     '    const uint64_t before = g_stream_cache_bytes;\n'
     '    size_t dropped = 0;\n'
     '    std::erase_if(g_stream_cache, [&dropped](auto &entry) {\n'
     '      if (!entry.second.copy || g_stream_cache_frame - entry.second.last_used < kRecentFrames)\n'
     '        return false;\n'
     '      DropCachedCopy(entry.second);\n'
     '      ++dropped;\n'
     '      return true;\n'
     '    });\n'
     '    std::erase_if(g_index_cache, [&dropped](auto &entry) {\n'
     '      if (!entry.second.copy || g_stream_cache_frame - entry.second.last_used < kRecentFrames)\n'
     '        return false;\n'
     '      DropCachedIndices(entry.second);\n'
     '      ++dropped;\n'
     '      return true;\n'
     '    });\n'
     '    static uint32_t logged = 0;\n'
     '    if (logged++ < 12 || logged % 50 == 0)\n'
     '      RGPU_INFO("[sasrt] stream cache full (sasrt_renut_stream_cache_follow): {} copies refused ({:.1f} MB) since "\n'
     '                "the last cleanup; {} copies not drawn in {} frames dropped ({:.1f} MB), {:.1f} MB held",\n'
     '                g_sasrt_cache_refused, g_sasrt_cache_refused_bytes / 1048576.0, dropped, kRecentFrames,\n'
     '                (before - g_stream_cache_bytes) / 1048576.0, g_stream_cache_bytes / 1048576.0);\n'
     '    g_sasrt_cache_full = false;\n'
     '    g_sasrt_cache_refused = g_sasrt_cache_refused_bytes = 0;\n'
     '  }\n'
     '}\n'
     '\n'
     'namespace {  // sasrt-nx: declared with the cache\'s state above\n'
     'bool SasrtCacheNoRoom(uint64_t bytes) {\n'
     '  if (!SasrtCacheFollowOn() ||\n'
     '      g_stream_cache_bytes + bytes <= banjo::renut_gpu::StreamCacheMaxBytes(kStreamCacheMaxBytes))\n'
     '    return false;\n'
     '  g_sasrt_cache_full = true;\n'
     '  ++g_sasrt_cache_refused;\n'
     '  g_sasrt_cache_refused_bytes += bytes;\n'
     '  return true;\n'
     '}\n'
     '}  // namespace\n'),
]

# sasrt-nx (2026-10-21, a test, sasrt_renut_diag_convert_at_bind): the race start's faults with the render thread
# lagging (dark smears over the car, red / green triangles in the sky) go when the game may not run a frame ahead
# (sasrt_renut_diag_no_frames_ahead): a late read of guest memory. Vertex streams are read at the kick's flush, after
# the draw was replayed; this key converts them at the draw instead (uncached), to tell the two windows apart.
EDITS += [
    ('render/draw.cpp',
     '      if (call.up_vertices && stream == 0) {\n'
     '        // A copy taken at the call (queued.cpp).\n',
     '      static const bool sasrt_at_bind = REXCVAR_GET(sasrt_renut_diag_convert_at_bind);  // sasrt-nx (a test)\n'
     '      if ((call.up_vertices && stream == 0) || sasrt_at_bind) {\n'
     '        // A copy taken at the call (queued.cpp).\n'),
    ('render/draw.cpp',
     'REXCVAR_DEFINE_BOOL(sasrt_renut_texture_signs, true, "SASRT",\n',
     'REXCVAR_DEFINE_BOOL(sasrt_renut_diag_convert_at_bind, false, "SASRT",\n'
     '                    "A test: Renut\'s renderer converts a draw\'s vertex streams when it replays the draw, not at "\n'
     '                    "the next kick\'s flush (and caches none)")\n'
     '    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\n'
     'REXCVAR_DEFINE_BOOL(sasrt_renut_texture_signs, true, "SASRT",\n'),
]

# sasrt-nx (2026-10-21, diagnostics, sasrt_renut_diag_late_streams): which vertex data the game changes between a draw
# call and the render thread's replay of it (the race start's late-read faults). The bound streams' first 4 KB are
# hashed on the game thread at the call (CaptureSurfaces, and a recorded buffer's draw op) and again at the replay.
EDITS += [
    ('backend/queued.h',
     'void SnapshotDeltasNewFrame();\n',
     '// sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams): up to four bound vertex streams of a draw, hashed at the call.\n'
     'struct SasrtStreamHashes {\n'
     '  u32 count = 0;\n'
     '  u32 va[4] = {}, size[4] = {}, stream[4] = {};\n'
     '  uint64_t hash[4] = {};\n'
     '  u32 stride[4] = {};  // sasrt_renut_capture_recorded_streams: SetStreamSource\'s stride (0: none given)\n'
     '};\n'
     'bool SasrtLateStreamsOn();\n'
     'void SasrtHashStreams(const u8 *device_bytes, SasrtStreamHashes &out);\n'
     'void SasrtCheckStreams(const SasrtStreamHashes &in, bool recorded);\n'
     '\n'
     'void SnapshotDeltasNewFrame();\n'),
    ('backend/queued.cpp',
     '#include "renut_engine/gpu/sa2_line_compare.h"\n',
     '#include "renut_engine/gpu/sa2_line_compare.h"\n'
     '\n'
     '#include <chrono>\n'
     '\n'
     'REXCVAR_DEFINE_BOOL(sasrt_renut_diag_late_streams, false, "SASRT",\n'
     '                    "Diagnostics: each draw\'s bound vertex streams (their first 4 KB) hashed at the game\'s draw "\n'
     '                    "call and again when Renut\'s render thread replays the draw; the ones that changed between are "\n'
     '                    "logged ([sasrt] late stream)")\n'
     '    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\n'
     '\n'
     'namespace renut::gpu {\n'
     '\n'
     'bool SasrtLateStreamsOn() {\n'
     '  static const bool on = REXCVAR_GET(sasrt_renut_diag_late_streams);\n'
     '  return on;\n'
     '}\n'
     '\n'
     'void SasrtHashStreams(const u8 *device_bytes, SasrtStreamHashes &out) {\n'
     '  out.count = 0;\n'
     '  for (u32 s = 0; s < 16u && out.count < 4; ++s) {  // the vertex streams (kMaxVertexStreams)\n'
     '    if (!u32(*reinterpret_cast<const be_u32 *>(device_bytes + d3d::kDeviceOffsetStreamSources + s * 4)))\n'
     '      continue;  // no vertex buffer bound there\n'
     '    const u32 index = d3d::kFirstVertexFetchIndex + d3d::StreamFetchIndex(s);\n'
     '    const u8 *w = device_bytes + offsetof(d3d::Device, m_Constants) + index * 8;\n'
     '    const u32 w0 = *reinterpret_cast<const be_u32 *>(w), w1 = *reinterpret_cast<const be_u32 *>(w + 4);\n'
     '    const u32 va = w0 & ~3u, size = std::min<u32>(w1 & 0x3FFFFFCu, 4096u);\n'
     '    const u8 *p = va && size ? GuestPhysicalPtr<const u8>(va) : nullptr;\n'
     '    if (!p)\n'
     '      continue;\n'
     '    out.va[out.count] = va;\n'
     '    out.size[out.count] = size;\n'
     '    out.stream[out.count] = s;\n'
     '    out.hash[out.count] = banjo::renut_gpu::ContentHash64(p, size);\n'
     '    ++out.count;\n'
     '  }\n'
     '}\n'
     '\n'
     'void SasrtCheckStreams(const SasrtStreamHashes &in, bool recorded) {\n'
     '  static std::mutex mutex;\n'
     '  static uint64_t checked = 0, changed[2] = {}, logged = 0, total_changed = 0;\n'
     '  static auto next = std::chrono::steady_clock::now() + std::chrono::seconds(10);\n'
     '  std::lock_guard lock(mutex);\n'
     '  for (u32 i = 0; i < in.count; ++i) {\n'
     '    const u8 *p = GuestPhysicalPtr<const u8>(in.va[i]);\n'
     '    ++checked;\n'
     '    if (!p || banjo::renut_gpu::ContentHash64(p, in.size[i]) == in.hash[i])\n'
     '      continue;\n'
     '    ++changed[recorded ? 1 : 0];\n'
     '    if (logged++ < 60 || ++total_changed % 2000 == 0)\n'
     '      RGPU_INFO("[sasrt] late stream: {} draw\'s stream {} at {:08X} ({} bytes hashed) changed between the "\n'
     '                "game\'s draw call and the replay", recorded ? "a recorded buffer\'s" : "a title device", in.stream[i],\n'
     '                in.va[i], in.size[i]);\n'
     '  }\n'
     '  if (std::chrono::steady_clock::now() >= next) {\n'
     '    next = std::chrono::steady_clock::now() + std::chrono::seconds(10);\n'
     '    RGPU_INFO("[sasrt] late streams in 10 s: {} checked, {} changed in title device draws, {} in recorded "\n'
     '              "buffers\' draws", checked, changed[0], changed[1]);\n'
     '    checked = changed[0] = changed[1] = 0;\n'
     '  }\n'
     '}\n'
     '\n'
     '}  // namespace renut::gpu\n'),
    ('backend/queued.cpp',
     '  d3d::IndexBuffer ib{};\n'
     '};\n',
     '  d3d::IndexBuffer ib{};\n'
     '  SasrtStreamHashes sasrt_streams;  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams)\n'
     '};\n'),
    ('backend/queued.cpp',
     '  c->ib_va = 0;\n'
     '  if (!bytes)\n'
     '    return;\n',
     '  c->ib_va = 0;\n'
     '  c->sasrt_streams.count = 0;\n'
     '  if (!bytes)\n'
     '    return;\n'
     '  if (SasrtLateStreamsOn())  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams)\n'
     '    SasrtHashStreams(bytes, c->sasrt_streams);\n'),
    ('backend/queued.cpp',
     '    SetReplayIndexBufferLocked(capture->ib_va, &capture->ib);  // sasrt-nx (2026-10-21)\n',
     '    SetReplayIndexBufferLocked(capture->ib_va, &capture->ib);  // sasrt-nx (2026-10-21)\n'
     '    if (capture->sasrt_streams.count)  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams)\n'
     '      SasrtCheckStreams(capture->sasrt_streams, false);\n'),
    ('guest/command_buffers.cpp',
     '  // Run\n'
     '  u32 command_buffer = 0;\n',
     '  // Run\n'
     '  u32 command_buffer = 0;\n'
     '\n'
     '  SasrtStreamHashes sasrt_streams;  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams)\n'),
    ('guest/command_buffers.cpp',
     '  op.state = CopyState(buffer, bytes, op.plain_dirty, op.vs_dirty, op.ps_dirty);\n',
     '  op.state = CopyState(buffer, bytes, op.plain_dirty, op.vs_dirty, op.ps_dirty);\n'
     '  if (kind == OpKind::Draw && SasrtLateStreamsOn())  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams)\n'
     '    SasrtHashStreams(bytes, op.sasrt_streams);\n'),
    ('guest/command_buffers.cpp',
     '      DrawStateLocked(state, call, &constants);\n'
     '      break;\n',
     '      if (op.sasrt_streams.count)  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams)\n'
     '        SasrtCheckStreams(op.sasrt_streams, true);\n'
     '      DrawStateLocked(state, call, &constants);\n'
     '      break;\n'),
]

# sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams, second form): the replay is not when the bytes are read. A
# draw's vertex streams are converted at the next kick's flush (the 360's GPU too sees a draw only at the kick, and
# the game may fill vertices after the call): the hashes taken at the call go with the draw's pending fills and are
# compared just before the conversion.
EDITS += [
    ('backend/queued.h',
     'void SasrtCheckStreams(const SasrtStreamHashes &in, bool recorded);\n',
     'void SasrtCheckStreams(const SasrtStreamHashes &in, bool recorded);\n'
     '// The draw being replayed: its streams\' hashes at the call (nullptr without), and whether a recorded buffer\'s.\n'
     'extern const SasrtStreamHashes *g_sasrt_draw_streams;\n'
     'extern bool g_sasrt_draw_recorded;\n'),
    ('backend/queued.cpp',
     'bool SasrtLateStreamsOn() {\n',
     'const SasrtStreamHashes *g_sasrt_draw_streams = nullptr;\n'
     'bool g_sasrt_draw_recorded = false;\n'
     '\n'
     'bool SasrtLateStreamsOn() {\n'),
    ('backend/queued.cpp',
     '    if (capture->sasrt_streams.count)  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams)\n'
     '      SasrtCheckStreams(capture->sasrt_streams, false);\n',
     '    // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams): compared at the conversion (FlushVertexFillsLocked).\n'
     '    g_sasrt_draw_streams = capture->sasrt_streams.count ? &capture->sasrt_streams : nullptr;\n'
     '    g_sasrt_draw_recorded = false;\n'),
    ('backend/queued.cpp',
     '    SetReplaySurfaceOverridesLocked(nullptr, nullptr, 0);  // sasrt-nx\n'
     '    SetReplayIndexBufferLocked(0, nullptr);  // sasrt-nx (2026-10-21)\n',
     '    SetReplaySurfaceOverridesLocked(nullptr, nullptr, 0);  // sasrt-nx\n'
     '    SetReplayIndexBufferLocked(0, nullptr);  // sasrt-nx (2026-10-21)\n'
     '    g_sasrt_draw_streams = nullptr;  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams)\n'),
    ('guest/command_buffers.cpp',
     '      if (op.sasrt_streams.count)  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams)\n'
     '        SasrtCheckStreams(op.sasrt_streams, true);\n'
     '      DrawStateLocked(state, call, &constants);\n'
     '      break;\n',
     '      // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams): compared at the conversion.\n'
     '      g_sasrt_draw_streams = op.sasrt_streams.count ? &op.sasrt_streams : nullptr;\n'
     '      g_sasrt_draw_recorded = true;\n'
     '      DrawStateLocked(state, call, &constants);\n'
     '      g_sasrt_draw_streams = nullptr;\n'
     '      break;\n'),
    ('render/draw.cpp',
     '#include "renut_engine/gpu/guest/command_buffers.h"\n',
     '#include "renut_engine/gpu/guest/command_buffers.h"\n'
     '#include "renut_engine/gpu/backend/queued.h"  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams)\n'),
    ('render/draw.cpp',
     '  StreamKey key{};   // cacheable: the g_stream_cache entry\n'
     '  bool cacheable = false;\n'
     '};\n',
     '  StreamKey key{};   // cacheable: the g_stream_cache entry\n'
     '  bool cacheable = false;\n'
     '  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams): the stream\'s first bytes as hashed at the draw call.\n'
     '  SasrtStreamHashes sasrt_call;\n'
     '  bool sasrt_recorded = false;\n'
     '};\n'),
    ('render/draw.cpp',
     '        fill.cacheable = cached && !cached->dynamic;\n',
     '        fill.cacheable = cached && !cached->dynamic;\n'
     '        if (g_sasrt_draw_streams) {  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams)\n'
     '          const u32 va = device.VertexFetchWord(d3d::kFirstVertexFetchIndex + d3d::StreamFetchIndex(stream), 0) & ~3u;\n'
     '          const SasrtStreamHashes &h = *g_sasrt_draw_streams;\n'
     '          for (u32 i = 0; i < h.count; ++i) {\n'
     '            if (h.stream[i] != stream || h.va[i] != va)\n'
     '              continue;\n'
     '            fill.sasrt_call.count = 1;\n'
     '            fill.sasrt_call.va[0] = va;\n'
     '            fill.sasrt_call.size[0] = h.size[i];\n'
     '            fill.sasrt_call.stream[0] = stream;\n'
     '            fill.sasrt_call.hash[0] = h.hash[i];\n'
     '            fill.sasrt_recorded = g_sasrt_draw_recorded;\n'
     '          }\n'
     '        }\n'),
    ('render/draw.cpp',
     '  for (const PendingStreamFill &f : g_stream_fills) {\n'
     '    ConvertVertices(f.stream, f.guest, f.stride, f.count, f.endian, f.host);\n',
     '  for (const PendingStreamFill &f : g_stream_fills) {\n'
     '    if (f.sasrt_call.count)  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams)\n'
     '      SasrtCheckStreams(f.sasrt_call, f.sasrt_recorded);\n'
     '    ConvertVertices(f.stream, f.guest, f.stride, f.count, f.endian, f.host);\n'),
]

# sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams, third form): the game may fill a draw's vertices after the call;
# the 360's GPU reads them after the kick. The title device's draws' streams since the last kick are hashed on the
# game thread at the kick (KickDevice, before its flush is queued) and compared at the conversion: a change there is
# one the 360 would not have seen.
EDITS += [
    ('backend/queued.h',
     'extern bool g_sasrt_draw_recorded;\n',
     'extern bool g_sasrt_draw_recorded;\n'
     '// At a kick on the game thread: the streams noted since the last kick hashed, for the render thread\'s flush.\n'
     'void SasrtQueueKickHashes();\n'
     '// At the conversion: the stream compared with its hash at the kick (when one was taken); after the flush, forgotten.\n'
     'void SasrtCheckKick(u32 va, u32 size);\n'
     'void SasrtClearKickHashes();\n'),
    ('backend/queued.cpp',
     'bool SasrtLateStreamsOn() {\n',
     '// sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams): the title device\'s streams since the last kick (game\n'
     '// thread), and their hashes at the kick (render thread).\n'
     'std::mutex g_sasrt_kick_mutex;\n'
     'std::vector<std::pair<u32, u32>> g_sasrt_kick_list;\n'
     'std::unordered_map<u32, uint64_t> g_sasrt_kick_hashes;\n'
     '\n'
     'void SasrtQueueKickHashes() {\n'
     '  if (!SasrtLateStreamsOn())\n'
     '    return;\n'
     '  std::vector<std::pair<u32, uint64_t>> hashes;\n'
     '  {\n'
     '    std::lock_guard lock(g_sasrt_kick_mutex);\n'
     '    hashes.reserve(g_sasrt_kick_list.size());\n'
     '    for (const auto &[va, size] : g_sasrt_kick_list) {\n'
     '      // GPU (physical) addresses of vertex streams; an index buffer\'s may be a CPU one.\n'
     '      if (const u8 *p = va < 0x20000000u ? GuestPhysicalPtr<const u8>(va) : GuestPtr<const u8>(va))\n'
     '        hashes.emplace_back(va, banjo::renut_gpu::ContentHash64(p, size));\n'
     '    }\n'
     '    g_sasrt_kick_list.clear();\n'
     '  }\n'
     '  render_thread::QueueUnlocked([hashes = std::move(hashes)] {\n'
     '    for (const auto &[va, hash] : hashes)\n'
     '      g_sasrt_kick_hashes[va] = hash;\n'
     '  });\n'
     '}\n'
     '\n'
     'void SasrtCheckKick(u32 va, u32 size) {\n'
     '  static uint64_t checked = 0, changed = 0, logged = 0;\n'
     '  static auto next = std::chrono::steady_clock::now() + std::chrono::seconds(10);\n'
     '  auto it = g_sasrt_kick_hashes.find(va);\n'
     '  const u8 *p = GuestPhysicalPtr<const u8>(va);\n'
     '  if (it != g_sasrt_kick_hashes.end() && p) {\n'
     '    ++checked;\n'
     '    if (banjo::renut_gpu::ContentHash64(p, size) != it->second) {\n'
     '      ++changed;\n'
     '      if (logged++ < 60 || logged % 1000 == 0)\n'
     '        RGPU_INFO("[sasrt] late stream after the kick: a draw\'s stream at {:08X} changed between the game\'s "\n'
     '                  "kick and the conversion ({} so far)", va, logged);\n'
     '    }\n'
     '  }\n'
     '  if (std::chrono::steady_clock::now() >= next) {\n'
     '    next = std::chrono::steady_clock::now() + std::chrono::seconds(10);\n'
     '    RGPU_INFO("[sasrt] late streams after the kick in 10 s: {} compared, {} changed", checked, changed);\n'
     '    checked = changed = 0;\n'
     '  }\n'
     '}\n'
     '\n'
     'void SasrtClearKickHashes() {\n'
     '  g_sasrt_kick_hashes.clear();\n'
     '}\n'
     '\n'
     'bool SasrtLateStreamsOn() {\n'),
    ('backend/queued.cpp',
     '    SasrtHashStreams(bytes, c->sasrt_streams);\n',
     '    SasrtHashStreams(bytes, c->sasrt_streams);\n'
     '  if (c->sasrt_streams.count) {  // sasrt-nx: noted for the hash at the kick (SasrtQueueKickHashes)\n'
     '    std::lock_guard lock(g_sasrt_kick_mutex);\n'
     '    for (u32 i = 0; i < c->sasrt_streams.count; ++i)\n'
     '      g_sasrt_kick_list.emplace_back(c->sasrt_streams.va[i], c->sasrt_streams.size[i]);\n'
     '  }\n'),
    ('d3d/hooks/device.cpp',
     '  FlushDeferredVertices(device_va);\n'
     '  // banjo-nx (package 27c): the texture fills too',
     '  FlushDeferredVertices(device_va);\n'
     '  SasrtQueueKickHashes();  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams)\n'
     '  // banjo-nx (package 27c): the texture fills too'),
    ('render/draw.cpp',
     '      SasrtCheckStreams(f.sasrt_call, f.sasrt_recorded);\n',
     '      SasrtCheckStreams(f.sasrt_call, f.sasrt_recorded);\n'
     '    if (f.sasrt_call.count && !f.sasrt_recorded)  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams)\n'
     '      SasrtCheckKick(f.sasrt_call.va[0], f.sasrt_call.size[0]);\n'),
    ('render/draw.cpp',
     '  g_stream_fills.clear();\n'
     '  ++g_queued_generation;  // banjo-nx (2026-10-19): the table emptied\n',
     '  g_stream_fills.clear();\n'
     '  SasrtClearKickHashes();  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams)\n'
     '  ++g_queued_generation;  // banjo-nx (2026-10-19): the table emptied\n'),
]

# sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams, index data): Renut reads a draw's indices at the replay (the
# vertex range to convert comes from them). The title device's index ranges are hashed at the game's kick as above;
# what the replay read is hashed then too, and the two compared when the kick's hashes reach the render thread.
EDITS += [
    ('backend/queued.h',
     'void SasrtClearKickHashes();\n',
     'void SasrtClearKickHashes();\n'
     '// At the replay: the index bytes the draw reads, compared with the game\'s at its kick when those arrive.\n'
     'void SasrtNoteReplayIndices(u32 address, const u8 *data, u32 size);\n'),
    ('backend/queued.cpp',
     '  render_thread::QueueUnlocked([hashes = std::move(hashes)] {\n'
     '    for (const auto &[va, hash] : hashes)\n'
     '      g_sasrt_kick_hashes[va] = hash;\n'
     '  });\n',
     '  render_thread::QueueUnlocked([hashes = std::move(hashes)] {\n'
     '    for (const auto &[va, hash] : hashes)\n'
     '      g_sasrt_kick_hashes[va] = hash;\n'
     '    SasrtCompareReplayIndices();  // sasrt-nx: index data\n'
     '  });\n'),
    ('backend/queued.cpp',
     'void SasrtQueueKickHashes() {\n',
     '// sasrt-nx (2026-10-21): what the replays read of index data since the last kick (render thread).\n'
     'std::unordered_map<u32, uint64_t> g_sasrt_replay_indices;\n'
     '\n'
     'void SasrtNoteReplayIndices(u32 address, const u8 *data, u32 size) {\n'
     '  if (SasrtLateStreamsOn() && data && size)\n'
     '    g_sasrt_replay_indices[address] = banjo::renut_gpu::ContentHash64(data, std::min<u32>(size, 4096u));\n'
     '}\n'
     '\n'
     'void SasrtCompareReplayIndices() {\n'
     '  static uint64_t compared = 0, differ = 0, logged = 0;\n'
     '  static auto next = std::chrono::steady_clock::now() + std::chrono::seconds(10);\n'
     '  for (const auto &[address, hash] : g_sasrt_replay_indices) {\n'
     '    auto it = g_sasrt_kick_hashes.find(address);\n'
     '    if (it == g_sasrt_kick_hashes.end())\n'
     '      continue;\n'
     '    ++compared;\n'
     '    if (it->second != hash && (++differ, logged++ < 60 || logged % 1000 == 0))\n'
     '      RGPU_INFO("[sasrt] late indices: a draw\'s indices at {:08X} as the replay read them differ from the game\'s "\n'
     '                "at its kick ({} so far)", address, logged);\n'
     '  }\n'
     '  g_sasrt_replay_indices.clear();\n'
     '  if (std::chrono::steady_clock::now() >= next) {\n'
     '    next = std::chrono::steady_clock::now() + std::chrono::seconds(10);\n'
     '    RGPU_INFO("[sasrt] late indices in 10 s: {} compared with the kick, {} differ", compared, differ);\n'
     '    compared = differ = 0;\n'
     '  }\n'
     '}\n'
     '\n'
     'void SasrtQueueKickHashes() {\n'),
    ('backend/queued.cpp',
     '  if (c->sasrt_streams.count) {  // sasrt-nx: noted for the hash at the kick (SasrtQueueKickHashes)\n',
     '  if (SasrtLateStreamsOn() && c->call.indexed && !c->call.up_indices && c->ib_va) {  // sasrt-nx: index data\n'
     '    const u32 is32 = (u32(c->ib.resource.Common) & d3d::kIndexBufferCommon32Bit) ? 1u : 0u;\n'
     '    const u32 address = u32(c->ib.Address) + c->call.start_index * (is32 ? 4u : 2u);\n'
     '    const u32 size = std::min<u32>(c->call.count * (is32 ? 4u : 2u), 4096u);\n'
     '    std::lock_guard lock(g_sasrt_kick_mutex);\n'
     '    g_sasrt_kick_list.emplace_back(address, size);\n'
     '  }\n'
     '  if (c->sasrt_streams.count) {  // sasrt-nx: noted for the hash at the kick (SasrtQueueKickHashes)\n'),
    ('render/draw.cpp',
     '      index_key = IndexKey{src, call.count, call.primitive, endian, is32};\n',
     '      index_key = IndexKey{src, call.count, call.primitive, endian, is32};\n'
     '      SasrtNoteReplayIndices(u32(ib->Address) + call.start_index * (is32 ? 4u : 2u), src,  // sasrt-nx (diag)\n'
     '                             call.count * (is32 ? 4u : 2u));\n'),
]

# sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams, recorded buffers): the race's 3D scene is drawn by the workers'
# recorded buffers, which the 360's GPU reads when the composed segment is submitted (QueueCapturedRun, called from
# the ring submission hook): their draws' stream and index ranges are hashed there, on the game thread, just before
# the replay is queued; streams are compared at the conversion, indices at the replay.
EDITS += [
    ('backend/queued.h',
     'void SasrtClearKickHashes();\n',
     'void SasrtClearKickHashes();\n'
     '// A range for the next SasrtQueueKickHashes (any thread).\n'
     'void SasrtNoteKickRange(u32 va, u32 size);\n'),
    ('backend/queued.cpp',
     'void SasrtNoteReplayIndices(u32 address, const u8 *data, u32 size) {\n'
     '  if (SasrtLateStreamsOn() && data && size)\n'
     '    g_sasrt_replay_indices[address] = banjo::renut_gpu::ContentHash64(data, std::min<u32>(size, 4096u));\n'
     '}\n',
     'void SasrtCountIndexCompare(u32 address, bool same) {\n'
     '  static uint64_t compared = 0, differ = 0, logged = 0;\n'
     '  static auto next = std::chrono::steady_clock::now() + std::chrono::seconds(10);\n'
     '  ++compared;\n'
     '  if (!same && (++differ, logged++ < 60 || logged % 1000 == 0))\n'
     '    RGPU_INFO("[sasrt] late indices: a draw\'s indices at {:08X} as the replay read them differ from the game\'s "\n'
     '              "at its kick ({} so far)", address, logged);\n'
     '  if (std::chrono::steady_clock::now() >= next) {\n'
     '    next = std::chrono::steady_clock::now() + std::chrono::seconds(10);\n'
     '    RGPU_INFO("[sasrt] late indices in 10 s: {} compared with the kick, {} differ", compared, differ);\n'
     '    compared = differ = 0;\n'
     '  }\n'
     '}\n'
     '\n'
     'void SasrtNoteReplayIndices(u32 address, const u8 *data, u32 size) {\n'
     '  if (!SasrtLateStreamsOn() || !data || !size)\n'
     '    return;\n'
     '  const uint64_t hash = banjo::renut_gpu::ContentHash64(data, std::min<u32>(size, 4096u));\n'
     '  // A recorded buffer\'s draw: its kick hashes came before its replay.\n'
     '  if (auto it = g_sasrt_kick_hashes.find(address); it != g_sasrt_kick_hashes.end())\n'
     '    SasrtCountIndexCompare(address, it->second == hash);\n'
     '  else\n'
     '    g_sasrt_replay_indices[address] = hash;\n'
     '}\n'
     '\n'
     'void SasrtNoteKickRange(u32 va, u32 size) {\n'
     '  std::lock_guard lock(g_sasrt_kick_mutex);\n'
     '  g_sasrt_kick_list.emplace_back(va, size);\n'
     '}\n'),
    ('backend/queued.cpp',
     '  static uint64_t compared = 0, differ = 0, logged = 0;\n'
     '  static auto next = std::chrono::steady_clock::now() + std::chrono::seconds(10);\n'
     '  for (const auto &[address, hash] : g_sasrt_replay_indices) {\n'
     '    auto it = g_sasrt_kick_hashes.find(address);\n'
     '    if (it == g_sasrt_kick_hashes.end())\n'
     '      continue;\n'
     '    ++compared;\n'
     '    if (it->second != hash && (++differ, logged++ < 60 || logged % 1000 == 0))\n'
     '      RGPU_INFO("[sasrt] late indices: a draw\'s indices at {:08X} as the replay read them differ from the game\'s "\n'
     '                "at its kick ({} so far)", address, logged);\n'
     '  }\n'
     '  g_sasrt_replay_indices.clear();\n'
     '  if (std::chrono::steady_clock::now() >= next) {\n'
     '    next = std::chrono::steady_clock::now() + std::chrono::seconds(10);\n'
     '    RGPU_INFO("[sasrt] late indices in 10 s: {} compared with the kick, {} differ", compared, differ);\n'
     '    compared = differ = 0;\n'
     '  }\n',
     '  for (const auto &[address, hash] : g_sasrt_replay_indices) {\n'
     '    if (auto it = g_sasrt_kick_hashes.find(address); it != g_sasrt_kick_hashes.end())\n'
     '      SasrtCountIndexCompare(address, it->second == hash);\n'
     '  }\n'
     '  g_sasrt_replay_indices.clear();\n'),
    ('render/draw.cpp',
     '    if (f.sasrt_call.count && !f.sasrt_recorded)  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams)\n'
     '      SasrtCheckKick(f.sasrt_call.va[0], f.sasrt_call.size[0]);\n',
     '    if (f.sasrt_call.count)  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams)\n'
     '      SasrtCheckKick(f.sasrt_call.va[0], f.sasrt_call.size[0]);\n'),
    ('guest/command_buffers.cpp',
     '  run->captured = std::move(captured);\n'
     '  render_thread::Queue([run, command_buffer_va] {\n',
     '  run->captured = std::move(captured);\n'
     '  if (SasrtLateStreamsOn()) {  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams): the 360 reads them now\n'
     '    for (const auto &[va, buffer] : run->captured->buffers) {\n'
     '      if (!buffer)\n'
     '        continue;\n'
     '      for (const Op &op : buffer->ops) {\n'
     '        if (op.kind != OpKind::Draw)\n'
     '          continue;\n'
     '        for (u32 i = 0; i < op.sasrt_streams.count; ++i)\n'
     '          SasrtNoteKickRange(op.sasrt_streams.va[i], op.sasrt_streams.size[i]);\n'
     '        if (op.call.indexed && op.up_indices == kNone && op.ib_va) {\n'
     '          const u32 esize = (u32(op.ib.resource.Common) & d3d::kIndexBufferCommon32Bit) ? 4u : 2u;\n'
     '          SasrtNoteKickRange(u32(op.ib.Address) + op.call.start_index * esize,\n'
     '                             std::min<u32>(op.call.count * esize, 4096u));\n'
     '        }\n'
     '      }\n'
     '    }\n'
     '    SasrtQueueKickHashes();\n'
     '  }\n'
     '  render_thread::Queue([run, command_buffer_va] {\n'),
]

# sasrt-nx (2026-10-21, sasrt_renut_recorded_binds; app/src/renut_engine/sasrt_renut_hooks.cpp): the race's octopus
# exploding (and the sky's red / green triangles) when the render thread lags. SASRT draws its scene meshes with no
# declaration: D3DVertexShader_Bind patches the formats into the shader's microcode, and the hook hands them to the
# shader record through the render thread's queue. The workers' recorded command buffers replay a frame after their
# draws, so a recorded draw met whatever bind was queued last, another mesh's layout of the same shader. Each draw now
# keeps its shader's binding as the game made it at the draw (the main device's captures and the recorded buffers'
# ops), and its replay gives it back to the shader record.
EDITS += [
    ('backend/queued.cpp',
     '#include <chrono>\n'
     '\n'
     'REXCVAR_DEFINE_BOOL(sasrt_renut_diag_late_streams',
     '#include <chrono>\n'
     '\n'
     '// sasrt-nx (2026-10-21, sasrt_renut_recorded_binds): app/src/renut_engine/sasrt_renut_hooks.cpp.\n'
     'bool SasrtRecordedBindsOn();\n'
     'bool SasrtBindingOf(uint32_t shader_va, uint32_t *declaration, uint32_t *strides);\n'
     'void SasrtApplyRecordedBinding(uint32_t shader_va, uint32_t declaration, const uint32_t *strides);\n'
     '\n'
     'REXCVAR_DEFINE_BOOL(sasrt_renut_diag_late_streams'),
    ('backend/queued.cpp',
     '  SasrtStreamHashes sasrt_streams;  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams)\n'
     '};\n',
     '  SasrtStreamHashes sasrt_streams;  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams)\n'
     '  // sasrt-nx (2026-10-21, sasrt_renut_recorded_binds): the vertex shader\'s binding at the call (0: none known).\n'
     '  u32 sasrt_vs = 0, sasrt_decl = 0;\n'
     '  u32 sasrt_strides[d3d::kMaxStreams] = {};\n'
     '};\n'),
    ('backend/queued.cpp',
     '  c->sasrt_streams.count = 0;\n',
     '  c->sasrt_streams.count = 0;\n'
     '  c->sasrt_vs = 0;\n'),
    ('backend/queued.cpp',
     '  if (SasrtLateStreamsOn())  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams)\n'
     '    SasrtHashStreams(bytes, c->sasrt_streams);\n',
     '  if (SasrtRecordedBindsOn()) {  // sasrt-nx (2026-10-21, sasrt_renut_recorded_binds)\n'
     '    const u32 vs = u32(*reinterpret_cast<const be_u32 *>(bytes + d3d::kDeviceOffsetVertexShader));\n'
     '    if (vs && SasrtBindingOf(vs, &c->sasrt_decl, c->sasrt_strides))\n'
     '      c->sasrt_vs = vs;\n'
     '  }\n'
     '  if (SasrtLateStreamsOn())  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams)\n'
     '    SasrtHashStreams(bytes, c->sasrt_streams);\n'),
    ('backend/queued.cpp',
     '    g_sasrt_draw_recorded = false;\n',
     '    g_sasrt_draw_recorded = false;\n'
     '    if (capture->sasrt_vs)  // sasrt-nx (2026-10-21, sasrt_renut_recorded_binds)\n'
     '      SasrtApplyRecordedBinding(capture->sasrt_vs, capture->sasrt_decl, capture->sasrt_strides);\n'),
    ('guest/command_buffers.cpp',
     'namespace renut::gpu {',
     '// sasrt-nx (2026-10-21, sasrt_renut_recorded_binds): app/src/renut_engine/sasrt_renut_hooks.cpp.\n'
     'bool SasrtRecordedBindsOn();\n'
     'bool SasrtBindingOf(uint32_t shader_va, uint32_t *declaration, uint32_t *strides);\n'
     'void SasrtApplyRecordedBinding(uint32_t shader_va, uint32_t declaration, const uint32_t *strides);\n'
     '\n'
     'namespace renut::gpu {'),
    ('guest/command_buffers.cpp',
     '  SasrtStreamHashes sasrt_streams;  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams)\n',
     '  SasrtStreamHashes sasrt_streams;  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams)\n'
     '  // sasrt-nx (2026-10-21, sasrt_renut_recorded_binds): the vertex shader\'s binding when recorded (0: none known).\n'
     '  u32 sasrt_vs = 0, sasrt_decl = 0;\n'
     '  u32 sasrt_strides[d3d::kMaxStreams] = {};\n'),
    ('guest/command_buffers.cpp',
     '  if (kind == OpKind::Draw && SasrtLateStreamsOn())  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams)\n',
     '  if (kind == OpKind::Draw && SasrtRecordedBindsOn()) {  // sasrt-nx (2026-10-21, sasrt_renut_recorded_binds)\n'
     '    const u32 vs = u32(*reinterpret_cast<const be_u32 *>(bytes + d3d::kDeviceOffsetVertexShader));\n'
     '    if (vs && SasrtBindingOf(vs, &op.sasrt_decl, op.sasrt_strides))\n'
     '      op.sasrt_vs = vs;\n'
     '  }\n'
     '  if (kind == OpKind::Draw && SasrtLateStreamsOn())  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams)\n'),
    ('guest/command_buffers.cpp',
     '      g_sasrt_draw_recorded = true;\n'
     '      DrawStateLocked(state, call, &constants);\n',
     '      g_sasrt_draw_recorded = true;\n'
     '      if (op.sasrt_vs)  // sasrt-nx (2026-10-21, sasrt_renut_recorded_binds)\n'
     '        SasrtApplyRecordedBinding(op.sasrt_vs, op.sasrt_decl, op.sasrt_strides);\n'
     '      DrawStateLocked(state, call, &constants);\n'),
]

# sasrt-nx (2026-10-21, a test, sasrt_renut_capture_recorded_streams): RenderDoc of the lagging PC (capture 5 of 10 at
# the race start): the octopus's geometry-pass draw read a position stream (R32G32B32, stride 12, re-uploaded that
# frame: the CPU animates it) of which a tenth were zeros, (1,0,0) or (21.9,1,-0.85), its normals (cached) right. The
# workers' recorded buffers are replayed a frame after they were recorded, when the game is writing the next frame's
# vertices. This test copies each recorded draw's vertex streams (up to 64 KB each) at the composed buffer's submission,
# when the 360's GPU gets them, and the replay reads the copies.
EDITS += [
    ('guest/command_buffers.h',
     'void QueueCapturedRun(u32 device_va, u32 command_buffer_va, std::shared_ptr<CapturedRun> captured);\n',
     'void QueueCapturedRun(u32 device_va, u32 command_buffer_va, std::shared_ptr<CapturedRun> captured);\n'
     '\n'
     '// sasrt-nx (2026-10-21, sasrt_renut_capture_recorded_streams): the vertex streams of the run being replayed as they\n'
     '// were at its submission, by GPU address (GetStreamSource reads these instead of guest memory); nullptr outside.\n'
     '// \'data\' spans the stream\'s \'size\' bytes, of which only the vertices the run\'s draws read at \'stride\' are filled\n'
     '// (stride 0: all of them).\n'
     'struct SasrtStreamCopy {\n'
     '  std::unique_ptr<u8[]> data;\n'
     '  u32 size = 0, stride = 0;\n'
     '};\n'
     'using SasrtStreamCopies = std::unordered_map<u32, SasrtStreamCopy>;\n'
     'extern const SasrtStreamCopies *g_sasrt_stream_copies;\n'
     '// After a flush converted the fills that point into the copies (FlushVertexFillsLocked).\n'
     'void SasrtReleaseStreamCopies();\n'),
    ('guest/command_buffers.cpp',
     '// sasrt-nx (2026-10-21, sasrt_renut_recorded_binds): app/src/renut_engine/sasrt_renut_hooks.cpp.\n'
     'bool SasrtRecordedBindsOn();\n',
     '#include <rex/cvar.h>\n'
     '#include "renut_engine/gpu/log.h"\n'
     'REXCVAR_DEFINE_BOOL(sasrt_renut_capture_recorded_streams, false, "SASRT",\n'
     '                    "A test: the vertex streams (up to 64 KB each) of the workers\' recorded draws are copied at the "\n'
     '                    "composed buffer\'s submission, when the 360\'s GPU gets them, and their replay a frame later "\n'
     '                    "reads the copies (the octopus\'s CPU-animated positions were read while the game wrote the "\n'
     '                    "next frame\'s)")\n'
     '    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\n'
     '\n'
     '// sasrt-nx (2026-10-21, sasrt_renut_recorded_binds): app/src/renut_engine/sasrt_renut_hooks.cpp.\n'
     'bool SasrtRecordedBindsOn();\n'),
    ('guest/command_buffers.cpp',
     '  // sasrt-nx (2026-10-21, sasrt_renut_recorded_binds): the vertex shader\'s binding when recorded (0: none known).\n',
     '  SasrtStreamHashes sasrt_ranges;  // sasrt-nx (2026-10-21, sasrt_renut_capture_recorded_streams): bound streams\n'
     '  // sasrt-nx (2026-10-21, sasrt_renut_recorded_binds): the vertex shader\'s binding when recorded (0: none known).\n'),
    ('guest/command_buffers.cpp',
     '  if (kind == OpKind::Draw && SasrtRecordedBindsOn()) {  // sasrt-nx (2026-10-21, sasrt_renut_recorded_binds)\n',
     '  if (kind == OpKind::Draw && SasrtCaptureStreamsOn())  // sasrt-nx (2026-10-21, sasrt_renut_capture_recorded_streams)\n'
     '    SasrtNoteStreamRanges(bytes, op.sasrt_ranges);\n'
     '  if (kind == OpKind::Draw && SasrtRecordedBindsOn()) {  // sasrt-nx (2026-10-21, sasrt_renut_recorded_binds)\n'),
    ('guest/command_buffers.cpp',
     '  struct Run {\n'
     '    std::vector<u8> running;  // the running device, whose constants the buffer inherits\n'
     '    std::shared_ptr<CapturedRun> captured;\n'
     '  };\n',
     '  struct Run {\n'
     '    std::vector<u8> running;  // the running device, whose constants the buffer inherits\n'
     '    std::shared_ptr<CapturedRun> captured;\n'
     '    std::shared_ptr<SasrtStreamCopies> copies;  // sasrt-nx (sasrt_renut_capture_recorded_streams)\n'
     '  };\n'),
    ('guest/command_buffers.cpp',
     '  run->captured = std::move(captured);\n',
     '  run->captured = std::move(captured);\n'
     '  if (SasrtCaptureStreamsOn()) {  // sasrt-nx (2026-10-21, sasrt_renut_capture_recorded_streams): copied now\n'
     '    // Per stream (GPU address): its size, the stride its draws read it with (~0u: they differ, so all of it) and\n'
     '    // the vertex ranges they read (PrepareGeometry\'s: base vertex plus the lowest to the highest index).\n'
     '    struct Want {\n'
     '      u32 size = 0, stride = 0;\n'
     '      std::vector<std::pair<u32, u32>> ranges;  // [first, last] vertex\n'
     '    };\n'
     '    std::unordered_map<u32, Want> wants;\n'
     '    for (const auto &[buffer_va, buffer] : run->captured->buffers) {\n'
     '      if (!buffer)\n'
     '        continue;\n'
     '      for (const Op &op : buffer->ops) {\n'
     '        if (op.kind != OpKind::Draw || !op.sasrt_ranges.count)\n'
     '          continue;\n'
     '        u32 first = 0, last = ~0u;  // ~0u: unknown, the whole stream\n'
     '        if (!op.call.tessellation && op.call.count) {\n'
     '          if (!op.call.indexed) {\n'
     '            first = op.call.start_vertex;\n'
     '            last = first + op.call.count - 1;\n'
     '          } else {\n'
     '            const u8 *src = nullptr;\n'
     '            bool is32 = false;\n'
     '            u32 endian = 0;\n'
     '            if (op.up_indices != kNone || (op.call.up_index_offset && op.up_vertices != kNone)) {  // as Replay\n'
     '              is32 = op.call.up_indices_32;\n'
     '              endian = is32 ? 2 : 1;\n'
     '              src = buffer->arena.data() +\n'
     '                    (op.up_indices != kNone ? op.up_indices : op.up_vertices + op.call.up_index_offset) +\n'
     '                    size_t(op.call.start_index) * (is32 ? 4 : 2);\n'
     '            } else if (op.ib_va) {\n'
     '              is32 = (u32(op.ib.resource.Common) & d3d::kIndexBufferCommon32Bit) != 0;\n'
     '              endian = d3d::IndexBufferEndian(u32(op.ib.resource.Common));\n'
     '              if (const u8 *base = GuestPhysicalPtr<const u8>(u32(op.ib.Address)))\n'
     '                src = base + size_t(op.call.start_index) * (is32 ? 4 : 2);\n'
     '            }\n'
     '            if (src) {\n'
     '              u32 lo = ~0u, hi = 0;\n'
     '              for (u32 k = 0; k < op.call.count; ++k) {\n'
     '                u32 v;\n'
     '                if (is32) {\n'
     '                  std::memcpy(&v, src + k * 4, 4);\n'
     '                  if (endian == 2)  // as SwapEndian\n'
     '                    v = __builtin_bswap32(v);\n'
     '                  else if (endian == 1)\n'
     '                    v = ((v & 0x00FF00FFu) << 8) | ((v >> 8) & 0x00FF00FFu);\n'
     '                  else if (endian == 3)\n'
     '                    v = (v >> 16) | (v << 16);\n'
     '                } else {\n'
     '                  uint16_t h;\n'
     '                  std::memcpy(&h, src + k * 2, 2);\n'
     '                  v = (endian == 1 || endian == 2) ? __builtin_bswap16(h) : h;  // as ReadIndices\n'
     '                }\n'
     '                lo = std::min(lo, v);\n'
     '                hi = std::max(hi, v);\n'
     '              }\n'
     '              if (lo <= hi && hi - lo < (1u << 20)) {\n'
     '                first = u32(int64_t(op.call.base_vertex) + lo);\n'
     '                last = u32(int64_t(op.call.base_vertex) + hi);\n'
     '              }\n'
     '            }\n'
     '          }\n'
     '        }\n'
     '        for (u32 i = 0; i < op.sasrt_ranges.count; ++i) {\n'
     '          if (op.sasrt_ranges.stream[i] == 0 && op.up_vertices != kNone)\n'
     '            continue;  // its own copy\n'
     '          Want &want = wants[op.sasrt_ranges.va[i]];\n'
     '          want.size = std::max(want.size, op.sasrt_ranges.size[i]);\n'
     '          const u32 stride = op.sasrt_ranges.stride[i];\n'
     '          if (!stride || last == ~0u)\n'
     '            want.stride = ~0u;\n'
     '          else if (want.stride != ~0u && want.stride != stride)\n'
     '            want.stride = want.stride ? ~0u : stride;\n'
     '          if (want.stride != ~0u)\n'
     '            want.ranges.emplace_back(first, last);\n'
     '        }\n'
     '      }\n'
     '    }\n'
     '    auto copies = std::make_shared<SasrtStreamCopies>();\n'
     '    uint64_t copied = 0;\n'
     '    for (auto &[stream_va, want] : wants) {\n'
     '      const u8 *p = GuestPhysicalPtr<const u8>(stream_va);\n'
     '      if (!p || !want.size)\n'
     '        continue;\n'
     '      // 12:40: whole streams only, up to 2 MB (the ranges left bytes some draws read unfilled: a PC race drew\n'
     '      // planes across the screen in most frames); a bigger stream is read from guest memory, as without the key.\n'
     '      if (want.size > (2u << 20))\n'
     '        continue;\n'
     '      want.stride = ~0u;\n'
     '      SasrtStreamCopy &copy = (*copies)[stream_va];\n'
     '      copy.data.reset(new u8[want.size]);\n'
     '      copy.size = want.size;\n'
     '      if (want.stride == ~0u || want.ranges.empty()) {\n'
     '        std::memcpy(copy.data.get(), p, want.size);\n'
     '        copied += want.size;\n'
     '        continue;\n'
     '      }\n'
     '      copy.stride = want.stride;\n'
     '      std::sort(want.ranges.begin(), want.ranges.end());\n'
     '      uint64_t end = 0;  // bytes copied so far from the start of the stream\n'
     '      for (const auto &[a, b] : want.ranges) {\n'
     '        uint64_t from = std::max<uint64_t>(uint64_t(a) * want.stride, end);\n'
     '        const uint64_t to = std::min<uint64_t>((uint64_t(b) + 1) * want.stride, want.size);\n'
     '        if (from < to) {\n'
     '          std::memcpy(copy.data.get() + from, p + from, size_t(to - from));\n'
     '          copied += to - from;\n'
     '          end = to;\n'
     '        }\n'
     '      }\n'
     '    }\n'
     '    SasrtCountStreamCopies(*copies, copied);\n'
     '    run->copies = std::move(copies);\n'
     '  }\n'),
    ('guest/command_buffers.cpp',
     '    Replay(running, run->captured->buffers, command_buffer_va, 0, Predication(running));\n',
     '    g_sasrt_stream_copies = run->copies.get();  // sasrt-nx (sasrt_renut_capture_recorded_streams)\n'
     '    Replay(running, run->captured->buffers, command_buffer_va, 0, Predication(running));\n'
     '    g_sasrt_stream_copies = nullptr;\n'
     '    if (run->copies)\n'
     '      g_sasrt_copies_alive.push_back(run->copies);  // the run\'s fills convert at the next flush\n'),
    ('guest/command_buffers.cpp',
     'void QueueCapturedRun(u32 device_va, u32 command_buffer_va, std::shared_ptr<CapturedRun> captured) {\n',
     '// sasrt-nx (2026-10-21, sasrt_renut_capture_recorded_streams).\n'
     'const SasrtStreamCopies *g_sasrt_stream_copies = nullptr;\n'
     'std::vector<std::shared_ptr<SasrtStreamCopies>> g_sasrt_copies_alive;  // render thread\n'
     '\n'
     'void SasrtReleaseStreamCopies() {\n'
     '  g_sasrt_copies_alive.clear();\n'
     '}\n'
     '\n'
     'bool SasrtCaptureStreamsOn() {\n'
     '  static const bool on = REXCVAR_GET(sasrt_renut_capture_recorded_streams);\n'
     '  return on;\n'
     '}\n'
     '\n'
     '// The bound vertex streams of a draw being recorded (the ones copied at the submission), with their strides.\n'
     'void SasrtNoteStreamRanges(const u8 *bytes, SasrtStreamHashes &out) {\n'
     '  out.count = 0;\n'
     '  for (u32 s = 0; s < 16u && out.count < 4; ++s) {\n'
     '    if (!u32(*reinterpret_cast<const be_u32 *>(bytes + d3d::kDeviceOffsetStreamSources + s * 4)))\n'
     '      continue;\n'
     '    const u8 *w = bytes + offsetof(d3d::Device, m_Constants) +\n'
     '                  (d3d::kFirstVertexFetchIndex + d3d::StreamFetchIndex(s)) * 8;\n'
     '    const u32 w0 = *reinterpret_cast<const be_u32 *>(w), w1 = *reinterpret_cast<const be_u32 *>(w + 4);\n'
     '    const u32 va = w0 & ~3u, size = w1 & 0x3FFFFFCu;\n'
     '    if (!va || !size)\n'
     '      continue;\n'
     '    out.va[out.count] = va;\n'
     '    out.size[out.count] = size;\n'
     '    out.stream[out.count] = s;\n'
     '    out.stride[out.count] = u32(bytes[d3d::kDeviceOffsetStreamStrides + s]) * 4;\n'
     '    ++out.count;\n'
     '  }\n'
     '}\n'
     '\n'
     'void SasrtCountStreamCopies(const SasrtStreamCopies &copies, uint64_t copied) {\n'
     '  static std::atomic<uint64_t> runs{0}, streams{0}, bytes{0}, spanned{0};\n'
     '  uint64_t b = 0;\n'
     '  for (const auto &entry : copies)\n'
     '    b += entry.second.size;\n'
     '  streams += copies.size();\n'
     '  bytes += copied;\n'
     '  spanned += b;\n'
     '  const uint64_t n = ++runs;\n'
     '  if (n % 600 == 0)\n'
     '    RGPU_INFO("[sasrt] recorded runs\' vertex streams copied at their submission: {} runs, {} streams, {:.1f} MB "\n'
     '              "copied of {:.1f} MB they span (sasrt_renut_capture_recorded_streams)", n, streams.load(),\n'
     '              bytes.load() / 1048576.0, spanned.load() / 1048576.0);\n'
     '}\n'
     '\n'
     'void QueueCapturedRun(u32 device_va, u32 command_buffer_va, std::shared_ptr<CapturedRun> captured) {\n'),
    ('render/draw.cpp',
     '  src.vertex_count = src.stride ? size / src.stride : (size ? 1 : 0);\n',
     '  // sasrt-nx (2026-10-21, sasrt_renut_capture_recorded_streams): a recorded run\'s stream as copied at its submission.\n'
     '  // Only at the stride its ranges were copied with (the vertices the draw converts); not cached (the copy goes).\n'
     '  if (g_sasrt_stream_copies && gpu_address) {\n'
     '    auto it = g_sasrt_stream_copies->find(gpu_address);\n'
     '    if (it != g_sasrt_stream_copies->end() && it->second.size >= size &&\n'
     '        (!it->second.stride || it->second.stride == src.stride)) {\n'
     '      src.data = it->second.data.get();\n'
     '      src.sasrt_held = true;\n'
     '    }\n'
     '  }\n'
     '  src.vertex_count = src.stride ? size / src.stride : (size ? 1 : 0);\n'),
    ('render/draw.cpp',
     '  SasrtClearKickHashes();  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams)\n',
     '  SasrtClearKickHashes();  // sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams)\n'
     '  SasrtReleaseStreamCopies();  // sasrt-nx (2026-10-21, sasrt_renut_capture_recorded_streams)\n'),
    ('guest/command_buffers.cpp',
     'namespace renut::gpu {',
     'namespace renut::gpu {\n'
     '\n'
     '// sasrt-nx (2026-10-21, sasrt_renut_capture_recorded_streams): defined before QueueCapturedRun.\n'
     'bool SasrtCaptureStreamsOn();\n'
     'void SasrtNoteStreamRanges(const u8 *bytes, SasrtStreamHashes &out);\n'
     'void SasrtCountStreamCopies(const SasrtStreamCopies &copies, uint64_t copied);'),
]

# sasrt-nx (2026-10-21, diagnostics, sasrt_renut_diag_layout_log): the race's octopus is drawn wrong on every back end
# and with no lag (its tentacles straight spikes; the emulated GPU curls them). RenderDoc: its draw has two streams,
# 32-bit float XYZ (stride 12) and half XYZW (stride 8). Once per vertex shader: its streams' strides, CPU addresses
# and element formats, to find the octopus's shader for banjo_renut_diag_stream_dump_vs.
EDITS += [
    ('render/draw.cpp',
     'REXCVAR_DEFINE_BOOL(sasrt_renut_texture_signs, true, "SASRT",\n',
     'REXCVAR_DEFINE_BOOL(sasrt_renut_diag_layout_log, false, "SASRT",\n'
     '                    "Diagnostics: once per vertex shader, its vertex streams\' strides, addresses and element "\n'
     '                    "formats ([sasrt] layout lines)")\n'
     '    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\n'
     'REXCVAR_DEFINE_BOOL(sasrt_renut_texture_signs, true, "SASRT",\n'),
    ('render/draw.cpp',
     '    const StreamSource src = GetStreamSource(device, call, vs, shader_strides, stream);\n'
     '    // A zero stride repeats one vertex for every index.\n',
     '    const StreamSource src = GetStreamSource(device, call, vs, shader_strides, stream);\n'
     '    if (static const bool sasrt_layout_log = REXCVAR_GET(sasrt_renut_diag_layout_log); sasrt_layout_log) {\n'
     '      if (stream == 0) {\n'
     '        ++g_sasrt_draw_seq;\n'
     '        static uint32_t logged_reads = 0;\n'
     '        const u32 rgpu = device.VertexFetchWord(d3d::kFirstVertexFetchIndex + d3d::StreamFetchIndex(0), 0) & ~3u;\n'
     '        if (g_stream_cache_frame >= 3000 && logged_reads < 400 && src.stride == 12 && (rgpu >> 24) == 0x16) {\n'
     '          ++logged_reads;\n'
     '          RGPU_INFO("[sasrt] order read frame {} draw {} vs {:016X} base {:08X} recorded {}", g_stream_cache_frame,\n'
     '                    g_sasrt_draw_seq, vs.hash, rgpu, g_sasrt_draw_recorded);\n'
     '        }\n'
     '      }\n'
     '      if ((src.stride && src.vertex_count && g.first_vertex + g.vertex_range > src.vertex_count) ||\n'
     '          call.count == 33942) {\n'
     '        static uint32_t short_logged = 0;  // sasrt-nx (diag): a stream shorter than the draw\'s vertex range\n'
     '        if (short_logged++ < 40 || (call.count == 33942 && short_logged < 400))\n'
     '          RGPU_INFO("[sasrt] layout short stream: vs {:016X} stream {} stride {} (shader {}, device {}, bound {}) "\n'
     '                    "holds {} vertices, the draw reads {}..{} (prim {} count {})", vs.hash, stream, src.stride,\n'
     '                    shader_strides ? shader_strides[stream] : 0u,\n'
     '                    u32(device.U8(d3d::kDeviceOffsetStreamStrides + stream)) * 4, vs.bound_strides[stream],\n'
     '                    src.vertex_count, g.first_vertex, g.first_vertex + g.vertex_range, call.primitive, call.count);\n'
     '      }\n'
     '      static std::unordered_map<uint64_t, uint32_t> seen;  // sasrt-nx (diag): streams logged per shader\n'
     '      uint32_t &mask = seen[vs.hash];\n'
     '      if (!(mask & (1u << stream))) {\n'
     '        mask |= 1u << stream;\n'
     '        std::string elements;\n'
     '        for (const HostVertexElement &e : hs.elements)\n'
     '          elements += fmt::format(" [g{} h{} fmt {}{}{} {} swz {}{}{}{}]", e.guest_offset, e.host_offset,\n'
     '                                  e.type.format, e.type.is_signed ? "s" : "", e.type.is_integer ? "i" : "",\n'
     '                                  e.conversion == ElementConversion::ExpandFloat ? "expand" : "copy",\n'
     '                                  e.type.swizzle[0], e.type.swizzle[1], e.type.swizzle[2], e.type.swizzle[3]);\n'
     '        RGPU_INFO("[sasrt] layout vs {:016X} stream {}: stride {} (shader {}, device {}, bound {}, fetch {}) "\n'
     '                  "host stride {} cpu {:08X} vertices {} endian {} elements{}",\n'
     '                  vs.hash, stream, src.stride, shader_strides ? shader_strides[stream] : 0u,\n'
     '                  u32(device.U8(d3d::kDeviceOffsetStreamStrides + stream)) * 4, vs.bound_strides[stream],\n'
     '                  vs.fetch_strides[stream], hs.host_stride, src.cpu_address, src.vertex_count, src.endian,\n'
     '                  elements);\n'
     '      }\n'
     '      // The guest positions of a float3 stream 0, over the draw\'s vertex range: how many are exactly (0,0,0) or\n'
     '      // (1,0,0), or beyond 1000 (the octopus\'s RenderDoc capture: a tenth of its positions so).\n'
     '      if (stream == 0 && src.stride == 12 && src.data && g.vertex_range && g.first_vertex < src.vertex_count) {\n'
     '        struct Stats { uint64_t draws = 0, vertices = 0, zero = 0, unit = 0, huge = 0; uint32_t cpu = 0; };\n'
     '        static std::unordered_map<uint64_t, Stats> stats;\n'
     '        static uint64_t calls = 0;\n'
     '        Stats &st = stats[vs.hash];\n'
     '        st.cpu = src.cpu_address;\n'
     '        ++st.draws;\n'
     '        const u32 n = std::min(g.vertex_range, src.vertex_count - g.first_vertex);\n'
     '        const u8 *p = src.data + size_t(g.first_vertex) * 12;\n'
     '        for (u32 v = 0; v < n; ++v, p += 12) {\n'
     '          float f[3];\n'
     '          for (int c = 0; c < 3; ++c) {\n'
     '            uint32_t w;\n'
     '            std::memcpy(&w, p + c * 4, 4);\n'
     '            w = __builtin_bswap32(w);\n'
     '            std::memcpy(&f[c], &w, 4);\n'
     '          }\n'
     '          ++st.vertices;\n'
     '          st.zero += f[0] == 0.0f && f[1] == 0.0f && f[2] == 0.0f;\n'
     '          st.unit += f[0] == 1.0f && f[1] == 0.0f && f[2] == 0.0f;\n'
     '          st.huge += !(std::fabs(f[0]) < 1000.0f && std::fabs(f[1]) < 1000.0f && std::fabs(f[2]) < 1000.0f);\n'
     '        }\n'
     '        if (++calls % 200000 == 0) {\n'
     '          for (const auto &[hash, s] : stats) {\n'
     '            if (s.zero + s.unit + s.huge > s.vertices / 50)\n'
     '              RGPU_INFO("[sasrt] layout positions vs {:016X} cpu {:08X}: {} draws, {} vertices: {} zero, {} (1,0,0), "\n'
     '                        "{} huge", hash, s.cpu, s.draws, s.vertices, s.zero, s.unit, s.huge);\n'
     '          }\n'
     '        }\n'
     '      }\n'
     '    }\n'
     '    // A zero stride repeats one vertex for every index.\n'),
]

# sasrt-nx (2026-10-21, diagnostics with sasrt_renut_diag_layout_log): the octopus's draw (vs EE2658022B0224B0) reads
# float3 positions from guest memory of which 40-80% are (0,0,0). Every export's range is noted when it is made
# (FinishMemExportLocked); a float3 stream 0 read with a tenth or more of its positions zero is logged with its address,
# whether a pending export or its window covers it, and the last export that overlapped it.
EDITS += [
    ('render/draw.cpp',
     'uint64_t g_stream_cache_bytes = 0;\n',
     'uint64_t g_stream_cache_bytes = 0;\n'
     '// sasrt-nx (2026-10-21, sasrt_renut_diag_layout_log): every export\'s range (base -> size, frame made, count).\n'
     'struct SasrtExportSeen {\n'
     '  u32 size = 0;\n'
     '  uint64_t frame = 0, count = 0;\n'
     '};\n'
     'std::map<u32, SasrtExportSeen> g_sasrt_exports_seen;\n'
     'uint64_t g_sasrt_draw_seq = 0;  // draws bound (BindStreams), for the order log\n'),
    ('render/draw.cpp',
     '    slot.pending.push_back({streams[i].base, streams[i].size, offsets[i]});\n'
     '    MarkExportGranules(streams[i].base, streams[i].size);\n',
     '    slot.pending.push_back({streams[i].base, streams[i].size, offsets[i]});\n'
     '    MarkExportGranules(streams[i].base, streams[i].size);\n'
     '    if (static const bool sasrt_seen = REXCVAR_GET(sasrt_renut_diag_layout_log); sasrt_seen) {  // sasrt-nx (diag)\n'
     '      SasrtExportSeen &e = g_sasrt_exports_seen[streams[i].base];\n'
     '      e.size = streams[i].size;\n'
     '      e.frame = g_stream_cache_frame;\n'
     '      ++e.count;\n'
     '      static uint32_t logged_exports = 0;\n'
     '      if (g_stream_cache_frame >= 3000 && logged_exports < 400) {\n'
     '        ++logged_exports;\n'
     '        RGPU_INFO("[sasrt] order export frame {} draw {} base {:08X} size {:X} recorded {}", g_stream_cache_frame,\n'
     '                  g_sasrt_draw_seq, streams[i].base, streams[i].size, g_sasrt_draw_recorded);\n'
     '      }\n'
     '    }\n'),
    ('render/draw.cpp',
     '          st.huge += !(std::fabs(f[0]) < 1000.0f && std::fabs(f[1]) < 1000.0f && std::fabs(f[2]) < 1000.0f);\n'
     '        }\n',
     '          st.huge += !(std::fabs(f[0]) < 1000.0f && std::fabs(f[1]) < 1000.0f && std::fabs(f[2]) < 1000.0f);\n'
     '        }\n'
     '        {  // sasrt-nx: a mostly-zero read: where it comes from\n'
     '          u32 zeros = 0;\n'
     '          const u8 *q = src.data + size_t(g.first_vertex) * 12;\n'
     '          for (u32 v = 0; v < n; ++v, q += 12) {\n'
     '            uint64_t lo;\n'
     '            uint32_t hi;\n'
     '            std::memcpy(&lo, q, 8);\n'
     '            std::memcpy(&hi, q + 8, 4);\n'
     '            zeros += lo == 0 && hi == 0;\n'
     '          }\n'
     '          static std::unordered_map<uint64_t, uint32_t> logged_zero;\n'
     '          uint32_t &lz = logged_zero[vs.hash];\n'
     '          if (n >= 8 && zeros * 10 >= n && lz < 6) {\n'
     '            ++lz;\n'
     '            u32 PendingExportSlots(u32 address, u32 size);\n'
     '            bool FindExportWindow(u32 base, u32 size, u32 & slot, uint64_t & offset);\n'
     '            const u32 fetch_index = d3d::kFirstVertexFetchIndex + d3d::StreamFetchIndex(stream);\n'
     '            const u32 gpu = device.VertexFetchWord(fetch_index, 0) & ~3u;\n'
     '            const u32 fsize = device.VertexFetchWord(fetch_index, 1) & 0x3FFFFFCu;\n'
     '            u32 wslot = 0;\n'
     '            uint64_t woff = 0;\n'
     '            const u32 pend = PendingExportSlots(gpu, fsize);\n'
     '            const bool window = pend && FindExportWindow(gpu, fsize, wslot, woff);\n'
     '            std::string last = "none";\n'
     '            auto it = g_sasrt_exports_seen.upper_bound(gpu + fsize);\n'
     '            while (it != g_sasrt_exports_seen.begin()) {\n'
     '              --it;\n'
     '              if (it->first + it->second.size <= gpu)\n'
     '                continue;\n'
     '              last = fmt::format("{:08X}+{:X} made {} frames ago ({} times)", it->first, it->second.size,\n'
     '                                 g_stream_cache_frame - it->second.frame, it->second.count);\n'
     '              break;\n'
     '            }\n'
     '            RGPU_INFO("[sasrt] layout zeros vs {:016X}: {} of {} positions (0,0,0) from gpu {:08X} size {:X} first {} "\n'
     '                      "(cpu {:08X}); pending export slots {:X}, window {}; last export overlapping: {}",\n'
     '                      vs.hash, zeros, n, gpu, fsize, g.first_vertex, src.cpu_address, pend, window, last);\n'
     '          }\n'
     '        }\n'),
]

# sasrt-nx (2026-10-21, sasrt_renut_exports_held): the race's octopus (and other skinned meshes) drawn with their
# positions (0,0,0). The title device exports the skinned positions in frame F (two buffers in turn); the workers'
# recorded buffers that draw them reach the render thread at the composed buffer's submission, in frame F+1. By then
# the export has been written back (its slot's fence waited) and is no longer pending, so the draw reads guest memory,
# which the game, a frame ahead, has already cleared for its next export ([writeback] check: every export's memory is
# zero again before the next one; order log: export frame 3141 draw 1638503, read frame 3142 draw 1641286 of the same
# base, all zero). On the 360 the GPU runs the composed buffer at its submission, before the CPU clears. The export
# results are now kept on the host after their write-back, and a vertex stream inside a kept export reads them, not
# the guest memory the game may have cleared since (the GPU's data, whenever the CPU's timeline moved on).
EDITS += [
    ('render/draw.cpp',
     'REXCVAR_DEFINE_BOOL(sasrt_renut_diag_layout_log, false, "SASRT",\n',
     'REXCVAR_DEFINE_BOOL(sasrt_renut_exports_held, true, "SASRT",\n'
     '                    "Renut\'s renderer: memexport results (the GPU-skinned characters and objects) are kept on the "\n'
     '                    "host after their write-back to guest memory, and a vertex stream inside one reads them. The "\n'
     '                    "workers\' recorded draws of them replay a frame after the export, when the game has already "\n'
     '                    "cleared that memory for its next export (the race\'s octopus as straight spikes, meshes "\n'
     '                    "collapsing to a point). Off: guest memory")\n'
     '    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\n'
     'REXCVAR_DEFINE_BOOL(sasrt_renut_diag_layout_log, false, "SASRT",\n'),
    ('render/draw.cpp',
     'uint64_t g_sasrt_draw_seq = 0;  // draws bound (BindStreams), for the order log\n',
     'uint64_t g_sasrt_draw_seq = 0;  // draws bound (BindStreams), for the order log\n'
     '// sasrt-nx (2026-10-21, sasrt_renut_exports_held): written-back export results by physical base, the frame they\n'
     '// were written back, and the replaced or expired ones the pending fills may still point into (freed at the flush).\n'
     'struct SasrtHeldExport {\n'
     '  uint64_t frame = 0;\n'
     '  std::shared_ptr<std::vector<u8>> data;\n'
     '};\n'
     'std::map<u32, SasrtHeldExport> g_sasrt_held_exports;\n'
     'std::vector<std::shared_ptr<std::vector<u8>>> g_sasrt_held_retired;\n'
     'uint64_t g_sasrt_held_reads = 0, g_sasrt_held_bytes = 0;\n'
     'bool SasrtExportsHeldOn() {\n'
     '  static const bool on = REXCVAR_GET(sasrt_renut_exports_held);\n'
     '  return on;\n'
     '}\n'
     '// Keeps an export\'s results (\'size\' bytes at \'data\', physical base \'base\'), dropping kept ones it overlaps.\n'
     'void SasrtHoldExport(u32 base, const u8 *data, u32 size, uint64_t frame) {\n'
     '  if (!size || size > (8u << 20))\n'
     '    return;\n'
     '  auto it = g_sasrt_held_exports.lower_bound(base);\n'
     '  if (it != g_sasrt_held_exports.begin())\n'
     '    --it;\n'
     '  while (it != g_sasrt_held_exports.end() && it->first < base + size) {\n'
     '    if (it->first + u32(it->second.data->size()) <= base) {\n'
     '      ++it;\n'
     '      continue;\n'
     '    }\n'
     '    g_sasrt_held_retired.push_back(std::move(it->second.data));\n'
     '    it = g_sasrt_held_exports.erase(it);\n'
     '  }\n'
     '  SasrtHeldExport &h = g_sasrt_held_exports[base];\n'
     '  h.data = std::make_shared<std::vector<u8>>(data, data + size);\n'
     '  h.frame = frame;\n'
     '}\n'),
    ('render/draw.cpp',
     '  u32 cpu_address = 0;       // guest VA of data, when read through the vertex buffer\n'
     '};\n',
     '  u32 cpu_address = 0;       // guest VA of data, when read through the vertex buffer\n'
     '  bool sasrt_held = false;   // sasrt-nx (sasrt_renut_exports_held): data is a kept export\'s, not guest memory\n'
     '};\n'),
    ('render/draw.cpp',
     '  src.vertex_count = src.stride ? size / src.stride : (size ? 1 : 0);\n',
     '  // sasrt-nx (2026-10-21, sasrt_renut_exports_held): inside a written-back export: its results as the GPU made them.\n'
     '  if (gpu_address && !g_sasrt_held_exports.empty() && SasrtExportsHeldOn()) {\n'
     '    const u32 phys = gpu_address & 0x1FFFFFFFu;\n'
     '    auto it = g_sasrt_held_exports.upper_bound(phys);\n'
     '    if (it != g_sasrt_held_exports.begin()) {\n'
     '      --it;\n'
     '      const size_t held = it->second.data->size(), off = phys - it->first;\n'
     '      if (off < held && size <= held - off) {\n'
     '        src.data = it->second.data->data() + off;\n'
     '        src.sasrt_held = true;\n'
     '        ++g_sasrt_held_reads;\n'
     '      }\n'
     '    }\n'
     '  }\n'
     '  src.vertex_count = src.stride ? size / src.stride : (size ? 1 : 0);\n'),
    ('render/draw.cpp',
     '    if (queued && src.stride) {\n'
     '      cached = &g_stream_memo.Get(g_stream_cache, key, true)->second;\n',
     '    if (queued && src.stride && !src.sasrt_held) {  // sasrt-nx: a kept export\'s copy is not cached\n'
     '      cached = &g_stream_memo.Get(g_stream_cache, key, true)->second;\n'),
    ('render/draw.cpp',
     '      if (u8 *guest = GuestPhysicalPtr<u8>(p.base)) {\n'
     '        std::memcpy(guest, data + p.offset, p.size);\n',
     '      if (SasrtExportsHeldOn())  // sasrt-nx (2026-10-21, sasrt_renut_exports_held)\n'
     '        SasrtHoldExport(p.base & 0x1FFFFFFFu, data + p.offset, p.size, g_stream_cache_frame);\n'
     '      if (u8 *guest = GuestPhysicalPtr<u8>(p.base)) {\n'
     '        std::memcpy(guest, data + p.offset, p.size);\n'),
    ('render/draw.cpp',
     '  SasrtReleaseStreamCopies();  // sasrt-nx (2026-10-21, sasrt_renut_capture_recorded_streams)\n',
     '  SasrtReleaseStreamCopies();  // sasrt-nx (2026-10-21, sasrt_renut_capture_recorded_streams)\n'
     '  g_sasrt_held_retired.clear();  // sasrt-nx (2026-10-21, sasrt_renut_exports_held): no fill points into them now\n'),
    ('render/draw.cpp',
     '  if (++g_stream_cache_frame % 60)\n'
     '    return;\n',
     '  // sasrt-nx (2026-10-21, sasrt_renut_exports_held): kept exports four frames old go (the game exports its\n'
     '  // skinned meshes every frame, in two buffers by turns).\n'
     '  for (auto it = g_sasrt_held_exports.begin(); it != g_sasrt_held_exports.end();) {\n'
     '    if (g_stream_cache_frame - it->second.frame > 4) {\n'
     '      g_sasrt_held_retired.push_back(std::move(it->second.data));\n'
     '      it = g_sasrt_held_exports.erase(it);\n'
     '    } else {\n'
     '      ++it;\n'
     '    }\n'
     '  }\n'
     '  if (g_sasrt_held_reads && SasrtExportsHeldOn() && g_stream_cache_frame % 300 == 0) {\n'
     '    RGPU_INFO("[sasrt] vertex streams read from kept export results (sasrt_renut_exports_held): {} in 300 frames; "\n'
     '              "{} exports kept", g_sasrt_held_reads, g_sasrt_held_exports.size());\n'
     '    g_sasrt_held_reads = 0;\n'
     '  }\n'
     '  if (++g_stream_cache_frame % 60)\n'
     '    return;\n'),
]

# sasrt-nx (2026-10-21, diagnostics with sasrt_renut_diag_layout_log): the octopus's skinning export (0x63708 bytes,
# 33942 float3) gives straight tentacles: what its export draw runs over (shader, primitive, vertices or indices).
EDITS += [
    ('render/draw.cpp',
     '  if (export_count) {\n'
     '    FinishMemExportLocked(s, exports, export_count, export_offsets);\n',
     '  if (export_count) {\n'
     '    if (static const bool sasrt_xlog = REXCVAR_GET(sasrt_renut_diag_layout_log); sasrt_xlog) {  // sasrt-nx (diag)\n'
     '      static std::unordered_map<uint64_t, uint32_t> logged_vs;\n'
     '      static uint32_t logged_big = 0;\n'
     '      bool big = false;\n'
     '      for (u32 i = 0; i < export_count; ++i)\n'
     '        big |= exports[i].size >= 0x10000;\n'
     '      if (logged_vs[vs->hash]++ < 3 || (big && logged_big++ < 12)) {\n'
     '        std::string ranges;\n'
     '        for (u32 i = 0; i < export_count; ++i)\n'
     '          ranges += fmt::format(" {:08X}+{:X} fmt {}", exports[i].base, exports[i].size, exports[i].format);\n'
     '        RGPU_INFO("[sasrt] export draw vs {:016X} ps {:016X}: prim {} indexed {} count {} start {} base_vertex {}; "\n'
     '                  "host {} {} first_vertex {} vertex_range {} instances {}; exports{}",\n'
     '                  vs->hash, ps ? ps->hash : 0, call.primitive, call.indexed, call.count,\n'
     '                  call.indexed ? call.start_index : call.start_vertex, call.base_vertex,\n'
     '                  geometry.indexed ? "indices" : "vertices",\n'
     '                  geometry.indexed ? geometry.index_count : geometry.vertex_count, geometry.first_vertex,\n'
     '                  geometry.vertex_range, geometry.instance_count, ranges);\n'
     '      }\n'
     '    }\n'
     '    FinishMemExportLocked(s, exports, export_count, export_offsets);\n'),
]

# sasrt-nx (2026-10-21, diagnostics with sasrt_renut_diag_layout_log): the octopus's skinning export (vs D80AC...,
# 33942 points) takes its input streams from the GPU conversion of export windows: which windows, for which input.
EDITS += [
    ('render/draw.cpp',
     '    if (gpu_streams.bytes[stream]) {\n',
     '    if (gpu_streams.bytes[stream]) {\n'
     '      if (static const bool sasrt_glog = REXCVAR_GET(sasrt_renut_diag_layout_log); sasrt_glog && false) {\n'
     '        static uint32_t glogged = 0;\n'
     '        if (glogged < 60 && (call.count == 33942 || glogged < 20)) {\n'
     '          ++glogged;\n'
     '          const u32 fi = d3d::kFirstVertexFetchIndex + d3d::StreamFetchIndex(stream);\n'
     '          RGPU_INFO("[sasrt] layout gpu stream: vs {:016X} stream {} fetch {:08X} size {:X} -> {} host bytes "\n'
     '                    "(prim {} count {}); last export overlapping it: {}", vs.hash, stream,\n'
     '                    device.VertexFetchWord(fi, 0) & ~3u, device.VertexFetchWord(fi, 1) & 0x3FFFFFCu,\n'
     '                    gpu_streams.bytes[stream], call.primitive, call.count,\n'
     '                    [&] {\n'
     '                      const u32 b = device.VertexFetchWord(fi, 0) & ~3u & 0x1FFFFFFFu;\n'
     '                      auto it = g_sasrt_exports_seen.upper_bound(b + (device.VertexFetchWord(fi, 1) & 0x3FFFFFCu));\n'
     '                      while (it != g_sasrt_exports_seen.begin()) {\n'
     '                        --it;\n'
     '                        if (it->first + it->second.size <= b)\n'
     '                          continue;\n'
     '                        return fmt::format("{:08X}+{:X}", it->first, it->second.size);\n'
     '                      }\n'
     '                      return std::string("none");\n'
     '                    }());\n'
     '        }\n'
     '      }\n'),
    ('render/draw.cpp',
     '  if (!BindStreams(device, call, *vs, shader_strides, declaration->layout,\n',
     '  if (static const bool sasrt_dlog = REXCVAR_GET(sasrt_renut_diag_layout_log); sasrt_dlog && call.count == 33942) {\n'
     '    static std::unordered_map<uint64_t, uint32_t> dlogged;  // sasrt-nx (diag): the octopus\'s draws\' layouts\n'
     '    if (dlogged[vs->hash]++ < 2) {\n'
     '      std::string streams;\n'
     '      for (u32 st = 0; st < kMaxVertexStreams; ++st) {\n'
     '        const HostVertexStream &h = declaration->layout.streams[st];\n'
     '        if (!h.used)\n'
     '          continue;\n'
     '        const u32 fi = d3d::kFirstVertexFetchIndex + d3d::StreamFetchIndex(st);\n'
     '        streams += fmt::format(" [stream {} host stride {} elements {} shader stride {} fetch {:08X} size {:X}]", st,\n'
     '                               h.host_stride, h.elements.size(), shader_strides ? shader_strides[st] : 0u,\n'
     '                               device.VertexFetchWord(fi, 0) & ~3u, device.VertexFetchWord(fi, 1) & 0x3FFFFFCu);\n'
     '      }\n'
     '      {  // the largest bone index in stream 3 (UBYTE4) against the palette (stream 5) the fetch constant declares\n'
     '        const u32 f3 = d3d::kFirstVertexFetchIndex + d3d::StreamFetchIndex(3);\n'
     '        const u32 f5 = d3d::kFirstVertexFetchIndex + d3d::StreamFetchIndex(5);\n'
     '        const u32 s3 = device.VertexFetchWord(f3, 1) & 0x3FFFFFCu;\n'
     '        const u8 *p3 = GuestPhysicalPtr<const u8>(device.VertexFetchWord(f3, 0) & ~3u);\n'
     '        u32 max_index = 0;\n'
     '        for (u32 i = 0; p3 && i < s3; ++i)\n'
     '          max_index = std::max<u32>(max_index, p3[i]);\n'
     '        const u32 pb = device.VertexFetchWord(f5, 0) & ~3u, ps5 = device.VertexFetchWord(f5, 1) & 0x3FFFFFCu;\n'
     '        u32 pzero = 0;\n'
     '        if (const u8 *pp = GuestPhysicalPtr<const u8>(pb))\n'
     '          for (u32 i = 0; i < ps5; i += 4)\n'
     '            pzero += pp[i] == 0 && pp[i + 1] == 0 && pp[i + 2] == 0 && pp[i + 3] == 0;\n'
     '        std::string pexp = "none";\n'
     '        for (auto it = g_sasrt_exports_seen.begin(); it != g_sasrt_exports_seen.end(); ++it)\n'
     '          if (it->first < (pb & 0x1FFFFFFFu) + ps5 && (pb & 0x1FFFFFFFu) < it->first + it->second.size)\n'
     '            pexp = fmt::format("{:08X}+{:X} made {} frames ago", it->first, it->second.size,\n'
     '                               g_stream_cache_frame - it->second.frame);\n'
     '        if (const u8 *pp = GuestPhysicalPtr<const u8>(pb)) {\n'
     '          for (u32 bone : {0u, 22u, 23u, 24u, 70u}) {\n'
     '            float m[16];\n'
     '            for (u32 k = 0; k < 16; ++k) {\n'
     '              uint32_t w;\n'
     '              std::memcpy(&w, pp + bone * 64 + k * 4, 4);\n'
     '              w = __builtin_bswap32(w);\n'
     '              std::memcpy(&m[k], &w, 4);\n'
     '            }\n'
     '            RGPU_INFO("[sasrt] layout octopus bone {}: {:.3g} {:.3g} {:.3g} {:.3g} | {:.3g} {:.3g} {:.3g} {:.3g} | "\n'
     '                      "{:.3g} {:.3g} {:.3g} {:.3g} | {:.3g} {:.3g} {:.3g} {:.3g}", bone, m[0], m[1], m[2], m[3], m[4],\n'
     '                      m[5], m[6], m[7], m[8], m[9], m[10], m[11], m[12], m[13], m[14], m[15]);\n'
     '          }\n'
     '        }\n'
     '        RGPU_INFO("[sasrt] layout octopus bones: largest index {} (needs {:X} bytes of palette), palette fetch "\n'
     '                  "{:08X} size {:X} ({} bones): {} of {} words zero; export over it: {}",\n'
     '                  max_index, (max_index + 1) * 64, pb, ps5, ps5 / 64, pzero, ps5 / 4, pexp);\n'
     '      }\n'
     '      RGPU_INFO("[sasrt] layout octopus export: vs {:016X} object {:08X} device declaration {:08X} declaration {} "\n'
     '                "bound {} used mask {:X}; gpu streams{}{}",\n'
     '                vs->hash, vs_va, declaration_va, fmt::ptr(declaration), vs->bound_declaration ? "yes" : "no",\n'
     '                declaration->layout.used_mask,\n'
     '                [&] { std::string g; for (u32 st = 0; st < kMaxVertexStreams; ++st) if (gpu_streams.bytes[st]) g += fmt::format(" {}", st); return g.empty() ? std::string(" none") : g; }(),\n'
     '                streams);\n'
     '    }\n'
     '  }\n'
     '  if (!BindStreams(device, call, *vs, shader_strides, declaration->layout,\n'),
]

# sasrt-nx (2026-10-21, a test, sasrt_renut_test_keep_swapped_halves): the octopus's skinning shader pairs its
# BLENDWEIGHT components with BLENDINDICES as (x-z, y-w, z-x, w-y): right only for the weights in the order the
# stream's 8in32 fetch leaves FLOAT16 data (each pair exchanged); the CPU conversion swaps the pairs back (the bound
# swizzle 1032, UnswapHalves), and the same shader applies .yxwz to its NORMAL itself.
EDITS += [
    ('render/vertex_format.cpp',
     '    host.swap_halves = UnswapHalves(copy_type, info.components);\n',
     '    host.swap_halves = UnswapHalves(copy_type, info.components);\n'
     '    if (static const bool sasrt_keep = REXCVAR_GET(sasrt_renut_test_keep_swapped_halves); sasrt_keep)\n'
     '      host.swap_halves = false;  // sasrt-nx (a test): the pairs as the 8in32 fetch leaves them\n'),
]

# sasrt-nx (2026-10-21, sasrt_renut_baked_fetches): the race's octopus (and two other meshes of the first race stretch)
# drawn with long spikes. Its skinning shader (vs 3CBD81B71CF37791) was dumped as D3DVertexShader_Bind left it: its
# vfetches name their formats and strides (k16_16_16_16_FLOAT, stride 2 dwords), and their destination swizzles hold
# the bind's pair exchange for 8in16 data under the stream's 8in32 swap (BLENDWEIGHT and NORMAL read .yxwz). The CPU
# conversion swapped the pairs back as well (the bound swizzle 1032, UnswapHalves): twice, so the weights met the
# wrong bone indices. The shader package's inputs split cleanly: 1118 name a format and a stride (bound when dumped,
# none read through vfetchBound), 889 name neither (the bind is emulated here: BoundDeclType). Every 16-bit float
# input of a bound one reads a pair-exchanged swizzle (.yx, .yxw, .yxwz). So for a shader's bound inputs, an 8in16
# element is converted as the 8in32 fetch leaves it: the declaration as those shaders read it is built once per
# declaration and set of bound locations, with the same host formats (the same input layout and pipelines) and its
# own stream cache key.
EDITS += [
    ('guest/resources.h',
     '  uint64_t layout_hash = 0;  // identifies the host input layout for pipeline keys\n',
     '  uint64_t layout_hash = 0;  // identifies the host input layout for pipeline keys\n'
     '  // sasrt-nx (2026-10-21, sasrt_renut_baked_fetches): the input locations of the elements with 8in16 data\n'
     '  // (FLOAT16, SHORT: their pairs swapped back on the CPU), and this declaration as vertex shaders whose fetches\n'
     '  // D3DVertexShader_Bind already patched read it, by those shaders\' bound locations (SasrtBakedDeclarationLocked;\n'
     '  // render thread). stream_salt: the converted streams\' cache key apart from this layout\'s (0 for the original).\n'
     '  mutable u32 sasrt_pair_locations = 0;\n'
     '  mutable bool sasrt_pairs_known = false;\n'
     '  mutable std::vector<std::pair<u32, std::shared_ptr<VertexDeclarationRecord>>> sasrt_baked;  // copies share\n'
     '  uint64_t sasrt_stream_salt = 0;\n'),
    ('guest/resources.h',
     '  bool fetch_declaration_built = false;\n',
     '  bool fetch_declaration_built = false;\n'
     '  // sasrt-nx (2026-10-21, sasrt_renut_baked_fetches): the input locations whose vfetch names a format and a stride\n'
     '  // (the shader was dumped bound: the bind\'s swizzle for the stream\'s 8in32 swap is in its microcode). Built on\n'
     '  // first use.\n'
     '  u32 sasrt_baked_locations = 0;\n'
     '  bool sasrt_baked_known = false;\n'),
    ('render/vertex_format.h',
     'u32 BoundDeclType(u32 type);\n',
     'u32 BoundDeclType(u32 type);\n'
     '\n'
     '// sasrt-nx (2026-10-21, sasrt_renut_baked_fetches): the host input location of a usage and index, as the layouts\n'
     '// place them; false for one no shader declares.\n'
     'bool SasrtInputLocation(u8 usage, u8 usage_index, u32 &location);\n'),
    ('render/vertex_format.cpp',
     '} // namespace\n'
     '\n'
     'u32 BoundDeclType(u32 type) {\n',
     '} // namespace\n'
     '\n'
     'bool SasrtInputLocation(u8 usage, u8 usage_index, u32 &location) {  // sasrt-nx (sasrt_renut_baked_fetches)\n'
     '  return InputLocation(usage, usage_index, location);\n'
     '}\n'
     '\n'
     'u32 BoundDeclType(u32 type) {\n'),
    ('render/draw.cpp',
     'REXCVAR_DEFINE_BOOL(sasrt_renut_exports_held, true, "SASRT",\n',
     'REXCVAR_DEFINE_BOOL(sasrt_renut_baked_fetches, true, "SASRT",\n'
     '                    "Renut\'s renderer: a vertex shader dumped as D3DVertexShader_Bind left it (its vfetches name "\n'
     '                    "their formats, their swizzles already exchange the pairs of 16-bit data) reads its FLOAT16 "\n'
     '                    "and SHORT elements as the stream\'s 8in32 fetch leaves them, not swapped back on the CPU a "\n'
     '                    "second time (the race\'s octopus as spikes: its blend weights met the wrong bones). Off: "\n'
     '                    "swapped back for every shader")\n'
     '    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\n'
     'REXCVAR_DEFINE_BOOL(sasrt_renut_exports_held, true, "SASRT",\n'),
    ('render/draw.cpp',
     'bool DrawStateLocked(const u8 *device_state, const DrawCall &call, const ReplayConstants *replay) {\n',
     '// sasrt-nx (2026-10-21, sasrt_renut_baked_fetches): \'declaration\' as vertex shader \'vs\' reads it. Its 8in16\n'
     '// elements at the shader\'s bound input locations (vfetches with a format) become 8in32 ones: no bound pair\n'
     '// exchange, no swap of the halves; the same host formats. The declaration itself when none is affected.\n'
     'const VertexDeclarationRecord *SasrtBakedDeclarationLocked(ShaderRecord &vs,\n'
     '                                                           const VertexDeclarationRecord *declaration) {\n'
     '  if (!vs.sasrt_baked_known) {\n'
     '    vs.sasrt_baked_known = true;\n'
     '    const ShaderVertexInput *inputs = g_shaderVertexInputs + vs.entry->vertexInputOffset;\n'
     '    for (u32 i = 0; i < vs.entry->vertexInputCount; ++i) {\n'
     '      u32 location;\n'
     '      if (inputs[i].format && SasrtInputLocation(inputs[i].usage, inputs[i].usageIndex, location) && location < 32)\n'
     '        vs.sasrt_baked_locations |= 1u << location;\n'
     '    }\n'
     '  }\n'
     '  if (!vs.sasrt_baked_locations)\n'
     '    return declaration;\n'
     '  if (!declaration->sasrt_pairs_known) {\n'
     '    declaration->sasrt_pairs_known = true;\n'
     '    for (const GuestVertexElement &e : declaration->elements) {\n'
     '      u32 location;\n'
     '      if (((u32(e.Type) >> 6) & 3) == 1 && SasrtInputLocation(e.Usage, e.UsageIndex, location) && location < 32)\n'
     '        declaration->sasrt_pair_locations |= 1u << location;\n'
     '    }\n'
     '  }\n'
     '  const u32 mask = vs.sasrt_baked_locations & declaration->sasrt_pair_locations;\n'
     '  if (!mask)\n'
     '    return declaration;\n'
     '  for (const auto &[m, baked] : declaration->sasrt_baked)\n'
     '    if (m == mask)\n'
     '      return baked.get();\n'
     '  auto baked = std::make_shared<VertexDeclarationRecord>();\n'
     '  baked->x360 = declaration->x360;\n'
     '  baked->self_va = declaration->self_va;\n'
     '  baked->elements = declaration->elements;\n'
     '  for (GuestVertexElement &e : baked->elements) {\n'
     '    u32 location;\n'
     '    if (((u32(e.Type) >> 6) & 3) == 1 && SasrtInputLocation(e.Usage, e.UsageIndex, location) && location < 32 &&\n'
     '        (mask & (1u << location)))\n'
     '      e.Type = (u32(e.Type) & ~0xC0u) | 0x80u;  // 8in32: the data as the stream\'s fetch swaps it\n'
     '  }\n'
     '  BuildDeclarationLayout(*baked);\n'
     '  baked->sasrt_stream_salt = (uint64_t(mask) << 32 | 0x5A5Bu) * 0x9E3779B97F4A7C15ull;\n'
     '  static uint32_t logged = 0;\n'
     '  if (LogLimited(logged, 24))\n'
     '    RGPU_INFO("[sasrt] baked fetches: vs {:016X} reads declaration {:08X} with its 8in16 elements at locations {:X} "\n'
     '              "as fetched (host layout {})", vs.hash, declaration->self_va, mask,\n'
     '              baked->layout_hash == declaration->layout_hash ? "the same" : "different");\n'
     '  declaration->sasrt_baked.emplace_back(mask, std::move(baked));\n'
     '  return declaration->sasrt_baked.back().second.get();\n'
     '}\n'
     '\n'
     'bool DrawStateLocked(const u8 *device_state, const DrawCall &call, const ReplayConstants *replay) {\n'),
    ('render/draw.cpp',
     '    return false;\n'
     '  }\n'
     '  // Earlier memexport results reach guest memory before this draw reads them\n',
     '    return false;\n'
     '  }\n'
     '  if (static const bool sasrt_baked = REXCVAR_GET(sasrt_renut_baked_fetches); sasrt_baked && vs->entry)\n'
     '    declaration = SasrtBakedDeclarationLocked(*vs, declaration);  // sasrt-nx (2026-10-21)\n'
     '  // Earlier memexport results reach guest memory before this draw reads them\n'),
    ('render/draw.cpp',
     '                   declaration->layout_hash, geometry, gpu_streams)) {\n',
     '                   declaration->layout_hash ^ declaration->sasrt_stream_salt, geometry, gpu_streams)) {\n'),
]

# sasrt-nx (2026-10-21, sasrt_display_gamma): the user's console runs look blown out in the sunlit stretches. The
# frames match the emulated GPU's (PC, matched frames: mean luma 131.4 / 129.8, blown-out pixels 2.16 / 2.27 %); this
# game's display gamma ramp is the identity (SA2's is not: sa2_renut_gamma_ramp), so the look is the game's own. As
# UnleashedRecomp's brightness and Xbox colour correction options, an exponent on the scan-out ramp lets the player darken
# the midtones (black and white stay): 1.0 leaves the frame as it is.
EDITS += [
    ('backend/present.cpp',
     'REXCVAR_DEFINE_BOOL(renut_vsync, true, "Nuts&Bolts/Graphics",\n',
     'REXCVAR_DEFINE_DOUBLE(sasrt_display_gamma, 1.0, "SASRT",\n'
     '                      "Display: an exponent on every colour at scan-out (with the game\'s gamma ramp, "\n'
     '                      "sa2_renut_gamma_ramp): above 1 darkens the midtones (1.15 or so for a less washed-out "\n'
     '                      "look in the sunlit stretches), below 1 lightens them; black and white stay. 1.0: the frame "\n'
     '                      "as the game made it")\n'
     '    .range(0.5, 2.0)\n'
     '    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\n'
     'REXCVAR_DEFINE_BOOL(renut_vsync, true, "Nuts&Bolts/Graphics",\n'),
    ('backend/present.cpp',
     '        g.texels[i * 4 + c] = float(value) / 1023.0f;\n',
     '        g.texels[i * 4 + c] = float(value) / 1023.0f;\n'
     '        if (static const double sasrt_gamma = REXCVAR_GET(sasrt_display_gamma); sasrt_gamma != 1.0)\n'
     '          g.texels[i * 4 + c] = float(std::pow(double(g.texels[i * 4 + c]), sasrt_gamma));  // sasrt-nx\n'),
    ('backend/present.cpp',
     '#include <chrono>\n',
     '#include <chrono>\n'
     '#include <cmath>  // sasrt-nx: sasrt_display_gamma\n'),
]

# sasrt-nx (2026-10-21, diagnostics, sasrt_renut_diag_ps_constants): the respawn effect's particles (RenderDoc of the PC:
# pixel shaders of the 2B4BE79A788DA9F0 family, event 5733) read their constants as zeros (g_ParticleColourMul c12,
# g_ParticleColourAdd c11) and 0x00000002 (gITMGF c146, gFogColour c148): drawn as a dark cloud. For the listed pixel
# shaders, the first 200 draws: the way the draw came (a worker's recorded buffer or the title device), the constant
# groups the draw has of its own, and the registers it reads, each from where the draw takes it.
EDITS += [
    ('render/draw.cpp',
     'REXCVAR_DEFINE_BOOL(sasrt_renut_exports_held, true, "SASRT",\n',
     'REXCVAR_DEFINE_STRING(sasrt_renut_diag_ps_constants, "", "SASRT",\n'
     '                      "Diagnostics: pixel shader hashes (hex, comma-separated) whose draws log their constants "\n'
     '                      "c0-c7, c10-c15, c142-c151, c254 and where each comes from (their own recorded state or the running "\n'
     '                      "device), and whether the draw is a worker\'s recorded one (the first 200 draws)")\n'
     '    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\n'
     'REXCVAR_DEFINE_BOOL(sasrt_renut_exports_held, true, "SASRT",\n'),
    ('render/draw.cpp',
     '  const FloatConstants ps_constants = DrawFloatConstants(device_state, replay, true);\n',
     '  const FloatConstants ps_constants = DrawFloatConstants(device_state, replay, true);\n'
     '  // sasrt-nx (2026-10-21, diagnostics, sasrt_renut_diag_ps_constants)\n'
     '  if (static const std::vector<uint64_t> sasrt_watch = [] {\n'
     '        std::vector<uint64_t> out;\n'
     '        const std::string list = REXCVAR_GET(sasrt_renut_diag_ps_constants);\n'
     '        for (size_t at = 0; at < list.size();) {\n'
     '          const size_t comma = std::min(list.find(\',\', at), list.size());\n'
     '          if (comma > at)\n'
     '            out.push_back(std::strtoull(list.substr(at, comma - at).c_str(), nullptr, 16));\n'
     '          at = comma + 1;\n'
     '        }\n'
     '        return out;\n'
     '      }();\n'
     '      !sasrt_watch.empty() && ps && ps->entry &&\n'
     '      std::find(sasrt_watch.begin(), sasrt_watch.end(), ps->entry->hash) != sasrt_watch.end()) {\n'
     '    static uint32_t logged = 0, seen = 0;\n'
     '    const u8 *c12 = ps_constants.Register(12);\n'
     '    const bool zero12 = std::all_of(c12, c12 + 16, [](u8 b) { return b == 0; });\n'
     '    if (logged < 200 && (seen++ < 20 || zero12)) {\n'
     '      ++logged;\n'
     '      std::string regs;\n'
     '      // 2026-10-30: c0-c7, c142-c146 and c254 too (Ristar at the race start, ps 21601CF1FD53537E).\n'
     '      for (u32 r : {0u, 1u, 2u, 3u, 5u, 6u, 7u, 10u, 11u, 12u, 15u, 142u, 143u, 144u, 145u, 146u, 148u, 254u}) {\n'
     '        const u8 *p = ps_constants.Register(r);\n'
     '        float v[4];\n'
     '        for (u32 k = 0; k < 4; ++k) {\n'
     '          u32 w;\n'
     '          std::memcpy(&w, p + k * 4, 4);\n'
     '          w = __builtin_bswap32(w);\n'
     '          std::memcpy(&v[k], &w, 4);\n'
     '        }\n'
     '        const bool own = !ps_constants.running || ((ps_constants.set >> (63 - r / 4)) & 1);\n'
     '        regs += fmt::format(" c{}{} ({:.3g} {:.3g} {:.3g} {:.3g})", r, own ? "" : "*", v[0], v[1], v[2], v[3]);\n'
     '      }\n'
     '      RGPU_INFO("[sasrt] ps {:016X} draw {}: recorded {}, up {}, count {}, own pixel groups {:016X};{} (* from the "\n'
     '                "running device)", ps->entry->hash, g_sasrt_draw_seq, replay != nullptr, call.up_vertices != nullptr,\n'
     '                call.count, ps_constants.set, regs);\n'
     '    }\n'
     '  }\n'),
]

# sasrt-nx (2026-10-21 16:20, sasrt_renut_frames_ahead; the user's console run with sasrt_renut_diag_no_frames_ahead):
# with the game one frame ahead of the render thread (Renut's default), the console's race ran at 16-18 fps with the
# render thread busy 38-44 ms a frame and 4.2-4.9 GB of upload churn per 10 s, and skinned meshes and whole objects
# exploded now and then (data the game rewrote before the render thread read it). With the game waiting at its Swap
# until the render thread has done the frame: 30 fps, 0 frames late, the render thread 16-22 ms, about 0.6 GB of
# churn, input to screen 24 ms (78 before), and most of the explosions gone (the user). The late reads made work (stale
# copies converted again, uploads redone) that made the render thread later still. As MarathonRecomp-NX's Present,
# which waits until the render thread has recorded the frame. app/sasrt_switch.toml sets 0; the PC keeps 1.
EDITS += [
    ('backend/render_thread.cpp',
     'REXCVAR_DEFINE_BOOL(sasrt_renut_diag_no_frames_ahead, false, "SASRT",\n',
     'REXCVAR_DEFINE_INT32(sasrt_renut_frames_ahead, 1, "SASRT",\n'
     '                     "Renut\'s renderer: how many frames the game may run ahead of the render thread. 0: the "\n'
     '                     "game waits at its Swap until the render thread has done the frame (the console: 30 fps "\n'
     '                     "instead of 16-18 and no late reads; app/sasrt_switch.toml), 1: one frame ahead (the PC)")\n'
     '    .range(0, 1)\n'
     '    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\n'
     'REXCVAR_DEFINE_BOOL(sasrt_renut_diag_no_frames_ahead, false, "SASRT",\n'),
    ('backend/render_thread.cpp',
     '    static const uint64_t ahead = REXCVAR_GET(sasrt_renut_diag_no_frames_ahead) ? 0 : kMaxFramesAhead;  // sasrt-nx\n',
     '    static const uint64_t ahead = REXCVAR_GET(sasrt_renut_diag_no_frames_ahead)\n'
     '                                      ? 0\n'
     '                                      : std::min<uint64_t>(uint64_t(REXCVAR_GET(sasrt_renut_frames_ahead)),\n'
     '                                                           kMaxFramesAhead);  // sasrt-nx\n'),
]

# sasrt-nx (2026-10-21 18:30, sasrt_deko3d_depth_resolve; the console's flickering, black-shadowed ground): the shadow
# maps are drawn into a 1024x1024 depth target (three cascades a frame) and copied by a draw into one 1024x3072 float
# texture the scene samples. banjo-nx's banjo_deko3d_depth_compression gives depth targets the GPU's hardware
# compression, and nothing decompressed them before they were read: Maxwell's texture unit cannot read compressed depth
# tiles (deko3d's dkCmdBufResolveDepthValues, Maxwell's DECOMPRESS_ZETA_SURFACE, exists for that), so a cascade read
# garbage where its tiles were compressed (flat ground seen from the sun compresses best): the ground under it black
# with specks, a straight edge where the cascade ends, coming and going as the camera moved; the characters' own shadow
# map the same (the driver a black ball). Ryujinx emulates no compression, so only the console showed it, with or
# without the deko3d shader passes. plume's deko3d back end now decompresses a compressed depth target before it is
# read (Deko3DOptions::depthResolve).
EDITS += [
    ('banjo_renut_tuning.cpp',
     'REXCVAR_DEFINE_BOOL(banjo_deko3d_alpha_spec, false, "Banjo/Enhancements",  // sasrt-nx: off, as sa2-nx\n',
     'REXCVAR_DEFINE_BOOL(sasrt_deko3d_depth_resolve, true, "SASRT",\n'
     '                    "deko3d renderer: a depth target with hardware compression (banjo_deko3d_depth_compression) "\n'
     '                    "is decompressed (dkCmdBufResolveDepthValues) before it is read as a texture or copied. Off: "\n'
     '                    "the shadow maps read compressed tiles as garbage on the console (black ground in whole "\n'
     '                    "shadow cascades, flickering as the camera moves; Ryujinx shows nothing either way)")\n'
     '    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\n'
     'REXCVAR_DEFINE_BOOL(banjo_deko3d_alpha_spec, false, "Banjo/Enhancements",  // sasrt-nx: off, as sa2-nx\n'),
    ('banjo_renut_tuning.cpp',
     'bool Deko3DZcullOn() { return REXCVAR_GET(banjo_deko3d_zcull); }\n',
     'bool Deko3DZcullOn() { return REXCVAR_GET(banjo_deko3d_zcull); }\n'
     'bool SasrtDeko3DDepthResolveOn() { return REXCVAR_GET(sasrt_deko3d_depth_resolve); }  // sasrt-nx (2026-10-21)\n'),
    ('banjo_renut_tuning.h',
     'bool Deko3DZcullOn();\n',
     'bool Deko3DZcullOn();\n'
     '// sasrt-nx (2026-10-21): sasrt_deko3d_depth_resolve (plume Deko3DOptions::depthResolve).\n'
     'bool SasrtDeko3DDepthResolveOn();\n'),
    ('banjo_renut_deko3d.cpp',
     '  options.zcull = Deko3DZcullOn();\n',
     '  options.zcull = Deko3DZcullOn();\n'
     '  options.depthResolve = SasrtDeko3DDepthResolveOn();  // sasrt-nx (2026-10-21)\n'),
    ('banjo_renut_deko3d.cpp',
     '"buffer copies, {} texture uploads, {} readbacks, {} image copies, {} resolves, {} blits",\n',
     '"buffer copies, {} texture uploads, {} readbacks, {} image copies, {} resolves, {} blits; depth targets "\n'
     '                     "decompressed before a read {} (sasrt_deko3d_depth_resolve)",\n'),
    ('banjo_renut_deko3d.cpp',
     '                     st.copyImage.load(), st.copyResolve.load(), st.copyBlit.load());\n',
     '                     st.copyImage.load(), st.copyResolve.load(), st.copyBlit.load(), st.depthResolves.load());\n'),
]

# sasrt-nx (2026-10-21 20:20, sasrt_renut_diag_dump_volumes): the race's lighting volumes (gGILight0-2: 32x8x32
# k_16_16_16_16, integer number format, exponent -10) read as UNORM give the GI nothing (the user: shadows far too
# black, on the console, Ryujinx and the PC alike, the emulated GPU too); read as integers the track went grey-blue.
# A diagnostic to decode them offline: every 3D k_16_16_16_16 texture's guest bytes (its tiled storage, 32-aligned)
# and Renut's host rows, once per address, next to the executable (volume_<address>_guest.bin / _host.bin, with the
# fetch constant in the log).
EDITS += [
    ('render/textures.cpp',
     'struct LevelSource {\n',
     '// sasrt-nx (2026-10-21, sasrt_renut_diag_dump_volumes): see the key (ReadLevel).\n'
     'REXCVAR_DEFINE_BOOL(sasrt_renut_diag_dump_volumes, false, "SASRT",\n'
     '                    "Diagnostic: write every 3D k_16_16_16_16 texture\'s guest bytes and Renut\'s host rows to "\n'
     '                    "volume_<address>_guest.bin / _host.bin next to the executable, once per address");\n'
     '\n'
     'struct LevelSource {\n'),
    ('render/textures.cpp',
     '      SwapEndian(endian, row.data(), row.data(), row.size());\n'
     '      uint8_t *out = dst + size_t(z) * dst_slice_pitch + size_t(y) * dst_row_pitch;\n'
     '      if (info.conversion == TexelConversion::Copy)\n'
     '        std::memcpy(out, row.data(), size_t(blocks_w) * hbpb);\n'
     '      else if (info.decoded_blocks)\n'
     '        DecodeBlockRow(info.conversion, row.data(), out, blocks_w, dst_row_pitch / info.block_size);\n'
     '      else\n'
     '        ConvertTexels(info.conversion, row.data(), out, blocks_w);\n'
     '    }\n'
     '  }\n'
     '}\n',
     '      SwapEndian(endian, row.data(), row.data(), row.size());\n'
     '      uint8_t *out = dst + size_t(z) * dst_slice_pitch + size_t(y) * dst_row_pitch;\n'
     '      if (info.conversion == TexelConversion::Copy)\n'
     '        std::memcpy(out, row.data(), size_t(blocks_w) * hbpb);\n'
     '      else if (info.decoded_blocks)\n'
     '        DecodeBlockRow(info.conversion, row.data(), out, blocks_w, dst_row_pitch / info.block_size);\n'
     '      else\n'
     '        ConvertTexels(info.conversion, row.data(), out, blocks_w);\n'
     '    }\n'
     '  }\n'
     '  // sasrt-nx (2026-10-21, sasrt_renut_diag_dump_volumes).\n'
     '  if (is_3d && fetch.Format() == GpuTextureFormat(26) && REXCVAR_GET(sasrt_renut_diag_dump_volumes)) {\n'
     '    static std::mutex dump_mutex;\n'
     '    static std::unordered_map<const uint8_t *, int> dumped;\n'
     '    std::lock_guard lock(dump_mutex);\n'
     '    if (dumped.size() < 32 && dumped.emplace(src.base, 1).second) {\n'
     '      const size_t guest_bytes = size_t((src.pitch_blocks + 31) & ~31u) * ((src.height_blocks + 31) & ~31u) *\n'
     '                                 ((depth + src.z_offset + 3) & ~3u) * gbpb;\n'
     '      const std::string stem = fmt::format("volume_{:08X}", uint32_t(fetch.dword[1] & 0xFFFFF000u));\n'
     '      if (FILE *f = std::fopen(banjo::renut_gpu::NextToExecutable(stem + "_guest.bin").string().c_str(), "wb")) {\n'
     '        std::fwrite(src.base, 1, guest_bytes, f);\n'
     '        std::fclose(f);\n'
     '      }\n'
     '      if (FILE *f = std::fopen(banjo::renut_gpu::NextToExecutable(stem + "_host.bin").string().c_str(), "wb")) {\n'
     '        std::fwrite(dst, 1, size_t(depth) * dst_slice_pitch, f);\n'
     '        std::fclose(f);\n'
     '      }\n'
     '      RGPU_INFO("[sasrt] volume dump {}: {}x{}x{} blocks, pitch {} height {} z {}, {} guest bytes, host row {} slice {}, "\n'
     '                "tiled {}, endian {}, fetch {:08X} {:08X} {:08X} {:08X} {:08X} {:08X}", stem, blocks_w, blocks_h, depth,\n'
     '                src.pitch_blocks, src.height_blocks, src.z_offset, guest_bytes, dst_row_pitch, dst_slice_pitch,\n'
     '                fetch.Tiled(), endian, fetch.dword[0], fetch.dword[1], fetch.dword[2], fetch.dword[3], fetch.dword[4],\n'
     '                fetch.dword[5]);\n'
     '    }\n'
     '  }\n'
     '}\n'),
]

# sasrt-nx (2026-10-21 20:50, sasrt_renut_texture_int_format on by default): the user's complaint on every renderer
# (the console, Ryujinx, the PC): the darks far too black. The race's lighting volumes (gGILight0-2: 32x8x32
# k_16_16_16_16, integer number format, exponent -10; the GI pass ps_ed0a8d53da14a749 recentres them by -32) read as
# normalized gave the GI nothing: the coefficients came out near -32 and every shadow was unlit. PS3 footage of the
# same intro flyover shows the start gate's pillars light grey stone where Renut (and the emulated GPU, which ignores
# the number format too) drew black silhouettes. Read as integers (0..64 after the exponent, as the hardware reads
# them) the shadows get their ambient light back; the user judged the result accurate (PC A/B of 2026-10-21,
# out/pc/captures video_212s on against video_210s off).
EDITS += [
    ('render/draw.cpp',
     'REXCVAR_DEFINE_BOOL(sasrt_renut_texture_int_format, false, "SASRT",\n'
     '                    "Renut\'s renderer: a 3D, cube or stacked fetch whose fetch constant asks for the integer number "\n'
     '                    "format reads a 16- or 8-bit normalized texture as its integers (0..65535, 0..255). Off (the "\n'
     '                    "default): normalized, as the emulated GPU reads it (on, this game\'s race lighting volume tints "\n'
     '                    "the track grey-blue against the emulated GPU\'s warm beige, both its paths)")\n',
     'REXCVAR_DEFINE_BOOL(sasrt_renut_texture_int_format, true, "SASRT",\n'
     '                    "Renut\'s renderer: a 3D, cube or stacked fetch whose fetch constant asks for the integer number "\n'
     '                    "format reads a 16- or 8-bit normalized texture as its integers (0..65535, 0..255), as the "\n'
     '                    "hardware does: this game\'s race lighting volumes (the GI), whose shadows were black without "\n'
     '                    "it. Off: normalized, as the emulated GPU reads it (no ambient light in the shadows)")\n'),
]

# The banjo-nx sync (2026-10-29): the entries banjo-nx 894d3256's renderer moved, re-anchored; those its own work
# replaced, dropped; this port's changes for its fast path, added (sasrt_edits_banjo_sync.py).
from sasrt_edits_banjo_sync import apply as _banjo_sync  # noqa: E402

EDITS = _banjo_sync(EDITS)

# sasrt-nx (2026-10-29, sasrt_renut_texture_memo_fetch_only): found in the banjo-nx sync's first runs. This game binds
# its textures by fetch constant alone: the device's texture slots hold no header pointer (D3D's SetTexture is not how
# its engine binds them), so banjo-nx's texture memo (keyed by the slot's header) and its record-time texture objects
# never applied: every bound slot of every draw went through BindTextureLocked (Ryujinx race: "texture slots: 0 by the
# memo, 148561 bound (100.0 %)" per 10 s). A slot without a header pointer is answered by the fetch words alone, which
# the memo already compares (with the frame, the binding epoch of the texture's pages and the depth epoch, as for one
# with a header); a zero header stands in for the guest one. sasrt_renut_texture_memo_fetch_only_verify binds every
# such memo answer again and compares the words.
EDITS += [
    ('render/draw.cpp',
     'REXCVAR_DEFINE_BOOL(sasrt_renut_texture_signs, true, "SASRT",\n',
     'REXCVAR_DEFINE_BOOL(sasrt_renut_texture_memo_fetch_only, true, "SASRT",\n'
     '                    "Renut\'s renderer (2026-10-29): a texture slot bound by its fetch constant alone (no header "\n'
     '                    "pointer in the device: how this game binds its textures) is answered by banjo-nx\'s texture "\n'
     '                    "memo, keyed by its fetch words, instead of a bind at every draw. Same words (the verify key "\n'
     '                    "below). Off: every such slot bound at every draw, as before")\n'
     '    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\n'
     'REXCVAR_DEFINE_BOOL(sasrt_renut_texture_memo_fetch_only_verify, false, "SASRT",\n'
     '                    "Renut\'s renderer (sasrt_renut_texture_memo_fetch_only): every memo answer for a slot without a "\n'
     '                    "header pointer is bound again and its words compared; the differences are counted in the "\n'
     '                    "10 s line and the first ones logged. Diagnostics: a bind a slot again")\n'
     '    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\n'
     'REXCVAR_DEFINE_BOOL(sasrt_renut_texture_signs, true, "SASRT",\n'),
    ('render/draw.cpp',
     '    const auto *header = texture_va ? GuestPtr<const d3d::BaseTexture>(texture_va) : nullptr;\n'
     '    const bool memo = banjo::renut_gpu::CpuMemosOn() && header;\n',
     '    // sasrt-nx (2026-10-29, sasrt_renut_texture_memo_fetch_only): a slot bound by its fetch constant alone is answered\n'
     '    // by its fetch words (the memo compares them); a zero header stands in for the guest one.\n'
     '    static const bool sasrt_fetch_only = REXCVAR_GET(sasrt_renut_texture_memo_fetch_only);\n'
     '    static const d3d::BaseTexture kSasrtNoHeader{};\n'
     '    const auto *header = texture_va ? GuestPtr<const d3d::BaseTexture>(texture_va)\n'
     '                         : sasrt_fetch_only ? &kSasrtNoHeader\n'
     '                                            : nullptr;\n'
     '    const bool memo = banjo::renut_gpu::CpuMemosOn() && header;\n'),
    ('render/draw.cpp',
     '      SetSlotWords(sc, r, m.dim, m.index, m.sampler);  // banjo-nx (2026-10-26): every word of the slot\n',
     '      if (!texture_va)  // sasrt-nx (2026-10-29): sasrt_renut_texture_memo_fetch_only_verify\n'
     '        SasrtVerifyFetchOnly(fetch, m.dim, m.index, m.sampler);\n'
     '      SetSlotWords(sc, r, m.dim, m.index, m.sampler);  // banjo-nx (2026-10-26): every word of the slot\n'),
    ('render/draw.cpp',
     'void BindingWords(const TextureBinding &binding, const TextureFetch &fetch, u32 &dim, u32 &index, u32 &sampler) {\n'
     '  dim = ',
     'void BindingWords(const TextureBinding &binding, const TextureFetch &fetch, u32 &dim, u32 &index, u32 &sampler);\n'
     '// sasrt-nx (2026-10-29, sasrt_renut_texture_memo_fetch_only_verify): a memo answer for a slot without a header\n'
     '// pointer against a bind now.\n'
     'uint64_t g_sasrt_fetch_only_checked = 0, g_sasrt_fetch_only_differ = 0;\n'
     'void SasrtVerifyFetchOnly(const TextureFetch &fetch, u32 dim, u32 index, u32 sampler) {\n'
     '  static const bool on = REXCVAR_GET(sasrt_renut_texture_memo_fetch_only_verify);\n'
     '  if (!on) [[likely]]\n'
     '    return;\n'
     '  BindEffects fx;\n'
     '  u32 vdim, vindex, vsampler;\n'
     '  BindingWords(BindTextureLocked(0, fetch, &fx), fetch, vdim, vindex, vsampler);\n'
     '  if ((++g_sasrt_fetch_only_checked & 0x3FFFF) == 0)\n'
     '    RGPU_INFO("[sasrt] sasrt_renut_texture_memo_fetch_only_verify: {} memo answers bound again, {} differ",\n'
     '              g_sasrt_fetch_only_checked, g_sasrt_fetch_only_differ);\n'
     '  if (vdim == dim && vindex == index && vsampler == sampler)\n'
     '    return;\n'
     '  ++g_sasrt_fetch_only_differ;\n'
     '  static uint32_t logged = 0;\n'
     '  if (logged++ < 16)\n'
     '    RGPU_WARN("sasrt_renut_texture_memo_fetch_only_verify: the memo\'s words {}/{:X}/{:X}, a bind now {}/{:X}/{:X} "\n'
     '              "(fetch {:08X} {:08X} {:08X} {:08X} {:08X} {:08X})", dim, index, sampler, vdim, vindex, vsampler,\n'
     '              fetch.dword[0], fetch.dword[1], fetch.dword[2], fetch.dword[3], fetch.dword[4], fetch.dword[5]);\n'
     '}\n'
     'void BindingWords(const TextureBinding &binding, const TextureFetch &fetch, u32 &dim, u32 &index, u32 &sampler) {\n'
     '  dim = '),
]
# (2026-10-29, the same) banjo-nx's draw paths keep a draw's texture words while each slot's header is the same
# (FastDrawLocked's kept textures, DrawStateLocked's chain reuse): a slot without a header pointer has the zero stand-in
# there too, so its kept words hold while its fetch words, the frame and the texture epochs do.
EDITS += [
    ('render/draw.cpp',
     '// sasrt-nx (2026-10-29, sasrt_renut_texture_memo_fetch_only_verify): a memo answer for a slot without a header\n',
     '// sasrt-nx (2026-10-29, sasrt_renut_texture_memo_fetch_only): a slot\'s guest header, or for a slot bound by its\n'
     '// fetch constant alone a zero header standing in for it (its answer depends on the fetch words, which every user of\n'
     '// it compares too).\n'
     'const d3d::BaseTexture *SasrtSlotHeader(u32 va) {\n'
     '  static const bool fetch_only = REXCVAR_GET(sasrt_renut_texture_memo_fetch_only);\n'
     '  static const d3d::BaseTexture kNone{};\n'
     '  return va ? GuestPtr<const d3d::BaseTexture>(va) : fetch_only ? &kNone : nullptr;\n'
     '}\n'
     '// sasrt-nx (2026-10-29, sasrt_renut_texture_memo_fetch_only_verify): a memo answer for a slot without a header\n'),
    ('render/draw.cpp',
     '      const auto *header = va ? GuestPtr<const d3d::BaseTexture>(va) : nullptr;\n'
     '      if (header)\n'
     '        std::memcpy(f.texture_header[r], &header->Format, sizeof(f.texture_header[r]));\n',
     '      const auto *header = SasrtSlotHeader(va);  // sasrt-nx (2026-10-29)\n'
     '      if (header)\n'
     '        std::memcpy(f.texture_header[r], &header->Format, sizeof(f.texture_header[r]));\n'),
    ('render/draw.cpp',
     '      const auto *header = f.texture_va[r] ? GuestPtr<const d3d::BaseTexture>(f.texture_va[r]) : nullptr;\n',
     '      const auto *header = SasrtSlotHeader(f.texture_va[r]);  // sasrt-nx (2026-10-29)\n'),
    ('render/draw.cpp',
     '    const auto *header = va ? GuestPtr<const d3d::BaseTexture>(va) : nullptr;\n'
     '    textures_reused = header &&\n',
     '    const auto *header = SasrtSlotHeader(va);  // sasrt-nx (2026-10-29)\n'
     '    textures_reused = header &&\n'),
    ('render/draw.cpp',
     '        const auto *header = va ? GuestPtr<const d3d::BaseTexture>(va) : nullptr;\n'
     '        if (header)\n'
     '          std::memcpy(treuse.header[r], &header->Format, sizeof(treuse.header[r]));\n',
     '        const auto *header = SasrtSlotHeader(va);  // sasrt-nx (2026-10-29)\n'
     '        if (header)\n'
     '          std::memcpy(treuse.header[r], &header->Format, sizeof(treuse.header[r]));\n'),
]

# sasrt-nx (2026-10-29, the race's alternate-frame far-cascade shadow flicker; console, Ryujinx and the PC at 30 fps):
# RenderDoc frames 1 and 2 of a PC race differ first in the light volume pass (the cascade spheres' stencil marks into
# the 1152x544 target, then each cascade's shading where the stencil is 1): a far pixel shaded by cascade 2 in one
# frame, by cascade 1 in the next, with the same draws and states. RenderDoc's view of the ring's constants is not
# usable there (the bound range's offset). Two diagnostics:
#   sasrt_renut_diag_constants_verify: after each draw's float constants went up (the ring upload or the pushes), the
#   model of the buffer must hold every register the shader reads (but its literal ones) with the bytes the draw's
#   constants have now: one held with other bytes is read stale by the GPU.
#   sasrt_renut_diag_light_volumes: from that game frame on, ten frames of the light volumes' draws (660 indices): the
#   spheres' transforms (vertex c0-c3), the shading pixel shader's cascade constants (c7-c24) and where each comes from.
EDITS += [
    ('render/draw.cpp',
     'REXCVAR_DEFINE_STRING(sasrt_renut_diag_ps_constants, "", "SASRT",\n',
     'REXCVAR_DEFINE_BOOL(sasrt_renut_diag_constants_verify, false, "SASRT",\n'
     '                    "Diagnostics: after each draw\'s float constants went up (the ring upload or the pushes), "\n'
     '                    "every register the shader reads (but its literal ones) is checked to be held by the "\n'
     '                    "model of the buffer with the bytes the draw\'s constants have now; the first 64 that are "\n'
     '                    "not are logged, and a count every 2^20 checks")\n'
     '    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\n'
     'REXCVAR_DEFINE_INT32(sasrt_renut_diag_light_volumes, 0, "SASRT",\n'
     '                     "Diagnostics: after this many frames that drew the race\'s light volumes (0: off), ten "\n'
     '                     "frames of its light volume "\n'
     '                     "draws (660 indices): the cascade spheres\' transforms (vertex c0-c3), the shading pixel "\n'
     '                     "shader\'s cascade constants (c7-c24) and where each comes from (* the running device)")\n'
     '    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\n'
     'extern std::atomic<uint64_t> g_sasrt_game_frames;  // sasrt-nx (2026-10-29): src/sasrt_capture.cpp\n'
     'REXCVAR_DEFINE_STRING(sasrt_renut_diag_ps_constants, "", "SASRT",\n'),
    ('render/draw.cpp',
     '  last.alloc = alloc;\n'
     '  last.replay = constants.replay;\n'
     '  if (constants.replay)\n'
     '    *constants.dirty = 0;\n'
     '  return alloc;\n'
     '}\n',
     '  last.alloc = alloc;\n'
     '  last.replay = constants.replay;\n'
     '  if (constants.replay)\n'
     '    *constants.dirty = 0;\n'
     '  return alloc;\n'
     '}\n'
     '\n'
     '// sasrt-nx (2026-10-29, sasrt_renut_diag_constants_verify / sasrt_renut_diag_light_volumes): see the keys.\n'
     'bool SasrtDiagConstantsOn() {\n'
     '  static const bool on =\n'
     '      REXCVAR_GET(sasrt_renut_diag_constants_verify) || REXCVAR_GET(sasrt_renut_diag_light_volumes) > 0;\n'
     '  return on;\n'
     '}\n'
     'std::string SasrtRegisterText(const u8 *p) {\n'
     '  float v[4];\n'
     '  for (u32 k = 0; k < 4; ++k) {\n'
     '    u32 w;\n'
     '    std::memcpy(&w, p + k * 4, 4);\n'
     '    w = __builtin_bswap32(w);\n'
     '    std::memcpy(&v[k], &w, 4);\n'
     '  }\n'
     '  return fmt::format("({:.5g} {:.5g} {:.5g} {:.5g})", v[0], v[1], v[2], v[3]);\n'
     '}\n'
     '// The registers the shader reads that the model does not hold with the draw\'s bytes: stale (held, other bytes) and\n'
     '// unheld; \'first\' the lowest of them.\n'
     'u32 SasrtStaleRegisters(const FloatConstants &constants, const u32 used[8], const ConstantUpload &last,\n'
     '                        const ShaderCacheEntry *entry, bool pushed, u32 &first, u32 &unheld) {\n'
     '  u32 lits[8] = {};\n'
     '  if (pushed) {\n'
     '    if (entry && last.literals == entry)\n'
     '      std::memcpy(lits, last.literal_regs, sizeof(lits));\n'
     '  } else if (entry && entry->literalCount) {\n'
     '    for (u32 i = 0; i < entry->literalCount; ++i) {\n'
     '      const ShaderLiteral &l = g_activeShaderLiterals[entry->literalOffset + i];\n'
     '      if (l.reg < 256)\n'
     '        lits[l.reg / 32] |= 1u << (l.reg % 32);\n'
     '    }\n'
     '  }\n'
     '  u32 stale = 0;\n'
     '  first = 256;\n'
     '  unheld = 0;\n'
     '  for (u32 r = 0; r < 256; ++r) {\n'
     '    const u32 bit = 1u << (r % 32);\n'
     '    if (!(used[r / 32] & bit) || (lits[r / 32] & bit))\n'
     '      continue;\n'
     '    if (!(last.valid[r / 32] & bit))\n'
     '      ++unheld;\n'
     '    else if (std::memcmp(last.bytes + r * 16, constants.Register(r), 16) != 0)\n'
     '      ++stale;\n'
     '    else\n'
     '      continue;\n'
     '    first = std::min(first, r);\n'
     '  }\n'
     '  return stale;\n'
     '}\n'
     'uint64_t g_sasrt_cv_checked = 0, g_sasrt_cv_bad = 0;\n'
     'void SasrtDiagConstants(const DrawCall &call, const ShaderRecord *vs, const ShaderRecord *ps,\n'
     '                        const FloatConstants &vs_constants, const FloatConstants &ps_constants, const u32 *vs_used,\n'
     '                        const u32 *ps_used, const ConstantUpload &vs_model, const ConstantUpload &ps_model,\n'
     '                        bool pushed, bool fast, const Targets *targets = nullptr) {\n'
     '  static const bool verify = REXCVAR_GET(sasrt_renut_diag_constants_verify);\n'
     '  static const int32_t volumes_from = REXCVAR_GET(sasrt_renut_diag_light_volumes);\n'
     '  const uint64_t frame = g_sasrt_game_frames.load(std::memory_order_relaxed);\n'
     '  for (u32 stage = 0; verify && stage < 2; ++stage) {\n'
     '    const ShaderRecord *r = stage ? ps : vs;\n'
     '    const ConstantUpload &m = stage ? ps_model : vs_model;\n'
     '    if (!r || (!pushed && !m.alloc))\n'
     '      continue;\n'
     '    const FloatConstants &c = stage ? ps_constants : vs_constants;\n'
     '    u32 first = 256, unheld = 0;\n'
     '    const u32 stale = SasrtStaleRegisters(c, stage ? ps_used : vs_used, m, r->entry, pushed, first, unheld);\n'
     '    if ((++g_sasrt_cv_checked & 0xFFFFF) == 0)\n'
     '      RGPU_INFO("[sasrt] sasrt_renut_diag_constants_verify: {} stages checked, {} with registers not held",\n'
     '                g_sasrt_cv_checked, g_sasrt_cv_bad);\n'
     '    if (!stale && !unheld)\n'
     '      continue;\n'
     '    ++g_sasrt_cv_bad;\n'
     '    static u32 logged = 0;\n'
     '    if (logged++ >= 64)\n'
     '      continue;\n'
     '    const bool own = !c.running || ((c.set >> (63 - first / 4)) & 1);\n'
     '    const bool held = (m.valid[first / 32] >> (first % 32)) & 1;\n'
     '    RGPU_WARN("[sasrt] sasrt_renut_diag_constants_verify: frame {} draw {} {} {:016X} ({} path, {}): {} registers "\n'
     '              "stale, {} not held; c{}{} held {} now {} (replay {}, the model\'s {}, {} indices)", frame,\n'
     '              g_sasrt_draw_seq, stage ? "ps" : "vs", r->hash, fast ? "fast" : "full", pushed ? "pushed" : "ring",\n'
     '              stale, unheld, first, own ? "" : "*", held ? SasrtRegisterText(m.bytes + first * 16) : std::string("-"),\n'
     '              SasrtRegisterText(c.Register(first)), c.replay, m.replay, call.count);\n'
     '  }\n'
     '  // The window: ten frames from the one after the volumes_from-th frame that drew a light volume.\n'
     '  static uint64_t lv_last = 0, lv_frames = 0, window = 0;\n'
     '  const bool light_volume = call.indexed && call.count == 660;\n'
     '  if (volumes_from > 0 && light_volume && frame != lv_last) {\n'
     '    lv_last = frame;\n'
     '    if (++lv_frames == uint64_t(volumes_from))\n'
     '      window = frame + 1;\n'
     '  }\n'
     '  const bool in_window = window && frame >= window && frame < window + 10;\n'
     '  if (in_window && light_volume) {\n'
     '    std::string text;\n'
     '    for (u32 reg = 0; reg < 4; ++reg) {\n'
     '      const bool own = !vs_constants.running || ((vs_constants.set >> (63 - reg / 4)) & 1);\n'
     '      text += fmt::format(" c{}{} {}", reg, own ? "" : "*", SasrtRegisterText(vs_constants.Register(reg)));\n'
     '    }\n'
     '    if (ps) {\n'
     '      uint64_t h = 0;\n'
     '      u32 running = 0;\n'
     '      for (u32 reg = 7; reg <= 24; ++reg) {\n'
     '        running += ps_constants.running && !((ps_constants.set >> (63 - reg / 4)) & 1);\n'
     '        h = XXH3_64bits_withSeed(ps_constants.Register(reg), 16, h);\n'
     '      }\n'
     '      text += fmt::format(" | ps c7-c24 {:016X} ({} of them the running device\'s)", h, running);\n'
     '      for (u32 reg = 7; reg <= 24; ++reg) {\n'
     '        const bool own = !ps_constants.running || ((ps_constants.set >> (63 - reg / 4)) & 1);\n'
     '        text += fmt::format(" c{}{} {}", reg, own ? "" : "*", SasrtRegisterText(ps_constants.Register(reg)));\n'
     '      }\n'
     '    }\n'
     '    RGPU_INFO("[sasrt] light volume: frame {} draw {} ({}) vs {:016X} ps {:016X} replay {} running {}:{}", frame,\n'
     '              g_sasrt_draw_seq, fast ? "fast" : "full", vs ? vs->hash : 0, ps ? ps->hash : 0,\n'
     '              vs_constants.replay, static_cast<const void *>(vs_constants.running), text);\n'
     '  }\n'
     '  // The shadow casters (the cascades\' 1024x1024 target): the first six draws of each frame, and a count.\n'
     '  if (in_window && targets && targets->width == 1024 && targets->height == 1024) {\n'
     '    static uint64_t casters_frame = 0;\n'
     '    static u32 casters = 0, inherited = 0, clip_off = 0;\n'
     '    if (frame != casters_frame) {\n'
     '      if (casters)\n'
     '        RGPU_INFO("[sasrt] shadow casters: frame {}: {} draws, {} with inherited vertex constants, {} with "\n'
     '                  "clipping off (PA_CL_CLIP_CNTL.CLIP_DISABLE)", casters_frame, casters, inherited, clip_off);\n'
     '      casters_frame = frame;\n'
     '      casters = inherited = clip_off = 0;\n'
     '    }\n'
     '    uint64_t used_groups = 0;\n'
     '    for (u32 g = 0; g < 64; ++g)\n'
     '      used_groups |= uint64_t(GroupRegisters(vs_used, g) != 0) << (63 - g);\n'
     '    const uint64_t from_running = vs_constants.running ? used_groups & ~vs_constants.set : 0;\n'
     '    inherited += from_running != 0;\n'
     '    clip_off += vs_constants.state &&\n'
     '                ((__builtin_bswap32(*reinterpret_cast<const u32 *>(vs_constants.state + 0x2944)) >> 16) & 1);\n'
     '    if (casters++ < 6) {\n'
     '      uint64_t h = 0;\n'
     '      for (u32 reg = 0; reg < 256; ++reg) {\n'
     '        if ((vs_used[reg / 32] >> (reg % 32)) & 1)\n'
     '          h = XXH3_64bits_withSeed(vs_constants.Register(reg), 16, h);\n'
     '      }\n'
     '      std::string text;\n'
     '      for (u32 reg = 0; reg < 8; ++reg) {\n'
     '        const bool own = !vs_constants.running || ((vs_constants.set >> (63 - reg / 4)) & 1);\n'
     '        text += fmt::format(" c{}{} {}", reg, own ? "" : "*", SasrtRegisterText(vs_constants.Register(reg)));\n'
     '      }\n'
     '      RGPU_INFO("[sasrt] shadow caster: frame {} draw {} vs {:016X} ps {:016X} count {} replay {} running {} "\n'
     '                "groups used {:016X} from the running device {:016X} constants {:016X} clip control {:08X}:{}", frame,\n'
     '                g_sasrt_draw_seq,\n'
     '                vs ? vs->hash : 0, ps ? ps->hash : 0, call.count, vs_constants.replay,\n'
     '                static_cast<const void *>(vs_constants.running), used_groups, from_running, h,\n'
     '                vs_constants.state ? __builtin_bswap32(*reinterpret_cast<const u32 *>(vs_constants.state + 0x2944)) : 0u,\n'
     '                text);\n'
     '    }\n'
     '  }\n'
     '}\n'),
    ('render/draw.cpp',
     '  banjo::renut_gpu::CountPushedConstants(1, 2);\n'
     '  plume::RenderBuffer *memexport = MemExportBufferLocked(s);\n',
     '  banjo::renut_gpu::CountPushedConstants(1, 2);\n'
     '  if (SasrtDiagConstantsOn()) [[unlikely]]  // sasrt-nx (2026-10-29)\n'
     '    SasrtDiagConstants(call, vs, ps, vs_constants, ps_constants, vs_used, ps_used, g_bound.pushed_vs,\n'
     '                       g_bound.pushed_ps, true, true);\n'
     '  plume::RenderBuffer *memexport = MemExportBufferLocked(s);\n'),
    ('render/draw.cpp',
     '    g_bound.pushed_vs.replay = 0;\n'
     '    g_bound.pushed_ps.replay = 0;\n'
     '  }\n'
     '  for (u32 i = 0; i < prefetch_stream_count; ++i) {',
     '    g_bound.pushed_vs.replay = 0;\n'
     '    g_bound.pushed_ps.replay = 0;\n'
     '  }\n'
     '  if (SasrtDiagConstantsOn()) [[unlikely]]  // sasrt-nx (2026-10-29)\n'
     '    SasrtDiagConstants(call, vs, ps, vs_constants, ps_constants, vs_used, ps_used,\n'
     '                       pushed ? g_bound.pushed_vs : g_bound.vs_constants,\n'
     '                       pushed ? g_bound.pushed_ps : g_bound.ps_constants, pushed, false, &targets);\n'
     '  for (u32 i = 0; i < prefetch_stream_count; ++i) {'),
]

# sasrt-nx (2026-10-30, sasrt_deko3d_msaa_positions and sasrt_deko3d_a2c_dither; plume's deko3d multisample state):
# deko3d's dkMultisampleStateDefaults puts every sample at the pixel's centre (sampleLocations 0x88888888) and turns the
# alpha-to-coverage dither on; dkCmdBufBindMultisampleState always writes the positions (Maxwell method 0x11E0,
# libdeko3d disassembled) and plume set neither, so a multisampled target's samples all sat at the centre: no edge
# antialiasing. This game makes one multisampled pipeline in a whole race (Ryujinx run fix1030_race); the fix is for
# the renderer's other users. The dither gave a fixed grid wherever alpha to coverage drew (Final Fantasy XIII's ice
# on the same plume files). The race draws about 115 indexed strips a frame, none with primitive restart before.
# sasrt_deko3d_strip_restart: the Vulkan back end cuts an indexed strip at the all-ones index (primitiveRestartEnable,
# as D3D's strip cut); deko3d never turns primitive restart on and plume's deko3d back end did not either.
EDITS += [
    ('banjo_renut_tuning.cpp',
     'REXCVAR_DEFINE_BOOL(banjo_deko3d_alpha_spec, false, "Banjo/Enhancements",  // sasrt-nx: off, as sa2-nx\n',
     'REXCVAR_DEFINE_BOOL(sasrt_deko3d_msaa_positions, true, "SASRT",\n'
     '                    "deko3d renderer: a multisampled target\'s pipelines get the standard sample positions for "\n'
     '                    "their sample count (dkMultisampleStateSetLocations, as nouveau). Off: deko3d\'s default, "\n'
     '                    "every sample at the pixel\'s centre, so 2x/4x targets have no edge antialiasing on the "\n'
     '                    "console (Ryujinx keeps the standard positions either way)")\n'
     '    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\n'
     'REXCVAR_DEFINE_BOOL(sasrt_deko3d_a2c_dither, false, "SASRT",\n'
     '                    "deko3d renderer: the hardware\'s alpha-to-coverage dither (deko3d turns it on by default). "\n'
     '                    "On: a fixed screen-space grid where alpha to coverage draws on a multisampled target; off: "\n'
     '                    "the coverage from alpha alone, as the Vulkan and D3D12 back ends")\n'
     '    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\n'
     'REXCVAR_DEFINE_BOOL(sasrt_deko3d_strip_restart, true, "SASRT",\n'
     '                    "deko3d renderer: an indexed triangle or line strip starts again at the all-ones index "\n'
     '                    "(0xFFFF for 16-bit indices), as the Vulkan back end and D3D. Off: deko3d\'s default, no "\n'
     '                    "restart, so a cut joins the strips with stray triangles to vertex 65535")\n'
     '    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\n'
     'REXCVAR_DEFINE_BOOL(banjo_deko3d_alpha_spec, false, "Banjo/Enhancements",  // sasrt-nx: off, as sa2-nx\n'),
    ('banjo_renut_tuning.cpp',
     'bool SasrtDeko3DDepthResolveOn() { return REXCVAR_GET(sasrt_deko3d_depth_resolve); }  // sasrt-nx (2026-10-21)\n',
     'bool SasrtDeko3DDepthResolveOn() { return REXCVAR_GET(sasrt_deko3d_depth_resolve); }  // sasrt-nx (2026-10-21)\n'
     'bool SasrtDeko3DMsaaPositionsOn() { return REXCVAR_GET(sasrt_deko3d_msaa_positions); }  // sasrt-nx (2026-10-30)\n'
     'bool SasrtDeko3DA2cDitherOn() { return REXCVAR_GET(sasrt_deko3d_a2c_dither); }\n'
     'bool SasrtDeko3DStripRestartOn() { return REXCVAR_GET(sasrt_deko3d_strip_restart); }\n'),
    ('banjo_renut_tuning.h',
     'bool SasrtDeko3DDepthResolveOn();\n',
     'bool SasrtDeko3DDepthResolveOn();\n'
     '// sasrt-nx (2026-10-30): sasrt_deko3d_msaa_positions and sasrt_deko3d_a2c_dither (plume Deko3DOptions::msaaPositions,\n'
     '// alphaToCoverageDither).\n'
     'bool SasrtDeko3DMsaaPositionsOn();\n'
     'bool SasrtDeko3DA2cDitherOn();\n'
     'bool SasrtDeko3DStripRestartOn();  // sasrt_deko3d_strip_restart (Deko3DOptions::stripRestart)\n'),
    ('banjo_renut_deko3d.cpp',
     '  options.depthResolve = SasrtDeko3DDepthResolveOn();  // sasrt-nx (2026-10-21)\n',
     '  options.depthResolve = SasrtDeko3DDepthResolveOn();  // sasrt-nx (2026-10-21)\n'
     '  options.msaaPositions = SasrtDeko3DMsaaPositionsOn();  // sasrt-nx (2026-10-30)\n'
     '  options.alphaToCoverageDither = SasrtDeko3DA2cDitherOn();\n'
     '  options.stripRestart = SasrtDeko3DStripRestartOn();\n'),
    ('banjo_renut_deko3d.cpp',
     '"decompressed before a read {} (sasrt_deko3d_depth_resolve)",\n',
     '"decompressed before a read {} (sasrt_deko3d_depth_resolve); multisampled pipelines {} ({} with alpha "\n'
     '                     "to coverage, {} given the standard sample positions: sasrt_deko3d_msaa_positions); "\n'
     '                     "indexed strips drawn with primitive restart {} (sasrt_deko3d_strip_restart)",\n'),
    ('banjo_renut_deko3d.cpp',
     '                     st.copyImage.load(), st.copyResolve.load(), st.copyBlit.load(), st.depthResolves.load());\n',
     '                     st.copyImage.load(), st.copyResolve.load(), st.copyBlit.load(), st.depthResolves.load(),\n'
     '                     st.msaaPipelines.load(), st.msaaAlphaToCoverage.load(), st.msaaPositioned.load(),\n'
     '                     st.stripRestartDraws.load());\n'),
]

# sasrt-nx (2026-10-30, sasrt_renut_resolve_readback; the race start's dark Ristar, black on every renderer): the tone
# mapper (sub_827A0A20) locks a 1x1 k_32_FLOAT resolve of the average scene luminance and sets gITMGF.x =
# 2.5 * (L + 0.01) / key; Renut never wrote resolves to guest memory, the CPU read 0 and gITMGF.x was 0.05, so every
# emissive surface (Ristar's material: gToneReflParams.x 20) stored its colour at 1/20. Found by the write watch
# (sasrt_diag_ps_constant_watch_writes) on the camera buffer's c146: sub_82747610 stores the tone mapper's value.
EDITS += [
    ('render/draw.cpp',
     'REXCVAR_DEFINE_BOOL(sasrt_renut_diag_writeback_check, false, "SASRT",\n',
     '// sasrt-nx (2026-10-30): a 1x1 32-bit float resolve written back to guest memory (SasrtQueueResolveReadbackLocked).\nREXCVAR_DEFINE_BOOL(sasrt_renut_resolve_readback, true, "SASRT",\n                    "Renut\'s renderer: a resolve into a 1x1 32-bit float texture (the race\'s average scene "\n                    "luminance) is also copied back to its guest memory when its frame\'s GPU work is done, where the "\n                    "game\'s CPU locks and reads it: the glow of emissive surfaces (gITMGF, Ristar at the race "\n                    "start) scales by it. Off: the CPU reads 0 there and every glow is 20x too dark")\n    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\nREXCVAR_DEFINE_BOOL(sasrt_renut_diag_writeback_check, false, "SASRT",\n'),
    ('render/draw.cpp',
     'void CompleteMemExportsLocked(uint32_t slot) {\n',
     '// sasrt-nx (2026-10-30, sasrt_renut_resolve_readback): Renut\'s resolves stay on the GPU, but this game\'s CPU reads one\n// of them: the race\'s average scene luminance, resolved into a 1x1 k_32_FLOAT texture and locked by the tone mapper\n// (sub_827A0A20: gITMGF.x = 2.5 * (L + 0.01) / key). With nothing written there it read 0 and gITMGF.x came out 0.05,\n// so every emissive surface stored its colour at 1/20 (Ristar at the race start black on every renderer: Renut, the\n// emulated GPU without its resolve readback, the console). Such a resolve\'s texel is copied to the slot\'s small\n// readback buffer after the resolve and written to its guest memory (big-endian, as the CPU\'s lfs reads it) when the\n// slot\'s fence is waited, a frame or two later, with the slot\'s memexport results: the game locks a texture of its\n// ring a frame behind.\nstruct SasrtResolveReadback {\n  u32 guest_pa;\n  u32 offset;\n};\nconstexpr u32 kSasrtReadbackStride = 512, kSasrtReadbackCount = 16;  // D3D12: 512-byte placement, 256-byte rows\nstd::vector<SasrtResolveReadback> g_sasrt_resolve_readbacks[kFramesInFlight];\nplume::RenderBuffer *g_sasrt_resolve_readback_buffer[kFramesInFlight] = {};  // kept until exit\nuint64_t g_sasrt_resolve_readbacks_done = 0;\n\nvoid SasrtQueueResolveReadbackLocked(VideoState &s, HostTexture *dest, uint32_t slice, uint32_t z, u32 level) {\n  static const bool on = REXCVAR_GET(sasrt_renut_resolve_readback);\n  if (!on || !dest || !dest->texture || slice || z || level || dest->width != 1 || dest->height != 1 ||\n      dest->host_format != plume::RenderFormat::R32_FLOAT || !dest->base_page)\n    return;\n  std::vector<SasrtResolveReadback> &list = g_sasrt_resolve_readbacks[s.frame];\n  if (list.size() >= kSasrtReadbackCount)\n    return;\n  plume::RenderBuffer *&buffer = g_sasrt_resolve_readback_buffer[s.frame];\n  if (!buffer)\n    buffer = s.device->createBuffer(plume::RenderBufferDesc::ReadbackBuffer(kSasrtReadbackStride * kSasrtReadbackCount))\n                 .release();\n  if (!buffer)\n    return;\n  const u32 offset = u32(list.size()) * kSasrtReadbackStride;\n  TransitionTextureLocked(dest, plume::RenderTextureLayout::COPY_SOURCE);\n  const plume::RenderBox box(0, 0, 1, 1);\n  s.command_list->copyTextureRegion(\n      plume::RenderTextureCopyLocation::PlacedFootprint(buffer, plume::RenderFormat::R32_FLOAT, 1, 1, 1, 64, offset),\n      plume::RenderTextureCopyLocation::Subresource(dest->texture.get()), 0, 0, 0, &box);\n  TransitionTextureLocked(dest, plume::RenderTextureLayout::SHADER_READ);\n  list.push_back({dest->base_page << 12, offset});\n  g_bound.framebuffer = nullptr;  // the copy ends any render pass\n}\n\nvoid SasrtCompleteResolveReadbacksLocked(uint32_t slot) {\n  std::vector<SasrtResolveReadback> &list = g_sasrt_resolve_readbacks[slot];\n  if (list.empty())\n    return;\n  plume::RenderBuffer *buffer = g_sasrt_resolve_readback_buffer[slot];\n  const plume::RenderRange range(0, uint64_t(kSasrtReadbackStride) * kSasrtReadbackCount);\n  if (const auto *data = buffer ? static_cast<const u8 *>(buffer->map(0, &range)) : nullptr) {\n    for (const SasrtResolveReadback &r : list) {\n      u32 bits;\n      std::memcpy(&bits, data + r.offset, 4);\n      if (u8 *guest = GuestPhysicalPtr<u8>(r.guest_pa)) {\n        const u32 big = __builtin_bswap32(bits);\n        std::memcpy(guest, &big, 4);\n      }\n      if (g_sasrt_resolve_readbacks_done++ < 4 || (g_sasrt_resolve_readbacks_done & 0x3FF) == 0) {\n        float v;\n        std::memcpy(&v, &bits, 4);\n        RGPU_INFO("[sasrt] resolve readback {}: {} to guest {:08X} (sasrt_renut_resolve_readback)",\n                  g_sasrt_resolve_readbacks_done, v, r.guest_pa);\n      }\n    }\n    buffer->unmap();\n  }\n  list.clear();\n}\n\nvoid CompleteMemExportsLocked(uint32_t slot) {\n  SasrtCompleteResolveReadbacksLocked(slot);  // sasrt-nx (2026-10-30)\n'),
    ('render/draw.cpp',
     '        TransitionTextureLocked(dest, plume::RenderTextureLayout::SHADER_READ);\n        if (dest->extra_levels && LazyResolveMipsOn()) {\n          // banjo-nx (2026-10-28, banjo_renut_lazy_resolve_mips',
     '        TransitionTextureLocked(dest, plume::RenderTextureLayout::SHADER_READ);\n        detail::SasrtQueueResolveReadbackLocked(s, dest, slice, z, dest_level);  // sasrt-nx (2026-10-30)\n        if (dest->extra_levels && LazyResolveMipsOn()) {\n          // banjo-nx (2026-10-28, banjo_renut_lazy_resolve_mips'),
]

# sasrt-nx (2026-10-30, the far-cascade shadow flicker, console only, still there with the all-safe config):
# sasrt_deko3d_color_compression (colour targets' hardware compression a key: the one console-only feature no config
# had turned off) and sasrt_renut_diag_shadow_dump (what the console's GPU made of the shading's inputs, frame by frame).
EDITS += [
    ('banjo_renut_tuning.cpp',
     'REXCVAR_DEFINE_BOOL(sasrt_deko3d_msaa_positions, true, "SASRT",\n',
     'REXCVAR_DEFINE_BOOL(sasrt_deko3d_color_compression, true, "SASRT",\n                    "deko3d renderer (2026-10-30, a console A/B): colour render targets with the GPU\'s "\n                    "hardware compression, as always. Off: uncompressed (Ryujinx emulates no compression, so "\n                    "only the console can show a difference; the far-shadow flicker\'s last console-only "\n                    "suspect after banjo_deko3d_depth_compression and banjo_deko3d_zcull)")\n    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\nREXCVAR_DEFINE_BOOL(sasrt_deko3d_msaa_positions, true, "SASRT",\n'),
    ('banjo_renut_tuning.cpp',
     'bool SasrtDeko3DA2cDitherOn() { return REXCVAR_GET(sasrt_deko3d_a2c_dither); }\n',
     'bool SasrtDeko3DA2cDitherOn() { return REXCVAR_GET(sasrt_deko3d_a2c_dither); }\nbool SasrtDeko3DColorCompressionOn() { return REXCVAR_GET(sasrt_deko3d_color_compression); }\n'),
    ('banjo_renut_tuning.h',
     'bool SasrtDeko3DA2cDitherOn();\n',
     'bool SasrtDeko3DA2cDitherOn();\nbool SasrtDeko3DColorCompressionOn();  // sasrt_deko3d_color_compression\n'),
    ('banjo_renut_deko3d.cpp',
     '  options.alphaToCoverageDither = SasrtDeko3DA2cDitherOn();\n',
     '  options.alphaToCoverageDither = SasrtDeko3DA2cDitherOn();\n  options.colorCompression = SasrtDeko3DColorCompressionOn();  // sasrt-nx (2026-10-30)\n'),
    ('render/draw.cpp',
     '// sasrt-nx (2026-10-30): a 1x1 32-bit float resolve written back to guest memory (SasrtQueueResolveReadbackLocked).\n',
     '// sasrt-nx (2026-10-30): resolves written to files for a few frames (SasrtShadowDumpLocked).\nREXCVAR_DEFINE_STRING(sasrt_renut_diag_shadow_dump, "", "SASRT",\n                      "Diagnostics: \\"<first s>,<every s>,<windows>\\": from <first s> after the start, every "\n                      "<every s>, <windows> times, the depth resolves (their float results: the shadow cascades, "\n                      "the scene depth) and the 1152x544 8-bit colour resolves (the G-buffer, the shadow mask) of 4 consecutive game frames are "\n                      "written to shadow_dump/ next to the executable, raw texels with a text header "\n                      "(tools/shadow_dump_view.py). About 32 MB a frame")\n    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\n// sasrt-nx (2026-10-30): a 1x1 32-bit float resolve written back to guest memory (SasrtQueueResolveReadbackLocked).\n'),
    ('render/draw.cpp',
     'void CompleteMemExportsLocked(uint32_t slot) {\n  SasrtCompleteResolveReadbacksLocked(slot);  // sasrt-nx (2026-10-30)\n',
     '// sasrt-nx (2026-10-30, sasrt_renut_diag_shadow_dump): the far-cascade shadows gone in every other frame on the\n// console only. What the console\'s GPU made of the shading\'s inputs (the cascades in the 1024x3072 float atlas, the\n// scene depth) and of the 1152x544 colour resolves (the shadow mask among them), frame by frame: copied to a readback\n// buffer of their own after the resolve and written to files when the slot\'s fence is waited.\nstruct SasrtShadowDump {\n  plume::RenderBuffer *buffer;\n  std::string name;\n  uint32_t width, height, row_bytes, texel_bytes;\n};\nstd::vector<SasrtShadowDump> g_sasrt_shadow_dumps[kFramesInFlight];\n\n// The window this game frame is in (-1: none). Windows of 4 consecutive game frames from the first frame past each\n// time mark.\nint SasrtShadowDumpWindow(uint64_t frame) {\n  static const std::vector<int> spec = [] {\n    std::vector<int> out;\n    const std::string text = REXCVAR_GET(sasrt_renut_diag_shadow_dump);\n    for (size_t at = 0; at < text.size() && out.size() < 3;) {\n      const size_t comma = std::min(text.find(\',\', at), text.size());\n      out.push_back(std::atoi(text.substr(at, comma - at).c_str()));\n      at = comma + 1;\n    }\n    return out;\n  }();\n  if (spec.size() < 3 || spec[2] <= 0)\n    return -1;\n  static const auto start = std::chrono::steady_clock::now();\n  static int window = -1;\n  static uint64_t window_frame = 0;\n  static int next = 0;\n  const double seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();\n  if (window >= 0 && frame >= window_frame + 4)\n    window = -1;\n  if (window < 0 && next < spec[2] && seconds >= double(spec[0]) + double(next) * double(std::max(1, spec[1]))) {\n    window = next++;\n    window_frame = frame;\n    RGPU_INFO("[sasrt] shadow dump window {} from game frame {} ({:.0f} s)", window, frame, seconds);\n  }\n  return window;\n}\n\nvoid SasrtShadowDumpLocked(VideoState &s, HostTexture *dest, const plume::RenderRect &region, const char *kind,\n                           u32 guest_va) {\n  const uint64_t frame = g_sasrt_game_frames.load(std::memory_order_relaxed);\n  const int window = SasrtShadowDumpWindow(frame);\n  if (window < 0 || !dest || !dest->texture || region.right <= region.left || region.bottom <= region.top)\n    return;\n  uint32_t texel = 0;\n  switch (dest->host_format) {\n  case plume::RenderFormat::R32_FLOAT:\n  case plume::RenderFormat::R8G8B8A8_UNORM:\n  case plume::RenderFormat::B8G8R8A8_UNORM:\n    texel = 4;\n    break;\n  default:\n    return;\n  }\n  const uint32_t w = uint32_t(region.right - region.left), h = uint32_t(region.bottom - region.top);\n  const uint32_t row_bytes = (w * texel + 255u) & ~255u;\n  std::unique_ptr<plume::RenderBuffer> buffer =\n      s.device->createBuffer(plume::RenderBufferDesc::ReadbackBuffer(uint64_t(row_bytes) * h));\n  if (!buffer)\n    return;\n  TransitionTextureLocked(dest, plume::RenderTextureLayout::COPY_SOURCE);\n  const plume::RenderBox box(region.left, region.top, region.right, region.bottom);\n  s.command_list->copyTextureRegion(\n      plume::RenderTextureCopyLocation::PlacedFootprint(buffer.get(), dest->host_format, w, h, 1, row_bytes / texel, 0),\n      plume::RenderTextureCopyLocation::Subresource(dest->texture.get()), 0, 0, 0, &box);\n  TransitionTextureLocked(dest, plume::RenderTextureLayout::SHADER_READ);\n  g_bound.framebuffer = nullptr;\n  static uint32_t serial = 0;\n  g_sasrt_shadow_dumps[s.frame].push_back(\n      {buffer.release(),\n       fmt::format("w{}_f{}_{:04}_{}_{:08X}_x{}_y{}_{}x{}_fmt{}", window, frame, serial++, kind, guest_va, region.left,\n                   region.top, w, h, u32(dest->host_format)),\n       w, h, row_bytes, texel});\n}\n\nvoid SasrtCompleteShadowDumpsLocked(uint32_t slot) {\n  std::vector<SasrtShadowDump> &list = g_sasrt_shadow_dumps[slot];\n  if (list.empty())\n    return;\n  static const bool made = [] {\n    std::error_code ec;\n    std::filesystem::create_directories(banjo::renut_gpu::NextToExecutable("shadow_dump"), ec);\n    return true;\n  }();\n  (void)made;\n  for (SasrtShadowDump &d : list) {\n    if (const auto *data = static_cast<const u8 *>(d.buffer->map())) {\n      const std::string path = banjo::renut_gpu::NextToExecutable("shadow_dump/" + d.name + ".bin").string();\n      if (FILE *f = std::fopen(path.c_str(), "wb")) {\n        for (uint32_t y = 0; y < d.height; ++y)\n          std::fwrite(data + size_t(y) * d.row_bytes, 1, size_t(d.width) * d.texel_bytes, f);\n        std::fclose(f);\n      }\n      d.buffer->unmap();\n    }\n    Video::RetireLocked(std::unique_ptr<plume::RenderBuffer>(d.buffer));\n  }\n  RGPU_INFO("[sasrt] shadow dump: {} resolves written (sasrt_renut_diag_shadow_dump)", list.size());\n  list.clear();\n}\n\nvoid CompleteMemExportsLocked(uint32_t slot) {\n  SasrtCompleteResolveReadbacksLocked(slot);  // sasrt-nx (2026-10-30)\n  SasrtCompleteShadowDumpsLocked(slot);  // sasrt-nx (2026-10-30)\n'),
    ('render/draw.cpp',
     '        detail::SasrtQueueResolveReadbackLocked(s, dest, slice, z, dest_level);  // sasrt-nx (2026-10-30)\n',
     '        detail::SasrtQueueResolveReadbackLocked(s, dest, slice, z, dest_level);  // sasrt-nx (2026-10-30)\n        if (dest->width == 1152 && dest->height == 544 && slice == 0 && z == 0 && dest_level == 0)\n          detail::SasrtShadowDumpLocked(s, dest, dest_rect, "colour", dest_texture_va);  // 2026-10-30\n'),
    ('render/draw.cpp',
     '        } else if (HandOverResolveLocked(surface, dest, src, dest_x, dest_y, words) ||\n                   ResolveDepth(surface, dest, src, dest_x, dest_y, words)) {\n          dest->resolve_signature = sig;\n',
     '        } else if (HandOverResolveLocked(surface, dest, src, dest_x, dest_y, words) ||\n                   ResolveDepth(surface, dest, src, dest_x, dest_y, words)) {\n          dest->resolve_signature = sig;\n          detail::SasrtShadowDumpLocked(  // sasrt-nx (2026-10-30, sasrt_renut_diag_shadow_dump)\n              s, dest,\n              ScaleRect(plume::RenderRect(dest_x, dest_y, dest_x + (src.x2 - src.x1), dest_y + (src.y2 - src.y1)),\n                        surface->scale),\n              "depth", dest_texture_va);\n'),
]

# sasrt-nx (2026-10-30): sasrt_renut_diag_shadow_dump hung the console (the render thread wrote a row a call to the SD
# card: 76 s for a frame) and got one whole frame. Now a writer thread, one fwrite a file, <frames> (8) a window and
# an address filter: the shadow mask of consecutive frames is what it is for.
EDITS += [
    ('render/draw.cpp',
     '#include <condition_variable>\n#include <cstring>\n',
     "#include <condition_variable>\n#include <cstring>\n#include <deque>  // sasrt-nx (2026-10-30): the shadow dump's writer\n"),
    ('render/draw.cpp',
     'REXCVAR_DEFINE_STRING(sasrt_renut_diag_shadow_dump, "", "SASRT",\n                      "Diagnostics: \\"<first s>,<every s>,<windows>\\": from <first s> after the start, every "\n                      "<every s>, <windows> times, the depth resolves (their float results: the shadow cascades, "\n                      "the scene depth) and the 1152x544 8-bit colour resolves (the G-buffer, the shadow mask) of 4 consecutive game frames are "\n                      "written to shadow_dump/ next to the executable, raw texels with a text header "\n                      "(tools/shadow_dump_view.py). About 32 MB a frame")',
     'REXCVAR_DEFINE_STRING(sasrt_renut_diag_shadow_dump, "", "SASRT",\n                      "Diagnostics: \\"<first s>,<every s>,<windows>[,<frames>[,<address>...]]\\": from <first s> "\n                      "after the start, every <every s>, <windows> times, the depth resolves (their float results: "\n                      "the shadow cascades, the scene depth) and the 1152x544 8-bit colour resolves (the G-buffer, "\n                      "the shadow mask) of <frames> (8) consecutive game frames are written to shadow_dump/ next to "\n                      "the executable, raw texels (tools/shadow_dump_view.py), by a thread of their own. With "\n                      "addresses (hex, as the files are named) only those resolves. 2.5 MB a 1152x544 resolve, 4 MB "\n                      "a cascade")'),
    ('render/draw.cpp',
     '// The window this game frame is in (-1: none). Windows of 4 consecutive game frames from the first frame past each\n// time mark.\nint SasrtShadowDumpWindow(uint64_t frame) {\n  static const std::vector<int> spec = [] {\n    std::vector<int> out;\n    const std::string text = REXCVAR_GET(sasrt_renut_diag_shadow_dump);\n    for (size_t at = 0; at < text.size() && out.size() < 3;) {\n      const size_t comma = std::min(text.find(\',\', at), text.size());\n      out.push_back(std::atoi(text.substr(at, comma - at).c_str()));\n      at = comma + 1;\n    }\n    return out;\n  }();\n  if (spec.size() < 3 || spec[2] <= 0)\n    return -1;\n  static const auto start = std::chrono::steady_clock::now();\n  static int window = -1;\n  static uint64_t window_frame = 0;\n  static int next = 0;\n  const double seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();\n  if (window >= 0 && frame >= window_frame + 4)\n    window = -1;\n  if (window < 0 && next < spec[2] && seconds >= double(spec[0]) + double(next) * double(std::max(1, spec[1]))) {\n    window = next++;\n    window_frame = frame;\n    RGPU_INFO("[sasrt] shadow dump window {} from game frame {} ({:.0f} s)", window, frame, seconds);\n  }\n  return window;\n}\n\n',
     '// The dump\'s spec: its times, the game frames a window lasts and the resolves it takes (by guest address).\nstruct SasrtShadowDumpSpec {\n  int first = 0, every = 0, windows = 0, frames = 8;\n  std::vector<u32> addresses;  // empty: all of them\n};\n\nconst SasrtShadowDumpSpec &SasrtShadowDumpSpecGet() {\n  static const SasrtShadowDumpSpec spec = [] {\n    SasrtShadowDumpSpec out;\n    const std::string text = REXCVAR_GET(sasrt_renut_diag_shadow_dump);\n    int field = 0;\n    for (size_t at = 0; at < text.size(); ++field) {\n      const size_t comma = std::min(text.find(\',\', at), text.size());\n      const std::string item = text.substr(at, comma - at);\n      at = comma + 1;\n      if (field == 0)\n        out.first = std::atoi(item.c_str());\n      else if (field == 1)\n        out.every = std::atoi(item.c_str());\n      else if (field == 2)\n        out.windows = std::atoi(item.c_str());\n      else if (field == 3)\n        out.frames = std::max(1, std::atoi(item.c_str()));\n      else if (!item.empty())\n        out.addresses.push_back(u32(std::strtoul(item.c_str(), nullptr, 16)));\n    }\n    return out;\n  }();\n  return spec;\n}\n\n// The window this game frame is in (-1: none). Windows of <frames> consecutive game frames from the first frame past\n// each time mark.\nint SasrtShadowDumpWindow(uint64_t frame) {\n  const SasrtShadowDumpSpec &spec = SasrtShadowDumpSpecGet();\n  if (spec.windows <= 0)\n    return -1;\n  static const auto start = std::chrono::steady_clock::now();\n  static int window = -1;\n  static uint64_t window_frame = 0;\n  static int next = 0;\n  const double seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();\n  if (window >= 0 && frame >= window_frame + uint64_t(spec.frames))\n    window = -1;\n  if (window < 0 && next < spec.windows && seconds >= double(spec.first) + double(next) * double(std::max(1, spec.every))) {\n    window = next++;\n    window_frame = frame;\n    RGPU_INFO("[sasrt] shadow dump window {} from game frame {} ({:.0f} s, {} frames, {} addresses)", window, frame,\n              seconds, spec.frames, spec.addresses.size());\n  }\n  return window;\n}\n\n'),
    ('render/draw.cpp',
     '  if (window < 0 || !dest || !dest->texture || region.right <= region.left || region.bottom <= region.top)\n    return;\n',
     '  if (window < 0 || !dest || !dest->texture || region.right <= region.left || region.bottom <= region.top)\n    return;\n  const std::vector<u32> &only = SasrtShadowDumpSpecGet().addresses;\n  if (!only.empty() && std::find(only.begin(), only.end(), guest_va) == only.end())\n    return;\n'),
    ('render/draw.cpp',
     'void SasrtCompleteShadowDumpsLocked(uint32_t slot) {\n  std::vector<SasrtShadowDump> &list = g_sasrt_shadow_dumps[slot];\n  if (list.empty())\n    return;\n  static const bool made = [] {\n    std::error_code ec;\n    std::filesystem::create_directories(banjo::renut_gpu::NextToExecutable("shadow_dump"), ec);\n    return true;\n  }();\n  (void)made;\n  for (SasrtShadowDump &d : list) {\n    if (const auto *data = static_cast<const u8 *>(d.buffer->map())) {\n      const std::string path = banjo::renut_gpu::NextToExecutable("shadow_dump/" + d.name + ".bin").string();\n      if (FILE *f = std::fopen(path.c_str(), "wb")) {\n        for (uint32_t y = 0; y < d.height; ++y)\n          std::fwrite(data + size_t(y) * d.row_bytes, 1, size_t(d.width) * d.texel_bytes, f);\n        std::fclose(f);\n      }\n      d.buffer->unmap();\n    }\n    Video::RetireLocked(std::unique_ptr<plume::RenderBuffer>(d.buffer));\n  }\n  RGPU_INFO("[sasrt] shadow dump: {} resolves written (sasrt_renut_diag_shadow_dump)", list.size());\n  list.clear();\n}\n\n',
     '// The files are written by a thread of their own: the render thread\'s fwrites of the first console dump (a call a row,\n// to its SD card) took 76 s for a frame\'s 10 files and hung the game. The render thread copies each readback to memory\n// and queues it, one fwrite a file. Past kSasrtShadowDumpQueued bytes queued it waits for the writer, up to 3 s; after\n// a wait that long the rest of the window is dropped (logged), so a slow card costs frames, not a hang.\nconstexpr size_t kSasrtShadowDumpQueued = size_t(48) << 20;\nstruct SasrtShadowDumpWriter {\n  std::mutex mutex;\n  std::condition_variable wake, room;\n  std::deque<std::pair<std::string, std::vector<u8>>> queue;\n  size_t queued = 0;\n  uint64_t written = 0, written_bytes = 0, failed = 0;\n  double seconds = 0;  // writing\n};\n\nSasrtShadowDumpWriter *g_sasrt_shadow_dump_writer = nullptr;\n\n// The writer thread. banjo::renut_gpu::StartLongLivedThread, as every long-lived thread here: on the console\n// std::thread throws "Function not implemented" (the first console run of this writer ended at its first file).\nvoid SasrtShadowDumpWriterMain() {\n  SasrtShadowDumpWriter *const w = g_sasrt_shadow_dump_writer;\n  for (;;) {\n    std::pair<std::string, std::vector<u8>> item;\n    {\n      std::unique_lock<std::mutex> lock(w->mutex);\n      w->wake.wait(lock, [w] { return !w->queue.empty(); });\n      item = std::move(w->queue.front());\n      w->queue.pop_front();\n    }\n    const auto began = std::chrono::steady_clock::now();\n    const std::string path = banjo::renut_gpu::NextToExecutable("shadow_dump/" + item.first + ".bin").string();\n    bool ok = false;\n    if (FILE *f = std::fopen(path.c_str(), "wb")) {\n      std::setvbuf(f, nullptr, _IONBF, 0);\n      ok = std::fwrite(item.second.data(), 1, item.second.size(), f) == item.second.size();\n      ok = std::fclose(f) == 0 && ok;\n    }\n    const double took = std::chrono::duration<double>(std::chrono::steady_clock::now() - began).count();\n    bool drained;\n    uint64_t written, bytes, failed;\n    double seconds;\n    {\n      std::lock_guard<std::mutex> lock(w->mutex);\n      w->queued -= item.second.size();\n      ++(ok ? w->written : w->failed);\n      w->written_bytes += ok ? item.second.size() : 0;\n      w->seconds += took;\n      drained = w->queue.empty();\n      written = w->written, bytes = w->written_bytes, failed = w->failed, seconds = w->seconds;\n    }\n    w->room.notify_all();\n    if (!ok)\n      RGPU_WARN("[sasrt] shadow dump: {} not written", path);\n    if (drained)\n      RGPU_INFO("[sasrt] shadow dump: {} files written ({:.1f} MB in {:.1f} s, {:.1f} MB/s), {} failed, queue empty",\n                written, double(bytes) / 1048576.0, seconds, double(bytes) / 1048576.0 / std::max(seconds, 1e-6),\n                failed);\n  }\n}\n\nSasrtShadowDumpWriter &SasrtShadowDumpWriterGet() {\n  static SasrtShadowDumpWriter *const writer = [] {\n    auto *w = new SasrtShadowDumpWriter;  // never freed: its thread runs until exit\n    std::error_code ec;\n    std::filesystem::create_directories(banjo::renut_gpu::NextToExecutable("shadow_dump"), ec);\n    g_sasrt_shadow_dump_writer = w;\n    banjo::renut_gpu::StartLongLivedThread(&SasrtShadowDumpWriterMain, 256 * 1024);\n    return w;\n  }();\n  return *writer;\n}\n\nvoid SasrtCompleteShadowDumpsLocked(uint32_t slot) {\n  std::vector<SasrtShadowDump> &list = g_sasrt_shadow_dumps[slot];\n  if (list.empty())\n    return;\n  SasrtShadowDumpWriter &writer = SasrtShadowDumpWriterGet();\n  static int behind_window = -1;  // the window whose files are dropped: the writer fell 3 s behind\n  uint32_t queued = 0, dropped = 0;\n  double waited = 0;\n  for (SasrtShadowDump &d : list) {\n    const size_t row = size_t(d.width) * d.texel_bytes, bytes = row * d.height;\n    bool take = d.window != behind_window;\n    if (take) {\n      const auto began = std::chrono::steady_clock::now();\n      std::unique_lock<std::mutex> lock(writer.mutex);\n      take = writer.room.wait_for(lock, std::chrono::seconds(3),\n                                  [&] { return writer.queued == 0 || writer.queued + bytes <= kSasrtShadowDumpQueued; });\n      if (take)\n        writer.queued += bytes;  // held for it while it is copied\n      waited += std::chrono::duration<double>(std::chrono::steady_clock::now() - began).count();\n      if (!take) {\n        behind_window = d.window;\n        RGPU_WARN("[sasrt] shadow dump: the writer is {} MB behind after 3 s; the rest of window {} is dropped",\n                  writer.queued >> 20, d.window);\n      }\n    }\n    const auto *data = take ? static_cast<const u8 *>(d.buffer->map()) : nullptr;\n    if (data) {\n      std::vector<u8> texels(bytes);\n      for (uint32_t y = 0; y < d.height; ++y)\n        std::memcpy(texels.data() + size_t(y) * row, data + size_t(y) * d.row_bytes, row);\n      d.buffer->unmap();\n      {\n        std::lock_guard<std::mutex> lock(writer.mutex);\n        writer.queue.emplace_back(std::move(d.name), std::move(texels));\n      }\n      writer.wake.notify_one();\n      ++queued;\n    } else {\n      if (take) {\n        std::lock_guard<std::mutex> lock(writer.mutex);\n        writer.queued -= bytes;\n      }\n      ++dropped;\n    }\n    Video::RetireLocked(std::unique_ptr<plume::RenderBuffer>(d.buffer));\n  }\n  RGPU_INFO("[sasrt] shadow dump: {} resolves queued, {} dropped, {:.2f} s waited for the writer "\n            "(sasrt_renut_diag_shadow_dump)",\n            queued, dropped, waited);\n  list.clear();\n}\n\n'),
    ('render/draw.cpp',
     '  plume::RenderBuffer *buffer;\n  std::string name;\n  uint32_t width, height, row_bytes, texel_bytes;\n};\n',
     '  plume::RenderBuffer *buffer;\n  std::string name;\n  uint32_t width, height, row_bytes, texel_bytes;\n  int window;\n};\n'),
    ('render/draw.cpp',
     '       w, h, row_bytes, texel});\n',
     '       w, h, row_bytes, texel, window});\n'),
]

# sasrt-nx (2026-10-30): the far-cascade shadow flicker's fix, sasrt_renut_depth_resolve_wait (docs/enhancements.md).
# Console dumps: the mask wrong in some frames with the mask alone dumped, never with the atlas dumped too (its
# readback copies put DkBarrier_Full after each cascade's resolve).
EDITS += [
    ('render/draw.cpp',
     'REXCVAR_DEFINE_BOOL(sasrt_renut_resolve_readback, true, "SASRT",\n',
     '// sasrt-nx (2026-10-30): the far-cascade shadow flicker\'s fix (ResolveDepth).\nREXCVAR_DEFINE_INT32(sasrt_renut_depth_resolve_wait, 2, "SASRT",\n                     "deko3d renderer (2026-10-30, the far-cascade shadow flicker): after each depth resolve (the "\n                     "three shadow cascades, each copied by a draw out of one depth target into the atlas; the scene "\n                     "depth) the GPU finishes it before anything after it starts, and drops its texture cache. 2: "\n                     "DkBarrier_Full (what the shadow dump\'s copies did, which ended the flicker), 1: "\n                     "DkBarrier_Primitives (wait for idle), 0: off (plume\'s fragment barrier alone: the flicker)")\n    .range(0, 2)\n    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\nREXCVAR_DEFINE_BOOL(sasrt_renut_resolve_readback, true, "SASRT",\n'),
    ('render/draw.cpp',
     '                    : 0.0f;\n  cmd->setGraphicsPushConstants(0, &push, 0, sizeof(push));\n  cmd->drawInstanced(3, 1, 0, 0);\n  TransitionTextureLocked(dest, plume::RenderTextureLayout::SHADER_READ);\n',
     "                    : 0.0f;\n  cmd->setGraphicsPushConstants(0, &push, 0, sizeof(push));\n  cmd->drawInstanced(3, 1, 0, 0);\n  // sasrt-nx (2026-10-30, sasrt_renut_depth_resolve_wait): the GPU finishes this resolve before what follows starts.\n  // The shadow cascades are three renders into one depth target, each copied into the atlas by this draw, the target\n  // cleared and drawn again after it. plume ordered that with deko3d's fragment barrier alone, and on the console a\n  // cascade's copy took in some of the next cascade (acne and coarse steps under the rocks, far shadows gone, in some\n  // frames: console dumps of 2026-10-30). The shadow dump's readback copies (DkBarrier_Full) after each cascade ended\n  // it. Ryujinx does not run the GPU's work overlapped, so it never showed.\n  if (IsDeko3D()) {\n    static const int32_t wait = REXCVAR_GET(sasrt_renut_depth_resolve_wait);\n    if (wait > 0)\n      cmd->barriers(wait >= 2 ? plume::RenderBarrierStage::COPY : plume::RenderBarrierStage::COMPUTE,\n                    plume::RenderTextureBarrier(dest->texture.get(), plume::RenderTextureLayout::SHADER_READ));\n  }\n  TransitionTextureLocked(dest, plume::RenderTextureLayout::SHADER_READ);\n"),
]

# sasrt-nx (2026-10-30, night): the shadow dump on A+B+X+Y (sasrt_renut_diag_shadow_dump_buttons, the user's request)
# and three more console A/Bs for the flicker in plume (sasrt_deko3d_read_wait, _write_wait, _clear_wait).
EDITS += [
    ('banjo_renut_tuning.cpp',
     'REXCVAR_DEFINE_BOOL(sasrt_deko3d_color_compression, true, "SASRT",\n',
     'REXCVAR_DEFINE_BOOL(sasrt_deko3d_read_wait, false, "SASRT",\n                    "deko3d renderer (2026-10-30, a console A/B for the far-cascade shadow flicker): a texture moving "\n                    "to a read layout (rendered, then sampled) waits for the GPU to go idle and drops the texture "\n                    "cache itself (DkBarrier_Primitives), instead of deko3d\'s fragment barrier with the tiled cache\'s "\n                    "invalidate")\n    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\nREXCVAR_DEFINE_BOOL(sasrt_deko3d_write_wait, false, "SASRT",\n                    "deko3d renderer (2026-10-30, a console A/B for the far-cascade shadow flicker): a texture moving "\n                    "to a write layout (sampled, then rendered or cleared again) waits for the GPU to go idle "\n                    "(DkBarrier_Primitives) instead of deko3d\'s fragment barrier")\n    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\nREXCVAR_DEFINE_BOOL(sasrt_deko3d_clear_wait, false, "SASRT",\n                    "deko3d renderer (2026-10-30, a console A/B for the far-cascade shadow flicker): the GPU goes "\n                    "idle before each clear (DkBarrier_Primitives): a clear cannot start while draws before it still "\n                    "read the target")\n    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\nREXCVAR_DEFINE_BOOL(sasrt_deko3d_color_compression, true, "SASRT",\n'),
    ('banjo_renut_tuning.cpp',
     'bool SasrtDeko3DColorCompressionOn() { return REXCVAR_GET(sasrt_deko3d_color_compression); }\n',
     'bool SasrtDeko3DColorCompressionOn() { return REXCVAR_GET(sasrt_deko3d_color_compression); }\nbool SasrtDeko3DReadWaitOn() { return REXCVAR_GET(sasrt_deko3d_read_wait); }\nbool SasrtDeko3DWriteWaitOn() { return REXCVAR_GET(sasrt_deko3d_write_wait); }\nbool SasrtDeko3DClearWaitOn() { return REXCVAR_GET(sasrt_deko3d_clear_wait); }\n'),
    ('banjo_renut_tuning.h',
     'bool SasrtDeko3DColorCompressionOn();  // sasrt_deko3d_color_compression\n',
     'bool SasrtDeko3DColorCompressionOn();  // sasrt_deko3d_color_compression\nbool SasrtDeko3DReadWaitOn();   // sasrt_deko3d_read_wait (2026-10-30)\nbool SasrtDeko3DWriteWaitOn();  // sasrt_deko3d_write_wait\nbool SasrtDeko3DClearWaitOn();  // sasrt_deko3d_clear_wait\n'),
    ('banjo_renut_deko3d.cpp',
     '  options.colorCompression = SasrtDeko3DColorCompressionOn();  // sasrt-nx (2026-10-30)\n',
     "  options.colorCompression = SasrtDeko3DColorCompressionOn();  // sasrt-nx (2026-10-30)\n  options.readWait = SasrtDeko3DReadWaitOn();    // sasrt-nx (2026-10-30, the flicker's A/Bs)\n  options.writeWait = SasrtDeko3DWriteWaitOn();\n  options.clearWait = SasrtDeko3DClearWaitOn();\n"),
    ('render/draw.cpp',
     '#include <rex/system/xmemory.h>\n',
     "#include <rex/system/xmemory.h>\n#include <rex/input/read_hook.h>  // sasrt-nx (2026-10-30): the shadow dump's A+B+X+Y\n"),
    ('render/draw.cpp',
     'REXCVAR_DEFINE_STRING(sasrt_renut_diag_shadow_dump, "", "SASRT",\n',
     'REXCVAR_DEFINE_BOOL(sasrt_renut_diag_shadow_dump_buttons, false, "SASRT",\n                    "Diagnostics (2026-10-30): sasrt_renut_diag_shadow_dump\'s windows start when A, B, X and Y are "\n                    "pressed together instead of at its times (<first s> and <every s> unused; <windows> the presses "\n                    "taken, 0 any number). Leave the shadow atlas (B5640EA8) out of its addresses: its copies hide "\n                    "the flicker")\n    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\nREXCVAR_DEFINE_STRING(sasrt_renut_diag_shadow_dump, "", "SASRT",\n'),
    ('render/draw.cpp',
     "// The dump's spec: its times, the game frames a window lasts and the resolves it takes (by guest address).\nstruct SasrtShadowDumpSpec {\n  int first = 0, every = 0, windows = 0, frames = 8;\n  std::vector<u32> addresses;  // empty: all of them\n};\n",
     '// sasrt_renut_diag_shadow_dump_buttons: A, B, X and Y down together on a user\'s pad (after one of them was up) is a\n// press; each starts a window. Called by the input system with each state the game reads (rex::input::SetStateHook).\nstd::atomic<uint32_t> g_sasrt_shadow_dump_presses{0};\n\nvoid SasrtShadowDumpButtons(uint32_t user_index, uint16_t buttons) {\n  static std::atomic<uint32_t> held{0};  // a bit a user index\n  constexpr uint16_t kAbxy = 0xF000;     // XINPUT_GAMEPAD_A | B | X | Y\n  const uint32_t bit = 1u << (user_index & 31);\n  if ((buttons & kAbxy) == kAbxy) {\n    if (!(held.fetch_or(bit, std::memory_order_relaxed) & bit)) {\n      const uint32_t n = g_sasrt_shadow_dump_presses.fetch_add(1, std::memory_order_relaxed) + 1;\n      RGPU_INFO("[sasrt] shadow dump: A+B+X+Y pressed (press {}, user {})", n, user_index);\n    }\n  } else {\n    held.fetch_and(~bit, std::memory_order_relaxed);\n  }\n}\n\n// The dump\'s spec: its times, the game frames a window lasts and the resolves it takes (by guest address).\nstruct SasrtShadowDumpSpec {\n  int first = 0, every = 0, windows = 0, frames = 8;\n  std::vector<u32> addresses;  // empty: all of them\n  bool buttons = false;        // sasrt_renut_diag_shadow_dump_buttons\n};\n'),
    ('render/draw.cpp',
     '        out.addresses.push_back(u32(std::strtoul(item.c_str(), nullptr, 16)));\n    }\n    return out;\n  }();\n',
     '        out.addresses.push_back(u32(std::strtoul(item.c_str(), nullptr, 16)));\n    }\n    out.buttons = REXCVAR_GET(sasrt_renut_diag_shadow_dump_buttons);\n    if (out.buttons)\n      rex::input::SetStateHook(&SasrtShadowDumpButtons);\n    return out;\n  }();\n'),
    ('render/draw.cpp',
     '// The window this game frame is in (-1: none). Windows of <frames> consecutive game frames from the first frame past\n// each time mark.\nint SasrtShadowDumpWindow(uint64_t frame) {\n  const SasrtShadowDumpSpec &spec = SasrtShadowDumpSpecGet();\n  if (spec.windows <= 0)\n    return -1;\n  static const auto start = std::chrono::steady_clock::now();\n  static int window = -1;\n  static uint64_t window_frame = 0;\n  static int next = 0;\n  const double seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();\n  if (window >= 0 && frame >= window_frame + uint64_t(spec.frames))\n    window = -1;\n  if (window < 0 && next < spec.windows && seconds >= double(spec.first) + double(next) * double(std::max(1, spec.every))) {\n    window = next++;\n    window_frame = frame;\n    RGPU_INFO("[sasrt] shadow dump window {} from game frame {} ({:.0f} s, {} frames, {} addresses)", window, frame,\n              seconds, spec.frames, spec.addresses.size());\n  }\n  return window;\n}\n',
     '// The window this game frame is in (-1: none). Windows of <frames> consecutive game frames from the first frame past\n// each time mark, or with sasrt_renut_diag_shadow_dump_buttons from the first frame after each A+B+X+Y.\nint SasrtShadowDumpWindow(uint64_t frame) {\n  const SasrtShadowDumpSpec &spec = SasrtShadowDumpSpecGet();\n  if (spec.windows <= 0 && !spec.buttons)\n    return -1;\n  static const auto start = std::chrono::steady_clock::now();\n  static int window = -1;\n  static uint64_t window_frame = 0;\n  static int next = 0;\n  static uint32_t presses_seen = 0;\n  const double seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();\n  if (window >= 0 && frame >= window_frame + uint64_t(spec.frames))\n    window = -1;\n  if (window < 0 && (spec.windows <= 0 || next < spec.windows)) {\n    bool begin;\n    if (spec.buttons) {\n      const uint32_t presses = g_sasrt_shadow_dump_presses.load(std::memory_order_relaxed);\n      begin = presses != presses_seen;\n      presses_seen = presses;\n    } else {\n      begin = seconds >= double(spec.first) + double(next) * double(std::max(1, spec.every));\n    }\n    if (begin) {\n      window = next++;\n      window_frame = frame;\n      RGPU_INFO("[sasrt] shadow dump window {} from game frame {} ({:.0f} s, {}, {} frames, {} addresses)", window,\n                frame, seconds, spec.buttons ? "A+B+X+Y" : "its time", spec.frames, spec.addresses.size());\n    }\n  }\n  return window;\n}\n'),
]

# sasrt-nx (2026-10-30, late night): sasrt_renut_depth_resolve_wait 2 did not end the flicker on the console. The
# atlas as the shading read it (sasrt_renut_diag_shadow_dump_late), and 3 / 4: the dump's own copy after each
# cascade, without the file. The key's default back to 0.
EDITS += [
    ('render/textures.h',
     'HostTexture *FindHostTextureBySlotLocked(uint32_t slot);\n',
     'HostTexture *FindHostTextureBySlotLocked(uint32_t slot);\n// sasrt-nx (2026-10-30, sasrt_renut_diag_shadow_dump_late): the host texture of a guest texture address, or null.\nHostTexture *FindHostTextureByVaLocked(u32 texture_va);\n'),
    ('render/textures.cpp',
     'HostTexture *FindHostTextureBySlotLocked(uint32_t slot) {\n',
     'HostTexture *FindHostTextureByVaLocked(u32 texture_va) {\n  const auto it = g_textures.find(texture_va);\n  return it != g_textures.end() ? it->second.get() : nullptr;\n}\n\nHostTexture *FindHostTextureBySlotLocked(uint32_t slot) {\n'),
    ('render/draw.cpp',
     'REXCVAR_DEFINE_BOOL(sasrt_renut_diag_shadow_dump_buttons, false, "SASRT",\n',
     'REXCVAR_DEFINE_STRING(sasrt_renut_diag_shadow_dump_late, "", "SASRT",\n                      "Diagnostics (2026-10-30): \\"<address>@<after address>[,...]\\": in a shadow dump window the "\n                      "texture at <address> is copied whole right after the dumped resolve into <after address>, not "\n                      "when it is resolved into. \\"B5640EA8@B5640E28\\": the shadow atlas as the shading read it, "\n                      "after the shadow mask, with no copy between the cascades (those hide the flicker)")\n    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\nREXCVAR_DEFINE_BOOL(sasrt_renut_diag_shadow_dump_buttons, false, "SASRT",\n'),
    ('render/draw.cpp',
     'void SasrtShadowDumpLocked(VideoState &s, HostTexture *dest, const plume::RenderRect &region, const char *kind,\n                           u32 guest_va) {\n  const uint64_t frame = g_sasrt_game_frames.load(std::memory_order_relaxed);\n  const int window = SasrtShadowDumpWindow(frame);\n  if (window < 0 || !dest || !dest->texture || region.right <= region.left || region.bottom <= region.top)\n    return;\n  const std::vector<u32> &only = SasrtShadowDumpSpecGet().addresses;\n  if (!only.empty() && std::find(only.begin(), only.end(), guest_va) == only.end())\n    return;\n',
     "// sasrt_renut_diag_shadow_dump_late: {texture address, the address after whose resolve it is copied}.\nconst std::vector<std::pair<u32, u32>> &SasrtShadowDumpLateGet() {\n  static const std::vector<std::pair<u32, u32>> late = [] {\n    std::vector<std::pair<u32, u32>> out;\n    const std::string text = REXCVAR_GET(sasrt_renut_diag_shadow_dump_late);\n    for (size_t at = 0; at < text.size();) {\n      const size_t comma = std::min(text.find(',', at), text.size());\n      const std::string item = text.substr(at, comma - at);\n      at = comma + 1;\n      const size_t sep = item.find('@');\n      if (sep != std::string::npos)\n        out.emplace_back(u32(std::strtoul(item.substr(0, sep).c_str(), nullptr, 16)),\n                         u32(std::strtoul(item.substr(sep + 1).c_str(), nullptr, 16)));\n    }\n    return out;\n  }();\n  return late;\n}\n\nvoid SasrtShadowDumpLocked(VideoState &s, HostTexture *dest, const plume::RenderRect &region, const char *kind,\n                           u32 guest_va, bool late = false) {\n  const uint64_t frame = g_sasrt_game_frames.load(std::memory_order_relaxed);\n  const int window = SasrtShadowDumpWindow(frame);\n  if (window < 0 || !dest || !dest->texture || region.right <= region.left || region.bottom <= region.top)\n    return;\n  const std::vector<u32> &only = SasrtShadowDumpSpecGet().addresses;\n  if (!late && !only.empty() && std::find(only.begin(), only.end(), guest_va) == only.end())\n    return;\n"),
    ('render/draw.cpp',
     '       fmt::format("w{}_f{}_{:04}_{}_{:08X}_x{}_y{}_{}x{}_fmt{}", window, frame, serial++, kind, guest_va, region.left,\n                   region.top, w, h, u32(dest->host_format)),\n       w, h, row_bytes, texel, window});\n}\n',
     '       fmt::format("w{}_f{}_{:04}_{}_{:08X}_x{}_y{}_{}x{}_fmt{}", window, frame, serial++, kind, guest_va, region.left,\n                   region.top, w, h, u32(dest->host_format)),\n       w, h, row_bytes, texel, window});\n  if (late)\n    return;\n  for (const auto &[late_va, after_va] : SasrtShadowDumpLateGet()) {\n    if (after_va != guest_va || late_va == guest_va)\n      continue;\n    if (HostTexture *t = FindHostTextureByVaLocked(late_va); t && t->texture)\n      SasrtShadowDumpLocked(s, t, plume::RenderRect(0, 0, int32_t(t->alloc_width), int32_t(t->alloc_height)), "late",\n                            late_va, true);\n  }\n}\n'),
    ('render/draw.cpp',
     'REXCVAR_DEFINE_INT32(sasrt_renut_depth_resolve_wait, 2, "SASRT",\n                     "deko3d renderer (2026-10-30, the far-cascade shadow flicker): after each depth resolve (the "\n                     "three shadow cascades, each copied by a draw out of one depth target into the atlas; the scene "\n                     "depth) the GPU finishes it before anything after it starts, and drops its texture cache. 2: "\n                     "DkBarrier_Full (what the shadow dump\'s copies did, which ended the flicker), 1: "\n                     "DkBarrier_Primitives (wait for idle), 0: off (plume\'s fragment barrier alone: the flicker)")\n    .range(0, 2)\n',
     'REXCVAR_DEFINE_INT32(sasrt_renut_depth_resolve_wait, 0, "SASRT",\n                     "deko3d renderer (2026-10-30, console A/Bs for the far-cascade shadow flicker): after each depth "\n                     "resolve (the three shadow cascades, each copied by a draw out of one depth target into the "\n                     "atlas; the scene depth): 1 DkBarrier_Primitives (wait for idle) and 2 DkBarrier_Full, both "\n                     "with the texture cache dropped (2 did not end the flicker); 3 a copy of one texel of it into "\n                     "a scratch buffer and 4 of all of it, plume\'s readback copy with its barriers (DkBarrier_Full "\n                     "and the texture cache dropped before, DkBarrier_Full and the L2 cache dropped after), what the "\n                     "shadow dump did after each cascade; 0 none")\n    .range(0, 4)\n'),
    ('render/draw.cpp',
     'bool ResolveDepth(HostSurface *surface, HostTexture *dest, const ClearRect &src, i32 dest_x,\n',
     "// sasrt-nx (2026-10-30, sasrt_renut_depth_resolve_wait 3 and 4): what the shadow dump did after each cascade's\n// resolve, without the file: a copy out of the resolve's region (one texel or all of it) into a scratch readback\n// buffer nothing reads. plume brackets the copy with DkBarrier_Full and the texture cache dropped before it, and\n// DkBarrier_Full and the L2 cache dropped after it.\nvoid SasrtResolveCopyOutLocked(VideoState &s, HostTexture *dest, const plume::RenderRect &region, bool whole) {\n  if (!dest || !dest->texture || region.right <= region.left || region.bottom <= region.top)\n    return;\n  switch (dest->host_format) {\n  case plume::RenderFormat::R32_FLOAT:\n  case plume::RenderFormat::R8G8B8A8_UNORM:\n  case plume::RenderFormat::B8G8R8A8_UNORM:\n    break;\n  default:\n    return;\n  }\n  constexpr uint64_t kScratchBytes = uint64_t(16) << 20;\n  static plume::RenderBuffer *scratch = nullptr;  // kept until exit; the GPU's copies overwrite it, nothing reads it\n  const uint32_t w = whole ? uint32_t(region.right - region.left) : 1u;\n  const uint32_t h = whole ? uint32_t(region.bottom - region.top) : 1u;\n  const uint32_t row_bytes = (w * 4u + 255u) & ~255u;\n  if (uint64_t(row_bytes) * h > kScratchBytes)\n    return;\n  if (!scratch)\n    scratch = s.device->createBuffer(plume::RenderBufferDesc::ReadbackBuffer(kScratchBytes)).release();\n  if (!scratch)\n    return;\n  TransitionTextureLocked(dest, plume::RenderTextureLayout::COPY_SOURCE);\n  const plume::RenderBox box(region.left, region.top, region.left + int32_t(w), region.top + int32_t(h));\n  s.command_list->copyTextureRegion(\n      plume::RenderTextureCopyLocation::PlacedFootprint(scratch, dest->host_format, w, h, 1, row_bytes / 4u, 0),\n      plume::RenderTextureCopyLocation::Subresource(dest->texture.get()), 0, 0, 0, &box);\n  TransitionTextureLocked(dest, plume::RenderTextureLayout::SHADER_READ);\n  g_bound.framebuffer = nullptr;\n}\n\nbool ResolveDepth(HostSurface *surface, HostTexture *dest, const ClearRect &src, i32 dest_x,\n"),
    ('render/draw.cpp',
     '                    plume::RenderTextureBarrier(dest->texture.get(), plume::RenderTextureLayout::SHADER_READ));\n  }\n  TransitionTextureLocked(dest, plume::RenderTextureLayout::SHADER_READ);\n',
     '                    plume::RenderTextureBarrier(dest->texture.get(), plume::RenderTextureLayout::SHADER_READ));\n  }\n  TransitionTextureLocked(dest, plume::RenderTextureLayout::SHADER_READ);\n  if (IsDeko3D()) {\n    static const int32_t copy_out = REXCVAR_GET(sasrt_renut_depth_resolve_wait);\n    if (copy_out >= 3)\n      SasrtResolveCopyOutLocked(\n          s, dest,\n          ScaleRect(plume::RenderRect(dest_x, dest_y, dest_x + (src.x2 - src.x1), dest_y + (src.y2 - src.y1)),\n                    surface->scale),\n          copy_out >= 4);\n  }\n'),
    ('render/draw.cpp',
     '    if (wait > 0)\n      cmd->barriers(wait >= 2 ? plume::RenderBarrierStage::COPY : plume::RenderBarrierStage::COMPUTE,',
     '    if (wait == 1 || wait == 2)\n      cmd->barriers(wait == 2 ? plume::RenderBarrierStage::COPY : plume::RenderBarrierStage::COMPUTE,'),
]

# sasrt-nx (2026-11-03): the far-cascade shadow flicker, sasrt_renut_diag_light_volumes = -1: the light-volume log
# follows the shadow dump's A+B+X+Y windows and adds each draw's state words and texture bindings as bound
# (docs/enhancements.md). newlogs9: the mask differs frame to frame with the atlas and the depth the same.
EDITS += [
    ('render/draw.cpp',
     'namespace renut::gpu {\n',
     "namespace renut::gpu {\n// sasrt-nx (2026-11-03, sasrt_renut_diag_light_volumes -1): the shadow dump's window (defined with the dump).\nnamespace detail {\nint SasrtShadowDumpWindow(uint64_t frame);\n}  // namespace detail\n"),
    ('render/draw.cpp',
     '      REXCVAR_GET(sasrt_renut_diag_constants_verify) || REXCVAR_GET(sasrt_renut_diag_light_volumes) > 0;\n',
     '      REXCVAR_GET(sasrt_renut_diag_constants_verify) || REXCVAR_GET(sasrt_renut_diag_light_volumes) != 0;\n'),
    ('render/draw.cpp',
     '                     "Diagnostics: after this many frames that drew the race\'s light volumes (0: off), ten "\n',
     '                     "Diagnostics: after this many frames that drew the race\'s light volumes (0: off; -1: the "\n                     "shadow dump\'s A+B+X+Y windows instead, each draw with its depth, stencil, clip and cull "\n                     "words, alpha test and texture slots as bound: sasrt-nx 2026-11-03), ten "\n'),
    ('render/draw.cpp',
     '                        bool pushed, bool fast, const Targets *targets = nullptr) {\n',
     '                        bool pushed, bool fast, const Targets *targets = nullptr,\n                        const SharedConstants *sc = nullptr, u32 texture_mask = 0) {\n'),
    ('render/draw.cpp',
     '  const bool in_window = window && frame >= window && frame < window + 10;\n',
     "  // sasrt-nx (2026-11-03): -1 follows the shadow dump's A+B+X+Y windows (asked for the light volumes and the\n  // casters only, so the window begins at the first of them after a press, the frame the dump starts at).\n  const bool in_window =\n      volumes_from < 0 ? (light_volume || (targets && targets->width == 1024 && targets->height == 1024)) &&\n                             detail::SasrtShadowDumpWindow(frame) >= 0\n                       : window && frame >= window && frame < window + 10;\n"),
    ('render/draw.cpp',
     '    RGPU_INFO("[sasrt] light volume: frame {} draw {} ({}) vs {:016X} ps {:016X} replay {} running {}:{}", frame,\n',
     '    // sasrt-nx (2026-11-03, -1): the draw\'s depth, hi-z, clip, cull and colour words, its stencil bytes, the alpha\n    // test and the texture slots as the host binds them (the descriptor index, the sampler word, and the host\n    // texture the index names now). The far-cascade shadow flicker: the mask differs frame to frame on the\n    // console with the atlas and the scene depth the same (newlogs9); what else the shading draws see.\n    if (volumes_from < 0 && vs_constants.state) {\n      const u8 *const st = vs_constants.state;\n      const auto word = [st](u32 off) {\n        u32 w;\n        std::memcpy(&w, st + off, 4);\n        return __builtin_bswap32(w);\n      };\n      text += fmt::format(" | depth {:08X} hi {:08X} clip {:08X} mode {:08X} colour {:08X} stencil {:02X} {:02X} "\n                          "{:02X} {:02X} ccw {:02X} {:02X} {:02X} {:02X}",\n                          word(0x2934), word(0x2940), word(0x2944), word(0x2948), word(0x293C), st[0x2900],\n                          st[0x2901], st[0x2902], st[0x2903], st[0x28FC], st[0x28FD], st[0x28FE], st[0x28FF]);\n      if (sc)\n        text += fmt::format(" alpha {} {:.4g} fltmax {:.4g} remap {:.4g} {:.4g} rt {:.4g} bools {:08X} {:08X}",\n                            sc->alpha_test_func, sc->alpha_threshold, sc->flt_max, sc->depth_remap[0],\n                            sc->depth_remap[1], sc->rt_scale[0], sc->booleans[4], sc->booleans[5]);\n      for (u32 r = 0; sc && r < 4; ++r) {\n        if (!((texture_mask >> r) & 1))\n          continue;\n        const u32 index = sc->texture_indices[0][r], sampler = sc->sampler_indices[r];\n        text += fmt::format(" | t{} va {:08X} index {:08X} sampler {:08X}", r,\n                            word(d3d::kDeviceOffsetTextures + r * 4), index, sampler);\n        if (HostTexture *t = FindHostTextureBySlotLocked(index & ((1u << kResolutionScaleShift) - 1u)))\n          text += fmt::format(" host {:08X} {}x{} fmt {} slot {} {}{}", t->guest_va, t->width, t->height,\n                              int(t->host_format), t->slot, t->render_target ? "target " : "",\n                              t->gpu_written ? "gpu" : "cpu");\n        else\n          text += " host none";\n      }\n    }\n    RGPU_INFO("[sasrt] light volume: frame {} draw {} ({}) vs {:016X} ps {:016X} replay {} running {}:{}", frame,\n'),
    ('render/draw.cpp',
     '    SasrtDiagConstants(call, vs, ps, vs_constants, ps_constants, vs_used, ps_used, g_bound.pushed_vs,\n                       g_bound.pushed_ps, true, true);\n',
     '    SasrtDiagConstants(call, vs, ps, vs_constants, ps_constants, vs_used, ps_used, g_bound.pushed_vs,\n                       g_bound.pushed_ps, true, true, nullptr, &sc, texture_mask);\n'),
    ('render/draw.cpp',
     '                       pushed ? g_bound.pushed_ps : g_bound.ps_constants, pushed, false, &targets);\n',
     '                       pushed ? g_bound.pushed_ps : g_bound.ps_constants, pushed, false, &targets, &sc,\n                       texture_mask);\n'),
]

# sasrt-nx (2026-11-03, later): the same diagnostic, part 2: a resolve destination made again is logged with the
# reason (the PC binds the scene depth through two host textures on alternate frames), and the light-volume
# lines carry the bound texture's resolve count and description.
EDITS += [
    ('render/textures.cpp',
     '               slot->alloc_width != scale.Size(slot->width) || slot->alloc_height != scale.Size(slot->height))) {\n    Retire(*slot);\n    slot.reset();\n  }\n',
     '               slot->alloc_width != scale.Size(slot->width) || slot->alloc_height != scale.Size(slot->height))) {\n    // sasrt-nx (2026-11-03, diagnostics): a destination made again, and why (the first 64, then every 1024th).\n    static uint32_t remade = 0;\n    if (remade++ < 64 || remade % 1024 == 0)\n      RGPU_INFO("[sasrt] resolve destination {:08X} ({}x{}, {} resolves) made again ({} so far): not a target {}, "\n                "desc differs {}, no texture {}, format {} vs {}, scale differs {}, size differs {}; desc {:08X} {:08X} "\n                "{:08X} {:08X} {:08X} {:08X} -> {:08X} {:08X} {:08X} {:08X} {:08X} {:08X}",\n                texture_va, slot->width, slot->height, slot->resolves, remade, !slot->render_target,\n                std::memcmp(slot->desc, desc, sizeof(desc)) != 0, !slot->texture, int(slot->host_format), int(format),\n                slot->scale != scale,\n                slot->alloc_width != scale.Size(slot->width) || slot->alloc_height != scale.Size(slot->height),\n                slot->desc[0], slot->desc[1], slot->desc[2], slot->desc[3], slot->desc[4], slot->desc[5], desc[0],\n                desc[1], desc[2], desc[3], desc[4], desc[5]);\n    Retire(*slot);\n    slot.reset();\n  }\n'),
    ('render/draw.cpp',
     '          text += fmt::format(" host {:08X} {}x{} fmt {} slot {} {}{}", t->guest_va, t->width, t->height,\n                              int(t->host_format), t->slot, t->render_target ? "target " : "",\n                              t->gpu_written ? "gpu" : "cpu");\n',
     '          text += fmt::format(" host {:08X} {}x{} fmt {} slot {} {}{} resolves {} desc {:08X} {:08X} {:08X}",\n                              t->guest_va, t->width, t->height, int(t->host_format), t->slot,\n                              t->render_target ? "target " : "", t->gpu_written ? "gpu" : "cpu", t->resolves,\n                              t->desc[0], t->desc[1], t->desc[2]);\n'),
]

# sasrt-nx (2026-11-03): sasrt_strip_markers, rr6-nx's fix of the range draw path ported (credit rr6-nx): an indexed
# strip's restart markers kept out of the vertex range and rewritten to the host marker (docs/enhancements.md).
EDITS += [
    ('render/draw.cpp',
     'REXCVAR_DEFINE_BOOL(sasrt_renut_resolve_readback, true, "SASRT",\n',
     '// sasrt-nx (2026-11-03, from rr6-nx\'s rr6_strip_markers, credit rr6-nx): PrepareGeometry.\nREXCVAR_DEFINE_BOOL(sasrt_strip_markers, true, "SASRT",\n                    "Renut\'s renderer (2026-11-03, rr6-nx\'s finding): an indexed strip\'s restart markers (the "\n                    "all-ones index) are kept out of the vertex range a draw converts and rewritten to the host "\n                    "format\'s marker, so the strip cuts there as the console\'s GPU cuts it. Off, as Renut had it: "\n                    "the marker counted as vertex 65535, the range became the buffer\'s tail, the host indices went "\n                    "32-bit and 0xFFFF in them restarts nothing on deko3d or Vulkan (their marker is 0xFFFFFFFF): "\n                    "the strip ran on through the cut and the cut\'s vertex read past the copy (triangles to the "\n                    "origin). A whole-buffer copy keeps the guest\'s 16-bit indices, so the fault showed only while "\n                    "no copy existed: on the console, which refuses copies under memory pressure, often")\n    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\nREXCVAR_DEFINE_BOOL(sasrt_renut_resolve_readback, true, "SASRT",\n'),
    ('render/draw.cpp',
     '  bool cacheable_indices = false;\n',
     "  bool cacheable_indices = false;\n  // sasrt-nx (2026-11-03, sasrt_strip_markers; rr6-nx's rr6_strip_markers): the strip's restart markers among\n  // g_indices, and the guest's marker value.\n  const bool strip = !expand && (call.primitive == kLineStrip || call.primitive == kTriangleStrip);\n  u32 markers = 0, guest_marker = 0xFFFFu;\n"),
    ('render/draw.cpp',
     '    u32 hi = 0;\n',
     '    guest_marker = is32 ? 0xFFFFFFFFu : 0xFFFFu;\n    u32 hi = 0;\n'),
    ('render/draw.cpp',
     '    if (hi - lo >= kMaxDrawVertices)\n      return false;\n',
     '    // sasrt-nx (2026-11-03, sasrt_strip_markers; rr6-nx): a strip\'s restart marker (the all-ones index of the guest\n    // format; plume restarts indexed strips at the host format\'s all-ones on every back end) is not a vertex. Taken\n    // into the range it made every strip with a cut read vertex 65535: the range became the buffer\'s tail (65536\n    // vertices converted a draw), the host indices 32-bit, and 0xFFFF in a 32-bit index buffer restarts nothing on\n    // deko3d or Vulkan: the strip ran on through the cut and the cut\'s vertex read past the copy. The markers are\n    // left out of the range and each is rewritten to the host format\'s marker below.\n    static const bool strip_markers = REXCVAR_GET(sasrt_strip_markers);\n    if (strip && hi == guest_marker && strip_markers) {\n      lo = UINT32_MAX;\n      hi = 0;\n      for (const u32 index : g_indices) {\n        if (index == guest_marker) {\n          ++markers;\n          continue;\n        }\n        lo = std::min(lo, index);\n        hi = std::max(hi, index);\n      }\n      if (lo == UINT32_MAX)\n        return false;  // markers only: nothing to draw\n      static uint64_t strips_with_markers = 0;\n      if (const uint64_t n = ++strips_with_markers; n <= 8 || (n & (n - 1)) == 0)\n        RGPU_INFO("[sasrt] strip with restart markers ({} so far): {} indices, {} markers, vertices {}..{}, {}",\n                  n, g_indices.size(), markers, lo, hi, call.primitive == kLineStrip ? "lines" : "triangles");\n    }\n    if (hi - lo >= kMaxDrawVertices)\n      return false;\n'),
    ('render/draw.cpp',
     '    UploadAllocation alloc = Video::UploadsLocked().Allocate(bytes, 16);\n    if (!alloc)\n      return false;\n',
     "    UploadAllocation alloc = Video::UploadsLocked().Allocate(bytes, 16);\n    if (!alloc)\n      return false;\n    // sasrt-nx (2026-11-03, sasrt_strip_markers; rr6-nx): each marker becomes lo + the host marker, so the rebase\n    // below (index - lo, in u32, then narrowed) leaves the host format's marker: 0xFFFF for 16-bit host indices\n    // (never a vertex: max_index is below it); for 32-bit ones 0xFFFFFFFF, except on D3D12, whose cut value is\n    // 0xFFFF for every width. The cached copy (TrackIndices) is rebased from the same g_indices.\n    if (markers) {\n      const u32 host_marker = wide && UsesVulkanBindings() ? 0xFFFFFFFFu : 0xFFFFu;\n      for (u32 &index : g_indices)\n        if (index == guest_marker)\n          index = lo + host_marker;\n    }\n"),
]

# sasrt-nx (2026-11-03): sasrt_renut_resolve_target_pages: a resolve destination kept across the base pages the
# game double-buffers behind one header (it was retired and made again every frame; docs/enhancements.md).
EDITS += [
    ('render/textures.cpp',
     'REXCVAR_DEFINE_BOOL(sasrt_renut_texture_keep_on_signs, true, "SASRT",\n',
     '// sasrt-nx (2026-11-03): ResolveTarget.\nREXCVAR_DEFINE_BOOL(sasrt_renut_resolve_target_pages, true, "SASRT",\n                    "Renut\'s renderer (2026-11-03): a resolve destination whose header now names another base "\n                    "address, everything else the same (this game double-buffers the memory behind its scene "\n                    "depth, lit scene and downsample textures: the page alternates every frame), keeps its host "\n                    "texture and takes the new description. Off: the destination is retired and made again at "\n                    "every such change (every frame here: a new image, words twin and framebuffer, a descriptor "\n                    "slot freed and taken, as it was until 2026-11-03)")\n    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\nREXCVAR_DEFINE_BOOL(sasrt_renut_texture_keep_on_signs, true, "SASRT",\n'),
    ('render/textures.cpp',
     '  if (slot && (!slot->render_target || std::memcmp(slot->desc, desc, sizeof(desc)) != 0 ||\n               !slot->texture || slot->host_format != format || slot->scale != scale ||\n               slot->alloc_width != scale.Size(slot->width) || slot->alloc_height != scale.Size(slot->height))) {\n',
     '  // sasrt-nx (2026-11-03, sasrt_renut_resolve_target_pages): the same destination at another base page (dword 1\'s\n  // page bits alone differ; the format, size, tiling, mips and dimension the same): the texture stays, the\n  // description follows, and the page\'s resolve target entry is set below. This game resolves its scene depth\n  // into two buffers on alternate frames through one header: the destination was made again every frame.\n  static const bool pages_kept = REXCVAR_GET(sasrt_renut_resolve_target_pages);\n  if (pages_kept && slot && slot->render_target && slot->texture && slot->host_format == format &&\n      slot->scale == scale && slot->alloc_width == scale.Size(slot->width) &&\n      slot->alloc_height == scale.Size(slot->height) && std::memcmp(slot->desc, desc, sizeof(desc)) != 0 &&\n      (slot->desc[1] & 0xFFFu) == (desc[1] & 0xFFFu) && slot->desc[0] == desc[0] && slot->desc[2] == desc[2] &&\n      slot->desc[3] == desc[3] && slot->desc[4] == desc[4] && slot->desc[5] == desc[5]) {\n    std::memcpy(slot->desc, desc, sizeof(desc));\n    static uint64_t kept = 0;\n    if (const uint64_t n = ++kept; n <= 4 || (n & (n - 1)) == 0)\n      RGPU_INFO("[sasrt] resolve destination {:08X} ({}x{}) kept across its base pages ({} so far; now page {:05X})",\n                texture_va, slot->width, slot->height, n, fetch.BasePage());\n  }\n  if (slot && (!slot->render_target || std::memcmp(slot->desc, desc, sizeof(desc)) != 0 ||\n               !slot->texture || slot->host_format != format || slot->scale != scale ||\n               slot->alloc_width != scale.Size(slot->width) || slot->alloc_height != scale.Size(slot->height))) {\n'),
]

# sasrt-nx (2026-11-03): sasrt_renut_diag_shadow_dump_passes: the mask target copied out after each light-volume
# shading draw in a dump window (which ring's draw goes wrong, and whether its shell or its shading does).
EDITS += [
    ('render/draw.cpp',
     'REXCVAR_DEFINE_BOOL(sasrt_renut_diag_shadow_dump_buttons, false, "SASRT",\n',
     'REXCVAR_DEFINE_BOOL(sasrt_renut_diag_shadow_dump_passes, false, "SASRT",\n                    "Diagnostics (2026-11-03): in a shadow dump window, the colour target is copied out after each "\n                    "light-volume shading draw (660 indices, a pixel shader): the shadow mask as each ring left it "\n                    "(files \\"pass\\", the draw\'s number in the frame as the address field). The copies add GPU "\n                    "barriers between the rings")\n    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\nREXCVAR_DEFINE_BOOL(sasrt_renut_diag_shadow_dump_buttons, false, "SASRT",\n'),
    ('render/draw.cpp',
     'int SasrtShadowDumpWindow(uint64_t frame);\n}  // namespace detail\n',
     'int SasrtShadowDumpWindow(uint64_t frame);\n// sasrt-nx (2026-11-03, sasrt_renut_diag_shadow_dump_passes): a colour target copied out (defined with the dump).\nvoid SasrtShadowDumpSurfaceLocked(VideoState &s, HostSurface *surface, const char *kind, u32 tag);\n}  // namespace detail\n'),
    ('render/draw.cpp',
     '    cmd->drawIndexedInstanced(geometry.index_count, geometry.instance_count, geometry.whole ? geometry.first_index : 0,\n                              0, 0);\n  } else {\n    cmd->drawInstanced(geometry.vertex_count, geometry.instance_count, 0, 0);\n  }\n',
     '    cmd->drawIndexedInstanced(geometry.index_count, geometry.instance_count, geometry.whole ? geometry.first_index : 0,\n                              0, 0);\n  } else {\n    cmd->drawInstanced(geometry.vertex_count, geometry.instance_count, 0, 0);\n  }\n  // sasrt-nx (2026-11-03, sasrt_renut_diag_shadow_dump_passes): the mask after this ring\'s shading draw.\n  {\n    static const bool passes = REXCVAR_GET(sasrt_renut_diag_shadow_dump_passes);\n    if (passes && ps && call.indexed && call.count == 660 && targets.color_count >= 1) [[unlikely]] {\n      static uint64_t pass_frame = 0;\n      static u32 pass_in_frame = 0;\n      const uint64_t now_frame = g_sasrt_game_frames.load(std::memory_order_relaxed);\n      if (now_frame != pass_frame) {\n        pass_frame = now_frame;\n        pass_in_frame = 0;\n      }\n      detail::SasrtShadowDumpSurfaceLocked(s, targets.colors[0], "pass", pass_in_frame++);\n    }\n  }\n'),
    ('render/draw.cpp',
     '    cmd->drawIndexedInstanced(geometry.index_count, geometry.instance_count, first_index,\n                              base_draw ? int32_t(geometry.whole_base) : 0, 0);\n  } else {\n    cmd->drawInstanced(geometry.vertex_count, geometry.instance_count, base_draw ? geometry.whole_base : 0u, 0);\n  }\n',
     '    cmd->drawIndexedInstanced(geometry.index_count, geometry.instance_count, first_index,\n                              base_draw ? int32_t(geometry.whole_base) : 0, 0);\n  } else {\n    cmd->drawInstanced(geometry.vertex_count, geometry.instance_count, base_draw ? geometry.whole_base : 0u, 0);\n  }\n  // sasrt-nx (2026-11-03, sasrt_renut_diag_shadow_dump_passes): the mask after this ring\'s shading draw.\n  {\n    static const bool passes = REXCVAR_GET(sasrt_renut_diag_shadow_dump_passes);\n    if (passes && ps && call.indexed && call.count == 660 && targets.color_count >= 1) [[unlikely]] {\n      static uint64_t pass_frame = 0;\n      static u32 pass_in_frame = 0;\n      const uint64_t now_frame = g_sasrt_game_frames.load(std::memory_order_relaxed);\n      if (now_frame != pass_frame) {\n        pass_frame = now_frame;\n        pass_in_frame = 0;\n      }\n      detail::SasrtShadowDumpSurfaceLocked(s, targets.colors[0], "pass", pass_in_frame++);\n    }\n  }\n'),
    ('render/draw.cpp',
     '      SasrtShadowDumpLocked(s, t, plume::RenderRect(0, 0, int32_t(t->alloc_width), int32_t(t->alloc_height)), "late",\n                            late_va, true);\n  }\n}\n',
     '      SasrtShadowDumpLocked(s, t, plume::RenderRect(0, 0, int32_t(t->alloc_width), int32_t(t->alloc_height)), "late",\n                            late_va, true);\n  }\n}\n\n// sasrt-nx (2026-11-03, sasrt_renut_diag_shadow_dump_passes): a colour target as it is now, into the dump (the\n// shadow mask target after each ring\'s shading draw). The copy ends the render pass; the next draw binds again.\nvoid SasrtShadowDumpSurfaceLocked(VideoState &s, HostSurface *surface, const char *kind, u32 tag) {\n  const uint64_t frame = g_sasrt_game_frames.load(std::memory_order_relaxed);\n  const int window = SasrtShadowDumpWindow(frame);\n  if (window < 0 || !surface || !surface->texture)\n    return;\n  uint32_t texel = 0;\n  switch (surface->format) {\n  case plume::RenderFormat::R32_FLOAT:\n  case plume::RenderFormat::R8G8B8A8_UNORM:\n  case plume::RenderFormat::B8G8R8A8_UNORM:\n    texel = 4;\n    break;\n  default:\n    return;\n  }\n  const uint32_t w = surface->scale.Size(surface->width), h = surface->scale.Size(surface->height);\n  const uint32_t row_bytes = (w * texel + 255u) & ~255u;\n  std::unique_ptr<plume::RenderBuffer> buffer =\n      s.device->createBuffer(plume::RenderBufferDesc::ReadbackBuffer(uint64_t(row_bytes) * h));\n  if (!buffer)\n    return;\n  TransitionSurfaceLocked(surface, plume::RenderTextureLayout::COPY_SOURCE);\n  const plume::RenderBox box(0, 0, int32_t(w), int32_t(h));\n  s.command_list->copyTextureRegion(\n      plume::RenderTextureCopyLocation::PlacedFootprint(buffer.get(), surface->format, w, h, 1, row_bytes / texel, 0),\n      plume::RenderTextureCopyLocation::Subresource(surface->texture.get()), 0, 0, 0, &box);\n  TransitionSurfaceLocked(surface, plume::RenderTextureLayout::COLOR_WRITE);\n  g_bound.framebuffer = nullptr;\n  static uint32_t serial = 0;\n  g_sasrt_shadow_dumps[s.frame].push_back(\n      {buffer.release(),\n       fmt::format("w{}_f{}_{:04}_{}_{:08X}_x0_y0_{}x{}_fmt{}", window, frame, serial++, kind, tag, w, h,\n                   u32(surface->format)),\n       w, h, row_bytes, texel, window});\n}\n'),
    # sasrt-nx (2026-11-04, the far-cascade flicker): the shadow caster lines logged the first six draws into the
    # cascade target, which are screen-space ones every frame (c0 2^23, c1-c3 zero: the fill quads and billboards);
    # the cascade's view-projection never appeared. Now the first six draws whose c3 is set (a world transform in
    # c0-c3), so the atlas's matrices can be compared with the mask draws' c16-c18 frame by frame.
    ('render/draw.cpp',
     '    if (casters++ < 6) {\n',
     '    ++casters;\n'
     '    // sasrt-nx (2026-11-04): the first draws of each frame are screen-space ones (c0 2^23, c1-c3 zero); the logged\n'
     '    // ones are the first six whose c3 is set, a world transform: the cascade\'s view-projection in c0-c3.\n'
     '    static uint64_t world_frame = 0;\n'
     '    static u32 world_logged = 0;\n'
     '    if (frame != world_frame) {\n'
     '      world_frame = frame;\n'
     '      world_logged = 0;\n'
     '    }\n'
     '    // PC check 2026-11-04 (sasrt_675): the screen-space quads read groups 0-1 only (c0-c7); the meshes and the\n'
     '    // billboards read groups 28-31 (c112-c127), c0-c3 left as the device had them. A world-space caster is one\n'
     '    // whose shader reads a group past 1; logged are the registers of its first two such groups.\n'
     '    const bool world_caster = (used_groups & ~(3ull << 62)) != 0;\n'
     '    if (world_caster && world_logged++ < 6) {\n'),
    ('render/draw.cpp',
     '      for (u32 reg = 0; reg < 8; ++reg) {\n'
     '        const bool own = !vs_constants.running || ((vs_constants.set >> (63 - reg / 4)) & 1);\n'
     '        text += fmt::format(" c{}{} {}", reg, own ? "" : "*", SasrtRegisterText(vs_constants.Register(reg)));\n'
     '      }\n'
     '      RGPU_INFO("[sasrt] shadow caster:',
     '      u32 shown = 0;\n'
     '      for (u32 g = 2; g < 64 && shown < 2; ++g) {\n'
     '        if (!((used_groups >> (63 - g)) & 1))\n'
     '          continue;\n'
     '        ++shown;\n'
     '        for (u32 reg = g * 4; reg < g * 4 + 4; ++reg) {\n'
     '          const bool own = !vs_constants.running || ((vs_constants.set >> (63 - reg / 4)) & 1);\n'
     '          text += fmt::format(" c{}{} {}", reg, own ? "" : "*", SasrtRegisterText(vs_constants.Register(reg)));\n'
     '        }\n'
     '      }\n'
     '      RGPU_INFO("[sasrt] shadow caster:'),
    # sasrt-nx (2026-11-04, sasrt_renut_splice_ended; the far-cascade shadow flicker): a recording knows whether the
    # game's EndCommandBuffer has run for it, so a composed buffer's splice can tell a finished recording from one the
    # worker is still writing (or has not begun again since the last frame's). sasrt_renut_hooks.cpp uses the three
    # functions; the flag is reset with each new recording.
    ('guest/command_buffers.cpp',
     '  uint64_t id = 0;  // banjo-nx (2026-10-26): a number per recording (the objects are pooled), for the census\n',
     '  uint64_t id = 0;  // banjo-nx (2026-10-26): a number per recording (the objects are pooled), for the census\n'
     '  bool ended = false;  // sasrt-nx (2026-11-04, sasrt_renut_splice_ended): the game ended this recording\n'
     '  bool captured = false;  // sasrt-nx (2026-11-04): a splice took it (taken again only once recorded again)\n'),
    ('guest/command_buffers.cpp',
     '  buffer->id = recording_id;\n',
     '  buffer->id = recording_id;\n'
     '  buffer->ended = buffer->captured = false;  // sasrt-nx (2026-11-04)\n'),
    ('guest/command_buffers.cpp',
     '    slot->id = g_recording_ids.fetch_add(1, std::memory_order_relaxed) + 1;  // banjo-nx (2026-10-26): a new recording\n',
     '    slot->id = g_recording_ids.fetch_add(1, std::memory_order_relaxed) + 1;  // banjo-nx (2026-10-26): a new recording\n'
     '    slot->ended = slot->captured = false;  // sasrt-nx (2026-11-04)\n'),
    ('guest/command_buffers.cpp',
     'std::shared_ptr<CapturedRun> CaptureCommandBufferRun(u32 command_buffer_va) {\n'
     '  auto captured = std::make_shared<CapturedRun>();\n'
     '  std::lock_guard lock(g_record_mutex);\n'
     '  CaptureBuffers(command_buffer_va, 0, captured->buffers);\n'
     '  return captured;\n'
     '}\n',
     'std::shared_ptr<CapturedRun> CaptureCommandBufferRun(u32 command_buffer_va) {\n'
     '  auto captured = std::make_shared<CapturedRun>();\n'
     '  std::lock_guard lock(g_record_mutex);\n'
     '  CaptureBuffers(command_buffer_va, 0, captured->buffers);\n'
     '  return captured;\n'
     '}\n'
     '\n'
     '// sasrt-nx (2026-11-04, sasrt_renut_splice_ended): the buffer a device is recording (0: none), a recording marked\n'
     '// ended (the game\'s EndCommandBuffer), and a buffer\'s recording captured only when it is ended and no splice took\n'
     '// it before (a buffer not recorded again since holds the previous frame\'s): state 0 taken, 1 still being\n'
     '// recorded (begun, not ended), 2 taken before and not recorded again, 3 no recording.\n'
     'u32 RecordingCommandBuffer(u32 device_va) {\n'
     '  return RecordingBuffer(device_va);\n'
     '}\n'
     '\n'
     'void MarkRecordingEnded(u32 command_buffer_va) {\n'
     '  std::lock_guard lock(g_record_mutex);\n'
     '  auto it = g_buffers.find(command_buffer_va);\n'
     '  if (it != g_buffers.end() && it->second)\n'
     '    it->second->ended = true;\n'
     '}\n'
     '\n'
     'std::shared_ptr<CapturedRun> CaptureIfEndedRun(u32 command_buffer_va, int *state) {\n'
     '  std::lock_guard lock(g_record_mutex);\n'
     '  auto it = g_buffers.find(command_buffer_va);\n'
     '  if (it == g_buffers.end() || !it->second) {\n'
     '    if (state)\n'
     '      *state = 3;\n'
     '    return nullptr;\n'
     '  }\n'
     '  if (!it->second->ended) {\n'
     '    if (state)\n'
     '      *state = 1;\n'
     '    return nullptr;\n'
     '  }\n'
     '  if (it->second->captured) {\n'
     '    if (state)\n'
     '      *state = 2;\n'
     '    return nullptr;\n'
     '  }\n'
     '  it->second->captured = true;\n'
     '  auto captured = std::make_shared<CapturedRun>();\n'
     '  CaptureBuffers(command_buffer_va, 0, captured->buffers);\n'
     '  if (state)\n'
     '    *state = 0;\n'
     '  return captured;\n'
     '}\n'),
    ('guest/command_buffers.h',
     'void QueueCapturedRun(u32 device_va, u32 command_buffer_va, std::shared_ptr<CapturedRun> captured);\n',
     'void QueueCapturedRun(u32 device_va, u32 command_buffer_va, std::shared_ptr<CapturedRun> captured);\n'
     '// sasrt-nx (2026-11-04, sasrt_renut_splice_ended): the buffer a device records now (0: none); a recording marked\n'
     '// ended by the game\'s EndCommandBuffer; a buffer\'s recording captured only once ended and not taken before\n'
     '// (state: 0 taken, 1 still being recorded, 2 taken before and not recorded again, 3 none).\n'
     'u32 RecordingCommandBuffer(u32 device_va);\n'
     'void MarkRecordingEnded(u32 command_buffer_va);\n'
     'std::shared_ptr<CapturedRun> CaptureIfEndedRun(u32 command_buffer_va, int *state);\n'),
    # sasrt-nx (2026-11-04): devkitPro\'s debug deko3d (PLUME_DEKO3D_DEBUG, run in Ryujinx) refused the SharedConstants
    # pushes: dkCmdBufPushConstants wants the uniform buffer\'s size a multiple of DK_UNIFORM_BUF_ALIGNMENT (256) and
    # sizeof(SharedConstants) is 1424. The release library rounds it up itself ((uboSize + 0xFF) & ~0xFF), the buffer
    # is allocated rounded (EnsurePushedBuffersSlow), so nothing changed on the hardware; the calls now pass the
    # rounded size (the binding too).
    ('render/draw.cpp',
     '  constexpr u32 kSize = u32(sizeof(SharedConstants));\n',
     '  constexpr u32 kSize = u32(sizeof(SharedConstants));\n'
     '  constexpr u32 kUboSize = (kSize + 255u) & ~255u;  // sasrt-nx (2026-11-04): DK_UNIFORM_BUF_ALIGNMENT\n'),
    ('render/draw.cpp',
     'Deko3DPushUniform(cmd, ubo, kSize,',
     'Deko3DPushUniform(cmd, ubo, kUboSize,'),
    ('render/draw.cpp',
     'Deko3DBindUniform(cmd, 2, g_pushed_buffers.address + kPushedSharedOffset, u32(sizeof(SharedConstants)));',
     'Deko3DBindUniform(cmd, 2, g_pushed_buffers.address + kPushedSharedOffset,\n'
     '                              (u32(sizeof(SharedConstants)) + 255u) & ~255u);  // sasrt-nx (2026-11-04)'),
    # sasrt-nx (2026-11-04, sasrt_deko3d_copy_wait): a texture or surface leaving a copy layout on deko3d moves with
    # a copy-stage barrier (plume: DkBarrier_Full, which waits for the copy engine); the graphics-stage move gave a
    # fragment barrier, which drains the 3D engine only. The key and its helper live in sasrt_renut_hooks.cpp.
    ('render/textures.cpp',
     '  const bool copy = layout == plume::RenderTextureLayout::COPY_DEST ||\n                    layout == plume::RenderTextureLayout::COPY_SOURCE ||\n                    layout == plume::RenderTextureLayout::RESOLVE_DEST;\n  cmd->barriers(copy ? plume::RenderBarrierStage::COPY : plume::RenderBarrierStage::GRAPHICS,\n                plume::RenderTextureBarrier(texture->texture.get(), layout));\n',
     '  const bool copy = layout == plume::RenderTextureLayout::COPY_DEST ||\n                    layout == plume::RenderTextureLayout::COPY_SOURCE ||\n                    layout == plume::RenderTextureLayout::RESOLVE_DEST;\n  // sasrt-nx (2026-11-04, sasrt_deko3d_copy_wait): leaving a copy layout on deko3d is a copy-stage move too: plume\n  // then emits DkBarrier_Full, the only barrier that waits for the copy engine (a fragment barrier drains the 3D\n  // engine only, and the draw could sample a texture the engine was still writing).\n  bool SasrtDeko3DCopyWaitOn();\n  const bool from_copy = IsDeko3D() && SasrtDeko3DCopyWaitOn() &&\n                         (texture->layout == plume::RenderTextureLayout::COPY_DEST ||\n                          texture->layout == plume::RenderTextureLayout::COPY_SOURCE ||\n                          texture->layout == plume::RenderTextureLayout::RESOLVE_DEST ||\n                          texture->layout == plume::RenderTextureLayout::RESOLVE_SOURCE);\n  cmd->barriers(copy || from_copy ? plume::RenderBarrierStage::COPY : plume::RenderBarrierStage::GRAPHICS,\n                plume::RenderTextureBarrier(texture->texture.get(), layout));\n'),
    ('render/surfaces.cpp',
     '  cmd->barriers(layout == plume::RenderTextureLayout::COPY_SOURCE ||\n                        layout == plume::RenderTextureLayout::COPY_DEST ||\n                        layout == plume::RenderTextureLayout::RESOLVE_SOURCE ||\n                        layout == plume::RenderTextureLayout::RESOLVE_DEST\n                    ? plume::RenderBarrierStage::COPY\n                    : plume::RenderBarrierStage::GRAPHICS,\n                plume::RenderTextureBarrier(surface->texture.get(), layout));\n',
     '  // sasrt-nx (2026-11-04, sasrt_deko3d_copy_wait): see TransitionTextureLocked (textures.cpp).\n  bool SasrtDeko3DCopyWaitOn();\n  const auto copy_layout = [](plume::RenderTextureLayout l) {\n    return l == plume::RenderTextureLayout::COPY_SOURCE || l == plume::RenderTextureLayout::COPY_DEST ||\n           l == plume::RenderTextureLayout::RESOLVE_SOURCE || l == plume::RenderTextureLayout::RESOLVE_DEST;\n  };\n  const bool from_copy = IsDeko3D() && SasrtDeko3DCopyWaitOn() && copy_layout(surface->layout);\n  cmd->barriers(copy_layout(layout) || from_copy ? plume::RenderBarrierStage::COPY\n                                                 : plume::RenderBarrierStage::GRAPHICS,\n                plume::RenderTextureBarrier(surface->texture.get(), layout));\n'),
    # sasrt-nx (2026-11-04, the Ridge Racer session's debug-deko3d run): the float constants' pushed UBO is 4112 bytes
    # (256 registers and the zero row), not a multiple of DK_UNIFORM_BUF_ALIGNMENT; the pushed buffer's stride is the
    # rounded 4352 (kPushedFloatStride, defined before the pushes), which the pushes and binds now pass. The debug
    # library traps the thread at its first refused input, so each such size stopped the emulator run at boot.
    ('render/draw.cpp',
     'plume::Deko3DPushUniform(cmd, ubo, kFloatConstantsUboBytes,',
     'plume::Deko3DPushUniform(cmd, ubo, u32(kPushedFloatStride),'),
    ('render/draw.cpp',
     'plume::Deko3DBindUniform(cmd, 0, g_pushed_buffers.address, kFloatConstantsUboBytes);',
     'plume::Deko3DBindUniform(cmd, 0, g_pushed_buffers.address, u32(kPushedFloatStride));  // sasrt-nx (2026-11-04)'),
    ('render/draw.cpp',
     'plume::Deko3DBindUniform(cmd, 1, g_pushed_buffers.address + kPushedFloatStride, kFloatConstantsUboBytes);',
     'plume::Deko3DBindUniform(cmd, 1, g_pushed_buffers.address + kPushedFloatStride, u32(kPushedFloatStride));'),
    # sasrt-nx (2026-11-04, sasrt_renut_diag_splice_pm4): a captured run's recorded vertex constants, for the compare
    # with the buffer's own PM4 at the submission (sasrt_renut_hooks.cpp).
    ('guest/command_buffers.cpp',
     'std::shared_ptr<CapturedRun> CaptureCommandBufferRun(u32 command_buffer_va) {\n  auto captured = std::make_shared<CapturedRun>();\n  std::lock_guard lock(g_record_mutex);\n  CaptureBuffers(command_buffer_va, 0, captured->buffers);\n  return captured;\n}\n',
     "std::shared_ptr<CapturedRun> CaptureCommandBufferRun(u32 command_buffer_va) {\n  auto captured = std::make_shared<CapturedRun>();\n  std::lock_guard lock(g_record_mutex);\n  CaptureBuffers(command_buffer_va, 0, captured->buffers);\n  return captured;\n}\n\n// sasrt-nx (2026-11-04, sasrt_renut_diag_splice_pm4): the vertex float constants c<first_reg>.. (count registers) as the\n// captured run's buffer recorded them for its first draw: its ops' state applied in order over a blank device image\n// (the first op copies every chunk and group), read at the first draw. False when the buffer or a draw is missing.\nbool CapturedRunVertexConstants(const CapturedRun &run, u32 command_buffer_va, u32 first_reg, u32 count, u32 *out) {\n  auto it = run.buffers.find(command_buffer_va);\n  if (it == run.buffers.end() || !it->second || first_reg + count > 256)\n    return false;\n  const HostCommandBuffer &b = *it->second;\n  std::vector<u8> image(d3d::kDeviceSnapshotSize, 0);\n  for (const Op &op : b.ops) {\n    if (op.state == kNone)\n      continue;\n    ApplyState(image.data(), b.arena.data() + op.state, op.plain_dirty, op.vs_dirty, op.ps_dirty);\n    if (op.kind == OpKind::Draw) {\n      std::memcpy(out, image.data() + kVertexShaderF + size_t(first_reg) * 16, size_t(count) * 16);\n      return true;\n    }\n  }\n  return false;\n}\n"),
    ('guest/command_buffers.h',
     'std::shared_ptr<CapturedRun> CaptureIfEndedRun(u32 command_buffer_va, int *state);\n',
     "std::shared_ptr<CapturedRun> CaptureIfEndedRun(u32 command_buffer_va, int *state);\n// sasrt-nx (2026-11-04, sasrt_renut_diag_splice_pm4): c<first_reg>.. of the run's buffer as its first draw recorded them.\nbool CapturedRunVertexConstants(const CapturedRun &run, u32 command_buffer_va, u32 first_reg, u32 count, u32 *out);\n"),
    # sasrt-nx (2026-11-04, replay tags): which replayed recording (buffer, id, swap counts at Begin / End / submission)
    # wrote each resolve destination, printed per bound texture and per draw in the light-volume and caster lines.
    ('render/textures.h',
     'struct HostTexture {\n  u32 guest_va = 0;\n',
     'struct HostTexture {\n  u32 guest_va = 0;\n  // sasrt-nx (2026-11-04, replay tags): the replayed recording whose resolve last wrote this texture (the spliced\n  // buffer, its recording id, the swap counts at its Begin / End / submission); 0 when none did.\n  u32 sasrt_tag_buffer = 0;\n  uint64_t sasrt_tag_recording = 0, sasrt_tag_begun = 0, sasrt_tag_ended = 0, sasrt_tag_submitted = 0;\n'),
    ('guest/command_buffers.h',
     'bool CapturedRunVertexConstants(const CapturedRun &run, u32 command_buffer_va, u32 first_reg, u32 count, u32 *out);\n',
     "bool CapturedRunVertexConstants(const CapturedRun &run, u32 command_buffer_va, u32 first_reg, u32 count, u32 *out);\n// sasrt-nx (2026-11-04, replay tags): the recording being replayed on the render thread (set before each run's\n// Replay; the resolves copy it into their destinations: HostTexture::sasrt_tag_*).\nstruct SasrtReplayTag {\n  u32 buffer = 0;\n  uint64_t recording = 0, begun = 0, ended = 0, submitted = 0;\n};\nextern SasrtReplayTag g_sasrt_replay_tag;\n"),
    ('guest/command_buffers.cpp',
     '  bool captured = false;  // sasrt-nx (2026-11-04): a splice took it (taken again only once recorded again)\n',
     '  bool captured = false;  // sasrt-nx (2026-11-04): a splice took it (taken again only once recorded again)\n  uint64_t begun_swap = 0, ended_swap = 0;  // sasrt-nx (2026-11-04, replay tags): rex::latency::SwapCount() then\n'),
    ('guest/command_buffers.cpp',
     '  buffer->ended = buffer->captured = false;  // sasrt-nx (2026-11-04)\n',
     '  buffer->ended = buffer->captured = false;  // sasrt-nx (2026-11-04)\n  buffer->begun_swap = rex::latency::SwapCount();\n  buffer->ended_swap = 0;\n'),
    ('guest/command_buffers.cpp',
     '    slot->ended = slot->captured = false;  // sasrt-nx (2026-11-04)\n',
     '    slot->ended = slot->captured = false;  // sasrt-nx (2026-11-04)\n    slot->begun_swap = rex::latency::SwapCount();\n    slot->ended_swap = 0;\n'),
    ('guest/command_buffers.cpp',
     '  if (it != g_buffers.end() && it->second)\n    it->second->ended = true;\n}\n',
     "  if (it != g_buffers.end() && it->second) {\n    it->second->ended = true;\n    it->second->ended_swap = rex::latency::SwapCount();\n  }\n}\n\nSasrtReplayTag g_sasrt_replay_tag;  // sasrt-nx (2026-11-04, replay tags)\n\n// The tag of a run about to be replayed: its top buffer's recording and swap counts.\nstatic SasrtReplayTag SasrtTagOf(const BufferSet &buffers, u32 command_buffer_va, uint64_t submitted) {\n  SasrtReplayTag tag;\n  tag.buffer = command_buffer_va;\n  tag.submitted = submitted;\n  auto it = buffers.find(command_buffer_va);\n  if (it != buffers.end() && it->second) {\n    tag.recording = it->second->id;\n    tag.begun = it->second->begun_swap;\n    tag.ended = it->second->ended_swap;\n  }\n  return tag;\n}\n"),
    ('guest/command_buffers.cpp',
     '  render_thread::Queue([run, command_buffer_va] {\n    const u8 *running = run->running.data();\n    Replay(running, run->buffers, command_buffer_va, 0, Predication(running));\n',
     '  const uint64_t submitted_swap = rex::latency::SwapCount();  // sasrt-nx (2026-11-04, replay tags)\n  render_thread::Queue([run, command_buffer_va, submitted_swap] {\n    const u8 *running = run->running.data();\n    g_sasrt_replay_tag = SasrtTagOf(run->buffers, command_buffer_va, submitted_swap);\n    Replay(running, run->buffers, command_buffer_va, 0, Predication(running));\n'),
    ('render/draw.cpp',
     '          detail::SasrtShadowDumpLocked(  // sasrt-nx (2026-10-30, sasrt_renut_diag_shadow_dump)\n              s, dest,\n',
     '          dest->sasrt_tag_buffer = g_sasrt_replay_tag.buffer;  // sasrt-nx (2026-11-04, replay tags)\n          dest->sasrt_tag_recording = g_sasrt_replay_tag.recording;\n          dest->sasrt_tag_begun = g_sasrt_replay_tag.begun;\n          dest->sasrt_tag_ended = g_sasrt_replay_tag.ended;\n          dest->sasrt_tag_submitted = g_sasrt_replay_tag.submitted;\n          detail::SasrtShadowDumpLocked(  // sasrt-nx (2026-10-30, sasrt_renut_diag_shadow_dump)\n              s, dest,\n'),
    ('render/draw.cpp',
     '            detail::SasrtShadowDumpLocked(s, dest, dest_rect, "colour", dest_texture_va);  // 2026-10-30\n',
     '            dest->sasrt_tag_buffer = g_sasrt_replay_tag.buffer;  // sasrt-nx (2026-11-04, replay tags)\n            dest->sasrt_tag_recording = g_sasrt_replay_tag.recording;\n            dest->sasrt_tag_begun = g_sasrt_replay_tag.begun;\n            dest->sasrt_tag_ended = g_sasrt_replay_tag.ended;\n            dest->sasrt_tag_submitted = g_sasrt_replay_tag.submitted;\n            detail::SasrtShadowDumpLocked(s, dest, dest_rect, "colour", dest_texture_va);  // 2026-10-30\n'),
    ('render/draw.cpp',
     '          text += fmt::format(" host {:08X} {}x{} fmt {} slot {} {}{} resolves {} desc {:08X} {:08X} {:08X}",\n                              t->guest_va, t->width, t->height, int(t->host_format), t->slot,\n                              t->render_target ? "target " : "", t->gpu_written ? "gpu" : "cpu", t->resolves,\n                              t->desc[0], t->desc[1], t->desc[2]);\n',
     '          text += fmt::format(" host {:08X} {}x{} fmt {} slot {} {}{} resolves {} desc {:08X} {:08X} {:08X}",\n                              t->guest_va, t->width, t->height, int(t->host_format), t->slot,\n                              t->render_target ? "target " : "", t->gpu_written ? "gpu" : "cpu", t->resolves,\n                              t->desc[0], t->desc[1], t->desc[2]);\n          // sasrt-nx (2026-11-04, replay tags): the recording whose resolve last wrote it.\n          if (t->sasrt_tag_recording)\n            text += fmt::format(" tag buf {:08X} rec {} swaps b{} e{} s{}", t->sasrt_tag_buffer, t->sasrt_tag_recording,\n                                t->sasrt_tag_begun, t->sasrt_tag_ended, t->sasrt_tag_submitted);\n'),
    ('render/draw.cpp',
     '    RGPU_INFO("[sasrt] light volume: frame {} draw {} ({}) vs {:016X} ps {:016X} replay {} running {}:{}", frame,\n              g_sasrt_draw_seq, fast ? "fast" : "full", vs ? vs->hash : 0, ps ? ps->hash : 0,\n              vs_constants.replay, static_cast<const void *>(vs_constants.running), text);\n',
     '    RGPU_INFO("[sasrt] light volume: frame {} draw {} ({}) vs {:016X} ps {:016X} replay {} running {} own tag buf {:08X} "\n              "rec {} swaps b{} e{} s{}:{}", frame,\n              g_sasrt_draw_seq, fast ? "fast" : "full", vs ? vs->hash : 0, ps ? ps->hash : 0,\n              vs_constants.replay, static_cast<const void *>(vs_constants.running), g_sasrt_replay_tag.buffer,\n              g_sasrt_replay_tag.recording, g_sasrt_replay_tag.begun, g_sasrt_replay_tag.ended,\n              g_sasrt_replay_tag.submitted, text);\n'),
    ('render/draw.cpp',
     '      RGPU_INFO("[sasrt] shadow caster: frame {} draw {} vs {:016X} ps {:016X} count {} replay {} running {} "\n                "groups used {:016X} from the running device {:016X} constants {:016X} clip control {:08X}:{}", frame,\n                g_sasrt_draw_seq,\n',
     '      RGPU_INFO("[sasrt] shadow caster: frame {} draw {} vs {:016X} ps {:016X} count {} replay {} running {} "\n                "groups used {:016X} from the running device {:016X} constants {:016X} clip control {:08X} own tag buf "\n                "{:08X} rec {} swaps b{} e{} s{}:{}", frame,\n                g_sasrt_draw_seq,\n'),
    ('render/draw.cpp',
     '                vs_constants.state ? __builtin_bswap32(*reinterpret_cast<const u32 *>(vs_constants.state + 0x2944)) : 0u,\n                text);\n',
     '                vs_constants.state ? __builtin_bswap32(*reinterpret_cast<const u32 *>(vs_constants.state + 0x2944)) : 0u,\n                g_sasrt_replay_tag.buffer, g_sasrt_replay_tag.recording, g_sasrt_replay_tag.begun, g_sasrt_replay_tag.ended,\n                g_sasrt_replay_tag.submitted, text);\n'),
    # sasrt-nx (2026-11-04, replay tags): two compile fixes, applied after the entries above.
    ('guest/command_buffers.cpp',
     "\nSasrtReplayTag g_sasrt_replay_tag;  // sasrt-nx (2026-11-04, replay tags)\n\n// The tag of a run about to be replayed: its top buffer's recording and swap counts.\nstatic SasrtReplayTag SasrtTagOf(const BufferSet &buffers, u32 command_buffer_va, uint64_t submitted) {\n",
     "\n// The tag of a run about to be replayed: its top buffer's recording and swap counts (declared before\n// QueueRunCommandBuffer, its first use).\nSasrtReplayTag SasrtTagOf(const BufferSet &buffers, u32 command_buffer_va, uint64_t submitted) {\n"),
    ('guest/command_buffers.cpp',
     'void QueueRunCommandBuffer(u32 device_va, u32 command_buffer_va) {\n',
     'SasrtReplayTag g_sasrt_replay_tag;  // sasrt-nx (2026-11-04, replay tags)\nSasrtReplayTag SasrtTagOf(const BufferSet &buffers, u32 command_buffer_va, uint64_t submitted);\n\nvoid QueueRunCommandBuffer(u32 device_va, u32 command_buffer_va) {\n'),
    ('render/draw.cpp',
     '          // sasrt-nx (2026-11-04, replay tags): the recording whose resolve last wrote it.\n          if (t->sasrt_tag_recording)\n            text += fmt::format(" tag buf {:08X} rec {} swaps b{} e{} s{}", t->sasrt_tag_buffer, t->sasrt_tag_recording,\n                                t->sasrt_tag_begun, t->sasrt_tag_ended, t->sasrt_tag_submitted);\n',
     ''),
    ('render/draw.cpp',
     '          text += fmt::format(" host {:08X} {}x{} fmt {} slot {} {}{} resolves {} desc {:08X} {:08X} {:08X}",\n                              t->guest_va, t->width, t->height, int(t->host_format), t->slot,\n                              t->render_target ? "target " : "", t->gpu_written ? "gpu" : "cpu", t->resolves,\n                              t->desc[0], t->desc[1], t->desc[2]);\n',
     '          text += fmt::format(" host {:08X} {}x{} fmt {} slot {} {}{} resolves {} desc {:08X} {:08X} {:08X}{}",\n                              t->guest_va, t->width, t->height, int(t->host_format), t->slot,\n                              t->render_target ? "target " : "", t->gpu_written ? "gpu" : "cpu", t->resolves,\n                              t->desc[0], t->desc[1], t->desc[2],\n                              // sasrt-nx (2026-11-04, replay tags): the recording whose resolve last wrote it\n                              t->sasrt_tag_recording\n                                  ? fmt::format(" tag buf {:08X} rec {} swaps b{} e{} s{}", t->sasrt_tag_buffer,\n                                                t->sasrt_tag_recording, t->sasrt_tag_begun, t->sasrt_tag_ended,\n                                                t->sasrt_tag_submitted)\n                                  : std::string());\n'),
    # sasrt-nx (2026-11-04, replay tags): the tag for the captured runs too (this game's path).
    ('guest/command_buffers.cpp',
     '  render_thread::Queue([run, command_buffer_va] {\n    const u8 *running = run->running.data();\n    g_sasrt_stream_copies = run->copies.get();  // sasrt-nx (sasrt_renut_capture_recorded_streams)\n    Replay(running, run->captured->buffers, command_buffer_va, 0, Predication(running));\n',
     '  const uint64_t submitted_swap = rex::latency::SwapCount();  // sasrt-nx (2026-11-04, replay tags)\n  render_thread::Queue([run, command_buffer_va, submitted_swap] {\n    const u8 *running = run->running.data();\n    g_sasrt_replay_tag = SasrtTagOf(run->captured->buffers, command_buffer_va, submitted_swap);\n    g_sasrt_stream_copies = run->copies.get();  // sasrt-nx (sasrt_renut_capture_recorded_streams)\n    Replay(running, run->captured->buffers, command_buffer_va, 0, Predication(running));\n'),
]

# sasrt-nx (2026-11-08, sasrt_renut_diag_depth_writers): the console's dumps of 2026-11-08 show every mask's
# constants one frame ahead of the scene depth it reads; which draws wrote that depth, and the replay order.
EDITS += [
    ('render/surfaces.h',
     '  uint64_t write_seq = 0;\n  uint64_t restored_from_seq = 0;\n',
     '  uint64_t write_seq = 0;\n  uint64_t restored_from_seq = 0;\n  // sasrt-nx (2026-11-08, sasrt_renut_diag_depth_writers): since the last whole clear (which recording made it, 0:\n  // the game thread, and the game frame), the depth-writing draws of the game thread and of recordings, and the last.\n  uint64_t sasrt_clear_rec = 0, sasrt_clear_frame = 0, sasrt_last_writer_rec = 0, sasrt_last_writer_frame = 0;\n  uint32_t sasrt_writes_main = 0, sasrt_writes_rec = 0;\n'),
    ('render/textures.h',
     '  uint64_t sasrt_tag_recording = 0, sasrt_tag_begun = 0, sasrt_tag_ended = 0, sasrt_tag_submitted = 0;\n',
     "  uint64_t sasrt_tag_recording = 0, sasrt_tag_begun = 0, sasrt_tag_ended = 0, sasrt_tag_submitted = 0;\n  // sasrt-nx (2026-11-08, sasrt_renut_diag_depth_writers): the depth resolve's source as it was then (HostSurface).\n  bool sasrt_src_known = false;\n  uint64_t sasrt_src_clear_rec = 0, sasrt_src_clear_frame = 0, sasrt_src_writer_rec = 0, sasrt_src_writer_frame = 0;\n  uint32_t sasrt_src_writes_main = 0, sasrt_src_writes_rec = 0;\n"),
    ('render/draw.cpp',
     '}  // namespace detail\n\nChainHint g_chain_hint;  // banjo-nx (2026-10-20, from sa2-nx): draw.h\n',
     '}  // namespace detail\n\n// sasrt-nx (2026-11-08, sasrt_renut_diag_depth_writers; the far-cascade flicker): which draws wrote a depth target\n// since its last whole clear (the game thread\'s own, or a replayed recording\'s: g_sasrt_replay_tag, cleared after each\n// run), carried into a depth resolve\'s destination and printed with its binding; and, in a shadow dump window, each\n// replayed recording\'s start and end with the depth-writing draws on each side ("seq:" lines).\nbool SasrtDiagDepthWritersOn();  // sasrt_renut_hooks.cpp\nuint32_t g_sasrt_seq_main[3] = {}, g_sasrt_seq_run[3] = {};  // depth-writing draws: scene-sized, 1024x1024, other\nstatic int SasrtDepthKind(const HostSurface &d) {\n  return d.width == 1024 && d.height == 1024 ? 1 : (d.width >= 1000 && d.height >= 500 ? 0 : 2);\n}\nvoid SasrtStampDepthWrite(HostSurface &d) {\n  if (!SasrtDiagDepthWritersOn())\n    return;\n  const uint64_t rec = g_sasrt_replay_tag.recording;\n  d.sasrt_last_writer_rec = rec;\n  d.sasrt_last_writer_frame = g_sasrt_game_frames.load(std::memory_order_relaxed);\n  if (rec) {\n    ++d.sasrt_writes_rec;\n    ++g_sasrt_seq_run[SasrtDepthKind(d)];\n  } else {\n    ++d.sasrt_writes_main;\n    ++g_sasrt_seq_main[SasrtDepthKind(d)];\n  }\n}\nvoid SasrtStampDepthClear(HostSurface &d, bool whole) {\n  if (!whole || !SasrtDiagDepthWritersOn())\n    return;\n  d.sasrt_clear_rec = g_sasrt_replay_tag.recording;\n  d.sasrt_clear_frame = g_sasrt_game_frames.load(std::memory_order_relaxed);\n  d.sasrt_writes_main = d.sasrt_writes_rec = 0;\n  d.sasrt_last_writer_rec = d.sasrt_last_writer_frame = 0;\n}\nstd::string SasrtSrcText(const HostTexture &t) {\n  if (!t.sasrt_src_known)\n    return std::string();\n  return fmt::format(" src: cleared by {} f{}; then {} depth draws of the game thread, {} of recordings; the last {} f{}",\n                     t.sasrt_src_clear_rec ? fmt::format("rec {}", t.sasrt_src_clear_rec) : std::string("game"),\n                     t.sasrt_src_clear_frame, t.sasrt_src_writes_main, t.sasrt_src_writes_rec,\n                     t.sasrt_src_writer_rec ? fmt::format("rec {}", t.sasrt_src_writer_rec) : std::string("game"),\n                     t.sasrt_src_writer_frame);\n}\nvoid SasrtSeqNoteRun(bool start) {\n  if (!SasrtDiagDepthWritersOn())\n    return;\n  const uint64_t frame = g_sasrt_game_frames.load(std::memory_order_relaxed);\n  if (detail::SasrtShadowDumpWindow(frame) >= 0) {\n    if (start)\n      RGPU_INFO("[sasrt] seq: frame {} run rec {} buf {:08X} swaps b{} e{} s{} starts; depth-writing draws of the game "\n                "thread since the last run: {} scene, {} 1024x1024, {} other", frame, g_sasrt_replay_tag.recording,\n                g_sasrt_replay_tag.buffer, g_sasrt_replay_tag.begun, g_sasrt_replay_tag.ended,\n                g_sasrt_replay_tag.submitted, g_sasrt_seq_main[0], g_sasrt_seq_main[1], g_sasrt_seq_main[2]);\n    else\n      RGPU_INFO("[sasrt] seq: frame {} run rec {} ends: its depth-writing draws {} scene, {} 1024x1024, {} other", frame,\n                g_sasrt_replay_tag.recording, g_sasrt_seq_run[0], g_sasrt_seq_run[1], g_sasrt_seq_run[2]);\n  }\n  for (int i = 0; i < 3; ++i) {\n    g_sasrt_seq_run[i] = 0;\n    if (start)\n      g_sasrt_seq_main[i] = 0;\n  }\n}\n\nChainHint g_chain_hint;  // banjo-nx (2026-10-20, from sa2-nx): draw.h\n'),
    ('render/draw.cpp',
     '      targets.depth->write_seq = ++g_surface_write_seq;  // sasrt-nx: the EDRAM depth restore\n',
     '      targets.depth->write_seq = ++g_surface_write_seq;  // sasrt-nx: the EDRAM depth restore\n      SasrtStampDepthWrite(*targets.depth);  // sasrt-nx (2026-11-08, sasrt_renut_diag_depth_writers)\n'),
    ('render/draw.cpp',
     '    ++d->writes;  // banjo-nx (banjo_renut_resolve_skip)\n    d->write_seq = ++g_surface_write_seq;  // sasrt-nx: the EDRAM depth restore\n    g_clears_whole += is_whole;\n',
     '    ++d->writes;  // banjo-nx (banjo_renut_resolve_skip)\n    d->write_seq = ++g_surface_write_seq;  // sasrt-nx: the EDRAM depth restore\n    SasrtStampDepthClear(*d, is_whole);  // sasrt-nx (2026-11-08, sasrt_renut_diag_depth_writers)\n    g_clears_whole += is_whole;\n'),
    ('render/draw.cpp',
     '          dest->sasrt_tag_submitted = g_sasrt_replay_tag.submitted;\n',
     '          dest->sasrt_tag_submitted = g_sasrt_replay_tag.submitted;\n          dest->sasrt_src_known = SasrtDiagDepthWritersOn();  // sasrt-nx (2026-11-08, sasrt_renut_diag_depth_writers)\n          dest->sasrt_src_clear_rec = surface->sasrt_clear_rec;\n          dest->sasrt_src_clear_frame = surface->sasrt_clear_frame;\n          dest->sasrt_src_writer_rec = surface->sasrt_last_writer_rec;\n          dest->sasrt_src_writer_frame = surface->sasrt_last_writer_frame;\n          dest->sasrt_src_writes_main = surface->sasrt_writes_main;\n          dest->sasrt_src_writes_rec = surface->sasrt_writes_rec;\n'),
    ('render/draw.cpp',
     '                                                t->sasrt_tag_recording, t->sasrt_tag_begun, t->sasrt_tag_ended,\n                                                t->sasrt_tag_submitted)\n                                  : std::string());\n',
     '                                                t->sasrt_tag_recording, t->sasrt_tag_begun, t->sasrt_tag_ended,\n                                                t->sasrt_tag_submitted) +\n                                        SasrtSrcText(*t)  // sasrt-nx (2026-11-08, sasrt_renut_diag_depth_writers)\n                                  : SasrtSrcText(*t));\n'),
    ('guest/command_buffers.cpp',
     'SasrtReplayTag SasrtTagOf(const BufferSet &buffers, u32 command_buffer_va, uint64_t submitted);\n',
     'SasrtReplayTag SasrtTagOf(const BufferSet &buffers, u32 command_buffer_va, uint64_t submitted);\nvoid SasrtSeqNoteRun(bool start);  // sasrt-nx (2026-11-08, sasrt_renut_diag_depth_writers): render/draw.cpp\n'),
    ('guest/command_buffers.cpp',
     '    g_sasrt_replay_tag = SasrtTagOf(run->buffers, command_buffer_va, submitted_swap);\n    Replay(running, run->buffers, command_buffer_va, 0, Predication(running));\n  });\n',
     "    g_sasrt_replay_tag = SasrtTagOf(run->buffers, command_buffer_va, submitted_swap);\n    SasrtSeqNoteRun(true);  // sasrt-nx (2026-11-08, sasrt_renut_diag_depth_writers)\n    Replay(running, run->buffers, command_buffer_va, 0, Predication(running));\n    SasrtSeqNoteRun(false);\n    g_sasrt_replay_tag = SasrtReplayTag{};  // the game thread's own draws next: untagged\n  });\n"),
    ('guest/command_buffers.cpp',
     '    g_sasrt_stream_copies = run->copies.get();  // sasrt-nx (sasrt_renut_capture_recorded_streams)\n    Replay(running, run->captured->buffers, command_buffer_va, 0, Predication(running));\n    g_sasrt_stream_copies = nullptr;\n',
     "    g_sasrt_stream_copies = run->copies.get();  // sasrt-nx (sasrt_renut_capture_recorded_streams)\n    SasrtSeqNoteRun(true);  // sasrt-nx (2026-11-08, sasrt_renut_diag_depth_writers)\n    Replay(running, run->captured->buffers, command_buffer_va, 0, Predication(running));\n    SasrtSeqNoteRun(false);\n    g_sasrt_replay_tag = SasrtReplayTag{};  // the game thread's own draws next: untagged\n    g_sasrt_stream_copies = nullptr;\n"),
]

# sasrt-nx (2026-11-08, sasrt_renut_diag_depth_writers): the scene pass's vertex constants, own or inherited.
EDITS += [
    ('render/draw.cpp',
     "  // The shadow casters (the cascades' 1024x1024 target): the first six draws of each frame, and a count.\n  if (in_window && targets && targets->width == 1024 && targets->height == 1024) {\n",
     '  // sasrt-nx (2026-11-08, sasrt_renut_diag_depth_writers): in a dump window, the first four scene-sized draws of\n  // each replayed run (the worker\'s scene pass) and of each frame\'s own game-thread draws, with the vertex constant\n  // groups they read, which of those come from the running device (the title device at the run\'s queueing, marked\n  // *) and the first four groups\' registers: is the scene pass\'s camera its own or inherited, and whose frame.\n  if (SasrtDiagDepthWritersOn() && targets && targets->width >= 1000 && targets->height >= 500 &&\n      !(targets->width == 1024 && targets->height == 1024) && detail::SasrtShadowDumpWindow(frame) >= 0) {\n    static uint64_t scene_key = ~0ull;\n    static u32 scene_logged = 0;\n    const uint64_t key = g_sasrt_replay_tag.recording ? g_sasrt_replay_tag.recording : (frame | (1ull << 63));\n    if (key != scene_key) {\n      scene_key = key;\n      scene_logged = 0;\n    }\n    if (scene_logged++ < 4) {\n      uint64_t used_groups = 0;\n      for (u32 g = 0; g < 64; ++g)\n        used_groups |= uint64_t(GroupRegisters(vs_used, g) != 0) << (63 - g);\n      const uint64_t from_running = vs_constants.running ? used_groups & ~vs_constants.set : 0;\n      std::string text;\n      u32 shown = 0;\n      for (u32 g = 0; g < 64 && shown < 4; ++g) {\n        if (!((used_groups >> (63 - g)) & 1))\n          continue;\n        ++shown;\n        for (u32 reg = g * 4; reg < g * 4 + 4; ++reg) {\n          const bool own = !vs_constants.running || ((vs_constants.set >> (63 - reg / 4)) & 1);\n          text += fmt::format(" c{}{} {}", reg, own ? "" : "*", SasrtRegisterText(vs_constants.Register(reg)));\n        }\n      }\n      RGPU_INFO("[sasrt] scene pass: frame {} {} draw {} vs {:016X} count {} groups used {:016X} from the "\n                "running device {:016X}:{}", frame,\n                g_sasrt_replay_tag.recording ? fmt::format("rec {} (b{} s{})", g_sasrt_replay_tag.recording,\n                                                           g_sasrt_replay_tag.begun, g_sasrt_replay_tag.submitted)\n                                             : std::string("game"),\n                g_sasrt_draw_seq, vs ? vs->hash : 0, call.count,\n                used_groups, from_running, text);\n    }\n  }\n  // The shadow casters (the cascades\' 1024x1024 target): the first six draws of each frame, and a count.\n  if (in_window && targets && targets->width == 1024 && targets->height == 1024) {\n'),
]

# sasrt-nx (2026-11-08, sasrt_renut_swap_wait_deferred): the Swap's wait for the render thread held over to the
# game thread's next queued work, so the game computes the next camera before it blocks (the far-cascade flicker).
EDITS += [
    ('backend/render_thread.cpp',
     'REXCVAR_DEFINE_INT32(sasrt_renut_frames_ahead, 1, "SASRT",\n',
     '// sasrt-nx (2026-11-08, the far-cascade shadow flicker; docs/enhancements.md): see the key.\nREXCVAR_DEFINE_BOOL(sasrt_renut_swap_wait_deferred, false, "SASRT",\n                    "Renut\'s renderer: the game\'s wait for the render thread (sasrt_renut_frames_ahead) is not "\n                    "made at its Swap but at the first work the game thread queues after it (or its next Swap): "\n                    "between the two the game computes the next frame\'s camera, which the worker thread\'s scene "\n                    "pass, recorded meanwhile, reads. Waiting at the Swap, a render thread as slow as the "\n                    "console\'s held the game there while the worker recorded the next scene with the old camera, "\n                    "so the shadows were drawn a frame apart from the scene (the far-cascade flicker). The same "\n                    "pacing otherwise")\n    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\nREXCVAR_DEFINE_INT32(sasrt_renut_frames_ahead, 1, "SASRT",\n'),
    ('backend/render_thread.cpp',
     'std::thread::id g_thread_id;\n',
     "std::thread::id g_thread_id;\n// sasrt-nx (2026-11-08, sasrt_renut_swap_wait_deferred): the thread that queues the frames (the game's Swap), whether\n// its wait is held over to its next queued work, and the time it waited there since its last Swap.\nstd::thread::id g_frame_thread;\nbool g_deferred_wait = false;  // under g_mutex\nstd::chrono::steady_clock::duration g_deferred_waited{};  // under g_mutex\n"),
    ('backend/render_thread.cpp',
     'void WakeForWaitLocked() {\n  if (g_render_waiting && !g_queue.empty())\n    g_work_cv.notify_one();\n}\n',
     "void WakeForWaitLocked() {\n  if (g_render_waiting && !g_queue.empty())\n    g_work_cv.notify_one();\n}\n\n// sasrt-nx (2026-11-08): QueueFrame's wait (frames ahead of the render thread), under g_mutex.\nbool SwapWaitDeferredOn() {\n  static const bool on = REXCVAR_GET(sasrt_renut_swap_wait_deferred);\n  return on;\n}\nvoid WaitFramesAheadLocked(std::unique_lock<std::mutex> &lock) {\n  WakeForWaitLocked();  // sa2-nx (sa2_renut_wake_batch)\n  ++g_done_waiters;  // sa2-nx (sa2_renut_done_notify_waiters)\n  g_done_cv.wait(lock, [] {\n    static const uint64_t ahead = REXCVAR_GET(sasrt_renut_diag_no_frames_ahead)\n                                      ? 0\n                                      : std::min<uint64_t>(uint64_t(REXCVAR_GET(sasrt_renut_frames_ahead)),\n                                                           kMaxFramesAhead);  // sasrt-nx\n    return !g_running || g_stopping || g_frames_queued - g_frames_done <= ahead;\n  });\n  --g_done_waiters;\n}\n"),
    ('backend/render_thread.cpp',
     "  Start();\n  {\n    std::unique_lock lock(g_mutex);\n    // (Work queued by the render thread's own work runs after it.)\n",
     "  Start();\n  {\n    std::unique_lock lock(g_mutex);\n    // sasrt-nx (2026-11-08, sasrt_renut_swap_wait_deferred): the Swap's wait, held over to here.\n    if (g_deferred_wait && std::this_thread::get_id() == g_frame_thread) {\n      g_deferred_wait = false;\n      const auto waiting = std::chrono::steady_clock::now();\n      WaitFramesAheadLocked(lock);\n      g_deferred_waited += std::chrono::steady_clock::now() - waiting;\n    }\n    // (Work queued by the render thread's own work runs after it.)\n"),
    ('backend/render_thread.cpp',
     '  const auto waiting = std::chrono::steady_clock::now();\n  std::unique_lock lock(g_mutex);\n  WakeForWaitLocked();  // sa2-nx (sa2_renut_wake_batch)\n  ++g_done_waiters;  // sa2-nx (sa2_renut_done_notify_waiters)\n  g_done_cv.wait(lock, [] {\n    static const uint64_t ahead = REXCVAR_GET(sasrt_renut_diag_no_frames_ahead)\n                                      ? 0\n                                      : std::min<uint64_t>(uint64_t(REXCVAR_GET(sasrt_renut_frames_ahead)),\n                                                           kMaxFramesAhead);  // sasrt-nx\n    return !g_running || g_stopping || g_frames_queued - g_frames_done <= ahead;\n  });\n  --g_done_waiters;\n  const uint64_t done = g_frames_done;\n  lock.unlock();\n  const auto waited = std::chrono::steady_clock::now() - waiting;\n',
     "  const auto waiting = std::chrono::steady_clock::now();\n  std::unique_lock lock(g_mutex);\n  std::chrono::steady_clock::duration held{};\n  if (SwapWaitDeferredOn()) {\n    // sasrt-nx (2026-11-08, sasrt_renut_swap_wait_deferred): no wait here; the frame thread's next queued work\n    // (or the frame item of its next Swap, above in Push) waits. What it waited since the last Swap counts now.\n    g_frame_thread = std::this_thread::get_id();\n    g_deferred_wait = true;\n    held = g_deferred_waited;\n    g_deferred_waited = {};\n  } else {\n    WaitFramesAheadLocked(lock);\n  }\n  const uint64_t done = g_frames_done;\n  lock.unlock();\n  const auto waited = std::chrono::steady_clock::now() - waiting + held;\n"),
    ('backend/render_thread.cpp',
     'uint64_t QueueFrame(std::function<void()> work) {\n  {\n    std::lock_guard lock(g_mutex);\n    ++g_frames_queued;\n  }\n',
     'uint64_t QueueFrame(std::function<void()> work) {\n  {\n    std::unique_lock lock(g_mutex);\n    // sasrt-nx (2026-11-08, sasrt_renut_swap_wait_deferred): a wait held over from the last Swap, nothing queued since.\n    if (g_deferred_wait && std::this_thread::get_id() == g_frame_thread) {\n      g_deferred_wait = false;\n      const auto waiting = std::chrono::steady_clock::now();\n      WaitFramesAheadLocked(lock);\n      g_deferred_waited += std::chrono::steady_clock::now() - waiting;\n    }\n    ++g_frames_queued;\n  }\n'),
]

# sasrt-nx (2026-11-08, sasrt_renut_diag_trace): the frame's thread timeline's hook points.
EDITS += [
    ('d3d/hooks/device.cpp',
     '#include "renut_engine/gpu/backend/video.h"\n',
     '#include "renut_engine/gpu/backend/video.h"\n#include "renut_engine/sasrt_trace.h"  // sasrt-nx (2026-11-08, sasrt_renut_diag_trace)\n'),
    ('d3d/hooks/device.cpp',
     'void D3DDevice_Swap_hook(u32 device_va, u32 front_buffer, u32 /*parameters*/) {\n',
     'void D3DDevice_Swap_hook(u32 device_va, u32 front_buffer, u32 /*parameters*/) {\n  sasrt::trace::Note(sasrt::trace::kSwap, g_sasrt_game_frames.load(std::memory_order_relaxed));\n'),
    ('d3d/hooks/device.cpp',
     '  sa2::renut::PaceSwap(device_va);\n',
     '  sasrt::trace::Note(sasrt::trace::kPaceBegin);\n  sa2::renut::PaceSwap(device_va);\n  sasrt::trace::Note(sasrt::trace::kPaceEnd);\n'),
    ('d3d/hooks/device.cpp',
     '  for (;;) {\n    RunReadyCallbacks();\n    if (!FencePending(bytes, fence))\n      break;\n',
     '  sasrt::trace::Note(sasrt::trace::kFenceWaitBegin, fence);\n  for (;;) {\n    RunReadyCallbacks();\n    if (!FencePending(bytes, fence))\n      break;\n'),
    ('d3d/hooks/device.cpp',
     '      break;  // no render thread: nothing would complete it\n  }\n',
     '      break;  // no render thread: nothing would complete it\n  }\n  sasrt::trace::Note(sasrt::trace::kFenceWaitEnd, fence);\n'),
    ('guest/callbacks.cpp',
     '#include "renut_engine/gpu/banjo_renut_checks.h"  // banjo-nx (package 27c)\n',
     '#include "renut_engine/gpu/banjo_renut_checks.h"  // banjo-nx (package 27c)\n#include "renut_engine/sasrt_trace.h"  // sasrt-nx (2026-11-08, sasrt_renut_diag_trace)\n'),
    ('guest/callbacks.cpp',
     '  banjo::renut_gpu::checks::QueueKickFlush();\n  render_thread::QueueCallbackMarker(seq);\n',
     '  sasrt::trace::Note(sasrt::trace::kCallbackInsert, function, context);\n  banjo::renut_gpu::checks::QueueKickFlush();\n  render_thread::QueueCallbackMarker(seq);\n'),
    ('guest/callbacks.cpp',
     '    rex::ppc::GuestToHostFunction<void>(function, callback.context);\n',
     '    sasrt::trace::Note(sasrt::trace::kCallbackRun, callback.function, callback.context);\n    rex::ppc::GuestToHostFunction<void>(function, callback.context);\n'),
    ('backend/render_thread.cpp',
     '  } else {\n    WaitFramesAheadLocked(lock);\n  }\n',
     '  } else {\n    sasrt::trace::Note(sasrt::trace::kFrameWaitBegin, g_frames_queued);\n    WaitFramesAheadLocked(lock);\n    sasrt::trace::Note(sasrt::trace::kFrameWaitEnd, g_frames_done);\n  }\n'),
    ('backend/render_thread.cpp',
     '      ++g_frames_done;\n',
     '      ++g_frames_done;\n      sasrt::trace::Note(sasrt::trace::kRenderFrameDone, g_frames_done);\n'),
    ('backend/render_thread.cpp',
     '    rex::latency::BeforeInputRead();\n',
     '    sasrt::trace::Note(sasrt::trace::kLateInputBegin);\n    rex::latency::BeforeInputRead();\n    sasrt::trace::Note(sasrt::trace::kLateInputEnd);\n'),
    ('render/draw.cpp',
     'REXCVAR_DECLARE(bool, banjo_renut_neon_compare);  // banjo-nx (2026-10-20, from sa2-nx): backend/queued.cpp\n',
     'REXCVAR_DECLARE(bool, banjo_renut_neon_compare);  // banjo-nx (2026-10-20, from sa2-nx): backend/queued.cpp\n#include "renut_engine/sasrt_trace.h"  // sasrt-nx (2026-11-08, sasrt_renut_diag_trace)\n'),
    ('backend/render_thread.cpp',
     '#include "renut_engine/gpu/backend/render_thread.h"\n',
     '#include "renut_engine/gpu/backend/render_thread.h"\n#include "renut_engine/sasrt_trace.h"  // sasrt-nx (2026-11-08, sasrt_renut_diag_trace)\n'),
    ('render/draw.cpp',
     '      window = next++;\n      window_frame = frame;\n',
     '      window = next++;\n      window_frame = frame;\n      sasrt::trace::WindowBegan(frame);  // sasrt-nx (2026-11-08, sasrt_renut_diag_trace)\n'),
]

# sasrt-nx (2026-11-08, sasrt_renut_diag_trace): the game thread's first draw after a Swap.
EDITS += [
    ('d3d/hooks/draw.cpp',
     '#include "renut_engine/gpu/backend/video.h"\n',
     '#include "renut_engine/gpu/backend/video.h"\n#include "renut_engine/sasrt_trace.h"  // sasrt-nx (2026-11-08, sasrt_renut_diag_trace)\n'),
    ('d3d/hooks/draw.cpp',
     'void D3DDevice_DrawIndexedVertices_hook(u32 device, u32 primitive, u32 base_vertex,\n                                        u32 start_index, u32 index_count) {\n  if (!Active())\n    return;\n',
     'void D3DDevice_DrawIndexedVertices_hook(u32 device, u32 primitive, u32 base_vertex,\n                                        u32 start_index, u32 index_count) {\n  if (!Active())\n    return;\n  if (sasrt::trace::On() && !IsRecordingCommandBuffer(device))  // sasrt-nx (2026-11-08, sasrt_renut_diag_trace)\n  {\n    sasrt::trace::NoteDraw(index_count);\n    if (const auto *d = GuestPtr<const u8>(device))\n      sasrt::trace::NoteGameCamera(d + offsetof(d3d::Device, m_Constants) + offsetof(d3d::Constants, VertexShaderF));\n  }\n'),
]

# sasrt-nx (2026-11-08, sasrt_renut_diag_trace): a captured run's constants at its first draw that matches.
EDITS += [
    ('guest/command_buffers.h',
     'bool CapturedRunVertexConstants(const CapturedRun &run, u32 command_buffer_va, u32 first_reg, u32 count, u32 *out);\n',
     "bool CapturedRunVertexConstants(const CapturedRun &run, u32 command_buffer_va, u32 first_reg, u32 count, u32 *out);\n// sasrt-nx (2026-11-08, sasrt_renut_diag_trace): the same for the first draw whose registers satisfy 'match' (the\n// device image's big-endian words).\nbool CapturedRunFindVertexConstants(const CapturedRun &run, u32 command_buffer_va, u32 first_reg, u32 count,\n                                    bool (*match)(const u32 *), u32 *out);\n"),
    ('guest/command_buffers.cpp',
     'bool CapturedRunVertexConstants(const CapturedRun &run, u32 command_buffer_va, u32 first_reg, u32 count, u32 *out) {\n',
     '// sasrt-nx (2026-11-08, sasrt_renut_diag_trace): command_buffers.h.\nbool CapturedRunFindVertexConstants(const CapturedRun &run, u32 command_buffer_va, u32 first_reg, u32 count,\n                                    bool (*match)(const u32 *), u32 *out) {\n  auto it = run.buffers.find(command_buffer_va);\n  if (it == run.buffers.end() || !it->second || first_reg + count > 256)\n    return false;\n  const HostCommandBuffer &b = *it->second;\n  std::vector<u8> image(d3d::kDeviceSnapshotSize, 0);\n  for (const Op &op : b.ops) {\n    if (op.state == kNone)\n      continue;\n    ApplyState(image.data(), b.arena.data() + op.state, op.plain_dirty, op.vs_dirty, op.ps_dirty);\n    if (op.kind == OpKind::Draw) {\n      std::memcpy(out, image.data() + kVertexShaderF + size_t(first_reg) * 16, size_t(count) * 16);\n      if (match(out))\n        return true;\n    }\n  }\n  return false;\n}\n\nbool CapturedRunVertexConstants(const CapturedRun &run, u32 command_buffer_va, u32 first_reg, u32 count, u32 *out) {\n'),
]

# sasrt-nx (2026-11-08, sasrt_renut_diag_trace): the camera hunt from the scene pass's replayed draws.
EDITS += [
    ('render/draw.cpp',
     'REXCVAR_DECLARE(bool, banjo_renut_neon_compare);  // banjo-nx (2026-10-20, from sa2-nx): backend/queued.cpp\n',
     'REXCVAR_DECLARE(bool, banjo_renut_neon_compare);  // banjo-nx (2026-10-20, from sa2-nx): backend/queued.cpp\nvoid SasrtHuntCamera(const uint32_t *regs);  // sasrt-nx (2026-11-08, sasrt_renut_diag_trace): sasrt_renut_hooks.cpp\n'),
    ('render/draw.cpp',
     '    if (scene_logged++ < 4) {\n',
     '    // sasrt-nx (2026-11-08, sasrt_renut_diag_trace): the first scene-pass draw with the camera block (c136 =\n    // (0 0 -1 -1), c137 = (0 0 -1 0)) after a window began looks for the camera in guest memory (PC).\n    if (g_sasrt_replay_tag.recording && sasrt::trace::On()) {\n      uint32_t regs[64];\n      for (u32 r = 0; r < 16; ++r)\n        std::memcpy(&regs[r * 4], vs_constants.Register(128 + r), 16);\n      if ((__builtin_bswap32(regs[34]) >> 16) == 0xBF80u && (__builtin_bswap32(regs[35]) >> 16) == 0xBF80u &&\n          (__builtin_bswap32(regs[38]) >> 16) == 0xBF80u && regs[39] == 0 && false)  // the End hook (worker thread) hunts\n        ::SasrtHuntCamera(regs);\n      static u32 hunt_debug = 0;\n      if (hunt_debug++ < 3)\n        RGPU_INFO("[sasrt] camera hunt check: {:08X} {:08X} {:08X} {:08X} hunt {}", __builtin_bswap32(regs[34]), __builtin_bswap32(regs[35]), __builtin_bswap32(regs[38]), regs[39], sasrt::trace::On());\n    }\n    if (scene_logged++ < 4) {\n'),
]

# sasrt-nx (2026-11-08, sasrt_renut_diag_trace): the worker's camera at its first camera-block draw.
EDITS += [
    ('guest/command_buffers.cpp',
     '#include "renut_engine/gpu/log.h"\n',
     '#include "renut_engine/gpu/log.h"\n#include "renut_engine/sasrt_trace.h"  // sasrt-nx (2026-11-08, sasrt_renut_diag_trace)\n'),
    ('guest/command_buffers.cpp',
     '  if (ShadowSortOn()) {\n    if (const auto *bytes = GuestPtr<const u8>(device_va))\n      op->sort_why = SortFacts(bytes, call, *op);\n  }\n  SetOpCall(op->call, call, GuestPtr<const u8>(device_va));\n',
     "  if (ShadowSortOn()) {\n    if (const auto *bytes = GuestPtr<const u8>(device_va))\n      op->sort_why = SortFacts(bytes, call, *op);\n  }\n  SetOpCall(op->call, call, GuestPtr<const u8>(device_va));\n  // sasrt-nx (2026-11-08, sasrt_renut_diag_trace): the first draw of each recording with the scene pass's camera\n  // block (c136 = (0 0 -1 -1), c137 = (0 0 -1 0)), noted on the recording thread with c133.w and the camera's x\n  // (c142.w) as its device holds them then.\n  if (sasrt::trace::On() && buffer) {\n    thread_local const HostCommandBuffer *noted = nullptr;\n    if (noted != buffer) {\n      if (const auto *d = GuestPtr<const u8>(device_va)) {\n        const auto word = [d](u32 reg, u32 c) {\n          u32 v;\n          std::memcpy(&v, d + kVertexShaderF + reg * 16 + c * 4, 4);\n          return __builtin_bswap32(v);\n        };\n        if ((word(136, 2) >> 16) == 0xBF80u && (word(136, 3) >> 16) == 0xBF80u && word(137, 3) == 0) {\n          noted = buffer;\n          sasrt::trace::Note(sasrt::trace::kSceneCamera, word(133, 3), word(142, 3));\n        }\n      }\n    }\n  }\n"),
]

# sasrt-nx (2026-11-08, sasrt_renut_scene_same_frame): a captured run filled after its queueing (the recording
# spliced after the submission: the scene pass of the same frame as the shading).
EDITS += [
    ('guest/command_buffers.h',
     'bool CapturedRunVertexConstants(const CapturedRun &run, u32 command_buffer_va, u32 first_reg, u32 count, u32 *out);\n',
     "bool CapturedRunVertexConstants(const CapturedRun &run, u32 command_buffer_va, u32 first_reg, u32 count, u32 *out);\n// sasrt-nx (2026-11-08, sasrt_renut_scene_same_frame): a captured run queued before its recording exists. The\n// render thread, at the run's place, waits for the slot to be filled (the recording spliced after the\n// submission) up to a timeout, then replays it, or the fallback (the recording the submission named).\nstruct SasrtRunSlot {\n  std::mutex mutex;\n  std::condition_variable cv;\n  bool filled = false;\n  u32 buffer = 0;\n  std::shared_ptr<CapturedRun> recording;\n  u32 fallback_buffer = 0;\n  std::shared_ptr<CapturedRun> fallback;\n};\nvoid QueueCapturedRunSlot(u32 device_va, std::shared_ptr<SasrtRunSlot> slot, uint32_t timeout_ms);\nvoid FillCapturedRunSlot(SasrtRunSlot &slot, u32 buffer, std::shared_ptr<CapturedRun> recording);\n// The slots' counts since the last call: filled in time, fallen back, the longest wait (us).\nvoid SasrtRunSlotCounts(uint64_t &filled, uint64_t &fallbacks, uint64_t &longest_wait_us);\n"),
    ('guest/command_buffers.h',
     '#include <memory>  // sasrt-nx (2026-10-21): CaptureCommandBufferRun\n',
     '#include <memory>  // sasrt-nx (2026-10-21): CaptureCommandBufferRun\n#include <condition_variable>  // sasrt-nx (2026-11-08): SasrtRunSlot\n#include <mutex>\n'),
    ('guest/command_buffers.cpp',
     'void ReleaseCommandBuffer(u32 command_buffer_va) {\n',
     '// sasrt-nx (2026-11-08, sasrt_renut_scene_same_frame): command_buffers.h.\nstd::atomic<uint64_t> g_slot_filled{0}, g_slot_fallbacks{0}, g_slot_longest_us{0};\n\nvoid FillCapturedRunSlot(SasrtRunSlot &slot, u32 buffer, std::shared_ptr<CapturedRun> recording) {\n  {\n    std::lock_guard lock(slot.mutex);\n    if (slot.filled)\n      return;\n    slot.buffer = buffer;\n    slot.recording = std::move(recording);\n    slot.filled = true;\n  }\n  slot.cv.notify_all();\n}\n\nvoid SasrtRunSlotCounts(uint64_t &filled, uint64_t &fallbacks, uint64_t &longest_wait_us) {\n  filled = g_slot_filled.exchange(0, std::memory_order_relaxed);\n  fallbacks = g_slot_fallbacks.exchange(0, std::memory_order_relaxed);\n  longest_wait_us = g_slot_longest_us.exchange(0, std::memory_order_relaxed);\n}\n\nvoid QueueCapturedRunSlot(u32 device_va, std::shared_ptr<SasrtRunSlot> slot, uint32_t timeout_ms) {\n  FlushDeferredVertices(device_va);\n  const u8 *device = GuestPtr<const u8>(device_va);\n  if (!device)\n    return;\n  // The running device as at the submission (the constants a run inherits), as QueueCapturedRun.\n  auto running = std::make_shared<std::vector<u8>>(device, device + d3d::kDeviceSnapshotSize);\n  const uint64_t submitted_swap = rex::latency::SwapCount();\n  render_thread::Queue([running, slot, timeout_ms, submitted_swap] {\n    std::shared_ptr<CapturedRun> recording;\n    u32 buffer = 0;\n    {\n      const auto waiting = std::chrono::steady_clock::now();\n      std::unique_lock lock(slot->mutex);\n      slot->cv.wait_for(lock, std::chrono::milliseconds(timeout_ms), [&slot] { return slot->filled; });\n      const uint64_t waited = uint64_t(std::chrono::duration_cast<std::chrono::microseconds>(\n                                           std::chrono::steady_clock::now() - waiting).count());\n      uint64_t longest = g_slot_longest_us.load(std::memory_order_relaxed);\n      while (waited > longest && !g_slot_longest_us.compare_exchange_weak(longest, waited)) {\n      }\n      if (slot->filled && slot->recording) {\n        recording = slot->recording;\n        buffer = slot->buffer;\n        g_slot_filled.fetch_add(1, std::memory_order_relaxed);\n      } else {\n        recording = slot->fallback;\n        buffer = slot->fallback_buffer;\n        g_slot_fallbacks.fetch_add(1, std::memory_order_relaxed);\n      }\n      slot->filled = true;  // a late fill changes nothing now\n    }\n    if (!recording || !buffer)\n      return;\n    const u8 *run_device = running->data();\n    g_sasrt_replay_tag = SasrtTagOf(recording->buffers, buffer, submitted_swap);\n    SasrtSeqNoteRun(true);\n    Replay(run_device, recording->buffers, buffer, 0, Predication(run_device));\n    SasrtSeqNoteRun(false);\n    g_sasrt_replay_tag = SasrtReplayTag{};\n  });\n}\n\nvoid ReleaseCommandBuffer(u32 command_buffer_va) {\n'),
]
