#!/usr/bin/env python3
"""Automatically re-render assets/ex1.svg ~ assets/ex3.svg from assets/ex1.goodnotes ~ assets/ex3.goodnotes."""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from goodnotes_re.archive import GoodNotesDocument
from goodnotes_re.export import write_svg

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets"


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
