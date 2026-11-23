/*
 * POSIX compatibility layer for threads on Horizon.
 *
 * Why a layer and not a separate version
 *
 * threading_posix.cpp is 1,546 lines and newlib has real pthreads, so most of it
 * works as is. Only four things are missing, and forking the whole file for that
 * would doom the port to diverge from the SDK on every update. This fills the
 * gaps and leaves the original almost untouched.
 *
 * What newlib lacks, and what fills it
 *
 *   cpu_set_t and CPU_*          own bit structure
 *   pthread_[gs]etaffinity_np    svcGetThreadCoreMask / svcSetThreadCoreMask
 *   pthread_[gs]etschedparam     svcGetThreadPriority / svcSetThreadPriority
 *   PTHREAD_MUTEX_ROBUST         Horizon has no robust mutexes: no effect
 *   SA_RESTART                   does not exist; defined as 0
 *
 * What cannot be filled
 *
 * Horizon does not deliver signals. The SDK's thread suspension works through
 * signals (SIGRTMIN+n or SIGUSR1/2), and that cannot work here however much
 * shimming is added. It is replaced by svcSetThreadActivity, the real
 * mechanism. See threading_switch.cpp.
 *
 * The thread registry, and why it is needed
 *
 * libnx exposes no public way to get the Horizon Handle from another thread's
 * pthread_t; only threadGetCurHandle() for the calling thread. Since the SDK
 * changes the priority and affinity of other threads, a registry of our own is
 * kept, which each thread fills in when it starts.
 */
#pragma once

#if defined(__SWITCH__)

/*
 * Careful: <switch.h> is deliberately not included here.
 *
 * libnx pollutes the global namespace with Thread, Timer, Event, Mutex,
 * Handle, Result... and the SDK has rex::thread::Thread, ::Timer, ::Event,
 * ::Mutant. Including switch.h in a header that ends up inside
 * threading_posix.cpp causes an avalanche of incomprehensible errors.
 * This shim's .cpp does include it, but privately.
 */
#include <pthread.h>
#include <stdint.h>
#include <string.h>

#ifdef __cplusplus
extern "C" {
#endif

/* The Horizon thread handle, without pulling in switch.h. */
typedef uint32_t RexSwitchHandle;
#define REX_SWITCH_INVALID_HANDLE ((RexSwitchHandle)0)

/* --- CPU sets ---------------------------------------------------------- */

/*
 * The Switch has 4 cores; core 3 is reserved by the system except in title
 * takeover. 64 bits are more than enough and keep the shape of the Linux API.
 */
#define CPU_SETSIZE 64

typedef struct {
    uint64_t bits;
} cpu_set_t;

static inline void CPU_ZERO(cpu_set_t* s) { s->bits = 0; }
static inline void CPU_SET(int cpu, cpu_set_t* s) {
    if (cpu >= 0 && cpu < CPU_SETSIZE) s->bits |= (uint64_t)1 << cpu;
}
static inline void CPU_CLR(int cpu, cpu_set_t* s) {
    if (cpu >= 0 && cpu < CPU_SETSIZE) s->bits &= ~((uint64_t)1 << cpu);
}
static inline int CPU_ISSET(int cpu, const cpu_set_t* s) {
    return (cpu >= 0 && cpu < CPU_SETSIZE) && ((s->bits >> cpu) & 1);
}
static inline int CPU_COUNT(const cpu_set_t* s) {
    return __builtin_popcountll(s->bits);
}

/* --- what newlib does not define --------------------------------------- */

#ifndef SA_RESTART
#define SA_RESTART 0
#endif

/*
 * Horizon has no robust mutexes. The calls are accepted and do nothing,
 * because the SDK uses them as a safeguard, not as a requirement.
 */
#ifndef PTHREAD_MUTEX_STALLED
#define PTHREAD_MUTEX_STALLED 0
#endif
#ifndef PTHREAD_MUTEX_ROBUST
#define PTHREAD_MUTEX_ROBUST 1
#endif

int pthread_mutexattr_setrobust(pthread_mutexattr_t* attr, int robustness);
int pthread_mutexattr_getrobust(const pthread_mutexattr_t* attr, int* robustness);
int pthread_attr_setschedpolicy(pthread_attr_t* attr, int policy);
/*
 * Without robust mutexes there is no EOWNERDEAD, so this is never actually
 * called. It exists so that the recovery path compiles.
 */
int pthread_mutex_consistent(pthread_mutex_t* mutex);

/* --- affinity and priority, on top of the system calls ----------------- */

int pthread_getaffinity_np(pthread_t thread, size_t size, cpu_set_t* set);
int pthread_setaffinity_np(pthread_t thread, size_t size, const cpu_set_t* set);
int pthread_getschedparam(pthread_t thread, int* policy, struct sched_param* param);
int pthread_setschedparam(pthread_t thread, int policy, const struct sched_param* param);

/* --- thread registry -------------------------------------------------- */

/* Registers the current thread. Called right on entry to the thread body. */
void RexSwitchRegisterCurrentThread(void);
/* Removes it. Called on exit. */
void RexSwitchUnregisterCurrentThread(void);
/* Horizon handle of another pthread, or REX_SWITCH_INVALID_HANDLE. */
RexSwitchHandle RexSwitchHandleFor(pthread_t thread);

/* --- suspension, which on Horizon does not use signals ----------------- */

int RexSwitchPauseThread(pthread_t thread);
int RexSwitchResumeThread(pthread_t thread);

/*
 * --- the priority scheme -------------------------------------------------
 *
 * HOS only time-slices threads at the preemption priority (0x3B); the other
 * priorities are cooperative. Recompiled code busy-waits constantly, so guest
 * threads have to run at 0x3B, and host service threads above them (lower
 * number) so they can preempt them.
 *
 * Without this, audio dropouts and stutter are guaranteed. It is the split used
 * by MarathonRecomp-NX, a finished Horizon port.
 */
#define REX_SWITCH_PRIO_AUDIO   0x2B  /* audio and decoder: the most urgent */
#define REX_SWITCH_PRIO_PRESENT 0x2C  /* presentation: must win over the spinners */
#define REX_SWITCH_PRIO_GUEST   0x3B  /* guest threads and heavy compute: the only band
                                       * with time slicing */

/* Unique id of the current thread. Horizon has no gettid(). */
uint32_t RexSwitchCurrentThreadId(void);

/* Changes the priority of the current thread. */
void RexSwitchSetCurrentThreadPriority(int priority);
/* Same, but reports whether the kernel really accepted it. Use it when that must be checked. */
bool RexSwitchSetCurrentThreadPriorityOk(int priority);

/*
 * Preferred core of the current thread, without touching its mask (not an exclusive affinity: the
 * kernel can keep moving it). -1 goes back to the process default core. Returns whether the kernel
 * accepted it. See the long comment in the .cpp.
 */
bool RexSwitchSetCurrentThreadCore(int core);

/*
 * The real pin: besides preferring that core, it forbids the others. More dangerous than
 * RexSwitchSetCurrentThreadCore (if that core saturates, the thread does not run). Returns whether
 * it was accepted.
 */
bool RexSwitchPinCurrentThreadToCore(int core);

/* banjo-nx (2026-10-16, ported 2026-10-20 for Renut's renderer): undoes RexSwitchPinCurrentThreadToCore: the current
 * thread may run on every core of the process again (the process's core mask), preferring `core` (-1: the process
 * default). For in-run A/Bs of a pin. */
bool RexSwitchUnpinCurrentThread(int core);

/* Which core the calling thread is running on right now. It can only be asked about oneself. */
int RexSwitchCurrentCore(void);

/* sasrt-nx (2026-11-09, banjo-nx's four-core mode, from NetherSX2_nx): with four cores granted (a forwarder's NPDM:
 * RexSwitchEnsureForwarderNpdm) core 3 is the "system core": the threads sasrt_system_core_threads names go there
 * alone, every other thread's mask loses it (__wrap_svcSetThreadCoreMask). RexSwitchInitSystemCore reads the keys
 * (after the toml); the others answer -1 / false with three cores. */
int RexSwitchInitSystemCore(void);
int RexSwitchEnsureForwarderNpdm(void);
unsigned RexSwitchProcessCoreMask(void);
int RexSwitchSystemCore(void);
int RexSwitchSystemCoreMode(void);
unsigned RexSwitchAppCoreMask(void);
bool RexSwitchMoveCurrentThreadToSystemCore(int priority);
// banjo-nx (2026-11-22): the calling thread's cores set to 'mask' (bits of cores) with 'preferred' its ideal one, the
// system core kept in it (svcSetThreadCoreMask's wrap takes the system core out of a mask of several cores); the
// process's cores only. False when nothing of the mask is the process's or the call fails.
bool RexSwitchSetCurrentThreadCoresWithSystem(int preferred, unsigned mask);
bool RexSwitchMoveThreadToSystemCore(pthread_t thread);
/* sasrt-nx (2026-11-10, sasrt_boost_threads): another thread's priority (Horizon numbers: lower is more urgent). */
bool RexSwitchSetThreadPriority(pthread_t thread, int priority);
bool RexSwitchSystemCoreWants(const char* name);
bool RexSwitchMoveCurrentThreadToAppCores(void);
bool RexSwitchMoveThreadToAppCores(pthread_t thread);
/* blur-nx (2026-11-18): with four_core_mode false RexSwitchEnsureForwarderNpdm removes the forwarder's NPDM instead (3
 * removed, 0 none of ours there); this does the same for the game menu's four-core option (on: written, off: removed),
 * at once. */
int RexSwitchApplyFourCoreMode(int on);
void RexSwitchSampleCoreIdle(void);
bool RexSwitchCoreIdleSample(int core, unsigned long long* idle_ticks, unsigned long long* at_ticks);
void RexSwitchSystemCoreDescribe(char* out, size_t out_len);

/*
 * --- why a thread could not be created -------------------------------------------------------------
 *
 * libnx reports every threadCreate failure as ENOMEM. This writes which resource is missing for a thread
 * with this stack size, in the order libnx needs them: one heap block for the stack (memalign), room for
 * its mirror in the stack region (virtmemFindStack before svcMapMemory), a kernel thread slot (the process
 * resource limit, svcCreateThread). For the failure path only: it allocates and frees a block of that size
 * and walks the heap (mallinfo).
 */
void RexSwitchDescribeThreadFailure(size_t stack_size, char* out, size_t out_len);

/* sasrt-nx (2026-11-09, the title's memory governor): the guest thread stacks kept for the next threads (the pool,
 * switch_thread_stack_pool) back to the heap now; the bytes given. A thread made later takes a new block. */
size_t RexSwitchReleaseSpareStacks(void);
/* sasrt-nx (2026-11-09 night): the pooled-size (guest) stacks in use, and the kept ones with their bytes. */
void RexSwitchStackFigures(size_t* live, size_t* kept, size_t* kept_bytes);
/* sasrt-nx (2026-11-09 night): pooled-size stacks taken so far (new and reused): a count that stops moving when no
 * guest thread is being made (the title's governor gives the kept stacks back after a minute of that). */
uint64_t RexSwitchStacksTaken(void);

/* sasrt-nx (2026-11-10, thread_event_address_wait): Horizon's address arbitration for the events' waits
 * (address_event_core.h). RexSwitchWaitIfEqual sleeps while *word == value, at most ns (-1: no limit); false only when
 * it timed out (true: woken, or the word had changed). RexSwitchWakeAddress wakes count threads sleeping on word
 * (-1: all). */
bool RexSwitchWaitIfEqual(volatile uint32_t* word, uint32_t value, int64_t ns);
void RexSwitchWakeAddress(volatile uint32_t* word, int32_t count);
/* blur-nx (2026-11-12, CPU batch 3): switch_thread_priorities. Gives the thread 'handle' the priority of the first
 * table entry whose prefix starts 'name'; returns that priority, or -1 (no entry, or the call failed). */
int RexSwitchApplyNamedPriority(unsigned handle, const char* name);
/* How many threads switch_thread_priorities has set (for the log). */
unsigned RexSwitchNamedPrioritiesApplied(void);

#ifdef __cplusplus
}
#endif

#endif  /* __SWITCH__ */
