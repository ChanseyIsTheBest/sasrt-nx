// Sonic & All-Stars Racing Transformed: the ReXGlue application object (paths, GPU plugin choice, analysis aids).

#pragma once

#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <system_error>

#include <rex/cvar.h>
#include <rex/filesystem.h>
#include <rex/logging.h>
#include <rex/rex_app.h>
#include <rex/runtime.h>

#include "me/me_native_system.h"

extern "C" const char* RexAppBuildStamp(void);  // base port 193 (TFU-nx's): src/build_stamp.cpp
#include "sasrt_capture.h"
#include "sasrt_dlc.h"
#include "sasrt_enhancements.h"
#include "sasrt_input_script.h"
#include "sasrt_pgo.h"  // sasrt-nx (2026-11-09): the PGO-instrumented build's counts
#include "sasrt_pc_profiler.h"
#include "game_menu.h"  // sasrt-nx (2026-11-19): the base's game menu (ports 177-182; A+B+X+Y+L+R, F8)
namespace blur::small_alloc {
void Enable();  // renut-ultimate port 151 (blur-nx #220): src/blur_small_alloc.cpp, after setup
}

// sasrt-nx (2026-10-19): Renut's Direct3D-level renderer (cmake/sasrt_renut_gpu.cmake), chosen at boot with
// sasrt_renderer = "renut": no PM4 ring, no EDRAM emulation, plume (Vulkan on the PC, deko3d on the Switch).
#if SASRT_RENUT_RENDERER
#include "renut_engine/gpu/banjo_renut_capture.h"
#include "renut_engine/gpu/banjo_renut_select.h"
#include "renut_engine/gpu/overlay/app_integration.h"
#endif

class SasrtApp : public rex::ReXApp {
 public:
  using rex::ReXApp::ReXApp;

  static std::unique_ptr<rex::ui::WindowedApp> Create(rex::ui::WindowedAppContext& ctx) {
    return std::unique_ptr<SasrtApp>(new SasrtApp(ctx, "sasrt", PPCImageConfig));
  }

  void OnPostInitLogging() override {
    REXLOG_INFO("[build] {}", RexAppBuildStamp());  // base port 193 (TFU-nx's): ties this log to its build
    // The runtime defaults to no GPU plugin: select ReXGlue's Xenos implementation, keeping an explicit
    // command-line or config-file choice.
    if (!rex::cvar::HasNonDefaultValue("gpu_plugin")) {
      rex::cvar::SetFlagByName("gpu_plugin", "xenos");
    }
    // Every performance enhancement's key, the two masters and verify mode, before anything reads them; one
    // "[enhancements]" log line lists what is active (sasrt_enhancements.cpp).
    sasrt::enhancements::Apply();
  }

  // Without --game_data_root, use a game_root/ folder next to the executable (on the Switch:
  // sdmc:/switch/sasrt-nx/game_root), and on a PC build tree the repository's assets/game_root.
  // An explicit path always wins.
  void OnConfigurePaths(rex::PathConfig& paths) override {
    if (!paths.game_data_root.empty()) {
      return;
    }
    std::error_code ec;
    const auto folder = rex::filesystem::GetExecutableFolder();
    if (folder.empty()) {
      return;
    }
    for (auto candidate = folder; !candidate.empty(); candidate = candidate.parent_path()) {
      for (const auto& sub : {std::filesystem::path("game_root"),
                              std::filesystem::path("assets") / "game_root"}) {
        // The folder itself, or only its asset cache (game_root.nxpack + .nxidx, see sdk pack_device.h): on the
        // Switch the folder is usually absent once the pack is on the card.
        auto pack = candidate / sub;
        pack += ".nxpack";
        if (std::filesystem::is_regular_file(candidate / sub / "default.xex", ec) ||
            std::filesystem::is_regular_file(pack, ec)) {
          paths.game_data_root = candidate / sub;
          return;
        }
      }
      if (candidate == candidate.parent_path()) {
        break;
      }
    }
  }

  // Stage 4: with masseffect_renderer_native = true the graphics system is the app's own native Vulkan renderer
  // (src/me), and the emulated Xenos GPU plugin is not loaded (ReXApp only loads it when config.graphics is empty).
  void OnPreSetup(rex::RuntimeConfig& config) override {
#if SASRT_RENUT_RENDERER
    if (banjo::renut_gpu::Active()) {
      // No SDK graphics system and no GPU plugin: the renderer is the app's (Renut's detached mode).
      renut::gpu::ConfigureRuntime(config);
      REXLOG_INFO("graphics: Renut native renderer (Direct3D level, plume; no PM4 ring, no EDRAM emulation)");
      return;
    }
#endif
    if (me::native::Enabled()) {
      config.graphics = me::native::CreateGraphicsSystem();
      REXLOG_INFO("graphics: native Vulkan renderer (PM4 ring)");
    }
  }

  // Video recording of the game image for testing (sasrt_video_s = N seconds after start; 0 = off). Taken from the
  // presenter's guest output, so it works minimized and nothing can cover it.
  void OnPostSetup() override {
    // sasrt-nx (2026-11-19, base port 151): the small-block arena, blur_small_alloc_mb (32 MB by default; 0 in the toml
    // turns it off). Before the DLC install, as the base has it.
    blur::small_alloc::Enable();
    // DLC packages from dlc/ next to the executable go into the content store before the game starts looking.
    sasrt::dlc::InstallPackages(runtime());
    // Scripted controller presses for unattended test runs (sasrt_input_script; empty = none).
    sasrt::input_script::Install(runtime());
#if SASRT_RENUT_RENDERER
    if (banjo::renut_gpu::Active()) {
      // Renut's renderer has no SDK presenter: its own Present reads the frame back (banjo_renut_capture.h).
      sasrt::capture::Start(std::function<bool(rex::ui::RawImage&)>(
          [](rex::ui::RawImage& image) { return renut::gpu::CaptureFrame(image); }));
    } else
#endif
    sasrt::capture::Start([this]() -> rex::ui::Presenter* {
      const auto* rt = runtime();
      const auto* graphics = rt ? rt->graphics_system() : nullptr;
      return graphics ? graphics->presenter() : nullptr;
    });
    // PC: function-level CPU profile (sasrt_pc_profile_s = N seconds per report; 0 = off; futari-nx's profiler).
    sasrt::pc_profiler::Start();
    // The PGO-instrumented build (SASRT_PGO=generate) saves its counts to pgo/ every 2 minutes (nothing otherwise).
    sasrt::pgo::Start();
  }

  // The PGO-instrumented build saves its counts when the game loses focus (HOME menu): it may be closed from there.
  void OnWindowFocusChanged(bool focused) override {
    if (!focused) sasrt::pgo::DumpNow();
  }

  // sasrt-nx (2026-11-19, the user: "can you port the game menu please"; the base's ports 177-182, Blur's menu): the
  // menu's fonts (the console's own shared font, the embedded ImGui ones) in the SDK drawer's atlas, and the menu
  // itself. Attached for good (its constructor adds it), it asks for no ImGui frame while closed (WantsFrame).
  void OnConfigureFonts(ImFontAtlas* atlas) override { blur::AddGameMenuFonts(atlas); }
  void OnCreateDialogs(rex::ui::ImGuiDrawer* drawer) override {
#if SASRT_RENUT_RENDERER
    // The app's dialogs draw with the ImGui of Renut's overlay drawer; under the SDK's presenter (the emulated GPU,
    // the reference image) there are none (the base's rule).
    if (!banjo::renut_gpu::Active()) return;
#endif
    game_menu_ = std::make_unique<blur::GameMenuDialog>(drawer, config_path(), [this] { return runtime(); },
                                                        [this] { return immediate_drawer(); });
  }

#if SASRT_RENUT_RENDERER
  // Renut's renderer draws the SDK's ImGui through its own plume drawer, and resizes its swapchain itself.
  std::unique_ptr<rex::ui::ImmediateDrawer> OnCreateImmediateDrawer() override {
    if (banjo::renut_gpu::Active()) return renut::gpu::CreateOverlayDrawer();
    return rex::ReXApp::OnCreateImmediateDrawer();
  }
  void OnWindowPixelSizeChanged(uint32_t pixel_width, uint32_t pixel_height) override {
    rex::ReXApp::OnWindowPixelSizeChanged(pixel_width, pixel_height);
    if (banjo::renut_gpu::Active()) renut::gpu::OnWindowResized();
  }
  // The window exists here, before the game starts: Renut's renderer comes up first (banjo-nx's order).
  std::optional<rex::PathConfig> OnFinalizePaths(const rex::PathConfig& defaults,
                                                 std::function<void(rex::PathConfig)> resume) override {
    if (banjo::renut_gpu::Active())
      renut::gpu::StartRenderer(app_context(), [this] { return imgui_drawer(); });
    return rex::ReXApp::OnFinalizePaths(defaults, std::move(resume));
  }
#endif

  void OnShutdown() override {
#if SASRT_RENUT_RENDERER
    if (banjo::renut_gpu::Active()) renut::gpu::ShutdownRenderer();
#endif
    sasrt::pc_profiler::Stop();
    sasrt::capture::Stop();
    sasrt::pgo::Stop();
  }
 private:
  std::unique_ptr<blur::GameMenuDialog> game_menu_;  // sasrt-nx (2026-11-19): the game menu
};
