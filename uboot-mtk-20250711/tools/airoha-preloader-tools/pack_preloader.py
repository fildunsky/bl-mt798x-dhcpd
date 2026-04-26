#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Pack preloader image for ECNT BL2 optimization flow.

Layout (same as trx -z path in provided trx.c):
    [bl21][f_header_t][bl22.lzma][bl23.lzma][flash_table]

f_header_t (8 x uint32 little-endian):
    bl22_length
    bl23_length
    flash_table_length
    lzma_src      (default: 0x1e843c00 + sizeof(f_header_t))
    lzma_des      (default: 0x08004000)
    lzma_length   (default: bl22_length)
    lzma_cmd      (default: 0)
    reserved      (default: 0)
"""

import argparse
import os
import struct
import sys


F_HEADER_SIZE = 32  # 8 * 4 bytes


def read_file(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def parse_int(val: str) -> int:
    # supports: 1234, 0x1234
    return int(val, 0)


def build_header(
    bl22_len: int,
    bl23_len: int,
    flash_table_len: int,
    lzma_src: int,
    lzma_des: int,
    lzma_length: int,
    lzma_cmd: int,
    reserved: int,
) -> bytes:
    return struct.pack(
        "<8I",
        bl22_len & 0xFFFFFFFF,
        bl23_len & 0xFFFFFFFF,
        flash_table_len & 0xFFFFFFFF,
        lzma_src & 0xFFFFFFFF,
        lzma_des & 0xFFFFFFFF,
        lzma_length & 0xFFFFFFFF,
        lzma_cmd & 0xFFFFFFFF,
        reserved & 0xFFFFFFFF,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pack preloader.bin from bl21 + bl22.lzma + bl23.lzma + flash_table"
    )
    parser.add_argument("bl21", help="Path to bl21 binary")
    parser.add_argument("bl22_lzma", help="Path to bl22.lzma")
    parser.add_argument("bl23_lzma", help="Path to bl23.lzma")
    parser.add_argument("flash_table", help="Path to flash_table binary")
    parser.add_argument("output", help="Output preloader.bin path")

    parser.add_argument(
        "--lzma-src-base",
        default="0x1e843c00",
        help="Base address used by trx.c for lzma_src before + header size (default: 0x1e843c00)",
    )
    parser.add_argument(
        "--lzma-des",
        default="0x08004000",
        help="LZMA destination address for BL22 (default: 0x08004000)",
    )
    parser.add_argument(
        "--lzma-cmd",
        default="0",
        help="lzma_cmd field (default: 0)",
    )
    parser.add_argument(
        "--reserved",
        default="0",
        help="reserved field (default: 0)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed packing information",
    )

    args = parser.parse_args()

    if not os.path.exists(args.bl21):
        print(f"[ERR] bl21 not found: {args.bl21}", file=sys.stderr)
        return 1
    if not os.path.exists(args.bl22_lzma):
        print(f"[ERR] bl22.lzma not found: {args.bl22_lzma}", file=sys.stderr)
        return 1
    if not os.path.exists(args.bl23_lzma):
        print(f"[ERR] bl23.lzma not found: {args.bl23_lzma}", file=sys.stderr)
        return 1
    if not os.path.exists(args.flash_table):
        print(f"[ERR] flash_table not found: {args.flash_table}", file=sys.stderr)
        return 1

    bl21 = read_file(args.bl21)
    bl22 = read_file(args.bl22_lzma)
    bl23 = read_file(args.bl23_lzma)
    flash_table = read_file(args.flash_table)

    bl22_len = len(bl22)
    bl23_len = len(bl23)
    flash_table_len = len(flash_table)

    lzma_src_base = parse_int(args.lzma_src_base)
    lzma_src = lzma_src_base + F_HEADER_SIZE
    lzma_des = parse_int(args.lzma_des)
    lzma_length = bl22_len
    lzma_cmd = parse_int(args.lzma_cmd)
    reserved = parse_int(args.reserved)

    header = build_header(
        bl22_len=bl22_len,
        bl23_len=bl23_len,
        flash_table_len=flash_table_len,
        lzma_src=lzma_src,
        lzma_des=lzma_des,
        lzma_length=lzma_length,
        lzma_cmd=lzma_cmd,
        reserved=reserved,
    )

    out_data = bl21 + header + bl22 + bl23 + flash_table

    out_dir = os.path.dirname(os.path.abspath(args.output))
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    with open(args.output, "wb") as f:
        f.write(out_data)

    print("[OK] Packed preloader image")
    print(f"  output          : {args.output}")
    print(f"  size            : {len(out_data)} bytes (0x{len(out_data):X})")
    print(f"  bl21            : {len(bl21)} bytes (0x{len(bl21):X})")
    print(f"  header          : {len(header)} bytes (0x{len(header):X})")
    print(f"  bl22.lzma       : {bl22_len} bytes (0x{bl22_len:X})")
    print(f"  bl23.lzma       : {bl23_len} bytes (0x{bl23_len:X})")
    print(f"  flash_table     : {flash_table_len} bytes (0x{flash_table_len:X})")
    print(f"  lzma_src        : 0x{lzma_src:08X}")
    print(f"  lzma_des        : 0x{lzma_des:08X}")
    print(f"  lzma_length     : 0x{lzma_length:X}")
    print(f"  lzma_cmd        : 0x{lzma_cmd:X}")
    print(f"  reserved        : 0x{reserved:X}")

    if args.verbose:
        fields = struct.unpack("<8I", header)
        names = [
            "bl22_length",
            "bl23_length",
            "flash_table_length",
            "lzma_src",
            "lzma_des",
            "lzma_length",
            "lzma_cmd",
            "reserved",
        ]
        print("  header fields   :")
        for n, v in zip(names, fields):
            print(f"    - {n:18s} = 0x{v:08X} ({v})")

    return 0


if __name__ == "__main__":
    sys.exit(main())