// Short video recordings of the game image (see sasrt_capture.h).
//
// From sasrt_video_s seconds after start, sasrt_video_frames consecutive presented frames are written as they come to
// captures/video_<s>s.rgba next to the executable (raw R8G8B8X8, frames back to back; streamed, so a long recording
// does not need RAM, ~55 MB per second at half resolution on disk) with a .txt beside it (width, height, measured fps,
// frame count). tools/make_video.sh turns it into an MP4 with ffmpeg. sasrt_video_every keeps one game frame in N.

#include "sasrt_capture.h"

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <condition_variable>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include <rex/cvar.h>
#include <rex/filesystem.h>
#include <rex/logging.h>
#include <rex/ui/presenter.h>

REXCVAR_DEFINE_INT32(sasrt_video_s, 0, "SASRT",
                     "Record a short video of the game image this many seconds after start, to captures/ next to "
                     "the executable (0 = off; works minimized). tools/make_video.sh makes the MP4")
    .range(0, 3600);
REXCVAR_DEFINE_INT32(sasrt_video_frame, 0, "SASRT",
                     "After sasrt_video_s, also wait for this game frame before recording (0 = off). With "
                     "vblank_per_swap every run then records the same stretch of the game, whatever the PC's speed "
                     "(lockstep comparisons, e.g. a renderer change against the CPU-off baseline; sa2-nx's)")
    .range(0, 2000000000);
REXCVAR_DEFINE_INT32(sasrt_video_frames, 300, "SASRT", "Frames in the video (sasrt_video_s); the game runs at 60 fps")
    .range(1, 36000);
REXCVAR_DEFINE_BOOL(sasrt_video_half, true, "SASRT",
                    "Record the video at half resolution (~55 MB of disk per second instead of ~220 MB)");
REXCVAR_DEFINE_INT32(sasrt_video_every, 1, "SASRT",
                     "Record one game frame in this many (6 = 10 fps: minutes of footage to compare against a "
                     "reference without filling the disk)")
    .range(1, 600);

std::atomic<uint64_t> g_sasrt_game_frames{0};
std::atomic<uint64_t> g_sasrt_wipe_end_frame{0};

namespace sasrt::capture {
namespace {

std::mutex g_mutex;
std::condition_variable g_cv;
bool g_stop = false;
std::thread g_thread;

bool StopRequested() {
  std::lock_guard lock(g_mutex);
  return g_stop;
}

void Record(std::function<bool(rex::ui::RawImage&)> grab, int start_s, int frame_count) {
  {
    std::unique_lock lock(g_mutex);
    if (g_cv.wait_for(lock, std::chrono::seconds(start_s), [] { return g_stop; })) {
      return;
    }
  }
  if (const uint64_t first = uint64_t(std::max(0, REXCVAR_GET(sasrt_video_frame)))) {
    while (g_sasrt_game_frames.load(std::memory_order_relaxed) + 1 < first) {
      if (StopRequested()) return;
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
  }
  const uint32_t step = REXCVAR_GET(sasrt_video_half) ? 2 : 1;
  const uint64_t every = uint64_t(REXCVAR_GET(sasrt_video_every));
  const auto folder = rex::filesystem::GetExecutableFolder() / "captures";
  std::error_code ec;
  std::filesystem::create_directories(folder, ec);
  const std::string name = "video_" + std::to_string(start_s) + "s";
  std::ofstream raw(folder / (name + ".rgba"), std::ios::binary | std::ios::trunc);
  if (!raw) {
    REXLOG_WARN("[capture] cannot write {}", rex::path_to_utf8(folder / (name + ".rgba")));
    return;
  }
  // The game frame of every recorded frame (uint64 each; UINT64_MAX when another flip came while it was being taken,
  // so the image may belong to either): comparisons of two lockstep runs match frames by game frame, whatever flips
  // each recorder skipped (tools/lockstep_compare.py).
  std::ofstream frames_file(folder / (name + ".frames"), std::ios::binary | std::ios::trunc);
  std::vector<uint8_t> frame;
  int written = 0;
  uint64_t skipped_flips = 0;  // flips that came and went while a capture was still being taken
  uint32_t width = 0, height = 0;
  const auto started = std::chrono::steady_clock::now();
  uint64_t last = g_sasrt_game_frames.load(std::memory_order_relaxed);
  REXLOG_INFO("[capture] recording {} frames from {} s, game frame {}", frame_count, start_s, last);
  while (written < frame_count && !StopRequested()) {
    // One capture per game frame, a few ms after the flip so the presenter holds the new image.
    const uint64_t now = g_sasrt_game_frames.load(std::memory_order_relaxed);
    if (now == last || (written && now - last < every)) {
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
      continue;
    }
    if (written) {
      skipped_flips += now - last - every;
    }
    last = now;
    std::this_thread::sleep_for(std::chrono::milliseconds(4));
    rex::ui::RawImage image;
    if (!grab || !grab(image) || !image.width || !image.height ||
        (width && (image.width != width || image.height != height))) {
      std::this_thread::sleep_for(std::chrono::milliseconds(5));
      continue;
    }
    width = image.width;
    height = image.height;
    const uint32_t w = width / step, h = height / step;
    frame.resize(size_t(w) * h * 4);
    for (uint32_t y = 0; y < h; ++y) {
      const uint8_t* row = image.data.data() + size_t(y) * step * image.stride;
      uint8_t* out = frame.data() + size_t(y) * w * 4;
      if (step == 1) {
        std::memcpy(out, row, size_t(w) * 4);
      } else {
        for (uint32_t x = 0; x < w; ++x) {
          std::memcpy(out + size_t(x) * 4, row + size_t(x) * step * 4, 4);
        }
      }
    }
    raw.write(reinterpret_cast<const char*>(frame.data()), std::streamsize(frame.size()));
    // sasrt-nx (2026-10-21, sasrt_renderdoc_after_wipe): the game's logo wipe (the race intro, a respawn) fills the
    // screen with saturated blue to all four corners, which no race frame does; the game frame of the first frame
    // after one is published for the RenderDoc trigger.
    {
      auto blue = [&](uint32_t x, uint32_t y) {
        const uint8_t* p = frame.data() + (size_t(y) * w + x) * 4;
        return p[2] > 60 && p[0] < 60 && p[1] < 130 && p[2] > p[0] + p[1];  // its corners go down to (0, 4, 74)
      };
      const uint32_t mx = w / 40, my = h / 24;
      const bool logo = blue(mx, my) && blue(w - 1 - mx, my) && blue(mx, h - 1 - my) && blue(w - 1 - mx, h - 1 - my);
      static bool was_logo = false;
      if (was_logo && !logo)
        g_sasrt_wipe_end_frame.store(now, std::memory_order_relaxed);
      was_logo = logo;
    }
    const uint64_t label = g_sasrt_game_frames.load(std::memory_order_relaxed) == now ? now : UINT64_MAX;
    frames_file.write(reinterpret_cast<const char*>(&label), sizeof(label));
    ++written;
    if (written % 600 == 0) {
      REXLOG_INFO("[capture] {} / {} frames", written, frame_count);
    }
  }
  raw.close();
  frames_file.close();
  if (!written) {
    REXLOG_WARN("[capture] no frame recorded (no presenter or no guest output)");
    return;
  }
  const double seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
  const double fps = seconds > 0 ? double(written) / seconds : 60.0;
  std::ofstream(folder / (name + ".txt"), std::ios::binary)
      << width / step << ' ' << height / step << ' ' << fps << ' ' << written << '\n';
  REXLOG_INFO("[capture] video {}: {} frames of {}x{} in {:.2f} s ({:.1f} fps, {} flips skipped by the recorder) -> {}",
              name, written, width / step, height / step, seconds, fps, skipped_flips,
              rex::path_to_utf8(folder / (name + ".rgba")));
}

}  // namespace

void Start(std::function<rex::ui::Presenter*()> get_presenter) {
  Start(std::function<bool(rex::ui::RawImage&)>([get_presenter](rex::ui::RawImage& image) {
    rex::ui::Presenter* presenter = get_presenter ? get_presenter() : nullptr;
    return presenter && presenter->CaptureGuestOutput(image);
  }));
}

// sasrt-nx (2026-10-19): any source of the game image (Renut's renderer has no SDK presenter: renut::gpu::CaptureFrame).
void Start(std::function<bool(rex::ui::RawImage&)> grab) {
  if (REXCVAR_GET(sasrt_video_s) <= 0 || g_thread.joinable()) {
    return;
  }
  {
    std::lock_guard lock(g_mutex);
    g_stop = false;
  }
  g_thread = std::thread(Record, std::move(grab), int(REXCVAR_GET(sasrt_video_s)),
                         int(REXCVAR_GET(sasrt_video_frames)));
}

void Stop() {
  {
    std::lock_guard lock(g_mutex);
    g_stop = true;
  }
  g_cv.notify_all();
  if (g_thread.joinable()) {
    g_thread.join();
  }
}

}  // namespace sasrt::capture
