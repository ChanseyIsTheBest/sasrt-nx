# sasrt-nx (2026-11-20): registers a fourth-round render-thread item: its X line at the end of SASRT_GPU_ROUND_ITEMS in
# sasrt_gpu_round.h (the first one also starts the round: a comment, SASRT_GPU_ROUND_RT4_FIRST, A/B group 403 in On()
# and AbName), and its key in sasrt_gpu_round.cpp. Idempotent per name.
#   python r4_item.py NAME KEY "short text" "key description" [default true|false]
import re
import sys

ROOT = r'D:/sonic transformed/sasrt-nx/app/src/renut_engine/gpu/'
name, key, short, desc = sys.argv[1:5]
default = sys.argv[5] if len(sys.argv) > 5 else 'true'
BS = chr(92)

p = ROOT + 'sasrt_gpu_round.h'
s = open(p, encoding='utf-8').read()
if 'X(%s,' % name not in s:
    end = s.index('\n\n#define SASRT_GPU_ROUND_RT2_FIRST')
    last_line_start = s.rindex('\n', 0, end) + 1
    last = s[last_line_start:end]
    assert last.startswith('  X(') and not last.endswith(BS), last
    add = ''
    if '#define SASRT_GPU_ROUND_RT4_FIRST' not in s:
        add += ('  /* the fourth render-thread round (2026-11-20, the user: "do these please and then do a massive ab of '
                'render thread stuff"; the third table\'s items left; docs/render-thread-ideas-1120.md): all at once '
                '403 */ ' + BS + '\n')
        s = s.replace('#define SASRT_GPU_ROUND_RT3_FIRST kRt3WordsOwnerTable',
                      '#define SASRT_GPU_ROUND_RT3_FIRST kRt3WordsOwnerTable\n#define SASRT_GPU_ROUND_RT4_FIRST ' + name)
        s = s.replace('constexpr int kAbRt3Group = 402;',
                      'constexpr int kAbRt3Group = 402;\n// sasrt-nx (2026-11-20): A/B target 403 switches the fourth '
                      'render-thread round\'s items (from SASRT_GPU_ROUND_RT4_FIRST on).\nconstexpr int kAbRt4Group = 403;')
        s = s.replace('kAbRt3Group < 512, "banjo_renut_ab_targets', 'kAbRt4Group < 512, "banjo_renut_ab_targets')
        s = s.replace('!(ab == kAbRt3Group && i >= SASRT_GPU_ROUND_RT3_FIRST);',
                      '!(ab == kAbRt3Group && i >= SASRT_GPU_ROUND_RT3_FIRST) &&\n         '
                      '!(ab == kAbRt4Group && i >= SASRT_GPU_ROUND_RT4_FIRST);')
    add += '  X(%s, %s, "%s")' % (name, key, short.replace('"', "'"))
    s = s[:end] + ' ' + BS + '\n' + add + s[end:]
    open(p, 'w', encoding='utf-8').write(s)

p = ROOT + 'sasrt_gpu_round.cpp'
s = open(p, encoding='utf-8').read()
if 'kAbRt4Group' not in s:
    s = s.replace('''  if (target == kAbRt3Group)  // sasrt-nx (2026-11-20)
    return "the third render-thread round's items, all at once (sasrt_rt3_*, A/B 402)";''',
                  '''  if (target == kAbRt3Group)  // sasrt-nx (2026-11-20)
    return "the third render-thread round's items, all at once (sasrt_rt3_*, A/B 402)";
  if (target == kAbRt4Group)  // sasrt-nx (2026-11-20)
    return "the fourth render-thread round's items, all at once (sasrt_rt4_*, A/B 403)";''')
    assert 'kAbRt4Group' in s
if 'REXCVAR_DEFINE_BOOL(%s,' % key not in s:
    anchor = 'REXCVAR_DEFINE_BOOL(sasrt_gpu_cut_ambient_sky, false, "SASRT/GPU",'
    text = ('REXCVAR_DEFINE_BOOL(%s, %s, "SASRT/RenderThread",\n'
            '                    "Render thread (fourth round, 2026-11-20; docs/render-thread-ideas-1120.md): %s")\n'
            '    .lifecycle(rex::cvar::Lifecycle::kInitOnly);\n') % (key, default, desc.replace('"', "'"))
    s = s.replace(anchor, text + anchor, 1)
open(p, 'w', encoding='utf-8').write(s)
h = open(ROOT + 'sasrt_gpu_round.h', encoding='utf-8').read()
items = re.findall(r'^  X\((k\w+),', h, re.M)
print('%s: index %d, A/B %d; %d items' % (name, items.index(name), 256 + items.index(name), len(items)))
