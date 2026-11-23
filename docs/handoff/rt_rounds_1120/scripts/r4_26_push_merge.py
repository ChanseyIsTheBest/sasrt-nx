ROOT = r'D:/sonic transformed/sasrt-nx/app/src/renut_engine/gpu/'


def edit(path, old, new, count=1):
    p = ROOT + path
    s = open(p, encoding='utf-8').read()
    assert s.count(old) == count, (path, s.count(old), old[:80])
    s = s.replace(old, new)
    open(p, 'w', encoding='utf-8').write(s)


edit('render/draw.cpp', '''  // The updates, a run of consecutive groups at a time.
  uint64_t pushed_bytes = 0;
  bool overwrote_literal = false;''', '''  // sasrt-nx (2026-11-20, sasrt_rt4_push_runs_merged; the third table's #26): two runs of groups to push that one or two
  // groups separate are pushed as one: the groups between them go too, with the device's current bytes (the loop below
  // copies all four registers of a group and makes them valid, as for any group it pushes), so one dkCmdBufPushConstants
  // call instead of two. Never across a group holding a literal register (this shader's or the buffer's): the device's
  // bytes would overwrite the literal.
  if (push && sasrt::gpu_round::On(sasrt::gpu_round::kRt4PushRunsMerged)) {
    uint64_t gaps = 0;
    for (uint64_t rest = push; rest;) {
      const u32 first = u32(std::countl_zero(rest));          // the lowest group left (group g is bit 63 - g)
      const u32 end = first + u32(std::countl_one(rest << first));  // the group after its run
      rest = end >= 64 ? 0 : rest & (~uint64_t(0) >> end);    // the groups from 'end' on
      if (!rest)
        break;
      const u32 next = u32(std::countl_zero(rest));
      if (next - end > 2)
        continue;
      bool free = true;
      for (u32 g = end; g < next && free; ++g)
        free = !(((own_literals ? own_literals[g / 8] : 0u) | last.literal_regs[g / 8]) >> (g % 8 * 4) & 0xFu);
      for (u32 g = end; free && g < next; ++g)
        gaps |= uint64_t(1) << (63 - g);
    }
    if (gaps) {
      push |= gaps;
      sasrt::gpu_round::Count(sasrt::gpu_round::kRt4PushRunsMerged, uint64_t(std::popcount(gaps)));
    }
  }
  // The updates, a run of consecutive groups at a time.
  uint64_t pushed_bytes = 0;
  bool overwrote_literal = false;''')
print('ok')
