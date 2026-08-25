<a id="english"></a>

# Document Parser for GoodNotes — CLI User Guide
[中文](#中文)

`Document Parser for GoodNotes` provides a complete command-line interface (CLI) suite for inspecting, decoding, comparing, and exporting GoodNotes 5 and GoodNotes 6 `.goodnotes` document files.

This tool decodes unpublished Protobuf wire formats directly, decompresses Apple LZ4 (`bv41`) streams and Troy Hanson TPL stroke data, and losslessly converts GoodNotes strokes, shapes, and page structures to JSON, high-quality vector SVGs, and multi-page PDFs.

---

## Table of Contents

- [Installation & Environment Setup](#installation--environment-setup)
- [CLI Command Overview](#cli-command-overview)
- [Detailed Command Documentation](#detailed-command-documentation)
  - [1. gn-inspect (Archive Inventory & Checksums)](#1-gn-inspect-archive-inventory--checksums)
  - [2. gn-dump (Protobuf Member to JSON)](#2-gn-dump-protobuf-member-to-json)
  - [3. gn-diff (Archive Difference Comparison)](#3-gn-diff-archive-difference-comparison)
  - [4. gn-export-json (Full Document Structure to JSON)](#4-gn-export-json-full-document-structure-to-json)
  - [5. gn-export-svg (Export Vector SVG Pages)](#5-gn-export-svg-export-vector-svg-pages)
  - [6. gn-export-pdf (Compile Directly to Multi-Page PDF)](#6-gn-export-pdf-compile-directly-to-multi-page-pdf)
  - [7. gn-recordings (Audio Recordings & Timed Handwriting Strokess)](#7-gn-recordings-audio-recordings--timed-handwriting-strokes)
  - [8. gn-export-audio (Extract Audio Recordings)](#8-gn-export-audio-extract-audio-recordings)
  - [9. gn-export-video (Export Synchronized Handwriting Video MP4)](#9-gn-export-video-export-synchronized-handwriting-video-mp4)
  - [10. gn-export-html (Export Interactive Web Player)](#10-gn-export-html-export-interactive-web-player)
- [Universal Module Invocation](#universal-module-invocation)
- [Batch Export Script Example](#batch-export-script-example)

---

## Installation & Environment Setup

### Using `uv` (Recommended)

```bash
# Install dependencies and sync virtual environment
uv sync

# Run unit tests to verify installation
uv run pytest
```

### Using Standard `pip`

```bash
# Install in editable development mode
pip install -e .
```

After installation, the system registers 10 standalone CLI executable commands:
- `gn-inspect`
- `gn-dump`
- `gn-diff`
- `gn-recordings`
- `gn-export-audio`
- `gn-export-video`
- `gn-export-html`
- `gn-export-json`
- `gn-export-svg`
- `gn-export-pdf`

---

## CLI Command Overview

| Command | Description | Primary Use Case |
| :--- | :--- | :--- |
| `gn-inspect` | List all member files, checksums, and audio recording summaries | Quickly inspect document structure and assets |
| `gn-dump` | Losslessly dump the JSON decoding tree of a specified Protobuf member | Reverse engineer and inspect specific `.pb` members |
| `gn-diff` | Compare member additions, deletions, and modifications between two archives | Analyze edits (e.g. new strokes, pasted stickers) |
| `gn-recordings` | List audio recordings, durations, linked pages, and stroke timestamps | Inspect audio sync / timed handwriting data |
| `gn-export-audio` | Extract audio tracks (`.m4a`) from the document | Extract voice recordings |
| `gn-export-video` | Render synchronized MP4 video matching audio playback with strokes | Video replay of lectures / study notes |
| `gn-export-html` | Generate interactive HTML5 web player with click-to-seek strokes | Browser presentation and study notes replay |
| `gn-export-json` | Export pages, stroke points, colors, text, and metadata into a single JSON | Programmatic data pipelines or format conversion |
| `gn-export-svg` | Export notebook pages as vector SVG images (supports `--pdf` compilation) | Visual inspection, high-res printing, web presentation |
| `gn-export-pdf` | Render all pages as vector SVGs and merge them into a single multi-page PDF | Generate complete PDF notebook documents directly |

---

## Detailed Command Documentation

### 1. gn-inspect (Archive Inventory & Checksums)

Lists all internal member files, file sizes, types (Protobuf or Asset), SHA-256 hash prefixes, and audio recording summaries for a `.goodnotes` file.

#### Syntax
```bash
gn-inspect <document>
```

#### Arguments
- `<document>`: Path to the `.goodnotes` file or extracted directory.

#### Example Usage
```bash
gn-inspect sample.goodnotes
```

---

### 2. gn-dump (Protobuf Member to JSON)

Decodes and outputs any specific Protobuf member from a `.goodnotes` archive into lossless JSON.

#### Syntax
```bash
gn-dump <document> <member>
```

#### Arguments
- `<document>`: Path to the `.goodnotes` archive.
- `<member>`: Name of the internal member file (e.g., `index.notes.pb` or a UUID `.pb` path).

#### Example Usage
```bash
gn-dump sample.goodnotes index.notes.pb
```

#### Example Output
```json
{
  "1": {
    "type": "bytes",
    "value": "..."
  },
  "2": {
    "type": "varint",
    "value": 1
  }
}
```

---

### 3. gn-diff (Archive Difference Comparison)

Compares SHA-256 checksums of all internal members between two `.goodnotes` files, listing added (`ADDED`), removed (`REMOVED`), or modified (`CHANGED`) members.

#### Syntax
```bash
gn-diff <before> <after>
```

#### Arguments
- `<before>`: Path to the `.goodnotes` file before modification.
- `<after>`: Path to the `.goodnotes` file after modification.

#### Example Usage
```bash
gn-diff before.goodnotes after.goodnotes
```

#### Example Output
```text
CHANGED  index.notes.pb
ADDED    attachments/3F2504E0-4F89-41D3-9A0C-0305E82C3301
REMOVED  attachments/1A2B3C4D-5E6F-7A8B-9C0D-1E2F3A4B5C6D
```

---

### 4. gn-export-json (Full Document Structure to JSON)

Parses the complete `.goodnotes` document—including page dimensions (MediaBox), PDF background associations, stroke paths, pen types, RGBA colors, sticky notes, and text boxes—into a single structured JSON file.

#### Syntax
```bash
gn-export-json <document> -o <output>
```

#### Arguments
- `<document>`: Path to the input `.goodnotes` file.
- `-o`, `--output`: (Required) Path to the output JSON file.

#### Example Usage
```bash
gn-export-json sample.goodnotes -o document.json
```

---

### 5. gn-export-svg (Export Vector SVG Pages)

Renders pages of a GoodNotes document into vector SVG files. Faithfully reproduces background PDF templates, ink stroke ribbons, highlighter blend modes, pen pressure dynamics, sticky notes, and text elements.

#### Syntax
```bash
gn-export-svg <document> -o <output> [options]
```

#### Arguments
- `<document>`: Path to the input `.goodnotes` file.
- `-o`, `--output`: (Required) Output directory or filename pattern.
- `--pdf`: Packages all exported SVG pages in sequence into a single multi-page PDF. Optionally specify a custom PDF filename (e.g. `--pdf output/custom.pdf`).
- `-a`, `--parse-all`: Parses and exports all pages in the document (instead of only the active page).
- `-s`, `--sticky-note-state`: Overrides sticky note state:
  - `open`: Force expands all sticky notes, displaying their content cards.
  - `close`: Force collapses all sticky notes, displaying only indicator icons.
  - `auto`: (Default) Follows the original state stored in the file.
- `-b`, `--textbox`: Controls text box bounding borders:
  - Default: Hidden.
  - `-b`: Displays selection bounding guide borders.
- `--no-fill`: Disables filling for closed vector shapes (draws outlines only).

#### Example Usage

##### Basic SVG Export
```bash
gn-export-svg sample.goodnotes -o output_svgs/
```

##### Export SVGs and Simultaneously Compile to PDF
```bash
gn-export-svg sample.goodnotes -o output_svgs/ --pdf
```

##### Force Expand Sticky Notes and Show Text Box Borders
```bash
gn-export-svg sample.goodnotes -o output_svgs/ -s open -b
```

---

### 6. gn-export-pdf (Compile Directly to Multi-Page PDF)

Converts each page of a GoodNotes document into a vector SVG and directly compiles the rendered vector output into a single multi-page PDF document using CairoSVG.

#### Syntax
```bash
gn-export-pdf <document> -o <output.pdf> [options]
```

#### Arguments
- `<document>`: Path to the input `.goodnotes` file.
- `-o`, `--output`: (Required) Output PDF file path or target directory.
- `-a`, `--parse-all`: Parses and exports all pages.
- `-s`, `--sticky-note-state`: Sticky note display override (`open` / `close` / `auto`).
- `-b`, `--textbox`: Displays text box bounding borders.
- `--no-fill`: Disables filling for closed vector shapes.

#### Example Usage
```bash
gn-export-pdf sample.goodnotes -o sample.pdf
```

---

### 7. gn-recordings (Audio Recordings & Timed Handwriting Strokes)

Inspects all audio recording sessions embedded inside a `.goodnotes` file, showing audio duration, linked page IDs, and the exact chronological timestamp of each written stroke.

#### Syntax
```bash
gn-recordings <document> [options]
```

#### Arguments
- `<document>`: Path to the `.goodnotes` file.
- `-a`, `--all`: Include deleted recording sessions.
- `--json`: Output recording sessions and stroke timelines as structured JSON.

#### Example Usage
```bash
gn-recordings sample.goodnotes
gn-recordings sample.goodnotes --json
```

---

### 8. gn-export-audio (Extract Audio Recordings)

Extracts audio tracks (`.m4a` / AAC) recorded during note taking. By default, concatenates all active recordings in sequence into a single audio file.

#### Syntax
```bash
gn-export-audio <document> -o <output_path_or_dir> [options]
```

#### Arguments
- `<document>`: Path to the `.goodnotes` file.
- `-o`, `--output`: (Required) Destination audio file or directory.
- `-r`, `--recording`: Specific recording ID to extract (default: all active recordings concatenated).
- `--no-concat`: Do not concatenate recordings; extract only the first recording if output is a single file.

#### Example Usage
```bash
gn-export-audio sample.goodnotes -o audio.m4a
```

---

### 9. gn-export-video (Export Synchronized Handwriting Video MP4)

Renders a high-definition MP4 video combining notebook pages, audio recordings, and dynamically illuminated handwriting strokes synchronized to the audio timeline. Automatically follows speech across multiple notebook pages and seamlessly renders all recording sessions sequentially into a single continuous video.

#### Syntax
```bash
gn-export-video <document> -o <output.mp4> [options]
```

#### Arguments
- `<document>`: Path to the `.goodnotes` file.
- `-o`, `--output`: (Required) Target output `.mp4` video path.
- `-r`, `--recording`: Target recording ID (default: all active recordings in sequential order).
- `-p`, `--page-index`: Target page index (0-indexed, default: auto-detects and transitions across pages dynamically).
- `-s`, `--sticky-note-state`: Sticky note display override (`open` / `close` / `auto`).
- `-b`, `--textbox`: Displays text box bounding borders.
- `-a`, `--parse-all`: Parses and renders all pages.
- `--no-fill`: Disables filling for closed vector shapes.
- `--fps`: Frame rate (default: `15`).
- `--scale`: Resolution multiplier (default: `2.0`).
- `--no-dim`: Reveal strokes as spoken instead of dimming future strokes.

#### Example Usage
```bash
gn-export-video sample.goodnotes -o lecture_replay.mp4 -s open -b --fps 15
```

---

### 10. gn-export-html (Export Interactive Web Player)

Generates a standalone, responsive HTML5 web player with embedded audio and interactive vector SVG notes across all notebook pages. Features:
- **Multi-page Navigation**: Prev/Next buttons, page selector dropdown, and page count badge.
- **Dual View Modes**: Single Page mode (with smart auto-page flipping as audio plays) and All Pages Continuous Stack mode (with auto-scroll).
- **Multi-recording Playlist**: Sequential all-in-one playback or specific session selection.
- **Cross-page Click-to-Seek**: Clicking any handwriting stroke on any page instantly jumps playback to that stroke's recording session and timestamp.

#### Syntax
```bash
gn-export-html <document> -o <output.html> [options]
```

#### Arguments
- `<document>`: Path to the `.goodnotes` file.
- `-o`, `--output`: (Required) Target output `.html` file path.
- `-r`, `--recording`: Target recording ID (default: includes all recordings with multi-session playlist).
- `-p`, `--page-index`: Initial page index (0-indexed, default: first active page).
- `-s`, `--sticky-note-state`: Sticky note display override (`open` / `close` / `auto`).
- `-b`, `--textbox`: Displays text box bounding borders.
- `-a`, `--parse-all`: Parses and embeds all pages (enabled by default).
- `--no-fill`: Disables filling for closed vector shapes.

#### Example Usage
```bash
gn-export-html sample.goodnotes -o player.html -s open -b -a
```

---

## Universal Module Invocation

If commands are not registered in system `PATH` or you prefer invoking Python modules directly, use `python -m goodnotes_re.cli`:

```bash
# Using uv
uv run python -m goodnotes_re.cli export-svg sample.goodnotes -o output_svgs/ --pdf
uv run python -m goodnotes_re.cli export-pdf sample.goodnotes -o sample.pdf

# Using PYTHONPATH
PYTHONPATH=src python3 -m goodnotes_re.cli inspect sample.goodnotes
PYTHONPATH=src python3 -m goodnotes_re.cli dump sample.goodnotes index.notes.pb
PYTHONPATH=src python3 -m goodnotes_re.cli diff before.goodnotes after.goodnotes
PYTHONPATH=src python3 -m goodnotes_re.cli export-json sample.goodnotes -o doc.json
PYTHONPATH=src python3 -m goodnotes_re.cli export-svg sample.goodnotes -o output_svgs/ --pdf
PYTHONPATH=src python3 -m goodnotes_re.cli export-pdf sample.goodnotes -o sample.pdf
```

---

## Batch Export Script Example

You can create a shell script to batch convert multiple `.goodnotes` files into SVGs and PDFs:

```bash
#!/bin/bash
# Batch export script example batch_export.sh

INPUT_DIR="./samples"
OUTPUT_DIR="./output_svgs"

mkdir -p "$OUTPUT_DIR"

for file in "$INPUT_DIR"/*.goodnotes; do
    if [ -f "$file" ]; then
        echo "Processing: $file"
        uv run gn-export-pdf "$file" -o "$OUTPUT_DIR"
    fi
done

echo "Batch export complete! Results saved to $OUTPUT_DIR"
```

<a id="中文"></a>

# Document Parser for GoodNotes — CLI 使用指南
[English](#english)

`Document Parser for GoodNotes` 提供了一套完整的命令列工具（CLI），用於檢視、解碼、比對以及匯出 GoodNotes 5 與 GoodNotes 6 的 `.goodnotes` 文件檔案。

本工具能直接解碼未公開的 Protobuf wire 格式、解壓縮 Apple LZ4 (bv41) 與 Troy Hanson TPL 筆劃資料，並可將 GoodNotes 筆跡與頁面結構無損轉換為 JSON、高品質向量 SVG 與多頁 PDF。

---

## 目錄

- [安裝與環境設定](#安裝與環境設定-1)
- [CLI 命令總覽](#cli-命令總覽-1)
- [詳細命令說明](#詳細命令說明-1)
  - [1. gn-inspect（檔案清單檢視）](#1-gn-inspect檔案清單檢視-1)
  - [2. gn-dump（Protobuf 轉 JSON）](#2-gn-dumpprotobuf-轉-json-1)
  - [3. gn-diff（檔案差異比對）](#3-gn-diff檔案差異比對-1)
  - [4. gn-export-json（完整結構匯出為 JSON）](#4-gn-export-json完整結構匯出為-json-1)
  - [5. gn-export-svg（頁面匯出為向量 SVG）](#5-gn-export-svg頁面匯出為向量-svg-1)
  - [6. gn-export-pdf（直接匯出為多頁 PDF）](#6-gn-export-pdf直接匯出為多頁-pdf-1)
  - [7. gn-recordings（錄音與時間筆畫解析）](#7-gn-recordings錄音與時間筆畫解析-1)
  - [8. gn-export-audio（提取錄音檔案）](#8-gn-export-audio提取錄音檔案-1)
  - [9. gn-export-video（匯出筆跡同步錄音 MP4 影片）](#9-gn-export-video匯出筆跡同步錄音-mp4-影片-1)
  - [10. gn-export-html（匯出互動式網頁播放器）](#10-gn-export-html匯出互動式網頁播放器-1)
- [通用模組調用方式](#通用模組調用方式-1)
- [批次匯出範例](#批次匯出範例-1)

---

## 安裝與環境設定

### 使用 `uv`（推薦）

```bash
# 安裝依賴並建立虛擬環境
uv sync

# 執行測試驗證安裝
uv run pytest
```

### 使用傳統 `pip`

```bash
# 以可編輯模式安裝
pip install -e .
```

安裝完成後，系統將註冊以下 10 個獨立 CLI 命令：
- `gn-inspect`
- `gn-dump`
- `gn-diff`
- `gn-recordings`
- `gn-export-audio`
- `gn-export-video`
- `gn-export-html`
- `gn-export-json`
- `gn-export-svg`
- `gn-export-pdf`

---

## CLI 命令總覽

| 命令 | 說明 | 主要用途 |
| :--- | :--- | :--- |
| `gn-inspect` | 列出 `.goodnotes` 壓縮檔內所有成員檔案、雜湊值與錄音概況 | 快速了解文件結構與內部資源 |
| `gn-dump` | 無損印出指定 Protobuf 成員的 JSON 解碼樹 | 格式分析特定 `.pb` 檔案 |
| `gn-diff` | 比對兩個 `.goodnotes` 檔案內部成員的增刪與修改狀態 | 分析編輯操作前後的變化 |
| `gn-recordings` | 列出錄音階段、時長、關聯頁面與每筆筆畫之時間戳記 | 檢視錄音同步與時間筆跡結構 |
| `gn-export-audio` | 提取文件內所錄製之原始音訊檔（`.m4a`） | 匯出課堂或會議錄音檔 |
| `gn-export-video` | 渲染結合錄音與時間筆跡同步點亮動畫之 MP4 影片 | 影音複習、課堂筆記重播 |
| `gn-export-html` | 產生獨立互動式 HTML5 網頁播放器，支援點擊筆跡跳轉音訊 | 瀏覽器互動播放與隨點隨播 |
| `gn-export-json` | 匯出整份文件的頁面、筆跡點位、顏色、文字與元資料為單一 JSON | 程式化資料處理或第三方格式轉換 |
| `gn-export-svg` | 將文件頁面匯出為高品質向量 SVG 圖檔（支援 `--pdf` 同步打包為 PDF） | 視覺化檢視與高品質列印 / 網頁呈現 |
| `gn-export-pdf` | 將文件各頁按順序渲染為向量 SVG 並直接打包合併為單一多頁 PDF | 快速產生完整 PDF 筆記文件 |

---

## 詳細命令說明

### 1. gn-inspect（檔案清單檢視）

列出指定 `.goodnotes` 檔案內部所有的成員檔案、大小、類型（Protobuf 或 Asset）以及 SHA-256 雜湊前碼。

#### 語法
```bash
gn-inspect <document>
```

#### 參數說明
- `<document>`：`.goodnotes` 檔案路徑或已解壓的目錄路徑。

#### 使用範例
```bash
gn-inspect sample.goodnotes
```

#### 輸出範例
```text
protobuf      12480 index.notes.pb  sha256:a1b2c3d4e5f6
asset        524188 0A1B2C3D-4E5F-6A7B-8C9D-0E1F2A3B4C5D.pdf  sha256:7f8e9d0c1b2a
```

---

### 2. gn-dump（Protobuf 轉 JSON）

將 `.goodnotes` 檔案中指定的 Protobuf 成員無損解碼並印出為 JSON 格式。

#### 語法
```bash
gn-dump <document> <member>
```

#### 參數說明
- `<document>`：`.goodnotes` 檔案路徑。
- `<member>`：內部成員檔案名稱（例如：`index.notes.pb` 或特定的 UUID `.pb` 檔）。

#### 使用範例
```bash
gn-dump sample.goodnotes index.notes.pb
```

#### 輸出範例
```json
{
  "1": {
    "type": "bytes",
    "value": "..."
  },
  "2": {
    "type": "varint",
    "value": 1
  }
}
```

---

### 3. gn-diff（檔案差異比對）

比對兩個 `.goodnotes` 檔案內所有成員的 SHA-256 雜湊值，列出新增（ADDED）、刪除（REMOVED）或修改（CHANGED）的項目。

#### 語法
```bash
gn-diff <before> <after>
```

#### 參數說明
- `<before>`：修改前的 `.goodnotes` 檔案路徑。
- `<after>`：修改後的 `.goodnotes` 檔案路徑。

#### 使用範例
```bash
gn-diff before.goodnotes after.goodnotes
```

#### 輸出範例
```text
CHANGED  index.notes.pb
ADDED    attachments/3F2504E0-4F89-41D3-9A0C-0305E82C3301
REMOVED  attachments/1A2B3C4D-5E6F-7A8B-9C0D-1E2F3A4B5C6D
```

---

### 4. gn-export-json（完整結構匯出為 JSON）

將整份 `.goodnotes` 文件解析，包含頁面尺寸（MediaBox）、PDF 背景關聯、筆劃軌跡點位、筆尖類型、精確 RGBA 顏色與不透明度、便條紙（Sticky Notes）與文字框內容，完整匯出至指定 JSON 檔案。

#### 語法
```bash
gn-export-json <document> -o <output>
```

#### 參數說明
- `<document>`：輸入的 `.goodnotes` 檔案路徑。
- `-o`, `--output`：（必填）輸出 JSON 檔案路徑。

#### 使用範例
```bash
gn-export-json sample.goodnotes -o document.json
```

---

### 5. gn-export-svg（頁面匯出為向量 SVG）

將 GoodNotes 文件頁面渲染為向量 SVG 圖檔。支援渲染原版 PDF 背景、筆跡 Ribbon 緞帶形狀、螢光筆半透明疊加、鋼筆/原子筆/畫筆動態筆壓變化、便條紙與文字方塊。

#### 語法
```bash
gn-export-svg <document> -o <output> [選項]
```

#### 參數說明
- `<document>`：輸入的 `.goodnotes` 檔案路徑。
- `-o`, `--output`：（必填）輸出目錄或檔名樣板。若文件包含多頁，將自動於目錄中生成 `page_1.svg`, `page_2.svg` 等檔案。
- `--pdf`：將輸出的所有 SVG 頁面按頁面順序打包為單一多頁 PDF 檔案。可選填指定 PDF 檔名（例如 `--pdf output_svgs/sample.pdf`），若未指定則預設自動於輸出目錄生成 `<檔案名>.pdf`。
- `-a`, `--parse-all`：解析並匯出整份文件所有的頁面（預設僅匯出活動頁）。
- `-s`, `--sticky-note-state`：控制便條紙（Sticky Notes）展開狀態：
  - `open`：強制展開所有便條紙，顯示內容。
  - `close`：強制收合所有便條紙，僅顯示圖示。
  - `auto`：（預設）依照 GoodNotes 檔案內原始儲存狀態顯示。
- `-b`, `--textbox`：控制文字方塊外框線：
  - 未指定：（預設）隱藏文字方塊外框線。
  - `-b`：顯示文字方塊外框輔助線。
- `--no-fill`：停用向量封閉圖形的自動填色功能（預設會填色）。

#### 使用範例

##### 基本匯出 SVG
```bash
gn-export-svg sample.goodnotes -o output_svgs/
```

##### 匯出 SVG 並按順序打包成 PDF
```bash
gn-export-svg sample.goodnotes -o output_svgs/ --pdf
```

##### 強制展開便條紙並顯示文字框線
```bash
gn-export-svg sample.goodnotes -o output_svgs/ -s open -b
```

##### 不填滿封閉幾何圖形
```bash
gn-export-svg sample.goodnotes -o output_svgs/ --no-fill
```

---

### 6. gn-export-pdf（直接匯出為多頁 PDF）

將 GoodNotes 文件各頁按順序轉換為向量 SVG 並直接打包合併為單一多頁 PDF 檔案（採用 CairoSVG 向量轉換）。

#### 語法
```bash
gn-export-pdf <document> -o <output.pdf> [選項]
```

#### 參數說明
- `<document>`：輸入的 `.goodnotes` 檔案路徑。
- `-o`, `--output`：（必填）輸出 PDF 檔案路徑或目標目錄。
- `-a`, `--parse-all`：解析並匯出整份文件所有的頁面。
- `-s`, `--sticky-note-state`：控制便條紙展開狀態（`open` / `close` / `auto`）。
- `-b`, `--textbox`：顯示文字方塊外框輔助線。
- `--no-fill`：停用向量封閉圖形的自動填色功能。

#### 使用範例
```bash
gn-export-pdf sample.goodnotes -o sample.pdf
```

---

### 7. gn-recordings（錄音與時間筆畫解析）

解析 `.goodnotes` 文件內含的所有錄音階段，顯示錄音時長、關聯之筆記頁面 UUID，以及每筆筆畫對應於錄音的精確時間戳記（秒）。

#### 語法
```bash
gn-recordings <document> [選項]
```

#### 參數說明
- `<document>`：輸入的 `.goodnotes` 檔案路徑。
- `-a`, `--all`：包含已被刪除的錄音階段。
- `--json`：將錄音與筆劃時間軸輸出為結構化 JSON 格式。

#### 使用範例
```bash
gn-recordings sample.goodnotes
gn-recordings sample.goodnotes --json
```

---

### 8. gn-export-audio（提取錄音檔案）

提取 GoodNotes 筆記中錄製的原始音訊檔案（`.m4a` / AAC 格式）。預設會自動依順序串接所有錄音段落並合併為單一音訊檔案。

#### 語法
```bash
gn-export-audio <document> -o <output> [選項]
```

#### 參數說明
- `<document>`：輸入的 `.goodnotes` 檔案路徑。
- `-o`, `--output`：（必填）輸出音訊檔案路徑或目標目錄。
- `-r`, `--recording`：指定欲匯出的單一錄音 UUID（預設依順序串接所有有效錄音）。
- `--no-concat`：停用自動串接功能，僅匯出第一筆錄音。

#### 使用範例
```bash
gn-export-audio sample.goodnotes -o audio.m4a
```

---

### 9. gn-export-video（匯出筆跡同步錄音 MP4 影片）

將 GoodNotes 頁面、音訊軌道與隨錄音進度同步點亮/繪製的筆畫動畫渲染並封裝為 MP4 影片。若錄音跨越多個頁面，影片會自動隨說話者語音進度智慧切換對應頁面；預設亦會將多段錄音依時間順序無縫接續渲染為單一連續影片。

#### 語法
```bash
gn-export-video <document> -o <output.mp4> [選項]
```

#### 參數說明
- `<document>`：輸入的 `.goodnotes` 檔案路徑。
- `-o`, `--output`：（必填）輸出 MP4 影片路徑。
- `-r`, `--recording`：指定欲匯出的單一錄音 UUID（預設依順序播放所有有效錄音）。
- `-p`, `--page-index`：指定固定頁面索引（0 為第一頁，預設會依語音進度自動跨頁切換）。
- `-s`, `--sticky-note-state`：控制便條紙展開狀態（`open` / `close` / `auto`）。
- `-b`, `--textbox`：顯示文字方塊外框輔助線。
- `-a`, `--parse-all`：解析並渲染整份文件所有頁面。
- `--no-fill`：停用向量封閉圖形的自動填色功能。
- `--fps`：影片幀率（預設為 `15`）。
- `--scale`：解析度縮放倍率（預設為 `2.0`）。
- `--no-dim`：未來筆跡完全隱藏直至念到該處，而非預先淡化顯示。

#### 使用範例
```bash
gn-export-video sample.goodnotes -o lecture.mp4 -s open -b --fps 15
```

---

### 10. gn-export-html（匯出互動式網頁播放器）

生成單一獨立、免伺服器的 HTML5 網頁播放器，完整支援多頁面導覽與跨頁互動：
- **完整多頁導覽控制列**：提供「上一頁」、「下一頁」快捷按鈕、即時頁面下拉選單與總頁數標籤。
- **雙重檢視模式**：支援「單頁翻頁模式」（錄音播放時遇跨頁筆畫會自動智慧翻頁）與「全頁連續捲動模式」（多頁依序縱向排列，播放時自動平滑滾動至目標筆畫）。
- **多錄音段落播放清單**：支援全部錄音連續播放或單一段落獨立播放。
- **跨頁隨點隨播**：在任一頁面上點擊任何筆跡，播放器會自動切換錄音段落與頁面，並瞬間跳轉至該筆畫書寫之時刻！

#### 語法
```bash
gn-export-html <document> -o <output.html> [選項]
```

#### 參數說明
- `<document>`：輸入的 `.goodnotes` 檔案路徑。
- `-o`, `--output`：（必填）輸出 HTML 檔案路徑。
- `-r`, `--recording`：指定欲匯出的單一錄音 UUID（預設包含所有錄音並支援連續播放）。
- `-p`, `--page-index`：初始載入之頁面索引（0 為第一頁）。
- `-s`, `--sticky-note-state`：控制便條紙展開狀態（`open` / `close` / `auto`）。
- `-b`, `--textbox`：顯示文字方塊外框輔助線。
- `-a`, `--parse-all`：解析並內嵌整份文件所有頁面（預設已開啟）。
- `--no-fill`：停用向量封閉圖形的自動填色功能。

#### 使用範例
```bash
gn-export-html sample.goodnotes -o player.html -s open -b -a
```

---

## 通用模組調用方式

若未將命令註冊至系統 PATH，或習慣使用 Python 模組直接執行，可透過 `python -m goodnotes_re.cli` 來調用：

```bash
# 使用 uv
uv run python -m goodnotes_re.cli export-svg sample.goodnotes -o output_svgs/ --pdf
uv run python -m goodnotes_re.cli export-pdf sample.goodnotes -o sample.pdf

# 設定 PYTHONPATH 執行
PYTHONPATH=src python3 -m goodnotes_re.cli inspect sample.goodnotes
PYTHONPATH=src python3 -m goodnotes_re.cli dump sample.goodnotes index.notes.pb
PYTHONPATH=src python3 -m goodnotes_re.cli diff before.goodnotes after.goodnotes
PYTHONPATH=src python3 -m goodnotes_re.cli export-json sample.goodnotes -o doc.json
PYTHONPATH=src python3 -m goodnotes_re.cli export-svg sample.goodnotes -o output_svgs/ --pdf
PYTHONPATH=src python3 -m goodnotes_re.cli export-pdf sample.goodnotes -o sample.pdf
```

---

## 批次匯出範例

可建立 Shell 腳本批次將多個 `.goodnotes` 檔案自動轉為 SVG 與 PDF：

```bash
#!/bin/bash
# 批次轉檔腳本範例 batch_export.sh

INPUT_DIR="./samples"
OUTPUT_DIR="./output_svgs"

mkdir -p "$OUTPUT_DIR"

for file in "$INPUT_DIR"/*.goodnotes; do
    if [ -f "$file" ]; then
        echo "正在處理: $file"
        uv run gn-export-pdf "$file" -o "$OUTPUT_DIR"
    fi
done

echo "批次轉換完成！結果儲存於 $OUTPUT_DIR"
```
