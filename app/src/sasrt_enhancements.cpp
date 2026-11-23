// On/off keys for every enhancement (see sasrt_enhancements.h).
//
// The user's rule (2026-10-06, relayed from futari-nx): every enhancement, CPU and non-CPU, can be switched off on its
// own in sasrt.toml, and each group has a master switch, so any change can be A/B-tested on the console without a new
// build. Build-time changes go into the one build the SD card gets, the optimised codegen (the user's rule of
// 2026-10-06: no A/B pair of NROs; such changes are compared through keys like these and the premade configs), and are
// listed in docs/enhancements.md, "Build-time".
//
// Most of the table is the native renderer's and the SDK's own performance work (masseffect-nx / nfsmw-nx / banjo-nx /
// sa2-nx, each already a cvar with a self-check where it needs one); masseffect-nx's docs/optimization-paths.md has
// the console measurements of each (e.g. deferred recording: ring thread 62 -> 40 %). The ones whose code default is
// off are turned on by app/sasrt_switch.toml, as masseffect-nx's best profile does (checked on PC in verify mode).
//
// Each row: the cvar, its group, what it does, the value it has when the enhancement is ON and the value that turns it
// OFF (a diagnostic that costs time is an enhancement whose ON value is "false"). Values go through the cvar registry
// by name (works for the SDK's cvars too, which live in another DLL on the PC). A key that does not exist on this
// platform (thread_wait_blocking is POSIX/Switch only) reads as empty and is listed as off.
//
// To add an enhancement: one row in kTable (its cvar must exist) and its ON value in app/sasrt_switch.toml if the code
// default is OFF; or, for the port's own code, SASRT_ENHANCEMENT (sasrt_enhancements.h). The premade configurations
// (tools/make_enhancement_configs.py) are made from app/sasrt_switch.toml.

#include "sasrt_enhancements.h"

#include <algorithm>
#include <chrono>
#include <iterator>
#include <string>
#include <thread>
#include <vector>

#include <fmt/format.h>

#include <rex/cvar.h>
#include <rex/logging.h>
#include <rex/platform.h>
#include <rex/ppc/context.h>
#include <rex/sys_counters.h>

// The codegen flavour of this build (tools/codegen.ps1 -Flavor; app/generated/codegen_flavor.txt, set by
// app/CMakeLists.txt), named in the first log line.
#ifndef SASRT_BUILD_FLAVOR
#define SASRT_BUILD_FLAVOR "unknown codegen"
#endif

#if REX_PLATFORM_SWITCH
#include <rex/ui/switch_apm.h>
#endif

// The whole process's CPU time in nanoseconds, all threads (me_pc_stubs.cpp, GetProcessTimes); 0 on the Switch.
#if REX_PLATFORM_WIN32
extern "C" uint64_t MeProcessCpuNs();
#else
static uint64_t MeProcessCpuNs() { return 0; }
#endif

REXCVAR_DEFINE_BOOL(sasrt_cpu_enhancements, true, "SASRT",
                    "Master switch of the CPU enhancements: false turns every one of them off (see the "
                    "\"[enhancements]\" log line for the list)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_BOOL(sasrt_noncpu_enhancements, true, "SASRT",
                    "Master switch of the non-CPU enhancements (GPU, memory, I/O): false turns every one of them off")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

// Verify configuration (configs/sasrt_cpu_verify.toml next to the NRO, tools/make_enhancement_configs.py): the same CPU enhancements, with every self-check of the
// renderer's fast paths comparing on EVERY use instead of the first masseffect_native_verify_n (2048), and the vertex
// copy check on its first 20,000 copies instead of masseffect_native_fast_copy_verify (256). Each comparison runs the original path too, so it is slower: for a test
// session, not for play. Every 10 s the log has a "[verify] checks done: ... | differences: N" line; N must be 0 (a
// difference also logs DIFFERENCE / MISMATCH and turns that one fast path off for the rest of the session).
REXCVAR_DEFINE_BOOL(sasrt_cpu_verify, false, "SASRT",
                    "Verify mode: every fast path's self-check compares with the original path on every use; "
                    "\"[verify]\" log lines count the checks and the differences (must be 0). Slower: test only")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

// Non-CPU: handheld GPU clock 384 -> 460.8 MHz with the memory clock unchanged (apm configuration 0x92220008, the pair
// commercial games use; nfsmw-nx, UnleashedRecomp-NX and MarathonRecomp-NX ship it on). The SDK's switch_apm sets it
// back if the memory clock moves. Docked: nothing is touched.
// sasrt-nx 1.0.0 (2026-11-23, the user: "make sure release build has no profiling"): off by default; app/sasrt_switch.toml turns it on for test runs
REXCVAR_DEFINE_INT32(sasrt_enhancements_report_s, 0, "SASRT",
                     "Seconds between two '[enh] uses' log lines of the port's own enhancements (0 = none)")
    .range(0, 3600)
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

// Diagnostic (PC builds: the SDK's sys_counters.h counts nothing of this on the Switch): how often the guest reaches
// the host runtime's lock-and-syscall paths, per second, with each '[enh] uses' report. It is what tells which of
// them is worth making cheaper on the A57 (a PC profile shows their Windows cost, not their Horizon cost).
REXCVAR_DEFINE_BOOL(sasrt_diag_runtime_census, false, "SASRT",
                    "Diagnostic (PC): calls per second of the host runtime's clock, critical section, event, "
                    "semaphore, wait and handle-lookup paths, in a '[census]' log line with each '[enh] uses' report")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

// In-run A/B (sasrt_enhancements.h, AbSwap). Diagnosis only: empty = off.
REXCVAR_DEFINE_STRING(sasrt_ab_keys, "", "SASRT",
                      "In-run A/B (diagnosis): SASRT_ENHANCEMENT keys, ';'-separated, switched off and on together "
                      "every sasrt_ab_period_ms at a Swap; each phase is measured and printed every "
                      "sasrt_enhancements_report_s (\"[ab]\" lines)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_INT32(sasrt_ab_period_ms, 2000, "SASRT", "In-run A/B: the length of each phase in milliseconds")
    .range(100, 600000)
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

// The console profiler's CPU sampler (sdk/src/ui/switch_perf.cpp reads it by name): what logs/rex/stacks_profile.flag
// does, from the config, so a profiling config does not depend on the flag file being copied to the SD card.
REXCVAR_DEFINE_BOOL(switch_profile_stacks, false, "SASRT",
                    "Switch profiler: sample every busy thread's pc at 1 kHz into logs/rex/rex_profile.log (the same as "
                    "an empty logs/rex/stacks_profile.flag; costs some speed)");
// sasrt-nx (2026-11-19, base port 150; blur-nx's 15 ms batch): the sampler's interval in ms (read by name too). Each
// sample pauses one game thread from a thread above all of them. 1 (the default) is the 1 kHz this port has measured with.
REXCVAR_DEFINE_INT32(switch_profile_stacks_ms, 1, "SASRT",
                     "Switch: the SDK sampler's interval in milliseconds (1-100; each sample pauses one game thread)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
// sasrt-nx (2026-11-19, base port 177; blur-nx's Renut audit #29): read by name by the SDK's profiler thread
// (switch_perf.cpp).
// sasrt-nx 1.0.0 (2026-11-23, the user: "make sure release build has no profiling"): off by default; app/sasrt_switch.toml turns it on for test runs
REXCVAR_DEFINE_BOOL(switch_perf_count_calls, false, "SASRT",
                    "Switch: the wrapped libnx calls (kicks, GPU mappings, cache cleans, yields and sleeps) counted for "
                    "the 10 s report's libnx line, a clock read and two atomics each. false skips that (a shipping "
                    "config that reads no reports)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

REXCVAR_DEFINE_BOOL(sasrt_handheld_gpu_boost, true, "SASRT",
                    "Handheld: GPU 460.8 MHz instead of 384 (memory clock unchanged); docked: no effect")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

// Build-time work with a run-time side (docs/enhancements.md, "Build-time").
SASRT_ENHANCEMENT(g_guest_cas_no_barrier, sasrt_cpu_guest_cas_no_barrier, ::sasrt::enhancements::Group::kCpu, true,
                  "Compare-and-swap (the game's interlocked operations, tools/guest_cas.py, and the SDK's lock words, "
                  "atomic_posix.cpp) without the legacy builtin's trailing `dmb ish` on the A57; off puts the barrier "
                  "back at run time");
// sasrt-nx (2026-11-19, base port 150; blur-nx's 15 ms batch, docs/cpu-15ms-batch-1116.md there): the generated code's
// guest compare-and-swap as relaxed exclusives (#163) and its lwsync / eieio as `dmb ishld` + `dmb ishst` / `dmb ishst`
// (#164 / #165, tools/guest_fences.py), each exact with respect to the 360's memory model (lwarx / stwcx. order nothing
// there; lwsync does not order a store before a later load; eieio orders stores). Off gives the old form back (AArch64
// only; the PC's x86 forms do not change). The base's key names.
SASRT_ENHANCEMENT(g_guest_cas_relaxed, blur_guest_cas_relaxed, ::sasrt::enhancements::Group::kCpu, true,
                  "The game's compare-and-swap as relaxed exclusives (ldxr / stxr), as the 360's lwarx / stwcx.; off: "
                  "the sequentially consistent loop (ldaxr / stlxr) as before");
SASRT_ENHANCEMENT(g_guest_fences_split, blur_guest_fences_split, ::sasrt::enhancements::Group::kCpu, true,
                  "The game's lwsync as dmb ishld + dmb ishst and eieio as dmb ishst (the PowerPC orderings); off: a "
                  "full dmb ish for both, as before");
#if defined(__aarch64__)
extern "C" unsigned char g_rex_atomic_legacy_barrier;
extern "C" unsigned char g_rex_guest_cas_seq_cst;  // sdk/src/core/atomic_posix.cpp (base port 150)
extern "C" unsigned char g_rex_guest_fence_full;
#endif

// sasrt-nx (2026-11-19, the game menu, src/game_menu.cpp): the base's live frame cap (katamari_keys.cpp's
// BlurSetFrameCapLive / BlurFrameCapNow) is this port's frame_cap key now (the user, 2026-11-19: 30 to 60 fps in steps
// of 5): renut_engine/gpu/sasrt_renut_pacing.cpp defines both.

// rex/ppc/context.h (2026-10-14), every platform: guest writes of the round-up / round-down modes. Defined here, in
// the program, because the PC build links the SDK runtime as a DLL and the generated code cannot import data from it.
extern "C" {
volatile uint32_t g_rex_directed_rounding_writes = 0;
}

#if !REX_PLATFORM_SWITCH
// tools/flush_mode_flow.py: off the Switch every flush-mode check the control flow proved redundant keeps its test
// (REX_FLUSH_KNOWN_ON / _OFF in the generated pch) and lands here when the proof was wrong, before the mode is
// switched after all. So every PC run checks the proof; the Switch build has no code at these places.
extern "C" {
volatile unsigned long long g_rex_flush_flow_checked = 0;  // a plain lossy count: "at least this many"
// rex/ppc/diet_ops.h, REX_DIET_CENSUS_ON (sa2-nx's): executions of the any-mode float helpers in the game code
// (conversions, compares, arithmetic, cold paths) and of the float copy forms (loads, stores). Plain lossy counts.
volatile unsigned long long g_rex_diet_census[6] = {};
// sasrt-nx (2026-11-19, base port 140; blur-nx's near-exact ideas): their census (rex/ppc/diet_ops.h REX_NX_CENSUS, on
// with REX_DIET_CENSUS_ON off the Switch), and the guest compare-and-swaps' word census switch (tools/guest_cas.py's
// RexNxCasCensus below; off: a test and nothing else).
volatile unsigned long long g_rex_nx_census[48] = {};
unsigned char g_rex_cas_census = 0;
}
namespace {
std::atomic<uint64_t> g_flush_flow_mismatches{0};
}
// base port 140: the PC census of which threads write each word a guest compare-and-swap writes (tools/guest_cas.py
// calls this with REX_NX_CENSUS_ON). Only counted while g_rex_cas_census is set (nothing in this port sets it: the
// base's report is not ported); unguarded, every compare-and-swap took one global mutex.
extern "C" void RexNxCasCensus(const void*) {
  if (!g_rex_cas_census) [[likely]] return;
}
extern "C" void RexFlushFlowMismatch(int on) noexcept {
  if (g_flush_flow_mismatches.fetch_add(1, std::memory_order_relaxed) < 16) {
    REXLOG_ERROR("[enh] DIFFERENCE: flush-mode flow: a check proven redundant had to switch the mode {} (return "
                 "address {})",
                 on ? "on" : "off", static_cast<const void*>(__builtin_return_address(0)));
  }
}
#endif

#if !REX_PLATFORM_SWITCH && defined(_WIN32)
extern "C" __declspec(dllimport) void* __stdcall GetModuleHandleW(const wchar_t* name);
static uint64_t CensusImageBase() { return reinterpret_cast<uint64_t>(GetModuleHandleW(nullptr)); }
#else
static uint64_t CensusImageBase() { return 0; }
#endif

namespace sasrt::enhancements {
namespace {

struct Entry {
  const char* key;
  Group group;
  const char* what;
  const char* on;   // value when the enhancement is active
  const char* off;  // value that turns it off
  // Never turned on for a key the config leaves out (Apply), and written OFF by the generated configs: it must be set
  // to its ON value explicitly to try it.
  bool explicit_only = false;
};
constexpr bool kExplicitOnly = true;

constexpr Group kCpu = Group::kCpu;
constexpr Group kGpu = Group::kNonCpu;

// Not in the table: the profiler's two keys, masseffect_gpu_marks_categories (GPU time per pass category) and
// switch_profile_stacks (the CPU sampler). The user's rule (2026-10-06, relayed from sa2-nx): the profiler is on in
// sasrt.toml and every premade config but the verify one, so no master switch may turn it on or off (the GPU marks
// used to be a row here, which a non-CPU master set to "off" = marks on).
// clang-format off
const Entry kTable[] = {
    // ---- CPU: the renderer's ring thread (masseffect-nx best profile; its optimization-paths.md section 3) --------
    // Deferred recording: explicit only. Its PC slowdowns (a third slower here, ~100 ms per copy in futari-nx) were
    // Windows' sleep granularity, fixed (ShortPause, masseffect_deferred_recording.cpp), and sa2-nx turned it on in its
    // round 5; but futari-nx's lockstep captures (2026-10-07) found a menu fade differing on 4 frames with it, by up to
    // 65 levels and differently in each run, and identical in five runs without it: not pixel-identical. The console
    // A/B: configs/sasrt_test_deferred_on.toml.
    {"masseffect_native_deferred_recording", kCpu, "ring: a worker records the vkCmd* calls (ME: ring 62 -> 40 %)", "true", "false", kExplicitOnly},
    {"masseffect_deferred_native_fast", kCpu, "ring: deferred queue published in batches", "true", "false", kExplicitOnly},
    {"masseffect_deferred_native_update", kCpu, "ring: vkUpdateDescriptorSets queued (~70 worker drains a frame)", "true", "false", kExplicitOnly},
    // sa2-nx's round 3: the upload buffer (every draw's vertices and indices) in CPU-cached memory, published before each
    // submit (sa2-nx's console: CPU writes 5,251 MB/s there against 2,506 in the uncached type the SDK picks). Also what
    // sasrt_cpu_ring_compare_uploaded reads.
    {"masseffect_native_upload_memory", kCpu, "upload buffer in CPU-cached memory (published before each submit)", "1", "0"},
    {"masseffect_native_fast_pair", kCpu, "ring: draw/record pairing on dense arrays, no lock", "true", "false"},
    {"masseffect_native_raw_microcode", kCpu, "ring: shader reload compared on raw guest words", "true", "false"},
    {"masseffect_native_pm4_fast", kCpu, "ring: constant/fetch register runs with NEON", "true", "false"},
    {"masseffect_native_flat_identity", kCpu, "ring: shader identity in direct-mapped tables", "true", "false"},
    {"masseffect_native_compare_fast", kCpu, "ring: ~15 memcmp per draw as inline compares", "true", "false"},
    {"masseffect_native_fast_copy", kCpu, "ring: vertex copy 64 B/iteration with prefetch", "true", "false"},
    {"masseffect_native_indices_cache", kCpu, "ring: same-frame index buffer cache", "true", "false"},
    {"masseffect_notify_no_lock", kCpu, "ring: progress notify without the mutex when nobody waits", "true", "false"},
    // sa2-nx's round 6: 2 = the A57's hardware CRC32 pair (masseffect_crc_fingerprint.h) for the index cache and the
    // sampled fingerprints; a build without +crc (the PC) uses 1, chained XXH3 blocks.
    {"masseffect_native_fingerprint_mode", kCpu, "ring: fingerprints by the CRC32 pair (A57) or chained XXH3", "2", "0"},
    {"masseffect_native_dedupe_max_fingerprint", kCpu, "ring: large static vertex ranges matched without hashing", "16384", "0"},
    {"masseffect_native_identity_memo", kCpu, "ring: shader identification memo by content", "true", "false"},
    {"masseffect_native_repeated_identity", kCpu, "ring: identical shader reload keeps its identity", "true", "false"},
    {"masseffect_native_registers_table", kCpu, "ring: draw records in a fixed table (no map)", "true", "false"},
    {"masseffect_native_fast_registers", kCpu, "ring: register write runs without per-word checks", "true", "false"},
    {"masseffect_native_dedupe_vertices", kCpu, "ring: a vertex range uploaded once per frame", "true", "false"},
    {"masseffect_native_dedupe_sample", kCpu, "ring: dedupe content check on sampled blocks", "true", "false"},
    {"masseffect_native_vertices_base_zero", kCpu, "ring: one vertex binding, draws shifted by offset", "true", "false"},
    {"masseffect_native_indices_neon", kCpu, "ring: 16-bit index copy/min/max with NEON", "true", "false"},
    {"masseffect_native_uploads_help", kCpu, "ring: helps the copy thread instead of waiting", "true", "false"},
    {"masseffect_native_framing_cache", kCpu, "ring: viewport/scissor reused while unchanged", "true", "false"},
    {"masseffect_native_util_height_memo", kCpu, "ring: usable target height memo", "true", "false"},
    {"masseffect_native_key_fast_pass", kCpu, "ring: pass key not rehashed for the same targets", "true", "false"},
    {"masseffect_native_cvars_per_frame", kCpu, "ring: per-draw cvars read once per frame", "true", "false"},
    {"masseffect_native_pipelines_direct", kCpu, "ring: direct-mapped pipeline cache", "true", "false"},
    {"masseffect_native_pipeline_between_passes", kCpu, "ring: bound pipeline kept across passes", "true", "false"},
    {"masseffect_native_textures_binding_thread", kCpu, "ring: vkBindImageMemory on a helper thread", "true", "false"},
    {"masseffect_native_textures_pool", kCpu, "textures in pooled blocks (~1.9 ms per dedicated alloc)", "true", "false"},
    {"masseffect_native_cache_textures_between_frames", kCpu, "ring: sampler caches valid across frames", "true", "false"},
    {"masseffect_shared_native_cache", kCpu, "ring: shared constants in cached memory (2 us/draw)", "true", "false"},
    {"masseffect_native_tile_fast", kCpu, "texture untiling in 16-byte steps", "true", "false"},
    {"masseffect_native_nvk_emission", kCpu, "NVK: each draw command written in one go", "true", "false"},
    {"masseffect_native_nvk_cbufs", kCpu, "NVK: cbuf flush skipped when nothing is dirty", "true", "false"},
    {"masseffect_native_nvk_dynamic", kCpu, "NVK: only dirty dynamic-state groups emitted", "true", "false"},
    {"masseffect_native_nvk_preload", kCpu, "NVK: cache hints for pipeline and shaders", "true", "false"},
    {"masseffect_native_set4_differences", kCpu, "NVK: descriptor set 4 by differences", "true", "false"},
    {"masseffect_native_output_no_wait", kCpu, "output through 3 slots, no wait for the previous one", "true", "false"},
    {"masseffect_vblank_sleep_exact", kCpu, "vblank thread sleeps to the exact vblank", "true", "false"},
    {"masseffect_native_diag_reuse", kCpu, "diagnostic off: texture reuse counting", "false", "true"},
    {"masseffect_native_diag_memory_upload", kCpu, "diagnostic off: memory-type write-speed test at start", "false", "true"},
    {"sa2_native_constants_dedupe", kCpu, "ring: shader constants uploaded once per change (sa2-nx)", "true", "false"},
    // ---- CPU: SDK (guest kernel / threads), masseffect-nx section 4 ---------------------------------------------
    {"thread_wait_blocking", kCpu, "SDK: waits parked on a wake point, not 1 ms polls (POSIX/Switch)", "true", "false"},
    // 2026-10-12: an event set or semaphore release with nobody blocked on it makes no wake syscall (the waiters of
    // each condition are counted under its mutex). ~19,000 signals a second in a race here.
    {"thread_signal_skip_idle", kCpu, "SDK: signals with nobody blocked skip the wake syscall (POSIX/Switch)", "true", "false"},
    // sa2-nx's second CPU round: RtlEnter / Leave / TryEnterCriticalSection take the owner id from the guest context
    // (r13 -> KPCR -> current thread) instead of looking the host thread up (a thread_local read: a call on the
    // Switch). 85,000 enters a second here. The PC build compares the two on every call.
    {"kernel_critsec_pcr_owner", kCpu, "SDK: critical sections take their owner from the PCR, no thread lookup", "true", "false"},
    {"clock_nonblocking", kCpu, "SDK: guest clock update never blocks", "true", "false"},
    {"global_lock_spin", kCpu, "SDK: bounded spin on the object-table lock", "48", "0"},
    // ---- non-CPU: GPU work and memory ---------------------------------------------------------------------------
    {"sasrt_handheld_gpu_boost", kGpu, "handheld GPU 460.8 MHz", "true", "false"},
    {"masseffect_native_vs_pruned_outputs", kGpu, "vertex shaders write only the outputs the PS reads", "true", "false"},
    {"masseffect_native_normalized_remap", kGpu, "vertex input remap fast path", "true", "false"},
    {"masseffect_native_z_early", kGpu, "early depth test for depth-test-only draws", "true", "false"},
    {"masseffect_native_ps_alpha_only", kGpu, "colourless passes: PS without colour writes", "true", "false"},
    {"masseffect_native_no_ps_no_color", kGpu, "no fragment stage for colourless draws", "true", "false"},
    {"masseffect_native_skip_invisibles", kGpu, "draws that cannot change a pixel skipped", "true", "false"},
    {"sasrt_native_skip_null_draws", kGpu, "Direct3D's null-shader draws skipped (no 4x shadow-map round trips)", "true", "false"},
    {"sasrt_native_edram4_grid_alias", kGpu, "4x clear alias learned through the raster-grid view (shadow-map clears redirected)", "true", "false"},
    // banjo-nx's EDRAM traffic items (2026-10-14, the user's go-ahead): more draws proven to overwrite whole tiles.
    {"sasrt_gpu_proof_tess_leftover", kGpu, "overwrite proof: a leftover tessellator setting refuses only explicit-major-mode draws (banjo-nx)", "true", "false"},
    {"sasrt_gpu_proof_triangle", kGpu, "overwrite proof: one full-viewport triangle counts like a rectangle (banjo-nx)", "true", "false"},
    {"sasrt_gpu_proof_depth_only", kGpu, "overwrite proof: alpha bits do not matter in the depth-only EDRAM mode (banjo-nx)", "true", "false"},
    {"sasrt_gpu_edram4_split_tiles", kGpu, "EDRAM tiles a draw covers in part taken split, the rest brought over only if needed (banjo-nx)", "true", "false"},
    {"sasrt_gpu_rect_split", kGpu, "rectangle lists of 2-8 rectangles drawn one rectangle at a time (banjo-nx)", "true", "false"},
    {"sasrt_gpu_skip_dead_draws", kGpu, "draws that can write nothing skipped before their EDRAM preparation", "true", "false"},
    {"sasrt_gpu_api_clear", kGpu, "Direct3D's Clear as an operation: a whole-surface clear takes its edge tiles whole (banjo-nx)", "true", "false"},
    {"masseffect_native_skip_cleared_repeated", kGpu, "repeated identical clears skipped", "true", "false"},
    {"masseffect_native_pass_narrow_dependency", kGpu, "narrow render-pass start dependency", "true", "false"},
    {"masseffect_native_pass_area_util", kGpu, "passes opened over the used rectangle", "true", "false"},
    {"masseffect_native_zcull", kGpu, "ZCULL plane for depth buffers", "true", "false"},
    {"sa2_native_edram4_clear_color0", kGpu, "Direct3D clears of colour 0 redirected to the owning image (sa2-nx)", "true", "false"},
    {"sa2_native_pass_narrow_end", kGpu, "narrow render-pass end dependency (sa2-nx)", "true", "false"},
    {"masseffect_native_precise_marks", kGpu, "diagnostic off: BOTTOM_OF_PIPE timestamps", "false", "true"},
    {"masseffect_native_pipelines_prewarm", kGpu, "earlier sessions' pipelines recreated at start", "true", "false"},
    {"masseffect_shaders_index", kGpu, "shader package by index (SPIR-V on first use)", "true", "false"},
    {"masseffect_shaders_preload", kGpu, "prewarm list's SPIR-V read in the background", "true", "false"},
};
// clang-format on

bool Active(const Entry& e) {
  const std::string value = rex::cvar::GetFlagByName(e.key);
  return !value.empty() && value != e.off;
}

std::vector<Enhancement*>& Registered() {
  static std::vector<Enhancement*> list;
  return list;
}

// The port's own enhancements: every 10 s, how often each active one ran (and its amount, e.g. time asleep).
void StartReport() {
  const int seconds = REXCVAR_GET(sasrt_enhancements_report_s);
  if (seconds <= 0 || Registered().empty()) return;
  // Never joined and never destroyed (libnx cannot detach a thread; see the SDK's threading_posix.cpp).
  new std::thread([seconds] {
    std::vector<uint64_t> last_uses(Registered().size(), 0), last_amount(Registered().size(), 0);
    for (;;) {
      std::this_thread::sleep_for(std::chrono::seconds(seconds));
      std::string line;
      for (size_t i = 0; i < Registered().size(); ++i) {
        Enhancement* e = Registered()[i];
        if (!e->active) continue;
        const uint64_t uses = e->uses.load(std::memory_order_relaxed);
        const uint64_t amount = e->amount.load(std::memory_order_relaxed);
        const uint64_t du = uses - last_uses[i], da = amount - last_amount[i];
        last_uses[i] = uses;
        last_amount[i] = amount;
        if (!du && !da) continue;
        line += fmt::format(" {} {}", e->key, du);
        if (e->amount_unit) line += fmt::format(" ({} {})", da, e->amount_unit);
      }
      if (!line.empty()) REXLOG_INFO("[enh] uses in the last {} s:{}", seconds, line);
      // sasrt-nx (2026-10-14; sa2-nx's idea 7), every platform: the float sign forms (tools/fp_sign_ops.py) let the
      // compiler fold a negation into the arithmetic next to it, which is exact unless the game rounds up or down.
      // The PC census of a race saw no rounding-mode write at all; this line says if the game ever does select one.
      static uint32_t directed_seen = 0;
      if (const uint32_t directed = g_rex_directed_rounding_writes; directed != directed_seen) {
        directed_seen = directed;
        REXLOG_WARN("[enh] the game selected the round-up or round-down mode ({} times so far): the float sign "
                    "forms (SASRT_GEN_FP_SIGN_OPS) and the fnmadd / fnmsub forms assume it never does; please keep "
                    "this log",
                    directed);
      }
#if REX_PLATFORM_SWITCH
      CodegenChecksReport(seconds);  // sasrt-nx (2026-11-12): the hooked build's stack-forward self-check (idea 2)
#endif
#if !REX_PLATFORM_SWITCH
      // tools/flush_mode_flow.py's self-check: the proven checks this run executed, and those that were wrong.
      if (const uint64_t proven = g_rex_flush_flow_checked) {
        const uint64_t wrong = g_flush_flow_mismatches.load(std::memory_order_relaxed);
        if (wrong) {
          REXLOG_ERROR("[enh] DIFFERENCE: flush-mode flow: {} of {} checks proven redundant had to switch the mode "
                       "(cumulative)",
                       wrong, proven);
        } else {
          REXLOG_INFO("[verify] flush-mode flow: {} checks proven redundant executed so far, 0 had to switch the mode",
                      proven);
        }
      }
      CodegenChecksReport(seconds);
      if (REXCVAR_GET(sasrt_diag_runtime_census)) {
        // sasrt_diag_runtime_census: the SDK's counters (rex/sys_counters.h), as calls per second.
        using namespace rex::syscount;
        static uint64_t last[kCensusCount] = {};
        const auto per_s = [&](unsigned id) {
          const uint64_t now = CensusRead(id);
          const uint64_t d = now - last[id];
          last[id] = now;
          return double(d) / double(seconds);
        };
        const double clock = per_s(kClockCall), clock_blocked = per_s(kClockBlocked);
        const double enter = per_s(kCensusCritSecEnter), recursive = per_s(kCensusCritSecRecursive);
        const double try_enter = per_s(kCensusTryEnter), cs_wait = per_s(kCritSecWait);
        const double set = per_s(kCensusEventSet), sem = per_s(kCensusSemRelease), wait = per_s(kCensusWait);
        const double lookup = per_s(kObjLookup), lookup_blocked = per_s(kObjBlocked);
        const double native = per_s(kCensusNativeObject), stamp = per_s(kTimestampTick);
        const double flush = per_s(kCensusFlushWrite), flush_same = per_s(kCensusFlushSame);
        const double note_locked = per_s(kCensusNoteShaderLocked);
        REXLOG_INFO("[census] guest code per second: {:.0f} flush-mode switches (each an msr fpcr on the console; "
                    "{:.0f} of them unconditional writes that left the mode as it was); NoteShaderObject took its "
                    "shared mutex {:.0f} times",
                    flush, flush_same, note_locked);
        // sasrt-nx (2026-10-14; sa2-nx's idea 7 asks first): the rounding modes the game sets (mtfsf), cumulative.
        // Float negations may only be written as float operations if the game never rounds up or down (the
        // symmetric modes, to nearest and toward zero, keep the compiler's folds exact). A race: no write at all.
        REXLOG_INFO("[census] FPSCR rounding mode written by the game (cumulative): nearest {}, toward zero {}, up {}, "
                    "down {}",
                    rex::syscount::CensusRead(rex::syscount::kCensusRoundMode + 0),
                    rex::syscount::CensusRead(rex::syscount::kCensusRoundMode + 1),
                    rex::syscount::CensusRead(rex::syscount::kCensusRoundMode + 2),
                    rex::syscount::CensusRead(rex::syscount::kCensusRoundMode + 3));
        {
          // What the switches saved by the generator's any-mode forms cost: a test in each of these calls (sa2-nx's
          // counters, rex/ppc/diet_ops.h REX_DIET_CENSUS_ON).
          static uint64_t last_diet[6] = {}, last_proven = 0;
          double diet[6];
          for (int i = 0; i < 6; ++i) {
            const uint64_t now = g_rex_diet_census[i];
            diet[i] = double(now - last_diet[i]) / double(seconds);
            last_diet[i] = now;
          }
          const uint64_t proven_now = g_rex_flush_flow_checked;
          const double proven_s = double(proven_now - last_proven) / double(seconds);
          last_proven = proven_now;
          REXLOG_INFO("[census] any-mode float helpers per second: conversions {:.0f}, compares {:.0f}, arithmetic "
                      "{:.0f}, cold paths {:.0f}; proven flush checks executed {:.0f}",
                      diet[0], diet[1], diet[2], diet[3], proven_s);
          REXLOG_INFO("[census] float copy forms per second (fp_copy_pairs): loads {:.0f}, stores {:.0f}", diet[4],
                      diet[5]);
          // blur-nx (2026-11-12, codegen-ideas-3 CG-13's census; base port 123, here 2026-11-13): what one flush mode for
          // all code would change. The any-mode cold paths above are scalar results in VMX code that met a denormal; the
          // FPU-mode regions are the plain scalar code between switches, and a region with a denormal operand or an
          // underflow (x86 flags, a lower bound) holds at least one result that would change.
          const double regions = per_s(rex::syscount::kCensusFpuRegions);
          const double denormal = per_s(rex::syscount::kCensusFpuDenormal);
          REXLOG_INFO("[census] CG-13 (one flush mode): per second {:.0f} any-mode cold paths and {:.0f} of {:.0f} "
                      "FPU-mode regions with a denormal operand or an underflow: scalar results the one-mode build "
                      "would change",
                      diet[3], denormal, regions);
          // Where those happen (cumulative, image offset:count; tools/census_sites.py --denormal).
          static int denormal_reports = 0;
          if ((++denormal_reports % 3) == 0) {
            // base port 226 (banjo-nx, 2026-11-19): 256 sites, not 48 (the forms self-check's own took about 20 of 48).
            static uint64_t addresses[256], counts[256];
            const size_t n = rex::syscount::CensusDenormalSites(addresses, counts, 256);
            std::string list;
            for (size_t i = 0; i < n; ++i)
              list += fmt::format(" +{:X}:{}", addresses[i] - CensusImageBase(), counts[i]);
            if (n)
              REXLOG_INFO("[census] denormal sites (CG-13, cumulative, image offset:count):{}", list);
          }
        }
        {
          // The runtime's own out-of-line calls for what is one load or nothing (sa2-nx's survey).
          const double logs = per_s(kCensusLogCall), heaps = per_s(kCensusLookupHeap);
          const double refs = per_s(kCensusRetainRelease), states = per_s(kCensusKernelState);
          const double pcr_owner = per_s(kCensusCritSecPcrOwner);
          REXLOG_INFO("[census] runtime overhead per second: {:.0f} log statements reached (written or not), {:.0f} "
                      "heap lookups for a pointer translation, {:.0f} object retains and releases, {:.0f} kernel "
                      "state reads; {:.0f} critical section owners from the PCR",
                      logs, heaps, refs, states, pcr_owner);
        }
        {
          // The kernel exports the game calls most (rex/hook.h counts every REX_EXPORT in PC builds).
          static uint64_t last_exports = 0;
          const char* names[24];
          uint64_t counts[24];
          const size_t n = ExportCensus(names, counts, 24);
          uint64_t shown = 0;
          std::string list;
          for (size_t i = 0; i < n; ++i) {
            const std::string name = names[i];
            list += fmt::format(" {}:{}", name.rfind("__imp__", 0) == 0 ? name.substr(7) : name, counts[i]);
            shown += counts[i];
          }
          if (n) {
            REXLOG_INFO("[census] kernel exports by calls (cumulative, the 24 most called; {:.0f} a second of "
                        "them):{}",
                        double(shown - last_exports) / double(seconds), list);
          }
          last_exports = shown;
        }
        // Where the mode is switched: the most counted code addresses so far, as offsets into the executable
        // (tools/census_sites.py turns them into functions and generated source lines).
        CensusSitesEnable(true);
        static int site_reports = 0;
        if ((++site_reports % 3) == 0) {
          uint64_t addresses[48], counts[48];
          const size_t n = CensusSites(addresses, counts, 48);
          std::string list;
          for (size_t i = 0; i < n; ++i) {
            list += fmt::format(" +{:X}:{}", addresses[i] - CensusImageBase(), counts[i]);
          }
          if (n) REXLOG_INFO("[census] flush-mode switch sites (cumulative, image offset:count):{}", list);
        }
        REXLOG_INFO("[census] runtime calls per second: guest clock {:.0f} ({:.0f} found its mutex taken); critical "
                    "sections entered {:.0f} ({:.0f} already owned, {:.0f} tried, {:.0f} waited); events set {:.0f}, "
                    "semaphores released {:.0f}, waits {:.0f}; handle lookups {:.0f} ({:.0f} found the global lock "
                    "taken), dispatcher objects looked up {:.0f}; timestamp ticks {:.0f}",
                    clock, clock_blocked, enter, recursive, try_enter, cs_wait, set, sem, wait, lookup, lookup_blocked,
                    native, stamp);
      }
#endif
    }
  });
}

// In-run A/B (AbSwap): only the GPU ring thread touches this.
struct AbPhase {
  uint64_t swaps = 0, wall_ns = 0, ring_work_ns = 0, ring_cycles = 0, draws = 0, process_ns = 0, bindings = 0;
};
struct AbState {
  bool resolved = false;
  std::vector<Enhancement*> keys;
  std::string names;
  uint64_t period_ns = 0, report_ns = 0;
  bool on = true;  // the phase being measured
  uint64_t start_wall = 0, start_process = 0, start_bindings = 0, swaps = 0, switches = 0, next_report = 0;
  AbSample start{};
  AbPhase total[2];     // [0] off, [1] on
  AbPhase reported[2];  // the totals at the last report
};

AbState& Ab() {
  static AbState state;
  return state;
}

uint64_t NowNs() {
  return uint64_t(std::chrono::duration_cast<std::chrono::nanoseconds>(
                      std::chrono::steady_clock::now().time_since_epoch())
                      .count());
}

void AbResolve(AbState& s) {
  s.resolved = true;
  const std::string list = REXCVAR_GET(sasrt_ab_keys);
  size_t from = 0;
  while (from < list.size()) {
    size_t to = list.find(';', from);
    if (to == std::string::npos) to = list.size();
    std::string key = list.substr(from, to - from);
    from = to + 1;
    key.erase(0, key.find_first_not_of(" \t"));
    key.erase(key.find_last_not_of(" \t") + 1);
    if (key.empty()) continue;
    Enhancement* found = nullptr;
    for (Enhancement* e : Registered()) {
      if (key == e->key) found = e;
    }
    if (!found) {
      REXLOG_WARN("[ab] {}: not one of the port's own enhancement keys, left alone", key);
    } else if (!found->active) {
      REXLOG_WARN("[ab] {}: off at start, left alone (the A/B switches keys that are on)", key);
    } else {
      s.keys.push_back(found);
      s.names += (s.names.empty() ? "" : ";") + key;
    }
  }
  if (s.keys.empty()) return;
  s.period_ns = uint64_t(REXCVAR_GET(sasrt_ab_period_ms)) * 1000000ull;
  s.report_ns = uint64_t(std::max(1, REXCVAR_GET(sasrt_enhancements_report_s))) * 1000000000ull;
  REXLOG_INFO("[ab] in-run A/B of {}: switched off and on together every {} ms at a Swap; each phase measured",
              s.names, REXCVAR_GET(sasrt_ab_period_ms));
}

std::string AbPercent(double on, double off) {
  return off > 0.0 ? fmt::format("{:+.1f} %", (on / off - 1.0) * 100.0) : std::string("-");
}

AbPhase Minus(const AbPhase& a, const AbPhase& b) {
  return {a.swaps - b.swaps,           a.wall_ns - b.wall_ns, a.ring_work_ns - b.ring_work_ns,
          a.ring_cycles - b.ring_cycles, a.draws - b.draws,     a.process_ns - b.process_ns,
          a.bindings - b.bindings};
}

// One line per phase pair: the raw sums (tools/ab_summary.py adds up chosen windows) and the per-Swap / per-draw
// figures with on against off.
void AbLine(const char* what, const std::string& names, const AbPhase& on, const AbPhase& off) {
  const auto per = [](uint64_t a, uint64_t n) { return n ? double(a) / double(n) : 0.0; };
  const auto sums = [](const AbPhase& p) {
    return fmt::format("{} Swaps {:.3f} s ring {:.1f} ms {} draws {} cycles process {:.1f} ms {} bindings", p.swaps,
                       double(p.wall_ns) / 1e9, double(p.ring_work_ns) / 1e6, p.draws, p.ring_cycles,
                       double(p.process_ns) / 1e6, p.bindings);
  };
  const auto figures = [&](const AbPhase& p) {
    return fmt::format("{:.1f} Swaps per s, ring {:.2f} ms per Swap / {:.2f} us per draw{}, process CPU {:.1f} ms per "
                       "Swap, {:.2f} vertex bindings per draw",
                       per(p.swaps * 1000000000ull, p.wall_ns), per(p.ring_work_ns, p.swaps) / 1e6,
                       per(p.ring_work_ns, p.draws) / 1e3,
                       p.ring_cycles ? fmt::format(" / {:.1f} kcycles per draw", per(p.ring_cycles, p.draws) / 1e3)
                                     : std::string(),
                       per(p.process_ns, p.swaps) / 1e6, per(p.bindings, p.draws));
  };
  REXLOG_INFO("[ab] {} {}: on {} | off {} || on: {} | off: {} || on against off: ring per Swap {}, per draw {}{}, "
              "process CPU per Swap {}, Swaps per s {}",
              what, names, sums(on), sums(off), figures(on), figures(off),
              AbPercent(per(on.ring_work_ns, on.swaps), per(off.ring_work_ns, off.swaps)),
              AbPercent(per(on.ring_work_ns, on.draws), per(off.ring_work_ns, off.draws)),
              on.ring_cycles ? fmt::format(", cycles per draw {}", AbPercent(per(on.ring_cycles, on.draws),
                                                                          per(off.ring_cycles, off.draws)))
                             : std::string(),
              AbPercent(per(on.process_ns, on.swaps), per(off.process_ns, off.swaps)),
              AbPercent(per(on.swaps * 1000000000ull, on.wall_ns), per(off.swaps * 1000000000ull, off.wall_ns)));
}

// Every report period: the window since the last report (loading screens do not swamp the race: pick the windows),
// then the whole run.
void AbReport(AbState& s) {
  AbLine("window", s.names, Minus(s.total[1], s.reported[1]), Minus(s.total[0], s.reported[0]));
  AbLine(fmt::format("cumulative ({} switches)", s.switches).c_str(), s.names, s.total[1], s.total[0]);
  s.reported[0] = s.total[0];
  s.reported[1] = s.total[1];
}

}  // namespace

uint64_t g_ab_vertex_bindings = 0;

void AbSwap(const AbSample& now) {
  AbState& s = Ab();
  if (!s.resolved) AbResolve(s);
  if (s.keys.empty()) return;
  const uint64_t wall = NowNs();
  if (!s.start_wall) {  // the first Swap: the first phase (on) starts here
    s.start_wall = wall;
    s.start = now;
    s.start_process = MeProcessCpuNs();
    s.start_bindings = g_ab_vertex_bindings;
    s.next_report = wall + s.report_ns;
    return;
  }
  ++s.swaps;
  if (wall - s.start_wall < s.period_ns) return;
  const uint64_t process = MeProcessCpuNs();
  AbPhase& p = s.total[s.on];
  p.swaps += s.swaps;
  p.wall_ns += wall - s.start_wall;
  p.ring_work_ns += now.ring_work_ns - s.start.ring_work_ns;
  p.ring_cycles += now.ring_cycles - s.start.ring_cycles;
  p.draws += now.draws - s.start.draws;
  p.process_ns += process - s.start_process;
  p.bindings += g_ab_vertex_bindings - s.start_bindings;
  s.on = !s.on;
  // Read by plain loads elsewhere (once per use, either value exact); a relaxed atomic store here.
  for (Enhancement* e : s.keys) __atomic_store_n(&e->active, s.on, __ATOMIC_RELAXED);
  ++s.switches;
  s.start_wall = wall;
  s.start = now;
  s.start_process = process;
  s.start_bindings = g_ab_vertex_bindings;
  s.swaps = 0;
  if (wall >= s.next_report) {
    s.next_report = wall + s.report_ns;
    AbReport(s);
  }
}

bool Register(Enhancement* e) {
  Registered().push_back(e);
  return true;
}

bool GuestCodeMatches(const uint8_t* base, uint32_t address, uint32_t bytes, uint64_t fnv, const char* what) {
  uint64_t h = 0xCBF29CE484222325ull;
  const uint8_t* p = base + address;
  for (uint32_t i = 0; i < bytes; ++i) {
    h ^= p[i];
    h *= 0x100000001B3ull;
  }
  if (h != fnv) {
    REXLOG_WARN("[enh] {}: the game code at {:08X} is not the code it was written from (hash {:016X}, expected "
                "{:016X}); it stays off",
                what, address, h, fnv);
    return false;
  }
  return true;
}

bool GroupOn(Group group) {
  return group == Group::kCpu ? REXCVAR_GET(sasrt_cpu_enhancements) : REXCVAR_GET(sasrt_noncpu_enhancements);
}

void Apply() {
  std::string active, inactive;
  size_t active_count = 0;
  for (Enhancement* e : Registered()) {
    const bool own = e->own();
    e->active = own && GroupOn(e->group);
#if defined(__aarch64__)
    // sasrt_cpu_guest_cas_no_barrier: off puts the legacy `dmb ish` back after every compare-and-swap.
    if (e == &g_guest_cas_no_barrier) g_rex_atomic_legacy_barrier = e->active ? 0 : 1;
    // base port 150: the relaxed compare-and-swap and the split fences (the keys above).
    if (e == &g_guest_cas_relaxed) g_rex_guest_cas_seq_cst = e->active ? 0 : 1;
    if (e == &g_guest_fences_split) g_rex_guest_fence_full = e->active ? 0 : 1;
#endif
    std::string& list = e->active ? active : inactive;
    if (!list.empty()) {
      list += ", ";
    }
    list += e->key;
    if (own && !e->active) list += " (master off)";
    active_count += e->active;
  }
  size_t defaulted_on = 0;
  for (const Entry& e : kTable) {
    if (!GroupOn(e.group) && Active(e)) {
      rex::cvar::SetFlagByName(e.key, e.off);
    }
#if REX_PLATFORM_SWITCH
    // On the console a key the config does not mention means ON (its group master decides): a sasrt.toml left on the
    // SD card from an older build lacks the newer keys, which then stayed at their code defaults, mostly OFF (futari-nx
    // found 21 CPU enhancements off that way on 2026-10-06). A key set in the config, the environment or on the
    // command line is left as it is. The PC keeps the code defaults: its sasrt.toml lists no keys, and the PC
    // measurements in docs/ were made with them.
    if (GroupOn(e.group) && !Active(e) && !e.explicit_only &&
        rex::cvar::GetFlagSource(e.key) == rex::cvar::Source::kDefault) {
      rex::cvar::SetFlagByName(e.key, e.on);
      ++defaulted_on;
    }
#endif
    const bool on = Active(e);
    std::string& list = on ? active : inactive;
    if (!list.empty()) {
      list += ", ";
    }
    list += e.key;
    active_count += on;
  }
  if (REXCVAR_GET(sasrt_cpu_verify)) {
    rex::cvar::SetFlagByName("masseffect_native_verify_n", "2147483647");
    // The vertex copy self-check re-copies each copy with the plain loop into a new buffer and compares: on every
    // copy the ring fell to 4 frames per 10 s in this game's intro (docs/enhancements.md, "Verification"). Its first
    // 20,000 copies (normally 256) are checked instead.
    rex::cvar::SetFlagByName("masseffect_native_fast_copy_verify", "20000");
    REXLOG_INFO("[verify] verify mode ON: every self-check of the fast paths compares on every use (slower; test "
                "sessions only). Look for \"[verify] ... differences: 0\" every 10 s");
  }
#if REX_PLATFORM_SWITCH
  if (REXCVAR_GET(sasrt_handheld_gpu_boost) && GroupOn(Group::kNonCpu)) {
    RexSwitchApmRequestGpuMhz(460);
    RexSwitchApmApply();
  }
#endif
  REXLOG_INFO("[enhancements] sasrt-nx build {} {} ({}); masters: CPU {}, non-CPU {} | {} of {} active ({} not in the "
              "config, turned on): {} | off: {}",
              __DATE__, __TIME__, SASRT_BUILD_FLAVOR, REXCVAR_GET(sasrt_cpu_enhancements) ? "on" : "OFF",
              REXCVAR_GET(sasrt_noncpu_enhancements) ? "on" : "OFF", active_count,
              std::size(kTable) + Registered().size(), defaulted_on, active.empty() ? "none" : active,
              inactive.empty() ? "none" : inactive);
  CodegenChecksInit();
  FormsSelfCheck();
  ::banjo::BlurMicrobench();  // sasrt-nx (2026-11-13, base port 90): off unless blur_microbench
  StartReport();
}

}  // namespace sasrt::enhancements
