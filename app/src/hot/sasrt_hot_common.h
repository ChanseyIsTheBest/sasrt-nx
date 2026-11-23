// Sonic & All-Stars Racing Transformed - native replacements of hot guest functions: shared definitions (sa2-nx's
// sa2_hot_common.h, from masseffect-nx's me_hot_common.h).
//
// A "hot hook" replaces one recompiled guest function (sub_X) by a native version with the same observable behaviour.
// Here they are all localized copies (tools/localize_native.py): the recompiled function's own C++, generated into
// app/generated/hot/n_<ADDR>.h as
//
//   namespace sasrt::hot::n_<ADDR> {
//     inline void Native(PPCContext& ctx, uint8_t* base);   // the replacement
//     inline void Shadow(PPCContext& ctx, uint8_t* base, ShadowMemory& m);  // leaf copies only: the same, with every
//   }                                                                         // guest store kept in `m`
//
// and registered in sasrt_hot_guest.cpp with its own key and the hash of the guest code it was written from.
//
// What "exact" means here: memory effects (every guest byte the original writes), every register the original leaves
// defined for its callers, and the FPSCR flush-mode state. Xbox 360 games were compiled with interprocedural register
// allocation: callers keep values in volatile registers across a call to a function known not to touch them
// (tools/call_site_liveness.py). So a native must never write a register the original does not write: the localized
// copies write back exactly the values the original leaves (every register they use, at every call and return).
#pragma once

#include <cstdint>
#include <cstring>
#include <vector>

#include <rex/platform.h>
#include <rex/ppc/context.h>

namespace sasrt::hot {

// Guest stores of a shadow run (the guard of leaf copies): the native version runs on a copy of the registers with its
// stores going here instead of guest memory (its own later loads see them), so nothing real is touched; the original
// then runs for real and every byte kept here must equal guest memory afterwards. `overflow`: too many stores to keep
// (the call is not verified, the original's result stands).
// 2026-10-07: the kept bytes are held by 4 KB page (a valid bit and a value per byte), found through a small
// open-addressing index of page numbers (a slot is in use only when its generation is the current one, so Reset()
// clears nothing) and a cache of the last page (the accesses are mostly sequential). The first version searched a list
// of at most 4,096 bytes: a copy that writes more (sub_82E7F918 stores a whole 1280x720x4 surface, 3,686,504 bytes, per
// call) then searched all 4,096 entries on every access after the overflow, about a billion compares per checked
// call, and verify mode checks every call (36 frames in 240 s). Now a call can keep up to 32 MB; pages are allocated
// once per thread, as many as its largest checked call needed (about 4 MB for that surface).
struct ShadowMemory {
  static constexpr uint32_t kPageBits = 12;
  static constexpr uint32_t kPageBytes = 1u << kPageBits;
  static constexpr uint32_t kMaxPages = 8192;  // 32 MB kept per checked call at most (verify mode)
  static constexpr uint32_t kGuardPages = 16;   // 64 KB outside verify mode (Check sets max_pages)
  static constexpr uint32_t kSlots = 16384;    // the page index: a load factor of 0.5 at most
  struct Page {
    uint32_t number = 0;                        // guest address >> kPageBits
    uint64_t valid[kPageBytes / 64];            // the bytes this call stored
    uint8_t value[kPageBytes];
  };
  std::vector<Page*> pages;  // this call's pages are pages[0, used); the rest are kept for later calls
  uint32_t used = 0;
  uint32_t max_pages = kGuardPages;
  bool overflow = false;
  uint64_t attempted = 0;    // distinct bytes the call stored, kept or not
  uint32_t gen = 1;          // the current call's generation
  uint32_t slot_gen[kSlots] = {};
  uint32_t slot_number[kSlots] = {};
  uint32_t slot_page[kSlots] = {};
  mutable const Page* last = nullptr;  // the page of the last access

  ShadowMemory() = default;
  ShadowMemory(const ShadowMemory&) = delete;
  ShadowMemory& operator=(const ShadowMemory&) = delete;

  void Reset() {
    used = 0;
    overflow = false;
    attempted = 0;
    last = nullptr;
    if (++gen == 0) {  // wrapped: every old generation could look current again
      std::memset(slot_gen, 0, sizeof(slot_gen));
      gen = 1;
    }
  }
  static uint32_t Slot(uint32_t number) { return (number * 0x9E3779B1u) >> (32 - 14); }  // 14 bits: kSlots
  const Page* FindPage(uint32_t number) const {
    if (last && last->number == number) return last;
    for (uint32_t s = Slot(number);; s = (s + 1) & (kSlots - 1)) {
      if (slot_gen[s] != gen) return nullptr;
      if (slot_number[s] == number) return last = pages[slot_page[s]];
    }
  }
  // The byte this call stored at `a`, if it did.
  bool Load(uint32_t a, uint8_t& v) const {
    const Page* p = FindPage(a >> kPageBits);
    if (!p) return false;
    const uint32_t o = a & (kPageBytes - 1);
    if (!((p->valid[o >> 6] >> (o & 63)) & 1)) return false;
    v = p->value[o];
    return true;
  }
  void Store8(uint32_t a, uint8_t v) {
    const uint32_t number = a >> kPageBits;
    Page* p = const_cast<Page*>(FindPage(number));
    if (!p) {
      if (used >= max_pages) {
        ++attempted;
        overflow = true;
        return;
      }
      if (used == pages.size()) pages.push_back(new Page());
      p = pages[used];
      p->number = number;
      std::memset(p->valid, 0, sizeof(p->valid));
      uint32_t s = Slot(number);
      while (slot_gen[s] == gen) s = (s + 1) & (kSlots - 1);
      slot_gen[s] = gen;
      slot_number[s] = number;
      slot_page[s] = used++;
      last = p;
    }
    const uint32_t o = a & (kPageBytes - 1);
    uint64_t& bits = p->valid[o >> 6];
    const uint64_t bit = uint64_t(1) << (o & 63);
    if (!(bits & bit)) {
      bits |= bit;
      ++attempted;
    }
    p->value[o] = v;
  }
};

// The +0x1000 physical-range offset of the Windows / Apple-silicon hosts (none on the Switch), as the generated code's
// REX_PHYS_HOST_OFFSET.
inline uint32_t PhysOff(uint32_t a) {
#if REX_PLATFORM_WIN32 || (REX_PLATFORM_MAC && REX_ARCH_ARM64)
  return a >= 0xE0000000u ? 0x1000u : 0u;
#else
  (void)a;
  return 0u;
#endif
}

inline uint8_t* Raw(uint8_t* base, uint32_t a) { return base + a + PhysOff(a); }
inline const uint8_t* Raw(const uint8_t* base, uint32_t a) { return base + a + PhysOff(a); }
// sasrt-nx (2026-10-21, sa2-nx's and banjo-nx's): the store cards (rex/system/xmemory.h, tools/store_cards.py): a
// native's write of guest memory zeroes the cards of its pages, as the generated stores do (REX_CARD), so Renut never
// proves a cached copy whose bytes a native changed. The cards are the first MB of the guest window: 'base' itself.
inline void Card(uint8_t* base, uint32_t a, uint32_t len) {
  if (!len) return;
  const uint64_t end = uint64_t(a) + len - 1;
  const uint32_t last = end > 0xFFFFFFFFull ? 0xFFFFFu : uint32_t(end >> 12);
  // Up to a page long, the range touches at most two pages, its first and its last: two byte stores (sa2-nx: GCC made
  // the loop a call of memset).
  if (len <= 4096) {
    base[a >> 12] = 0;
    base[last] = 0;
    return;
  }
  for (uint32_t page = a >> 12; page <= last; ++page) base[page] = 0;
}

// sasrt-nx (2026-10-14; sa2-nx's audit of its codegen ideas 3, 6 and 9): the physical views from 0xA0000000
// (0xA0000000, 0xC0000000, 0xE0000000) all map the same 512 MB, so two different guest addresses can be the same byte.
// The virtual ranges never alias a view. Natives ask MayOverlap, not a comparison of guest addresses, before they
// decide two ranges do not overlap, and decline a range that leaves its view or wraps (CrossesView).
inline bool CrossesView(uint32_t a, uint32_t n) {
  if (!n) return false;
  const uint32_t e = a + (n - 1);
  if (e < a) return true;
  return (a >= 0xA0000000u) != (e >= 0xA0000000u) || (a >= 0xA0000000u && (a >> 29) != (e >> 29)) ||
         PhysOff(a) != PhysOff(e);
}
// True when [a, a + n) and [b, b + n) may share a byte, through an alias of the physical views too. Two different
// views are compared by their offset within the view with 0x1000 of slack: the 0xE0000000 view sits 0x1000 further on
// in physical memory on some hosts (Xenia's layout), not on others.
inline bool MayOverlap(uint32_t a, uint32_t b, uint32_t n) {
  if (!n) return false;
  const bool pa = a >= 0xA0000000u, pb = b >= 0xA0000000u;
  if (pa != pb) return false;
  uint64_t ka = a, kb = b, slack = 0;
  if (pa && (a >> 29) != (b >> 29)) {
    ka = a & 0x1FFFFFFFu;
    kb = b & 0x1FFFFFFFu;
    slack = 0x1000;
  }
  return (ka < kb ? kb - ka : ka - kb) < uint64_t(n) + slack;
}

// Hand-written natives (n_<ADDR>.h in app/src/hot, e.g. the CRT memcpy) cannot run as a shadow: their guard snapshots
// the guest ranges they may write, computed from the inputs BEFORE the call, runs the native, keeps its result, rolls
// the memory back, runs the original and compares (sa2-nx's guard). `overflow` = too many/too large to verify.
struct Region {
  uint32_t addr;
  uint32_t len;
};
struct Writes {
  static constexpr int kMax = 8;
  // sasrt-nx (2026-10-21): 16 MB (was 1 MB), for sub_82E7F918's whole 1280x720x4 picture a call.
  static constexpr uint32_t kMaxBytes = 16u << 20;
  Region r[kMax];
  int n = 0;
  bool overflow = false;
  void Add(uint32_t addr, uint32_t len) {
    if (!len) return;
    if (n >= kMax || len > kMaxBytes || uint64_t(addr) + len > 0x100000000ull) {
      overflow = true;
      return;
    }
    r[n++] = {addr, len};
  }
};

// Guest memory through a shadow run's stores (big-endian, like the guest).
inline uint8_t ShLoad8(const ShadowMemory& m, const uint8_t* base, uint32_t a) {
  uint8_t v;
  return m.Load(a, v) ? v : base[uint64_t(a) + PhysOff(a)];
}
inline uint16_t ShLoad16(const ShadowMemory& m, const uint8_t* base, uint32_t a) {
  return uint16_t(ShLoad8(m, base, a) << 8 | ShLoad8(m, base, a + 1));
}
inline uint32_t ShLoad32(const ShadowMemory& m, const uint8_t* base, uint32_t a) {
  return uint32_t(ShLoad16(m, base, a)) << 16 | ShLoad16(m, base, a + 2);
}
inline uint64_t ShLoad64(const ShadowMemory& m, const uint8_t* base, uint32_t a) {
  return uint64_t(ShLoad32(m, base, a)) << 32 | ShLoad32(m, base, a + 4);
}
inline void ShStore8(ShadowMemory& m, uint32_t a, uint8_t v) { m.Store8(a, v); }
inline void ShStore16(ShadowMemory& m, uint32_t a, uint16_t v) {
  m.Store8(a, uint8_t(v >> 8));
  m.Store8(a + 1, uint8_t(v));
}
inline void ShStore32(ShadowMemory& m, uint32_t a, uint32_t v) {
  ShStore16(m, a, uint16_t(v >> 16));
  ShStore16(m, a + 2, uint16_t(v));
}
inline void ShStore64(ShadowMemory& m, uint32_t a, uint64_t v) {
  ShStore32(m, a, uint32_t(v >> 32));
  ShStore32(m, a + 4, uint32_t(v));
}

}  // namespace sasrt::hot
