"""Evidence-preserving extraction of typed-text payloads from decoded messages."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterator

from .wire import Message, try_decode_message


@dataclass(frozen=True)
class TextElement:
    """A rich-text box element extracted from GoodNotes records."""

    uuid: str
    text: str
    x: float
    y: float
    width: float = 0.0
    height: float = 0.0
    font_family: str = "Helvetica Neue"
    font_size: float = 14.0
    color_hex: str = "#000000"
    alpha: float = 1.0
    is_bold: bool = False
    is_italic: bool = False
    is_underline: bool = False
    is_strikethrough: bool = False
    list_type: str | None = None  # "bullet", "numbered", or None
    alignment: str = "left"  # "left", "center", "right"

    def as_dict(self) -> dict[str, object]:
        return {
            "uuid": self.uuid,
            "text": self.text,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "font_family": self.font_family,
            "font_size": self.font_size,
            "color_hex": self.color_hex,
            "alpha": self.alpha,
            "is_bold": self.is_bold,
            "is_italic": self.is_italic,
            "is_underline": self.is_underline,
            "is_strikethrough": self.is_strikethrough,
            "list_type": self.list_type,
            "alignment": self.alignment,
        }


def _parse_text_elements_from_dec_msg(
    dec_msg: Message,
    rec_uuid: str,
    x: float,
    y: float,
    width: float,
    height: float,
    default_font: str = "Helvetica Neue",
    default_size: float = 14.0,
) -> list[TextElement]:
    elements: list[TextElement] = []
    for field in dec_msg.fields:
        if not isinstance(field.value, bytes):
            continue
        m_item = try_decode_message(field.value)
        if not m_item:
            continue

        txt = ""
        f1_txt = m_item.by_number(1)
        if f1_txt and isinstance(f1_txt[0].value, bytes):
            txt = f1_txt[0].value.decode("utf-8", errors="ignore")

        if not txt:
            continue

        font_name = default_font
        font_size = default_size
        color_hex = "#000000"
        alpha = 1.0
        strikethrough = False
        underline = False
        italic = False
        bold = False
        list_type = None
        alignment = "left"

        # Parse formatting in m_item f2
        f2_val = m_item.by_number(2)
        if f2_val and isinstance(f2_val[0].value, bytes):
            m2 = try_decode_message(f2_val[0].value)
            if m2:
                if m2.by_number(1) and not isinstance(m2.by_number(1)[0].value, bytes) and m2.by_number(1)[0].value == 1:
                    strikethrough = True
                if m2.by_number(2) and not isinstance(m2.by_number(2)[0].value, bytes) and m2.by_number(2)[0].value == 1:
                    underline = True
                if m2.by_number(50) and not isinstance(m2.by_number(50)[0].value, bytes) and m2.by_number(50)[0].value == 1:
                    italic = True

                f30 = m2.by_number(30)
                if f30 and isinstance(f30[0].value, bytes):
                    font_name = f30[0].value.decode("utf-8", "ignore") or font_name

                f40 = m2.by_number(40)
                if f40 and f40[0].fixed_float() and f40[0].fixed_float() > 0:
                    font_size = f40[0].fixed_float()

                f60 = m2.by_number(60)
                if f60 and not isinstance(f60[0].value, bytes):
                    if f60[0].value > 18446744073709551212 or "bold" in font_name.lower():
                        bold = True
                elif "bold" in font_name.lower():
                    bold = True

                # Color parsing from f3 in m2
                f3_color = m2.by_number(3)
                if f3_color and isinstance(f3_color[0].value, bytes):
                    c_msg = try_decode_message(f3_color[0].value)
                    if c_msg:
                        cr, cg, cb = c_msg.by_number(1), c_msg.by_number(2), c_msg.by_number(3)
                        ca = c_msg.by_number(4)
                        if cr and cg and cb:
                            r = int(max(0.0, min(1.0, cr[0].fixed_float() or 0.0)) * 255)
                            g = int(max(0.0, min(1.0, cg[0].fixed_float() or 0.0)) * 255)
                            b = int(max(0.0, min(1.0, cb[0].fixed_float() or 0.0)) * 255)
                            color_hex = f"#{r:02X}{g:02X}{b:02X}"
                        if ca and ca[0].fixed_float() is not None:
                            alpha = max(0.0, min(1.0, ca[0].fixed_float()))

        # Parse list & alignment in m_item f3
        f3_val = m_item.by_number(3)
        if f3_val and isinstance(f3_val[0].value, bytes):
            m3 = try_decode_message(f3_val[0].value)
            if m3:
                f3_3 = m3.by_number(3)
                if f3_3:
                    if isinstance(f3_3[0].value, bytes):
                        if f3_3[0].value == b"":
                            list_type = "bullet"
                        else:
                            m3_3 = try_decode_message(f3_3[0].value)
                            if m3_3 and m3_3.by_number(1) and not isinstance(m3_3.by_number(1)[0].value, bytes) and m3_3.by_number(1)[0].value == 1:
                                list_type = "numbered"
                            elif m3_3 and len(m3_3.fields) == 0:
                                list_type = "bullet"
                f4_align = m3.by_number(4)
                if f4_align and not isinstance(f4_align[0].value, bytes):
                    align_code = int(f4_align[0].value)
                    if align_code == 1:
                        alignment = "left"
                    elif align_code == 2:
                        alignment = "center"
                    elif align_code == 3:
                        alignment = "right"

        elements.append(
            TextElement(
                uuid=rec_uuid,
                text=txt,
                x=x,
                y=y,
                width=width,
                height=height,
                font_family=font_name,
                font_size=font_size,
                color_hex=color_hex,
                alpha=alpha,
                is_bold=bold,
                is_italic=italic,
                is_underline=underline,
                is_strikethrough=strikethrough,
                list_type=list_type,
                alignment=alignment,
            )
        )
    return elements


def parse_text_elements(records: Sequence[Message]) -> tuple[TextElement, ...]:
    """Extract structured rich text elements from Type 35 / bv41 record payloads (including Sticky Notes)."""
    from .compression import decode_apple_lz4

    text_elements: list[TextElement] = []

    # 1. Parse standard rich text box records (f21 payload)
    for record in records:
        f16 = record.by_number(16)
        type_code = f16[0].value if f16 and not isinstance(f16[0].value, bytes) else None

        rec_uuid = ""
        f1 = record.by_number(1)
        if f1 and isinstance(f1[0].value, bytes):
            try:
                u_str = f1[0].value.decode("utf-8")
                if len(u_str) == 36 and "-" in u_str:
                    rec_uuid = u_str
            except UnicodeDecodeError:
                pass

        f21 = record.by_number(21)
        if not f21 or not isinstance(f21[0].value, bytes):
            continue

        msg = try_decode_message(f21[0].value)
        if not msg:
            continue

        # Extract canvas spatial coordinates (x, y) from f20 in msg
        x, y = 0.0, 0.0
        f20_pos = msg.by_number(20)
        if f20_pos and isinstance(f20_pos[0].value, bytes):
            m20 = try_decode_message(f20_pos[0].value)
            if m20 and m20.by_number(1) and isinstance(m20.by_number(1)[0].value, bytes):
                m20_1 = try_decode_message(m20.by_number(1)[0].value)
                if m20_1:
                    fx = m20_1.by_number(1)
                    fy = m20_1.by_number(2)
                    if fx and fy:
                        x = fx[0].fixed_float() or 0.0
                        y = fy[0].fixed_float() or 0.0

        f32 = msg.by_number(32)
        if not f32 or not isinstance(f32[0].value, bytes):
            continue

        msg32 = try_decode_message(f32[0].value)
        if not msg32:
            continue

        # Fallback spatial position from msg32 f2
        if x == 0.0 and y == 0.0:
            f2_pos = msg32.by_number(2)
            if f2_pos and isinstance(f2_pos[0].value, bytes):
                m2_pos = try_decode_message(f2_pos[0].value)
                if m2_pos:
                    fx = m2_pos.by_number(1)
                    fy = m2_pos.by_number(2)
                    if fx and fy:
                        x = fx[0].fixed_float() or 0.0
                        y = fy[0].fixed_float() or 0.0

        # Extract the *content* box dimensions (width, height) from msg32 f2.
        content_width, content_height = 0.0, 0.0
        f2_dim = msg32.by_number(2)
        if f2_dim and isinstance(f2_dim[0].value, bytes):
            m2_dim = try_decode_message(f2_dim[0].value)
            if m2_dim:
                fw = m2_dim.by_number(1)
                fh = m2_dim.by_number(2)
                if fw and fw[0].fixed_float() and fw[0].fixed_float() > 0:
                    content_width = fw[0].fixed_float()
                if fh and fh[0].fixed_float() and fh[0].fixed_float() > 0:
                    content_height = fh[0].fixed_float()

        # msg32 f10 is *not* a second box size -- it's the per-side inset
        # (padding) between the content box and the box GoodNotes actually
        # draws in its UI. Confirmed against real samples: the visible box
        # consistently equals content_size + 2 * inset (e.g. content 91.14 +
        # 2*5.45 inset = 102.04, matching the drawn box's 102.05 width).
        inset_width, inset_height = 0.0, 0.0
        f10_size = msg32.by_number(10)
        if f10_size and isinstance(f10_size[0].value, bytes):
            m10 = try_decode_message(f10_size[0].value)
            if m10:
                fw = m10.by_number(1)
                fh = m10.by_number(2)
                if fw and fh:
                    inset_width = fw[0].fixed_float() or 0.0
                    inset_height = fh[0].fixed_float() or 0.0

        width = content_width + 2.0 * inset_width
        height = content_height + 2.0 * inset_height

        # Default font family & font size from msg32 f5
        default_font = "Helvetica Neue"
        default_size = 24.0
        f5 = msg32.by_number(5)
        if f5 and isinstance(f5[0].value, bytes):
            m5 = try_decode_message(f5[0].value)
            if m5 and m5.by_number(1) and isinstance(m5.by_number(1)[0].value, bytes):
                m5_1 = try_decode_message(m5.by_number(1)[0].value)
                if m5_1:
                    f30 = m5_1.by_number(30)
                    if f30 and isinstance(f30[0].value, bytes):
                        default_font = f30[0].value.decode("utf-8", "ignore") or default_font
                    f40 = m5_1.by_number(40)
                    if f40 and f40[0].fixed_float() and f40[0].fixed_float() > 0:
                        default_size = f40[0].fixed_float()

        # Decode bv41 LZ4 payload in msg32 f1 -> f2
        f1_msg32 = msg32.by_number(1)
        if not f1_msg32 or not isinstance(f1_msg32[0].value, bytes):
            continue

        msg1 = try_decode_message(f1_msg32[0].value)
        if not msg1:
            continue

        f2_bv41 = msg1.by_number(2)
        if not f2_bv41 or not isinstance(f2_bv41[0].value, bytes):
            continue

        bv41_bytes = f2_bv41[0].value
        if not b"bv41" in bv41_bytes:
            continue

        try:
            decompressed, _ = decode_apple_lz4(bv41_bytes)
        except Exception:
            continue

        dec_msg = try_decode_message(decompressed)
        if not dec_msg:
            continue

        text_elements.extend(
            _parse_text_elements_from_dec_msg(dec_msg, rec_uuid, x, y, width, height, default_font, default_size)
        )

    # 2. Parse Sticky Note (Type 35) rich text payloads in f20 records
    for record in records:
        f20 = record.by_number(20)
        if not f20:
            continue
        for field in f20:
            if not isinstance(field.value, bytes):
                continue
            msg = try_decode_message(field.value)
            if not msg:
                continue
            is_type_35 = any(not isinstance(f.value, bytes) and f.value == 35 for f in msg.by_number(2))
            if not is_type_35:
                continue

            f1 = msg.by_number(1)
            u_str = f1[0].value.decode("utf-8", errors="ignore") if f1 and isinstance(f1[0].value, bytes) else ""

            # Extract sticky note position (x, y)
            nx, ny = 0.0, 0.0
            f20_pos = msg.by_number(20)
            if f20_pos and isinstance(f20_pos[0].value, bytes):
                pos_msg = try_decode_message(f20_pos[0].value)
                if pos_msg and pos_msg.by_number(1) and isinstance(pos_msg.by_number(1)[0].value, bytes):
                    pt_msg = try_decode_message(pos_msg.by_number(1)[0].value)
                    if pt_msg:
                        fx, fy = pt_msg.by_number(1), pt_msg.by_number(2)
                        if fx and fy:
                            nx = fx[0].fixed_float() or 0.0
                            ny = fy[0].fixed_float() or 0.0

            # Decode field 31 LZ4 payload
            f31_list = msg.by_number(31)
            for f31 in f31_list:
                if not isinstance(f31.value, bytes):
                    continue
                m31 = try_decode_message(f31.value)
                if not m31:
                    continue
                f1_list = m31.by_number(1)
                for f1_item in f1_list:
                    if not isinstance(f1_item.value, bytes):
                        continue
                    m31_f1 = try_decode_message(f1_item.value)
                    if not m31_f1:
                        continue
                    f2_list = m31_f1.by_number(2)
                    for f2_item in f2_list:
                        if isinstance(f2_item.value, bytes) and b"bv41" in f2_item.value:
                            pos = f2_item.value.find(b"bv41")
                            try:
                                lz4_data, _ = decode_apple_lz4(f2_item.value[pos:])
                                dec_msg = try_decode_message(lz4_data)
                                if dec_msg:
                                    extracted = _parse_text_elements_from_dec_msg(
                                        dec_msg, u_str, nx, ny, 256.0, 256.0, default_font="Helvetica Neue", default_size=14.0
                                    )
                                    text_elements.extend(extracted)
                            except Exception:
                                pass

    return tuple(text_elements)


@dataclass(frozen=True)
class TextFragment:
    source_path: str
    format: str
    raw: bytes
    text: str


_RTF_HEX = re.compile(rb"\\'([0-9a-fA-F]{2})")
_RTF_CONTROL = re.compile(r"\\[a-zA-Z]+-?\d* ?|[{}]")


def _remove_rtf_destination_groups(value: str) -> str:
    """Drop non-content RTF groups while respecting nested braces."""
    ignored = ("\\fonttbl", "\\colortbl", "\\stylesheet", "\\*\\expandedcolortbl")
    def visit(start: int, stop: int) -> str:
        result: list[str] = []
        index = start
        while index < stop:
            if value[index] != "{":
                result.append(value[index])
                index += 1
                continue
            depth, end = 1, index + 1
            while end < stop and depth:
                if value[end] == "{":
                    depth += 1
                elif value[end] == "}":
                    depth -= 1
                end += 1
            content = value[index + 1 : end - 1]
            if not content.startswith(ignored):
                result.append(visit(index + 1, end - 1))
            index = end
        return "".join(result)

    return visit(0, len(value))


def rtf_to_text(data: bytes) -> str:
    """Extract readable text from GoodNotes' RTF payload without losing raw bytes.

    GoodNotes samples use traditional-Chinese byte escapes despite an RTF header that
    declares a generic code page. Try CP950 first, then Latin-1 as a lossless fallback.
    """
    replaced = _RTF_HEX.sub(lambda match: bytes([int(match.group(1), 16)]), data)
    decoded = _remove_rtf_destination_groups(replaced.decode("cp950", errors="replace"))
    return _RTF_CONTROL.sub("", decoded).replace("\\\\", "\\").strip()


def extract_text(message: Message, path: str = "$") -> Iterator[TextFragment]:
    """Yield literal UTF-8 and RTF fields, including nested protobuf messages."""
    for index, field in enumerate(message.fields):
        field_path = f"{path}.field_{field.number}[{index}]"
        if not isinstance(field.value, bytes):
            continue
        if field.value.startswith(b"{\\rtf"):
            yield TextFragment(field_path, "rtf", field.value, rtf_to_text(field.value))
            continue
        try:
            value = field.value.decode("utf-8")
        except UnicodeDecodeError:
            value = ""
        if value and value.isprintable() and len(value) > 1:
            yield TextFragment(field_path, "utf8", field.value, value)
        nested = try_decode_message(field.value)
        if nested is not None:
            yield from extract_text(nested, field_path)