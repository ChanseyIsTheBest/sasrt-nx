"""sasrt-nx (2026-11-22, the user: "change the and in the title to &"): an NRO packaged again from a build's stripped
ELF with another NACP (title, author, version) and icon, without the build: the same commands rexglue_switch_add_nro
runs (nacptool --create, elf2nro), called with no shell between (cmd.exe takes a "&" in the title as a command
separator). Then the NRO's own NACP and icon are read back and printed.

    python tools/nro_repack.py --elf out/nx-inplace/sasrt.stripped.elf --out out/.../sasrt.nro
        --title "Sonic & All-Stars Racing Transformed" --author ChanseyIsTheBest --version 1.0.0 --icon app/icon.jpg
    python tools/nro_repack.py --show some.nro
"""
import argparse
import os
import struct
import subprocess
import sys
import tempfile

DEVKITPRO = os.environ.get('DEVKITPRO', '')
if not os.path.isdir(DEVKITPRO):  # an MSYS path (/opt/devkitpro) Windows' Python cannot open
    DEVKITPRO = 'C:/devkitPro'


def nro_assets(data):
    """(title, author, version, icon bytes) from an NRO's asset section (ASET after the NRO's own size)."""
    if data[0x10:0x14] != b'NRO0':
        raise SystemExit('not an NRO')
    size = struct.unpack_from('<I', data, 0x18)[0]
    aset = data[size:]
    if aset[:4] != b'ASET':
        raise SystemExit('the NRO has no asset section')
    icon_off, icon_size, nacp_off, nacp_size = struct.unpack_from('<QQQQ', aset, 8)
    nacp = aset[nacp_off:nacp_off + nacp_size]
    title = nacp[0:0x200].split(b'\0')[0].decode('utf-8')
    author = nacp[0x200:0x300].split(b'\0')[0].decode('utf-8')
    version = nacp[0x3060:0x3070].split(b'\0')[0].decode('utf-8')
    return title, author, version, aset[icon_off:icon_off + icon_size]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--elf')
    ap.add_argument('--out')
    ap.add_argument('--title')
    ap.add_argument('--author')
    ap.add_argument('--version')
    ap.add_argument('--icon')
    ap.add_argument('--show')
    a = ap.parse_args()
    if not a.show:
        tools = os.path.join(DEVKITPRO, 'tools', 'bin')
        exe = '.exe' if os.name == 'nt' else ''
        with tempfile.TemporaryDirectory() as tmp:
            nacp = os.path.join(tmp, 'app.nacp')
            subprocess.run([os.path.join(tools, 'nacptool' + exe), '--create', a.title, a.author, a.version, nacp],
                           check=True)
            subprocess.run([os.path.join(tools, 'elf2nro' + exe), a.elf, a.out, f'--nacp={nacp}', f'--icon={a.icon}'],
                           check=True)
    path = a.show or a.out
    title, author, version, icon = nro_assets(open(path, 'rb').read())
    kind = 'JPEG' if icon[:2] == bytes([0xFF, 0xD8]) else 'not a JPEG'
    print(f'{path}: "{title}" by "{author}", version {version}, icon {len(icon)} bytes ({kind})')


if __name__ == '__main__':
    sys.exit(main())
