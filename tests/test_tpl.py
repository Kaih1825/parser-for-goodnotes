from __future__ import annotations

import struct
import unittest

from goodnotes_re.tpl import decode_tpl


class TplTests(unittest.TestCase):
    def test_decodes_a_typed_array_without_float_scanning(self) -> None:
        format_bytes = b"uA(S(uu))\0"
        body = struct.pack("<IIIII", 7, 2, 10, 20, 30) + struct.pack("<I", 40)
        image = b"tpl\0" + struct.pack("<I", 8 + len(format_bytes) + len(body)) + format_bytes + body
        decoded = decode_tpl(image)
        self.assertEqual(decoded.format, "uA(S(uu))")
        self.assertEqual(decoded.values, (7, [(10, 20), (30, 40)]))
