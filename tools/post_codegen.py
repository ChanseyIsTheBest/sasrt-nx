#!/usr/bin/env python3
"""The post-codegen steps of the codegen flavour, in one place (docs/enhancements.md, "Build-time"; sa2-nx's script).

Run after EVERY codegen, by tools/codegen.ps1 and by the build itself: app/CMakeLists.txt appends this script to the
generated sasrt_codegen command, because the PC build re-runs the generator on its own whenever an input changes (the
manifest, a toml, the xex, the generator binary) and that would otherwise drop the steps silently (futari-nx's
finding).

  - the flavour is read from app/codegen_flavor.toml (written by tools/codegen.ps1 -Flavor): "optimised" when it sets
    any codegen key, else "classic";
  - optimised, in this order (sa2-nx's sequence since its CPU rounds of 2026-10-12, with this port's thunk step):
      pch_no_volatile.py   guest loads and stores without volatile
      thunk_calls.py       calls through the .xidata jump thunks go straight to their target (this game)
      indirect_calls.py    every indirect call site tagged (function, ordinal); the sites of
                           app/indirect_promotions.txt as guarded direct calls. Before direct_calls.py (a promoted
                           call is a direct call like any other) and BEFORE loop_barriers.py (a loop needs no barrier
                           when every way round it passes an indirect call, and a promoted call is no longer one)
      loop_barriers.py     a compiler barrier at the loop headers that need one. REQUIRED with the plain loads: GCC
                           hoists guest polls out of loops (futari-nx's console hang)
      pch_cold_traps.py    the trap helper out of line and cold
      direct_calls.py      --redo: calls between unhooked functions become direct; a function hooked since the last
                           run is called through its hook again
      guest_cas.py         compare-and-swap without the legacy builtin's trailing `dmb ish`
      flush_mode_flow.py   --redo --image: the flush-mode checks the control flow, the callees' summaries and the
                           direct callers fix (nothing on the Switch, still tested in the PC build). After
                           direct_calls.py: a proof depends on which callees are called directly
      vec_byteswap.py, pch_neon_shuffles.py   guest vector reversal and constant shuffles as known permutations
      localize_native.py   (2026-11-08: katamari-nx's localizer, after flush_hoist.py below, as katamari-nx runs it)
                           the localized copies of app/src/cpu/hot/localized.txt and localized_bulk.txt, made from the
                           text as it stands after the steps before it; it reads the late steps' forms too (r1l,
                           REX_INL, store cards), so it can also run on a processed tree by itself
      ro_constants.py      --image: loads from the image's read-only data as constants (the PC build still loads and
                           compares). Before float_loads.py (it folds the integer form of a float load)
      float_loads.py       single-precision loads straight into a float register
      loop_locals.py       the ctx registers of a call-free loop as locals for the length of the loop
      leaf_locals.py       the ctx registers of leaf functions with loops as locals
      vperm_one_source.py  a vperm of one vector (both sources the same register) as a one-register lookup
                           (2026-10-14). Last: it matches the operand forms the locals steps write
      fp_sign_ops.py       fneg / fabs / fnabs as float operations instead of integer sign-bit operations
                           (2026-10-14; exact while the game never selects round-up / round-down)
      leaf_dead_stores.py  the leaf write-backs no caller can read, as REX_LEAF_DEAD (2026-10-14; an analysis of the
                           whole program's guest code, about a minute). After leaf_locals.py, whose stores it marks
      single_floats.py     fadds / fsubs / fmuls / fdivs / fsqrts with proven single inputs computed in float
                           (2026-10-14; a per-function analysis of the guest code)
      inline_memcalls.py   memcpy / memset calls of a constant size up to 64 bytes inline (2026-10-14)
      vec_unaligned_stores.py  stvlx / stvrx as a few stores instead of byte loops (2026-10-14)
      vec_cvt_fixed.py, vec_prefetch_line.py, vec_lvlx_splat.py, vec_shift_whole.py   (2026-11-13, the base's port 90:
                           blur-nx's CPU batch 1) right after it; fma_single.py (port 96) after vmx_float_macros.py;
                           card_groups.py, vec_dp_merge.py, vec_const_fold.py, vec_dcbz_zva.py (port 90) on the
                           copies after the last store_cards.py (vec_dcbz_zva.py --restore first of all)
    The image is out/default_image.bin, the generator's dump (REXGLUE_DUMP_IMAGE, tools/codegen.ps1 writes it).
  - a file the steps leave with the text it had keeps its time. On a processed tree thunk_calls.py rewrites the calls
    inside the promoted indirect call sites (their targets are thunks) and indirect_calls.py writes them back: the
    same text again, but 104 files with a new time, which the build then compiled again after every run of this
    script (the PC build runs it whenever the generator binary changes, which any SDK edit does).
  - both flavours: app/generated/codegen_flavor.txt (the build's name in the first "[enhancements]" log line).

  python tools/post_codegen.py
"""
import hashlib
import os
import re
import subprocess
import sys


def gen_file(gen, suffix):
    """renut-ultimate (2026-11-19, port 186; found by sasrt-nx's sync): the generator names its files after the project
    (<project>_pch.h, <project>_init.cpp, <project>_recomp.N.cpp): renut_ in the base, a port's own name otherwise."""
    for name in sorted(os.listdir(gen)):
        m = re.fullmatch(r'(\w+)_recomp\.\d+\.cpp', name)
        if m:
            return os.path.join(gen, m.group(1) + '_' + suffix)
    return os.path.join(gen, 'renut_' + suffix)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, 'app')
GEN = os.path.join(APP, 'generated')
IMAGE = os.path.join(ROOT, 'out', 'default_image.bin')
PROMOTIONS = os.path.join(APP, 'indirect_promotions.txt')
PROOFS = os.path.join(ROOT, 'out', 'codegen_proofs')  # tools/lr_preserve.py and tools/r1_preserve.py write here


def run(*args):
    result = subprocess.run([sys.executable, *args], cwd=ROOT)
    if result.returncode != 0:
        sys.exit(f'post_codegen: {os.path.basename(args[0])} failed ({result.returncode})')


def tool(name):
    return os.path.join(ROOT, 'tools', name)


def snapshot(tree):
    """path -> (hash of the content, modification time in ns) of every file of the generated tree."""
    state = {}
    for name in os.listdir(tree):
        path = os.path.join(tree, name)
        if os.path.isfile(path):
            with open(path, 'rb') as f:
                state[path] = (hashlib.sha1(f.read()).digest(), os.stat(path).st_mtime_ns)
    return state


def keep_times(before):
    """Files whose text is what it was before the steps get their old time back (see the header)."""
    kept = 0
    for path, (digest, mtime) in before.items():
        if not os.path.isfile(path) or os.stat(path).st_mtime_ns == mtime:
            continue
        with open(path, 'rb') as f:
            if hashlib.sha1(f.read()).digest() != digest:
                continue
        os.utime(path, ns=(mtime, mtime))
        kept += 1
    return kept


def main():
    flavor_toml = open(os.path.join(APP, 'codegen_flavor.toml'), encoding='utf-8').read()
    optimised = re.search(r'^\s*[a-z_]+\s*=\s*true', flavor_toml, re.M) is not None
    flavor = 'optimised' if optimised else 'classic'
    # --gen <folder>: a copy of app/generated to process instead (the idempotency test: two runs on a copy, hashed).
    gen = sys.argv[sys.argv.index('--gen') + 1] if '--gen' in sys.argv else GEN
    scratch = os.path.abspath(gen) != os.path.abspath(GEN)
    tree = os.path.join(gen, 'default')
    pch = os.path.join(tree, 'sasrt_pch.h')
    if optimised:
        if not os.path.isfile(IMAGE):
            sys.exit('post_codegen: out/default_image.bin is missing (the image dump of the code generator): run '
                     'tools\\codegen.ps1 once, it writes it (REXGLUE_DUMP_IMAGE)')
        xex = os.path.join(ROOT, 'assets', 'game_root', 'default.xex')
        if os.path.isfile(xex) and os.path.getmtime(xex) > os.path.getmtime(IMAGE):
            sys.exit('post_codegen: out/default_image.bin is older than assets/game_root/default.xex: run '
                     'tools\\codegen.ps1 (it writes the dump again)')
        # A tree this script already processed (the later steps' forms are in the text): the copies stay as they are.
        processed = any(marker in open(pch, encoding='utf-8').read()
                        for marker in ('tools/ro_constants.py', 'tools/float_loads.py', 'tools/loop_locals.py',
                                       'tools/leaf_locals.py', 'tools/vperm_one_source.py',
                                       'tools/fp_sign_ops.py', 'tools/leaf_dead_stores.py',
                                       'tools/single_floats.py', 'tools/inline_memcalls.py',
                                       'tools/vec_unaligned_stores.py'))
        before = snapshot(tree)
        os.environ.setdefault('REXSDK_DIR', os.path.join(ROOT, 'sdk'))
        # banjo-nx's late rewrites (ported 2026-10-19) change statements the analyses parse (r1l for ctx.r1,
        # REX_LR_WRITE_SAME, computed gotos, hoisted checks, inline copies, REX_VSEL): on a tree that was processed
        # before they are taken back out first, so every analysis sees the text it was written for. On a fresh codegen
        # these find nothing. (tools/dead_ctx_defs.py restores its own rewrites before it analyses.)
        # sasrt-nx (2026-10-21, sa2-nx's and banjo-nx's): the store cards were the last step: out first, on the tree and
        # the localized copies.
        # sasrt-nx (2026-11-13, base port 90; blur-nx's CPU batch 1): the DC ZVA pairs come out before the cards
        # (store_cards.py finds a dcbz by its memset, and tools/localize_native.py knows the memset's store, not
        # REX_DCBZ128), on the tree and the localized copies.
        run(tool('vec_dcbz_zva.py'), '--gen', tree, '--hot', os.path.join(gen, 'hot'), '--restore')
        run(tool('store_cards.py'), '--gen', tree, '--hot', os.path.join(gen, 'hot'), '--restore')
        run(tool('inline_leaves.py'), '--gen', tree, '--restore')
        run(tool('vsel_neon.py'), '--gen', tree, '--restore')
        run(tool('switch_goto.py'), '--gen', tree, '--restore')
        run(tool('r1_local.py'), '--gen', tree, '--restore')
        run(tool('lr_preserve.py'), '--gen', tree, '--out', PROOFS, '--restore')
        run(tool('flush_hoist.py'), '--gen', tree, '--restore')
        # sasrt-nx (2026-11-11, blur-nx's vector-lane pass): its lane form out too (put back before the copies below).
        run(tool('stack_forward.py'), '--gen', tree, '--restore')  # sasrt-nx (2026-11-12, moonshot idea 2)
        # sasrt-nx (2026-11-19, base port 144; tw2de_nx's): the negated fused multiply-adds' macro out too
        # (single_floats.py and fma_single.py read the forms it wraps; put back below).
        run(tool('fnm_sign.py'), '--gen', tree, '--restore')
        run(tool('vec_lane_index.py'), '--gen', tree, '--restore')
        # And the round's earlier rewrites (sa2-nx's copy of peggle2-nx's round_restore.py, 2026-10-19): on a second run
        # the base steps decided differently on their forms (single_floats proved fewer, flush_hoist hoisted 249 loops
        # instead of 256, ro_constants folded 17 more vector loads: each exact, but the tree depended on how often this
        # script had run, and a PC build's re-run rewrote 279 files while a Switch build was reading them). Taken out
        # here too, two runs give identical files.
        run(tool('round_restore.py'), '--gen', tree)
        run(tool('pch_no_volatile.py'), pch)
        run(tool('thunk_calls.py'), '--gen', tree)
        run(tool('indirect_calls.py'), '--gen', tree, '--promote', PROMOTIONS)
        run(tool('loop_barriers.py'), tree)
        run(tool('pch_cold_traps.py'), pch)
        run(tool('direct_calls.py'), '--redo', '--gen', tree)
        run(tool('guest_cas.py'), '--gen', tree)
        # sasrt-nx (2026-11-19, base port 150; blur-nx's 15 ms batch, #164 / #165): sync, lwsync and eieio with the
        # PowerPC's orderings (lwsync `dmb ishld` + `dmb ishst`, eieio `dmb ishst` on AArch64;
        # g_rex_guest_fence_full puts the full fence back).
        run(tool('guest_fences.py'), '--gen', tree)
        run(tool('flush_mode_flow.py'), '--redo', '--gen', tree, '--image', IMAGE)
        run(tool('vec_byteswap.py'), '--gen', tree)
        run(tool('pch_neon_shuffles.py'), pch)
        # --xex: loads of the XEX's import records (kernel variable addresses the loader writes) stay loads (banjo-nx's
        # guard, 2026-10-19; none was folded here before it).
        xex_args = ['--xex', xex] if os.path.isfile(xex) else []
        run(tool('ro_constants.py'), '--gen', tree, '--image', IMAGE, *xex_args)
        run(tool('float_loads.py'), '--gen', tree)
        # banjo-nx's order (2026-10-19): the stack-frame statements marked (REX_LR_READ / REX_LR_WRITE / ...; its
        # elisions stay off), which tools/lr_preserve.py reads.
        run(tool('frame_traffic.py'), '--gen', tree)
        run(tool('loop_locals.py'), '--gen', tree)
        run(tool('leaf_locals.py'), '--gen', tree)
        run(tool('vperm_one_source.py'), '--gen', tree)
        run(tool('fp_sign_ops.py'), '--gen', tree)
        run(tool('leaf_dead_stores.py'), '--gen', tree, '--image', IMAGE)
        run(tool('single_floats.py'), '--gen', tree)
        run(tool('inline_memcalls.py'), '--gen', tree)
        run(tool('vec_unaligned_stores.py'), '--gen', tree)
        # sasrt-nx (2026-11-13, base port 90; blur-nx's CPU batch 1, the user there: "do all the exact ones"): the base's
        # docs/vector-store-ideas.md VS-27, VS-08, VS-25 and docs/vector-ideas-2.md VX-20, VX-21, each exact and checked by
        # the forms self-check on the device (app/src/sasrt_forms_selfcheck.cpp, VecBatch1). The base runs them right
        # after its vec_lane_index.py, before ro_constants_cfg.py and dead_ctx_defs.py: the same place here (this port
        # runs vec_lane_index.py later, before stack_forward.py; none of the four touches its stvewx / stvehx forms).
        # Before the localized copies, so they take the same forms.
        run(tool('vec_cvt_fixed.py'), '--gen', tree)      # vcfsx / vcfux with a scale: one SCVTF / UCVTF #n
        run(tool('vec_prefetch_line.py'), '--gen', tree)  # a guest dcbt prefetches the whole 128-byte line
        run(tool('vec_lvlx_splat.py'), '--gen', tree)     # lvlx + vspltw 0: one 4-byte load (where the lvlx is dead after)
        run(tool('vec_shift_whole.py'), '--gen', tree)    # vsrw / vsraw as one vector shift; vslw without the dead clamp
        # banjo-nx's codegen rounds of 2026-10-15 to 2026-10-19, ported 2026-10-19 (docs/enhancements.md, "banjo-nx's
        # codegen rounds"), in its order. Each has its CMake switch back (app/CMakeLists.txt SASRT_GEN_*).
        # Read-only constants over the control-flow graph (loop heads): the PC build compares each with the load.
        run(tool('ro_constants_cfg.py'), '--gen', tree, '--image', IMAGE, *xex_args)
        # Guest register writes nothing reads, on leaf_dead_stores.py's analysis (SASRT_DEAD_DEFS_OFF=1 in the
        # environment takes them out instead; the poison build tests them).
        if os.environ.get('SASRT_DEAD_DEFS_HOLD'):  # tools/dead_defs_bisect.py has set the files: leave them
            print('post_codegen: dead_ctx_defs.py held (SASRT_DEAD_DEFS_HOLD)')
        elif os.environ.get('SASRT_DEAD_DEFS_OFF'):
            run(tool('dead_ctx_defs.py'), '--gen', tree, '--restore-only')
        else:
            run(tool('dead_ctx_defs.py'), '--gen', tree, '--image', IMAGE, '--abi-indirect')
        # A loop header's flush-mode check in front of the loop (the PC build's flush-flow check counts it).
        run(tool('flush_hoist.py'), '--gen', tree)
        # sasrt-nx (2026-11-11, machine-copy idea 43, B3): vupkd3d128 type 0 as one NEON table lookup (before the copies,
        # so they get it too; REX_VUPKD3D_LANES: the four lane lines).
        run(tool('vupkd3d_neon.py'), '--gen', tree)
        # sasrt-nx (2026-11-11, machine-copy idea 43, F1 / F2): vrsqrtefp, vrefp and vmaddfp as macros (their default
        # is the exact expression; CMake SASRT_VMX_FAST_ESTIMATES / SASRT_VMX_FUSED_MADD, ON since 2026-11-11 by the user's
        # call, switch the faster forms on).
        run(tool('vmx_float_macros.py'), '--gen', tree)
        # sasrt-nx (2026-11-13, base port 96; blur-nx 2026-11-12, the user there: "Please do the fmadds change", and for the
        # base: "I want 96 on by default"): fmadds / fmsubs / fnmadds / fnmsubs rounded once in single precision, as the
        # Xenon does (sdk/include/rex/ppc/fma_single.h: one fmaf when the three inputs are floats, the double form
        # otherwise; the generator's double(float(std::fma(...))) rounds twice, one unit in the last place off in rare
        # halfway cases). CMake SASRT_FMADDS_SINGLE=OFF compiles the double form back (REX_FMADDS_DOUBLE_ROUNDING);
        # BLUR_FMA_SINGLE_OFF=1 in the environment skips the rewrite. The base's place: after vmx_float_macros.py, before
        # stack_forward.py and the copies, so a copy and its original statements have the same form.
        run(tool('fma_single.py'), '--gen', tree)
        # sasrt-nx (2026-11-19, base port 144; tw2de_nx's fnmadd / fnmsub fix): the negated fused multiply-adds as
        # REX_FNEG_FUSED(...), the plain negation by default (the same code); CMake TW2DE_FNMADD_SIGN=ON (off by
        # default) gives the PowerPC's sign of zero and NaN (sdk/include/rex/ppc/fpu_fma.h). After fma_single.py,
        # before the copies.
        run(tool('fnm_sign.py'), '--gen', tree)
        # sasrt-nx (2026-11-11, blur-nx's commit 6b6759d7): stvewx / stvehx lanes read from the register, not stored to
        # the stack and loaded back (the A57 cannot forward the wider store; sdk/include/rex/ppc/vec_lane.h, checked on
        # the device at start-up by banjo_hot_guest.cpp's lane self-check). Before the localized copies, so they take
        # the same form; REX_VEC_LANE_MEMORY (compile time) gives the indexed reads back.
        run(tool('vec_lane_index.py'), '--gen', tree)
        # sasrt-nx (2026-11-12, docs/cpu-moonshots-1112.md idea 2): a vector load of a stack slot that four 4-byte stores
        # of the same block just wrote takes the stored values (the stores stay; REX_STACK_FWD4 checks the address).
        # Before the copies, so they take the same form. REX_STACK_FWD_OFF (compile time): the original loads.
        run(tool('stack_forward.py'), '--gen', tree)
        # sasrt-nx (2026-11-19, base ports 136 / 150; blur-nx's M-23 and #231): float_loads.py again, now with the
        # any-mode pairs (CG-13: the helpers are the plain conversions, so their loads and stores go through the vector
        # unit too), the plain single loads the steps above made after its first run, and lfd. After
        # ro_constants_cfg.py, dead_ctx_defs.py and stack_forward.py (the base's place), before the copies (so they
        # take the same forms) and store_cards.py (which marks the new stores' cards).
        run(tool('float_loads.py'), '--gen', tree, '--any-mode', '--doubles')
        # sasrt-nx (2026-11-19, base port 140; blur-nx's near-exact switches): the forms a near-exact switch changes as
        # helpers whose default is the generator's expression (#42: vmaxfp / vminfp as rex::ppc::VMaxFp / VMinFp,
        # sdk/include/rex/ppc/diet_ops.h; CMake BLUR_NEAR_EXACT, OFF). Before the copies, so they take the same forms.
        run(tool('near_exact.py'), '--gen', tree)
        # sasrt-nx (2026-11-08, katamari-nx's docs/optimising-functions.md): the localized copies (app/generated/hot)
        # of app/src/cpu/hot/localized.txt and of the bulk list localized_bulk.txt (tools/switch_hot_bulk.py, from the
        # console profiles), with the hand-written natives of hand.txt in front of their copies; made from the text as
        # it stands here, so each copy matches the function the build compiles (katamari-nx's place for it).
        if scratch:
            print('post_codegen: a copy (--gen): the localized copies are not made')
        else:
            # sasrt-nx (2026-11-12, docs/calling-convention-plan.md stage 1): whole-program liveness with the vector
            # registers, right before the copies are made from this same text (localize_native.py checks the stamp).
            run(tool('reg_liveness.py'), '--gen', tree)
            run(tool('localize_native.py'), '--list', '--bulk')
            # sasrt-nx (2026-11-11, machine-copy idea 46): the census list of the writable globals the copies load at
            # a known address (app/generated/hot/frozen_census.inc, compiled into banjo_hot_guest.cpp).
            run(tool('frozen_census.py'), '--write')
        # The jump-table dispatch of the renderer thread's bitstream decoder sub_82EB6B78 (4.6 % of the guest samples
        # of the PC profile; 137 handlers jump back to its 512-case switch) threaded into each handler.
        run(tool('switch_goto.py'), '--gen', tree, '--thread', '--only', 'sub_82EB6B78')
        # Link-register write-backs proven to store the value ctx.lr holds compile to nothing (REX_LR_WRITE_SAME; the
        # PC build checks each); in the functions of app/config/lr_write_same_choice.json when it exists (measured).
        lr_choice = os.path.join(APP, 'config', 'lr_write_same_choice.json')
        run(tool('lr_preserve.py'), '--gen', tree, '--out', PROOFS, '--assume-indirect', '--rewrite',
            *(['--only-file', lr_choice] if os.path.isfile(lr_choice) else []))
        # r1 as a local mirror where it compiles cheaper (app/config/r1_local_choice.json, measured: banjo-nx found it a
        # loss in every function together, +0.33 %), on the whole-program proof that callees return with r1 unchanged.
        # Without the list nothing is rewritten. REX_R1_CHECK (PC) tests the assumed calls.
        r1_choice = os.path.join(APP, 'config', 'r1_local_choice.json')
        run(tool('r1_preserve.py'), '--gen', tree, '--out', os.path.join(PROOFS, 'strict'))
        # sasrt-nx (2026-11-19, base port 140; blur-nx's near-exact #9): with BLUR_NX_R1_ASSUME=1 in the environment, the
        # assumed proof also takes a function as preserving unless its own body fails (r1_preserve.py --near-exact);
        # the strict one stays a proof, so REX_R1_CHECK (PC) tests every call the assumption covers.
        run(tool('r1_preserve.py'), '--gen', tree, '--out', os.path.join(PROOFS, 'assumed'), '--indirect-preserve',
            *(['--near-exact'] if os.environ.get('BLUR_NX_R1_ASSUME') == '1' else []))
        if os.path.isfile(r1_choice) or os.environ.get('SASRT_R1_LOCAL_ALL'):
            run(tool('r1_local.py'), '--gen', tree,
                '--proof-strict', os.path.join(PROOFS, 'strict', 'r1_preserve.json'),
                '--proof-assumed', os.path.join(PROOFS, 'assumed', 'r1_preserve.json'),
                *([] if os.environ.get('SASRT_R1_LOCAL_ALL') else ['--only-file', r1_choice]))
        # Last, on the final text: VMX vsel as one NEON bit select, then the inline copies of the tiny leaf functions
        # each file calls in another.
        run(tool('vsel_neon.py'), '--gen', tree)
        run(tool('inline_leaves.py'), '--gen', tree)
        # sasrt-nx (2026-10-21, banjo-nx's CPU proposal 1 by way of sa2-nx): the store cards, after everything else (the
        # inline copies and the localized copies included): every store outside the stack marks its page for Renut's
        # cached copies (REX_STORE_CARDS_OFF compiles them out).
        run(tool('store_cards.py'), '--gen', tree, '--hot', os.path.join(gen, 'hot'))
        # sasrt-nx (2026-11-13, base port 90; blur-nx's CPU batch 2): in the localized copies (app/generated/hot), after
        # the store cards, as the base runs them. The base's tree is one folder with its copies in hot/ under it; here the
        # copies are gen/hot and the functions and the pch gen/default (tree), so the steps that read both take --hot.
        # docs/vector-store-ideas.md VS-14 (the base's): one card check per group of card stores to the same base in a
        # straight stretch (two at its end: the lowest and highest offset's page).
        run(tool('card_groups.py'), '--gen', gen)  # gen/hot/n_*.h
        # The base's docs/vector-ideas-2.md VX-15 / VX-14: in the copies' f_ bodies only (the o_ bodies stay the guard's
        # reference), two or four broadcast dot products merged by vmrghw / vmrglw as one pairwise-add tree
        # (sdk/include/rex/ppc/vec_batch2.h; BLUR_DP_MERGE_OFF=1 in the environment: nothing).
        run(tool('vec_dp_merge.py'), '--gen', tree, '--hot', os.path.join(gen, 'hot'))
        # VX-29 / VX-02: in the copies' f_ bodies, vupkd3d128 of a zero register as 1.0 and vcuxwfp128 / vcsxwfp128 of a
        # known splat as their constants (BLUR_CONST_FOLD_OFF=1: nothing).
        run(tool('vec_const_fold.py'), '--gen', gen)  # gen/hot/n_*.h
        # VS-05: a 128-byte dcbzl as two DC ZVA (no read of the line it zeroes), in the tree and the copies. After
        # store_cards.py, which finds the dcbz by its memset to put the card in front (REX_DCBZ_MEMSET, compile time: the
        # memset everywhere).
        run(tool('vec_dcbz_zva.py'), '--gen', tree, '--hot', os.path.join(gen, 'hot'))
        changed = sum(1 for path, (digest, mtime) in before.items()
                      if os.path.isfile(path) and os.stat(path).st_mtime_ns != mtime)
        kept = keep_times(before)
        print(f'post_codegen: {changed} files written by the steps, {kept} of them with the text they had (their '
              f'times are kept: no rebuild), {changed - kept} really changed')
    else:
        # sasrt-nx (2026-11-11, round A's audit): the classic tree has no LiveOut of its own (no leaf_dead_stores.py):
        # every write-back of the copies stays (machine-copy idea 37 off).
        os.environ['SASRT_LOCALIZE_LIVE_OUT'] = '0'
        run(tool('localize_native.py'), '--list', '--bulk')
    if scratch:
        print(f'post_codegen: {flavor} codegen steps done on {gen}')
        return
    # sasrt-nx (2026-10-21, sa2-nx's fix): written only when it changes: the file is a CMake configure dependency
    # (app/CMakeLists.txt), and rewriting it made every PC build re-run CMake and the codegen (12-17 minutes a build).
    path = os.path.join(GEN, 'codegen_flavor.txt')
    text = f'{flavor} codegen'
    if not os.path.isfile(path) or open(path, encoding='utf-8').read() != text:
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
    print(f'post_codegen: {flavor} codegen steps done')


if __name__ == '__main__':
    main()
