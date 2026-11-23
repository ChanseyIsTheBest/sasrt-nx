#!/usr/bin/env python3
"""Writes "localized copies" of recompiled guest functions: native replacements made mechanically from the generated C++
(app/generated/default), into app/generated/hot/n_<ADDR>.h, plus app/generated/hot/hooks.inc, the hook registrations
that app/src/hot/sasrt_hot_guest.cpp includes (sa2-nx's tools/localize_native.py, UnleashedRecomp-NX's
switch-localize.py idea).

A copy runs exactly the same operations as the recompiled function, with two differences that make it faster:
  - the guest registers it uses (r, f, v, cr0-cr7, ctr, xer, reserved) live in C++ locals instead of the PPCContext:
    loaded from ctx at entry, written back to ctx before every call and every return, and reloaded after every call,
    so callers and callees see exactly the state the recompiled function would leave. Every register it uses is
    written back with the value the original leaves, so it never writes a register the original leaves alone
    (interprocedural register allocation: tools/call_site_liveness.py);
  - guest memory is accessed without `volatile` (sasrt_hot_guest.cpp redefines the REX_LOAD/STORE macros), so the
    compiler can pair and schedule the loads and stores. Every loop header (a label a later goto of the same function
    jumps back to) gets REX_LOOP_BARRIER(), a compiler memory barrier: GCC hoisted guest polls out of loops otherwise
    (futari-nx's console hang; tools/loop_barriers.py does the same for the optimised flavour's generated code).
ctx.lr, ctx.fpscr and ctx.msr stay in the context.

Leaf functions (no call) whose memory accesses all go through the REX_LOAD/STORE macros also get Shadow(): the same
body with every guest store kept in a ShadowMemory and every load reading it first. The guard of sasrt_hot_guest.cpp
runs Shadow on a copy of the registers, the original for real, and compares every register and every byte the shadow
stored: no hand-written list of written ranges, and no rollback. The others run unguarded (callees' side effects
would happen twice), exact by construction.

Exactness caveat: floating-point code must not contain double-precision multiply/add pairs that the compiler could
contract differently in the two copies. Single-precision results go through float() roundings no contraction crosses;
a bare double multiply, add or subtract is refused unless --allow-double. (The build has -ffp-contract=off anyway.)

  python tools/localize_native.py --list app/src/hot/localized.txt      (all of them + hooks.inc; post_codegen.py
                                                                          runs this after every codegen)
  python tools/localize_native.py 82146ED8 --what "..." [--out file]     (one, for a look)
  python tools/localize_native.py --check <addresses>                     (which can be localized, leaf/shadow or not)
"""
import argparse
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(ROOT, 'app', 'generated', 'default')
HOT = os.path.join(ROOT, 'app', 'generated', 'hot')
IMAGE = os.path.join(ROOT, 'out', 'default_image.bin')
IMAGE_BASE = 0x82000000
REG = re.compile(r'\bctx\.(r\d+|f\d+|v\d+|cr\d|ctr|xer|reserved)\b')
# Calls: recompiled functions, the save/restore helpers (__savegprlr_N and friends read and write the context too),
# indirect calls and traps.
CALLEE = r'(?:__imp__)?(?:sub_[0-9A-F]+|__(?:save|rest)[a-z]+_\d+)'
CALL = re.compile(r'\b' + CALLEE + r'\(ctx, base\);|\bREX_CALL_INDIRECT_FUNC\([^;]*\);|\bppc_trap\(ctx, base[^;]*\);')
LABEL = re.compile(r'^(loc_[0-9A-F]{8}):\s*$')
GOTO = re.compile(r'goto (loc_[0-9A-F]{8});')
BARRIER = '\tREX_LOOP_BARRIER();'
# Memory accessed some other way than the REX_LOAD/STORE macros: no shadow run for these.
RAW_MEMORY = re.compile(r'\bREX_RAW_ADDR\b|\bREX_ADDR_D\b|\bREX_MM_|\bREX_LOAD_STRING\b|\bbase \+|\bbase\[')
MEMORY_MACROS = ['REX_LOAD_U8', 'REX_LOAD_U16', 'REX_LOAD_U32', 'REX_LOAD_U64', 'REX_STORE_U8', 'REX_STORE_U16',
                 'REX_STORE_U32', 'REX_STORE_U64', 'REX_LOAD_D_U8', 'REX_LOAD_D_U16', 'REX_LOAD_D_U32', 'REX_LOAD_D_U64',
                 'REX_STORE_D_U8', 'REX_STORE_D_U16', 'REX_STORE_D_U32', 'REX_STORE_D_U64']
# The 16-byte vector loads and stores through REX_RAW_ADDR (lvx and the aligned halves of lvlx/lvrx, stvx): the only
# raw accesses a shadow run can take over, through ShLoadV / ShStoreV (sasrt_hot_guest.cpp). Any other raw access
# leaves a copy unguarded.
VLOAD = 'simde_mm_load_si128((simde__m128i*)REX_RAW_ADDR('
VSTORE = 'simde_mm_store_si128((simde__m128i*)REX_RAW_ADDR('


def closing(text, i):
    """Index of the ')' closing the '(' just before position i."""
    depth = 1
    while i < len(text):
        if text[i] == '(':
            depth += 1
        elif text[i] == ')':
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError('unbalanced parentheses')


def shadow_vectors(line):
    """The line with its vector loads/stores through REX_RAW_ADDR going through the shadow (recursively)."""
    out, i = '', 0
    while True:
        found = [j for j in (line.find(VLOAD, i), line.find(VSTORE, i)) if j >= 0]
        if not found:
            return out + line[i:]
        j = min(found)
        out += line[i:j]
        if line.startswith(VLOAD, j):
            k = j + len(VLOAD)
            e = closing(line, k)  # closes REX_RAW_ADDR(
            if line[e + 1:e + 2] != ')':
                raise ValueError('unexpected vector load shape')
            out += f'::sasrt::hot::ShLoadV(m, base, (u32)({shadow_vectors(line[k:e])}))'
            i = e + 2
        else:
            k = j + len(VSTORE)
            e = closing(line, k)  # closes REX_RAW_ADDR(
            if line[e + 1:e + 3] != ', ':
                raise ValueError('unexpected vector store shape')
            close = closing(line, e + 3)  # closes simde_mm_store_si128(
            out += (f'::sasrt::hot::ShStoreV(m, (u32)({shadow_vectors(line[k:e])}), '
                    f'{shadow_vectors(line[e + 3:close])})')
            i = close + 1


def raw_after_vectors(line):
    """True when the line accesses memory raw in a way a shadow run cannot take over."""
    try:
        return RAW_MEMORY.search(shadow_vectors(line)) is not None
    except ValueError:
        return True


SHADOW_DEFINES = '''#define REX_LOAD_U8(x) ::sasrt::hot::ShLoad8(m, base, (u32)(x))
#define REX_LOAD_U16(x) ::sasrt::hot::ShLoad16(m, base, (u32)(x))
#define REX_LOAD_U32(x) ::sasrt::hot::ShLoad32(m, base, (u32)(x))
#define REX_LOAD_U64(x) ::sasrt::hot::ShLoad64(m, base, (u32)(x))
#define REX_STORE_U8(x, y) ::sasrt::hot::ShStore8(m, (u32)(x), (u8)(y))
#define REX_STORE_U16(x, y) ::sasrt::hot::ShStore16(m, (u32)(x), (u16)(y))
#define REX_STORE_U32(x, y) ::sasrt::hot::ShStore32(m, (u32)(x), (u32)(y))
#define REX_STORE_U64(x, y) ::sasrt::hot::ShStore64(m, (u32)(x), (u64)(y))
#define REX_LOAD_D_U8(r, d) REX_LOAD_U8((u32)(r) + (d))
#define REX_LOAD_D_U16(r, d) REX_LOAD_U16((u32)(r) + (d))
#define REX_LOAD_D_U32(r, d) REX_LOAD_U32((u32)(r) + (d))
#define REX_LOAD_D_U64(r, d) REX_LOAD_U64((u32)(r) + (d))
#define REX_STORE_D_U8(r, d, y) REX_STORE_U8((u32)(r) + (d), y)
#define REX_STORE_D_U16(r, d, y) REX_STORE_U16((u32)(r) + (d), y)
#define REX_STORE_D_U32(r, d, y) REX_STORE_U32((u32)(r) + (d), y)
#define REX_STORE_D_U64(r, d, y) REX_STORE_U64((u32)(r) + (d), y)
'''


def function_starts(gen):
    starts = set()
    for path in glob.glob(os.path.join(gen, '*_recomp.*.cpp')):
        for m in re.finditer(r'^DEFINE_REX_FUNC\(sub_([0-9A-F]+)\)', open(path, encoding='utf-8', errors='replace').read(),
                             re.M):
            starts.add(int(m.group(1), 16))
    return sorted(starts)


def fnv1a64(data):
    h = 0xCBF29CE484222325
    for b in data:
        h ^= b
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


def code_hash(addr, starts, image):
    following = [s for s in starts if s > addr]
    end = following[0] if following else addr + 4
    code = image[addr - IMAGE_BASE:end - IMAGE_BASE]
    return len(code), fnv1a64(code)


def find_body(gen, name):
    for path in sorted(glob.glob(os.path.join(gen, '*_recomp.*.cpp'))):
        text = open(path, encoding='utf-8', errors='replace').read()
        m = re.search(r'^DEFINE_REX_FUNC\(' + name + r'\) \{\n(.*?)^\}\n', text, re.S | re.M)
        if m:
            return m.group(1), path
    return None, None


def type_of(reg):
    if reg.startswith('cr'):
        return 'PPCCRRegister'
    if reg == 'xer':
        return 'PPCXERRegister'
    if reg.startswith('v'):
        return 'PPCVRegister'
    return 'PPCRegister'


def analyse(addr, gen, allow_double):
    """(body lines, path, problem or None, calls, shadow-able)."""
    name = 'sub_' + addr
    body, path = find_body(gen, name)
    if body is None:
        return None, None, f'{name} not found in {gen}', 0, False
    lines = body.splitlines()
    risky = [l for l in lines if re.search(r'\.f64 = (?:ctx\.)?f\d+\.f64 [-+*] (?:ctx\.)?f\d+\.f64;', l)]
    if risky and not allow_double:
        return lines, path, 'double-precision arithmetic (check contraction by hand, --allow-double)', 0, False
    code = [l for l in lines if not l.strip().startswith('//')]
    calls = sum(len(CALL.findall(l)) for l in code)
    raw = any(raw_after_vectors(l) for l in code)
    return lines, path, None, calls, calls == 0 and not raw


def with_barriers(code):
    """REX_LOOP_BARRIER() after every loop header (a label a later goto of the same function jumps back to)."""
    seen, headers = set(), set()
    for line in code:
        m = LABEL.match(line)
        if m:
            seen.add(m.group(1))
            continue
        for target in GOTO.findall(line):
            if target in seen:
                headers.add(target)
    out = []
    for i, line in enumerate(code):
        out.append(line)
        m = LABEL.match(line)
        if m and m.group(1) in headers and (i + 1 >= len(code) or code[i + 1].strip() != 'REX_LOOP_BARRIER();'):
            out.append(BARRIER)
    return out, len(headers)


def localize(addr, what, gen, out, allow_double):
    lines, path, problem, calls, shadow = analyse(addr, gen, allow_double)
    if problem:
        sys.exit(f'sub_{addr}: {problem}')
    regs = sorted({m.group(1) for l in lines for m in REG.finditer(l)},
                  key=lambda r: (re.sub(r'\d', '', r), int(re.sub(r'\D', '', r) or 0)))
    out_regs = '; '.join(f'ctx.{r} = l_{r}' for r in regs) or '(void)0'
    in_regs = '; '.join(f'l_{r} = ctx.{r}' for r in regs) or '(void)0'
    code = []
    for l in lines:
        if l.strip().startswith('//'):
            continue  # the PPC disassembly comments
        l = REG.sub(lambda m: 'l_' + m.group(1), l)
        # Calls and returns get braces: the generated code also writes them as the body of a one-line `if`
        # ("if (ctx.cr6.eq) return;"), where a bare "SASRT_SYNC_OUT(); return;" would return unconditionally.
        l = CALL.sub(lambda m: '{ SASRT_SYNC_OUT(); ' + m.group(0) + ' SASRT_SYNC_IN(); }', l)
        l = re.sub(r'\breturn;', '{ SASRT_SYNC_OUT(); return; }', l)
        code.append(l)
    code, loops = with_barriers(code)
    code.append('\tSASRT_SYNC_OUT();')  # falling off the end of the function is a return too
    decl = '\n'.join(f'  {type_of(r)} l_{r} = ctx.{r};' for r in regs)
    callees = sorted({m.group(1) for l in lines for m in re.finditer(r'\b(' + CALLEE + r')\(ctx, base\)', l)})
    externs = ''.join(f'REX_EXTERN({c});\n' for c in callees)
    rel = os.path.relpath(path, ROOT).replace('\\', '/')
    body = '\n'.join(code)
    sync = (f'#define SASRT_SYNC_OUT() do {{ {out_regs}; }} while (0)\n'
            f'#define SASRT_SYNC_IN() do {{ {in_regs}; }} while (0)\n')
    shadow_fn = ''
    if shadow:
        shadow_body = '\n'.join(shadow_vectors(l) for l in body.split('\n'))
        push = ''.join(f'#pragma push_macro("{n}")\n#undef {n}\n' for n in MEMORY_MACROS)
        pop = ''.join(f'#pragma pop_macro("{n}")\n' for n in MEMORY_MACROS)
        shadow_fn = f'''
// The same body with every guest store kept in `m` (loads read it first): the guard's shadow run.
{push}{SHADOW_DEFINES}inline void Shadow(PPCContext& ctx, uint8_t* base, ::sasrt::hot::ShadowMemory& m) {{
{decl}
{sync}{shadow_body}
#undef SASRT_SYNC_OUT
#undef SASRT_SYNC_IN
}}
{pop}'''
    text = f'''// sub_{addr}: {what}.
// GENERATED by tools/localize_native.py from {rel} (do not edit; post_codegen.py re-runs the tool after every
// codegen): the recompiled function's own operations, with its {len(regs)} guest registers in C++ locals (written back
// before each of its {calls} call(s) and at every return), plain guest memory accesses and a compiler barrier at each of
// its {loops} loop header(s). Exact by construction{"; the guard compares its Shadow() run with the original" if shadow else ""}.
#pragma once

{externs}
namespace sasrt::hot::n_{addr} {{

inline void Native(PPCContext& ctx, uint8_t* base) {{
{decl}
{sync}{body}
#undef SASRT_SYNC_OUT
#undef SASRT_SYNC_IN
}}
{shadow_fn}
}}  // namespace sasrt::hot::n_{addr}
'''
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, 'w', encoding='utf-8', newline='\n').write(text)
    return len(regs), calls, loops, shadow


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('address', nargs='?')
    ap.add_argument('--what', default='')
    ap.add_argument('--gen', default=GEN)
    ap.add_argument('--out')
    ap.add_argument('--allow-double', action='store_true')
    ap.add_argument('--list', help='file of "<address> <what>" lines: localize them all into app/generated/hot/ and '
                                   'write app/generated/hot/hooks.inc')
    ap.add_argument('--check', nargs='*', help='report which of these addresses can be localized')
    a = ap.parse_args()
    if a.check is not None:
        for addr in a.check:
            addr = addr.upper().replace('SUB_', '')
            _, _, problem, calls, shadow = analyse(addr, a.gen, a.allow_double)
            print(f'{addr}: {problem or ("leaf, shadow guard" if shadow else f"{calls} call(s): unguarded" if calls else "leaf, raw memory: unguarded")}')
        return
    if a.list:
        starts = function_starts(a.gen)
        image = open(IMAGE, 'rb').read()
        hooks = ['// GENERATED by tools/localize_native.py --list app/src/hot/localized.txt: the hook of every localized '
                 'copy (sasrt_hot_guest.cpp includes it).']
        n_shadow = 0
        for line in open(a.list, encoding='utf-8'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            addr, _, what = line.partition(' ')
            addr = addr.upper()
            what = what.strip() or f'sub_{addr}'
            regs, calls, loops, shadow = localize(addr, what, a.gen, os.path.join(HOT, f'n_{addr}.h'), a.allow_double)
            size, h = code_hash(int(addr, 16), starts, image)
            macro = 'SASRT_HOT_HOOK_SHADOW' if shadow else 'SASRT_HOT_HOOK_UNGUARDED'
            n_shadow += shadow
            desc = what.replace('\\', '').replace('"', "'")
            hooks.append(f'#include "n_{addr}.h"')
            hooks.append(f'{macro}({addr}, sasrt_cpu_native_sub_{addr.lower()}, "Native localized copy of sub_{addr}: '
                         f'{desc}", {size}, 0x{h:016X}ull)')
            print(f'sub_{addr}: {regs} registers localized, {calls} calls, {loops} loops, '
                  f'{"shadow guard" if shadow else "unguarded"}, {size} bytes, hash 0x{h:016X}')
        open(os.path.join(HOT, 'hooks.inc'), 'w', encoding='utf-8', newline='\n').write('\n'.join(hooks) + '\n')
        print(f'hooks.inc: {len(hooks) - 1 >> 1} hooks, {n_shadow} with the shadow guard')
        return
    if not a.address:
        ap.error('an address, --list or --check')
    addr = a.address.upper().replace('SUB_', '').replace('0X', '')
    print(localize(addr, a.what or f'sub_{addr}', a.gen, a.out or os.path.join(HOT, f'n_{addr}.h'), a.allow_double))


if __name__ == '__main__':
    main()
