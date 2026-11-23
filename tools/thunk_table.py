#!/usr/bin/env python3
"""Finds the jump thunks of an Xbox 360 image and writes them as code generator [functions] entries.

Sonic & All-Stars Racing Transformed was linked with a thunk table (like the MSVC linker's incremental-linking
table): its .xidata section holds 62,827 thunks of 16 bytes,

    lis   r11, target@ha
    addi  r11, r11, target@l
    mtctr r11
    bctr

followed by the XEX import thunks. Most calls in .text go through a thunk (bl/b to the thunk, which jumps on to the
real function), and the vtables and callback tables hold thunk addresses too. Automatic discovery only makes
functions of bl targets, and GapFill does not split the table at bctr, so a thunk reached only through a b (tail call)
or a pointer in data was not a function: 4,020 "target not in any function" errors at the first codegen
(sasrt-nx, 2026-10-05), and a virtual call through such a thunk would stop the game with "Call to invalid or
unregistered function". Every thunk is therefore declared, with its target as the evidence.

The thunk targets are function entries too, and the generator cannot see them: a thunk's bctr goes to an address
built with lis/addi, which discovery does not follow. Targets with a .pdata entry are registered anyway; the 34,616
without one (leaf functions: MSVC writes no unwind data for a function without a frame) were registered only when
GapFill happened to start a segment there, and three were not (sub_82964A08 and sub_82964B40, leaves right after
another function whose last block ends in a b, and 0x82C8F378, an entry of the CRT's copy routines; first codegen
with the thunks, 2026-10-05). So every target in .text or PSFD00 without a .pdata entry is declared as well, without
a size (discovery finds its end), with the thunk that points at it as the evidence. Targets in the XEX import thunks
are left to the generator, which registers those as imports.

The entries of the register save/restore helpers (__savegprlr_N, __restgprlr_N, __savefpr_N, __restfpr_N,
__savevmx_N, __restvmx_N) are left to the generator too, although 82 of them are thunk targets: it finds the
helpers by their first instruction and names every entry, and the code generator elides the calls to them by that
name when registers are C++ locals (non_volatile_as_local). Declared here they became CONFIG functions, which
replace the generator's HELPER ones and are named sub_X: 30 GPR, 28 FPR and 24 VMX entries lost their names (found
2026-10-07 while enabling non_volatile_as_local; the 27,730 GPR helper calls of the game are all direct bl/b, none
goes through those thunks).

Usage:
    python tools/thunk_table.py [--image out/default_image.bin] [--out app/thunks.toml]

The image is the loaded default.xex (REXGLUE_DUMP_IMAGE=out/default_image.bin with tools/codegen.ps1). The section
table is read from the PE header inside the image. Thunks outside .xidata (any 16-byte aligned run of the same four
instructions in another executable section) are listed but not written: inside .text the same shape can be the last
instructions of a function that tail-calls a constant address.
"""
import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ppc_mini import Image  # noqa: E402
import ppc_dis  # noqa: E402  (.pdata reader)

BASE = 0x82000000


def sections(image):
    pe = struct.unpack_from('<I', image, 0x3C)[0]
    count = struct.unpack_from('<H', image, pe + 6)[0]
    optional = struct.unpack_from('<H', image, pe + 20)[0]
    table = pe + 24 + optional
    out = []
    for i in range(count):
        entry = table + i * 40
        name = image[entry:entry + 8].split(b'\0')[0].decode('ascii', 'replace')
        vsize, vaddr = struct.unpack_from('<II', image, entry + 8)
        flags = struct.unpack_from('<I', image, entry + 36)[0]
        out.append((name, BASE + vaddr, vsize, bool(flags & 0x20000000)))
    return out


def thunk_at(image, addr):
    """Target of the thunk at addr, or None."""
    off = addr - BASE
    w0, w1, w2, w3 = struct.unpack_from('>IIII', image, off)
    if (w0 >> 26) != 15 or (w0 >> 16) & 0x1F != 0:          # lis rD = addis rD, 0, imm
        return None
    reg = (w0 >> 21) & 0x1F
    if (w1 >> 26) != 14 or (w1 >> 21) & 0x1F != reg or (w1 >> 16) & 0x1F != reg:   # addi rD, rD, imm
        return None
    if w2 != (0x7C0903A6 | (reg << 21)):                     # mtctr rD (mtspr 9, rD)
        return None
    if w3 != 0x4E800420:                                     # bctr
        return None
    lo = w1 & 0xFFFF
    lo = lo - 0x10000 if lo & 0x8000 else lo
    return ((w0 & 0xFFFF) << 16) + lo & 0xFFFFFFFF


def helper_ranges(image, code):
    """Address ranges of the save/restore helper entries, found as the generator finds them
    (sdk/src/codegen/phase_register.cpp, detectSaveRestoreHelpers: the first match of each pattern)."""
    single = {0xE9C1FF68: (4, 18, 'restgprlr'), 0xF9C1FF68: (4, 18, 'savegprlr'),
              0xC9CCFF70: (4, 18, 'restfpr'), 0xD9CCFF70: (4, 18, 'savefpr')}
    pair = {(0x3960FEE0, 0x7DCB60CE): (8, 18, 'restvmx_14'), (0x3960FEE0, 0x7DCB61CE): (8, 18, 'savevmx_14'),
            (0x3960FC00, 0x100B60CB): (8, 64, 'restvmx_64'), (0x3960FC00, 0x100B61CB): (8, 64, 'savevmx_64')}
    found = {}
    for _, start, size in code:
        words = struct.unpack_from('>%dI' % (size // 4), image, start - BASE)
        for i, w in enumerate(words):
            addr = start + 4 * i
            if w in single and single[w][2] not in found:
                found[single[w][2]] = (addr, single[w][0] * single[w][1])
            if i + 1 < len(words):
                key = (w, words[i + 1])
                if key in pair and pair[key][2] not in found:
                    found[pair[key][2]] = (addr, pair[key][0] * pair[key][1])
    return found


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--image', default=os.path.join(root, 'out', 'default_image.bin'))
    ap.add_argument('--out', default=os.path.join(root, 'app', 'thunks.toml'))
    args = ap.parse_args()

    image = open(args.image, 'rb').read()
    secs = sections(image)
    code = [(n, a, s) for n, a, s, x in secs if x]

    def in_code(addr):
        return any(a <= addr < a + s for _, a, s in code)

    found = {}
    elsewhere = []
    bad_target = []
    for name, start, size, _ in secs:
        if not any(name == n for n, _, _ in code):
            continue
        for addr in range((start + 15) & ~15, start + size - 15, 16):
            target = thunk_at(image, addr)
            if target is None:
                continue
            if not in_code(target):
                bad_target.append((addr, target))
                continue
            if name == '.xidata':
                found[addr] = target
            else:
                elsewhere.append((name, addr, target))

    if not found:
        sys.exit('no thunk found in .xidata')
    lo, hi = min(found), max(found) + 16
    targets = len(set(found.values()))

    pdata = {b for b, _ in ppc_dis.pdata_entries(Image(args.image, BASE))}
    entry_sections = [(a, s) for n, a, s in code if n in ('.text', 'PSFD00')]
    first_thunk = {}
    for addr in sorted(found):
        first_thunk.setdefault(found[addr], addr)
    helpers = helper_ranges(image, code)
    leaves = sorted(t for t in first_thunk
                    if t not in pdata and any(a <= t < a + s for a, s in entry_sections) and
                    not any(a <= t < a + n for a, n in helpers.values()))
    lines = [
        '# Generated by tools/thunk_table.py from the loaded default.xex: do not edit by hand.',
        '#',
        '# The jump thunks of the .xidata section (lis r11 / addi r11 / mtctr r11 / bctr, 16 bytes each), every one',
        '# declared as a function: most calls and many vtable entries go through them, and discovery alone misses the',
        '# ones reached only by a tail call or a pointer (see the header of tools/thunk_table.py). Each line gives the',
        '# thunk\'s target, which is its evidence.',
        '#',
        '# %d thunks in 0x%08X-0x%08X, %d distinct targets.' % (len(found), lo, hi, targets),
        '',
        '[functions]',
    ]
    for addr in sorted(found):
        lines.append('"0x%08X" = { size = 16 }  # -> 0x%08X' % (addr, found[addr]))
    lines += [
        '',
        '# Thunk targets without a .pdata entry (%d): function entries the generator cannot see behind the thunks\''
        % len(leaves),
        '# bctr. No size: discovery finds each end. The comment names the (first) thunk pointing at it.',
    ]
    for target in leaves:
        lines.append('"0x%08X" = { }  # thunk 0x%08X' % (target, first_thunk[target]))
    with open(args.out, 'w', newline='\n') as f:
        f.write('\n'.join(lines) + '\n')
    print('%d thunks in .xidata 0x%08X-0x%08X (%d distinct targets, %d of them without .pdata) -> %s'
          % (len(found), lo, hi, targets, len(leaves), args.out))
    print('save/restore helpers left to the generator: ' +
          ', '.join('%s at 0x%08X' % (k, a) for k, (a, _) in sorted(helpers.items())))
    if bad_target:
        print('%d thunk-shaped blocks with a target outside the code, not written:' % len(bad_target))
        for addr, target in bad_target[:20]:
            print('  0x%08X -> 0x%08X' % (addr, target))
    if elsewhere:
        print('%d thunk-shaped blocks outside .xidata, not written (check by hand):' % len(elsewhere))
        for name, addr, target in elsewhere[:40]:
            print('  %s 0x%08X -> 0x%08X' % (name, addr, target))


if __name__ == '__main__':
    main()
