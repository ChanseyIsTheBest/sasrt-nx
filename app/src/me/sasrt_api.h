// Sonic & All-Stars Racing Transformed: the native Direct3D layer (sa2-nx's API-level renderer, its
// docs/api-renderer.md; ported 2026-10-07).
//
// The game's Xbox 360 Direct3D (the XDK library linked into the executable) turns every call into PM4 packets for an
// emulated Xenos command processor. Here its busiest entry points are native code: they keep the Direct3D device
// structure exactly as the game sees it (the game reads and writes parts of it inline), and hand the renderer host
// records of operations (src/me/me_native_system.cpp, the direct-state record format) instead of PM4. Each group of
// entry points has its own key (sasrt_api_*); verify mode (sasrt_cpu_verify) runs the original on a copy of the device
// first and compares everything (device bytes, the guest memory the call writes, and the native ops against the
// original's packets decoded the same way).
//
// This game's census (sasrt_diag_d3d_census, race of track 2.3): DrawIndexedVertices 44,118 calls a second (98 % of the
// draws; sa2-nx never calls it), the window scissor writer 12,052, the resolve 1,073, DrawVertices 604, Clear 209,
// DrawVerticesUP 119. Only draws into the main command buffer are native (Direct3D runs the command buffers it builds
// inside a segment many times and patches them after the call: a record is one-shot).
#pragma once

#include <cstdint>

struct PPCContext;

namespace sasrt::api {

// Draws (sasrt_api_draws): D3DDevice_DrawIndexedVertices and DrawVertices with Direct3D's draw-time state flush and
// shader load. Each returns false when it did not run (key off, the direct renderer off, not the main command buffer,
// a path the native code does not take): the hook then runs its old path.
bool DrawIndexedVertices(PPCContext& ctx, uint8_t* base);
bool DrawVertices(PPCContext& ctx, uint8_t* base);
// D3DDevice_BeginVertices (returns the inline vertices' address in r3) and D3DDevice_DrawVerticesUP (sa2-nx's).
bool BeginVertices(PPCContext& ctx, uint8_t* base);
bool DrawVerticesUP(PPCContext& ctx, uint8_t* base);
// Verify mode: Direct3D's inline-data allocator inside a shadow run of the original (a scratch address, no waiting).
bool ShadowInlineAlloc(PPCContext& ctx, uint8_t* base);
// D3DDevice_Clear (sasrt_api_clears, sa2-nx's).
bool Clear(PPCContext& ctx, uint8_t* base);
// Direct3D's window offset/scissor writer (registers 0x2080-0x2082; SetViewport, SetScissorRect, the surface setters).
bool WindowScissor(PPCContext& ctx, uint8_t* base);

// The [api] report lines (every 10 s, with the renderer's report).
void Report();

}  // namespace sasrt::api
