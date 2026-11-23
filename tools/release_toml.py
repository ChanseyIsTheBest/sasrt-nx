"""sasrt-nx (2026-11-22, the user: "make sure all logging besides crash logging is turned off in release build"): the
release's sasrt.toml, from app/sasrt_switch.toml with every log and diagnostic off:
  log_level "off"                    no game log, no deko3d.log (banjo_renut_deko3d.cpp), no stderr file; the
                                     crash handler's logs/rex/rex_crash.log (and its stderr copy) are still written
  switch_profile_stacks false        the CPU sampler (logs/rex/rex_profile_NNN.log, and its cost)
  masseffect_gpu_marks_categories    the GPU timestamps at every category change (fewer GPU flushes)
  renut_gpu_profile 0                the 10 s GPU profile
  sasrt_renut_diag_shadow_dump ""    the shadow dumps (and their A+B+X+Y chord)
  switch_perf_count_calls ... sasrt_enhancements_report_s   the test runs' diagnostics (call counts, memory report,
                                     slow-frame and flash watches, GPU census, formats, the "[enh] uses" line)
Every changed line is checked to exist once; the rest of the file is kept as it is.

    python tools/release_toml.py [--src app/sasrt_switch.toml] --out <release folder>/sasrt.toml
"""
import argparse
import re
import sys

SET = {
    'log_level': '"off"',
    'switch_profile_stacks': 'false',
    'masseffect_gpu_marks_categories': 'false',
    'renut_gpu_profile': '0.0',
    'sasrt_renut_diag_shadow_dump': '""',
    'sasrt_renut_diag_shadow_dump_buttons': 'false',
    # 2026-11-23 (the user: "make sure release build has no profiling"): the test runs' diagnostics, off by default in
    # the code since then and on in app/sasrt_switch.toml; written off here too
    'switch_perf_count_calls': 'false',
    'renut_memory_report': '0.0',
    'sasrt_renut_diag_slow_frames': 'false',
    'sasrt_renut_diag_flash_watch': 'false',
    'renut_diag_gpu_census': 'false',
    'renut_diag_formats': 'false',
    'sasrt_enhancements_report_s': '0',
}
NOTE = ('# sasrt-nx release (tools/release_toml.py): every log and diagnostic off but the crash reports '
        '(logs/rex/rex_crash.log).\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default='app/sasrt_switch.toml')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    text = open(a.src, encoding='utf-8').read()
    for key, value in SET.items():
        pattern = re.compile(rf'^{re.escape(key)}\s*=.*$', re.M)
        hits = pattern.findall(text)
        if len(hits) != 1:
            sys.exit(f'release_toml: {key}: {len(hits)} lines in {a.src}')
        text = pattern.sub(f'{key} = {value}', text)
    with open(a.out, 'w', encoding='utf-8', newline='\n') as f:
        f.write(NOTE + text)
    print(f'{a.out}: ' + ', '.join(f'{k} = {v}' for k, v in SET.items()))


if __name__ == '__main__':
    sys.exit(main())
