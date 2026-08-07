import tempfile
import unittest
from pathlib import Path

from goodnotes_re.element import StickyNote
from goodnotes_re.export import write_svg
from goodnotes_re.page import Page, PageDimensions
from goodnotes_re.shape import ShapePath
from goodnotes_re.stroke import Stroke, StrokePoint


class MockDocument:
    def __init__(self, page: Page):
        self._page = page

    def pages(self) -> list[Page]:
        return [self._page]

    def member_names(self) -> set[str]:
        return set()

    def read(self, path: str) -> bytes:
        return b""


class ExportRefactorTests(unittest.TestCase):
    def test_arrowhead_marker_dynamic_color(self) -> None:
        shape = ShapePath(
            record_index=0,
            uuid="shape-1",
            points=((10.0, 10.0), (100.0, 100.0)),
            stroke_width=2.0,
            field_numbers=(1, 2),
            color_hex="#FF0000",
            start_arrow=1,
            end_arrow=2,
            shape_type="polyline",
        )
        page = Page(index=0, uuid="p1", member_path="pages/1", dimensions=PageDimensions(612.0, 792.0), shapes=[shape])
        doc = MockDocument(page)
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_svg(doc, tmpdir)
            content = Path(paths[0]).read_text(encoding="utf-8")
            self.assertIn('id="arrow-start-open-FF0000"', content)
            self.assertIn('id="arrow-end-filled-FF0000"', content)
            self.assertIn('marker-start="url(#arrow-start-open-FF0000)"', content)

    def test_sticky_note_fold_opacity_overlay(self) -> None:
        note = StickyNote(
            uuid="note-1",
            x=50.0,
            y=50.0,
            color_hex="#FFC0CB",  # Pink note
            is_open=False,
        )
        page = Page(index=0, uuid="p1", member_path="pages/1", dimensions=PageDimensions(612.0, 792.0), sticky_notes=(note,))
        doc = MockDocument(page)
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_svg(doc, tmpdir)
            content = Path(paths[0]).read_text(encoding="utf-8")
            self.assertIn('fill="#FFC0CB"', content)
            self.assertIn('fill="black" fill-opacity="0.18"', content)

    def test_thick_rectangle_preserves_rounded_corners(self) -> None:
        shape = ShapePath(
            record_index=0,
            uuid="rect-thick",
            points=((10.0, 10.0), (100.0, 10.0), (100.0, 100.0), (10.0, 100.0), (10.0, 10.0)),
            stroke_width=5.0,
            field_numbers=(1, 2),
            color_hex="#000000",
            shape_type="rectangle",
            corner_radius=6.0,
        )
        page = Page(index=0, uuid="p1", member_path="pages/1", dimensions=PageDimensions(612.0, 792.0), shapes=[shape])
        doc = MockDocument(page)
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_svg(doc, tmpdir)
            content = Path(paths[0]).read_text(encoding="utf-8")
            self.assertIn('rx="3.27"', content)  # rounded corner rx preserved

    def test_single_point_dot_stroke(self) -> None:
        stroke = Stroke(
            uuid="dot-1",
            points=(StrokePoint(50.0, 50.0, pressure=1.5),),
            color_hex="#00FF00",
            alpha=1.0,
            width=2.0,
            is_dot=True,
            is_highlighter=False,
            tpl_format="vu",
        )
        page = Page(index=0, uuid="p1", member_path="pages/1", dimensions=PageDimensions(612.0, 792.0), strokes=[stroke])
        doc = MockDocument(page)
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_svg(doc, tmpdir)
            content = Path(paths[0]).read_text(encoding="utf-8")
            self.assertIn('<circle cx=', content)
            self.assertIn('fill="#00FF00"', content)


    def test_image_layer_beneath_strokes(self) -> None:
        from goodnotes_re.element import ImageElement

        img = ImageElement(uuid="img-1", attachment_uuid="att-1", x=0, y=0, width=100, height=100)
        stroke = Stroke(
            uuid="stroke-1",
            points=(StrokePoint(10.0, 10.0, 1.0), StrokePoint(20.0, 20.0, 1.0)),
            color_hex="#000000",
            alpha=1.0,
            width=2.0,
            is_dot=False,
            is_highlighter=False,
            tpl_format="vu",
        )
        page = Page(index=0, uuid="p1", member_path="pages/1", dimensions=PageDimensions(612.0, 792.0), strokes=[stroke], image_elements=(img,))

        class ImageMockDocument(MockDocument):
            def member_names(self) -> set[str]:
                return {"attachments/att-1"}

            def read(self, path: str) -> bytes:
                return b"\xff\xd8\xff\xe0"  # JPEG header

        doc = ImageMockDocument(page)
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_svg(doc, tmpdir)
            content = Path(paths[0]).read_text(encoding="utf-8")
            img_pos = content.find("Image Attachment:")
            stroke_pos = content.find("<path d=")
            self.assertNotEqual(img_pos, -1)
            self.assertNotEqual(stroke_pos, -1)
            self.assertLess(img_pos, stroke_pos)


if __name__ == "__main__":
    unittest.main()

