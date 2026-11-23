#!/usr/bin/env python3
"""sasrt-nx (2026-11-08): three-way merge of the ultimate base (D:/renut-ultimate/base, rr6-nx's session's shared
renderer; read-only) into this port's Renut sources, as rr6-nx moved onto it. The common ancestor is banjo-nx 894d3256
(out/renut_sources/banjo: renderer and plume; out/renut_sources/banjo_xr: the translator, git archive of that commit),
ours is sa2-nx's hybrid tree merged with banjo-nx (out/renut_sources/sa2_banjo, what tools/renut_from_sa2.py reads)
and this port's plume and translator (app/thirdparty), theirs the base's.

Writes out/renut_sources/sa2_ult (the renderer: sa2_banjo with gpu/, display_sync.*, perf/, renut_logging.h and
globals.h merged), out/renut_sources/ult_plume and out/renut_sources/ult_xr, and out/renut_sources/ult_merge.txt (what
happened to each file). Per file: the same on both sides, or changed on one side only, takes that side; changed on both
goes through git merge-file (diff3 markers where it conflicts). The per-XDK files (the device layout and hooks: d3d/hooks,
d3d.h, d3d_native.h, d3d_native_state.cpp, banjo_shared_hooks.h) are ours whatever the base did: the base's are
Katamari's XDK 5632; its fixes in them are carried by hand.
    python tools/ult_merge.py
"""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'out', 'renut_sources')
BASE = 'D:/renut-ultimate/base'
RE = 'app/src/renut_engine'
OURS_KEEP = ('gpu/d3d/hooks/', 'gpu/d3d/d3d.h', 'gpu/d3d/d3d_native.h', 'gpu/d3d/d3d_native_state.cpp',
             'gpu/banjo_shared_hooks.h')

# (name, ancestor root, ours root, theirs root, output root, sub-paths to merge or None for everything)
SETS = [
    ('renderer', os.path.join(SRC, 'banjo', RE), os.path.join(SRC, 'sa2_banjo', RE), os.path.join(BASE, RE),
     os.path.join(SRC, 'sa2_ult', RE), ['gpu', 'display_sync.cpp', 'display_sync.h', 'perf', 'renut_logging.h',
                                        'globals.h']),
    ('plume', os.path.join(SRC, 'banjo', 'app/thirdparty/plume'), os.path.join(ROOT, 'app/thirdparty/plume'),
     os.path.join(BASE, 'app/thirdparty/plume'), os.path.join(SRC, 'ult_plume'), None),
    ('translator', os.path.join(SRC, 'banjo_xr', 'app/thirdparty/reblue-XenosRecomp'),
     os.path.join(ROOT, 'app/thirdparty/reblue-XenosRecomp'), os.path.join(BASE, 'app/thirdparty/reblue-XenosRecomp'),
     os.path.join(SRC, 'ult_xr'), None),
]
SKIP_DIRS = {'.git', '__pycache__'}  # 2026-11-08: not 'build' / 'out' (zstd's build/cmake went missing)
# --generated: ours is this port's GENERATED renderer (app/src/renut_engine/gpu, sa2_banjo with every EDIT, the renames and
# the address maps applied), the result goes to out/renut_sources/sasrt_ult/gpu and becomes app/src/renut_engine/gpu: the
# generator (tools/renut_from_sa2.py) is retired for the merged tree (2026-11-08).
if '--generated' in sys.argv:
    SETS = [('renderer', os.path.join(SRC, 'banjo', RE), os.path.join(ROOT, 'app/src/renut_engine'),
             os.path.join(BASE, RE), os.path.join(SRC, 'sasrt_ult'), ['gpu'])] + SETS[1:]


def files(root, subs):
    out = set()
    tops = subs if subs is not None else ['']
    for sub in tops:
        p = os.path.join(root, sub)
        if os.path.isfile(p):
            out.add(sub.replace('\\', '/'))
            continue
        for d, ds, fs in os.walk(p):
            ds[:] = [x for x in ds if x not in SKIP_DIRS]
            for f in fs:
                out.add(os.path.relpath(os.path.join(d, f), root).replace('\\', '/'))
    return out


def read(root, rel):
    p = os.path.join(root, rel)
    if not os.path.isfile(p):
        return None
    return open(p, 'rb').read()


def norm(b):
    return None if b is None else b.replace(b'\r\n', b'\n')


def is_text(*bs):
    return all(b is None or b'\0' not in b[:8192] for b in bs)


def merge3(o, a, t):
    with tempfile.TemporaryDirectory(dir=os.path.join(ROOT, 'out')) as td:
        paths = []
        for name, data in (('ours', o), ('ancestor', a if a is not None else b''), ('theirs', t)):
            p = os.path.join(td, name)
            open(p, 'wb').write(data)
            paths.append(p)
        r = subprocess.run(['git', 'merge-file', '-p', '--diff3', '-L', 'ours (sasrt)', '-L', 'ancestor (banjo 894d3256)',
                            '-L', 'theirs (ultimate)'] + paths, capture_output=True)
        return r.stdout, r.returncode


def main():
    report = []
    totals = {}
    only = sys.argv[sys.argv.index('--only') + 1].split(',') if '--only' in sys.argv else None
    for name, A, O, T, OUT, subs in SETS:
        if only and name not in only:
            continue  # sasrt-nx: --only renderer,plume,translator (a set merged again loses its hand resolutions)
        if name == 'renderer' and '--generated' in sys.argv:
            if os.path.isdir(OUT):
                shutil.rmtree(OUT)
        elif name == 'renderer':
            # The whole of ours first (sa2_compat and the rest stay as they are), then the merged parts over it.
            src_all = os.path.join(SRC, 'sa2_banjo')
            dst_all = os.path.join(SRC, 'sa2_ult')
            if os.path.isdir(dst_all):
                shutil.rmtree(dst_all)
            shutil.copytree(src_all, dst_all)
            for sub in subs:
                p = os.path.join(OUT, sub)
                if os.path.isdir(p):
                    shutil.rmtree(p)
                elif os.path.isfile(p):
                    os.remove(p)
        else:
            if os.path.isdir(OUT):
                shutil.rmtree(OUT)
        rels = sorted(files(A, subs) | files(O, subs) | files(T, subs))
        counts = {}
        for rel in rels:
            a, o, t = read(A, rel), read(O, rel), read(T, rel)
            if not is_text(o, t, a):
                # sasrt-nx (2026-11-08): binary files as they are (the first run normalised their line ends too and
                # broke the translator's dxcompiler.dll: XenosRecomp exited 0xC000007B).
                data = o if (o == t or a == t) else t if a == o else o
                if data is not None:
                    dst = os.path.join(OUT, rel)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    open(dst, 'wb').write(data)
                continue
            na, no, nt = norm(a), norm(o), norm(t)
            crlf = o is not None and b'\r\n' in o
            if name == 'renderer' and any(rel.startswith(k) for k in OURS_KEEP):
                action, data = ('ours (per XDK)' + ('' if nt == na else ', the base changed it'), no)
            elif no == nt:
                action, data = 'same', no
            elif na == no:
                action, data = ('theirs' if nt is not None else 'deleted by theirs'), nt
            elif na == nt:
                action, data = ('ours' if no is not None else 'deleted by ours'), no
            elif no is None:
                action, data = 'CONFLICT: deleted by ours, changed by theirs (theirs taken)', nt
            elif nt is None:
                action, data = 'CONFLICT: deleted by theirs, changed by ours (ours taken)', no
            elif not is_text(no, nt, na):
                action, data = 'CONFLICT: binary changed on both sides (ours taken)', o
                crlf = False
            else:
                merged, n = merge3(no, na if na is not None else b'', nt)
                action, data = ('merged' if n == 0 else 'CONFLICT: %d hunks' % n), merged
            key = action.split(':')[0]
            counts[key] = counts.get(key, 0) + 1
            if data is None:
                continue
            if crlf or (o is None and t is not None and b'\r\n' in t):
                data = data.replace(b'\n', b'\r\n')
            dst = os.path.join(OUT, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            open(dst, 'wb').write(data)
            if action not in ('same',):
                report.append('%-10s %-60s %s' % (name, rel, action))
        totals[name] = counts
    open(os.path.join(SRC, 'ult_merge.txt'), 'w', encoding='utf-8').write('\n'.join(report) + '\n')
    for name, counts in totals.items():
        print(name, ', '.join('%s %d' % kv for kv in sorted(counts.items())))
    print('\n'.join(l for l in report if 'CONFLICT' in l or 'base changed it' in l))


if __name__ == '__main__':
    main()
