// sasrt-nx (2026-10-29, the banjo-nx sync): banjo-nx's Switch CPU profiler (its app/src/profiler) as far as Renut's
// tuning reads it: the A/B halves' CPU a frame. This port's per-thread accounting is the SDK's (sdk/src/ui/switch_perf.cpp
// RexSwitchPerfTotalThreadTicks).
#pragma once

#include <cstdint>

uint64_t RexSwitchPerfTotalThreadTicks();

namespace os::switch_cpu_profiler {

// The CPU time of every registered thread so far, summed, in system ticks (19.2 MHz).
inline uint64_t TotalThreadTicks() { return RexSwitchPerfTotalThreadTicks(); }

}  // namespace os::switch_cpu_profiler
