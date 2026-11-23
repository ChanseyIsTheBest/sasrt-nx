#!/usr/bin/env python3
"""sasrt-nx (2026-11-08): resolves the diff3 conflict hunks tools/ult_merge.py left, one file at a time, by a choice per
hunk: ours, theirs, ours+theirs, theirs+ours, or the literal text of a file (custom:<path>).
    python tools/ult_resolve.py <merged file> <choice for hunk 1> [<choice for hunk 2> ...]
A single choice applies to every hunk. The resolutions made for the move to the ultimate base are listed in
docs/ultimate-base.md."""
import sys

path, choices = sys.argv[1], sys.argv[2:]
raw = open(path, 'rb').read()
crlf = b'\r\n' in raw
lines = raw.decode('utf-8').replace('\r\n', '\n').split('\n')
out = []
k = 0
i = 0
while i < len(lines):
    if not lines[i].startswith('<<<<<<< '):
        out.append(lines[i])
        i += 1
        continue
    parts = {'ours': [], 'ancestor': [], 'theirs': []}
    cur = 'ours'
    i += 1
    while not lines[i].startswith('>>>>>>> '):
        if lines[i].startswith('||||||| '):
            cur = 'ancestor'
        elif lines[i].startswith('======='):
            cur = 'theirs'
        else:
            parts[cur].append(lines[i])
        i += 1
    i += 1
    choice = choices[k] if k < len(choices) else choices[-1]
    k += 1
    if choice == 'ours':
        out += parts['ours']
    elif choice == 'theirs':
        out += parts['theirs']
    elif choice == 'ours+theirs':
        out += parts['ours'] + parts['theirs']
    elif choice == 'theirs+ours':
        out += parts['theirs'] + parts['ours']
    elif choice.startswith('custom:'):
        out += open(choice[7:], encoding='utf-8').read().rstrip('\n').split('\n')
    else:
        sys.exit('unknown choice ' + choice)
text = '\n'.join(out)
if crlf:
    text = text.replace('\n', '\r\n')
open(path, 'wb').write(text.encode('utf-8'))
print('%s: %d hunks resolved' % (path, k))
