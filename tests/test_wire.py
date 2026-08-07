from __future__ import annotations

import struct

import unittest

from goodnotes_re.wire import DecodeError, WireType, decode_message


class WireTests(unittest.TestCase):
    def test_decodes_all_standard_wire_values(self) -> None:
        data = bytes.fromhex("0896011108070605040302011a0368696e2504030201")
        message = decode_message(data)
        self.assertEqual([field.wire_type for field in message.fields], [WireType.VARINT, WireType.FIXED64, WireType.LENGTH_DELIMITED, WireType.FIXED32])
        self.assertEqual(message.fields[0].value, 150)
        self.assertEqual(message.fields[2].value, b"hin")
        self.assertEqual(message.fields[3].fixed_float(), struct.unpack("<f", b"\x04\x03\x02\x01")[0])

    def test_rejects_malformed_wire_data(self) -> None:
        with self.assertRaises(DecodeError):
            decode_message(b"\x0a\x03x")

    def test_nonfinite_float_candidate_is_json_safe(self) -> None:
        message = decode_message(bytes.fromhex("0d0000807f"))
        self.assertNotIn("float_candidate", message.fields[0].as_json())
