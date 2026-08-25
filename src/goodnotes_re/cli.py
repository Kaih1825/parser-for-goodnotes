"""Console entry points."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .archive import GoodNotesDocument
from .export import (
    write_audio,
    write_json,
    write_pdf,
    write_recording_html,
    write_recording_video,
    write_svg,
)


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

        recordings = document.recordings()
        if recordings:
            print(f"\nFound {len(recordings)} audio recording(s):")
            for r in recordings:
                print(f"  - Recording {r.id}: {r.duration:.2f}s, {len(r.stroke_timings)} timed stroke(s), audio: {r.audio_attachment_path}")
    return 0


def dump_main(argv: Sequence[str] | None = None) -> int:
    parser = _parser("gn-dump")
    parser.add_argument("document", type=Path)
    parser.add_argument("member")
    args = parser.parse_args(argv)
    with GoodNotesDocument.open(args.document) as document:
        print(json.dumps(document.decode(args.member).as_json(), ensure_ascii=False, indent=2, allow_nan=False))
    return 0


def recordings_main(argv: Sequence[str] | None = None) -> int:
    parser = _parser("gn-recordings")
    parser.add_argument("document", type=Path, help="Path to .goodnotes file")
    parser.add_argument("-a", "--all", action="store_true", help="Include deleted recording sessions")
    parser.add_argument("--json", action="store_true", help="Output recording list and stroke timings as JSON")
    args = parser.parse_args(argv)

    with GoodNotesDocument.open(args.document) as document:
        recordings = document.recordings(include_deleted=args.all)
        if args.json:
            print(json.dumps([r.as_dict() for r in recordings], ensure_ascii=False, indent=2))
            return 0

        if not recordings:
            print("No audio recordings found in this document.")
            return 0

        print(f"Found {len(recordings)} audio recording session(s):")
        for idx, rec in enumerate(recordings, start=1):
            status = " [DELETED]" if rec.is_deleted else ""
            m, s = divmod(int(rec.duration), 60)
            print(f"\n[{idx}] Recording ID: {rec.id}{status}")
            print(f"    Audio Attachment: {rec.audio_attachment_path}")
            print(f"    Duration:         {m:02d}:{s:02d} ({rec.duration:.2f}s)")
            print(f"    Linked Pages:     {', '.join(rec.page_uuids) or 'None'}")
            print(f"    Timed Strokes:    {len(rec.stroke_timings)}")
            if rec.stroke_timings:
                print("    Stroke Timings:")
                for st in rec.stroke_timings:
                    print(f"      - {st.timestamp:6.2f}s  stroke:{st.stroke_uuid[:18]}...  page:{st.page_uuid[:18]}...")
    return 0


def export_audio_main(argv: Sequence[str] | None = None) -> int:
    parser = _parser("gn-export-audio")
    parser.add_argument("document", type=Path, help="Path to .goodnotes file")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output audio file path or directory")
    parser.add_argument("-r", "--recording", type=str, default=None, help="Recording ID to extract (default: all active recordings concatenated, or first)")
    parser.add_argument("--no-concat", dest="concat", action="store_false", help="Do not concatenate recordings; export only first recording if single file")
    parser.set_defaults(concat=True)
    args = parser.parse_args(argv)

    with GoodNotesDocument.open(args.document) as document:
        out_path = write_audio(document, args.output, recording_id=args.recording, concat=args.concat)
        print(str(out_path))
    return 0


def export_video_main(argv: Sequence[str] | None = None) -> int:
    parser = _parser("gn-export-video")
    parser.add_argument("document", type=Path, help="Path to .goodnotes file")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output MP4 video file path")
    parser.add_argument("-r", "--recording", type=str, default=None, help="Recording ID to export (default: all active recordings in sequence)")
    parser.add_argument("-p", "--page-index", type=int, default=None, help="Target page index (0-indexed, default: auto-detect from recording)")
    parser.add_argument("-s", "--sticky-note-state", choices=["open", "close", "auto"], default=None, help="Force sticky notes state: open (expand all) or close (collapse all)")
    parser.add_argument("-b", "--textbox", nargs="?", const=True, default=False, help="Show text box bounding borders (flag or -b open / -b close)")
    parser.add_argument("-a", "--parse-all", action="store_true", help="Parse all pages instead of only active page")
    parser.add_argument("--no-fill", dest="fill_shapes", action="store_false", help="Do not fill vector shapes")
    parser.set_defaults(fill_shapes=True)
    parser.add_argument("--fps", type=int, default=15, help="Video frame rate (default: 15)")
    parser.add_argument("--scale", type=float, default=2.0, help="Resolution scale factor (default: 2.0)")
    parser.add_argument("--no-dim", dest="dim_future", action="store_false", help="Hide future strokes completely until spoken instead of dimming")
    parser.set_defaults(dim_future=True)
    args = parser.parse_args(argv)

    with GoodNotesDocument.open(args.document) as document:
        out_path = write_recording_video(
            document,
            args.output,
            recording_id=args.recording,
            page_index=args.page_index,
            fps=args.fps,
            resolution_scale=args.scale,
            dim_future=args.dim_future,
            fill_shapes=args.fill_shapes,
            sticky_note_state=args.sticky_note_state,
            textbox_state=args.textbox,
            parse_all=args.parse_all,
        )
        print(str(out_path))
    return 0


def export_html_main(argv: Sequence[str] | None = None) -> int:
    parser = _parser("gn-export-html")
    parser.add_argument("document", type=Path, help="Path to .goodnotes file")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output HTML player file path")
    parser.add_argument("-r", "--recording", type=str, default=None, help="Recording ID to export (default: includes all recordings)")
    parser.add_argument("-p", "--page-index", type=int, default=None, help="Target page index (0-indexed, default: auto-detect from recording)")
    parser.add_argument("-s", "--sticky-note-state", choices=["open", "close", "auto"], default=None, help="Force sticky notes state: open (expand all) or close (collapse all)")
    parser.add_argument("-b", "--textbox", nargs="?", const=True, default=False, help="Show text box bounding borders (flag or -b open / -b close)")
    parser.add_argument("-a", "--parse-all", action="store_true", help="Parse all pages instead of only active page")
    parser.add_argument("--no-fill", dest="fill_shapes", action="store_false", help="Do not fill vector shapes")
    parser.set_defaults(fill_shapes=True)
    args = parser.parse_args(argv)

    with GoodNotesDocument.open(args.document) as document:
        out_path = write_recording_html(
            document,
            args.output,
            recording_id=args.recording,
            page_index=args.page_index,
            fill_shapes=args.fill_shapes,
            sticky_note_state=args.sticky_note_state,
            textbox_state=args.textbox,
            parse_all=args.parse_all,
        )
        print(str(out_path))
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
    parser.add_argument("-b", "--textbox", nargs="?", const=True, default=False, help="Show text box bounding borders (flag or -b open / -b close)")
    parser.add_argument("-a", "--parse-all", action="store_true", help="Parse all pages instead of only active page")
    parser.add_argument("--no-fill", dest="fill_shapes", action="store_false", help="Do not fill vector shapes")
    parser.set_defaults(fill_shapes=True)
    parser.add_argument(
        "--pdf",
        nargs="?",
        const=True,
        default=False,
        help="Package exported SVG pages in sequence into a single PDF (optionally specify custom PDF filename)",
    )
    args = parser.parse_args(argv)
    with GoodNotesDocument.open(args.document) as document:
        paths = write_svg(
            document,
            args.output,
            fill_shapes=args.fill_shapes,
            sticky_note_state=args.sticky_note_state,
            textbox_state=args.textbox,
            parse_all=args.parse_all,
            export_pdf=args.pdf,
        )
    print("\n".join(str(path) for path in paths))
    return 0


def export_pdf_main(argv: Sequence[str] | None = None) -> int:
    parser = _parser("gn-export-pdf")
    parser.add_argument("document", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("-s", "--sticky-note-state", choices=["open", "close", "auto"], default=None, help="Force sticky notes state: open (expand all) or close (collapse all)")
    parser.add_argument("-b", "--textbox", nargs="?", const=True, default=False, help="Show text box bounding borders (flag or -b open / -b close)")
    parser.add_argument("-a", "--parse-all", action="store_true", help="Parse all pages instead of only active page")
    parser.add_argument("--no-fill", dest="fill_shapes", action="store_false", help="Do not fill vector shapes")
    parser.set_defaults(fill_shapes=True)
    args = parser.parse_args(argv)
    with GoodNotesDocument.open(args.document) as document:
        pdf_path = write_pdf(
            document,
            args.output,
            fill_shapes=args.fill_shapes,
            sticky_note_state=args.sticky_note_state,
            textbox_state=args.textbox,
            parse_all=args.parse_all,
        )
    print(str(pdf_path))
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
        print("Usage: python -m goodnotes_re.cli [gn-inspect|gn-dump|gn-recordings|gn-export-audio|gn-export-video|gn-export-html|gn-export-json|gn-export-svg|gn-export-pdf|gn-diff] ...")
        return 1
    cmd = args[0].replace("gn-", "")
    rest = args[1:]
    if cmd == "inspect":
        return inspect_main(rest)
    elif cmd == "dump":
        return dump_main(rest)
    elif cmd == "recordings":
        return recordings_main(rest)
    elif cmd == "export-audio":
        return export_audio_main(rest)
    elif cmd == "export-video":
        return export_video_main(rest)
    elif cmd == "export-html":
        return export_html_main(rest)
    elif cmd == "diff":
        return diff_main(rest)
    elif cmd == "export-json":
        return export_json_main(rest)
    elif cmd == "export-svg":
        return export_svg_main(rest)
    elif cmd == "export-pdf":
        return export_pdf_main(rest)
    else:
        return inspect_main(args)


if __name__ == "__main__":
    import sys
    sys.exit(main())
