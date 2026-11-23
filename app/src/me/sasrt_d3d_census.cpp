// Sonic & All-Stars Racing Transformed: a census of the game's Direct3D entry points (sasrt_diag_d3d_census, a
// diagnostic; sa2-nx's method, docs/api-renderer.md in sa2-nx, step 1 of removing the guest Direct3D): how often each
// entry point the native layer would replace is called, and how much PM4 each outermost call writes into the command
// buffer (the device's write pointer, +48, before and after; a segment switch in between is counted, not measured).
//
// The Draw* functions are counted by their own hooks (sasrt_me_hooks.cpp calls Begin / End); the other entry points
// have census hooks here, which only call the original (and count while the cvar is on). The device is the one the
// Draw* calls were made on (r3), also for the entry points that are not device methods. Every 10 s a report lists
// calls per second, outermost calls, and PM4 words per outermost call. Changes nothing.

#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <string>

#include <fmt/format.h>

#include <rex/cvar.h>
#include <rex/hook.h>
#include <rex/logging.h>
#include <rex/ppc.h>

#include "me/sasrt_d3d_census.h"
#include "me/sasrt_api.h"
#include "renut_engine/sasrt_renut_yield.h"

REXCVAR_DEFINE_BOOL(sasrt_diag_d3d_census, false, "SASRT",
                    "Diagnostic: count the calls of the Direct3D entry points the native layer would replace and the "
                    "PM4 words each outermost call writes (a report every 10 s). Changes nothing")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

namespace sasrt::census {
namespace {

struct Entry {
  uint32_t address;
  const char* name;
  std::atomic<uint64_t> calls{0}, outermost{0}, words{0}, switches{0};
};

// The entry points (this game's addresses; sa2-nx's in brackets, matched by tools/d3d_match.py).
Entry g_entries[] = {
    {0x82CD18D0, "D3DDevice_DrawVertices [82565C60]"},
    {0x82CD1DB8, "D3DDevice_DrawIndexedVertices [82566078]"},
    {0x82CD1168, "D3DDevice_DrawVerticesUP [82565C18]"},
    {0x82CD0BB8, "D3DDevice_BeginVertices [82565758]"},
    {0x82CE71B0, "D3DDevice_Clear [82563AB0]"},
    {0x82CCB540, "window scissor writer [8254FCE8]"},
    {0x82CDCC98, "resolve entry [825656F8]"},
    {0x82CDB7C8, "D3DDevice_Resolve [825645A0]"},
    {0x82CD7D08, "D3DSurface_LockRect [825490E8]"},
    {0x82CE4F38, "D3DResource_Release [8254A4A8?]"},
    {0x82CE0EC8, "register groups re-sent [825555A0]"},
};

std::atomic<uint32_t> g_device{0};
thread_local int t_depth = 0;
std::atomic<int64_t> g_next_report_ms{0};

bool On() {
  static const bool on = REXCVAR_GET(sasrt_diag_d3d_census);
  return on;
}

uint32_t Load32(const uint8_t* base, uint32_t address) {
  uint32_t v;
  std::memcpy(&v, base + address + (address >= 0xE0000000u ? 0x1000u : 0u), 4);
  return __builtin_bswap32(v);
}

void Report() {
  const int64_t now = std::chrono::duration_cast<std::chrono::milliseconds>(
                          std::chrono::steady_clock::now().time_since_epoch()).count();
  int64_t due = g_next_report_ms.load(std::memory_order_relaxed);
  if (due == 0) {
    g_next_report_ms.compare_exchange_strong(due, now + 10000);
    return;
  }
  if (now < due || !g_next_report_ms.compare_exchange_strong(due, now + 10000)) return;
  std::string text;
  for (Entry& e : g_entries) {
    const uint64_t calls = e.calls.exchange(0, std::memory_order_relaxed);
    if (!calls) continue;
    const uint64_t outer = e.outermost.exchange(0, std::memory_order_relaxed);
    const uint64_t words = e.words.exchange(0, std::memory_order_relaxed);
    const uint64_t sw = e.switches.exchange(0, std::memory_order_relaxed);
    text += fmt::format("\n  sub_{:08X} {:<44} {:>9.1f} calls/s ({} outermost), {:.1f} PM4 words per outermost call, "
                        "{} segment switches",
                        e.address, e.name, double(calls) / 10.0, outer,
                        outer > sw ? double(words) / double(outer - sw) : 0.0, sw);
  }
  REXLOG_INFO("[d3d-census] last 10 s:{}", text.empty() ? std::string(" nothing") : text);
}

}  // namespace

Token Begin(uint32_t entry, const uint8_t* base, uint32_t device) {
  Token t;
  if (!On()) return t;
  if (device >= 0x40000000u && device < 0x7F000000u) g_device.store(device, std::memory_order_relaxed);
  t.entry = entry;
  t.outermost = t_depth++ == 0;
  const uint32_t d = g_device.load(std::memory_order_relaxed);
  if (t.outermost && d) {
    t.device = d;
    t.wptr = Load32(base, d + 48);
    t.limit = Load32(base, d + 52);
  }
  return t;
}

void End(const Token& t, const uint8_t* base) {
  if (!t.entry) return;
  --t_depth;
  for (Entry& e : g_entries) {
    if (e.address != t.entry) continue;
    e.calls.fetch_add(1, std::memory_order_relaxed);
    if (t.outermost) {
      e.outermost.fetch_add(1, std::memory_order_relaxed);
      if (t.device) {
        const uint32_t wptr = Load32(base, t.device + 48), limit = Load32(base, t.device + 52);
        if (limit != t.limit || wptr < t.wptr) e.switches.fetch_add(1, std::memory_order_relaxed);
        else e.words.fetch_add((wptr - t.wptr) / 4, std::memory_order_relaxed);
      }
    }
    break;
  }
  Report();
}

}  // namespace sasrt::census

// Census hooks of the entry points the renderer does not hook itself: the original, counted.
#define SASRT_CENSUS_HOOK(ADDR)                                                         \
  REX_EXTERN(__imp__sub_##ADDR);                                                        \
  REX_HOOK_RAW(sub_##ADDR) {                                                            \
    SASRT_RENUT_YIELD(sub_##ADDR)                                                       \
    const auto t = sasrt::census::Begin(0x##ADDR##u, base, ctx.r3.u32);                 \
    __imp__sub_##ADDR(ctx, base);                                                       \
    sasrt::census::End(t, base);                                                        \
  }

// The same at an address Renut's renderer hooks too (tools/renut_gpu_retarget.py: shared).
#define SASRT_CENSUS_HOOK_SHARED(ADDR)                                                  \
  REX_EXTERN(__imp__sub_##ADDR);                                                        \
  REX_HOOK_RAW(sub_##ADDR) {                                                            \
    SASRT_RENUT_YIELD_SHARED(sub_##ADDR)                                                \
    const auto t = sasrt::census::Begin(0x##ADDR##u, base, ctx.r3.u32);                 \
    __imp__sub_##ADDR(ctx, base);                                                       \
    sasrt::census::End(t, base);                                                        \
  }

// D3DDevice_BeginVertices: native first (sasrt_api_draws; it returns the inline vertices' address in r3).
REX_EXTERN(__imp__sub_82CD0BB8);
REX_HOOK_RAW(sub_82CD0BB8) {
  SASRT_RENUT_YIELD_SHARED(sub_82CD0BB8)  // sasrt_renderer = "renut" (renut_engine/sasrt_renut_yield.h)
  if (sasrt::api::BeginVertices(ctx, base)) return;
  const auto t = sasrt::census::Begin(0x82CD0BB8u, base, ctx.r3.u32);
  __imp__sub_82CD0BB8(ctx, base);
  sasrt::census::End(t, base);
}
// D3DDevice_Clear: native first (sasrt_api_clears).
REX_EXTERN(__imp__sub_82CE71B0);
REX_HOOK_RAW(sub_82CE71B0) {
  SASRT_RENUT_YIELD(sub_82CE71B0)  // sasrt_renderer = "renut" (renut_engine/sasrt_renut_yield.h)
  if (sasrt::api::Clear(ctx, base)) return;
  const auto t = sasrt::census::Begin(0x82CE71B0u, base, ctx.r3.u32);
  __imp__sub_82CE71B0(ctx, base);
  sasrt::census::End(t, base);
}
// Direct3D's inline-data allocator [8254D9A8] (sasrt_api_draws / sasrt_api_clears, verify mode): inside a shadow run of
// an original on the device copy it answers at once with a scratch block (sasrt::api::ShadowInlineAlloc).
REX_EXTERN(__imp__sub_82CDDF30);
REX_HOOK_RAW(sub_82CDDF30) {
  SASRT_RENUT_YIELD_SHARED(sub_82CDDF30)  // sasrt_renderer = "renut" (renut_engine/sasrt_renut_yield.h)
  if (sasrt::api::ShadowInlineAlloc(ctx, base)) return;
  __imp__sub_82CDDF30(ctx, base);
}
// The window scissor writer (SetViewport, SetScissorRect, surface setters): native first (sasrt_api_draws).
REX_EXTERN(__imp__sub_82CCB540);
REX_HOOK_RAW(sub_82CCB540) {
  SASRT_RENUT_YIELD_SHARED(sub_82CCB540)  // sasrt_renderer = "renut" (renut_engine/sasrt_renut_yield.h)
  if (sasrt::api::WindowScissor(ctx, base)) return;
  const auto t = sasrt::census::Begin(0x82CCB540u, base, ctx.r3.u32);
  __imp__sub_82CCB540(ctx, base);
  sasrt::census::End(t, base);
}
SASRT_CENSUS_HOOK_SHARED(82CDCC98)  // resolve entry
SASRT_CENSUS_HOOK(82CDB7C8)  // D3DDevice_Resolve
SASRT_CENSUS_HOOK(82CD7D08)  // D3DSurface_LockRect
SASRT_CENSUS_HOOK(82CE4F38)  // D3DResource_Release
SASRT_CENSUS_HOOK(82CE0EC8)  // register groups re-sent
