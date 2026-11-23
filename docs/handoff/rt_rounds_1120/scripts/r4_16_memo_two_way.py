ROOT = r'D:/sonic transformed/sasrt-nx/app/src/renut_engine/gpu/'


def edit(path, old, new, count=1):
    p = ROOT + path
    s = open(p, encoding='utf-8').read()
    assert s.count(old) == count, (path, s.count(old), old[:80])
    s = s.replace(old, new)
    open(p, 'w', encoding='utf-8').write(s)


edit('render/draw.cpp', '''  Entry *Find(const typename Map::key_type &key, size_t hash) const {
    const Slot &slot = slots_[Index(hash)];
    return slot.hash == hash && slot.entry && slot.entry->first == key ? slot.entry : nullptr;
  }''', '''  // sasrt-nx (2026-11-20, sasrt_rt4_stream_memo_two_way; the third table's #16): two ways, the slot and its pair (the
  // same line): the most recently used kept in the first (a hit in the second swaps them; a new entry pushes the first
  // into the second). Four views' streams and indices (thousands of keys a frame) conflicted in the direct-mapped slots,
  // each conflict a map lookup (the bucket's and the node's lines).
  static bool TwoWay() { return sasrt::gpu_round::On(sasrt::gpu_round::kRt4StreamMemoTwoWay); }
  Entry *Find(const typename Map::key_type &key, size_t hash) const {
    const u32 i = Index(hash);
    const Slot &slot = slots_[i];
    if (slot.hash == hash && slot.entry && slot.entry->first == key)
      return slot.entry;
    if (!TwoWay())
      return nullptr;
    Slot &other = const_cast<Slot &>(slots_[i ^ 1u]);
    if (other.hash == hash && other.entry && other.entry->first == key) {
      std::swap(const_cast<Slot &>(slot), other);
      return slots_[i].entry;
    }
    return nullptr;
  }
  void Place(size_t hash, Entry *entry) {
    const u32 i = Index(hash);
    if (TwoWay() && slots_[i].entry && slots_[i].entry != entry)
      slots_[i ^ 1u] = slots_[i];
    slots_[i] = {hash, entry};
  }''')
edit('render/draw.cpp', '''    auto it = map.find(key);
    if (it == map.end()) {
      if (!make)
        return nullptr;
      it = map.try_emplace(key).first;
    }
    slots_[Index(hash)] = {hash, &*it};
    return &*it;
  }''', '''    auto it = map.find(key);
    if (it == map.end()) {
      if (!make)
        return nullptr;
      it = map.try_emplace(key).first;
    }
    Place(hash, &*it);
    return &*it;
  }''')
edit('render/draw.cpp', '''    Entry *entry = &*map.try_emplace(key).first;
    slots_[Index(hash)] = {hash, entry};
    return entry;
  }''', '''    Entry *entry = &*map.try_emplace(key).first;
    Place(hash, entry);
    return entry;
  }''')
edit('render/draw.cpp', '''  void Forget(size_t hash, const Entry *entry) {
    Slot &slot = slots_[Index(hash)];
    if (slot.entry == entry)
      slot = Slot{};
  }''', '''  void Forget(size_t hash, const Entry *entry) {
    Slot &slot = slots_[Index(hash)];
    if (slot.entry == entry)
      slot = Slot{};
    Slot &other = slots_[Index(hash) ^ 1u];  // sasrt-nx (2026-11-20): either way (the key may have been on or off since)
    if (other.entry == entry)
      other = Slot{};
  }''')
edit('render/draw.cpp', '''  void PrefetchEntry(const typename Map::key_type &key) const {
    const size_t hash = Hash{}(key);
    const Slot &slot = slots_[Index(hash)];
    if (slot.hash == hash && slot.entry) {
      __builtin_prefetch(slot.entry);
      __builtin_prefetch(reinterpret_cast<const char *>(slot.entry) + 64);
    }
  }''', '''  void PrefetchEntry(const typename Map::key_type &key) const {
    const size_t hash = Hash{}(key);
    const Slot &slot = slots_[Index(hash)];
    const Slot &other = slots_[Index(hash) ^ 1u];  // sasrt-nx (2026-11-20): the pair, on the same line
    const Slot *s = slot.hash == hash && slot.entry ? &slot : other.hash == hash && other.entry ? &other : nullptr;
    if (s) {
      __builtin_prefetch(s->entry);
      __builtin_prefetch(reinterpret_cast<const char *>(s->entry) + 64);
    }
  }''')
print('ok')
