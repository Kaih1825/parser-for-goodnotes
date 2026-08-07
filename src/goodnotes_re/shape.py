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
                    
                    # 產生 144 邊形陣列，相容你的 gn-export-svg 工具
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
    """Decode the (dx, dy) translation GoodNotes attaches to a shape record
    (protobuf field 6, two fixed32 floats) after it has been repositioned with
    the lasso/selection tool.
    """
    field6 = msg.by_number(6)
    if field6 and isinstance(field6[0].value, bytes) and field6[0].value:
        try:
            offset_msg = decode_message(field6[0].value)
            f1 = offset_msg.by_number(1)
            f2 = offset_msg.by_number(2)
            dx = f1[0].fixed_float() if f1 else None
            dy = f2[0].fixed_float() if f2 else None
            return dx or 0.0, dy or 0.0
        except Exception:
            pass
    return 0.0, 0.0


def parse_shape_record(record_index: int, record: Message) -> ShapePath | None:
    """Parse the explicit field-9 geometry used by GoodNotes shape-like records."""
    field7 = record.by_number(7)
    if not field7 or not isinstance(field7[0].value, bytes):
        return None
    
    outer = try_decode_message(field7[0].value)
    if outer is None:
        return None
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
        rotation=geom_data["rotation"]
    )