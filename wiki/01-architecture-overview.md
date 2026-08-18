<a id="english"></a>

# 01 - Architecture Overview
[中文](#中文)

This chapter introduces the overall system design, internal module breakdown, and data processing pipeline (Data Pipeline) of the **Document Parser for GoodNotes**, as well as the format evolution between GoodNotes 5 and GoodNotes 6.

---

## System Architecture

This toolkit adopts a layered, modular architecture design. The low level focuses on schema-free decompression and byte stream decoding; the mid level performs feature extraction and geometric reconstruction; the high level provides JSON and SVG vector rendering and a CLI interface.

```mermaid
flowchart TD
    A[".goodnotes Archive (ZIP File)"] --> B["archive.py (GoodNotesDocument)"]
    
    subgraph LowLevel["1. Low-Level Decoding"]
        B --> C["wire.py (Protobuf Wire Decoder)"]
        B --> D["compression.py (Apple LZ4 Stream Decoder)"]
        D --> E["tpl.py (Troy Hanson TPL Parser)"]
    end
    
    subgraph MidLevel["2. Feature Extraction & Reconstruction"]
        C & E --> F["stroke.py (Ink Stroke & Color Trailer Extractor)"]
        C --> G["shape.py (Vector Shape Geometry Parser)"]
        C & D --> H["text.py (Rich Text & RTF Extractor)"]
        C --> I["element.py (Image Crop & Sticky Note Parser)"]
        B & C --> J["pdf.py (PDF MediaBox & Background Renderer)"]
    end
    
    subgraph HighLevel["3. Page Model & Export Subsystem"]
        F & G & H & I & J --> K["page.py (Page & PageDimensions Model)"]
        K --> L["export.py (JSON & SVG Renderers)"]
        L --> M["cli.py (gn-inspect, gn-dump, gn-diff, gn-export-*)"]
    end
```

---

## Module Breakdown

The project source code is located in [`src/goodnotes_re/`](../src/goodnotes_re/), and the responsibilities of each module are as follows:

| Module Name | Absolute Path / Clickable Link | Core Responsibility & Functionality |
| :--- | :--- | :--- |
| **`wire.py`** | [`src/goodnotes_re/wire.py`](../src/goodnotes_re/wire.py) | **Protobuf Wire Decoder**. Implements 7-bit Varint reading, WireType determination, Length-Delimited decoding, and stream framing (`decode_delimited_messages`). Maintains full byte structure without needing `.proto` files. |
| **`archive.py`** | [`src/goodnotes_re/archive.py`](../src/goodnotes_re/archive.py) | **ZIP Archive Management**. Provides the `GoodNotesDocument` class, responsible for reading internal member files (e.g., `index.notes.pb`, `notes/<UUID>`), generating Inventory lists, and computing SHA256 hashes. |
| **`compression.py`** | [`src/goodnotes_re/compression.py`](../src/goodnotes_re/compression.py) | **Apple Framed LZ4 Decompression**. Decodes Apple proprietary LZ4 streams headed with `bv41`/`bv4-` and terminated by `bv4$`, maintaining a 64KB history window. |
| **`tpl.py`** | [`src/goodnotes_re/tpl.py`](../src/goodnotes_re/tpl.py) | **Troy Hanson TPL Memory Image Parser**. Parses binary coordinate points and Format Strings (e.g., `vuA(v)...`) written by the C language TPL library. |
| **`stroke.py`** | [`src/goodnotes_re/stroke.py`](../src/goodnotes_re/stroke.py) | **Ink Stroke & Color Parser**. Combines TPL control points to extract pressure sensitivity and calculate smoothed normal vectors; parses the Protobuf Trailer after `bv4$` to extract RGBA colors and Lasso move offsets `(dx, dy)`; handles v9 eraser cutouts. |
| **`shape.py`** | [`src/goodnotes_re/shape.py`](../src/goodnotes_re/shape.py) | **Vector Shape Geometry Parser**. Parses rectangles, ellipses, polygons, dash patterns (`dash_pattern`), and arrow styles from Protobuf Records (Tags 9, 21, 22, etc.). |
| **`text.py`** | [`src/goodnotes_re/text.py`](../src/goodnotes_re/text.py) | **Rich Text & RTF Parser**. Decodes the fonts, sizes, colors, alignments, and list styles of Type 35 / bv41 typewriter text boxes, as well as legacy RTF payloads. |
| **`element.py`** | [`src/goodnotes_re/element.py`](../src/goodnotes_re/element.py) | **Page Element Abstraction**. Parses image stickers (including bounding boxes, crop parameters, and rotation angles), sticky notes states (expanded/collapsed), and tombstone records. |
| **`page.py`** | [`src/goodnotes_re/page.py`](../src/goodnotes_re/page.py) | **Page Model**. Combines PDF `/MediaBox` dimension parsing (132 DPI to 72 DPI scaling) to aggregate strokes, shapes, text, images, and backgrounds in a single page. |
| **`pdf.py`** | [`src/goodnotes_re/pdf.py`](../src/goodnotes_re/pdf.py) | **PDF Background Renderer**. Uses PyMuPDF (fitz) to render `.goodnotes` embedded PDF attachment pages into vector SVG paths or image backgrounds. |
| **`export.py`** | [`src/goodnotes_re/export.py`](../src/goodnotes_re/export.py) | **Exporter (JSON & SVG)**. Converts the page model into a complete JSON structure or high-fidelity SVG vector graphics. |
| **`cli.py`** | [`src/goodnotes_re/cli.py`](../src/goodnotes_re/cli.py) | **Command Line Tools**. Provides entry points for `gn-inspect`, `gn-dump`, `gn-diff`, `gn-export-json`, and `gn-export-svg`. |

---

## Data Pipeline Flow

When invoking `gn-export-svg sample.goodnotes -o output_dir`, the data flows as follows:

```
[sample.goodnotes (ZIP Archive)]
       │
       ▼
1. GoodNotesDocument.open() 
   └─ Extract ZIP directory inventory
       │
       ▼
2. GoodNotesDocument.pages()
   ├─ 1. Read index.notes.pb to get page UUID sequence (`notes/<UUID>`)
   ├─ 2. Read index.attachments.pb / index.events.pb to bind background PDF
   └─ 3. Call decode_records() for each `notes/<UUID>` member
       │
       ▼
3. Record-by-record parsing (parse_page_from_records)
   ├─ Detect Tag containing "bv41" ──► decode_apple_lz4() Decompress ──► decode_tpl() Decode Points
   │                                                             │
   │                                                             ▼
   │                                             parse_stroke_field() Extract Points, Pressure, RGBA Color
   ├─ Detect Tag 9 / Tag 21 / Tag 22 ────────────────────────────► parse_shape_record() Build Shapes
   ├─ Detect Tag 16 == 35 or Rich Text ──────────────────────────► parse_text_elements() Extract Text
   └─ Detect Tag 4 Attachment ──────────────────────────────────► parse_image_elements() Extract Images & Crop
       │
       ▼
4. Build Page Entity (incl. PageDimensions: PDF MediaBox Scaling 72/132)
       │
       ▼
5. write_svg() (export.py)
   └─ Generate SVG by Layer (PDF Background -> Sticky Note Cards -> Shapes -> Strokes -> Images -> Text)
```

---

## GN5 vs GN6 Evolution (GoodNotes 5 vs 6 Formats)

GoodNotes 5 (GN5) and GoodNotes 6 (GN6) maintain high compatibility in their underlying storage structure, both using the ZIP + Length-Delimited Protobuf + Apple LZ4 + TPL architecture. The main differences are outlined below:

| Criteria | GoodNotes 5 (GN5) | GoodNotes 6 (GN6) | Toolkit Compatibility Mechanism |
| :--- | :--- | :--- | :--- |
| **File Extension** | `.goodnotes` | `.goodnotes` | Both are standard ZIP formats, read using `zipfile`. |
| **Protobuf Record Framing** | Varint prefix framing (Length-delimited records) | Varint prefix framing or embedded Record wrapped in Tag 7 | `decode_records()` automatically detects direct framing or Tag 7 wrapping. |
| **Stroke Coordinate Format** | TPL classic 4-tuple (`uuuu`) / 11-tuple (`uuuuuuuuuuu`) | Added dynamic high-density 6-float/3-float/5-float formats | `extract_points_from_tpl()` has a built-in multiple format matching mechanism. |
| **Shapes & Arrows** | Tag 9 basic hand-drawn shapes | Added Tag 21 (Type 35), Tag 22 (Type 31) complex shapes and arrow markers | `shape.py` fully supports 3 arrow styles and rounded rectangles in Type 31/35. |
| **Text Boxes & Sticky Notes** | RTF Payload or UTF-8 block | Extended Type 35 bv41 encapsulated rich text (fonts/colors/lists/alignment) | `text.py` automatically supports CP950/UTF-8 parsing of typewriter text and RTF. |

---

In the next chapter, **[02 - Archive and Wire Format](02-archive-and-wire-format#english)**, we will dive into the file distribution within the ZIP archive and the low-level byte reading principles of the schema-free Protobuf Wire decoder.

---

<a id="中文"></a>

# 01 - 系統架構與資料流 (Architecture Overview)
[English](#english)

本章節介紹 **Document Parser for GoodNotes** 的整體系統設計、內部模組劃分、數據處理管道 (Data Pipeline)，以及 GoodNotes 5 與 GoodNotes 6 檔案格式的演進關聯。

---

## 系統整體架構 (System Architecture)

本工具包採層次化、模組化架構設計。低層專注於無模式 (Schema-free) 的解壓與位元組串流解碼，中層進行特徵提取與幾何重建，高層則提供 JSON 與 SVG 向量繪製與 CLI 介面。

```mermaid
flowchart TD
    A[".goodnotes Archive (ZIP File)"] --> B["archive.py (GoodNotesDocument)"]
    
    subgraph LowLevel["1. 低階解壓與二進制 Wire 解碼 (Low-Level Decoding)"]
        B --> C["wire.py (Protobuf Wire Decoder)"]
        B --> D["compression.py (Apple LZ4 Stream Decoder)"]
        D --> E["tpl.py (Troy Hanson TPL Parser)"]
    end
    
    subgraph MidLevel["2. 特徵提取與幾何重建 (Feature Extraction & Reconstruction)"]
        C & E --> F["stroke.py (Ink Stroke & Color Trailer Extractor)"]
        C --> G["shape.py (Vector Shape Geometry Parser)"]
        C & D --> H["text.py (Rich Text & RTF Extractor)"]
        C --> I["element.py (Image Crop & Sticky Note Parser)"]
        B & C --> J["pdf.py (PDF MediaBox & Background Renderer)"]
    end
    
    subgraph HighLevel["3. 模型聚合與導出 (Page Model & Export Subsystem)"]
        F & G & H & I & J --> K["page.py (Page & PageDimensions Model)"]
        K --> L["export.py (JSON & SVG Renderers)"]
        L --> M["cli.py (gn-inspect, gn-dump, gn-diff, gn-export-*)"]
    end
```

---

## 核心模組職責對照表 (Module Breakdown)

專案源碼位於 [`src/goodnotes_re/`](../src/goodnotes_re/)，各模組職責劃分如下：

| 模組名稱 | 絕對路徑 / Clickable Link | 核心職責與功能 |
| :--- | :--- | :--- |
| **`wire.py`** | [`src/goodnotes_re/wire.py`](../src/goodnotes_re/wire.py) | **Protobuf Wire 解碼器**。實現 7-bit Varint 讀取、WireType 判定、Length-Delimited 解碼與串流分幀 (`decode_delimited_messages`)。不需 `.proto` 即可保持完整位元組結構。 |
| **`archive.py`** | [`src/goodnotes_re/archive.py`](../src/goodnotes_re/archive.py) | **ZIP 檔案封裝管理**。提供 `GoodNotesDocument` 類別，負責讀取內部成員檔（如 `index.notes.pb`, `notes/<UUID>`）、生成 Inventory 清單與計算 SHA256。 |
| **`compression.py`** | [`src/goodnotes_re/compression.py`](../src/goodnotes_re/compression.py) | **Apple Framed LZ4 解壓縮**。解碼以 `bv41`/`bv4-` 為標頭、`bv4$` 為結尾的 Apple 專有 LZ4 串流，維護 64KB 歷史視窗。 |
| **`tpl.py`** | [`src/goodnotes_re/tpl.py`](../src/goodnotes_re/tpl.py) | **Troy Hanson TPL 記憶體映像解析**。解析 C 語言 TPL 庫寫出的二進制點陣與字串格式描述符（ Format Strings，如 `vuA(v)...`）。 |
| **`stroke.py`** | [`src/goodnotes_re/stroke.py`](../src/goodnotes_re/stroke.py) | **筆跡與顏色解析**。結合 TPL 控制點提取壓感、計算平滑法向量；並解析 `bv4$` 後方的 Protobuf Trailer 提取 RGBA 顏色與 Lasso 移動偏移量 `(dx, dy)`；處理 v9 橡皮擦切口。 |
| **`shape.py`** | [`src/goodnotes_re/shape.py`](../src/goodnotes_re/shape.py) | **向量圖形解析**。從 Protobuf Record（Tag 9, 21, 22 等）解析矩形、橢圓、多邊形、虛線模式 (`dash_pattern`) 與箭頭樣式。 |
| **`text.py`** | [`src/goodnotes_re/text.py`](../src/goodnotes_re/text.py) | **富文本與 RTF 解析**。解碼 Type 35 / bv41 打字機文字框的字型、字號、顏色、對齊方式、列表樣式，以及舊版 RTF Payload。 |
| **`element.py`** | [`src/goodnotes_re/element.py`](../src/goodnotes_re/element.py) | **頁面元素特徵抽象**。解析圖片貼圖（包含邊界框、裁切 Crop 參數與旋轉角度）、便條紙 (Sticky Notes) 狀態（展開/折疊）與記錄墓碑 (Tombstone)。 |
| **`page.py`** | [`src/goodnotes_re/page.py`](../src/goodnotes_re/page.py) | **頁面模型 (Page Model)**。結合 PDF `/MediaBox` 尺寸解析（132 DPI 到 72 DPI 轉換），聚合單頁中的筆跡、圖形、文字、圖片與背景。 |
| **`pdf.py`** | [`src/goodnotes_re/pdf.py`](../src/goodnotes_re/pdf.py) | **PDF 背景繪製**。利用 PyMuPDF (fitz) 將 `.goodnotes` 內嵌的 PDF 附件頁面渲染為向量 SVG path 或圖像背景。 |
| **`export.py`** | [`src/goodnotes_re/export.py`](../src/goodnotes_re/export.py) | **匯出器 (JSON & SVG)**。將頁面模型轉換為完整 JSON 結構或高忠實度 SVG 向量圖。 |
| **`cli.py`** | [`src/goodnotes_re/cli.py`](../src/goodnotes_re/cli.py) | **命令行工具集**。提供 `gn-inspect`、`gn-dump`、`gn-diff`、`gn-export-json` 與 `gn-export-svg` 進入點。 |

---

## 解析管道與資料流 (Data Pipeline Flow)

當調用 `gn-export-svg sample.goodnotes -o output_dir` 時，資料的流動過程如下：

```
[sample.goodnotes (ZIP Archive)]
       │
       ▼
1. GoodNotesDocument.open() 
   └─ 解開 ZIP 檔案目錄清單 (Inventory)
       │
       ▼
2. GoodNotesDocument.pages()
   ├─ 1. 讀取 index.notes.pb 獲取頁面 UUID 順序 (`notes/<UUID>`)
   ├─ 2. 讀取 index.attachments.pb / index.events.pb 綁定背景 PDF
   └─ 3. 對每一個 `notes/<UUID>` 成員調用 decode_records()
       │
       ▼
3. Record 逐筆解析 (parse_page_from_records)
   ├─ 偵測 Tag 含有 "bv41" 關鍵字 ──► decode_apple_lz4() 解壓 ──► decode_tpl() 解點陣
   │                                                             │
   │                                                             ▼
   │                                             parse_stroke_field() 提取點、壓感、RGBA Color
   ├─ 偵測 Tag 9 / Tag 21 / Tag 22 ────────────────────────────► parse_shape_record() 構建圖形
   ├─ 偵測 Tag 16 == 35 或 Rich Text ──────────────────────────► parse_text_elements() 提取文字
   └─ 偵測 Tag 4 Attachment ──────────────────────────────────► parse_image_elements() 提取圖片與 Crop
       │
       ▼
4. 建立 Page 實體 (含 PageDimensions: PDF MediaBox Scaling 72/132)
       │
       ▼
5. write_svg() (export.py)
   └─ 按圖層 (PDF Background -> Sticky Note Cards -> Shapes -> Strokes -> Images -> Text) 產生 SVG
```

---

## GoodNotes 5 與 GoodNotes 6 格式比較 (GN5 vs GN6 Evolution)

GoodNotes 5 (GN5) 與 GoodNotes 6 (GN6) 在底層儲存結構上保持高度相容，皆使用 ZIP + Length-Delimited Protobuf + Apple LZ4 + TPL 結構。主要差異如下表：

| 評估項目 | GoodNotes 5 (GN5) | GoodNotes 6 (GN6) | 本工具包相容機制 |
| :--- | :--- | :--- | :--- |
| **檔案副檔名** | `.goodnotes` | `.goodnotes` | 均為標準 ZIP 格式，使用 `zipfile` 讀取。 |
| **Protobuf Record Framing** | Varint 前綴分幀 (Length-delimited records) | Varint 前綴分幀 或 Tag 7 包裹的內嵌 Record | `decode_records()` 會自動檢測是直接分幀或是包裹在 Tag 7 內。 |
| **筆跡座標格式** | TPL 經典 4 元組 (`uuuu`) / 11 元組 (`uuuuuuuuuuu`) | 增加動態高密度 6-float/3-float/5-float 格式 | `extract_points_from_tpl()` 內建多重 Format 匹配機制。 |
| **圖形與箭頭** | Tag 9 基本手繪圖形 | 增加 Tag 21 (Type 35)、Tag 22 (Type 31) 複雜圖形與箭頭 Marker | `shape.py` 全面支援 Type 31/35 的 3 種箭頭樣式與圓角矩形。 |
| **文字框與便條紙** | RTF Payload 或 UTF-8 區塊 | 擴充 Type 35 bv41 封裝富文本 (含字型/顏色/列表/對齊) | `text.py` 自動支援打字機文本與 RTF 的 CP950/UTF-8 解析。 |

---

在下一章 **[02 - ZIP 容器與 Protobuf Wire 解析](02-archive-and-wire-format#中文)** 中，我們將深入剖析 ZIP 包內的檔案分佈以及無模式 Protobuf Wire 解碼器的低階位元組讀取原理。
