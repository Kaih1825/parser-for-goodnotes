from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from goodnotes_re.cli import diff_main, export_json_main, export_svg_main, inspect_main


def resolve_sample(name: str) -> Path:
    p = Path("samples") / name
    return p if p.exists() else Path(name)


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dataset_file = resolve_sample("Teat.goodnotes")

    def test_inspect_cli(self) -> None:
        if self.dataset_file.exists():
            code = inspect_main([str(self.dataset_file)])
            self.assertEqual(code, 0)

    def test_export_json_cli(self) -> None:
        if self.dataset_file.exists():
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
                out_path = Path(tmp.name)
            try:
                code = export_json_main([str(self.dataset_file), "-o", str(out_path)])
                self.assertEqual(code, 0)
                self.assertTrue(out_path.exists())
                self.assertGreater(out_path.stat().st_size, 0)
            finally:
                if out_path.exists():
                    out_path.unlink()

    def test_export_svg_cli(self) -> None:
        if self.dataset_file.exists():
            with tempfile.TemporaryDirectory() as tmp_dir:
                code = export_svg_main([str(self.dataset_file), "-o", tmp_dir])
                self.assertEqual(code, 0)
                svg_files = list(Path(tmp_dir).glob("*.svg"))
                self.assertGreater(len(svg_files), 0)

    def test_export_svg_no_fill_cli(self) -> None:
        if self.dataset_file.exists():
            with tempfile.TemporaryDirectory() as tmp_dir:
                code = export_svg_main([str(self.dataset_file), "-o", tmp_dir, "--no-fill"])
                self.assertEqual(code, 0)
                svg_files = list(Path(tmp_dir).glob("*.svg"))
                self.assertGreater(len(svg_files), 0)
                # Ensure no polygon paths have fill-opacity or color fill (should be fill="none")
                for path in svg_files:
                    content = path.read_text(encoding="utf-8")
                    if "<path" in content:
                        # Check that filled paths in shapes are "none"
                        self.assertNotIn('fill-opacity="0.15"', content)

    def test_export_svg_sticky_note_state_cli(self) -> None:
        sticker_file = resolve_sample("sticker.goodnotes")
        if sticker_file.exists():
            with tempfile.TemporaryDirectory() as tmp_dir:
                code = export_svg_main([str(sticker_file), "-o", tmp_dir, "-s", "open"])
                self.assertEqual(code, 0)
                svg_content = (Path(tmp_dir) / "page_1_notes_B48FFFED-D3E2-4440-809D-EE60482744C1.svg").read_text(encoding="utf-8")
                # When forced open, BOTH notes should be expanded, so 2 Expanded comments
                self.assertEqual(svg_content.count("Sticky Note (Expanded)"), 2)
                self.assertEqual(svg_content.count("Sticky Note (Folded)"), 0)

            with tempfile.TemporaryDirectory() as tmp_dir:
                code = export_svg_main([str(sticker_file), "-o", tmp_dir, "-s", "close"])
                self.assertEqual(code, 0)
                svg_content = (Path(tmp_dir) / "page_1_notes_B48FFFED-D3E2-4440-809D-EE60482744C1.svg").read_text(encoding="utf-8")
                # When forced closed, BOTH notes should be folded, so 2 Folded comments
                self.assertEqual(svg_content.count("Sticky Note (Folded)"), 2)
                self.assertEqual(svg_content.count("Sticky Note (Expanded)"), 0)


if __name__ == "__main__":
    unittest.main()
