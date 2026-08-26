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
    start_cut_vec: tuple[float, float] | None = None
    end_cut_vec: tuple[float, float] | None = None
    parent_uuid: str | None = None
    dash_pattern: tuple[float, ...] | None = None
    eraser_cuts: tuple[tuple[float, ...], ...] = ()
    native_cgpaths: tuple[tuple[tuple[str, tuple[float, ...]], ...], ...] = ()

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
    return 0.001 <= p <= 100.0


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

    # 0. Erased / Segmented Strokes: values[4] is a flat list of 6-tuples (x1, y1, x2, y2, r1, r2)
    # Only active for erased strokes (where values[9] mesh exists)
    is_erased_stroke = len(tpl_img.values) > 9 and isinstance(tpl_img.values[9], list) and len(tpl_img.values[9]) > 0
    if is_erased_stroke and len(tpl_img.values) > 4 and isinstance(tpl_img.values[4], list) and len(tpl_img.values[4]) >= 6:
        v4 = tpl_img.values[4]
        if isinstance(v4[0], (int, float)) and len(v4) % 6 == 0 and "A(S(" not in fmt:
            floats4 = [uint32_to_float32(u) if isinstance(u, int) else u for u in v4]
            if len(floats4) >= 4 and all(is_valid_coord(fl) and abs(fl) >= 10.0 for fl in floats4[:4]):
                segs = []
                for i in range(0, len(floats4), 6):
                    if i + 6 <= len(floats4):
                        segs.append(floats4[i : i + 6])
                if segs:
                    valid_r = [s[4] for s in segs if s[4] > 1.0]
                    nominal_r = sorted(valid_r)[len(valid_r) // 2] if valid_r else 8.87
                    max_allowed_r = nominal_r * 1.10

                    clean_segs = []
                    for s in segs:
                        r1 = min(max_allowed_r, s[4])
                        r2 = min(max_allowed_r, s[5])
                        clean_segs.append([s[0], s[1], s[2], s[3], r1, r2])
                    segs = clean_segs

                    sub_segs = []
                    cut_jumps = []
                    curr_s = [segs[0]]
                    last_jump = None
                    eraser_cuts: list[tuple[float, ...]] = []
                    for idx in range(len(segs) - 1):
                        s_curr, s_next = segs[idx], segs[idx + 1]
                        seg_len = math.hypot(s_curr[2] - s_curr[0], s_curr[3] - s_curr[1])
                        gap = math.hypot(s_next[0] - s_curr[2], s_next[1] - s_curr[3])
                        ratio = gap / max(1e-3, seg_len)
                        is_cut = (gap > 30.0) or (gap > 18.0 and ratio > 2.2) or (gap > 12.0 and ratio > 3.5)
                        if is_cut:
                            sub_segs.append(curr_s)
                            jump = (s_next[0] - s_curr[2], s_next[1] - s_curr[3])
                            cut_jumps.append((last_jump, jump))
                            last_jump = jump
                            curr_s = [s_next]

                            x1, y1 = s_curr[2], s_curr[3]
                            x2, y2 = s_next[0], s_next[1]
                            r_c = max(s_curr[5], s_next[4])
                            if gap <= 60.0:
                                cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
                                r_erase = max(gap / 2.0, r_c * 0.95)
                                eraser_cuts.append((0.0, cx, cy, r_erase))
                                eraser_cuts.append((1.0, x1, y1, x2, y2, r_erase * 2.0))
                        else:
                            curr_s.append(s_next)
                    if curr_s:
                        sub_segs.append(curr_s)
                        cut_jumps.append((last_jump, None))

                    valid_groups = []
                    valid_jumps = []
                    for s_idx, s_list in enumerate(sub_segs):
                        tot_len = sum(math.hypot(s[2] - s[0], s[3] - s[1]) for s in s_list)
                        start_j, end_j = cut_jumps[s_idx]
                        if tot_len < 1.0 and start_j is not None and end_j is not None:
                            continue

                        # Smooth any sudden pinch at cut endpoints
                        if start_j is not None and len(s_list) >= 2:
                            if s_list[0][4] < s_list[1][4] * 0.7:
                                s_list[0][4] = s_list[1][4]
                        if end_j is not None and len(s_list) >= 2:
                            if s_list[-1][5] < s_list[-2][5] * 0.7:
                                s_list[-1][5] = s_list[-2][5]

                        pts_raw = [(s_list[0][0], s_list[0][1], s_list[0][4])]
                        for s in s_list:
                            pts_raw.append((s[2], s[3], s[5]))

                        clean_pts = [StrokePoint(pts_raw[0][0], pts_raw[0][1], pts_raw[0][2])]
                        for p in pts_raw[1:]:
                            if math.hypot(p[0] - clean_pts[-1].x, p[1] - clean_pts[-1].y) >= 1.2:
                                clean_pts.append(StrokePoint(p[0], p[1], p[2]))
                        if len(pts_raw) > 1 and math.hypot(pts_raw[-1][0] - clean_pts[-1].x, pts_raw[-1][1] - clean_pts[-1].y) > 0.2:
                            clean_pts.append(StrokePoint(pts_raw[-1][0], pts_raw[-1][1], pts_raw[-1][2]))
                        if len(clean_pts) < 2:
                            clean_pts = [StrokePoint(pts_raw[0][0], pts_raw[0][1], pts_raw[0][2]), StrokePoint(pts_raw[-1][0], pts_raw[-1][1], pts_raw[-1][2])] if len(pts_raw) >= 2 else clean_pts
                        if len(clean_pts) >= 2:
                            valid_groups.append(clean_pts)
                            valid_jumps.append(cut_jumps[s_idx])

                    if valid_groups:
                        return valid_groups, default_width, valid_jumps, eraser_cuts

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
                return valid_groups, default_width, [(None, None)] * len(valid_groups), []

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
                return groups, default_width, [(None, None)] * len(groups), []

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
                return groups, default_width, [(None, None)] * len(groups), []

    # 3. Candidate point-array format matching (a) 3-float, (b) 5-float, (c) 2-float
    # Limit idx <= 5 to avoid misidentifying trailing outline polygon / mesh lists (values[6..10]) as point arrays
    # (a) 3-float 3-tuple (x, y, p)
    for idx, v in enumerate(tpl_img.values):
        if idx <= 5 and isinstance(v, list) and len(v) >= 3 and isinstance(v[0], (int, float)) and len(v) % 3 == 0:
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
        if idx <= 5 and isinstance(v, list) and len(v) >= 5 and isinstance(v[0], (int, float)) and len(v) % 5 == 0:
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
        return groups, default_width, [(None, None)] * len(groups), []

    return groups, default_width, [(None, None)] * len(groups), []


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
    """Extract native outline mesh polygons (v9) as individual closed cross-section panels."""
    # If values[4] contains 6-tuple segments, stroke points are directly and cleanly reconstructed
    if len(tpl_img.values) > 4 and isinstance(tpl_img.values[4], list) and len(tpl_img.values[4]) >= 6:
        if isinstance(tpl_img.values[4][0], (int, float)):
            return []

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
    if len(pts) < 3:
        return []

    panels: list[list[tuple[float, float]]] = []
    curr = [pts[0]]

    # Detect panel boundaries based on cross-section panel lengths and jump distances
    for i in range(1, len(pts)):
        d = math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])
        if (len(curr) in (6, 12, 15) and d > 1.8) or d > 2.2:
            if len(curr) >= 3:
                panels.append(curr)
            curr = [pts[i]]
        else:
            curr.append(pts[i])

    if len(curr) >= 3:
        panels.append(curr)

    return panels


def extract_segment_polygons_from_tpl(tpl_img: TplImage) -> list[list[list[tuple[float, float]]]]:
    """Segment polygons disabled in favor of smooth continuous ribbon."""
    return []


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
        math.hypot(pts[i].x - pts[i-1].x, pts[i].y - pts[i-1].y) if hasattr(pts[i], 'x') else math.hypot(pts[i][0] - pts[i-1][0], pts[i][1] - pts[i-1][1])
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
    start_cut_vec: tuple[float, float] | None = None,
    end_cut_vec: tuple[float, float] | None = None,
    ext_dist: float = 4.0,
) -> str | None:
    """Generate SVG path d attribute for a variable-width stroke ribbon or native outline mesh."""

    # 1. Handle GoodNotes native v9 mesh (erased strokes, keeping original sharp flat edges)
    if outline_polygons:
        def _proj(pt: tuple[float, float]) -> tuple[float, float]:
            x = pt[0] * scale
            y = (flip_y_height - (pt[1] * scale)) if flip_y_height is not None else (pt[1] * scale)
            return (x, y)

        path_parts = []
        for poly in outline_polygons:
            if len(poly) < 3:
                continue
            cmds = [
                f"{'M' if idx == 0 else 'L'} {x:.2f} {y:.2f}"
                for idx, (x, y) in enumerate(_proj(p) for p in poly)
            ]
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

    # Extend cut endpoints slightly along tangent to reach true eraser boundary
    pts_to_render = list(filtered_points)
    n_pts = len(pts_to_render)
    tot_len = sum(math.hypot(pts_to_render[k].x - pts_to_render[k - 1].x, pts_to_render[k].y - pts_to_render[k - 1].y) for k in range(1, n_pts)) if n_pts >= 2 else 0.0
    effective_ext = ext_dist if tot_len >= 8.0 else 0.0

    if is_cut_start and effective_ext > 0 and len(pts_to_render) >= 2:
        p0, p1 = pts_to_render[0], pts_to_render[1]
        tdx, tdy = p0.x - p1.x, p0.y - p1.y
        tdist = math.hypot(tdx, tdy)
        if tdist > 1e-4:
            e = min(effective_ext, tdist * 0.35)
            pts_to_render[0] = StrokePoint(p0.x + (tdx / tdist) * e, p0.y + (tdy / tdist) * e, p0.pressure)
    if is_cut_end and effective_ext > 0 and len(pts_to_render) >= 2:
        p0, p1 = pts_to_render[-1], pts_to_render[-2]
        tdx, tdy = p0.x - p1.x, p0.y - p1.y
        tdist = math.hypot(tdx, tdy)
        if tdist > 1e-4:
            e = min(effective_ext, tdist * 0.35)
            pts_to_render[-1] = StrokePoint(p0.x + (tdx / tdist) * e, p0.y + (tdy / tdist) * e, p0.pressure)

    if flip_y_height is not None:
        raw_pts = [(p.x * scale, flip_y_height - (p.y * scale), max(0.05, p.pressure * scale * 0.99)) for p in pts_to_render]
    else:
        raw_pts = [(p.x * scale, p.y * scale, max(0.05, p.pressure * scale * 0.99)) for p in pts_to_render]

    n = len(raw_pts)
    if n == 1:
        x, y, r = raw_pts[0]
        return f"M {x - r:.2f},{y:.2f} A {r:.2f},{r:.2f} 0 1,1 {x + r:.2f},{y:.2f} A {r:.2f},{r:.2f} 0 1,1 {x - r:.2f},{y:.2f}"

    # Direct spline vertices (already interpolated in GoodNotes engine)
    pass

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

    # Normal vector moving average smoothing (preserve strict endpoint normals for cut boundaries)
    smoothed_normals: list[tuple[float, float]] = []
    for i in range(n):
        if (i == 0 and is_cut_start) or (i == n - 1 and is_cut_end):
            smoothed_normals.append(normals[i])
            continue
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
        for i in range(n_len - 1):
            p0 = pts_list[max(0, i - 1)]
            p1 = pts_list[i]
            p2 = pts_list[i + 1]
            p3 = pts_list[min(n_len - 1, i + 2)]
            c1x = p1[0] + (p2[0] - p0[0]) / 6.0
            c1y = p1[1] + (p2[1] - p0[1]) / 6.0
            c2x = p2[0] - (p3[0] - p1[0]) / 6.0
            c2y = p2[1] - (p3[1] - p1[1]) / 6.0
            cmds.append(f"C {c1x:.2f} {c1y:.2f}, {c2x:.2f} {c2y:.2f}, {p2[0]:.2f} {p2[1]:.2f}")
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


def extract_native_cgpath_segments_from_tpl(
    tpl_img: TplImage,
) -> tuple[tuple[tuple[str, tuple[float, ...]], ...], ...]:
    """Extract native Apple CGPath segment definitions (M, C, A commands) from tpl values."""
    if len(tpl_img.values) <= 9 or not isinstance(tpl_img.values[9], list) or len(tpl_img.values[9]) < 6:
        return ()
    if (
        len(tpl_img.values) <= 7
        or not isinstance(tpl_img.values[7], list)
        or not isinstance(tpl_img.values[5], list)
        or not isinstance(tpl_img.values[6], list)
    ):
        return ()
    v5 = tpl_img.values[5]
    v6 = tpl_img.values[6]
    v7 = [uint32_to_float32(x) for x in tpl_img.values[7]]
    v9 = [uint32_to_float32(x) for x in tpl_img.values[9]]
    v10 = [uint32_to_float32(x) for x in tpl_img.values[10]] if len(tpl_img.values) > 10 and isinstance(tpl_img.values[10], list) else []
    v11 = tpl_img.values[11] if len(tpl_img.values) > 11 and isinstance(tpl_img.values[11], list) else []

    v7_pts = [(v7[i], v7[i + 1]) for i in range(0, len(v7), 2)]
    v9_pts = [(v9[i], v9[i + 1]) for i in range(0, len(v9), 2)]
    v10_arcs = [(v10[i], v10[i + 1], v10[i + 2], v10[i + 3], v10[i + 4]) for i in range(0, len(v10), 5)]

    v6_idx = 0
    v7_idx = 0
    v9_idx = 0
    v10_idx = 0
    v11_idx = 0

    segments = []
    for count in v5:
        seg_v6 = v6[v6_idx : v6_idx + count]
        v6_idx += count

        seg_cmds = []
        for cmd in seg_v6:
            if cmd == 2:
                if v7_idx < len(v7_pts):
                    p0 = v7_pts[v7_idx]
                    v7_idx += 1
                    seg_cmds.append(("M", (p0[0], p0[1])))
            elif cmd == 4:
                if v9_idx + 2 < len(v9_pts):
                    c1 = v9_pts[v9_idx]
                    c2 = v9_pts[v9_idx + 1]
                    p2 = v9_pts[v9_idx + 2]
                    v9_idx += 3
                    seg_cmds.append(("C", (c1[0], c1[1], c2[0], c2[1], p2[0], p2[1])))
            elif cmd == 5:
                if v10_idx < len(v10_arcs):
                    cx, cy, r, a0, a1 = v10_arcs[v10_idx]
                    flag = v11[v11_idx] if v11_idx < len(v11) else 1
                    v10_idx += 1
                    v11_idx += 1
                    seg_cmds.append(("A", (cx, cy, r, a0, a1, float(flag))))
        if seg_cmds:
            segments.append(tuple(seg_cmds))
    return tuple(segments)


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
        point_groups, default_width, cut_jumps, eraser_cuts = extract_points_from_tpl(tpl_img)
        native_polygons = extract_outline_polygons_from_tpl(tpl_img)
        segment_polygon_groups = extract_segment_polygons_from_tpl(tpl_img)
        tpl_dash = extract_dash_pattern_from_tpl(tpl_img)
        native_cgpaths = extract_native_cgpath_segments_from_tpl(tpl_img)
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
        segment_polygon_groups = [
            [[(x + dx, y + dy) for x, y in quad] for quad in quads]
            for quads in segment_polygon_groups
        ]
    # Highlighter detection based on alpha
    is_highlighter = alpha < 0.95

    chains = []
    chain_polys: list[tuple[tuple[tuple[float, float], ...], ...]] = []
    chain_cut_jumps: list[tuple[tuple[float, float] | None, tuple[float, float] | None]] = []
    have_segment_polys = len(segment_polygon_groups) == len(point_groups)

    for group_idx, group in enumerate(point_groups):
        sub_chains = split_stroke_points(group, threshold=300.0)
        chains.extend(sub_chains)
        c_jump = cut_jumps[group_idx] if group_idx < len(cut_jumps) else (None, None)
        chain_cut_jumps.append(c_jump)
        chain_cut_jumps.extend([(None, None)] * (len(sub_chains) - 1))
        if have_segment_polys and sub_chains:
            group_quads = tuple(tuple(pt for pt in quad) for quad in segment_polygon_groups[group_idx])
            chain_polys.append(group_quads)
            chain_polys.extend([()] * (len(sub_chains) - 1))
        else:
            chain_polys.extend([()] * len(sub_chains))

    if native_cgpaths:
        first_pts = point_groups[0] if point_groups else []
        return [
            Stroke(
                uuid=uuid,
                points=tuple(first_pts),
                color_hex=color_hex,
                alpha=alpha,
                width=default_width,
                is_dot=len(first_pts) == 1,
                is_highlighter=is_highlighter,
                tpl_format=tpl_img.format,
                parent_uuid=parent_uuid,
                dash_pattern=tpl_dash,
                eraser_cuts=tuple(eraser_cuts),
                native_cgpaths=native_cgpaths,
            )
        ]

    strokes = []
    num_chains = len(chains)
    for chain_i, chain in enumerate(chains):
        is_dot = len(chain) == 1
        start_cut, end_cut = chain_cut_jumps[chain_i] if chain_i < len(chain_cut_jumps) else (None, None)
        is_cut_start = start_cut is not None
        is_cut_end = end_cut is not None
        dash_pattern = tpl_dash
        chain_outline_polygons = chain_polys[chain_i] if chain_i < len(chain_polys) and chain_polys[chain_i] else tuple(native_polygons)

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
                outline_polygons=chain_outline_polygons,
                is_cut_start=is_cut_start,
                is_cut_end=is_cut_end,
                start_cut_vec=start_cut,
                end_cut_vec=end_cut,
                parent_uuid=parent_uuid,
                dash_pattern=dash_pattern,
                eraser_cuts=tuple(eraser_cuts),
            )
        )

    return strokes