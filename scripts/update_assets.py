#!/usr/bin/env python3
"""Automatically re-render assets/ex*.svg from assets/ex*.goodnotes."""
from __future__ import annotations

import re
import shutil
import sys
import tempfile
from pathlib import Path

from goodnotes_re.archive import GoodNotesDocument
from goodnotes_re.export import write_svg

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets"

ANIMATED_TOGGLE_CSS = """<style>
@keyframes gn-tape-body-anim {
  0%, 42%, 100% { fill-opacity: 1; }
  50%, 92% { fill-opacity: 0.22; }
}
@keyframes gn-tape-cover-anim {
  0%, 42%, 100% { opacity: 1; }
  50%, 92% { opacity: 0; }
}
@keyframes gn-sticky-closed-anim {
  0%, 42%, 100% { opacity: 1; }
  50%, 92% { opacity: 0; }
}
@keyframes gn-sticky-open-anim {
  0%, 42%, 100% { opacity: 0; }
  50%, 92% { opacity: 1; }
}
.gn-tape-body {
  animation: gn-tape-body-anim 3s ease-in-out infinite;
}
.gn-tape-shadow,
[data-tape-overlay] {
  animation: gn-tape-cover-anim 3s ease-in-out infinite;
}
.gn-sticky-closed {
  animation: gn-sticky-closed-anim 3s ease-in-out infinite;
}
.gn-sticky-open {
  animation: gn-sticky-open-anim 3s ease-in-out infinite;
}
</style>"""

_STICKY_FOLDED_RE = re.compile(
    r"(?:<!-- Sticky Note \(Folded\): .*? -->\n[^\n]+\n)+",
)
_STICKY_EXPANDED_RE = re.compile(
    r"(?:<!-- Sticky Note \(Expanded\): .*? -->\n(?:<(?:rect|text)[^\n]+\n)+)+",
)


def _build_animated_svg(closed_svg: str, open_svg: str) -> str:
    """Combine closed and open renders into a CSS-animated SVG toggling tape & sticky notes."""
    svg = closed_svg
    folded_match = _STICKY_FOLDED_RE.search(closed_svg)
    expanded_match = _STICKY_EXPANDED_RE.search(open_svg)
    if folded_match and expanded_match:
        combined_sticky = (
            f'<g class="gn-sticky-closed">\n{folded_match.group(0)}</g>\n'
            f'<g class="gn-sticky-open">\n{expanded_match.group(0)}</g>\n'
        )
        svg = svg[: folded_match.start()] + combined_sticky + svg[folded_match.end() :]

    # Inject animation CSS right after the opening <svg ...> tag
    svg = re.sub(r"(<svg\b[^>]*>)", rf"\1\n{ANIMATED_TOGGLE_CSS}", svg, count=1)
    return svg


def update_asset_svgs() -> int:
    if not ASSETS_DIR.exists():
        print(f"Assets directory not found at {ASSETS_DIR}", file=sys.stderr)
        return 1

    targets = sorted(ASSETS_DIR.glob("ex*.goodnotes"))
    if not targets:
        print(f"No ex*.goodnotes files found in {ASSETS_DIR}", file=sys.stderr)
        return 1

    updated_count = 0
    for gn_file in targets:
        stem = gn_file.stem  # e.g. 'ex1'
        svg_target = ASSETS_DIR / f"{stem}.svg"
        print(f"Re-rendering {gn_file.name} -> {svg_target.name}...")

        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                with GoodNotesDocument.open(gn_file) as doc:
                    if stem == "ex1":
                        closed_dir = Path(tmpdir) / "closed"
                        open_dir = Path(tmpdir) / "open"
                        closed_paths = write_svg(
                            doc,
                            closed_dir,
                            fill_shapes=True,
                            sticky_note_state="close",
                            tape_state="on",
                        )
                        open_paths = write_svg(
                            doc,
                            open_dir,
                            fill_shapes=True,
                            sticky_note_state="open",
                            tape_state="off",
                        )
                        if closed_paths and open_paths:
                            animated_svg = _build_animated_svg(
                                closed_paths[0].read_text(encoding="utf-8"),
                                open_paths[0].read_text(encoding="utf-8"),
                            )
                            svg_target.write_text(animated_svg, encoding="utf-8")
                            print(f"  ✓ Successfully updated {svg_target.name} (animated)")
                            updated_count += 1
                        else:
                            print(f"  ⚠ No SVG output produced for {gn_file.name}", file=sys.stderr)
                    else:
                        written_paths = write_svg(doc, tmpdir, fill_shapes=True)
                        if written_paths:
                            # Copy the first page SVG to the asset target
                            shutil.copy(written_paths[0], svg_target)
                            print(f"  ✓ Successfully updated {svg_target.name}")
                            updated_count += 1
                        else:
                            print(f"  ⚠ No SVG output produced for {gn_file.name}", file=sys.stderr)
            except Exception as exc:
                print(f"  ✗ Error rendering {gn_file.name}: {exc}", file=sys.stderr)

    print(f"\nDone! Updated {updated_count}/{len(targets)} asset SVGs.")
    return 0


if __name__ == "__main__":
    sys.exit(update_asset_svgs())
