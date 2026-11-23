#!/usr/bin/env python3
"""sasrt-nx (2026-11-08): the cvars of the merged renderer (out/renut_sources/sasrt_ult/gpu) with this port's other
sources (app/src without app/src/renut_engine/gpu, sdk/src): which are defined twice, and which are read or declared
but defined nowhere.
    python tools/ult_keys.py [gpu root]"""
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GPU = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'out', 'renut_sources', 'sasrt_ult', 'gpu')
DEF = re.compile(r'REXCVAR_DEFINE_\w+\(\s*(\w+)\s*,')
USE = re.compile(r'REXCVAR_(?:GET|DECLARE\([^,]*,|SET)\(?\s*(\w+)')


def sources():
    for d, _, fs in os.walk(GPU):
        for f in fs:
            if f.endswith(('.cpp', '.h', '.inc')):
                yield os.path.join(d, f)
    skip = os.path.normpath(os.path.join(ROOT, 'app', 'src', 'renut_engine', 'gpu'))
    for top in (os.path.join(ROOT, 'app', 'src'), os.path.join(ROOT, 'sdk', 'src')):
        for d, _, fs in os.walk(top):
            if os.path.normpath(d).startswith(skip):
                continue
            for f in fs:
                if f.endswith(('.cpp', '.h', '.inc')):
                    yield os.path.join(d, f)


defs = defaultdict(list)
uses = defaultdict(list)
for p in sources():
    text = open(p, encoding='utf-8', errors='replace').read()
    text = re.sub(r'//[^\n]*', '', text)
    for m in DEF.finditer(text):
        defs[m.group(1)].append(os.path.relpath(p, ROOT))
    for m in re.finditer(r'REXCVAR_GET\(\s*(\w+)\s*\)|REXCVAR_DECLARE\([^,]*,\s*(\w+)\s*\)', text):
        uses[m.group(1) or m.group(2)].append(os.path.relpath(p, ROOT))
print('defined twice:')
for k, v in sorted(defs.items()):
    if len(v) > 1:
        print('  %s: %s' % (k, ', '.join(v)))
print('used, not defined:')
for k, v in sorted(uses.items()):
    if k not in defs:
        print('  %s: %s' % (k, ', '.join(sorted(set(v)))[:200]))
