#!/usr/bin/env python3
"""Retargets banjo-nx's imported Renut renderer (app/src/renut_engine/gpu, hooks at Banjo-Kazooie: Nuts & Bolts'
addresses) to this game's Direct3D (2026-10-19, the deko3d native renderer route of banjo-nx's
docs/deko3d-native-renderer-kit.md; Renut: github.com/masterspike52/reNut, credit reNut and masterspike52).

banjo-nx's tree is Renut's renderer after banjo-nx's own tools/renut_gpu_import.py: every hook names a function
by N&B's address, `BANJO_RENUT_HOOK(sub_X, fn);  // Name`. This tool copies that tree and rewrites each N&B address to
this game's address of the same Direct3D function:
  - N&B address -> name: reNut's config/renut_gpu_funcs.toml (the names banjo-nx's import used);
  - name -> SASRT address: app/config/renut_gpu_funcs.toml (this game's map, XDK 2.0.21119; how each was found is in
    its comments).
A hook whose function this game does not have (or that is N&B game code, not Direct3D) is left out: the line becomes a
comment saying so, and the game's original runs. A whole file of N&B game code (widescreen, photo capture, graphics
options) is replaced by an empty stub.

Addresses this port's own renderer hooks too (app/src outside renut_engine: the PM4 renderer's draw hooks, the native
Direct3D layer, the census) get Renut's function as `renut_native_sub_X` (BANJO_RENUT_HOOK_SHARED), which this port's
hook calls first when Renut's renderer is chosen (BANJO_RENUT_YIELD_SHARED in that hook); every other hook is a plain
dispatcher (BANJO_RENUT_HOOK: Renut's code with sasrt_renderer = "renut", the original otherwise). The list goes to
app/src/renut_engine/gpu/banjo_shared_hooks.h. The game's own non-shared hooks at an address Renut also hooks call
BANJO_RENUT_YIELD (the original) when Renut's renderer is chosen; tools/renut_gpu_retarget.py --check lists the
hooks of this port that need one.

  python tools/renut_gpu_retarget.py --banjo "D:/Banjo kazooie port/banjo-nx" --renut "D:/Banjo kazooie port/reNut"
         [--dry-run] [--check]
Running it again gives the same tree (the copy is replaced each time; files listed in KEEP are this port's own).
"""
import argparse
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_SRC = os.path.join(ROOT, 'app', 'src')
DEST = os.path.join(APP_SRC, 'renut_engine', 'gpu')
SASRT_TOML = os.path.join(ROOT, 'app', 'config', 'renut_gpu_funcs.toml')
# This port's own files in DEST (kept across runs).
KEEP = {'sasrt_renut_layout.h'}
# N&B game code inside the renderer: an empty translation unit instead (the hooks are N&B's own functions).
STUB = {
    os.path.join('guest', 'widescreen.cpp'): 'N&B engine hooks for the aspect ratio',
    os.path.join('guest', 'photo_capture.cpp'): "N&B's photo feature",
}

TOML_RE = re.compile(r'\s*0x([0-9A-Fa-f]{8})\s*=\s*\{\s*name\s*=\s*"(\w+)"')
HOOK_RE = re.compile(r'^(?P<indent>\s*)BANJO_RENUT_HOOK(?P<kind>_SHARED)?\((?P<sub>sub_[0-9A-F]{8}),\s*(?P<fn>[^;]+?)\);'
                     r'(?P<rest>.*)$')
RAW_RE = re.compile(r'BANJO_RENUT_HOOK_RAW(?:_SHARED)?\((sub_[0-9A-F]{8})\)')
SUB_RE = re.compile(r'\b(sub_[0-9A-F]{8})\b')
CENSUS_RE = re.compile(r'^SASRT_CENSUS_HOOK(?:_SHARED)?\(([0-9A-F]{8})\)', re.M)
GAME_HOOK_RE = re.compile(r'\b(?:REX_HOOK|REX_HOOK_RAW|REX_PPC_HOOK|REX_FUNC|SASRT_[A-Z_]*HOOK[A-Z_]*)\(\s*(sub_[0-9A-F]{8})')


def load(path):
    out = {}
    for line in open(path, encoding='utf-8'):
        m = TOML_RE.match(line)
        if m:
            out['sub_' + m.group(1).upper()] = m.group(2)
    return out


def game_hooks():
    """Addresses this port hooks outside renut_engine (its own renderer, native layer, census, fixes)."""
    hooked = {}
    for base, dirs, files in os.walk(APP_SRC):
        if os.path.join('src', 'renut_engine') in base:
            continue
        for f in files:
            if not f.endswith(('.cpp', '.h')):
                continue
            path = os.path.join(base, f)
            text = open(path, encoding='utf-8', errors='replace').read()
            for m in GAME_HOOK_RE.finditer(text):
                hooked.setdefault(m.group(1), set()).add(os.path.relpath(path, ROOT))
            for m in CENSUS_RE.finditer(text):  # SASRT_CENSUS_HOOK(82CDB7C8): the address without sub_
                hooked.setdefault('sub_' + m.group(1), set()).add(os.path.relpath(path, ROOT))
    return hooked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--banjo', required=True, help='banjo-nx checkout (its app/src/renut_engine/gpu is copied)')
    ap.add_argument('--renut', required=True, help='reNut checkout (config/renut_gpu_funcs.toml: N&B names)')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--check', action='store_true', help='list the game hooks that need a BANJO_RENUT_YIELD')
    a = ap.parse_args()

    nb_names = load(os.path.join(a.renut, 'config', 'renut_gpu_funcs.toml'))  # N&B sub -> name
    ours = {name: sub for sub, name in load(SASRT_TOML).items()}               # name -> SASRT sub
    hooked = game_hooks()
    src = os.path.join(a.banjo, 'app', 'src', 'renut_engine', 'gpu')

    def target(nb_sub):
        name = nb_names.get(nb_sub)
        return (ours.get(name) if name else None), name

    shared, plain, dropped, renamed = [], [], [], {}
    out_files = {}
    for base, dirs, files in os.walk(src):
        for f in files:
            rel = os.path.relpath(os.path.join(base, f), src)
            if f == 'banjo_shared_hooks.h' or f in KEEP:
                continue
            text = open(os.path.join(base, f), encoding='utf-8', newline='').read()
            if rel in STUB:
                text = ('// sasrt-nx (tools/renut_gpu_retarget.py): banjo-nx\'s %s is N&B game code (%s); not in this '
                        'port.\n' % (rel.replace(os.sep, '/'), STUB[rel]))
                out_files[rel] = text
                continue
            if f.endswith(('.cpp', '.h', '.inl')):
                lines = text.split('\n')
                new = []
                for line in lines:
                    m = HOOK_RE.match(line)
                    if m:
                        nb_sub = m.group('sub')
                        t, name = target(nb_sub)
                        if not t:
                            dropped.append('%s %s (%s)' % (nb_sub, name or '?', rel))
                            new.append('%s// sasrt-nx: not in this game (N&B %s, %s): the original runs. %s' % (
                                m.group('indent'), nb_sub, name or 'N&B game code', line.strip()))
                            continue
                        renamed[nb_sub] = t
                        if t in hooked:
                            shared.append(t)
                            new.append('%sBANJO_RENUT_HOOK_SHARED(%s, %s);%s' % (m.group('indent'), t, m.group('fn'),
                                                                               m.group('rest')))
                        else:
                            plain.append(t)
                            new.append('%sBANJO_RENUT_HOOK(%s, %s);%s' % (m.group('indent'), t, m.group('fn'),
                                                                        m.group('rest')))
                        continue
                    new.append(line)
                text = '\n'.join(new)
                # Raw hooks of N&B game code and other N&B addresses: rewritten where the name maps, else flagged.
                for m in RAW_RE.finditer(text):
                    t, name = target(m.group(1))
                    if not t:
                        dropped.append('%s %s RAW (%s)' % (m.group(1), name or '?', rel))
            out_files[rel] = text

    # Every other reference to an N&B address (REX_EXTERN(__imp__sub_X), renut_native_sub_X, comments) the same way.
    unmapped_refs = {}
    sasrt_subs = set(ours.values())
    for rel, text in list(out_files.items()):
        def sub(m):
            s = m.group(1)
            if s in sasrt_subs:
                return s  # already this game's (a hook line rewritten above)
            t = renamed.get(s) or target(s)[0]
            if t:
                return t
            unmapped_refs.setdefault(s, set()).add(rel)
            return s
        out_files[rel] = SUB_RE.sub(sub, text)

    # This port's edits (tools/renut_patches/sasrt_edits.py): the boot key, this game's Direct3D globals, layout.
    sys.path.insert(0, os.path.join(ROOT, 'tools', 'renut_patches'))
    import sasrt_edits
    for rel, old, new in sasrt_edits.EDITS:
        rel = rel.replace('/', os.sep)
        if rel not in out_files or old not in out_files[rel]:
            print('  EDIT NOT APPLIED (banjo-nx changed the text?): %s: %s' % (rel, old.splitlines()[0][:80]))
            continue
        out_files[rel] = out_files[rel].replace(old, new)

    shared = sorted(set(shared))
    header = ['// Generated by tools/renut_gpu_retarget.py: the addresses both renderers hook. This port\'s hook there calls',
              '// renut_native_sub_X when Renut\'s renderer is chosen (banjo_renut_select.h, BANJO_RENUT_YIELD_SHARED).',
              '#pragma once', '', '#include <rex/ppc.h>', '']
    header += ['extern "C" void renut_native_%s(PPCContext& ctx, uint8_t* base);' % s for s in shared]
    out_files['banjo_shared_hooks.h'] = '\n'.join(header) + '\n'

    print('renut_gpu_retarget: %d plain hooks, %d shared with this port\'s hooks, %d left out' % (
        len(set(plain)), len(shared), len(dropped)))
    for d in dropped:
        print('  left out: ' + d)
    for s, files in sorted(unmapped_refs.items()):
        print('  N&B address still referenced: %s %s in %s' % (s, nb_names.get(s, '?'), ', '.join(sorted(files))))
    for s in shared:
        print('  shared: %s %s (this port: %s)' % (s, next((n for n, v in ours.items() if v == s), '?'),
                                                    ', '.join(sorted(hooked[s]))))
    if a.check or a.dry_run:
        return
    keep = {}
    if os.path.isdir(DEST):
        for f in KEEP:
            p = os.path.join(DEST, f)
            if os.path.exists(p):
                keep[f] = open(p, encoding='utf-8', newline='').read()
        shutil.rmtree(DEST)
    for rel, text in out_files.items():
        p = os.path.join(DEST, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, 'w', encoding='utf-8', newline='').write(text)
    # Binary and other files (shaders' host sources are text and were copied above).
    for base, dirs, files in os.walk(src):
        for f in files:
            rel = os.path.relpath(os.path.join(base, f), src)
            if rel not in out_files and f != 'banjo_shared_hooks.h' and f not in KEEP:
                os.makedirs(os.path.join(DEST, os.path.dirname(rel)), exist_ok=True)
                shutil.copy2(os.path.join(base, f), os.path.join(DEST, rel))
    for f, text in keep.items():
        open(os.path.join(DEST, f), 'w', encoding='utf-8', newline='').write(text)


if __name__ == '__main__':
    main()
