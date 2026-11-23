#!/usr/bin/env python3
"""Checks a Switch build before it goes on the SD card (tools/win/build_switch_package.ps1 runs it on the ELF,
tools/win/package_switch.ps1 runs --flavour-only on the NRO it copies).

  - the codegen flavour the build names in its first "[enhancements]" log line must be "optimised codegen": the SD card
    gets one NRO, the optimised codegen (the user's rule of 2026-10-06, no classic / optimised A/B pair; features are
    compared through sasrt.toml keys and the premade configs). A classic build is for diagnosis on the PC only;
  - branch-to-self instructions in recompiled functions (tools/find_self_loops.py): a guest poll GCC hoisted out of
    its loop is an infinite loop that hangs the console (futari-nx). Only the game's own halts are allowed: the four
    `b .` of the classic build, which are in the PowerPC code itself;
  - the Vulkan driver: none when REXGLUE_SWITCH_LINK_NVK is off (2026-10-20, the default); else the ELF's Mesa string
    must be the one of the NVK SDK the build folder was configured with
    (sdk/cmake/rexglue_switch.cmake links its libvulkan.a by full path; devkitPro's generic portlibs driver is another
    Mesa, which the NROs once picked up by name);
  - _start at address 0 (sa2-nx's check; nfsmw-nx: a section-ordering file that moved the start-up code made the NRO
    unbootable; app/hot_functions.ld starts with KEEP(*(.crt0)));
  - no vector fmla/fmls in recompiled functions (sa2-nx's check): the generated code has no vector fused multiply-add
    (VMX multiply-adds are a multiply and an add), so any is contraction that leaked past -ffp-contract=off (the LTO
    link repeats it). Scalar fmadd/fmsub are the guest's own (std::fma).
With LTO (SASRT_SWITCH_LTO) GCC may inline a guest halt into its caller: a function whose generated body calls a known
halt directly is accepted, and named (sa2-nx's round 7).

  python tools/check_switch_build.py out/nx/sasrt [--nvk <NVK SDK folder>]
  python tools/check_switch_build.py --flavour-only out/nx/sasrt.nro
One line per check; exit code 0 when all pass.
"""
import argparse
import collections
import glob
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import find_self_loops  # noqa: E402

FLAVOURS = ('optimised codegen', 'classic codegen', 'unknown codegen')
# The game's own infinite loops (`b .` in the PowerPC code), listed by find_self_loops.py on the classic build.
GUEST_HALTS = {'sub_82B36C30', 'sub_82D4C500', 'sub_82D4D350', 'sub_82E687D8'}
MESA = re.compile(rb'Mesa \d+\.\d+\.\d+(?:-devel)? \(git-[0-9a-f]+\)')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEVKITA64 = next((d + '/devkitA64/bin/' for d in (os.environ.get('DEVKITPRO', ''), 'C:/devkitPro', '/opt/devkitpro')
                  if d and os.path.isdir(d + '/devkitA64/bin')), 'C:/devkitPro/devkitA64/bin/')
EXE = '.exe' if os.name == 'nt' else ''


def generated_bodies(names):
    """The generated C++ bodies of the given functions (sub_XXXXXXXX), from app/generated/default."""
    out = {}
    pat = re.compile(r'^DEFINE_REX_FUNC\((sub_[0-9A-F]{8})\) \{\n(.*?)^\}\n', re.S | re.M)
    for path in glob.glob(os.path.join(ROOT, 'app', 'generated', 'default', '*_recomp.*.cpp')):
        for m in pat.finditer(open(path, encoding='utf-8', errors='replace').read()):
            if m.group(1) in names:
                out[m.group(1)] = m.group(2)
    return out


def check_flavour(data):
    found = [f for f in FLAVOURS if f.encode() in data]
    good = found == ['optimised codegen']
    print(f'flavour: {" + ".join(found) or "none named"}' + ('' if good else '  <- FAIL: must be the optimised codegen'))
    return good


def check_self_loops(elf):
    found = find_self_loops.scan(elf)
    guest = {}
    for name, hits in found.items():
        m = re.search(r'sub_[0-9A-Fa-f]{8}', name)
        if m:
            guest.setdefault(m.group(0).upper().replace('SUB_', 'sub_'), []).extend(hits)
    unknown = sorted(n for n in guest if n not in GUEST_HALTS)
    inlined = []
    if unknown:  # a known halt GCC inlined into its caller (LTO): the caller's generated body calls it directly
        bodies = generated_bodies(set(unknown))
        for f in list(unknown):
            calls = set(re.findall(r'\b(?:__imp__)?(sub_[0-9A-F]{8})\(ctx, base\)', bodies.get(f, '')))
            if calls & GUEST_HALTS:
                inlined.append(f'{f} (inlines {", ".join(sorted(calls & GUEST_HALTS))})')
                unknown.remove(f)
    print(f'self loops: {sum(len(v) for v in found.values())} self-branches, {len(guest)} in recompiled functions '
          f'({", ".join(sorted(guest)) or "none"})'
          + (f'; {len(inlined)} calling a known halt GCC inlined: {"; ".join(inlined)}' if inlined else '')
          + (f'  <- FAIL: not a known guest halt: {", ".join(unknown)}' if unknown else ''))
    return not unknown


def check_start(elf):
    nm = subprocess.run([DEVKITA64 + 'aarch64-none-elf-nm' + EXE, elf], capture_output=True, text=True).stdout
    start = next((int(l.split()[0], 16) for l in nm.splitlines() if l.endswith(' _start')), None)
    good = start == 0
    print((f'_start at {start:#x}' if start is not None else '_start not found') +
          ('' if good else '  <- FAIL: the start-up code must be at address 0 (app/hot_functions.ld: KEEP(*(.crt0)))'))
    return good


def check_vector_fma(elf):
    """One streaming pass over the disassembly: fused multiply-adds in the recompiled functions."""
    proc = subprocess.Popen([DEVKITA64 + 'aarch64-none-elf-objdump' + EXE, '-d', '--no-show-raw-insn', elf],
                            stdout=subprocess.PIPE, text=True, errors='replace', bufsize=1 << 20)
    func = None
    vector = collections.Counter()
    scalar = 0
    lookups = two_register = 0
    self_indexed = collections.Counter()
    one = re.compile(r'\{(v\d+)\.16b\}, (v\d+)\.16b')
    two = re.compile(r'\{(v\d+)\.16b-(v\d+)\.16b\}, (v\d+)\.16b')
    head = re.compile(r'^[0-9a-f]+ <([^>]+)>:$')
    ins = re.compile(r'^\s+[0-9a-f]+:\s+(\S+)')
    for line in proc.stdout:
        m = head.match(line)
        if m:
            func = m.group(1)
            continue
        m = ins.match(line)
        if not m or not func or not func.startswith(('sub_8', '__imp__sub_8')):
            continue
        op = m.group(1)
        if op in ('fmla', 'fmls'):
            vector[func] += 1
        elif op in ('fmadd', 'fmsub', 'fnmadd', 'fnmsub'):
            scalar += 1
        elif op in ('tbl', 'tbx'):
            # peggle2-nx's tell-tale of GCC's early register allocation fault: a table lookup indexed by its own
            # table. No generated statement permutes a vector by itself.
            lookups += 1
            m2 = two.search(line)
            m1 = None if m2 else one.search(line)
            two_register += 1 if m2 else 0
            if (m2 and m2.group(3) in (m2.group(1), m2.group(2))) or (m1 and m1.group(1) == m1.group(2)):
                self_indexed[func] += 1
    proc.wait()
    print(f'table lookups in recompiled functions: {lookups} ({two_register} two-register), indexed by their own table: '
          f'{sum(self_indexed.values())}'
          + ('' if not self_indexed else '  <- FAIL (GCC early_ra? see app/CMakeLists.txt): ' +
             ', '.join(f'{k} x{v}' for k, v in self_indexed.most_common(10))))
    good = not vector and not self_indexed
    print(f'fused multiply-adds in recompiled functions: scalar {scalar} (the guest\'s own), vector '
          f'{sum(vector.values())} in {len(vector)} functions'
          + ('' if good else '  <- FAIL (contraction leaked): ' + ', '.join(f'{k} x{v}' for k, v in
                                                                        vector.most_common(10))))
    return good


def check_early_ra(elf):
    """Every C and C++ compile statement of the build tree, and the link of the program, carries -mearly-ra=none
    (app/CMakeLists.txt: GCC 16.1's AArch64 early register allocation pass loses table lookups; peggle2-nx's console
    finding)."""
    ninja = os.path.join(os.path.dirname(os.path.abspath(elf)), 'build.ninja')
    if not os.path.isfile(ninja):
        print('early register allocation: no build.ninja next to the ELF, not checked')
        return True
    lines = open(ninja, encoding='utf-8', errors='replace').read().split('\n')
    compiles = missing = 0
    examples = []
    link_ok = None
    for i, line in enumerate(lines):
        m = re.match(r'build (\S+): (C|CXX)_COMPILER__', line)
        link = re.match(r'build (\S+): CXX_EXECUTABLE_LINKER__', line)
        if not m and not link:
            continue
        flags = ''
        for following in lines[i + 1:i + 16]:
            if not following.startswith('  '):
                break
            if following.startswith(('  FLAGS = ', '  LINK_FLAGS = ')):
                flags += following
        has = '-mearly-ra=none' in flags
        if m:
            compiles += 1
            if not has:
                missing += 1
                if len(examples) < 3:
                    examples.append(m.group(1))
        elif link_ok is None or not has:
            link_ok = has
    good = compiles > 0 and missing == 0 and link_ok is not False
    print(f'early register allocation off (-mearly-ra=none): {compiles - missing} of {compiles} compile statements, '
          f'the link {"has it" if link_ok else "LACKS IT" if link_ok is False else "not found"}'
          + ('' if good else '  <- FAIL: ' + ', '.join(examples)))
    return good


def nvk_from_cache(elf):
    cache = os.path.join(os.path.dirname(os.path.abspath(elf)), 'CMakeCache.txt')
    if os.path.exists(cache):
        for line in open(cache, encoding='utf-8', errors='replace'):
            if line.startswith('REXGLUE_SWITCH_NVK_SDK:'):
                return line.split('=', 1)[1].strip()
    return None


def links_nvk(elf):
    # sasrt-nx (2026-10-20): REXGLUE_SWITCH_LINK_NVK (sdk/cmake/rexglue_switch.cmake), off by default: no Vulkan driver.
    cache = os.path.join(os.path.dirname(os.path.abspath(elf)), 'CMakeCache.txt')
    if os.path.exists(cache):
        for line in open(cache, encoding='utf-8', errors='replace'):
            if line.startswith('REXGLUE_SWITCH_LINK_NVK:'):
                return line.split('=', 1)[1].strip().upper() in ('ON', 'TRUE', '1', 'YES')
    return False


def check_driver(elf, data, nvk):
    if not links_nvk(elf):
        have = set(MESA.findall(data))
        good = not have
        print('driver: none (REXGLUE_SWITCH_LINK_NVK off: the native deko3d renderer)' +
              ('' if good else '  <- FAIL: a Mesa driver is in it: ' + ', '.join(sorted(x.decode() for x in have))))
        return good
    nvk = nvk or nvk_from_cache(elf)
    lib = os.path.join(nvk, 'lib', 'libvulkan.a') if nvk else None
    want = set(MESA.findall(open(lib, 'rb').read())) if lib and os.path.exists(lib) else set()
    have = set(MESA.findall(data))
    good = bool(want) and have == want
    names = lambda s: ', '.join(sorted(x.decode() for x in s)) or 'none'  # noqa: E731
    print(f'driver: {names(have)}' + ('' if good else f'  <- FAIL: the NVK SDK has {names(want)} ({lib})'))
    return good


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('binary', help='the Switch ELF (out/nx/sasrt), or the NRO with --flavour-only')
    ap.add_argument('--nvk', help="NVK SDK folder (default: the build folder's CMakeCache.txt)")
    ap.add_argument('--flavour-only', action='store_true', help='only the codegen flavour (works on an NRO)')
    args = ap.parse_args()
    data = open(args.binary, 'rb').read()
    ok = check_flavour(data)
    if not args.flavour_only:
        ok = check_self_loops(args.binary) and ok
        ok = check_driver(args.binary, data, args.nvk) and ok
        ok = check_start(args.binary) and ok
        ok = check_vector_fma(args.binary) and ok
        ok = check_early_ra(args.binary) and ok
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
