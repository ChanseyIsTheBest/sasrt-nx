#pragma once

// futari-nx (sasrt-nx takes it): count of every self-check that found the fast path and the reference path disagreeing
// (each DIFFERENCE / MISMATCH log line of the renderer). With sasrt_cpu_verify the self-checks compare on every use
// and the "[verify]" report line prints this count: 0 means every fast path gave the same result as the original path
// for the whole run.
#include <atomic>
#include <cstdint>

namespace me::native {

inline std::atomic<uint64_t> g_verify_differences{0};

// sasrt-nx (2026-11-08, katamari-nx's): calls the guards of the localized copies compared (app/src/cpu/banjo_hot_guest.cpp).
inline std::atomic<uint64_t> g_verify_native_checks{0};

inline void VerifyDifference() { g_verify_differences.fetch_add(1, std::memory_order_relaxed); }

}  // namespace me::native
