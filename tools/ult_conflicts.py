#!/usr/bin/env python3
"""sasrt-nx (2026-11-08): the conflict hunks of a file tools/ult_merge.py wrote (diff3 markers), numbered, each side
cut to N lines (default 40).
    python tools/ult_conflicts.py <merged file> [N]"""
import sys

path = sys.argv[1]
cut = int(sys.argv[2]) if len(sys.argv) > 2 else 40
lines = open(path, encoding='utf-8', errors='replace').read().split('\n')
k = 0
i = 0
while i < len(lines):
    if lines[i].startswith('<<<<<<< '):
        k += 1
        parts = {'ours': [], 'ancestor': [], 'theirs': []}
        cur = 'ours'
        start = i
        i += 1
        while i < len(lines) and not lines[i].startswith('>>>>>>> '):
            if lines[i].startswith('||||||| '):
                cur = 'ancestor'
            elif lines[i].startswith('======='):
                cur = 'theirs'
            else:
                parts[cur].append(lines[i])
            i += 1
        print('=== hunk %d at line %d' % (k, start + 1))
        for name in ('ancestor', 'ours', 'theirs'):
            p = parts[name]
            print('--- %s (%d lines)' % (name, len(p)))
            for l in p[:cut]:
                print('   ' + l[:200])
            if len(p) > cut:
                print('   ...')
    i += 1
