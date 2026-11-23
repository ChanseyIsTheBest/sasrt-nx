#!/usr/bin/env python3
"""sasrt-nx (2026-10-21): the console tests of Renut's deko3d renderer for the visual faults seen only on the console
(the race's sky dropping out, green or in stretched triangles, the "ocean" frames, flashing models in the menus). Each
configuration is app/sasrt_switch.toml with only the keys its name says changed (none but sasrt_renut_alpha_spec changes a
shader, so no other shader is compiled on the console because of them):

  sasrt_renut_sync_frames.toml     sasrt_renut_diag_sync_frames: each frame waits for the GPU at its present. A fault
                                   this clears comes from GPU work of two frames overlapping or the CPU writing what
                                   the GPU still reads.
  sasrt_renut_no_frames_ahead.toml sasrt_renut_diag_no_frames_ahead: the game waits at its Swap until the render thread
                                   has replayed the frame. A fault this clears is a late read of guest memory. (06:45:
                                   on the PC it clears the race start's sky triangles and smeared car; slower, since
                                   the game and the render thread no longer overlap.)
  sasrt_renut_gpu_before.toml      banjo-nx's deko3d GPU work off (drawn resolves, depth compression, Zcull, merged and
                                   lean barriers, depth hand-over, pushed constants, the ring cleaner, kick submits).
  sasrt_renut_cpu_before.toml      sa2-nx's and banjo-nx's render-thread CPU work off (snapshot deltas and their chain,
                                   capture batches, fetch-data and fetch-slot skips, stream masks, prefetch, the shared
                                   constants' partial clear, the texture defaults copy).
  sasrt_renut_kicks_off.toml       the frame goes to the GPU whole at its present (no kick or eager submits).
  sasrt_renut_barriers_full.toml   every barrier as recorded, each with every cache invalidation (no merge, not lean).
  sasrt_renut_depth_plain.toml     no Zcull, no depth compression, no depth hand-over.

Added 04:00-05:30 (the faults' cause found: the composed buffer pool's wrap; A/B of the night's changes):

  sasrt_renut_pool_wrap_off.toml   sasrt_renut_pool_wrap_run off: the fix of the "ocean" frames and the menus'
                                   vanishing models undone (they come back every ~63 frames).
  sasrt_renut_expand_decoder.toml  sasrt_renut_vertex_expand_tables off: packed normals decoded one component at a
                                   time again (the CPU cost of the vertex expansion, before).
  sasrt_renut_signs_retire.toml    sasrt_renut_texture_keep_on_signs off: textures sampled with gamma and without
                                   retired and uploaded again at each switch (~217 uploads a frame, before).
  sasrt_renut_alpha_spec.toml      banjo_deko3d_alpha_spec on (banjo-nx's default; off in sa2-nx and here since it
                                   gave flat colours to SA2 in Ryujinx): draws without the alpha test lose their
                                   discard and test depth before shading. This one compiles shader variants on the
                                   console (uam, in the background, a few seconds of the generic shaders first).
  sasrt_renut_stream_cache_128.toml  the converted stream cache back at banjo-nx's 128 MB, without the eviction of
                                   copies not drawn lately (banjo_renut_stream_cache_pressure off; sasrt_renut_stream_cache_follow until 2026-10-29).
  sasrt_renut_stream_cache_384.toml  a bigger cache (384 MB): whether the console's render thread drops further.

Added 07:20 (the console run of 07:03 is GPU-bound: the render thread waits on GPU fences):

  sasrt_renut_gpu_profile.toml     renut_gpu_profile 10: every 10 s a "GPU profile" line, the GPU's time per frame
                                   by kind of work (draws per target, resolves, mip levels, present).
  sasrt_renut_gpu_shaders.toml     the same, with banjo_renut_diag_gpu_shaders: the passes split by pixel shader and
                                   blending, 60 lines (the timestamps cost a little GPU and render-thread time).

Added 11:45 (the octopus fix):

  sasrt_renut_baked_fetches_off.toml  sasrt_renut_baked_fetches off: the 16-bit vertex data of shaders Direct3D had
                                   already bound swapped back a second time (the race's octopus as spikes, before).
  sasrt_renut_exports_held_off.toml   sasrt_renut_exports_held off: skinned meshes read their positions from guest
                                   memory the game may have cleared (meshes collapsing to a point, before).

Added 13:00 (the console brighter than the PC after dark scenes; deko3d's shader passes, which the PC never runs):

  sasrt_renut_txq_verify.toml      banjo_deko3d_txq_verify: every pixel whose shader got a texture size from plume's
                                   size buffer that differs from the texture's own size is magenta (the downsample,
                                   bloom and exposure shaders read sizes; banjo-nx's txq pass).
  sasrt_renut_txq_query.toml       banjo_deko3d_txq_constants off: the shaders query the sizes again, as on the PC.
  sasrt_display_gamma_115.toml     sasrt_display_gamma 1.15: the midtones darker at scan-out (a less washed-out look;
                                   the frames match the emulated GPU's, whose look is the same). Set it in sasrt.toml
                                   to keep it.

Added 14:00 (the console's whole objects drawn in the wrong place for a few frames, a truss over the start line, the
triangles over the grid: neither the PC nor Ryujinx shows them):

  sasrt_renut_deko3d_plain.toml    every deko3d shader specialisation and uam compiler option of banjo-nx's off
                                   (output pruning, early depth, early hoist, value numbering, byte permutes, uniform
                                   branches, 128-bit bone rows, tessellation constant, texture size buffer): the
                                   shaders closer to the PC's. Shaders compile again on first use (stutters).
  sasrt_renut_store_cards_off.toml banjo_renut_store_cards off: cached vertex and index copies hashed at their first
                                   use after every kick, not proven by the store cards (the PC's check found none
                                   stale; the console runs other code).
  sasrt_renut_capture_streams.toml sasrt_renut_capture_recorded_streams: the workers' vertex streams (up to 2 MB each)
                                   copied when their command buffers are submitted, as MarathonRecomp-NX copies a
                                   buffer at its Unlock. Costly (about 20 MB a submission): a test only.

Added 16:30 (the user's runs: no_frames_ahead removed most explosions and ran the race at 30 fps; capture_streams and
store_cards_off made them worse, both costing render-thread time):

  sasrt_renut_frames_ahead_1.toml  sasrt_renut_frames_ahead 1: the game one frame ahead of the render thread again, as
                                   before (the console's toml has 0 since 16:30).

Added 18:30 (the race's flickering black ground and black driver, the same with the deko3d shader passes off: the
shadow maps were copied out of compressed depth targets, which the GPU's texture unit cannot read; the console's toml
has sasrt_deko3d_depth_resolve = true since):

  sasrt_deko3d_depth_resolve_off.toml   sasrt_deko3d_depth_resolve off: compressed depth read as it is (the fault back).
  sasrt_renut_depth_uncompressed.toml   banjo_deko3d_depth_compression off: depth targets without compression (nothing
                                        to decompress; the other cure, if the first is not enough; more GPU bandwidth).

Added 18:50 (the user's stock-clock run: the intro movie at 18 fps, the legal screen at 11 fps with the GPU idle):

  sasrt_movie_colour_native_off.toml     sasrt_cpu_native_sub_82e7f918 off: the movies' colour conversion as the
                                         recompiled original (the native's gain on the console).

Added 20:50 (the darks far too black on every renderer: the race's GI volumes read as normalized gave no ambient light;
sasrt_renut_texture_int_format on by default since):

  sasrt_renut_gi_normalized.toml         sasrt_renut_texture_int_format off: the GI volumes normalized again (black
                                         shadows, as the emulated GPU draws them).

The banjo-nx renderer sync (2026-10-29, docs/deko3d-renderer.md "Banjo sync 2026-10-29"), each piece off on its
own, to find the one behind a fault the console shows with it:

  sasrt_banjo_fast_draw_off.toml       banjo_renut_fast_draw off: every draw DrawStateLocked's (the fast path's
                                       re-done steps, this port's additions to them among them).
  sasrt_banjo_record_objects_off.toml  the record-time objects off (texture, stream and index objects, the
                                       slots' extents, the recording threads' lookups).
  sasrt_banjo_replay_stream_off.toml   banjo_renut_replay_stream off: no prefetching ahead in the replay.
  sasrt_banjo_fetch_cache_off.toml     banjo_renut_fetch_cache off: vertex-shader fetch data copied every kick.
  sasrt_banjo_gpu_region_off.toml      banjo_deko3d_gpu_region off: GPU memory from the heap as before.
  sasrt_banjo_async_variants_off.toml  banjo_deko3d_async_variants and _cache_reads off: a draw waits for
                                       its shader variant (no generic variant meanwhile).

Added 2026-10-29 evening (the far-cascade shadows gone in every other frame on the console only: the PC and Ryujinx
recordings do not alternate, and Ryujinx emulates neither hierarchical depth culling nor depth compression):

  sasrt_banjo_zcull_off.toml           banjo_deko3d_zcull off: no hierarchical depth culling (Zcull).
  (with sasrt_renut_depth_uncompressed.toml, depth compression off, and sasrt_renut_depth_plain.toml, both off and
  the depth hand-over too)

Added 2026-10-30 (newlogs6: depth compression off kept the flicker; Zcull off stopped the boot twice, most likely
plume's Zcull invalidate recorded without its if, fixed): the rest of what only the console's GPU does differently
from Ryujinx, all at once first, then one at a time:

  sasrt_flicker_all_safe.toml          every one below at once, with Zcull and depth compression off: the flicker
                                       still there means none of these is it.
  sasrt_renut_sync_frames.toml         (above) each frame waits for the GPU: two frames' GPU work never overlaps and
                                       the CPU never writes what the GPU still reads.
  sasrt_renut_barriers_full.toml       (above) barrier merging and the lean barriers off: every barrier drops the
                                       texture cache (Ryujinx has none to drop).
  sasrt_banjo_upload_uncached.toml     banjo_renut_upload_cached off: the upload ring write-combined, not CPU-cached
                                       and cleaned before each submit (Ryujinx has no CPU cache to clean).

And the new deko3d multisample keys, back to deko3d's defaults (the old behaviour):

  sasrt_deko3d_msaa_positions_off.toml sasrt_deko3d_msaa_positions off: every sample at the pixel's centre.
  sasrt_deko3d_a2c_dither_on.toml      sasrt_deko3d_a2c_dither on: the hardware's alpha-to-coverage dither grid.
  sasrt_deko3d_strip_restart_off.toml  sasrt_deko3d_strip_restart off: indexed strips without primitive restart.
  sasrt_renut_resolve_readback_off.toml sasrt_renut_resolve_readback off: the CPU reads 0 for the scene's
                                       luminance and every glow (Ristar at the race start) is 20x too dark.

Added 2026-10-30 afternoon (the flicker kept with the all-safe config):

  sasrt_renut_shadow_dump.toml         sasrt_renut_diag_shadow_dump "30,30,10,8,B5640E28,B5642E28,B5640B28": every 30 s
                                       from 30 to 300 s, eight frames of the shadow mask, the lit scene and the scene
                                       depth written to shadow_dump/ by a thread of their own (60 MB a window, 600 MB
                                       in all; tools/shadow_dump_view.py). The first version wrote every resolve from
                                       the render thread, a row a call, and hung the console after one frame.
  sasrt_renut_shadow_dump_atlas.toml   (2026-10-30 evening) sasrt_renut_diag_shadow_dump "30,30,8,8,B5640EA8,B5640E28":
                                       the shadow atlas (its three cascades) and the shadow mask of the same 8 frames,
                                       every 30 s from 30 to 240 s (116 MB a window, about 930 MB in all). Does a bad
                                       frame's mask come with a bad cascade? (The dump's copies after each cascade also
                                       order the GPU's work there: no bad frame at all would point at that.)
  sasrt_renut_depth_resolve_wait_idle.toml  (2026-10-30 night) after each depth resolve a wait for idle.
  sasrt_renut_depth_resolve_wait_full.toml  ... a full drain (2: did not end the flicker, the user's console).
  sasrt_renut_depth_resolve_wait_texel.toml ... a copy of one texel out of it (plume's readback copy and barriers).
  sasrt_renut_depth_resolve_wait_copy.toml  ... a copy of all of it: what the atlas dump did after each cascade.
  sasrt_deko3d_compression_off.toml    depth and colour targets both uncompressed (each alone kept the flicker).
  sasrt_renut_shadow_dump_late.toml    the A+B+X+Y dump also copies the shadow atlas whole after the shadow mask:
                                       the cascades as the shading read them (12 MB more a frame).
  sasrt_flicker_shaders_plain.toml     banjo-nx's shader compiler passes and specialisations off (uam's dropped
                                       reconvergence around branches it takes for uniform among them: real Maxwell
                                       relies on it, Ryujinx rebuilds the control flow its own way) and no draw
                                       with a generic variant while its own compiles (stutters at first).
  sasrt_flicker_submit_whole.toml      each frame to the GPU whole at the present (no kicks: the GPU never runs a
                                       frame's start while the CPU records the rest), no recording worker thread,
                                       no ring cleaner thread.
  sasrt_flicker_fix_all.toml           (2026-10-30, the user's request: as few tomls as possible) every candidate below
                                       not yet ruled out on the console at once: resolve wait 4, the read / write /
                                       clear waits, both compressions, Zcull, barrier merge and lean off, the
                                       shaders_plain, submit_whole and both caches groups; A+B+X+Y also copies the
                                       shadow atlas after the mask. Slow. If it ends the flicker:
  sasrt_flicker_fix_gpu.toml           ... its GPU half (all but the caches), and
  sasrt_flicker_fix_cpu.toml           ... its CPU half (the two caches groups).
  sasrt_flicker_bindings.toml          (2026-11-03) the fixes off as in sasrt.toml; in each A+B+X+Y window every
                                       light-volume draw is logged with its depth, stencil, clip and cull words, its
                                       alpha test and its texture slots as bound (descriptor index, sampler, host
                                       texture), and the atlas is copied after the mask. Pairs each dumped frame
                                       with what its shading draws were given.
  sasrt_strip_markers_off.toml         (2026-11-03) rr6-nx's fix of the range draw path off: an indexed strip's
                                       restart marker counts as vertex 65535 again (the strip runs on through its
                                       cuts on deko3d, triangles to the origin, the range converts the buffer's tail).
  sasrt_renut_resolve_target_pages_off.toml (2026-11-03) a resolve destination whose base page changed is retired and
                                       made again (every frame for the scene depth, the lit scene and the downsample
                                       chain, as before): the far-cascade shadow flicker's candidate off.
  sasrt_flicker_passes.toml            (2026-11-03, late) sasrt_flicker_bindings plus the shadow mask copied out after
                                       each ring's shading draw in the A+B+X+Y windows (files "pass", the draw's
                                       number as the address): which ring goes wrong, its shell or its shading.
  sasrt_direct_state_off.toml          (2026-11-04) the direct renderer off (sasrt_cpu_direct_state and _flush: per-draw
                                       state from host records instead of the PM4 ring), with the passes diagnostics.
  sasrt_direct_flush_off.toml          ... only its step 2 off (the state flush placeholders), the records kept.
  sasrt_me_native_plain.toml           ... the ring's CPU fast paths the Switch config turns on and the PC's does not
                                       (masseffect_native_pm4_fast, fast_pair, raw_microcode, flat_identity,
                                       compare_fast, fast_copy, indices_cache, the CRC fingerprint, the dedupe size).
  sasrt_clear_repeat_off.toml          ... a whole clear of a target already holding that clear sent after all
                                       (banjo_renut_clear_repeat): the cascade target's clear before each cascade.
  sasrt_splice_ended_off.toml          (2026-11-04, morning) the fix off: a composed buffer's splice takes a recorded
                                       buffer's recording as it is at the splice, ended or not (the previous frame's
                                       when the worker's shadow pass had not begun this frame's), with the passes
                                       diagnostics. On (sasrt.toml): only an ended recording, taken at its end.
  sasrt_deko3d_copy_wait_off.toml      (2026-11-04, morning) a texture leaving a copy layout moved with a fragment
                                       barrier again (no wait for the copy engine), as before.
  sasrt_flicker_pm4.toml               (2026-11-04, noon) the shadow casters' matrix (vertex c128-c131) read from the
                                       worker buffers' own PM4 at the splice and again at the ring submission, logged
                                       beside the recorded snapshot's values ("shadow caster" lines): does Direct3D
                                       patch the recorded packets after the worker recorded them? With the passes
                                       diagnostics; press A+B+X+Y when it flickers.
  sasrt_flicker_depth_writers.toml     (2026-11-08) the console's dumps of 2026-11-08 show every shading pass's cascade
                                       constants fitting the scene depth of the frame after the one it samples: which
                                       draws wrote that depth (the game thread's or a recording's, and when) and the
                                       order of the recordings' replays against the game thread's own draws ("seq:"
                                       lines). With the atlas copy, no per-pass copies (card space); A+B+X+Y in a race.
  sasrt_flicker_scene_pass.toml        (2026-11-08) the same diagnostics with only the mask dumped (20 MB a window):
                                       the worker's scene-pass draws' vertex constants, own or inherited from the
                                       title device ("scene pass:" lines), against the game thread's.
  sasrt_flicker_ahead1.toml            (2026-11-08) sasrt_flicker_depth_writers.toml with sasrt_renut_frames_ahead = 1: the
                                       game thread not held at its Swap for the render thread. Does the worker's scene
                                       pass get the shading's camera again (the depth test on the dumps)?
  sasrt_scene_same_frame_off.toml      (2026-11-08) the flicker's fix off: each frame's scene drawn a frame late, under the
                                       next frame's shadows, as before (the flicker back).
  sasrt_flicker_same_frame.toml        (2026-11-08) the fix candidate sasrt_renut_scene_same_frame (each frame's scene pass
                                       replayed in the frame it was recorded, under the shadows of that frame's camera)
                                       with the diagnostics to check it (scene-pass lines, mask/depth/atlas dumps).
  sasrt_hot_verify.toml                (2026-11-08, katamari-nx's docs/optimising-functions.md "Verifying") the localized
                                       copies and hand-written natives (app/src/cpu/hot) with a dense guard: the first
                                       4000 calls of each thread and then one in 64 run both the copy and the
                                       recompiled original and compare them ("[hot] DIFFERENCE" when they differ).
  sasrt_hot_off.toml                   (2026-11-08) the bulk copies and the hand-written natives off (the generated
                                       code there; the list's copies keep their own keys): an A/B half.
  sasrt_flicker_caches_state.toml      Renut's caches that skip work they judge unchanged, on the constants' and
                                       state's way (snapshot deltas, persistent shared constants, pushed-constant
                                       deltas, fast draws, memos, texture and vertex binding skips): the console's
                                       CPU orders memory less strictly than Ryujinx's x86 host.
  sasrt_flicker_caches_data.toml       ... on the vertex, index and texture data's way (store cards, kick reuse,
                                       fetch cache, whole buffers, mesh / geometry / resource objects, record
                                       extents and lookups, chain reuse). Both together ran a Ryujinx race at a
                                       sixth of the speed, hence two halves.
  sasrt_deko3d_read_wait.toml          the fix off and a wait for idle (with the texture cache's own invalidate)
                                       for every texture moving to a read layout: rendered, then sampled.
  sasrt_deko3d_write_wait.toml         the fix off and a wait for idle for every texture moving to a write layout:
                                       sampled, then rendered or cleared again.
  sasrt_deko3d_clear_wait.toml         the fix off and a wait for idle before every clear.
  Every config has the shadow dump on A+B+X+Y (app/sasrt_switch.toml) but the two timed dumps above.
  sasrt_deko3d_color_uncompressed.toml sasrt_deko3d_color_compression off: colour targets without the GPU's
                                       compression (the last console-only feature no config had turned off).

Added 2026-11-08 (the GPU round after the move to the ultimate base, docs/gpu-round-1108.md; every item on in
sasrt.toml):

  sasrt_gpu_round_off.toml             every item of the round off (the renderer as moved, before the round).
  sasrt_gpu_round_profile.toml         the GPU profile split by pixel shader (banjo_renut_diag_gpu_shaders) and the
                                       barriers counted by cause (sasrt_deko3d_diag_barriers): where the GPU time goes
                                       now, per shader, for the next round.
  sasrt_gpu_ab_<n>.toml                the in-run A/B of item n (banjo_renut_ab_target = 90 + n): 4 s halves with and
                                       without it, "[renut A/B]" lines with fps, the GPU's and the render thread's ms
                                       (items 12 and 14, off by default, are on in these; item 10 has none).
  sasrt_gpu_try_tiled_cache.toml       item 12, Maxwell's tiled caching, on (off by default: Ryujinx does not emulate it).
  sasrt_gpu_try_lazy_depth.toml        item 14, depth decompressed right before its read, on (off by default: Ryujinx
                                       emulates no depth compression).
  sasrt_gpu_face_sign_off.toml         item 10 off (the face register's reciprocal back).

Added 2026-11-08 later (the second GPU round, items 15-29, docs/gpu-round-1108.md "Round 2"):

  sasrt_gpu_round2_off.toml            the second round's items off (the first round's on): its whole effect in one
                                       pair of runs against the normal toml.
  sasrt_gpu_ab_<n>.toml (n 15-29)      the in-run A/B of item n (banjo_renut_ab_target = 90 + n).
  sasrt_gpu_trace.toml                 one frame's command stream every 600 frames ([deko3d trace] lines) with the barrier
                                       causes and the census (sasrt_deko3d_diag_trace, sasrt_deko3d_diag_barriers).

    python tools/make_renut_test_configs.py --out out/nx/sdcard/switch/sasrt-nx/configs
"""
import argparse
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GPU_BEFORE = {
    'banjo_deko3d_draw_resolves': 'false',
    'banjo_deko3d_depth_compression': 'false',
    'banjo_deko3d_zcull': 'false',
    'banjo_deko3d_barrier_merge': 'false',
    'banjo_deko3d_barrier_lean': 'false',
    'banjo_deko3d_depth_handover': 'false',
    'banjo_deko3d_push_constants': 'false',
    'banjo_deko3d_ring_cleaner': 'false',
    'banjo_deko3d_kick_submit': 'false',
    'banjo_deko3d_eager_kicks': 'false',
}
CPU_BEFORE = {
    'sa2_renut_snapshot_deltas': 'false',
    'sa2_renut_snapshot_deltas_constants': 'false',
    'sa2_renut_deferred_chain': 'false',
    'sa2_renut_capture_batches': 'false',
    'banjo_renut_fetch_data_unread': 'false',
    'banjo_renut_fetch_slots_skip': 'false',
    'banjo_renut_stream_mask': 'false',
    'sa2_renut_prefetch_next': 'false',
    'banjo_renut_shared_partial_clear': 'false',
    'banjo_renut_texture_defaults_copy': 'false',
}
CONFIGS = {
    'sasrt_renut_sync_frames': {'sasrt_renut_diag_sync_frames': 'true'},
    'sasrt_renut_no_frames_ahead': {'sasrt_renut_diag_no_frames_ahead': 'true'},
    'sasrt_renut_gpu_before': GPU_BEFORE,
    'sasrt_renut_cpu_before': CPU_BEFORE,
    'sasrt_renut_kicks_off': {'banjo_deko3d_kick_submit': 'false', 'banjo_deko3d_eager_kicks': 'false'},
    'sasrt_renut_barriers_full': {'banjo_deko3d_barrier_merge': 'false', 'banjo_deko3d_barrier_lean': 'false'},
    'sasrt_renut_depth_plain': {'banjo_deko3d_zcull': 'false', 'banjo_deko3d_depth_compression': 'false',
                                'banjo_deko3d_depth_handover': 'false'},
    'sasrt_renut_pool_wrap_off': {'sasrt_renut_pool_wrap_run': 'false'},
    'sasrt_renut_expand_decoder': {'sasrt_renut_vertex_expand_tables': 'false'},
    'sasrt_renut_signs_retire': {'sasrt_renut_texture_keep_on_signs': 'false'},
    'sasrt_renut_alpha_spec': {'banjo_deko3d_alpha_spec': 'true'},
    'sasrt_renut_stream_cache_128': {'banjo_renut_stream_cache_mb': '128', 'banjo_renut_stream_cache_pressure': 'false'},
    'sasrt_renut_stream_cache_384': {'banjo_renut_stream_cache_mb': '384'},
    'sasrt_renut_gpu_profile': {'renut_gpu_profile': '10.0'},
    'sasrt_renut_gpu_shaders': {'renut_gpu_profile': '10.0', 'banjo_renut_diag_gpu_shaders': 'true'},
    'sasrt_renut_baked_fetches_off': {'sasrt_renut_baked_fetches': 'false'},
    'sasrt_renut_txq_verify': {'banjo_deko3d_txq_verify': 'true'},
    'sasrt_renut_txq_query': {'banjo_deko3d_txq_constants': 'false'},
    'sasrt_display_gamma_115': {'sasrt_display_gamma': '1.15'},
    'sasrt_renut_deko3d_plain': {'banjo_deko3d_vs_outputs': 'false', 'banjo_deko3d_early_z': 'false',
                                 'banjo_deko3d_early_hoist': 'false', 'banjo_deko3d_uam_gvn': 'false',
                                 'banjo_deko3d_uam_prmt': 'false', 'banjo_deko3d_uam_uniform_branches': 'false',
                                 'banjo_deko3d_uam_wide_rows': 'false', 'banjo_deko3d_tess_spec': 'false',
                                 'banjo_deko3d_txq_constants': 'false'},
    'sasrt_renut_store_cards_off': {'banjo_renut_store_cards': 'false'},
    'sasrt_renut_capture_streams': {'sasrt_renut_capture_recorded_streams': 'true'},
    'sasrt_renut_frames_ahead_1': {'sasrt_renut_frames_ahead': '1'},
    'sasrt_renut_exports_held_off': {'sasrt_renut_exports_held': 'false'},
    'sasrt_deko3d_depth_resolve_off': {'sasrt_deko3d_depth_resolve': 'false'},
    'sasrt_renut_depth_uncompressed': {'banjo_deko3d_depth_compression': 'false'},
    'sasrt_movie_colour_native_off': {'sasrt_cpu_native_sub_82e7f918': 'false'},
    'sasrt_renut_gi_normalized': {'sasrt_renut_texture_int_format': 'false'},
    # The banjo-nx sync of 2026-10-29 (docs/deko3d-renderer.md): its pieces off one at a time.
    'sasrt_banjo_fast_draw_off': {'banjo_renut_fast_draw': 'false'},
    'sasrt_banjo_record_objects_off': {'banjo_renut_resource_objects': 'false', 'banjo_renut_geometry_objects': 'false',
                                       'banjo_renut_record_extents': 'false', 'banjo_renut_record_lookups': 'false'},
    'sasrt_banjo_replay_stream_off': {'banjo_renut_replay_stream': 'false'},
    'sasrt_banjo_fetch_cache_off': {'banjo_renut_fetch_cache': 'false'},
    'sasrt_banjo_gpu_region_off': {'banjo_deko3d_gpu_region': 'false'},
    'sasrt_banjo_async_variants_off': {'banjo_deko3d_async_variants': 'false', 'banjo_deko3d_async_cache_reads': 'false'},
    # The far-cascade shadow flicker (2026-10-29): the console's hardware depth features Ryujinx does not emulate.
    'sasrt_banjo_zcull_off': {'banjo_deko3d_zcull': 'false'},
    # 2026-10-30: the rest of what the console's GPU does differently from Ryujinx, all at once and one at a time.
    'sasrt_flicker_all_safe': {'banjo_deko3d_zcull': 'false', 'banjo_deko3d_depth_compression': 'false',
                               'sasrt_renut_diag_sync_frames': 'true', 'banjo_deko3d_barrier_merge': 'false',
                               'banjo_deko3d_barrier_lean': 'false', 'banjo_renut_upload_cached': 'false'},
    'sasrt_banjo_upload_uncached': {'banjo_renut_upload_cached': 'false'},
    'sasrt_deko3d_msaa_positions_off': {'sasrt_deko3d_msaa_positions': 'false'},
    'sasrt_deko3d_a2c_dither_on': {'sasrt_deko3d_a2c_dither': 'true'},
    'sasrt_deko3d_strip_restart_off': {'sasrt_deko3d_strip_restart': 'false'},
    'sasrt_renut_resolve_readback_off': {'sasrt_renut_resolve_readback': 'false'},
    'sasrt_renut_shadow_dump': {'sasrt_renut_diag_shadow_dump': '"30,30,10,8,B5640E28,B5642E28,B5640B28"',
                                'sasrt_renut_diag_shadow_dump_buttons': 'false'},
    'sasrt_deko3d_color_uncompressed': {'sasrt_deko3d_color_compression': 'false'},
    'sasrt_renut_shadow_dump_atlas': {'sasrt_renut_diag_shadow_dump': '"30,30,8,8,B5640EA8,B5640E28"',
                                      'sasrt_renut_diag_shadow_dump_buttons': 'false'},
    'sasrt_renut_depth_resolve_wait_idle': {'sasrt_renut_depth_resolve_wait': '1'},
    'sasrt_renut_depth_resolve_wait_full': {'sasrt_renut_depth_resolve_wait': '2'},
    'sasrt_renut_depth_resolve_wait_texel': {'sasrt_renut_depth_resolve_wait': '3'},
    'sasrt_renut_depth_resolve_wait_copy': {'sasrt_renut_depth_resolve_wait': '4'},
    'sasrt_deko3d_compression_off': {'banjo_deko3d_depth_compression': 'false', 'sasrt_deko3d_color_compression': 'false'},
    'sasrt_renut_shadow_dump_late': {'sasrt_renut_diag_shadow_dump_late': '"B5640EA8@B5640E28"'},
    # 2026-10-30, late night: the flicker's console-only suspects outside the GPU's barriers, in three groups.
    'sasrt_flicker_shaders_plain': {'banjo_deko3d_vs_outputs': 'false', 'banjo_deko3d_early_z': 'false', 'banjo_deko3d_early_hoist': 'false', 'banjo_deko3d_uam_gvn': 'false', 'banjo_deko3d_uam_prmt': 'false', 'banjo_deko3d_uam_uniform_branches': 'false', 'banjo_deko3d_uam_wide_rows': 'false', 'banjo_deko3d_tess_spec': 'false', 'banjo_deko3d_txq_constants': 'false', 'banjo_deko3d_async_variants': 'false', 'banjo_deko3d_async_cache_reads': 'false'},
    'sasrt_flicker_submit_whole': {'banjo_deko3d_kick_submit': 'false', 'banjo_deko3d_eager_kicks': 'false', 'banjo_renut_record_worker': 'false', 'banjo_deko3d_ring_cleaner': 'false'},
    # 2026-10-30, the user's request: every untested candidate in as few tomls as possible, halves for bisecting;
    # each also copies the shadow atlas after the mask on A+B+X+Y.
    'sasrt_flicker_fix_all': {'sasrt_renut_depth_resolve_wait': '4', 'sasrt_deko3d_read_wait': 'true', 'sasrt_deko3d_write_wait': 'true', 'sasrt_deko3d_clear_wait': 'true', 'banjo_deko3d_depth_compression': 'false', 'sasrt_deko3d_color_compression': 'false', 'banjo_deko3d_zcull': 'false', 'banjo_deko3d_barrier_merge': 'false', 'banjo_deko3d_barrier_lean': 'false', 'banjo_deko3d_vs_outputs': 'false', 'banjo_deko3d_early_z': 'false', 'banjo_deko3d_early_hoist': 'false', 'banjo_deko3d_uam_gvn': 'false', 'banjo_deko3d_uam_prmt': 'false', 'banjo_deko3d_uam_uniform_branches': 'false', 'banjo_deko3d_uam_wide_rows': 'false', 'banjo_deko3d_tess_spec': 'false', 'banjo_deko3d_txq_constants': 'false', 'banjo_deko3d_async_variants': 'false', 'banjo_deko3d_async_cache_reads': 'false', 'banjo_deko3d_kick_submit': 'false', 'banjo_deko3d_eager_kicks': 'false', 'banjo_renut_record_worker': 'false', 'banjo_deko3d_ring_cleaner': 'false', 'sa2_renut_snapshot_deltas': 'false', 'sa2_renut_snapshot_deltas_constants': 'false', 'sa2_renut_deferred_chain': 'false', 'banjo_renut_persistent_shared': 'false', 'banjo_renut_shared_dedupe': 'false', 'banjo_renut_shared_partial_clear': 'false', 'banjo_deko3d_push_constants': 'false', 'banjo_renut_literals_resident': 'false', 'banjo_deko3d_texture_skip': 'false', 'banjo_deko3d_vtx_dedupe': 'false', 'banjo_renut_pipeline_memo': 'false', 'banjo_renut_cpu_memos': 'false', 'banjo_renut_fast_draw': 'false', 'banjo_renut_store_cards': 'false', 'banjo_renut_kick_reuse': 'false', 'banjo_renut_fetch_cache': 'false', 'banjo_renut_whole_buffers': 'false', 'banjo_renut_mesh_objects': 'false', 'banjo_renut_geometry_objects': 'false', 'banjo_renut_resource_objects': 'false', 'banjo_renut_record_extents': 'false', 'banjo_renut_record_lookups': 'false', 'banjo_renut_chain_reuse': 'false', 'banjo_renut_chain_reuse_replays': 'false', 'sasrt_renut_diag_shadow_dump_late': '"B5640EA8@B5640E28"'},
    'sasrt_flicker_fix_gpu': {'sasrt_renut_depth_resolve_wait': '4', 'sasrt_deko3d_read_wait': 'true', 'sasrt_deko3d_write_wait': 'true', 'sasrt_deko3d_clear_wait': 'true', 'banjo_deko3d_depth_compression': 'false', 'sasrt_deko3d_color_compression': 'false', 'banjo_deko3d_zcull': 'false', 'banjo_deko3d_barrier_merge': 'false', 'banjo_deko3d_barrier_lean': 'false', 'banjo_deko3d_vs_outputs': 'false', 'banjo_deko3d_early_z': 'false', 'banjo_deko3d_early_hoist': 'false', 'banjo_deko3d_uam_gvn': 'false', 'banjo_deko3d_uam_prmt': 'false', 'banjo_deko3d_uam_uniform_branches': 'false', 'banjo_deko3d_uam_wide_rows': 'false', 'banjo_deko3d_tess_spec': 'false', 'banjo_deko3d_txq_constants': 'false', 'banjo_deko3d_async_variants': 'false', 'banjo_deko3d_async_cache_reads': 'false', 'banjo_deko3d_kick_submit': 'false', 'banjo_deko3d_eager_kicks': 'false', 'banjo_renut_record_worker': 'false', 'banjo_deko3d_ring_cleaner': 'false', 'sasrt_renut_diag_shadow_dump_late': '"B5640EA8@B5640E28"'},
    'sasrt_flicker_fix_cpu': {'sa2_renut_snapshot_deltas': 'false', 'sa2_renut_snapshot_deltas_constants': 'false', 'sa2_renut_deferred_chain': 'false', 'banjo_renut_persistent_shared': 'false', 'banjo_renut_shared_dedupe': 'false', 'banjo_renut_shared_partial_clear': 'false', 'banjo_deko3d_push_constants': 'false', 'banjo_renut_literals_resident': 'false', 'banjo_deko3d_texture_skip': 'false', 'banjo_deko3d_vtx_dedupe': 'false', 'banjo_renut_pipeline_memo': 'false', 'banjo_renut_cpu_memos': 'false', 'banjo_renut_fast_draw': 'false', 'banjo_renut_store_cards': 'false', 'banjo_renut_kick_reuse': 'false', 'banjo_renut_fetch_cache': 'false', 'banjo_renut_whole_buffers': 'false', 'banjo_renut_mesh_objects': 'false', 'banjo_renut_geometry_objects': 'false', 'banjo_renut_resource_objects': 'false', 'banjo_renut_record_extents': 'false', 'banjo_renut_record_lookups': 'false', 'banjo_renut_chain_reuse': 'false', 'banjo_renut_chain_reuse_replays': 'false', 'sasrt_renut_diag_shadow_dump_late': '"B5640EA8@B5640E28"'},
    'sasrt_flicker_caches_state': {'sa2_renut_snapshot_deltas': 'false', 'sa2_renut_snapshot_deltas_constants': 'false', 'sa2_renut_deferred_chain': 'false', 'banjo_renut_persistent_shared': 'false', 'banjo_renut_shared_dedupe': 'false', 'banjo_renut_shared_partial_clear': 'false', 'banjo_deko3d_push_constants': 'false', 'banjo_renut_literals_resident': 'false', 'banjo_deko3d_texture_skip': 'false', 'banjo_deko3d_vtx_dedupe': 'false', 'banjo_renut_pipeline_memo': 'false', 'banjo_renut_cpu_memos': 'false', 'banjo_renut_fast_draw': 'false'},
    'sasrt_flicker_caches_data': {'banjo_renut_store_cards': 'false', 'banjo_renut_kick_reuse': 'false', 'banjo_renut_fetch_cache': 'false', 'banjo_renut_whole_buffers': 'false', 'banjo_renut_mesh_objects': 'false', 'banjo_renut_geometry_objects': 'false', 'banjo_renut_resource_objects': 'false', 'banjo_renut_record_extents': 'false', 'banjo_renut_record_lookups': 'false', 'banjo_renut_chain_reuse': 'false', 'banjo_renut_chain_reuse_replays': 'false'},
    'sasrt_deko3d_read_wait': {'sasrt_renut_depth_resolve_wait': '0', 'sasrt_deko3d_read_wait': 'true'},
    'sasrt_deko3d_write_wait': {'sasrt_renut_depth_resolve_wait': '0', 'sasrt_deko3d_write_wait': 'true'},
    'sasrt_deko3d_clear_wait': {'sasrt_renut_depth_resolve_wait': '0', 'sasrt_deko3d_clear_wait': 'true'},
    # 2026-11-03: the flicker's shading draws logged with their bindings in the A+B+X+Y windows (the atlas copied too).
    'sasrt_flicker_bindings': {'sasrt_renut_diag_light_volumes': '-1',
                               'sasrt_renut_diag_shadow_dump_late': '"B5640EA8@B5640E28"'},
    # 2026-11-03: rr6-nx's range-path fix off (the strip restart marker counted as vertex 65535 again).
    'sasrt_strip_markers_off': {'sasrt_strip_markers': 'false'},
    # 2026-11-03: the destinations made again every frame, as before (the flicker's candidate off).
    'sasrt_renut_resolve_target_pages_off': {'sasrt_renut_resolve_target_pages': 'false'},
    # 2026-11-03, late: the bindings run plus the mask after each ring's shading draw.
    'sasrt_flicker_passes': {'sasrt_renut_diag_light_volumes': '-1',
                             'sasrt_renut_diag_shadow_dump_late': '"B5640EA8@B5640E28"',
                             'sasrt_renut_diag_shadow_dump_passes': 'true'},
    # 2026-11-04 (newlogs11): the console's mask draws compute exactly what their inputs say; the bad frame's atlas and
    # shading matrices are a frame apart. The console-only ways per-draw state reaches the renderer, off one at a time
    # (each also logs the mask draws and copies the atlas and the mask after each ring, as sasrt_flicker_passes).
    'sasrt_direct_state_off': {'sasrt_cpu_direct_state': 'false', 'sasrt_cpu_direct_flush': 'false',
                               'sasrt_renut_diag_light_volumes': '-1',
                               'sasrt_renut_diag_shadow_dump_late': '"B5640EA8@B5640E28"',
                               'sasrt_renut_diag_shadow_dump_passes': 'true'},
    'sasrt_direct_flush_off': {'sasrt_cpu_direct_flush': 'false',
                               'sasrt_renut_diag_light_volumes': '-1',
                               'sasrt_renut_diag_shadow_dump_late': '"B5640EA8@B5640E28"',
                               'sasrt_renut_diag_shadow_dump_passes': 'true'},
    'sasrt_me_native_plain': {'masseffect_native_pm4_fast': 'false', 'masseffect_native_fast_pair': 'false',
                              'masseffect_native_raw_microcode': 'false', 'masseffect_native_flat_identity': 'false',
                              'masseffect_native_compare_fast': 'false', 'masseffect_native_fast_copy': 'false',
                              'masseffect_native_indices_cache': 'false', 'masseffect_native_fingerprint_mode': '0',
                              'masseffect_native_dedupe_max_fingerprint': '0',
                              'sasrt_renut_diag_light_volumes': '-1',
                              'sasrt_renut_diag_shadow_dump_late': '"B5640EA8@B5640E28"',
                              'sasrt_renut_diag_shadow_dump_passes': 'true'},
    'sasrt_clear_repeat_off': {'banjo_renut_clear_repeat': 'false',
                               'sasrt_renut_diag_light_volumes': '-1',
                               'sasrt_renut_diag_shadow_dump_late': '"B5640EA8@B5640E28"',
                               'sasrt_renut_diag_shadow_dump_passes': 'true'},
    # 2026-11-04, morning: the fix's A/B (sasrt_renut_splice_ended, on in sasrt.toml): a composed buffer's splice taking
    # the recorded buffer as it is at the splice again (the previous frame's when the worker had not begun this one's).
    'sasrt_splice_ended_off': {'sasrt_renut_splice_ended': 'false',
                               'sasrt_renut_diag_light_volumes': '-1',
                               'sasrt_renut_diag_shadow_dump_late': '"B5640EA8@B5640E28"',
                               'sasrt_renut_diag_shadow_dump_passes': 'true'},
    # 2026-11-04, morning: the copy-engine wait off (a fragment barrier after an upload, as before).
    'sasrt_deko3d_copy_wait_off': {'sasrt_deko3d_copy_wait': 'false'},
    # 2026-11-04, noon: the console's splice counters were all "taken ended" (the fix a no-op there). Next: the worker
    # buffers' own PM4 read at the splice and at the submission (c128-c131), beside the recorded snapshot's values.
    'sasrt_flicker_pm4': {'sasrt_renut_diag_splice_pm4': 'true', 'sasrt_renut_diag_light_volumes': '-1',
                          'sasrt_renut_diag_shadow_dump_late': '"B5640EA8@B5640E28"',
                          'sasrt_renut_diag_shadow_dump_passes': 'true'},
    'sasrt_flicker_depth_writers': {'sasrt_renut_diag_depth_writers': 'true', 'sasrt_renut_diag_light_volumes': '-1',
                                    'sasrt_renut_diag_shadow_dump_late': '"B5640EA8@B5640E28"'},
    'sasrt_flicker_scene_pass': {'sasrt_renut_diag_depth_writers': 'true', 'sasrt_renut_diag_light_volumes': '-1',
                                 'sasrt_renut_diag_shadow_dump': '"0,0,0,8,B5640E28"'},
    'sasrt_scene_same_frame_off': {'sasrt_renut_scene_same_frame': 'false'},
    'sasrt_hot_verify': {'banjo_hot_guard_calls': '4000', 'banjo_hot_guard_period': '64'},
    'sasrt_hot_off': {'banjo_cpu_native_bulk': 'false', 'sasrt_hand_cookie_check': 'false',
                      'sasrt_hand_water_table': 'false', 'sasrt_hand_sphere_fit': 'false',
                      'sasrt_hand_resampler': 'false', 'sasrt_hand_water_step': 'false'},
    'sasrt_flicker_same_frame': {'sasrt_renut_scene_same_frame': 'true', 'sasrt_renut_diag_depth_writers': 'true',
                                 'sasrt_renut_diag_light_volumes': '-1',
                                 'sasrt_renut_diag_shadow_dump': '"0,0,0,8,B5640E28,B5642E28,B5640B28"',
                                 'sasrt_renut_diag_shadow_dump_late': '"B5640EA8@B5640E28"'},
    'sasrt_flicker_ahead1': {'sasrt_renut_diag_depth_writers': 'true', 'sasrt_renut_diag_light_volumes': '-1',
                             'sasrt_renut_diag_shadow_dump': '"0,0,0,8,B5640E28,B5640B28"',
                             'sasrt_renut_diag_shadow_dump_late': '"B5640EA8@B5640E28"',
                             'sasrt_renut_frames_ahead': '1'},
}

# sasrt-nx (2026-11-08): the GPU round's items in order (app/src/renut_engine/gpu/sasrt_gpu_round.h; A/B 90 + index).
GPU_ROUND_KEYS = [
    'sasrt_gpu_skip_inert_draws', 'sasrt_gpu_precise_depth_resolve', 'sasrt_gpu_plain_fetches', 'sasrt_gpu_alpha_spec',
    'sasrt_gpu_gamma_upload_once', 'sasrt_gpu_decompress_merge', 'sasrt_gpu_readback_barrier_merge',
    'sasrt_gpu_fetch_copy_compute', 'sasrt_gpu_data_cache_invalidate', 'sasrt_gpu_one_x', 'sasrt_gpu_face_sign',
    'sasrt_gpu_readback_compute', 'sasrt_gpu_tiled_cache', 'sasrt_gpu_texel_readback_compute',
    'sasrt_gpu_lazy_depth_resolve',
    # the second round (2026-11-08): items 15-29, A/B 105-119
    'sasrt_gpu_seed_no_lead_wait', 'sasrt_gpu_convert_lead_wait', 'sasrt_gpu_identity_ramp', 'sasrt_gpu_convert_memo_keep',
    'sasrt_gpu_depth_resolve_float_ps', 'sasrt_gpu_same_targets_kept', 'sasrt_gpu_readback_spans',
    'sasrt_gpu_seed_wait_only', 'sasrt_gpu_readback_fence_flush', 'sasrt_gpu_convert_tail_vertex_only',
    'sasrt_gpu_convert_lead_data_only', 'sasrt_gpu_clip_spec', 'sasrt_gpu_lean_barrier_skip',
    'sasrt_gpu_readback_barriers_trim', 'sasrt_gpu_export_raster_discard',
    # the third round (2026-11-08): items 30 on, A/B 120 on
    'sasrt_gpu_seed_cpu_direct',
    'sasrt_gpu_convert_tail_no_texture_drop',
    'sasrt_gpu_vs_input_mask',
    'sasrt_gpu_export_no_pixel_shader',
    'sasrt_gpu_vs_screen_space_spec',
    'sasrt_gpu_vs_depth_remap_spec',
    'sasrt_gpu_stacked_3d_spec',
    'sasrt_gpu_stacked_filter_spec',
    'sasrt_gpu_fetch_endian_spec',
    'sasrt_gpu_gpr_cap',
    'sasrt_gpu_gpr_cap_filter',
    'sasrt_gpu_export_format_spec',
    'sasrt_gpu_texture_drop_tracked',
    'sasrt_gpu_target_wait_tracked',
    'sasrt_gpu_read_wait_tracked',
    'sasrt_gpu_handover_with_smaa',
    'sasrt_gpu_export_window_ubo',
    'sasrt_gpu_export_list_topology',
    'sasrt_gpu_export_no_point_gs',
]
GPU_ROUND2_KEYS = GPU_ROUND_KEYS[15:30]
GPU_ROUND3_KEYS = GPU_ROUND_KEYS[30:]
GPU_ROUND_OFF_BY_DEFAULT = {'sasrt_gpu_tiled_cache', 'sasrt_gpu_lazy_depth_resolve'}
CONFIGS['sasrt_gpu_round_off'] = {k: 'false' for k in GPU_ROUND_KEYS}
# the second round's items off, the first round's on (the renderer of NRO 2026-11-08 13:28)
CONFIGS['sasrt_gpu_round2_off'] = {k: 'false' for k in GPU_ROUND2_KEYS}
# the third round's items off, the first two rounds' on (sasrt-nx, 2026-11-08)
CONFIGS['sasrt_gpu_round3_off'] = {k: 'false' for k in GPU_ROUND3_KEYS}
# the third round with the export repeats and the trace (its evidence)
CONFIGS['sasrt_gpu_round3_diag'] = {'sasrt_deko3d_diag_trace': 'true', 'sasrt_deko3d_diag_barriers': 'true',
                                   'sasrt_gpu_diag_export_dupes': 'true'}
# one frame's command stream every 600 frames, with the barrier causes and the census (the second round's evidence)
CONFIGS['sasrt_gpu_trace'] = {'sasrt_deko3d_diag_trace': 'true', 'sasrt_deko3d_diag_barriers': 'true'}
# the game's FXAA as before (SMAA off): the AA swap's comparison (sasrt_smaa_replaces_fxaa)
CONFIGS['sasrt_fxaa_game'] = {'banjo_renut_smaa': 'false', 'sasrt_smaa_replaces_fxaa': 'false'}
# the per-shader GPU profile with the export repeats counted (sasrt_gpu_diag_export_dupes)
CONFIGS['sasrt_gpu_shader_profile'] = {'banjo_renut_diag_gpu_shaders': 'true', 'sasrt_gpu_diag_export_dupes': 'true'}
# the two items off by default, on (each its own run, then its A/B with it on)
CONFIGS['sasrt_gpu_try_tiled_cache'] = {'sasrt_gpu_tiled_cache': 'true'}
CONFIGS['sasrt_gpu_try_lazy_depth'] = {'sasrt_gpu_lazy_depth_resolve': 'true'}
# item 10 has no in-run A/B (its pipelines keep their keys): the run with it off
CONFIGS['sasrt_gpu_face_sign_off'] = {'sasrt_gpu_face_sign': 'false'}
CONFIGS['sasrt_gpu_round_profile'] = {'banjo_renut_diag_gpu_shaders': 'true', 'sasrt_deko3d_diag_barriers': 'true'}
for _n, _k in enumerate(GPU_ROUND_KEYS):
    if _k == 'sasrt_gpu_face_sign':
        continue
    _keys = {'banjo_renut_ab_target': str(90 + _n)}
    if _k in GPU_ROUND_OFF_BY_DEFAULT:
        _keys[_k] = 'true'  # its A/B with it on in the other half
    CONFIGS['sasrt_gpu_ab_%d' % _n] = _keys


def apply(text, keys):
    for k, v in keys.items():
        line = '%s = %s' % (k, v)
        if re.search(r'(?m)^%s\s*=' % re.escape(k), text):
            text = re.sub(r'(?m)^%s\s*=.*$' % re.escape(k), line, text)
        else:
            text = text.rstrip() + '\n' + line + '\n'
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--base', default=os.path.join(ROOT, 'app', 'sasrt_switch.toml'))
    a = ap.parse_args()
    base = open(a.base, encoding='utf-8').read()
    os.makedirs(a.out, exist_ok=True)
    for name, keys in CONFIGS.items():
        head = '# %s: app/sasrt_switch.toml with %s (tools/make_renut_test_configs.py)\n' % (
            name, ', '.join('%s = %s' % kv for kv in keys.items()))
        with open(os.path.join(a.out, name + '.toml'), 'w', encoding='utf-8', newline='\n') as f:
            f.write(head + apply(base, keys))
        print(name)


if __name__ == '__main__':
    main()
