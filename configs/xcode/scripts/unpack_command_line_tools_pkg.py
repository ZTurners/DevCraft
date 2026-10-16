#!/usr/bin/env python3
"""Unpack an Apple distribution .pkg into a plain folder.

usage: unpack_command_line_tools_pkg.py <pkg> <dest> [strip_prefix]

Opens the xar container with /usr/bin/xar, decodes the Payload stream
(pbzx-chunked XZ on modern Apple pkgs) and writes out the cpio entries —
files, directories and symlinks — under <dest>. Runs entirely as the
current user: nothing is installed system-wide and no admin rights are
involved. Standard library only.
"""

import gzip
import lzma
import os
import stat
import subprocess
import sys
import tempfile


def decode_payload(path):
    """Return the raw cpio stream stored in a pkg Payload file."""
    with open(path, 'rb') as fh:
        data = fh.read()
    if data[:4] == b'pbzx':
        out = bytearray()
        offset = 12  # magic + u64 total uncompressed size
        # Chunk framing: [u64 uncompressed size][u64 stored size][blob];
        # blobs starting with the XZ magic are compressed, others stored raw.
        while offset + 16 <= len(data):
            offset += 8
            stored_size = int.from_bytes(data[offset:offset + 8], 'big')
            offset += 8
            blob = data[offset:offset + stored_size]
            offset += stored_size
            if blob[:6] == b'\xfd7zXZ\x00':
                out.extend(lzma.decompress(blob))
            else:
                out.extend(blob)
        return bytes(out)
    if data[:2] == b'\x1f\x8b':
        return gzip.decompress(data)
    if data[:6] == b'\xfd7zXZ\x00':
        return lzma.decompress(data)
    return data


def iter_cpio(stream):
    """Yield (name, mode, filesize, data_offset) from a cpio stream.

    Supports both Apple payload variants: "newc" (SVR4 ASCII, 070701/2) and
    "odc" (portable ASCII, 070707).
    """
    offset = 0
    length = len(stream)
    while offset + 76 <= length:
        magic = stream[offset:offset + 6]
        if magic in (b'070701', b'070702'):
            fields = [int(stream[offset + 6 + i * 8:offset + 14 + i * 8], 16) for i in range(13)]
            mode, filesize, namesize = fields[1], fields[6], fields[11]
            name_offset = offset + 110
            data_offset = (name_offset + namesize + 3) & ~3
            next_offset = (data_offset + filesize + 3) & ~3
        elif magic == b'070707':
            mode = int(stream[offset + 18:offset + 24], 8)
            namesize = int(stream[offset + 59:offset + 65], 8)
            filesize = int(stream[offset + 65:offset + 76], 8)
            name_offset = offset + 76
            data_offset = name_offset + namesize
            next_offset = data_offset + filesize
        else:
            raise SystemExit(f'not a supported cpio archive (magic {magic!r} at offset {offset})')
        name = stream[name_offset:name_offset + max(0, namesize - 1)].decode('utf-8', 'replace')
        yield name, mode, filesize, data_offset
        if name == 'TRAILER!!!':
            return
        offset = next_offset


def unpack(pkg, dest, strip_prefix=''):
    os.makedirs(dest, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='devcraft_pkg_') as xar_dir:
        subprocess.run(['/usr/bin/xar', '-x', '-f', pkg, '-C', xar_dir],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        payload = os.path.join(xar_dir, 'Payload')
        if not os.path.exists(payload):
            raise SystemExit(f'no Payload entry in {pkg}')
        stream = decode_payload(payload)

    dest_abs = os.path.abspath(dest)
    written = 0
    for name, mode, filesize, data_offset in iter_cpio(stream):
        if name == 'TRAILER!!!':
            break
        while name.startswith('./'):
            name = name[2:]
        name = name.lstrip('/')
        if not name:
            continue
        if strip_prefix and name.startswith(strip_prefix + '/'):
            name = name[len(strip_prefix) + 1:]
        out_path = os.path.normpath(os.path.join(dest_abs, name))
        if os.path.commonpath([out_path, dest_abs]) != dest_abs:
            raise SystemExit(f'refusing unsafe pkg entry path: {name!r}')
        written += 1
        if written % 5000 == 0:
            print(f'  ... {written} entries')
        if stat.S_ISLNK(mode):
            target = stream[data_offset:data_offset + filesize].decode('utf-8', 'replace')
            if os.path.lexists(out_path):
                os.remove(out_path)
            os.symlink(target, out_path)
        elif stat.S_ISDIR(mode):
            os.makedirs(out_path, exist_ok=True)
        else:
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, 'wb') as out_fh:
                out_fh.write(stream[data_offset:data_offset + filesize])
            os.chmod(out_path, mode & 0o7777)
    print(f'{os.path.basename(pkg)}: {written} entries -> {dest}')


if __name__ == '__main__':
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    unpack(sys.argv[1], sys.argv[2], sys.argv[3].strip('/') if len(sys.argv) > 3 else '')
