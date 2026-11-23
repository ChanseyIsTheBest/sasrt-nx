// Sonic & All-Stars Racing Transformed hooks for the native renderer (src/me, from masseffect-nx through banjo-nx and
// sa2-nx), with this game's addresses (docs/sasrt-notes.md, "Direct3D": the same XDK library as SA2's, found by
// matching SA2's named functions; every hooked function has SA2's code with other global addresses).
//
// The renderer reads the game's PM4 ring by itself; these hooks only feed it what the ring cannot say:
//
//   - Shader objects. NoteShaderObject reads the container copy inside a D3D shader object and its microcode pointer.
//     The draw-time shader load is sub_82CE27D8 (r3 = device; SA2's sub_82556A60, the same code): it reads the
//     bound VS from device+13072 and the PS from device+13068 (XDK 21119, as SA2's 21076), so the
//     objects are noted there, before the original patches the VS for the vertex declaration.
//   - Draw records, a hint for pairing (NoteDrawCall: primitive type, then r5..r7 as D3D received them):
//       D3DDevice_DrawVertices        sub_82CD18D0 (dev, type, start, count)
//       D3DDevice_DrawIndexedVertices sub_82CD1DB8 (dev, type, base, start, count)
//       D3DDevice_DrawVerticesUP      sub_82CD1168 (dev, type, count, data, stride)
//   - Shader containers for the library (sasrt_dump_shaders = true): the blob D3DDevice_CreateVertexShader (sub_82CC64E8)
//     and D3DDevice_CreatePixelShader (sub_82CC61F0) receive in r3. It describes itself: [0] flags, [1] header size
//     (the microcode starts there), [2] microcode size. Written whole to shaders/vs_<hash>.bin / ps_<hash>.bin next to
//     the executable, once each; tools/build_shader_library.sh turns the folder into the shader package.
//   - The direct renderer, step 1 (sasrt_cpu_direct_state, sa2-nx's): around each of the three draw functions,
//     BeginDrawDirect and EndDrawDirect turn the state packets the draw function wrote into a host record the ring
//     applies (one NOP packet covers them; the draw packet and every address Direct3D keeps stay where they were). The
//     only guest memory a hook writes: the NOP's three words over the packets' first three, which no guest code reads
//     back. Direct3D's own Clear and Resolve draws keep their PM4.
//
// The game frame counter (D3DDevice_Swap, sub_82CD9AE8) lives in src/sasrt_d3d_trace.cpp. Every hook here calls the original;
// none changes a PPC register.

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <mutex>
#include <string>
#include <system_error>
#include <unordered_set>
#include <vector>

#include <fmt/format.h>

#include <rex/cvar.h>
#include <rex/filesystem.h>
#include <rex/hook.h>
#include <rex/logging.h>
#include <rex/platform.h>
#include <rex/ppc.h>
#include <rex/system/kernel_state.h>
#include <rex/system/xmemory.h>

#define XXH_INLINE_ALL
#include <xxhash.h>

#include "me/me_native_system.h"
#include "me/sasrt_d3d_census.h"
#include "me/sasrt_api.h"
#include "renut_engine/sasrt_renut_yield.h"

REXCVAR_DEFINE_BOOL(sasrt_dump_shaders, false, "SASRT",
                    "Write every shader container the game creates to shaders/ next to the executable "
                    "(vs_<hash>.bin / ps_<hash>.bin), for tools/build_shader_library.sh");
REXCVAR_DEFINE_INT32(sasrt_dump_shaders_scan_s, 0, "SASRT",
                     "With sasrt_dump_shaders: every N seconds also look through guest memory for the shader objects "
                     "the game has loaded and dump those not drawn yet, so one visit to a track gives all its shaders "
                     "(PC only; 0 = off)");

namespace {

// Guest loads through the memory's translation: shader objects live in the image (0x83xxxxxx) and in physical
// views (0xA0000000 and up), and on Windows the 0xE0000000 view is not at base + address.
inline uint32_t LoadV32(uint32_t address) {
  uint32_t v;
  std::memcpy(&v, rex::system::kernel_state()->memory()->TranslateVirtual<const uint8_t*>(address), 4);
  return __builtin_bswap32(v);
}

// Where this game's shader objects are: statically in the image's .data (0x83xxxxxx), in physical allocations
// (0xB8xxxxxx), or on the heap like other games' (0x40000000-0x7EFFFFFF).
inline bool IsShaderObjectAddress(uint32_t a) {
  return (a >= 0x40000000u && a < 0x7F000000u) || (a >= 0x80000000u && a < 0x90000000u) || a >= 0xA0000000u;
}

inline uint32_t Load32(const uint8_t* base, uint32_t address) {
  uint32_t v;
  std::memcpy(&v, base + address, 4);
  return __builtin_bswap32(v);
}

constexpr uint32_t kDeviceVertexShader = 13072;  // 0x3310
constexpr uint32_t kDevicePixelShader = 13068;   // 0x330C

// The draw records (NoteDrawCall) read the bound shaders from the same device fields.
const bool g_device_layout_set = [] {
  me::native::SetDeviceShaderOffsets(kDeviceVertexShader, kDevicePixelShader);
  return true;
}();

std::mutex g_dump_mutex;
std::unordered_set<uint64_t> g_dumped;

std::atomic<uint32_t> g_create_calls{0};

void DumpShaderBlob(const uint8_t* base, uint32_t blob_address, bool vertex) {
  if (g_create_calls.fetch_add(1, std::memory_order_relaxed) < 4) {
    REXLOG_INFO("[shaders] Create{}Shader(blob {:08X}), dump {}", vertex ? "Vertex" : "Pixel", blob_address,
                REXCVAR_GET(sasrt_dump_shaders) ? "on" : "off");
  }
  if (!REXCVAR_GET(sasrt_dump_shaders) || !blob_address) {
    return;
  }
  const uint32_t header = Load32(base, blob_address + 4);
  const uint32_t ucode = Load32(base, blob_address + 8);
  if (header < 12 || header > (1u << 20) || !ucode || ucode > (1u << 20)) {
    REXLOG_WARN("[shaders] implausible {} blob at {:08X} (header {}, microcode {}), skipped", vertex ? "VS" : "PS",
                blob_address, header, ucode);
    return;
  }
  const uint8_t* blob = base + blob_address;
  const size_t size = size_t(header) + ucode;
  const uint64_t hash = XXH3_64bits(blob, size);
  {
    std::lock_guard lock(g_dump_mutex);
    if (!g_dumped.insert(hash).second) {
      return;
    }
  }
  const auto folder = rex::filesystem::GetExecutableFolder() / "shaders";
  std::error_code ec;
  std::filesystem::create_directories(folder, ec);
  const auto path = folder / fmt::format("{}_{:016x}.bin", vertex ? "vs" : "ps", hash);
  std::ofstream(path, std::ios::binary).write(reinterpret_cast<const char*>(blob), std::streamsize(size));
}

// The game builds its shader objects itself: it never calls D3DDevice_CreateVertexShader/CreatePixelShader for them
// (no call in a boot to the race, 2026-10-05); the objects are static ones in the image's .data (0x83xxxxxx) and
// physical allocations (0xB8xxxxxx). So with
// sasrt_dump_shaders the draw-time shader load also writes the container of each bound object, assembled the way the
// renderer's NoteShaderObject reads it: the container's virtual part is a copy inside the object (vertex +0x368,
// pixel +0x28; same layout as SA2's), its physical part (the microcode) is at the object's microcode pointer (vertex
// +0x20, pixel +0x18), a physical address. Called before the original, so a vertex shader is still unpatched by its
// first vertex declaration.
std::unordered_set<uint32_t> g_dumped_objects;

void DumpBoundShader(const uint8_t* base, uint32_t object, bool vertex) {
  if (!IsShaderObjectAddress(object) || (LoadV32(object) & 0xFF) != (vertex ? 6u : 7u)) {
    return;
  }
  {
    std::lock_guard lock(g_dump_mutex);
    if (!g_dumped_objects.insert(object << 1 | (vertex ? 1 : 0)).second) {
      return;
    }
  }
  const uint32_t header = object + (vertex ? 0x368 : 0x28);
  const uint32_t virtual_size = LoadV32(header + 4);
  const uint32_t physical_size = LoadV32(header + 8);
  const uint32_t microcode = LoadV32(object + (vertex ? 0x20 : 0x18));
  if ((LoadV32(header) & 0xFFFFFF00u) != 0x102A1100u || virtual_size < 28 || virtual_size > 0x40000 ||
      !physical_size || physical_size > 0x40000 || microcode < 0xA0000000u) {
    REXLOG_WARN("[shaders] bound {} object {:08X} has no container (word {:08X}, sizes {}/{}, microcode {:08X})",
                vertex ? "VS" : "PS", object, LoadV32(header), virtual_size, physical_size, microcode);
    return;
  }
  std::vector<uint8_t> container(size_t(virtual_size) + physical_size);
  std::memcpy(container.data(), rex::system::kernel_state()->memory()->TranslateVirtual<const uint8_t*>(header),
              virtual_size);
  // The microcode is in a physical-memory view; on Windows the SDK shifts the 0xE0000000 view, so translate.
  const uint8_t* code = rex::system::kernel_state()->memory()->TranslateVirtual<const uint8_t*>(microcode);
  std::memcpy(container.data() + virtual_size, code, physical_size);
  const uint64_t hash = XXH3_64bits(container.data(), container.size());
  {
    std::lock_guard lock(g_dump_mutex);
    if (!g_dumped.insert(hash).second) {
      return;
    }
  }
  const auto folder = rex::filesystem::GetExecutableFolder() / "shaders";
  std::error_code ec;
  std::filesystem::create_directories(folder, ec);
  const auto path = folder / fmt::format("{}_{:016x}.bin", vertex ? "vs" : "ps", hash);
  std::ofstream(path, std::ios::binary).write(reinterpret_cast<const char*>(container.data()),
                                              std::streamsize(container.size()));
}

#if !REX_PLATFORM_SWITCH
// sasrt_dump_shaders_scan_s: the draw-time dump only sees shaders that get drawn, so a track's shaders came one race
// stretch at a time. A track's package holds them all as objects once it is loaded, so this looks through guest
// memory for objects with DumpBoundShader's layout (type 6/7 in the first word, the container's virtual part at
// +0x368/+0x28, the microcode pointer at +0x20/+0x18) and dumps those not drawn yet. Objects already drawn are left to
// the draw-time dump, which saw them before Direct3D patched their fetches. Only committed, readable regions of the
// guest heaps are read (freed physical memory is decommitted on the host, so the raw physical arena is not readable
// throughout), including the microcode each object points at, so a stale object cannot fault. PC only: on the Switch
// physical memory is committed as it is touched.
struct ScanCounts {
  uint32_t objects = 0, written = 0, unreadable = 0;
};

// Whether [address, address + size) lies in one committed, readable region of its heap.
bool Readable(rex::memory::Memory* memory, uint32_t address, uint32_t size) {
  auto* heap = memory->LookupHeap(address);
  rex::memory::HeapAllocationInfo info{};
  if (!heap || address < heap->heap_base() || !heap->QueryRegionInfo(address, &info)) {
    return false;
  }
  const uint32_t into = address & (heap->page_size() - 1);
  return (info.state & rex::memory::kMemoryAllocationCommit) && (info.protect & rex::memory::kMemoryProtectRead) &&
         info.region_size > into && info.region_size - into >= size;
}

void DumpScannedObject(const uint8_t* object, const uint8_t* end, uint32_t guest_object, bool vertex,
                       ScanCounts& counts) {
  auto* memory = rex::system::kernel_state()->memory();
  const auto load = [](const uint8_t* p) {
    uint32_t v;
    std::memcpy(&v, p, 4);
    return __builtin_bswap32(v);
  };
  const uint8_t* header = object + (vertex ? 0x368 : 0x28);
  const uint32_t virtual_size = load(header + 4);
  const uint32_t physical_size = load(header + 8);
  const uint32_t microcode = load(object + (vertex ? 0x20 : 0x18));
  if (virtual_size < 28 || virtual_size > 0x40000 || !physical_size || physical_size > 0x40000 ||
      (physical_size & 3) || microcode < 0xA0000000u || virtual_size > size_t(end - header)) {
    return;
  }
  ++counts.objects;
  {
    std::lock_guard lock(g_dump_mutex);
    if (g_dumped_objects.count(guest_object << 1 | (vertex ? 1 : 0))) {
      return;
    }
  }
  if (!Readable(memory, microcode, physical_size)) {
    ++counts.unreadable;
    return;
  }
  std::vector<uint8_t> container(size_t(virtual_size) + physical_size);
  std::memcpy(container.data(), header, virtual_size);
  std::memcpy(container.data() + virtual_size, memory->TranslateVirtual<const uint8_t*>(microcode), physical_size);
  const uint64_t hash = XXH3_64bits(container.data(), container.size());
  {
    std::lock_guard lock(g_dump_mutex);
    if (!g_dumped.insert(hash).second) {
      return;
    }
  }
  const auto folder = rex::filesystem::GetExecutableFolder() / "shaders";
  std::error_code ec;
  std::filesystem::create_directories(folder, ec);
  const auto path = folder / fmt::format("{}_{:016x}.bin", vertex ? "vs" : "ps", hash);
  if (!std::filesystem::exists(path, ec)) {
    std::ofstream(path, std::ios::binary).write(reinterpret_cast<const char*>(container.data()),
                                                std::streamsize(container.size()));
    ++counts.written;
  }
}

// Every word that starts a container (0x102A11xx) is checked as the virtual part of a pixel object (0x28 bytes in)
// and of a vertex object (0x368 bytes in). `guest` is the guest address of host[0].
void ScanRange(const uint8_t* host, size_t size, uint32_t guest, ScanCounts& counts) {
  for (size_t off = 0x28; off + 12 <= size; off += 4) {
    if (host[off] != 0x10 || host[off + 1] != 0x2A || host[off + 2] != 0x11) {
      continue;
    }
    for (const bool vertex : {false, true}) {
      const size_t at = vertex ? 0x368 : 0x28;
      if (off < at || host[off - at + 3] != (vertex ? 6 : 7)) {
        continue;
      }
      DumpScannedObject(host + off - at, host + size, guest + uint32_t(off - at), vertex, counts);
    }
  }
}

void ScanShaderObjects() {
  auto* memory = rex::system::kernel_state()->memory();
  const auto start = std::chrono::steady_clock::now();
  ScanCounts counts;
  // The virtual heaps (the 0x40000000 heap, the image's .data, the XEX heap) and the three views of physical memory
  // (the game's physical allocations are 0xB8xxxxxx: the 0xA0000000 view), committed regions only.
  for (uint32_t heap_base : {0x40000000u, 0x80000000u, 0x90000000u, 0xA0000000u, 0xC0000000u, 0xE0000000u}) {
    auto* heap = memory->LookupHeap(heap_base);
    if (!heap) {
      continue;
    }
    const uint32_t end = heap->heap_base() + heap->heap_size();
    for (uint32_t a = heap->heap_base(); a < end;) {
      rex::memory::HeapAllocationInfo info{};
      if (!heap->QueryRegionInfo(a, &info) || !info.region_size) {
        break;
      }
      if ((info.state & rex::memory::kMemoryAllocationCommit) && (info.protect & rex::memory::kMemoryProtectRead)) {
        ScanRange(memory->TranslateVirtual<const uint8_t*>(a), std::min<uint32_t>(info.region_size, end - a), a,
                  counts);
      }
      if (info.region_size >= end - a) {
        break;
      }
      a += info.region_size;
    }
  }
  REXLOG_INFO("[shaders] scan: {} shader objects in memory, {} new containers written to shaders/, {} with "
              "unreadable microcode ({:.0f} ms)",
              counts.objects, counts.written, counts.unreadable,
              std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - start).count());
}

void MaybeScanShaderObjects() {
  const int32_t every = REXCVAR_GET(sasrt_dump_shaders_scan_s);
  if (every <= 0) {
    return;
  }
  static auto next = std::chrono::steady_clock::now() + std::chrono::seconds(every);
  const auto now = std::chrono::steady_clock::now();
  if (now < next) {
    return;
  }
  next = now + std::chrono::seconds(every);
  ScanShaderObjects();
}
#else
void MaybeScanShaderObjects() {}
#endif

}  // namespace

// Draw-time shader load (FlushState's shader part, called from every Draw*).
REX_EXTERN(__imp__sub_82CE27D8);
REX_HOOK_RAW(sub_82CE27D8) {
  SASRT_RENUT_YIELD(sub_82CE27D8)  // sasrt_renderer = "renut" (renut_engine/sasrt_renut_yield.h)
  const uint32_t device = ctx.r3.u32;
  if (device >= 0x40000000 && device < 0x7F000000) {
    if (REXCVAR_GET(sasrt_dump_shaders)) {
      DumpBoundShader(base, Load32(base, device + kDeviceVertexShader), true);
      DumpBoundShader(base, Load32(base, device + kDevicePixelShader), false);
      MaybeScanShaderObjects();
    }
    const uint32_t vs = Load32(base, device + kDeviceVertexShader), ps = Load32(base, device + kDevicePixelShader);
    if (!me::native::ShaderObjectsFinished(vs, ps)) {  // sasrt_cpu_note_shader_pair: both finished, both skipped
      me::native::NoteShaderObject(base, vs, true);
      me::native::NoteShaderObject(base, ps, false);
    }
  }
  __imp__sub_82CE27D8(ctx, base);
}

// Each draw hook also hands the state packets the draw function writes to the ring as a host record
// (sasrt_cpu_direct_state: BeginDrawDirect before the original, EndDrawDirect right after it).
REX_EXTERN(__imp__sub_82CD18D0);
REX_HOOK_RAW(sub_82CD18D0) {  // D3DDevice_DrawVertices
  SASRT_RENUT_YIELD_SHARED(sub_82CD18D0)  // sasrt_renderer = "renut" (renut_engine/sasrt_renut_yield.h)
  if (sasrt::api::DrawVertices(ctx, base)) return;  // sasrt_api_draws: native, records instead of PM4
  const auto direct = me::native::BeginDrawDirect(base, ctx.r3.u32);
  me::native::NoteDrawCall(base, ctx.r3.u32, ctx.r4.u32, ctx.r5.u32, ctx.r6.u32, ctx.r7.u32);
  const auto census = sasrt::census::Begin(0x82CD18D0u, base, ctx.r3.u32);  // sasrt_diag_d3d_census
  __imp__sub_82CD18D0(ctx, base);
  sasrt::census::End(census, base);
  me::native::EndDrawDirect(base, direct);
}

REX_EXTERN(__imp__sub_82CD1DB8);
REX_HOOK_RAW(sub_82CD1DB8) {  // D3DDevice_DrawIndexedVertices
  SASRT_RENUT_YIELD_SHARED(sub_82CD1DB8)  // sasrt_renderer = "renut" (renut_engine/sasrt_renut_yield.h)
  if (sasrt::api::DrawIndexedVertices(ctx, base)) return;  // sasrt_api_draws: native, records instead of PM4
  const auto direct = me::native::BeginDrawDirect(base, ctx.r3.u32);
  me::native::NoteDrawCall(base, ctx.r3.u32, ctx.r4.u32, ctx.r5.u32, ctx.r6.u32, ctx.r7.u32);
  const auto census = sasrt::census::Begin(0x82CD1DB8u, base, ctx.r3.u32);  // sasrt_diag_d3d_census
  __imp__sub_82CD1DB8(ctx, base);
  sasrt::census::End(census, base);
  me::native::EndDrawDirect(base, direct);
}

REX_EXTERN(__imp__sub_82CD1168);
REX_HOOK_RAW(sub_82CD1168) {  // D3DDevice_DrawVerticesUP
  SASRT_RENUT_YIELD_SHARED(sub_82CD1168)  // sasrt_renderer = "renut" (renut_engine/sasrt_renut_yield.h)
  if (sasrt::api::DrawVerticesUP(ctx, base)) return;  // sasrt_api_draws: native, records instead of PM4
  const auto direct = me::native::BeginDrawDirect(base, ctx.r3.u32);
  me::native::NoteDrawCall(base, ctx.r3.u32, ctx.r4.u32, ctx.r5.u32, ctx.r6.u32, ctx.r7.u32);
  const auto census = sasrt::census::Begin(0x82CD1168u, base, ctx.r3.u32);  // sasrt_diag_d3d_census
  __imp__sub_82CD1168(ctx, base);
  sasrt::census::End(census, base);
  me::native::EndDrawDirect(base, direct);
}

// sasrt_cpu_direct_flush (the direct renderer, step 2; sa2-nx's): Direct3D's three state flush functions, called by
// the Draw* functions' inlined FlushState (r3 = device, r4 = dirty mask, bit 63 first, r5 = first register, r6 =
// shadow). Inside a converted draw call they write the call's direct record themselves (FlushRunsDirect); otherwise,
// or when the original would take its slow path, they run as before. The dirty masks stay the caller's business.
REX_EXTERN(__imp__sub_82CE1760);
REX_HOOK_RAW(sub_82CE1760) {  // shader constants: 16 registers a bit (r5 = 0x4000 VS / 0x4400 PS)
  SASRT_RENUT_YIELD(sub_82CE1760)  // sasrt_renderer = "renut" (renut_engine/sasrt_renut_yield.h)
  if (me::native::FlushRunsDirect(ctx, base, ctx.r3.u32, ctx.r4.u64, ctx.r5.u32, ctx.r6.u32,
                                  me::native::FlushKind::kConstants, __imp__sub_82CE1760))
    return;
  __imp__sub_82CE1760(ctx, base);
}

REX_EXTERN(__imp__sub_82CE15C0);
REX_HOOK_RAW(sub_82CE15C0) {  // fetch constants: 6 registers a bit from 0x4800 (shadow device+1152), then 0x5000
  SASRT_RENUT_YIELD(sub_82CE15C0)  // sasrt_renderer = "renut" (renut_engine/sasrt_renut_yield.h)
  if (me::native::FlushRunsDirect(ctx, base, ctx.r3.u32, ctx.r4.u64, 0x4800, ctx.r3.u32 + 1152,
                                  me::native::FlushKind::kFetch, __imp__sub_82CE15C0))
    return;
  __imp__sub_82CE15C0(ctx, base);
}

REX_EXTERN(__imp__sub_82CE1310);
REX_HOOK_RAW(sub_82CE1310) {  // register groups: 1 register a bit
  SASRT_RENUT_YIELD(sub_82CE1310)  // sasrt_renderer = "renut" (renut_engine/sasrt_renut_yield.h)
  if (me::native::FlushRunsDirect(ctx, base, ctx.r3.u32, ctx.r4.u64, ctx.r5.u32, ctx.r6.u32,
                                  me::native::FlushKind::kGroups, __imp__sub_82CE1310))
    return;
  __imp__sub_82CE1310(ctx, base);
}

// D3DDevice_BeginTiling / EndTiling (predicated tiling): the draws in between keep their packets (the tiled range runs
// once per tile; sasrt_cpu_direct_state), and the first calls log where Direct3D writes its command buffer before and
// after (device+48 the last word written, +52 / +56 the segment's limits).
namespace {
std::atomic<int> g_tiling_logs{0};
void LogTiling(const uint8_t* base, uint32_t device, const char* what, const char* when) {
  if (device < 0x40000000 || device >= 0x7F000000 || g_tiling_logs.fetch_add(1, std::memory_order_relaxed) >= 24) return;
  REXLOG_INFO("[tiling] {} {}: write pointer {:08X}, segment end {:08X} / {:08X}", what, when, Load32(base, device + 48),
              Load32(base, device + 52), Load32(base, device + 56));
}
}  // namespace

REX_EXTERN(__imp__sub_82CE7868);
REX_HOOK_RAW(sub_82CE7868) {  // D3DDevice_BeginTiling
  SASRT_RENUT_YIELD_SHARED(sub_82CE7868)  // sasrt_renderer = "renut" (renut_engine/sasrt_renut_yield.h)
  const uint32_t device = ctx.r3.u32;
  LogTiling(base, device, "BeginTiling", "before");
  me::native::NoteTiling(true);
  __imp__sub_82CE7868(ctx, base);
  LogTiling(base, device, "BeginTiling", "after");
}

REX_EXTERN(__imp__sub_82CE8098);
REX_HOOK_RAW(sub_82CE8098) {  // D3DDevice_EndTiling
  SASRT_RENUT_YIELD_SHARED(sub_82CE8098)  // sasrt_renderer = "renut" (renut_engine/sasrt_renut_yield.h)
  const uint32_t device = ctx.r3.u32;
  LogTiling(base, device, "EndTiling", "before");
  __imp__sub_82CE8098(ctx, base);
  me::native::NoteTiling(false);
  LogTiling(base, device, "EndTiling", "after");
}

// D3DVertexBuffer_Lock (r3 = the vertex buffer; its fetch constant at +24/+28 holds the data address and size): the
// renderer learns that the game may rewrite that range (a vertex cache's invalidation; counted for now).
REX_EXTERN(__imp__sub_82CE57A0);
REX_HOOK_RAW(sub_82CE57A0) {
  SASRT_RENUT_YIELD(sub_82CE57A0)  // sasrt_renderer = "renut" (renut_engine/sasrt_renut_yield.h)
  const uint32_t vb = ctx.r3.u32;
  if (vb >= 0x40000000 && vb < 0x7F000000) {
    me::native::NoteVertexBufferLock(Load32(base, vb + 24) & ~3u, Load32(base, vb + 28) & 0x03FFFFFCu, ctx.r7.u32);
  }
  __imp__sub_82CE57A0(ctx, base);
}

REX_EXTERN(__imp__sub_82CC64E8);
REX_HOOK_RAW(sub_82CC64E8) {  // D3DDevice_CreateVertexShader (r3 = the container blob)
  SASRT_RENUT_YIELD(sub_82CC64E8)  // sasrt_renderer = "renut" (renut_engine/sasrt_renut_yield.h)
  DumpShaderBlob(base, ctx.r3.u32, true);
  __imp__sub_82CC64E8(ctx, base);
}

REX_EXTERN(__imp__sub_82CC61F0);
REX_HOOK_RAW(sub_82CC61F0) {  // D3DDevice_CreatePixelShader (r3 = the container blob)
  SASRT_RENUT_YIELD(sub_82CC61F0)  // sasrt_renderer = "renut" (renut_engine/sasrt_renut_yield.h)
  DumpShaderBlob(base, ctx.r3.u32, false);
  __imp__sub_82CC61F0(ctx, base);
}
