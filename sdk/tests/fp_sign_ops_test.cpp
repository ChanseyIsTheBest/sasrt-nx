// sasrt-nx (2026-10-14; idea 7 of sa2-nx's list): fneg / fabs / fnabs as float operations (tools/fp_sign_ops.py,
// REX_FNEG / REX_FABS / REX_FNABS) against the integer forms the generator writes (an XOR, AND-NOT or OR of the sign
// bit), bit for bit: every special value, every single-precision bit pattern widened to double (the values float
// code holds), and random 64-bit patterns; with the flush-to-zero / denormals-are-zero mode off and on and in all
// four rounding modes. The operands come through volatile, so the compiler cannot work a result out at build time.
//
//   clang++ -O2 -std=c++23 sdk/tests/fp_sign_ops_test.cpp -o out/tools/fp_sign_ops_test.exe   [tools/win/run_sdk_tests.ps1]
#include <cfenv>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <random>

#if defined(__x86_64__) || defined(_M_X64)
#include <xmmintrin.h>
#endif

namespace {

union Reg {
  double f64;
  uint64_t u64;
};

// The macros of tools/fp_sign_ops.py, both forms.
#define FLOAT_FNEG(d, s) ((d).f64 = -(s).f64)
#define FLOAT_FABS(d, s) ((d).f64 = __builtin_fabs((s).f64))
#define FLOAT_FNABS(d, s) ((d).f64 = -__builtin_fabs((s).f64))
#define INT_FNEG(d, s) ((d).u64 = (s).u64 ^ 0x8000000000000000ull)
#define INT_FABS(d, s) ((d).u64 = (s).u64 & ~0x8000000000000000ull)
#define INT_FNABS(d, s) ((d).u64 = (s).u64 | 0x8000000000000000ull)

uint64_t g_checked = 0, g_failures = 0;

[[gnu::noinline]] void Check(uint64_t bits) {
  volatile uint64_t in = bits;
  Reg s, a, b;
  s.u64 = in;
  FLOAT_FNEG(a, s);
  INT_FNEG(b, s);
  if (a.u64 != b.u64 && g_failures++ < 10) std::printf("fneg %016llX: %016llX, want %016llX\n", (unsigned long long)bits, (unsigned long long)a.u64, (unsigned long long)b.u64);
  FLOAT_FABS(a, s);
  INT_FABS(b, s);
  if (a.u64 != b.u64 && g_failures++ < 10) std::printf("fabs %016llX: %016llX, want %016llX\n", (unsigned long long)bits, (unsigned long long)a.u64, (unsigned long long)b.u64);
  FLOAT_FNABS(a, s);
  INT_FNABS(b, s);
  if (a.u64 != b.u64 && g_failures++ < 10) std::printf("fnabs %016llX: %016llX, want %016llX\n", (unsigned long long)bits, (unsigned long long)a.u64, (unsigned long long)b.u64);
  g_checked += 3;
}

void SetFlush(bool on) {
#if defined(__x86_64__) || defined(_M_X64)
  // FTZ (bit 15) and DAZ (bit 6): what the recompiled code's flush mode sets on the PC.
  _mm_setcsr(on ? (_mm_getcsr() | 0x8040u) : (_mm_getcsr() & ~0x8040u));
#elif defined(__aarch64__)
  uint64_t fpcr;
  __asm__ volatile("mrs %0, fpcr" : "=r"(fpcr));
  fpcr = on ? (fpcr | (1ull << 24)) : (fpcr & ~(1ull << 24));
  __asm__ volatile("msr fpcr, %0" : : "r"(fpcr));
#endif
}

}  // namespace

int main() {
  const uint64_t specials[] = {
      0x0000000000000000ull, 0x8000000000000000ull,  // +-0
      0x0000000000000001ull, 0x800FFFFFFFFFFFFFull,  // denormals
      0x0010000000000000ull, 0x3FF0000000000000ull, 0xBFF0000000000000ull, 0x7FEFFFFFFFFFFFFFull,
      0x7FF0000000000000ull, 0xFFF0000000000000ull,  // infinities
      0x7FF8000000000000ull, 0xFFF8000000000000ull,  // quiet NaNs
      0x7FF0000000000001ull, 0xFFF4000000000000ull,  // signalling NaNs: must stay signalling
      0x7FF8000020000000ull, 0x36A0000000000000ull,  // a widened single NaN, the smallest single denormal
  };
  const int modes[] = {FE_TONEAREST, FE_TOWARDZERO, FE_UPWARD, FE_DOWNWARD};
  std::mt19937_64 rng(20261014);
  for (int flush = 0; flush < 2; ++flush) {
    for (int mode : modes) {
      std::fesetround(mode);
      SetFlush(flush != 0);
      for (uint64_t s : specials) Check(s);
      for (int i = 0; i < 1000000; ++i) Check(rng());
    }
  }
  std::fesetround(FE_TONEAREST);
  // Every single-precision value as the double a load gives (flush off, round to nearest: the conversion is exact).
  // With the flush mode on, every 7th pattern (the mode goes off for each conversion and on again for the check).
  SetFlush(false);
  for (uint64_t u = 0; u <= 0xFFFFFFFFull; ++u) {
    float f;
    const uint32_t w = uint32_t(u);
    std::memcpy(&f, &w, 4);
    Reg r;
    r.f64 = double(f);
    Check(r.u64);
  }
  for (uint64_t u = 0; u <= 0xFFFFFFFFull; u += 7) {
    float f;
    const uint32_t w = uint32_t(u);
    std::memcpy(&f, &w, 4);
    Reg r;
    r.f64 = double(f);
    SetFlush(true);
    Check(r.u64);
    SetFlush(false);
  }
  std::printf("%llu comparisons of the float sign forms (fneg, fabs, fnabs) with the integer forms\n",
              (unsigned long long)g_checked);
  std::printf(g_failures ? "RESULT: FAILED (%llu differences)\n" : "RESULT: ok (0 differences)\n",
              (unsigned long long)g_failures);
  return g_failures ? 1 : 0;
}
