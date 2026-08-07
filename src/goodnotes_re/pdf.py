"""PDF background rendering helper for GoodNotes export."""
from __future__ import annotations

import re


def render_pdf_page_to_svg(pdf_bytes: bytes, page_index: int = 0, width: float | None = None, height: float | None = None) -> str | None:
    """Render a single page of PDF bytes to SVG string using PyMuPDF (fitz)."""
    try:
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if len(doc) == 0:
            return None
        target_idx = min(max(0, page_index), len(doc) - 1)
        page = doc[target_idx]
        svg_code = page.get_svg_image(matrix=fitz.Identity, text_as_path=True)
        if not svg_code:
            return None
        
        # Clean XML header / DOCTYPE
        lines = []
        for line in svg_code.splitlines():
            line_strip = line.strip()
            if line_strip.startswith("<?xml") or line_strip.startswith("<!DOCTYPE"):
                continue
            lines.append(line)
        cleaned = "\n".join(lines).strip()
        
        if width is not None and height is not None and cleaned.startswith("<svg"):
            end_idx = cleaned.find(">")
            if end_idx != -1:
                opening_tag = cleaned[:end_idx]
                rest = cleaned[end_idx:]
                tag_cleaned = re.sub(r'\s*\b(x|y|width|height|preserveAspectRatio)\s*=\s*"[^"]*"', '', opening_tag)
                tag_cleaned = re.sub(r"\s*\b(x|y|width|height|preserveAspectRatio)\s*=\s*'[^']*'", '', tag_cleaned)
                new_tag = f'{tag_cleaned} x="0" y="0" width="{width:.2f}" height="{height:.2f}" preserveAspectRatio="none"'
                return new_tag + rest
        
        return cleaned
    except Exception:
        return None
