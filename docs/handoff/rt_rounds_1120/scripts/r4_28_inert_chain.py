ROOT = r'D:/sonic transformed/sasrt-nx/app/src/renut_engine/gpu/'


def edit(path, old, new, count=1):
    p = ROOT + path
    s = open(p, encoding='utf-8').read()
    assert s.count(old) == count, (path, s.count(old), old[:80])
    s = s.replace(old, new)
    open(p, 'w', encoding='utf-8').write(s)


# the carry and the helper, next to FastMiss (in the same anonymous namespace as g_fast)
edit('render/draw.cpp', '''inline int FastMiss(u32 why) {
  ++g_fast_why[why];
  return 0;
}
''', '''inline int FastMiss(u32 why) {
  ++g_fast_why[why];
  return 0;
}

// sasrt-nx (2026-11-20, sasrt_rt4_inert_keeps_chain; the third table's #28, the first's #15): a draw left out before the
// fast path (sasrt_gpu_skip_inert_draws, sasrt_gpu_skip_cull_both: it writes nothing) keeps the chain: the fast state
// takes its number and its changed fields are carried into the next draw's (the union of the two steps' changes covers
// the change from the last drawn one). The 4P race left out ~240 draws a second, each a chain break for the next.
u32 g_chain_carry_fields = 0;
inline void SasrtKeepChainOverSkipped() {
  FastState &f = g_fast;
  const ChainHint &chain = g_chain_hint;
  if (f.valid && chain.seq && chain.seq == f.seq + 1 && sasrt::gpu_round::On(sasrt::gpu_round::kRt4InertKeepsChain)) {
    f.seq = chain.seq;
    g_chain_carry_fields |= chain.fields;
    sasrt::gpu_round::Count(sasrt::gpu_round::kRt4InertKeepsChain);
  }
}
''')
# the fast path takes the carry once its chain holds
edit('render/draw.cpp', '''  if (!chain.seq || chain.seq != f.seq + 1)
    return FastMiss(kFastBreak);
  // (Stage 2: Draw*UP, Begin*Vertices, range geometry and rectangle lists are the executor's too.)''',
     '''  if (!chain.seq || chain.seq != f.seq + 1)
    return FastMiss(kFastBreak);
  // sasrt-nx (2026-11-20, sasrt_rt4_inert_keeps_chain): the fields of draws left out since the last drawn one.
  const u32 carried_fields = g_chain_carry_fields;
  g_chain_carry_fields = 0;
  // (Stage 2: Draw*UP, Begin*Vertices, range geometry and rectangle lists are the executor's too.)''')
edit('render/draw.cpp', '''  const u32 fields = chain.fields;
  // banjo-nx (2026-10-28, per-draw night): the predication is one of the viewport's inputs below (the viewport is all''',
     '''  const u32 fields = chain.fields | carried_fields;
  // banjo-nx (2026-10-28, per-draw night): the predication is one of the viewport's inputs below (the viewport is all''')
# the full path's store starts a new chain
edit('render/draw.cpp', '''  g_last_draw_fields = g_chain_hint.fields;
  g_last_draw_fast = false;
  f.valid = usable;
  if (!usable)
    return;
  f.seq = g_chain_hint.seq;''', '''  g_last_draw_fields = g_chain_hint.fields;
  g_last_draw_fast = false;
  g_chain_carry_fields = 0;  // sasrt-nx (2026-11-20, sasrt_rt4_inert_keeps_chain): a new chain from this draw
  f.valid = usable;
  if (!usable)
    return;
  f.seq = g_chain_hint.seq;''')
# the two skips
edit('render/draw.cpp', '''    const bool cull_both = g_ds_keys.cull_both;
    if (cull_both && SasrtCullBothLocked(device_state, call)) [[unlikely]]
      return true;''', '''    const bool cull_both = g_ds_keys.cull_both;
    if (cull_both && SasrtCullBothLocked(device_state, call)) [[unlikely]] {
      SasrtKeepChainOverSkipped();  // sasrt-nx (2026-11-20, sasrt_rt4_inert_keeps_chain)
      return true;
    }''')
edit('render/draw.cpp', '''    if ((dc & 6) != 6 && SasrtInertDrawLocked(device_state)) [[unlikely]] {
      sasrt::gpu_round::Count(sasrt::gpu_round::kInertDraws);
      return true;
    }''', '''    if ((dc & 6) != 6 && SasrtInertDrawLocked(device_state)) [[unlikely]] {
      sasrt::gpu_round::Count(sasrt::gpu_round::kInertDraws);
      SasrtKeepChainOverSkipped();  // sasrt-nx (2026-11-20, sasrt_rt4_inert_keeps_chain)
      return true;
    }''')
print('ok')
