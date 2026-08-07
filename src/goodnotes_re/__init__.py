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
from .export import write_json, write_svg

__all__ = [
    "Field",
    "GoodNotesDocument",
    "Message",
    "Page",
    "PageDimensions",
    "PageElement",
    "ShapePath",
    "Stroke",
    "StrokePoint",
    "TextFragment",
    "TplImage",
    "WireType",
    "decode_apple_lz4",
    "decode_message",
    "decode_tpl",
    "write_json",
    "write_svg",
]
