#!/usr/bin/env python3
"""Brings sa2-nx's Renut renderer (app/src/renut_engine, Renut's Direct3D-level renderer as banjo-nx carries it,
retargeted by sa2-nx to Sonic Adventure 2's Direct3D 2.0.21076) into this port (2026-10-19/20, the deko3d native
renderer route; Renut: github.com/masterspike52/reNut, credit reNut and masterspike52; banjo-nx's
docs/deko3d-native-renderer-kit.md).

Why sa2-nx's tree: this game's Direct3D (2.0.21119) is SA2's instruction for instruction. 634 of the 640 functions of
SA2's Direct3D range have a function of exactly the same instruction shape here (opcodes and registers; immediates and
branch targets aside), and the device layout is the same. sa2-nx's layout work (d3d.h, d3d_native.h) and its hook
set apply as they are; only addresses differ:
  - functions: SA2 sub_X -> this game's, through the exact-shape map (app/config/renut_sa2_map.tsv: SA2, SASRT);
  - guest globals (0x82xxxxxx / 0x83xxxxxx constants): through the same pairs. In two functions of identical shape the
    k-th lis-built absolute address of one is the k-th of the other (app/config/renut_sa2_globals.tsv);
  - SA2's names: sa2_renderer -> sasrt_renderer, SA2_RENUT_RENDERER -> SASRT_RENUT_RENDERER, sa2_compat ->
    sasrt_compat, SA2's frame counter and enhancement masters -> this port's.
Hooks at addresses this port hooks too (src/me, src/*.cpp: its PM4 renderer, native Direct3D layer, census) become
BANJO_RENUT_HOOK_SHARED / _RAW_SHARED (Renut's side as renut_native_sub_X, which this port's hook calls first:
SASRT_RENUT_YIELD_SHARED); every other hook stays a plain dispatcher. The port's own hooks get their yield line
(SASRT_RENUT_YIELD_SHARED or SASRT_RENUT_YIELD) rewritten to match.

  python tools/renut_from_sa2.py [--sa2 "D:/sonic adventure 2/sa2-nx"] [--dry-run]
An unmapped address in code is reported and left as it is (the build then fails on it or the hook is wrong: fix the
map). Running it again gives the same tree.
"""
import argparse
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_SRC = os.path.join(ROOT, 'app', 'src')
DEST = os.path.join(APP_SRC, 'renut_engine')
FUNC_MAP = os.path.join(ROOT, 'app', 'config', 'renut_sa2_map.tsv')
GLOBAL_MAP = os.path.join(ROOT, 'app', 'config', 'renut_sa2_globals.tsv')
# This port's own files under DEST, kept.
KEEP = {'sasrt_renut_yield.h'}
# Copied from sa2-nx's renut_engine (relative paths); renamed on the way.
COPY = ['gpu', 'sa2_compat', 'display_sync.cpp', 'display_sync.h', 'perf', 'renut_logging.h', 'globals.h']
# Taken from banjo-nx's renut_engine instead (relative paths, the same names, edits and address rewrite). Until
# 2026-10-29 five files (tuning, pipeline.cpp, textures.cpp, draw.h); since the sync with banjo-nx of 2026-10-29 the
# source tree (out/renut_sources/sa2_banjo) is itself banjo-nx's HEAD merged three-way with sa2-nx's retargeting
# (docs/deko3d-renderer.md "Banjo sync 2026-10-29"), so nothing comes from the banjo snapshot directly.
FROM_BANJO = set()
RENAME_PATH = {'sa2_compat': 'sasrt_compat', 'sa2_compat.cpp': 'sasrt_compat.cpp', 'sa2_screen.cpp': 'sasrt_screen.cpp',
               'sa2_renut_pacing.cpp': 'sasrt_renut_pacing.cpp', 'sa2_renut_pacing.h': 'sasrt_renut_pacing.h',
               'sa2_renut_yield.h': None}  # None: not copied (this port has its own)

NAMES = [  # (SA2's text, this port's): applied to every copied file, in order
    ('sa2_renderer_native', 'masseffect_renderer_native'),
    ('REXCVAR_DEFINE_STRING(sa2_renderer, "xenos", "SA2",', 'REXCVAR_DEFINE_STRING(sasrt_renderer, "xenos", "SASRT",'),
    ('sa2_renderer', 'sasrt_renderer'),
    ('SA2_RENUT_RENDERER', 'SASRT_RENUT_RENDERER'),
    ('sa2_compat', 'sasrt_compat'),
    ('sa2_screen', 'sasrt_screen'),
    ('renut_engine/gpu/sa2_renut_yield.h', 'renut_engine/sasrt_renut_yield.h'),
    ('g_sa2_game_frames', 'g_sasrt_game_frames'),
    ('#include "cpu/sa2_enhancements.h"', '#include "sasrt_enhancements.h"'),
    ('sa2::enh::CpuMaster()', 'sasrt::enhancements::GroupOn(sasrt::enhancements::Group::kCpu)'),
    ('sa2::enh::NonCpuMaster()', 'sasrt::enhancements::GroupOn(sasrt::enhancements::Group::kNonCpu)'),
    ('src/sa2_d3d_trace.cpp', 'src/sasrt_d3d_trace.cpp'),
    # sa2-nx's frame pacing (gpu/sa2_renut_pacing.cpp): this port's relaxed-vsync enhancement has the same name.
    ('sa2_renut_pacing', 'sasrt_renut_pacing'),
    ('::sa2::enh::Enhancement', '::sasrt::enhancements::Enhancement'),
    ('sa2::renut', 'sasrt::renut'),
    ('sa2_renut_vblank_pacing', 'sasrt_renut_vblank_pacing'),
    ('sa2_vsync_relaxed', 'sasrt_vsync_relaxed'),
    # sa2-nx's lockstep captures through Renut's Present (stubs in this port's sasrt_capture.h) and its GLSL package key.
    ('#include "sa2_capture.h"', '#include "sasrt_capture.h"'),
    ('sa2::capture::', 'sasrt::capture::'),
    ('sa2_deko3d_', 'sasrt_deko3d_'),
    (', "SA2",', ', "SASRT",'),
]

# sa2-nx does not build these (its gpu.cmake): N&B's state setters at N&B's addresses, and N&B's game code.
STUB = {
    os.path.join('gpu', 'd3d', 'hooks', 'state.cpp'): "N&B's state setters at N&B's addresses; the game's own run",
    os.path.join('gpu', 'guest', 'photo_capture.cpp'): "N&B's photo feature",
    os.path.join('gpu', 'guest', 'widescreen.cpp'): "N&B's screen code; guest/sasrt_screen.cpp instead",
}
sys.path.insert(0, os.path.join(ROOT, 'tools', 'renut_patches'))
from sasrt_edits import EDITS  # noqa: E402
# Addresses not to report: this game's own (written by EDITS), and N&B's constants whose only uses EDITS replaced.
KNOWN_HEX = {h.upper() for _, _, new in EDITS for h in re.findall(r'0x(8[23][0-9A-Fa-f]{6})', new)}
KNOWN_HEX |= {'82F39E34', '82F597B4', '82FAD204', '82FAD208'}

# Also inside __imp__sub_X, renut_native_sub_X, banjo_renut_raw_sub_X (no word boundary after an underscore).
SUB_RE = re.compile(r'(?<![A-Za-z0-9])(sub_[0-9A-F]{8})\b')
HEX_RE = re.compile(r'\b0x(8[23][0-9A-Fa-f]{6})\b')
HOOK_RE = re.compile(r'\bBANJO_RENUT_HOOK(_RAW)?(_SHARED)?\((sub_[0-9A-F]{8})')
GAME_HOOK_RE = re.compile(r'\b(?:REX_HOOK|REX_HOOK_RAW)\(\s*(sub_[0-9A-F]{8})')
CENSUS_RE = re.compile(r'^SASRT_CENSUS_HOOK(?:_SHARED)?\(([0-9A-F]{8})\)', re.M)
YIELD_RE = re.compile(r'SASRT_RENUT_YIELD(?:_SHARED)?\((sub_[0-9A-F]{8}|sub_##ADDR)\)')


def load_map(path):
    out = {}
    for line in open(path, encoding='utf-8'):
        if line.startswith('#') or not line.strip():
            continue
        p = line.split()
        out[p[0]] = p[1]
    return out


def game_hooks():
    hooked = {}
    for base, dirs, files in os.walk(APP_SRC):
        if base.startswith(DEST):
            continue
        for f in files:
            if f.endswith(('.cpp', '.h')):
                path = os.path.join(base, f)
                text = open(path, encoding='utf-8', errors='replace').read()
                for m in GAME_HOOK_RE.finditer(text):
                    hooked.setdefault(m.group(1), path)
                for m in CENSUS_RE.finditer(text):
                    hooked.setdefault('sub_' + m.group(1), path)
    return hooked


def is_comment(line):
    s = line.lstrip()
    return s.startswith('//') or s.startswith('*') or s.startswith('/*')


def main():
    ap = argparse.ArgumentParser()
    # The sources are pinned snapshots (out/renut_sources/{sa2,banjo}/app/src/renut_engine): sa2-nx's and banjo-nx's
    # trees change while their sessions work, and a half-merged file there broke this port's build (2026-10-20).
    # --refresh copies the live trees into the snapshots first (when both build); --sa2 / --banjo name other roots.
    # 2026-10-29: the default source is sa2_banjo, banjo-nx 894d3256 (snapshot 'banjo') merged three-way with sa2-nx's
    # tree of 2026-10-20 ('sa2') over their common ancestor banjo-nx 25940a65 ('banjo_25940a65'); its conflicts were
    # resolved by hand (the SA2 layout and hooks kept, banjo-nx's renderer taken). Do not --refresh over it.
    snap = os.path.join(ROOT, 'out', 'renut_sources')
    ap.add_argument('--sa2', default=os.path.join(snap, 'sa2_banjo'))
    ap.add_argument('--banjo', default=os.path.join(snap, 'banjo'))
    ap.add_argument('--refresh', action='store_true',
                    help='copy D:/sonic adventure 2/sa2-nx and D:/Banjo kazooie port/banjo-nx renut_engine into the snapshots')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    if a.refresh:
        for name, live in (('sa2', 'D:/sonic adventure 2/sa2-nx'), ('banjo', 'D:/Banjo kazooie port/banjo-nx')):
            dst = os.path.join(snap, name, 'app', 'src', 'renut_engine')
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            shutil.copytree(os.path.join(live, 'app', 'src', 'renut_engine'), dst)
            print('renut_from_sa2: snapshot of %s refreshed' % live)
    funcs = load_map(FUNC_MAP)
    globs = {k.upper(): v.upper() for k, v in load_map(GLOBAL_MAP).items()}
    hooked = game_hooks()
    src_root = os.path.join(a.sa2, 'app', 'src', 'renut_engine')
    banjo_root = os.path.join(a.banjo, 'app', 'src', 'renut_engine')

    out_files = {}
    unmapped = {}
    applied_edits = set()
    for item in COPY:
        src = os.path.join(src_root, item)
        paths = []
        if os.path.isdir(src):
            for base, dirs, files in os.walk(src):
                for f in files:
                    paths.append(os.path.relpath(os.path.join(base, f), src_root))
        else:
            paths.append(item)
        for rel in paths:
            parts = rel.split(os.sep)
            new_parts = []
            skip = False
            for p in parts:
                if p in RENAME_PATH:
                    if RENAME_PATH[p] is None:
                        skip = True
                    p = RENAME_PATH[p] or p
                new_parts.append(p)
            if skip:
                continue
            dest_rel = os.sep.join(new_parts)
            from_root = banjo_root if rel in FROM_BANJO else src_root
            data = open(os.path.join(from_root, rel), 'rb').read()
            if not rel.endswith(('.cpp', '.h', '.inl', '.cmake', '.hlsl', '.hlsli', '.txt', '.md')):
                out_files[dest_rel] = data
                continue
            text = data.decode('utf-8').replace('\r\n', '\n')  # sa2-nx's files are partly CRLF: LF here
            if dest_rel in STUB:
                out_files[dest_rel] = ('// sasrt-nx (tools/renut_from_sa2.py): %s is not built (sa2-nx\'s gpu.cmake: %s).\n'
                                       % (dest_rel.replace(os.sep, '/'), STUB[dest_rel])).encode('utf-8')
                continue
            # This port's values where sa2-nx kept N&B's (paths sa2-nx does not take): tools/renut_patches/sasrt_edits.py.
            for e_index, (e_rel, e_old, e_new) in enumerate(EDITS):
                if os.path.join('gpu', e_rel.replace('/', os.sep)) == dest_rel and e_old in text:
                    text = text.replace(e_old, e_new)
                    applied_edits.add(e_index)
            for old, new in NAMES:
                text = text.replace(old, new)
            lines = text.split('\n')
            for i, line in enumerate(lines):
                comment = is_comment(line)

                def fsub(m):
                    t = funcs.get(m.group(1))
                    if t:
                        return t
                    if not comment and '//' not in line[:m.start()]:
                        unmapped.setdefault(m.group(1), set()).add(dest_rel)
                    return m.group(1)

                def gsub(m):
                    t = globs.get(m.group(1).upper())
                    if t:
                        return '0x' + t
                    if m.group(1).upper() in KNOWN_HEX:
                        return m.group(0)
                    if not comment and '//' not in line[:m.start()]:
                        unmapped.setdefault('0x' + m.group(1).upper(), set()).add(dest_rel)
                    return m.group(0)

                line = SUB_RE.sub(fsub, line)
                line = HEX_RE.sub(gsub, line)
                lines[i] = line
            out_files[dest_rel] = '\n'.join(lines).encode('utf-8')

    for e_index, (e_rel, e_old, e_new) in enumerate(EDITS):
        # The ones for banjo-nx's own tree (banjo_renut_select.cpp's key) may not apply to sa2-nx's: reported only
        # when the file is there and the text is not.
        if e_index not in applied_edits and os.path.join('gpu', e_rel.replace('/', os.sep)) in out_files and                 e_new not in out_files[os.path.join('gpu', e_rel.replace('/', os.sep))].decode('utf-8'):
            print('  EDIT NOT APPLIED: %s: %s' % (e_rel, e_old.split(chr(10))[0][:90]))

    # sa2-nx's compat file defines keys SA2 lacks (masseffect_native_nvk_* ...); this port may define them itself: its
    # own definition wins, sa2-nx's goes (one REXCVAR_DEFINE_* statement, up to its ';').
    defined = set()
    for base, dirs, files in os.walk(APP_SRC):
        if base.startswith(DEST):
            continue
        for f in files:
            if f.endswith(('.cpp', '.h')):
                defined |= set(re.findall(r'REXCVAR_DEFINE_\w+\(\s*(\w+)\s*,',
                                          open(os.path.join(base, f), encoding='utf-8', errors='replace').read()))
    for rel, data in list(out_files.items()):
        if not rel.startswith('sasrt_compat') or not rel.endswith('.cpp'):
            continue
        text = data.decode('utf-8')
        dropped = []

        def drop(m):
            if m.group(1) in defined:
                dropped.append(m.group(1))
                return '// sasrt-nx: %s is this port\'s own (tools/renut_from_sa2.py)\n' % m.group(1)
            return m.group(0)

        text = re.sub(r'REXCVAR_DEFINE_\w+\(\s*(\w+)\s*,(?:[^;"]|"(?:[^"\\]|\\.)*")*;\n', drop, text)
        # sasrt-nx (2026-11-08): banjo::hot::Report is this port's own since the localized copies moved to
        # katamari-nx's guard (app/src/cpu/banjo_hot_guest.cpp): sa2-nx's empty one goes.
        text = text.replace('namespace banjo::hot {' + chr(10) + 'void Report() {}' + chr(10) + '}  // namespace banjo::hot',
                            '// sasrt-nx: banjo::hot::Report is this port' + chr(39) + 's own (app/src/cpu/banjo_hot_guest.cpp)')
        out_files[rel] = text.encode('utf-8')
        if dropped:
            print('  %s: sa2-nx\'s definitions of %s left out' % (rel, ', '.join(dropped)))

    # Shared or not, by this port's own hooks.
    shared, plain = set(), set()
    for rel, data in list(out_files.items()):
        if not rel.endswith('.cpp'):
            continue
        text = data.decode('utf-8')

        def hook(m):
            raw, sub = m.group(1) or '', m.group(3)
            if sub in hooked:
                shared.add(sub)
                return 'BANJO_RENUT_HOOK%s_SHARED(%s' % (raw, sub)
            plain.add(sub)
            return 'BANJO_RENUT_HOOK%s(%s' % (raw, sub)

        text = '\n'.join(HOOK_RE.sub(hook, l) if not is_comment(l) else l for l in text.split('\n'))
        out_files[rel] = text.encode('utf-8')
    # This port's own Renut hooks (renut_engine/sasrt_renut_hooks.cpp: command buffers, tiling), shared ones included.
    own = os.path.join(DEST, 'sasrt_renut_hooks.cpp')
    if os.path.exists(own):
        for m in HOOK_RE.finditer(open(own, encoding='utf-8').read()):
            (shared if m.group(2) else plain).add(m.group(3))
    header = ['// Generated by tools/renut_from_sa2.py: the addresses both renderers hook. This port\'s hook there calls',
              '// renut_native_sub_X first when Renut\'s renderer is chosen (SASRT_RENUT_YIELD_SHARED,',
              '// renut_engine/sasrt_renut_yield.h).', '#pragma once', '', '#include <rex/ppc.h>', '']
    header += ['extern "C" void renut_native_%s(PPCContext& ctx, uint8_t* base);' % s for s in sorted(shared)]
    out_files[os.path.join('gpu', 'banjo_shared_hooks.h')] = ('\n'.join(header) + '\n').encode('utf-8')

    # This port's own files inside the tree (tools/renut_patches/extra/<path under renut_engine>), copied as they are:
    # host shaders must sit in gpu/shaders/host (gpu.cmake's renut_host_shader).
    extra_root = os.path.join(ROOT, 'tools', 'renut_patches', 'extra')
    for base, dirs, files in os.walk(extra_root):
        for f in files:
            src = os.path.join(base, f)
            out_files[os.path.relpath(src, extra_root)] = open(src, 'rb').read().replace(b'\r\n', b'\n')

    print('renut_from_sa2: %d files; hooks %d plain, %d shared with this port\'s' % (len(out_files), len(plain),
                                                                                  len(shared)))
    for s in sorted(shared):
        print('  shared: %s (this port: %s)' % (s, os.path.relpath(hooked[s], ROOT)))
    for k, files in sorted(unmapped.items()):
        print('  UNMAPPED in code: %s in %s' % (k, ', '.join(sorted(files))))

    # This port's hooks: the yield matching Renut's side.
    yields = []
    for sub, path in sorted(hooked.items()):
        text = open(path, encoding='utf-8').read()
        new = YIELD_RE.sub(lambda m: m.group(0) if m.group(1) == 'sub_##ADDR' else
                           ('SASRT_RENUT_YIELD_SHARED(%s)' if m.group(1) in shared else 'SASRT_RENUT_YIELD(%s)')
                           % m.group(1), text)
        if new != text:
            yields.append(path)
            if not a.dry_run:
                open(path, 'w', encoding='utf-8', newline='\n').write(new)
    # The census hooks' macro (src/me/sasrt_d3d_census.cpp): SASRT_CENSUS_HOOK_SHARED where Renut hooks the address.
    census = os.path.join(APP_SRC, 'me', 'sasrt_d3d_census.cpp')
    if os.path.exists(census):
        text = open(census, encoding='utf-8').read()
        new = re.sub(r'^SASRT_CENSUS_HOOK(?:_SHARED)?\(([0-9A-F]{8})\)',
                     lambda m: 'SASRT_CENSUS_HOOK%s(%s)' % ('_SHARED' if 'sub_' + m.group(1) in shared else '',
                                                           m.group(1)), text, flags=re.M)
        if new != text:
            yields.append(census)
            if not a.dry_run:
                open(census, 'w', encoding='utf-8', newline='\n').write(new)
    for p in sorted(set(yields)):
        print('  yields rewritten: %s' % os.path.relpath(p, ROOT))
    if a.dry_run:
        return
    # Only files whose text changed are written (their times stay otherwise: no rebuild); files the copy no longer has
    # go.
    written = 0
    for item in ['gpu', 'sasrt_compat', 'perf']:
        p = os.path.join(DEST, item)
        for base, dirs, files in os.walk(p):
            for f in files:
                rel = os.path.relpath(os.path.join(base, f), DEST)
                if rel not in out_files:
                    os.remove(os.path.join(base, f))
    for rel, data in out_files.items():
        p = os.path.join(DEST, rel)
        if os.path.exists(p) and open(p, 'rb').read() == data:
            continue
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, 'wb').write(data)
        written += 1
    print('renut_from_sa2: %d files written' % written)

if __name__ == '__main__':
    main()
