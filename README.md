# Document Parser for GoodNotes <a id="english"></a> 
[中文](#中文)

> [!WARNING]
> **Vibe Coding Disclaimer**: This entire project was developed through **Vibe Coding** (AI-assisted rapid pair-programming and exploratory development). While the parser has been verified against test corpora, code and architecture choices reflect an experimental AI-driven iteration style. Use at your own discretion!

[![Live Web Demo](https://img.shields.io/badge/🚀%20Live%20Demo-Try%20in%20Browser-blueviolet?style=for-the-badge)](https://kaih1825.github.io/parser-for-goodnotes/?lang=en)

![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![License: MIT](https://img.shields.io/badge/License-MIT-green)
[![Web Demo Status](https://github.com/Kaih1825/document-parser-for-goodnotes/actions/workflows/pages.yml/badge.svg?branch=main)](https://github.com/Kaih1825/document-parser-for-goodnotes/actions/workflows/pages.yml)
![CI](https://github.com/Kaih1825/document-parser-for-goodnotes/actions/workflows/ci.yml/badge.svg)

An independent, open-source, fully typed Python toolkit for inspecting and parsing user-supplied GoodNotes 5 and 6 `.goodnotes` archives. It decodes protobuf **wire format** directly, parses Apple LZ4 framed streams, decodes Troy Hanson TPL memory images, extracts observed RGBA stroke data, and exports documents to JSON and SVG.

**This project is not affiliated with, endorsed by, sponsored by, or officially connected to Goodnotes Limited.** See [`LEGAL-NOTICE.md`](LEGAL-NOTICE.md) for release and usage notes.

It **deliberately does NOT use heuristic float scanning**.

## Table of Contents
- [Rendering Comparison](#️-rendering-comparison)
- [Motivation & Under the Hood](#motivation--under-the-hood)
- [Features](#features)
- [Installation & Setup](#installation--setup)
- [CLI Usage](#cli-usage)
- [Python Library API](#python-library-api)
- [Documentation](#documentation)



## 🖼️ Rendering Comparison

| Source Archive | GoodNotes Original (`.jpg`) | This Project SVG Export (`.svg`) |
| :---: | :---: | :---: |
| **Example 1: Handwritten Formulas & Images**<br>([`ex1.goodnotes`](assets/ex1.goodnotes)) | <img src="assets/ex1.jpg" width="400" alt="GoodNotes Original 1"> | <img src="assets/ex1.svg" width="400" alt="Parser SVG 1"> |
| **Example 2: Brush Styles & Stroke Variations**<br>([`ex2.goodnotes`](assets/ex2.goodnotes)) | <img src="assets/ex2.jpg" width="400" alt="GoodNotes Original 2"> | <img src="assets/ex2.svg" width="400" alt="Parser SVG 2"> |
| **Example 3: Multi-Layer Images & Chinese Text**<br>([`ex3.goodnotes`](assets/ex3.goodnotes)) | <img src="assets/ex3.jpg" width="400" alt="GoodNotes Original 3"> | <img src="assets/ex3.svg" width="400" alt="Parser SVG 3"> |

## Motivation & Under the Hood

GoodNotes is an amazing note-taking app, but its closed ecosystem has always been a pain point. If you want to export your notebooks while keeping the vector strokes editable, you're pretty much out of luck—you either have to stick with the proprietary `.goodnotes` file format or export to a flattened PDF that loses editability. To solve this, I built an open-source parser that can decode `.goodnotes` files.

I have zero background in reverse engineering, and decoding this format wasn't easy (I haven't seen many successful projects tackling this). So, I built this entirely through "vibe coding" using LLMs—primarily Gemini 3.1 Pro, Gemini 3.6 Flash, and Claude Sonnet 5.

Here is how the parsing works under the hood:

* **ZIP & Protobuf:** After some analysis, it turns out that `.goodnotes` is essentially a ZIP archive. The main stroke data is stored page by page in the `notes/` directory as serialized Protobuf files. Since I didn't have the official `.proto` schemas, the project blindly parses the Protobuf via the underlying Wire Format to construct an Abstract Syntax Tree (AST).
* **Apple LZ4:** Next, we discovered that some data fields start with `bv41` or `bv4-` and end with `bv4$`. This is a signature for Apple's proprietary Framed LZ4 compression. We successfully decompressed this by maintaining a 64KB sliding history window and using bitwise operations to handle the LZ4 tokens.
* **Troy Hanson's TPL:** The decompressed plaintext starts with the magic bytes `tpl\0`, revealing it as Troy Hanson's TPL format (a C serialization library). By inferring the format strings, we were able to extract the raw stroke data—which consists of discrete points containing pressure values.
* **SVG Ribbons:** Finally, to render the strokes with natural variable widths, the parser calculates the normal vectors between adjacent points and applies a sliding average for smoothing. It then pushes the edges outward based on the pressure values, stitching the discrete points into a closed SVG polygon ribbon.

Currently, the project can parse the binary files inside a `.goodnotes` archive to extract strokes, text, and other elements, exporting them directly to `.svg` or `.pdf`. Unlike standard exports from the GoodNotes app itself, this parser completely unlocks the raw data. The ultimate goal is to allow conversions to other open vector formats (like InkML) so users can migrate to other apps and prevent their hard work from being locked in by a single vendor.

For more detailed parsing principles, please refer to the [GitHub Wiki](https://github.com/Kaih1825/document-parser-for-goodnotes/wiki).


## Features

- **Protobuf Wire Decoder**: Lossless parsing of framed and unframed protobuf messages, preserving unknown fields.
- **Apple LZ4 & Troy Hanson TPL Decoder**: Decompresses `bv41` LZ4 streams and decodes embedded TPL format strings (`vuA(v)A(S(uu))...`) into structured stroke points and variable-width ribbons.
- **Stroke & Color Parsing**: Direct protobuf trailer decoding after `bv4$` to extract exact RGBA colors and highlighter transparency.
- **Stroke Support**: Parses a growing set of dots, lines, curves, pen tools, highlighters, erasers, shapes, and moved/copied elements observed in the test corpus.
- **Page & Background Resolution**: Automatic PDF background `/MediaBox` dimension detection (A4, Letter, landscape vs. portrait), page ordering, text fragments, and sticky notes (便條紙) content extraction.
- **CLI Tools**: `gn-inspect`, `gn-dump`, `gn-diff`, `gn-export-json`, `gn-export-svg`, `gn-export-pdf`.

### Feature Support Status

#### ✅ Working / Fully Supported
- **Fountain Pen, Ballpoint Pen, Brush Pen, Highlighter**: Full support with custom colors and line thicknesses.
- **Text**: Typed text fragments.
- **Sticky Notes**: Sticky note contents and formatting.
- **Images**: Embedded images.
- **Auto-Shapes & Shapes**: Vector shape rendering.
- **Eraser**: Eraser strokes and line cuts.
- **Lasso Tool**: Transformed, copied, or moved elements.
- **PDF-backed Notebooks**: PDF background pages with dimensions (`/MediaBox`).

#### ⚠️ Known Issues / In Progress
- **Pencil**: Visible output, but pressure sensitivity is incorrect and tilt sensitivity is missing.
- **Arrows**: Render output is currently highly unstable.
- **Stickers / Elements**: Certain vector lines/strokes may fail to export.
- **Audio Recordings**: Not yet implemented.


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

# Export vector SVGs and package all pages into a PDF
gn-export-svg sample.goodnotes -o pages-svg --pdf

# Directly export multi-page PDF document
gn-export-pdf sample.goodnotes -o document.pdf
```

Or via module invocation:

```sh
PYTHONPATH=src python3 -m goodnotes_re.cli export-svg sample.goodnotes -o pages-svg
```

For the full CLI reference (including all flags and batch export examples), see [`cli.md`](cli.md#english).

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
| [`cli.md`](cli.md#english) | Full CLI reference |
| [GitHub Wiki](https://github.com/Kaih1825/document-parser-for-goodnotes/wiki) | Deep-dive technical documentation (architecture, formats, rendering) |
| [`LEGAL-NOTICE.md`](LEGAL-NOTICE.md) | Legal, trademark, privacy, and redistribution notice |

See also the [Contributing Guide](CONTRIBUTING.md).

> [!IMPORTANT]
> **Legal & Trademark Notice**: "Goodnotes" and related names, logos, and marks are the property of Goodnotes Limited. Document Parser for GoodNotes is an independent, community-developed project and is **not affiliated with, endorsed by, sponsored by, or officially connected to Goodnotes Limited**. For full legal, trademark, privacy, and redistribution details, please read [`LEGAL-NOTICE.md`](LEGAL-NOTICE.md).

---


<a id="中文"></a>

# Document Parser for GoodNotes
[English](#english)

> [!WARNING]
> **Vibe Coding 免責聲明**：本專案完全採用 **Vibe Coding**（AI 輔助快速結對程式設計與探索式開發）進行構建。雖然解析器已通過測試樣本驗證，但程式碼結構與架構選擇體現了 AI 驅動的實驗性疊代風格。請自行評估並謹慎使用！

[![Live Web Demo](https://img.shields.io/badge/🚀%20線上展示-在瀏覽器中直接體驗-blueviolet?style=for-the-badge)](https://kaih1825.github.io/parser-for-goodnotes/?lang=zh_TW)


![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![License: MIT](https://img.shields.io/badge/License-MIT-green)
[![Web Demo Status](https://github.com/Kaih1825/document-parser-for-goodnotes/actions/workflows/pages.yml/badge.svg?branch=main)](https://github.com/Kaih1825/document-parser-for-goodnotes/actions/workflows/pages.yml)
![CI](https://github.com/Kaih1825/document-parser-for-goodnotes/actions/workflows/ci.yml/badge.svg)


一套獨立、開源且完整型別化的 Python 工具組，用於檢視與解析使用者提供的 GoodNotes 5 與 GoodNotes 6 `.goodnotes` 封存檔。它可直接解碼 protobuf **wire format**、解析 Apple LZ4 框架串流、解碼 Troy Hanson TPL 記憶體映像、擷取觀察到的 RGBA 筆跡資料，並將文件匯出為 JSON 與 SVG。

**本專案與 Goodnotes Limited 沒有任何關聯、背書、贊助或官方合作關係。** 發布與使用注意事項請參閱 [`LEGAL-NOTICE.md`](LEGAL-NOTICE.md)。

本專案**刻意不使用啟發式浮點數掃描**。

## 目錄
- [渲染效果對比](#️-渲染效果對比)
- [開發動機與解析原理](#開發動機與解析原理)
- [功能](#功能)
- [安裝與設定](#安裝與設定)
- [CLI 使用方式](#cli-使用方式)
- [Python 函式庫 API](#python-函式庫-api)
- [文件](#文件)



## 🖼️ 渲染效果對比

| 原始封存檔 | GoodNotes 原版渲染 (`.jpg`) | 本專案 SVG 匯出 (`.svg`) |
| :---: | :---: | :---: |
| **範例 1：手寫公式與插圖**<br>([`ex1.goodnotes`](assets/ex1.goodnotes)) | <img src="assets/ex1.jpg" width="400" alt="GoodNotes 原版渲染 1"> | <img src="assets/ex1.svg" width="400" alt="本專案 SVG 匯出 1"> |
| **範例 2：多款筆刷與色彩筆跡**<br>([`ex2.goodnotes`](assets/ex2.goodnotes)) | <img src="assets/ex2.jpg" width="400" alt="GoodNotes 原版渲染 2"> | <img src="assets/ex2.svg" width="400" alt="本專案 SVG 匯出 2"> |
| **範例 3：多層圖文疊加與中文手寫**<br>([`ex3.goodnotes`](assets/ex3.goodnotes)) | <img src="assets/ex3.jpg" width="400" alt="GoodNotes 原版渲染 3"> | <img src="assets/ex3.svg" width="400" alt="本專案 SVG 匯出 3"> |

## 開發動機與解析原理

GoodNotes 是一個很棒的筆記軟體，但由於其封閉性，除了匯出成封閉的 `.goodnotes` 專屬檔案，或是會失去編輯能力的 PDF 之外，幾乎沒有其他保留向量筆跡的選擇，因此我開發了一個解析工具來解析 `.goodnotes` 檔案。

因為我對這類工程沒有經驗，且解析此 `.goodnotes` 不是那麼容易（目前沒有看到幾個有成功解析出來的專案），因此我使用 vibe coding (主要是 Gemini 3.1 Pro, Gemini 3.6 Flash 及 Claude Sonnet 5) 來完成這個專案。

以下是解析原理：

* **壓縮與 Protobuf 盲解：** 經過分析，得知 `.goodnotes` 本質上是一個壓縮檔，而主要的筆跡資訊以頁為單位存在 `notes/` 下，各頁面的筆跡資訊存為 Protobuf 序列化檔案。在這個專案中，使用了 Wire Format 的方式來解析，將其構建成抽象語法樹。
* **Apple LZ4 逆向：** 接著，我們發現了部分欄位以 `bv41` 或 `bv4-` 開頭，並且以 `bv4$` 結尾，代表這是經過 Apple LZ4 壓縮的資料，我們利用維護 64KB 的歷史滑動視窗，靠位元運算處理 LZ4 的 token 來將其成功解壓。
* **TPL 記憶體映像：** 解壓後的明文以 `tpl\0` 開頭，因此得知他是 Troy Hanson's TPL 格式，並透過格式字串推導出他的筆跡資訊（帶有壓感的離散點）。
* **向量幾何重建：** 接著，透過計算相鄰兩點間的法向量並進行滑動平均平滑化，再結合壓感值向外推移，就能將離散點縫合成封閉的多邊形，最終輸出為帶有自然粗細變化的 SVG 向量筆跡。

目前，專案可以分析 `.goodnotes` 中的二進制檔案來獲取筆跡、文字等資訊，並輸出成 `.svg` 或 `.pdf` 格式。與直接從 GoodNotes app 匯出不同，本專案因為解析了 `.goodnotes` 格式，因此未來完全可以將解析出的資料，轉換為其他開源格式（如 InkML），讓使用者的心血不再被單一廠商綁架。

詳細的解析原理可以前往 [GitHub Wiki](https://github.com/Kaih1825/document-parser-for-goodnotes/wiki) 區查看。


## 功能

- **Protobuf Wire Decoder**：無損解析有框架與無框架的 protobuf 訊息，並保留未知欄位。
- **Apple LZ4 與 Troy Hanson TPL Decoder**：解壓縮 `bv41` LZ4 串流，並將嵌入的 TPL 格式字串解碼為結構化筆跡點與可變寬度筆跡帶。
- **筆跡與色彩解析**：解析 `bv4$` 後的 protobuf trailer，以擷取精確 RGBA 顏色與螢光筆透明度。
- **筆跡與幾何元件支援**：解析測試樣本中觀察到的單點、直線、曲線、鋼筆/原子筆工具、螢光筆、橡皮擦切口、圖形及移動/複製元素。
- **頁面與背景解析**：自動偵測 PDF `/MediaBox` 尺寸（A4、Letter、橫向與直向）、頁面順序、文字片段與便條紙內容。
- **CLI 工具**：`gn-inspect`、`gn-dump`、`gn-diff`、`gn-export-json`、`gn-export-svg`、`gn-export-pdf`。

### 功能支援狀態

#### ✅ 目前測試可正常輸出
- **鋼筆、原子筆、畫筆、螢光筆**：可處理不同顏色及粗細。
- **文字**：打字文字內容。
- **便利貼**：便條紙內容。
- **圖片**：內嵌圖片。
- **自動形狀、形狀**：幾何圖形。
- **橡皮擦**：橡皮擦筆跡與切口。
- **套索工具**：選取、移動與變形的元素。
- **有 PDF 的筆記本**：PDF 背景與頁面尺寸。

#### ⚠️ 目前已知有問題 / 開發中
- **鉛筆**：可顯示，但壓感有問題，以及沒有傾斜感知。
- **箭頭**：目前輸出極度不穩定。
- **素材（貼紙）**：可能有部分線條無法輸出。
- **錄音**：還沒實作。


## 安裝與設定

使用 [`uv`](https://github.com/astral-sh/uv)：

```sh
uv sync
```

或使用標準 pip：

```sh
pip install -e .
```

執行測試：

```sh
uv run pytest
```

> **注意：** `samples/` 刻意被忽略，且不屬於公開原始碼樹。除非您擁有重新發布的權限，否則請勿發布 `.goodnotes` 檔案或擷取出的資產。

## CLI 使用方式

```sh
# 檢視封存檔目錄清單與 sha256 校驗碼
gn-inspect sample.goodnotes

# 無損印出任何 protobuf 成員至 JSON
gn-dump sample.goodnotes index.notes.pb

# 比對兩個 .goodnotes 封存檔差異
gn-diff before.goodnotes after.goodnotes

# 匯出整份文件、元資料、頁面、筆跡與原始 wire 樹狀圖至 JSON
gn-export-json sample.goodnotes -o document.json

# 匯出包含精確筆跡緞帶、顏色與尺寸的向量 SVG 頁面
gn-export-svg sample.goodnotes -o pages-svg

# 匯出向量 SVG 並同步按頁面順序打包為 PDF
gn-export-svg sample.goodnotes -o pages-svg --pdf

# 直接將整份筆記匯出為多頁 PDF 文件
gn-export-pdf sample.goodnotes -o document.pdf
```

完整 CLI 參考請參閱 [`cli.md`](cli.md#中文)。

## Python 函式庫 API

```python
from goodnotes_re import GoodNotesDocument

with GoodNotesDocument.open("sample.goodnotes") as doc:
    # 目錄清單
    members = doc.inventory()
    
    # 包含筆跡、尺寸與文字的文件頁面
    pages = doc.pages()
    for page in pages:
        print(f"Page {page.index + 1}: {page.dimensions.width}x{page.dimensions.height} pt")
        print(f"筆跡數量: {len(page.strokes)}")
        for stroke in page.strokes:
            print(f"  Stroke {stroke.uuid}: color {stroke.color_hex}, alpha {stroke.alpha}, points {len(stroke.points)}")
    
    # 打字文字與便條紙內容
    fragments = doc.text_fragments()
    for frag in fragments:
        print(f"[{frag.source_path}] {frag.format}: {frag.text}")

    # 用於格式分析的結構化頁面元素摘要
    for page in pages:
        for element in page.elements:
            print(element.kind, element.uuid, element.attachment_uuid, element.related_uuids)
```

## 文件

| 文件 | 說明 |
|---|---|
| [`cli.md`](cli.md#中文) | 完整 CLI 參考|
| [GitHub Wiki](https://github.com/Kaih1825/document-parser-for-goodnotes/wiki) | 深入技術文件（架構、格式、渲染原理） |
| [`LEGAL-NOTICE.md`](LEGAL-NOTICE.md) | 法律、商標、隱私與重新發布注意事項 |

另請參閱 [貢獻指南](CONTRIBUTING.md)。

> [!IMPORTANT]
> **法律與商標聲明**：「Goodnotes」及相關名稱、標誌與標誌均為 Goodnotes Limited 所有。Document Parser for GoodNotes 是一套獨立且由社群開發的開源專案，**與 Goodnotes Limited 沒有任何附屬、背書、贊助或官方合作關係**。完整法律、商標、隱私及重新發布注意事項，請參閱 [`LEGAL-NOTICE.md`](LEGAL-NOTICE.md)。


