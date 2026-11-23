// The game's frame counter, and the tracing of its Direct3D (stage 4 of the port: confirm the map of the game's D3D
// before replacing anything).
//
// The game carries the Xbox 360 XDK's Direct3D statically linked (XDK 2.0.21119, around 0x82CDxxxx). Each function
// listed in g_traced is wrapped: the wrapper always calls the original, and with sasrt_d3d_trace=true logs every 5
// seconds how often each one ran and from where (its most frequent return addresses). With the cvar off it only adds
// one branch per call.
//
// How the wrapping works: each recompiled function sub_XXXXXXXX is a weak alias of __imp__sub_XXXXXXXX. The strong
// definitions here win for every caller (direct, and indirect through the function table, which is how the game's
// thunks in .xidata reach it), and __imp__ is still the original.

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <string>
#include <mutex>
#include <unordered_map>
#include <vector>

#include <rex/cvar.h>
#include <rex/hook.h>
#include <rex/logging.h>
#include <rex/system/kernel_state.h>
#include <rex/system/xmemory.h>

#include "sasrt_capture.h"
#include "sasrt_renderdoc.h"
#include "renut_engine/sasrt_renut_yield.h"

REXCVAR_DEFINE_BOOL(sasrt_d3d_trace, false, "SASRT",
                    "Trace the game's Direct3D: count the calls to the wrapped functions (docs/sasrt-notes.md) and "
                    "log them every 5 s with their most frequent callers (the callers need code generated without "
                    "elide_lr_stores, which drops the guest link-register stores)");

REXCVAR_DEFINE_STRING(sasrt_watch_floats, "", "SASRT",
                      "Diagnostic: physical addresses (hex, comma separated) whose 32-bit float is logged every 5 s "
                      "at a Swap, e.g. the 1x1 exposure texture both renderers resolve (09DBB000)");

namespace {

// sasrt_watch_floats: the parsed addresses (once) and when they were last logged.
std::vector<uint32_t> WatchedAddresses() {
  static const std::vector<uint32_t> addresses = [] {
    std::vector<uint32_t> out;
    std::string list = REXCVAR_GET(sasrt_watch_floats);
    std::erase(list, '"');
    size_t pos = 0;
    while (pos < list.size()) {
      size_t end = list.find(',', pos);
      if (end == std::string::npos) end = list.size();
      const std::string item = list.substr(pos, end - pos);
      if (!item.empty()) out.push_back(uint32_t(std::strtoul(item.c_str(), nullptr, 16)));
      pos = end + 1;
    }
    return out;
  }();
  return addresses;
}

void LogWatchedFloats() {
  static std::atomic<int64_t> next_ms{0};
  const auto& addresses = WatchedAddresses();
  if (addresses.empty()) return;
  const auto now = std::chrono::duration_cast<std::chrono::milliseconds>(
                       std::chrono::steady_clock::now().time_since_epoch()).count();
  int64_t due = next_ms.load(std::memory_order_relaxed);
  if (now < due || !next_ms.compare_exchange_strong(due, now + 5000)) return;
  auto* memory = rex::system::kernel_state()->memory();
  std::string text;
  for (uint32_t address : addresses) {
    const uint8_t* p = memory->TranslatePhysical<const uint8_t*>(address);
    uint32_t bits;
    std::memcpy(&bits, p, 4);
    bits = __builtin_bswap32(bits);
    float value;
    std::memcpy(&value, &bits, 4);
    text += fmt::format(" {:08X}={:.6g}", address, value);
  }
  REXLOG_INFO("[watch]{}", text);
}

struct Traced {
  uint32_t address;
  const char* what;
  std::atomic<uint64_t> calls{0};
  std::mutex mu;
  std::unordered_map<uint32_t, uint64_t> callers;  // return address -> calls
};

Traced g_traced[] = {
    {0x82CD9AE8, "D3DDevice_Swap (the only caller of VdSwap)"},
};

std::atomic<int64_t> g_next_report_ms{0};

void Report() {
  const auto now = std::chrono::duration_cast<std::chrono::milliseconds>(
                       std::chrono::steady_clock::now().time_since_epoch())
                       .count();
  int64_t due = g_next_report_ms.load(std::memory_order_relaxed);
  if (now < due || !g_next_report_ms.compare_exchange_strong(due, now + 5000)) {
    return;
  }
  REXLOG_INFO("[d3d-trace] calls since the last report:");
  for (auto& t : g_traced) {
    const uint64_t calls = t.calls.exchange(0, std::memory_order_relaxed);
    if (!calls) {
      continue;
    }
    std::vector<std::pair<uint32_t, uint64_t>> top;
    {
      std::lock_guard lock(t.mu);
      top.assign(t.callers.begin(), t.callers.end());
      t.callers.clear();
    }
    std::sort(top.begin(), top.end(), [](auto& a, auto& b) { return a.second > b.second; });
    std::string from;
    for (size_t i = 0; i < top.size() && i < 4; ++i) {
      from += fmt::format(" {:08X}x{}", top[i].first, top[i].second);
    }
    REXLOG_INFO("[d3d-trace]   sub_{:08X} {:<42} {:>8} calls, from{}", t.address, t.what, calls, from);
  }
}

inline void Record(Traced& t, const PPCContext& ctx) {
  t.calls.fetch_add(1, std::memory_order_relaxed);
  const uint32_t lr = uint32_t(ctx.lr);
  std::lock_guard lock(t.mu);
  ++t.callers[lr];
}

}  // namespace

// D3DDevice_Swap: once per presented frame. Counts the game's frames, always: the video recorder (sasrt_capture.cpp)
// captures one image per frame.
extern "C" REX_FUNC(__imp__sub_82CD9AE8);
REX_HOOK_RAW(sub_82CD9AE8) {
#if SASRT_RENUT_RENDERER
  if (::banjo::renut_gpu::Active()) {  // sasrt_renderer = "renut": Renut's Swap (renut_engine/sasrt_renut_yield.h)
    renut_native_sub_82CD9AE8(ctx, base);  // counts g_sasrt_game_frames itself (d3d/hooks/device.cpp)
    sasrt::renderdoc::AfterSwap();         // sasrt_renderdoc_capture_s (a diagnostic)
    return;
  }
#endif
  if (REXCVAR_GET(sasrt_d3d_trace)) {
    Record(g_traced[0], ctx);
    Report();
  }
  __imp__sub_82CD9AE8(ctx, base);
  g_sasrt_game_frames.fetch_add(1, std::memory_order_relaxed);
  LogWatchedFloats();
  sasrt::renderdoc::AfterSwap(true);  // sasrt_renderdoc_capture_s with the emulated GPU (a diagnostic)
}
