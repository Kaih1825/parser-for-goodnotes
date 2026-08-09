"""PDF background rendering helper for GoodNotes export."""
from __future__ import annotations

import re


def render_pdf_page_to_svg(
    pdf_bytes: bytes,
    page_index: int = 0,
    width: float | None = None,
    height: float | None = None,
    id_prefix: str | None = None,
    fragment: bool = False,
) -> str | None:
    """Render a single PDF page to SVG while isolating generated resource IDs."""
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

        # PyMuPDF reuses generic IDs such as ``clip_1`` in every SVG it
        # generates. SVG IDs are document-global, so embedded PDF SVGs can
        # otherwise collide and apply the wrong clipping path to later objects.
        if id_prefix:
            safe_prefix = re.sub(r"[^A-Za-z0-9_.-]", "_", id_prefix)
            declared_ids = set(re.findall(r'\bid=["\']([A-Za-z_][A-Za-z0-9_.:-]*)["\']', cleaned))
            for old in declared_ids:
                new = f"{safe_prefix}_{old}"
                cleaned = re.sub(
                    rf'(\bid=["\']){re.escape(old)}(["\'])',
                    rf'\g<1>{new}\g<2>',
                    cleaned,
                )
                cleaned = cleaned.replace(f"#{old}", f"#{new}")
        
        # PDF soft masks can use either alpha or luminance semantics. PyMuPDF
        # emits SVG masks using the SVG default (luminance), which is wrong for
        # PDF masks declared with ``/S /Alpha``. Preserve the PDF mask semantics
        # explicitly so opaque black mask paths remain visible.
        if b"/S /Alpha" in pdf_bytes and "<mask" in cleaned:
            cleaned = re.sub(
                r'(<mask\b[^>]*)(>)',
                r'\1 mask-type="alpha"\2',
                cleaned,
            )

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
