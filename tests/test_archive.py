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
