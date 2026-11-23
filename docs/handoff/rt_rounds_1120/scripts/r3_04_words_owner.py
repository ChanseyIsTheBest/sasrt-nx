p = r'D:/sonic transformed/sasrt-nx/app/src/renut_engine/gpu/render/textures.cpp'
s = open(p, encoding='utf-8').read()
old = '''  static uint32_t memo_slot = UINT32_MAX, memo_va = 0;
  const bool memo = sasrt::gpu_round::On(sasrt::gpu_round::kRtWordsOwnerMemo);
  if (memo && slot == memo_slot) {
    if (HostTexture *t = FindHostTextureLocked(memo_va); t && t->words)
      for (const auto &v : t->words_views)
        if (v.slot == slot) {
          sasrt::gpu_round::Count(sasrt::gpu_round::kRtWordsOwnerMemo);
          return t;
        }
  }'''
new = '''  static uint32_t memo_slot = UINT32_MAX, memo_va = 0;
  const bool memo = sasrt::gpu_round::On(sasrt::gpu_round::kRtWordsOwnerMemo);
  // sasrt-nx (2026-11-20, sasrt_rt3_words_owner_table; the third render-thread round's #4): an answer per slot (256 sets
  // by its low bits), each checked as before: the views' restore copies (two a view a frame, four views) took turns on
  // the one entry, and each miss walked every texture (SasrtRestoreCopyLocked 1.2 % of the render thread, 4 players).
  struct OwnerMemo {
    uint32_t slot = UINT32_MAX, va = 0;
  };
  static OwnerMemo table[256];
  const bool table_on = memo && sasrt::gpu_round::On(sasrt::gpu_round::kRt3WordsOwnerTable);
  if (table_on && table[slot & 255u].slot == slot) {
    if (HostTexture *t = FindHostTextureLocked(table[slot & 255u].va); t && t->words)
      for (const auto &v : t->words_views)
        if (v.slot == slot) {
          sasrt::gpu_round::Count(sasrt::gpu_round::kRt3WordsOwnerTable);
          return t;
        }
  } else if (memo && slot == memo_slot) {
    if (HostTexture *t = FindHostTextureLocked(memo_va); t && t->words)
      for (const auto &v : t->words_views)
        if (v.slot == slot) {
          sasrt::gpu_round::Count(sasrt::gpu_round::kRtWordsOwnerMemo);
          return t;
        }
  }'''
assert s.count(old) == 1
s = s.replace(old, new)
old = '''        if (memo) {
          memo_slot = slot;
          memo_va = va;
          sasrt::gpu_round::Count(sasrt::gpu_round::kRtWordsOwnerMemo, 1, 1);
        }
        return t;'''
new = '''        if (memo) {
          memo_slot = slot;
          memo_va = va;
          sasrt::gpu_round::Count(sasrt::gpu_round::kRtWordsOwnerMemo, 1, 1);
        }
        if (table_on)
          table[slot & 255u] = {slot, va};
        return t;'''
assert s.count(old) == 1
s = s.replace(old, new)
open(p, 'w', encoding='utf-8').write(s)
print('ok')
