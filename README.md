# GoodNotes Document Parser

![CI](https://github.com/<your-org>/goodnotes-document-parser/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![License: MIT](https://img.shields.io/badge/License-MIT-green)

An independent, open-source, fully typed Python toolkit for inspecting and parsing user-supplied GoodNotes 5 and 6 `.goodnotes` archives. It decodes protobuf **wire format** directly, parses Apple LZ4 framed streams, decodes Troy Hanson TPL memory images, extracts observed RGBA stroke data, and exports documents to JSON and SVG.

**This project is not affiliated with, endorsed by, sponsored by, or officially connected to Goodnotes Limited.** See [`LEGAL-NOTICE.md`](LEGAL-NOTICE.md) for release and usage notes.

It **deliberately does NOT use heuristic float scanning**.

## Features

- **Protobuf Wire Decoder**: Lossless parsing of framed and unframed protobuf messages, preserving unknown fields.
- **Apple LZ4 & Troy Hanson TPL Decoder**: Decompresses `bv41` LZ4 streams and decodes embedded TPL format strings (`vuA(v)A(S(uu))...`) into structured stroke points and variable-width ribbons.
- **Stroke & Color Parsing**: Direct protobuf trailer decoding after `bv4$` to extract exact RGBA colors and highlighter transparency.
- **Stroke Support**: Parses a growing set of dots, lines, curves, pen tools, highlighters, erasers, shapes, and moved/copied elements observed in the test corpus.
- **Page & Background Resolution**: Automatic PDF background `/MediaBox` dimension detection (A4, Letter, landscape vs. portrait), page ordering, text fragments, and sticky notes (便條紙) content extraction.
- **CLI Tools**: `gn-inspect`, `gn-dump`, `gn-diff`, `gn-export-json`, `gn-export-svg`.

## Installation & Setup

Using [`uv`](https://github.com/astral-sh/uv):

```sh
uv sync
```

Or standard pip install:

```sh
pip install -e .
```

Run the unit test suite with:

```sh
uv run pytest
```

> **Note:** `samples/` is intentionally ignored and is not part of the public source tree. Do not publish `.goodnotes` files or extracted assets unless you have permission to redistribute them.

## CLI Usage

```sh
# Inspect archive inventory and sha256 checksums
gn-inspect sample.goodnotes

# Lossless dump of any protobuf member to JSON
gn-dump sample.goodnotes index.notes.pb

# Diff two .goodnotes archives
gn-diff before.goodnotes after.goodnotes

# Export entire document, metadata, pages, strokes, and raw wire trees to JSON
gn-export-json sample.goodnotes -o document.json

# Export vector SVG pages with exact stroke ribbons, colors, and dimensions
gn-export-svg sample.goodnotes -o pages-svg
```

Or via module invocation:

```sh
PYTHONPATH=src python3 -m goodnotes_re.cli export-svg sample.goodnotes -o pages-svg
```

For the full CLI reference (including all flags and batch export examples), see [`docs/cli-zh.md`](docs/cli-zh.md) (Traditional Chinese).

## Python Library API

```python
from goodnotes_re import GoodNotesDocument

with GoodNotesDocument.open("sample.goodnotes") as doc:
    # Inventory
    members = doc.inventory()
    
    # Document pages with strokes, dimensions, and text
    pages = doc.pages()
    for page in pages:
        print(f"Page {page.index + 1}: {page.dimensions.width}x{page.dimensions.height} pt")
        print(f"Strokes: {len(page.strokes)}")
        for stroke in page.strokes:
            print(f"  Stroke {stroke.uuid}: color {stroke.color_hex}, alpha {stroke.alpha}, points {len(stroke.points)}")
    
    # Text and Sticky Notes content
    fragments = doc.text_fragments()
    for frag in fragments:
        print(f"[{frag.source_path}] {frag.format}: {frag.text}")

    # Structural page-element summaries for format analysis
    for page in pages:
        for element in page.elements:
            print(element.kind, element.uuid, element.attachment_uuid, element.related_uuids)
```

## Documentation

| Document | Description |
|---|---|
| [`docs/knowledge-base.md`](docs/knowledge-base.md) | Format analysis findings and field annotations |
| [`docs/corpus-protocol.md`](docs/corpus-protocol.md) | Protocol for adding new wire-format observations |
| [`docs/cli-zh.md`](docs/cli-zh.md) | Full CLI reference (Traditional Chinese) |
| [`wiki/`](wiki/) | Deep-dive technical documentation (architecture, formats, rendering) |
| [`LEGAL-NOTICE.md`](LEGAL-NOTICE.md) | Legal, trademark, privacy, and redistribution notice |

See also the [Contributing Guide](CONTRIBUTING.md) and [Changelog](CHANGELOG.md).
