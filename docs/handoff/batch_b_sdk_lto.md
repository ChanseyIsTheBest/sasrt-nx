# Batch B (sasrt-nx, 2026-11-12): the SDK's OBJECT libraries in LTO + PGO, a bigger target-block cache, CaptureDelta

Console race, handheld 1020 / 460.8 / 1600, Ocean View, the same in-place build otherwise (abI -> abB, 21 race windows):
fps 27.59 -> 27.65 (+0.2 %), process CPU 82.99 -> 82.39 ms a frame (-0.7 %), render thread (core 1) 19.85 -> 19.48 ms
(-1.9 %), SlRenderer 14.89 -> 14.82, WaterThread -1.4 %, AK -1.5 %, Audio Worker -4.9 %. Small but kept. Script with all
three edits: the scratchpad's batchB.py (copied here as batch_b.py).

## B1: the SDK's OBJECT libraries in the Switch LTO and PGO (universal; Blur's finding)

rexaudio, rexcore, rexfilesystem, rexinput, rexui are OBJECT libraries compiled with their own options, so they had
neither LTO nor PGO. In app/CMakeLists.txt, next to the existing `_sasrt_sdk_opt_targets` list:

```cmake
option(SASRT_SWITCH_SDK_OBJECT_OPT "The SDK's OBJECT libraries in the Switch LTO and PGO too" ON)
if(SASRT_SWITCH_SDK_OBJECT_OPT)
    list(APPEND _sasrt_sdk_opt_targets rexaudio rexcore rexfilesystem rexinput rexui)
    set(_sasrt_wrap_sources
        "${CMAKE_CURRENT_SOURCE_DIR}/../sdk/src/core/threading_switch.cpp"
        "${CMAKE_CURRENT_SOURCE_DIR}/../sdk/src/ui/switch_perf.cpp"
        "${CMAKE_CURRENT_SOURCE_DIR}/../sdk/src/core/exception_handler_switch.cpp"
        "${CMAKE_CURRENT_SOURCE_DIR}/../sdk/src/core/fiber_switch.cpp")
endif()
...
# after target_link_options(sasrt PRIVATE ${_sasrt_lto_link}):
if(_sasrt_wrap_sources)
    set_property(SOURCE ${_sasrt_wrap_sources} TARGET_DIRECTORY rexcore rexui APPEND PROPERTY COMPILE_OPTIONS -fno-lto)
endif()
```

The four -fno-lto files, and why (each one cost a failed link):
- threading_switch.cpp, switch_perf.cpp define `__wrap_` functions for `--wrap`: the linker must see them as ordinary
  definitions, which LTO's late symbol resolution does not give.
- exception_handler_switch.cpp and fiber_switch.cpp have **top-level asm** that names C symbols (`g_rex_exc_*`,
  `rex_fiber_trampoline`): references from top-level asm are invisible to LTO, so it drops the symbols and the link
  fails with undefined references.
- exception_handler_switch.cpp also declared `extern "C" void _start(void);` while switch_code_blocks.cpp declares
  `extern "C" char _start;`: in one LTO link lto1 refuses a function and a variable of the same name. Declare it
  `extern "C" char _start;` (only its address is used).

## B2: target-block cache 160 -> 320 MB (SASRT-specific number)

`sasrt_target_block_cache_mb` (docs/handoff/target_block_cache.md). At 320: 78 blocks (315 MB) kept, 1811 targets took
a kept block, 150 made a new one (263 at 160 MB), 22 dropped over the cap. Size the cap from your own `Memory: kept
target blocks` line.

## B3: CaptureDelta visits only the marked chunks (Renut tree; universal where the capture marks exist)

SlRenderer's CaptureDelta 10.7 % -> 8.0 % of the thread: the chunk list is split once (constexpr) into its unmarkable head
and a 64-bit mask of its markable entries, and a delta walks `marked & mask` by set bits (same chunks, same ascending
order), with the compared count in a local.
