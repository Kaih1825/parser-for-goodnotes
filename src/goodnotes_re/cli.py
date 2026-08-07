"""Console entry points."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .archive import GoodNotesDocument
from .export import write_json, write_svg


def _parser(command: str) -> argparse.ArgumentParser:
    return argparse.ArgumentParser(prog=command)


def inspect_main(argv: Sequence[str] | None = None) -> int:
    parser = _parser("gn-inspect")
    parser.add_argument("document", type=Path)
    args = parser.parse_args(argv)
    with GoodNotesDocument.open(args.document) as document:
        for member in document.inventory():
            kind = "protobuf" if member.is_protobuf else "asset"
            print(f"{kind:8} {member.size:9} {member.path}  sha256:{member.sha256[:12]}")
    return 0


def dump_main(argv: Sequence[str] | None = None) -> int:
    parser = _parser("gn-dump")
    parser.add_argument("document", type=Path)
    parser.add_argument("member")
    args = parser.parse_args(argv)
    with GoodNotesDocument.open(args.document) as document:
        print(json.dumps(document.decode(args.member).as_json(), ensure_ascii=False, indent=2, allow_nan=False))
    return 0


def export_json_main(argv: Sequence[str] | None = None) -> int:
    parser = _parser("gn-export-json")
    parser.add_argument("document", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args(argv)
    with GoodNotesDocument.open(args.document) as document:
        write_json(document, args.output)
    return 0


def export_svg_main(argv: Sequence[str] | None = None) -> int:
    parser = _parser("gn-export-svg")
    parser.add_argument("document", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("-s", "--sticky-note-state", choices=["open", "close", "auto"], default=None, help="Force sticky notes state: open (expand all) or close (collapse all)")
    parser.add_argument("-b", "--textbox", choices=["open", "close"], default="close", help="Toggle text box bounding borders: open (show borders) or close (hide borders)")
    parser.add_argument("--no-fill", dest="fill_shapes", action="store_false", help="Do not fill vector shapes")
    parser.set_defaults(fill_shapes=True)
    args = parser.parse_args(argv)
    with GoodNotesDocument.open(args.document) as document:
        paths = write_svg(
            document,
            args.output,
            fill_shapes=args.fill_shapes,
            sticky_note_state=args.sticky_note_state,
            textbox_state=args.textbox,
        )
    print("\n".join(str(path) for path in paths))
    return 0


def diff_main(argv: Sequence[str] | None = None) -> int:
    parser = _parser("gn-diff")
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    args = parser.parse_args(argv)
    with GoodNotesDocument.open(args.before) as before, GoodNotesDocument.open(args.after) as after:
        left = {item.path: item.sha256 for item in before.inventory()}
        right = {item.path: item.sha256 for item in after.inventory()}
    for name in sorted(set(left) | set(right)):
        if name not in left:
            print(f"ADDED    {name}")
        elif name not in right:
            print(f"REMOVED  {name}")
        elif left[name] != right[name]:
            print(f"CHANGED  {name}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    import sys
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("Usage: python -m goodnotes_re.cli [gn-inspect|gn-dump|gn-diff|gn-export-json|gn-export-svg] ...")
        return 1
    cmd = args[0].replace("gn-", "")
    rest = args[1:]
    if cmd == "inspect":
        return inspect_main(rest)
    elif cmd == "dump":
        return dump_main(rest)
    elif cmd == "diff":
        return diff_main(rest)
    elif cmd == "export-json":
        return export_json_main(rest)
    elif cmd == "export-svg":
        return export_svg_main(rest)
    else:
        # Fallback to inspect_main with all args
        return inspect_main(args)


if __name__ == "__main__":
    import sys
    sys.exit(main())
