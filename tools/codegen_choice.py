#!/usr/bin/env python3
"""Per-function choices for the codegen steps whose gain depends on the function (sasrt-nx, 2026-10-19; banjo-nx's
method: its out/cpu_proposals/cc.py and tools/locals_choice.py, here as one tool).

A step like tools/r1_local.py (guest r1 as a local mirror) or tools/lr_preserve.py (link-register write-backs that
compile to nothing) is exact in every function, but whether the compiled A57 code gets cheaper depends on the
function: a local wants a host register, and where too many are live GCC spills. banjo-nx measured r1 as a local a
loss over every function together (+0.33 %) and a gain on a per-function choice (-0.41 %). So the steps take a list,
made here from the compiled code:

  form A  every generated file as the Switch build compiles it (its own command line from build.ninja; -flto taken
          out so the object holds machine code, the defines of the CMake switches as they are ON);
  form B  the same file with the step's switch back (-DREX_R1_LOCAL_OFF, -DREX_LR_WRITE_SAME_OFF, ...);
per function (objdump -dr, tools/locals_choice.py's costs): instructions, memory operations, stack traffic and the
loop-weighted cost sum(w * (1 + is_mem)), w = 10 inside a cycle of the function's control-flow graph, 1 elsewhere,
code reached only after a call of ppc_trap left out. Static counts of the compiled code, not run-time samples.

Experiments (--experiment):
  r1       functions with REX_R1_LOCAL(): chosen when A (the mirror) is cheaper than B -> app/config/r1_local_choice.json
  lr       functions with REX_LR_WRITE_SAME(: chosen when A is not dearer than B -> app/config/lr_write_same_choice.json
  locals   functions with loop / leaf locals: listed when B (no locals) is cheaper by more than --threshold % of A ->
           app/config/locals_optout.txt (the same rule and format as tools/locals_choice.py)
  vecvalue functions with loop / leaf locals: B without -DREX_VECTOR_LOCALS_BY_VALUE (vector locals as references):
           a report only (the define is global)

  python tools/codegen_choice.py --gen <COPY of app/generated/default> --ninja out/nx/build.ninja --out <dir>
                                 --experiment r1 [--jobs 6] [--threshold 2] [--files 0,5]
Form A objects are kept in <out>/objA and reused by the next experiment while their source is older.
"""
import argparse
import concurrent.futures
import datetime
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import locals_choice as lc  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUNC = re.compile(r'^DEFINE_REX_FUNC\((\w+)\) \{$')
LTO = re.compile(r'^-flto(=.*)?$|^-fno-fat-lto-objects$|^-ffat-lto-objects$')
# The defines of the CMake switches that are ON in the build (app/CMakeLists.txt): only this one adds a define.
FORM_A = ['-DREX_VECTOR_LOCALS_BY_VALUE']
EXPERIMENTS = {
    'r1': (['-DREX_R1_LOCAL_OFF'], re.compile(r'\bREX_R1_LOCAL\(\)')),
    'lr': (['-DREX_LR_WRITE_SAME_OFF'], re.compile(r'\bREX_LR_WRITE_SAME\(')),
    'locals': (['-DREX_LOOP_LOCALS_OFF', '-DREX_LEAF_LOCALS_OFF'], re.compile(r'\bREX_(?:LOOP|LEAF)_LOCAL\(')),
    'vecvalue': (['-UREX_VECTOR_LOCALS_BY_VALUE'], re.compile(r'\bREX_(?:LOOP|LEAF)_LOCAL\(PPCVRegister,')),
}


def marked_functions(path, marker):
    """{name} of the functions of a generated file whose body matches the experiment's marker."""
    out = set()
    lines = open(path, encoding='utf-8').read().split('\n')
    i = 0
    while i < len(lines):
        m = FUNC.match(lines[i])
        if not m:
            i += 1
            continue
        j = i + 1
        while j < len(lines) and lines[j] != '}':
            j += 1
        if any(marker.search(l) for l in lines[i + 1:j]):
            out.add(m.group(1))
        i = j + 1
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--gen', required=True)
    ap.add_argument('--ninja', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--experiment', required=True, choices=sorted(EXPERIMENTS))
    ap.add_argument('--jobs', type=int, default=6)
    ap.add_argument('--threshold', type=float, default=2.0)
    ap.add_argument('--files')
    ap.add_argument('--write', help='write the choice list here (default: only into --out)')
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    gen = os.path.abspath(a.gen)
    defs_b, marker = EXPERIMENTS[a.experiment]
    for d in ('objA', 'obj_' + a.experiment):
        os.makedirs(os.path.join(out, d), exist_ok=True)
    cmd, prefix, orig_gen, _ = lc.compile_command(a.ninja, gen, out)
    cmd = [c for c in cmd if not LTO.match(c)]
    if os.path.normcase(os.path.abspath(orig_gen)) == os.path.normcase(gen):
        print('codegen_choice: WARNING: --gen is the build\'s own generated folder, not a copy')
    files = sorted((int(lc.TU.search(f).group(2)), f) for f in os.listdir(gen)
                   if lc.TU.search(f) and lc.TU.search(f).group(1) == prefix)
    if a.files:
        want = {int(x) for x in a.files.split(',')}
        files = [(n, f) for n, f in files if n in want]
    marked = {}
    for n, f in files:
        names = marked_functions(os.path.join(gen, f), marker)
        if names:
            marked[n] = names
    print('codegen_choice %s: %d functions in %d of %d files' % (
        a.experiment, sum(len(v) for v in marked.values()), len(marked), len(files)))
    print('  form A: %s' % subprocess.list2cmdline(cmd + FORM_A + ['-o', '<obj>', '-c', '<file>']))
    print('  form B: A %s' % ' '.join(defs_b))

    # The compiler's temporary files on D: (the user's rule: the system drive is not this port's scratch; a run of
    # 2026-10-19 failed when C: ran full).
    tmp = os.path.join(ROOT, 'out', 'tmp')
    os.makedirs(tmp, exist_ok=True)
    env = dict(os.environ, TMP=tmp, TEMP=tmp, TMPDIR=tmp)

    def compile_form(src, obj, extra):
        if os.path.exists(obj) and os.path.getmtime(obj) > os.path.getmtime(src):
            return
        p = subprocess.run(cmd + extra + ['-o', obj, '-c', src], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, encoding='utf-8', errors='replace', env=env)
        if p.returncode:
            raise RuntimeError('compile %s:\n%s' % (src, p.stdout[-4000:]))

    def build(n):
        src = os.path.join(gen, '%s_recomp.%d.cpp' % (prefix, n))
        obj_a = os.path.join(out, 'objA', '%d.o' % n)
        obj_b = os.path.join(out, 'obj_' + a.experiment, '%d.o' % n)
        compile_form(src, obj_a, FORM_A)
        compile_form(src, obj_b, FORM_A + defs_b)
        return n, lc.function_costs(obj_a, 'cfg'), lc.function_costs(obj_b, 'cfg')

    results = {}
    start = datetime.datetime.now()
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.jobs) as ex:
        for k, fut in enumerate(concurrent.futures.as_completed([ex.submit(build, n) for n in sorted(marked)])):
            n, ca, cb = fut.result()
            results[n] = (ca, cb)
            if (k + 1) % 10 == 0 or k + 1 == len(marked):
                print('  %d / %d files (%s)' % (k + 1, len(marked), str(datetime.datetime.now() - start)[:7]),
                      flush=True)
    rows = []
    for n, (ca, cb) in results.items():
        for name in marked[n]:
            if name in ca and name in cb:
                rows.append((name, n, ca[name], cb[name]))
    # Columns of locals_choice's costs: 0 instructions, 1 loads, 2 stores, 3 sp loads, 4 sp stores, 6 the
    # loop-weighted cost (cfg loops).
    tot_a = sum(r[2][6] for r in rows)
    tot_b = sum(r[3][6] for r in rows)
    ins_a = sum(r[2][0] for r in rows)
    ins_b = sum(r[3][0] for r in rows)
    sp_a = sum(r[2][3] + r[2][4] for r in rows)
    sp_b = sum(r[3][3] + r[3][4] for r in rows)
    lines = ['codegen_choice %s, %s: %d functions compared' % (a.experiment, datetime.date.today().isoformat(),
                                                                len(rows)),
             'form A (as built) / form B (%s): loop-weighted cost %d / %d (A - B = %+d, %+.2f %% of B); '
             'instructions %d / %d; sp loads+stores %d / %d' % (' '.join(defs_b), tot_a, tot_b, tot_a - tot_b,
                                                               100.0 * (tot_a - tot_b) / tot_b if tot_b else 0,
                                                               ins_a, ins_b, sp_a, sp_b)]
    choice = None
    if a.experiment in ('r1', 'lr'):
        # The step stays where form A is cheaper (r1: strictly; lr: not dearer, since it only removes statements).
        keep = [r for r in rows if (r[2][6] < r[3][6] if a.experiment == 'r1' else r[2][6] <= r[3][6])]
        drop = [r for r in rows if r not in keep]
        chosen_a = sum(r[2][6] for r in keep) + sum(r[3][6] for r in drop)
        lines.append('chosen: %d functions keep the step (A cheaper%s), %d go back; with the choice the cost is %d '
                     '(%+.2f %% of B, %+.2f %% of A)' % (
                         len(keep), '' if a.experiment == 'r1' else ' or equal', len(drop), chosen_a,
                         100.0 * (chosen_a - tot_b) / tot_b if tot_b else 0,
                         100.0 * (chosen_a - tot_a) / tot_a if tot_a else 0))
        choice = sorted(r[0] for r in keep)
        name = 'r1_local_choice.json' if a.experiment == 'r1' else 'lr_write_same_choice.json'
        json.dump(choice, open(os.path.join(out, name), 'w'), indent=0)
        if a.write:
            json.dump(choice, open(a.write, 'w'), indent=0)
            lines.append('wrote %s' % a.write)
    elif a.experiment == 'locals':
        losers = sorted((r for r in rows if r[2][6] > 0 and 100.0 * (r[2][6] - r[3][6]) / r[2][6] > a.threshold),
                        key=lambda r: r[0])
        gain = sum(r[2][6] - r[3][6] for r in losers)
        lines.append('opt-out (no locals cheaper by more than %.1f %% of the locals form): %d functions; with them '
                     'off: %d -> %d (%+.2f %%)' % (a.threshold, len(losers), tot_a, tot_a - gain,
                                                   -100.0 * gain / tot_a if tot_a else 0))
        text = ('# Guest functions whose A57 code is cheaper WITHOUT the loop / leaf locals (tools/codegen_choice.py\n'
                '# --experiment locals, %s; banjo-nx\'s tools/locals_choice.py rule: every generated file with\n'
                '# locals compiled with the Switch build\'s command line, as built and with -DREX_LOOP_LOCALS_OFF\n'
                '# -DREX_LEAF_LOCALS_OFF; listed when the off form is cheaper by more than %.1f %% of the on form\n'
                '# (loop-weighted cost). %d of %d functions. One per line: "<loop|leaf> <name>".\n'
                % (datetime.date.today().isoformat(), a.threshold, len(losers), len(rows)))
        body = []
        for r in losers:
            src = open(os.path.join(gen, '%s_recomp.%d.cpp' % (prefix, r[1])), encoding='utf-8').read()
            start_at = src.index('DEFINE_REX_FUNC(%s) {' % r[0])
            fn = src[start_at:src.index('\n}\n', start_at)]
            if 'REX_LOOP_LOCAL(' in fn:
                body.append('loop %s' % r[0])
            if 'REX_LEAF_LOCAL(' in fn:
                body.append('leaf %s' % r[0])
        open(os.path.join(out, 'locals_optout.txt'), 'w', encoding='utf-8', newline='\n').write(
            text + '\n'.join(body) + '\n')
        if a.write:
            open(a.write, 'w', encoding='utf-8', newline='\n').write(text + '\n'.join(body) + '\n')
            lines.append('wrote %s' % a.write)
    better = sorted(rows, key=lambda r: r[2][6] - r[3][6])
    lines.append('most improved by form A (cost A - B): ' + ', '.join(
        '%s %+d' % (r[0], r[2][6] - r[3][6]) for r in better[:8]))
    lines.append('most worsened by form A: ' + ', '.join(
        '%s %+d' % (r[0], r[2][6] - r[3][6]) for r in reversed(better[-8:])))
    report = '\n'.join(lines) + '\n'
    print(report, end='')
    open(os.path.join(out, 'report_%s.txt' % a.experiment), 'w', encoding='utf-8', newline='\n').write(report)
    with open(os.path.join(out, 'rows_%s.csv' % a.experiment), 'w', encoding='utf-8', newline='\n') as f:
        f.write('function,file,ins_A,ins_B,mem_A,mem_B,sp_A,sp_B,cost_A,cost_B\n')
        for name, n, ra, rb in sorted(rows):
            f.write('%s,%d,%d,%d,%d,%d,%d,%d,%d,%d\n' % (name, n, ra[0], rb[0], ra[1] + ra[2], rb[1] + rb[2],
                                                        ra[3] + ra[4], rb[3] + rb[4], ra[6], rb[6]))


if __name__ == '__main__':
    main()
