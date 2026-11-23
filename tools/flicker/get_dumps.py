"""Download the card's shadow_dump files named in a list ("size name" lines, from tools/switch_remote.py ls shadow_dump) in
one ftp session (switch_remote.ftp_get_many).  python tools/flicker/get_dumps.py <list> <out dir>"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import switch_remote as sr

lst, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
items = []
for line in open(lst):
    if line.strip():
        size, name = line.split()
        items.append((sr.sd_path('shadow_dump/' + name), os.path.join(out, name), int(size)))
failed = sr.ftp_get_many('192.168.1.197', items, log=lambda t: print(t, flush=True))
print('done: %d files, %d failed' % (len(items), len(failed)), flush=True)
for f in failed:
    print('FAILED', f, flush=True)
