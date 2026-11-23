"""sasrt-nx (2026-11-08, the move to the ultimate base): every dumped shader's deko3d SPIR-V from Renut's translator.

    python tools/deko3d_spirv_all.py [--in out/renut_shader_dump] [--out out/deko3d_shaders_ult/spirv] [--jobs 8]

docs/deko3d-renderer.md ("Shaders"): XenosRecomp with BANJO_DEKO3D_SPIRV_DIR writes each shader's deko3d SPIR-V, and
it is run once per shader (a run over the whole directory fails fast part way through). Each shader is copied into a
directory of its own under out/tmp/spv_one and translated there; a run that fails is tried again twice (the
translator's intermittent access violation, docs/ultimate-base.md). Then: tools/deko3d_shaders.py --no-uam,
tools/deko3d_glsl_opt.py --check, tools/deko3d_shader_package.py. Game data: the build tree only.
"""
import argparse
import concurrent.futures
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XR = os.path.join(ROOT, 'out', 'pc', 'xenos_recomp', 'build', 'XenosRecomp', 'XenosRecomp.exe')
COMMON = os.path.join(ROOT, 'app', 'thirdparty', 'reblue-XenosRecomp', 'XenosRecomp', 'shader_common.h')


def one(src, out, tmp_root):
    name = os.path.basename(src)
    stem = os.path.splitext(name)[0]
    work = os.path.join(tmp_root, stem)
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(os.path.join(work, 'in'))
    shutil.copyfile(src, os.path.join(work, 'in', name))
    env = dict(os.environ, BANJO_DEKO3D_SPIRV_DIR=out)
    last = ''
    for attempt in range(3):
        r = subprocess.run([XR, os.path.join(work, 'in'), os.path.join(work, 'c.cpp'), COMMON], env=env,
                           capture_output=True, text=True, errors='replace')
        if r.returncode == 0:
            shutil.rmtree(work, ignore_errors=True)
            return stem, attempt, ''
        last = f'exit {r.returncode & 0xFFFFFFFF:08X}: ' + (r.stderr or r.stdout).strip()[-200:]
    shutil.rmtree(work, ignore_errors=True)
    return stem, 3, last


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='src', default=os.path.join(ROOT, 'out', 'renut_shader_dump'))
    ap.add_argument('--out', default=os.path.join(ROOT, 'out', 'deko3d_shaders_ult', 'spirv'))
    ap.add_argument('--jobs', type=int, default=8)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    tmp_root = os.path.join(ROOT, 'out', 'tmp', 'spv_one')
    os.makedirs(tmp_root, exist_ok=True)
    files = sorted(os.path.join(a.src, f) for f in os.listdir(a.src) if f.endswith('.bin'))
    retried, failed = 0, []
    with concurrent.futures.ThreadPoolExecutor(a.jobs) as ex:
        for stem, attempts, err in ex.map(lambda f: one(f, os.path.abspath(a.out), tmp_root), files):
            if err:
                failed.append((stem, err))
            elif attempts:
                retried += 1
    print(f'{len(files)} shaders, {len(files) - len(failed)} translated ({retried} on a second or third try), '
          f'{len(failed)} failed; {len(os.listdir(a.out))} SPIR-V files in {a.out}')
    for stem, err in failed:
        print('  failed', stem, err)


if __name__ == '__main__':
    sys.exit(main())
