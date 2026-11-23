# Machine-copy idea 27 for the base: the guard forms only in a guard / verify build

From sasrt-nx (2026-11-10; not a git repo, so this file is the patch). Asked for by the Blur session for the ultimate
base, 2026-11-11.

## What it does

- tools/localize_native.py already writes each copy header with `Native` (the fast form), `NativeLogged` and
  `ReferenceLogged` (the guard's two logged forms: the copy and the original statements `o_*`, instantiated with
  `::banjo::hot::Logged`) and `NativeCounted`. All are inline or templates: a form nothing takes the address of is never
  instantiated. **No generator change is needed.**
- With `BANJO_HOT_GUARD_FORMS=0` the hook macro passes `nullptr` for the two logged forms, so they and the `o_*` copies
  of the original statements are never compiled: about two thirds of the copies' code in SASRT (NRO 85.6 to 74.2 MB
  with the batch it shipped in). InitHook then always picks `kDirect` (the hook calls `Native` directly), whatever
  `banjo_hot_guard_*` / `sasrt_cpu_verify` say, and warns once if one of them asks for a guard.
- `NativeCounted` (banjo_hot_count) stays; it is only instantiated through `BANJO_HOT_COUNTED`, untouched here.
- -Final in build_switch.ps1 does exactly two things: LTO ON (`SASRT_SWITCH_LTO`) and these forms OFF (unless
  -GuardForms). Nothing else.

## Check after porting

- A guard build (-GuardForms, or no -Final) still runs the guard: the race log's `[hot]` lines say "guard" / "verify".
- The -Final NRO is smaller and its `[hot]` lines say "direct"; with `banjo_hot_guard_calls` > 0 in a toml it logs the
  one warning ("this build has no guard forms") and stays direct.

## The code

### app/CMakeLists.txt (the option; the sasrt target is the one that compiles the copies and banjo_hot_guest.cpp)

```cmake
# sasrt-nx (2026-11-10, machine-copy idea 27): the guard's logged forms of every localized copy. OFF (a shipping build
# that runs no guard): about two thirds of the copies' code is not made; every hook calls its copy directly.
option(SASRT_HOT_GUARD_FORMS "Localized copies: the guard's logged forms (banjo_hot_guard_*, sasrt_cpu_verify)" ON)
if(NOT SASRT_HOT_GUARD_FORMS)
    target_compile_definitions(sasrt PRIVATE BANJO_HOT_GUARD_FORMS=0)
endif()
```

### app/src/cpu/banjo_hot_guest.h (the two macros; the hook macro uses them in place of &n_##ID::NativeLogged / ReferenceLogged)

```cpp
// sasrt-nx (2026-11-10, machine-copy idea 27): the guard's two forms of every copy (the copy's logged form and the
// original statements' logged form, about two thirds of the copies' code) are made only with BANJO_HOT_GUARD_FORMS
// (CMake SASRT_HOT_GUARD_FORMS, ON by default; a shipping build without the guard turns it OFF). Without them every
// hook calls its copy directly (InitHook), whatever banjo_hot_guard_* say.
#ifndef BANJO_HOT_GUARD_FORMS
#define BANJO_HOT_GUARD_FORMS 1
#endif
#if BANJO_HOT_GUARD_FORMS
#define BANJO_HOT_LOGGED(ID) &n_##ID::NativeLogged
#define BANJO_HOT_REFERENCE(ID) &n_##ID::ReferenceLogged
#else
#define BANJO_HOT_LOGGED(ID) nullptr
#define BANJO_HOT_REFERENCE(ID) nullptr
#endif
...
  Hook g_hook_##ID{#SYM, #KEY, &__imp__##SYM, &n_##ID::Native, BANJO_HOT_LOGGED(ID), BANJO_HOT_REFERENCE(ID),    \
```

### app/src/cpu/banjo_hot_guest.cpp, InitHook (no forms: always direct; warn once if a guard key asks for one)

```cpp
  // No guard at all: the hook calls its copy directly (banjo_hot_guest.h, kDirect). sasrt-nx (2026-11-10, machine-copy
  // idea 27): also when the build has no guard forms (BANJO_HOT_GUARD_FORMS 0: the logged forms are not made).
  const bool forms = h.native_logged && h.reference_logged;
  if (!forms && (verify || h.guard_calls || REXCVAR_GET(banjo_hot_guard_period))) {
    static std::atomic<bool> said{false};
    if (!said.exchange(true, std::memory_order_relaxed))
      REXLOG_WARN("[hot] this build has no guard forms (SASRT_HOT_GUARD_FORMS OFF): sasrt_cpu_verify and "
                  "banjo_hot_guard_* are ignored, every native copy is called directly");
  }
  const bool direct = !forms || (!verify && h.guard_calls == 0 && REXCVAR_GET(banjo_hot_guard_period) == 0);
```

### tools/win/build_switch.ps1 (-Final turns the forms off unless -GuardForms; the cache is re-set when it differs)

```powershell
$forms = if ($Final -and -not $GuardForms) { 'OFF' } else { 'ON' }
$cachedForms = Select-String -Path (Join-Path $build 'CMakeCache.txt') -Pattern '^SASRT_HOT_GUARD_FORMS:BOOL=(.*)$' |
    ForEach-Object { $_.Matches[0].Groups[1].Value } | Select-Object -First 1
if ("$cachedForms" -ne $forms) {
    & cmake "-DSASRT_HOT_GUARD_FORMS=$forms" $build
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
}
```
