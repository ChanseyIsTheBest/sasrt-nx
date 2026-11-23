// sasrt-nx (2026-11-08, sasrt_renut_diag_trace; the far-cascade shadow flicker): a timeline of the threads that make a
// frame (the game thread's Swap, its pacing and waits; the worker's command buffer recording; splices, submissions,
// GPU callbacks and fence waits), kept in a ring and written to the log around each shadow dump window.
#pragma once

#include <atomic>  // sasrt-nx (2026-11-12, batch C10)
#include <cstdint>

namespace sasrt::trace {

enum Kind : uint16_t {
  kSwap = 1,           // the game's Swap hook entered; arg: the device's swap count after it
  kPaceBegin,          // the vblank pacing's wait (game thread)
  kPaceEnd,
  kFrameWaitBegin,     // QueueFrame's wait for the render thread
  kFrameWaitEnd,
  kBeginCb,            // BeginCommandBuffer; arg: the command buffer
  kEndCb,              // EndCommandBuffer; arg: the command buffer
  kSceneCamera,        // at an EndCommandBuffer of the scene pass: arg the first draw's c133.w as float bits, arg2 c131.w
  kSplice,             // sub_82CEF770; arg: the composed buffer
  kSubmit,             // sub_82CDE200 with recorded buffers; arg: their count
  kCallbackInsert,     // D3DDevice_InsertCallback; arg: the function
  kCallbackRun,        // a GPU callback run; arg: the function
  kFenceWaitBegin,     // the game's GPU fence wait (device.cpp's loop)
  kFenceWaitEnd,
  kLateInputBegin,     // banjo_late_input's delay of the frame's first controller read
  kLateInputEnd,
  kRenderFrameDone,    // the render thread finished a frame (QueueFrame's item)
  kWindow,             // a shadow dump window began (arg: the game frame)
  kGameFirstDraw,      // the first indexed draw not being recorded after a Swap (arg: its index count)
  kGameCamera,         // the game thread's draws with the camera block: c142.w, c143.w (the camera's x, y) when x changes
  // sasrt-nx (2026-11-19, split screen: the world following the other player):
  kSpliceBuffer,       // a buffer spliced: arg the buffer, arg2 its recording's camera x (c142.w; 0: none ended)
  kSubmitBuffer,       // a submission's buffer: arg the buffer, arg2 the camera x of the recording it named
  kSlotFill,           // a same-frame place filled: arg the buffer, arg2 the camera x
  kComposite,          // render thread: a composite (arg its number in the render frame, arg2 the frame before's count)
  kRenderCamera,       // render thread: the drawn camera changed: arg c142.w, arg2 the replayed buffer (0: direct)
  kSplitRun,           // sasrt_renut_split_scene: a submission's run: arg the buffer run, arg2 its camera x
};

// Records an event (any thread; lock-free; a no-op unless sasrt_renut_diag_trace is on).
void Note(Kind kind, uint64_t arg = 0, uint64_t arg2 = 0);
// sasrt-nx (2026-11-12, batch C10): a plain load once latched (it was an out-of-line call and a static's guard, a
// load-acquire, in every draw hook); the value comes from the configuration only.
extern bool g_on_value;
extern std::atomic<bool> g_on_latched;
[[gnu::cold, gnu::noinline]] bool LatchOn();
[[gnu::always_inline]] inline bool On() {
  if (!g_on_latched.load(std::memory_order_relaxed)) [[unlikely]]
    return LatchOn();
  return g_on_value;
}
// In the draw hooks: notes kGameFirstDraw for the first such draw after each Swap.
void NoteDraw(uint64_t index_count);
// In the draw hooks: notes kGameCamera when the camera x of the game thread's draws with the camera block changes.
void NoteGameCamera(const uint8_t *vertex_constants);
// sasrt-nx (2026-11-19): on the render thread (draw.cpp), the same for the drawn constants (c136, c137, c142, c143:
// 16 bytes each in guest order); arg2 the replayed buffer (0: the game thread's own draws).
void NoteRenderCamera(const uint8_t *c136, const uint8_t *c137, const uint8_t *c142, uint32_t replay_buffer);
// sasrt-nx (2026-11-19): a guest float's bits (big-endian words read as they are) for the dump.
inline uint64_t CameraWord(const uint8_t *reg16, int k) {
  uint32_t v;
  __builtin_memcpy(&v, reg16 + k * 4, 4);
  return __builtin_bswap32(v);
}
// A guest address whose big-endian word (a float) every later event samples (0: none); the dump prints it.
void SetWatch(uint32_t guest_address);
// Whether a camera hunt is wanted (set when a window begins, taken by the first scene pass after it).
bool TakeHunt();
// Called when a shadow dump window begins: the events of the last 1.5 s and of the next 1.5 s are written to the log.
void WindowBegan(uint64_t frame);
// sasrt-nx (2026-11-20): 0 for 150 ms after a window began, else -1: the shadow dump's window (draw.cpp
// SasrtShadowDumpWindow, a stub since 2026-11-08) for its light-volume and depth-writer logs.
int DiagWindowNow();

}  // namespace sasrt::trace
