"""Tests for PDF background to SVG rendering module."""
import unittest
from goodnotes_re.pdf import render_pdf_page_to_svg


class PdfRenderingTests(unittest.TestCase):
    def test_render_pdf_page_to_svg_invalid_bytes(self) -> None:
        result = render_pdf_page_to_svg(b"invalid pdf bytes")
        self.assertIsNone(result)

    def test_render_pdf_page_to_svg_valid_pdf(self) -> None:
        try:
            import fitz
            doc = fitz.open()
            page = doc.new_page(width=500, height=700)
            page.draw_rect(fitz.Rect(10, 10, 100, 100), color=(1, 0, 0))
            pdf_bytes = doc.tobytes()
            
            svg = render_pdf_page_to_svg(pdf_bytes, page_index=0, width=500, height=700)
            self.assertIsNotNone(svg)
            self.assertIn("<svg", svg)
            self.assertIn('width="500.00"', svg)
            self.assertIn('height="700.00"', svg)
        except ImportError:
            self.skipTest("fitz (PyMuPDF) is not installed.")


if __name__ == "__main__":
    unittest.main()
