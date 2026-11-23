# Events wait on an address, not the mutex's condition variable (SASRT, 2026-11-10)

For RR6 and the ultimate base (the user: "anything that you think will help the ultimate port base please send to
rr6"). SDK only (`sdk/src/core/`), Switch only, behind one key (`thread_event_address_wait`, on); nothing changes on the
PC. The base does not have it (checked 2026-11-10 14:50).

## Why

On Horizon a condition variable's wake gives the woken thread the mutex at once (svcSignalProcessWideKey takes the
mutex tag for it) although the thread may not run for a while: with cores 0-2 busy a woken guest thread (priority 0x3B)
waits for its core. A thread setting the same event meanwhile blocks on the mutex behind a thread that does not run.
SASRT's handheld race (run P1) had the game's main thread in `pthread_mutex_lock` at `PosixEvent::Set+0x20` (the
event's own mutex) for 5.6 % of its samples (~2.3 ms a 42 ms frame).

## What

An event's blocked threads sleep on a 32-bit word (`svcWaitForAddress`, wait if equal) and take the mutex only when they
run again; `Set` changes the word under the mutex and wakes the address after releasing it. The 360's semantics, which
the condition variable kept only because the second Set waited for the first waiter:

- an auto-reset `Set` that finds a thread blocked releases one blocked thread (a grant; the event stays unsignalled);
- a manual-reset `Set` releases every thread blocked at that moment (a `Reset` right after, or `Pulse`, cannot strand
  them) and leaves it signalled;
- a blocked thread that runs again takes a grant first, then the signal, then an interrupt (an alertable wait's queued
  callback), then its timeout; it re-checks every 100 ms unwoken (a net; a release found that way is counted).

WaitMultiple, Reset, Query and the other handle types are unchanged (the mutex still guards the state).

## Evidence

- Host stress test `files/test_address_event.cpp` (the same header on Windows' WaitOnAddress; build line at its top):
  200,000 ping-pongs; 20,000 rounds of 4 blocked waiters released by 4 back-to-back Sets and by a manual Set + Reset;
  1,000 interrupts (worst 0.24 ms); random mixes of Sets, Resets, timeouts and interrupts with 16 consumers and 4
  producers (15-16 million Sets): no lost wake-up, successes <= Sets, counters back at 0, 0 safety releases (two runs).
- Console (handheld 1020/460/1600, Ocean View): on in every race since 2026-11-10 morning (about a dozen, docked and
  handheld, ~3 h of play); the main thread's samples in that mutex: 5.6 % (P1) -> 0.0 % (races hh_base2, fixship).
  (The GPU hangs of that day were the depth-words copy, `docs/handoff/gpu_hang_1110`, with the key on and off alike.)

## The changes

1. New file `sdk/src/core/address_event_core.h` (`files/address_event_core.h`): `AddressEventCore<Arbiter>`.
2. `sdk/src/core/threading_switch.h` / `.cpp`: two helpers (threading_posix.cpp keeps libnx's names out):

```c
/* threading_switch.h, inside its extern "C" block */
bool RexSwitchWaitIfEqual(volatile uint32_t* word, uint32_t value, int64_t ns);
void RexSwitchWakeAddress(volatile uint32_t* word, int32_t count);
```

```cpp
// threading_switch.cpp, inside its extern "C" block
bool RexSwitchWaitIfEqual(volatile uint32_t* word, uint32_t value, int64_t ns) {
  const Result rc = svcWaitForAddress((void*)word, ArbitrationType_WaitIfEqual, (s64)(s32)value, ns);
  return R_VALUE(rc) != KERNELRESULT(TimedOut);
}
void RexSwitchWakeAddress(volatile uint32_t* word, int32_t count) {
  svcSignalToAddress((void*)word, SignalType_Signal, 0, count);
}
```

3. `sdk/src/core/threading_posix.cpp`:
   - `#include "address_event_core.h"` in the `#if defined(__SWITCH__)` include block (after `threading_switch.h`);
   - the key (next to `thread_signal_skip_idle`):

```cpp
REXCVAR_DEFINE_BOOL(thread_event_address_wait, true, "Threading",
                    "Switch: a thread blocked on an event sleeps on an address (svcWaitForAddress) instead of the "
                    "event mutex's condition variable, so waking it no longer hands it the mutex before it runs (a "
                    "Set of the same event then waited behind a woken thread with no core yet: 5.5 % of the game "
                    "thread in the handheld race). An auto-reset Set that finds a thread blocked releases it "
                    "directly, a manual-reset Set every blocked thread (the 360's semantics). false = the condition "
                    "variable, as before")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
```

   - in `PosixConditionBase`: `InterruptWaiters()` and `Wait(...)` become `virtual`;
   - in `PosixCondition<Event>`: `Signal()` starts with

```cpp
#if defined(__SWITCH__)
    if (AddressWaitOn()) {
      int32_t wake;
      {
        auto lock = std::unique_lock<std::mutex>(mutex_);
        wake = address_.SetLocked(manual_reset_, signal_);
      }
      if (wake) {
        address_.Wake(wake);
      } else {
        REX_SYS_COUNT(rex::syscount::kSignalIdle, 1);
      }
      NotifyMulti();
      return true;
    }
#endif
```

   and after `Reset()` the class gets (Switch only) a `Wait` override, an `InterruptWaiters` override, the key's reader
   and the member:

```cpp
#if defined(__SWITCH__)
  WaitResult Wait(std::chrono::milliseconds timeout, const std::atomic<bool>* interrupt = nullptr) override {
    if (!AddressWaitOn()) {
      return PosixConditionBase::Wait(timeout, interrupt);
    }
    const bool infinite = timeout == std::chrono::milliseconds::max();
    const auto deadline = infinite ? std::chrono::steady_clock::time_point::max()
                                   : std::chrono::steady_clock::now() + timeout;
    std::unique_lock<std::mutex> lock(mutex_, std::defer_lock);
    if (infinite) {
      lock.lock();
    } else {
      while (!lock.try_lock()) {
        const auto now = std::chrono::steady_clock::now();
        if (now >= deadline) {
          return WaitResult::kTimeout;
        }
        const auto remaining = std::chrono::ceil<std::chrono::microseconds>(deadline - now);
        std::this_thread::sleep_for(std::min(remaining, std::chrono::microseconds(100)));
      }
    }
    if (signal_) {
      post_execution();
      return WaitResult::kSuccess;
    }
    if (interrupt && interrupt->load(std::memory_order_acquire)) {
      return WaitResult::kTimeout;  // interrupted by a queued user callback
    }
    if (!infinite && std::chrono::steady_clock::now() >= deadline) {
      return WaitResult::kTimeout;
    }
    constexpr int64_t kSafetyNs = 100'000'000;  // a blocked thread re-checks every 100 ms unwoken (a net)
    switch (address_.Block(lock, signal_, interrupt, infinite, deadline, kSafetyNs)) {
      case detail::AddressWaitResult::kSignaled:
        post_execution();
        return WaitResult::kSuccess;
      case detail::AddressWaitResult::kGranted:
        return WaitResult::kSuccess;
      default:
        return WaitResult::kTimeout;
    }
  }

  void InterruptWaiters() override {
    if (!AddressWaitOn()) {
      PosixConditionBase::InterruptWaiters();
      return;
    }
    int32_t wake;
    {
      std::lock_guard<std::mutex> lock(mutex_);
      wake = address_.InterruptLocked();
    }
    if (wake) {
      address_.Wake(wake);
    }
  }
#endif

 private:
#if defined(__SWITCH__)
  static bool AddressWaitOn() {
    static const bool on = REXCVAR_GET(thread_event_address_wait);
    return on;
  }
  struct HorizonArbiter {  // threading_switch.cpp (this file leaves libnx's names out)
    static bool WaitIfEqual(std::atomic<uint32_t>* word, uint32_t value, int64_t ns) {
      return RexSwitchWaitIfEqual(reinterpret_cast<volatile uint32_t*>(word), value, ns);
    }
    static void Wake(std::atomic<uint32_t>* word, int32_t count) {
      RexSwitchWakeAddress(reinterpret_cast<volatile uint32_t*>(word), count);
    }
  };
  detail::AddressEventCore<HorizonArbiter> address_;
#endif
```

(SASRT's own full files: `sdk/src/core/threading_posix.cpp`, `threading_switch.cpp/.h`, `address_event_core.h`.)
