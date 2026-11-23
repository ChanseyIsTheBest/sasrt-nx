# sasrt-nx (2026-11-11 ~15:40, the stutter hunt, run slow2): a dynamic-resolution step cost one render-thread frame of
# 80-130 ms (16 targets built in ~40 ms, 17 resolve textures made in ~40 ms: each a dedicated deko3d memory block, an
# nvmap of its own and four GPU mappings, ~2.5 ms) and one or two of ~60 ms after it (the old code's blocks destroyed
# once the GPU let them go). 55 of the race's 60 frames over 60 ms followed a step.
# The fix: a dedicated target chunk that empties keeps its block in a capped cache instead of destroying it; a new
# dedicated target takes a cached block of its size or up to an eighth bigger (the smallest), else makes one. The
# cache is given back with the image heap's empty chunks (the governor's low mark, a block that could not be made) and
# counts as free memory for the governor. A reused block holds whatever its last target left, as the shared image
# chunks' freed ranges always have (a new colour target is cleared by BuildTarget; a resolve writes its destination).
# Idempotent; asserts every anchor once.
R = 'D:/sonic transformed/sasrt-nx/app/'
MARK = 'Deko3DSetTargetBlockCacheMb'


def patch(path, edits, mark=MARK):
    b = open(R + path, 'rb').read()
    crlf = b'\r\n' in b
    s = b.decode('utf-8').replace('\r\n', '\n')
    if mark in s:
        print('already patched:', path)
        return
    for old, new in edits:
        assert s.count(old) == 1, (path, old[:80], s.count(old))
        s = s.replace(old, new)
    open(R + path, 'wb').write((s.replace('\n', '\r\n') if crlf else s).encode('utf-8'))
    print('patched:', path)


patch('thirdparty/plume/plume_deko3d.h', [
    ('''        std::mutex heapMutex;
        std::vector<Chunk> chunks;
''', '''        std::mutex heapMutex;
        std::vector<Chunk> chunks;
        // sasrt-nx (2026-11-11, Deko3DSetTargetBlockCacheMb): emptied dedicated targets' blocks kept for the next
        // targets (heapMutex), oldest first.
        struct CachedBlock {
            DkMemBlock block = nullptr;
            uint32_t size = 0;
        };
        std::vector<CachedBlock> targetCache;
        uint64_t targetCacheBytes = 0;
        void cacheTargetBlockLocked(DkMemBlock block, uint32_t size);
        DkMemBlock takeCachedTargetBlockLocked(uint32_t size, uint32_t &blockSize);
        uint64_t releaseTargetCacheLocked();
'''),
    ('''    void Deko3DSetDedicatedTargets(bool on);
    uint64_t Deko3DReleaseEmptyImageChunks();''', '''    void Deko3DSetDedicatedTargets(bool on);
    uint64_t Deko3DReleaseEmptyImageChunks();
    // sasrt-nx (2026-11-11, the stutter hunt: a dynamic-resolution step made ~33 dedicated blocks in one frame, ~2.5 ms
    // each, and destroyed the old ones two frames later): an emptied dedicated target's block stays, up to this many
    // MB in all, for the next target of its size or up to an eighth smaller; given back with the empty image chunks
    // (Deko3DReleaseEmptyImageChunks: the governor's low mark, a block that could not be made). 0: off (destroyed at
    // once, as before).
    void Deko3DSetTargetBlockCacheMb(uint32_t mb);
    struct Deko3DTargetCacheInfo {
        uint64_t bytes = 0, hits = 0, misses = 0, kept = 0, evicted = 0, released = 0;
        uint32_t blocks = 0;
    };
    void Deko3DTargetCacheFigures(Deko3DTargetCacheInfo &out);'''),
])

patch('thirdparty/plume/plume_deko3d.cpp', [
    ('''    void Deko3DSetDedicatedTargets(bool on) { g_dedicatedTargets.store(on, std::memory_order_relaxed); }
''', '''    void Deko3DSetDedicatedTargets(bool on) { g_dedicatedTargets.store(on, std::memory_order_relaxed); }

    // sasrt-nx (2026-11-11, Deko3DSetTargetBlockCacheMb)
    static std::atomic<uint64_t> g_targetCacheCap{0};
    static std::atomic<uint64_t> g_targetCacheBytesNow{0}, g_targetCacheHits{0}, g_targetCacheMisses{0},
        g_targetCacheKept{0}, g_targetCacheEvicted{0}, g_targetCacheReleased{0};
    static std::atomic<uint32_t> g_targetCacheBlocks{0};
    void Deko3DSetTargetBlockCacheMb(uint32_t mb) { g_targetCacheCap.store(uint64_t(mb) << 20, std::memory_order_relaxed); }
    void Deko3DTargetCacheFigures(Deko3DTargetCacheInfo &out) {
        out.bytes = g_targetCacheBytesNow.load(std::memory_order_relaxed);
        out.blocks = g_targetCacheBlocks.load(std::memory_order_relaxed);
        out.hits = g_targetCacheHits.load(std::memory_order_relaxed);
        out.misses = g_targetCacheMisses.load(std::memory_order_relaxed);
        out.kept = g_targetCacheKept.load(std::memory_order_relaxed);
        out.evicted = g_targetCacheEvicted.load(std::memory_order_relaxed);
        out.released = g_targetCacheReleased.load(std::memory_order_relaxed);
    }

    void Deko3DDevice::cacheTargetBlockLocked(DkMemBlock block, uint32_t size) {
        const uint64_t cap = g_targetCacheCap.load(std::memory_order_relaxed);
        if (!cap || size > cap) {
            destroyBlock(block);
            return;
        }
        targetCache.push_back({block, size});
        targetCacheBytes += size;
        g_targetCacheKept.fetch_add(1, std::memory_order_relaxed);
        // over the cap: the oldest go
        size_t drop = 0;
        while (targetCacheBytes > cap && drop < targetCache.size()) {
            destroyBlock(targetCache[drop].block);
            targetCacheBytes -= targetCache[drop].size;
            ++drop;
        }
        if (drop) {
            targetCache.erase(targetCache.begin(), targetCache.begin() + drop);
            g_targetCacheEvicted.fetch_add(drop, std::memory_order_relaxed);
        }
        g_targetCacheBytesNow.store(targetCacheBytes, std::memory_order_relaxed);
        g_targetCacheBlocks.store(uint32_t(targetCache.size()), std::memory_order_relaxed);
    }

    DkMemBlock Deko3DDevice::takeCachedTargetBlockLocked(uint32_t size, uint32_t &blockSize) {
        if (targetCache.empty()) {
            g_targetCacheMisses.fetch_add(1, std::memory_order_relaxed);
            return nullptr;
        }
        // the smallest block of the size or up to an eighth bigger
        const uint64_t most = uint64_t(size) + size / 8;
        size_t best = SIZE_MAX;
        for (size_t i = 0; i < targetCache.size(); i++) {
            const uint32_t s = targetCache[i].size;
            if (s >= size && s <= most && (best == SIZE_MAX || s < targetCache[best].size))
                best = i;
        }
        if (best == SIZE_MAX) {
            g_targetCacheMisses.fetch_add(1, std::memory_order_relaxed);
            return nullptr;
        }
        const CachedBlock taken = targetCache[best];
        targetCache.erase(targetCache.begin() + best);
        targetCacheBytes -= taken.size;
        g_targetCacheHits.fetch_add(1, std::memory_order_relaxed);
        g_targetCacheBytesNow.store(targetCacheBytes, std::memory_order_relaxed);
        g_targetCacheBlocks.store(uint32_t(targetCache.size()), std::memory_order_relaxed);
        blockSize = taken.size;
        return taken.block;
    }

    uint64_t Deko3DDevice::releaseTargetCacheLocked() {
        uint64_t freed = 0;
        for (const CachedBlock &c : targetCache) {
            destroyBlock(c.block);
            freed += c.size;
        }
        if (!targetCache.empty())
            g_targetCacheReleased.fetch_add(targetCache.size(), std::memory_order_relaxed);
        targetCache.clear();
        targetCacheBytes = 0;
        g_targetCacheBytesNow.store(0, std::memory_order_relaxed);
        g_targetCacheBlocks.store(0, std::memory_order_relaxed);
        return freed;
    }
'''),
    # The governor's and the failure paths' release takes the cache too.
    ('''    uint64_t Deko3DDevice::releaseEmptyChunksLocked() {
        uint64_t freed = 0;''', '''    uint64_t Deko3DDevice::releaseEmptyChunksLocked() {
        uint64_t freed = releaseTargetCacheLocked();  // sasrt-nx (2026-11-11, Deko3DSetTargetBlockCacheMb)'''),
    # A dedicated target: a cached block first.
    ('''            const uint32_t own = alignUp(size + alignment, DK_MEMBLOCK_ALIGNMENT);
            t_inImageAlloc = true;
            DkMemBlock block = makeBlock(own, DkMemBlockFlags_GpuCached | DkMemBlockFlags_Image, "render target (own chunk)");
            if (!block) {''', '''            uint32_t own = alignUp(size + alignment, DK_MEMBLOCK_ALIGNMENT);
            // sasrt-nx (2026-11-11, Deko3DSetTargetBlockCacheMb): a kept block of the size (or a little bigger) first
            uint32_t cachedSize = 0;
            DkMemBlock block = takeCachedTargetBlockLocked(own, cachedSize);
            if (block)
                own = cachedSize;
            t_inImageAlloc = true;
            if (!block)
                block = makeBlock(own, DkMemBlockFlags_GpuCached | DkMemBlockFlags_Image, "render target (own chunk)");
            if (!block) {'''),
    # An emptied dedicated chunk: its block to the cache, not destroyed.
    ('''                    if (c.dedicated && c.block && c.freeList.size() == 1 && c.freeList[0].first == 0 &&
                        c.freeList[0].second == c.size) {
                        destroyBlock(c.block);''', '''                    if (c.dedicated && c.block && c.freeList.size() == 1 && c.freeList[0].first == 0 &&
                        c.freeList[0].second == c.size) {
                        cacheTargetBlockLocked(c.block, c.size);  // sasrt-nx (2026-11-11): kept for the next target'''),
])

# The key, and the governor's room counting the cache as free; the memory line gets the cache's figures.
patch('src/renut_engine/gpu/sasrt_gpu_round.cpp', [
    ('''REXCVAR_DEFINE_BOOL(sasrt_dedicated_targets, true, "SASRT/GPU",''', '''// sasrt-nx (2026-11-11, the stutter hunt, run slow2: 55 of the race's 60 frames over 60 ms followed a dynamic-resolution
// step, each step ~33 dedicated blocks made in one frame and the old ones destroyed two frames later). plume_deko3d.h,
// Deko3DSetTargetBlockCacheMb.
REXCVAR_DEFINE_INT32(sasrt_target_block_cache_mb, 160, "SASRT/GPU",
                     "MB of emptied render-target memory blocks kept for the next targets (a resolution step's new set "
                     "takes the last set's blocks instead of making ~33 new ones in one frame); given back at the memory "
                     "governor's low mark and when a block cannot be made. 0: off")
    .range(0, 1024)
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_dedicated_targets, true, "SASRT/GPU",'''),
    ('''  plume::Deko3DSetDedicatedTargets(REXCVAR_GET(sasrt_dedicated_targets));  // sasrt-nx (2026-11-09)''',
     '''  plume::Deko3DSetDedicatedTargets(REXCVAR_GET(sasrt_dedicated_targets));  // sasrt-nx (2026-11-09)
  plume::Deko3DSetTargetBlockCacheMb(uint32_t(REXCVAR_GET(sasrt_target_block_cache_mb)));  // sasrt-nx (2026-11-11)'''),
], mark='Deko3DSetTargetBlockCacheMb')

patch('src/renut_engine/gpu/render/surfaces.cpp', [
    ('''    const uint64_t heap = plume::Deko3DHeapRoomBytes();
    uint64_t room = heap + (region.on ? uint64_t(region.freeBytes) : 0);''', '''    const uint64_t heap = plume::Deko3DHeapRoomBytes();
    uint64_t room = heap + (region.on ? uint64_t(region.freeBytes) : 0);
    {  // sasrt-nx (2026-11-11, sasrt_target_block_cache_mb): the kept target blocks are given back at the low mark
      plume::Deko3DTargetCacheInfo cache;
      plume::Deko3DTargetCacheFigures(cache);
      room += cache.bytes;
    }'''),
], mark='sasrt_target_block_cache_mb')

patch('src/renut_engine/gpu/backend/memory_report.cpp', [
    ('''                r.growths, r.givebacks, Mb(r.givenBack), r.refused);
  }''', '''                r.growths, r.givebacks, Mb(r.givenBack), r.refused);
    // sasrt-nx (2026-11-11, sasrt_target_block_cache_mb)
    plume::Deko3DTargetCacheInfo c;
    plume::Deko3DTargetCacheFigures(c);
    RGPU_INFO("Memory: kept target blocks {} ({:.0f} MB); so far {} targets took one, {} made a new one, {} kept, {} "
              "dropped over the cap, {} given back (sasrt_target_block_cache_mb)",
              c.blocks, Mb(c.bytes), c.hits, c.misses, c.kept, c.evicted, c.released);
  }'''),
], mark='sasrt_target_block_cache_mb')
print('target_block_cache: done')
