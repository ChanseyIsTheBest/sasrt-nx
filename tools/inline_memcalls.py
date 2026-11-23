#!/usr/bin/env python3
"""memcpy / memset calls of a constant size up to 64 bytes inline at the call site (sasrt-nx, 2026-10-14; idea 6 of
sa2-nx's list, also sonic-unleashed-nx's SWITCH_INLINE_MEMCPY).

A call of the C runtime's memcpy or memset whose size register r5 is set to a constant (li r5,N) earlier in the same
straight line, with nothing in between that writes r5, a label or a call, becomes

    REX_MEMCPY_CONST(N, <the call as it was>);      REX_MEMSET_CONST(N, <the call as it was>);

The helpers (in the generated pch, below) copy or fill the N bytes with a few loads and stores the compiler picks for
the constant size, and run the original call when they must not:
  - memcpy: the CRT routine copies FORWARD, so when dst > src and the ranges overlap it smears already-copied bytes:
    the original runs (for dst <= src an overlap gives what memmove gives, and the helper loads everything before it
    stores anything, as the hand-written native memcpy does);
  - both: a range that touches the physical views from 0xA0000000 (they alias each other, so two different guest
    addresses can be the same memory) or 0x7F000000-0x7FFFFFFF (hardware registers, where the width of each write
    matters) runs the original; so does a range that wraps around 4 GB;
  - memcpy keeps the original's first instruction, `std r3,-8(r1)` (lesson (b): the game may read that stack word
    later); memset has no stack store;
  - memcpy reloads r3 from that slot before it returns, so a destination that covers the slot returns the copied
    bytes in r3: that call runs the original (CoversSlot; banjo-nx found the case missing here, 2026-10-14);
  - r3 (the destination, the return value) is left as it is, as both originals leave it. The originals are assembly
    routines that use r0 and r4-r12, ctr and cr0 as scratch; the callers were compiled against the ABI and do not read
    those after the call. The helpers leave them unchanged, as the native memcpy (app/src/hot/n_82C8EEF0.h) always has.

The calls are found by the routines' addresses (tools/crt_signatures.py of sa2-nx found them in this image: memcpy
82C8EEF0, memset 82C8D8D0, both unique matches). memmove has 8 calls of a constant size and is left alone.
REX_INLINE_MEMCALLS_OFF (app/CMakeLists.txt SASRT_GEN_INLINE_MEMCALLS=OFF) gives the calls back.

  python tools/inline_memcalls.py --gen app/generated/default [--memcpy 82C8EEF0] [--memset 82C8D8D0] [--check]
"""
import argparse
import collections
import glob
import os
import re
import sys

SET_R5 = re.compile(r'^\t(?:ctx\.)?r5\.s64 = (-?\d+);$')
WRITES_R5 = re.compile(r'(?:ctx\.|l_|ll_|\b)r5\.[su](?:64|32) =|REX_LOOP_(?:IN|OUT)\(ll_r5|\(ctx, base\)|'
                       r'REX_CALL_INDIRECT|ppc_trap|REX_PROMOTED|\bctx\.r5 =')
DONE = re.compile(r'REX_MEM(?:CPY|SET)_CONST\((\d+), ([^;]*\(ctx, base\))\);')
MARKER = '// rexglue ports: memcpy / memset of a constant size inline (tools/inline_memcalls.py)'
END = '// (end of the macros of tools/inline_memcalls.py)\n'
MACROS = MARKER + r'''
#ifndef REX_MEMCPY_CONST
#if defined(REX_INLINE_MEMCALLS_OFF)
#define REX_MEMCPY_CONST(n, call) call
#define REX_MEMSET_CONST(n, call) call
#else
#include <rex/ppc/memcalls.h>
// The decisions and the copy are in rex/ppc/memcalls.h (tested by sdk/tests/memcalls_test.cpp); here only what needs
// the guest memory macros.
template <uint32_t N>
[[gnu::always_inline]] static inline bool RexMemcpyConst(PPCContext& ctx, uint8_t* base) noexcept {
  const uint32_t dst = ctx.r3.u32, src = ctx.r4.u32;
  if (rex::ppc::CopySmears<N>(dst, src)) return false;      // dst > src, overlapping: the original smears
  if (!rex::ppc::PlainRange<N>(dst) || !rex::ppc::PlainRange<N>(src)) return false;
  if (rex::ppc::CoversSlot<N>(dst, ctx.r1.u32 - 8)) return false;  // the original returns the copied bytes in r3
  REX_STORE_U64(ctx.r1.u32 - 8, ctx.r3.u64);                // std r3,-8(r1), the original's first instruction
  rex::ppc::CopyConst<N>(REX_RAW_ADDR(dst), REX_RAW_ADDR(src));
  return true;
}
template <uint32_t N>
[[gnu::always_inline]] static inline bool RexMemsetConst(PPCContext& ctx, uint8_t* base) noexcept {
  const uint32_t dst = ctx.r3.u32;
  if (!rex::ppc::PlainRange<N>(dst)) return false;
  __builtin_memset(REX_RAW_ADDR(dst), int(ctx.r4.u32 & 0xFF), N);
  return true;
}
#define REX_MEMCPY_CONST(n, call) do { if (!RexMemcpyConst<n>(ctx, base)) { call; } } while (0)
#define REX_MEMSET_CONST(n, call) do { if (!RexMemsetConst<n>(ctx, base)) { call; } } while (0)
#endif  // REX_INLINE_MEMCALLS_OFF
#endif  // REX_MEMCPY_CONST
''' + END


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--gen', required=True)
    # renut-ultimate (2026-11-20, port 200; deadpool-nx's 8c90b5ca): each takes a comma-separated list (a game with two
    # memsets: deadpool-nx's 82F88DF0,82D71E58). sasrt-nx: this game's addresses.
    ap.add_argument('--memcpy', default='82C8EEF0')
    ap.add_argument('--memset', default='82C8D8D0')
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    mc = {x.strip().upper() for x in a.memcpy.split(',') if x.strip()}
    ms = {x.strip().upper() for x in a.memset.split(',') if x.strip()}
    # port 200 (deadpool-nx's): a call followed on its line by an r1 macro (REX_R1_...();, from the r1 passes) is
    # taken too, the macro kept after the inline form.
    call = re.compile(r'^(\t+)((?:__imp__)?sub_(%s)\(ctx, base\));(\s*REX_R1_\w+\(\);)?$' % '|'.join(sorted(mc | ms)))
    counts = collections.Counter()
    sizes = collections.Counter()
    changed = 0
    for path in sorted(glob.glob(os.path.join(a.gen, '*_recomp.*.cpp'))):
        text = open(path, encoding='utf-8').read()
        lines = text.split('\n')
        known = None
        for i, line in enumerate(lines):
            if line.startswith(('loc_', 'DEFINE_REX_FUNC', '}')):
                known = None
                continue
            m = SET_R5.match(line)
            if m:
                known = int(m.group(1))
                continue
            c = call.match(line)
            if c:
                which = 'memcpy' if c.group(3) in mc else 'memset'
                counts[which + ' calls'] += 1
                if known is not None and 1 <= known <= 64:
                    lines[i] = '%sREX_%s_CONST(%d, %s);%s' % (c.group(1), which.upper(), known, c.group(2),
                                                             c.group(4) or '')
                    counts[which] += 1
                    sizes[(which, known)] += 1
                known = None
                continue
            if known is not None and line.strip() and not line.strip().startswith('//') and WRITES_R5.search(line):
                known = None
        counts['already'] += sum(1 for _ in DONE.finditer(text))
        new = '\n'.join(lines)
        if new != text:
            changed += 1
            if not a.check:
                open(path, 'w', encoding='utf-8', newline='\n').write(new)
    pchs = glob.glob(os.path.join(a.gen, '*_pch.h'))
    if len(pchs) != 1:
        sys.exit('ERROR (post-codegen patch): inline_memcalls: no single *_pch.h in %s' % a.gen)
    text = open(pchs[0], encoding='utf-8').read()
    if MACROS not in text and not a.check:
        anchor = '#define REX_LOAD_U8(x)'
        if MARKER in text:
            start = text.index(MARKER)
            text = text[:start] + text[text.index(END, start) + len(END):]
        # After the load / store macros the helpers use (REX_STORE_U64, REX_RAW_ADDR): before the first function
        # declaration block, i.e. at the end of the pch's macro section.
        anchor2 = '#define REX_MEMORY_SIZE'
        if anchor2 not in text:
            sys.exit('ERROR (post-codegen patch): inline_memcalls: no REX_MEMORY_SIZE in %s' % pchs[0])
        text = text.replace(anchor2, MACROS + anchor2, 1)
        open(pchs[0], 'w', encoding='utf-8', newline='\n').write(text)
    top = ', '.join('%s %d x%d' % (w, n, c) for (w, n), c in sizes.most_common(8))
    print('inline_memcalls%s: %d of %d memcpy and %d of %d memset calls have a constant size of 1-64 bytes and are '
          'inline (%d files; %d already); most common: %s' % (
              ' (check only)' if a.check else '', counts['memcpy'], counts['memcpy calls'], counts['memset'],
              counts['memset calls'], changed, counts['already'], top))


if __name__ == '__main__':
    main()
