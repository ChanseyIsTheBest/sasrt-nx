p = r'D:/sonic transformed/sasrt-nx/app/src/renut_engine/gpu/render/draw.cpp'
s = open(p, encoding='utf-8').read()
old = '''inline TextureSlotMemo &TextureMemoSlot(u32 texture_va, const TextureFetch &fetch) {
  static_assert(kTextureMemoEntries == 1u << 12);
  return g_texture_slot_memo[((texture_va ^ (fetch.dword[0] * 0x85EBCA6Bu) ^ fetch.dword[1]) * 0x9E3779B1u) >> 20];
}
'''
new = '''inline TextureSlotMemo &TextureMemoSlot(u32 texture_va, const TextureFetch &fetch) {
  static_assert(kTextureMemoEntries == 1u << 12);
  const u32 h = (texture_va ^ (fetch.dword[0] * 0x85EBCA6Bu) ^ fetch.dword[1]) * 0x9E3779B1u;
  // sasrt-nx (2026-11-20, sasrt_rt2_texture_memo_two_way; the second render-thread round's #2): 2,048 sets of two (the
  // same 4,096 entries): the entry of this texture and fetch words when either way holds it, else the way bound in an
  // earlier frame (the four-player race missed ~1,950 a second by "another entry", each a whole BindTextureLocked). Every
  // use checks the entry's words as before, so an entry stored under the other mapping (the A/B's other half) is only
  // a miss.
  if (sasrt::gpu_round::On(sasrt::gpu_round::kRt2TextureMemoTwoWay)) {
    TextureSlotMemo *const set = &g_texture_slot_memo[(h >> 21) << 1];
    for (u32 w = 0; w < 2; ++w)
      if (set[w].va == texture_va && SameBytes<24>(set[w].device, fetch.dword))
        return set[w];
    return set[0].frame <= set[1].frame ? set[0] : set[1];
  }
  return g_texture_slot_memo[h >> 20];
}
'''
assert s.count(old) == 1
s = s.replace(old, new)
open(p, 'w', encoding='utf-8').write(s)
print('ok')
