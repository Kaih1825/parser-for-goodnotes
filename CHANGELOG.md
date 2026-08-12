# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2025

### Added
- **Protobuf Wire Decoder** (`wire.py`): Lossless, schema-free parsing of framed and unframed protobuf messages, preserving unknown fields.
- **Apple LZ4 Decompressor** (`compression.py`): Full `bv41`-framed LZ4 block stream decompression.
- **Troy Hanson TPL Decoder** (`tpl.py`): Decodes embedded TPL memory images (`vuA(v)A(S(uu))…`) into structured stroke-point arrays and variable-width ribbon geometry.
- **Stroke & Color Extraction** (`stroke.py`): Direct protobuf trailer decoding after `bv4$` to extract exact RGBA colors; highlighter transparency; ribbon tessellation for ballpoint, fountain, brush, pencil, and highlighter pens.
- **Shape Parser** (`shape.py`): Reconstructs auto-shape paths (rectangles, ellipses, triangles, polygons, lines, arrows) from GoodNotes wire fields.
- **Text & Sticky Note Parser** (`text.py`): Extracts rich text fragments (RTF-lite), sticky-note body and open/closed state from embedded protobuf sub-messages.
- **Page & Background Resolution** (`page.py`): Resolves page order from `index.notes.pb`, auto-detects PDF `/MediaBox` dimensions (A4, Letter, landscape vs. portrait), and merges strokes with background metadata.
- **SVG Exporter** (`export.py`): Renders full-fidelity vector SVG pages including PDF background rasterisation via PyMuPDF, stroke ribbons with per-segment opacity, shape fills, sticky notes, and text boxes.
- **JSON Exporter** (`export.py`): Structured JSON export of all document data (pages, strokes, colors, elements, text).
- **Archive Reader** (`archive.py`): Handles both `.goodnotes` ZIP archives and pre-extracted directory trees.
- **CLI Tools** (`cli.py`): Five entry-point commands — `gn-inspect`, `gn-dump`, `gn-diff`, `gn-export-json`, `gn-export-svg`.
- **Test Suite** (`tests/`): 10 test modules covering wire decoding, compression, TPL, strokes, pages, text, PDF, archive, export, and CLI.
