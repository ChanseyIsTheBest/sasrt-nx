#!/usr/bin/env python3
"""Counts the texture-fetch instructions of dumped shader containers by their own filter fields.

A Xenos tfetch can override the fetch constant's filters (mag/min/mip: 0 point, 1 linear, 2 base map, 3 = use the
fetch constant), its anisotropy, LOD bias and sample location. This lists how often each override occurs, and with
--list the shaders (container files) whose fetches override mag/min to point or linear.

  python tools/fetch_filters.py out/pc/shaders [more folders] [--list]
"""
import collections
import glob
import os
import struct
import sys

FILTER = {0: 'point', 1: 'linear', 2: 'basemap', 3: 'const'}
EXEC_OPCODES = {1, 2, 3, 4, 5, 6, 13, 14}


def microcode(path):
    b = open(path, 'rb').read()
    if len(b) < 12:
        return None
    virtual = struct.unpack_from('>I', b, 4)[0]
    shader_offset = struct.unpack_from('>I', b, 0x18)[0]
    if shader_offset + 8 > len(b):
        return None
    # The shader's code starts at its own physical offset (definitions can come first), `size` bytes long.
    physical_offset, size = struct.unpack_from('>II', b, shader_offset)
    code = b[virtual + physical_offset:virtual + physical_offset + size]
    return [struct.unpack_from('>I', code, i)[0] for i in range(0, len(code) - 3, 4)]


def fetches(words):
    """Yields (instruction index, dword0, dword1, dword2) of every texture fetch reached by an exec."""
    n = len(words) // 3
    seen = set()
    end = n
    cf = 0
    while cf * 3 + 2 < len(words) and cf < end:
        d0, d1, d2 = words[cf * 3:cf * 3 + 3]
        for c0, c1 in ((d0, d1 & 0xFFFF), ((d1 >> 16) | ((d2 << 16) & 0xFFFFFFFF), d2 >> 16)):
            op = (c1 >> 12) & 0xF
            if op in EXEC_OPCODES:
                address, count, seq = c0 & 0xFFF, (c0 >> 12) & 7, (c0 >> 16) & 0xFFF
                end = min(end, address) if address else end
                for i in range(count):
                    if (seq >> (i * 2)) & 1 and address + i < n and address + i not in seen:
                        seen.add(address + i)
                        w = words[(address + i) * 3:(address + i) * 3 + 3]
                        if (w[0] & 0x1F) == 1:  # texture fetch
                            yield address + i, w[0], w[1], w[2]
        cf += 1


def main():
    folders = [a for a in sys.argv[1:] if not a.startswith('--')]
    listing = '--list' in sys.argv
    totals = collections.Counter()
    per_shader = collections.defaultdict(collections.Counter)
    shaders_with = collections.Counter()
    for folder in folders:
        for path in sorted(glob.glob(os.path.join(folder, '*.bin'))):
            words = microcode(path)
            if not words:
                continue
            kinds = set()
            for _, d0, d1, d2 in fetches(words):
                mag, mnf, mip = (d1 >> 12) & 3, (d1 >> 14) & 3, (d1 >> 16) & 3
                aniso = (d1 >> 18) & 7
                bias = ((d2 >> 2) & 0x7F)
                bias = bias - 128 if bias & 0x40 else bias
                loc = (d2 >> 1) & 1
                key = f'mag {FILTER[mag]} min {FILTER[mnf]} mip {FILTER[mip]}'
                totals[key] += 1
                totals[f'aniso field {aniso}'] += 1
                totals[f'lod bias {bias}'] += 1
                totals[f'sample location {"center" if loc else "centroid"}'] += 1
                if mag != 3 or mnf != 3:
                    kinds.add(key)
                    per_shader[os.path.basename(path)][key] += 1
            for k in kinds:
                shaders_with[k] += 1
    for k, v in sorted(totals.items()):
        print(f'{v:7d}  {k}')
    print('shaders with an explicit mag/min filter:')
    for k, v in sorted(shaders_with.items()):
        print(f'{v:7d}  {k}')
    if listing:
        for name, c in sorted(per_shader.items()):
            print(name, dict(c))


if __name__ == '__main__':
    main()
