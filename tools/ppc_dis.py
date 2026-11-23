#!/usr/bin/env python3
"""Prints a disassembly listing of the loaded image (tools/ppc_mini.py), with the .pdata function starts and the
thunks of .xidata marked, for checking an analysis entry by eye.

  python tools/ppc_dis.py 0x82964A00 0x82964AC0            listing of [start, end)
  python tools/ppc_dis.py 0x82964A18 -n 40                 40 instructions from 0x82964A18
  python tools/ppc_dis.py --pdata 0x82964A18               the .pdata entry that covers the address

The image is out/default_image.bin (REXGLUE_DUMP_IMAGE with tools/codegen.ps1); --image picks another one.
"""
import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ppc_mini import Image, decode, text  # noqa: E402

BASE = 0x82000000


def pdata_entries(img):
    """[(begin, length in bytes)] from the PE exception directory (RUNTIME_FUNCTION: begin, packed length)."""
    data = img.data
    pe = struct.unpack_from('<I', data, 0x3C)[0]
    optional = pe + 24
    magic = struct.unpack_from('<H', data, optional)[0]
    dirs = optional + (96 if magic == 0x10B else 112)
    rva, size = struct.unpack_from('<II', data, dirs + 3 * 8)   # IMAGE_DIRECTORY_ENTRY_EXCEPTION
    out = []
    for off in range(BASE + rva, BASE + rva + size, 8):
        begin = img.word(off)
        packed = img.word(off + 4)
        length = ((packed >> 8) & 0x3FFFFF) * 4
        if begin:
            out.append((begin, length))
    return out


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('start', type=lambda s: int(s, 0))
    ap.add_argument('end', nargs='?', type=lambda s: int(s, 0))
    ap.add_argument('-n', type=int, default=32, help='instructions to print without an end address')
    ap.add_argument('--image', default=os.path.join(root, 'out', 'default_image.bin'))
    ap.add_argument('--pdata', action='store_true', help='print the .pdata entry covering start and exit')
    args = ap.parse_args()

    img = Image(args.image, BASE)
    pdata = pdata_entries(img)
    starts = {b: n for b, n in pdata}
    if args.pdata:
        hits = [(b, n) for b, n in pdata if b <= args.start < b + n]
        for b, n in hits:
            print('.pdata: 0x%08X-0x%08X (%d bytes)' % (b, b + n, n))
        if not hits:
            before = max((b for b, _ in pdata if b <= args.start), default=None)
            print('no .pdata entry covers 0x%08X; nearest start before it: %s'
                  % (args.start, '0x%08X' % before if before else '-'))
        return
    end = args.end if args.end else args.start + 4 * args.n
    for addr in range(args.start & ~3, end, 4):
        w = img.word(addr)
        mark = ''
        if addr in starts:
            mark = '   <- .pdata start (%d bytes)' % starts[addr]
        ins = decode(w, addr)
        print('%08X  %08X  %-40s%s' % (addr, w, text(ins), mark))


if __name__ == '__main__':
    main()
