"""Tests for PDF background to SVG rendering module."""
import base64
import io
import unittest
from PIL import Image
from goodnotes_re.pdf import render_pdf_page_to_svg, resolve_svg_image_masks


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

    def test_resolve_svg_image_masks(self) -> None:
        mask_im = Image.new("L", (10, 10), 128)
        mask_buf = io.BytesIO()
        mask_im.save(mask_buf, format="PNG")
        mask_b64 = base64.b64encode(mask_buf.getvalue()).decode("ascii")

        src_im = Image.new("RGB", (10, 10), (255, 0, 0))
        src_buf = io.BytesIO()
        src_im.save(src_buf, format="PNG")
        src_b64 = base64.b64encode(src_buf.getvalue()).decode("ascii")

        sample_svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">'
            '<defs>'
            '<mask id="test_mask_1">'
            f'<image xlink:href="data:image/png;base64,{mask_b64}"/>'
            '</mask>'
            '</defs>'
            '<g mask="url(#test_mask_1)">'
            f'<image xlink:href="data:image/png;base64,{src_b64}"/>'
            '</g>'
            '</svg>'
        )

        resolved = resolve_svg_image_masks(sample_svg)
        self.assertNotIn("test_mask_1", resolved)
        self.assertNotIn("mask=", resolved)
        self.assertIn("data:image/png;base64,", resolved)


if __name__ == "__main__":
    unittest.main()

