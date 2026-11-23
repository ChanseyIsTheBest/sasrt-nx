"""sasrt-nx (2026-11-22, the web installer's shader step; the user: "compile shaders in the browser like Blur"): where
each shader container of out/renut_shader_dump lies in the game's own files, for sasrt-nx-installer's release manifest.

The game's shaders are Direct3D shader objects built into its resource packages (Data/*.M00): each container's header
(the "virtual" part, words [0] flags 10 2A 11 xx, [1] header size, [2] microcode size) sits in a package's CPU section
and its microcode (the "physical" part) whole and contiguous in the same package's GPU section, later in the file. A
dump (vs_/ps_<XXH3 of the container>.bin) is the two joined, as NoteShaderObject reads a loaded object. This finds both
parts by their bytes (read only) and writes, per container: the file, the header's offset and length, the microcode's
offset and length, and the SHA-256 of the joined bytes (the page reads the two ranges, joins them and checks it). No
shader data goes into the output: only where the player's own files hold it.

    python tools/shader_records.py --game assets/game_root --dump out/renut_shader_dump --out out/shader_records.json         --image out/default_image.bin
"""
import argparse
import hashlib
import json
import mmap
import os
import struct
import sys
import time
from collections import Counter, defaultdict

FILES = ['Data/GameAssets.M00', 'Data/Frontend.M00', 'Data/GameData.M00']
IMAGE = '<default.xex image>'


def header_index(maps):
    """Every container header in the files, by the SHA-256 of its header bytes: [(file, offset)]."""
    index = defaultdict(list)
    for fn, m in maps.items():
        n = len(m)
        pos = m.find(b'\x10\x2a\x11')
        while pos != -1:
            if pos % 4 == 0 and pos + 12 <= n:
                hs, ms = struct.unpack_from('>II', m, pos + 4)
                if 12 <= hs < 0x10000 and 0 < ms < 0x40000 and hs % 4 == 0 and ms % 4 == 0 and pos + hs <= n:
                    index[hashlib.sha256(m[pos:pos + hs]).digest()].append((fn, pos))
            pos = m.find(b'\x10\x2a\x11', pos + 1)
    return index


def microcode_index(maps, codes, log=print):
    """Where each microcode is, in one numpy pass a file: every 4-byte-aligned 8-byte word of the files is looked up
    among one probe word a microcode (its rarest word in a sample of the largest file, so a run of zeros or a common
    instruction does not make millions of hits), through a 24-bit table first; each hit is checked whole.
    codes: {key: bytes}. Returns {(key, file): offset}, the first place in each file."""
    import numpy as np
    cands = {}
    for key, code in codes.items():
        last = min(len(code) - 8, 1024)
        if last >= 0:
            cands[key] = [(o, int.from_bytes(code[o:o + 8], 'little')) for o in range(0, last + 1, 4)]
    allw = np.unique(np.array([w for cs in cands.values() for _, w in cs], dtype=np.uint64))
    big = max(maps, key=lambda fn: len(maps[fn]))
    m = maps[big]
    counts = np.zeros(len(allw), dtype=np.int64)
    span = 16 << 20
    for i in range(16):  # a 256 MB sample, spread over the file
        base = (len(m) - span) * i // 15 // 4 * 4
        buf = np.frombuffer(m[base:base + span + 8], dtype=np.uint8)
        words = np.ndarray(((len(buf) - 8) // 4,), dtype=np.uint64, buffer=buf.data, strides=(4,))
        idx = np.searchsorted(allw, words)
        np.clip(idx, 0, len(allw) - 1, out=idx)
        ok = allw[idx] == words
        counts += np.bincount(idx[ok], minlength=len(allw))
    count_of = dict(zip(allw.tolist(), counts.tolist()))  # Python ints: a word over 2**63 would make numpy go by objects
    want = defaultdict(list)
    for key, cs in cands.items():
        o, w = min(cs, key=lambda c: (count_of[c[1]], c[0]))
        want[w].append((key, o))
    targets = np.array(sorted(want), dtype=np.uint64)
    table = np.zeros(1 << 24, dtype=bool)
    table[(targets & np.uint64(0xFFFFFF)).astype(np.int64)] = True
    log(f'microcode index: {len(cands)} probes ({len(targets)} words) from a {big} sample', flush=True)
    found = {}
    chunk = 64 << 20
    for fn, m in maps.items():
        n = len(m)
        hits_total = 0
        for base in range(0, n, chunk):
            end = min(n, base + chunk + 8)
            buf = np.frombuffer(m[base:end], dtype=np.uint8)
            count = min((len(buf) - 8) // 4, chunk // 4)
            if count <= 0:
                continue
            words = np.ndarray((count,), dtype=np.uint64, buffer=buf.data, strides=(4,))
            pre = np.nonzero(table[(words & np.uint64(0xFFFFFF)).astype(np.int64)])[0]
            hits = pre[np.isin(words[pre], targets)]
            hits_total += len(hits)
            for h in hits:
                p = base + int(h) * 4
                for key, o in want[int(words[h])]:
                    start = p - o
                    if start < 0 or (key, fn) in found:
                        continue
                    code = codes[key]
                    if m[start:start + len(code)] == code:
                        found[(key, fn)] = start
        log(f'  {fn}: {hits_total} probe hits, {sum(1 for k in found if k[1] == fn)} found', flush=True)
    return found


def patched_index(maps, codes, log=print):
    """2026-11-22: a vertex shader the game's D3D has bound to a vertex declaration is patched in memory: its header's
    flag byte gets 0x40 and its vertex fetches (the first instructions) their formats and strides, so the dump is not
    in the files byte for byte. The original microcode is found by four rare 8-byte words of the code's second half
    (left alone), voting for a start; the best start of the six most voted is kept when at most half of its
    dwords differ. codes: {key: bytes}. Returns {key: (file, offset)}."""
    import numpy as np
    cands = {k: [(o, int.from_bytes(c[o:o + 8], 'little')) for o in range(len(c) // 2 // 4 * 4, len(c) - 7, 4)]
             for k, c in codes.items()}
    cands = {k: cs for k, cs in cands.items() if cs}
    if not cands:
        return {}
    allw = np.unique(np.array([w for cs in cands.values() for _, w in cs], dtype=np.uint64))
    m = maps[max(maps, key=lambda fn: len(maps[fn]))]
    counts = np.zeros(len(allw), dtype=np.int64)
    span = 16 << 20
    for i in range(16):
        base = max(0, (len(m) - span) * i // 15 // 4 * 4)
        buf = np.frombuffer(m[base:base + span + 8], dtype=np.uint8)
        words = np.ndarray(((len(buf) - 8) // 4,), dtype=np.uint64, buffer=buf.data, strides=(4,))
        idx = np.searchsorted(allw, words)
        np.clip(idx, 0, len(allw) - 1, out=idx)
        counts += np.bincount(idx[allw[idx] == words], minlength=len(allw))
    count_of = dict(zip(allw.tolist(), counts.tolist()))
    want = defaultdict(list)
    for key, cs in cands.items():
        for o, w in sorted(cs, key=lambda c: (count_of[c[1]], -c[0]))[:4]:
            want[w].append((key, o))
    targets = np.array(sorted(want), dtype=np.uint64)
    table = np.zeros(1 << 24, dtype=bool)
    table[(targets & np.uint64(0xFFFFFF)).astype(np.int64)] = True
    votes = defaultdict(Counter)
    chunk = 64 << 20
    for fn, m in maps.items():
        n = len(m)
        for base in range(0, n, chunk):
            buf = np.frombuffer(m[base:min(n, base + chunk + 8)], dtype=np.uint8)
            count = min((len(buf) - 8) // 4, chunk // 4)
            if count <= 0:
                continue
            words = np.ndarray((count,), dtype=np.uint64, buffer=buf.data, strides=(4,))
            pre = np.nonzero(table[(words & np.uint64(0xFFFFFF)).astype(np.int64)])[0]
            hits = pre[np.isin(words[pre], targets)]
            for h, w in zip(hits.tolist(), words[hits].tolist()):
                p = base + h * 4
                for key, o in want[w]:
                    if p >= o:
                        votes[key][(fn, p - o)] += 1
    found = {}
    for key, code in codes.items():
        best = None
        for (fn, start), _ in votes[key].most_common(6):
            other = maps[fn][start:start + len(code)]
            diff = sum(1 for i in range(0, len(code), 4) if code[i:i + 4] != other[i:i + 4])
            if best is None or diff < best[2]:
                best = (fn, start, diff)
        if best is not None and best[2] <= len(code) // 8:  # at most half its dwords (the fetches of a short shader)
            found[key] = best[:2]
    log(f'patched index: {len(found)} of {len(codes)} found', flush=True)
    return found


def find_microcode(m, code, start):
    """The microcode's offset in m: first after 'start' (its package's GPU section follows the CPU one), else anywhere."""
    probe = code[:64]
    for lo in (start, 0):
        at = m.find(probe, lo)
        while at != -1:
            if m[at:at + len(code)] == code:
                return at
            at = m.find(probe, at + 1)
    return -1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--game', required=True)
    ap.add_argument('--dump', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--only', default=None, help='a file of shader names (one a line): only those')
    ap.add_argument('--image', default=None, help="default.xex's decrypted image (out/default_image.bin): searched too")
    ap.add_argument('--slow', action='store_true', help='search byte by byte for a microcode the index misses')
    args = ap.parse_args()
    if args.only:
        args.only = {ln.split('#')[0].strip().lower() for ln in open(args.only, encoding='utf-8')} - {''}
    handles, maps = [], {}
    for fn in FILES:
        p = os.path.join(args.game, fn)
        if os.path.exists(p) and os.path.getsize(p):
            f = open(p, 'rb')
            handles.append(f)
            maps[fn] = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    if args.image:  # 2026-11-22: a third of the dump is the engine's own shaders, split the same way in default.xex
        maps[IMAGE] = open(args.image, 'rb').read()
    t0 = time.time()
    index = header_index(maps)
    print(f'{sum(len(v) for v in index.values())} headers in the files, {len(index)} distinct ({time.time() - t0:.0f} s)',
          flush=True)
    records, missing = [], []
    counts = Counter()
    names = sorted(n for n in os.listdir(args.dump) if n.endswith('.bin') and
                   (args.only is None or n[:-4].lower() in args.only))
    codes = {}
    for name in names:
        d = open(os.path.join(args.dump, name), 'rb').read()
        _, hs, ms = struct.unpack_from('>III', d, 0)
        if hs + ms == len(d):
            codes[name] = d[hs:]
    micro_at = microcode_index(maps, codes)
    print(f'microcode index: {len({k for k, _ in micro_at})} of {len(codes)} found on 4-byte boundaries '
          f'({time.time() - t0:.0f} s)', flush=True)
    for k, name in enumerate(names):
        d = open(os.path.join(args.dump, name), 'rb').read()
        flags, hs, ms = struct.unpack_from('>III', d, 0)
        if hs + ms != len(d):
            counts['sizes'] += 1
            missing.append({'name': name, 'why': f'header {hs} + microcode {ms} != {len(d)} bytes'})
            continue
        hits = index.get(hashlib.sha256(d[:hs]).digest())
        if not hits:
            counts['header'] += 1
            missing.append({'name': name, 'why': 'header not in the files', 'flags': flags & 0xFF})
            continue
        found = None
        for fn, pos in hits:  # the index first, then the slow search (a block off a 32-byte boundary)
            if (name, fn) in micro_at:
                found = (fn, pos, micro_at[(name, fn)])
                break
        for fn, pos in ([] if found or not args.slow else hits):
            at = find_microcode(maps[fn], d[hs:], pos + hs)
            if at != -1:
                found = (fn, pos, at)
                break
        if not found:
            counts['microcode'] += 1
            missing.append({'name': name, 'why': 'microcode not in the header\'s file', 'flags': flags & 0xFF})
            continue
        fn, pos, at = found
        records.append({'name': name[:-4], 'file': fn, 'at': pos, 'length': hs, 'phys_at': at, 'phys_length': ms,
                        'sha256': hashlib.sha256(d).hexdigest()})
        counts['found'] += 1
        if k % 200 == 0:
            print(f'{k}/{len(names)} {dict(counts)} ({time.time() - t0:.0f} s)', flush=True)
    # 2026-11-22: the patched ones (patched_index): the header with the flag byte's 0x40 cleared, the original microcode
    # by its untouched half, and the dwords the game changed as edits ([offset in the container, the 4 bytes in hex])
    # the page writes over the two parts before it checks the SHA-256
    patched = {}
    for x in missing:
        if x['why'].startswith('header ') and 'not in the files' not in x['why']:
            continue
        d = open(os.path.join(args.dump, x['name']), 'rb').read()
        patched[x['name']] = d
    at = patched_index(maps, {n: d[struct.unpack_from('>I', d, 4)[0]:] for n, d in patched.items()})
    still = []
    for x in missing:
        name = x['name']
        if name not in at:
            still.append(x)
            continue
        d = patched[name]
        hs, ms = struct.unpack_from('>II', d, 4)
        fn, phys = at[name]
        h = bytearray(d[:hs])
        h[3] &= ~0x40
        pos = next((p for f, p in index.get(hashlib.sha256(bytes(h)).digest(), []) if f == fn), None)
        if pos is None:
            pos = next((p for f, p in index.get(hashlib.sha256(d[:hs]).digest(), []) if f == fn), None)
        if pos is None:
            x['why'] = "patched: no header in the microcode's file"
            still.append(x)
            continue
        orig = bytes(maps[fn][pos:pos + hs]) + bytes(maps[fn][phys:phys + ms])
        edits = [[i, d[i:i + 4].hex()] for i in range(0, len(d), 4) if d[i:i + 4] != orig[i:i + 4]]
        records.append({'name': name[:-4], 'file': fn, 'at': pos, 'length': hs, 'phys_at': phys, 'phys_length': ms,
                        'sha256': hashlib.sha256(d).hexdigest(), 'edits': edits})
        counts['patched'] += 1
    for x in missing:
        if x not in still:
            reason = 'header' if x['why'].startswith('header') else 'microcode'
            counts[reason] -= 1
    missing = still
    counts = Counter({k: v for k, v in counts.items() if v})
    # sasrt-nx-installer's tools/make_release.py --records takes [{ file, codec: 'split', containers: [...] }], one record
    # a file (lib/sources.js reads each container's two parts by their offsets); 'found'/'missing' for the release notes
    by_file = defaultdict(list)
    for r in records:
        by_file[r['file']].append({k: r[k] for k in ('name', 'at', 'length', 'phys_at', 'phys_length', 'sha256', 'edits')
                                   if k in r})
    out = []
    for fn, cs in sorted(by_file.items()):
        if fn == IMAGE:  # read by the page from default.xex's image (lib/xex.js), as it decrypts it
            out.append({'file': 'default.xex', 'source': 'image', 'codec': 'split', 'containers': cs})
        else:
            out.append({'file': fn, 'codec': 'split', 'containers': cs})
    json.dump(out, open(args.out, 'w'), indent=1)
    json.dump({'found': len(records), 'missing': missing},
              open(os.path.splitext(args.out)[0] + '_missing.json', 'w'), indent=1)
    print(f'{len(names)} containers: {dict(counts)}; {args.out} ({time.time() - t0:.0f} s)')
    by = Counter((x['why'], x.get('flags')) for x in missing)
    for (why, fl), c in by.most_common():
        print(f'  missing: {c} {why} (flag byte {fl})')


if __name__ == '__main__':
    sys.exit(main())
