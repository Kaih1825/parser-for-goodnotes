"""Public API for lossless GoodNotes archive inspection."""

from .archive import GoodNotesDocument
from .wire import Field, Message, WireType, decode_message
from .text import TextFragment
from .compression import decode_apple_lz4
from .tpl import TplImage, decode_tpl
from .element import PageElement
from .shape import ShapePath
from .stroke import Stroke, StrokePoint
from .page import Page, PageDimensions
from .recording import Recording, RecordingStrokeTiming, parse_recordings_from_events
from .export import (
    page_to_svg,
    svg_to_pdf_bytes,
    svgs_to_pdf,
    write_audio,
    write_json,
    write_pdf,
    write_recording_html,
    write_recording_video,
    write_svg,
)

__all__ = [
    "Field",
    "GoodNotesDocument",
    "Message",
    "Page",
    "PageDimensions",
    "PageElement",
    "Recording",
    "RecordingStrokeTiming",
    "ShapePath",
    "Stroke",
    "StrokePoint",
    "TextFragment",
    "TplImage",
    "WireType",
    "decode_apple_lz4",
    "decode_message",
    "decode_tpl",
    "page_to_svg",
    "parse_recordings_from_events",
    "svg_to_pdf_bytes",
    "svgs_to_pdf",
    "write_audio",
    "write_json",
    "write_pdf",
    "write_recording_html",
    "write_recording_video",
    "write_svg",
]
