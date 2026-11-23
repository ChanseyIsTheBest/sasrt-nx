#!/usr/bin/env python3
"""sasrt-nx (2026-11-08): the move to the ultimate base, after the conflicts (tools/ult_merge.py --generated,
tools/ult_resolve.py): one definition per cvar.
  - sa2-nx's renames of banjo-nx keys (sa2_renut_<x>) back to the names the base's code reads (banjo_renut_<x>);
  - this port's own definitions of the keys renut-ultimate's ultimate.cpp defines (the fixes it took from sasrt-nx) go,
    in the merged renderer and in app/src/renut_engine/sasrt_renut_hooks.cpp;
  - banjo_cpu_verify (banjo-nx's name) is this port's sasrt_cpu_verify.
    python tools/ult_normalise.py"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GPU = os.path.join(ROOT, 'out', 'renut_sources', 'sasrt_ult', 'gpu')
HOOKS = os.path.join(ROOT, 'app', 'src', 'renut_engine', 'sasrt_renut_hooks.cpp')
RENAME = {'sa2_renut_' + k: 'banjo_renut_' + k for k in (
    'capture_batches', 'neon_compare', 'snapshot_deltas', 'snapshot_deltas_constants', 'snapshot_deltas_narrow',
    'snapshot_deltas_verify')}
RENAME['banjo_cpu_verify'] = 'sasrt_cpu_verify'


def files():
    for d, _, fs in os.walk(GPU):
        for f in fs:
            if f.endswith(('.cpp', '.h', '.inc', '.hlsl', '.hlsli')):
                yield os.path.join(d, f)


def load(p):
    raw = open(p, 'rb').read()
    return raw.decode('utf-8').replace('\r\n', '\n'), b'\r\n' in raw


def save(p, s, crlf):
    open(p, 'wb').write((s.replace('\n', '\r\n') if crlf else s).encode('utf-8'))


def drop_define(s, key):
    """The REXCVAR_DEFINE_* statement of key (up to its ';'), with the comment lines right above it, out."""
    m = re.search(r'(?m)^REXCVAR_DEFINE_\w+\(\s*%s\s*,' % re.escape(key), s)
    if not m:
        return s, False
    start = m.start()
    # the statement ends at the first ';' outside a string
    i, in_str = m.end(), False
    while i < len(s):
        c = s[i]
        if c == '"' and s[i - 1] != '\\':
            in_str = not in_str
        elif c == ';' and not in_str:
            break
        i += 1
    end = s.index('\n', i) + 1
    # the comment lines directly above
    lines_before = s[:start].split('\n')[:-1]
    k = len(lines_before)
    while k > 0 and lines_before[k - 1].lstrip().startswith('//'):
        k -= 1
    start = len('\n'.join(lines_before[:k])) + (1 if k else 0)
    return s[:start] + '// sasrt-nx (2026-11-08): %s is renut-ultimate\'s now (gpu/ultimate.cpp).\n' % key + s[end:], True


ult = open(os.path.join(GPU, 'ultimate.cpp'), encoding='utf-8').read()
ult_keys = set(re.findall(r'REXCVAR_DEFINE_\w+\(\s*(\w+)\s*,', ult))
changed = 0
for p in list(files()) + [HOOKS]:
    s, crlf = load(p)
    t = s
    for a, b in RENAME.items():
        t = re.sub(r'\b%s\b' % a, b, t)
    if not p.endswith('ultimate.cpp'):
        for k in sorted(ult_keys):
            while True:
                t, hit = drop_define(t, k)
                if not hit:
                    break
                print('  %s: definition of %s out' % (os.path.relpath(p, ROOT), k))
    if t != s:
        save(p, t, crlf)
        changed += 1
print('ult_normalise: %d files changed' % changed)
