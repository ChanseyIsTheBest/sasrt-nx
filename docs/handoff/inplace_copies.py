# sasrt-nx (2026-11-11 ~19:00, the user: "go ahead with the plan"): machine copies IN PLACE, behind CMake
# SASRT_HOT_IN_PLACE (OFF: the hooked copies as before). With it ON:
#   - each copy's hook is a bare redirect: the generated function's symbol (REX_HOOK_RAW) IS the copy's Native, inlinable
#     (no [[gnu::noinline]]): no state byte, no guard, no per-copy key at run time (a copy marked off in the list keeps
#     the original), no in-run A/B 70. The originals (__imp__) lose their last reference and LTO drops them.
#   - the guard's logged forms are not made (BANJO_HOT_GUARD_FORMS 0): the guard is a verify build's (switch OFF).
#   - list entries marked `inplace_only` (the small copies idea 30 drops from the hooked build) are compiled only in place.
# Applied AFTER the 2026-11-11 optimised build (not during it). Idempotent; asserts every anchor once.
R = 'D:/sonic transformed/sasrt-nx/'


def patch(rel, edits, mark):
    path = R + rel
    b = open(path, 'rb').read()
    crlf = b'\r\n' in b
    s = b.decode('utf-8').replace('\r\n', '\n')
    if mark in s:
        print('already patched:', rel)
        return
    for old, new in edits:
        assert s.count(old) == 1, (rel, old[:80], s.count(old))
        s = s.replace(old, new)
    open(path, 'wb').write((s.replace('\n', '\r\n') if crlf else s).encode('utf-8'))
    print('patched:', rel)


patch('app/CMakeLists.txt', [
    ('''option(SASRT_HOT_GUARD_FORMS "Localized copies: the guard's logged forms (banjo_hot_guard_*, sasrt_cpu_verify)" ON)
if(NOT SASRT_HOT_GUARD_FORMS)
    target_compile_definitions(sasrt PRIVATE BANJO_HOT_GUARD_FORMS=0)
endif()''', '''option(SASRT_HOT_GUARD_FORMS "Localized copies: the guard's logged forms (banjo_hot_guard_*, sasrt_cpu_verify)" ON)
# sasrt-nx (2026-11-11, the user: "go ahead with the plan"): machine copies in place. ON: every copy's hook is a bare
# redirect, the generated function's symbol is the copy (inlinable, no state, no guard, no run-time key), the originals
# unreferenced (LTO drops them), and the list's `inplace_only` copies (the small ones) compiled too. Implies no guard
# forms. OFF: the hooked copies (keys, guard, in-run A/B 70).
option(SASRT_HOT_IN_PLACE "Localized copies in place of the generated functions (no hooks, no guard)" OFF)
if(SASRT_HOT_IN_PLACE)
    target_compile_definitions(sasrt PRIVATE BANJO_HOT_IN_PLACE=1 BANJO_HOT_GUARD_FORMS=0)
elseif(NOT SASRT_HOT_GUARD_FORMS)
    target_compile_definitions(sasrt PRIVATE BANJO_HOT_GUARD_FORMS=0)
endif()'''),
], 'SASRT_HOT_IN_PLACE')

patch('app/src/cpu/banjo_hot_guest.h', [
    ('''#ifndef BANJO_HOT_GUARD_FORMS
#define BANJO_HOT_GUARD_FORMS 1
#endif''', '''#ifndef BANJO_HOT_GUARD_FORMS
#define BANJO_HOT_GUARD_FORMS 1
#endif
// sasrt-nx (2026-11-11, CMake SASRT_HOT_IN_PLACE): the copies in place of the generated functions (see BANJO_HOT_HOOK_EX).
#ifndef BANJO_HOT_IN_PLACE
#define BANJO_HOT_IN_PLACE 0
#endif
// The copy's entry: kept out of line behind a hook (one body, the hook's paths around it); inlinable in place.
#ifndef BANJO_HOT_NATIVE_SPEC
#if BANJO_HOT_IN_PLACE
#define BANJO_HOT_NATIVE_SPEC
#else
#define BANJO_HOT_NATIVE_SPEC [[gnu::noinline]]
#endif
#endif'''),
    ('''#define BANJO_HOT_HOOK_EX(SYM, ID, KEY, DEFAULT, SLOT, DESC, BULK, CATEGORY)                                     \\
  REXCVAR_DEFINE_BOOL(KEY, DEFAULT, CATEGORY, DESC).lifecycle(rex::cvar::Lifecycle::kInitOnly);                  \\''',
     '''#if BANJO_HOT_IN_PLACE
// sasrt-nx (2026-11-11, SASRT_HOT_IN_PLACE): the generated function's symbol is the copy itself. The key stays defined
// (tomls that name it still load) but is not read; a copy marked off in the list keeps the original.
#define BANJO_HOT_HOOK_EX(SYM, ID, KEY, DEFAULT, SLOT, DESC, BULK, CATEGORY)                                     \\
  REXCVAR_DEFINE_BOOL(KEY, DEFAULT, CATEGORY, DESC).lifecycle(rex::cvar::Lifecycle::kInitOnly);                  \\
  REX_EXTERN(__imp__##SYM);                                                                                      \\
  REX_HOOK_RAW(SYM) {                                                                                            \\
    if constexpr (DEFAULT)                                                                                       \\
      banjo::hot::n_##ID::Native(ctx, base);                                                                     \\
    else                                                                                                         \\
      __imp__##SYM(ctx, base);                                                                                   \\
  }
#else
#define BANJO_HOT_HOOK_EX(SYM, ID, KEY, DEFAULT, SLOT, DESC, BULK, CATEGORY)                                     \\
  REXCVAR_DEFINE_BOOL(KEY, DEFAULT, CATEGORY, DESC).lifecycle(rex::cvar::Lifecycle::kInitOnly);                  \\'''),
    # close the #else after the hooked macro's last line
    ('''    banjo::hot::n_##ID::Native(ctx, base);                                                                       \\
  }''', '''    banjo::hot::n_##ID::Native(ctx, base);                                                                       \\
  }
#endif  // BANJO_HOT_IN_PLACE'''),
], 'SASRT_HOT_IN_PLACE')

patch('tools/localize_native.py', [
    ('''[[gnu::noinline]] inline void Native(PPCContext& ctx, uint8_t* base) {{''',
     '''BANJO_HOT_NATIVE_SPEC inline void Native(PPCContext& ctx, uint8_t* base) {{'''),
    ('''        if l.startswith('[[gnu::noinline]] inline void Native('):''',
     '''        if l.startswith('BANJO_HOT_NATIVE_SPEC inline void Native('):  # sasrt-nx (2026-11-11, in place)'''),
    # a fallback for the spec where a header is compiled without banjo_hot_guest.h's definition first
    ('''#pragma once

{"".join(f"REX_EXTERN({c});" + chr(10) for c in sorted(externs))}''', '''#pragma once
#ifndef BANJO_HOT_NATIVE_SPEC  // sasrt-nx (2026-11-11): banjo_hot_guest.h's (SASRT_HOT_IN_PLACE)
#define BANJO_HOT_NATIVE_SPEC [[gnu::noinline]]
#endif

{"".join(f"REX_EXTERN({c});" + chr(10) for c in sorted(externs))}'''),
    # the in-place-only copies
    ('''        shard[1] += [f'#include "n_{rid}.h"',
                     f'BANJO_HOT_HOOK_BULK({root}, {rid}, {key_of(root, opts)}, {"false" if opts.get("off") else "true"}, '
                     f'{BULK_SLOT}, "{desc}")']''', '''        lines = [f'#include "n_{rid}.h"',
                 f'BANJO_HOT_HOOK_BULK({root}, {rid}, {key_of(root, opts)}, {"false" if opts.get("off") else "true"}, '
                 f'{BULK_SLOT}, "{desc}")']
        if opts.get('inplace_only'):  # sasrt-nx (2026-11-11): compiled only with SASRT_HOT_IN_PLACE (the small copies)
            lines = ['#if BANJO_HOT_IN_PLACE'] + lines + ['#endif']
        shard[1] += lines'''),
], 'inplace_only')
print('inplace_copies: done (then: the inplace_only list entries, post_codegen, the two builds)')
