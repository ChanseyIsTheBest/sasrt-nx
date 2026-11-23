#!/usr/bin/env python3
"""sasrt-nx (2026-11-09): rr6-nx's tools/pgo_merge.py (banjo-nx's, from sa2-nx), for sasrt_pgo_*.stream.
Profile-guided optimisation, step 2 of 3 (banjo-nx, 2026-10-21; sa2-nx's tools/win/pgo_merge.ps1 in Python, since
PowerShell scripts do not run on this PC).

Step 1 is the instrumented NRO (a build folder configured with -DSASRT_PGO=generate), played on the console or in
Ryujinx: it writes pgo/sasrt_pgo_<N>.stream next to the NRO (one per session, app/src/banjo_pgo.cpp). Copy that pgo
folder to the PC and run this: every session's counts are added into the .gcda files of the profile folder
(gcov-tool merge-stream), then their summary is filled in (tools/pgo_summary.py: the stream API writes it as zero).
Step 3: a build folder configured with -DSASRT_PGO=use (and -DSASRT_SWITCH_LTO=ON); docs/pgo-lto.md.

  python tools/pgo_merge.py <folder with the .stream files> [<profile folder>] [--gen-build <ELF/NRO>] [--all]

The profile folder is pgo/ at the root of the repository (the build's SASRT_PGO_DIR): one .gcda per object, named by
the object's path in the build folder with # for each separator (GCC's names with -fprofile-prefix-path). The streams
name the files they fill with the profile folder of the PC that built the instrumented NRO: merge on that PC.

merge-stream ADDS to .gcda files already there: a second run with the same streams would count them twice, so this
stops when the profile folder already has .gcda files (move them aside first).

sasrt-nx (2026-11-13): the folder must hold ONE stream (the training rule: one race) unless --all is given, and with
--gen-build <instrumented ELF or NRO> no stream may be older than that build. Cycle B of 2026-11-12 reused a run
folder that still held an 11-11 stream from another build: both were merged, gcov-tool skipped 383 functions on a
cfg_checksum mismatch, about 90 machine copies lost their hot status and the build measured 1.4 % slower.
"""
import os
import subprocess
import sys

TOOL = 'C:/devkitPro/devkitA64/bin/aarch64-none-elf-gcov-tool.exe'


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    args = sys.argv[1:]
    many = '--all' in args
    args = [a for a in args if a != '--all']
    gen_build = None
    if '--gen-build' in args:
        i = args.index('--gen-build')
        gen_build = args[i + 1]
        del args[i:i + 2]
    streams = args[0]
    out = os.path.abspath(args[1]) if len(args) > 1 else os.path.join(root, 'pgo')
    if not os.path.exists(TOOL):
        sys.exit('gcov-tool not found: ' + TOOL)
    files = sorted(f for f in os.listdir(streams) if f.startswith('sasrt_pgo_') and f.endswith('.stream'))
    if not files:
        sys.exit('no sasrt_pgo_*.stream in ' + streams)
    import time
    for f in files:
        print('  %s written %s' % (f, time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(os.path.join(streams, f))))))
    if len(files) > 1 and not many:
        sys.exit('%d streams in %s: one training race makes one stream, so another is probably left over from an older '
                 'build (its functions would not match). Keep only this session\'s stream, or pass --all to merge '
                 'several sessions of the SAME instrumented build' % (len(files), streams))
    if gen_build:
        if not os.path.exists(gen_build):
            sys.exit('--gen-build: no such file ' + gen_build)
        built = os.path.getmtime(gen_build)
        old = [f for f in files if os.path.getmtime(os.path.join(streams, f)) < built]
        if old:
            sys.exit('stream(s) older than the instrumented build %s (%s): %s' % (
                gen_build, time.strftime('%Y-%m-%d %H:%M', time.localtime(built)), ', '.join(old)))
    os.makedirs(out, exist_ok=True)
    if any(f.endswith('.gcda') for f in os.listdir(out)):
        sys.exit(out + ' already has .gcda files: move them aside first (merge-stream would add to them)')
    for f in files:
        path = os.path.join(streams, f)
        print('merging %s (%.1f MB)' % (f, os.path.getsize(path) / 1048576.0), flush=True)
        r = subprocess.run([TOOL, 'merge-stream', path])
        if r.returncode:
            sys.exit('gcov-tool merge-stream failed on ' + path)
    count = sum(1 for f in os.listdir(out) if f.endswith('.gcda'))
    if not count:
        sys.exit('no .gcda file in %s after merging: the streams name another folder (merge on the PC that built the '
                 'instrumented NRO)' % out)
    r = subprocess.run([sys.executable, os.path.join(root, 'tools', 'pgo_summary.py'), out, str(len(files))])
    if r.returncode:
        sys.exit('pgo_summary.py failed')
    print('%d session(s) merged into %d file(s) in %s' % (len(files), count, out))


if __name__ == '__main__':
    main()
