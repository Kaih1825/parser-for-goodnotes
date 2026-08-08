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
    return 0.01 <= p <= 50.0


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

    for val in tpl_img.values:
        if isinstance(val, int):
            w = uint32_to_float32(val)
            if 0.05 <= w <= 100.0:
                default_width = w
                break
        elif isinstance(val, list) and len(val) > 1 and isinstance(val[1], int):
            w = uint32_to_float32(val[1])
            if 0.05 <= w <= 100.0:
                default_width = w
                break
            
    default_radius = default_width / 2.0
    candidates: list[tuple[bool, int, int, list[StrokePoint]]] = []

    # 1. Schema 1: vuA(v)A(S(uu))A(S(uuuu))vA(f) (四元組 (x1, y1, x2, y2))
    # 嚴格匹配 Schema 1 標籤，防止其他格式被誤攔截
    #
    # 修復重點：這裡原本只用 "A(S(uuuu))" in fmt 判斷，但這是「不管位置」的
    # 子字串搜尋。鉛筆的複合格式 (vuA(v)A(S(uuuuu))A(S(uuuuuuuuuuu))...
    # ...A(S(uuuu))A(u)) 剛好在字串「後段」也含有一模一樣的 "A(S(uuuu))"
    # token（對應到 values[8]），導致這個分支被錯誤觸發，卻仍然寫死去讀
    # values[4]——而 values[4] 在這個格式裡實際上是 Schema 2 的 11 元組
    # 陣列 (A(S(uuuuuuuuuuu)))，不是四元組。四元組的欄位被硬解成 x1,y1,x2,y2，
    # 壓力則整段被 default_radius 蓋掉，這正是鋸齒筆跡與壓力/寬度錯誤的根因。
    #
    # 加回 "A(S(uuuuuuuuuuu" not in fmt 排除條件，讓含有 11 元組的複合格式
    # 改為落入下面正確的 Schema 2 分支處理。
    if "A(S(uuuu))" in fmt and "A(S(uuuuuuuuuuu" not in fmt:
        if len(tpl_img.values) > 4 and isinstance(tpl_img.values[4], list) and len(tpl_img.values[4]) > 0:
            vis_flags = (tpl_img.values[2]
                         if len(tpl_img.values) > 2 and isinstance(tpl_img.values[2], list)
                         else [])

            # 嚴格驗證 vis_flags 是否為合法的抬筆/落筆標記（應全為 0 或 1）
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
                # 只有在 vis_flags 合法且值為 0 時才進行切斷
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

            # 確保提取出的點群組包含 2 個點以上才返回，否則退回 candidates 解析
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

    # 2. Schema 2: vuA(v)A(S(uuuuu))A(S(uuuuuuuuuuu))... (11 元組)
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

    # 3. 候選點陣格式比對 (a) 6-float, (b) 3-float, (c) 5-float, (d) 2-float
    # (a) 6-float 六元组 -> 取左右邊界點之中點作為筆劃中心座標（解決彈簧鋸齒）
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

    # (b) 3-float 三元組 (x, y, p)
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

    # (c) 5-float 五元組 (x, y, p, w, angle)
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

    # (d) 2-float 二元組 (x, y)
    for idx, v in enumerate(tpl_img.values):
        if isinstance(v, list) and len(v) >= 4 and isinstance(v[0], (int, float)) and len(v) % 2 == 0:
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

    if candidates:
        # 過濾包含 2 個點以上的筆劃，秒殺 1 個點的 Metadata 雜訊
        multi_point = [c for c in candidates if c[1] >= 2]
        pool = multi_point if multi_point else candidates
        
        # 排序優先順序：
        # 1. -int(has_p)：優先選用動態壓感 (讓 shape2 恢復動態粗細)
        # 2. _path_jitter_ratio：滑順度
        # 3. -length：點數長度
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
    """將 v9 原生網格轉換為帶有頂點編號的 SVG，用於肉眼逆向分析"""
    if not v9_floats:
        return
        
    pts = [(v9_floats[i], v9_floats[i+1]) for i in range(0, len(v9_floats), 2)]
    
    # 計算畫布範圍，留一點邊距
    min_x = min(p[0] for p in pts) - 10
    max_x = max(p[0] for p in pts) + 10
    min_y = min(p[1] for p in pts) - 10
    max_y = max(p[1] for p in pts) + 10
    width = max_x - min_x
    height = max_y - min_y

    svg = []
    svg.append(f'<html><body style="background-color: #eee;">')
    svg.append(f'<h2>GoodNotes v9 Mesh Reverse Engineering</h2>')
    # 使用 SVG 繪製，設定 viewBox 自動縮放
    svg.append(f'<svg viewBox="{min_x} {min_y} {width} {height}" style="width: 100%; height: 80vh; background: white; border: 1px solid black;" xmlns="http://www.w3.org/2000/svg">')
    
    # 1. 畫出原始陣列的連線順序 (淺藍色細線)，這會呈現我們之前失敗的 Z 字型連線
    path_d = "M " + " L ".join(f"{p[0]:.2f},{p[1]:.2f}" for p in pts)
    svg.append(f'<path d="{path_d}" fill="none" stroke="lightblue" stroke-width="0.3"/>')

    # 2. 畫出每一個點，並標上陣列的 Index (紅色點，黑色字)
    for i, p in enumerate(pts):
        svg.append(f'<circle cx="{p[0]:.2f}" cy="{p[1]:.2f}" r="0.2" fill="red" />')
        # 字體大小設為 0.6，並在點的右下角稍微偏移，避免重疊
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
    
    # 恢復最初最完美的 v9 提取邏輯：依賴 20.0 作為不同區塊間的安全斷點
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

    # 1. 處理 GoodNotes 原生 v9 網格 (被橡皮擦切過的筆跡，保持原本的平頭銳利邊緣)
    #
    # v9 陣列不是外框走訪順序，直接依序用 L 直線連接會在筆劃彎曲/收尖處
    # 自我交叉，填色時出現鋸齒缺口。改用滑動視窗凸包 (_v9_polygon_to_hull_panels)
    # 重建：每個視窗內的點取凸包、視窗間刻意重疊，各自成獨立子路徑再
    # 聯集，完全不需要判斷點屬於左邊還是右邊，對彎曲/收尖/密度不均都
    # 一樣穩定，同時視窗夠小不會磨圓橡皮擦切出的平頭銳角邊緣。
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
                # 保底：點數過少時，退回舊的簡單連線方式
                cmds = []
                for idx, pt in enumerate(poly):
                    x, y = _proj(pt)
                    cmds.append(f"{'M' if idx == 0 else 'L'} {x:.2f} {y:.2f}")
                cmds.append("Z")
                path_parts.append(" ".join(cmds))

        if path_parts:
            return " ".join(path_parts)

    # 2. 處理未被擦除的一般筆跡 (加上平滑與完美圓角)
    if not points:
        return None

    # 過濾近乎重疊的重複點
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

    # 座標平滑 (保留兩端端點位置，避免 short stroke 被往內拉縮短長度)
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

    # 計算法向量
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

    # 法向量滑動平均平滑 (關鍵修正：必須重新歸一化長度)
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

    # 強制圓角收頭，徹底解決左側未被擦除筆跡的鋸齒問題
    d = [f"M {left_side[0][0]:.2f} {left_side[0][1]:.2f}"]
    d.append(f"A {r0:.2f} {r0:.2f} 0 0 1 {right_side[0][0]:.2f} {right_side[0][1]:.2f}")
    d.extend(smooth_commands(right_side))
    d.append(f"A {r1:.2f} {r1:.2f} 0 0 1 {left_side[-1][0]:.2f} {left_side[-1][1]:.2f}")
    d.extend(smooth_commands(reversed_left))
    d.append("Z")
    return " ".join(d)

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
    # 對所有提取出的點群組應用安全防護斷線切割
    for group in point_groups:
        # 恢復使用 300.0 的安全距離門檻。這可以防止座標異常跳躍，
        # 但確保正常快速筆劃和小範圍擦除切口不會被意外斷線。
        chains.extend(split_stroke_points(group, threshold=300.0))

    strokes = []
    num_chains = len(chains)
    for chain_i, chain in enumerate(chains):
        is_dot = len(chain) == 1
        # 單一 GoodNotes 資料若被 split，通常意味著擦除。
        # 中間的切點應該被繪製為平頭。
        is_cut_start = (chain_i > 0)
        is_cut_end = (chain_i < num_chains - 1)
        dash_pattern = None
        if not is_highlighter and len(chain) >= 2 and default_width > 3.0:
            pressures = [p.pressure for p in chain]
            p_var = max(pressures) - min(pressures)
            if p_var < 1e-4:
                dists = [math.hypot(chain[j+1].x - chain[j].x, chain[j+1].y - chain[j].y) for j in range(len(chain)-1)]
                tot_len = sum(dists)
                if len(dists) > 0 and tot_len > 0:
                    avg_d = tot_len / len(dists)
                    ratio = avg_d / default_width
                    if ratio < 0.17:
                        dash_pattern = (0.0, 3.0)
                    elif 0.17 <= ratio < 0.3:
                        dash_pattern = (10.0, 6.0)

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