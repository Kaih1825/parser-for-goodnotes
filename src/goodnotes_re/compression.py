"""Decoder for Apple's framed LZ4 stream (``bv41`` / ``bv4$``)."""
from __future__ import annotations

import struct


class CompressionError(ValueError):
    """Raised when an Apple LZ4 stream is malformed."""


def _decode_lz4_block(source: bytes, expected_size: int, dictionary: bytes) -> bytes:
    """Decode a standard LZ4 block, using at most 64 KiB of prior output."""
    output = bytearray()
    position = 0
    history = dictionary[-65536:]
    while position < len(source):
        token = source[position]
        position += 1
        literal_length = token >> 4
        if literal_length == 15:
            while True:
                if position >= len(source):
                    raise CompressionError("truncated LZ4 literal length")
                extension = source[position]
                position += 1
                literal_length += extension
                if extension != 255:
                    break
        if position + literal_length > len(source):
            raise CompressionError("truncated LZ4 literals")
        output.extend(source[position : position + literal_length])
        position += literal_length
        if position == len(source):
            break
        if position + 2 > len(source):
            raise CompressionError("truncated LZ4 match offset")
        offset = int.from_bytes(source[position : position + 2], "little")
        position += 2
        if offset == 0 or offset > len(history) + len(output):
            raise CompressionError("invalid LZ4 match offset")
        match_length = token & 15
        if match_length == 15:
            while True:
                if position >= len(source):
                    raise CompressionError("truncated LZ4 match length")
                extension = source[position]
                position += 1
                match_length += extension
                if extension != 255:
                    break
        match_length += 4
        for _ in range(match_length):
            combined = history + output
            output.append(combined[-offset])
    if len(output) != expected_size:
        raise CompressionError(f"LZ4 size mismatch: expected {expected_size}, got {len(output)}")
    return bytes(output)


def decode_apple_lz4(data: bytes) -> tuple[bytes, int]:
    """Decode an Apple framed LZ4 payload and return (output, bytes_consumed).

    The frame is a sequence of explicit ``bv41`` compressed or ``bv4-`` stored
    blocks, terminated by ``bv4$``. This is a format decoder, not float scanning.
    """
    output = bytearray()
    position = 0
    while True:
        if position + 4 > len(data):
            raise CompressionError("missing Apple LZ4 end marker")
        magic = data[position : position + 4]
        position += 4
        if magic == b"bv4$":
            return bytes(output), position
        if magic not in (b"bv41", b"bv4-"):
            raise CompressionError(f"unexpected Apple LZ4 block magic {magic!r}")
        if position + 8 > len(data):
            raise CompressionError("truncated Apple LZ4 block header")
        uncompressed_size, stored_size = struct.unpack_from("<II", data, position)
        position += 8
        if position + stored_size > len(data):
            raise CompressionError("truncated Apple LZ4 block")
        block = data[position : position + stored_size]
        position += stored_size
        if magic == b"bv4-":
            if len(block) != uncompressed_size:
                raise CompressionError("stored Apple LZ4 block size mismatch")
            output.extend(block)
        else:
            output.extend(_decode_lz4_block(block, uncompressed_size, bytes(output)))
