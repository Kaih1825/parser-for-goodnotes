"""A small, dependency-free protobuf wire decoder.

This module intentionally knows no GoodNotes schema. It retains raw bytes and only
recurses into a length-delimited value when the *whole* value is valid protobuf.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
import base64
from math import isfinite
import struct
from typing import Final


class WireType(IntEnum):
    VARINT = 0
    FIXED64 = 1
    LENGTH_DELIMITED = 2
    START_GROUP = 3
    END_GROUP = 4
    FIXED32 = 5


class DecodeError(ValueError):
    """Raised for malformed or truncated protobuf wire data."""


@dataclass(frozen=True)
class Field:
    number: int
    wire_type: WireType
    value: int | bytes
    raw: bytes
    offset: int

    def fixed_float(self) -> float | None:
        """Return a float only for an explicitly fixed-width protobuf field."""
        if self.wire_type is WireType.FIXED32:
            return struct.unpack("<f", struct.pack("<I", self.value))[0]  # type: ignore[arg-type]
        if self.wire_type is WireType.FIXED64:
            return struct.unpack("<d", struct.pack("<Q", self.value))[0]  # type: ignore[arg-type]
        return None

    def as_json(self, depth: int = 0, max_depth: int = 24) -> dict[str, object]:
        result: dict[str, object] = {
            "number": self.number,
            "wire_type": self.wire_type.name.lower(),
            "offset": self.offset,
            "raw_base64": base64.b64encode(self.raw).decode("ascii"),
        }
        if isinstance(self.value, bytes):
            result["length"] = len(self.value)
            result["value_base64"] = base64.b64encode(self.value).decode("ascii")
            try:
                text = self.value.decode("utf-8")
            except UnicodeDecodeError:
                text = None
            if text is not None and text.isprintable():
                result["utf8"] = text
            if depth < max_depth:
                nested = try_decode_message(self.value)
                if nested is not None and nested.fields:
                    result["message"] = nested.as_json(depth + 1, max_depth)
        else:
            result["value"] = self.value
            float_value = self.fixed_float()
            if float_value is not None and isfinite(float_value):
                result["float_candidate"] = float_value
        return result


@dataclass(frozen=True)
class Message:
    fields: tuple[Field, ...]
    raw: bytes

    def by_number(self, number: int) -> tuple[Field, ...]:
        return tuple(field for field in self.fields if field.number == number)

    def as_json(self, depth: int = 0, max_depth: int = 24) -> dict[str, object]:
        return {"byte_length": len(self.raw), "fields": [f.as_json(depth, max_depth) for f in self.fields]}


_MAX_VARINT_BYTES: Final = 10


def _read_varint(data: bytes, pos: int) -> tuple[int, int]:
    value = 0
    for shift in range(0, _MAX_VARINT_BYTES * 7, 7):
        if pos >= len(data):
            raise DecodeError("truncated varint")
        byte = data[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, pos
    raise DecodeError("varint exceeds 10 bytes")


def decode_message(data: bytes) -> Message:
    """Decode one protobuf message and preserve every field's encoded bytes."""
    fields: list[Field] = []
    pos = 0
    while pos < len(data):
        start = pos
        key, pos = _read_varint(data, pos)
        number, wire_number = key >> 3, key & 7
        if number == 0:
            raise DecodeError("field number 0 is invalid")
        try:
            wire_type = WireType(wire_number)
        except ValueError as error:
            raise DecodeError(f"unknown wire type {wire_number}") from error
        if wire_type in (WireType.START_GROUP, WireType.END_GROUP):
            raise DecodeError("groups are not supported")
        if wire_type is WireType.VARINT:
            value, pos = _read_varint(data, pos)
        elif wire_type is WireType.FIXED64:
            if pos + 8 > len(data):
                raise DecodeError("truncated fixed64")
            value = int.from_bytes(data[pos : pos + 8], "little")
            pos += 8
        elif wire_type is WireType.FIXED32:
            if pos + 4 > len(data):
                raise DecodeError("truncated fixed32")
            value = int.from_bytes(data[pos : pos + 4], "little")
            pos += 4
        else:
            length, pos = _read_varint(data, pos)
            if pos + length > len(data):
                raise DecodeError("truncated length-delimited field")
            value = data[pos : pos + length]
            pos += length
        fields.append(Field(number, wire_type, value, data[start:pos], start))
    return Message(tuple(fields), data)


def decode_delimited_messages(data: bytes) -> tuple[Message, ...]:
    """Decode a stream of varint-length-prefixed protobuf messages.

    GoodNotes indexes and note members in the supplied corpus use this framing;
    it is distinct from a protobuf field and is therefore decoded before schema
    interpretation rather than guessed from arbitrary byte patterns.
    """
    messages: list[Message] = []
    pos = 0
    while pos < len(data):
        length, pos = _read_varint(data, pos)
        end = pos + length
        if end > len(data):
            raise DecodeError("truncated delimited protobuf record")
        messages.append(decode_message(data[pos:end]))
        pos = end
    return tuple(messages)


def try_decode_message(data: bytes) -> Message | None:
    """Return a message only when all bytes form a valid, non-empty protobuf stream."""
    if not data:
        return None
    try:
        return decode_message(data)
    except DecodeError:
        return None
