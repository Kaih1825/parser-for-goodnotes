"""Typed page element summaries for analyzed GoodNotes document records."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .wire import Message, try_decode_message


def _looks_like_uuid(value: str) -> bool:
    return len(value) == 36 and value.count("-") == 4


def _utf8_uuids(message: Message) -> tuple[str, ...]:
    values: list[str] = []
    for field in message.fields:
        if not isinstance(field.value, bytes):
            continue
        try:
            text = field.value.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if _looks_like_uuid(text):
            values.append(text)
    return tuple(values)


@dataclass(frozen=True)
class ImageElement:
    """An image attachment element positioned on a GoodNotes page."""

    uuid: str
    attachment_uuid: str
    x: float
    y: float
    width: float
    height: float
    orig_x: float = 0.0
    orig_y: float = 0.0
    orig_width: float = 0.0
    orig_height: float = 0.0
    rotation_rad: float = 0.0

    def as_dict(self) -> dict[str, object]:
        return {
            "uuid": self.uuid,
            "attachment_uuid": self.attachment_uuid,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "orig_x": self.orig_x,
            "orig_y": self.orig_y,
            "orig_width": self.orig_width,
            "orig_height": self.orig_height,
            "rotation_rad": self.rotation_rad,
        }


def parse_image_elements(records: Sequence[Message]) -> tuple[ImageElement, ...]:
    """Extract all image attachment bounding boxes and crop parameters from page records."""
    images: list[ImageElement] = []
    for i, rec in enumerate(records):
        att_uuid = None
        f7 = rec.by_number(7)
        if f7 and isinstance(f7[0].value, bytes):
            s = f7[0].value.decode("utf-8", errors="ignore")
            if _looks_like_uuid(s):
                att_uuid = s

        if not att_uuid:
            f4 = rec.by_number(4)
            if f4 and isinstance(f4[0].value, bytes):
                s = f4[0].value.decode("utf-8", errors="ignore")
                if _looks_like_uuid(s):
                    att_uuid = s

        if not att_uuid:
            continue

        # An image record that was moved off this page (e.g. via lasso move
        # to another page) is left behind as a tombstone: same record uuid
        # and attachment uuid as before, but field 3 == 1 marks it erased.
        # Skip those so a moved-away image isn't parsed as still present.
        f3 = rec.by_number(3)
        if f3 and not isinstance(f3[0].value, bytes) and f3[0].value == 1:
            continue

        rec_uuid = ""
        f1 = rec.by_number(1)
        if f1 and isinstance(f1[0].value, bytes):
            s = f1[0].value.decode("utf-8", errors="ignore")
            if _looks_like_uuid(s):
                rec_uuid = s

        # Look in current record or subsequent record for spatial bounding box and cropping
        orig_x, orig_y, orig_w, orig_h, rot = 0.0, 0.0, 0.0, 0.0, 0.0
        cx, cy, crop_w, crop_h = 0.0, 0.0, 0.0, 0.0
        has_crop = False

        candidates = [rec]
        if i + 1 < len(records):
            candidates.append(records[i + 1])

        found_box = False
        for cand in candidates:
            for field in cand.fields:
                if not isinstance(field.value, bytes):
                    continue
                msg = try_decode_message(field.value)
                if not msg:
                    continue

                f2_msg = msg.by_number(2)
                f3_msg = msg.by_number(3)
                if f2_msg and isinstance(f2_msg[0].value, bytes):
                    m2 = try_decode_message(f2_msg[0].value)
                    if m2:
                        m2_1 = m2.by_number(1)
                        m2_2 = m2.by_number(2)
                        if m2_1 and isinstance(m2_1[0].value, bytes):
                            m_xy = try_decode_message(m2_1[0].value)
                            if m_xy:
                                fx, fy = m_xy.by_number(1), m_xy.by_number(2)
                                if fx and fy:
                                    orig_x = fx[0].fixed_float() or 0.0
                                    orig_y = fy[0].fixed_float() or 0.0
                        if m2_2 and isinstance(m2_2[0].value, bytes):
                            m_wh = try_decode_message(m2_2[0].value)
                            if m_wh:
                                fw, fh = m_wh.by_number(1), m_wh.by_number(2)
                                if fw and fh:
                                    orig_w = fw[0].fixed_float() or 0.0
                                    orig_h = fh[0].fixed_float() or 0.0
                                    found_box = True

                if f3_msg and isinstance(f3_msg[0].value, bytes):
                    m3 = try_decode_message(f3_msg[0].value)
                    if m3:
                        m3_1 = m3.by_number(1)
                        m3_2 = m3.by_number(2)
                        m3_3 = m3.by_number(3)
                        if m3_1 and isinstance(m3_1[0].value, bytes):
                            m_c = try_decode_message(m3_1[0].value)
                            if m_c:
                                fcx, fcy = m_c.by_number(1), m_c.by_number(2)
                                if fcx and fcy:
                                    cx = fcx[0].fixed_float() or 0.0
                                    cy = fcy[0].fixed_float() or 0.0
                        if m3_2 and isinstance(m3_2[0].value, bytes):
                            m_cw = try_decode_message(m3_2[0].value)
                            if m_cw:
                                fcw, fch = m_cw.by_number(1), m_cw.by_number(2)
                                if fcw and fch:
                                    crop_w = fcw[0].fixed_float() or 0.0
                                    crop_h = fch[0].fixed_float() or 0.0
                                    has_crop = True
                        if m3_3 and m3_3[0].fixed_float() is not None:
                            rot = m3_3[0].fixed_float()

                if found_box:
                    break
            if found_box:
                break

        if att_uuid:
            if has_crop and crop_w > 0 and crop_h > 0:
                final_w = crop_w
                final_h = crop_h
                final_x = (cx - crop_w / 2.0) if cx > 0 else orig_x
                final_y = (cy - crop_h / 2.0) if cy > 0 else orig_y
            else:
                final_x, final_y, final_w, final_h = orig_x, orig_y, orig_w, orig_h

            images.append(
                ImageElement(
                    uuid=rec_uuid or att_uuid,
                    attachment_uuid=att_uuid,
                    x=final_x,
                    y=final_y,
                    width=final_w,
                    height=final_h,
                    orig_x=orig_x,
                    orig_y=orig_y,
                    orig_width=orig_w,
                    orig_height=orig_h,
                    rotation_rad=rot,
                )
            )

    return tuple(images)



@dataclass(frozen=True)
class StickyNote:
    """A GoodNotes sticky note (comment/note element)."""

    uuid: str
    x: float
    y: float
    width: float = 256.0
    height: float = 256.0
    color_hex: str = "#FAE778"
    author: str = ""
    text: str = ""
    is_open: bool = True

    def as_dict(self) -> dict[str, object]:
        return {
            "uuid": self.uuid,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "color_hex": self.color_hex,
            "author": self.author,
            "text": self.text,
            "is_open": self.is_open,
        }


def _extract_sticky_note_text(msg: Message) -> str:
    """Extract plain text payload from StickyNote (Type 35) field 31 LZ4 message."""
    texts: list[str] = []
    f31_list = msg.by_number(31)
    for f31 in f31_list:
        if not isinstance(f31.value, bytes):
            continue
        m31 = try_decode_message(f31.value)
        if not m31:
            continue
        f1_list = m31.by_number(1)
        for f1 in f1_list:
            if not isinstance(f1.value, bytes):
                continue
            m31_f1 = try_decode_message(f1.value)
            if not m31_f1:
                continue
            f2_list = m31_f1.by_number(2)
            for f2 in f2_list:
                if isinstance(f2.value, bytes) and b"bv41" in f2.value:
                    pos = f2.value.find(b"bv41")
                    try:
                        from .compression import decode_apple_lz4
                        lz4_data, _ = decode_apple_lz4(f2.value[pos:])
                        proto = try_decode_message(lz4_data)
                        if proto:
                            for pf in proto.fields:
                                if isinstance(pf.value, bytes):
                                    m_pf = try_decode_message(pf.value)
                                    if m_pf:
                                        f1_txt = m_pf.by_number(1)
                                        if f1_txt and isinstance(f1_txt[0].value, bytes):
                                            txt = f1_txt[0].value.decode("utf-8", errors="ignore")
                                            if txt:
                                                texts.append(txt)
                    except Exception:
                        pass
    return "".join(texts)


def parse_sticky_notes(records: Sequence[Message]) -> tuple[StickyNote, ...]:
    """Extract all sticky note objects (Type 35) from decoded page records."""
    note_meta: dict[str, dict[str, object]] = {}
    for rec in records:
        f2 = rec.by_number(2)
        f16 = rec.by_number(16)
        type_code = f2[0].value if f2 and not isinstance(f2[0].value, bytes) else (f16[0].value if f16 and not isinstance(f16[0].value, bytes) else None)
        if type_code == 35:
            f1 = rec.by_number(1)
            if f1 and isinstance(f1[0].value, bytes):
                u_str = f1[0].value.decode("utf-8", errors="ignore")
                if _looks_like_uuid(u_str):
                    is_folded = False
                    f7_state = rec.by_number(7)
                    if f7_state and isinstance(f7_state[0].value, bytes):
                        m7 = try_decode_message(f7_state[0].value)
                        if m7 and m7.by_number(1) and isinstance(m7.by_number(1)[0].value, bytes):
                            m7_1 = try_decode_message(m7.by_number(1)[0].value)
                            if m7_1 and m7_1.by_number(1):
                                is_folded = True

                    w, h = 256.0, 256.0
                    f21_size = rec.by_number(21)
                    if f21_size and isinstance(f21_size[0].value, bytes):
                        size_msg = try_decode_message(f21_size[0].value)
                        if size_msg and size_msg.by_number(2) and isinstance(size_msg.by_number(2)[0].value, bytes):
                            s_inner = try_decode_message(size_msg.by_number(2)[0].value)
                            if s_inner:
                                fw = s_inner.by_number(1)
                                fh = s_inner.by_number(2)
                                if fw and fh:
                                    w = fw[0].fixed_float() or 256.0
                                    h = fh[0].fixed_float() or 256.0

                    note_meta[u_str] = {"is_folded": is_folded, "w": w, "h": h}

    sticky_notes: dict[str, StickyNote] = {}
    for rec in records:
        f20 = rec.by_number(20)
        if not f20:
            continue
        for field in f20:
            if not isinstance(field.value, bytes):
                continue
            msg = try_decode_message(field.value)
            if not msg:
                continue
            f1 = msg.by_number(1)
            if not f1 or not isinstance(f1[0].value, bytes):
                continue
            u_str = f1[0].value.decode("utf-8", errors="ignore")
            is_type_35 = any(not isinstance(f.value, bytes) and f.value == 35 for f in msg.by_number(2))
            if u_str in note_meta or is_type_35:
                meta = note_meta.get(u_str, {})
                x, y = 0.0, 0.0
                f20_pos = msg.by_number(20)
                if f20_pos and isinstance(f20_pos[0].value, bytes):
                    pos_msg = try_decode_message(f20_pos[0].value)
                    if pos_msg and pos_msg.by_number(1) and isinstance(pos_msg.by_number(1)[0].value, bytes):
                        pt_msg = try_decode_message(pos_msg.by_number(1)[0].value)
                        if pt_msg:
                            fx = pt_msg.by_number(1)
                            fy = pt_msg.by_number(2)
                            if fx and fy:
                                x = fx[0].fixed_float() or 0.0
                                y = fy[0].fixed_float() or 0.0

                w = float(meta.get("w", 256.0))
                h = float(meta.get("h", 256.0))

                # Fallback to inner msg f21 if not found in outer metadata record
                if w == 256.0 and h == 256.0:
                    f21_size = msg.by_number(21)
                    if f21_size and isinstance(f21_size[0].value, bytes):
                        size_msg = try_decode_message(f21_size[0].value)
                        if size_msg and size_msg.by_number(2) and isinstance(size_msg.by_number(2)[0].value, bytes):
                            s_inner = try_decode_message(size_msg.by_number(2)[0].value)
                            if s_inner:
                                fw = s_inner.by_number(1)
                                fh = s_inner.by_number(2)
                                if fw and fh:
                                    w = fw[0].fixed_float() or 256.0
                                    h = fh[0].fixed_float() or 256.0

                color_hex = "#FAE778"
                f30_color = msg.by_number(30)
                if f30_color and isinstance(f30_color[0].value, bytes):
                    c_msg = try_decode_message(f30_color[0].value)
                    if c_msg:
                        cr = c_msg.by_number(1)
                        cg = c_msg.by_number(2)
                        cb = c_msg.by_number(3)
                        if cr and cg and cb:
                            r = int(max(0.0, min(1.0, cr[0].fixed_float() or 1.0)) * 255)
                            g = int(max(0.0, min(1.0, cg[0].fixed_float() or 1.0)) * 255)
                            b = int(max(0.0, min(1.0, cb[0].fixed_float() or 1.0)) * 255)
                            color_hex = f"#{r:02X}{g:02X}{b:02X}"

                author = ""
                f33_auth = msg.by_number(33)
                if f33_auth and isinstance(f33_auth[0].value, bytes):
                    author = f33_auth[0].value.decode("utf-8", errors="ignore")

                note_text = _extract_sticky_note_text(msg)

                is_folded = bool(meta.get("is_folded", False))
                if not is_folded:
                    for candidate_msg in (msg, rec):
                        f7_state = candidate_msg.by_number(7)
                        if f7_state and isinstance(f7_state[0].value, bytes):
                            m7 = try_decode_message(f7_state[0].value)
                            if m7 and m7.by_number(1) and isinstance(m7.by_number(1)[0].value, bytes):
                                m7_1 = try_decode_message(m7.by_number(1)[0].value)
                                if m7_1 and m7_1.by_number(1):
                                    is_folded = True
                                    break
                is_open = not is_folded

                sticky_notes[u_str] = StickyNote(
                    uuid=u_str,
                    x=x,
                    y=y,
                    width=w,
                    height=h,
                    color_hex=color_hex,
                    author=author,
                    text=note_text,
                    is_open=is_open,
                )

    return tuple(sticky_notes.values())


@dataclass(frozen=True)
class PageElement:
    """A structural summary of one decoded GoodNotes page record."""

    record_index: int
    uuid: str | None
    kind: str
    type_code: int | None
    attachment_uuid: str | None
    related_uuids: tuple[str, ...]
    field_numbers: tuple[int, ...]
    has_stroke_payload: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "record_index": self.record_index,
            "uuid": self.uuid,
            "kind": self.kind,
            "type_code": self.type_code,
            "attachment_uuid": self.attachment_uuid,
            "related_uuids": list(self.related_uuids),
            "field_numbers": list(self.field_numbers),
            "has_stroke_payload": self.has_stroke_payload,
        }


def parse_page_elements(records: Sequence[Message]) -> tuple[PageElement, ...]:
    """Summarize each page record without discarding raw unknown fields."""
    elements: list[PageElement] = []
    for record_index, record in enumerate(records):
        field_numbers = tuple(field.number for field in record.fields)

        uuid = None
        uuid_fields = record.by_number(1)
        if uuid_fields and isinstance(uuid_fields[0].value, bytes):
            try:
                candidate = uuid_fields[0].value.decode("utf-8")
            except UnicodeDecodeError:
                candidate = ""
            if _looks_like_uuid(candidate):
                uuid = candidate

        attachment_uuid = None
        f7_fields = record.by_number(7)
        if f7_fields and isinstance(f7_fields[0].value, bytes):
            try:
                candidate = f7_fields[0].value.decode("utf-8")
            except UnicodeDecodeError:
                candidate = ""
            if _looks_like_uuid(candidate):
                attachment_uuid = candidate

        if not attachment_uuid:
            attachment_fields = record.by_number(4)
            if attachment_fields and isinstance(attachment_fields[0].value, bytes):
                try:
                    candidate = attachment_fields[0].value.decode("utf-8")
                except UnicodeDecodeError:
                    candidate = ""
                if _looks_like_uuid(candidate):
                    attachment_uuid = candidate

        related_uuids = tuple(
            value
            for value in _utf8_uuids(record)
            if value != uuid and value != attachment_uuid
        )

        type_code = None
        type_fields = record.by_number(16)
        if type_fields and not isinstance(type_fields[0].value, bytes):
            type_code = int(type_fields[0].value)
        else:
            alt_type_fields = record.by_number(21)
            if alt_type_fields and not isinstance(alt_type_fields[0].value, bytes):
                type_code = int(alt_type_fields[0].value)

        has_stroke_payload = any(isinstance(field.value, bytes) and b"bv41" in field.value for field in record.fields)
        if has_stroke_payload:
            kind = "stroke"
        elif attachment_uuid is not None:
            kind = "attachment"
        else:
            kind = "element"

        elements.append(
            PageElement(
                record_index=record_index,
                uuid=uuid,
                kind=kind,
                type_code=type_code,
                attachment_uuid=attachment_uuid,
                related_uuids=related_uuids,
                field_numbers=field_numbers,
                has_stroke_payload=has_stroke_payload,
            )
        )
    return tuple(elements)