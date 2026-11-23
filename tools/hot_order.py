#!/usr/bin/env python3
"""Writes app/hot_functions.ld: the hottest functions grouped at the start of .text (passed to the Switch link with
-Wl,--section-ordering-file when SASRT_SWITCH_HOT_ORDER is on; sa2-nx's tools/hot_order.py, from nfsmw-nx's
orden_funciones.ld and tools/calientes.py).

Why: the NRO has ~60 MB of code and the Cortex-A57 has a 48 KB instruction cache and a small TLB. Hot functions
scattered across the whole image cost instruction-cache and TLB misses on every far call; grouped, the hot set spans
a few hundred KB. Only placement changes (every function already has its own section, -ffunction-sections).

Inputs (any mix, weights added up):
  --profile LOG ELF      a console profile (logs/rex/rex_profile_NNN.log, switch_profile_stacks = true) and the ELF of the
                         build that recorded it: every sampled address (pc, lr and the stack frames) adds the share of
                         samples it appeared in to its function (sa2-nx's method);
  --pc-profile LOG ELF   a PC profile (out/pc/logs/pc_profile.log, self time per function) and the Switch ELF to name
                         the sections from: the recompiled game functions keep their names on both platforms
                         (sub_XXXXXXXX), the app's own C++ functions are matched by their demangled qualified name
                         (every overload), the C runtime's memcpy/memmove/memset by name. A start until a console
                         profile of this game exists: x86 and the A57 rank the renderer's code differently.

  python tools/hot_order.py --pc-profile out/pc/logs/pc_profile.log out/nx/sasrt [--count 1500]
  python tools/hot_order.py --profile rex_profile.log out/nx/sasrt [...]

THE TRAP (nfsmw-nx): the linker places what this file lists BEFORE everything in its own script, including libnx's
start-up code. The first line inside .text must be KEEP (*(.crt0)), and every build is checked for _start at 0
(tools/check_switch_build.py).
"""
import argparse
import bisect
import collections
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEVKITA64 = next((d + '/devkitA64/bin/' for d in (os.environ.get('DEVKITPRO', ''), 'C:/devkitPro', '/opt/devkitpro')
                  if d and os.path.isdir(d + '/devkitA64/bin')), 'C:/devkitPro/devkitA64/bin/')
EXE = '.exe' if os.name == 'nt' else ''

# Assembly routines of newlib with no per-function section: named by archive member (nfsmw-nx's list).
LIBC_OBJECTS = ['memcpy', 'memmove', 'memset', 'memcmp', 'strcmp', 'strlen']
WAITING = re.compile(r'__syscall_|^svc|nanosleep|cond_wait|cond_timedwait|condvarWait|WaitProcessWideKey|'
                     r'WaitSynchronization|SleepThread')


def symbols(elf, demangle=False):
    args = [DEVKITA64 + 'aarch64-none-elf-nm' + EXE, '-n', '--defined-only'] + (['-C'] if demangle else []) + [elf]
    out = subprocess.run(args, capture_output=True, text=True, check=True).stdout
    addrs, names = [], []
    for line in out.splitlines():
        parts = line.split(None, 2)
        if len(parts) == 3 and parts[1] in 'tTwW':
            addrs.append(int(parts[0], 16))
            names.append(parts[2])
    return addrs, names


def weigh(log, elf, weight):
    addrs, names = symbols(elf)
    samples = 0
    for line in open(log, encoding='utf-8', errors='replace'):
        m = re.match(r'\s+(\d+) samples, ', line)
        if m:
            samples = int(m.group(1))
            continue
        m = re.match(r'\s+([\d.]+)%\s+(pc|lr|stack|wait) (.*)$', line)
        if not m or m.group(2) == 'wait':
            continue
        if m.group(2) == 'pc' and re.search(r' x\d+\s*$', line):
            share = float(re.search(r' x(\d+)\s*$', line).group(1))
        else:
            share = float(m.group(1)) * samples / 100.0
        frames = []
        for a in re.findall(r'image\+0x([0-9a-f]+)', m.group(3)):
            i = bisect.bisect_right(addrs, int(a, 16)) - 1
            frames.append(names[i] if i >= 0 else '??')
        # A stack whose innermost frame is a kernel wait is a sleeping thread: not hot code.
        if m.group(2) == 'stack' and frames and WAITING.search(frames[0]):
            continue
        for name in set(frames):
            weight[name] += share


def qualified(demangled):
    """`me::native::(anonymous namespace)::NativeGraphicsSystem::Type3(me::native::...) const` ->
    `me::native::(anonymous namespace)::NativeGraphicsSystem::Type3` (the parameter list and qualifiers dropped)."""
    depth, cut = 0, len(demangled)
    for i, ch in enumerate(demangled):
        if ch == '<':
            depth += 1
        elif ch == '>':
            depth -= 1
        elif ch == '(' and depth == 0 and not demangled.startswith('(anonymous namespace)', i):
            cut = i
            break
    return demangled[:cut].strip()


def weigh_pc(log, elf, weight, missing):
    """PC profile lines `    3.1%  sasrt!me::native::`anonymous namespace'::X::Y x261` (self samples per function)."""
    addrs, mangled = symbols(elf)
    _, demangled = symbols(elf, demangle=True)
    by_name = collections.defaultdict(list)
    sections = set(mangled)
    for m_name, d_name in zip(mangled, demangled):
        by_name[qualified(d_name)].append(m_name)
    for line in open(log, encoding='utf-8', errors='replace'):
        m = re.match(r'^\s+[\d.]+%\s+(\S+?)!(.+) x(\d+)$', line)
        if not m:
            continue
        module, name, count = m.group(1), m.group(2), int(m.group(3))
        if module.startswith('VCRUNTIME') or module.startswith('ucrtbase'):
            if name in LIBC_OBJECTS:
                weight['__libc_' + name] += count
            continue
        if not module.startswith('sasrt'):
            continue  # the driver, the OS, the C++ runtime: not ours to place
        name = name.replace("`anonymous namespace'", '(anonymous namespace)')
        if re.fullmatch(r'sub_[0-9A-F]{8}', name):
            found = [n for n in (name, '__imp__' + name) if n in sections]
        else:
            found = by_name.get(name, [])
        if not found:
            missing[name] += count
            continue
        for n in found:
            weight[n] += count / len(found)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--profile', nargs=2, action='append', default=[], metavar=('LOG', 'ELF'))
    ap.add_argument('--pc-profile', nargs=2, action='append', default=[], metavar=('LOG', 'ELF'))
    ap.add_argument('--count', type=int, default=1500)
    ap.add_argument('--out', default=os.path.join(ROOT, 'app', 'hot_functions.ld'))
    a = ap.parse_args()
    if not a.profile and not a.pc_profile:
        ap.error('give --profile and/or --pc-profile')
    weight = collections.Counter()
    missing = collections.Counter()
    for log, elf in a.profile:
        weigh(log, elf, weight)
    for log, elf in a.pc_profile:
        weigh_pc(log, elf, weight, missing)
    for n in LIBC_OBJECTS:
        weight.pop('__libc_' + n, None)
        weight.pop(n, None)
    libc = list(LIBC_OBJECTS)
    # Functions without their own section or that must not move: the start-up code is placed first explicitly.
    for skip in ('_start', '__libnx_init', '??'):
        weight.pop(skip, None)
    hot = [n for n, _ in weight.most_common(a.count)]
    sources = [os.path.basename(p[0]) for p in a.profile] + [os.path.basename(p[0]) + ' (PC)' for p in a.pc_profile]
    kind = 'console stack sampling' if a.profile else 'a PC profile (self time; names mapped to the Switch ELF)'
    lines = ['/*',
             f' * Hot functions grouped at the start of .text ({len(hot)} of them, hottest first), from {kind}.',
             ' * Generated by tools/hot_order.py from ' + ', '.join(sources) + '.',
             ' * The start-up code must stay first (nfsmw-nx: memcpy at address 0 made the NRO unbootable).',
             ' */',
             '.text : {',
             '  KEEP (*(.crt0))',
             '  /* newlib assembly routines without their own section: by archive member */']
    lines += [f'  *libc.a:libc_a-{n}.o(.text .text.*)' for n in libc]
    # sasrt-nx (2026-11-11, batch B4): with PGO the hot functions' sections are .text.hot.<name>; both forms listed
    lines += [f'  *(.text.{n} .text.hot.{n})' for n in hot]
    lines.append('}')
    with open(a.out, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines) + '\n')
    guest = sum(1 for n in hot if 'sub_8' in n)
    print(f'{a.out}: {len(hot)} functions ({guest} recompiled game functions); hottest: {hot[:6]}')
    if missing:
        print(f'not found in the ELF (inlined there, or PC-only): {len(missing)} names, '
              f'{sum(missing.values())} samples; top: {[n for n, _ in missing.most_common(5)]}')


if __name__ == '__main__':
    main()
