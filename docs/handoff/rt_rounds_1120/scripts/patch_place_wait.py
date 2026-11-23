p = r'D:/sonic transformed/sasrt-nx/app/src/renut_engine/gpu/guest/command_buffers.cpp'
s = open(p, encoding='utf-8').read()
old = '''#include "renut_engine/gpu/render/textures.h"  // banjo-nx (2026-10-28): TextureFrameLocked (the packet census's frames)
'''
new = old + '''#include "renut_engine/gpu/backend/video.h"  // sasrt-nx (2026-11-20, sasrt_rt2_place_wait_unlocked): State().mutex
#include "renut_engine/gpu/sasrt_gpu_round.h"  // sasrt-nx (2026-11-20): the second render-thread round's switches
'''
assert s.count(old) == 1
s = s.replace(old, new)
old = '''    {
      const auto waiting = std::chrono::steady_clock::now();
      std::unique_lock lock(slot->mutex);
      slot->cv.wait_for(lock, std::chrono::milliseconds(timeout_ms), [&slot] { return slot->filled; });
      const uint64_t waited'''
new = '''    {
      const auto waiting = std::chrono::steady_clock::now();
      // sasrt-nx (2026-11-20, sasrt_rt2_place_wait_unlocked; the second render-thread round): the wait without
      // State().mutex (this item runs with it held: render_thread Execute), so the game thread's destroys and
      // creates that take it are not held up by the place (up to the timeout). Waiting here touches no renderer state;
      // anything another thread does meanwhile is as if done before this item began. The slot's mutex is let go
      // before State().mutex is taken again (never the one inside the other).
      if (sasrt::gpu_round::On(sasrt::gpu_round::kRt2PlaceWaitFree)) {
        bool ready;
        {
          std::lock_guard peek(slot->mutex);
          ready = slot->filled;
        }
        if (!ready) {
          State().mutex.unlock();
          {
            std::unique_lock lock(slot->mutex);
            slot->cv.wait_for(lock, std::chrono::milliseconds(timeout_ms), [&slot] { return slot->filled; });
          }
          State().mutex.lock();
          sasrt::gpu_round::Count(sasrt::gpu_round::kRt2PlaceWaitFree);
        }
      }
      std::unique_lock lock(slot->mutex);
      const auto left = std::chrono::milliseconds(timeout_ms) -
                        std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - waiting);
      if (!slot->filled && left.count() > 0)
        slot->cv.wait_for(lock, left, [&slot] { return slot->filled; });
      const uint64_t waited'''
assert s.count(old) == 1
s = s.replace(old, new)
open(p, 'w', encoding='utf-8').write(s)
print('ok')
