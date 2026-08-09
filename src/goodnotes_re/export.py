"""JSON and high-fidelity vector SVG export for GoodNotes documents."""
from __future__ import annotations

import html
import json
import math
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


def _catmull_rom_to_svg_path(pts: tuple[tuple[float, float], ...], scale: float = 1.0) -> str:
    if not pts:
        return ""
    if len(pts) == 1:
        x, y = pts[0][0] * scale, pts[0][1] * scale
        return f"M {x:.2f} {y:.2f} L {x:.2f} {y:.2f}"
    if len(pts) == 2:
        return f"M {pts[0][0]*scale:.2f} {pts[0][1]*scale:.2f} L {pts[1][0]*scale:.2f} {pts[1][1]*scale:.2f}"

    p = [pts[0]] + list(pts) + [pts[-1]]
    path = [f"M {pts[0][0]*scale:.2f} {pts[0][1]*scale:.2f}"]

    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i-1], p[i], p[i+1], p[i+2]

        d1 = math.hypot(p1[0] - p0[0], p1[1] - p0[1]) ** 0.5 or 1e-4
        d2 = math.hypot(p2[0] - p1[0], p2[1] - p1[1]) ** 0.5 or 1e-4
        d3 = math.hypot(p3[0] - p2[0], p3[1] - p2[1]) ** 0.5 or 1e-4

        t1x = (p1[0] - p0[0]) / d1 - (p2[0] - p0[0]) / (d1 + d2) + (p2[0] - p1[0]) / d2
        t1y = (p1[1] - p0[1]) / d1 - (p2[1] - p0[1]) / (d1 + d2) + (p2[1] - p1[1]) / d2
        t2x = (p2[0] - p1[0]) / d2 - (p3[0] - p1[0]) / (d2 + d3) + (p3[0] - p2[0]) / d3
        t2y = (p2[1] - p1[1]) / d2 - (p3[1] - p1[1]) / (d2 + d3) + (p3[1] - p2[1]) / d3

        t1x *= d2 / 3.0
        t1y *= d2 / 3.0
        t2x *= d2 / 3.0
        t2y *= d2 / 3.0

        c1x = p1[0] + t1x
        c1y = p1[1] + t1y
        c2x = p2[0] - t2x
        c2y = p2[1] - t2y

        path.append(f"C {c1x*scale:.2f} {c1y*scale:.2f} {c2x*scale:.2f} {c2y*scale:.2f} {p2[0]*scale:.2f} {p2[1]*scale:.2f}")

    return " ".join(path)


def _rounded_polygon_svg_path(pts: tuple[tuple[float, float], ...], r: float, scale: float = 1.0, is_closed: bool = True) -> str:
    if not pts:
        return ""
    if len(pts) == 1:
        x, y = pts[0][0] * scale, pts[0][1] * scale
        return f"M {x:.2f} {y:.2f} L {x:.2f} {y:.2f}"
    if len(pts) == 2:
        return f"M {pts[0][0]*scale:.2f} {pts[0][1]*scale:.2f} L {pts[1][0]*scale:.2f} {pts[1][1]*scale:.2f}"

    p_list = [p for p in pts]
    if len(p_list) > 1 and p_list[-1] == p_list[0]:
        p_list.pop()

    n = len(p_list)
    if n < 3:
        return f"M {pts[0][0]*scale:.2f} {pts[0][1]*scale:.2f} L {pts[-1][0]*scale:.2f} {pts[-1][1]*scale:.2f}"

    if r <= 0.0:
        path = [f"M {p_list[0][0]*scale:.2f} {p_list[0][1]*scale:.2f}"]
        for p in p_list[1:]:
            path.append(f"L {p[0]*scale:.2f} {p[1]*scale:.2f}")
        if is_closed:
            path.append("Z")
        return " ".join(path)

    path_cmds = []
    for i in range(n):
        p_prev = p_list[(i - 1) % n]
        p_curr = p_list[i]
        p_next = p_list[(i + 1) % n]

        v1 = (p_prev[0] - p_curr[0], p_prev[1] - p_curr[1])
        v2 = (p_next[0] - p_curr[0], p_next[1] - p_curr[1])

        len1 = math.hypot(v1[0], v1[1])
        len2 = math.hypot(v2[0], v2[1])

        if len1 < 1e-4 or len2 < 1e-4:
            continue

        eff_r = min(r, len1 / 2.0, len2 / 2.0)
        start_pt = (p_curr[0] + (v1[0] / len1) * eff_r, p_curr[1] + (v1[1] / len1) * eff_r)
        end_pt = (p_curr[0] + (v2[0] / len2) * eff_r, p_curr[1] + (v2[1] / len2) * eff_r)

        if i == 0:
            path_cmds.append(f"M {start_pt[0]*scale:.2f} {start_pt[1]*scale:.2f}")

        path_cmds.append(f"Q {p_curr[0]*scale:.2f} {p_curr[1]*scale:.2f} {end_pt[0]*scale:.2f} {end_pt[1]*scale:.2f}")

        p_next_next = p_list[(i + 2) % n]
        v_next_to_next = (p_next_next[0] - p_next[0], p_next_next[1] - p_next[1])
        len_next_to_next = math.hypot(v_next_to_next[0], v_next_to_next[1])
        eff_r_next = min(r, len2 / 2.0, len_next_to_next / 2.0)
        v_next_back = (-v2[0], -v2[1])
        next_start_pt = (p_next[0] + (v_next_back[0] / len2) * eff_r_next, p_next[1] + (v_next_back[1] / len2) * eff_r_next)

        path_cmds.append(f"L {next_start_pt[0]*scale:.2f} {next_start_pt[1]*scale:.2f}")

    if is_closed:
        path_cmds.append("Z")
    return " ".join(path_cmds)


def _get_marker_ref_x(path_d: str, align: str = "tip") -> float:
    """Calculates refX dynamically from marker path geometry."""
    import re
    coords = [float(x) for x in re.findall(r"[-+]?\d*\.\d+|\d+", path_d)]
    x_coords = coords[0::2] if coords else [5.0]
    if align == "min":
        return min(x_coords)
    elif align == "max":
        return max(x_coords)
    return (min(x_coords) + max(x_coords)) / 2.0


def write_svg(
    document: GoodNotesDocument,
    directory: str | Path,
    fill_shapes: bool = True,
    sticky_note_state: str | None = None,
    textbox_state: bool = False,
    parse_all: bool = False
) -> list[Path]:
    """Export SVG vector pages for each page in the GoodNotes document.

    sticky_note_state: Optional override for sticky notes state ('open' or 'close').
    textbox_state: Optional toggle for drawing text box bounding borders ('open' or 'close').
    """
    output = Path(directory)
    output.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    pages = document.pages(parse_all=parse_all)
    
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
                    pdf_svg = render_pdf_page_to_svg(
                        bdata,
                        page_index=page.index,
                        width=pw,
                        height=ph,
                        id_prefix=f"background_{page.index}",
                    )
                    if pdf_svg:
                        elements.append(pdf_svg)
            except Exception:
                pass

        # Render image elements (placed right above background, beneath strokes, shapes and text)
        for img in page.image_elements:
            att_path = None
            if f"attachments/{img.attachment_uuid}" in document.member_names():
                att_path = f"attachments/{img.attachment_uuid}"
            if att_path:
                try:
                    idata = document.read(att_path)
                    is_pdf_attachment = idata.startswith(b"%PDF")
                    mime = "image/jpeg" if idata.startswith(b"\xff\xd8\xff") else "image/png"
                    img_b64 = None if is_pdf_attachment else base64.b64encode(idata).decode("ascii")
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

                        if is_pdf_attachment:
                            # Vector sticker/attachment: rasterizing to PNG/JPEG would
                            # mislabel the mime type and fail to decode, so render the
                            # PDF page as an SVG fragment sized to the *original*
                            # (uncropped) attachment box, then reuse the same
                            # translate + viewBox-clip technique used for raster crops.
                            inner_svg = render_pdf_page_to_svg(
                                idata,
                                page_index=0,
                                width=orig_w,
                                height=orig_h,
                                id_prefix=f"attachment_{img.uuid}_crop",
                            )
                            if inner_svg:
                                elements.append(
                                    f'<g{transform}>'
                                    f'<svg x="{crop_x:.2f}" y="{crop_y:.2f}" width="{crop_w:.2f}" height="{crop_h:.2f}" viewBox="0 0 {crop_w:.2f} {crop_h:.2f}" overflow="hidden">'
                                    f'<g transform="translate({img_x:.2f},{img_y:.2f})">{inner_svg}</g>'
                                    f'</svg>'
                                    f'</g>'
                                )
                        else:
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

                        if is_pdf_attachment:
                            inner_svg = render_pdf_page_to_svg(
                                idata,
                                page_index=0,
                                width=crop_w,
                                height=crop_h,
                                id_prefix=f"attachment_{img.uuid}",
                            )
                            if inner_svg:
                                elements.append(
                                    f'<g{transform_attr}>'
                                    f'<svg x="{crop_x:.2f}" y="{crop_y:.2f}" width="{crop_w:.2f}" height="{crop_h:.2f}">{inner_svg}</svg>'
                                    f'</g>'
                                )
                        else:
                            elements.append(
                                f'<image href="data:{mime};base64,{img_b64}" x="{crop_x:.2f}" y="{crop_y:.2f}" width="{crop_w:.2f}" height="{crop_h:.2f}" preserveAspectRatio="none"{transform_attr}/>'
                            )
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
                    f'<rect x="{nx:.2f}" y="{ny:.2f}" width="{nw:.2f}" height="{nh:.2f}" rx="8" ry="8" fill="{note.color_hex}" fill-opacity="0.95" stroke="rgba(0,0,0,0.15)" stroke-width="0.8"/>'
                )
                if note.author:
                    tx = nx + 12.0 * dpi_scale
                    ty = ny + nh - 12.0 * dpi_scale
                    elements.append(
                        f'<text x="{tx:.2f}" y="{ty:.2f}" font-family="sans-serif" font-size="10" fill="#555555" font-weight="500">{html.escape(note.author)}</text>'
                    )
            else:
                # Render folded note icon indicator at (nx, ny) with natural opacity overlay
                elements.append(f'<!-- Sticky Note (Folded): {html.escape(note.uuid)} -->')
                elements.append(
                    f'<g transform="translate({nx:.2f}, {ny:.2f})">'
                    f'<path d="M 3 0 L 14 0 C 16 0 17 1 17 3 L 17 14 L 11 20 L 3 20 C 1 20 0 19 0 17 L 0 3 C 0 1 1 0 3 0 Z" fill="{note.color_hex}" stroke="rgba(0,0,0,0.25)" stroke-width="0.8" stroke-linejoin="round"/>'
                    f'<path d="M 11 20 L 11 15 C 11 14.5 11.5 14 12 14 L 17 14 Z" fill="black" fill-opacity="0.18" stroke="rgba(0,0,0,0.25)" stroke-width="0.8" stroke-linejoin="round"/>'
                    f'</g>'
                )

        # Render vector shapes
        arrow_shapes = [s for s in page.shapes if getattr(s, "start_arrow", False) or getattr(s, "end_arrow", False)]
        if arrow_shapes:
            arrow_colors = sorted({s.color_hex for s in arrow_shapes})
            defs_elements = ['<defs>']
            for color in arrow_colors:
                color_clean = color.replace('#', '')

                open_start_path = "M 10 0 L 0 5 L 10 10"
                open_end_path = "M 0 0 L 10 5 L 0 10"
                filled_start_path = "M 10 0 L 0 5 L 10 10 Z"
                filled_end_path = "M 0 0 L 10 5 L 0 10 Z"

                # Dual formulas: Open V-Shape aligns to tip vertex; Solid Triangle aligns to solid base
                rx_open_start = _get_marker_ref_x(open_start_path, "min")
                rx_open_end = _get_marker_ref_x(open_end_path, "max")
                rx_filled_start = _get_marker_ref_x(filled_start_path, "max")
                rx_filled_end = _get_marker_ref_x(filled_end_path, "min")

                # Open V-shape arrowhead (Style 1)
                defs_elements.append(
                    f'<marker id="arrow-start-open-{color_clean}" viewBox="0 0 10 10" refX="{rx_open_start:.2f}" refY="5" markerWidth="4.5" markerHeight="4.5" orient="auto">'
                    f'<path d="{open_start_path}" fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'
                    f'</marker>'
                    f'<marker id="arrow-end-open-{color_clean}" viewBox="0 0 10 10" refX="{rx_open_end:.2f}" refY="5" markerWidth="4.5" markerHeight="4.5" orient="auto">'
                    f'<path d="{open_end_path}" fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'
                    f'</marker>'
                )
                # Filled triangle arrowhead (Style 2)
                defs_elements.append(
                    f'<marker id="arrow-start-filled-{color_clean}" viewBox="0 0 10 10" refX="{rx_filled_start:.2f}" refY="5" markerWidth="4.5" markerHeight="4.5" orient="auto">'
                    f'<path d="{filled_start_path}" fill="{color}"/>'
                    f'</marker>'
                    f'<marker id="arrow-end-filled-{color_clean}" viewBox="0 0 10 10" refX="{rx_filled_end:.2f}" refY="5" markerWidth="4.5" markerHeight="4.5" orient="auto">'
                    f'<path d="{filled_end_path}" fill="{color}"/>'
                    f'</marker>'
                )
                # Circle dot arrowhead (Style 3)
                defs_elements.append(
                    f'<marker id="arrow-start-dot-{color_clean}" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="4.5" markerHeight="4.5" orient="auto">'
                    f'<circle cx="5" cy="5" r="4" fill="{color}"/>'
                    f'</marker>'
                    f'<marker id="arrow-end-dot-{color_clean}" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="4.5" markerHeight="4.5" orient="auto">'
                    f'<circle cx="5" cy="5" r="4" fill="{color}"/>'
                    f'</marker>'
                )
            defs_elements.append('</defs>')
            elements.append("".join(defs_elements))

        for shape in page.shapes:
            is_polyline = 1 in shape.field_numbers or 2 not in shape.field_numbers or shape.shape_type == "polyline"
            pts = shape.points
            stroke_w = max(0.5, shape.stroke_width * dpi_scale)

            dash_pattern = getattr(shape, "dash_pattern", None)
            dash_attr = ""
            if dash_pattern:
                first_val = dash_pattern[0]
                gap_val = dash_pattern[1] if len(dash_pattern) > 1 else dash_pattern[0]
                if first_val <= 2.5:
                    dot_gap = max(stroke_w * 2.5, gap_val * 2.0 * dpi_scale)
                    dash_attr = f' stroke-dasharray="0 {dot_gap:.2f}"'
                else:
                    dash_len = max(stroke_w * 2.5, first_val * dpi_scale)
                    gap_len = max(stroke_w * 2.0, gap_val * dpi_scale)
                    dash_attr = f' stroke-dasharray="{dash_len:.2f} {gap_len:.2f}"'

            marker_attr = ""
            c_clean = shape.color_hex.replace('#', '')
            s_style = int(getattr(shape, "start_arrow", 0))
            e_style = int(getattr(shape, "end_arrow", 0))

            if s_style == 1:
                marker_attr += f' marker-start="url(#arrow-start-open-{c_clean})"'
            elif s_style == 2 or (isinstance(getattr(shape, "start_arrow", False), bool) and shape.start_arrow):
                marker_attr += f' marker-start="url(#arrow-start-filled-{c_clean})"'
            elif s_style >= 3:
                marker_attr += f' marker-start="url(#arrow-start-dot-{c_clean})"'

            if e_style == 1:
                marker_attr += f' marker-end="url(#arrow-end-open-{c_clean})"'
            elif e_style == 2 or (isinstance(getattr(shape, "end_arrow", False), bool) and shape.end_arrow):
                marker_attr += f' marker-end="url(#arrow-end-filled-{c_clean})"'
            elif e_style >= 3:
                marker_attr += f' marker-end="url(#arrow-end-dot-{c_clean})"'

            is_filled = getattr(shape, "is_filled", True)
            if fill_shapes and is_filled:
                fill_opacity = "1.0" if getattr(shape, "is_text_box_background", False) else "0.08"
                fill_attr = f'fill="{shape.color_hex}" fill-opacity="{fill_opacity}"'
            else:
                fill_attr = 'fill="none"'

            c_rad = getattr(shape, "corner_radius", 0.0)
            is_dotted = bool(dash_pattern and dash_pattern[0] <= 2.5)
            if marker_attr:
                join_cap_attr = 'stroke-linecap="butt" stroke-linejoin="miter"'
            else:
                join_cap_attr = 'stroke-linecap="round" stroke-linejoin="round"'

            if shape.shape_type == "ellipse" and shape.cx is not None and shape.cy is not None:
                cx = shape.cx * dpi_scale
                cy = shape.cy * dpi_scale
                rx = (shape.rx or 0.0) * dpi_scale
                ry = (shape.ry or 0.0) * dpi_scale
                elements.append(
                    f'<ellipse cx="{cx:.2f}" cy="{cy:.2f}" rx="{rx:.2f}" ry="{ry:.2f}" stroke="{shape.color_hex}" stroke-opacity="{shape.alpha:.2f}" stroke-width="{stroke_w:.2f}" {join_cap_attr}{dash_attr}{marker_attr} {fill_attr}/>'
                )
            elif shape.shape_type == "capsule":
                left = min(p[0] for p in pts) * dpi_scale
                top = min(p[1] for p in pts) * dpi_scale
                right = max(p[0] for p in pts) * dpi_scale
                bottom = max(p[1] for p in pts) * dpi_scale
                w = right - left
                h = bottom - top
                r_val = min(w, h) / 2.0
                elements.append(
                    f'<rect x="{left:.2f}" y="{top:.2f}" width="{w:.2f}" height="{h:.2f}" rx="{r_val:.2f}" ry="{r_val:.2f}" stroke="{shape.color_hex}" stroke-opacity="{shape.alpha:.2f}" stroke-width="{stroke_w:.2f}" stroke-linecap="round" stroke-linejoin="round"{dash_attr}{marker_attr} {fill_attr}/>'
                )
            elif shape.shape_type == "rectangle" and len(pts) == 5:
                left = min(p[0] for p in pts) * dpi_scale
                top = min(p[1] for p in pts) * dpi_scale
                right = max(p[0] for p in pts) * dpi_scale
                bottom = max(p[1] for p in pts) * dpi_scale
                w = right - left
                h = bottom - top
                if c_rad > 0.0:
                    rx_val = min(c_rad * dpi_scale, w / 4.0, h / 4.0)
                else:
                    rx_val = 0.0
                elements.append(
                    f'<rect x="{left:.2f}" y="{top:.2f}" width="{w:.2f}" height="{h:.2f}" rx="{rx_val:.2f}" ry="{rx_val:.2f}" stroke="{shape.color_hex}" stroke-opacity="{shape.alpha:.2f}" stroke-width="{stroke_w:.2f}" {join_cap_attr}{dash_attr}{marker_attr} {fill_attr}/>'
                )
            elif shape.shape_type == "polygon":
                is_closed = (len(pts) > 1 and pts[-1] == pts[0]) or is_filled
                d_path = _rounded_polygon_svg_path(pts, c_rad, dpi_scale, is_closed=is_closed)
                elements.append(
                    f'<path d="{d_path}" stroke="{shape.color_hex}" stroke-opacity="{shape.alpha:.2f}" stroke-width="{stroke_w:.2f}" {join_cap_attr}{dash_attr}{marker_attr} {fill_attr}/>'
                )
            elif is_polyline:
                if len(pts) == 2:
                    (x1, y1), (x2, y2) = pts
                    elements.append(
                        f'<line x1="{x1 * dpi_scale:.2f}" y1="{y1 * dpi_scale:.2f}" x2="{x2 * dpi_scale:.2f}" y2="{y2 * dpi_scale:.2f}" stroke="{shape.color_hex}" stroke-opacity="{shape.alpha:.2f}" stroke-width="{stroke_w:.2f}" {join_cap_attr}{dash_attr}{marker_attr} fill="none"/>'
                    )
                elif len(pts) == 3:
                    (x0, y0), (x1, y1), (x2, y2) = pts
                    area = abs((x1 - x0) * (y2 - y0) - (y1 - y0) * (x2 - x0))
                    dist = math.hypot(x2 - x0, y2 - y0)
                    if dist > 0 and (area / dist) < 3.0:
                        elements.append(
                            f'<line x1="{x0 * dpi_scale:.2f}" y1="{y0 * dpi_scale:.2f}" x2="{x2 * dpi_scale:.2f}" y2="{y2 * dpi_scale:.2f}" stroke="{shape.color_hex}" stroke-opacity="{shape.alpha:.2f}" stroke-width="{stroke_w:.2f}" {join_cap_attr}{dash_attr}{marker_attr} fill="none"/>'
                        )
                    else:
                        d_path = _catmull_rom_to_svg_path(pts, dpi_scale)
                        elements.append(
                            f'<path d="{d_path}" stroke="{shape.color_hex}" stroke-opacity="{shape.alpha:.2f}" stroke-width="{stroke_w:.2f}" {join_cap_attr}{dash_attr}{marker_attr} fill="none"/>'
                        )
                else:
                    d_path = _catmull_rom_to_svg_path(pts, dpi_scale)
                    elements.append(
                        f'<path d="{d_path}" stroke="{shape.color_hex}" stroke-opacity="{shape.alpha:.2f}" stroke-width="{stroke_w:.2f}" {join_cap_attr}{dash_attr}{marker_attr} fill="none"/>'
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

            dash_pattern = getattr(stroke, "dash_pattern", None)
            if stroke.is_dot and pts:
                # Single point / Dot
                pt = pts[0]
                cx, cy = pt.x * dpi_scale, pt.y * dpi_scale
                r = max(0.5, (stroke.width * pt.pressure * 0.5) * dpi_scale)
                elements.append(
                    f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="{stroke.color_hex}" fill-opacity="{stroke.alpha:.2f}" stroke="none"/>'
                )
            elif dash_pattern:
                stroke_w = max(0.5, stroke.width * dpi_scale)
                first_val = dash_pattern[0]
                gap_val = dash_pattern[1] if len(dash_pattern) > 1 else dash_pattern[0]
                if first_val <= 2.5:
                    dot_gap = max(stroke_w * 2.5, gap_val * 2.0 * dpi_scale)
                    dash_attr = f' stroke-dasharray="0 {dot_gap:.2f}"'
                else:
                    dash_len = max(stroke_w * 2.5, first_val * dpi_scale)
                    gap_len = max(stroke_w * 2.0, gap_val * dpi_scale)
                    dash_attr = f' stroke-dasharray="{dash_len:.2f} {gap_len:.2f}"'
                
                stroke_pts = tuple((pt.x, pt.y) for pt in pts)
                if len(stroke_pts) >= 2:
                    d_path = _catmull_rom_to_svg_path(stroke_pts, dpi_scale)
                    elements.append(
                        f'<path d="{d_path}" stroke="{stroke.color_hex}" stroke-opacity="{stroke.alpha:.2f}" stroke-width="{stroke_w:.2f}" stroke-linecap="round" stroke-linejoin="round"{dash_attr} fill="none"/>'
                    )
            else:
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
                    elements.append(
                        f'<path d="{ribbon_d}" fill="{stroke.color_hex}" fill-opacity="{stroke.alpha:.2f}" stroke="none"/>'
                    )

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
            is_sticky = any(uuid == note.uuid for note in page.sticky_notes)
            top_pad = (22.0 * dpi_scale) if is_sticky else (6.0 * dpi_scale)
            left_pad = (16.0 * dpi_scale) if is_sticky else (6.0 * dpi_scale)
            right_pad = (16.0 * dpi_scale) if is_sticky else (6.0 * dpi_scale)

            bw = max_box_width if max_box_width > 0 else 50.0
            primary_fs = line_font_sizes[0]
            fit_bh = max_box_height if max_box_height > 0 else sum(line_heights)
            fit_by = box_y

            # Vertically center the text block within the box: compare total
            # content height against the space available between top/bottom
            # padding, and split the slack evenly above/below. When content
            # overflows the box (available < content height), fall back to
            # top-anchored (offset clamped to 0) instead of pushing text
            # above the box.
            bottom_pad = top_pad
            total_content_height = sum(line_heights)
            available_height = fit_bh - top_pad - bottom_pad
            vertical_offset = max(0.0, (available_height - total_content_height) / 2.0)

            ly_top = fit_by + top_pad + vertical_offset

            # Draw text box border matching GoodNotes UI selection bounds
            if textbox_state:
                elements.append(f'<!-- Text Box Border ({html.escape(uuid)}) -->')
                elements.append(
                    f'<rect x="{box_x:.2f}" y="{fit_by:.2f}" width="{bw:.2f}" height="{fit_bh:.2f}" fill="none" stroke="#38BDF8" stroke-width="0.8"/>'
                )

            current_row_top = ly_top
            numbered_counter = 0

            for line_idx, line_items in enumerate(lines):
                has_numbered = any(te.list_type == "numbered" for te, _ in line_items)
                if has_numbered:
                    numbered_counter += 1

                # Center of this line's row. Using dominant-baseline="central"
                # below hands the actual glyph-to-baseline offset to the SVG
                # renderer, which uses the real font metrics -- unlike a fixed
                # 0.75*font-size guess, this centers correctly regardless of
                # whether the text has descenders (e.g. all-caps or digits
                # like "WFH"/"2011" vs lowercase text with "g"/"y"/"p").
                row_center_y = current_row_top + line_heights[line_idx] / 2.0

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
                        'dominant-baseline="central"',
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

                    # Use `bw` (the box's authoritative width, same value used
                    # to draw the box/debug border) rather than this single
                    # TextElement's own te.width. Individual runs within the
                    # same box can report slightly different widths, which
                    # previously caused center/right alignment to drift off
                    # the box's true center by however much that run's width
                    # fell short of the box.
                    line_style_attrs = list(style_attrs)

                    tx = box_x + left_pad
                    if te.alignment == "center":
                        line_style_attrs.append('text-anchor="middle"')
                        if bw > 0:
                            tx = box_x + bw / 2.0
                        else:
                            tx = box_x + left_pad + 50.0
                    elif te.alignment == "right":
                        line_style_attrs.append('text-anchor="end"')
                        if bw > 0:
                            tx = box_x + bw - right_pad
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
                            f'<text x="{tx:.2f}" y="{row_center_y:.2f}" {style_str}>{escaped_text}</text>'
                        )

                current_row_top += line_heights[line_idx]

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