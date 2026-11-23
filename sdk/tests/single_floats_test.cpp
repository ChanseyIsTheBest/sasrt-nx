// sasrt-nx (2026-10-14; idea 2 of sa2-nx's list): single-precision arithmetic in float (tools/single_floats.py,
// REX_FADDS / REX_FSUBS / REX_FMULS / REX_FDIVS / REX_FSQRTS) against the generator's double form
// double(float(a op b)), bit for bit, for operands that hold single-precision values (what the tool proves): special
// values (zeros, denormals, the largest and smallest normals, infinities, NaNs with payloads), operands built to hit
// the halfway cases of the single rounding, and random pairs, in all four rounding modes with the flush mode off (the
// FPU mode these statements always run in: the generator switches to it before every scalar float operation).
//
// The negative control runs the same with flush-to-zero on: there the forms DIFFER (float(a) flushes a single
// denormal operand to zero before the operation, the double form uses it), which is why the tool leaves the any-mode
// forms alone and only rewrites the plain statements. The control must report differences.
//
//   clang++ -O2 -std=c++23 sdk/tests/single_floats_test.cpp -o out/tools/single_floats_test.exe [run_sdk_tests.ps1]
#include <cfenv>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <random>

#if defined(__x86_64__) || defined(_M_X64)
#include <xmmintrin.h>
#endif

namespace {

uint64_t g_checked = 0, g_failures = 0;
bool g_control = false;

uint64_t Bits(double d) {
  uint64_t u;
  std::memcpy(&u, &d, 8);
  return u;
}
double FromSingle(uint32_t bits) {
  float f;
  std::memcpy(&f, &bits, 4);
  return double(f);
}

void SetFlush(bool on) {
#if defined(__x86_64__) || defined(_M_X64)
  _mm_setcsr(on ? (_mm_getcsr() | 0x8040u) : (_mm_getcsr() & ~0x8040u));
#elif defined(__aarch64__)
  uint64_t fpcr;
  __asm__ volatile("mrs %0, fpcr" : "=r"(fpcr));
  fpcr = on ? (fpcr | (1ull << 24)) : (fpcr & ~(1ull << 24));
  __asm__ volatile("msr fpcr, %0" : : "r"(fpcr));
#endif
}

// The two forms, kept out of line so the operands are not constants.
[[gnu::noinline]] double DoubleForm(int op, double a, double b) {
  switch (op) {
    case 0: return double(float(a + b));
    case 1: return double(float(a - b));
    case 2: return double(float(a * b));
    case 3: return double(float(a / b));
    default: return double(float(std::sqrt(a)));
  }
}
[[gnu::noinline]] double FloatForm(int op, double a, double b) {
  switch (op) {
    case 0: return double(float(a) + float(b));
    case 1: return double(float(a) - float(b));
    case 2: return double(float(a) * float(b));
    case 3: return double(float(a) / float(b));
    default: return double(__builtin_sqrtf(float(a)));
  }
}

const char* const kOp[] = {"fadds", "fsubs", "fmuls", "fdivs", "fsqrts"};

void Check(double a, double b) {
  for (int op = 0; op < 5; ++op) {
    const uint64_t want = Bits(DoubleForm(op, a, b)), got = Bits(FloatForm(op, a, b));
    ++g_checked;
    if (got != want) {
      if (!g_control && g_failures < 12)
        std::printf("%s(%016llX, %016llX): float form %016llX, double form %016llX\n", kOp[op],
                    (unsigned long long)Bits(a), (unsigned long long)Bits(b), (unsigned long long)got,
                    (unsigned long long)want);
      ++g_failures;
    }
  }
}

uint32_t RandomSingle(std::mt19937& rng) {
  // A mix of every class: random exponent incl. 0 (denormals) and 255 (inf / NaN), random sign and mantissa.
  const uint32_t r = rng();
  switch (r & 7) {
    case 0: return (r & 0x807FFFFFu);                           // zero / denormal
    case 1: return (r & 0x80000000u) | 0x7F800000u | ((r >> 3) & 0x7FFFFFu);  // inf / NaN
    case 2: return (r & 0x80000000u) | (((r >> 8) % 6 + 1) << 23) | (r & 0x7FFFFFu);  // just above denormal
    case 3: return (r & 0x80000000u) | ((254 - (r >> 8) % 4) << 23) | (r & 0x7FFFFFu); // near overflow
    default: return rng();
  }
}

}  // namespace

int main(int argc, char** argv) {
  g_control = argc > 1 && std::strcmp(argv[1], "control") == 0;
  const uint32_t specials[] = {0x00000000u, 0x80000000u, 0x00000001u, 0x807FFFFFu, 0x00800000u, 0x3F800000u,
                               0xBF800000u, 0x7F7FFFFFu, 0xFF7FFFFFu, 0x7F800000u, 0xFF800000u, 0x7FC00000u,
                               0xFFC12345u, 0x7FA00001u, 0x3EAAAAABu, 0x4B800001u, 0x33800000u, 0x34000001u};
  const int modes[] = {FE_TONEAREST, FE_TOWARDZERO, FE_UPWARD, FE_DOWNWARD};
  const int pairs = argc > 2 ? std::atoi(argv[2]) : 4000000;
  std::mt19937 rng(20261014);
  for (int mode : modes) {
    std::fesetround(FE_TONEAREST);
    SetFlush(false);
    // The operands as the registers hold them: singles widened exactly (flush off, round to nearest).
    std::fesetround(mode);
    SetFlush(g_control);
    for (uint32_t x : specials)
      for (uint32_t y : specials) Check(FromSingle(x), FromSingle(y));
    for (int i = 0; i < pairs; ++i) {
      const uint32_t x = RandomSingle(rng), y = RandomSingle(rng);
      SetFlush(false);
      const double a = FromSingle(x), b = FromSingle(y);
      SetFlush(g_control);
      Check(a, b);
      // Halfway cases of the single rounding: a sum whose exact value sits on a tie of the single format (the
      // second operand rounded to a single first: the forms are only equal for single operands).
      Check(a, double(float(a * 0x1p-24)));
    }
  }
  std::fesetround(FE_TONEAREST);
  SetFlush(false);
  std::printf("%llu comparisons of the float forms with the double forms (%s)\n", (unsigned long long)g_checked,
              g_control ? "NEGATIVE CONTROL: flush-to-zero on" : "flush off, four rounding modes");
  if (g_control) {
    std::printf(g_failures ? "RESULT: ok (the control found %llu differences, as it must)\n"
                           : "RESULT: FAILED (the control found no difference: the inputs miss the denormal cases)\n",
                (unsigned long long)g_failures);
    return g_failures ? 0 : 1;
  }
  std::printf(g_failures ? "RESULT: FAILED (%llu differences)\n" : "RESULT: ok (0 differences)\n",
              (unsigned long long)g_failures);
  return g_failures ? 1 : 0;
}
