#!/usr/bin/env python3
"""sasrt-nx (2026-11-13): take the ultimate base's ports into this port one commit at a time (the user: "sync up with
the ultimate base"). D:/renut-ultimate/base is read-only from here.

For each port commit C, for each file it changes: a three-way merge (git merge-file) of this port's file (ours) with the
base's file before C (the ancestor) and after C (theirs), so exactly C's change comes in and everything this port did
since stays. Ports this port made itself are skipped (the base's form of them is a copy of ours). Files the commit adds
and this port lacks are copied; files this port has under another name, Katamari's own files and the docs are listed for
a hand port. Line ends: compared without CR, written back in the file's own style.

    python tools/ult_port_sync.py PORTS.json [--dry-run]

PORTS.json: [[port number, commit], ...] in the order to apply. Writes out/ult_port_sync.txt (what happened to each
file). A file with conflicts gets diff3 markers (<<<<<<< ours / ||||||| base / ======= / >>>>>>> base port N) in place.
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = 'D:/renut-ultimate/base'
SKIP_PREFIX = ('docs/', 'dist/', 'pgo/', 'app/katamari', 'app/src/katamari', 'README.md', 'THIRD_PARTY_NOTICES.md',
               'LICENSE')
# The per-XDK files are this port's (ult_merge.py): their fixes are carried by hand.
OURS_KEEP = ('app/src/renut_engine/gpu/d3d/hooks/', 'app/src/renut_engine/gpu/d3d/d3d.h',
             'app/src/renut_engine/gpu/d3d/d3d_native.h', 'app/src/renut_engine/gpu/d3d/d3d_native_state.cpp',
             'app/src/renut_engine/gpu/banjo_shared_hooks.h')


def git_show(rev, path):
    r = subprocess.run(['git', '-C', BASE, 'show', '%s:%s' % (rev, path)], capture_output=True)
    return r.stdout if r.returncode == 0 else None


def name_status(c):
    out = subprocess.run(['git', '-C', BASE, 'show', '--name-status', '--format=', c], capture_output=True,
                         text=True).stdout
    rows = []
    for line in out.splitlines():
        p = line.split('\t')
        if p[0].startswith('R'):
            rows.append(('R', p[2], p[1]))
        else:
            rows.append((p[0][0], p[1], None))
    return rows


def lf(b):
    return b.replace(b'\r\n', b'\n')


def main():
    ports = json.load(open(sys.argv[1]))
    dry = '--dry-run' in sys.argv
    log = []
    totals = {'clean': 0, 'conflict': 0, 'copied': 0, 'same': 0, 'hand': 0, 'skipped': 0}
    for n, c in ports:
        for st, path, old in name_status(c):
            tag = 'port %d %s' % (n, c[:9])
            if path.startswith(SKIP_PREFIX):
                log.append('%s skip (docs / Katamari / dist) %s' % (tag, path))
                totals['skipped'] += 1
                continue
            if path.startswith(OURS_KEEP):
                log.append('%s HAND (per-XDK file, ours) %s' % (tag, path))
                totals['hand'] += 1
                continue
            mine = os.path.join(ROOT, path)
            after = git_show(c, path) if st != 'D' else None
            before = git_show(c + '^', old or path) if st != 'A' else None
            if st == 'D':
                log.append('%s HAND (deleted in the base) %s' % (tag, path))
                totals['hand'] += 1
                continue
            if not os.path.exists(mine):
                if st == 'A':
                    if not dry:
                        os.makedirs(os.path.dirname(mine), exist_ok=True)
                        open(mine, 'wb').write(after)
                    log.append('%s copied (new) %s' % (tag, path))
                    totals['copied'] += 1
                else:
                    log.append('%s HAND (not in this port under this path) %s' % (tag, path))
                    totals['hand'] += 1
                continue
            ours_raw = open(mine, 'rb').read()
            crlf = b'\r\n' in ours_raw
            ours, base, theirs = lf(ours_raw), lf(before or b''), lf(after)
            if ours == theirs:
                log.append('%s same already %s' % (tag, path))
                totals['same'] += 1
                continue
            with tempfile.TemporaryDirectory() as d:
                po, pb, pt = (os.path.join(d, x) for x in ('ours', 'base', 'theirs'))
                open(po, 'wb').write(ours)
                open(pb, 'wb').write(base)
                open(pt, 'wb').write(theirs)
                r = subprocess.run(['git', 'merge-file', '-p', '--diff3', '-L', 'ours (sasrt-nx)', '-L', 'base before',
                                    '-L', 'base port %d' % n, po, pb, pt], capture_output=True)
                merged = r.stdout
                conflicts = r.returncode
            if conflicts < 0:
                log.append('%s HAND (merge-file failed) %s' % (tag, path))
                totals['hand'] += 1
                continue
            if not dry:
                open(mine, 'wb').write(merged.replace(b'\n', b'\r\n') if crlf else merged)
            if conflicts:
                log.append('%s CONFLICT x%d %s' % (tag, conflicts, path))
                totals['conflict'] += 1
            else:
                log.append('%s clean %s' % (tag, path))
                totals['clean'] += 1
    out = os.path.join(ROOT, 'out', 'ult_port_sync.txt')
    open(out, 'w', encoding='utf-8').write('\n'.join(log) + '\n')
    print('\n'.join(l for l in log if 'CONFLICT' in l or 'HAND' in l))
    print(totals, '->', out)


if __name__ == '__main__':
    main()
