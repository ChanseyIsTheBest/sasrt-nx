# sasrt-nx (2026-11-12, CC3 idea 1 safety census): does any function use an incoming SAVED register's value other than
# to save it? Per function: the saved registers (r14-r31, f14-f31, v14-v31, v64-v127) read before written, by an
# instruction that is not a store of that register to the stack (r1-relative) and not a save helper call. Under the
# calling convention there are none: a callee only saves and restores them.
import collections, re, sys
sys.path.insert(0, 'D:/sonic transformed/sasrt-nx/tools')
import leaf_dead_stores as lds
import reg_liveness as rl

GEN = 'D:/sonic transformed/sasrt-nx/app/generated/default'
rl._ns['MID_ASM_HOOKS'] = lds.load_mid_asm_hooks(GEN)
bodies = lds.functions(GEN, {})
SAVED = (sum(rl.R(n) for n in range(14, 32)) | sum(rl.F(n) for n in range(14, 32)) | sum(rl.V(n) for n in range(14, 32))
         | sum(rl.V(n) for n in range(64, 128)))
STACK_STORE = re.compile(r'^(stw|std|stfd|stfs|stvx|stvx128|stwu|stdu)$')
uses = collections.Counter()
funcs = 0
examples = []
EXK = collections.Counter(); SEEN = set()
for addr, (path, lines) in bodies.items():
    nodes = rl.parse_function(lines)
    comments = [c for c in (lds.COMMENT.match(l) for l in lines) if c]
    if len(comments) != len(nodes):
        continue
    nn = len(nodes)
    du = []
    for c in comments:
        mn = c.group(1).rstrip('.')
        ops = [o.strip() for o in c.group(2).split(',')] if c.group(2).strip() else []
        try:
            d, u = rl.defuse(c.group(1), c.group(2))
        except Exception:
            d, u = 0, rl.regs(c.group(2))
        real = u
        # a store of a saved register (any store: the VMX saves go through r11 / r12 frame copies) is a save, not a
        # use of its value; traps read only their operands; full-write forms read no destination
        if mn.startswith('st') and ops:
            real = u & ~rl.regs(ops[0])
        elif mn.startswith(('tw', 'td')):
            real = rl.regs(c.group(2)) & ~(d if False else 0)
        elif mn in ('vupkd3d128', 'lvlx', 'lvlx128', 'lvrx', 'lvrx128') and ops:
            real = u & ~rl.regs(ops[0])
        if real == rl.ALL:
            real = rl.regs(c.group(2))
        du.append((d, u, real))
    # forward: the saved registers not yet written; a "real" read of one of them is a use of its incoming value
    undefined = [0] * nn
    undefined[0] = SAVED
    work = [0]
    seen_in = {0: SAVED}
    hits = 0
    order = list(range(nn))
    changed = True
    state = [None] * nn
    state[0] = SAVED
    while changed:
        changed = False
        for i in order:
            st = state[i]
            if st is None:
                continue
            node = nodes[i]
            d, u, real = du[i]
            if node.call or node.indirect:
                if node.call:
                    name_hit = 0
                out = st & ~d
            else:
                out = st & ~d
            for s in node.succ:
                new = (state[s] or 0) | out
                if state[s] is None or new != state[s]:
                    state[s] = new
                    changed = True
    found = 0
    for i in range(nn):
        st = state[i]
        if st is None:
            continue
        d, u, real = du[i]
        node = nodes[i]
        if node.call or node.indirect:
            continue  # what a callee does with them is its own census entry
        bad = st & real & SAVED
        if bad:
            found |= bad
            EXK[comments[i].group(1)] += 1
            if len(examples) < 30 and comments[i].group(1) not in SEEN:
                SEEN.add(comments[i].group(1))
                regs_ = [('r%d' % b if b < 32 else 'f%d' % (b - 32) if b < 64 else 'v%d' % (b - 64)) for b in range(192) if bad >> b & 1]
                examples.append(('%08X' % addr, i, comments[i].group(1), comments[i].group(2)[:40], regs_[:6]))
    if found:
        funcs += 1
        for b in range(192):
            if found >> b & 1:
                uses['r%d' % b if b < 32 else 'f%d' % (b - 32) if b < 64 else 'v%d' % (b - 64)] += 1
print('functions using an incoming saved register other than to save it: %d of %d' % (funcs, len(bodies)))
print('by register:', uses.most_common(30))
print('by instruction:', EXK.most_common(30))
for e in examples:
    print('  ', e)
