# Batch 3's SDK / app half (machine-copy idea 43, B4 so far). Idempotent. Apply after batch 2's builds.
R = 'D:/sonic transformed/sasrt-nx/'
MARK = 'machine-copy batch 3 (2026-11-11)'


def load(p):
    b = open(R + p, 'rb').read()
    crlf = b'\r\n' in b
    return b.decode('utf-8').replace('\r\n', '\n'), crlf


def save(p, s, crlf):
    open(R + p, 'wb').write((s.replace('\n', '\r\n') if crlf else s).encode('utf-8'))


def patch(path, edits):
    s, c = load(path)
    if MARK in s:
        print('already patched:', path)
        return
    for old, new in edits:
        assert s.count(old) == 1, (path, old[:80], s.count(old))
        s = s.replace(old, new)
    save(path, s, c)
    print('patched:', path)


patch('sdk/include/rex/ppc/context.h', [
    ('''  inline void setFromMask(simde__m128 mask, int imm) noexcept {
    int m = simde_mm_movemask_ps(mask);''', '''  inline void setFromMask(simde__m128 mask, int imm) noexcept {
#if (defined(__aarch64__) || defined(_M_ARM64)) && !defined(REX_SETFROMMASK_MOVEMASK)
    // sasrt-nx (2026-11-11, machine-copy batch 3 (2026-11-11), idea 43 B4): cr6 of a vcmp*fp. with the all-lanes
    // immediate (the only one the generator emits): lt when every lane's sign bit is set, eq when none is, for any
    // mask. Each lane to all-ones / zero by its sign (an arithmetic shift), narrowed to 16 bits, read as one 64-bit
    // word: all-ones exactly when all four are set, zero exactly when none is. movemask's shifts, `addv` and constant go.
    // REX_SETFROMMASK_MOVEMASK: the movemask form.
    if (__builtin_constant_p(imm) && imm == 0xF) {
      const uint64_t s = vget_lane_u64(vreinterpret_u64_u16(vmovn_u32(vreinterpretq_u32_s32(
                                           vshrq_n_s32(vreinterpretq_s32_f32(simde__m128_to_neon_f32(mask)), 31)))),
                                       0);
      lt = s == ~uint64_t(0);
      gt = 0;
      eq = s == 0;
      so = 0;
      return;
    }
#endif
    int m = simde_mm_movemask_ps(mask);'''),
    ('''  inline void setFromMask(simde__m128i mask, int imm) noexcept {
    int m = simde_mm_movemask_epi8(mask);''', '''  inline void setFromMask(simde__m128i mask, int imm) noexcept {
#if (defined(__aarch64__) || defined(_M_ARM64)) && !defined(REX_SETFROMMASK_MOVEMASK)
    // (Idea 43 B4, the byte form: vcmp*. on integers, immediate 0xFFFF.) Each byte to all-ones / zero by its sign, two
    // bytes' halves into one byte (shift right by 4 and narrow), read as one 64-bit word.
    if (__builtin_constant_p(imm) && imm == 0xFFFF) {
      const uint64_t s = vget_lane_u64(vreinterpret_u64_u8(vshrn_n_u16(vreinterpretq_u16_s8(
                                           vshrq_n_s8(simde__m128i_to_neon_i8(mask), 7)), 4)),
                                       0);
      lt = s == ~uint64_t(0);
      gt = 0;
      eq = s == 0;
      so = 0;
      return;
    }
#endif
    int m = simde_mm_movemask_epi8(mask);'''),
])
print('batch 3 app half done')

# --- idea 43 F1 / F2: the CMake switches of tools/vmx_float_macros.py (both off: today's results) ---
patch('app/CMakeLists.txt', [('''option(SASRT_FORCE_INLINE_HELPERS''', '''# sasrt-nx (2026-11-11, machine-copy batch 3 (2026-11-11), idea 43 F1 / F2): VMX's estimates and multiply-add in their
# faster AArch64 forms (tools/vmx_float_macros.py): NOT the same results as today (closer to the 360's own, which
# estimates and rounds once); off until sasrt_test_vmx_fuzz's numbers are read. Global, so the SDK sees the same.
option(SASRT_VMX_FAST_ESTIMATES "VMX vrsqrtefp / vrefp as frsqrte / frecpe with two Newton steps (not bit-exact)" OFF)
option(SASRT_VMX_FUSED_MADD "VMX vmaddfp as one fused multiply-add (not bit-exact)" OFF)
if(SASRT_VMX_FAST_ESTIMATES)
    add_compile_definitions(REX_VMX_FAST_ESTIMATES)
endif()
if(SASRT_VMX_FUSED_MADD)
    add_compile_definitions(REX_VMX_FUSED_MADD)
endif()
option(SASRT_FORCE_INLINE_HELPERS''')])

# --- idea 43 F1 / F2: the fuzz test on the console (sasrt_test_vmx_fuzz) ---
FUZZ = r'''
// sasrt-nx (2026-11-11, machine-copy batch 3 (2026-11-11), idea 43 F1 / F2): tools/vmx_float_macros.py's fast forms
// against today's exact ones, on the console itself (x86 cannot reproduce NEON's estimates). With the key, a thread
// started at the first hook runs N million lanes of random bit patterns (plus the special values) through each pair with
// the flush mode on (as the game's VMX code runs) and logs the largest difference in units in the last place and the
// special cases that differ (NaN, infinity, sign, zero). Only reports; nothing in the game changes.
REXCVAR_DEFINE_INT32(sasrt_test_vmx_fuzz, 0, "SASRT/Localized copies",
                     "Test: compare the fast VMX estimate and multiply-add forms with the exact ones over N million "
                     "lanes on the console (\"[vmxfuzz]\" lines; 0 off)")
    .range(0, 1000)
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
'''
FUZZ_FN = r'''
#if defined(REX_VMX_FLOAT_HELPERS)
namespace {
// Idea 43's fuzz test (sasrt_test_vmx_fuzz above).
struct FuzzStat {
  uint64_t lanes = 0, differ = 0, special = 0;
  uint32_t max_ulp = 0;
  uint32_t worst_in[3] = {0, 0, 0};
};
uint32_t UlpApart(uint32_t a, uint32_t b) {
  auto key = [](uint32_t v) { return (v & 0x80000000u) ? 0x80000000u - (v & 0x7FFFFFFFu) : 0x80000000u + v; };
  const uint32_t x = key(a), y = key(b);
  return x > y ? x - y : y - x;
}
void FuzzNote(FuzzStat& st, uint32_t exact, uint32_t fast, uint32_t a, uint32_t b, uint32_t c) {
  ++st.lanes;
  if (exact == fast) return;
  ++st.differ;
  const bool nan_e = (exact & 0x7FFFFFFFu) > 0x7F800000u, nan_f = (fast & 0x7FFFFFFFu) > 0x7F800000u;
  const bool inf_e = (exact & 0x7FFFFFFFu) == 0x7F800000u, inf_f = (fast & 0x7FFFFFFFu) == 0x7F800000u;
  if (nan_e != nan_f || inf_e != inf_f || ((exact ^ fast) & 0x80000000u)) {
    ++st.special;
    return;
  }
  if (nan_e) return;  // both NaN (payloads aside)
  const uint32_t u = UlpApart(exact, fast);
  if (u > st.max_ulp) {
    st.max_ulp = u;
    st.worst_in[0] = a, st.worst_in[1] = b, st.worst_in[2] = c;
  }
}
void VmxFuzz(int millions) {
  uint64_t fpcr;
  __asm__ __volatile__("mrs %0, fpcr" : "=r"(fpcr));
  __asm__ __volatile__("msr fpcr, %0" ::"r"(fpcr | (1ull << 24)) : "memory");  // FZ, as the game's VMX code runs
  uint64_t s = 0x9E3779B97F4A7C15ull;
  auto next = [&s] {
    s ^= s << 13, s ^= s >> 7, s ^= s << 17;
    return uint32_t(s);
  };
  static const uint32_t kSpecial[] = {0x00000000u, 0x80000000u, 0x7F800000u, 0xFF800000u, 0x7FC00000u, 0x7F800001u,
                                      0x00000001u, 0x807FFFFFu, 0x00800000u, 0x3F800000u, 0xBF800000u, 0x7F7FFFFFu};
  FuzzStat rs, re, ma;
  const uint64_t n = uint64_t(millions) * 1000000ull / 4 + 3;
  for (uint64_t i = 0; i < n; ++i) {
    alignas(16) uint32_t a[4], b[4], c[4], e[4], f[4];
    for (int k = 0; k < 4; ++k) {
      a[k] = i < 3 ? kSpecial[(i * 4 + k) % 12] : next();
      b[k] = next();
      c[k] = next();
    }
    const simde__m128 va = simde_mm_load_ps(reinterpret_cast<const float*>(a));
    const simde__m128 vb = simde_mm_load_ps(reinterpret_cast<const float*>(b));
    const simde__m128 vc = simde_mm_load_ps(reinterpret_cast<const float*>(c));
    simde_mm_store_ps(reinterpret_cast<float*>(e), simde_mm_div_ps(simde_mm_set1_ps(1), simde_mm_sqrt_ps(va)));
    simde_mm_store_ps(reinterpret_cast<float*>(f), rex_vrsqrtefp_fast_(va));
    for (int k = 0; k < 4; ++k) FuzzNote(rs, e[k], f[k], a[k], 0, 0);
    simde_mm_store_ps(reinterpret_cast<float*>(e), simde_mm_div_ps(simde_mm_set1_ps(1), va));
    simde_mm_store_ps(reinterpret_cast<float*>(f), rex_vrefp_fast_(va));
    for (int k = 0; k < 4; ++k) FuzzNote(re, e[k], f[k], a[k], 0, 0);
    simde_mm_store_ps(reinterpret_cast<float*>(e), simde_mm_add_ps(simde_mm_mul_ps(va, vb), vc));
    simde_mm_store_ps(reinterpret_cast<float*>(f), rex_vmaddfp_fused_(va, vb, vc));
    for (int k = 0; k < 4; ++k) FuzzNote(ma, e[k], f[k], a[k], b[k], c[k]);
  }
  __asm__ __volatile__("msr fpcr, %0" ::"r"(fpcr) : "memory");
  for (const auto& [name, st] : {std::pair<const char*, const FuzzStat&>{"vrsqrtefp", rs}, {"vrefp", re},
                                 {"vmaddfp (fused)", ma}})
    REXLOG_INFO("[vmxfuzz] {}: {} lanes, {} differ ({:.3f} %), {} in a special case (NaN / infinity / sign); the "
                "largest difference {} ulp (inputs {:#010x} {:#010x} {:#010x})",
                name, st.lanes, st.differ, st.lanes ? 100.0 * double(st.differ) / double(st.lanes) : 0.0, st.special,
                st.max_ulp, st.worst_in[0], st.worst_in[1], st.worst_in[2]);
}
}  // namespace
#endif
'''
patch('app/src/cpu/banjo_hot_guest.cpp', [
    ('''REXCVAR_DEFINE_INT32(banjo_hot_guard_calls,''', FUZZ.lstrip('\n') + '''REXCVAR_DEFINE_INT32(banjo_hot_guard_calls,'''),
    ('''uint8_t InitHook(Hook& h, uint8_t* base) {
  // sasrt-nx (2026-11-11, machine-copy idea 46): the census thread''', FUZZ_FN.lstrip('\n') + '''uint8_t InitHook(Hook& h, uint8_t* base) {
#if defined(REX_VMX_FLOAT_HELPERS)
  // sasrt-nx (2026-11-11, machine-copy idea 43): the fuzz test's thread, once (sasrt_test_vmx_fuzz).
  static std::once_flag fuzz_once;
  if (const int m = REXCVAR_GET(sasrt_test_vmx_fuzz); m > 0)
    std::call_once(fuzz_once, [m] {
      StartBackground([](void* p) { VmxFuzz(int(reinterpret_cast<intptr_t>(p))); }, reinterpret_cast<void*>(intptr_t(m)));
    });
#endif
  // sasrt-nx (2026-11-11, machine-copy idea 46): the census thread'''),
])
print('fuzz staged')

# --- idea 46 part 2: the frozen loops' switch (tools/localize_native.py, frozen.txt) ---
s46, c46 = load('app/src/cpu/banjo_hot_common.h')
if 'REX_FROZEN_ON' not in s46:
    old = '#ifndef REX_CARD_RUN_DECL'
    assert s46.count(old) == 1
    s46 = s46.replace(old, '''// sasrt-nx (2026-11-11, machine-copy batch 3, idea 46 part 2): the copies' frozen loops (tools/localize_native.py,
// app/src/cpu/hot/frozen.txt) use their built-in values only when this is 1 and the entry check passes. CMake
// SASRT_HOT_FROZEN=OFF: 0 (every load as before).
#ifndef REX_FROZEN_ON
#if defined(SASRT_HOT_FROZEN_OFF)
#define REX_FROZEN_ON 0
#else
#define REX_FROZEN_ON 1
#endif
#endif
''' + old, 1)
    save('app/src/cpu/banjo_hot_common.h', s46, c46)
    print('patched: banjo_hot_common.h (REX_FROZEN_ON)')
s46, c46 = load('app/CMakeLists.txt')
if 'SASRT_HOT_FROZEN' not in s46:
    old = 'option(SASRT_VMX_FAST_ESTIMATES'
    assert s46.count(old) == 1
    s46 = s46.replace(old, '''# sasrt-nx (2026-11-11, machine-copy batch 3, idea 46 part 2): the copies' loops with the stable globals built in.
option(SASRT_HOT_FROZEN "Localized copies: stable guest globals built into their loops behind an entry check" ON)
if(NOT SASRT_HOT_FROZEN)
    add_compile_definitions(SASRT_HOT_FROZEN_OFF)
endif()
''' + old, 1)
    save('app/CMakeLists.txt', s46, c46)
    print('patched: CMakeLists.txt (SASRT_HOT_FROZEN)')
