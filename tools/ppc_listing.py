#!/usr/bin/env python3
"""The PowerPC listing of recompiled functions, from the comments the generator writes into app/generated/default.

  python tools/ppc_listing.py sub_82CD18D0                 one function's instructions (thunks followed)
  python tools/ppc_listing.py --grep 'stw r\\d+,52\\(r' --range 82CC0000 82CF0000
                                                           functions in an address range with a matching instruction

Each generated function is `DEFINE_REX_FUNC(sub_XXXXXXXX) { ... }` with one `// <instruction>` comment per PowerPC
instruction. A thunk (lis r11 / addi r11 / mtctr / bctr) is followed to its target with --follow (on by default for a
single function).
"""
import argparse
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(ROOT, 'app', 'generated', 'default')
START = re.compile(r'^DEFINE_REX_FUNC\((sub_[0-9A-F]{8})\)')
COMMENT = re.compile(r'^\s*// (.*)$')


def load():
    funcs = {}
    for path in sorted(glob.glob(os.path.join(GEN, 'sasrt_recomp.*.cpp'))):
        name, body = None, []
        for line in open(path, encoding='utf-8', errors='replace'):
            m = START.match(line)
            if m:
                name, body = m.group(1), []
                continue
            if name is None:
                continue
            if line.startswith('}'):
                funcs[name] = body
                name = None
                continue
            c = COMMENT.match(line)
            if c:
                body.append(c.group(1).strip())
    return funcs


def thunk_target(body):
    if len(body) == 4 and body[2] == 'mtctr r11' and body[3].startswith('bctr'):
        hi = re.match(r'lis r11,(-?\d+)', body[0])
        lo = re.match(r'addi r11,r11,(-?\d+)', body[1])
        if hi and lo:
            return 'sub_%08X' % (((int(hi.group(1)) << 16) + int(lo.group(1))) & 0xFFFFFFFF)
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('function', nargs='?')
    ap.add_argument('--grep')
    ap.add_argument('--range', nargs=2)
    ap.add_argument('--no-follow', action='store_true')
    a = ap.parse_args()
    funcs = load()
    if a.function:
        name = a.function if a.function.startswith('sub_') else 'sub_' + a.function.upper()
        seen = set()
        while not a.no_follow and name in funcs and thunk_target(funcs[name]) and name not in seen:
            seen.add(name)
            print(f'{name}: thunk to {thunk_target(funcs[name])}')
            name = thunk_target(funcs[name])
        if name not in funcs:
            sys.exit(f'{name} not found')
        print(f'== {name} ({len(funcs[name])} instructions)')
        for i, ins in enumerate(funcs[name]):
            print(f'{i:5d}  {ins}')
        return
    pattern = re.compile(a.grep)
    lo, hi = (int(a.range[0], 16), int(a.range[1], 16)) if a.range else (0, 0xFFFFFFFF)
    for name in sorted(funcs):
        if not lo <= int(name[4:], 16) < hi:
            continue
        hits = [ins for ins in funcs[name] if pattern.search(ins)]
        if hits:
            print(f'{name} ({len(funcs[name])}): ' + ' | '.join(hits[:6]))


if __name__ == '__main__':
    main()
