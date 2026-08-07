"""JSON and high-fidelity vector SVG export for GoodNotes documents."""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Iterator

from .archive import GoodNotesDocument
from .pdf import render_pdf_page_to_svg
from .stroke import build_stroke_ribbon
from .wire import Field, Message, WireType, try_decode_message


def write_json(document: GoodNotesDocument, output: str | Path) -> None:
    Path(output).write_text(json.dumps(document.as_json(), ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _messages(message: Message, path: str = "") -> Iterator[tuple[str, Message]]:
    yield path or "$", message
    for index, field in enumerate(message.fields):
        if isinstance(field.value, bytes):
            nested = try_decode_message(field.value)
            if nested is not None:
                yield from _messages(nested, f"{path}.f{field.number}[{index}]")


def _point(message: Message) -> tuple[float, float] | None:
    """Recognise only an explicit nested fixed-width x/y protobuf point."""
    x, y = message.by_number(1), message.by_number(2)
    if len(x) != 1 or len(y) != 1:
        return None
    if x[0].wire_type not in (WireType.FIXED32, WireType.FIXED64) or y[0].wire_type not in (WireType.FIXED32, WireType.FIXED64):
        return None
    fx, fy = x[0].fixed_float(), y[0].fixed_float()
    if fx is None or fy is None or not (-1e6 < fx < 1e6 and -1e6 < fy < 1e6):
        return None
    return fx, fy


def stroke_candidates(message: Message) -> Iterator[tuple[str, list[tuple[float, float]]]]:
    """Find repeated nested x/y point messages; never inspect raw float bytes."""
    for path, candidate in _messages(message):
        by_number: dict[int, list[Field]] = {}
        for field in candidate.fields:
            by_number.setdefault(field.number, []).append(field)
        for number, fields in by_number.items():
            points: list[tuple[float, float]] = []
            for field in fields:
                if not isinstance(field.value, bytes):
                    break
                point_message = try_decode_message(field.value)
                point = _point(point_message) if point_message else None
                if point is None:
                    break
                points.append(point)
            if len(points) >= 2:
                yield f"{path}.f{number}", points


import base64

def write_svg(
    document: GoodNotesDocument,
    directory: str | Path,
    fill_shapes: bool = True,
    sticky_note_state: str | None = None,
    textbox_state: str | None = None,
) -> list[Path]:
    """Export SVG vector pages for each page in the GoodNotes document.

    sticky_note_state: Optional override for sticky notes state ('open' or 'close').
    textbox_state: Optional toggle for drawing text box bounding borders ('open' or 'close').
    """
    output = Path(directory)
    output.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    pages = document.pages()
    # GoodNotes internal coordinates are 132 DPI, PDF canvas is 72 DPI
    dpi_scale = 72.0 / 132.0

    for page in pages:
        pw, ph = page.dimensions.width, page.dimensions.height
        name = f"page_{page.index + 1}_{page.member_path.replace('/', '_')}.svg"
        target = output / name

        elements: list[str] = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{pw:.2f}" height="{ph:.2f}" viewBox="0 0 {pw:.2f} {ph:.2f}">',
            f'<!-- GoodNotes Page {page.index + 1} ({page.uuid}) -->',
        ]

        if page.background_attachment_path and page.background_attachment_path in document.member_names():
            elements.append(f'<!-- Background Attachment: {html.escape(page.background_attachment_path)} -->')
            try:
                bdata = document.read(page.background_attachment_path)
                if bdata.startswith((b"\xff\xd8\xff", b"\x89PNG")):
                    mime = "image/jpeg" if bdata.startswith(b"\xff\xd8\xff") else "image/png"
                    img_b64 = base64.b64encode(bdata).decode("ascii")
                    elements.append(
                        f'<image href="data:{mime};base64,{img_b64}" x="0" y="0" width="{pw:.2f}" height="{ph:.2f}" preserveAspectRatio="none"/>'
                    )
                elif bdata.startswith(b"%PDF"):
                    pdf_svg = render_pdf_page_to_svg(bdata, page_index=page.index, width=pw, height=ph)
                    if pdf_svg:
                        elements.append(pdf_svg)
            except Exception:
                pass

        # Determine sticky note open/close state override
        state_override: bool | None = None
        if sticky_note_state:
            st_lower = sticky_note_state.lower().strip()
            if st_lower == "open":
                state_override = True
            elif st_lower in ("close", "closed"):
                state_override = False

        # Determine text box border toggle
        draw_textbox_border: bool = False
        if textbox_state:
            tb_lower = textbox_state.lower().strip()
            if tb_lower in ("open", "true", "1", "yes"):
                draw_textbox_border = True

        # Render sticky notes (便條紙) cards and icons
        sticky_note_map = {note.uuid: note for note in page.sticky_notes}
        for note in page.sticky_notes:
            is_open = state_override if state_override is not None else note.is_open
            nx = note.x * dpi_scale
            ny = note.y * dpi_scale
            if is_open:
                nw = note.width * dpi_scale
                nh = note.height * dpi_scale
                elements.append(f'<!-- Sticky Note (Expanded): {html.escape(note.uuid)} -->')
                elements.append(
                    f'<rect x="{nx:.2f}" y="{ny:.2f}" width="{nw:.2f}" height="{nh:.2f}" rx="8" ry="8" fill="{note.color_hex}" fill-opacity="0.95" stroke="#E0CE5E" stroke-width="0.8"/>'
                )
                if note.author:
                    tx = nx + 12.0 * dpi_scale
                    ty = ny + nh - 12.0 * dpi_scale
                    elements.append(
                        f'<text x="{tx:.2f}" y="{ty:.2f}" font-family="sans-serif" font-size="10" fill="#555555" font-weight="500">{html.escape(note.author)}</text>'
                    )
            else:
                # Render folded note icon indicator at (nx, ny)
                elements.append(f'<!-- Sticky Note (Folded): {html.escape(note.uuid)} -->')
                elements.append(
                    f'<g transform="translate({nx:.2f}, {ny:.2f})">'
                    f'<path d="M 3 0 L 14 0 C 16 0 17 1 17 3 L 17 14 L 11 20 L 3 20 C 1 20 0 19 0 17 L 0 3 C 0 1 1 0 3 0 Z" fill="{note.color_hex}" stroke="#555555" stroke-width="0.8" stroke-linejoin="round"/>'
                    f'<path d="M 11 20 L 11 15 C 11 14.5 11.5 14 12 14 L 17 14 Z" fill="#D8C554" stroke="#555555" stroke-width="0.8" stroke-linejoin="round"/>'
                    f'</g>'
                )

        # Render vector shapes
        has_arrows = any(getattr(s, "start_arrow", False) or getattr(s, "end_arrow", False) for s in page.shapes)
        if has_arrows:
            elements.append(
                '<defs>'
                '<marker id="arrow-start" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse">'
                '<path d="M 0 5 L 10 0 L 7 5 L 10 10 Z" fill="#1e1b1b"/>'
                '</marker>'
                '<marker id="arrow-end" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="4" markerHeight="4" orient="auto">'
                '<path d="M 0 0 L 10 5 L 0 10 L 3 5 Z" fill="#1e1b1b"/>'
                '</marker>'
                '</defs>'
            )

        for shape in page.shapes:
            is_polyline = 1 in shape.field_numbers or 2 not in shape.field_numbers or shape.shape_type == "polyline"
            pts = shape.points
            dash_pattern = getattr(shape, "dash_pattern", None)
            dash_attr = f' stroke-dasharray="{" ".join(f"{d * dpi_scale:.2f}" for d in dash_pattern)}"' if dash_pattern else ""

            marker_attr = ""
            if getattr(shape, "start_arrow", False):
                marker_attr += ' marker-start="url(#arrow-start)"'
            if getattr(shape, "end_arrow", False):
                marker_attr += ' marker-end="url(#arrow-end)"'

            is_filled = getattr(shape, "is_filled", True)
            fill_attr = f'fill="{shape.color_hex}" fill-opacity="0.08"' if (fill_shapes and is_filled) else 'fill="none"'
            stroke_w = max(0.5, shape.stroke_width * dpi_scale)

            if shape.shape_type == "rectangle" and len(pts) == 5:
                left = min(p[0] for p in pts) * dpi_scale
                top = min(p[1] for p in pts) * dpi_scale
                right = max(p[0] for p in pts) * dpi_scale
                bottom = max(p[1] for p in pts) * dpi_scale
                w = right - left
                h = bottom - top
                rx_val = min(6.0 * dpi_scale, w / 4.0, h / 4.0)
                elements.append(
                    f'<rect x="{left:.2f}" y="{top:.2f}" width="{w:.2f}" height="{h:.2f}" rx="{rx_val:.2f}" ry="{rx_val:.2f}" stroke="{shape.color_hex}" stroke-opacity="{shape.alpha:.2f}" stroke-width="{stroke_w:.2f}" stroke-linecap="round" stroke-linejoin="round"{dash_attr}{marker_attr} {fill_attr}/>'
                )
            elif is_polyline:
                if len(pts) == 2:
                    (x1, y1), (x2, y2) = pts
                    elements.append(
                        f'<line x1="{x1 * dpi_scale:.2f}" y1="{y1 * dpi_scale:.2f}" x2="{x2 * dpi_scale:.2f}" y2="{y2 * dpi_scale:.2f}" stroke="{shape.color_hex}" stroke-opacity="{shape.alpha:.2f}" stroke-width="{stroke_w:.2f}" stroke-linecap="round"{dash_attr}{marker_attr} fill="none"/>'
                    )
                elif len(pts) >= 3 and shape.shape_type == "polyline":
                    path = [f'M {pts[0][0] * dpi_scale:.2f} {pts[0][1] * dpi_scale:.2f}']
                    for i in range(1, len(pts) - 1):
                        cx = (pts[i][0] + pts[i+1][0]) / 2.0
                        cy = (pts[i][1] + pts[i+1][1]) / 2.0
                        path.append(f'Q {pts[i][0] * dpi_scale:.2f} {pts[i][1] * dpi_scale:.2f} {cx * dpi_scale:.2f} {cy * dpi_scale:.2f}')
                    path.append(f'L {pts[-1][0] * dpi_scale:.2f} {pts[-1][1] * dpi_scale:.2f}')
                    d_path = " ".join(path)
                    elements.append(
                        f'<path d="{d_path}" stroke="{shape.color_hex}" stroke-opacity="{shape.alpha:.2f}" stroke-width="{stroke_w:.2f}" stroke-linecap="round" stroke-linejoin="round"{dash_attr}{marker_attr} fill="none"/>'
                    )
                else:
                    path = [f'M {pts[0][0] * dpi_scale:.2f} {pts[0][1] * dpi_scale:.2f}']
                    for x, y in pts[1:]:
                        path.append(f'L {x * dpi_scale:.2f} {y * dpi_scale:.2f}')
                    if shape.shape_type != "polyline":
                        path.append("Z")
                    d_path = " ".join(path)
                    elements.append(
                        f'<path d="{d_path}" stroke="{shape.color_hex}" stroke-opacity="{shape.alpha:.2f}" stroke-width="{stroke_w:.2f}" stroke-linecap="round" stroke-linejoin="round"{dash_attr}{marker_attr} {fill_attr}/>'
                    )
            else:
                # Curves
                if len(pts) == 3:
                    p0, p1, p2 = pts
                    d_path = (
                        f"M {p0[0] * dpi_scale:.2f} {p0[1] * dpi_scale:.2f} "
                        f"Q {p1[0] * dpi_scale:.2f} {p1[1] * dpi_scale:.2f} "
                        f"{p2[0] * dpi_scale:.2f} {p2[1] * dpi_scale:.2f}"
                    )
                elif len(pts) == 4:
                    p0, p1, p2, p3 = pts
                    d_path = (
                        f"M {p0[0] * dpi_scale:.2f} {p0[1] * dpi_scale:.2f} "
                        f"C {p1[0] * dpi_scale:.2f} {p1[1] * dpi_scale:.2f} "
                        f"{p2[0] * dpi_scale:.2f} {p2[1] * dpi_scale:.2f} "
                        f"{p3[0] * dpi_scale:.2f} {p3[1] * dpi_scale:.2f}"
                    )
                else:
                    path = [f'M {pts[0][0] * dpi_scale:.2f} {pts[0][1] * dpi_scale:.2f}']
                    for x, y in pts[1:]:
                        path.append(f'L {x * dpi_scale:.2f} {y * dpi_scale:.2f}')
                    d_path = " ".join(path)
                elements.append(
                    f'<path d="{d_path}" stroke="{shape.color_hex}" stroke-opacity="{shape.alpha:.2f}" stroke-width="{stroke_w:.2f}" stroke-linecap="round" stroke-linejoin="round"{dash_attr}{marker_attr} {fill_attr}/>'
                )

        shape_uuids = {shape.uuid for shape in page.shapes if shape.uuid}
        from .stroke import StrokePoint

        for stroke in page.strokes:
            base_uuid = stroke.uuid.split("_")[0] if stroke.uuid else ""
            if base_uuid in shape_uuids:
                continue

            pts = stroke.points
            outline_polys = stroke.outline_polygons

            if stroke.parent_uuid and stroke.parent_uuid in sticky_note_map:
                parent_note = sticky_note_map[stroke.parent_uuid]
                parent_is_open = state_override if state_override is not None else parent_note.is_open
                if not parent_is_open:
                    # Skip strokes belonging to folded notes
                    continue
                # Shift stroke points by parent note origin
                pts = tuple(StrokePoint(pt.x + parent_note.x, pt.y + parent_note.y, pt.pressure) for pt in stroke.points)
                if outline_polys:
                    outline_polys = tuple(
                        tuple((px + parent_note.x, py + parent_note.y) for px, py in poly)
                        for poly in outline_polys
                    )

            ribbon_d = build_stroke_ribbon(
                pts,
                stroke.width,
                dpi_scale,
                tpl_format=stroke.tpl_format,
                outline_polygons=outline_polys,
                is_cut_start=stroke.is_cut_start,
                is_cut_end=stroke.is_cut_end,
            )
            if ribbon_d:
                if stroke.is_dot:
                    # Single point / Dot
                    pt = pts[0]
                    cx, cy = pt.x * dpi_scale, pt.y * dpi_scale
                    r = max(0.5, (stroke.width * pt.pressure * 0.5) * dpi_scale)
                    elements.append(
                        f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="{stroke.color_hex}" fill-opacity="{stroke.alpha:.2f}" stroke="none"/>'
                    )
                else:
                    elements.append(
                        f'<path d="{ribbon_d}" fill="{stroke.color_hex}" fill-opacity="{stroke.alpha:.2f}" stroke="none"/>'
                    )

        # Render image elements
        for img in page.image_elements:
            att_path = None
            if f"attachments/{img.attachment_uuid}" in document.member_names():
                att_path = f"attachments/{img.attachment_uuid}"
            if att_path:
                try:
                    idata = document.read(att_path)
                    mime = "image/jpeg" if idata.startswith(b"\xff\xd8\xff") else "image/png"
                    img_b64 = base64.b64encode(idata).decode("ascii")
                    crop_x = img.x * dpi_scale
                    crop_y = img.y * dpi_scale
                    crop_w = img.width * dpi_scale
                    crop_h = img.height * dpi_scale
                    rot_deg = img.rotation_rad * (180.0 / 3.141592653589793)

                    elements.append(f'<!-- Image Attachment: {html.escape(img.attachment_uuid)} -->')

                    is_cropped = (
                        img.orig_width > 0
                        and img.orig_height > 0
                        and (abs(img.width - img.orig_width) > 0.1 or abs(img.height - img.orig_height) > 0.1)
                    )

                    if is_cropped:
                        cx = crop_x + crop_w / 2.0
                        cy = crop_y + crop_h / 2.0
                        orig_w = img.orig_width * dpi_scale
                        orig_h = img.orig_height * dpi_scale
                        img_x = (img.orig_x - img.x) * dpi_scale
                        img_y = (img.orig_y - img.y) * dpi_scale

                        transform = f' transform="rotate({rot_deg:.2f}, {cx:.2f}, {cy:.2f})"' if abs(rot_deg) > 0.01 else ""

                        elements.append(
                            f'<g{transform}>'
                            f'<svg x="{crop_x:.2f}" y="{crop_y:.2f}" width="{crop_w:.2f}" height="{crop_h:.2f}" viewBox="0 0 {crop_w:.2f} {crop_h:.2f}" overflow="hidden">'
                            f'<image href="data:{mime};base64,{img_b64}" x="{img_x:.2f}" y="{img_y:.2f}" width="{orig_w:.2f}" height="{orig_h:.2f}" preserveAspectRatio="none"/>'
                            f'</svg>'
                            f'</g>'
                        )
                    else:
                        transform_attr = ""
                        if abs(rot_deg) > 0.01:
                            cx, cy = crop_x + crop_w / 2.0, crop_y + crop_h / 2.0
                            transform_attr = f' transform="rotate({rot_deg:.2f}, {cx:.2f}, {cy:.2f})"'
                        elements.append(
                            f'<image href="data:{mime};base64,{img_b64}" x="{crop_x:.2f}" y="{crop_y:.2f}" width="{crop_w:.2f}" height="{crop_h:.2f}" preserveAspectRatio="none"{transform_attr}/>'
                        )
                except Exception:
                    pass

        # Render rich text elements grouped by text box
        text_boxes: dict[tuple[float, float, str], list[TextElement]] = {}
        for te in page.text_elements:
            key = (round(te.x, 1), round(te.y, 1), te.uuid)
            text_boxes.setdefault(key, []).append(te)

        for (bx, by, uuid), te_list in text_boxes.items():
            box_x = bx * dpi_scale
            box_y = by * dpi_scale

            # Exact text box width and height from protobuf
            max_box_width = max((te.width for te in te_list if te.width > 0), default=0.0) * dpi_scale
            max_box_height = max((te.height for te in te_list if te.height > 0), default=0.0) * dpi_scale

            # Group text items into distinct lines across the text box
            lines: list[list[tuple[TextElement, str]]] = [[]]
            for te in te_list:
                txt = te.text or ""
                parts = txt.split("\n")
                for i, part in enumerate(parts):
                    if i > 0:
                        lines.append([])
                    lines[-1].append((te, part))

            # Calculate line heights and total content height
            line_heights: list[float] = []
            line_font_sizes: list[float] = []
            for line_items in lines:
                fs_max = 14.0 * dpi_scale
                for te, _ in line_items:
                    fs = te.font_size * dpi_scale
                    if fs >= 8.0:
                        fs_max = max(fs_max, fs)
                    elif fs < 8.0 and te.font_size > 0:
                        fs_max = max(fs_max, 24.0 * dpi_scale)
                line_font_sizes.append(fs_max)
                line_heights.append(fs_max * 1.15)

            bw = max_box_width if max_box_width > 0 else 50.0
            primary_fs = line_font_sizes[0]
            if len(lines) == 1:
                fit_bh = primary_fs * 0.85
                fit_by = box_y + (max_box_height - fit_bh) / 2.0 if max_box_height > fit_bh else box_y
                ly_0 = fit_by + (fit_bh + 0.62 * primary_fs) / 2.0
            else:
                fit_bh = max_box_height if max_box_height > 0 else sum(line_heights)
                fit_by = box_y
                total_text_block_h = sum(line_heights)
                v_gap = max(0.0, (fit_bh - total_text_block_h) / 2.0)
                ly_0 = fit_by + v_gap + (primary_fs * 0.70)

            # Draw text box border matching GoodNotes UI selection bounds
            if draw_textbox_border:
                elements.append(f'<!-- Text Box Border ({html.escape(uuid)}) -->')
                elements.append(
                    f'<rect x="{box_x:.2f}" y="{fit_by:.2f}" width="{bw:.2f}" height="{fit_bh:.2f}" fill="none" stroke="#38BDF8" stroke-width="0.8"/>'
                )

            current_y = ly_0
            numbered_counter = 0

            for line_idx, line_items in enumerate(lines):
                has_numbered = any(te.list_type == "numbered" for te, _ in line_items)
                if has_numbered:
                    numbered_counter += 1

                for te, line_str in line_items:
                    if not line_str.strip() and len(line_items) == 1 and line_idx == len(lines) - 1:
                        continue

                    font_size_pt = te.font_size * dpi_scale
                    if font_size_pt < 8.0:
                        font_size_pt = 24.0 * dpi_scale

                    style_attrs: list[str] = [
                        f'font-family="{html.escape(te.font_family)}"',
                        f'font-size="{font_size_pt:.2f}"',
                        f'fill="{te.color_hex}"',
                    ]
                    if te.alpha < 1.0:
                        style_attrs.append(f'fill-opacity="{te.alpha:.2f}"')
                    if te.is_bold:
                        style_attrs.append('font-weight="bold"')
                    if te.is_italic:
                        style_attrs.append('font-style="italic"')

                    decorations: list[str] = []
                    if te.is_underline:
                        decorations.append("underline")
                    if te.is_strikethrough:
                        decorations.append("line-through")
                    if decorations:
                        style_attrs.append(f'text-decoration="{" ".join(decorations)}"')

                    line_width = (te.width * dpi_scale) if te.width > 0 else max_box_width
                    line_style_attrs = list(style_attrs)

                    tx = box_x
                    if te.alignment == "center":
                        line_style_attrs.append('text-anchor="middle"')
                        if line_width > 0:
                            tx = box_x + line_width / 2.0
                    elif te.alignment == "right":
                        line_style_attrs.append('text-anchor="end"')
                        if line_width > 0:
                            tx = box_x + line_width
                    else:
                        line_style_attrs.append('text-anchor="start"')

                    display_text = line_str
                    if te.list_type == "bullet" and display_text:
                        display_text = f"• {display_text}"
                    elif te.list_type == "numbered" and display_text:
                        display_text = f"{numbered_counter}. {display_text}"

                    escaped_text = html.escape(display_text)
                    style_str = " ".join(line_style_attrs)

                    if escaped_text:
                        elements.append(
                            f'<text x="{tx:.2f}" y="{current_y:.2f}" {style_str}>{escaped_text}</text>'
                        )

                if line_idx < len(lines) - 1:
                    current_y += line_heights[line_idx]

        # Render fallback text fragments if no structured text elements found
        if not page.text_elements:
            for frag in page.text_fragments:
                if frag.text and len(frag.text) < 200 and frag.format != "uuid" and not (len(frag.text) == 36 and frag.text.count("-") == 4):
                    escaped_text = html.escape(frag.text)
                    elements.append(
                        f'<text x="50" y="50" font-family="sans-serif" font-size="14" fill="#333333"><!-- Fragment: {escaped_text} --></text>'
                    )

        elements.append('</svg>\n')
        target.write_text('\n'.join(elements), encoding="utf-8")
        written.append(target)

    return written

