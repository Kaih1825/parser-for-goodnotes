from __future__ import annotations

from pathlib import Path
import unittest
import zipfile

from goodnotes_re.archive import GoodNotesDocument
from goodnotes_re.export import write_json


class ArchiveTests(unittest.TestCase):
    def test_archive_inventory_and_json_export(self) -> None:
        # TemporaryDirectory avoids pytest-only fixtures.
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "sample.goodnotes"
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr("schema.pb", b"\x08#")
                archive.writestr("notes/page", b"\x0a\x02ok")
            with GoodNotesDocument.open(source) as document:
                self.assertEqual(document.decode("schema.pb").fields[0].value, 35)
                output = root / "out.json"
                write_json(document, output)
            self.assertIn('"notes/page"', output.read_text(encoding="utf-8"))

    def test_teat_goodnotes_page_backgrounds(self) -> None:
        sample = Path("samples/Teat.goodnotes")
        if not sample.exists():
            self.skipTest("Teat.goodnotes not present")
        with GoodNotesDocument.open(sample) as document:
            pages = document.pages()
            self.assertEqual(len(pages), 3)
            # Page 1 & Page 2 share white template PDF; Page 3 has black template PDF
            self.assertEqual(pages[0].background_attachment_path, "attachments/5B0C9E9F-C00D-4ED5-9F5F-2D5ECB13A2FD")
            self.assertEqual(pages[1].background_attachment_path, "attachments/5B0C9E9F-C00D-4ED5-9F5F-2D5ECB13A2FD")
            self.assertEqual(pages[2].background_attachment_path, "attachments/2BFD1B79-172D-41E7-97DC-4798F79625B0")

