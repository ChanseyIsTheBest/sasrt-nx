p = r'D:/sonic transformed/sasrt-nx/app/src/renut_engine/gpu/render/surfaces.cpp'
s = open(p, encoding='utf-8').read()
old = '''SurfaceMemo g_surface_memo[64];  // banjo-nx (2026-10-19, render-thread proposal 8): 64, indexed by a hash of the VA'''
new = '''// banjo-nx (2026-10-19, render-thread proposal 8): 64, indexed by a hash of the VA. sasrt-nx (2026-11-20,
// sasrt_rt3_surface_memo_256; the third render-thread round's #24): 256 (the four views' targets and resolves, their
// EDRAM views and the stack headers conflicted in 64); the first 64 alone with the key off.
SurfaceMemo g_surface_memo[256];'''
assert s.count(old) == 1
s = s.replace(old, new)
old = '''  SurfaceMemo &m = g_surface_memo[((surface_va ^ (view ? u32(desc->ColorInfo) * 0x45D9F3Bu + 1u : 0u)) * 0x9E3779B1u) >> 26];'''
new = '''  const u32 memo_hash = (surface_va ^ (view ? u32(desc->ColorInfo) * 0x45D9F3Bu + 1u : 0u)) * 0x9E3779B1u;
  SurfaceMemo &m = g_surface_memo[sasrt::gpu_round::On(sasrt::gpu_round::kRt3SurfaceMemo256) ? memo_hash >> 24
                                                                                               : memo_hash >> 26];'''
assert s.count(old) == 1
s = s.replace(old, new)
open(p, 'w', encoding='utf-8').write(s)
print('ok')
