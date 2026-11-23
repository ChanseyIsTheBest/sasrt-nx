#!/usr/bin/env python3
"""sasrt-nx (2026-11-21, the audio to Opus): what SASRT's Wwise packages hold. Each Data/sound/*.pck is an AKPK
(big-endian on the 360): a header (header size, version, language map size, sound bank table size, streamed file table
size, external file table size), the language map, then the tables (a count, then entries of u32 id, u32 block size,
u32 size, u32 start block, u32 language: the file at start block x block size). A streamed file is a WEM (RIFX, big
endian: 'fmt ', maybe 'seek' etc., 'data'); a sound bank (BKHD ...) holds its in-memory WEMs in DIDX (u32 id, u32
offset, u32 size each, offsets in DATA) and DATA.

  python tools/wwise_pck_survey.py DIR [--list]
"""
import collections
import os
import struct
import sys

FORMATS = {0x0001: 'PCM', 0xFFFE: 'PCM(ext)', 0x0165: 'XMA1', 0x0166: 'XMA2', 0x0002: 'ADPCM', 0xFFFF: 'Vorbis'}


def be32(d, o):
    return struct.unpack_from('>I', d, o)[0]


def riff_chunks(d, base, size):
    """RIFX chunks of the WEM at base: {name: (offset of payload, size)}."""
    out = {}
    if d[base:base + 4] != b'RIFX' or d[base + 8:base + 12] != b'WAVE':
        return None
    p = base + 12
    end = base + min(size, 8 + be32(d, base + 4))
    while p + 8 <= end:
        name, ln = d[p:p + 4], be32(d, p + 4)
        out.setdefault(name.decode('latin1'), (p + 8, ln))
        p += 8 + ln + (ln & 1)
    return out


def wem_info(d, base, size):
    ch = riff_chunks(d, base, size)
    if not ch or 'fmt ' not in ch or 'data' not in ch:
        return None
    fo, fl = ch['fmt ']
    tag, chans, rate = struct.unpack_from('>HHI', d, fo)
    info = dict(format=FORMATS.get(tag, hex(tag)), channels=chans, rate=rate, data_offset=ch['data'][0] - base,
                data_size=ch['data'][1], chunks=list(ch))
    if tag == 0x0166 and fl >= 34:
        # XMA2WAVEFORMATEX after WAVEFORMATEX(18): u16 NumStreams, u32 ChannelMask, u32 SamplesEncoded, u32 BytesPerBlock,
        # u32 PlayBegin, u32 PlayLength, u32 LoopBegin, u32 LoopLength, u8 LoopCount, u8 EncoderVersion, u16 BlockCount
        info['streams'] = struct.unpack_from('>H', d, fo + 18)[0]
        info['samples'] = be32(d, fo + 24)
        info['block_bytes'] = be32(d, fo + 28)
        info['loop'] = (be32(d, fo + 40), be32(d, fo + 44), d[fo + 48])
    return info


def tables(d):
    if d[:4] != b'AKPK':
        raise SystemExit('not an AKPK')
    hsize, ver, lang, banks, streams = struct.unpack_from('>IIIII', d, 4)
    ext = hsize - 20 - lang - banks - streams
    p = 8 + 20 + lang
    out = []
    for kind, size in (('bank', banks), ('stream', streams)):
        n = be32(d, p)
        for k in range(n):
            fid, block, fsize, start, lid = struct.unpack_from('>IIIII', d, p + 4 + 20 * k)
            out.append((kind, fid, start * block, fsize, lid))
        p += size
    return out, ext


def bank_wems(d, base, size):
    """The WEMs inside a sound bank: [(id, offset in the file, size)]."""
    p, end = base, base + size
    didx = data = None
    while p + 8 <= end:
        name = d[p:p + 4]
        ln = be32(d, p + 4)
        if name == b'DIDX':
            didx = (p + 8, ln)
        elif name == b'DATA':
            data = p + 8
        p += 8 + ln
    out = []
    if didx and data is not None:
        for k in range(didx[1] // 12):
            wid, off, sz = struct.unpack_from('>III', d, didx[0] + 12 * k)
            out.append((wid, data + off, sz))
    return out


def main():
    root = sys.argv[1]
    listing = '--list' in sys.argv
    total = collections.Counter()
    nsounds = collections.Counter()
    for name in sorted(os.listdir(root)):
        if not name.lower().endswith('.pck'):
            continue
        d = open(os.path.join(root, name), 'rb').read()
        files, ext = tables(d)
        per = collections.Counter()
        cnt = collections.Counter()
        wems = []
        for kind, fid, off, fsize, lid in files:
            if kind == 'stream':
                wems.append(('stream', fid, off, fsize))
            else:
                for wid, woff, wsz in bank_wems(d, off, fsize):
                    wems.append(('bank', wid, woff, wsz))
        for where, wid, off, sz in wems:
            info = wem_info(d, off, sz)
            if not info:
                key = (where, 'not RIFX')
            else:
                key = (where, info['format'], info['rate'], info['channels'], info.get('streams'))
            per[key] += sz
            cnt[key] += 1
            total[key[1:] if info else key] += sz
            nsounds[key[1:] if info else key] += 1
            if listing and info and info['format'] == 'XMA2':
                print(f'  {name} {where} {wid:08X} at {off} {sz} {info}')
        print(f'{name}: {len(d) / 1e6:.1f} MB, {len(files)} table entries, external table {ext} bytes')
        for key in sorted(per, key=lambda k: -per[k]):
            print(f'    {cnt[key]:5d} x {key}: {per[key] / 1e6:.1f} MB')
    print('all packages:')
    for key in sorted(total, key=lambda k: -total[k]):
        print(f'    {nsounds[key]:5d} x {key}: {total[key] / 1e6:.1f} MB')


if __name__ == '__main__':
    main()
