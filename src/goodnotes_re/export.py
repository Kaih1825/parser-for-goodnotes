"""JSON and high-fidelity vector SVG export for GoodNotes documents."""
from __future__ import annotations

import html
import json
import math
from pathlib import Path
from typing import Iterator, Sequence

from .archive import GoodNotesDocument
from .pdf import render_pdf_page_to_svg, resolve_svg_image_masks
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


def _format_font_family_stack(font_family: str | None, sample_text: str = "") -> str:
    """Build a comprehensive CSS font-family fallback stack supporting CJK (Chinese, Japanese, Korean).

    Detects the script of sample_text (Japanese Hiragana/Katakana, Korean Hangul, or Chinese Hanzi)
    and prioritizes the corresponding native system fonts to prevent Cairo from missing glyphs.
    """
    clean = (font_family or "").strip()
    if not clean:
        clean = "sans-serif"

    lower = clean.lower()
    is_serif = any(k in lower for k in ("times", "serif", "georgia", "song", "mincho", "myeongjo", "batang"))
    is_mono = any(k in lower for k in ("courier", "mono", "menlo", "consolas", "gothic coding"))

    # Script detection from sample_text
    has_jp = any(0x3040 <= ord(c) <= 0x30FF or 0x31F0 <= ord(c) <= 0x31FF for c in sample_text) if sample_text else False
    has_kr = any(0xAC00 <= ord(c) <= 0xD7AF or 0x1100 <= ord(c) <= 0x11FF or 0x3130 <= ord(c) <= 0x318F for c in sample_text) if sample_text else False
    has_cjk = any(ord(c) >= 0x2E80 for c in sample_text) if sample_text else False

    # Font definitions by language / script
    tc_sans = ["PingFang TC", "Heiti TC", "Microsoft JhengHei", "Noto Sans CJK TC"]
    sc_sans = ["PingFang SC", "Heiti SC", "Microsoft YaHei", "Noto Sans CJK SC"]
    jp_sans = ["Hiragino Sans", "Hiragino Kaku Gothic ProN", "Yu Gothic", "Meiryo", "Noto Sans JP", "MS Gothic"]
    kr_sans = ["Apple SD Gothic Neo", "Malgun Gothic", "NanumGothic", "Noto Sans KR", "Gulim"]

    tc_serif = ["Songti TC", "STSong", "SimSun", "Noto Serif CJK TC"]
    sc_serif = ["Songti SC", "STSong", "SimSun", "Noto Serif CJK SC"]
    jp_serif = ["Hiragino Mincho ProN", "Yu Mincho", "MS Mincho", "Noto Serif JP"]
    kr_serif = ["Apple Myungjo", "Batang", "NanumMyeongjo", "Noto Serif KR"]

    mono_fonts = ["PingFang TC", "Hiragino Sans", "Apple SD Gothic Neo", "Microsoft JhengHei", "monospace"]

    if is_mono:
        fallbacks = mono_fonts
    elif is_serif:
        if has_jp:
            fallbacks = jp_serif + tc_serif + sc_serif + kr_serif + ["serif"]
        elif has_kr:
            fallbacks = kr_serif + tc_serif + sc_serif + jp_serif + ["serif"]
        else:
            fallbacks = tc_serif + sc_serif + jp_serif + kr_serif + ["serif"]
    else:
        if has_jp:
            fallbacks = jp_sans + tc_sans + sc_sans + kr_sans + ["-apple-system", "BlinkMacSystemFont", "sans-serif"]
        elif has_kr:
            fallbacks = kr_sans + tc_sans + sc_sans + jp_sans + ["-apple-system", "BlinkMacSystemFont", "sans-serif"]
        else:
            fallbacks = tc_sans + sc_sans + jp_sans + kr_sans + ["-apple-system", "BlinkMacSystemFont", "sans-serif"]

    is_known_cjk_font = any(
        k in lower
        for k in (
            "tc", "sc", "hk", "tw", "jp", "kr", "cjk", "pingfang", "songti", "heiti",
            "kaiti", "wawati", "yahei", "jhenghei", "simsun", "simhei", "mingliu",
            "biaukai", "dfkai", "hiragino", "gothic", "mincho", "meiryo", "yu gothic",
            "nanum", "malgun", "apple sd gothic", "batang", "myungjo"
        )
    ) or any(ord(c) >= 0x2E80 for c in clean)

    items: list[str] = []
    if is_known_cjk_font or not has_cjk:
        if clean not in ("sans-serif", "serif", "monospace"):
            items.append(f'"{clean}"' if " " in clean else clean)
        for fb in fallbacks:
            formatted_fb = f'"{fb}"' if " " in fb else fb
            if formatted_fb not in items:
                items.append(formatted_fb)
    else:
        for fb in fallbacks:
            formatted_fb = f'"{fb}"' if " " in fb else fb
            if formatted_fb not in items:
                items.append(formatted_fb)
        if clean not in ("sans-serif", "serif", "monospace"):
            formatted_clean = f'"{clean}"' if " " in clean else clean
            if formatted_clean not in items:
                items.append(formatted_clean)

    return ", ".join(items)


def page_to_svg(
    page: Page,
    document: GoodNotesDocument,
    fill_shapes: bool = True,
    sticky_note_state: str | None = None,
    textbox_state: bool | str | None = False,
    stroke_styles: dict[str, dict[str, object]] | None = None,
    stroke_data_attributes: bool = False,
) -> str:
    """Render a single GoodNotes Page object to an SVG XML string in memory."""
    # GoodNotes internal coordinates are 132 DPI, PDF canvas is 72 DPI
    dpi_scale = 72.0 / 132.0
    pw, ph = page.dimensions.width, page.dimensions.height

    elements: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{pw:.2f}" height="{ph:.2f}" viewBox="0 0 {pw:.2f} {ph:.2f}">',
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
                    page_index=max(0, page.pdf_page_index - 1),
                    width=pw,
                    height=ph,
                    id_prefix=f"background_{page.index}",
                )
                if pdf_svg:
                    elements.append(pdf_svg)
                else:
                    pdf_b64 = base64.b64encode(bdata).decode("ascii")
                    target_p_idx = max(0, page.pdf_page_index - 1)
                    elements.append(
                        f'<g class="gn-pdf-placeholder" data-pdf-b64="{pdf_b64}" data-pdf-page="{target_p_idx}" data-width="{pw:.2f}" data-height="{ph:.2f}"></g>'
                    )
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
                            pdf_b64 = base64.b64encode(idata).decode("ascii")
                            elements.append(
                                f'<g{transform}>'
                                f'<svg x="{crop_x:.2f}" y="{crop_y:.2f}" width="{crop_w:.2f}" height="{crop_h:.2f}" viewBox="0 0 {crop_w:.2f} {crop_h:.2f}" overflow="hidden">'
                                f'<g transform="translate({img_x:.2f},{img_y:.2f})">'
                                f'<g class="gn-pdf-placeholder" data-pdf-b64="{pdf_b64}" data-pdf-page="0" data-width="{orig_w:.2f}" data-height="{orig_h:.2f}"></g>'
                                f'</g>'
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
                            pdf_b64 = base64.b64encode(idata).decode("ascii")
                            elements.append(
                                f'<g{transform_attr}>'
                                f'<svg x="{crop_x:.2f}" y="{crop_y:.2f}" width="{crop_w:.2f}" height="{crop_h:.2f}">'
                                f'<g class="gn-pdf-placeholder" data-pdf-b64="{pdf_b64}" data-pdf-page="0" data-width="{crop_w:.2f}" data-height="{crop_h:.2f}"></g>'
                                f'</svg>'
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

    # Render sticky notes cards and icons
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
                font_stack = _format_font_family_stack("sans-serif")
                elements.append(
                    f'<text x="{tx:.2f}" y="{ty:.2f}" font-family="{html.escape(font_stack)}" font-size="10" fill="#555555" font-weight="500">{html.escape(note.author)}</text>'
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

    stroke_uuids = {s.uuid for s in page.strokes if s.uuid}

    for shape in page.shapes:
        if shape.uuid and shape.uuid in stroke_uuids:
            continue

        if shape.parent_uuid and shape.parent_uuid in sticky_note_map:
            parent_note = sticky_note_map[shape.parent_uuid]
            parent_is_open = state_override if state_override is not None else parent_note.is_open
            if not parent_is_open:
                continue
            pts = tuple((px + parent_note.x, py + parent_note.y) for px, py in shape.points)
            cx = (shape.cx + parent_note.x) if shape.cx is not None else None
            cy = (shape.cy + parent_note.y) if shape.cy is not None else None
        else:
            pts = shape.points
            cx = shape.cx
            cy = shape.cy

        is_polyline = 1 in shape.field_numbers or 2 not in shape.field_numbers or shape.shape_type == "polyline"
        stroke_w = max(0.5, shape.stroke_width * dpi_scale)

        dash_pattern = getattr(shape, "dash_pattern", None)
        dash_attr = ""
        if dash_pattern:
            first_val = dash_pattern[0]
            gap_val = dash_pattern[1] if len(dash_pattern) > 1 else dash_pattern[0]
            if first_val <= 2.5:
                dot_gap = max(stroke_w * 1.5, gap_val * dpi_scale)
                dash_attr = f' stroke-dasharray="0 {dot_gap:.2f}"'
            else:
                dash_len = max(stroke_w * 2.0, first_val * dpi_scale)
                gap_len = max(stroke_w * 1.5, gap_val * dpi_scale)
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
            fill_opacity = getattr(shape, "fill_alpha", getattr(shape, "alpha", 1.0))
            fill_attr = f'fill="{shape.color_hex}" fill-opacity="{fill_opacity:.2f}"'
        else:
            fill_attr = 'fill="none"'

        c_rad = getattr(shape, "corner_radius", 0.0)
        is_dotted = bool(dash_pattern and dash_pattern[0] <= 2.5)
        if marker_attr:
            join_cap_attr = 'stroke-linecap="butt" stroke-linejoin="miter"'
        else:
            join_cap_attr = 'stroke-linecap="round" stroke-linejoin="round"'

        if shape.shape_type == "ellipse" and cx is not None and cy is not None:
            ellipse_cx = cx * dpi_scale
            ellipse_cy = cy * dpi_scale
            rx = (shape.rx or 0.0) * dpi_scale
            ry = (shape.ry or 0.0) * dpi_scale
            elements.append(
                f'<ellipse cx="{ellipse_cx:.2f}" cy="{ellipse_cy:.2f}" rx="{rx:.2f}" ry="{ry:.2f}" stroke="{shape.color_hex}" stroke-opacity="{shape.alpha:.2f}" stroke-width="{stroke_w:.2f}" {join_cap_attr}{dash_attr}{marker_attr} {fill_attr}/>'
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

    for stroke_idx, stroke in enumerate(page.strokes):
        if stroke.uuid in shape_uuids:
            continue

        pts = stroke.points
        outline_polys = stroke.outline_polygons
        parent_note = None

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

        s_style = (stroke_styles.get(stroke.uuid, {}) if stroke_styles and stroke.uuid else {})
        if s_style.get("hidden", False):
            continue
        s_color = str(s_style.get("color", stroke.color_hex))
        s_alpha = float(s_style.get("opacity", stroke.alpha))
        s_highlight = bool(s_style.get("highlight", False))
        data_attr = f' data-stroke-id="{html.escape(stroke.uuid)}"' if (stroke_data_attributes or stroke_styles is not None or stroke.uuid) else ""
        css_class = ' class="gn-stroke"' if data_attr else ""

        dash_pattern = getattr(stroke, "dash_pattern", None)
        if stroke.is_dot and pts:
            # Single point / Dot
            pt = pts[0]
            cx, cy = pt.x * dpi_scale, pt.y * dpi_scale
            r = max(0.12, (stroke.width * pt.pressure * 0.5) * dpi_scale)
            if s_highlight:
                elements.append(
                    f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r * 2.0:.2f}" fill="#fffa65" fill-opacity="0.7" stroke="none"/>'
                )
            elements.append(
                f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="{s_color}" fill-opacity="{s_alpha:.2f}" stroke="none"{css_class}{data_attr}/>'
            )
        elif dash_pattern:
            stroke_w = max(0.5, stroke.width * dpi_scale)
            first_val = dash_pattern[0]
            gap_val = dash_pattern[1] if len(dash_pattern) > 1 else dash_pattern[0]
            if first_val <= 2.5:
                dot_gap = max(stroke_w * 1.5, gap_val * dpi_scale)
                dash_attr = f' stroke-dasharray="0 {dot_gap:.2f}"'
            else:
                dash_len = max(stroke_w * 2.0, first_val * dpi_scale)
                gap_len = max(stroke_w * 1.5, gap_val * dpi_scale)
                dash_attr = f' stroke-dasharray="{dash_len:.2f} {gap_len:.2f}"'
            
            stroke_pts = tuple((pt.x, pt.y) for pt in pts)
            if len(stroke_pts) >= 2:
                d_path = _catmull_rom_to_svg_path(stroke_pts, dpi_scale)
                if s_highlight:
                    elements.append(
                        f'<path d="{d_path}" stroke="#fffa65" stroke-opacity="0.75" stroke-width="{stroke_w * 2.2:.2f}" stroke-linecap="round" stroke-linejoin="round" fill="none"/>'
                    )
                elements.append(
                    f'<path d="{d_path}" stroke="{s_color}" stroke-opacity="{s_alpha:.2f}" stroke-width="{stroke_w:.2f}" stroke-linecap="round" stroke-linejoin="round"{dash_attr} fill="none"{css_class}{data_attr}/>'
                )
        elif getattr(stroke, "native_cgpaths", ()):
            native_cgpaths = stroke.native_cgpaths
            dx = parent_note.x if parent_note else 0.0
            dy = parent_note.y if parent_note else 0.0

            all_path_cmds = []
            for seg_cmds in native_cgpaths:
                cmds = []
                for op, args in seg_cmds:
                    if op == "M":
                        x, y = args[0] + dx, args[1] + dy
                        cmds.append(f"M {x * dpi_scale:.2f} {y * dpi_scale:.2f}")
                    elif op == "C":
                        c1x, c1y = args[0] + dx, args[1] + dy
                        c2x, c2y = args[2] + dx, args[3] + dy
                        p2x, p2y = args[4] + dx, args[5] + dy
                        cmds.append(f"C {c1x * dpi_scale:.2f} {c1y * dpi_scale:.2f}, {c2x * dpi_scale:.2f} {c2y * dpi_scale:.2f}, {p2x * dpi_scale:.2f} {p2y * dpi_scale:.2f}")
                    elif op == "A":
                        cx, cy, r, a0, a1, flag = args
                        cx = cx + dx
                        cy = cy + dy
                        flag_int = int(flag)
                        if flag_int == 1:
                            d_theta = (a0 - a1) % (2 * math.pi)
                            sweep = 0
                        else:
                            d_theta = (a1 - a0) % (2 * math.pi)
                            sweep = 1
                        large_arc = 1 if d_theta > math.pi else 0
                        end_x = cx + r * math.cos(a1)
                        end_y = cy + r * math.sin(a1)
                        r_scaled = r * dpi_scale
                        cmds.append(f"A {r_scaled:.2f} {r_scaled:.2f} 0 {large_arc} {sweep} {end_x * dpi_scale:.2f} {end_y * dpi_scale:.2f}")
                cmds.append("Z")
                all_path_cmds.append(" ".join(cmds))

            d_str = " ".join(all_path_cmds)
            if s_highlight:
                elements.append(
                    f'<path d="{d_str}" fill="#fffa65" fill-opacity="0.75" stroke="#fffa65" stroke-width="4.0" stroke-linecap="round" stroke-linejoin="round"/>'
                )
            elements.append(
                f'<path d="{d_str}" fill="{s_color}" fill-opacity="{s_alpha:.2f}" stroke="none"{css_class}{data_attr}/>'
            )
        elif outline_polys:
            poly_elems = []
            for poly in outline_polys:
                if len(poly) < 3:
                    continue
                pts_str = " ".join(f"{x * dpi_scale:.2f},{y * dpi_scale:.2f}" for x, y in poly)
                poly_elems.append(f'<polygon points="{pts_str}"/>')
            if poly_elems:
                elements.append(
                    f'<g fill="{s_color}" fill-opacity="{s_alpha:.2f}" stroke="{s_color}" stroke-opacity="{s_alpha:.2f}" stroke-width="{0.5 * dpi_scale:.2f}" stroke-linejoin="round"{css_class}{data_attr}>{"".join(poly_elems)}</g>'
                )
        else:
                ribbon_d = build_stroke_ribbon(
                    pts,
                    stroke.width,
                    dpi_scale,
                    tpl_format=stroke.tpl_format,
                    is_cut_start=stroke.is_cut_start,
                    is_cut_end=stroke.is_cut_end,
                    start_cut_vec=stroke.start_cut_vec,
                    end_cut_vec=stroke.end_cut_vec,
                )
                if ribbon_d:
                    if s_highlight:
                        elements.append(
                            f'<path d="{ribbon_d}" fill="#fffa65" fill-opacity="0.75" stroke="#fffa65" stroke-width="4.0" stroke-linecap="round" stroke-linejoin="round"/>'
                        )
                    elements.append(
                        f'<path d="{ribbon_d}" fill="{s_color}" fill-opacity="{s_alpha:.2f}" stroke="none"{css_class}{data_attr}/>'
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
        top_pad = (10.0 * dpi_scale) if is_sticky else (6.0 * dpi_scale)
        left_pad = (10.0 * dpi_scale) if is_sticky else (6.0 * dpi_scale)
        right_pad = (10.0 * dpi_scale) if is_sticky else (6.0 * dpi_scale)

        bw = max_box_width if max_box_width > 0 else 50.0
        primary_fs = line_font_sizes[0]
        fit_bh = max_box_height if max_box_height > 0 else sum(line_heights)
        fit_by = box_y

        # Sticky Note text is top-anchored; regular text boxes remain
        # vertically centered within their available content area.
        bottom_pad = top_pad
        total_content_height = sum(line_heights)
        available_height = fit_bh - top_pad - bottom_pad
        if is_sticky:
            vertical_offset = 0.0
        else:
            vertical_offset = max(0.0, (available_height - total_content_height) / 2.0)

        ly_top = fit_by + top_pad + vertical_offset

        # GoodNotes sticker text is rendered above the sticker artwork with
        # an opaque text-box background. Identify it only when the parsed
        # text box substantially overlaps a parsed image attachment; this
        # keeps ordinary page text and unrelated shapes unchanged.
        text_area = max_box_width * max_box_height
        sticker_text_background = False
        if text_area > 0.0:
            text_left = box_x
            text_top = fit_by
            text_right = text_left + bw
            text_bottom = text_top + fit_bh
            for image in page.image_elements:
                image_left = image.x * dpi_scale
                image_top = image.y * dpi_scale
                image_right = image_left + image.width * dpi_scale
                image_bottom = image_top + image.height * dpi_scale
                overlap_w = max(0.0, min(text_right, image_right) - max(text_left, image_left))
                overlap_h = max(0.0, min(text_bottom, image_bottom) - max(text_top, image_top))
                if overlap_w * overlap_h >= text_area * 0.90:
                    sticker_text_background = True
                    break

        if sticker_text_background:
            # Use the color explicitly stored in the text payload instead of
            # assuming a white sticker background.
            background_color = te_list[0].background_color_hex
            background_alpha = te_list[0].background_alpha
            if background_color is not None and background_alpha > 0.0:
                elements.append(f'<!-- Sticker Text Background ({html.escape(uuid)}) -->')
                elements.append(
                    f'<rect x="{box_x:.2f}" y="{fit_by:.2f}" width="{bw:.2f}" height="{fit_bh:.2f}" '
                    f'fill="{background_color}" fill-opacity="{background_alpha:.3f}"/>'
                )

        # Draw text box border matching GoodNotes UI selection bounds
        is_tb_open = (
            textbox_state is True
            or (isinstance(textbox_state, str) and textbox_state.lower() in ("open", "true", "on", "1"))
        )
        if is_tb_open:
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

                display_text = line_str
                if te.list_type == "bullet" and display_text:
                    display_text = f"• {display_text}"
                elif te.list_type == "numbered" and display_text:
                    display_text = f"{numbered_counter}. {display_text}"

                font_stack = _format_font_family_stack(te.font_family, display_text)
                style_attrs: list[str] = [
                    f'font-family="{html.escape(font_stack)}"',
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
                fallback_font_stack = _format_font_family_stack("sans-serif", frag.text)
                elements.append(
                    f'<text x="50" y="50" font-family="{html.escape(fallback_font_stack)}" font-size="14" fill="#333333"><!-- Fragment: {escaped_text} --></text>'
                )

    elements.append('</svg>\n')
    return '\n'.join(elements)


def write_svg(
    document: GoodNotesDocument,
    directory: str | Path,
    fill_shapes: bool = True,
    sticky_note_state: str | None = None,
    textbox_state: bool | str | None = False,
    parse_all: bool = False,
    export_pdf: bool | str | Path = False,
) -> list[Path]:
    """Export SVG vector pages for each page in the GoodNotes document.

    sticky_note_state: Optional override for sticky notes state ('open' or 'close').
    textbox_state: Optional toggle for drawing text box bounding borders ('open' or 'close').
    export_pdf: Optional flag or path to package exported SVG pages into a single PDF.
    """
    output = Path(directory)
    output.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    try:
        pages = document.pages(parse_all=parse_all)
    except TypeError:
        pages = document.pages()

    for page in pages:
        name = f"page_{page.index + 1}_{page.member_path.replace('/', '_')}.svg"
        target = output / name
        svg_str = page_to_svg(
            page=page,
            document=document,
            fill_shapes=fill_shapes,
            sticky_note_state=sticky_note_state,
            textbox_state=textbox_state,
        )
        target.write_text(svg_str, encoding="utf-8")
        written.append(target)

    if export_pdf:
        if isinstance(export_pdf, (str, Path)) and str(export_pdf) != "True":
            pdf_path = Path(export_pdf)
            if pdf_path.is_dir():
                doc_name = document.path.stem if getattr(document, "path", None) else "document"
                pdf_path = pdf_path / f"{doc_name}.pdf"
        else:
            doc_name = document.path.stem if getattr(document, "path", None) else "document"
            pdf_path = output / f"{doc_name}.pdf"

        svgs_to_pdf(written, pdf_path)
        written.append(pdf_path)

    return written


def _ensure_cairo_loaded() -> None:
    import os
    import sys
    import ctypes.util

    if sys.platform == "darwin":
        orig_find = ctypes.util.find_library
        def _find_library(name: str) -> str | None:
            res = orig_find(name)
            if not res:
                for p in ["/opt/homebrew/lib", "/usr/local/lib", "/opt/local/lib"]:
                    for ext in [".dylib", ".2.dylib", "-2.dylib", ".0.dylib", ".so"]:
                        candidate = os.path.join(p, f"lib{name}{ext}")
                        if os.path.exists(candidate):
                            return candidate
            return res
        ctypes.util.find_library = _find_library


def svg_to_pdf_bytes(svg_data: str | bytes) -> bytes:
    """Convert SVG XML string or bytes to PDF bytes using CairoSVG (with PyMuPDF fallback)."""
    if isinstance(svg_data, bytes):
        try:
            svg_text = svg_data.decode("utf-8")
        except UnicodeDecodeError:
            svg_text = None
    else:
        svg_text = svg_data

    if svg_text is not None and "<mask" in svg_text and "mask=" in svg_text:
        svg_text = resolve_svg_image_masks(svg_text)
        svg_bytes = svg_text.encode("utf-8")
    elif isinstance(svg_data, str):
        svg_bytes = svg_data.encode("utf-8")
    else:
        svg_bytes = svg_data

    try:
        _ensure_cairo_loaded()
        import cairosvg
        return cairosvg.svg2pdf(bytestring=svg_bytes)
    except Exception:
        import fitz
        svg_doc = fitz.open(stream=svg_bytes, filetype="svg")
        pdf_bytes = svg_doc.convert_to_pdf()
        svg_doc.close()
        return pdf_bytes


def svgs_to_pdf(
    svg_sources: Sequence[str | Path | bytes],
    output: str | Path,
) -> Path:
    """Compile multiple SVG files or SVG XML strings/bytes in sequence into a single multi-page PDF using CairoSVG."""
    import fitz

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_doc = fitz.open()

    for item in svg_sources:
        if isinstance(item, Path):
            svg_bytes = item.read_bytes()
        elif isinstance(item, str):
            if item.strip().startswith("<svg") or item.strip().startswith("<?xml"):
                svg_bytes = item.encode("utf-8")
            elif Path(item).is_file():
                svg_bytes = Path(item).read_bytes()
            else:
                svg_bytes = item.encode("utf-8")
        elif isinstance(item, bytes):
            svg_bytes = item
        else:
            raise ValueError(f"Unsupported SVG source type: {type(item)}")

        page_pdf_bytes = svg_to_pdf_bytes(svg_bytes)
        page_doc = fitz.open("pdf", page_pdf_bytes)
        pdf_doc.insert_pdf(page_doc)
        page_doc.close()

    pdf_doc.save(str(output_path))
    pdf_doc.close()
    return output_path


def write_pdf(
    document: GoodNotesDocument,
    output: str | Path,
    fill_shapes: bool = True,
    sticky_note_state: str | None = None,
    textbox_state: bool = False,
    parse_all: bool = False,
) -> Path:
    """Export all document pages to vector SVGs in order and compile into a single multi-page PDF via CairoSVG."""
    import tempfile

    output_path = Path(output)
    if output_path.is_dir() or str(output).endswith(("/", "\\")):
        doc_stem = document.path.stem if getattr(document, "path", None) else "document"
        output_path = output_path / f"{doc_stem}.pdf"
    elif output_path.suffix.lower() != ".pdf":
        output_path = output_path.with_suffix(".pdf")

    with tempfile.TemporaryDirectory() as tmp_dir:
        svg_paths = write_svg(
            document,
            tmp_dir,
            fill_shapes=fill_shapes,
            sticky_note_state=sticky_note_state,
            textbox_state=textbox_state,
            parse_all=parse_all,
            export_pdf=False,
        )
        return svgs_to_pdf(svg_paths, output_path)


def write_audio(
    document: GoodNotesDocument,
    output: str | Path,
    recording_id: str | None = None,
    concat: bool = True,
) -> Path:
    """Extract audio recording(s) from document.

    If recording_id is None and concat is True, concatenates all active recordings in sequence.
    """
    import os
    import shutil
    import subprocess
    import tempfile

    recordings = document.recordings()
    if not recordings:
        raise ValueError("Document contains no audio recordings")

    output_path = Path(output)

    if recording_id:
        target_rec = None
        for r in recordings:
            if r.id == recording_id:
                target_rec = r
                break
        if not target_rec:
            raise ValueError(f"Recording ID '{recording_id}' not found")

        if output_path.is_dir() or str(output).endswith(("/", "\\")):
            output_path = output_path / f"{target_rec.id}.m4a"
        return document.export_audio(target_rec, output_path)

    # If output is a directory and not concat, export each recording
    if (output_path.is_dir() or str(output).endswith(("/", "\\"))) and not concat:
        output_path.mkdir(parents=True, exist_ok=True)
        for r in recordings:
            document.export_audio(r, output_path / f"{r.id}.m4a")
        return output_path

    # If only 1 recording or concat=False with file output
    if len(recordings) == 1 or not concat:
        if output_path.is_dir() or str(output).endswith(("/", "\\")):
            output_path = output_path / f"{recordings[0].id}.m4a"
        return document.export_audio(recordings[0], output_path)

    # Concat all recordings via ffmpeg
    if not shutil.which("ffmpeg"):
        # Fallback to exporting first recording if ffmpeg not available
        if output_path.is_dir() or str(output).endswith(("/", "\\")):
            output_path = output_path / f"{recordings[0].id}.m4a"
        return document.export_audio(recordings[0], output_path)

    if output_path.is_dir() or str(output).endswith(("/", "\\")):
        doc_stem = document.path.stem if getattr(document, "path", None) else "document"
        output_path = output_path / f"{doc_stem}_audio_all.m4a"
    elif output_path.suffix.lower() not in (".m4a", ".mp4", ".aac"):
        output_path = output_path.with_suffix(".m4a")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    audio_tmps = []
    try:
        for r in recordings:
            f = tempfile.NamedTemporaryFile(suffix=".m4a", delete=False)
            f.write(document.read_audio(r))
            f.close()
            audio_tmps.append(f.name)

        cmd_concat = ["ffmpeg", "-y"]
        for a in audio_tmps:
            cmd_concat.extend(["-i", a])
        filter_str = "".join(f"[{i}:a]" for i in range(len(audio_tmps))) + f"concat=n={len(audio_tmps)}:v=0:a=1[outa]"
        cmd_concat.extend(["-filter_complex", filter_str, "-map", "[outa]", "-c:a", "aac", str(output_path)])
        subprocess.check_call(cmd_concat, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finally:
        for a in audio_tmps:
            if os.path.exists(a):
                os.unlink(a)

    return output_path


def write_recording_video(
    document: GoodNotesDocument,
    output: str | Path,
    recording_id: str | None = None,
    page_index: int | None = None,
    fps: int = 15,
    resolution_scale: float = 2.0,
    dim_future: bool = True,
    highlight_duration: float = 1.2,
    fill_shapes: bool = True,
    sticky_note_state: str | None = None,
    textbox_state: bool | str | None = False,
    parse_all: bool = False,
) -> Path:
    """Export synchronized MP4 video matching recorded audio with handwritten strokes.

    If recording_id is None, plays and concatenates all active recording sessions in sequence!
    """
    import os
    import shutil
    import subprocess
    import tempfile

    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required for video export but was not found on PATH")

    all_recordings = document.recordings()
    if not all_recordings:
        raise ValueError("Document contains no audio recordings")

    target_recordings: list[Recording] = []
    if recording_id:
        found = next((r for r in all_recordings if r.id == recording_id), None)
        if not found:
            raise ValueError(f"Recording ID '{recording_id}' not found")
        target_recordings = [found]
    else:
        target_recordings = list(all_recordings)

    # Extract pages
    try:
        pages = document.pages(parse_all=parse_all)
    except TypeError:
        pages = document.pages()

    if not pages:
        raise ValueError("Document contains no pages")

    page_map = {p.uuid[:32]: p for p in pages}

    output_path = Path(output)
    if output_path.is_dir() or str(output).endswith(("/", "\\")):
        doc_stem = document.path.stem if getattr(document, "path", None) else "document"
        suffix_name = target_recordings[0].id[:8] if len(target_recordings) == 1 else "all_recordings"
        output_path = output_path / f"{doc_stem}_{suffix_name}.mp4"
    elif output_path.suffix.lower() != ".mp4":
        output_path = output_path.with_suffix(".mp4")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Dump and probe each audio file
    audio_tmps: list[str] = []
    durations: list[float] = []
    for r in target_recordings:
        f = tempfile.NamedTemporaryFile(suffix=".m4a", delete=False)
        f.write(document.read_audio(r))
        f.close()
        audio_tmps.append(f.name)

        dur = r.duration
        if shutil.which("ffprobe"):
            try:
                cmd_dur = [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    f.name,
                ]
                dur_str = subprocess.check_output(cmd_dur).decode().strip()
                if dur_str:
                    dur = max(dur, float(dur_str))
            except Exception:
                pass
        durations.append(max(0.5, dur))

    # Build concatenated audio file if multiple recordings
    combined_audio_tmp: str = ""
    try:
        if len(audio_tmps) == 1:
            combined_audio_tmp = audio_tmps[0]
        else:
            concat_f = tempfile.NamedTemporaryFile(suffix=".m4a", delete=False)
            concat_f.close()
            combined_audio_tmp = concat_f.name

            cmd_concat = ["ffmpeg", "-y"]
            for a in audio_tmps:
                cmd_concat.extend(["-i", a])
            filter_str = "".join(f"[{i}:a]" for i in range(len(audio_tmps))) + f"concat=n={len(audio_tmps)}:v=0:a=1[outa]"
            cmd_concat.extend(["-filter_complex", filter_str, "-map", "[outa]", "-c:a", "aac", combined_audio_tmp])
            subprocess.check_call(cmd_concat, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        has_rsvg = bool(shutil.which("rsvg-convert"))

        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-f", "image2pipe",
            "-vcodec", "png",
            "-r", str(fps),
            "-i", "-",
            "-i", combined_audio_tmp,
            "-vf", f"scale=iw*{resolution_scale}:ih*{resolution_scale}:flags=lanczos,pad=ceil(iw/2)*2:ceil(ih/2)*2",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-shortest",
            str(output_path),
        ]

        proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

        # Collect stroke UUIDs by recording for inter-recording visibility tracking
        rec_stroke_sets = [set(t.stroke_uuid for t in r.stroke_timings) for r in target_recordings]

        for rec_idx, r in enumerate(target_recordings):
            dur = durations[rec_idx]
            num_frames = max(1, int(math.ceil(dur * fps)))
            timings = {t.stroke_uuid: t.timestamp for t in r.stroke_timings}

            prior_strokes = set().union(*rec_stroke_sets[:rec_idx]) if rec_idx > 0 else set()
            future_strokes = set().union(*rec_stroke_sets[rec_idx+1:]) if rec_idx + 1 < len(target_recordings) else set()

            for f_idx in range(num_frames):
                t = f_idx / fps
                stroke_styles: dict[str, dict[str, object]] = {}

                # Determine active page at time t
                if page_index is not None and 0 <= page_index < len(pages):
                    target_page = pages[page_index]
                else:
                    active_puuid = None
                    for timing in r.stroke_timings:
                        if timing.timestamp <= t:
                            active_puuid = timing.page_uuid[:32]
                        else:
                            break
                    if not active_puuid and r.stroke_timings:
                        active_puuid = r.stroke_timings[0].page_uuid[:32]
                    elif not active_puuid and r.page_uuids:
                        active_puuid = r.page_uuids[0][:32]

                    target_page = page_map.get(active_puuid, pages[0]) if active_puuid else pages[0]

                # Prior recordings' strokes are completed and fully visible
                for s in prior_strokes:
                    stroke_styles[s] = {"opacity": 1.0, "highlight": False}

                # Future recordings' strokes are dimmed/hidden
                for s in future_strokes:
                    stroke_styles[s] = {"opacity": 0.15 if dim_future else 0.0, "hidden": not dim_future}

                # Current recording's strokes
                for suuid, stime in timings.items():
                    if t < stime:
                        stroke_styles[suuid] = {"opacity": 0.15 if dim_future else 0.0, "hidden": not dim_future}
                    elif stime <= t <= stime + highlight_duration:
                        stroke_styles[suuid] = {"opacity": 1.0, "highlight": True}
                    else:
                        stroke_styles[suuid] = {"opacity": 1.0, "highlight": False}

                svg_text = page_to_svg(
                    target_page,
                    document,
                    fill_shapes=fill_shapes,
                    sticky_note_state=sticky_note_state,
                    textbox_state=textbox_state,
                    stroke_styles=stroke_styles,
                )

                if has_rsvg:
                    rsvg_proc = subprocess.Popen(
                        ["rsvg-convert", "-f", "png"],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                    )
                    png_bytes, _ = rsvg_proc.communicate(input=svg_text.encode("utf-8"))
                else:
                    try:
                        import fitz
                        doc_fitz = fitz.open(stream=svg_text.encode("utf-8"), filetype="svg")
                        pix = doc_fitz[0].get_pixmap(dpi=int(72 * resolution_scale))
                        png_bytes = pix.tobytes("png")
                        doc_fitz.close()
                    except Exception:
                        _ensure_cairo_loaded()
                        import cairosvg
                        png_bytes = cairosvg.svg2png(bytestring=svg_text.encode("utf-8"), scale=resolution_scale)

                proc.stdin.write(png_bytes)

        if proc.stdin:
            proc.stdin.close()
        stderr = proc.stderr.read() if proc.stderr else b""
        proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg encoding failed with code {proc.returncode}: {stderr.decode(errors='ignore')}")

    finally:
        for a in audio_tmps:
            if os.path.exists(a):
                os.unlink(a)
        if combined_audio_tmp and combined_audio_tmp not in audio_tmps and os.path.exists(combined_audio_tmp):
            os.unlink(combined_audio_tmp)

    return output_path


def write_recording_html(
    document: GoodNotesDocument,
    output: str | Path,
    recording_id: str | None = None,
    page_index: int | None = None,
    fill_shapes: bool = True,
    sticky_note_state: str | None = None,
    textbox_state: bool | str | None = False,
    parse_all: bool = True,
) -> Path:
    """Export standalone interactive HTML5 player for playback with synchronized handwriting highlight."""
    all_recordings = document.recordings()
    if not all_recordings:
        raise ValueError("Document contains no audio recordings")

    target_recordings: list[Recording] = []
    if recording_id:
        found = next((r for r in all_recordings if r.id == recording_id), None)
        if not found:
            raise ValueError(f"Recording ID '{recording_id}' not found")
        target_recordings = [found]
    else:
        target_recordings = list(all_recordings)

    try:
        pages = document.pages(parse_all=parse_all)
    except TypeError:
        pages = document.pages()

    if not pages:
        raise ValueError("Document contains no pages")

    def match_page_uuid(page_uuid_str):
        if not page_uuid_str:
            return None
        clean = page_uuid_str.replace("-", "").lower()
        for idx, p in enumerate(pages):
            p_clean = p.uuid.replace("-", "").lower()
            if p_clean == clean or (len(p_clean) >= 28 and len(clean) >= 28 and p_clean[:28] == clean[:28]):
                return idx
        return None

    output_path = Path(output)
    if output_path.is_dir() or str(output).endswith(("/", "\\")):
        doc_stem = document.path.stem if getattr(document, "path", None) else "document"
        suffix_name = target_recordings[0].id[:8] if len(target_recordings) == 1 else "all_recordings"
        output_path = output_path / f"{doc_stem}_{suffix_name}.html"
    elif output_path.suffix.lower() != ".html":
        output_path = output_path.with_suffix(".html")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Render SVGs for all pages
    page_svgs: dict[int, str] = {}
    for p_idx, p in enumerate(pages):
        page_svgs[p_idx] = page_to_svg(
            p,
            document,
            fill_shapes=fill_shapes,
            sticky_note_state=sticky_note_state,
            textbox_state=textbox_state,
            stroke_data_attributes=True,
        )

    # Prepare recordings data structure
    recordings_data = []
    for r_idx, r in enumerate(target_recordings):
        audio_b64 = base64.b64encode(document.read_audio(r)).decode("ascii")
        p_idx = 0
        if page_index is not None and 0 <= page_index < len(pages):
            p_idx = page_index
        elif r.page_uuids:
            matched = match_page_uuid(r.page_uuids[0])
            if matched is not None:
                p_idx = matched

        # Each stroke timing has timestamp and resolved page index (-1 if deleted/unmapped)
        timings = {}
        for t in r.stroke_timings:
            st_pidx = match_page_uuid(t.page_uuid)
            if st_pidx is None:
                st_pidx = -1
            timings[t.stroke_uuid] = {
                "t": round(t.timestamp, 4),
                "page_index": st_pidx,
            }

        recordings_data.append({
            "id": r.id,
            "duration": round(r.duration, 4),
            "page_index": p_idx,
            "stroke_timings": timings,
            "audio_b64": audio_b64,
        })

    recordings_json = json.dumps(recordings_data)
    page_svgs_json = json.dumps(page_svgs)

    doc_title = html.escape(document.path.name if getattr(document, "path", None) else "GoodNotes Audio Note")
    total_dur = sum(r["duration"] for r in recordings_data)
    dur_min = int(total_dur // 60)
    dur_sec = int(total_dur % 60)
    dur_display = f"{dur_min:02d}:{dur_sec:02d}"

    template = _load_player_template()

    rec_options_html = "".join(
        f'<option value="{idx}">段落 {idx+1} ({r["id"][:8]}... {int(r["duration"]//60):02d}:{int(r["duration"]%60):02d})</option>'
        for idx, r in enumerate(recordings_data)
    )
    page_options_html = "".join(
        f'<option value="{idx}">第 {idx+1} 頁 / 共 {len(pages)} 頁</option>'
        for idx in range(len(pages))
    )

    rendered_html = (
        template
        .replace("__DOC_TITLE__", doc_title)
        .replace("__RECORDINGS_COUNT__", str(len(recordings_data)))
        .replace("__TOTAL_PAGES__", str(len(pages)))
        .replace("__TOTAL_DURATION__", str(total_dur))
        .replace("__DUR_DISPLAY__", dur_display)
        .replace("__RECORDINGS_OPTIONS__", rec_options_html)
        .replace("__PAGE_OPTIONS__", page_options_html)
        .replace("__RECORDINGS_JSON__", recordings_json)
        .replace("__PAGE_SVGS_JSON__", page_svgs_json)
    )

    output_path.write_text(rendered_html, encoding="utf-8")
    return output_path


def _load_player_template() -> str:
    """Load the standalone HTML player template."""
    try:
        from importlib.resources import files
        return files("goodnotes_re").joinpath("templates/player_template.html").read_text(encoding="utf-8")
    except Exception:
        tpl_file = Path(__file__).parent / "templates" / "player_template.html"
        return tpl_file.read_text(encoding="utf-8")