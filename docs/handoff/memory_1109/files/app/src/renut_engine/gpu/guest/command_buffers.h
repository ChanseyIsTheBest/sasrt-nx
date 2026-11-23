/**
 * @file    gpu/guest/command_buffers.h
 * @brief   D3D command buffers: draws recorded on one device, run on another.
 *
 * N&B records parts of its frame on worker threads, each with its own device
 * between D3DDevice_BeginCommandBuffer and EndCommandBuffer, and runs the
 * buffers on the title device with D3DDevice_RunCommandBuffer. The hooked
 * draw, clear and resolve calls of a recording device are kept with a copy of
 * the device state they read, and replayed through the same draw path when
 * the buffer runs. The guest buffer still gets the originals' packets for the
 * calls that are not replaced; nothing reads them.
 *
 * Every buffer N&B records inherits the vertex and pixel shader float
 * constants: those it does not set itself come from the running device.
 *
 * The recorded buffers have a lock of their own, which these functions take;
 * none of them needs State().mutex. A run is queued for the render thread
 * with the buffers as they are at the call (a buffer recorded again later is
 * a new one), so the game may record the next frame's while it replays.
 */
#pragma once

#include <string>

#include <memory>  // sasrt-nx (2026-10-21): CaptureCommandBufferRun
#include <condition_variable>  // sasrt-nx (2026-11-08): SasrtRunSlot
#include <mutex>

#include <rex/types.h>

#include "renut_engine/gpu/render/draw.h"

namespace renut::gpu {

// True while the device records a command buffer.
bool IsRecordingCommandBuffer(u32 device_va);

// halo3-nx (2026-11-03, banjo_renut_recorded_binds; d3d/hooks/shader.cpp): a game thread, at a draw: the id of the
// D3DVertexShader_Bind its shader has now (0: none). The render thread, before that draw: the shader record takes it.
u32 LastBindingOf(u32 shader_va);
void ApplyBindingLocked(u32 id);

// After the original BeginCommandBuffer: drops what the buffer held before.
void BeginRecording(u32 device_va, u32 command_buffer_va);

// Records a draw on a recording device. 'up_vertex_bytes' / 'up_index_bytes'
// are the sizes of call.up_vertices / call.up_indices, copied now, as the GPU
// copies them into the buffer.
void RecordDraw(u32 device_va, const DrawCall &call, u32 up_vertex_bytes, u32 up_index_bytes);

// Records a Begin*Vertices draw whose 'bytes' of vertex data the game writes
// to 'scratch' after the call; copied at the device's next hooked call.
void RecordDeferredDraw(u32 device_va, const DrawCall &call, const u8 *scratch, u32 bytes);

void RecordClear(u32 device_va, u32 flags, const ClearRect *rect, const float color[4],
                 float depth, u32 stencil);

void RecordResolve(u32 device_va, u32 flags, const ClearRect *source_rect, u32 dest_texture_va,
                   i32 dest_x, i32 dest_y, u32 dest_level, u32 dest_slice,
                   const float clear_color[4], float clear_depth, u32 clear_stencil);

// D3DDevice_RunCommandBuffer on a recording device: records the run.
void RecordRun(u32 device_va, u32 command_buffer_va);
// banjo-nx (2026-10-26, banjo_renut_diag_fast_census): replayed recordings against the frame before's; empty when none.
// (2026-10-29: its own name; it shared render/draw.h's, one definition of the two was linked.)
std::string ReplayRepeatCensusReport();
// banjo-nx (2026-10-28, banjo_renut_diag_packet_census): replayed draws a whole-state keyed cache would answer.
std::string PacketCensusReport();
std::string StateSourceReport();  // banjo-nx (2026-10-26, banjo_renut_diag_fast_census)

// Copies the data of the device's recorded Begin*Vertices draw, if any. Any
// thread, with or without State().mutex.
void FlushRecordedVertices(u32 device_va);

// D3DDevice_RunCommandBuffer on a device that is not recording: queues the
// buffer's replay on it, with the device's state now (the constants the
// buffer inherits).
void QueueRunCommandBuffer(u32 device_va, u32 command_buffer_va);

// sasrt-nx (2026-10-21): a buffer's recording (and those it runs) as it is now, for a run queued later
// (QueueCapturedRun): what a composed command buffer's splice points at (sasrt_renut_hooks.cpp).
struct CapturedRun;
std::shared_ptr<CapturedRun> CaptureCommandBufferRun(u32 command_buffer_va);
// QueueRunCommandBuffer with the recording captured before (null: as it is now).
void QueueCapturedRun(u32 device_va, u32 command_buffer_va, std::shared_ptr<CapturedRun> captured);
// sasrt-nx (2026-11-04, sasrt_renut_splice_ended): the buffer a device records now (0: none); a recording marked
// ended by the game's EndCommandBuffer; a buffer's recording captured only once ended and not taken before
// (state: 0 taken, 1 still being recorded, 2 taken before and not recorded again, 3 none).
u32 RecordingCommandBuffer(u32 device_va);
void MarkRecordingEnded(u32 command_buffer_va);
std::shared_ptr<CapturedRun> CaptureIfEndedRun(u32 command_buffer_va, int *state);
// sasrt-nx (2026-11-04, sasrt_renut_diag_splice_pm4): c<first_reg>.. of the run's buffer as its first draw recorded them.
bool CapturedRunVertexConstants(const CapturedRun &run, u32 command_buffer_va, u32 first_reg, u32 count, u32 *out);
// sasrt-nx (2026-11-08, sasrt_renut_scene_same_frame): a captured run queued before its recording exists. The
// render thread, at the run's place, waits for the slot to be filled (the recording spliced after the
// submission) up to a timeout, then replays it, or the fallback (the recording the submission named).
struct SasrtRunSlot {
  std::mutex mutex;
  std::condition_variable cv;
  bool filled = false;
  u32 buffer = 0;
  std::shared_ptr<CapturedRun> recording;
  u32 fallback_buffer = 0;
  std::shared_ptr<CapturedRun> fallback;
};
void QueueCapturedRunSlot(u32 device_va, std::shared_ptr<SasrtRunSlot> slot, uint32_t timeout_ms);
void FillCapturedRunSlot(SasrtRunSlot &slot, u32 buffer, std::shared_ptr<CapturedRun> recording);
// The slots' counts since the last call: filled in time, fallen back, the longest wait (us).
void SasrtRunSlotCounts(uint64_t &filled, uint64_t &fallbacks, uint64_t &longest_wait_us);
// sasrt-nx (2026-11-08, sasrt_renut_diag_trace): the same for the first draw whose registers satisfy 'match' (the
// device image's big-endian words).
bool CapturedRunFindVertexConstants(const CapturedRun &run, u32 command_buffer_va, u32 first_reg, u32 count,
                                    bool (*match)(const u32 *), u32 *out);
// sasrt-nx (2026-11-04, replay tags): the recording being replayed on the render thread (set before each run's
// Replay; the resolves copy it into their destinations: HostTexture::sasrt_tag_*).
struct SasrtReplayTag {
  u32 buffer = 0;
  uint64_t recording = 0, begun = 0, ended = 0, submitted = 0;
};
extern SasrtReplayTag g_sasrt_replay_tag;

// sasrt-nx (2026-10-21, sasrt_renut_capture_recorded_streams): the vertex streams of the run being replayed as they
// were at its submission, by GPU address (GetStreamSource reads these instead of guest memory); nullptr outside.
// 'data' spans the stream's 'size' bytes, of which only the vertices the run's draws read at 'stride' are filled
// (stride 0: all of them).
struct SasrtStreamCopy {
  std::unique_ptr<u8[]> data;
  u32 size = 0, stride = 0;
};
using SasrtStreamCopies = std::unordered_map<u32, SasrtStreamCopy>;
extern const SasrtStreamCopies *g_sasrt_stream_copies;
// After a flush converted the fills that point into the copies (FlushVertexFillsLocked).
void SasrtReleaseStreamCopies();

void ReleaseCommandBuffer(u32 command_buffer_va);

// banjo-nx (2026-10-28, the heap): the spare buffers given back while the heap's room is below 256 MB (checked every
// 5 s; the frame's hook calls it).
void ReleaseSpareBuffersWhenHeapShort();
// banjo-nx (2026-10-28, the console's OOM): the spare buffers given back now (plume's memory pressure callback: a GPU
// memory block found no room in the heap). Any thread; takes only the spares' own lock.
void ReleaseSpareBuffersNow();

// For the memory report: the capacity of the recordings the game's command
// buffers hold now, and of the spare recordings kept for reuse; 'live'
// counts every recording, including older ones queued runs still hold.
struct CommandBufferMemory {
  size_t recorded_bytes = 0;
  size_t recorded = 0;
  // sasrt-nx (2026-11-09 night): the ended recordings' bytes in use and their capacity (the others are being written)
  size_t ended_used = 0, ended_capacity = 0;
  size_t spare_bytes = 0;
  size_t spare = 0;
  size_t live = 0;
};
CommandBufferMemory CommandBufferMemoryUsage();

// banjo-nx (2026-10-26, banjo_renut_tags): the 10 s "[renut] recording from marks" line (empty with nothing recorded);
// resets its counts.
std::string TagsReport();
// banjo-nx (2026-10-27, banjo_renut_shadow_sort): the 10 s "[renut] shadow sort" line; resets its counts.
std::string ShadowSortReport();
// banjo-nx (2026-10-27, banjo_renut_shadow_sort): a shader object's content hash and whether its draws may be reordered
// (draw.h ShaderSortableByHash), where it is made; any thread.
void NoteShaderSortKey(u32 va, uint64_t hash, bool sortable);

// sasrt-nx (2026-10-21, sasrt_renut_constant_f4_pending): for a game's D3DDevice_BeginShaderConstantF4 hook, after the original
// succeeded: the range's float constant groups pending again on the device, so a recorded draw takes them from it.
void KeepConstantF4Pending(u32 device_va, bool pixel, u32 start, u32 count);

} // namespace renut::gpu
