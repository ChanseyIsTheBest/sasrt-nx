# sasrt-nx (2026-11-12, batch D; the agents' second-tier items, audited). Exact items.
#  D1 FindHostTextureBySlotLocked: the last answer remembered (slot -> texture VA), checked against the same fields the
#     scan tests (descriptor slots come only from AllocateTextureSlotLocked: one live owner each), so the copy-back
#     check does not walk every texture (1.7 % of the render thread, one call site).
#  D2 held exports: the retired buffers no fill points into any more (the flush) kept in a small pool and filled with
#     assign() by the next HoldExport (the same bytes; no 12 KB make_shared + free each export draw).
#  D3 sasrt::gpu_round::On: the latched flag read relaxed, as banjo's Latch() (values from the configuration only; the
#     render thread latches at its start): no load-acquire at the ~70 switch sites a fast draw passes.
#  D4 RenderScale::Coord in integers: round half away from zero of guest * n / d, which lround of the double quotient
#     gives exactly (the quotient's rounding error, < 2^-20, cannot cross a .5: a non-half quotient is >= 1/(2d) away).
R = 'D:/sonic transformed/sasrt-nx/'


def patch(rel, edits, mark):
    p = R + rel
    b = open(p, 'rb').read()
    crlf = b'\r\n' in b
    s = b.decode('utf-8').replace('\r\n', '\n')
    if mark in s:
        print('already patched:', rel, '(' + mark + ')')
        return
    for o, n in edits:
        assert s.count(o) == 1, (rel, o[:90], s.count(o))
        s = s.replace(o, n)
    open(p, 'wb').write((s.replace('\n', '\r\n') if crlf else s).encode('utf-8'))
    print('patched:', rel, '(' + mark + ')')


# ---- D1
patch('app/src/renut_engine/gpu/render/textures.cpp', [
    ('''HostTexture *FindHostTextureBySlotLocked(uint32_t slot) {
  for (const auto &[va, owned] : g_textures) {
    HostTexture *t = owned.get();
    if (!t)
      continue;
    if (t->slot == slot || t->level0_slot == slot)
      return t;
    for (const auto &v : t->swizzle_views)
      if (v.slot == slot)
        return t;
    if (t->words && t->words->slot == slot)
      return t->words.get();
    for (const auto &v : t->words_views)
      if (v.slot == slot)
        return t->words.get() ? t->words.get() : t;
  }
  return nullptr;
}''', '''// sasrt-nx (2026-11-12, batch D1): the scan's test of one texture (what it returns for it, or nullptr).
static HostTexture *SasrtSlotOwner(HostTexture *t, uint32_t slot) {
  if (t->slot == slot || t->level0_slot == slot)
    return t;
  for (const auto &v : t->swizzle_views)
    if (v.slot == slot)
      return t;
  if (t->words && t->words->slot == slot)
    return t->words.get();
  for (const auto &v : t->words_views)
    if (v.slot == slot)
      return t->words.get() ? t->words.get() : t;
  return nullptr;
}
REXCVAR_DEFINE_BOOL(sasrt_texture_slot_memo, true, "SASRT/GPU",
                    "FindHostTextureBySlotLocked remembers its last answer (slot -> texture), checked by the same "
                    "fields the scan tests, instead of walking every texture each call")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

HostTexture *FindHostTextureBySlotLocked(uint32_t slot) {
  // sasrt-nx (2026-11-12, batch D1): a slot has one live owner (AllocateTextureSlotLocked; Retire frees them), so the
  // remembered texture, if it still holds the slot, is the one the scan finds.
  static const bool memo_on = REXCVAR_GET(sasrt_texture_slot_memo);
  static uint32_t memo_slot = UINT32_MAX, memo_va = 0;
  if (memo_on && slot == memo_slot && slot != UINT32_MAX) {
    const auto it = g_textures.find(memo_va);
    if (it != g_textures.end() && it->second)
      if (HostTexture *r = SasrtSlotOwner(it->second.get(), slot))
        return r;
  }
  for (const auto &[va, owned] : g_textures) {
    HostTexture *t = owned.get();
    if (!t)
      continue;
    if (HostTexture *r = SasrtSlotOwner(t, slot)) {
      memo_slot = slot;
      memo_va = va;
      return r;
    }
  }
  return nullptr;
}'''),
], 'batch D1')

# ---- D2
patch('app/src/renut_engine/gpu/render/draw.cpp', [
    ('''std::map<u32, HeldExport> g_held_exports;
std::vector<std::shared_ptr<std::vector<u8>>> g_held_retired;''', '''std::map<u32, HeldExport> g_held_exports;
std::vector<std::shared_ptr<std::vector<u8>>> g_held_retired;
// sasrt-nx (2026-11-12, batch D2): retired buffers nothing points into any more (the flush), for the next holds.
std::vector<std::shared_ptr<std::vector<u8>>> g_held_pool;'''),
    ('''  HeldExport &h = g_held_exports[base];
  h.data = std::make_shared<std::vector<u8>>(data, data + size);
  h.frame = frame;
  h.checked = UINT64_MAX;''', '''  HeldExport &h = g_held_exports[base];
  if (!g_held_pool.empty()) {  // sasrt-nx (2026-11-12, batch D2): a pooled buffer, the same bytes
    h.data = std::move(g_held_pool.back());
    g_held_pool.pop_back();
    h.data->assign(data, data + size);
  } else {
    h.data = std::make_shared<std::vector<u8>>(data, data + size);
  }
  h.frame = frame;
  h.checked = UINT64_MAX;'''),
    ('''  g_held_retired.clear();  // sasrt-nx (2026-10-21, sasrt_renut_exports_held): no fill points into them now''',
     '''  // sasrt-nx (2026-11-12, batch D2): the ones only this list holds go to the pool (64 at most, up to 1 MB each)
  for (auto &p : g_held_retired)
    if (p && p.use_count() == 1 && g_held_pool.size() < 64 && p->capacity() <= (1u << 20))
      g_held_pool.push_back(std::move(p));
  g_held_retired.clear();  // sasrt-nx (2026-10-21, sasrt_renut_exports_held): no fill points into them now'''),
], 'batch D2')

# ---- D3
patch('app/src/renut_engine/gpu/sasrt_gpu_round.h', [
    ('''[[gnu::always_inline]] inline bool On(Item i) {
  if (!g_latched_ready.load(std::memory_order_acquire)) [[unlikely]]''', '''// sasrt-nx (2026-11-12, batch D3): the flag read relaxed, as banjo's Latch(): no load-acquire at each switch a draw
// passes (it kept the A57 from starting the draw's later loads early); the values come from the configuration only.
[[gnu::always_inline]] inline bool On(Item i) {
  if (!g_latched_ready.load(std::memory_order_relaxed)) [[unlikely]]'''),
], 'batch D3')

# ---- D4
patch('app/src/renut_engine/gpu/render/render_scale.h', [
    ('''  int32_t Coord(int32_t guest) const {
    return int32_t(std::lround(double(guest) * kNumerators[code] / kDenominators[code]));
  }''', '''  // sasrt-nx (2026-11-12, batch D4): in integers, round half away from zero of guest * n / d: what lround of the
  // double quotient gave (its error, under 2^-20, cannot cross a .5, as a quotient that is not a half is at least
  // 1/(2d) from one), without the libm call and the double division.
  int32_t Coord(int32_t guest) const {
    const int64_t n = kNumerators[code], d = kDenominators[code];
    const int64_t a = (guest < 0 ? -int64_t(guest) : int64_t(guest)) * n;
    const int64_t q = (2 * a + d) / (2 * d);
    return int32_t(guest < 0 ? -q : q);
  }'''),
], 'batch D4')
print('batchD: done')
