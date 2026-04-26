#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unpack ECNT BL2 optimized preloader image.

Expected layout:
  [bl21][f_header_t][bl22.lzma][bl23.lzma][flash_table]

f_header_t (8 * uint32 LE):
  bl22_length
  bl23_length
  flash_table_length
  lzma_src
  lzma_des
  lzma_length
  lzma_cmd
  reserved
"""

import argparse
import os
import struct
import sys

HEADER_FMT = "<8I"
HEADER_SIZE = struct.calcsize(HEADER_FMT)


def read_all(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def ensure_dir(path: str):
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)


def is_lzma_alone_stream(buf: bytes) -> bool:
    # .lzma "alone" header usually starts with props byte + dict size + uncompressed size
    # Common first byte is 0x5d but we keep loose check to avoid false negatives.
    return len(buf) >= 13 and buf[0] in (0x5d, 0x6d, 0x7d)


def main() -> int:
    p = argparse.ArgumentParser(description="Unpack preloader.bin into bl21/header/bl22/bl23/flash_table")
    p.add_argument("input", help="preloader.bin path")
    p.add_argument("-o", "--outdir", default="unpacked_preloader", help="output directory")
    p.add_argument("--bl21-size", type=lambda x: int(x, 0), default=None,
                   help="Known bl21 size (hex/dec), e.g. 0x3c00. If omitted, auto-scan for header.")
    p.add_argument("--scan-max", type=lambda x: int(x, 0), default=0x200000,
                   help="Max bytes to scan for header when --bl21-size is not given")
    p.add_argument("--strict", action="store_true", help="Fail if lzma_length != bl22_length")
    args = p.parse_args()

    data = read_all(args.input)
    total = len(data)

    header_off = None
    fields = None

    def try_header_at(off: int):
        if off < 0 or off + HEADER_SIZE > total:
            return None
        vals = struct.unpack_from(HEADER_FMT, data, off)
        b22, b23, ft, src, des, lzlen, cmd, rsv = vals
        # Basic sanity:
        # lengths non-zero reasonable, payload fit in file
        payload_sum = b22 + b23 + ft
        if payload_sum == 0:
            return None
        end = off + HEADER_SIZE + payload_sum
        if end > total:
            return None
        # optional soft checks
        return vals

    if args.bl21_size is not None:
        header_off = args.bl21_size
        fields = try_header_at(header_off)
        if fields is None:
            print(f"[ERR] No valid header at --bl21-size offset 0x{header_off:X}", file=sys.stderr)
            return 2
    else:
        scan_max = min(args.scan_max, total - HEADER_SIZE)
        # 4-byte alignment scan
        for off in range(0, max(scan_max, 0), 4):
            vals = try_header_at(off)
            if vals is None:
                continue
            b22, b23, ft, src, des, lzlen, cmd, rsv = vals
            # prefer candidate with lzlen == b22 and likely lzma stream right after header
            bl22_start = off + HEADER_SIZE
            bl22_buf = data[bl22_start: bl22_start + min(b22, 32)]
            score = 0
            if lzlen == b22:
                score += 2
            if is_lzma_alone_stream(bl22_buf):
                score += 2
            if cmd in (0, 1):
                score += 1
            # select first good enough candidate
            if score >= 3:
                header_off = off
                fields = vals
                break

        if fields is None:
            print("[ERR] Failed to auto-detect header. Try --bl21-size 0x... explicitly.", file=sys.stderr)
            return 3

    b22, b23, ft, src, des, lzlen, cmd, rsv = fields
    if args.strict and lzlen != b22:
        print(f"[ERR] strict mode: lzma_length(0x{lzlen:X}) != bl22_length(0x{b22:X})", file=sys.stderr)
        return 4

    bl21_start = 0
    bl21_end = header_off
    hdr_start = header_off
    hdr_end = hdr_start + HEADER_SIZE
    bl22_start = hdr_end
    bl22_end = bl22_start + b22
    bl23_start = bl22_end
    bl23_end = bl23_start + b23
    ft_start = bl23_end
    ft_end = ft_start + ft

    if ft_end > total:
        print("[ERR] Computed slices exceed file size.", file=sys.stderr)
        return 5

    outdir = args.outdir
    ensure_dir(outdir)

    bl21_path = os.path.join(outdir, "bl21.bin")
    hdr_path = os.path.join(outdir, "f_header.bin")
    txt_path = os.path.join(outdir, "f_header.txt")
    bl22_path = os.path.join(outdir, "bl22.lzma")
    bl23_path = os.path.join(outdir, "bl23.lzma")
    ft_path = os.path.join(outdir, "flash_table.bin")

    with open(bl21_path, "wb") as f:
        f.write(data[bl21_start:bl21_end])
    with open(hdr_path, "wb") as f:
        f.write(data[hdr_start:hdr_end])
    with open(bl22_path, "wb") as f:
        f.write(data[bl22_start:bl22_end])
    with open(bl23_path, "wb") as f:
        f.write(data[bl23_start:bl23_end])
    with open(ft_path, "wb") as f:
        f.write(data[ft_start:ft_end])

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("f_header_t (little-endian)\n")
        f.write(f"bl22_length      = 0x{b22:08X} ({b22})\n")
        f.write(f"bl23_length      = 0x{b23:08X} ({b23})\n")
        f.write(f"flash_table_len  = 0x{ft:08X} ({ft})\n")
        f.write(f"lzma_src         = 0x{src:08X}\n")
        f.write(f"lzma_des         = 0x{des:08X}\n")
        f.write(f"lzma_length      = 0x{lzlen:08X} ({lzlen})\n")
        f.write(f"lzma_cmd         = 0x{cmd:08X} ({cmd})\n")
        f.write(f"reserved         = 0x{rsv:08X}\n")
        f.write("\n")
        f.write(f"header_offset    = 0x{header_off:X}\n")
        f.write(f"file_size        = 0x{total:X} ({total})\n")

    print("[OK] Unpacked:")
    print(f"  input           : {args.input}")
    print(f"  outdir          : {outdir}")
    print(f"  header_offset   : 0x{header_off:X}")
    print(f"  bl21.bin        : {bl21_end - bl21_start} bytes")
    print(f"  f_header.bin    : {HEADER_SIZE} bytes")
    print(f"  bl22.lzma       : {b22} bytes")
    print(f"  bl23.lzma       : {b23} bytes")
    print(f"  flash_table.bin : {ft} bytes")
    print(f"  lzma_src        : 0x{src:08X}")
    print(f"  lzma_des        : 0x{des:08X}")
    print(f"  lzma_length     : 0x{lzlen:08X}")
    print(f"  lzma_cmd        : 0x{cmd:08X}")

    return 0


if __name__ == "__main__":
    sys.exit(main())