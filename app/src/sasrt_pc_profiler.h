#pragma once

// PC sampling profiler (cvar sasrt_pc_profile_s); see sasrt_pc_profiler.cpp. Does nothing on the Switch, where the
// SDK's sampler (sdk/src/ui/switch_perf.cpp) does the same job.
namespace sasrt::pc_profiler {

void Start();
void Stop();

}  // namespace sasrt::pc_profiler
