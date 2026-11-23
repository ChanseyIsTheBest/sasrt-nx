# 2026-11-20: render-thread cost ideas (4-player split screen)

The user (2026-11-20 ~01:40): "come up with 35 ideas in a table to make the render thread cheaper ... implement them
over the 12 hours ... a/b test them do things in a big batch ... after you fully fix the shadow issue with dynamic
resolution on".

Profile: c1120_p4 (rex_profile_307, NRO 00:48, 4 players, CPU 1020 / GPU 460.8 / memory 1600 MHz): 2,737 draws a frame,
render thread 55 ms a frame (~20 us a draw), core 1 at 92 %, 21 % of its samples in the kernel. Busy share by function:
FastDrawLocked 15.0 %, DrawStateLocked 5.6, WholeGeometryTry 5.0, Replay 4.9, PushFloatConstants 4.3,
FindHostTextureBySlotLocked 3.4, QueueCapture 2.9, FillTextures 2.9, PagesClean 2.4, BindStreams 2.3, render_thread Run
2.2, BindTargets 2.1 (scratchpad rt_funcs.py). By category: draw state 26 %, vertex data 19, textures 10, constants 10,
targets/resolves 8, replay 8, deko3d commands 8.

From sasrt_308: 93.5 % of draws take the fast path (~180 full a frame: 100 a pending export window, 54 own exports, 21
chain breaks); 34 % range geometry (580 a frame "written lately"); texture memo "another entry" misses ~1,950/s; the
render thread waits ~1.4-1.5 ms at each same-frame place (4 a frame: ~6 ms); the stream cache at 135.7 MB over its 128 MB
cap (DropReplacedRanges' over-limit walk every frame).

1 % of the render thread ~ 0.55 ms a frame ~ 200 ns a draw. Savings are upper bounds and overlap.

| # | idea | target | mechanism | est. | risk |
|---|---|---|---|---|---|
| 1 | slot -> texture index | textures.cpp:1900, draw.cpp:15584 | a 256-entry direct-mapped slot -> va memo (or an owner array set at slot alloc/retire) for FindHostTextureBySlotLocked on the copy-back path (today a walk of every texture ~13 times a frame) | 2.5-3 % | low |
| 2 | 2-way texture slot memo | draw.cpp:4948-4973 | 2048 sets x 2 ways (same 512 KB): fewer "another entry" misses (each a full BindTextureLocked) | 0.3-0.6 % | low |
| 3 | texture objects for fetch-only slots | command_buffers.cpp:2097, draw.cpp:5471 | SASRT's slots have no header ("0 objects made"): key objects by fetch words + va 0 | 0.5-1 % | med |
| 4 | no texture refill on a target change alone | draw.cpp:12314-12320 | refill only when a kept slot has a hand-over/depth source or samples one of the new targets | 0.3-0.6 % | med |
| 5 | skip bindTextures' txq loop | plume_deko3d_commands.cpp:794-834 | unchanged handles/descriptorEpoch/image set: the size pushes cannot change | 0.2-0.4 % | low |
| 6 | spec-word memo | draw.cpp:12825-12841 | recompute FetchSpecWords / SasrtPlainFetchMask / SasrtClipBit / SasrtSpecWordsOf only when their inputs changed (g_sc_dirty before PushSharedConstants) | 1.5-2 % | low-med |
| 7 | inline key compares | draw.cpp:12834, 12854, 8534 | 80/16-byte std::memcmp (libc calls) -> SameBytes<N> | 0.1-0.3 % | low |
| 8 | special-shader checks per shader change | draw.cpp:12098-12124 | ~12 hash compares + gpu_round::On a fast draw -> a veto byte computed when the shaders change | 0.2-0.4 % | low |
| 9 | latched census switches | stage_census.h:61, banjo_renut_tuning.cpp:1302, 2885 | census::On / host_batch::CensusOn/VerifyOn: out-of-line, thread-safe statics (LDARB) 12-15 times a draw -> inline latched loads | 0.5-1 % | low |
| 10 | hot accessors latched | ultimate.cpp:347-521, banjo_renut_tuning.cpp:2036, 2075, surfaces.cpp:1381, video.cpp:1384 | -fno-threadsafe-statics covers only draw.cpp and command_buffers.cpp; ConstNanFlushOn inside the per-group push loop (draw.cpp:4487), DepthRestoreOn, Clamp7e3On, ExportsHeldOn, VertexReadableCheckOn ... | 0.5-1 % | low |
| 11 | dynamic-state helpers only on change | draw.cpp:12412, 13012, 1174, 13080 | SetUserClipPlane, SetDrawDepthBias (0.7 %), SetSampleMaskLocked, SetLoopConstants only when their packets/targets/g_bound changed | 0.3-0.6 % | low-med |
| 12 | host packets in split screen | draw.cpp:553, 11609, 12041 | banjo_renut_host_packets / A/B 65: neutral in one view; 4 views replay the same state words (try kHostPacketBits 11) | 1-3 % | low |
| 13 | targets memo | draw.cpp:12249-12256 | 8 entries keyed by target words + destination packets + surface epoch (Targets after DropSmallerDepth) | 0.3-0.6 % | low-med |
| 14 | narrower BindTargets rebind test | draw.cpp:12968-12973 | g_layout_epoch moves at every transition: test the draw's own targets' layouts + pending copies + handed flags | 0.3-0.8 % | med |
| 15 | inert / cull-both draws keep the chain | draw.cpp:14317-14331 | a skipped draw breaks the next draw's chain (~1.3k of 3.4k breaks a 10 s): fold its fields into a pending mask | 0.2-0.4 % | med |
| 16 | export-reading draws on the fast path | draw.cpp:11851, 12377-12380 | 1,600 draws/s go the full way (~17 us each); split kFastExportRead by kind | 1-2 % | high |
| 17 | 4-way pipeline cache | draw.cpp:11665, 12862-12874 | ~4k conflicts a 10 s (MakeKey + GetPipelineLocked) | 0.1-0.2 % | low |
| 18 | cleanups | draw.cpp:12608/12611, 12613, 12959, 12119, 12784-12795 | duplicate SetShared(depth_remap), dead SasrtSetRtScale call, repeated kCutTakeOnOverwrite loop, non-static REXCVAR_GET, memexport buffer once a list | ~0.1 % | low |
| 19 | skip PushFloatConstants when nothing is due | draw.cpp:12770-12777 | inline precheck (tracked, no dirty group in summary.groups, unheld 0) | 0.2-0.4 % | low |
| 20 | merge push runs across short gaps | draw.cpp:4476-4501 | runs 1-2 held groups apart: one dkCmdBufPushConstants | 0.2-0.4 % | low |
| 21 | NEON group compare | draw.cpp:4457-4467 | 64-byte group compare in NEON under the register mask | 0.1-0.2 % | low |
| 22 | reuse stream sources on the range fallback | draw.cpp:7629-7646 -> 13041-13044, 8143 | pass WholeGeometryTry's StreamSources to BindStreams and DescribeBoundFetches | 0.4-0.8 % | low |
| 23 | held-export granule bitmap | draw.cpp:6598-6612 (map 1471) | every GetStreamSource does a std::map upper_bound over ~257 held exports: a 64 KB-granule bitmap first | 0.5-1 % | low |
| 24 | DropReplacedRanges throttled over the cap | draw.cpp:16547-16554 | 135.7 MB > 128 MB: a full walk of both caches every frame and stale mesh objects; every 4th frame / only when spans matured, or a 160 MB cap | ~1 % + object hits | low |
| 25 | per-copy versions for whole-copy drops | draw.cpp:2275, 6065, 7274 | g_mesh_gen moves at any erase (25.9k "older generation" misses a 10 s) | 0.3-0.6 % | med |
| 26 | WholeRepeat with exports pending | draw.cpp:7564 | store the export generation and the export-free answer with the repeat | 0.2-0.5 % | low-med |
| 27 | WholeRepeatHit with the recorded index buffer | draw.cpp:7516 | ReplayIndexBuffer() instead of the live guest header (a correctness fix too) | ~0.1 % | low |
| 28 | masked NEON tail in PagesClean | draw.cpp:2049-2092 | the last 1-7 pages in one masked block, not 4 atomic loads a page | 0.3-0.6 % | low |
| 29 | GuestReadablePrefix memo | draw.cpp:10820-10875, sdk xmemory.cpp:2067 | each fill takes the heap's recursive_mutex and walks the page table: cache readable runs under a commit/protect generation | 0.3-0.8 % + waits | low-med |
| 30 | ReplayIndexBuffer's diagnostic read gated | surfaces.cpp:1347-1362 | reads the live guest header every call only to count changes | 0.1-0.2 % | low |
| 31 | no per-fill layout element copy | draw.cpp:8045-8047 | intern the layout's elements per layout hash for the kick | 0.1-0.2 % | low-med |
| 32 | range-fill conversion on core 3 | draw.cpp:10877, 8043-8071 | a core-3 worker converts fills as queued; FlushVertexFillsLocked joins it | 1-1.5 % moved | med-high |
| 33 | ColorAliasesLocked memo | surfaces.cpp:1208-1230, draw.cpp:19256, 19837 | two full g_targets scans per colour resolve (~118 a frame in 4P): per-surface key + alias list per table epoch | 0.6-0.8 % | low-med |
| 34 | unchanged replay overrides skipped | command_buffers.cpp:3376-3377, surfaces.cpp:1391-1395 | same recorded surface block as the previous op: no update; SameBytes | 0.2-0.3 % | low |
| 35 | prefetch the whole ring delta | render_thread.cpp:154-159, queued.cpp:1021 | 4 lines prefetched, the delta averages ~360 bytes (6-7 lines) | 0.2-0.3 % | low |
| 36 | State().mutex held across ready ring items | render_thread.cpp:468-553 | once per run of published items (<= 32), released before waits | 0.2-0.4 % | med |
| 37 | lighter ring item | render_thread.cpp:136-140, 543 | function pointer + inline payload instead of std::function | 0.1-0.3 % | low-med |
| 38 | work during place waits | command_buffers.cpp:5017-5041 | wait in <= 200 us slices; run order-free work between (DropReplacedRanges, ForgetChangingRanges, queued range fills, FlushTextureFillsLocked, ring cleans): ~6 ms a frame | 2-3 % | med |
| 39 | place wait without State().mutex, spin then address wait | command_buffers.cpp:5017-5041, render_thread.cpp:471 | the wait holds State().mutex up to 50 ms; release it, spin 50-100 us, wait on a word | 0.3-0.5 % + no convoy | med |
| 40 | replay a scene recording while it is recorded | command_buffers.cpp:5009-5051 | chunked ops + a published count; replay to the frontier | wait -4-5 ms a frame | high |
| 41 | WholeRepeat ring of 4 | draw.cpp:7473-7537 | the last 4 distinct answers | 0.2-0.4 % | low |
| 42 | CRC32 RenderStateIdLocked | draw.cpp:11558-11562 | 27 serial multiplies -> 3-lane CRC32 | ~0.1 % | low |
| 43 | incremental texture export check | draw.cpp:11884-11937 | re-check only slots whose fetch words changed (same export generation) | 0.2-0.4 % | low-med |
| 44 | deko3d recording worker on core 3 | plume's deko3d calls | a proxy stream (as banjo_renut_record for Vulkan) | 3-5 % net | high |
| 45 | "written lately" streams converted on the GPU | draw.cpp:7019 path | the vertex shader fetches those ranges from guest memory through the address window | 1.5-2.5 % | high |

Correctness notes (the survey): WholeRepeatHit reads the live index-buffer header (draw.cpp:7516) where
WholeGeometryTry uses the recorded one; the same-frame place wait holds State().mutex up to 50 ms (game-thread
DestroyShaderRecord / DestroyVertexDeclarationRecord block meanwhile); DropReplacedRanges' over-limit mode permanently on
in 4P (any whole entry erased staled every mesh object); texture objects never apply in SASRT; the fetch-data keep (A/B
36) never hit; -fno-threadsafe-statics only in draw.cpp and command_buffers.cpp.

## Batch 1 (2026-11-20 04:00-05:00, while the console waited)

Each item is a key in sasrt_gpu_round (`SASRT/RenderThread`, on by default, kInitOnly) with its own in-run A/B target
(banjo_renut_ab_target = 256 + its index) and a count in the 10 s "[sasrt gpu]" line; A/B **401** turns the whole
round off for a half (render thread ms a frame and us a draw in the "[renut A/B]" line).

| A/B | key | idea # | what |
|---|---|---|---|
| 339 | sasrt_rt2_slot_index | 1 | FindHostTextureBySlotLocked: a 256-entry memo by slot, each answer checked as the walk checks it |
| 340 | sasrt_rt2_spec_memo | 6 | FetchSpecWords / SasrtPlainFetchMask / SasrtClipBit / SasrtSpecWordsOf kept while no g_draw_sc line was written (g_sc_dirty_seen, folded in at each push), the shaders, targets (and their colour words), instancing, sampler table and A/B halves are the same; never for exporting vertex shaders. banjo_renut_fast_draw_verify recomputes and logs a difference |
| 341 | sasrt_rt2_drop_throttle | 24 | DropReplacedRanges over the stream cache's limit: every 4th frame |
| 342 | sasrt_rt2_pages_tail | 28 | PagesClean: a range's last 1-7 pages in one masked NEON block |
| 343 | sasrt_rt2_color_alias_memo | 33 | ColorAliasesLocked's list per surface, valid for g_sasrt_table_epoch (bumped by every target built or retired) |
| 344 | sasrt_rt2_repeat_recorded_index | 27, 30 | WholeRepeatHit reads ReplayIndexBuffer (the recorded header); ReplayIndexBuffer's diagnostic live read at one call in 64 |
| 345 | sasrt_rt2_held_export_bitmap | 23 | GetStreamSource looks in g_held_exports only where a 64 KB granule bitmap (a superset, made again when the frame's start drops some) says one may lie |
| 346 | sasrt_rt2_place_wait_unlocked | 39 | the same-frame place's wait lets go of State().mutex (taken again after; the slot's mutex never held across it) |
| 347 | sasrt_rt2_ring_prefetch | 35 | the next ring item's narrowed delta prefetched to six lines |
| 348 | sasrt_rt2_readable_memo | 29 | GuestBytesReadable keeps 64 readable ranges while rex::memory::g_page_access_generation (SDK: raised by every Decommit, Release, Protect, Reset, Restore) is unchanged |

Without a switch (the same answers, no A/B): #8 the cuts' switches tested before the hashes and the bloom list walk in
FastDrawLocked; #9 census::On, host_batch::CensusOn / VerifyOn latched and inline; #10 `-fno-threadsafe-statics` for
ultimate.cpp and backend/render_thread.cpp (every function static there a plain value from a key). Looked at and left:
#11 (plume already drops an unchanged sample mask; the depth bias compares its words), #18 (PushFloatConstants' own
all-held test is the precheck), #20 (GetStreamSource also reads the held exports and a run's stream copies, which the
per-slot memo does not key on), #36 (a ring item's closure is destroyed after it runs, and a destructor taking
State().mutex would deadlock under a held lock).

Batch 1 checks on Ryujinx (2026-11-20 05:10-07:00): a single-player race with banjo_renut_fast_draw_verify and
banjo_renut_persistent_shared_verify (rt2bVerify2): the spec memo answered 146,799 fast draws and computed 35,039
(81 %), every kept answer equal to a fresh one; the verify's only lines the pipeline-pointer notes earlier builds have.
Batch 2's first item, **349 sasrt_rt2_bind_layout_narrow** (#14), counts 0: a layout change comes with an unbound
framebuffer (a resolve ends the render pass), which binds the targets again anyway. **348 sasrt_rt2_readable_memo**
counts 0 too: SASRT's toml has dishonored_renut_vertex_readable_check off, so the check it speeds up never runs (the
profile's GuestReadablePrefix share was the call alone). Both stay (no effect).

## Batch 2 (2026-11-20 07:00-07:30)

| A/B | key | idea # | what |
|---|---|---|---|
| 349 | sasrt_rt2_bind_layout_narrow | 14 | (above: no effect) |
| 350 | sasrt_rt2_texture_memo_two_way | 2 | FillTextures' memo as 2,048 sets of two ways (the same 4,096 entries), the way of an earlier frame replaced; every hit checks the entry's words as before |
| 351 | sasrt_rt2_repeat_ring | 41 | WholeGeometryTry's repeat answer for the last four meshes of a kick |

A dark triangle behind the kart in the Ryujinx races (rt2dCheck) is there with every second-round key off too
(rt2dBase): not this round's (and not seen in the console's shots).

## Console A/B of batches 1-2 (2026-11-20 08:20, c1120_rt2_ab, rt2e, 4 players, A/B 401, 20 s halves)

Render thread time a frame against draws a frame, one slope for both halves (13.0 us a draw): **on 55.0 ms, off
56.6 ms at 2,600 draws (-2.8 %, -1.6 ms; window noise 1.5 ms, the difference's error ~0.9 ms)**. fps 17.3 / 17.6 (the
halves' scenes differ). The spec memo answered 65 % of the fast draws in four players. Kept on.

## The second table (2026-11-20 ~08:30, the user: "Come up with 35 more render thread optimisations")

From rex_profile_314 (the A/B race, rt2e, its map in out/console_runs/c1120_rt2_ab): render thread 18 % in the kernel;
busy: FastDrawLocked 16.0 %, DrawStateLocked 6.3, PushFloatConstants 4.7, Replay 3.9, WholeGeometryTry 3.8,
FillTextures 3.0, QueueCapture's item 2.8, PagesClean 2.7, render_thread Run 1.9, BindTargets 1.8, BindStreams 1.8,
GeometryObjectsHit 1.7, GetHostSurfaceLocked 1.7, PrepareGeometry 1.6, GetStreamSource 1.5, ResolveTargetsLocked 1.5,
FindHostTextureBySlot 1.4 (3.4 before), FastExportReads 1.3, plume setPipeline 1.3, SasrtRestoreCopyLocked 1.2,
ConvertVertices 1.1, bindTextures 1.1, PushSharedConstants 1.0, BindWholeStreams 1.0, drawIndexedInstanced 0.9,
setVertexBuffers 0.8, SetViewport 0.7, DropReplacedRanges 0.7, the stream memo 0.7, FlushVertexFills 0.7, export
conversion 0.7, GatherTargetsWords 0.6, dkCmdBufPushConstants 0.6, PendingExportSlots 0.6, malloc/free 0.6.

| # | idea | target | est. | risk |
|---|---|---|---|---|
| 1 | line tables for the hot files (SASRT_SWITCH_RENDERER_LINES) and a line profile of FastDrawLocked's 16 % | build | enabler | none |
| 2 | host packets in split screen (banjo_renut_host_packets, A/B 65): four views replay the same state words | config | 1-3 % | low |
| 3 | export answers by export generation: FastExportReads, PendingExportSlots, DrawNeedsExportFlush, FindExportedStream (3 % together) | draw.cpp | 1-2 % | med |
| 4 | SasrtRestoreCopyLocked's early out by pixel shader before its work (1.2 % at every draw) | draw.cpp | ~1 % | low |
| 5 | one push path for both stages: VS and PS constants in one call, one census scope | draw.cpp | 0.5-1 % | low |
| 6 | push runs merged across 1-2 held groups (first table #19) | draw.cpp | 0.3 % | low |
| 7 | NEON group compare in PushFloatConstants (first table #21) | draw.cpp | 0.2 % | low |
| 8 | Replay: the next op's state and tags prefetched while this one runs | command_buffers.cpp | 0.5-1 % | low |
| 9 | ApplyState's copy in NEON blocks | command_buffers.cpp | 0.2-0.4 % | low |
| 10 | GeometryObjectsHit: the object's checks in the order that fails first | draw.cpp | 0.3-0.6 % | low |
| 11 | PrepareGeometry: no index range scan for whole-buffer draws | draw.cpp | 0.3-0.8 % | low-med |
| 12 | GetStreamSource memo keyed by the held-export generation and the run's copy set too (a sound version of first #20) | draw.cpp | 0.5 % | med |
| 13 | BindWholeStreams: the vertex buffer views not set again when equal to the bound ones | draw.cpp | 0.3-0.5 % | low |
| 14 | ConvertVertices: NEON paths for the common formats (float3, ubyte4n, half2) | draw.cpp | 0.3-0.6 % | med |
| 15 | texture objects for fetch-only slots (first table #3) | draw.cpp | 0.5-1 % | med |
| 16 | slot headers and texture addresses prefetched with the fetch words (SlotHeader, SlotTextureVa) | draw.cpp | 0.2-0.4 % | low |
| 17 | QueueCapture's item: the DrawCall by reference, its vectors' pointers read once | queued.cpp | 0.5-1 % | low |
| 18 | SetReplaySurfaceOverridesLocked compares a hash of the list first | surfaces.cpp | 0.2-0.3 % | low |
| 19 | PagesClean: a 64 KB summary of the cards (clean granules skip their pages) | draw.cpp | 1-1.5 % | med |
| 20 | PagesClean not called for a copy proven at this flush serial (the kick's proof reused) | draw.cpp | 0.5-1 % | low-med |
| 21 | lighter ring item: function pointer and inline payload, no std::function heap block (first #37) | render_thread.cpp | 0.5-1 % | med |
| 22 | the captures' closures pooled (malloc/free 0.6 %) | queued.cpp | 0.3-0.5 % | low-med |
| 23 | targets memo: 8 entries by target words, packets and epoch (first #13) | draw.cpp | 0.3-0.6 % | low-med |
| 24 | GetHostSurfaceLocked's memo 256 entries and a better hash (1.7 %) | surfaces.cpp | 0.5-1 % | low |
| 25 | ResolveTargetsLocked: the same resolve as last frame's (source, rect, destination) set up from a memo | draw.cpp | 0.5-1 % | med |
| 26 | plume setPipeline: the shaders bound only when they change between pipelines | plume | 0.3-0.6 % | low-med |
| 27 | plume: the DkImageView info per texture kept (ImageInfo::fromImageView at each bind) | plume | 0.3 % | low |
| 28 | plume bindTextures' size-push loop skipped when unchanged (first #5) | plume | 0.2-0.4 % | low |
| 29 | plume: vertex buffer state not bound again when equal | plume | 0.2-0.4 % | low |
| 30 | SetViewport: the plume calls skipped when the viewport and scissor are the bound ones | draw.cpp | 0.3-0.5 % | low |
| 31 | SetDrawDepthBias: the packet read only when the mode control word changed | draw.cpp | 0.2-0.4 % | low |
| 32 | gpu_profile CountDraw / Mark cheaper (a draw counter, the label only when timed) | gpu_profile | 0.3-0.5 % | low |
| 33 | DepthHandOverSampledOn and the other out-of-line banjo accessors latched inline | tuning | 0.3 % | low |
| 34 | FlushVertexFillsLocked / AdvanceStreamCacheFrameLocked's per-kick and per-frame walks trimmed | draw.cpp | 0.3-0.6 % | med |
| 35 | the place waits (18 % kernel): the render thread's order-free frame-start work moved into them (first #38) | command_buffers.cpp | 2-3 % | med-high |

### The second table's items after reading the code (2026-11-20 08:40-09:10; the user: "Do a 35 batch")

Done (each its key, A/B 256 + its index; all at once 402): #4 **sasrt_rt3_words_owner_table** (the restore copy's
words-view owner: a 256-entry table by slot, as #1 of the first table; the 1.2 % was its misses' walks of every
texture, not SasrtRestoreCopyLocked's early out, which tests the pixel shader first already), #24
**sasrt_rt3_surface_memo_256** (GetHostSurfaceLocked's memo 256 entries), #31 **sasrt_rt3_depth_bias_fields** (no
SetDrawDepthBias when its packets' fields are unchanged and the bias is bound), #33 (banjo_renut_tuning.cpp without
thread-safe statics: its ~35 accessors; the A/B list under std::call_once; no key), #1 (SASRT_SWITCH_RENDERER_LINES on
in out/nx-inplace: line tables for a line profile of FastDrawLocked; the code the same). #2 is a key already
(banjo_renut_host_packets): its A/B 65 in the next console run.

Already done by earlier rounds (nothing to gain): #3 (the export answers are kept by export generation and the
recorded extents: PendingExportSlotsMemo, Round 4), #8 (Replay prefetches three ops ahead, the resources two ahead and
the next state chunks), #13 (BindWholeStreams binds through BindHashed, which skips an equal binding), #20 (the proofs
run once an interval: KickHeld / FetchCopyHeld's checked serial), #30 (SetViewport compares with the bound viewport and
scissor), #11 (PrepareGeometry answers repeated index draws from CachedIndexDraw and ranges 16-bit indices in the NEON read already), #5-#7 (the push path:
PushFloatConstants' tracked case pushes only dirty or unheld groups already; a merge saves a call).

Left out: #12 (a stream-source memo must also key the held exports and a run's stream copies, which change per run: the first table's #20), #19 (a 64 KB card summary needs every guest store to write it: game-thread cost), #32 (the per-draw GPU
profile counting is the user's renut_gpu_profile), #35 (using the ~5 ms a frame of place waits, 1.2 ms a place, would
need draws recorded out of order and the scene spliced in before them: one command list and its bound state),
#21-#22 (the capture item's closure holds one pointer: std::function keeps it inline, no heap block; the malloc/free
are elsewhere), #26-#29 (plume: to be looked at with the line profile).

## Console A/B of round 3 (2026-11-20 09:21, c1120_rt3_ab, rt3a, 4 players, targets 402 and 65, 20 s halves)

80 s a side a target (too short for a fit of its own; adjusted by the 13 us a draw slope of the earlier run): 402
(sasrt_rt3_words_owner_table, _surface_memo_256, _depth_bias_fields) about +0.5 ms, neutral within the noise; 65
(banjo_renut_host_packets) about -2.4 ms a frame (-4 %) in four players. rt3a on Ryujinx (rt3aVerify): host packets
answered 95 % of the draws, only the pipeline-pointer notes in the verify.

## The third table (2026-11-20 ~09:45, the user: "another 35 table ... in one big batch")

The table as posted in the chat; what came of it after reading the code:

- Done: #1 **sasrt_rt3_host_packets_split** (host packets while the screen is split, whatever banjo_renut_host_packets;
  the recording makes the keys then), #2 **sasrt_rt3_place_spin** (+ sasrt_rt3_place_spin_us 400: the place wait spins
  on the slot's new `ready` flag before sleeping; State().mutex already let go).
- Already done by earlier rounds: #7-#9 (the export answers: AnyPendingExports first, PendingExportSlotsMemo's granule
  test, the kept answers by export generation), #11 (same_as_kept compares the count first), #12 (CapturedHeaderVa is a
  range test), #14 (DropReplacedRanges returns at once without spans), #20 (the fast path's next-draw prefetches), #22
  and #23 (FindShaderLocked runs on a shader change only; SasrtBakedDeclarationLocked keeps its answers per shader and
  declaration).
- Left: #3-#6, #10, #13, #15-#19, #21, #24-#33 (each 0.1-0.5 % at best by the profile, many in code already tuned by
  banjo / blur rounds), #34-#35 (high risk: not without a verify plan).

## The fourth round: the third table's items left (2026-11-20 13:30-14:10, the user: "do these please and then do a massive ab of render thread stuff")

Where the time is (4P race, run 323 on rt3e: 2,490 draws a frame, 93 % fast, render thread 25 ms of a 33 ms frame;
the instruction-level profile of FastDrawLocked over runs 320-323, scratchpad rt_pcs.py: its 15 % spread thin, no
stretch above 0.5 % of the thread, mostly loads that miss). Full-path draws a frame: export read 93, own exports 53,
chain break 21, whole clears 18, shaders 16.

Done (each its key, A/B 256 + index; all at once 403; "this round and later" as 400-402):

| A/B | key | # | what |
|---|---|---|---|
| 357 | sasrt_rt4_push_runs_merged | 26 | two runs of pushed constant groups one or two groups apart pushed as one (the gap's current device bytes; never over a literal register) |
| 358 | sasrt_rt4_state_id_crc | 25 | RenderStateIdLocked's slot by CRC32C (14 crc32cx) instead of 27 dependent multiplies |
| 359 | sasrt_rt4_pipeline_four_way | 24 | the fast pipeline cache four-way (4,516 conflicts a 10 s with two) |
| 360 | sasrt_rt4_spec_key_skip | 27 | a spec memo hit skips comparing the spec answers with the kept key when it was checked against them and no key was written since (a count of key writes) |
| 361 | sasrt_rt4_stream_memo_two_way | 16 | the stream and index memos two-way (most recent first; Forget clears both ways) |
| 362 | sasrt_rt4_ring_lock_once | 4 | State().mutex kept from one queued draw into the next published one (8 at most, never past the run; place waits and other items as before) |
| 363 | sasrt_rt4_inert_keeps_chain | 28 | an inert or cull-both draw left out keeps the fast path's chain (its fields carried into the next draw) |
| 364 | sasrt_rt4_export_reads_fast | 34 | a draw whose only export reads are host-layout streams found on the GPU stays on the fast path (ConvertExportedStreamsLocked there, as the full path) |

Not done, and why: #3 (a kick's fills are ~50 us, six kicks a frame; a core-3 worker's wake costs 20-50 us), #5
(texture objects: banjo's resource-object machinery, which SASRT's header-less slots do not use; a large build for
0.5 %), #6 (the refill after a target change is a few dozen memo hits a frame), #10 (ApplyState's copies are fixed-size
memcpys GCC keeps inline as NEON pairs), #13 (GatherTargetsWords has side effects: views, the UI redirect, the restore;
its lookups are memoised already: rt3's 256 entries), #15 (the frame-start passes work by events, not walks), #17 (the
upload ring is cleaned by the cleaner thread: proposal 23), #18 (fromImageView is inside libdeko3d: the binds are
already kept by sameTargetsKept), #19 (plume holds barriers pending and merges them), #21 (CountDraw is a counter, the
label made on timed frames only), #29/#30 (answered by the per-slot export answers and the store cards already), #31
(the memexport preparation is the GPU rounds' already), #32 (ContentHash64 is the PMULL CRC; ~230 calls a frame of
540 bytes on average), #33 (draw captures are pooled; the rest has no call site the frame-pointer stacks show), #35
(deko3d recording on a second core: plume's command list writes the command buffer synchronously; a proxy stream
and a second command buffer are days of work).

## Console A/B of rounds 1-4 (2026-11-20 14:34-15:05, rt4a, the user's toml at their clocks 1020 / 460.8 / 1600)

Runs out/console_runs c1120_rt4_ab1-3 (324-326: driving, one cycle each) and c1120_rt4_still (327: four players
standing still on the start line, the user's idea: "4 player race at start not moving at all"; 6 s halves, two
cycles in the race). Render thread us a draw, on vs off; one pair of halves is about +-3-5 % of noise while driving
(the no-op 363 "measured" -2 to -3 %), +-1-2 % standing still.

| A/B | what | still, cycle 2 | still, cycle 3 | driving |
|---|---|---|---|---|
| 400 | rounds 1-4 | -7.8 % | | -15.0 % |
| 401 | rounds 2-4 | -7.5 % | | -12.6 % |
| 402 | rounds 3-4 | -5.2 % | | (+4 %, other scenes) |
| 403 | round 4 | -2.1 % | | -3.2 % |
| 357 | push runs merged | +0.5 % | -0.9 % | -1.1 % |
| 358 | state id CRC | -0.8 % | -2.0 % | -0.3 % |
| 359 | pipeline four-way | -0.7 % | +0.1 % | (+10.8 %: 2,704 vs 3,057 draws a frame) |
| 360 | spec key skip | -2.9 % | +1.2 % | -0.6 % |
| 361 | stream memo two-way | +0.9 % | +1.3 % | +0.3 % |
| 362 | ring lock once | -2.0 % | (+6.1 %) | -5.2 % |
| 364 | export reads fast | -2.6 % | | 0 % |
| 355 | place spin (rt3) | -1.3 % | | -3.7 % |
| 356 | host packets split (rt3) | -0.7 % | | +3.4 % |

Rounds 1-4 together about -8 % a draw (4P, ~3,300 draws a frame: ~4.5 ms a frame of the render thread); round 4 about
-2 to -3 %. Item by item they are at the noise; 361 (two-way memos) leans slightly worse (+0.3, +0.9, +1.3): a
candidate to switch off after a longer still A/B. 363 (inert keeps chain) never applies (0 counts: the skipped draws do
not follow the last drawn one in the chain's numbering).

### The round-4 items standing still, two runs (327 and 328: rt4a / rt4b, 2026-11-20 14:55 and 16:13)

Pairs kept: both halves in the race (2,000+ draws a frame) with draw counts within 10 % (scratchpad still_ab.py);
render thread us a draw, on vs off, mean +- standard error:

| A/B | item | pairs | mean | each |
|---|---|---|---|---|
| 357 | push runs merged | 6 | -0.26 +- 0.42 % | +0.5 -0.9 -1.4 +0.7 -1.2 +0.8 |
| 358 | state id CRC | 5 | -0.78 +- 0.77 % | -0.8 -2.0 +1.9 -0.5 -2.6 |
| 359 | pipeline four-way | 5 | +0.74 +- 0.64 % | -0.7 +0.1 +3.0 +0.2 +1.2 |
| 360 | spec key skip | 5 | +0.09 +- 0.94 % | -2.9 +1.2 +2.7 -0.3 -0.2 |
| 361 | stream memo two-way | 4 | +0.46 +- 0.39 % | +0.9 +1.3 -0.2 -0.2 |
| 362 | ring lock once | 5 | +1.07 +- 1.42 % | -2.0 +6.1 -0.5 +2.2 -0.5 |
| 364 | export reads fast | 5 | -1.16 +- 0.90 % | -2.6 +2.2 -2.8 -1.8 -0.9 |

None alone is significant (the group: -2.1 / -3.2 %). 359 and 361 show no gain and lean worse: OFF by default from
rt4c (sasrt_rt4_pipeline_four_way, sasrt_rt4_stream_memo_two_way false; the code kept). The menus' flash fix
(sasrt_resolve_alias_previous) held on the console in 328: "texture 0784582E (format 32) reads the earlier resolve
destination B5640C28 (1152x544) of its page, not the latest B5640DA8 (format 6)", no "[flash]" line.

## Before and after, directly (2026-11-20 18:47-19:03, 4 players standing still, the user's toml and clocks)

| build | fps | render thread ms a frame | draws a frame | us a draw | GPU ms |
|---|---|---|---|---|---|
| the user's NRO (11-19, PGO trained on its own code) | 15.66 | 60.55 | 3,457 | 17.57 | 36.66 |
| rt4d (rounds 2-4, flash fix, copies) | 15.35 | 61.40 | 3,391 | 18.22 (+3.7 %) | 36.97 |

(out/console_runs c1120_cmp_user = 330, c1120_cmp_rt4d = 331; scratchpad cmp_runs.py.) rt4d is not faster than the user's
build, though the in-run A/B of the same rounds says -8 %. The reason: the profile in pgo-inplace/ is 11-19 14:30's,
trained on the code the user's NRO was built from; rounds 2-4 changed the render thread's hottest functions
(FastDrawLocked, DrawStateLocked, PushFloatConstants, FillTextures, Replay ...), and with -Wno-coverage-mismatch GCC
compiles each changed function with no profile at all: no hot/cold split, no branch weights. The in-run A/B runs both
halves in the same binary, so it sees the rounds' own gain; a new build sees it only with a profile of its own code.
Next: a PGO cycle (pgo_cycle.ps1 -Step generate -InPlace, one 4P training race, -Step use), then the same comparison.

## After a fresh PGO cycle (2026-11-20 19:06-20:13)

pgo_cycle -Step generate -InPlace (19:19), one 4P training race on the console (stream sasrt_pgo_32, 19:28; the one
merged: "1 session(s) merged into 569 file(s)", 0 mismatches; the old profile kept as pgo_20261120_193006), -Step use:
rt4e (round 4, 359/361 off, the menus' flash fix, the 12 new copies). Ryujinx race check clean (verifies as the
baseline). Standing still in 4P at the user's clocks, bracketed by two runs of the user's 11-19 NRO:

| build | fps | render thread ms a frame | us a draw | GPU ms |
|---|---|---|---|---|
| the user's NRO (330, 18:47) | 15.66 | 60.55 | 17.57 | 36.66 |
| the user's NRO (334, 20:06) | 15.45 | 60.37 | 18.00 | 36.87 |
| rt4e (333, 19:59) | 16.73 | 53.08 | 15.99 | 36.57 |

About -10 % a draw, -12 % render thread a frame, +7-8 % fps against the user's build; the GPU unchanged. Lesson: a round
is worth nothing in a build until the profile is trained on its code (pgo_cycle after every render-thread round).

## Round 5: banjo-nx's cycles 2-4 findings tested in SASRT (2026-11-21 17:50-19:15)

banjo-nx sent its render-thread A/B results (its docs/render-thread-for-ports.md): three Replay prefetches measured as
costing in N&B's town, kick submits as a per-game trade, cached command memory as a GPU win. Ported as keys with the
base's A/B numbers (build rt5a, out/console_runs/c1121_rt5_build/, the 11-20 PGO profile):

- 174 `banjo_renut_replay_shader_behind`: Replay's PrefetchShaderBehind (default on, as before).
- 175 `banjo_renut_replay_copy_prefetch`: ApplyResources' copy and card prefetch (default on, as before).
- 56 `banjo_renut_replay_object_prefetch`: PrefetchResourceObjects, newly keyed (default on, as before).
- 179: the kick submits' off half (the frame at the present).
- 173 `banjo_deko3d_cached_commands`: plume's CPU-cached command memory (banjo-nx 849e7a3f, without its doubled
  `while`; default off). On for the whole run; libdeko3d's layout check never tripped.

Console, the user's clocks and toml, 4 players standing still (only ~3 min of each race is the still start: the race ends
by itself ~5 min in), 5 races (runs 340-344; 5 s then 4 s halves), pairs with >= 3,000 draws a frame, draw counts
within 10 % and < 30 us a draw; per-pair medians (out/console_runs/c1121_rt5_still2/ab_all.txt, scratchpad ab_med.py):

| A/B | item | render thread a draw (on vs off) | GPU a draw | all threads' CPU a draw | fps |
|---|---|---|---|---|---|
| 174 | PrefetchShaderBehind | -0.35 % (on higher 7/20) | -0.90 % | -1.17 % | -1.05 % |
| 175 | copy and card prefetch | -0.06 % (8/19) | +0.32 % | -0.52 % | -0.38 % |
| 56 | resource objects' prefetch | -0.06 % (10/22) | -1.55 % | +0.23 % | -0.82 % |
| 173 | cached command memory | -0.24 % (7/19) | +0.03 % | -0.25 % | +0.18 % |
| 179 | kick submits | **+1.28 %** (12/18, se 0.47) | +0.55 % | **-1.08 %** (on higher 1/18) | +0.23 % |

None of banjo-nx's three prefetch costs shows in SASRT (all within noise, if anything on is faster); cached command
memory does nothing here. Kick submits cost the render thread ~1.3 % a draw, as in N&B, but the other threads' CPU drops
~1 % and fps is unchanged; they buy input latency. **No default changed.** The keys and A/B targets stay in the source
(the old behaviour by default); the changed Replay means the next delivered build needs its PGO cycle as usual.

## Base port 251 in SASRT: banjo-nx's core-3 command stage and render-thread cycles 1-4 (2026-11-22)

The user (2026-11-21): "later tonight rr6 will send you ultimate base render thread improvements please use them". RR6
sent the base's port 251 (D:\renut-ultimate\tools\ports\p251_command_stage.patch; banjo-nx's N&B console run: render
thread -14.9 % a draw, fps +6.4 %). Merged into sasrt-nx (backups out/console_runs/c1122_p251/src_before; round 5's own
versions of the same items reverted first: the base has them, with its defaults):
- 21 hunks fitted by hand: `g_ab_off_plain` added (the base's plain copy of the A/B word); the base's SpecKeep in
  FastDrawLocked (A/B 172) left out (SASRT keeps its own spec memo, sasrt_rt2_spec_memo); every direct plume list call in
  draw.cpp through the stage's wrappers (record::PushUniform, BindUniform, SetSharedWords, SharedLinesWritten, and
  SASRT's own FlushL2 x9 and DiscardNextDraw); SASRT's depth-bounds sky cut (off by default) not on the stage's proxy; the
  staged submit's draw count is SASRT's submit_frame_draws. The recorder overrides all 39 RenderCommandList virtuals.
- Defaults now (the base's): `banjo_deko3d_command_stage` on (Switch, 4-core mode), `banjo_deko3d_kick_submit` OFF on
  the Switch (SASRT kept kicks on for latency before: an A/B 179 with the stage on the console decides),
  the Replay prefetches 174/175/56 off (noise in SASRT's round 5), cached commands with the stage on.
- Build `sasrt_p251a` (out/console_runs/c1122_p251), warning-free in the merged files.
- Ryujinx: run p251stage (the stage forced on any core, `banjo_deko3d_command_stage_verify`): every list through the
  stage (0 direct), 100,000+ shared-constant copies checked a 10 s, 0 differ; run p251default (the stage off: no 4-core
  mode in Ryujinx): the race at 13-22 fps, no faults.
- Next: a PGO cycle (the training race is a console one) and the console's A/B of the stage (182) and kicks (179), when
  the user allows the console.
