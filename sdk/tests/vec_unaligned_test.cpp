// sasrt-nx (2026-10-14; idea 5 of sa2-nx's list): stvlx / stvrx without byte loops (rex/ppc/vec_unaligned.h, written
// by tools/vec_unaligned_stores.py) against the generator's byte loops, for every alignment of the address inside its
// 16-byte block and random vectors: the 48 bytes around the block must be identical afterwards.
//
//   clang++ -O2 -std=c++23 -Isdk/include sdk/tests/vec_unaligned_test.cpp -o out/tools/vec_unaligned_test.exe
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <random>

#include <rex/ppc/vec_unaligned.h>

int main() {
  std::mt19937 rng(20261014);
  uint64_t checked = 0, failures = 0;
  for (int round = 0; round < 20000; ++round) {
    uint8_t u8[16];
    for (auto& b : u8) b = uint8_t(rng());
    uint8_t fill[48];
    for (auto& b : fill) b = uint8_t(rng());
    for (uint32_t offset = 0; offset < 16; ++offset) {
      const uint32_t ea = 0x40001000u + 16 + offset;  // a guest address in the middle block of the 48 bytes
      // stvlx
      uint8_t want[48], got[48];
      std::memcpy(want, fill, 48);
      std::memcpy(got, fill, 48);
      uint8_t* wbase = want - (0x40001000u);  // host = wbase + guest address
      for (size_t i = 0; i < (16 - (ea & 0xF)); i++) wbase[ea + i] = u8[15 - i];
      rex::ppc::StoreVectorLeft(got + (ea - 0x40001000u), ea, u8);
      ++checked;
      if (std::memcmp(want, got, 48) != 0 && failures++ < 10) std::printf("stvlx offset %u differs\n", offset);
      // stvrx
      std::memcpy(want, fill, 48);
      std::memcpy(got, fill, 48);
      for (size_t i = 0; i < (ea & 0xF); i++) wbase[ea - i - 1] = u8[i];
      rex::ppc::StoreVectorRight(got + ((ea & ~0xFu) - 0x40001000u), ea, u8);
      ++checked;
      if (std::memcmp(want, got, 48) != 0 && failures++ < 10) std::printf("stvrx offset %u differs\n", offset);
    }
  }
  std::printf("%llu comparisons of the stvlx / stvrx stores with the byte loops (16 alignments, random vectors)\n",
              (unsigned long long)checked);
  std::printf(failures ? "RESULT: FAILED (%llu differences)\n" : "RESULT: ok (0 differences)\n",
              (unsigned long long)failures);
  return failures ? 1 : 0;
}
