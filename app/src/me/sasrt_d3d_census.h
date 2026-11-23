// Sonic & All-Stars Racing Transformed: the Direct3D census (sasrt_diag_d3d_census; sasrt_d3d_census.cpp).
#pragma once

#include <cstdint>

namespace sasrt::census {

// One entry point's call: Begin before the original, End right after it. Nothing happens while the cvar is off.
struct Token {
  uint32_t entry = 0;  // 0: not counted
  bool outermost = false;
  uint32_t device = 0, wptr = 0, limit = 0;
};
Token Begin(uint32_t entry, const uint8_t* base, uint32_t device);
void End(const Token& token, const uint8_t* base);

}  // namespace sasrt::census
