from pathlib import Path
import unittest

from goodnotes_re.archive import GoodNotesDocument
from goodnotes_re.text import extract_text, parse_text_elements, rtf_to_text
from goodnotes_re.wire import decode_message


def resolve_sample(name: str) -> Path:
    p = Path("samples") / name
    return p if p.exists() else Path(name)


class TextTests(unittest.TestCase):
    def test_extracts_rtf_cp950_hex_escapes(self) -> None:
        rtf = b"{\\rtf1 \\'a4\\'a4\\'a4\\'e5}"
        self.assertEqual(rtf_to_text(rtf), "中文")
        payload = b"\x0a" + bytes([len(rtf)]) + rtf
        fragments = tuple(extract_text(decode_message(payload)))
        self.assertEqual(fragments[0].format, "rtf")
        self.assertEqual(fragments[0].text, "中文")

    def test_muti_goodnotes_rich_text_and_images(self) -> None:
        sample = resolve_sample("muti.goodnotes")
        if not sample.exists():
            self.skipTest("muti.goodnotes not present")
        with GoodNotesDocument.open(sample) as document:
            page = document.pages()[0]
            # Verify text elements extracted
            self.assertGreaterEqual(len(page.text_elements), 10)
            texts = [te.text for te in page.text_elements]
            self.assertIn("Bold", texts)
            self.assertIn("Delete", texts)
            self.assertIn("台東", texts)
            self.assertIn("abc", texts)

            # Check specific formatting
            delete_elem = next(te for te in page.text_elements if te.text == "Delete")
            self.assertTrue(delete_elem.is_strikethrough)

            italic_elem = next(te for te in page.text_elements if te.text == "abc")
            self.assertTrue(italic_elem.is_italic)

            underline_elem = next(te for te in page.text_elements if te.text == "olala")
            self.assertTrue(underline_elem.is_underline)

            bullet_elem = next(te for te in page.text_elements if "dot" in te.text)
            self.assertEqual(bullet_elem.list_type, "bullet")

            numbered_elem = next(te for te in page.text_elements if "num1" in te.text)
            self.assertEqual(numbered_elem.list_type, "numbered")

            # Verify image elements extracted
            self.assertEqual(len(page.image_elements), 2)
            img1 = page.image_elements[0]
            self.assertGreater(img1.width, 0)
            self.assertGreater(img1.height, 0)

    def test_textbox_border_option(self) -> None:
        sample = resolve_sample("muti.goodnotes")
        if not sample.exists():
            self.skipTest("muti.goodnotes not present")
        import tempfile
        from goodnotes_re.export import write_svg
        with tempfile.TemporaryDirectory() as tmpdir:
            with GoodNotesDocument.open(sample) as document:
                written_close = write_svg(document, tmpdir, textbox_state="close")
                svg_close = written_close[0].read_text(encoding="utf-8")
                self.assertNotIn('stroke="#38BDF8"', svg_close)

                written_open = write_svg(document, tmpdir, textbox_state="open")
                svg_open = written_open[0].read_text(encoding="utf-8")
                self.assertIn('stroke="#38BDF8"', svg_open)


if __name__ == "__main__":
    unittest.main()
