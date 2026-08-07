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
    shape_type: str = "polygon"
    cx: float | None = None
    cy: float | None = None
    rx: float | None = None
    ry: float | None = None
    rotation: float = 0.0
    is_filled: bool = True
    dash_pattern: tuple[float, ...] | None = None
    start_arrow: bool = False
    end_arrow: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "record_index": self.record_index,
            "uuid": self.uuid,
            "points": [{"x": x, "y": y} for x, y in self.points],
            "stroke_width": self.stroke_width,
            "field_numbers": list(self.field_numbers),
            "color_hex": self.color_hex,
            "alpha": self.alpha,
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
        points: list[tuple[float, float]] = []
        for item_field in container.fields:
            if not isinstance(item_field.value, bytes):
                continue
            item = decode_message(item_field.value)
            pt = _extract_point(item)
            if pt:
                points.append(pt)
        
        # 若成功解析出點陣，則回傳。若無點位，則繼續往下嘗試 Tag 4 或 Tag 3
        if len(points) >= 2:
            geom["points"] = tuple(points)
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


def _parse_type31_shape(record_index: int, msg: Message) -> ShapePath | None:
    uuid = _uuid_from_message(msg)

    start_arrow = bool(msg.by_number(30) and msg.by_number(30)[0].value in (1, 2))
    end_arrow = bool(msg.by_number(31) and msg.by_number(31)[0].value in (1, 2))

    pts: list[tuple[float, float]] = []
    f21 = msg.by_number(21)
    if f21 and isinstance(f21[0].value, bytes):
        m21 = try_decode_message(f21[0].value)
        if m21:
            for sub_tag in [1, 2, 3, 4, 5]:
                fields = m21.by_number(sub_tag)
                if fields and isinstance(fields[0].value, bytes):
                    m_sub = try_decode_message(fields[0].value)
                    if m_sub:
                        for sf in m_sub.fields:
                            if isinstance(sf.value, bytes):
                                m_pt = try_decode_message(sf.value)
                                if m_pt and m_pt.by_number(1) and m_pt.by_number(2):
                                    fx = m_pt.by_number(1)[0].fixed_float()
                                    fy = m_pt.by_number(2)[0].fixed_float()
                                    if fx is not None and fy is not None:
                                        pts.append((fx, fy))

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
        shape_type="polyline" if len(pts) == 2 else "polygon",
        is_filled=False,
        dash_pattern=dash_pattern,
        start_arrow=start_arrow,
        end_arrow=end_arrow,
    )


def _parse_type35_shape(record_index: int, msg: Message) -> ShapePath | None:
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

    color_hex, alpha = "#1e1b1b", 1.0
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
                        a_val = m1.by_number(4)[0].fixed_float()
                        if a_val is not None:
                            alpha = a_val

    shape_subtype = 0
    f7 = msg.by_number(7)
    if f7 and isinstance(f7[0].value, bytes):
        m7 = try_decode_message(f7[0].value)
        if m7 and m7.by_number(1) and isinstance(m7.by_number(1)[0].value, bytes):
            m7_1 = try_decode_message(m7.by_number(1)[0].value)
            if m7_1 and m7_1.by_number(1):
                shape_subtype = int(m7_1.by_number(1)[0].value)
    
    is_filled = shape_subtype in range(5, 24)

    norm_pts = []
    f22 = msg.by_number(22)
    if f22 and isinstance(f22[0].value, bytes):
        m22 = try_decode_message(f22[0].value)
        if m22 and m22.by_number(3) and isinstance(m22.by_number(3)[0].value, bytes):
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

    cx = pos_x + w / 2.0
    cy = pos_y + h / 2.0
    rx = w / 2.0
    ry = h / 2.0

    if shape_subtype in (2, 3, 8, 9, 10, 12, 13):
        steps = 144
        pts = [(cx + rx * math.cos(2 * math.pi * i / steps), cy + ry * math.sin(2 * math.pi * i / steps)) for i in range(steps)]
        pts.append(pts[0])
        shape_type = "ellipse"
    elif norm_pts:
        pts = [(pos_x + nx * w, pos_y + ny * h) for nx, ny in norm_pts]
        pts.append(pts[0])
        shape_type = "polygon"
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
        shape_type=shape_type,
        cx=cx,
        cy=cy,
        rx=rx,
        ry=ry,
        rotation=0.0,
        is_filled=is_filled,
        dash_pattern=dash_pattern,
    )


def parse_shape_record(record_index: int, record: Message) -> ShapePath | None:
    """Parse explicit field-9, field-21, or field-22 geometry used by GoodNotes shape/line records."""
    f22 = record.by_number(22)
    if f22 and isinstance(f22[0].value, bytes):
        msg22 = try_decode_message(f22[0].value)
        if msg22 and msg22.by_number(2) and msg22.by_number(2)[0].value == 31:
            t31 = _parse_type31_shape(record_index, msg22)
            if t31 is not None:
                return t31

    f21 = record.by_number(21)
    if f21 and isinstance(f21[0].value, bytes):
        msg21 = try_decode_message(f21[0].value)
        if msg21:
            t35 = _parse_type35_shape(record_index, msg21)
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
            t31 = _parse_type31_shape(record_index, msg22)
            if t31 is not None:
                return t31

    f21_outer = outer.by_number(21)
    if f21_outer and isinstance(f21_outer[0].value, bytes):
        msg21 = try_decode_message(f21_outer[0].value)
        if msg21:
            t35 = _parse_type35_shape(record_index, msg21)
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
        is_filled=False
    )