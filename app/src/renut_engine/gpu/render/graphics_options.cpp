/**
 * @file    gpu/render/graphics_options.cpp
 */
#include "renut_engine/gpu/render/graphics_options.h"

#include <algorithm>  // sasrt-nx (2026-11-09): std::clamp
#include <cstdlib>
#include <string>

#include <rex/cvar.h>
#include <rex/types.h>

#include "renut_engine/gpu/backend/backend.h"
#include "renut_engine/gpu/guest/widescreen.h"
#include "renut_engine/gpu/render/format.h"
#include "renut_engine/gpu/sasrt_gpu_round.h"  // sasrt-nx (2026-11-09): the shadow cuts

// sasrt-nx (2026-11-20, split screen's too-dark far shadows): SASRT's shadow maps are square D24FS8 targets (the
// scene depth is D24FS8 too, never square); IsShadowMap knew them only with the two-thirds cut, so they took the 3D
// image's dynamic resolution scale: every step made the cascade target and the 1024x3072 shadow atlas again.
REXCVAR_DEFINE_BOOL(sasrt_shadow_maps_native, false, "SASRT/Graphics",
                    "Shadow maps (square D24FS8 depth targets: 512, 768, 1024) at the console's size whatever the "
                    "dynamic resolution's height (banjo-nx's design: the shadow maps stay at 1x); off: they follow the "
                    "3D image's scale, made again at every step with the shadow atlas (2026-11-20)");
REXCVAR_DEFINE_STRING(renut_shadow_resolution, "Resolution", "Nuts&Bolts/Graphics",
                      "Shadow map resolution, as a multiple of the console's: Resolution follows "
                      "renut_resolution; 1x is the console's; 2x, 3x and 4x are sharper.")
    .allowed({"Resolution", "1x", "2x", "3x", "4x"});

REXCVAR_DEFINE_STRING(renut_ambient_occlusion, "Half", "Nuts&Bolts/Graphics",
                      "Ambient occlusion (SSAO) resolution: Half the screen's, as on the console, "
                      "or Full.")
    .allowed({"Half", "Full"});

REXCVAR_DEFINE_BOOL(banjo_renut_dynamic_resolution, false, "Nuts&Bolts/Graphics",
                    "Dynamic resolution (2026-10-28, the user's request; not pixel-identical while it acts): the 3D "
                    "image between banjo_renut_dynamic_handheld_low and _high in handheld mode, _docked_low and _high "
                    "docked (in place of banjo_renut_render_height_handheld / _docked): the low height while the GPU's "
                    "time a frame is above banjo_renut_dynamic_gpu_ms, the high one when it would fit again (at least "
                    "5 s between changes). One end of each range is 720 lines (the 1x scale)");
// sasrt-nx (2026-11-19, the user: "dynamic resolution on/off, dynamic resolution handheld maximum, ... minimum, docked
// maximum, ... minimum" in the game menu): the switch and the four ends are live now (not kInitOnly): surfaces.cpp's
// latch builds the steps again when one of them changes.
REXCVAR_DEFINE_INT32(banjo_renut_dynamic_handheld_low, 540, "Nuts&Bolts/Graphics",
                     "banjo_renut_dynamic_resolution: the handheld range's low height (a multiple of 9)")
    .range(360, 1080);
REXCVAR_DEFINE_INT32(banjo_renut_dynamic_handheld_high, 720, "Nuts&Bolts/Graphics",
                     "banjo_renut_dynamic_resolution: the handheld range's high height")
    .range(360, 1080);
// sasrt-nx 1.0.1 (2026-11-24, the user: "make the game dynamic 720p in both handheld and docked 540p-720p by default"):
// docked 540 to 720 (720 to 1080 before; app/sasrt_switch.toml has why), the 3D upscaled to the 1080 display.
REXCVAR_DEFINE_INT32(banjo_renut_dynamic_docked_low, 540, "Nuts&Bolts/Graphics",
                     "banjo_renut_dynamic_resolution: the docked range's low height")
    .range(360, 1080);
REXCVAR_DEFINE_INT32(banjo_renut_dynamic_docked_high, 720, "Nuts&Bolts/Graphics",
                     "banjo_renut_dynamic_resolution: the docked range's high height (a multiple of 9; 1080 is the "
                     "docked display's own size, 900 before night_gpu5; sasrt-nx 1.0.1: 720, as handheld)")
    .range(360, 1080);
REXCVAR_DEFINE_INT32(banjo_renut_dynamic_steps, 4, "Nuts&Bolts/Graphics",
                     "banjo_renut_dynamic_resolution (night_gpu5, the user's request): heights between each range's low "
                     "and high, evenly spaced (multiples of 36: 576 612 648 684 handheld, 792 864 936 1008 docked); the "
                     "GPU's time picks the highest that fits. 0: only the two ends")
    .range(0, 10)  // sasrt-nx (2026-11-09, the user: "more steps, especially in docked"): 10, 8 before
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
// sasrt-nx (2026-11-09, the user: "more steps, especially in docked"): each mode's grid of heights (a multiple of 9:
// whole host pixels across the 1280-wide screen). 36 (banjo's) is whole pixels at 320x180 too; 18 at 640x360, and a
// quarter-size target's edge then rounds to the nearest pixel (RenderScale::Coord), half a pixel off at most.
REXCVAR_DEFINE_INT32(sasrt_dynamic_lines_handheld, 36, "SASRT/Graphics",
                     "banjo_renut_dynamic_resolution: the handheld steps are multiples of this many lines (9 to 72, a "
                     "multiple of 9; 36 banjo's)")
    .range(9, 72)
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_INT32(sasrt_dynamic_lines_docked, 18, "SASRT/Graphics",  // sasrt-nx 1.0.1: 18, as handheld (36)
                     "banjo_renut_dynamic_resolution: the docked steps are multiples of this many lines (9 to 72, a "
                     "multiple of 9; 36 banjo's)")
    .range(9, 72)
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_DOUBLE(banjo_renut_dynamic_up_s, 1.0, "Nuts&Bolts/Graphics",
                      "banjo_renut_dynamic_resolution: seconds in a row the high height must be predicted to fit (and "
                      "since the last change) before it is taken again (0.1 to 600; 1 = quick, the user's choice)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
// banjo-nx (2026-10-28): 34.5 (the user's choice; a decimal key since then), 40 before.
REXCVAR_DEFINE_DOUBLE(banjo_renut_dynamic_gpu_ms, 34.5, "Nuts&Bolts/Graphics",
                      "banjo_renut_dynamic_resolution: the GPU's time a frame (ms, a moving average) above which the low "
                      "height is taken (10 to 200)")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_INT32(banjo_renut_dynamic_test_s, 0, "Nuts&Bolts/Graphics",
                     "banjo_renut_dynamic_resolution test: alternate the two heights every N seconds whatever the load "
                     "(0: by the GPU's time)")
    .range(0, 600)
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_INT32(banjo_renut_anisotropy_cap, 0, "Nuts&Bolts/Graphics",
                     "NOT pixel-identical (2026-10-28, GPU block, the user's call): the most anisotropic filtering any "
                     "texture gets: 0 the game's own (as on the Xbox 360), 1 none, 2/4/8 at most that ratio. The "
                     "heaviest shaders read 14-21 textures a pixel; a high ratio multiplies each read. Compare runs "
                     "with and without it (the renderer's GPU ms)")
    .range(0, 16)
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_STRING(renut_anisotropic_filtering, "Game", "Nuts&Bolts/Graphics",
                      "Anisotropic texture filtering: the game's own, or at least 2x, 4x, 8x or "
                      "16x.")
    .allowed({"Game", "2x", "4x", "8x", "16x"});

// sa2-nx (2026-10-20): "Game" by default: SA2's picture stays the console's (16-bit buffers change it).
REXCVAR_DEFINE_STRING(renut_post_process_precision, "Game", "Nuts&Bolts/Graphics",
                      "Precision of the bloom, depth of field and SSAO buffers: Game keeps the "
                      "console's 8 bits (faint glow shows as blobs sliding over dark areas), High "
                      "uses 16 bits.")
    .allowed({"Game", "High"});

namespace renut::gpu {

namespace {

// D3DFORMAT low bits of D3DFMT_D24S8 (the shadow maps; the scene's depth is
// D24FS8).
constexpr u32 kFormatD24S8 = 22;
// The SSAO targets' EDRAM base (sub_8232E488).
constexpr u32 kAmbientOcclusionEdramBase = 1864;
// The game's screen height (widescreen.h).
constexpr u32 kGuestScreenHeight = 720;

bool g_shadow_maps_native = false;  // sasrt-nx (2026-11-20): sasrt_shadow_maps_native, latched with the options

bool IsShadowMap(const d3d::SurfaceDesc &desc, u32 width, u32 height) {
  if (width != height)
    return false;
  // sasrt-nx (2026-11-20, sasrt_shadow_maps_native): SASRT's own (square float depth), whatever the cut.
  if (g_shadow_maps_native && d3d::IsDepthFormat(desc.Format) && (width == 512 || width == 768 || width == 1024))
    return true;
  // sasrt-nx (2026-11-09, sasrt_gpu_cut_shadow_two_thirds): SASRT's shadow maps are square float-depth (D24FS8) targets.
  if (sasrt::gpu_round::g_latched.on[sasrt::gpu_round::kCutShadowScale] && d3d::IsDepthFormat(desc.Format) &&
      (width == 512 || width == 768 || width == 1024 || width == 2048))
    return true;
  if ((u32(desc.Format) & 0x3F) == kFormatD24S8)
    return width == 512 || width == 768 || width == 1024;
  // The local lights' depth, converted for their atlas.
  return !d3d::IsDepthFormat(desc.Format) && width == 512 &&
         GpuColorFormat((u32(desc.ColorInfo) >> 16) & 0xF) == GpuColorFormat::Fmt16_16_Float;
}

bool IsAmbientOcclusion(const d3d::SurfaceDesc &desc, u32 width, u32 height) {
  return !d3d::IsDepthFormat(desc.Format) && width == 640 && height == 360 &&
         (u32(desc.ColorInfo) & 0xFFF) == kAmbientOcclusionEdramBase;
}

// A quarter of the screen or less: the post-processing buffers (depth of
// field and bloom, 320x180 down to 20x11 at 1280x720). Their blurs average a
// few taps 2 of their own texels apart, made for buffers box-downsampled from
// the screen; rendered at a higher scale, the buffers keep detail those taps
// step over, so edges come out as ghost copies rather than blurred.
bool IsPostProcessBuffer(const d3d::SurfaceDesc &desc, u32 width, u32 height) {
  return !d3d::IsDepthFormat(desc.Format) && width * 4 <= GuestScreenWidth() &&
         height * 4 <= kGuestScreenHeight;
}

// Half the screen or less, single-sampled, 8_8_8_8: the bloom's bright pass
// (640x360) and the post-processing buffers below it, and the SSAO targets.
bool IsLowPrecisionPostTarget(const d3d::SurfaceDesc &desc) {
  const u32 width = d3d::SurfaceWidth(desc.Size);
  const u32 height = d3d::SurfaceHeight(desc.Size);
  return !d3d::IsDepthFormat(desc.Format) && ((u32(desc.SurfaceInfo) >> 16) & 3) == 0 &&
         width * 2 <= GuestScreenWidth() && height * 2 <= kGuestScreenHeight &&
         GpuColorFormat((u32(desc.ColorInfo) >> 16) & 0xF) == GpuColorFormat::Fmt8_8_8_8;
}

// The options as LatchGraphicsOptionsLocked last read them: the draw path
// asks for every target and sampler of every draw, too often for the
// settings' strings.
struct Latched {
  bool shadow_follows_resolution = true;
  RenderScale shadow_scale;
  bool full_ambient_occlusion = false;
  uint32_t min_anisotropy = 1;
  bool high_precision_post = true;
};
Latched g_latched;

} // namespace

void LatchGraphicsOptionsLocked() {
  g_shadow_maps_native = REXCVAR_GET(sasrt_shadow_maps_native);  // sasrt-nx (2026-11-20)
  const std::string &shadows = REXCVAR_GET(renut_shadow_resolution);
  g_latched.shadow_follows_resolution = shadows == "Resolution" || shadows.empty();
  g_latched.shadow_scale = {};
  if (!g_latched.shadow_follows_resolution)
    RenderScale::FromRatio(uint32_t(std::atoi(shadows.c_str())), 1, g_latched.shadow_scale);
  g_latched.full_ambient_occlusion = REXCVAR_GET(renut_ambient_occlusion) == "Full";
  // banjo-nx (2026-10-18): deko3d draws every target at the console's scale (its shaders are made for 1x, pass scale1
  // of tools/deko3d_glsl_opt.py): shadow maps follow the resolution (1x) and the ambient occlusion is the game's.
  // banjo-nx (2026-10-21, internal resolution): the 3D image at 648p or 900p (and the menus at 1080p docked): the shadow
  // maps stay at the console's size (1x, the game's shadows; not 0.9x), the ambient occlusion the game's.
  if (IsDeko3D()) {
    g_latched.shadow_follows_resolution = false;
    g_latched.shadow_scale = {};
    g_latched.full_ambient_occlusion = false;
    // sasrt-nx (2026-11-09, sasrt_gpu_cut_shadow_two_thirds: a cut, CHANGES PIXELS): two thirds (code 1)
    if (!sasrt::gpu_round::g_latched_ready.load(std::memory_order_acquire))
      sasrt::gpu_round::LatchNow();
    if (sasrt::gpu_round::g_latched.on[sasrt::gpu_round::kCutShadowScale])
      g_latched.shadow_scale = RenderScale{1};
  }
  const int anisotropy = std::atoi(REXCVAR_GET(renut_anisotropic_filtering).c_str());
  g_latched.min_anisotropy = anisotropy >= 2 ? uint32_t(anisotropy) : 1;
  g_latched.high_precision_post = REXCVAR_GET(renut_post_process_precision) != "Game";
}

RenderScale SurfaceRenderScale(const d3d::SurfaceDesc &desc, RenderScale resolution) {
  if ((u32(desc.SurfaceInfo) >> 16) & 3)
    return resolution;  // multisampled: the scene's
  const u32 width = d3d::SurfaceWidth(desc.Size);
  const u32 height = d3d::SurfaceHeight(desc.Size);
  if (IsShadowMap(desc, width, height))
    return g_latched.shadow_follows_resolution ? resolution : g_latched.shadow_scale;
  if (g_latched.full_ambient_occlusion && IsAmbientOcclusion(desc, width, height))
    return resolution.Times(2);
  if (IsPostProcessBuffer(desc, width, height))
    return {};  // the console's
  // banjo-nx (2026-10-21, package 36z2): a depth target of a quarter of the screen or less goes with the colour targets
  // of that size (the post-processing buffers' rule, which takes colour only): a 128x128 one at 0.9x under its 128x128
  // colour target at 1x cut its draws to 115x115 (console log of 36z: ten draws a frame).
  if (IsDeko3D() && d3d::IsDepthFormat(desc.Format) && width * 4 <= GuestScreenWidth() &&
      height * 4 <= kGuestScreenHeight)
    return {};
  return resolution;
}

plume::RenderFormat SurfaceColorFormat(const d3d::SurfaceDesc &desc) {
  // 16-bit unorm keeps 8-bit's clamping to [0, 1], which the game's blends
  // and shaders were made for.
  if (g_latched.high_precision_post && IsLowPrecisionPostTarget(desc))
    return plume::RenderFormat::R16G16B16A16_UNORM;
  return ColorTargetFormat(GpuColorFormat((u32(desc.ColorInfo) >> 16) & 0xF));
}

// sasrt-nx (2026-11-19, the game menu's rows): read at each call (the keys are live; surfaces.cpp's latch notices a
// change and builds the steps again).
bool DynamicResolutionOn() { return REXCVAR_GET(banjo_renut_dynamic_resolution); }
int32_t DynamicHeight(bool docked, bool high) {
  const int32_t set =
      docked ? int32_t(high ? REXCVAR_GET(banjo_renut_dynamic_docked_high) : REXCVAR_GET(banjo_renut_dynamic_docked_low))
             : int32_t(high ? REXCVAR_GET(banjo_renut_dynamic_handheld_high)
                            : REXCVAR_GET(banjo_renut_dynamic_handheld_low));
  // sasrt-nx 1.0.1 (2026-11-24, the user: "Clamp dynamic resolution the config so it cant go above 720p"): neither end
  // of either range above 720 lines, whatever the toml or the game menu says (docked's 720-1080 ran heavy events out of
  // memory; out/console_runs/c1124_101). The fixed heights (dynamic resolution off) are not clamped.
  constexpr int32_t kDynamicMax = 720;
  return set > kDynamicMax ? kDynamicMax : set;
}
double DynamicUpSeconds() {
  static const double set = double(REXCVAR_GET(banjo_renut_dynamic_up_s));
  static const double v = set < 0.1 ? 0.1 : set > 600.0 ? 600.0 : set;
  return v;
}
double DynamicGpuMs() {
  static const double set = double(REXCVAR_GET(banjo_renut_dynamic_gpu_ms));
  static const double v = set < 10.0 ? 10.0 : set > 200.0 ? 200.0 : set;
  return v;
}
int32_t DynamicTestSeconds() {
  static const int32_t v = int32_t(REXCVAR_GET(banjo_renut_dynamic_test_s));
  return v;
}
int32_t DynamicSteps() {
  static const int32_t v = int32_t(REXCVAR_GET(banjo_renut_dynamic_steps));
  return v < 0 ? 0 : v > 10 ? 10 : v;  // sasrt-nx (2026-11-09): 10, 8 before
}
int32_t DynamicStepLines(bool docked) {  // sasrt-nx (2026-11-09): sasrt_dynamic_lines_handheld / _docked
  static const int32_t h = int32_t(REXCVAR_GET(sasrt_dynamic_lines_handheld));
  static const int32_t d = int32_t(REXCVAR_GET(sasrt_dynamic_lines_docked));
  const int32_t v = docked ? d : h;
  return std::clamp(v / 9 * 9, 9, 72);
}

uint32_t AnisotropyCap() {
  static const int value = int(REXCVAR_GET(banjo_renut_anisotropy_cap));
  return value > 0 ? uint32_t(value) : 0u;
}

uint32_t MinAnisotropy() {
  return g_latched.min_anisotropy;
}

} // namespace renut::gpu
