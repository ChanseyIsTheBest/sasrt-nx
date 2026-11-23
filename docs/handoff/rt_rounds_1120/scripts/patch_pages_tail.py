p = r'D:/sonic transformed/sasrt-nx/app/src/renut_engine/gpu/render/draw.cpp'
s = open(p, encoding='utf-8').read()
old = '''        page += 7;  // the loop's ++page makes 8
        continue;
      }
    }
#endif
'''
new = '''        page += 7;  // the loop's ++page makes 8
        continue;
      }
    }
    // sasrt-nx (2026-11-20, sasrt_rt2_pages_tail; the second render-thread round): a range's last 1-7 pages (most vertex
    // ranges are that short) in one block the same way, the lanes past the range masked: their cards read as written-
    // never and their serials as old. Loads stay inside the card table and g_page_serial (page + 8 <= 0x20000).
    if (!diag && page != 0 && last - page < 7 && page + 8 <= 0x20000u && (page + 8 <= 0x1000u || page >= 0x1000u) &&
        sasrt::gpu_round::On(sasrt::gpu_round::kRt2PagesTail)) {
      static const uint8_t kLanes8[8] = {0, 1, 2, 3, 4, 5, 6, 7};
      static const uint32_t kLanes32[8] = {0, 1, 2, 3, 4, 5, 6, 7};
      const u32 n = last - page + 1;
      const uint8x8_t outside = vcge_u8(vld1_u8(kLanes8), vdup_n_u8(u8(n)));
      const uint8x8_t ca = vld1_u8(cards + 0xA0000u + page), cc = vld1_u8(cards + 0xC0000u + page);
      const uint8x8_t ce = vld1_u8(cards + 0xE0000u + page - 1);
      const uint8x8_t cf = page < 0x1000u ? vld1_u8(cards + 0x7F000u + page) : ca;
      if (vminv_u8(vorr_u8(vmin_u8(vmin_u8(ca, cc), vmin_u8(ce, cf)), outside)) != 0) {
        const uint32x4_t nn = vdupq_n_u32(n), p = vdupq_n_u32(u32(proven));
        const u32 *serials = g_page_serial + page;
        const uint32x4_t newer =
            vorrq_u32(vandq_u32(vcgeq_u32(vld1q_u32(serials), p), vcltq_u32(vld1q_u32(kLanes32), nn)),
                      vandq_u32(vcgeq_u32(vld1q_u32(serials + 4), p), vcltq_u32(vld1q_u32(kLanes32 + 4), nn)));
        if (vmaxvq_u32(newer) != 0)
          clean = false;
        sasrt::gpu_round::Count(sasrt::gpu_round::kRt2PagesTail);
        page += n - 1;  // the loop's ++page makes n
        continue;
      }
    }
#endif
'''
assert s.count(old) == 1
s = s.replace(old, new)
open(p, 'w', encoding='utf-8').write(s)
print('ok')
