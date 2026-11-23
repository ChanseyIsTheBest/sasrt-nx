"""The import record addresses of a XEX (optional header 0x000103FF) and the folded loads of the generated tree that
touch them (futari-nx's finding: tools/ro_constants.py folds them, though the loader writes them at run time)."""
import glob
import os
import re
import struct
import sys

XEX = sys.argv[1]
GEN = sys.argv[2]
d = open(XEX, 'rb').read(1 << 20)
assert d[:4] == b'XEX2', d[:4]
count, = struct.unpack_from('>I', d, 20)
records = []
libraries = []
for i in range(count):
    key, value = struct.unpack_from('>II', d, 24 + 8 * i)
    if key != 0x000103FF:
        continue
    size, strings_size, n_libraries = struct.unpack_from('>III', d, value)
    strings = d[value + 12:value + 12 + strings_size].split(b'\0')
    at = value + 12 + strings_size
    for _ in range(n_libraries):
        lib_size, = struct.unpack_from('>I', d, at)
        name_index, n = struct.unpack_from('>HH', d, at + 4 + 20 + 12)
        addresses = struct.unpack_from('>%dI' % n, d, at + 4 + 20 + 12 + 4)
        libraries.append((strings[name_index].decode() if name_index < len(strings) else '?', n))
        records.extend(addresses)
        at += lib_size
print('import libraries:', ', '.join('%s (%d records)' % l for l in libraries))
print('record words: %d, from %08X to %08X' % (len(records), min(records), max(records)))
words = set(records)
pattern = re.compile(r'REX_RO_(U8|U16|U32|U64|F32|F64|V128)\((0x[0-9A-Fa-f]+)')
hits = {}
total = 0
for path in glob.glob(os.path.join(GEN, '*_recomp.*.cpp')):
    for m in pattern.finditer(open(path, encoding='utf-8', errors='replace').read()):
        total += 1
        address = int(m.group(2), 16)
        width = {'U8': 1, 'U16': 2, 'U32': 4, 'U64': 8, 'F32': 4, 'F64': 8, 'V128': 16}[m.group(1)]
        for a in range(address & ~3, address + width, 4):
            if a in words:
                hits.setdefault(a, []).append((os.path.basename(path), m.group(0)))
                break
print('folded loads in the tree: %d; touching an import record word: %d (at %d distinct records)' %
      (total, sum(len(v) for v in hits.values()), len(hits)))
for a in sorted(hits)[:12]:
    print('  %08X: %d loads, e.g. %s in %s' % (a, len(hits[a]), hits[a][0][1], hits[a][0][0]))
