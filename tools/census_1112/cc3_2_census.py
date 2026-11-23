# sasrt-nx (2026-11-12, CC3 item 2 census): at an indirect call, which argument registers hold garbage, i.e. on every
# path from the function's entry they were last set by a clobbering call (an indirect / hook / import call: the
# convention lets its target change every volatile register), not by an instruction of the caller? Results of that
# call (r3, r4, f1-f4, v1-v4) are meaningful and never garbage. Reports how many indirect sites have garbage argument
# registers, and the sanity check: promoted sites whose KNOWN targets read one of them (UE) - that would mean the
# reasoning is wrong somewhere.
import collections, sys
sys.path.insert(0, 'D:/sonic transformed/sasrt-nx/tools')
import leaf_dead_stores as lds
import reg_liveness as rl

GEN = 'D:/sonic transformed/sasrt-nx/app/generated/default'
rl._ns['MID_ASM_HOOKS'] = lds.load_mid_asm_hooks(GEN)
bodies = lds.functions(GEN, {})
R, F, V = rl.R, rl.F, rl.V
CLOB = (sum(R(n) for n in range(5, 11)) | sum(F(n) for n in range(5, 14)) | sum(V(n) for n in range(5, 14)))


def name(b):
    return 'r%d' % b if b < 32 else 'f%d' % (b - 32) if b < 64 else 'v%d' % (b - 64)


sites = 0
with_garbage = 0
garbage_bits = collections.Counter()
promoted_sites = 0
promoted_conflicts = 0
parsed = {}
for addr, (path, lines) in bodies.items():
    parsed[addr] = rl.parse_function(lines)
# UE of every function (local reads before writes only; enough for the sanity check)
ue_local = {}
for addr, nodes in parsed.items():
    und = rl.lds_forward(nodes)
    m = 0
    for node, st in zip(nodes, und):
        m |= node.use & st
    ue_local[addr] = m
examples = []
for addr, nodes in parsed.items():
    if not any(n.indirect for n in nodes):
        continue
    nn = len(nodes)
    # forward: G = registers that hold garbage (set last by a clobbering call) on every path; meet = intersection
    G = [None] * nn
    G[0] = 0
    changed = True
    order = range(nn)
    while changed:
        changed = False
        for i in order:
            g = G[i]
            if g is None:
                continue
            node = nodes[i]
            clob = node.indirect or (node.call and not node.call[1])
            out = (g & ~node.defn) | (CLOB if clob else 0)
            if node.call and node.call[1] and not node.indirect:
                out = g & ~node.defn  # a known direct call: what it writes is meaningful to the caller (IPA possible)
                out &= ~(rl.ALL)  # conservatively forget all garbage after a known call
            for s in node.succ:
                new = out if G[s] is None else (G[s] & out)
                if G[s] is None or new != G[s]:
                    G[s] = new
                    changed = True
    for i, node in enumerate(nodes):
        if not node.indirect:
            continue
        sites += 1
        g = (G[i] or 0) & CLOB
        if g:
            with_garbage += 1
            for b in range(192):
                if g >> b & 1:
                    garbage_bits[name(b)] += 1
        if node.call:
            promoted_sites += 1
            tgts = [node.call[0]] + [t for t, _ in node.extra]
            bad = 0
            for t in tgts:
                bad |= ue_local.get(t, 0) & g
            if bad:
                promoted_conflicts += 1
                if len(examples) < 12:
                    examples.append(('%08X' % addr, i, ['%08X' % t for t in tgts][:3], [name(b) for b in range(192) if bad >> b & 1][:6]))
print('indirect call sites %d; with garbage argument registers %d' % (sites, with_garbage))
print('garbage registers:', garbage_bits.most_common(20))
print('promoted sites %d; whose known target reads a garbage register (sanity check) %d' % (promoted_sites, promoted_conflicts))
for e in examples:
    print('  ', e)
