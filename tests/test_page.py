from __future__ import annotations

from pathlib import Path
import unittest
import tempfile
from goodnotes_re.archive import GoodNotesDocument
from goodnotes_re.export import write_svg
from goodnotes_re.page import PageDimensions


def resolve_sample(name: str) -> Path:
    p = Path("samples") / name
    return p if p.exists() else Path(name)


class PageTests(unittest.TestCase):
    def test_dimensions_from_pdf_mediabox(self) -> None:
        pdf_content = b"%PDF-1.4 ... /MediaBox [ 0 0 455.04 588.45 ] ..."
        dims = PageDimensions.from_pdf_mediabox(pdf_content)
        self.assertAlmostEqual(dims.width, 455.04, places=2)
        self.assertAlmostEqual(dims.height, 588.45, places=2)
        self.assertFalse(dims.is_landscape)

    def test_dimensions_landscape(self) -> None:
        pdf_content = b"%PDF-1.4 ... /MediaBox [ 0 0 650.88 406.8 ] ..."
        dims = PageDimensions.from_pdf_mediabox(pdf_content)
        self.assertAlmostEqual(dims.width, 650.88, places=2)
        self.assertAlmostEqual(dims.height, 406.8, places=2)
        self.assertTrue(dims.is_landscape)

    def test_page_elements_capture_attachment_metadata(self) -> None:
        sample = resolve_sample("Teat.goodnotes")
        if not sample.exists():
            self.skipTest("Teat.goodnotes not present")
        with GoodNotesDocument.open(sample) as document:
            page = document.pages()[1]
            attachment_ids = {element.attachment_uuid for element in page.elements if element.attachment_uuid}
            self.assertIn("31BE4069-02E5-4C5D-BFF9-2A8DCBC744E9", attachment_ids)
            self.assertGreater(len(page.elements), 0)

    def test_page_shapes_are_parsed(self) -> None:
        sample = resolve_sample("Teat.goodnotes")
        if not sample.exists():
            self.skipTest("Teat.goodnotes not present")
        with GoodNotesDocument.open(sample) as document:
            page = document.pages()[0]
            self.assertGreater(len(page.shapes), 0)
            self.assertTrue(any(len(shape.points) == 2 for shape in page.shapes))

    def test_teat_shape_export_stays_open(self) -> None:
        sample = resolve_sample("Teat.goodnotes")
        if not sample.exists():
            self.skipTest("Teat.goodnotes not present")
        with tempfile.TemporaryDirectory() as tmpdir:
            with GoodNotesDocument.open(sample) as document:
                written = write_svg(document, tmpdir)
            svg_text = written[0].read_text(encoding="utf-8")
            shape_lines = [line for line in svg_text.splitlines() if 'fill="none"' in line and '<path d="M ' in line]
            self.assertTrue(shape_lines)
            self.assertTrue(all(' Z"' not in line for line in shape_lines))

    def test_tri_shapes_bounding_box(self) -> None:
        sample = resolve_sample("_tri.goodnotes")
        if not sample.exists():
            sample = resolve_sample("tri.goodnotes")
        if not sample.exists():
            self.skipTest("tri sample not present")
        with GoodNotesDocument.open(sample) as document:
            page = document.pages()[0]
            if sample.name == "_tri.goodnotes":
                self.assertEqual(len(page.shapes), 5)
                five_point_shapes = [s for s in page.shapes if len(s.points) == 5]
                self.assertEqual(len(five_point_shapes), 3)
            else:
                self.assertGreaterEqual(len(page.shapes), 2)

    def test_tri2_shape_move_offset(self) -> None:
        sample = resolve_sample("tri2.goodnotes")
        if not sample.exists():
            self.skipTest("tri2.goodnotes not present")
        with GoodNotesDocument.open(sample) as document:
            page = document.pages()[0]
            self.assertEqual(len(page.shapes), 2)
            # Find the moved red triangle (record_index=1, color #f33f3f)
            triangle = next((s for s in page.shapes if s.color_hex == "#f33f3f"), None)
            self.assertIsNotNone(triangle)
            if triangle:
                # With (dx=194.79, dy=3.62) offset applied, all x coordinates of the triangle should be > 200
                min_x = min(pt[0] for pt in triangle.points)
                self.assertGreater(min_x, 200.0)

    def test_sticker_sticky_notes(self) -> None:
        sample = resolve_sample("sticker.goodnotes")
        if not sample.exists():
            self.skipTest("sticker.goodnotes not present")
        with GoodNotesDocument.open(sample) as document:
            page = document.pages()[0]
            self.assertEqual(len(page.sticky_notes), 2)
            open_notes = [sn for sn in page.sticky_notes if sn.is_open]
            folded_notes = [sn for sn in page.sticky_notes if not sn.is_open]
            self.assertEqual(len(open_notes), 1)
            self.assertEqual(len(folded_notes), 1)
            self.assertEqual(open_notes[0].author, "KAI")
            self.assertEqual(open_notes[0].color_hex, "#FAE778")

        with tempfile.TemporaryDirectory() as tmpdir:
            with GoodNotesDocument.open(sample) as document:
                written = write_svg(document, tmpdir)
            svg_text = written[0].read_text(encoding="utf-8")
            self.assertIn("Sticky Note (Expanded)", svg_text)
            self.assertIn("Sticky Note (Folded)", svg_text)
            self.assertIn(">KAI<", svg_text)


if __name__ == "__main__":
    unittest.main()
