/**
 * @file    gpu/backend/queued.h
 * @brief   The game thread's side of draws, clears and resolves on a device
 *          that is not recording a command buffer.
 *
 * Each call captures what the render thread will need and the game may change
 * once the call returns (a snapshot of the device state, the data of Draw*UP
 * calls) and queues the work (render_thread.h). A Begin*Vertices draw waits for
 * its vertices, which the game writes after the call, until the device's next
 * D3D call (FlushDeferredVertices) before it is queued. These are called on
 * the game's threads without State().mutex.
 */
#pragma once

#include <string>

#include <rex/types.h>

#include "renut_engine/gpu/render/draw.h"

namespace renut::gpu {

// sa2-nx (2026-10-20, banjo_renut_snapshot_deltas: queued.cpp): a draw keeps only what changed in the device since the
// previous one. At each Swap: the frame's first draw keeps the whole device again.
// sasrt-nx (2026-10-21, sasrt_renut_diag_late_streams): up to four bound vertex streams of a draw, hashed at the call.
struct SasrtStreamHashes {
  u32 count = 0;
  u32 va[4] = {}, size[4] = {}, stream[4] = {};
  uint64_t hash[4] = {};
  u32 stride[4] = {};  // sasrt_renut_capture_recorded_streams: SetStreamSource's stride (0: none given)
};
bool SasrtLateStreamsOn();
void SasrtHashStreams(const u8 *device_bytes, SasrtStreamHashes &out);
void SasrtCheckStreams(const SasrtStreamHashes &in, bool recorded);
// The draw being replayed: its streams' hashes at the call (nullptr without), and whether a recorded buffer's.
extern const SasrtStreamHashes *g_sasrt_draw_streams;
extern bool g_sasrt_draw_recorded;
// At a kick on the game thread: the streams noted since the last kick hashed, for the render thread's flush.
void SasrtQueueKickHashes();
// At the conversion: the stream compared with its hash at the kick (when one was taken); after the flush, forgotten.
void SasrtCheckKick(u32 va, u32 size);
void SasrtClearKickHashes();
// A range for the next SasrtQueueKickHashes (any thread).
void SasrtNoteKickRange(u32 va, u32 size);
// At the replay: the index bytes the draw reads, compared with the game's at its kick when those arrive.
void SasrtNoteReplayIndices(u32 address, const u8 *data, u32 size);

void SnapshotDeltasNewFrame();
// Something else consumed the dirty masks of 'device' (a command buffer's op): when it is the chain's device, the next
// draw keeps the whole device.
void ForgetSnapshotDeltas(const void *device);
// The 10 s "[renut] device snapshots" line (empty with the deltas off); resets its counts.
std::string SnapshotDeltaReport();

// 'up_vertex_bytes' / 'up_index_bytes': the sizes of call.up_vertices /
// call.up_indices, copied now.
void QueueDraw(u32 device_va, const DrawCall &call, u32 up_vertex_bytes, u32 up_index_bytes);

// A Begin*Vertices draw whose 'bytes' of vertices the game writes to 'scratch'
// after the call.
void QueueDeferredDraw(u32 device_va, const DrawCall &call, const u8 *scratch, u32 bytes);

// Queues the device's Begin*Vertices draw with its vertices as they are now,
// and copies those of one it recorded into a command buffer. Every hook calls
// this first for its device.
void FlushDeferredVertices(u32 device_va);

void QueueClear(u32 device_va, u32 flags, const ClearRect *rect, const float color[4], float depth,
                u32 stencil);

void QueueResolve(u32 device_va, u32 flags, const ClearRect *source_rect, u32 dest_texture_va,
                  i32 dest_x, i32 dest_y, u32 dest_level, u32 dest_slice,
                  const float clear_color[4], float clear_depth, u32 clear_stencil);

} // namespace renut::gpu
