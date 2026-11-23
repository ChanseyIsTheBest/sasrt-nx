# sasrt-nx (2026-11-12, batch D6): headroom in new render-target blocks. Run abC2's slow-frame image-memory lines: a
# resolution step's frame (65-110 ms) is almost all new blocks made (up to 24 per step, ~3 ms each: the cache had no
# block of the new, slightly bigger size); destroying and the retired collect cost nothing now. A new dedicated block is
# made 1/8 bigger than its first image needs (the image uses its start, the tail stays the chunk's free space, which no
# other image takes: dedicated chunks are skipped by the shared search), so the next step up (~3 %) fits it; the cache
# then takes blocks up to (1 + (1 + headroom) / 8) times a request, so a step down still finds the bigger ones. Memory
# only: the same images, the same pixels. Key sasrt_target_block_headroom_8ths (0: as before).
R = 'D:/sonic transformed/sasrt-nx/'


def patch(rel, edits, mark):
    p = R + rel
    b = open(p, 'rb').read()
    crlf = b'\r\n' in b
    s = b.decode('utf-8').replace('\r\n', '\n')
    if mark in s:
        print('already patched:', rel, '(' + mark + ')')
        return
    for o, n in edits:
        assert s.count(o) == 1, (rel, o[:90], s.count(o))
        s = s.replace(o, n)
    open(p, 'wb').write((s.replace('\n', '\r\n') if crlf else s).encode('utf-8'))
    print('patched:', rel, '(' + mark + ')')


patch('app/thirdparty/plume/plume_deko3d.h', [
    ('''    void Deko3DSetTargetBlockCacheMb(uint32_t mb);
''', '''    void Deko3DSetTargetBlockCacheMb(uint32_t mb);
    // sasrt-nx (2026-11-12, batch D6): a new dedicated target block 'eighths' / 8 bigger than its image (the next
    // resolution step up fits it), and the cache takes blocks up to (1 + (1 + eighths) / 8) times a request. 0: as before.
    void Deko3DSetTargetBlockHeadroom(uint32_t eighths);
'''),
], 'batch D6')
patch('app/thirdparty/plume/plume_deko3d.cpp', [
    ('''    void Deko3DSetTargetBlockCacheMb(uint32_t mb) { g_targetCacheCap.store(uint64_t(mb) << 20, std::memory_order_relaxed); }''',
     '''    void Deko3DSetTargetBlockCacheMb(uint32_t mb) { g_targetCacheCap.store(uint64_t(mb) << 20, std::memory_order_relaxed); }
    static std::atomic<uint32_t> g_targetHeadroom8ths{0};  // sasrt-nx (2026-11-12, batch D6)
    void Deko3DSetTargetBlockHeadroom(uint32_t eighths) {
        g_targetHeadroom8ths.store(eighths > 8 ? 8 : eighths, std::memory_order_relaxed);
    }'''),
    ('''        // the smallest block of the size or up to an eighth bigger
        const uint64_t most = uint64_t(size) + size / 8;''', '''        // the smallest block of the size or up to an eighth bigger (sasrt-nx 2026-11-12, batch D6: plus the headroom new
        // blocks are made with, so a step down still takes the bigger blocks a step up made)
        const uint64_t most = uint64_t(size) + uint64_t(size) * (1 + g_targetHeadroom8ths.load(std::memory_order_relaxed)) / 8;'''),
    ('''            t_inImageAlloc = true;
            if (!block)
                block = makeBlock(own, DkMemBlockFlags_GpuCached | DkMemBlockFlags_Image, "render target (own chunk)");''',
     '''            t_inImageAlloc = true;
            // sasrt-nx (2026-11-12, batch D6): a new block with headroom (the image takes its start; the tail stays free in
            // this dedicated chunk, which the shared search skips)
            if (!block) {
                if (const uint32_t h = g_targetHeadroom8ths.load(std::memory_order_relaxed))
                    own = alignUp(uint32_t(std::min<uint64_t>(uint64_t(own) + uint64_t(own) * h / 8, 0xFFFF0000u)),
                                  DK_MEMBLOCK_ALIGNMENT);
                block = makeBlock(own, DkMemBlockFlags_GpuCached | DkMemBlockFlags_Image, "render target (own chunk)");
            }'''),
], 'batch D6')
patch('app/src/renut_engine/gpu/sasrt_gpu_round.cpp', [
    ('''REXCVAR_DEFINE_BOOL(sasrt_dedicated_targets, true, "SASRT/GPU",''', '''// sasrt-nx (2026-11-12, batch D6; run abC2: a step's frame was almost all new blocks, up to 24 at ~3 ms)
REXCVAR_DEFINE_INT32(sasrt_target_block_headroom_8ths, 1, "SASRT/GPU",
                     "A new render-target memory block is made this many eighths bigger than its image, so the next "
                     "resolution step up reuses it from the block cache instead of making a new one. 0: exact size")
    .range(0, 8)
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_dedicated_targets, true, "SASRT/GPU",'''),
    ('''  plume::Deko3DSetTargetBlockCacheMb(uint32_t(REXCVAR_GET(sasrt_target_block_cache_mb)));  // sasrt-nx (2026-11-11)''',
     '''  plume::Deko3DSetTargetBlockCacheMb(uint32_t(REXCVAR_GET(sasrt_target_block_cache_mb)));  // sasrt-nx (2026-11-11)
  plume::Deko3DSetTargetBlockHeadroom(uint32_t(REXCVAR_GET(sasrt_target_block_headroom_8ths)));  // batch D6'''),
], 'batch D6')
print('batchD2: done')
