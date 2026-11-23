#!/usr/bin/env python3
"""katamari-nx (2026-11-02, futari-nx's and peggle2-nx's tools/renut_release_shaders.py): the Switch build's Renut shader
files without translated game shaders, for a build that can be distributed (app/out/renut_switch_release/), and the
file the web installer makes in their place, for tests.

    python tools/renut_release_shaders.py [--glsl out/deko3d_shaders/glsl_opt] [--cache app/out/renut_switch/shader_cache_switch.cpp]

Writes into app/out/renut_switch_release/:
  shader_cache_switch.cpp   the shader table (numbers: hashes, fetch masks, vertex input formats) without the SPIR-V
                            (the deko3d back end never reads it; the PC's Vulkan one does)
  sd/deko3d_glsl.bin        the package of the game's shaders, which the web installer makes from the player's files and
                            puts beside the NRO (this one is the Python tools' copy: game data, for tests only, never
                            distributed)
Every one of Beautiful Katamari's 195 shaders is a container stored in its files (111 in default.xex, 84 in the models
of d02-d05.dat), so no GLSL package is built into the NRO: app/cmake/banjo_renut_gpu.cmake
(BANJO_RENUT_RELEASE_SHADERS) builds with these files.

sasrt-nx (2026-11-22, the web installer's shader step): --only FILE (shader names, one a line, as
tools/shader_records.py's *_missing.json lists them) keeps those shaders built into the NRO: the ones the game makes at
runtime, which no game file holds and the page cannot make (app/cmake/sasrt_renut_gpu.cmake builds the
deko3d_glsl_switch.cpp written then). The NRO looks a shader up in deko3d_glsl.bin beside it, then in its own package.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def package(glsl_dir, names, out_dir, raw=False):
    """tools/deko3d_shader_package.py over the given shaders only. raw: no dictionary, each GLSL in a zstd frame of raw
    blocks, the form the web installer reads out of the NRO (lib/nro.js nroShaders) to compile their variants too."""
    os.makedirs(out_dir, exist_ok=True)
    src = os.path.join(out_dir, 'glsl')
    shutil.rmtree(src, ignore_errors=True)
    os.makedirs(src)
    for n in names:
        shutil.copyfile(os.path.join(glsl_dir, n), os.path.join(src, n))
    subprocess.run([sys.executable, '-P', os.path.join(ROOT, 'tools', 'deko3d_shader_package.py'), '--glsl', src,
                    '--out', out_dir] + (['--raw'] if raw else []), check=True)
    shutil.rmtree(src)


def strip_spirv(text):
    """shader_cache_switch.cpp without the SPIR-V: the assembler's .incbin goes, its sizes are 0, and every entry's
    SPIR-V offset and size (the 4th and 5th numbers of g_shaderCacheEntries' lines) are 0."""
    text, n = re.subn(r'// banjo-nx: the compressed SPIR-V.*?\.previous\\n"\);\n',
                      'const uint8_t g_compressedSpirvCache[] = {0};  // no SPIR-V (deko3d reads none)\n',
                      text, flags=re.S)
    if n != 1:
        sys.exit('renut_release_shaders: the SPIR-V block of shader_cache_switch.cpp not found')
    text = re.sub(r'(g_spirvCache(?:Compressed|Decompressed)Size\s*=\s*)\d+', r'\g<1>0', text)

    def entry(m):
        fields = m.group(2).split(', ')
        fields[3] = fields[4] = '0'
        return m.group(1) + ', '.join(fields)
    text, n = re.subn(r'^(\t\{ )(0x[0-9A-F]+, \d+, \d+, \d+, \d+)', entry, text, flags=re.M)
    if not n:
        sys.exit('renut_release_shaders: no entry of g_shaderCacheEntries found')
    if 'incbin' in text:
        sys.exit('renut_release_shaders: an .incbin is left in the shader table')
    return text


def main():
    ap = argparse.ArgumentParser()
    # sasrt-nx: the shipping GLSL is out/deko3d_shaders_sync/glsl_opt (2026-11-13, with SASRT's passes; the 2,007 of
    # app/out/renut_switch's package), not the base's out/deko3d_shaders/glsl_opt (10-21, before them)
    ap.add_argument('--glsl', default=os.path.join(ROOT, 'out', 'deko3d_shaders_sync', 'glsl_opt'))
    ap.add_argument('--cache', default=os.path.join(ROOT, 'app', 'out', 'renut_switch', 'shader_cache_switch.cpp'))
    ap.add_argument('--out', default=os.path.join(ROOT, 'app', 'out', 'renut_switch_release'))
    ap.add_argument('--only', default=None, help='shader names to keep built into the NRO (one a line)')
    a = ap.parse_args()
    names = sorted(f for f in os.listdir(a.glsl) if re.fullmatch(r'(vs|ps)_[0-9A-F]{16}\.glsl', f))
    if not names:
        sys.exit(f'renut_release_shaders: no shaders in {a.glsl}')
    os.makedirs(a.out, exist_ok=True)
    package(a.glsl, names, os.path.join(a.out, 'sd'))
    os.remove(os.path.join(a.out, 'sd', 'deko3d_glsl_switch.cpp'))  # the installer's file is never built in
    built_in = os.path.join(a.out, 'deko3d_glsl_switch.cpp')
    if os.path.exists(built_in):
        os.remove(built_in)
    if a.only:  # sasrt-nx: the shaders the game makes at runtime, built in
        # one form for a name: vs_/ps_ and the hash in capitals (the GLSL files' form; the dumps' are lower case)
        norm = lambda s: s[:3].lower() + s[3:].upper()  # noqa: E731
        keep = {norm(ln.split('#')[0].strip()) for ln in open(a.only, encoding='utf-8') if ln.split('#')[0].strip()}
        keep_names = [n for n in names if norm(n[:-5]) in keep]
        if len(keep_names) != len(keep):
            sys.exit(f'renut_release_shaders: --only names {len(keep)} shaders, {len(keep_names)} of them in {a.glsl}')
        tmp = os.path.join(a.out, 'built_in')
        package(a.glsl, keep_names, tmp, raw=True)
        # the package's .incbin names its own folder's deko3d_glsl.bin: keep that beside the .cpp, the folder goes
        blob = os.path.join(a.out, 'deko3d_glsl_built_in.bin')
        shutil.move(os.path.join(tmp, 'deko3d_glsl.bin'), blob)
        cpp = open(os.path.join(tmp, 'deko3d_glsl_switch.cpp'), encoding='utf-8').read()
        old_path = os.path.join(tmp, 'deko3d_glsl.bin').replace(os.sep, '/')
        if cpp.count(old_path) != 1:
            sys.exit(f'renut_release_shaders: the built-in package does not .incbin {old_path}')
        with open(built_in, 'w', encoding='utf-8', newline='\n') as f:
            f.write(cpp.replace(old_path, blob.replace(os.sep, '/')))
        shutil.rmtree(tmp)
        print(f'renut_release_shaders: {len(keep_names)} shaders built into the NRO ({blob})')
    text = open(a.cache, encoding='utf-8').read()
    with open(os.path.join(a.out, 'shader_cache_switch.cpp'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(strip_spirv(text))
    print(f'renut_release_shaders: {"no" if not a.only else len(keep_names)} shaders built in; deko3d_glsl.bin (tests '
          f'only: the page makes the players\' own) {len(names)} game shaders -> {a.out}')


if __name__ == '__main__':
    main()
