p = r'D:/sonic transformed/sasrt-nx/app/src/renut_engine/gpu/backend/render_thread.cpp'
s = open(p, encoding='utf-8').read()
old = '''  if (const auto *b = static_cast<const char *>(item.prefetch[1])) {
    __builtin_prefetch(b);
    __builtin_prefetch(b + 64);
    __builtin_prefetch(b + 128);
    __builtin_prefetch(b + 192);
  }
}'''
new = '''  if (const auto *b = static_cast<const char *>(item.prefetch[1])) {
    __builtin_prefetch(b);
    __builtin_prefetch(b + 64);
    __builtin_prefetch(b + 128);
    __builtin_prefetch(b + 192);
    // sasrt-nx (2026-11-20, sasrt_rt2_ring_prefetch; the second render-thread round's #30): a narrowed delta averages
    // ~360 bytes in the 4-player race (6-7 lines): two lines more.
    if (sasrt::gpu_round::On(sasrt::gpu_round::kRt2RingPrefetch)) {
      __builtin_prefetch(b + 256);
      __builtin_prefetch(b + 320);
    }
  }
}'''
assert s.count(old) == 1
s = s.replace(old, new)
if 'sasrt_gpu_round.h' not in s:
    i = s.index('#include "renut_engine/gpu/')
    s = s[:i] + '#include "renut_engine/gpu/sasrt_gpu_round.h"  // sasrt-nx (2026-11-20): the second render-thread round\n' + s[i:]
open(p, 'w', encoding='utf-8').write(s)
print('ok')
