// Short video recordings of the game image for testing, taken from the presenter's guest output (what the game
// presents), so they work with the window minimized and nothing can cover them. Same design and file format as the
// banjo-nx recorder: tools/make_video.sh turns the raw file into an MP4 and a contact sheet.

#pragma once

#include <atomic>
#include <cstdint>
#include <functional>

#include <rex/ui/presenter.h>  // rex::ui::RawImage

namespace rex::ui {
class Presenter;
}

// Frames the game has presented (its D3DDevice_Swap, sub_82CD9AE8, once per frame); the recorder waits on it.
extern std::atomic<uint64_t> g_sasrt_game_frames;
// sasrt-nx (2026-10-21): the game frame of the first recorded frame after the game's logo wipe (a race intro, a
// respawn), 0 before any; set by the video recorder (sasrt_video_s), read by sasrt_renderdoc_after_wipe.
extern std::atomic<uint64_t> g_sasrt_wipe_end_frame;

namespace sasrt::capture {

// Starts the recorder thread when sasrt_video_s > 0.
void Start(std::function<rex::ui::Presenter*()> get_presenter);
// The same with any source of the game image (true when it filled the image; Renut's renderer: CaptureFrame).
void Start(std::function<bool(rex::ui::RawImage&)> grab);

// Stops it (writes what it has, if anything).
void Stop();

// sa2-nx's lockstep recording through Renut's Present (tools/renut_from_sa2.py brings its calls): not in this port.
inline bool RenutLockstepOn() { return false; }
inline void RenutLockstepFrame(uint64_t, const rex::ui::RawImage*) {}

}  // namespace sasrt::capture
