#!/usr/bin/env python3
"""sasrt-nx (2026-11-08): which shaders of out/renut_shader_dump make the translator (XenosRecomp) crash: runs it on
halves of the dump in out/xr_bisect/<n> until single shaders remain. Each run's output goes to a throwaway .cpp.
    python tools/xr_bisect.py [max shaders per leaf, default 1]"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DUMP = os.path.join(ROOT, 'out', 'renut_shader_dump')
WORK = os.path.join(ROOT, 'out', 'xr_bisect')
EXE = os.path.join(ROOT, 'out', 'pc', 'xenos_recomp', 'build', 'XenosRecomp', 'XenosRecomp.exe')
COMMON = os.path.join(ROOT, 'app', 'thirdparty', 'reblue-XenosRecomp', 'XenosRecomp', 'shader_common.h')
leaf = int(sys.argv[1]) if len(sys.argv) > 1 else 1
runs = [0]


def crashes(files):
    runs[0] += 1
    d = os.path.join(WORK, 'run%d' % runs[0])
    os.makedirs(d)
    for f in files:
        shutil.copy2(os.path.join(DUMP, f), d)
    r = subprocess.run([EXE, d, os.path.join(d, 'out.cpp'), COMMON], capture_output=True, cwd=os.path.dirname(EXE))
    shutil.rmtree(d)
    bad = r.returncode != 0 and r.returncode not in (1,)
    print('run %d: %d shaders -> exit %d%s' % (runs[0], len(files), r.returncode, ' CRASH' if bad else ''), flush=True)
    return bad


def search(files):
    if len(files) <= leaf:
        return [files]
    half = len(files) // 2
    a, b = files[:half], files[half:]
    found = []
    if crashes(a):
        found += search(a)
    if crashes(b):
        found += search(b)
    return found


if os.path.isdir(WORK):
    shutil.rmtree(WORK)
os.makedirs(WORK)
shaders = sorted(f for f in os.listdir(DUMP) if f.endswith('.bin'))
print('%d shaders' % len(shaders))
bad = search(shaders)
print('crashing:', bad)
shutil.rmtree(WORK)
