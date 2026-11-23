// banjo-nx - PC build only: the Switch profiler counters the renderer reports to (sdk/src/ui/switch_perf.cpp on the
// Switch) have nothing to feed on PC.
#include <cstdint>

#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>

extern "C" void RexSwitchPerfCount(unsigned) {}
extern "C" void RexSwitchPerfHitch(uint64_t, uint64_t) {}

// futari-nx's finding: on a PC loaded by other work, wall time per window swings by tens of percent, the calling
// thread's own CPU cycles do not. The ring thread's timer line reports them next to its milliseconds.
extern "C" uint64_t MeThreadCycles() {
  ULONG64 cycles = 0;
  QueryThreadCycleTime(GetCurrentThread(), &cycles);
  return uint64_t(cycles);
}

// The whole process's CPU time (all threads, user + kernel) in nanoseconds: the in-run A/B's total CPU per phase
// (sasrt_ab_keys, sasrt_enhancements.cpp).
extern "C" uint64_t MeProcessCpuNs() {
  FILETIME created, exited, kernel, user;
  if (!GetProcessTimes(GetCurrentProcess(), &created, &exited, &kernel, &user)) return 0;
  const auto ticks = [](const FILETIME& t) { return (uint64_t(t.dwHighDateTime) << 32) | t.dwLowDateTime; };
  return (ticks(kernel) + ticks(user)) * 100;  // 100 ns units
}
