ROOT = r'D:/sonic transformed/sasrt-nx/'


def edit(path, old, new, count=1):
    p = ROOT + path
    s = open(p, encoding='utf-8').read()
    assert s.count(old) == count, (path, s.count(old), old[:80])
    s = s.replace(old, new)
    open(p, 'w', encoding='utf-8').write(s)


# The SDK: a generation raised before any page can lose read access.
h = 'sdk/include/rex/system/xmemory.h'
s = open(ROOT + h, encoding='utf-8').read()
i = s.index('class BaseHeap {')
# put the declaration just before the class (inside the same namespace)
decl = ('// sasrt-nx (2026-11-20, sasrt_rt2_readable_memo): raised at the start of every heap operation that can take read\n'
        '// access from a page (Decommit, Release, Protect, Reset, Restore): an answer that a range was readable holds\n'
        '// while it is unchanged (the renderer\'s vertex fills keep such answers instead of walking the page table).\n'
        'extern std::atomic<uint64_t> g_page_access_generation;\n\n')
s = s[:i] + decl + s[i:]
if '#include <atomic>' not in s:
    j = s.index('#include <')
    s = s[:j] + '#include <atomic>\n' + s[j:]
open(ROOT + h, 'w', encoding='utf-8').write(s)

c = 'sdk/src/system/xmemory.cpp'
s = open(ROOT + c, encoding='utf-8').read()
bump = '  g_page_access_generation.fetch_add(1, std::memory_order_acq_rel);  // sasrt-nx (2026-11-20)\n'
for sig in ['bool BaseHeap::Decommit(uint32_t address, uint32_t size) {\n',
            'bool BaseHeap::Release(uint32_t base_address, uint32_t* out_region_size) {\n',
            'bool BaseHeap::Protect(uint32_t address, uint32_t size, uint32_t protect, uint32_t* old_protect) {\n',
            'void BaseHeap::Reset() {\n',
            'bool BaseHeap::Restore(stream::ByteStream* stream) {\n']:
    assert s.count(sig) == 1, sig
    s = s.replace(sig, sig + bump)
k = s.index('std::unique_lock<std::recursive_mutex> BaseHeap::AcquireHostPageReconcileLock() const {')
s = s[:k] + ('std::atomic<uint64_t> g_page_access_generation{1};  // sasrt-nx (2026-11-20, sasrt_rt2_readable_memo): '
             'xmemory.h\n\n') + s[k:]
open(ROOT + c, 'w', encoding='utf-8').write(s)

# The renderer: the memo in GuestBytesReadable (the Switch's branch).
edit('app/src/renut_engine/gpu/render/draw.cpp', '''  if (!heap || address + len - 1 > 0xFFFFFFFFull)
    return false;
  return uint32_t(heap->QueryRangeAccess(uint32_t(address), uint32_t(address + len - 1))) &
         uint32_t(rex::memory::PageAccess::kReadOnly);
#endif
}''', '''  if (!heap || address + len - 1 > 0xFFFFFFFFull)
    return false;
  // sasrt-nx (2026-11-20, sasrt_rt2_readable_memo; the second render-thread round's #29): ranges found readable, 64 of
  // them by their first 64 KB, kept while no page anywhere has lost read access since (g_page_access_generation: each
  // query takes the heap's recursive mutex, which the game's allocations hold too, and walks the page table). Two
  // readable ranges that touch are one.
  struct ReadableMemo {
    const rex::memory::BaseHeap *heap = nullptr;
    uint32_t lo = 0, hi = 0;
    uint64_t generation = 0;
  };
  static ReadableMemo memo[64];
  const uint32_t lo = uint32_t(address), hi = uint32_t(address + len - 1);
  const bool memo_on = sasrt::gpu_round::On(sasrt::gpu_round::kRt2ReadableMemo);
  const uint64_t generation = rex::memory::g_page_access_generation.load(std::memory_order_acquire);
  ReadableMemo &m = memo[(lo >> 16) & 63u];
  if (memo_on && m.heap == heap && m.generation == generation && m.lo <= lo && hi <= m.hi) {
    sasrt::gpu_round::Count(sasrt::gpu_round::kRt2ReadableMemo);
    return true;
  }
  const bool readable = uint32_t(heap->QueryRangeAccess(lo, hi)) & uint32_t(rex::memory::PageAccess::kReadOnly);
  if (memo_on && readable) {
    sasrt::gpu_round::Count(sasrt::gpu_round::kRt2ReadableMemo, 1, 1);  // queried (the 10 s line's /n)
    if (m.heap == heap && m.generation == generation && lo <= uint64_t(m.hi) + 1 && uint64_t(hi) + 1 >= m.lo) {
      m.lo = std::min(m.lo, lo);
      m.hi = std::max(m.hi, hi);
    } else {
      m = {heap, lo, hi, generation};
    }
  }
  return readable;
#endif
}''')
print('ok')
