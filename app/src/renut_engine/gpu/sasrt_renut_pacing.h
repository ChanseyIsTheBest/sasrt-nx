// sa2-nx (2026-10-20): the game's frame pacing with Renut's renderer (sasrt_renut_pacing.cpp).
#pragma once

#include <cstdint>

namespace sasrt::renut {

void PaceSwap(uint32_t device_va);

// sasrt-nx (2026-11-19, the user: "framerate cap so we can increase the max framerate of the game to 60 let it be
// adjustable in increments of 5"): the frame cap in use, 30 to 60 in steps of 5 (frame_cap; 30 = the game's own
// presentation interval, as before). Any thread.
int FrameCap();

}  // namespace sasrt::renut

// The game menu's live setter and getter (src/game_menu.cpp, the base's names): fps rounded to a step of 5 in 30-60.
void BlurSetFrameCapLive(int fps);
int BlurFrameCapNow();
