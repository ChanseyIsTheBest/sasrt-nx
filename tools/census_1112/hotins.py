# The hottest instructions of one function in a profile, with a few instructions of context each.
#   hotins.py PROF MAP ELF PATTERN [N]
import bisect, collections, re, subprocess, sys
sys.path.insert(0, 'D:/sonic transformed/sasrt-nx/tools')
import switch_hot_functions as shf
PROF, MAP, ELF, PAT = sys.argv[1:5]
N = int(sys.argv[5]) if len(sys.argv) > 5 else 12
OBJ = 'C:/devkitPro/devkitA64/bin/aarch64-none-elf-objdump.exe'
secs = sorted(shf.load_map(MAP))
sec = next(s for s in secs if re.search(PAT, s[2]))
lo, hi = sec[0], sec[1]
PC = re.compile(r'^\s+[\d.]+%\s+pc image\+0x([0-9a-f]+) x(\d+)')
pcs = collections.Counter()
rep = 0
for line in open(PROF, encoding='utf-8', errors='replace'):
    if line.startswith('==== '):
        rep += 1
        continue
    m = PC.match(line)
    if m and rep > 2:
        a = int(m.group(1), 16)
        if lo <= a < hi:
            pcs[a] += int(m.group(2))
out = subprocess.run([OBJ, '-d', '--no-show-raw-insn', '--start-address=0x%x' % lo, '--stop-address=0x%x' % hi, ELF],
                     capture_output=True, text=True, errors='replace').stdout.splitlines()
INS = re.compile(r'^\s*([0-9a-f]+):\s+(.*)$')
ins = [(int(m.group(1), 16), m.group(2)) for m in map(INS.match, out) if m]
idx = {a: k for k, (a, _) in enumerate(ins)}
print('%s: %d samples' % (sec[2][-60:], sum(pcs.values())))
# group consecutive hot instructions into regions of +-6 instructions
for a, n in pcs.most_common(N):
    k = idx.get(a)
    if k is None:
        continue
    ctx = ' | '.join(t.split('//')[0].strip()[:34] for _, t in ins[max(0, k - 3):k + 1])
    print('%5d  +%04x  %s' % (n, a - lo, ctx))
