// Switch build only: the calling thread's own CPU time for the ring thread's timer line and the in-run A/B
// (sasrt_ab_keys). On the PC, me_pc_stubs.cpp answers with QueryThreadCycleTime (futari-nx's method); here Horizon
// counts the ticks (19.2 MHz) the thread ran on any core (InfoType_ThreadTickCount, 13.0.0+, the same call the SDK's
// profiler makes in switch_perf.cpp). They are scaled to Cortex-A57 cycles at 1,020 MHz, the console's CPU clock, so
// the "kcycles per draw" lines mean the same thing on both. 0 if the kernel refuses the call (older firmware).
#include <cstdint>

#include <switch.h>

extern "C" uint64_t MeThreadCycles() {
  u64 ticks = 0;
  if (R_FAILED(svcGetInfo(&ticks, InfoType_ThreadTickCount, CUR_THREAD_HANDLE, UINT64_MAX))) return 0;
  return uint64_t(ticks) * 1020 * 1000 / 19200;  // 19.2 MHz ticks -> cycles at 1,020 MHz (x 53.125)
}
