ROOT = r'D:/sonic transformed/sasrt-nx/app/src/renut_engine/gpu/'


def edit(path, old, new, count=1):
    p = ROOT + path
    s = open(p, encoding='utf-8').read()
    assert s.count(old) == count, (path, s.count(old), old[:80])
    s = s.replace(old, new)
    open(p, 'w', encoding='utf-8').write(s)


edit('backend/render_thread.cpp', '''    size_t n = 0;
    Clock::time_point item_start = start;
    do {
      RingSlot &slot = g_ring[pos & (kRingSlots - 1)];
      if (prefetch && RingReady(pos + 1))
        PrefetchItem(g_ring[(pos + 1) & (kRingSlots - 1)].item);
      if (!batch_clock)
        g_item_start = item_start;
      Execute(slot.item);
      slot.item.work = nullptr;  // the closure's captures go now, as the batch's cleared vector freed them''', '''    size_t n = 0;
    Clock::time_point item_start = start;
    // sasrt-nx (2026-11-20, sasrt_rt4_ring_lock_once; the third table's #4): State().mutex held from one draw's item
    // into the next when that one is published already and a draw's too (QueuePrefetched's: prefetch[0] is its capture),
    // at most 8 in a row (the game thread's hooks that take the lock wait at most that long), and never past the run's
    // end: a lock and an unlock fewer an item. Only draws: the place waits (which wait on the game thread, the deadlock
    // proposal 19 met with every item) and every other item take it on their own as before. The closures still go after
    // their item (under the lock when it is kept: a capture's memory, no lock of its own).
    static const bool chain_lock = sasrt::gpu_round::On(sasrt::gpu_round::kRt4RingLockOnce);
    bool held = false;
    uint32_t held_items = 0;
    do {
      RingSlot &slot = g_ring[pos & (kRingSlots - 1)];
      const bool next_ready = RingReady(pos + 1);
      if (prefetch && next_ready)
        PrefetchItem(g_ring[(pos + 1) & (kRingSlots - 1)].item);
      if (!batch_clock)
        g_item_start = item_start;
      if (chain_lock && slot.item.locked && slot.item.prefetch[0] &&
          sasrt::gpu_round::On(sasrt::gpu_round::kRt4RingLockOnce)) {
        if (!held) {
          State().mutex.lock();
          held = true;
          held_items = 0;
        } else {
          sasrt::gpu_round::Count(sasrt::gpu_round::kRt4RingLockOnce);  // a lock and an unlock saved
        }
        {
          ::renut::gpu::census::Scope census_scope(::renut::gpu::census::kRunItem);
          slot.item.work();
        }
        ++held_items;
        const Item *next = next_ready ? &g_ring[(pos + 1) & (kRingSlots - 1)].item : nullptr;
        const bool keep = next && next->locked && next->prefetch[0] && held_items < 8 && n + 1 < kRingRun;
        slot.item.work = nullptr;
        if (!keep) {
          State().mutex.unlock();
          held = false;
        }
      } else {
        if (held) {  // not expected (keep looked at this item), but never two holds
          State().mutex.unlock();
          held = false;
        }
        Execute(slot.item);
        slot.item.work = nullptr;  // the closure's captures go now, as the batch's cleared vector freed them
      }''')
edit('backend/render_thread.cpp', '''    } while (n < kRingRun && RingReady(pos));
    if (batch_clock)
      g_busy += Clock::now() - start;''', '''    } while (n < kRingRun && RingReady(pos));
    if (held)  // sasrt-nx (2026-11-20, sasrt_rt4_ring_lock_once): never kept past the run
      State().mutex.unlock();
    if (batch_clock)
      g_busy += Clock::now() - start;''')
print('ok')
