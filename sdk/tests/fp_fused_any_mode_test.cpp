// sasrt-nx (2026-11-12, moonshot idea 1 part 2: codegen option fp_fused_single_any_mode): the any-mode helpers of the
// fused single operations (rex::ppc::FmaddSingleAnyMode, FmsubSingleAnyMode, FnmaddSingleAnyMode, FnmsubSingleAnyMode
// in rex/ppc/diet_ops.h) against the generator's plain FPU-mode expressions, `double(float(+-std::fma(a, c, +-b)))`
// evaluated with the host flush mode OFF. Each helper must give the same bits with the mode off AND on, and leave the
// mode as it found it.
//
// Inputs: every triple of a list of edge values, then random triples (exponents drawn from the edges half of the
// time) and triples whose addend nearly cancels the product (b = -(a * c) with its low bits disturbed: fused results
// that are tiny in double or below FLT_MIN, the cases the mode can change).
//
//   clang++ -O2 -std=c++23 -ffp-contract=off -mfma -Isdk/include -Isdk/thirdparty/simde -Isdk/thirdparty/simde/simde
//           sdk/tests/fp_fused_any_mode_test.cpp -o out/tools/fp_fused_any_mode_test.exe
//   fp_fused_any_mode_test [random triples = 20000000] [control]
// -mfma: std::fma as the hardware instruction (the A57's fmadd honours FZ the way vfmadd honours DAZ/FTZ; a software
// fma would test the library instead). "control" puts the plain expressions in the helpers' place: that run must
// report differences (the inputs reach the cases where the mode matters).
#include <bit>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <vector>

#include <rex/ppc/diet_ops.h>

namespace {

using P = rex::platform::FPSCRPlatform;

#if defined(__aarch64__)
#define OPAQUE(x) __asm__ __volatile__("" : "+w"(x))
#else
#define OPAQUE(x) __asm__ __volatile__("" : "+x"(x))
#endif

void SetFlush(bool on) {
  auto csr = P::getcsr();
  csr = on ? decltype(csr)(csr | decltype(csr)(P::FlushMask)) : decltype(csr)(csr & ~decltype(csr)(P::FlushMask));
  P::setcsr(csr);
}

#define FUSED(NAME, EXPR, HELPER)                                          \
  [[gnu::noinline]] uint64_t Plain##NAME(double a, double c, double b) {   \
    OPAQUE(a);                                                             \
    OPAQUE(c);                                                             \
    OPAQUE(b);                                                             \
    double d = EXPR;                                                       \
    OPAQUE(d);                                                             \
    float f = float(d);                                                    \
    OPAQUE(f);                                                             \
    double r = double(f);                                                  \
    OPAQUE(r);                                                             \
    return std::bit_cast<uint64_t>(r);                                     \
  }                                                                        \
  [[gnu::noinline]] uint64_t Any##NAME(double a, double c, double b) {     \
    OPAQUE(a);                                                             \
    OPAQUE(c);                                                             \
    OPAQUE(b);                                                             \
    double r = rex::ppc::HELPER(a, c, b);                                  \
    OPAQUE(r);                                                             \
    return std::bit_cast<uint64_t>(r);                                     \
  }
FUSED(Fmadd, std::fma(a, c, b), FmaddSingleAnyMode)
FUSED(Fmsub, std::fma(a, c, -b), FmsubSingleAnyMode)
FUSED(Fnmadd, -std::fma(a, c, b), FnmaddSingleAnyMode)
FUSED(Fnmsub, -std::fma(a, c, -b), FnmsubSingleAnyMode)
#undef FUSED

uint64_t g_state = 0x9E3779B97F4A7C15ull;
uint64_t Next() {
  g_state ^= g_state << 13;
  g_state ^= g_state >> 7;
  g_state ^= g_state << 17;
  return g_state;
}
double RandomDouble() {
  static const uint64_t exponents[] = {0,     0,     1,     2,     3,     0x369, 0x36A, 0x380, 0x381, 0x382,
                                       0x3FF, 0x47E, 0x47F, 0x7FE, 0x7FF, 0x1FF, 0x200, 0x201, 0x3BF, 0x3C0,
                                       0x3C1, 0x3B4, 0x3B5, 0x43E, 0x43F, 0x5FE, 0x5FF, 0x3F0, 0x3E0, 0x3D0};
  uint64_t r = Next();
  uint64_t e = (r >> 52) & 0x7FF;
  if (Next() & 1) e = exponents[Next() % (sizeof(exponents) / sizeof(exponents[0]))];
  uint64_t m = r & 0x000FFFFFFFFFFFFFull;
  switch (Next() & 7) {
    case 0: m = 0; break;
    case 1: m = 0x000FFFFFFFFFFFFFull; break;
    case 2: case 3: case 4: m &= 0x000FFFFFE0000000ull; break;  // a single's mantissa (the guest's usual operands)
    case 5: m = (m & 0x000FFFFFE0000000ull) | 0x10000000ull; break;  // a tie when rounded to single
    default: break;
  }
  return std::bit_cast<double>((r & 0x8000000000000000ull) | (e << 52) | m);
}

uint64_t g_failures = 0, g_checks = 0, g_mode_matters[4] = {};
bool g_control = false;
void Fail(const char* what, bool mode, double a, double c, double b, uint64_t got, uint64_t want) {
  if (g_failures++ < 20) {
    std::printf("FAILED %s (flush mode %s): a %016llX c %016llX b %016llX got %llX want %llX\n", what,
                mode ? "on" : "off", static_cast<unsigned long long>(std::bit_cast<uint64_t>(a)),
                static_cast<unsigned long long>(std::bit_cast<uint64_t>(c)),
                static_cast<unsigned long long>(std::bit_cast<uint64_t>(b)), static_cast<unsigned long long>(got),
                static_cast<unsigned long long>(want));
  }
}

void CheckTriple(double a, double c, double b) {
  SetFlush(false);
  const uint64_t want[4] = {PlainFmadd(a, c, b), PlainFmsub(a, c, b), PlainFnmadd(a, c, b), PlainFnmsub(a, c, b)};
  // NaN payloads: compared as "is a NaN" (the operation returns one of the operands' payloads either way).
  const auto same = [](uint64_t x, uint64_t y) {
    const bool nx = (x & 0x7FFFFFFFFFFFFFFFull) > 0x7FF0000000000000ull;
    const bool ny = (y & 0x7FFFFFFFFFFFFFFFull) > 0x7FF0000000000000ull;
    return nx || ny ? nx == ny : x == y;
  };
  static const char* const names[4] = {"FmaddSingleAnyMode", "FmsubSingleAnyMode", "FnmaddSingleAnyMode",
                                       "FnmsubSingleAnyMode"};
  for (const bool mode : {false, true}) {
    SetFlush(mode);
    const auto before = P::getcsr();
    const uint64_t got[4] = {
        g_control ? PlainFmadd(a, c, b) : AnyFmadd(a, c, b), g_control ? PlainFmsub(a, c, b) : AnyFmsub(a, c, b),
        g_control ? PlainFnmadd(a, c, b) : AnyFnmadd(a, c, b), g_control ? PlainFnmsub(a, c, b) : AnyFnmsub(a, c, b)};
    const auto after = P::getcsr();
    for (int k = 0; k < 4; ++k) {
      if (!same(got[k], want[k])) Fail(names[k], mode, a, c, b, got[k], want[k]);
    }
    if (mode) {
      const uint64_t plain_on[4] = {PlainFmadd(a, c, b), PlainFmsub(a, c, b), PlainFnmadd(a, c, b),
                                    PlainFnmsub(a, c, b)};
      for (int k = 0; k < 4; ++k) g_mode_matters[k] += !same(plain_on[k], want[k]);
    }
    g_checks += 4;
    if ((before ^ after) & decltype(before)(P::FlushMask)) Fail("the mode was left changed", mode, a, c, b, after, before);
  }
}

}  // namespace

int main(int argc, char** argv) {
  const uint64_t random_triples = argc > 1 ? std::strtoull(argv[1], nullptr, 10) : 20000000ull;
  g_control = argc > 2 && argv[2][0] == 'c';
  const auto saved = P::getcsr();
  std::vector<double> edges;
  const uint64_t magnitudes[] = {
      0x0000000000000000ull, 0x0000000000000001ull, 0x000FFFFFFFFFFFFFull, 0x0010000000000000ull,  // DBL_MIN
      0x36A0000000000000ull, 0x3690000000000000ull,                          // the smallest single denormal, half of it
      0x380FFFFFFFFFFFFFull, 0x3810000000000000ull, 0x3800000000000000ull,  // FLT_MIN, a single denormal
      0x3FF0000000000000ull, 0x3FF0000010000000ull, 0x3FEFFFFFFFFFFFFFull,  // around 1
      0x2000000000000000ull, 0x1FF0000000000000ull,                          // 2^-511, 2^-512: products near DBL_MIN
      0x3C00000000000000ull, 0x3BF0000000000000ull,                          // 2^-63, 2^-64: products near FLT_MIN
      0x47EFFFFFE0000000ull, 0x7FEFFFFFFFFFFFFFull, 0x7FF0000000000000ull, 0x7FF8000000000000ull,
      0x7FF0000000000001ull};
  for (const uint64_t m : magnitudes) {
    edges.push_back(std::bit_cast<double>(m));
    edges.push_back(std::bit_cast<double>(m | 0x8000000000000000ull));
  }
  for (const double a : edges)
    for (const double c : edges)
      for (const double b : edges) CheckTriple(a, c, b);
  for (uint64_t i = 0; i < random_triples; ++i) {
    const double a = RandomDouble();
    const double c = (i & 7) == 0 ? edges[Next() % edges.size()] : RandomDouble();
    double b = (i & 3) == 0 ? edges[Next() % edges.size()] : RandomDouble();
    if ((i & 3) == 1) {
      // A near-cancelling addend: the fused result lands on tiny values (exactly representable products of
      // single-mantissa operands make many of them exact).
      SetFlush(false);
      double p = a * c;
      OPAQUE(p);
      const uint64_t bits = std::bit_cast<uint64_t>(p) ^ 0x8000000000000000ull ^ (Next() & 0x3FFFFFFFull);
      b = std::bit_cast<double>(bits);
    }
    CheckTriple(a, c, b);
  }
  P::setcsr(saved);
  std::printf("%llu edge triples and %llu random triples, %llu comparisons of a helper with the plain expression\n",
              static_cast<unsigned long long>(edges.size() * edges.size() * edges.size()),
              static_cast<unsigned long long>(random_triples), static_cast<unsigned long long>(g_checks));
  std::printf("triples whose plain result differs between the modes: fmadds %llu, fmsubs %llu, fnmadds %llu, "
              "fnmsubs %llu\n",
              static_cast<unsigned long long>(g_mode_matters[0]), static_cast<unsigned long long>(g_mode_matters[1]),
              static_cast<unsigned long long>(g_mode_matters[2]), static_cast<unsigned long long>(g_mode_matters[3]));
  if (g_control) {
    std::printf("NEGATIVE CONTROL (plain expressions with the mode on): %llu differences; the test can see the "
                "mode: %s\n",
                static_cast<unsigned long long>(g_failures), g_failures ? "yes" : "NO");
    return g_failures ? 0 : 1;
  }
  std::printf(g_failures ? "RESULT: FAILED (%llu differences)\n" : "RESULT: ok (0 differences)\n",
              static_cast<unsigned long long>(g_failures));
  return g_failures ? 1 : 0;
}
