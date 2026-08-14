"""Decoder and representation for GoodNotes stroke ink (LZ4 + TPL + Protobuf Trailer)."""
from __future__ import annotations

from dataclasses import dataclass
import math
import struct
from typing import Sequence

from .compression import CompressionError, decode_apple_lz4
from .tpl import TplDecodeError, TplImage, decode_tpl
from .wire import DecodeError, Message, decode_message


def uint32_to_float32(u: int) -> float:
    """Convert a 32-bit unsigned integer to an IEEE 754 float32."""
    return struct.unpack("<f", struct.pack("<I", u & 0xFFFFFFFF))[0]


@dataclass(frozen=True)
class StrokePoint:
    x: float
    y: float
    pressure: float = 1.0


@dataclass(frozen=True)
class Stroke:
    uuid: str
    points: tuple[StrokePoint, ...]
    color_hex: str
    alpha: float
    width: float
    is_dot: bool
    is_highlighter: bool
    tpl_format: str
    ribbon_path: str | None = None
    outline_polygons: tuple[tuple[tuple[float, float], ...], ...] = ()
    is_cut_start: bool = False
    is_cut_end: bool = False
    parent_uuid: str | None = None
    dash_pattern: tuple[float, ...] | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "uuid": self.uuid,
            "points": [{"x": p.x, "y": p.y, "pressure": p.pressure} for p in self.points],
            "color_hex": self.color_hex,
            "alpha": self.alpha,
            "width": self.width,
            "is_dot": self.is_dot,
            "is_highlighter": self.is_highlighter,
            "tpl_format": self.tpl_format,
            "parent_uuid": self.parent_uuid,
        }


def extract_color_from_trailer(trailer_bytes: bytes) -> tuple[str, float]:
    """Decode stroke RGBA color from the protobuf message trailer following 'bv4$'."""
    if not trailer_bytes:
        return "#000000", 1.0
    try:
        msg = decode_message(trailer_bytes)
        for field in msg.fields:
            if field.number == 4 and isinstance(field.value, bytes):
                color_msg = decode_message(field.value)
                f1 = color_msg.by_number(1)
                f2 = color_msg.by_number(2)
                f3 = color_msg.by_number(3)
                f4 = color_msg.by_number(4)
                r_val = f1[0].fixed_float() if f1 else 0.0
                g_val = f2[0].fixed_float() if f2 else 0.0
                b_val = f3[0].fixed_float() if f3 else 0.0
                a_val = f4[0].fixed_float() if f4 else 1.0
                if r_val is None: r_val = 0.0
                if g_val is None: g_val = 0.0
                if b_val is None: b_val = 0.0
                if a_val is None: a_val = 1.0
                r_int = min(255, max(0, int(round(r_val * 255.0))))
                g_int = min(255, max(0, int(round(g_val * 255.0))))
                b_int = min(255, max(0, int(round(b_val * 255.0))))
                return f"#{r_int:02x}{g_int:02x}{b_int:02x}", a_val
    except (DecodeError, ValueError, struct.error):
        pass
    return "#000000", 1.0


def extract_move_offset_from_trailer(trailer_bytes: bytes) -> tuple[float, float]:
    """Decode the (dx, dy) translation GoodNotes attaches to a stroke's trailer
    (protobuf field 6, two fixed32 floats) after it has been repositioned with
    the lasso/selection tool. The underlying TPL point data is left untouched
    at its original, pre-move coordinates; this offset must be added to every
    point to get the stroke's actual on-page position. Strokes that have never
    been moved simply omit this field, so (0.0, 0.0) is returned for them.
    """
    if not trailer_bytes:
        return 0.0, 0.0
    try:
        msg = decode_message(trailer_bytes)
        for field in msg.fields:
            if field.number == 6 and isinstance(field.value, bytes) and field.value:
                offset_msg = decode_message(field.value)
                f1 = offset_msg.by_number(1)
                f2 = offset_msg.by_number(2)
                dx = f1[0].fixed_float() if f1 else None
                dy = f2[0].fixed_float() if f2 else None
                return dx or 0.0, dy or 0.0
    except (DecodeError, ValueError, struct.error):
        pass
    return 0.0, 0.0


def _top_level_tokens(format_string: str) -> list[str]:
    tokens = []
    i = 0
    while i < len(format_string):
        char = format_string[i]
        if char in "AS":
            # Consume everything until matching parenthesis
            start = i
            i += 1
            if i < len(format_string) and format_string[i] == "(":
                i += 1
                depth = 1
                while i < len(format_string) and depth > 0:
                    if format_string[i] == "(":
                        depth += 1
                    elif format_string[i] == ")":
                        depth -= 1
                    i += 1
                tokens.append(format_string[start:i])
            else:
                tokens.append(char)
        else:
            tokens.append(char)
            i += 1
    return tokens


def is_valid_coord(val: float) -> bool:
    if not (-5000.0 <= val <= 5000.0):
        return False
    if 0.0 < abs(val) < 1e-6:
        return False
    return True


def is_valid_pressure(p: float) -> bool:
    return 0.01 <= p <= 10.0


def _path_jitter_ratio(points: Sequence[StrokePoint]) -> float:
    """Fraction of consecutive segments whose direction sharply reverses.

    Real ink advances roughly forward even through loops and cursive turns;
    an array that happens to satisfy the coordinate/pressure range checks but
    actually holds something else (e.g. per-point tangent/heading metadata
    instead of the path itself) tends to double back on almost every step.
    Calibrated against real GoodNotes strokes: normal ink stays under ~0.25
    even at the 99th percentile, while a misidentified metadata array scores
    close to 1.0.
    """
    if len(points) < 3:
        return 0.0
    reversals = 0
    segments = 0
    prev_dx = points[1].x - points[0].x
    prev_dy = points[1].y - points[0].y
    for i in range(1, len(points) - 1):
        dx = points[i + 1].x - points[i].x
        dy = points[i + 1].y - points[i].y
        prev_len = math.hypot(prev_dx, prev_dy)
        cur_len = math.hypot(dx, dy)
        if prev_len > 1e-6 and cur_len > 1e-6:
            cos_angle = (prev_dx * dx + prev_dy * dy) / (prev_len * cur_len)
            segments += 1
            if cos_angle < -0.3:
                reversals += 1
        prev_dx, prev_dy = dx, dy
    return reversals / segments if segments else 0.0


_JITTER_REJECT_THRESHOLD = 0.35



def extract_points_from_tpl(tpl_img: TplImage) -> tuple[list[list[StrokePoint]], float]:
    """Extract stroke points grouped by underlying arrays, and default width."""
    fmt = tpl_img.format
    groups: list[list[StrokePoint]] = []
    default_width = 1.0

    # default_width is only interpreted from top-level integer values.
    # Note: vA(v)A(u)A(u)... format (GN6 new format) values are all coordinate arrays,
    # where list[1] is the y-coordinate and cannot be used as width.
    # vuA(v)A(S(uu))A(S(uuuu))vA(f) format has values[1] = width float.
    _width_from_list = "A(S(" in fmt  # Only legacy schemas store width in list[1]
    for val in tpl_img.values:
        if isinstance(val, int):
            w = uint32_to_float32(val)
            if 0.05 <= w <= 100.0:
                default_width = w
                break
        elif _width_from_list and isinstance(val, list) and len(val) > 1 and isinstance(val[1], int):
            w = uint32_to_float32(val[1])
            if 0.05 <= w <= 100.0:
                default_width = w
                break

    default_radius = default_width / 2.0
    candidates: list[tuple[bool, int, int, list[StrokePoint]]] = []

    # 1. Schema 1: vuA(v)A(S(uu))A(S(uuuu))vA(f) (4-tuple (x1, y1, x2, y2))
    # Strictly match Schema 1 tag to prevent intercepting other formats by mistake.
    #
    # Fix note: Previously only "A(S(uuuu))" in fmt was checked, but that was a position-agnostic
    # substring search. The compound pencil format (vuA(v)A(S(uuuuu))A(S(uuuuuuuuuuu))...
    # ...A(S(uuuu))A(u)) happened to contain the exact same "A(S(uuuu))" token in its trailing
    # section (corresponding to values[8]), incorrectly triggering this branch while still hardcoding
    # reading of values[4] — which in that format is actually Schema 2's 11-tuple
    # array (A(S(uuuuuuuuuuu))), not a 4-tuple. The 4-tuple fields were misparsed as x1,y1,x2,y2,
    # and pressure was overwritten by default_radius, causing jagged strokes and incorrect pressure/width.
    #
    # Re-adding "A(S(uuuuuuuuuuu" not in fmt exclusion allows compound formats containing 11-tuples
    # to fall into the correct Schema 2 branch below.
    if "A(S(uuuu))" in fmt and "A(S(uuuuuuuuuuu" not in fmt:
        if len(tpl_img.values) > 4 and isinstance(tpl_img.values[4], list) and len(tpl_img.values[4]) > 0:
            vis_flags = (tpl_img.values[2]
                         if len(tpl_img.values) > 2 and isinstance(tpl_img.values[2], list)
                         else [])

            # Strictly validate whether vis_flags is valid pen up/down flags (should be all 0 or 1)
            is_valid_vis = isinstance(vis_flags, list) and all(isinstance(x, int) and x in (0, 1) for x in vis_flags)

            g: list[StrokePoint] = []
            seg_idx = 0

            if len(tpl_img.values) > 3 and isinstance(tpl_img.values[3], list):
                for pair in tpl_img.values[3]:
                    if isinstance(pair, (tuple, list)) and len(pair) >= 2:
                        x0, y0 = uint32_to_float32(pair[0]), uint32_to_float32(pair[1])
                        if is_valid_coord(x0) and is_valid_coord(y0):
                            if not g or math.hypot(x0 - g[-1].x, y0 - g[-1].y) >= 1e-3:
                                g.append(StrokePoint(x0, y0, default_radius))

            for quad in tpl_img.values[4]:
                seg_idx += 1
                if not (isinstance(quad, (tuple, list)) and len(quad) >= 4):
                    continue
                # Only cut when vis_flags is valid and its value is 0
                if is_valid_vis and seg_idx < len(vis_flags) and vis_flags[seg_idx] == 0 and g:
                    if len(g) >= 1:
                        groups.append(g)
                    g = []
                x1, y1 = uint32_to_float32(quad[0]), uint32_to_float32(quad[1])
                x2, y2 = uint32_to_float32(quad[2]), uint32_to_float32(quad[3])
                if is_valid_coord(x1) and is_valid_coord(y1):
                    if not g or math.hypot(x1 - g[-1].x, y1 - g[-1].y) >= 1e-3:
                        g.append(StrokePoint(x1, y1, default_radius))
                if is_valid_coord(x2) and is_valid_coord(y2):
                    if not g or math.hypot(x2 - g[-1].x, y2 - g[-1].y) >= 1e-3:
                        g.append(StrokePoint(x2, y2, default_radius))

            if g:
                groups.append(g)

            # Ensure extracted point groups contain at least 2 points before returning, otherwise fall back to candidates parsing
            valid_groups = [gr for gr in groups if len(gr) >= 2]
            if valid_groups:
                return valid_groups, default_width

        if len(tpl_img.values) > 3 and isinstance(tpl_img.values[3], list) and len(tpl_img.values[3]) > 0:
            g = []
            for pair in tpl_img.values[3]:
                if isinstance(pair, (tuple, list)) and len(pair) >= 2:
                    x, y = uint32_to_float32(pair[0]), uint32_to_float32(pair[1])
                    if is_valid_coord(x) and is_valid_coord(y):
                        if not g or math.hypot(x - g[-1].x, y - g[-1].y) >= 1e-3:
                            g.append(StrokePoint(x, y, default_radius))
            if len(g) >= 2:
                groups.append(g)
                return groups, default_width

    # 2. Schema 2: vuA(v)A(S(uuuuu))A(S(uuuuuuuuuuu))... (11-tuple)
    if "A(S(uuuuuuuuuuu" in fmt:
        if len(tpl_img.values) > 4 and isinstance(tpl_img.values[4], list) and len(tpl_img.values[4]) > 0:
            g = []
            if len(tpl_img.values) > 3 and isinstance(tpl_img.values[3], list) and len(tpl_img.values[3]) > 0:
                for p5 in tpl_img.values[3]:
                    if isinstance(p5, (tuple, list)) and len(p5) >= 5:
                        x0, y0, raw_p0 = uint32_to_float32(p5[0]), uint32_to_float32(p5[1]), uint32_to_float32(p5[4])
                        p0 = raw_p0 if is_valid_pressure(raw_p0) else default_radius
                        if is_valid_coord(x0) and is_valid_coord(y0):
                            if not g or math.hypot(x0 - g[-1].x, y0 - g[-1].y) >= 1e-3:
                                g.append(StrokePoint(x0, y0, p0))
            for p11 in tpl_img.values[4]:
                if isinstance(p11, (tuple, list)) and len(p11) >= 11:
                    x1, y1, raw_p1 = uint32_to_float32(p11[1]), uint32_to_float32(p11[2]), uint32_to_float32(p11[5])
                    x2, y2, raw_p2 = uint32_to_float32(p11[6]), uint32_to_float32(p11[7]), uint32_to_float32(p11[10])
                    p1 = raw_p1 if is_valid_pressure(raw_p1) else default_radius
                    p2 = raw_p2 if is_valid_pressure(raw_p2) else default_radius
                    if is_valid_coord(x1) and is_valid_coord(y1):
                        if not g or math.hypot(x1 - g[-1].x, y1 - g[-1].y) >= 1e-3:
                            g.append(StrokePoint(x1, y1, p1))
                    if is_valid_coord(x2) and is_valid_coord(y2):
                        if not g or math.hypot(x2 - g[-1].x, y2 - g[-1].y) >= 1e-3:
                            g.append(StrokePoint(x2, y2, p2))
            if len(g) >= 2:
                groups.append(g)
                return groups, default_width

    # 3. Candidate point-array format matching (a) 6-float, (b) 3-float, (c) 5-float, (d) 2-float
    # (a) 6-float -> Take the midpoint of left/right boundary points as stroke center coordinate (resolves spring jitter)
    for idx, v in enumerate(tpl_img.values):
        if isinstance(v, list) and len(v) >= 12 and isinstance(v[0], (int, float)) and len(v) % 6 == 0:
            parsed: list[StrokePoint] = []
            ok = True
            for k in range(0, len(v), 6):
                x1, y1 = uint32_to_float32(v[k]), uint32_to_float32(v[k + 1])
                x2, y2 = uint32_to_float32(v[k + 2]), uint32_to_float32(v[k + 3])
                p1, p2 = uint32_to_float32(v[k + 4]), uint32_to_float32(v[k + 5])
                if not (is_valid_coord(x1) and is_valid_coord(y1) and is_valid_coord(x2) and is_valid_coord(y2)):
                    ok = False; break
                if not (is_valid_pressure(p1) and is_valid_pressure(p2)):
                    ok = False; break
                
                cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
                cp = (p1 + p2) / 2.0
                if not parsed or math.hypot(cx - parsed[-1].x, cy - parsed[-1].y) >= 1e-3:
                    parsed.append(StrokePoint(cx, cy, cp))
            if ok and len(parsed) >= 1:
                candidates.append((True, len(parsed), idx, parsed))

    # (b) 3-float 3-tuple (x, y, p)
    for idx, v in enumerate(tpl_img.values):
        if isinstance(v, list) and len(v) >= 3 and isinstance(v[0], (int, float)) and len(v) % 3 == 0:
            parsed = []
            ok = True
            for k in range(0, len(v), 3):
                x, y, p = uint32_to_float32(v[k]), uint32_to_float32(v[k + 1]), uint32_to_float32(v[k + 2])
                if not (is_valid_coord(x) and is_valid_coord(y) and is_valid_pressure(p)):
                    ok = False; break
                if not parsed or math.hypot(x - parsed[-1].x, y - parsed[-1].y) >= 1e-3:
                    parsed.append(StrokePoint(x, y, p))
            if ok and len(parsed) >= 1:
                candidates.append((True, len(parsed), idx, parsed))

    # (c) 5-float 5-tuple (x, y, p, w, angle)
    for idx, v in enumerate(tpl_img.values):
        if isinstance(v, list) and len(v) >= 5 and isinstance(v[0], (int, float)) and len(v) % 5 == 0:
            parsed = []
            ok = True
            for k in range(0, len(v), 5):
                x, y, p = uint32_to_float32(v[k]), uint32_to_float32(v[k + 1]), uint32_to_float32(v[k + 2])
                if not (is_valid_coord(x) and is_valid_coord(y) and is_valid_pressure(p)):
                    ok = False; break
                if not parsed or math.hypot(x - parsed[-1].x, y - parsed[-1].y) >= 1e-3:
                    parsed.append(StrokePoint(x, y, p))
            if ok and len(parsed) >= 1:
                candidates.append((True, len(parsed), idx, parsed))

    # (d) 2-float 2-tuple (x, y) - limit idx <= 5 to avoid misidentifying metadata list (values[8]) as point array
    for idx, v in enumerate(tpl_img.values):
        if idx <= 5 and isinstance(v, list) and len(v) >= 2 and isinstance(v[0], (int, float)) and len(v) % 2 == 0:
            parsed = []
            ok = True
            for k in range(0, len(v), 2):
                x, y = uint32_to_float32(v[k]), uint32_to_float32(v[k + 1])
                if not (is_valid_coord(x) and is_valid_coord(y)):
                    ok = False
                    break
                if not parsed or math.hypot(x - parsed[-1].x, y - parsed[-1].y) >= 1e-3:
                    parsed.append(StrokePoint(x, y, default_radius))
            if ok and len(parsed) >= 1:
                candidates.append((False, len(parsed), idx, parsed))

    # (e) 4-tuple array (x1, y1, x2, y2) -> specifically for Pencil Strokes compound format
    if "A(S(uuuuuuuuuuu" in fmt:
        for idx, v in enumerate(tpl_img.values):
            if idx >= 6 and isinstance(v, list) and len(v) >= 1 and isinstance(v[0], tuple) and len(v[0]) == 4:
                parsed = []
                ok = True
                for t in v:
                    if not isinstance(t, tuple) or len(t) < 4:
                        ok = False
                        break
                    x1, y1 = uint32_to_float32(t[0]), uint32_to_float32(t[1])
                    x2, y2 = uint32_to_float32(t[2]), uint32_to_float32(t[3])
                    if not (is_valid_coord(x1) and is_valid_coord(y1) and is_valid_coord(x2) and is_valid_coord(y2)):
                        ok = False
                        break
                    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
                    if not parsed or math.hypot(cx - parsed[-1].x, cy - parsed[-1].y) >= 1e-3:
                        parsed.append(StrokePoint(cx, cy, default_radius))
                if ok and len(parsed) >= 1:
                    candidates.append((False, len(parsed), idx, parsed))

    if candidates:
        # Filter strokes with 2 or more points to eliminate 1-point metadata noise
        multi_point = [c for c in candidates if c[1] >= 2]
        pool = multi_point if multi_point else candidates
        
        # Priority order for sorting:
        # 1. -int(has_p): Prefer dynamic pressure sensitivity (restores dynamic thickness for shape2)
        # 2. _path_jitter_ratio: Smoothness
        # 3. -length: Point count length
        scored = [(-int(has_p), _path_jitter_ratio(pts), -length, idx, pts) for has_p, length, idx, pts in pool]
        scored.sort()
        
        plausible = [c for c in scored if c[1] <= 0.85]
        best_pts = (plausible[0] if plausible else scored[0])[4]
        
        normal_pts = [p for p in best_pts if not (p.x < 10.0 and p.y < 10.0)]
        target_pts = normal_pts if len(normal_pts) >= 1 else best_pts

        groups.append(target_pts)
        return groups, default_width

    return groups, default_width


def _convex_hull(points: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    """Andrew's monotone chain convex hull. Pure-python, no deps."""
    pts = sorted(set(points))
    if len(pts) <= 2:
        return list(pts)

    def cross(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[tuple[float, float]] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper: list[tuple[float, float]] = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _v9_polygon_to_hull_panels(
    poly: Sequence[tuple[float, float]],
    window: int = 16,
    stride: int = 4,
) -> list[list[tuple[float, float]]]:
    """將 v9 原生網格的一段連續點列，重建為一串局部凸包 (convex hull) 面板。

    實測逆向 v9_debug.html 發現：陣列裡的點並非「外框走訪順序」，而是
    每 6 個點一組，代表沿筆劃前進方向某個橫截面的左右兩側取樣點；在
    筆劃收筆變尖或彎曲劇烈處，這個 6 點分組並不總是乾淨對齊（例如
    收尖處的密集三角扇），曾經嘗試過的「明確切左右邊、組成四邊形」
    作法在這些地方仍會留下沒填滿的縫隙。

    改用更穩健、不依賴分組是否對齊的作法：對原始點序列取「滑動視窗」，
    每個視窗內的點取凸包(convex hull)並個別填色，視窗之間刻意重疊
    (stride < window)以確保面板彼此相接、不留縫隙。因為完全不需要
    判斷每個點屬於左邊還是右邊、也不需要陣列長度整除，所以在筆劃
    彎曲、收尖、密度不均的地方都一樣穩定；只要視窗夠小，橡皮擦切出
    的平頭銳角邊緣也不會被凸包磨圓。
    """
    n = len(poly)
    if n < 3:
        return []
    panels: list[list[tuple[float, float]]] = []
    i = 0
    while i < n:
        chunk = poly[i : i + window]
        if len(chunk) >= 3:
            hull = _convex_hull(chunk)
            if len(hull) >= 3:
                panels.append(hull)
        if i + window >= n:
            break
        i += stride
    return panels


def dump_v9_to_svg_html(v9_floats: list[float], output_path="v9_debug.html"):
    """將 v9 原生網格轉換為帶有頂點編號的 SVG，用於視覺化格式分析"""
    if not v9_floats:
        return
        
    pts = [(v9_floats[i], v9_floats[i+1]) for i in range(0, len(v9_floats), 2)]
    
    # Calculate canvas bounds with padding
    min_x = min(p[0] for p in pts) - 10
    max_x = max(p[0] for p in pts) + 10
    min_y = min(p[1] for p in pts) - 10
    max_y = max(p[1] for p in pts) + 10
    width = max_x - min_x
    height = max_y - min_y

    svg = []
    svg.append(f'<html><body style="background-color: #eee;">')
    svg.append(f'<h2>GoodNotes v9 Mesh Analysis</h2>')
    # Render using SVG with automatic viewBox scaling
    svg.append(f'<svg viewBox="{min_x} {min_y} {width} {height}" style="width: 100%; height: 80vh; background: white; border: 1px solid black;" xmlns="http://www.w3.org/2000/svg">')
    
    # 1. Draw raw array connection order (light blue thin line), showing Z-shaped connections
    path_d = "M " + " L ".join(f"{p[0]:.2f},{p[1]:.2f}" for p in pts)
    svg.append(f'<path d="{path_d}" fill="none" stroke="lightblue" stroke-width="0.3"/>')

    # 2. Draw each point and label with array index (red points, black text)
    for i, p in enumerate(pts):
        svg.append(f'<circle cx="{p[0]:.2f}" cy="{p[1]:.2f}" r="0.2" fill="red" />')
        # Set font size to 0.6 and offset slightly to bottom-right of points to prevent overlap
        svg.append(f'<text x="{p[0]+0.2:.2f}" y="{p[1]+0.2:.2f}" font-size="0.6" fill="black" font-family="sans-serif">{i}</text>')

    svg.append('</svg></body></html>')

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(svg))
        
    print(f"\n[分析完成] 逆向視覺化檔案已儲存至: {output_path}")

def extract_outline_polygons_from_tpl(tpl_img: TplImage) -> list[list[tuple[float, float]]]:
    """Extract native outline mesh polygons (v9) as continuous perimeters."""
    v9 = None
    if len(tpl_img.values) > 9 and isinstance(tpl_img.values[9], list):
        v = tpl_img.values[9]
        if len(v) >= 50 and len(v) % 2 == 0:
            floats = [uint32_to_float32(u) if isinstance(u, int) else 0.0 for u in v]
            if len(floats) >= 4 and all(50.0 <= abs(fl) <= 5000.0 for fl in floats[:4]):
                if abs(floats[2]) >= 50.0:
                    v9 = floats

    if not v9:
        return []

    pts = [(v9[i], v9[i + 1]) for i in range(0, len(v9), 2)]
    polys: list[list[tuple[float, float]]] = []
    curr = [pts[0]]
    
    # Restore original v9 extraction logic: rely on 20.0 as safe breakpoint between blocks
    for i in range(1, len(pts)):
        d = math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])
        if d > 20.0:
            if len(curr) >= 3:
                polys.append(curr)
            curr = [pts[i]]
        else:
            curr.append(pts[i])
            
    if len(curr) >= 3:
        polys.append(curr)

    return polys

def split_stroke_points(pts: list[StrokePoint], threshold: float | None = None) -> list[list[StrokePoint]]:
    """
    以距離作為斷線安全防護（防止異常座標跳躍）。
    門檻恢復為安全的 300.0 點，確保快速連續筆畫與小範圍擦除皆不受人為距離切割影響。
    """
    if not pts:
        return []

    if len(pts) < 2:
        return [pts]

    dists = [
        math.hypot(pts[i].x - pts[i-1].x, pts[i].y - pts[i-1].y)
        for i in range(1, len(pts))
    ]

    if threshold is None:
        threshold = 300.0

    strokes = []
    current = [pts[0]]
    for i in range(1, len(pts)):
        if dists[i-1] > threshold:
            strokes.append(current)
            current = [pts[i]]
        else:
            current.append(pts[i])

    if current:
        strokes.append(current)

    return strokes

def build_stroke_ribbon(
    points: Sequence[StrokePoint],
    default_width: float = 1.0,
    scale: float = 1.0,
    flip_y_height: float | None = None,
    tpl_format: str = "",
    outline_polygons: Sequence[Sequence[tuple[float, float]]] = (),
    is_cut_start: bool = False,
    is_cut_end: bool = False,
) -> str | None:
    """Generate SVG path d attribute for a variable-width stroke ribbon or native outline mesh."""

    # 1. Handle GoodNotes native v9 mesh (erased strokes, keeping original sharp flat edges)
    #
    # v9 array is not outline traversal order; connecting points sequentially with L lines causes
    # self-intersections at curves/tapers, leading to jagged gaps when filled. Reconstructed
    # using sliding window convex hulls (_v9_polygon_to_hull_panels): points in each window
    # form a convex hull with intentional overlap between windows, forming independent subpaths.
    # No need to determine left/right sides, remaining stable for curves/tapers/uneven density,
    # while small windows prevent rounding off sharp erased edges.
    if outline_polygons:
        def _proj(pt: tuple[float, float]) -> tuple[float, float]:
            x = pt[0] * scale
            y = (flip_y_height - (pt[1] * scale)) if flip_y_height is not None else (pt[1] * scale)
            return (x, y)

        path_parts = []
        for poly in outline_polygons:
            if len(poly) < 3:
                continue

            panels = _v9_polygon_to_hull_panels(poly)
            if panels:
                for hull in panels:
                    projected = [_proj(p) for p in hull]
                    cmds = [
                        f"{'M' if idx == 0 else 'L'} {x:.2f} {y:.2f}"
                        for idx, (x, y) in enumerate(projected)
                    ]
                    cmds.append("Z")
                    path_parts.append(" ".join(cmds))
            else:
                # Fallback: when point count is too small, revert to simple connection
                cmds = []
                for idx, pt in enumerate(poly):
                    x, y = _proj(pt)
                    cmds.append(f"{'M' if idx == 0 else 'L'} {x:.2f} {y:.2f}")
                cmds.append("Z")
                path_parts.append(" ".join(cmds))

        if path_parts:
            return " ".join(path_parts)

    # 2. Handle un-erased regular strokes (with smoothing and rounded caps)
    if not points:
        return None

    # Filter nearly overlapping duplicate points
    filtered_points: list[StrokePoint] = []
    for p in points:
        if not filtered_points:
            filtered_points.append(p)
        else:
            if math.hypot(p.x - filtered_points[-1].x, p.y - filtered_points[-1].y) >= 1e-3:
                filtered_points.append(p)

    if not filtered_points:
        return None

    if len(filtered_points) == 1:
        p = filtered_points[0]
        r = max(0.1, p.pressure * scale)
        cx = p.x * scale
        cy = (flip_y_height - (p.y * scale)) if flip_y_height is not None else (p.y * scale)
        return f"M {cx - r:.2f},{cy:.2f} A {r:.2f},{r:.2f} 0 1,1 {cx + r:.2f},{cy:.2f} A {r:.2f},{r:.2f} 0 1,1 {cx - r:.2f},{cy:.2f}"

    if flip_y_height is not None:
        raw_pts = [(p.x * scale, flip_y_height - (p.y * scale), max(0.05, p.pressure * scale)) for p in filtered_points]
    else:
        raw_pts = [(p.x * scale, p.y * scale, max(0.05, p.pressure * scale)) for p in filtered_points]

    n = len(raw_pts)
    if n == 1:
        x, y, r = raw_pts[0]
        return f"M {x - r:.2f},{y:.2f} A {r:.2f},{r:.2f} 0 1,1 {x + r:.2f},{y:.2f} A {r:.2f},{r:.2f} 0 1,1 {x - r:.2f},{y:.2f}"

    # Coordinate smoothing (preserve both endpoints to prevent short strokes from shrinking)
    if n >= 3:
        smoothed = []
        for i in range(n):
            if i == 0 or i == n - 1:
                smoothed.append(raw_pts[i])
            else:
                lo = max(0, i - 1)
                hi = min(n, i + 2)
                window = raw_pts[lo:hi]
                sx = sum(pt[0] for pt in window) / len(window)
                sy = sum(pt[1] for pt in window) / len(window)
                sr = sum(pt[2] for pt in window) / len(window)
                smoothed.append((sx, sy, sr))
        raw_pts = smoothed

    # Calculate normal vectors
    normals: list[tuple[float, float]] = []
    for i in range(n):
        if i == 0:
            dx, dy = raw_pts[1][0] - raw_pts[0][0], raw_pts[1][1] - raw_pts[0][1]
        elif i == n - 1:
            dx, dy = raw_pts[n - 1][0] - raw_pts[n - 2][0], raw_pts[n - 1][1] - raw_pts[n - 2][1]
        else:
            dx, dy = raw_pts[i + 1][0] - raw_pts[i - 1][0], raw_pts[i + 1][1] - raw_pts[i - 1][1]

        dist = math.hypot(dx, dy)
        if dist < 1e-6:
            nx, ny = 0.0, 1.0 
        else:
            nx, ny = -dy / dist, dx / dist
        normals.append((nx, ny))

    # Normal vector moving average smoothing (critical fix: must re-normalize length)
    smoothed_normals: list[tuple[float, float]] = []
    for i in range(n):
        lo = max(0, i - 1)
        hi = min(n, i + 2)
        window = normals[lo:hi]
        sx = sum(nor[0] for nor in window) / len(window)
        sy = sum(nor[1] for nor in window) / len(window)
        
        norm = math.hypot(sx, sy)
        if norm > 1e-6:
            sx, sy = sx / norm, sy / norm
        else:
            sx, sy = 0.0, 1.0
            
        smoothed_normals.append((sx, sy))
    normals = smoothed_normals 

    left_side: list[tuple[float, float]] = []
    right_side: list[tuple[float, float]] = []
    for i in range(n):
        x, y, r = raw_pts[i]
        nx, ny = normals[i]
        left_side.append((x + nx * r, y + ny * r))
        right_side.append((x - nx * r, y - ny * r))

    def smooth_commands(pts_list: list[tuple[float, float]]) -> list[str]:
        n_len = len(pts_list)
        cmds: list[str] = []
        if n_len < 2:
            return cmds
        if n_len == 2:
            cmds.append(f"L {pts_list[1][0]:.2f} {pts_list[1][1]:.2f}")
            return cmds
        for i in range(1, n_len - 1):
            cx, cy = pts_list[i]
            nx2, ny2 = pts_list[i + 1]
            mx, my = (cx + nx2) / 2.0, (cy + ny2) / 2.0
            cmds.append(f"Q {cx:.2f} {cy:.2f} {mx:.2f} {my:.2f}")
        cmds.append(f"L {pts_list[-1][0]:.2f} {pts_list[-1][1]:.2f}")
        return cmds

    r0 = max(0.1, raw_pts[0][2])
    r1 = max(0.1, raw_pts[-1][2])
    reversed_left = list(reversed(left_side))

    d = [f"M {left_side[0][0]:.2f} {left_side[0][1]:.2f}"]
    if is_cut_start:
        d.append(f"L {right_side[0][0]:.2f} {right_side[0][1]:.2f}")
    else:
        d.append(f"A {r0:.2f} {r0:.2f} 0 0 1 {right_side[0][0]:.2f} {right_side[0][1]:.2f}")

    d.extend(smooth_commands(right_side))

    if is_cut_end:
        d.append(f"L {left_side[-1][0]:.2f} {left_side[-1][1]:.2f}")
    else:
        d.append(f"A {r1:.2f} {r1:.2f} 0 0 1 {left_side[-1][0]:.2f} {left_side[-1][1]:.2f}")

    d.extend(smooth_commands(reversed_left))
    d.append("Z")
    return " ".join(d)

def extract_dash_pattern_from_tpl(tpl_img: TplImage) -> tuple[float, ...] | None:
    """Extract dash pattern floats (e.g. from A(f) trailing array) if present."""
    if "A(f)" not in tpl_img.format:
        return None
    try:
        from .tpl import _parse_format
        nodes = _parse_format(tpl_img.format)
        for i, node in enumerate(nodes):
            if node == ("A", ("f",)):
                if i < len(tpl_img.values):
                    val = tpl_img.values[i]
                    if isinstance(val, list) and val:
                        d_vals = []
                        for x in val:
                            if isinstance(x, int):
                                f = uint32_to_float32(x)
                            elif isinstance(x, float) and 0.0 < abs(x) < 1e-10:
                                try:
                                    f = struct.unpack("<f", struct.pack("<d", x)[:4])[0]
                                except Exception:
                                    f = float(x)
                            else:
                                f = float(x)
                            d_vals.append(f)
                        if any(v > 0 for v in d_vals):
                            return tuple(d_vals)
    except Exception:
        pass
    return None


def parse_stroke_field(uuid: str, field_data: bytes, parent_uuid: str | None = None) -> list[Stroke]:
    """Parse GoodNotes binary field data to extract Strokes."""
    pos = field_data.find(b"bv41")
    if pos < 0:
        return []
    try:
        lz4_data, bytes_consumed = decode_apple_lz4(field_data[pos:])
    except CompressionError:
        return []

    if not lz4_data.startswith(b"tpl"):
        return []

    try:
        tpl_img = decode_tpl(lz4_data)
        point_groups, default_width = extract_points_from_tpl(tpl_img)
        native_polygons = extract_outline_polygons_from_tpl(tpl_img)
        tpl_dash = extract_dash_pattern_from_tpl(tpl_img)
    except Exception:
        return []

    if not point_groups:
        return []

    trailer = field_data[pos + bytes_consumed :]
    color_hex, alpha = extract_color_from_trailer(trailer)
    dx, dy = extract_move_offset_from_trailer(trailer)
    if dx or dy:
        point_groups = [
            [StrokePoint(p.x + dx, p.y + dy, p.pressure) for p in group] for group in point_groups
        ]
        native_polygons = tuple(
            tuple((x + dx, y + dy) for x, y in polygon) for polygon in native_polygons
        )
    # Highlighter detection based on alpha
    is_highlighter = alpha < 0.95

    chains = []
    # Apply safe disconnect splitting to all extracted point groups
    for group in point_groups:
        # Restore safe distance threshold of 300.0 to prevent abnormal coordinate jumps
        # while ensuring normal fast strokes and small eraser cuts are not accidentally split.
        chains.extend(split_stroke_points(group, threshold=300.0))

    strokes = []
    num_chains = len(chains)
    for chain_i, chain in enumerate(chains):
        is_dot = len(chain) == 1
        # If a single GoodNotes entry is split, it usually implies erasure.
        # Intermediate cut points should be rendered as flat caps.
        is_cut_start = (chain_i > 0)
        is_cut_end = (chain_i < num_chains - 1)
        dash_pattern = tpl_dash

        strokes.append(
            Stroke(
                uuid=uuid,
                points=tuple(chain),
                color_hex=color_hex,
                alpha=alpha,
                width=default_width,
                is_dot=is_dot,
                is_highlighter=is_highlighter,
                tpl_format=tpl_img.format,
                outline_polygons=tuple(native_polygons),
                is_cut_start=is_cut_start,
                is_cut_end=is_cut_end,
                parent_uuid=parent_uuid,
                dash_pattern=dash_pattern,
            )
        )

    return strokes