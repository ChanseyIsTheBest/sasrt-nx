// Native graphics system (see me_native_system.cpp).
#pragma once

#include <memory>

#include <rex/system/interfaces/graphics.h>

struct PPCContext;  // rex/ppc/context.h (FlushRunsDirect)

namespace me::native {

// true when MASSEFFECT_NATIVE=1: the app installs the native system instead of Xenos emulation.
bool Enabled();

std::unique_ptr<rex::system::IGraphicsSystem> CreateGraphicsSystem();

// Called on the game thread when Direct3D binds a shader object (sub_8222F850), before it patches the
// vertex shader: records which library entry the microcode at that physical address belongs to, so the
// ring can identify IM_LOADs by address No-op without the native system.
void NoteShaderObject(const uint8_t* base, uint32_t object, bool vertex);

// True when the shader object was matched to a library entry (diagnostics).
bool HasEntry(uint32_t object);

// sasrt_cpu_note_shader_pair: true when NoteShaderObject's work is finished for both objects (two NoteShaderObject calls
// would return at once): the hooks then skip both. Two relaxed table loads; false with the key off.
bool ShaderObjectsFinished(uint32_t vs, uint32_t ps);

// Called on the game thread by the Direct3D draw functions (the game's hooks file): the device they were called on
// (r3), the call's primitive type and counts. The record also takes the bound VS and PS objects from the device and
// its command-buffer position (device+48). The ring pairs each DRAW_INDX with these records in order, because the
// ring's own shader loads can be immediate copies Direct3D patched. No-op without the native system.
void NoteDrawCall(const uint8_t* base, uint32_t device, uint32_t type, uint32_t r5, uint32_t r6, uint32_t r7);

// sasrt_cpu_direct_state (the direct renderer, step 1, sa2-nx's): the draw hooks call BeginDrawDirect before Direct3D's
// draw function and EndDrawDirect right after it. The state packets the draw function wrote before its draw packet
// become a host record the ring applies directly (no PM4 parsing for them), covered in the command buffer by one NOP
// packet. See namespace direct in me_native_system.cpp. No-op without the native system or with the key off.
struct DrawDirect {
  uint32_t device = 0;       // 0 = nothing to do after the call
  uint32_t start = 0;        // Direct3D's command buffer write pointer before the call (the last word written)
  uint32_t limit = 0;        // the command buffer segment's limits before the call (device+52, +56): a segment
  uint32_t soft_limit = 0;   //   change during the call leaves the packets as they are
  uint64_t submissions = 0;  // the ring write pointer's guest writes before the call
};
DrawDirect BeginDrawDirect(const uint8_t* base, uint32_t device);
void EndDrawDirect(uint8_t* base, const DrawDirect& d);
// D3DDevice_BeginTiling (true) and EndTiling (false), from the game's hooks: predicated tiling runs the range in between
// once per tile, so its draws keep their packets.
void NoteTiling(bool begin);
// sasrt_cpu_direct_flush (the direct renderer, step 2), from the hooks of Direct3D's three state flush functions
// (r3 = device, r4 = dirty mask, bit 63 first, r5 = first register, r6 = shadow in the device): inside a converted
// draw call, the call's register runs go into its record and a placeholder NOP into the command buffer. false when it
// does not apply (no converted call, the original would take its slow path, no room, outside the main command
// buffer): the hook then runs the original. `original` is the recompiled function, which the self-check runs on a copy.
enum class FlushKind : uint8_t {
  kConstants,  // 16 registers per bit (the shader constant flush, sub_82CE1760; sa2-nx sub_82555CC8)
  kFetch,      // 6 registers per bit, then the 0x5000 end packet (the fetch constant flush, sub_82CE15C0)
  kGroups,     // 1 register per bit (the register group flush, sub_82CE1310)
};
bool FlushRunsDirect(PPCContext& ctx, uint8_t* base, uint32_t device, uint64_t mask, uint32_t register_base,
                     uint32_t shadow, FlushKind kind, void (*original)(PPCContext&, uint8_t*));

// sasrt_api_draws (the native Direct3D layer, sasrt_api_draw.cpp; sa2-nx's docs/api-renderer.md): records the native
// code writes itself, on the calling thread's own ring of records, named by a marker NOP [0xC0011000][kApiMarkerMagic]
// [seq] the caller puts in the command buffer after publishing. ApiProducer: this thread's ring (nullptr: the direct
// renderer is off or every ring is taken; keep it per thread). ApiMainBuffer: the device writes into the main command
// buffer and nothing is tiled (only there are records one-shot). Reserve/Commit write a record in place (Reserve:
// nullptr when there is no room; Commit: 0 when the reservation was lost); Publish copies one. Both return its number.
constexpr uint32_t kApiMarkerMagic = 0x53413241u;  // 'SA2A'
void* ApiProducer();
bool ApiMainBuffer(const uint8_t* base, uint32_t device);
uint32_t* ReserveApiRecord(void* producer, uint32_t max_words);
uint32_t CommitApiRecord(void* producer, const uint32_t* ops, uint32_t n);
uint32_t PublishApiRecord(void* producer, const uint32_t* ops, uint32_t n);

// D3DVertexBuffer_Lock (the game's hooks): the buffer's data range [address, address + bytes) may be rewritten by the
// game from now on (a vertex cache must copy it again). Counted for the report.
void NoteVertexBufferLock(uint32_t address, uint32_t bytes, uint32_t flags);

// Where the game's Direct3D device keeps the bound vertex and pixel shader objects; it moves between XDK versions
// (Mass Effect, the default: +12416 / +12412; Banjo-Kazooie N&B, 2008: +12696 / +12692; SA2, 2012: +13072 / +13068).
// Set once by the game's hooks file, before the first draw.
void SetDeviceShaderOffsets(uint32_t vertex_shader_offset, uint32_t pixel_shader_offset);

// Called by the ring thread after it writes the read pointer back: wakes the game's D3D GPU wait
// (src/native/me_ring_wait.cpp, sub_8222FA98).
void NotifyRingProgress();

// The progress counter NotifyRingProgress bumps, and a sleep until it moves past `seen` (at most max_us; true when it
// moved). For the game's D3D GPU wait (src/sasrt_gpu_wait.cpp).
uint32_t RingProgress();
bool WaitRingProgress(uint32_t seen, uint32_t max_us);

}  // namespace me::native
