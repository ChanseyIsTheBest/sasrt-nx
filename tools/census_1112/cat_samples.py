#!/usr/bin/env python3
"""Busy samples (pc lines) of a console profile, by category of the sampled function's name, per thread.
python cat_samples.py PROFILE MAP [from_report=10]"""
import bisect, collections, re, sys
sys.path.insert(0, r'D:/sonic transformed/sasrt-nx/tools')
import switch_hot_functions as shf
PROF, MAP = sys.argv[1:3]
FROM = int(sys.argv[3]) if len(sys.argv) > 3 else 10
secs = sorted(shf.load_map(MAP)); starts = [s[0] for s in secs]
def name(a):
    i = bisect.bisect_right(starts, a) - 1
    if i >= 0 and a < secs[i][1]:
        return secs[i][2]
    return '?'
CATS = [
    ('kernel export / HLE', r'HostToGuestFunction|xboxkrnl|xam|XObject|KernelState|ObjectTable|kernel'),
    ('host sync (mutex/condvar/event/wait)', r'mutex|rmutex|condvar|PosixEvent|PosixCondition|WaitMultiple|__syscall|pthread|semaphore|Semaphore|__libc_lock|svc'),
    ('critical sections (Rtl*)', r'RtlEnterCriticalSection|RtlLeaveCriticalSection|RtlTryEnter'),
    ('malloc/free/new', r'_malloc_r|_free_r|_memalign_r|_Znwm|_ZdlPv|malloc|free|_realloc'),
    ('dynamic_cast/RTTI', r'dyncast|__dynamic_cast|class_type_info'),
    ('memcpy/memset/memmove (host)', r'^memcpy|^memset|^memmove|hot\.memcpy|hot\.memset'),
    ('TLS read_tp', r'read_tp'),
    ('clock/time', r'steady_clock|QueryGuestTick|Clock|armGetSystemTick|UpdateGuestClock'),
    ('ffmpeg/xma', r'decode_frame|av_|ff_|xma|Xma|avcodec'),
    ('renut/plume/deko', r'renut|plume|Deko3D|dkCmd|dk[A-Z]|banjo9renut|sasrt_renut|Lines64'),
    ('guest copy/native', r'banjo3hot|sasrt3hot'),
    ('guest generated', r'sub_[0-9A-F]{8}'),
    ('unknown', r'^\?$'),
]
cre = [(c, re.compile(p)) for c, p in CATS]
THREAD = re.compile(r'^-- thread (\d+) "(.*?)"')
PC = re.compile(r'^\s+[\d.]+%\s+pc image\+0x([0-9a-f]+) x(\d+)')
PCU = re.compile(r'^\s+[\d.]+%\s+pc (0x[0-9a-f]+) x(\d+)')
rep = 0; thread = ''
tot = collections.Counter(); per = collections.defaultdict(collections.Counter); total = 0
other = collections.Counter()
for line in open(PROF, encoding='utf-8', errors='replace'):
    if line.startswith('==== '):
        rep += 1; continue
    if rep <= FROM: continue
    m = THREAD.match(line)
    if m: thread = m.group(2); continue
    m = PC.match(line)
    if m:
        n = int(m.group(2)); nm = name(int(m.group(1), 16))
    else:
        m = PCU.match(line)
        if not m: continue
        n = int(m.group(2)); nm = '?'
    total += n
    for c, r in cre:
        if r.search(nm):
            tot[c] += n; per[thread][c] += n; break
    else:
        tot['other host'] += n; per[thread]['other host'] += n; other[nm[:80]] += n
print('busy samples %d' % total)
for c, n in tot.most_common(): print('  %6d %5.1f %%  %s' % (n, 100.0 * n / total, c))
print('other host top:')
for nm, n in other.most_common(25): print('  %5d  %s' % (n, nm))
for t in ('Main XThread (F', 'SlRenderer (F80', 'AK::EventManage', 'Model Instance ', 'XMA Decoder (F8', '?'):
    if t in per:
        s = sum(per[t].values())
        print('== %s %d' % (t, s), ', '.join('%s %.1f%%' % (c, 100.0 * n / s) for c, n in per[t].most_common(8)))
