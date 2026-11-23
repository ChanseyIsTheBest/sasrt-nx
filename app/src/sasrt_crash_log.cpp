// Windows: logs fatal host exceptions that the SDK does not report (illegal instruction from a __builtin_trap in the
// generated code, divide by zero, stack overflow, ...) with the module and offset, so the crash can be symbolized
// afterwards: llvm-symbolizer --obj=sasrt.exe 0x<0x140000000 + offset>. Access violations are left alone: the SDK
// handles those itself (guest memory, MMIO) and reports the unhandled ones.

#if defined(_WIN32)

#include <windows.h>

#include <cstring>

#include <rex/logging.h>
#include <rex/logging/api.h>

namespace {

LONG CALLBACK LogFatalException(EXCEPTION_POINTERS* info) {
  const DWORD code = info->ExceptionRecord->ExceptionCode;
  switch (code) {
    case EXCEPTION_ILLEGAL_INSTRUCTION:
    case EXCEPTION_PRIV_INSTRUCTION:
    case EXCEPTION_INT_DIVIDE_BY_ZERO:
    case EXCEPTION_STACK_OVERFLOW:
    case EXCEPTION_ARRAY_BOUNDS_EXCEEDED:
    case STATUS_STACK_BUFFER_OVERRUN:
      break;
    default:
      return EXCEPTION_CONTINUE_SEARCH;
  }
  const auto pc = reinterpret_cast<uintptr_t>(info->ExceptionRecord->ExceptionAddress);
  HMODULE module = nullptr;
  char path[MAX_PATH] = "?";
  if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                         reinterpret_cast<LPCSTR>(pc), &module) && module) {
    GetModuleFileNameA(module, path, MAX_PATH);
  }
  const char* name = std::strrchr(path, '\\');
  REXLOG_CRITICAL("[crash] host exception {:08X} at {:016X} ({}+0x{:X}) on thread {}", uint32_t(code), pc,
                  name ? name + 1 : path, pc - reinterpret_cast<uintptr_t>(module), GetCurrentThreadId());
  rex::FlushLogging();
  return EXCEPTION_CONTINUE_SEARCH;
}

// Installed before main, first in the chain; it only logs and never handles.
const PVOID g_handler = AddVectoredExceptionHandler(1, LogFatalException);

// sasrt-nx (2026-11-08): an access violation nothing handled (the SDK handles guest memory's itself), with the address
// it read or wrote and the caller frames' return addresses into the exe, for llvm-symbolizer.
LONG WINAPI LogUnhandled(EXCEPTION_POINTERS* info) {
  const DWORD code = info->ExceptionRecord->ExceptionCode;
  const auto pc = reinterpret_cast<uintptr_t>(info->ExceptionRecord->ExceptionAddress);
  HMODULE module = nullptr;
  char path[MAX_PATH] = "?";
  if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                         reinterpret_cast<LPCSTR>(pc), &module) && module) {
    GetModuleFileNameA(module, path, MAX_PATH);
  }
  const char* name = std::strrchr(path, '\\');
  const uintptr_t data = info->ExceptionRecord->NumberParameters >= 2 ? info->ExceptionRecord->ExceptionInformation[1] : 0;
  REXLOG_CRITICAL("[crash] unhandled exception {:08X} at {:016X} ({}+0x{:X}), data address {:016X}, thread {}",
                  uint32_t(code), pc, name ? name + 1 : path, pc - reinterpret_cast<uintptr_t>(module), data,
                  GetCurrentThreadId());
  // Return addresses on the stack that point into the exe (a rough backtrace).
  const HMODULE exe = GetModuleHandleA(nullptr);
  const auto lo = reinterpret_cast<uintptr_t>(exe);
  const auto* sp = reinterpret_cast<const uintptr_t*>(info->ContextRecord->Rsp);
  int found = 0;
  for (int i = 0; i < 2048 && found < 24; ++i) {
    const uintptr_t v = sp[i];
    if (v > lo && v < lo + 0x8000000) {
      REXLOG_CRITICAL("[crash]   stack [{}] exe+0x{:X}", i, v - lo);
      ++found;
    }
  }
  rex::FlushLogging();
  return EXCEPTION_CONTINUE_SEARCH;
}
const LPTOP_LEVEL_EXCEPTION_FILTER g_previous_filter = SetUnhandledExceptionFilter(LogUnhandled);

}  // namespace

#endif
