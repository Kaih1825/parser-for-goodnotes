"""PDF background rendering helper for GoodNotes export."""
from __future__ import annotations

import re


def resolve_svg_image_masks(svg_text: str) -> str:
    """Resolve SVG image masks by merging luminance/grayscale masks directly into RGBA PNGs.

    PyMuPDF exports PDF images with /SMask into SVG as separate mask images and RGB images.
    Because CairoSVG and many other SVG-to-PDF renderers fail to process image-based luminance masks properly,
    baking them into native RGBA PNGs ensures universal transparency support in both vector SVG and exported PDF.
    """
    if "<mask" not in svg_text or "mask=" not in svg_text:
        return svg_text

    try:
        import base64
        import io
        from PIL import Image
    except ImportError:
        return svg_text

    mask_pattern = re.compile(
        r'<mask\s+id=["\']([^"\']+)["\'][^>]*>(.*?)</mask>',
        re.DOTALL,
    )

    mask_data: dict[str, str] = {}
    for m in mask_pattern.finditer(svg_text):
        mask_id = m.group(1)
        mask_content = m.group(2)
        match = re.search(r'data:image/[^;]+;base64,([A-Za-z0-9+/=\s]+)', mask_content)
        if match:
            mask_data[mask_id] = match.group(1).replace('\n', '').replace('\r', '').replace(' ', '')

    if not mask_data:
        return svg_text

    modified_svg = svg_text

    for mask_id, clean_m_b64 in mask_data.items():
        # Handle <g ... mask="url(#mask_id)" ...> ... </g>
        usage_regex = re.compile(
            rf'<g\s+[^>]*\bmask=["\']url\(#{re.escape(mask_id)}\)["\'][^>]*>(.*?)</g>',
            re.DOTALL,
        )
        for usage_match in list(usage_regex.finditer(modified_svg)):
            usage_block = usage_match.group(0)
            inner_content = usage_match.group(1)

            base_img_match = re.search(
                r'xlink:href=["\']data:image/[^;]+;base64,([A-Za-z0-9+/=\s]+)["\']|href=["\']data:image/[^;]+;base64,([A-Za-z0-9+/=\s]+)["\']',
                inner_content,
            )
            if not base_img_match:
                continue

            raw_b64 = base_img_match.group(1) or base_img_match.group(2)
            base_b64 = raw_b64.replace('\n', '').replace('\r', '').replace(' ', '')

            try:
                mask_raw = base64.b64decode(clean_m_b64)
                base_raw = base64.b64decode(base_b64)

                mask_img = Image.open(io.BytesIO(mask_raw)).convert('L')
                base_img = Image.open(io.BytesIO(base_raw)).convert('RGB')

                if mask_img.size != base_img.size:
                    mask_img = mask_img.resize(base_img.size, Image.Resampling.BILINEAR)

                rgba_img = Image.merge('RGBA', (*base_img.split(), mask_img))

                out_buf = io.BytesIO()
                rgba_img.save(out_buf, format='PNG', optimize=True)
                new_b64 = base64.b64encode(out_buf.getvalue()).decode('ascii')

                new_usage_block = usage_block
                new_usage_block = re.sub(
                    rf'\s*\bmask=["\']url\(#{re.escape(mask_id)}\)["\']',
                    '',
                    new_usage_block,
                )
                new_usage_block = new_usage_block.replace(
                    base_img_match.group(0),
                    f'xlink:href="data:image/png;base64,{new_b64}"',
                )

                modified_svg = modified_svg.replace(usage_block, new_usage_block)
            except Exception:
                continue

        # Also handle direct <image ... mask="url(#mask_id)" ...>
        direct_img_regex = re.compile(
            rf'<image\s+[^>]*\bmask=["\']url\(#{re.escape(mask_id)}\)["\'][^>]*>',
            re.DOTALL,
        )
        for direct_match in list(direct_img_regex.finditer(modified_svg)):
            img_tag = direct_match.group(0)
            base_img_match = re.search(
                r'xlink:href=["\']data:image/[^;]+;base64,([A-Za-z0-9+/=\s]+)["\']|href=["\']data:image/[^;]+;base64,([A-Za-z0-9+/=\s]+)["\']',
                img_tag,
            )
            if not base_img_match:
                continue
            raw_b64 = base_img_match.group(1) or base_img_match.group(2)
            base_b64 = raw_b64.replace('\n', '').replace('\r', '').replace(' ', '')
            try:
                mask_raw = base64.b64decode(clean_m_b64)
                base_raw = base64.b64decode(base_b64)

                mask_img = Image.open(io.BytesIO(mask_raw)).convert('L')
                base_img = Image.open(io.BytesIO(base_raw)).convert('RGB')

                if mask_img.size != base_img.size:
                    mask_img = mask_img.resize(base_img.size, Image.Resampling.BILINEAR)

                rgba_img = Image.merge('RGBA', (*base_img.split(), mask_img))

                out_buf = io.BytesIO()
                rgba_img.save(out_buf, format='PNG', optimize=True)
                new_b64 = base64.b64encode(out_buf.getvalue()).decode('ascii')

                new_img_tag = re.sub(
                    rf'\s*\bmask=["\']url\(#{re.escape(mask_id)}\)["\']',
                    '',
                    img_tag,
                )
                new_img_tag = new_img_tag.replace(
                    base_img_match.group(0),
                    f'xlink:href="data:image/png;base64,{new_b64}"',
                )
                modified_svg = modified_svg.replace(img_tag, new_img_tag)
            except Exception:
                continue

        # Remove the <mask id="mask_id">...</mask> definition from defs
        modified_svg = re.sub(
            rf'<mask\s+id=["\']{re.escape(mask_id)}["\'][^>]*>.*?</mask>\s*',
            '',
            modified_svg,
            flags=re.DOTALL,
        )

    return modified_svg


def render_pdf_page_to_svg(
    pdf_bytes: bytes,
    page_index: int = 0,
    width: float | None = None,
    height: float | None = None,
    id_prefix: str | None = None,
    fragment: bool = False,
) -> str | None:
    """Render a single PDF page directly to clean SVG."""
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

        # Isolate SVG element IDs to avoid collisions when embedding multiple pages
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

        # Resolve image masks into single transparent RGBA PNGs
        cleaned = resolve_svg_image_masks(cleaned)

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

