p = r'D:/sonic transformed/sasrt-nx/sdk/src/system/xmemory.cpp'
s = open(p, encoding='utf-8').read()
old = '''bool BaseHeap::AllocFixed(uint32_t base_address, uint32_t size, uint32_t alignment,
                          uint32_t allocation_type, uint32_t protect) {
'''
new = old + '''  // sasrt-nx (2026-11-20, sasrt_rt2_readable_memo): a commit over pages already committed sets their protection (it
  // can take read access away): the readable answers go when the new one has no read.
  if (!(protect & memory::kMemoryProtectRead))
    g_page_access_generation.fetch_add(1, std::memory_order_acq_rel);
'''
assert s.count(old) == 1
s = s.replace(old, new)
open(p, 'w', encoding='utf-8').write(s)
print('ok')
