# sasrt-nx (2026-11-12, calling-convention stage 1e question): does the game's compiler treat the volatile registers
# as clobbered after every call? For each call site, the volatile non-result registers (r0, r5-r12, f0, f5-f13, v0,
# v1, v3-v13, v32-v63) that an INSTRUCTION of the caller reads after the call before writing them (calls in between
# clobber them; the caller's exit reads nothing). If no direct call site has any, a direct callee's LiveOut can drop
# them too (the caller never relies on them), as stage 1c does for pointer-reached functions.
#   python abi_after_call_census.py [--gen app/generated/default]
import collections, os, re, sys
sys.path.insert(0, 'D:/sonic transformed/sasrt-nx/tools')
import leaf_dead_stores as lds
import reg_liveness as rl

GEN = sys.argv[sys.argv.index('--gen') + 1] if '--gen' in sys.argv else 'D:/sonic transformed/sasrt-nx/app/generated/default'
VOL = rl.EXIT_DEAD if rl.EXIT_DEAD else (rl.SCRATCH_V | sum(rl.V(n) for n in range(3, 14)) | rl.R(0) | sum(rl.R(n) for n in range(5, 13)) | rl.F(0) | sum(rl.F(n) for n in range(5, 14)))
CLOBBER = VOL | rl.R(3) | rl.R(4) | sum(rl.F(n) for n in range(1, 5)) | rl.V(2)  # every volatile register

rl._ns['MID_ASM_HOOKS'] = lds.load_mid_asm_hooks(GEN)
named_calls = {}
bodies = lds.functions(GEN, named_calls)
sites = 0
flagged = collections.Counter()
by_reg = collections.Counter()
examples = []
UNKNOWN = collections.Counter(); ALLUSE = collections.Counter()
ind_examples = []
FIRST = collections.Counter(); FIRSTEX = collections.defaultdict(list)
indirect_flag = 0
indirect_sites = 0
for addr, (path, lines) in bodies.items():
    nodes = rl.parse_function(lines)
    if not any(n.call or n.indirect for n in nodes):
        continue
    comments = [lds.COMMENT.match(l) for l in lines]
    comments = [c for c in comments if c]
    if len(comments) != len(nodes):
        continue
    du = []
    for c in comments:
        try:
            d, u = rl.defuse(c.group(1), c.group(2))
        except Exception:
            d, u = 0, rl.regs(c.group(2))
            UNKNOWN[c.group(1)] += 1
        if u == rl.ALL or (u & rl.VMASK) == rl.VMASK:
            ALLUSE[c.group(1)] += 1
            u = rl.regs(c.group(2))
        du.append((d, u))
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
                if node.call and node.tail:
                    new = u  # the caller returns right after: its LiveOut, not this question
                else:
                    new = ((out & ~(d | CLOBBER)) | u)
            else:
                new = (out & ~d) | u
            if new != live[i]:
                live[i] = new
                changed = True
    for i, node in enumerate(nodes):
        if not (node.call or node.indirect) or (node.call and node.tail):
            continue
        after = 0
        for s in node.succ:
            after |= live[s]
        bad = after & VOL
        if node.indirect:
            indirect_sites += 1
            indirect_flag += bool(bad)
            if bad:
                # the first instruction on a path after the call that reads a flagged register before writing it
                # (forward search, depth-first over successors, per register)
                for b in range(192):
                    if not bad >> b & 1:
                        continue
                    bit = 1 << b
                    stack = list(node.succ); seen = set(); hit = None
                    while stack and hit is None:
                        k = stack.pop()
                        if k in seen or k >= nn:
                            continue
                        seen.add(k)
                        d_, u_ = du[k]
                        if u_ & bit:
                            hit = k; break
                        if (d_ & bit) or ((nodes[k].call or nodes[k].indirect) and not (nodes[k].call and nodes[k].tail)):
                            continue
                        stack.extend(nodes[k].succ)
                    if hit is not None:
                        c_ = comments[hit]
                        ops_ = [o.strip() for o in c_.group(2).split(',')]
                        key = c_.group(1)
                        if key in ('mr', 'or') and len(set(ops_)) == 1 or (key in ('or',) and len(ops_) == 3 and ops_[0] == ops_[1] == ops_[2]):
                            key = 'self-move'
                        elif key in ('subfe', 'subfe.') and len(ops_) == 3 and ops_[1] == ops_[2]:
                            key = 'subfe same'
                        FIRST[key] += 1
                        if len(FIRSTEX[key]) < 2:
                            FIRSTEX[key].append(('%08X' % addr, i, c_.group(1), c_.group(2)[:40], 'r%d' % b if b < 32 else 'f%d' % (b - 32) if b < 64 else 'v%d' % (b - 64)))
            if bad and len(ind_examples) < 20:
                regs_ = [('r%d' % b if b < 32 else 'f%d' % (b - 32) if b < 64 else 'v%d' % (b - 64)) for b in range(192) if bad >> b & 1]
                nxt = [(comments[k].group(1), comments[k].group(2)[:20]) for k in range(i + 1, min(nn, i + 6))]
                ind_examples.append(('%08X' % addr, i, regs_[:8], nxt))
            continue
        sites += 1
        if bad:
            flagged[addr] += 1
            for b in range(192):
                if bad >> b & 1:
                    by_reg['r%d' % b if b < 32 else 'f%d' % (b - 32) if b < 64 else 'v%d' % (b - 64)] += 1
            if len(examples) < 25:
                regs = [('r%d' % b if b < 32 else 'f%d' % (b - 32) if b < 64 else 'v%d' % (b - 64)) for b in range(192) if bad >> b & 1]
                examples.append(('%08X' % addr, i, comments[i].group(1), comments[i].group(2)[:30], regs[:8]))
print('direct (non-tail) call sites %d; with a volatile non-result register read after the call: %d sites in %d '
      'functions' % (sites, sum(flagged.values()), len(flagged)))
print('indirect call sites %d; flagged %d' % (indirect_sites, indirect_flag))
print('by register:', by_reg.most_common(30))
for e in examples:
    print('  ', e)
print('unknown forms', UNKNOWN.most_common(10), 'all-use forms', ALLUSE.most_common(10))
print('FIRST READERS after indirect calls:', FIRST.most_common())
for k, v in FIRSTEX.items():
    print('  ', k, v)
