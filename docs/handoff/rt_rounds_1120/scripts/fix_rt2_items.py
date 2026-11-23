# Rewrites the second and third render-thread rounds' item lines of sasrt_gpu_round.h (one X per line, each continued
# with a backslash), the round-3 first-item define, and adds the round-3 keys' cvars (from items3.txt next to this
# script: name|key|short text|cvar description, one item a line).
import os
import re
import sys

ROOT = r'D:/sonic transformed/sasrt-nx/app/src/renut_engine/gpu/'
ITEMS = [
    ('kRt2SlotIndex', 'sasrt_rt2_slot_index', "render thread: FindHostTextureBySlotLocked's memo a 256-entry table by slot (each answer checked as before), not one entry"),
    ('kRt2SpecMemo', 'sasrt_rt2_spec_memo', "render thread: a fast draw's fetch-spec, plain-fetch, clip and spec words kept from the draw before when no shared-constant line, shader, target or A/B half changed"),
    ('kRt2DropThrottle', 'sasrt_rt2_drop_throttle', "render thread: DropReplacedRanges' pass over the stream cache's limit every 4th frame, not every frame (memory only)"),
    ('kRt2PagesTail', 'sasrt_rt2_pages_tail', "render thread: PagesClean's last 1-7 pages of a range in one masked NEON block when none of their cards is written"),
    ('kRt2ColorAliasMemo', 'sasrt_rt2_color_alias_memo', "render thread: ColorAliasesLocked's answer kept per surface until a target is made or retired"),
    ('kRt2RepeatRecordedIndex', 'sasrt_rt2_repeat_recorded_index', "render thread: WholeRepeatHit reads the replay's recorded index buffer, as WholeGeometryTry does (a correctness fix too)"),
    ('kRt2HeldExportBitmap', 'sasrt_rt2_held_export_bitmap', "render thread: GetStreamSource looks up the kept exports only where a 64 KB granule bitmap says one may lie"),
    ('kRt2PlaceWaitFree', 'sasrt_rt2_place_wait_unlocked', "render thread: a same-frame place's wait without State().mutex held (spin, then a timed wait)"),
    ('kRt2RingPrefetch', 'sasrt_rt2_ring_prefetch', "render thread: the next ring item's narrowed device delta prefetched to six lines, not four"),
    ('kRt2ReadableMemo', 'sasrt_rt2_readable_memo', "render thread: the vertex fills' guest readability answers kept while no page has lost read access (no heap mutex, no page walk)"),
    ('kRt2BindLayoutNarrow', 'sasrt_rt2_bind_layout_narrow', "render thread: a layout change elsewhere binds the fast draw's targets again only when its own targets are not in their bind layouts"),
    ('kRt2TextureMemoTwoWay', 'sasrt_rt2_texture_memo_two_way', "render thread: the texture slot memo two-way (2,048 sets of two), the way of an earlier frame replaced"),
    ('kRt2RepeatRing', 'sasrt_rt2_repeat_ring', "render thread: WholeGeometryTry's repeat answer kept for the last four meshes of a kick, not one"),
]
ITEMS3 = []
f3 = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'items3.txt')
if os.path.exists(f3):
    for line in open(f3, encoding='utf-8'):
        line = line.rstrip('\n')
        if line.strip() and not line.startswith('#'):
            ITEMS3.append(tuple(line.split('|', 3)))
BS = chr(92)

p = ROOT + 'sasrt_gpu_round.h'
s = open(p, encoding='utf-8').read()
start = s.index('  X(kRtCachedExportSeeds,')
end = s.index('#define SASRT_GPU_ROUND_RT2_FIRST')
cached = re.match(r'  X\(kRtCachedExportSeeds, [^\n]*?"\)', s[start:]).group(0)
lines = [cached + ' ' + BS,
         '  /* the second render-thread round (2026-11-20, the user: "35 ideas ... to make the render thread cheaper"; '
         'docs/render-thread-ideas-1120.md): A/B 339 and up, all at once 401 */ ' + BS]
ALL = ITEMS + [it[:3] for it in ITEMS3]
for i, (name, key, what) in enumerate(ALL):
    if ITEMS3 and i == len(ITEMS):
        lines.append('  /* the third render-thread round (2026-11-20, the user: "Come up with 35 more ... Do a 35 batch"; '
                     'docs/render-thread-ideas-1120.md): all at once 402 */ ' + BS)
    line = '  X(%s, %s, "%s")' % (name, key, what)
    if i + 1 < len(ALL):
        line += ' ' + BS
    lines.append(line)
s = s[:start] + '\n'.join(lines) + '\n\n' + s[end:]
first3 = ITEMS3[0][0] if ITEMS3 else 'kCount'
if '#define SASRT_GPU_ROUND_RT3_FIRST' in s:
    s = re.sub(r'#define SASRT_GPU_ROUND_RT3_FIRST [A-Za-z0-9_]+', '#define SASRT_GPU_ROUND_RT3_FIRST ' + first3, s)
else:
    s = s.replace('#define SASRT_GPU_ROUND_RT2_FIRST kRt2SlotIndex',
                  '#define SASRT_GPU_ROUND_RT2_FIRST kRt2SlotIndex\n#define SASRT_GPU_ROUND_RT3_FIRST ' + first3)
open(p, 'w', encoding='utf-8').write(s)

p = ROOT + 'sasrt_gpu_round.cpp'
s = open(p, encoding='utf-8').read()
anchor = 'REXCVAR_DEFINE_BOOL(sasrt_gpu_cut_ambient_sky, false, "SASRT/GPU",'
added = 0
for it in ITEMS3:
    name, key, what = it[:3]
    desc = it[3] if len(it) > 3 else what
    if 'REXCVAR_DEFINE_BOOL(%s,' % key in s:
        continue
    text = ('REXCVAR_DEFINE_BOOL(%s, true, "SASRT/RenderThread",\n'
            '                    "Render thread (third round, 2026-11-20; docs/render-thread-ideas-1120.md): %s")\n'
            '    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\n') % (key, desc.replace('"', "'"))
    s = s.replace(anchor, text + anchor, 1)
    added += 1
open(p, 'w', encoding='utf-8').write(s)
print('items', len(ITEMS), '+', len(ITEMS3), 'cvars added', added, 'total', 83 + len(ALL))
