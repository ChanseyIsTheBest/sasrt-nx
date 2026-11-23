# sasrt-nx (2026-11-12, CC3 item 2, stronger variant census): after a KNOWN direct call X, the argument registers X's
# tree may write (MayWrite, transitive; unknown parts: all clobberable ones) hold X's values. If the caller's own
# instructions never read such a register before writing it (direct reads only), the caller treats it as clobbered,
# so at a later indirect call it would be garbage too. How many more indirect sites get garbage registers that way,
# and how many direct call sites have the caller READ a register X may write (X's deliberate output or IPA: those
# registers stay meaningful and are excluded per site anyway).
import collections, sys
sys.path.insert(0, 'D:/sonic transformed/sasrt-nx/tools')
import leaf_dead_stores as lds
import reg_liveness as rl

GEN = 'D:/sonic transformed/sasrt-nx/app/generated/default'
rl._ns['MID_ASM_HOOKS'] = lds.load_mid_asm_hooks(GEN)
bodies = lds.functions(GEN, {})
R, F, V = rl.R, rl.F, rl.V
CLOB = rl.CLOBBERED_ARGS if hasattr(rl, 'CLOBBERED_ARGS') else (sum(R(n) for n in range(5, 11)) | sum(F(n) for n in range(5, 14)) | sum(V(n) for n in range(5, 14)))
parsed = {a: rl.parse_function(l) for a, (_, l) in bodies.items()}
# MayWrite fixed point
local_w = {}
calls_of = {}
for a, nodes in parsed.items():
    w = 0
    cs = []
    for n in nodes:
        w |= n.defn
        if n.indirect or (n.call and not n.call[1]):
            w |= CLOB
        if n.call and n.call[1]:
            cs.append(n.call[0])
        for t, kn in n.extra:
            if kn:
                cs.append(t)
            else:
                w |= CLOB
    local_w[a] = w & CLOB
    calls_of[a] = cs
mw = dict(local_w)
changed = True
while changed:
    changed = False
    for a, cs in calls_of.items():
        new = mw[a]
        for c in cs:
            new |= mw.get(c, CLOB)
        if new != mw[a]:
            mw[a] = new
            changed = True
# per function: forward garbage (as reg_liveness CC3-2) plus: after a known direct call, MayWrite(callee) registers the
# caller's own instructions do not read afterwards (checked per site with a backward "direct read" liveness)
sites_old = sites_new = 0
gain_bits = collections.Counter()
reads_after = 0
direct_sites = 0
for a, nodes in parsed.items():
    nn = len(nodes)
    if not any(n.indirect for n in nodes):
        continue
    # backward: registers read by the caller's own instructions (calls read nothing here; they kill CLOB)
    dl = [0] * nn
    ch = True
    while ch:
        ch = False
        for i in range(nn - 1, -1, -1):
            n = nodes[i]
            out = 0
            for s in n.succ:
                out |= dl[s]
            if n.indirect or n.call:
                new = out & ~CLOB  # after a call they are whatever the callee left: a read there is of that value
                new |= (n.use & ~rl.ALL)  # nothing
            else:
                new = (out & ~n.defn) | n.use
            if new != dl[i]:
                dl[i] = new
                ch = True
    for variant in (0, 1):
        g_in = [None] * nn
        g_in[0] = 0
        ch = True
        while ch:
            ch = False
            for i, n in enumerate(nodes):
                g = g_in[i]
                if g is None:
                    continue
                if n.indirect or (n.call and not n.call[1]):
                    out = (g & ~n.defn) | CLOB
                elif n.call:
                    if variant == 0:
                        out = 0
                    else:
                        after = 0
                        for s in n.succ:
                            after |= dl[s]
                        out = (mw.get(n.call[0], CLOB) & ~after) & CLOB
                else:
                    out = g & ~n.defn
                for s in n.succ:
                    new = out if g_in[s] is None else (g_in[s] & out)
                    if g_in[s] is None or new != g_in[s]:
                        g_in[s] = new
                        ch = True
        for i, n in enumerate(nodes):
            if n.indirect and g_in[i]:
                if variant == 0:
                    sites_old += 1
                    old_g = g_in[i]
                else:
                    sites_new += 1
    for i, n in enumerate(nodes):
        if n.call and n.call[1] and not n.indirect:
            direct_sites += 1
            after = 0
            for s in n.succ:
                after |= dl[s]
            if after & mw.get(n.call[0], CLOB) & CLOB:
                reads_after += 1
print('indirect sites with garbage argument registers: rule as built %d, stronger variant %d' % (sites_old, sites_new))
print('direct call sites %d; where the caller reads (directly) a register the callee may write: %d' % (direct_sites, reads_after))
