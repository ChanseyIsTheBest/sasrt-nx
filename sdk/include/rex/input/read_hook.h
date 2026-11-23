/**
 * sasrt-nx (2026-10-20, from sa2-nx's SDK): a function the input system calls at every controller state read
 * (InputSystem::GetState), before the read. Renut's late input delays the frame's first read there and its latency
 * probe notes the read (rex::latency::BeforeInputRead / NoteInputRead, app/src/renut_engine/sasrt_compat/
 * frame_latency.cpp). None by default.
 */
#pragma once

#include <cstdint>

namespace rex::input {

using ReadHook = void (*)();
void SetReadHook(ReadHook hook);

// sasrt-nx (2026-10-30): a function the input system calls with each state it gives the game (InputSystem::GetState,
// after the read, the user's devices merged): the user index and the buttons (XINPUT_GAMEPAD_* bits). The shadow
// dump's A+B+X+Y (sasrt_renut_diag_shadow_dump_buttons). None by default.
using StateHook = void (*)(uint32_t user_index, uint16_t buttons);
void SetStateHook(StateHook hook);

}  // namespace rex::input
