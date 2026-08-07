"""PDF background rendering helper for GoodNotes export."""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


def render_pdf_page_to_png(pdf_bytes: bytes, page_index: int = 0, dpi: float = 150.0) -> bytes | None:
    """Render a single page of PDF bytes to PNG bytes using available python packages or native Swift helper."""
    # 1. Try pypdfium2 if available
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(pdf_bytes)
        target_idx = min(max(0, page_index), len(pdf) - 1)
        page = pdf[target_idx]
        image = page.render(scale=dpi / 72.0).to_pil()
        import io
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        pass

    # 2. Try fitz (PyMuPDF) if available
    try:
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        target_idx = min(max(0, page_index), len(doc) - 1)
        page = doc[target_idx]
        pix = page.get_pixmap(dpi=int(dpi))
        return pix.tobytes("png")
    except Exception:
        pass

    # 3. Try compiled macOS native swift renderer
    try:
        bin_path = Path(__file__).parent / "bin" / "render_pdf"
        if not bin_path.exists():
            bin_path.parent.mkdir(parents=True, exist_ok=True)
            swift_src = Path(__file__).parent / "render_pdf.swift"
            if swift_src.exists():
                cache_dir = bin_path.parent / ".cache"
                cache_dir.mkdir(parents=True, exist_ok=True)
                subprocess.run(
                    ["swiftc", "-module-cache-path", str(cache_dir), str(swift_src), "-o", str(bin_path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )

        if bin_path.exists():
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
                tmp_pdf.write(pdf_bytes)
                tmp_pdf_path = tmp_pdf.name
            tmp_png_path = tmp_pdf_path + ".png"
            try:
                res = subprocess.run(
                    [str(bin_path), tmp_pdf_path, str(page_index), tmp_png_path, str(int(dpi))],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                if res.returncode == 0 and os.path.exists(tmp_png_path):
                    with open(tmp_png_path, "rb") as f:
                        png_bytes = f.read()
                    return png_bytes
            finally:
                if os.path.exists(tmp_pdf_path):
                    try:
                        os.remove(tmp_pdf_path)
                    except OSError:
                        pass
                if os.path.exists(tmp_png_path):
                    try:
                        os.remove(tmp_png_path)
                    except OSError:
                        pass
    except Exception:
        pass

    return None
