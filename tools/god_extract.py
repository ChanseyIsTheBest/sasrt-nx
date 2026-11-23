#!/usr/bin/env python3
"""Extracts an Xbox 360 Games on Demand package (GOD) into a folder, checking every SHA-1 hash on the way.

A GOD package is an STFS header file (LIVE/CON/PIRS, content type 0x00007000 for Games on Demand, 0x00004000 for a
disc install) whose volume is SVOD: the disc's game partition (XDVDFS), cut into the files <header>.data/DataNNNN.
Each data file is a master hash table (0x1000 bytes) followed by up to 203 groups of one level-0 hash table and
204 data blocks of 0x1000 bytes:

    level-0 table entry j = SHA-1 of data block j of its group
    master entry g        = SHA-1 of level-0 table g of the file
    master entry 203      = SHA-1 of the next data file's master table
    header root hash      = SHA-1 of Data0000's master table (SVOD volume descriptor, header offset 0x37D)

so every block read can be checked against the header. This tool checks the master tables of all data files first,
then every level-0 table and data block it reads; --verify-all reads the whole image instead (a full integrity check
of the dump). It only reads the package.

Usage:
    python tools/god_extract.py <header file>                    extract into assets/game_root
    python tools/god_extract.py <header file> -o some/folder     extract somewhere else
    python tools/god_extract.py <header file> --list             list the files, extract nothing
    python tools/god_extract.py <header file> --xex-only         extract only the .xex files
    python tools/god_extract.py <header file> --verify-all       check every block of the image, extract nothing

Pure Python 3.8+, no dependencies. The XEX header of default.xex is printed by tools/extract_iso.py --info.
"""

import argparse
import hashlib
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract_iso  # noqa: E402  (XDVDFS directory walk and XEX header printer)

BLOCK = 0x1000                      # SVOD data block and hash table size
SECTOR = 0x800                      # XDVDFS sector
HASH = 20                           # SHA-1
BLOCKS_PER_GROUP = 204              # data blocks covered by one level-0 table
GROUPS_PER_FILE = 203               # level-0 tables covered by one master table
BLOCKS_PER_FILE = BLOCKS_PER_GROUP * GROUPS_PER_FILE
GROUP_SPAN = (1 + BLOCKS_PER_GROUP) * BLOCK
XDVDFS_MAGIC = b"MICROSOFT*XBOX*MEDIA"

CONTENT_TYPES = {0x00004000: "installed disc game", 0x00007000: "Games on Demand", 0x000D0000: "Xbox Live Arcade"}


class GodError(Exception):
    pass


class GodPackage:
    def __init__(self, header_path):
        with open(header_path, "rb") as f:
            hdr = f.read(0xB000)
        if hdr[:4] not in (b"LIVE", b"PIRS", b"CON "):
            raise GodError("%s is not an STFS header (magic %r)" % (header_path, hdr[:4]))
        self.content_type = struct.unpack_from(">I", hdr, 0x344)[0]
        self.media_id, _, _, self.title_id = struct.unpack_from(">IIII", hdr, 0x354)
        self.display_name = hdr[0x411:0x491].decode("utf-16-be", "replace").split("\0")[0]
        if struct.unpack_from(">I", hdr, 0x3A9)[0] != 1:
            raise GodError("the volume is STFS, not SVOD: use tools/stfs_extract.py")
        self.file_count = struct.unpack_from(">I", hdr, 0x39D)[0]
        self.combined_size = struct.unpack_from(">Q", hdr, 0x3A1)[0]
        vd = hdr[0x379:0x379 + 0x24]
        self.root_hash = vd[0x04:0x18]
        self.features = vd[0x18]
        self.data_blocks = (vd[0x19] << 16) | (vd[0x1A] << 8) | vd[0x1B]

        folder = header_path + ".data"
        self.paths = [os.path.join(folder, "Data%04d" % i) for i in range(self.file_count)]
        missing = [p for p in self.paths if not os.path.isfile(p)]
        if missing:
            raise GodError("missing data files: %s" % ", ".join(missing))
        sizes = [os.path.getsize(p) for p in self.paths]
        if sum(sizes) != self.combined_size:
            raise GodError("the data files hold %d bytes, the header says %d" % (sum(sizes), self.combined_size))
        self.files = [open(p, "rb") for p in self.paths]
        # Data blocks in each file: the last one ends with a partial group.
        self.file_blocks = []
        for size in sizes:
            groups, rest = divmod(size - BLOCK, GROUP_SPAN)
            self.file_blocks.append(groups * BLOCKS_PER_GROUP + max(rest // BLOCK - 1, 0))
        if sum(self.file_blocks) != self.data_blocks:
            raise GodError("the data files hold %d data blocks, the header says %d"
                           % (sum(self.file_blocks), self.data_blocks))

        self.masters = self._check_masters()
        self.level0 = {}
        self.blocks_checked = 0
        # Where the image starts: the XDVDFS volume descriptor is partition sector 32. Classic layout (the XSF
        # header is kept): data block 0 is partition sector 0. Enhanced GDF layout (XGD3): the first 32 sectors are
        # left out and data block 0 starts with the volume descriptor.
        self.first_sector = None
        for first_sector in (0, 32):
            self.first_sector = first_sector
            if self.read(32 * SECTOR, len(XDVDFS_MAGIC)) == XDVDFS_MAGIC:
                break
        else:
            raise GodError("no XDVDFS volume descriptor found (features 0x%02X)" % self.features)

    def _check_masters(self):
        masters = []
        expected = self.root_hash
        for i, f in enumerate(self.files):
            f.seek(0)
            master = f.read(BLOCK)
            if hashlib.sha1(master).digest() != expected:
                raise GodError("master hash table of %s does not match %s"
                               % (self.paths[i], "the header" if i == 0 else self.paths[i - 1]))
            masters.append(master)
            expected = master[GROUPS_PER_FILE * HASH:(GROUPS_PER_FILE + 1) * HASH]
        return masters

    def _level0(self, file_index, group):
        key = (file_index, group)
        table = self.level0.get(key)
        if table is None:
            f = self.files[file_index]
            f.seek(BLOCK + group * GROUP_SPAN)
            table = f.read(BLOCK)
            if hashlib.sha1(table).digest() != self.masters[file_index][group * HASH:(group + 1) * HASH]:
                raise GodError("level-0 hash table %d of %s is corrupt" % (group, self.paths[file_index]))
            if len(self.level0) > 4096:
                self.level0.clear()
            self.level0[key] = table
        return table

    def read_blocks(self, block, count):
        """Data blocks [block, block + count) of the image, each checked against its level-0 table."""
        out = bytearray()
        while count > 0:
            file_index, in_file = divmod(block, BLOCKS_PER_FILE)
            if file_index >= self.file_count or in_file >= self.file_blocks[file_index]:
                raise GodError("read past the end of the image (data block %d)" % block)
            group, first = divmod(in_file, BLOCKS_PER_GROUP)
            n = min(count, BLOCKS_PER_GROUP - first, self.file_blocks[file_index] - in_file)
            table = self._level0(file_index, group)
            f = self.files[file_index]
            f.seek(BLOCK + group * GROUP_SPAN + BLOCK + first * BLOCK)
            data = f.read(n * BLOCK)
            if len(data) != n * BLOCK:
                raise GodError("%s is truncated" % self.paths[file_index])
            view = memoryview(data)
            for j in range(n):
                k = first + j
                if hashlib.sha1(view[j * BLOCK:(j + 1) * BLOCK]).digest() != table[k * HASH:(k + 1) * HASH]:
                    raise GodError("data block %d (%s, group %d, entry %d) fails its SHA-1 check"
                                   % (block + j, self.paths[file_index], group, k))
            self.blocks_checked += n
            out += data
            block += n
            count -= n
        return bytes(out)

    def read(self, offset, size):
        """`size` bytes at partition offset `offset`."""
        start = offset - self.first_sector * SECTOR
        if start < 0:
            raise GodError("partition offset 0x%X lies before the start of the image" % offset)
        first = start // BLOCK
        last = (start + size + BLOCK - 1) // BLOCK
        data = self.read_blocks(first, last - first)
        skip = start - first * BLOCK
        return data[skip:skip + size]

    def verify_all(self):
        """Reads and checks every data block of every file."""
        total = self.data_blocks
        done = 0
        step = BLOCKS_PER_GROUP * 64
        while done < total:
            n = min(step, total - done)
            self.read_blocks(done, n)
            done += n
            print("  %5.1f%%  %d of %d blocks" % (100.0 * done / total, done, total), end="\r")
        print()


class PartitionReader:
    """File-like view of the game partition for extract_iso's XDVDFS walker (seek + read only)."""

    def __init__(self, package):
        self.package = package
        self.pos = 0

    def seek(self, pos, whence=0):
        if whence != 0:
            raise OSError("only absolute seeks are supported")
        self.pos = pos

    def read(self, size):
        data = self.package.read(self.pos, size)
        self.pos += len(data)
        return data


def main(argv=None):
    parser = argparse.ArgumentParser(description="Extracts an Xbox 360 Games on Demand package, checking its hashes.")
    parser.add_argument("header", help="the GOD header file (its data files are in <header>.data/)")
    parser.add_argument("-o", "--output", default=extract_iso.default_output(),
                        help="destination folder (default: assets/game_root of this repository)")
    parser.add_argument("--list", action="store_true", help="list the contents, extract nothing")
    parser.add_argument("--xex-only", action="store_true", help="extract only the .xex files")
    parser.add_argument("--verify-all", action="store_true", help="check every block of the image, extract nothing")
    args = parser.parse_args(argv)

    try:
        god = GodPackage(args.header)
        print("%r: title %08X, media %08X, content type %08X (%s)"
              % (god.display_name, god.title_id, god.media_id, god.content_type,
                 CONTENT_TYPES.get(god.content_type, "unknown")))
        print("%d data files, %s bytes, %d data blocks; master tables match the header (SHA-1)"
              % (god.file_count, f"{god.combined_size:,}", god.data_blocks))
        print("image starts at partition sector %d (%s layout)"
              % (god.first_sector, "enhanced GDF" if god.first_sector else "classic"))
        if args.verify_all:
            god.verify_all()
            print("all %d data blocks match their hash tables" % god.blocks_checked)
            return 0

        fh = PartitionReader(god)
        root_sector, root_size = extract_iso.read_volume_descriptor(fh, 0)
        entries = list(extract_iso.walk(fh, 0, root_sector, root_size))
        files = [(p, e) for p, e in entries if not e["is_dir"]]
        print("%d files, %d directories, %s bytes in total\n"
              % (len(files), len(entries) - len(files), f"{sum(e['size'] for _, e in files):,}"))
        if args.list:
            for path, entry in entries:
                print("  [dir]  %s" % path if entry["is_dir"] else "  %12s  %s" % (f"{entry['size']:,}", path))
            return 0

        wanted = files
        if args.xex_only:
            wanted = [(p, e) for p, e in files if p.lower().endswith((".xex", ".xexp"))]
        else:
            for path, entry in entries:
                if entry["is_dir"]:
                    os.makedirs(extract_iso._safe_destination(args.output, path), exist_ok=True)
        done = 0
        for path, entry in wanted:
            extract_iso.extract_file(fh, 0, entry, extract_iso._safe_destination(args.output, path))
            done += 1
            if done % 100 == 0:
                print("  ... %d files" % done)
        print("\n%d files extracted into %s; %d data blocks read, all match their SHA-1 hashes"
              % (done, args.output, god.blocks_checked))
        xex = os.path.join(args.output, "default.xex")
        if os.path.exists(xex):
            print()
            extract_iso.print_xex_info(xex)
    except (GodError, extract_iso.ExtractError) as error:
        print("error: %s" % error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
