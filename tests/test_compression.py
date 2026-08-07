from __future__ import annotations

import struct
import unittest

from goodnotes_re.compression import decode_apple_lz4


class CompressionTests(unittest.TestCase):
    def test_decodes_literal_apple_lz4_block(self) -> None:
        # LZ4 token 0x50: five literal bytes and no match.
        frame = b"bv41" + struct.pack("<II", 5, 6) + b"\x50hello" + b"bv4$"
        decoded, consumed = decode_apple_lz4(frame + b"tail")
        self.assertEqual(decoded, b"hello")
        self.assertEqual(consumed, len(frame))
