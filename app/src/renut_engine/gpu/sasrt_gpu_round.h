#pragma once
// sasrt-nx (2026-11-08): the GPU round after the move to the ultimate base (docs/gpu-round-1108.md). Pixel-identical GPU
// optimisations, each with its own key (on by default), an in-run A/B target (banjo_renut_ab_target = 90 + its number:
// its "off" half runs without it) and a count in the 10 s "[sasrt gpu]" line.
#include <atomic>
#include <cstdint>
#include <string>

#include "renut_engine/gpu/banjo_renut_tuning.h"

namespace sasrt::gpu_round {

// X(name, key, what it does): the items in order; the A/B target of item i is 90 + i.
#define SASRT_GPU_ROUND_ITEMS(X)                                                                                         \
  X(kInertDraws, sasrt_gpu_skip_inert_draws, "draws that write nothing skipped before their targets are bound")      \
  X(kPreciseDepth, sasrt_gpu_precise_depth_resolve, "depth decompressed only when written since its last decompression") \
  X(kPlainFetches, sasrt_gpu_plain_fetches, "pixel shaders without the sign / gamma / exponent code of plain fetches") \
  X(kAlphaSpec, sasrt_gpu_alpha_spec, "the alpha test's function in the pipeline: no discard without the test")         \
  X(kGammaOnce, sasrt_gpu_gamma_upload_once, "the game's gamma ramp copied to its texture only when it changes")       \
  X(kDecompressMerge, sasrt_gpu_decompress_merge, "the barrier after a depth decompression merged with the pending one") \
  X(kReadbackMerge, sasrt_gpu_readback_barrier_merge, "a readback's full barriers merged with those next to them")    \
  X(kFetchCopyCompute, sasrt_gpu_fetch_copy_compute, "memexport seeds and fetch data copied by the 3D engine's compute") \
  X(kDataInvalidate, sasrt_gpu_data_cache_invalidate, "buffer barriers drop the shaders' data caches, not their code") \
  X(kOneX, sasrt_gpu_one_x, "a draw at 1x: the texture scale codes and the pixel position's scale folded")        \
  X(kFaceSign, sasrt_gpu_face_sign, "the face register's sign test without its reciprocal")                         \
  X(kReadbackCompute, sasrt_gpu_readback_compute, "the memexport readbacks copied by the 3D engine's compute")      \
  X(kTiledCache, sasrt_gpu_tiled_cache, "Maxwell's tiled caching (binning) on (off by default: the console's to judge)") \
  X(kTexelReadback, sasrt_gpu_texel_readback_compute, "the 1x1 luminance read back for the CPU by the 3D engine's compute") \
  X(kLazyDepth, sasrt_gpu_lazy_depth_resolve, "depth decompressed right before a read, not at each unbind (off by default)") \
  /* the second round (2026-11-08, docs/gpu-round-1108.md "Round 2"): A/B 105 and up */                                 \
  X(kSeedLead, sasrt_gpu_seed_no_lead_wait, "memexport seeds into fresh windows without a wait for the 3D engine first") \
  X(kConvertLead, sasrt_gpu_convert_lead_wait, "an exported stream conversion without its wait when no export was drawn since one") \
  X(kIdentityRamp, sasrt_gpu_identity_ramp, "the scan-out's gamma ramp not looked up when it is the identity at 8 bits") \
  X(kConvertMemoKeep, sasrt_gpu_convert_memo_keep, "exported stream conversions kept for later draws across new exports") \
  X(kDepthFloatPs, sasrt_gpu_depth_resolve_float_ps, "a depth resolve without words by a shader that computes the float alone") \
  X(kSameTargets, sasrt_gpu_same_targets_kept, "the targets bound already not bound again after a dispatch or resolve") \
  X(kReadbackSpans, sasrt_gpu_readback_spans, "the memexport readback's windows that follow one another copied by one dispatch") \
  X(kSeedWaitOnly, sasrt_gpu_seed_wait_only, "the wait after the seeds keeps the texture, data and constant caches") \
  X(kFenceFlush, sasrt_gpu_readback_fence_flush, "the compute readbacks without an L2 flush of their own (the slot's fence flushes it)") \
  X(kConvertTail, sasrt_gpu_convert_tail_vertex_only, "the wait after a stream conversion keeps the shaders' data and constant caches") \
  X(kConvertLeadData, sasrt_gpu_convert_lead_data_only, "the wait before a stream conversion drops the global-data cache alone") \
  X(kClipSpec, sasrt_gpu_clip_spec, "vertex shaders without the user clip distance where no plane is set, the clip slot off") \
  X(kLeanSkip, sasrt_gpu_lean_barrier_skip, "a move into a target layout with nothing to wait for is not a barrier") \
  X(kReadbackTrim, sasrt_gpu_readback_barriers_trim, "the memexport readback's waits: the data cache alone first, none after") \
  X(kExportDiscard, sasrt_gpu_export_raster_discard, "export-only draws with the rasterizer off, not only an empty scissor") \
  /* the third round (2026-11-08, docs/gpu-round-1108.md "Round 3"): A/B 120 and up */                                 \
  X(kSeedCpu, sasrt_gpu_seed_cpu_direct, "memexport seeds written into their windows by the CPU: no copy dispatch, no wait") \
  X(kConvertTailNoImage, sasrt_gpu_convert_tail_no_texture_drop, "the wait after a stream conversion keeps the texture cache too") \
  X(kVsInputMask, sasrt_gpu_vs_input_mask, "vertex attributes the bound vertex shader variant never reads are not fetched") \
  X(kExportNoPs, sasrt_gpu_export_no_pixel_shader, "export-only draws (rasterizer off) built without their pixel shader") \
  X(kVsScreenSpec, sasrt_gpu_vs_screen_space_spec, "the vertex shaders' screen-space branch as a constant of the draw") \
  X(kVsRemapSpec, sasrt_gpu_vs_depth_remap_spec, "the vertex shaders' depth remap branch as a constant of the draw") \
  X(kStackSpec, sasrt_gpu_stacked_3d_spec, "a 3D fetch's stacked-or-volume choice as a constant of the draw") \
  X(kStackFilterSpec, sasrt_gpu_stacked_filter_spec, "a stacked fetch's layer filter and wrap as constants of the draw") \
  X(kFetchEndianSpec, sasrt_gpu_fetch_endian_spec, "a vertex shader's memory fetches' byte order as constants of the draw") \
  X(kGprCap, sasrt_gpu_gpr_cap, "three pixel shaders just over 32 registers compiled with 32 (a register or two spilled)") \
  X(kGprCapFilter, sasrt_gpu_gpr_cap_filter, "the 60-register filter pass 9041AFF6 compiled with 32 (full occupancy, spills)") \
  X(kExportFmtSpec, sasrt_gpu_export_format_spec, "a memexport's format word as a constant of the draw: its one pack compiled") \
  X(kTexDropTracked, sasrt_gpu_texture_drop_tracked, "a texture made readable drops the texture cache only if it was sampled since the last drop") \
  X(kTargetWaitTracked, sasrt_gpu_target_wait_tracked, "a texture made a target waits only if it was sampled or copied since the last wait") \
  X(kReadWaitTracked, sasrt_gpu_read_wait_tracked, "a texture made readable waits only if it was written since the last wait (or drops the cache)") \
  /* the fourth round (2026-11-08, night: the 33 ms goal; docs/gpu-round-1108.md "Round 4"): A/B 135 and up */          \
  X(kHandoverSmaa, sasrt_gpu_handover_with_smaa, "banjo's colour hand-over kept on with SMAA (SMAA's target settled first)") \
  X(kExportWindowUbo, sasrt_gpu_export_window_ubo, "memexport windows read from the constant buffer, not a local array (constant 944)") \
  X(kExportListTopology, sasrt_gpu_export_list_topology, "export draws with the rasterizer off drawn as triangle or line lists, not points") \
  X(kExportNoPointGs, sasrt_gpu_export_no_point_gs, "export point lists with the rasterizer off drawn without the point-sprite geometry shader") \
  /* the fifth round (2026-11-09: A393B1E0, docs/gpu-round-1108.md "Round 5"): A/B 139 and up */                         \
  X(kRestoreDirect, sasrt_gpu_depth_restore_direct, "the EDRAM depth restore drawn from the depth resolve, its colour copy left out") \
  X(kRestoreClear, sasrt_gpu_depth_restore_whole_clear, "the depth restore clears depth and stencil together when it draws the whole target") \
  X(kFetchConvSpec, sasrt_gpu_fetch_conversion_spec, "a non-plain fetch's sign, gamma and exponent words as constants of the draw (950-957)") \
  X(kFetchExpSpec, sasrt_gpu_fetch_exp_3d_spec, "a 3D or cube fetch's exponent adjust as a constant of the draw (958-973)") \
  X(kConvertVertexPass, sasrt_gpu_convert_vertex_pass, "exported stream conversions drawn as a vertex pass on the 3D engine, not dispatched") \
  /* pixel-changing cuts (2026-11-09, the user: "non-pixel identical GPU cuts as well, I'll determine what stays"): off */ \
  X(kCutDepthAlias, sasrt_gpu_cut_depth_alias, "CHANGES PIXELS: the light and composite passes test against the G-buffer's own depth, no restore") \
  X(kCutCopyDrop, sasrt_gpu_cut_restore_copy_drop, "CHANGES PIXELS (where the G-buffer leaves pixels): a restore copy left out is never drawn") \
  X(kCutMipNearest, sasrt_gpu_cut_mip_nearest, "CHANGES PIXELS: the game's trilinear textures sampled bilinear (the nearer mip level)") \
  X(kCutLodBias, sasrt_gpu_cut_lod_bias, "CHANGES PIXELS: the game's mipmapped textures sampled half a level smaller") \
  X(kCutShadowScale, sasrt_gpu_cut_shadow_two_thirds, "CHANGES PIXELS: the shadow maps at two thirds of their size (made so: no in-run A/B)") \
  X(kShadowUncompressed, sasrt_gpu_shadow_uncompressed, "shadow-map depth targets without hardware compression: no decompression before their resolves (made so: no in-run A/B)") \
  X(kRestoreReuse, sasrt_gpu_depth_restore_reuse, "a depth restore of the same resolve as an earlier one, whose depth is unchanged: that target, its stencil cleared") \
  X(kCutTakeOnOverwrite, sasrt_gpu_cut_take_on_overwrite, "CHANGES PIXELS if a post pass leaves a pixel: a handed resolve keeps the image a full-screen post draw overwrites") \
  X(kCutGatherPcf, sasrt_gpu_cut_gather_pcf, "MAY CHANGE PIXELS at texel edges: four point taps half a texel around one place read by one gather (976)") \
  X(kRestoreClearSkip, sasrt_gpu_depth_restore_clear_skip, "the direct depth restore clears to the scene's clear depth and leaves the pixels at it as cleared") \
  X(kCutSsaoOff, sasrt_gpu_cut_ssao_off, "CHANGES PIXELS: no ambient occlusion: the SSAO pass's draw is a clear to white (no occlusion)") \
  X(kCutPcfHalf, sasrt_gpu_cut_pcf_half, "CHANGES PIXELS: the scene's shadow filter (9041AFF6) averages 4 of its 8 bilinear PCF places (977)") \
  X(kCutNoAa, sasrt_gpu_cut_no_aa, "CHANGES PIXELS: no anti-aliasing: SMAA not run (the game's FXAA pass stays its centre sample)") \
  X(kCutShadowAlphaCasters, sasrt_gpu_cut_shadow_alpha_casters, "CHANGES PIXELS: the shadow maps' alpha-tested casters (3ECDED03: foliage, fences) not drawn") \
  X(kShadowD32f, sasrt_gpu_shadow_d32f, "shadow-map depth targets as D32F (no stencil plane: the casters use none): half the bytes") \
  X(kSkipCopyBack, sasrt_gpu_skip_copy_back, "a post copy of a resolve back into the same unchanged target it came from is not drawn") \
  X(kCutFarCascade, sasrt_gpu_cut_far_cascade, "CHANGES PIXELS: the far shadow cascade's casters not drawn (no shadows in its range)") \
  X(kCutFarCascadeHalf, sasrt_gpu_cut_far_cascade_half_rate, "CHANGES PIXELS: the far shadow cascade drawn every other frame (the atlas keeps the last one)") \
  X(kCutBloomOff, sasrt_gpu_cut_bloom_off, "CHANGES PIXELS: no bloom: the bloom chain's passes are clears to black") \
  X(kCutSmaaLow, sasrt_gpu_cut_smaa_low, "CHANGES PIXELS: SMAA's low preset edge threshold (0.15 instead of 0.1): fewer edges smoothed") \
  X(kCutSsaoHalfRate, sasrt_gpu_cut_ssao_half_rate, "CHANGES PIXELS: SSAO and its blur every other frame (the composite reads the last result)") \
  X(kCutShadowsOff, sasrt_gpu_cut_shadows_off, "CHANGES PIXELS: no shadows: no caster drawn into any shadow map (the maps stay cleared: lit)") \
  X(kCutPointLightsOff, sasrt_gpu_cut_point_lights_off, "CHANGES PIXELS: no point lights: the light pass's draws after the sun's (their stencil volumes too) not drawn") \
  X(kShadowAtlasDirect, sasrt_gpu_shadow_atlas_direct, "the shadow cascades drawn straight into their slices of the atlas (D32F images over its memory): no resolve copies") \
  X(kCutAmbientSky, sasrt_gpu_cut_ambient_sky, "CHANGES PIXELS (the sky, unless a later pass replaces it): the additive ambient pass ED0A8D53 not shaded where the restored depth is the clear (depth bounds)") \
  /* the render-thread round (2026-11-09, the user: "15 or so render thread optimisations"; docs/render-thread-round-1109.md): A/B 169 and up */ \
  X(kRtRestoreCandidates, sasrt_rt_restore_candidates, "render thread: a depth target's EDRAM-restore source found among its own few candidate colour targets, kept until a target is built or retired, not by two scans of every target a draw") \
  X(kRtWordsOwnerMemo, sasrt_rt_words_owner_memo, "render thread: the texture owning a depth-words view slot (the restore copy's) remembered and checked, not found by a scan of every texture") \
  X(kRtViewSurfaceMemo, sasrt_rt_view_surface_memo, "render thread: a replayed op's colour EDRAM view looked up through the surface memo too (keyed by its view words), not by the slow lookup every time") \
  X(kRtCachedExportSeeds, sasrt_rt_cached_export_seeds, "render thread: the memexport windows' buffer CPU-cached, so the CPU writes the seeds at cache speed and cleans their lines (chosen at start: no in-run A/B)") \
  /* the second render-thread round (2026-11-20, the user: "35 ideas ... to make the render thread cheaper"; docs/render-thread-ideas-1120.md): A/B 339 and up, all at once 401 */ \
  X(kRt2SlotIndex, sasrt_rt2_slot_index, "render thread: FindHostTextureBySlotLocked's memo a 256-entry table by slot (each answer checked as before), not one entry") \
  X(kRt2SpecMemo, sasrt_rt2_spec_memo, "render thread: a fast draw's fetch-spec, plain-fetch, clip and spec words kept from the draw before when no shared-constant line, shader, target or A/B half changed") \
  X(kRt2DropThrottle, sasrt_rt2_drop_throttle, "render thread: DropReplacedRanges' pass over the stream cache's limit every 4th frame, not every frame (memory only)") \
  X(kRt2PagesTail, sasrt_rt2_pages_tail, "render thread: PagesClean's last 1-7 pages of a range in one masked NEON block when none of their cards is written") \
  X(kRt2ColorAliasMemo, sasrt_rt2_color_alias_memo, "render thread: ColorAliasesLocked's answer kept per surface until a target is made or retired") \
  X(kRt2RepeatRecordedIndex, sasrt_rt2_repeat_recorded_index, "render thread: WholeRepeatHit reads the replay's recorded index buffer, as WholeGeometryTry does (a correctness fix too)") \
  X(kRt2HeldExportBitmap, sasrt_rt2_held_export_bitmap, "render thread: GetStreamSource looks up the kept exports only where a 64 KB granule bitmap says one may lie") \
  X(kRt2PlaceWaitFree, sasrt_rt2_place_wait_unlocked, "render thread: a same-frame place's wait without State().mutex held (spin, then a timed wait)") \
  X(kRt2RingPrefetch, sasrt_rt2_ring_prefetch, "render thread: the next ring item's narrowed device delta prefetched to six lines, not four") \
  X(kRt2ReadableMemo, sasrt_rt2_readable_memo, "render thread: the vertex fills' guest readability answers kept while no page has lost read access (no heap mutex, no page walk)") \
  X(kRt2BindLayoutNarrow, sasrt_rt2_bind_layout_narrow, "render thread: a layout change elsewhere binds the fast draw's targets again only when its own targets are not in their bind layouts") \
  X(kRt2TextureMemoTwoWay, sasrt_rt2_texture_memo_two_way, "render thread: the texture slot memo two-way (2,048 sets of two), the way of an earlier frame replaced") \
  X(kRt2RepeatRing, sasrt_rt2_repeat_ring, "render thread: WholeGeometryTry's repeat answer kept for the last four meshes of a kick, not one") \
  /* the third render-thread round (2026-11-20, the user: "Come up with 35 more ... Do a 35 batch"; docs/render-thread-ideas-1120.md): all at once 402 */ \
  X(kRt3WordsOwnerTable, sasrt_rt3_words_owner_table, "render thread: the depth-words view owner a 256-entry table by slot, not one entry") \
  X(kRt3SurfaceMemo256, sasrt_rt3_surface_memo_256, "render thread: GetHostSurfaceLocked's memo 256 entries, not 64") \
  X(kRt3DepthBiasFields, sasrt_rt3_depth_bias_fields, "render thread: the fast draw's depth bias not set again when its packets are unchanged since the draw before") \
  X(kRt3PlaceSpin, sasrt_rt3_place_spin, "render thread: a same-frame place's wait spins on the slot's flag first (sasrt_rt3_place_spin_us), then sleeps") \
  X(kRt3HostPacketsSplit, sasrt_rt3_host_packets_split, "render thread: host packets (banjo_renut_host_packets) while the screen is split, whatever the key") \
  /* the fourth render-thread round (2026-11-20, the user: "do these please and then do a massive ab of render thread stuff"; the third table's items left; docs/render-thread-ideas-1120.md): all at once 403 */ \
  X(kRt4PushRunsMerged, sasrt_rt4_push_runs_merged, "render thread: two runs of pushed constant groups with one or two groups between them pushed as one run (the gap's current device bytes too; never over a literal register)") \
  X(kRt4StateIdCrc, sasrt_rt4_state_id_crc, "render thread: RenderStateIdLocked's table index by CRC32C of the words (14 crc32cx), not 27 dependent multiplies") \
  X(kRt4PipelineFourWay, sasrt_rt4_pipeline_four_way, "render thread: the fast pipeline cache four-way (the index's aligned group of four), not two") \
  X(kRt4SpecKeySkip, sasrt_rt4_spec_key_skip, "render thread: a fast draw with the spec memo's answers skips comparing them with the kept key when it was checked against them and no key was written since") \
  X(kRt4StreamMemoTwoWay, sasrt_rt4_stream_memo_two_way, "render thread: the stream and index caches' memos two-way (a slot and its pair, the most recent first), not direct-mapped") \
  X(kRt4RingLockOnce, sasrt_rt4_ring_lock_once, "render thread: State().mutex kept from one draw item into the next published draw item (at most 8 in a row), not taken and let go at each") \
  X(kRt4InertKeepsChain, sasrt_rt4_inert_keeps_chain, "render thread: a draw left out as inert or culled both ways keeps the fast path's chain (its changed fields carried into the next draw)") \
  X(kRt4ExportReadsFast, sasrt_rt4_export_reads_fast, "render thread: a draw whose only memexport reads are host-layout vertex streams found on the GPU stays on the fast path (the streams converted there as the full path does)")

#define SASRT_GPU_ROUND_RT2_FIRST kRt2SlotIndex
#define SASRT_GPU_ROUND_RT3_FIRST kRt3WordsOwnerTable
#define SASRT_GPU_ROUND_RT4_FIRST kRt4PushRunsMerged

enum Item : int {
#define SASRT_GPU_ROUND_ENUM(name, key, what) name,
  SASRT_GPU_ROUND_ITEMS(SASRT_GPU_ROUND_ENUM)
#undef SASRT_GPU_ROUND_ENUM
  kCount
};

// sasrt-nx (2026-11-19, base port 188): this port's own A/B numbers are 256 and up (the base keeps 1-255 and
// never takes a number from 256 on); 90-172 before, which met the base's 150-156 and its 240.
constexpr int kAbBase = 256;
// sasrt-nx (2026-11-09, the render-thread round): A/B target 200 switches every render-thread item (from
// kRtRestoreCandidates on) at once: the round's total, with banjo_renut_ab_s 30 (the user's 30 s halves).
constexpr int kAbRtGroup = 400;  // 200 before 2026-11-19 (port 188)
// sasrt-nx (2026-11-20): A/B target 401 switches the second render-thread round's items (from kRt2SlotIndex on) at once.
constexpr int kAbRt2Group = 401;
// sasrt-nx (2026-11-20): A/B target 402 switches the third render-thread round's items (from SASRT_GPU_ROUND_RT3_FIRST on).
constexpr int kAbRt3Group = 402;
// sasrt-nx (2026-11-20): A/B target 403 switches the fourth render-thread round's items (from SASRT_GPU_ROUND_RT4_FIRST on).
constexpr int kAbRt4Group = 403;
static_assert(kCount <= 128, "plume's Deko3DStats::sasrtRound has 128 counts");
static_assert(kAbBase + kCount <= kAbRtGroup && kAbRt4Group < 512, "banjo_renut_ab_targets takes targets up to 511");

struct Latched {
  bool on[kCount] = {};
};
extern Latched g_latched;
extern std::atomic<bool> g_latched_ready;
void LatchNow();

// The item's key as latched at the first use (the toml is final by then), and not in its A/B "off" half.
// sasrt-nx (2026-11-12, batch D3): the flag read relaxed, as banjo's Latch(): no load-acquire at each switch a draw
// passes (it kept the A57 from starting the draw's later loads early); the values come from the configuration only.
// banjo-nx (2026-11-20, N&B's render thread against renut-nx 1.0.2 in Showdown Town): each item's answer kept in one
// byte (0 not latched yet, 1 off, 2 on: zero-initialised means unlatched), set by LatchNow and again by
// RefreshEffective at each A/B switch (AbApply).
// On() is that one load: before, every call read the latch flag and the A/B half (two atomics) and the latched key,
// FastDrawLocked asks dozens of times a draw, and those loads were 0.13 us of the 9.2 us a draw (1 ms sampling).
// banjo-nx (2026-11-21): plain bytes (relaxed atomics before: loads the compiler could not merge), written at the latch
// and at each A/B switch (the render thread), as g_ab_off_plain.
extern uint8_t g_effective[kCount];
void RefreshEffective();  // the answers again from the latched keys and banjo::renut_gpu::g_ab_off
[[gnu::always_inline]] inline bool On(Item i) {
  uint8_t v = g_effective[i];
  if (v == 0) [[unlikely]] {
    LatchNow();
    v = g_effective[i];
  }
  return v == 2;
}

// Counts for the 10 s line: a load and a store (no read-modify-write on the A57; a count lost between two threads is a
// diagnostic's error, not the renderer's).
extern std::atomic<uint64_t> g_counts[kCount][2];
[[gnu::always_inline]] inline void Count(Item i, uint64_t n = 1, int which = 0) {
  if (!banjo::renut_gpu::Latch().counts)  // banjo-nx (2026-11-20): off with the logs (banjo_renut_draw_counts)
    return;
  std::atomic<uint64_t> &c = g_counts[i][which];
  c.store(c.load(std::memory_order_relaxed) + n, std::memory_order_relaxed);
}

const char *AbName(int target);  // nullptr: not one of these
// The items that live in plume's deko3d back end, set from the keys and the A/B half (at start-up and at each A/B
// switch, on the render thread).
void ApplyPlume();
// sasrt-nx (2026-11-09, the cuts 56-57): bit 0 kCutMipNearest, bit 1 kCutLodBias, as the A/B half has them now.
uint32_t SamplerCutBits();
std::string Report();            // the 10 s line's text (and the counts start again)

}  // namespace sasrt::gpu_round
