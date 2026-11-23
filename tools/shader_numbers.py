#!/usr/bin/env python3
"""Maps the native renderer's shader numbers (the "VS n12 / PS n105" of its logs and frame traces) to container
files: the number is the entry's position in the package, and the package index (sasrt_shaders.mesp.idx) holds each
entry's original container, which is matched byte for byte against the containers the package was built from.

  python tools/shader_numbers.py [--index out/pc/sasrt_shaders.mesp.idx] [--containers out/shaders/in_ok] [n ...]

Without numbers it prints the whole table. The HLSL of a container is out/shaders/hlsl/<name>.hlsl.
"""
import argparse
import glob
import hashlib
import os
import struct

HEADER, ENTRY = 56, 40


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('numbers', nargs='*', type=int)
    ap.add_argument('--index', default='out/pc/sasrt_shaders.mesp.idx')
    ap.add_argument('--containers', default='out/shaders/in_ok')
    a = ap.parse_args()
    data = open(a.index, 'rb').read()
    if data[:8] != b'MESSIDX\0':
        raise SystemExit('not a shader index')
    count = struct.unpack_from('<I', data, 12)[0]
    by_content = {}
    for path in glob.glob(os.path.join(a.containers, '*.bin')):
        by_content[hashlib.sha1(open(path, 'rb').read()).hexdigest()] = os.path.basename(path)[:-4]
    originals = HEADER + count * ENTRY
    consumed = 0
    wanted = set(a.numbers)
    for i in range(count):
        size = struct.unpack_from('<I', data, HEADER + i * ENTRY)[0]
        original = data[originals + consumed:originals + consumed + size]
        consumed += size
        if wanted and i not in wanted:
            continue
        name = by_content.get(hashlib.sha1(original).hexdigest(), '?')
        print(f'n{i}: {name}')


if __name__ == '__main__':
    main()
