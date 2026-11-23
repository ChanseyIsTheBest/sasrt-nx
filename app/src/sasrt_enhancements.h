#pragma once

// Every performance enhancement of the port, CPU and non-CPU, with an on/off key each and two group masters
// (sasrt_cpu_enhancements, sasrt_noncpu_enhancements). Two kinds, both in the startup "[enhancements]" log line:
//
//   - the table in sasrt_enhancements.cpp: enhancements that are plain cvars of the renderer or the SDK (most of
//     masseffect-nx's and sa2-nx's work); a group whose master is off sets them to their "off" value;
//   - the port's own (SASRT_ENHANCEMENT below, sa2-nx's pattern): its own key, `active` resolved once, a use counter
//     printed every 10 s ("[enh] uses in the last 10 s: ...") so a console log shows that it really ran.
//
// Build-time changes (codegen options, compiler flags) cannot be switched at run time: they go into the one build the
// SD card gets, the optimised codegen (the user's rule of 2026-10-06, no A/B pair of NROs), docs/enhancements.md lists
// them, and the first log line names the build's codegen flavour. Pattern from futari-nx (futari_enhancements.cpp) and
// sa2-nx (sa2_enhancements.h).
#include <atomic>
#include <cstdint>

#include <rex/cvar.h>

namespace sasrt::enhancements {

enum class Group : uint8_t { kCpu, kNonCpu };

struct Enhancement {
  const char* key;
  Group group;
  const char* what;
  bool (*own)();  // reads the enhancement's own cvar
  bool active = false;
  std::atomic<uint64_t> uses{0};
  // Extra number for the periodic line (e.g. microseconds slept), with its unit; nullptr = none.
  std::atomic<uint64_t> amount{0};
  const char* amount_unit = nullptr;

  void Use(uint64_t n = 1) { uses.fetch_add(n, std::memory_order_relaxed); }
  // For a use on one hot thread (e.g. every draw): a plain load and store of a private count (it is only a report),
  // and one shared add per 256 uses (sa2-nx's).
  std::atomic<uint32_t> sampled{0};
  void UseSampled() {
    const uint32_t n = sampled.load(std::memory_order_relaxed) + 1;
    sampled.store(n, std::memory_order_relaxed);
    if ((n & 255) == 0) Use(256);
  }
  void Add(uint64_t n) { amount.fetch_add(n, std::memory_order_relaxed); }
};

// Static registration (SASRT_ENHANCEMENT); safe at static-initialisation time.
bool Register(Enhancement* e);

// At startup, after the config is read and before anything reads the keys or a guest thread exists
// (SasrtApp::OnPostInitLogging): resolves the masters and every key (a group whose master is off turns all of its keys
// off), verify mode raises the renderer's self-check counts, one log line lists every enhancement and whether it is
// active, and the 10 s use report starts.
void Apply();

// The group master.
bool GroupOn(Group group);

// The PC side of the generated code's self-checks and the indirect call census (sasrt_codegen_checks.cpp, from
// sa2-nx; nothing on the Switch). Init: once, from Apply. Report: with every use report.
void CodegenChecksInit();
void CodegenChecksReport(int seconds);

// Runs every helper that has a form for one processor only (the conversions to integer, the divisions, the float
// copies, the small VMX helpers) on fixed edge inputs against plain C++ references and logs the result
// (sasrt_forms_selfcheck.cpp, from sa2-nx; the idea is banjo-nx's). Once, from Apply: on the console it is the first
// time the AArch64 forms run.
void FormsSelfCheck();

// In-run A/B (futari-nx's method, 2026-10-07): sasrt_ab_keys names enhancements of this file's kind (SASRT_ENHANCEMENT),
// ';'-separated, that the GPU ring thread switches off and on together every sasrt_ab_period_ms, at a Swap. Each
// phase's Swaps, wall time, ring work and ring cycles, draws and the whole process's CPU time are added up and printed
// every sasrt_enhancements_report_s: other work on the PC (builds, other ports' tests) then weighs on both phases
// alike, which back-to-back runs cannot promise. Diagnosis only; the keys must be on at start (their fast paths fall
// back to the plain path per use when off, so a switch at any Swap is exact).
struct AbSample {
  uint64_t ring_work_ns;  // the ring's parse loop so far, less its waits for the game
  uint64_t ring_cycles;   // the ring thread's own CPU cycles in it (PC; 0 on the Switch)
  uint64_t draws;
};
// GPU ring thread, at every Swap. Does nothing unless sasrt_ab_keys names a key that is on.
void AbSwap(const AbSample& now);
// The vertex bindings the ring has bound (vkCmdBindVertexBuffers, each an NVK macro on the console), which the A/B
// reports per draw in each phase. Added to by the GPU ring thread only: a plain counter.
extern uint64_t g_ab_vertex_bindings;

// True when the loaded guest code at `address` (`bytes` long) has the FNV-1a 64 hash a replacement was written from.
// Logs a warning naming `what` when it does not (the replacement then stays off).
bool GuestCodeMatches(const uint8_t* base, uint32_t address, uint32_t bytes, uint64_t fnv, const char* what);

}  // namespace sasrt::enhancements

// sasrt-nx (2026-11-13, base port 90; blur-nx 2026-11-11): timings of a few processor forms at boot when the cvar
// blur_microbench is on (app/src/cpu/blur_microbench.cpp, the base's file as it is: namespace banjo). Called right
// after FormsSelfCheck from Apply; nothing when the cvar is off (the default), nothing to measure off the AArch64.
namespace banjo {
void BlurMicrobench();
}  // namespace banjo

#define SASRT_ENHANCEMENT(VAR, KEY, GROUP, DEFAULT, DESC)                                                \
  REXCVAR_DEFINE_BOOL(KEY, DEFAULT, "SASRT", DESC).lifecycle(rex::cvar::Lifecycle::kInitOnly);           \
  ::sasrt::enhancements::Enhancement VAR{#KEY, GROUP, DESC, [] { return REXCVAR_GET(KEY); }};             \
  [[maybe_unused]] static const bool VAR##_registered_ = ::sasrt::enhancements::Register(&VAR)
