"""Minimal LZ4 block decompressor — pure Python, zero dependencies.

Usage:
    decompressed = lz4_decompress(compressed_data, uncompressed_size)
"""

from __future__ import annotations
import struct

MINMATCH = 4


def lz4_decompress(src: bytes, uncompressed_size: int) -> bytes:
    dst = bytearray()
    pos = 0
    src_len = len(src)

    while len(dst) < uncompressed_size:
        if pos >= src_len:
            break

        token = src[pos]
        pos += 1

        # --- Literal length ---
        lit_len = token >> 4
        if lit_len == 15:
            while pos < src_len:
                b = src[pos]
                pos += 1
                lit_len += b
                if b < 255:
                    break

        # --- Copy literals ---
        if lit_len > 0:
            if pos + lit_len > src_len:
                dst.extend(src[pos:])
                break
            dst.extend(src[pos:pos + lit_len])
            pos += lit_len

        # Check end of block
        if pos >= src_len or len(dst) >= uncompressed_size:
            break

        # --- Match offset ---
        if pos + 2 > src_len:
            break
        match_offset = struct.unpack_from("<H", src, pos)[0]
        pos += 2
        if match_offset == 0:
            raise ValueError("LZ4 invalid match offset 0")

        # --- Match length ---
        match_len = (token & 0x0F) + MINMATCH
        if (token & 0x0F) == 15:
            while pos < src_len:
                b = src[pos]
                pos += 1
                match_len += b
                if b < 255:
                    break

        # --- Copy match ---
        start = len(dst) - match_offset
        if start < 0:
            raise ValueError(f"LZ4 match before start (offset={match_offset}, len={len(dst)})")
        for i in range(match_len):
            dst.append(dst[start + i])

    return bytes(dst[:uncompressed_size])
