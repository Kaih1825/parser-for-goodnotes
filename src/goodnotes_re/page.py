"""Page model and background attachment metadata parser for GoodNotes documents."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import re
from typing import Sequence

from .element import ImageElement, PageElement, StickyNote, parse_image_elements, parse_page_elements, parse_sticky_notes
from .shape import ShapePath, parse_shape_record
from .stroke import Stroke, parse_stroke_field
from .text import TextElement, TextFragment, extract_text, parse_text_elements
from .wire import Message, decode_message, try_decode_message


@dataclass(frozen=True)
class PageDimensions:
    width: float = 612.0
    height: float = 792.0
    is_landscape: bool = False

    @classmethod
    def from_pdf_mediabox(cls, pdf_bytes: bytes) -> "PageDimensions":
        """Extract width, height, and orientation from PDF /MediaBox [0 0 w h]."""
        m = re.search(b"/MediaBox\\s*\\[\\s*([\\d\\.]+)\\s+([\\d\\.]+)\\s+([\\d\\.]+)\\s+([\\d\\.]+)\\s*\\]", pdf_bytes)
        if m:
            w = float(m.group(3))
            h = float(m.group(4))
            return cls(width=w, height=h, is_landscape=w > h)
        return cls()


@dataclass
class Page:
    index: int
    uuid: str
    member_path: str
    dimensions: PageDimensions
    background_attachment_path: str | None = None
    elements: tuple[PageElement, ...] = field(default_factory=tuple)
    shapes: list[ShapePath] = field(default_factory=list)
    strokes: list[Stroke] = field(default_factory=list)
    sticky_notes: tuple[StickyNote, ...] = field(default_factory=tuple)
    text_fragments: list[TextFragment] = field(default_factory=list)
    text_elements: tuple[TextElement, ...] = field(default_factory=tuple)
    image_elements: tuple[ImageElement, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "uuid": self.uuid,
            "member_path": self.member_path,
            "dimensions": {
                "width": self.dimensions.width,
                "height": self.dimensions.height,
                "is_landscape": self.dimensions.is_landscape,
            },
            "background_attachment_path": self.background_attachment_path,
            "element_count": len(self.elements),
            "shape_count": len(self.shapes),
            "stroke_count": len(self.strokes),
            "sticky_note_count": len(self.sticky_notes),
            "text_fragment_count": len(self.text_fragments),
            "text_element_count": len(self.text_elements),
            "image_element_count": len(self.image_elements),
            "elements": [element.as_dict() for element in self.elements],
            "shapes": [shape.as_dict() for shape in self.shapes],
            "strokes": [s.as_dict() for s in self.strokes],
            "sticky_notes": [sn.as_dict() for sn in self.sticky_notes],
            "text_fragments": [
                {"source_path": t.source_path, "format": t.format, "text": t.text} for t in self.text_fragments
            ],
            "text_elements": [te.as_dict() for te in self.text_elements],
            "image_elements": [ie.as_dict() for ie in self.image_elements],
        }


def parse_page_from_records(
    page_index: int,
    page_uuid: str,
    member_path: str,
    records: Sequence[Message],
    pdf_attachment_bytes: bytes | None = None,
    attachment_path: str | None = None,
) -> Page:
    """Construct a Page instance from note protobuf records and optional background PDF bytes."""
    dimensions = PageDimensions.from_pdf_mediabox(pdf_attachment_bytes) if pdf_attachment_bytes else PageDimensions()
    elements = parse_page_elements(records)
    sticky_notes = parse_sticky_notes(records)
    text_elements = parse_text_elements(records)
    image_elements = parse_image_elements(records)
    shapes: list[ShapePath] = []
    strokes: list[Stroke] = []
    fragments: list[TextFragment] = []

    # Map UUID -> metadata (is_erased, type_code) & parent UUID from metadata records
    uuid_metadata: dict[str, dict[str, object]] = {}
    uuid_parent: dict[str, str] = {}
    sn_uuids = {sn.uuid for sn in sticky_notes}
    for record in records:
        f1 = record.by_number(1)
        f3 = record.by_number(3)
        f16 = record.by_number(16)
        f20 = record.by_number(20)
        f21 = record.by_number(21)
        if f1 and isinstance(f1[0].value, bytes):
            try:
                u_str = f1[0].value.decode("utf-8")
                if len(u_str) == 36 and "-" in u_str:
                    is_erased = bool(f3 and f3[0].value == 1)
                    type_code = f16[0].value if f16 and not isinstance(f16[0].value, bytes) else None
                    uuid_metadata[u_str] = {"is_erased": is_erased, "type_code": type_code}

                    p_20 = ""
                    if f20 and isinstance(f20[0].value, bytes):
                        try:
                            cand = f20[0].value.decode("utf-8")
                            if len(cand) == 36 and "-" in cand:
                                p_20 = cand
                        except UnicodeDecodeError:
                            pass

                    p_21 = ""
                    if f21 and isinstance(f21[0].value, bytes):
                        try:
                            cand = f21[0].value.decode("utf-8")
                            if len(cand) == 36 and "-" in cand:
                                p_21 = cand
                        except UnicodeDecodeError:
                            pass

                    if p_21 in sn_uuids:
                        uuid_parent[u_str] = p_21
                    elif p_20 in sn_uuids:
                        uuid_parent[u_str] = p_20
                    elif p_20:
                        uuid_parent[u_str] = p_20
                    elif p_21:
                        uuid_parent[u_str] = p_21
            except UnicodeDecodeError:
                pass

    for r_idx, record in enumerate(records):
        rec_path = f"{member_path}.record[{r_idx}]"
        # Extract text fragments / sticky note content
        for frag in extract_text(record, rec_path):
            fragments.append(frag)

        shape = parse_shape_record(r_idx, record)
        if shape is not None:
            if shape.uuid:
                meta = uuid_metadata.get(shape.uuid, {})
                if meta.get("is_erased"):
                    continue
            shapes.append(shape)

        def process_stroke_bytes(val: bytes):
            stroke_uuid = f"stroke_{r_idx}"
            f1 = record.by_number(1)
            if f1 and isinstance(f1[0].value, bytes):
                try:
                    u_str = f1[0].value.decode("utf-8")
                    if len(u_str) == 36 and "-" in u_str:
                        stroke_uuid = u_str
                except UnicodeDecodeError:
                    pass

            if val.startswith(b"\n$") and len(val) >= 38:
                try:
                    stroke_uuid = val[2:38].decode("utf-8")
                except UnicodeDecodeError:
                    pass

            meta = uuid_metadata.get(stroke_uuid, {})
            if meta.get("is_erased"):
                return

            parent_uuid = uuid_parent.get(stroke_uuid)

            try:
                sub_strokes = parse_stroke_field(stroke_uuid, val, parent_uuid=parent_uuid)
                if sub_strokes:
                    strokes.extend(sub_strokes)
            except Exception:
                pass

        for f in record.fields:
            if isinstance(f.value, bytes) and b"bv41" in f.value:
                process_stroke_bytes(f.value)

        f7 = record.by_number(7)
        if f7 and isinstance(f7[0].value, bytes) and b"bv41" not in f7[0].value:
            # Only look one level deeper when the outer per-field scan above
            # couldn't already see a "bv41" marker directly in field 7's raw
            # bytes; otherwise this would re-process the same stroke twice.
            sub_msg = try_decode_message(f7[0].value)
            if sub_msg is not None:
                for sf in sub_msg.fields:
                    if isinstance(sf.value, bytes) and b"bv41" in sf.value:
                        process_stroke_bytes(sf.value)

    # Map (color_hex, width) -> dash_pattern for brush dash inheritance to shapes
    brush_dash_map = {}
    for stroke in strokes:
        if stroke.dash_pattern:
            key = (stroke.color_hex, round(stroke.width, 2))
            brush_dash_map[key] = stroke.dash_pattern

    if brush_dash_map and shapes:
        for idx, sh in enumerate(shapes):
            if not sh.dash_pattern:
                key = (sh.color_hex, round(sh.stroke_width, 2))
                if key in brush_dash_map:
                    shapes[idx] = replace(sh, dash_pattern=brush_dash_map[key])

    return Page(
        index=page_index,
        uuid=page_uuid,
        member_path=member_path,
        dimensions=dimensions,
        background_attachment_path=attachment_path,
        elements=elements,
        shapes=shapes,
        strokes=strokes,
        sticky_notes=sticky_notes,
        text_fragments=fragments,
        text_elements=text_elements,
        image_elements=image_elements,
    )