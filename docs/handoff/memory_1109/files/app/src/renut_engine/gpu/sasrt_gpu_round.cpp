// sasrt-nx (2026-11-08): the GPU round after the move to the ultimate base (sasrt_gpu_round.h, docs/gpu-round-1108.md).
#include "renut_engine/gpu/sasrt_gpu_round.h"

#include <fmt/format.h>
#include <rex/cvar.h>

#include "cpu/banjo_enhancements.h"

REXCVAR_DEFINE_BOOL(sasrt_gpu_skip_inert_draws, true, "SASRT/GPU",
                    "Renut's renderer (GPU round of 2026-11-08, item 0, A/B 90): a draw that can write nothing (no colour "
                    "channel in its colour mask, no depth write, no stencil operation, no memory export in either "
                    "shader) is not drawn, and its targets are not bound for it. The race's two draws a frame into the "
                    "576x272 4x-multisampled depth target (depth test NEVER, nothing written) cost the console 1.85 ms a "
                    "frame with their target changes. Nothing the draw could change exists: same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

REXCVAR_DEFINE_BOOL(sasrt_gpu_precise_depth_resolve, true, "SASRT/GPU",
                    "deko3d renderer (GPU round of 2026-11-08, item 1, A/B 91): with sasrt_deko3d_depth_resolve, a "
                    "compressed depth target is decompressed before a read or when it leaves the bind point only if a "
                    "draw, clear or copy wrote it since its last decompression; before, every bind marked it. The race's "
                    "lighting passes take the scene depth (1152x544) on and off dozens of times a frame and only test "
                    "it: each change decompressed it again. Decompressing tiles that are already plain changes nothing: "
                    "same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

REXCVAR_DEFINE_BOOL(sasrt_gpu_plain_fetches, true, "SASRT/GPU",
                    "deko3d renderer (GPU round of 2026-11-08, item 2, A/B 92): a pixel shader's texture fetches whose "
                    "fetch constants have no signs, no gamma and no exponent adjust for the draw are compiled without "
                    "that code (constant 926, a bit a fetch constant; tools/deko3d_glsl_opt.py pass plainfetch): the "
                    "shader skipped it for them anyway, but its temporaries counted in its registers. The race's "
                    "G-buffer shader 33 -> 28 GPRs and the final pass 42 -> 31 (32 or fewer: every warp slot of the SM "
                    "in use, to hide texture latency with). New pipelines, built in the background; until one is "
                    "built the draw uses the generic one. Same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

REXCVAR_DEFINE_BOOL(sasrt_gpu_alpha_spec, true, "SASRT/GPU",
                    "deko3d renderer (GPU round of 2026-11-08, item 3, A/B 93): banjo-nx's alpha test specialization "
                    "(banjo_deko3d_alpha_spec, off here since sa2-nx saw flat colours on SA2 in Ryujinx) for this game: "
                    "the alpha test's function is the pixel shader's constant 903, so a draw without the test has no "
                    "compare and no discard, its shader no longer 'kills pixels', and the GPU tests depth before "
                    "shading instead of after: hidden pixels of opaque draws are not shaded. Checked in Ryujinx for "
                    "this game's race. Same pixels (the test passes every pixel when it is off)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_gamma_upload_once, true, "SASRT/GPU",
                    "Renut's renderer (GPU round of 2026-11-08, item 4, A/B 94): the game's display gamma ramp "
                    "(sa2_renut_gamma_ramp) is copied to its texture when the game changes it and in the first 300 "
                    "frames (a frame's list can be dropped at start-up), not every frame: each copy was a copy-engine "
                    "upload between two barriers, the first a full one. kameo-nx's banjo_renut_gamma_upload_once for the "
                    "base's ramp code; this port's ramp code is sa2-nx's. The texture holds the same texels: same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_decompress_merge, true, "SASRT/GPU",
                    "deko3d renderer (GPU round of 2026-11-08, item 5, A/B 95): when a compressed depth target is "
                    "decompressed as the targets change (sasrt_deko3d_depth_resolve) and a barrier is already waiting to "
                    "be emitted (not a full one), the decompression is recorded first and the two barriers are one: "
                    "the waiting one, which went out before the decompression, and the one after it. The decompression "
                    "is ordered after the draws before it either way (as when nothing is waiting). Same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

REXCVAR_DEFINE_BOOL(sasrt_gpu_readback_barrier_merge, true, "SASRT/GPU",
                    "deko3d renderer (GPU round of 2026-11-08, item 6, A/B 96): an image read back to a buffer for the "
                    "CPU (the race's 1x1 average luminance, every frame: sasrt_renut_resolve_readback) had its full "
                    "barrier before the copy emitted right after the full barrier of the texture's own move into the "
                    "copy layout, and its full barrier after the copy right before the full barrier of the move back: "
                    "four drains of the whole GPU with nothing between the pairs. Each pair is one barrier now (the "
                    "stronger wait and both invalidations, in the same place): two. Same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

REXCVAR_DEFINE_BOOL(sasrt_gpu_fetch_copy_compute, true, "SASRT/GPU",
                    "deko3d renderer (GPU round of 2026-11-08, item 7, A/B 97): the copies the memory exports need are "
                    "made by a compute shader on the 3D engine (fetch_copy_cs) instead of the copy engine: each memexport "
                    "window's seed (its bytes from guest memory, before the export draw writes into it: one to three a "
                    "character, about 40 a frame in the race) and the fetch data of a draw that reads exported vertices "
                    "from memory. A wait for the 3D engine on each side instead of a full barrier (the whole GPU idle, the "
                    "copy engine with it); and the export draw no longer races the seed copy, nor a vertex shader its "
                    "fetch copy (the barriers after them waited for the 3D engine only, not the copy engine). The same "
                    "bytes in the same places: same pixels. The 10 s count: fetch data copies / seeded export draws")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

REXCVAR_DEFINE_BOOL(sasrt_gpu_data_cache_invalidate, true, "SASRT/GPU",
                    "deko3d renderer (GPU round of 2026-11-08, item 8, A/B 98): a barrier for a buffer (memory exports, "
                    "the exported streams' conversions, fetch data: about 100 a frame in the race) invalidates the "
                    "shaders' global-data and constant caches (Maxwell's InvalidateShaderCaches with those two bits), "
                    "no longer their instruction cache as well (deko3d's DkInvalidateFlags_Shader sets all three): a "
                    "buffer holds no shader code, and the shaders refetched theirs after every such barrier. New code "
                    "(a compiled variant) still invalidates it (the descriptor and code epochs). Same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

REXCVAR_DEFINE_BOOL(sasrt_gpu_one_x, true, "SASRT/GPU",
                    "deko3d renderer (GPU round of 2026-11-08, item 9, A/B 99): a draw whose targets are 1x and whose "
                    "sampled textures all have scale code 0 (every gameplay draw in handheld mode; the HUD docked is "
                    "1.5x) has its pixel shader compiled with both folded (constant 926 bit 31; tools/deko3d_glsl_opt.py "
                    "pass onex, banjo-nx's scale1 and fragscale as a draw's choice): the scale factor's seven-way select "
                    "before a texel-coordinate fetch or an offset sample, and the reciprocal and multiplies of the pixel "
                    "position's scale. The final FXAA pass 150 -> 121 instructions. The same values: same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

REXCVAR_DEFINE_BOOL(sasrt_gpu_face_sign, true, "SASRT/GPU",
                    "deko3d renderer (GPU round of 2026-11-08, item 10; no in-run A/B: the pipelines keep their keys, "
                    "compare with it off): the Xenos face register's sign in the pixel shaders that read it "
                    "(clamp(1 / Y, -FLT_MAX, FLT_MAX) >= 0, Y the pixel position times +1 or -1 by the facing) as Y's "
                    "sign bit (tools/deko3d_glsl_opt.py pass facesign, constant 928): a reciprocal (a quarter-rate "
                    "instruction), two clamps and a compare a pixel fewer in the race's most-drawn G-buffer shader and "
                    "nine others. For any Y that is not NaN, and it never is, the same answer: same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

REXCVAR_DEFINE_BOOL(sasrt_gpu_readback_compute, true, "SASRT/GPU",
                    "deko3d renderer (GPU round of 2026-11-08, item 11, A/B 101): the memexport results the CPU reads "
                    "back (banjo_renut_batched_readbacks: one group at a list's end) are copied to the readback buffer by "
                    "fetch_copy_cs on the 3D engine instead of the copy engine: a wait for the 3D engine before instead of "
                    "a full barrier, then a wait and the GPU's L2 written back to memory for the CPU. The same bytes: same "
                    "pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

REXCVAR_DEFINE_BOOL(sasrt_gpu_tiled_cache, false, "SASRT/GPU",
                    "deko3d renderer (GPU round of 2026-11-08, item 12, A/B 102; OFF by default until a console run says "
                    "the picture is the same: Ryujinx does not emulate it): Maxwell's tiled caching (binning: the GPU "
                    "renders each screen tile's primitives together, keeping its colour and depth on chip), which NVN "
                    "uses and deko3d leaves off. The race's G-buffer (three targets and depth, overdraw) and its additive "
                    "lights (a read and a write of the 64-bit target a pixel per light) are the bandwidth it saves. "
                    "Same pixels by the hardware's design (each pixel's order is kept; deko3d's barriers and fences flush "
                    "the tiles; a full barrier gets a flush ahead of it)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

REXCVAR_DEFINE_BOOL(sasrt_gpu_texel_readback_compute, true, "SASRT/GPU",
                    "deko3d renderer (GPU round of 2026-11-08, item 13, A/B 103): the 1x1 float resolve the game's CPU "
                    "reads every frame (the race's average luminance, sasrt_renut_resolve_readback) is read back by a "
                    "compute shader on the 3D engine (texel_readback_cs: the texel's 32 bits as they are) instead of a "
                    "copy-engine copy: no move into and out of the copy layout, each with a full barrier (the whole GPU "
                    "idle), but a wait for the 3D engine and the L2 written back for the CPU. The same bits: same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

REXCVAR_DEFINE_BOOL(sasrt_gpu_lazy_depth_resolve, false, "SASRT/GPU",
                    "deko3d renderer (GPU round of 2026-11-08, item 14, A/B 104; OFF by default until a console run says "
                    "the picture is the same: Ryujinx emulates no depth compression): with sasrt_deko3d_depth_resolve and "
                    "sasrt_gpu_precise_depth_resolve, a written compressed depth target is decompressed right before "
                    "something reads it (bound alone for it, then the targets bound again), not each time it leaves the "
                    "bind point or a command list ends: the race's remaining 13 decompressions a frame, most of them of a "
                    "target bound again and written again before any read. The read sees decompressed tiles either way: "
                    "same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

// The second round (2026-11-08): items 15 and up, A/B 105 and up.
REXCVAR_DEFINE_BOOL(sasrt_gpu_seed_no_lead_wait, true, "SASRT/GPU",
                    "deko3d renderer (second GPU round of 2026-11-08, item 15, A/B 105): the memexport seeds that "
                    "sasrt_gpu_fetch_copy_compute dispatches (guest memory into a draw's export windows, 46-63 a race "
                    "frame) start without the wait for the 3D engine before them. The windows they write are fresh: past "
                    "the slot's last window (256-byte aligned, no shared cache line), so no earlier draw, conversion or copy "
                    "of this list read or wrote those bytes; the wait after the seeds (before the export draw) stays and "
                    "orders everything before it. Same bytes, same pixels; one wait for idle fewer a seeded draw")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_convert_lead_wait, true, "SASRT/GPU",
                    "deko3d renderer (second GPU round, item 16, A/B 106): an exported stream conversion (a draw that "
                    "reads vertices a memexport draw wrote) skips its leading wait for the 3D engine when the command "
                    "list has recorded a buffer barrier (a wait for idle with the data caches dropped) since its last "
                    "memexport draw: the exports it reads are written and visible already, and it writes a fresh part of "
                    "the stream buffer. The wait after it (before the draw) stays. Same bytes, same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_identity_ramp, true, "SASRT/GPU",
                    "Renut renderer (second GPU round, item 17, A/B 107; deko3d and D3D12): when the game's display gamma "
                    "ramp is the linear one (every channel's entry i within a quarter of level i at 8 bits: the XDK's ramp "
                    "repeats i's bits, i << 2 | i >> 6, at most 0.185 off; sasrt_display_gamma 1) and the scan-out applies "
                    "no output gamma, the present shader writes the colour's 8-bit level i / 255 instead of looking the "
                    "ramp up (three dependent texture loads a pixel): the 8-bit target, rounding to the nearest level, "
                    "stores i either way. Same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

REXCVAR_DEFINE_BOOL(sasrt_gpu_convert_memo_keep, true, "SASRT/GPU",
                    "Renut renderer (second GPU round, item 18, A/B 108; both back ends, with banjo_renut_convert_reuse): "
                    "an exported stream conversion made earlier in the frame is used again by a later draw that needs the "
                    "same one (the same export window, offset, vertices, strides and elements) even when other memexport "
                    "draws ran in between: a new export writes a fresh window (another offset, so another key), never "
                    "one converted already. The conversions are forgotten as before when a window is written again in "
                    "place, a slot's exports complete (its windows are used again from 0), an export or stream buffer is "
                    "replaced, or the frame changes. banjo-nx's memo was cleared by every export (88 conversions and 11 "
                    "used again a race frame in Ryujinx). The same bytes: same pixels; a dispatch and its two waits fewer "
                    "a hit")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

REXCVAR_DEFINE_BOOL(sasrt_gpu_depth_resolve_float_ps, true, "SASRT/GPU",
                    "Renut renderer (second GPU round, item 19, A/B 109; both back ends): a single-sampled depth resolve "
                    "whose words nothing reads (banjo_renut_depth_words_lazy: the race's shadow cascades and scene depth, "
                    "the words target bound and write-masked) is drawn by depth_resolve_float_ps, which loads the depth "
                    "and writes it, without the stencil load, the 24-bit / 20e4 encode and the words output the masked "
                    "target threw away. The float is the same load: same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

REXCVAR_DEFINE_BOOL(sasrt_gpu_same_targets_kept, true, "SASRT/GPU",
                    "deko3d renderer (second GPU round, item 20, A/B 110): the render targets are not bound again when the "
                    "framebuffer asked for is the one this command list bound last: the renderer asks again after every "
                    "compute dispatch (each memexport seed and stream conversion, about 120 a race frame: its trace) and "
                    "every resolve, and each bind rewrote the colour, depth and Zcull set-up of the same images. A "
                    "framebuffer's views never change and the one in use is alive; plume's own binds (the lazy depth "
                    "decompression) forget it. Same state: same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

REXCVAR_DEFINE_BOOL(sasrt_gpu_readback_spans, true, "SASRT/GPU",
                    "deko3d renderer (second GPU round, item 21, A/B 111; with sasrt_gpu_readback_compute): the memexport "
                    "windows read back at a list's end that follow one another in an export buffer (each starting where the "
                    "last ends, 256-byte aligned) are copied by one fetch_copy_cs dispatch, the padding between them with "
                    "them (bytes the CPU never reads: it takes the windows alone), not one dispatch a window (44 a race "
                    "frame). The windows' bytes are the same: same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

REXCVAR_DEFINE_BOOL(sasrt_gpu_seed_wait_only, true, "SASRT/GPU",
                    "deko3d renderer (second GPU round, item 22, A/B 112; with sasrt_gpu_fetch_copy_compute): the barrier "
                    "between a draw's memexport seeds and the export draw is a wait for the 3D engine alone, not a buffer "
                    "barrier that also drops the texture cache, the shaders' data caches and the constant cache (about 50 "
                    "times a race frame). The export draw only writes the windows; every later reader of them (the stream "
                    "conversions, the readback) has its own barrier that drops those caches. Same order: same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_readback_fence_flush, true, "SASRT/GPU",
                    "deko3d renderer (second GPU round, item 23, A/B 113): the compute readbacks of round 1 "
                    "(sasrt_gpu_readback_compute, sasrt_gpu_texel_readback_compute: 4 a race frame) record no L2 flush "
                    "of their own (a wait for idle, the L2's dirty lines written out and every system-memory line of it "
                    "dropped: on the Tegra X1 that is the whole L2). The CPU reads those buffers only after waiting for the "
                    "slot's fence, which plume signals with deko3d's cache flush (SyncptAction FlushCache: the L2 written "
                    "out before the fence signals). The same bytes: same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

REXCVAR_DEFINE_BOOL(sasrt_gpu_convert_tail_vertex_only, true, "SASRT/GPU",
                    "deko3d renderer (second GPU round, item 24, A/B 114): the barrier between an exported stream "
                    "conversion and its draw (85 a race frame) waits for the 3D engine and drops the texture cache, as it "
                    "did, but not the shaders' global-data and constant caches: the stream buffer's only reader is the "
                    "draw's vertex fetch, which reads neither (its constants come in through the command buffer). Same "
                    "order, same bytes: same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_convert_lead_data_only, true, "SASRT/GPU",
                    "deko3d renderer (second GPU round, item 25, A/B 115): the barrier before an exported stream "
                    "conversion (when sasrt_gpu_convert_lead_wait keeps it) waits for the 3D engine and drops the shaders' "
                    "global-data cache alone (the conversion loads the export windows as storage buffers), not the "
                    "texture cache and the constant cache: its push constants are fresh transient memory, and the constant "
                    "cache is dropped at every list's start for them (plume's freshComputeConstants). Same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

REXCVAR_DEFINE_BOOL(sasrt_gpu_clip_spec, true, "SASRT/GPU",
                    "deko3d renderer (second GPU round, item 26, A/B 116): a draw without a user clip plane (every draw of "
                    "this game so far: the shared constants' plane is zeros) gets its vertex shader without the clip "
                    "distance (constant 929 = 0, tools/deko3d_glsl_opt.py pass clipspec: no dot product with the plane "
                    "a vertex), and plume sets the hardware clip slot off for it (SET_USER_CLIP_ENABLE 0; rr6-nx's "
                    "banjo_deko3d_user_clip_enable turned slot 0 on for every draw). A zero plane gave every vertex a "
                    "distance of 0, which clips nothing: same pixels. A draw with a plane keeps both (PipelineKey bit 3)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

REXCVAR_DEFINE_BOOL(sasrt_gpu_lean_barrier_skip, true, "SASRT/GPU",
                    "deko3d renderer (second GPU round, item 27, A/B 117): a barrier that only moves textures into a "
                    "colour or depth target layout (a fragment barrier, no cache dropped: banjo_deko3d_lean_barriers) is "
                    "not recorded when no draw, dispatch, copy or depth decompression was recorded since the last barrier "
                    "that waited for the fragments: the reads it would put before the writes are done already (the "
                    "trace's runs of target binds and clears at a pass's start, T12 BFC Cc T13 BFC Cc ...). Clears read "
                    "no texture and write in order with the draws. Same order: same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_readback_barriers_trim, true, "SASRT/GPU",
                    "deko3d renderer (second GPU round, item 28, A/B 118; with sasrt_gpu_readback_compute): the memexport "
                    "readback at a list's end waits for the 3D engine dropping the global-data cache alone (its copies "
                    "load the windows as storage buffers), not the texture and constant caches, and records no barrier "
                    "after its copies: the list ends there, and the slot's windows are written again only after its "
                    "fence was waited for. Same bytes: same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_export_raster_discard, true, "SASRT/GPU",
                    "deko3d renderer (second GPU round, item 29, A/B 119; with banjo_renut_export_only_draws): a draw "
                    "whose vertex shader only exports to memory (the race's skinning exports) is drawn with the rasterizer "
                    "off (3D method RasterizerEnable 0, then on again) as well as the empty scissor: the vertex shader "
                    "runs and exports as before; its primitives are dropped before clipping and triangle setup instead "
                    "of reaching the scissor. No pixel either way: same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

// sasrt-nx (2026-11-08): the third GPU round (docs/gpu-round-1108.md "Round 3"; the user: "Try to aim for 20 more pixel
// identical gpu optimisations"). A/B 120 and up.
REXCVAR_DEFINE_BOOL(sasrt_gpu_seed_cpu_direct, true, "SASRT/GPU",
                    "deko3d renderer (third GPU round, item 30, A/B 120; with sasrt_gpu_fetch_copy_compute): a memexport "
                    "draw's fresh windows get their seed (guest memory's bytes there) written by the CPU straight into the "
                    "slot's export buffer as the draw is recorded, not copied into the upload ring and then by a compute "
                    "dispatch: no dispatch, and no wait between it and the export draw. The buffer is the GPU's and the "
                    "CPU's (uncached for the CPU); the windows are fresh (nothing recorded reads or writes them before), "
                    "the slot was last used before its fence, which wrote the GPU's caches out, and every queue flush drops "
                    "the GPU's L2 before the next one's work, as for the upload ring. The wait before the export draw stays "
                    "when a memexport draw of the same list has had no buffer wait since (a draw may read its windows). "
                    "Same bytes in the same places: same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

REXCVAR_DEFINE_BOOL(sasrt_gpu_convert_tail_no_texture_drop, true, "SASRT/GPU",
                    "deko3d renderer (third GPU round, item 31, A/B 121; with sasrt_gpu_convert_tail_vertex_only): the wait "
                    "after an exported stream conversion no longer drops the texture cache (deko3d's Image invalidate): the "
                    "conversion writes a part of the slot's stream buffer past everything written or read in the frame "
                    "(its 'used' end, 256-byte aligned), so no cache of the GPU holds a line of it; the slot was last used "
                    "frames ago, and every queue flush since dropped the texture and L2 caches (deko3d's postSubmitFlush). "
                    "The wait itself (all 3D work done, the stream in L2) stays. Same bytes read: same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_vs_input_mask, true, "SASRT/GPU",
                    "deko3d renderer (third GPU round, item 32, A/B 122): a pipeline's vertex attributes that the bound "
                    "vertex shader variant never reads (its shader program header's input map, read from the DKSH at load: "
                    "the outputs a pixel shader does not read, constant 905, take their inputs out with them) are bound as "
                    "constants, which the vertex attribute fetch does not read from memory. The shader reads the same "
                    "attributes as before: same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_export_no_pixel_shader, true, "SASRT/GPU",
                    "deko3d renderer (third GPU round, item 33, A/B 123; with sasrt_gpu_export_raster_discard): an "
                    "export-only draw (its vertex shader only exports to memory; drawn with the rasterizer off and an empty "
                    "scissor) is built without its pixel shader, which never ran: its vertex shader then writes no output "
                    "for it (constant 905 = 0), its textures and constants are not set up, and its draws share one "
                    "pipeline per vertex shader and state. Not when the pixel shader exports itself. Same pixels (none)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_vs_screen_space_spec, true, "SASRT/GPU",
                    "deko3d renderer (third GPU round, item 34, A/B 124): every vertex shader's epilogue tests the draw's "
                    "screen-space flag (SharedConstants.screen_space, the viewport transform off) at run time; the draw's "
                    "value goes into the pipeline key (PipelineKey::fetch_types[0] bits 0-1 of a draw that is not "
                    "tessellated) and the shader gets it as constant 932 (tools/deko3d_glsl_opt.py pass vsepi): the "
                    "branch, and the scale and offset it reads, fold. A key not built yet draws with the generic pipeline. "
                    "The same value as the run-time test: same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_vs_depth_remap_spec, true, "SASRT/GPU",
                    "deko3d renderer (third GPU round, item 35, A/B 125): the same for the epilogue's depth remap test "
                    "(SharedConstants.depth_remap[0] != 0; never on deko3d: a backwards depth range is the PC's): bits 2-3 "
                    "of the word, constant 932. Same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_stacked_3d_spec, true, "SASRT/GPU",
                    "deko3d renderer (third GPU round, item 36, A/B 126): a pixel shader's 3D fetch picks at run time between "
                    "a stacked texture (a 2D array: two fetches and a blend between layers) and a volume texture, by the "
                    "draw's texture word (bit 31, kStackedTextureBit); the draw's bits for the fetch constants its pixel "
                    "shader samples go into the key (PipelineKey::fetch_types[1] of a draw that is not tessellated, bit 31 "
                    "set) and the shader gets them as constant 934 (pass stack3d): the path not taken and its size query "
                    "fold. Seven of this game's pixel shaders, the race's full-screen ED0A8D53 and the composite among "
                    "them. The same choice: same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_stacked_filter_spec, true, "SASRT/GPU",
                    "deko3d renderer (third GPU round, item 37, A/B 127): the same for a stacked fetch's filter between "
                    "layers and its Z wrap (texture word bits 30 and 29): PipelineKey::fetch_types[2] and [3], constants 935 "
                    "and 936 (pass stack3d). Same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

// sasrt-nx (2026-11-09 23:40 - 2026-11-10 00:00): with it on, the Ocean View octopus (its tentacles skinned by a memexport
// pass that reads its bone matrices by address) came apart whenever the GPU was heavily loaded (console track-preview
// bisect, run octo_bis38: this item alone). The hole was the chain reuse's pipeline shortcut, which handed back the draw
// before's pipeline without comparing the key's per-draw words (draw.cpp, PipelineReuse; RR6 found it): fixed, and
// the same heavy test with this item on drew the octopus right (run octo_fix38). On again.
REXCVAR_DEFINE_BOOL(sasrt_gpu_fetch_endian_spec, true, "SASRT/GPU",
                    "deko3d renderer (third GPU round, item 38, A/B 128): a vertex shader that fetches by address "
                    "(vfetchMemory: the race's skinning exports read their bone matrices so, 64 words a vertex) swaps each "
                    "word every way and picks the byte order at run time from the fetch slot's word "
                    "(SharedConstants.vertex_fetch_slots, bits 0-1); the draw's order for the slots its shader reads goes "
                    "into the key (PipelineKey::sasrt_words[4-6]) and the shader gets it as constants 937-939 "
                    "(tools/deko3d_glsl_opt.py pass fetchendian): one swap a word instead of four and three selects. "
                    "Renut's translator output, not this game's: any port's vertex fetches by address. Same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

REXCVAR_DEFINE_BOOL(sasrt_gpu_gpr_cap, false, "SASRT/GPU",
                    "OFF: SLOWER ON THE CONSOLE (2026-11-08, runs r3_bis2 / r3_nocap: the G-buffer pass 23.7 ms with the caps, 19.4 without; the 576x272 pass 1.20 / 1.09): the spills cost more than the occupancy gives. "
                    "deko3d renderer (third GPU round, item 39, A/B 129): pixel shaders 364C9BF8 (the light volumes, 1.75 ms "
                    "a race frame on the console), F646B7A8 and 92D1F7E4 use 34, 33 and 38 registers with the race's plain "
                    "fetches: an SM then holds 48 of its 64 warps of them. Compiled with 32 (constant 910, uam's register "
                    "cap: tools/gpr32_shaders.txt), it holds all 64 to hide texture latency with, for one or two registers "
                    "spilled to local memory (512 or 1024 bytes a warp). The same instructions' results: same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_gpr_cap_filter, false, "SASRT/GPU",
                    "OFF: SLOWER ON THE CONSOLE (2026-11-08, runs r3_bis2 / r3_nocap: the G-buffer pass 23.7 ms with the caps, 19.4 without; the 576x272 pass 1.20 / 1.09): the spills cost more than the occupancy gives. "
                    "deko3d renderer (third GPU round, item 40, A/B 130): the 34-fetch full-screen filter 9041AFF6 (2.1 ms a "
                    "race frame on the console) uses 60 registers: 32 warps an SM. Compiled with 32 (constant 910) it gets "
                    "64, for about eight registers spilled (4 KB a warp of local memory). Whether that is faster is the "
                    "console's A/B to say (target 130). Same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

REXCVAR_DEFINE_BOOL(sasrt_gpu_export_format_spec, true, "SASRT/GPU",
                    "deko3d renderer (third GPU round, item 41, A/B 131): a vertex shader that exports to memory forms its "
                    "export address register from a float constant (eA = c<N> + the index), whose z word holds the export's "
                    "format and number flags; Renut's translator then packs every exported value through a switch over "
                    "the formats and a loop over the components with arrays indexed at run time (local memory: 6 KB a warp "
                    "in the race's skinning export shader). The draw's z word of up to three such registers (as the "
                    "constant buffer holds it: the literal's if the shader defines one, NaN-flushed as uploaded) goes "
                    "into the key (PipelineKey::sasrt_words[8-11]) and the shader gets it as constants 940-943 in place "
                    "of that operand (tools/deko3d_glsl_opt.py pass expfmt): the same operations on the same bits, which "
                    "uam folds to the one format's pack. Renut's translator output: any port's memory exports. Same bytes")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);


REXCVAR_DEFINE_BOOL(sasrt_gpu_texture_drop_tracked, false, "SASRT/GPU",
                    "OFF: WRONG ON THE CONSOLE (2026-11-08, run r3_all: the menu's 3D scene and sky washed out white; "
                    "bisected to this key, runs r3_bis1 / r3_bis2). The render targets are hardware-compressed, and the "
                    "texture-cache drop after rendering into one is needed whatever was sampled before (most likely the "
                    "texture unit's compression state). Kept for study. "
                    "deko3d renderer (third GPU round, item 42, A/B 132): a barrier that makes a texture readable (a "
                    "render target, a decompressed depth, a copy's destination, about 60 a race frame) dropped the texture "
                    "cache every time (deko3d: with a wait for idle before it, on a fragment barrier). The cache can hold "
                    "lines of an image only if a draw sampled it since the last drop: plume now notes, per texture, the "
                    "drop epoch it was last bound for sampling in (at each bind, and for everything still bound at each "
                    "drop that waits for the GPU), and the barrier drops the cache only when one of its textures was "
                    "sampled in the current epoch. Without the drop a fragment barrier waits for the fragments alone. The "
                    "same data read: same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

REXCVAR_DEFINE_BOOL(sasrt_gpu_target_wait_tracked, true, "SASRT/GPU",
                    "deko3d renderer (third GPU round, item 43, A/B 133; with sasrt_gpu_lean_barrier_skip): a barrier that "
                    "only moves textures into a colour or depth target layout (no cache dropped: a fragment barrier, about "
                    "20 a race frame) orders the earlier draws' reads of them before the new writes. Item 27 skipped it "
                    "when no work at all came since the last fragment wait; now it is skipped when none of its textures "
                    "was bound for sampling, copied, resolved or decompressed since that wait (plume: per texture, the "
                    "fragment-wait epoch of its last such use; everything bound is marked again at each wait). Nothing "
                    "then reads them while they are written. Same order of every read and write: same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

REXCVAR_DEFINE_BOOL(sasrt_gpu_read_wait_tracked, false, "SASRT/GPU",
                    "OFF (2026-11-08): it skips a read move only when sasrt_gpu_texture_drop_tracked (wrong on the console, "
                    "off) leaves no drop due, so it does nothing without it. "
                    "deko3d renderer (third GPU round, item 44, A/B 134): a barrier that makes a texture readable waits for "
                    "the fragments so the draws that wrote it are done before it is sampled. It now waits only when the "
                    "texture was written (bound as a target, cleared, copied or resolved into, decompressed) since the last "
                    "fragment wait, or its texture-cache drop is due (sasrt_gpu_texture_drop_tracked); with neither the "
                    "barrier records nothing. Plume notes per texture the fragment-wait epoch of its last write, and marks "
                    "the bound targets again at each wait. Same order of every write and read: same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

// sasrt-nx (2026-11-08, night): the fourth GPU round (the user: "our goal is getting down to 33 ms GPU time, pixel
// identical"). A/B 135 and up.
REXCVAR_DEFINE_BOOL(sasrt_gpu_export_window_ubo, true, "SASRT/GPU",
                    "deko3d renderer (fourth GPU round, item 46, A/B 136): a memexport vertex shader finds each export's "
                    "window in a loop over a local copy of the four windows (SharedConstants 61-64), indexed at run time, "
                    "so in local memory (192 bytes a thread in SASRT's skinning shader, whose draws cost ~180 ns a vertex). "
                    "With constant 944 (pass expwin) the loop reads the constant buffer itself: the same words, no local "
                    "memory. Needs the shader package and the DKSH cache made with pass expwin")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
// sasrt-nx (2026-11-09 night, the user: "15-20 more memory improvements"): plume_deko3d.h, Deko3DSetRegionBestFit.
REXCVAR_DEFINE_BOOL(sasrt_region_best_fit, true, "SASRT/GPU",
                    "The GPU region places a block in the smallest free range it fits (its bottom range last) instead of "
                    "the highest: fewer, larger free ranges (run mem12: 200-300 MB free in 40-54 ranges, the largest "
                    "28-55 MB, and a 27 MB target found no room)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
// sasrt-nx (2026-11-09 night): plume_deko3d.h, Deko3DSetImageBestFit.
REXCVAR_DEFINE_BOOL(sasrt_image_best_fit, true, "SASRT/GPU",
                    "An image goes to the smallest free range it fits among the image heap's shared chunks (the first "
                    "that fit before): fewer holes, and chunks that empty go back to the GPU region")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
// sasrt-nx (2026-11-09, the user: "make the game more memory efficient"): plume_deko3d.h, Deko3DSetDedicatedTargets.
REXCVAR_DEFINE_BOOL(sasrt_dedicated_targets, true, "SASRT/GPU",
                    "Render and depth targets of 1 MB or more in a memory chunk of their own, given back to the GPU region "
                    "(for buffers too) as soon as the target is freed, instead of a hole in a shared 64 MB image chunk "
                    "only images can use (the docked race's resolution changes left ~500 MB of such holes)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_INT32(sasrt_gpu_exp_sph_no_global_store, 0, "SASRT/GPU",
                     "EXPERIMENT (2026-11-09): vertex programs loaded with their header's DoesGlobalStore bit cleared (1), "
                     "and DoesLoadOrStore too (3): whether the store flag makes the GPU run SASRT's memexport vertex "
                     "shaders (~120 ns a vertex whatever they compute) one way that is slow");
REXCVAR_DEFINE_BOOL(sasrt_gpu_export_list_topology, false, "SASRT/GPU",
                    "deko3d renderer (fourth GPU round, item 47, A/B 137): a memexport draw recorded with the rasterizer "
                    "off (item 29) that is a point list is drawn as a triangle list when its count is a multiple of 3, "
                    "else as a line list when it is even: only its vertex shader runs, once for each vertex either way, "
                    "so the exports are the same and no pixel is drawn. SASRT's skinning exports are point lists of up "
                    "to 34,000 vertices that cost ~150 ns a vertex")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_export_no_point_gs, true, "SASRT/GPU",
                    "deko3d renderer (fourth GPU round, item 48, A/B 138): an export draw recorded with the rasterizer off "
                    "(item 29) that is a point list is built without Renut's point-sprite geometry shader, which made a "
                    "quad of every point for a rasterizer that is off. SASRT's skinning exports (~47,000 points a frame) "
                    "cost ~120 ns a point whatever their vertex shader did. The vertex shader runs once a point either way: "
                    "the same exports, and no pixel either way. Its vertex variant then gets constant 905 (no outputs)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_handover_with_smaa, false, "SASRT/GPU",
                    "deko3d renderer (fourth GPU round, item 45, A/B 135): banjo's colour hand-over "
                    "(banjo_deko3d_color_handover: a whole resolve into a texture of its size and format left in the "
                    "target's image, not copied) was off whenever SMAA was on, so every resolve was drawn since the SMAA "
                    "swap (+0.8 ms of resolves). Here SMAA runs only right after the composite draw, on that draw's first "
                    "target; any texture still sharing that target's image is settled (its resolve drawn) before SMAA "
                    "writes it, so the hand-over stays on with SMAA. Every texel is the one the copy would write: same "
                    "pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

// sasrt-nx (2026-11-09): the fifth GPU round (the user: "A393B1E0, I'm sure we can make it much more efficient"). A/B 139
// and up.
REXCVAR_DEFINE_BOOL(sasrt_gpu_depth_restore_direct, true, "SASRT/GPU",
                    "deko3d renderer (fifth GPU round, item 49, A/B 139): SASRT restores its scene depth twice a frame "
                    "(for the light pass and the composite) by drawing the depth resolve's words as colour (A393B1E0: "
                    "1200x544, the 40-pixel halves of each EDRAM tile column swapped) into the EDRAM where the depth then "
                    "sits; Renut then turns that colour back into depth (sasrt_renut_depth_restore): two full-screen passes. "
                    "With this key the copy draw is left out and the restore computes in one pass what the two give a "
                    "pixel (depth_restore_direct.hlsli: the copy's own words view, sampler, size and coordinates at the "
                    "pixel the restore reads, the bytes as the RGBA8 target stores them, the restore's decode). The colour "
                    "target is drawn (restore_copy_ps) before anything else uses it. Console run I (2026-11-09): the "
                    "restored depth equal to the old chain's on every texel (sasrt_gpu_diag_restore_verify: 118 restores, "
                    "74 M texels, 0 differ); in-run A/B -1.35 ms. (The first form read the resolve's float: 60 % of texels "
                    "differed, the copy's point samples at texel corners.)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

REXCVAR_DEFINE_BOOL(sasrt_gpu_depth_restore_whole_clear, true, "SASRT/GPU",
                    "deko3d renderer (fifth GPU round, item 50, A/B 140): the EDRAM depth restore cleared the stencil alone "
                    "(depth kept) before drawing every pixel's depth with the test off: a stencil-only clear keeps the depth, "
                    "so it cannot be a fast clear. When the restore's rectangle is the whole depth target, depth and stencil "
                    "are cleared together (the depth to 0, then every pixel drawn over it, as before): the same depth and "
                    "stencil 0 in every pixel")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
// sasrt-nx (2026-11-09): the fifth round's cuts that change pixels (the user decides which stay); never for RR6's base.
REXCVAR_DEFINE_BOOL(sasrt_gpu_cut_depth_alias, false, "SASRT/GPU",
                    "CHANGES PIXELS (fifth GPU round, item 54, A/B 144): the EDRAM depth restore (the light pass's and the "
                    "composite's depth: the G-buffer's depth resolve quantised to the game's 24 bits, stencil 0) is not "
                    "drawn: those passes bind the G-buffer's own depth target (its depth unchanged since that resolve, "
                    "float, not quantised) with its stencil cleared to 0. Saves the restore draws (~1.8 ms a race frame) "
                    "and, with item 49, nothing reads the copies. Depth tests at a light volume's edge can differ in the "
                    "last bit of 24")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_cut_restore_copy_drop, false, "SASRT/GPU",
                    "CHANGES PIXELS where the G-buffer does not draw (fifth GPU round, item 55, A/B 145): with item 49, a "
                    "restore copy left out is dropped when its target (the G-buffer's colour targets 1 and 2) is next "
                    "bound, not drawn first: the G-buffer draws over it. Saves the two copies (~0.63 ms a race frame). "
                    "Pixels the G-buffer leaves keep the last frame's G-buffer values instead of the depth words")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_cut_mip_nearest, false, "SASRT/GPU",
                    "CHANGES PIXELS (fifth GPU round, item 56, A/B 146): the game's textures that filter between mip levels "
                    "(trilinear) sample the nearer level only (bilinear): half the texel reads a sample; the step between "
                    "levels can show on surfaces at a slant. Render targets' host levels keep theirs")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_cut_lod_bias, false, "SASRT/GPU",
                    "CHANGES PIXELS (fifth GPU round, item 57, A/B 147): the game's mipmapped textures sampled with half a "
                    "level more LOD bias (smaller levels: fewer texels read, blurrier at a distance)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_cut_shadow_two_thirds, false, "SASRT/GPU",
                    "CHANGES PIXELS (fifth GPU round, item 58): SASRT's shadow maps (square 512-2048 depth targets: the "
                    "three 1024x1024 cascades resolved into the 1024x3072 atlas) rendered at two thirds of their size "
                    "(render scale code 1, as Renut's 480p): 0.44 of the shadow fill and of the depth resolves; softer, "
                    "blockier shadow edges. Decided when a target is made: no in-run A/B (compare runs)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_shadow_uncompressed, false, "SASRT/GPU",
                    "deko3d renderer (fifth GPU round, item 59): SASRT's shadow-map depth targets (square 512-2048) made "
                    "without hardware compression: each cascade is drawn, then resolved into the atlas, and a compressed "
                    "depth target is decompressed (a full pass over it) before every read; uncompressed it is read as it "
                    "is. Lossless either way: the same depth, the same pixels. Its draws write more bytes. Decided when a "
                    "target is made: no in-run A/B (compare runs)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_depth_restore_reuse, true, "SASRT/GPU",
                    "deko3d renderer (fifth GPU round, item 60, A/B 150): SASRT restores the same depth resolve twice a "
                    "frame (the light pass's depth, then the composite's: the same 24-bit values, stencil 0), and the "
                    "light pass writes only stencil. The second restore binds the first one's target instead, its stencil "
                    "cleared to 0 (the restore's): the same depth bits and stencil, one full-screen depth write less "
                    "(~0.9 ms). Checked: same resolve (texture, resolves count, signature), that target's depth plane "
                    "not written since its restore, the same format, size and scale")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_cut_take_on_overwrite, false, "SASRT/GPU",
                    "CHANGES PIXELS only if a post pass does not cover its target (fifth GPU round, item 61, A/B 151; needs "
                    "sasrt_gpu_handover_with_smaa): banjo's colour hand-over leaves a resolve in its target's image, and "
                    "the next draw into the target copies it out first (the post chain draws, resolves, and draws into "
                    "the same 1152x544 RGBA16F target again: ~0.74 ms a copy). When that draw is one of SASRT's post "
                    "passes (a listed pixel shader with no discard of its own: no alpha test, no blending, every channel, "
                    "a full-screen quad or grid within a scissor covering the target), the texture keeps the image and the "
                    "target takes another (as a whole clear does): the draw writes every pixel of it anyway")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_cut_gather_pcf, false, "SASRT/GPU",
                    "MAY CHANGE PIXELS at exact texel edges (fifth GPU round, item 62, A/B 152): a pixel shader's four "
                    "fetches of one texture at the same place offset by (+-0.5, +-0.5) texels (the game's shadow filter "
                    "9041AFF6: 8 such groups, 32 fetches of the shadow atlas) through a point sampler read the 2x2 block "
                    "a gather at that place reads: one textureGather instead (constant 976, pass gatherpcf; bit r: fetch "
                    "constant r's sampler is point). The texels picked can differ where a coordinate falls on a texel "
                    "edge (the rounding of the two paths)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_depth_restore_clear_skip, true, "SASRT/GPU",
                    "deko3d renderer (fifth GPU round, item 63, A/B 153; with items 49 and 50): the direct depth restore "
                    "clears the depth to the G-buffer's own clear depth (when that is known and exact in 24 bits: 0 or 1) "
                    "instead of 0, and its shader discards the pixels whose restored depth is that value (the pixels no "
                    "draw covered, the sky): they keep the fast clear, the same depth. Fewer depth writes, and those tiles "
                    "stay compressed for the light pass's depth tests")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_cut_ssao_off, false, "SASRT/GPU",
                    "CHANGES PIXELS (fifth GPU round, item 64, A/B 154): the game's screen-space ambient occlusion "
                    "(pixel shader 92D1F7E40EBB8E86: 8 sample spheres at 576x272, ~0.8 ms a race frame) is not drawn: its "
                    "target is cleared to white instead, the shader's own value for no occlusion (1 - occlusion, alpha 1); "
                    "the blur after it (137003414D593F33) then gives white too. Corners and contacts lose their darkening")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_cut_pcf_half, false, "SASRT/GPU",
                    "CHANGES PIXELS (fifth GPU round, item 65, A/B 155): the scene's shadow filter (pixel shader "
                    "9041AFF62011FC58, ~2 ms a race frame) reads the shadow map at 8 places around the pixel (a rotated "
                    "disc), each a bilinear PCF of 4 taps (32 fetches), and averages the 8: with this cut it averages 4 of "
                    "them (one of each pair the shader builds together), so the other 16 fetches go (constant 977, pass "
                    "pcfhalf). Shadow edges get coarser / noisier; fully lit and fully shadowed pixels stay the same")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_cut_no_aa, false, "SASRT/GPU",
                    "CHANGES PIXELS (fifth GPU round, item 66, A/B 156): no anti-aliasing: banjo's SMAA (edges, weights "
                    "and blend, ~1.4 ms a race frame) is not run after the composite; with sasrt_smaa_replaces_fxaa the "
                    "game's FXAA pass stays a copy of its centre sample, so edges are left aliased")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_cut_shadow_alpha_casters, false, "SASRT/GPU",
                    "CHANGES PIXELS (fifth GPU round, item 67, A/B 157): the shadow maps' alpha-tested casters (pixel "
                    "shader 3ECDED036BF3FFC0 into a square depth target: foliage, fences, crowds; ~0.65 ms a race frame "
                    "of pixel work plus their vertices) are not drawn: those objects cast no shadow")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_shadow_d32f, true, "SASRT/GPU",
                    "deko3d renderer (fifth GPU round, item 68; the round-2 experiment sasrt_gpu_exp_shadow_d32f made an "
                    "item): SASRT's depth is the 20e4 float format, so every depth target is Maxwell's ZF32_X24S8, 8 bytes "
                    "a pixel. The shadow maps (square 512-2048 depth targets: three 1024x1024 cascades a frame) use no "
                    "stencil (their draws' and clears' depth controls have it off), so they are made D32F: the same 32-bit "
                    "float depth in half the bytes for the casters' depth writes, the decompression and the resolves into "
                    "the atlas. A draw or clear that does use stencil on one is logged ([sasrt] stencil on a depth target "
                    "without stencil). Decided when a target is made: no in-run A/B (compare runs)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_skip_copy_back, true, "SASRT/GPU",
                    "deko3d renderer (fifth GPU round, item 69, A/B 159; console run O: sasrt_gpu_diag_copy_back_verify "
                    "drew 5050 of them anyway and compared the target with the texture after: 3.16 G texels, 0 differ). "
                    "SASRT's post chain draws full-screen copies (pixel shaders 50544D63 and "
                    "BA4853E3: one fetch, written out) into its 1152x544 target. When the copy's texture is a whole resolve "
                    "of that same target and the target has not been written since, the copy writes what the target "
                    "already holds: the draw is left out (and a later resolve of the unchanged target into the same "
                    "texture is skipped as before, banjo_renut_resolve_skip)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_cut_far_cascade, false, "SASRT/GPU",
                    "CHANGES PIXELS (fifth GPU round, item 70, A/B 160): SASRT draws three 1024x1024 shadow cascades a "
                    "frame and resolves them into a 1024x3072 atlas (y 0, 1024, 2048). The third (the far one) is not "
                    "drawn: its casters are left out (memory-export draws still run), so its resolve copies the cleared "
                    "map: nothing in the far cascade's range is shadowed")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_cut_far_cascade_half_rate, false, "SASRT/GPU",
                    "CHANGES PIXELS (fifth GPU round, item 71, A/B 161): the far shadow cascade (see item 70) drawn and "
                    "resolved every other frame; on the others its casters are left out and its resolve too, so the atlas "
                    "keeps the frame before's: far shadows move at half the frame rate")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_cut_bloom_off, false, "SASRT/GPU",
                    "CHANGES PIXELS (fifth GPU round, item 72, A/B 162): no bloom (the glow around bright things): the "
                    "bloom chain's 160x68 blurs (0EFBCCD0, 4404297A, 8C086C29, whose result B5642CA8 the composite "
                    "2414CA96 adds; ~0.3 ms a race frame with their resolves) are each a clear of their target to black. "
                    "The 288x136 bright pass stays: the luminance chain (the exposure the CPU reads) starts from it too "
                    "(the post-chain map, run O)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_cut_smaa_low, false, "SASRT/GPU",
                    "CHANGES PIXELS (fifth GPU round, item 73, A/B 163): banjo's SMAA finds edges with SMAA's low preset "
                    "threshold (luma step 0.15 instead of banjo_renut_smaa_threshold's 0.1): fewer pixels are edges, so "
                    "the weights and blending passes do less; softer steps between similar colours stay aliased")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_cut_ssao_half_rate, false, "SASRT/GPU",
                    "CHANGES PIXELS (fifth GPU round, item 74, A/B 164): the SSAO pass (92D1F7E4, 576x272) and its blur "
                    "(13700341) drawn every other frame; on the others both draws and their resolves into the textures "
                    "the composite reads are left out, so the composite uses the frame before's ambient occlusion (~1 ms "
                    "of half-resolution work every other frame; AO lags a frame on moving things)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_cut_shadows_off, false, "SASRT/GPU",
                    "CHANGES PIXELS (fifth GPU round, item 75, A/B 165): no shadows: no caster is drawn into any shadow map "
                    "(square 512-2048 depth targets; memory-export draws still run). The maps keep their clear, so the "
                    "atlas the light pass reads says lit everywhere: the shadow pass (~2.3 ms a race frame) goes; the "
                    "light pass's shadow filter still runs")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_cut_point_lights_off, false, "SASRT/GPU",
                    "CHANGES PIXELS (fifth GPU round, item 76, A/B 166): no point lights. SASRT's light pass draws the sun "
                    "(a stencil volume, then 9041AFF6 with its shadows) and then each point light as two stencil-volume "
                    "draws (vertex shader 98B53A18, no pixel shader) and a light draw (C8053B63, 14C81445, 40BB8EDF, "
                    "453EF879 in the race). The draws into the light target after the sun's are left out until the "
                    "targets change: lamps, glows and the like stop lighting the scene; the sun and the ambient stay")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_shadow_atlas_direct, false, "SASRT/GPU",
                    "deko3d renderer (fifth GPU round, item 77, A/B 167; with item 68): SASRT draws its three shadow "
                    "cascades into one 1024x1024 depth target and resolves each into a slice of a 1024x3072 atlas (y 0, "
                    "1024, 2048): three full copies a frame (~2.1 ms on the console, run U). The atlas is made without "
                    "compression and three D32F depth images are made over its memory, one a slice (the same block-linear "
                    "rows: 128-row tiles, 4 MB a slice); at each cascade's whole clear the target takes the next slice's "
                    "image (the order learnt from the resolves), so the cascade is drawn where the resolve would have "
                    "copied it and the resolve is left out (a barrier for the reads instead). Where the order differs the "
                    "resolve copies as before. The atlas texels are the depth's float bits either way "
                    "(sasrt_gpu_diag_atlas_verify checks it on the GPU). The shadow maps' depth is then uncompressed "
                    "(item 59's cost, +0.6 ms). Off: slower on the console (run W, +0.45 ms: the casters' uncompressed depth "
                    "and the in-place cascades' barriers give back the copies saved)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_rt_restore_candidates, true, "SASRT/RenderThread",
                    "Render thread (render-thread round, RT1, A/B 169): the EDRAM depth restore asks, for every draw with a "
                    "depth target bound whose surfaces were written since (the fast path's check; nearly every draw), which "
                    "RGBA8 colour target over the same EDRAM base and pitch was written after the depth "
                    "(DepthRestoreSourceLocked). That scanned the whole target table twice (to find the depth's own key, "
                    "then every target; ~2.6 % of the render thread in the race, run X). With this key each depth target "
                    "keeps its own few candidates (same base and pitch, colour, one sample, its scale, RGBA8 or BGRA8), "
                    "found again only when a target is built or retired (an epoch of its own): the same answer from the "
                    "same write sequences")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_rt_words_owner_memo, true, "SASRT/RenderThread",
                    "Render thread (render-thread round, RT2, A/B 170): the EDRAM restore copy (A393B1E0, two draws a race "
                    "frame) asks which texture owns the depth-words view its fetch 0 binds (SasrtWordsViewOwnerLocked), "
                    "which scanned every texture's words views (~0.75 % of the render thread in run X: the race has "
                    "thousands of textures). With this key the last answer is kept (the slot and the texture's address) "
                    "and checked first: the texture is looked up by its address and must still hold a words view with "
                    "that slot (a descriptor slot belongs to one view at a time), so the answer is the scan's")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_rt_view_surface_memo, false, "SASRT/RenderThread",
                    "Render thread (render-thread round, RT3, A/B 171): a replayed op's surface bound through an EDRAM "
                    "view (SetSurfaceViewLocked: the destination packet's base and pitch; this game renders its post chain "
                    "at EDRAM base 0 through views) skipped banjo-nx's 64-entry surface memo ('the memo knows no EDRAM "
                    "base') and took GetHostSurfaceSlow every time (~2 % of the render thread with SurfaceRenderScale). "
                    "With this key a colour view is memoised too, keyed by the view's own words (size, surface info, "
                    "format and colour info: the EDRAM base) and marked as a view (a view entry answers only a view "
                    "lookup), in a slot of its own (the VA and the view words hashed). For a target that exists the slow "
                    "path's only effects are the four header words, which a hit sets the same; the surface epoch (targets "
                    "built, re-pointed or retired, the render scale) clears the memo as for the other entries. Depth views "
                    "are left to the slow path (banjo_deko3d_depth24's format can change at a later sighting)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_rt_cached_export_seeds, true, "SASRT/RenderThread",
                    "Render thread (render-thread round, RT5; chosen at start, so no in-run A/B: target 172 does nothing): "
                    "the CPU writes each fresh memexport window's seed (its guest bytes, item 30: ~12 MB a second in the "
                    "race) into the slot's export buffer, which was CPU-uncached memory: memcpy's bulk loop at uncached "
                    "speed was ~2 % of the render thread (run P1's lines). With this key the buffer is CPU-cached (plume: "
                    "an upload buffer with HOST_CACHED, flushed at creation so no older dirty line can land on the GPU's "
                    "results) and each seed's lines are cleaned (dc cvac) right after it is written, before anything is "
                    "submitted. The windows start on 256-byte boundaries, so no line holds two windows; every line a seed "
                    "touches is wholly its own (its last one's padding is no window's): the GPU sees the same bytes. The "
                    "CPU never reads the buffer (readbacks go through a GPU copy)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_cut_ambient_sky, false, "SASRT/GPU",
                    "CHANGES PIXELS where the sky's ambient term shows (sixth GPU round, item 78, A/B 168): SASRT's HDR "
                    "composite draws a full-screen additive pass, pixel shader ED0A8D53 (~1.5 ms a race frame: three "
                    "volume-texture lookups a pixel, 47 registers) with no depth or stencil test, so it shades the sky too "
                    "(~40 % of a race frame's pixels are at the clear depth). With this key it is drawn with the depth "
                    "bounds test excluding the clear depth of the restored scene depth bound to it (known from the depth "
                    "restore: 0 or 1, exact): sky pixels keep what the passes before gave them. The sun's and point lights' "
                    "passes already skip the sky (their stencil test)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_convert_vertex_pass, true, "SASRT/GPU",
                    "deko3d renderer (fifth GPU round, item 53, A/B 143): an exported stream's conversion into vertex format "
                    "(stream_convert_cs, ~45 small dispatches a race frame between an export draw and the draw that reads "
                    "it, ~15 us each: each one switches the 3D engine to compute and back) drawn instead as a point list "
                    "of one vertex per element with the rasterizer off, whose vertex shader (stream_convert_vs) runs the "
                    "same conversion code and stores the same words; the waits around it are the same. The same vertex "
                    "data: the same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_fetch_exp_3d_spec, true, "SASRT/GPU",
                    "deko3d renderer (fifth GPU round, item 52, A/B 142): item 51 for the exponent adjust a 3D or cube fetch "
                    "reads from its own word (texture_indices[1] / [2] bits 20-25): constants 958-965 (3D) and 966-973 "
                    "(cube) for fetch constants 0-7 (pass fetchconv). The race's composite pass (ED0A8D53) reads its 3D "
                    "lookup tables' words this way. Same values: the same pixels")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_gpu_fetch_conversion_spec, true, "SASRT/GPU",
                    "deko3d renderer (fifth GPU round, item 51, A/B 141): a pixel shader's texture fetch applies Xenos' "
                    "signs, gamma and exponent adjust from the draw's words (SharedConstants: sampler bits 13-19, the 2D "
                    "texture word's bits 20-25) for each of the four channels, choosing among the conversions at run time; "
                    "item 3 (sasrt_gpu_plain_fetches) drops the block where a fetch constant has none of them. Here the "
                    "words of fetch constants 0-7 are constants of the draw (950-957, pass fetchconv), so the shader keeps "
                    "only the conversions the draw's texture has, on the channels that have them. The same operations on "
                    "the same values: the same pixels. The race's G-buffer shaders: 238 -> ~120 instructions")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

#if defined(PLUME_DEKO3D)
#include <plume_deko3d.h>
#endif

namespace renut::gpu {
extern uint64_t g_sasrt_sampler_generation;  // render/draw.cpp (BindingEpoch)
}

namespace sasrt::gpu_round {

Latched g_latched;
std::atomic<bool> g_latched_ready{false};
std::atomic<uint64_t> g_counts[kCount][2] = {};

void LatchNow() {
  using banjo::EnhancementActive;
  using banjo::EnhancementGroup;
  Latched l;
#define SASRT_GPU_ROUND_LATCH(name, key, what) l.on[name] = EnhancementActive(EnhancementGroup::kNonCpu, REXCVAR_GET(key));
  SASRT_GPU_ROUND_ITEMS(SASRT_GPU_ROUND_LATCH)
#undef SASRT_GPU_ROUND_LATCH
  g_latched = l;
  g_latched_ready.store(true, std::memory_order_release);
}

uint32_t SamplerCutBits() {
  return (On(kCutMipNearest) ? 1u : 0u) | (On(kCutLodBias) ? 2u : 0u);
}

void ApplyPlume() {
  {  // sasrt-nx (2026-11-09, the cuts 56-57): the draws bind their samplers again when the A/B half changes them
    static uint32_t last = 0;
    const uint32_t now = SamplerCutBits();
    if (now != last) {
      last = now;
      ++renut::gpu::g_sasrt_sampler_generation;
    }
  }
#if defined(PLUME_DEKO3D)
  plume::g_deko3dOptions.preciseDepthResolve = On(kPreciseDepth);
  plume::g_deko3dOptions.decompressMerge = On(kDecompressMerge);
  plume::g_deko3dOptions.readbackMerge = On(kReadbackMerge);
  plume::g_deko3dOptions.dataOnlyInvalidate = On(kDataInvalidate);
  plume::g_deko3dOptions.tiledCache = On(kTiledCache);
  plume::g_deko3dOptions.lazyDepthResolve = On(kLazyDepth);
  plume::g_deko3dOptions.sameTargetsKept = On(kSameTargets);
  plume::g_deko3dOptions.leanBarrierSkip = On(kLeanSkip);
  plume::g_deko3dOptions.freshComputeConstants = On(kSeedLead) || On(kConvertLead) || On(kConvertLeadData);
  plume::g_deko3dOptions.vsInputMask = On(kVsInputMask);  // sasrt-nx (2026-11-08): the third round
  plume::g_deko3dOptions.trackedImageInvalidate = On(kTexDropTracked);
  plume::g_deko3dOptions.trackedTargetWait = On(kTargetWaitTracked);
  plume::g_deko3dOptions.trackedReadWait = On(kReadWaitTracked);
  plume::g_deko3dOptions.expSphStoreBits = uint32_t(REXCVAR_GET(sasrt_gpu_exp_sph_no_global_store));  // an experiment
  plume::Deko3DSetDedicatedTargets(REXCVAR_GET(sasrt_dedicated_targets));  // sasrt-nx (2026-11-09)
  plume::Deko3DSetRegionBestFit(REXCVAR_GET(sasrt_region_best_fit));      // sasrt-nx (2026-11-09 night)
  plume::Deko3DSetImageBestFit(REXCVAR_GET(sasrt_image_best_fit));        // sasrt-nx (2026-11-09 night)
#endif
}

const char *AbName(int target) {
  static const char *const kNames[] = {
#define SASRT_GPU_ROUND_NAME(name, key, what) what " (" #key ")",
      SASRT_GPU_ROUND_ITEMS(SASRT_GPU_ROUND_NAME)
#undef SASRT_GPU_ROUND_NAME
  };
  if (target == kAbRtGroup)  // sasrt-nx (2026-11-09)
    return "the render-thread round's items, all at once (sasrt_rt_*, A/B 200)";
  const int i = target - kAbBase;
  return i >= 0 && i < kCount ? kNames[i] : nullptr;
}

std::string Report() {
  static const char *const kKeys[] = {
#define SASRT_GPU_ROUND_KEY(name, key, what) #key,
      SASRT_GPU_ROUND_ITEMS(SASRT_GPU_ROUND_KEY)
#undef SASRT_GPU_ROUND_KEY
  };
  if (!g_latched_ready.load(std::memory_order_acquire))
    LatchNow();
  std::string text = "[sasrt gpu] GPU round (2026-11-08), in the last 10 s:";
#if defined(PLUME_DEKO3D)
  // plume's items count in its statistics (cumulative): their part since the last report.
  static uint64_t plume_last[128] = {};
  uint64_t plume_now[128] = {};
  for (int i = 0; i < 128; ++i)
    plume_now[i] = plume::GetDeko3DStats().sasrtRound[i].load(std::memory_order_relaxed);
#endif
  for (int i = 0; i < kCount; ++i) {
    uint64_t a = g_counts[i][0].exchange(0, std::memory_order_relaxed);
#if defined(PLUME_DEKO3D)
    if (i < 128) {
      a += plume_now[i] - plume_last[i];
      plume_last[i] = plume_now[i];
    }
#endif
    const uint64_t b = g_counts[i][1].exchange(0, std::memory_order_relaxed);
    text += fmt::format(" {} {}{}{}", kKeys[i], g_latched.on[i] ? "" : "(off) ", a, b ? fmt::format("/{}", b) : "");
    text += i + 1 < kCount ? ',' : '.';
  }
  return text;
}

}  // namespace sasrt::gpu_round
