ROOT = r'D:/sonic transformed/sasrt-nx/app/src/renut_engine/gpu/'


def edit(path, old, new, count=1):
    p = ROOT + path
    s = open(p, encoding='utf-8').read()
    assert s.count(old) == count, (path, s.count(old), old[:80])
    s = s.replace(old, new)
    open(p, 'w', encoding='utf-8').write(s)


edit('render/draw.cpp', '''  uint64_t h = 0x9E3779B97F4A7C15ull;
  for (u32 i = 0; i < 20; ++i)
    h = (h ^ rs[i]) * 0xFF51AFD7ED558CCDull;
  for (u32 i = 0; i < 7; ++i)
    h = (h ^ sig[i]) * 0xC4CEB9FE1A85EC53ull;
  RenderStateIdEntry &e = g_rs_ids[u32(h >> 56)];''', '''  u32 slot;
#if defined(__aarch64__) && defined(__ARM_FEATURE_CRC32)
  // sasrt-nx (2026-11-20, sasrt_rt4_state_id_crc; the third table's #25, the first's #42): the table's index from a
  // CRC32C of the words, 8 bytes an instruction (14, 3 cycles each on the A57), not 27 dependent multiplies; a hit
  // compares the words either way, so only the slots the states land in change.
  if (sasrt::gpu_round::On(sasrt::gpu_round::kRt4StateIdCrc)) {
    uint32_t c = 0xFFFFFFFFu;
    for (u32 i = 0; i < 20; i += 2) {
      uint64_t w;
      std::memcpy(&w, rs + i, 8);
      c = __builtin_aarch64_crc32cx(c, w);
    }
    for (u32 i = 0; i < 8; i += 2) {
      uint64_t w;
      std::memcpy(&w, sig + i, 8);
      c = __builtin_aarch64_crc32cx(c, w);
    }
    slot = (c ^ (c >> 8) ^ (c >> 16) ^ (c >> 24)) & 0xFFu;
  } else
#endif
  {
    uint64_t h = 0x9E3779B97F4A7C15ull;
    for (u32 i = 0; i < 20; ++i)
      h = (h ^ rs[i]) * 0xFF51AFD7ED558CCDull;
    for (u32 i = 0; i < 7; ++i)
      h = (h ^ sig[i]) * 0xC4CEB9FE1A85EC53ull;
    slot = u32(h >> 56);
  }
  RenderStateIdEntry &e = g_rs_ids[slot];''')
print('ok')
