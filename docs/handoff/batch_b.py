# sasrt-nx (2026-11-11 ~22:40, the 12 h round, batch B; the user: large batches). Exact items, one PGO cycle:
#  B1 the SDK's OBJECT libraries (rexaudio, rexcore, rexfilesystem, rexinput, rexui) in the Switch LTO and PGO (Blur's
#     finding: their objects are compiled with their own options, so they had neither), with -fno-lto on the two files
#     that define --wrap functions (threading_switch.cpp, switch_perf.cpp) and exception_handler_switch.cpp's `_start`
#     declared as the variable the other users declare (lto1 refuses a function and a variable of one name);
#  B2 the render-target block cache 160 -> 320 MB (cache1/opt1: 172 kept blocks dropped over the cap, 263 targets made
#     a new block: the remaining step misses);
#  B3 CaptureDelta (SlRenderer 10.7 %): with the capture marks, only the marked chunks are visited (the set bits, in
#     the list's ascending order) instead of all ~77 list entries each tested for its mark (the skip loop was 16 % of the
#     function's samples), and the compared-chunk count is kept in a local (one store a delta, not one a chunk).
# Idempotent; asserts every anchor once.
R = 'D:/sonic transformed/sasrt-nx/'


def patch(rel, edits, mark):
    p = R + rel
    b = open(p, 'rb').read()
    crlf = b'\r\n' in b
    s = b.decode('utf-8').replace('\r\n', '\n')
    if mark in s:
        print('already patched:', rel)
        return
    for o, n in edits:
        assert s.count(o) == 1, (rel, o[:80], s.count(o))
        s = s.replace(o, n)
    open(p, 'wb').write((s.replace('\n', '\r\n') if crlf else s).encode('utf-8'))
    print('patched:', rel)


patch('app/CMakeLists.txt', [
    ('''    if(SASRT_SWITCH_SDK_OPT AND REXGLUE_OUTPUT_IN_BUILD)
        set(_sasrt_sdk_opt_targets rexruntime libavcodec libavutil)
    endif()''', '''    if(SASRT_SWITCH_SDK_OPT AND REXGLUE_OUTPUT_IN_BUILD)
        set(_sasrt_sdk_opt_targets rexruntime libavcodec libavutil)
        # sasrt-nx (2026-11-11, batch B1; Blur's finding): the SDK's OBJECT libraries are compiled with their own options,
        # so they had no LTO and no PGO (rexaudio's XMA context, the kernel's core, the file system, input, the UI and
        # the profiler). In now; the two files that define --wrap functions stay out of LTO (the linker must see their
        # __wrap_ symbols as ordinary definitions).
        option(SASRT_SWITCH_SDK_OBJECT_OPT "The SDK's OBJECT libraries in the Switch LTO and PGO too" ON)
        if(SASRT_SWITCH_SDK_OBJECT_OPT)
            list(APPEND _sasrt_sdk_opt_targets rexaudio rexcore rexfilesystem rexinput rexui)
            set(_sasrt_wrap_sources
                "${CMAKE_CURRENT_SOURCE_DIR}/../sdk/src/core/threading_switch.cpp"
                "${CMAKE_CURRENT_SOURCE_DIR}/../sdk/src/ui/switch_perf.cpp")
        endif()
    endif()'''),
    ('''        target_link_options(sasrt PRIVATE ${_sasrt_lto_link})
        message(STATUS "sasrt: Switch LTO on''', '''        target_link_options(sasrt PRIVATE ${_sasrt_lto_link})
        # sasrt-nx (2026-11-11, batch B1): the --wrap definitions out of LTO
        if(_sasrt_wrap_sources)
            set_property(SOURCE ${_sasrt_wrap_sources} TARGET_DIRECTORY rexcore rexui APPEND PROPERTY COMPILE_OPTIONS -fno-lto)
        endif()
        message(STATUS "sasrt: Switch LTO on'''),
], 'SASRT_SWITCH_SDK_OBJECT_OPT')

patch('sdk/src/core/exception_handler_switch.cpp', [
    ('''extern "C" void _start(void);''',
     '''// sasrt-nx (2026-11-11, batch B1): a char, as switch_code_blocks.cpp declares it (only its address is taken); with
// both in one LTO link, lto1 refuses a function and a variable of the same name.
extern "C" char _start;'''),
], 'batch B1): a char')

patch('app/src/renut_engine/gpu/sasrt_gpu_round.cpp', [
    ('''REXCVAR_DEFINE_INT32(sasrt_target_block_cache_mb, 160, "SASRT/GPU",''',
     '''// (2026-11-11 batch B2: 160 -> 320 MB; cache1 / opt1 dropped 172 kept blocks over the cap, and 263 targets made a block)
REXCVAR_DEFINE_INT32(sasrt_target_block_cache_mb, 320, "SASRT/GPU",'''),
], 'batch B2: 160 -> 320 MB')

patch('app/src/renut_engine/gpu/backend/queued.cpp', [
    ('''constexpr DeltaChunkList kDeltaAllChunks = MakeDeltaChunkList(false);
constexpr DeltaChunkList kDeltaReadChunks = MakeDeltaChunkList(true);''', '''constexpr DeltaChunkList kDeltaAllChunks = MakeDeltaChunkList(false);
constexpr DeltaChunkList kDeltaReadChunks = MakeDeltaChunkList(true);
// sasrt-nx (2026-11-11, batch B3): a list split for the capture marks: its entries before the first markable chunk
// (always compared) and a mask of its markable entries (bit i - kDeltaMarkFirst), so a delta visits only the set bits.
struct DeltaMarkedList {
  u32 pre_count = 0;
  u8 pre[32] = {};
  uint64_t markable = 0;
};
constexpr u32 kDeltaMarkFirstChunk = (0x480 / kDeltaUnitBytes);  // = kDeltaMarkFirst (below)
static_assert(kDeltaChunks - kDeltaMarkFirstChunk <= 64);
constexpr DeltaMarkedList MakeDeltaMarkedList(const DeltaChunkList &l) {
  DeltaMarkedList m{};
  for (u32 k = 0; k < l.count; ++k) {
    const u32 i = l.index[k];
    if (i < kDeltaMarkFirstChunk)
      m.pre[m.pre_count++] = u8(i);
    else
      m.markable |= uint64_t(1) << (i - kDeltaMarkFirstChunk);
  }
  return m;
}
constexpr DeltaMarkedList kDeltaAllMarked = MakeDeltaMarkedList(kDeltaAllChunks);
constexpr DeltaMarkedList kDeltaReadMarked = MakeDeltaMarkedList(kDeltaReadChunks);'''),
    ('''      const DeltaChunkList &list = narrow ? kDeltaReadChunks : kDeltaAllChunks;
      const bool neon = NeonCompareOn();
      for (u32 k = 0; k < list.count; ++k) {
        const u32 i = list.index[k];
        if (i >= kDeltaMarkFirst && !((marked >> (i - kDeltaMarkFirst)) & 1))
          continue;
        ++c.marks_chunks;
        const u32 at = DeltaChunkOffset(i), size = DeltaChunkSize(i);
        const bool differs = size == kDeltaUnitBytes ? banjo::renut_gpu::Line64Differs(bytes + at, c.shadow + at, neon)
                                                     : std::memcmp(bytes + at, c.shadow + at, size) != 0;
        if (differs)
          take(i);
      }
      ++c.marks_deltas;''', '''      const bool neon = NeonCompareOn();
      // sasrt-nx (2026-11-11, batch B3): the list's unmarkable head, then its marked chunks by their set bits: the same
      // chunks in the same ascending order as the list walk, without testing the ~77 entries' marks one by one.
      static_assert(kDeltaMarkFirst == kDeltaMarkFirstChunk);
      const DeltaMarkedList &ml = narrow ? kDeltaReadMarked : kDeltaAllMarked;
      u32 compared = 0;
      const auto visit = [&](u32 i) {
        ++compared;
        const u32 at = DeltaChunkOffset(i), size = DeltaChunkSize(i);
        const bool differs = size == kDeltaUnitBytes ? banjo::renut_gpu::Line64Differs(bytes + at, c.shadow + at, neon)
                                                     : std::memcmp(bytes + at, c.shadow + at, size) != 0;
        if (differs)
          take(i);
      };
      for (u32 k = 0; k < ml.pre_count; ++k)
        visit(ml.pre[k]);
      for (uint64_t bits = marked & ml.markable; bits; bits &= bits - 1)
        visit(kDeltaMarkFirst + u32(std::countr_zero(bits)));
      c.marks_chunks += compared;
      ++c.marks_deltas;'''),
], 'batch B3')
print('batchB: done')
