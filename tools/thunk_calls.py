#!/usr/bin/env python3
"""Calls through the .xidata jump thunks go straight to their target (post-codegen step of the "optimised" codegen
flavour; docs/enhancements.md, "Build-time").

Sonic & All-Stars Racing Transformed calls almost every function through a 16-byte jump thunk in .xidata
(`lis r11,hi; addi r11,r11,lo; mtctr r11; bctr`; app/thunks.toml, tools/thunk_table.py): in the generated code
159,419 call sites name a thunk and 2,248 name a function. The generator writes each thunk as a function that loads
its constant target into r11 and ctr and calls REX_CALL_INDIRECT_FUNC, i.e. a bounds check, a load from the dispatch
table and an indirect call, after the call to the thunk itself. This step:

  - in every thunk whose target is a function of this module, replaces REX_CALL_INDIRECT_FUNC with a direct call of
    that function (sub_X), for the calls that still reach the thunk through a pointer (vtables);
  - at every call site of such a thunk, replaces `sub_T(ctx, base);` with what the thunk does:
    `ctx.r11.s64 = X; ctx.ctr.u64 = ctx.r11.u64; sub_X(ctx, base);`.
  With non_argument_as_local and ctr_as_local the thunk's r11 and ctr are its own locals, which it publishes in ctx for
  its target; when the target reads neither ctx.r11 nor ctx.ctr (none does in this game: only share_registers and
  non_argument_as_local_keep functions could), the body and every call site are the plain call `sub_X(ctx, base);`.

Why it is exact: the thunk only sets r11 and ctr to its target and branches there without linking, so the target
runs with the same context and returns to the same caller. The dispatch table entry of X is sub_X itself (the
generated init table), and a hook on X (REX_HOOK_RAW) replaces the symbol sub_X, which the direct call names too.
Thunks named in the sources (hooks) and targets that are not functions of this module are left alone.

Run it BEFORE tools/direct_calls.py (which then makes the new sub_X calls direct when X has no hook). Idempotent.
The newly named functions are declared in each file's <project>_funcs.N.h.

  python tools/thunk_calls.py [--gen <generated folder>] [--dry-run] [--check]
    --check: exit 1 if thunk call sites are left that this step would rewrite.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import direct_calls  # noqa: E402  (the same "hooked" rule: any 82xxxxxx address in the sources)

GEN = os.path.join(ROOT, 'app', 'generated', 'default')

# A thunk as the generator writes it. Classic flavour: ctr lives in ctx, the jump is REX_CALL_INDIRECT_FUNC(ctx.ctr.u32).
# Optimised flavour (ctr_as_local): ctr is a local, and the generator publishes it in ctx.ctr for the callee during the
# call and restores ctx.ctr afterwards ({ const auto s_ctr = ctx.ctr; ctx.ctr = ctr; ...; ctx.ctr = s_ctr; }).
# With non_argument_as_local r11 is a local of the thunk too (`r11.s64 = ...`), and the generator publishes it in ctx.r11
# for the indirect call as it does ctr ({ const auto s_r11 = ctx.r11; ctx.r11 = r11; ...; ctx.r11 = s_r11; }). Only a
# function that keeps r11 in ctx (share_registers, non_argument_as_local_keep) can read ctx.r11, and with ctr_as_local
# no function reads ctx.ctr at all except to publish or restore it (r11_in_ctx / ctr_in_ctx below find the readers).
# A call site of such a thunk is then the plain call `sub_X(ctx, base);` (tools/direct_calls.py makes it direct: three
# loads and stores of ctx fewer per call, and a callee the compiler can inline); when its target does read one of
# them, the site publishes both for the call as the thunk does. A thunk in non_argument_as_local_keep keeps r11 in ctx
# itself (the first form).
THUNK = re.compile(
    r'DEFINE_REX_FUNC\(sub_(?P<thunk>[0-9A-F]{8})\) \{\n'
    r'\tREX_FUNC_PROLOGUE\(\);\n'
    r'(?:\tPPCRegister (?:ctr|r11)\{\};\n)*'
    r'\t// lis r11,-?\d+\n'
    r'\t(?P<r11ctx>(?:ctx\.)?)r11\.s64 = (?P<hi>-?\d+);\n'
    r'\t// addi r11,r11,-?\d+\n'
    r'\t(?P=r11ctx)r11\.s64 = (?P=r11ctx)r11\.s64 \+ (?P<lo>-?\d+);\n'
    r'\t// mtctr r11\n'
    r'\t(?:ctx\.)?ctr\.u64 = (?P=r11ctx)r11\.u64;\n'
    r'\t// bctr \n'
    r'(?P<publish>\t\{\n(?P<pub11>\t\tconst auto s_r11 = ctx\.r11; ctx\.r11 = r11;\n)?'
    r'\t\tconst auto s_ctr = ctx\.ctr; ctx\.ctr = ctr;\n\t)?'
    r'\t(?P<call>REX_CALL_INDIRECT_FUNC\((?:ctx\.)?ctr\.u32\);|(?:__imp__)?sub_[0-9A-F]{8}\(ctx, base\);)\n'
    r'(?(publish)(?(pub11)\t\tctx\.r11 = s_r11;\n)\t\tctx\.ctr = s_ctr;\n\t\}\n)'
    r'\treturn;\n'
    r'\}')
TABLE = re.compile(r'\{ 0x([0-9A-F]{8}), sub_\1 \}')
CALL = re.compile(r'(?<![\w])(?:__imp__)?sub_([0-9A-F]{8})\(ctx, base\);')
FUNC = re.compile(r'^DEFINE_REX_FUNC\(sub_([0-9A-F]{8})\) \{\n(.*?)^\}\n', re.S | re.M)
# The generator's hand-over of a localized r11 around a call (and its restore); not a use of ctx.r11 by the function.
R11_HANDOVER = re.compile(r'^\s*(?:const auto s_r11 = ctx\.r11; ctx\.r11 = r11;|r11 = ctx\.r11;|ctx\.r11 = s_r11;)\s*$')


CTR_PUBLISH = re.compile(r'^\s*(?:const auto s_ctr = ctx\.ctr; ctx\.ctr = ctr;|ctx\.ctr = s_ctr;)\s*$')


def ctr_in_ctx(texts):
    """Functions that read or write ctx.ctr other than in the generator's publish around an indirect call or a call
    site this step rewrote. With ctr_as_local the generator keeps ctr in a local everywhere: none in this game."""
    out = set()
    for text in texts.values():
        for m in FUNC.finditer(text):
            for ln in m.group(2).split('\n'):
                t = ln.strip()
                if 'ctx.ctr' not in t or t.startswith('//') or CTR_PUBLISH.match(t):
                    continue
                if 's_ctr' in t and '(ctx, base);' in t:  # a call site this step rewrote (idempotent re-runs)
                    continue
                out.add(m.group(1))
                break
    return out


def r11_in_ctx(texts):
    """Functions that keep r11 in ctx: they use ctx.r11 other than in a hand-over (share_registers functions,
    non_argument_as_local_keep entries, the save/restore helpers; every function without non_argument_as_local)."""
    out = set()
    for text in texts.values():
        for m in FUNC.finditer(text):
            for ln in m.group(2).split('\n'):
                t = ln.strip()
                if 'ctx.r11' not in t or t.startswith('//') or R11_HANDOVER.match(t):
                    continue
                if 's_ctr' in t and '(ctx, base);' in t:  # a call site this step rewrote (idempotent re-runs)
                    continue
                out.add(m.group(1))
                break
    return out


def s32(value):
    value &= 0xFFFFFFFF
    return value - (1 << 32) if value & 0x80000000 else value


def main():
    gen = sys.argv[sys.argv.index('--gen') + 1] if '--gen' in sys.argv else GEN
    dry = '--dry-run' in sys.argv or '--check' in sys.argv
    check = '--check' in sys.argv
    files = sorted(f for f in os.listdir(gen) if re.match(r'\w+_recomp\.\d+\.cpp$', f))
    inits = [f for f in os.listdir(gen) if re.match(r'\w+_init\.cpp$', f)]
    if not files or not inits:
        sys.exit('ERROR (post-codegen patch): thunk_calls: no *_recomp.N.cpp / *_init.cpp in %s' % gen)
    functions = set()
    for f in inits:
        functions.update(TABLE.findall(open(os.path.join(gen, f), encoding='utf-8').read()))
    hooked = direct_calls.hooked()

    texts = {f: open(os.path.join(gen, f), encoding='utf-8').read() for f in files}
    # Thunk -> target, for the thunks this step may use.
    targets = {}
    for text in texts.values():
        for m in THUNK.finditer(text):
            thunk = m.group('thunk')
            target = '%08X' % ((int(m.group('hi')) + int(m.group('lo'))) & 0xFFFFFFFF)
            if target in functions and 'sub_' + thunk not in hooked and target != thunk:
                targets[thunk] = (target, m.group('publish') is not None, m.group('r11ctx') != '')
    if not targets:
        sys.exit('ERROR (post-codegen patch): thunk_calls: no thunk found; the generated thunk shape changed')
    localized = any(not e[2] for e in targets.values())
    keeps_r11 = r11_in_ctx(texts) if localized else set()
    keeps_ctr = ctr_in_ctx(texts) if localized else set()

    bodies = sites = changed_files = 0
    plain = [0]
    for f in files:
        text = texts[f]
        new_names = set()

        def body(m):
            nonlocal bodies
            entry = targets.get(m.group('thunk'))
            if not entry:
                return m.group(0)
            target, publish, r11_in_ctx = entry
            if publish and not r11_in_ctx and target not in keeps_r11 and target not in keeps_ctr:
                # Reached through a pointer (vtables): the plain call, as at the call sites (the r11 and ctr locals
                # the body still computes are dead).
                text0 = m.group(0)
                head = text0[:text0.index('\t// bctr \n') + len('\t// bctr \n')]
                new = head + '\tsub_%s(ctx, base);\n\treturn;\n}' % target
                if new != text0:
                    bodies += 1
                    new_names.add(target)
                return new
            if not m.group('call').startswith('REX_CALL_INDIRECT_FUNC'):
                return m.group(0)
            bodies += 1
            new_names.add(target)
            return m.group(0).replace(m.group('call'), 'sub_%s(ctx, base);' % target)

        text = THUNK.sub(body, text)

        def site(m):
            nonlocal sites
            entry = targets.get(m.group(1))
            if not entry:
                return m.group(0)
            target, publish, r11_in_ctx = entry
            sites += 1
            new_names.add(target)
            if publish and not r11_in_ctx:  # non_argument_as_local: the thunk's r11 is its own local
                value = s32(int(target, 16))
                if target in keeps_r11 or target in keeps_ctr:  # it may read them: published, as the thunk does
                    return ('{ const auto s_r11 = ctx.r11; ctx.r11.s64 = %d; const auto s_ctr = ctx.ctr; '
                            'ctx.ctr.s64 = %d; sub_%s(ctx, base); ctx.r11 = s_r11; ctx.ctr = s_ctr; }' %
                            (value, value, target))
                plain[0] += 1
                return 'sub_%s(ctx, base);' % target
            if publish:  # what the optimised thunk does: ctx.ctr = target for the call only
                return ('ctx.r11.s64 = %d; { const auto s_ctr = ctx.ctr; ctx.ctr.u64 = ctx.r11.u64; '
                        'sub_%s(ctx, base); ctx.ctr = s_ctr; }' % (s32(int(target, 16)), target))
            return 'ctx.r11.s64 = %d; ctx.ctr.u64 = ctx.r11.u64; sub_%s(ctx, base);' % (s32(int(target, 16)), target)

        # Call sites only outside the thunk bodies (a rewritten body already calls its target).
        parts = []
        last = 0
        for m in THUNK.finditer(text):
            parts.append(CALL.sub(site, text[last:m.start()]))
            parts.append(m.group(0))
            last = m.end()
        parts.append(CALL.sub(site, text[last:]))
        text = ''.join(parts)

        if text != texts[f]:
            changed_files += 1
            if not dry:
                open(os.path.join(gen, f), 'w', encoding='utf-8', newline='\n').write(text)
                header = os.path.join(gen, f.replace('_recomp.', '_funcs.').replace('.cpp', '.h'))
                declared = open(header, encoding='utf-8').read()
                missing = sorted(n for n in new_names if 'DECLARE_REX_FUNC(sub_%s);' % n not in declared)
                if missing:
                    declared = declared.rstrip('\n') + '\n' + ''.join('DECLARE_REX_FUNC(sub_%s);\n' % n
                                                                      for n in missing)
                    open(header, 'w', encoding='utf-8', newline='\n').write(declared)
    if check:
        print('thunk_calls --check: %d thunk bodies and %d call sites still to rewrite (%d usable thunks)' %
              (bodies, sites, len(targets)))
        sys.exit(1 if bodies or sites else 0)
    print('thunk_calls%s: %d thunks usable (%d hooked addresses respected); %d thunk bodies and %d call sites '
          'rewritten in %d files (%d as plain calls; functions reading ctx.r11 %d, ctx.ctr %d)' %
          (' (dry-run)' if dry else '', len(targets), len(hooked), bodies, sites, changed_files, plain[0],
           len(keeps_r11), len(keeps_ctr)))


if __name__ == '__main__':
    main()
