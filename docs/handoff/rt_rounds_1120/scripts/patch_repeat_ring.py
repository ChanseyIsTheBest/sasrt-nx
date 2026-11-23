p = r'D:/sonic transformed/sasrt-nx/app/src/renut_engine/gpu/render/draw.cpp'
s = open(p, encoding='utf-8').read()


def rep(old, new):
    global s
    assert s.count(old) == 1, old[:80]
    s = s.replace(old, new)


rep('''WholeRepeat g_whole_repeat;
''', '''// sasrt-nx (2026-11-20, sasrt_rt2_repeat_ring; the second render-thread round's #41): the last four answers, not one
// (draws that take turns between a few meshes of one kick: a kart's body and wheels, a view's props); [0] alone off.
WholeRepeat g_whole_repeats[4];
u32 g_whole_repeat_next = 0;
''')
rep('''  const WholeRepeat &r = g_whole_repeat;
  if (!r.valid || r.vs != &vs || r.strides != strides || r.layout != &layout || r.layout_hash != layout_hash ||
      r.flush != g_flush_serial || r.frame != g_stream_cache_frame || r.mesh_gen != g_mesh_gen ||
      r.indexed != call.indexed || uint64_t(base) >= r.min_vertices)
    return false;''', '''  const bool ring = sasrt::gpu_round::On(sasrt::gpu_round::kRt2RepeatRing);
  const WholeRepeat *found = nullptr;
  for (u32 i = 0; i < (ring ? 4u : 1u); ++i) {
    const WholeRepeat &c = g_whole_repeats[i];
    if (c.valid && c.vs == &vs && c.strides == strides && c.layout == &layout && c.layout_hash == layout_hash &&
        c.flush == g_flush_serial && c.frame == g_stream_cache_frame && c.mesh_gen == g_mesh_gen &&
        c.indexed == call.indexed && uint64_t(base) < c.min_vertices) {
      found = &c;
      break;
    }
  }
  if (!found)
    return false;
  const WholeRepeat &r = *found;''')
rep('''  if (repeat_on) {
    WholeRepeat &r = g_whole_repeat;
    r.valid = true;''', '''  if (repeat_on) {
    const bool ring = sasrt::gpu_round::On(sasrt::gpu_round::kRt2RepeatRing);
    WholeRepeat &r = g_whole_repeats[ring ? (g_whole_repeat_next++ & 3u) : 0u];
    r.valid = true;''')
open(p, 'w', encoding='utf-8').write(s)
print('ok')
