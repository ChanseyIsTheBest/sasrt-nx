# Which vector registers does this game's code pass arguments / results in? Per function: the vector registers read
# before written (local UE, calls treated as reading nothing and clobbering the volatile ones). Per call site: the
# vector registers an instruction reads right after the call before writing them (results).
import collections, sys
sys.path.insert(0, 'D:/sonic transformed/sasrt-nx/tools')
import leaf_dead_stores as lds
import reg_liveness as rl

GEN = 'D:/sonic transformed/sasrt-nx/app/generated/default'
rl._ns['MID_ASM_HOOKS'] = lds.load_mid_asm_hooks(GEN)
bodies = lds.functions(GEN, {})
taken = lds.address_taken(GEN, 'D:/sonic transformed/sasrt-nx/out/default_image.bin', set(bodies), bodies)
PR = ('data word', 'lis pair', 'named in app/indirect_promotions.txt', 'named in app/src/hot/localized.txt')
ptr = {a for a, r in taken.items() if all(x in PR for x in r)}
ptr_entry = collections.Counter(); ptr_n = 0
VOLV = rl.V(0) | rl.V(1) | sum(rl.V(n) for n in range(2, 14)) | sum(rl.V(n) for n in range(32, 64))
ALLV = sum(rl.V(n) for n in range(128))
# write-full vector loads / unpacks the conservative defuse treats as read-modify-write
FULL_WRITE = ('lvlx', 'lvlx128', 'lvrx', 'lvrx128', 'vupkd3d128')
entry = collections.Counter()
entry_funcs = 0
after = collections.Counter()
after_sites = 0
taken_entry = collections.Counter()
for addr, (path, lines) in bodies.items():
    nodes = rl.parse_function(lines)
    comments = [c for c in (lds.COMMENT.match(l) for l in lines) if c]
    if len(comments) != len(nodes):
        continue
    du = []
    for c in comments:
        mn = c.group(1).rstrip('.')
        try:
            d, u = rl.defuse(c.group(1), c.group(2))
        except Exception:
            d, u = 0, rl.regs(c.group(2))
        if u == rl.ALL or (u & ALLV) == ALLV:
            u = rl.regs(c.group(2))
        if mn in FULL_WRITE:
            ops = [o.strip() for o in c.group(2).split(',')]
            dv = rl.regs(ops[0]) & ALLV
            u &= ~dv
            d |= dv
        du.append((d & ALLV, u & ALLV))
    nn = len(nodes)
    live = [0] * nn
    changed = True
    while changed:
        changed = False
        for i in range(nn - 1, -1, -1):
            node = nodes[i]
            out = 0
            for s in node.succ:
                out |= live[s]
            d, u = du[i]
            if node.call or node.indirect:
                new = (out & ~(d | VOLV)) | u
            else:
                new = (out & ~d) | u
            if new != live[i]:
                live[i] = new
                changed = True
    ue = live[0] if nn else 0
    if ue:
        entry_funcs += 1
    for n in range(128):
        if ue >> (64 + n) & 1:
            entry['v%d' % n] += 1
            if addr in ptr:
                ptr_entry['v%d' % n] += 1
    if addr in ptr:
        ptr_n += 1
    for i, node in enumerate(nodes):
        if not (node.call or node.indirect) or (node.call and node.tail):
            continue
        a = 0
        for s in node.succ:
            a |= live[s]
        a &= VOLV
        if a:
            after_sites += 1
        for n in range(128):
            if a >> (64 + n) & 1:
                after['v%d' % n] += 1
print('functions reading a vector register on entry: %d' % entry_funcs)
print('  by register:', entry.most_common(24))
print('call sites with a volatile vector register read right after: %d' % after_sites)
print('  by register:', after.most_common(24))
print('pointer-reached functions %d; vector registers read on entry:' % ptr_n, ptr_entry.most_common(30))
