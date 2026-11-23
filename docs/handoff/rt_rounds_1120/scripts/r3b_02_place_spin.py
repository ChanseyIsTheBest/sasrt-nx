ROOT = r'D:/sonic transformed/sasrt-nx/app/src/renut_engine/gpu/'


def edit(path, old, new):
    p = ROOT + path
    s = open(p, encoding='utf-8').read()
    assert s.count(old) == 1, (path, old[:70])
    s = s.replace(old, new)
    open(p, 'w', encoding='utf-8').write(s)


edit('guest/command_buffers.h', '''struct SasrtRunSlot {
  std::mutex mutex;
  std::condition_variable cv;
  bool filled = false;''', '''struct SasrtRunSlot {
  std::mutex mutex;
  std::condition_variable cv;
  bool filled = false;
  // sasrt-nx (2026-11-20, sasrt_rt3_place_spin): set (release) with 'filled' by FillCapturedRunSlot, so the render
  // thread can watch it without the mutex while it spins before sleeping.
  std::atomic<bool> ready{false};''')
if '#include <atomic>' not in open(ROOT + 'guest/command_buffers.h', encoding='utf-8').read():
    edit('guest/command_buffers.h', '#include <mutex>', '#include <atomic>\n#include <mutex>')

edit('guest/command_buffers.cpp', '''    slot.buffer = buffer;
    slot.recording = std::move(recording);
    slot.filled = true;
  }
  slot.cv.notify_all();''', '''    slot.buffer = buffer;
    slot.recording = std::move(recording);
    slot.filled = true;
    slot.ready.store(true, std::memory_order_release);  // sasrt-nx (2026-11-20, sasrt_rt3_place_spin)
  }
  slot.cv.notify_all();''')

edit('guest/command_buffers.cpp', '''        if (!ready) {
          State().mutex.unlock();
          {
            std::unique_lock lock(slot->mutex);
            slot->cv.wait_for(lock, std::chrono::milliseconds(timeout_ms), [&slot] { return slot->filled; });
          }
          State().mutex.lock();''', '''        if (!ready) {
          State().mutex.unlock();
          // sasrt-nx (2026-11-20, sasrt_rt3_place_spin; the third render-thread round's #2): the first part of the
          // wait spun on the slot's flag (the render thread has core 1 to itself), so a recording that ends within it
          // is taken without a sleep and the kernel's wake (the places waited 1.2 ms on average, four a frame with four
          // players); then the wait as before.
          if (sasrt::gpu_round::On(sasrt::gpu_round::kRt3PlaceSpin)) {
            static const int32_t spin_us = REXCVAR_GET(sasrt_rt3_place_spin_us);
            const auto spin_until = waiting + std::chrono::microseconds(spin_us);
            uint32_t n = 0;
            while (!slot->ready.load(std::memory_order_acquire)) {
#if defined(__aarch64__)
              __asm__ volatile("yield");
#endif
              if ((++n & 63u) == 0 && std::chrono::steady_clock::now() >= spin_until)
                break;
            }
            if (slot->ready.load(std::memory_order_acquire))
              sasrt::gpu_round::Count(sasrt::gpu_round::kRt3PlaceSpin);
            else
              sasrt::gpu_round::Count(sasrt::gpu_round::kRt3PlaceSpin, 1, 1);  // slept after the spin (the line's /n)
          }
          {
            std::unique_lock lock(slot->mutex);
            slot->cv.wait_for(lock, std::chrono::milliseconds(timeout_ms), [&slot] { return slot->filled; });
          }
          State().mutex.lock();''')

edit('guest/command_buffers.cpp', '''#include "renut_engine/gpu/sasrt_gpu_round.h"  // sasrt-nx (2026-11-20): the second render-thread round's switches''',
     '''#include "renut_engine/gpu/sasrt_gpu_round.h"  // sasrt-nx (2026-11-20): the second render-thread round's switches
#include <rex/cvar.h>
REXCVAR_DEFINE_INT32(sasrt_rt3_place_spin_us, 400, "SASRT/RenderThread",
                     "sasrt_rt3_place_spin: how long (us) the render thread spins on a same-frame place before it sleeps")
    .range(0, 5000)
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);''')
print('ok')
