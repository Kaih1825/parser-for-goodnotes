from __future__ import annotations

from pathlib import Path
import unittest
from goodnotes_re.stroke import StrokePoint, build_stroke_ribbon, extract_color_from_trailer, uint32_to_float32
from goodnotes_re.archive import GoodNotesDocument


def resolve_sample(name: str) -> Path:
    p = Path("samples") / name
    return p if p.exists() else Path(name)


class StrokeTests(unittest.TestCase):
    def test_uint32_to_float32(self) -> None:
        self.assertAlmostEqual(uint32_to_float32(0x3F800000), 1.0, places=5)
        self.assertAlmostEqual(uint32_to_float32(0x00000000), 0.0, places=5)

    def test_extract_color_from_trailer(self) -> None:
        # Protobuf trailer containing field 4 (tag 0x22, len 20) with RGBA floats
        # tag 0x0d: 1.0, tag 0x15: 0.0, tag 0x1d: 0.0, tag 0x25: 1.0
        color_msg_bytes = b"\x0d\x00\x00\x80?\x15\x00\x00\x00\x00\x1d\x00\x00\x00\x00\x25\x00\x00\x80?"
        trailer = b"\x22\x14" + color_msg_bytes
        hex_color, alpha = extract_color_from_trailer(trailer)
        self.assertEqual(hex_color, "#ff0000")
        self.assertEqual(alpha, 1.0)

    def test_build_stroke_ribbon_single_point(self) -> None:
        pts = [StrokePoint(100.0, 200.0, 1.0)]
        d = build_stroke_ribbon(pts, default_width=2.0, scale=1.0)
        self.assertIsNotNone(d)
        self.assertTrue(d.startswith("M "))

    def test_build_stroke_ribbon_multiple_points(self) -> None:
        pts = [StrokePoint(10.0, 10.0, 1.0), StrokePoint(20.0, 30.0, 1.0), StrokePoint(40.0, 50.0, 1.0)]
        d = build_stroke_ribbon(pts, default_width=2.0, scale=1.0)
        self.assertIsNotNone(d)
        self.assertTrue(d.startswith("M "))
        self.assertTrue(d.endswith("Z"))

    def test_ooo_strokes_have_variable_pressure(self) -> None:
        sample = resolve_sample("ooo.goodnotes")
        if not sample.exists():
            self.skipTest("ooo.goodnotes not present")
        with GoodNotesDocument.open(sample) as document:
            page = document.pages()[0]
            self.assertGreater(len(page.strokes), 0)
            pressures = [pressure for stroke in page.strokes for pressure in (point.pressure for point in stroke.points)]
            self.assertGreater(max(pressures) - min(pressures), 0.5)


    def test_dot_goodnotes_dash_and_dotted_patterns(self) -> None:
        sample = resolve_sample("dot.goodnotes")
        if not sample.exists():
            self.skipTest("dot.goodnotes not present")
        with GoodNotesDocument.open(sample) as document:
            page = document.pages()[0]
            self.assertEqual(len(page.strokes), 3)
            self.assertEqual(len(page.shapes), 4)
            # Check strokes have valid dash_pattern
            for stroke in page.strokes:
                self.assertIsNotNone(stroke.dash_pattern)
                self.assertEqual(len(stroke.dash_pattern), 2)
            # Check shapes have valid dash_pattern
    def test_era_goodnotes_erased_strokes_render_cleanly(self) -> None:
        sample = resolve_sample("era.goodnotes")
        if not sample.exists():
            self.skipTest("era.goodnotes not present")
        with GoodNotesDocument.open(sample) as document:
            page = document.pages()[0]
            self.assertGreater(len(page.strokes), 0)
            for stroke in page.strokes:
                self.assertGreater(len(stroke.points), 0)
                ribbon_d = build_stroke_ribbon(
                    stroke.points,
                    default_width=stroke.width,
                    outline_polygons=stroke.outline_polygons,
                )
                self.assertIsNotNone(ribbon_d)
                self.assertTrue(ribbon_d.startswith("M "))
                self.assertTrue(ribbon_d.endswith("Z"))


if __name__ == "__main__":
    unittest.main()
