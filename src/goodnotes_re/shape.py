"""Typed shape geometry extracted from GoodNotes page records."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .wire import Message, decode_message, try_decode_message


@dataclass(frozen=True)
class ShapePath:
    record_index: int
    uuid: str | None
    points: tuple[tuple[float, float], ...]
    stroke_width: float
    field_numbers: tuple[int, ...]
    color_hex: str = "#1e1b1b"
    alpha: float = 1.0
    fill_alpha: float = 1.0
    shape_type: str = "polygon"
    cx: float | None = None
    cy: float | None = None
    rx: float | None = None
    ry: float | None = None
    rotation: float = 0.0
    is_filled: bool = True
    dash_pattern: tuple[float, ...] | None = None
    start_arrow: int | bool = False
    end_arrow: int | bool = False
    corner_radius: float = 0.0
    is_text_box_background: bool = False
    parent_uuid: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "record_index": self.record_index,
            "uuid": self.uuid,
            "points": [{"x": x, "y": y} for x, y in self.points],
            "stroke_width": self.stroke_width,
            "field_numbers": list(self.field_numbers),
            "color_hex": self.color_hex,
            "alpha": self.alpha,
            "fill_alpha": self.fill_alpha,
            "shape_type": self.shape_type,
            "cx": self.cx,
            "cy": self.cy,
            "rx": self.rx,
            "ry": self.ry,
            "rotation": self.rotation,
            "is_filled": self.is_filled,
            "dash_pattern": list(self.dash_pattern) if self.dash_pattern else None,
            "start_arrow": self.start_arrow,
            "end_arrow": self.end_arrow,
            "corner_radius": self.corner_radius,
            "is_text_box_background": self.is_text_box_background,
            "parent_uuid": self.parent_uuid,
        }


def _uuid_from_message(message: Message) -> str | None:
    fields = message.by_number(1)
    if not fields or not isinstance(fields[0].value, bytes):
        return None
    try:
        value = fields[0].value.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return value if len(value) == 36 and value.count("-") == 4 else None


def _extract_point(msg: Message) -> tuple[float, float] | None:
    """
    安全擷取 X 與 Y 座標。
    Protobuf 序列化時不保證欄位順序，若直接依序讀取會導致 X/Y 顛倒。
    此函式將所有浮點數依 Tag 號碼排序後取前兩個，保證座標正確且相容不同的 Tag 定義。
    """
    valid_floats = []
    for field in sorted(msg.fields, key=lambda x: x.number):
        val = field.fixed_float()
        if val is not None:
            valid_floats.append(val)
            
    if len(valid_floats) >= 2:
        return valid_floats[0], valid_floats[1]
    return None

def _get_point(msg: Message) -> tuple[float, float] | None:
    """自動處理不同層級的 Protobuf 巢狀結構以提取座標"""
    pt = _extract_point(msg)
    if pt: return pt
    for field in sorted(msg.fields, key=lambda x: x.number):
        if isinstance(field.value, bytes):
            sub = try_decode_message(field.value)
            if sub:
                pt = _extract_point(sub)
                if pt: return pt
    return None

def _parse_curves(container: Message) -> list[tuple[float, float]]:
    """通用的路徑解析：同時支援 Tag ID 對應 (Type 31) 與序列指令 (Field 9)"""
    pts_dict = {}
    for f in container.fields:
        if isinstance(f.value, bytes):
            sub = try_decode_message(f.value)
            if sub:
                pt = _get_point(sub)
                if pt: pts_dict[f.number] = pt

    # 情況 A：單一貝茲曲線片段 (通常存在於 Type 31 的 f21)
    if 1 in pts_dict and 2 in pts_dict and (3 in pts_dict or 4 in pts_dict):
        pts = [pts_dict[1]]
        p_start = pts_dict[1]
        if 3 in pts_dict and 4 not in pts_dict:
            # 二次貝茲曲線 (Quadratic)
            p_c, p_end = pts_dict[2], pts_dict[3]
            for j in range(1, 31):
                t = j / 30.0
                u = 1.0 - t
                x = u**2 * p_start[0] + 2 * u * t * p_c[0] + t**2 * p_end[0]
                y = u**2 * p_start[1] + 2 * u * t * p_c[1] + t**2 * p_end[1]
                pts.append((x, y))
        elif 3 in pts_dict and 4 in pts_dict:
            # 三次貝茲曲線 (Cubic)
            p_c1, p_c2, p_end = pts_dict[2], pts_dict[3], pts_dict[4]
            print("Type1")
            for j in range(1, 31):
                t = j / 30.0
                u = 1.0 - t
                x = u**3 * p_start[0] + 3 * u**2 * t * p_c1[0] + 3 * u * t**2 * p_c2[0] + t**3 * p_end[0]
                y = u**3 * p_start[1] + 3 * u**2 * t * p_c1[1] + 3 * u * t**2 * p_c2[1] + t**3 * p_end[1]
                pts.append((x, y))
        else:
            pts.append(pts_dict[2])
        return pts

    # 情況 B：連續路徑指令 (通常存在於 Field 9)
    commands = []
    for item_field in container.fields:
        if not isinstance(item_field.value, bytes): continue
        item = try_decode_message(item_field.value)
        if not item: continue
        cmd = item_field.number
        if item.fields:
            inner_cmd = item.fields[0].number
            if inner_cmd in (1, 2, 3, 4, 5): cmd = inner_cmd
        pt = _get_point(item)
        if pt: commands.append((cmd, pt))
    
    pts = []
    i = 0
    while i < len(commands):
        cmd, pt = commands[i]
        if cmd == 3 and i + 1 < len(commands): # Quad
            p_c, p_end = pt, commands[i+1][1]
            p_start = pts[-1] if pts else p_c
            for j in range(1, 31):
                t = j / 30.0
                u = 1.0 - t
                x = u**2 * p_start[0] + 2 * u * t * p_c[0] + t**2 * p_end[0]
                y = u**2 * p_start[1] + 2 * u * t * p_c[1] + t**2 * p_end[1]
                pts.append((x, y))
            i += 2
            continue
        elif cmd == 4 and i + 2 < len(commands): # Cubic
            p_c1, p_c2, p_end = pt, commands[i+1][1], commands[i+2][1]
            p_start = pts[-1] if pts else p_c1
            for j in range(1, 31):
                t = j / 30.0
                u = 1.0 - t
                x = u**3 * p_start[0] + 3 * u**2 * t * p_c1[0] + 3 * u * t**2 * p_c2[0] + t**3 * p_end[0]
                y = u**3 * p_start[1] + 3 * u**2 * t * p_c1[1] + 3 * u * t**2 * p_c2[1] + t**3 * p_end[1]
                pts.append((x, y))
            i += 3
            continue
        pts.append(pt)
        i += 1
    return pts


def _parse_geometry_from_field9(field9: Message) -> dict[str, Any]:
    geom = {
        "points": (),
        "shape_type": "polygon",
        "cx": None, "cy": None, "rx": None, "ry": None, "rotation": 0.0
    }

    # 1. 處理手繪多邊形 / 線條 (Tag 1 或是 Tag 2)
    container_fields = field9.by_number(1) or field9.by_number(2)
    if container_fields and isinstance(container_fields[0].value, bytes):
        container = decode_message(container_fields[0].value)
        pts = _parse_curves(container)
        if len(pts) >= 2:
            geom["points"] = tuple(pts)
            return geom

    # 2. 處理傾斜物件 (例如傾斜紅色橢圓 Tag 4)
    f4_fields = field9.by_number(4)
    if f4_fields and isinstance(f4_fields[0].value, bytes):
        try:
            sub = decode_message(f4_fields[0].value)
            f1 = sub.by_number(1) # Center pt
            f2 = sub.by_number(2) # Radii
            f3 = sub.by_number(3) # Rotation angle (radians)

            if f1 and f2 and isinstance(f1[0].value, bytes) and isinstance(f2[0].value, bytes):
                pt1_msg = decode_message(f1[0].value)
                pt2_msg = decode_message(f2[0].value)

                center = _extract_point(pt1_msg)
                radii = _extract_point(pt2_msg)

                if center and radii:
                    geom["cx"], geom["cy"] = center
                    geom["rx"], geom["ry"] = radii
                    
                    if f3:
                        geom["rotation"] = f3[0].fixed_float() or 0.0

                    geom["shape_type"] = "ellipse"
                    
                    points_list = []
                    steps = 144
                    cos_rot = math.cos(geom["rotation"])
                    sin_rot = math.sin(geom["rotation"])
                    
                    for i in range(steps):
                        t = (2 * math.pi * i) / steps
                        cos_t = math.cos(t)
                        sin_t = math.sin(t)
                        
                        px = geom["cx"] + geom["rx"] * cos_t * cos_rot - geom["ry"] * sin_t * sin_rot
                        py = geom["cy"] + geom["rx"] * cos_t * sin_rot + geom["ry"] * sin_t * cos_rot
                        points_list.append((px, py))
                        
                    points_list.append(points_list[0]) # 閉合多邊形
                    geom["points"] = tuple(points_list)
                    return geom
        except Exception:
            pass

    # 3. 處理無旋轉的矩形/圓形 (Tag 3)
    f3_fields = field9.by_number(3)
    if f3_fields and isinstance(f3_fields[0].value, bytes):
        try:
            sub = decode_message(f3_fields[0].value)
            f1 = sub.by_number(1)
            f2 = sub.by_number(2)
            
            if f1 and f2 and isinstance(f1[0].value, bytes) and isinstance(f2[0].value, bytes):
                pt1_msg = decode_message(f1[0].value)
                pt2_msg = decode_message(f2[0].value)
                
                center = _extract_point(pt1_msg) # 確定是中心點 (cx, cy)
                size = _extract_point(pt2_msg)   # 確定是完整寬高 (w, h)
                
                if center and size:
                    cx, cy = center
                    w, h = size
                    
                    geom["shape_type"] = "rectangle"
                    geom["cx"] = cx
                    geom["cy"] = cy
                    geom["rx"] = w / 2.0
                    geom["ry"] = h / 2.0
                    
                    # 從中心點反推正確的四個邊界位置
                    left = cx - (w / 2.0)
                    top = cy - (h / 2.0)
                    right = cx + (w / 2.0)
                    bottom = cy + (h / 2.0)
                    
                    # 依序建構矩形的 5 個頂點
                    geom["points"] = (
                        (left, top),       # 左上
                        (right, top),      # 右上
                        (right, bottom),   # 右下
                        (left, bottom),    # 左下
                        (left, top)        # 閉合
                    )
                    return geom
        except Exception:
            pass

    return geom
    

def extract_move_offset_from_message(msg: Message) -> tuple[float, float]:
    """
    Extract dx, dy move offset applied to a shape when selected or moved by user.
    """
    for f_num in (14, 6):
        f = msg.by_number(f_num)
        if f and isinstance(f[0].value, bytes) and f[0].value:
            try:
                offset_msg = decode_message(f[0].value)
                f1 = offset_msg.by_number(1)
                f2 = offset_msg.by_number(2)
                dx = f1[0].fixed_float() if f1 else None
                dy = f2[0].fixed_float() if f2 else None
                if dx is not None or dy is not None:
                    return dx or 0.0, dy or 0.0
            except Exception:
                pass
    return 0.0, 0.0


def _parse_type31_shape(record_index: int, msg: Message, parent_uuid: str | None = None) -> ShapePath | None:
    uuid = _uuid_from_message(msg)

    start_arrow = msg.by_number(30)[0].value if (msg.by_number(30) and isinstance(msg.by_number(30)[0].value, int)) else 0
    end_arrow = msg.by_number(31)[0].value if (msg.by_number(31) and isinstance(msg.by_number(31)[0].value, int)) else 0

    pts: list[tuple[float, float]] = []
    f21 = msg.by_number(21)
    if f21 and isinstance(f21[0].value, bytes):
        m21 = try_decode_message(f21[0].value)
        if m21:
            pts = _parse_curves(m21)


    if not pts:
        f20 = msg.by_number(20)
        if f20 and isinstance(f20[0].value, bytes):
            m20 = try_decode_message(f20[0].value)
            if m20:
                for sf in m20.by_number(2):
                    if isinstance(sf.value, bytes):
                        m_pt = try_decode_message(sf.value)
                        if m_pt and m_pt.by_number(1) and m_pt.by_number(2):
                            fx = m_pt.by_number(1)[0].fixed_float()
                            fy = m_pt.by_number(2)[0].fixed_float()
                            if fx is not None and fy is not None:
                                pts.append((fx, fy))

    if not pts:
        return None

    stroke_width = 1.0
    color_hex, alpha = "#1e1b1b", 1.0
    dash_pattern: tuple[float, ...] | None = None
    f32 = msg.by_number(32)
    if f32 and isinstance(f32[0].value, bytes):
        m32 = try_decode_message(f32[0].value)
        if m32:
            if m32.by_number(1):
                stroke_width = m32.by_number(1)[0].fixed_float() or 1.0
            f32_2 = m32.by_number(2)
            if f32_2 and isinstance(f32_2[0].value, bytes):
                m2 = try_decode_message(f32_2[0].value)
                if m2 and m2.by_number(2) and isinstance(m2.by_number(2)[0].value, bytes):
                    m_dash = try_decode_message(m2.by_number(2)[0].value)
                    if m_dash:
                        d_vals = [sf.fixed_float() for sf in m_dash.fields if sf.fixed_float() is not None]
                        if d_vals:
                            dash_pattern = tuple(d_vals)
            if m32.by_number(3) and isinstance(m32.by_number(3)[0].value, bytes):
                m_c = try_decode_message(m32.by_number(3)[0].value)
                if m_c and m_c.by_number(1) and isinstance(m_c.by_number(1)[0].value, bytes):
                    m_rgb = try_decode_message(m_c.by_number(1)[0].value)
                    if m_rgb:
                        r = m_rgb.by_number(1)
                        g = m_rgb.by_number(2)
                        b = m_rgb.by_number(3)
                        if r and g and b:
                            cr = min(255, max(0, int(round((r[0].fixed_float() or 0) * 255.0))))
                            cg = min(255, max(0, int(round((g[0].fixed_float() or 0) * 255.0))))
                            cb = min(255, max(0, int(round((b[0].fixed_float() or 0) * 255.0))))
                            color_hex = f"#{cr:02x}{cg:02x}{cb:02x}"

    return ShapePath(
        record_index=record_index,
        uuid=uuid,
        points=tuple(pts),
        stroke_width=stroke_width,
        field_numbers=(1, 2, 8, 9, 14, 16),
        color_hex=color_hex,
        alpha=alpha,
        shape_type="polyline",
        is_filled=False,
        dash_pattern=dash_pattern,
        start_arrow=start_arrow,
        end_arrow=end_arrow,
        parent_uuid=parent_uuid,
    )


def _parse_type35_shape(record_index: int, msg: Message, parent_uuid: str | None = None) -> ShapePath | None:
    """Parse a Type 35 geometric shape payload."""
    uuid = _uuid_from_message(msg)

    pos_x, pos_y = 0.0, 0.0
    f20 = msg.by_number(20)
    if f20 and isinstance(f20[0].value, bytes):
        m20 = try_decode_message(f20[0].value)
        if m20 and m20.by_number(1) and isinstance(m20.by_number(1)[0].value, bytes):
            m_pt = try_decode_message(m20.by_number(1)[0].value)
            if m_pt:
                fx = m_pt.by_number(1)
                fy = m_pt.by_number(2)
                pos_x = fx[0].fixed_float() if fx else 0.0
                pos_y = fy[0].fixed_float() if fy else 0.0

    w, h = 0.0, 0.0
    f21_size = msg.by_number(21)
    if f21_size and isinstance(f21_size[0].value, bytes):
        m21 = try_decode_message(f21_size[0].value)
        if m21 and m21.by_number(2) and isinstance(m21.by_number(2)[0].value, bytes):
            m_sz = try_decode_message(m21.by_number(2)[0].value)
            if m_sz:
                fw = m_sz.by_number(1)
                fh = m_sz.by_number(2)
                w = fw[0].fixed_float() if fw else 0.0
                h = fh[0].fixed_float() if fh else 0.0

    if w <= 0.0 or h <= 0.0:
        return None

    color_hex, alpha, fill_alpha = "#1e1b1b", 1.0, 0.0
    f30 = msg.by_number(30)
    if f30 and isinstance(f30[0].value, bytes):
        m30 = try_decode_message(f30[0].value)
        if m30 and m30.by_number(1) and isinstance(m30.by_number(1)[0].value, bytes):
            m_c = try_decode_message(m30.by_number(1)[0].value)
            if m_c and m_c.by_number(1) and isinstance(m_c.by_number(1)[0].value, bytes):
                m_rgb = try_decode_message(m_c.by_number(1)[0].value)
                if m_rgb:
                    r = m_rgb.by_number(1)
                    g = m_rgb.by_number(2)
                    b = m_rgb.by_number(3)
                    if m_rgb.by_number(4):
                        parsed_alpha = m_rgb.by_number(4)[0].fixed_float()
                        if parsed_alpha is not None:
                            # fill_alpha controls fill opacity only; do NOT copy to alpha (stroke opacity)
                            fill_alpha = max(0.0, min(1.0, parsed_alpha))
                    if r and g and b:
                        cr = min(255, max(0, int(round((r[0].fixed_float() or 0) * 255.0))))
                        cg = min(255, max(0, int(round((g[0].fixed_float() or 0) * 255.0))))
                        cb = min(255, max(0, int(round((b[0].fixed_float() or 0) * 255.0))))
                        color_hex = f"#{cr:02x}{cg:02x}{cb:02x}"

    stroke_width = 1.0
    dash_pattern: tuple[float, ...] | None = None
    f31 = msg.by_number(31)
    if f31 and isinstance(f31[0].value, bytes):
        m31 = try_decode_message(f31[0].value)
        if m31:
            if m31.by_number(1):
                stroke_width = m31.by_number(1)[0].fixed_float() or 1.0
            f31_2 = m31.by_number(2)
            if f31_2 and isinstance(f31_2[0].value, bytes):
                m2 = try_decode_message(f31_2[0].value)
                if m2 and m2.by_number(2) and isinstance(m2.by_number(2)[0].value, bytes):
                    m_dash = try_decode_message(m2.by_number(2)[0].value)
                    if m_dash:
                        d_vals = [sf.fixed_float() for sf in m_dash.fields if sf.fixed_float() is not None]
                        if d_vals:
                            dash_pattern = tuple(d_vals)
            if m31.by_number(3) and isinstance(m31.by_number(3)[0].value, bytes):
                m3 = try_decode_message(m31.by_number(3)[0].value)
                if m3 and m3.by_number(1) and isinstance(m3.by_number(1)[0].value, bytes):
                    m1 = try_decode_message(m3.by_number(1)[0].value)
                    if m1 and m1.by_number(4):
                        # Stroke color alpha is the authoritative stroke opacity
                        a_val = m1.by_number(4)[0].fixed_float()
                        if a_val is not None:
                            alpha = max(0.0, min(1.0, a_val))
    # Fill detection: fill_alpha > 0 means the fill color field with opacity was present
    is_filled = fill_alpha > 0.0

    # Generic Geometry & Shape Type Detection from tag 22
    norm_pts = []
    shape_type = "rectangle"
    corner_radius = 0.0

    f22 = msg.by_number(22)
    if f22 and isinstance(f22[0].value, bytes):
        m22 = try_decode_message(f22[0].value)
        if m22:
            if m22.by_number(3) and isinstance(m22.by_number(3)[0].value, bytes):
                m3 = try_decode_message(m22.by_number(3)[0].value)
                if m3 and m3.by_number(1) and isinstance(m3.by_number(1)[0].value, bytes):
                    m1 = try_decode_message(m3.by_number(1)[0].value)
                    if m1:
                        for item in m1.by_number(1):
                            if isinstance(item.value, bytes):
                                m_pt = try_decode_message(item.value)
                                if m_pt:
                                    f_inner = m_pt.by_number(1)
                                    if f_inner and isinstance(f_inner[0].value, bytes):
                                        m_xy = try_decode_message(f_inner[0].value)
                                        if m_xy:
                                            px = m_xy.by_number(1)[0].fixed_float() if m_xy.by_number(1) else 0.0
                                            py = m_xy.by_number(2)[0].fixed_float() if m_xy.by_number(2) else 0.0
                                            norm_pts.append((px, py))
                                    if m_pt.by_number(3):
                                        r_val = m_pt.by_number(3)[0].fixed_float()
                                        if r_val is not None:
                                            corner_radius = r_val
                if norm_pts:
                    shape_type = "polygon"
            elif m22.by_number(2):
                shape_type = "ellipse"
            elif m22.by_number(1) and isinstance(m22.by_number(1)[0].value, bytes):
                m1 = try_decode_message(m22.by_number(1)[0].value)
                if m1 and m1.by_number(1):
                    r_val = m1.by_number(1)[0].fixed_float() or 0.0
                    if r_val >= 50.0:
                        shape_type = "capsule"
                    else:
                        shape_type = "rectangle"
                        corner_radius = r_val

    cx = pos_x + w / 2.0
    cy = pos_y + h / 2.0
    rx = w / 2.0
    ry = h / 2.0

    if shape_type == "ellipse":
        steps = 144
        pts = [(cx + rx * math.cos(2 * math.pi * i / steps), cy + ry * math.sin(2 * math.pi * i / steps)) for i in range(steps)]
        pts.append(pts[0])
    elif shape_type == "capsule":
        left, top, right, bottom = pos_x, pos_y, pos_x + w, pos_y + h
        pts = [(left, top), (right, top), (right, bottom), (left, bottom), (left, top)]
    elif shape_type == "polygon" and norm_pts:
        pts = [(pos_x + nx * w, pos_y + ny * h) for nx, ny in norm_pts]
        pts.append(pts[0])
    else:
        left, top, right, bottom = pos_x, pos_y, pos_x + w, pos_y + h
        pts = [(left, top), (right, top), (right, bottom), (left, bottom), (left, top)]
        shape_type = "rectangle"

    return ShapePath(
        record_index=record_index,
        uuid=uuid,
        points=tuple(pts),
        stroke_width=stroke_width,
        field_numbers=(1, 2, 8, 9, 14, 16),
        color_hex=color_hex,
        alpha=alpha,
        fill_alpha=fill_alpha,
        shape_type=shape_type,
        cx=cx,
        cy=cy,
        rx=rx,
        ry=ry,
        rotation=0.0,
        is_filled=is_filled,
        dash_pattern=dash_pattern,
        corner_radius=corner_radius,
        parent_uuid=parent_uuid,
    )


def parse_shape_record(record_index: int, record: Message, parent_uuid: str | None = None) -> ShapePath | None:
    """Parse explicit field-9, field-21, or field-22 geometry used by GoodNotes shape/line records."""
    f22 = record.by_number(22)
    if f22 and isinstance(f22[0].value, bytes):
        msg22 = try_decode_message(f22[0].value)
        if msg22 and msg22.by_number(2) and msg22.by_number(2)[0].value == 31:
            t31 = _parse_type31_shape(record_index, msg22, parent_uuid=parent_uuid)
            if t31 is not None:
                return t31

    f21 = record.by_number(21)
    if f21 and isinstance(f21[0].value, bytes):
        # Type 35 stores both text boxes and geometric shapes in the same envelope.
        # Only suppress a shape when the dedicated text parser can actually decode
        # text from this exact record; empty/metadata-only bv41 payloads are kept.
        from .text import parse_text_elements

        if not parse_text_elements([record]):
            msg21 = try_decode_message(f21[0].value)
            if msg21:
                t35 = _parse_type35_shape(record_index, msg21, parent_uuid=parent_uuid)
                if t35 is not None:
                    return t35

    field7 = record.by_number(7)
    if not field7 or not isinstance(field7[0].value, bytes):
        return None

    outer = try_decode_message(field7[0].value)
    if outer is None:
        return None

    f22_outer = outer.by_number(22)
    if f22_outer and isinstance(f22_outer[0].value, bytes):
        msg22 = try_decode_message(f22_outer[0].value)
        if msg22 and msg22.by_number(2) and msg22.by_number(2)[0].value == 31:
            t31 = _parse_type31_shape(record_index, msg22, parent_uuid=parent_uuid)
            if t31 is not None:
                return t31

    f21_outer = outer.by_number(21)
    if f21_outer and isinstance(f21_outer[0].value, bytes):
        msg21 = try_decode_message(f21_outer[0].value)
        if msg21:
            t35 = _parse_type35_shape(record_index, msg21, parent_uuid=parent_uuid)
            if t35 is not None:
                return t35

    field9 = outer.by_number(9)
    if not field9 or not isinstance(field9[0].value, bytes):
        return None
    shape_msg = try_decode_message(field9[0].value)
    if shape_msg is None:
        return None

    geom_data = _parse_geometry_from_field9(shape_msg)

    if len(geom_data["points"]) < 2:
        return None

    dx, dy = extract_move_offset_from_message(outer)
    if dx == 0.0 and dy == 0.0:
        dx, dy = extract_move_offset_from_message(record)

    points = geom_data["points"]
    cx = geom_data["cx"]
    cy = geom_data["cy"]

    if dx != 0.0 or dy != 0.0:
        points = tuple((x + dx, y + dy) for x, y in points)
        if cx is not None:
            cx += dx
        if cy is not None:
            cy += dy

    width_fields = shape_msg.by_number(15)
    stroke_width = width_fields[0].fixed_float() if width_fields else 1.0
    if stroke_width is None:
        stroke_width = 1.0

    color_hex, alpha = "#1e1b1b", 1.0
    field4 = outer.by_number(4)
    if field4 and isinstance(field4[0].value, bytes):
        try:
            color_msg = decode_message(field4[0].value)
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
            color_hex = f"#{r_int:02x}{g_int:02x}{b_int:02x}"
            alpha = a_val
        except Exception:
            pass

    return ShapePath(
        record_index=record_index,
        uuid=_uuid_from_message(outer),
        points=points,
        stroke_width=stroke_width,
        field_numbers=tuple(field.number for field in shape_msg.fields),
        color_hex=color_hex,
        alpha=alpha,
        shape_type=geom_data["shape_type"],
        cx=cx,
        cy=cy,
        rx=geom_data["rx"],
        ry=geom_data["ry"],
        rotation=geom_data["rotation"],
        is_filled=False,
        parent_uuid=parent_uuid,
    )