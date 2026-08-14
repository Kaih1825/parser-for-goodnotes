[中文](#中文)

<a id="english"></a>

# 05 - Shapes, Text & Elements

This chapter introduces the analysis of various geometric and multimedia elements recorded on GoodNotes pages, including vector shapes, marker arrows, rich text/typewriter text elements, sticky notes, and image attachments & crops.

---

## 1. Vector Shape Geometry Analysis (`shape.py`)

In GoodNotes, hand-drawn auto-recognized shapes (such as lines, circles, rectangles, polygons, and arrows) are stored in specific tags within the Protobuf Record.

### Shape Protobuf Tag Structure Classification

| Shape Type | Tag Source | Geometric Data Structure and Analysis Method (`shape.py`) |
| :--- | :--- | :--- |
| **Hand-drawn Polygon / Polyline** | Tag 1 or Tag 2 inside Tag 9 | Contains repeated child Messages, each with a FIXED32 $x, y$ coordinate pair. Read by sorting Tags using `_extract_point()`. |
| **Tilted Ellipse / Circle** | Tag 4 inside Tag 9 | `f1` is the center point $(c_x, c_y)$, `f2` is the semi-major/minor axis $(r_x, r_y)$, `f3` is the rotation angle $\theta$ (radians). 144 vertices are calculated based on the parametric equation of an ellipse. |
| **Axis-Aligned Rectangle** | Tag 3 inside Tag 9 | `f1` is the center point $(c_x, c_y)$, `f2` is the full width and height $(w, h)$. Derives the top-left, top-right, bottom-right, and bottom-left vertices. |
| **Type 31 / Type 35 Advanced Shape** | Record inside Tag 21 / Tag 22 | Includes `_parse_type31_shape` (polyline/arrow) and `_parse_type35_shape` (rounded rectangle, capsule shape, dashed style `dash_pattern`). |

---

## 2. Endpoint Arrow Marker and Dynamic `refX` Alignment

GoodNotes supports adding different marker styles at the ends of lines or arrows (such as open V-shaped arrows, solid triangle arrows, and dots).

### 3 Arrow Styles and Alignment Calculation

In SVG, `<marker>` is defined using `<defs>`, and its `orient="auto"` can automatically rotate along the line tangent. However, the arrow vertex must be precisely aligned with the line endpoint, otherwise overlapping or suspension will occur.

[`export.py`](../src/goodnotes_re/export.py) implements the dynamic `refX` calculation function `_get_marker_ref_x()`:

```python
def _get_marker_ref_x(path_d: str, align: str = "tip") -> float:
    coords = [float(x) for x in re.findall(r"[-+]?\d*\.\d+|\d+", path_d)]
    x_coords = coords[0::2]
    if align == "min": return min(x_coords)
    elif align == "max": return max(x_coords)
    return (min(x_coords) + max(x_coords)) / 2.0
```

| Arrow Code (`start_arrow`/`end_arrow`) | Style Name | Marker Path | `refX` Formula and Alignment Anchor |
| :---: | :--- | :--- | :--- |
| **`1`** | Open V-Shape | `M 10 0 L 0 5 L 10 10` | Vertex aligned (`align="min"` or `"max"`), the line perfectly pierces the V-shape tip. |
| **`2` / `True`** | Solid Triangle | `M 10 0 L 0 5 L 10 10 Z` | Base aligned, the bottom of the solid triangle sits flush with the line endpoint. |
| **`3`+** | Circle Dot | `circle cx="5" cy="5" r="4"` | Center aligned (`refX=5, refY=5`). |

---

## 3. Typewriter Rich Text Box and RTF Parsing (`text.py`)

Typewriter text boxes (Text Elements) in GoodNotes are stored within the Type 35 Record, and contain detailed rich text formatting information after being decompressed via Apple LZ4.

### Text Box Structure Mapping (`parse_text_elements`)

- **Text Box Spatial Position**: Read pixel coordinates $(x, y)$ from Tag 20 / Tag 32 `f2` of the `msg`.
- **Text Box Width & Height Bounds**: Read physical width and height $(w, h)$ from Tag 32 `f10` / `f2`.
- **Default Font and Size**: Extract `default_font` (e.g., `"Helvetica Neue"`) and `default_size` (e.g., `24.0`) from Tag 32 `f5`.
- **Embedded Payload (bv41 LZ4)**: Iterate through sub-fields after decompression:
  - `f1`: UTF-8 text string.
  - `f2`: Formatting control. `f1==1` for Strikethrough, `f2==1` for Underline, `f50==1` for Italic, `f60` / font name containing "Bold" for Bold; `f3` for color RGBA, `f30` for font, `f40` for font size.
  - `f3`: Paragraph control. `f3_3` is list type (`"bullet"` or `"numbered"`); `f4` is alignment (`1` left, `2` center, `3` right).

### Legacy RTF Fallback Parser (`rtf_to_text`)
For early or simple text, GoodNotes uses the RTF format. [`rtf_to_text()`](../src/goodnotes_re/text.py) uses a custom regular expression, decoding preferentially with Traditional Chinese (CP950) to accurately extract Chinese text and remove `\fonttbl` and RTF control characters.

---

## 4. Sticky Note Parsing (`Sticky Note`)

Sticky Notes in GoodNotes are yellow/colored cards where users can attach notes or messages.

In `parse_sticky_notes()` within [`element.py`](../src/goodnotes_re/element.py):
- **Card Attributes**: Extract $(x, y)$ coordinates, default size (256x256), background color `color_hex` (default yellow `#FAE778`), and author `author`.
- **Fold/Unfold State (`is_open`)**: Check Tag 7 for a hidden flag. If folded (`is_folded=True`), the SVG rendering will display it as a small sticky note icon with a folded corner at the bottom right; if unfolded, it will be rendered as a full translucent background card.

---

## 5. Image Attachments and Crop Matrix (`ImageElement`)

Image attachments are stored in the `attachments/<UUID>` directory (JPEG or PNG).

In `parse_image_elements()` within [`element.py`](../src/goodnotes_re/element.py):

### 1. Tombstone Detection
When an image is deleted or cut and moved to another page in GoodNotes, a record is left on the old page as a tombstone (same Record UUID and Attachment UUID), but its **Field 3 is set to 1** (`f3 == 1`). The parser will automatically filter out records where `f3 == 1` to avoid drawing deleted images.

### 2. Original Bounds and Crop Matrix
Images contain two sets of size information:
- **Original Bounding Box**: $(orig_x, orig_y, orig_w, orig_h)$.
- **Crop Bounding Box**: $(cx, cy, crop_w, crop_h)$ and rotation angle $\theta$ (`rotation_rad`).

During SVG export ([`export.py`](../src/goodnotes_re/export.py)):
If it detects that the image has been cropped (`crop_w != orig_w`):
It uses the SVG `<g transform="rotate(...)">` and child `<svg overflow="hidden">` container viewport to implement a Clipping Window, accurately restoring any shape cropping and rotation effects of images within GoodNotes.

---

In the next chapter, **[06 - PDF Integration and SVG Export](06-pdf-integration-and-svg-export.md)**, we will detail the analysis of PDF background dimensions, the 132 DPI and 72 DPI coordinate transformation matrices, and the layered drawing logic of the SVG canvas.

---

[English](#english)

<a id="中文"></a>

# 05 - 圖形、文字與頁面元素 (Shapes, Text & Elements)

本章節介紹 GoodNotes 頁面上記錄的各種幾何與多媒體元素解析，包含向量圖形 (Shapes)、端點箭頭 Marker、富文本/打字機文字框 (Text Elements)、便條紙 (Sticky Notes) 以及圖片貼圖與裁切 (Image Attachments & Crops)。

---

## 1. 向量圖形幾何解析 (`shape.py`)

GoodNotes 中的手繪自動識別圖形（如直線、圓形、矩形、多邊形、箭頭）儲存於 Protobuf Record 的特定標籤中。

### 圖形 Protobuf Tag 結構分類

| 圖形類型 | Tag 來源 | 幾何數據結構與解析方式 (`shape.py`) |
| :--- | :--- | :--- |
| **手繪多邊形 / 折線** | Tag 9 內部的 Tag 1 或 Tag 2 | 包含 repeated 子 Message，每個 Message 帶有 FIXED32 $x, y$ 座標對。使用 `_extract_point()` 排序 Tag 後讀取。 |
| **傾斜橢圓 / 圓形** | Tag 9 內部的 Tag 4 | `f1` 為中心點 $(c_x, c_y)$，`f2` 為半長短軸 $(r_x, r_y)$，`f3` 為旋轉弧度 $\theta$ (radians)。基於橢圓參數方程算 144 個頂點。 |
| **軸對齊矩形** | Tag 9 內部的 Tag 3 | `f1` 為中心點 $(c_x, c_y)$，`f2` 為完整寬高 $(w, h)$。反推左上、右上、右下、左下四個頂點。 |
| **Type 31 / Type 35 高級圖形** | Tag 21 / Tag 22 內的 Record | 包含 `_parse_type31_shape` (折線/箭頭) 與 `_parse_type35_shape` (圓角矩形、Capsule 膠囊形、虛線樣式 `dash_pattern`)。 |

---

## 2. 端點箭頭 Marker 與動態 `refX` 對齊

GoodNotes 支援在線條或箭頭兩端加上不同的 Marker 樣式（如開口 V 形箭頭、實心三角形箭頭、圓點）。

### 3 種箭頭樣式與對齊計算

在 SVG 中使用 `<defs>` 定義 `<marker>`，其 `orient="auto"` 能自動沿線條切線旋轉。但箭頭頂點必須精準對齊線條端點，否則會產生重疊或懸空。

[`export.py`](../src/goodnotes_re/export.py) 實現了動態 `refX` 計算函數 `_get_marker_ref_x()`：

```python
def _get_marker_ref_x(path_d: str, align: str = "tip") -> float:
    coords = [float(x) for x in re.findall(r"[-+]?\d*\.\d+|\d+", path_d)]
    x_coords = coords[0::2]
    if align == "min": return min(x_coords)
    elif align == "max": return max(x_coords)
    return (min(x_coords) + max(x_coords)) / 2.0
```

| 箭頭代碼 (`start_arrow`/`end_arrow`) | 樣式名稱 | Marker Path | `refX` 算式與對齊錨點 |
| :---: | :--- | :--- | :--- |
| **`1`** | Open V-Shape | `M 10 0 L 0 5 L 10 10` | 頂點對齊 (`align="min"` 或 `"max"`)，線條剛好刺入 V 形尖端。 |
| **`2` / `True`** | Solid Triangle | `M 10 0 L 0 5 L 10 10 Z` | 底邊對齊，實心三角形底部貼平線條端點。 |
| **`3`+** | Circle Dot | `circle cx="5" cy="5" r="4"` | 中心對齊 (`refX=5, refY=5`)。 |

---

## 3. 打字機富文本框與 RTF 解析 (`text.py`)

GoodNotes 中的打字機文字框（Text Element）儲存於 Type 35 Record 內，經 Apple LZ4 解壓後包含詳細的富文本排版資訊。

### 文字框結構對照 (`parse_text_elements`)

- **文字框空間位置**：從 `msg` 的 Tag 20 / Tag 32 `f2` 讀取像素座標 $(x, y)$。
- **文字框寬高邊界**：從 Tag 32 `f10` / `f2` 讀取物理寬高 $(w, h)$。
- **預設字型與字號**：從 Tag 32 `f5` 提取 `default_font` (如 `"Helvetica Neue"`) 與 `default_size` (如 `24.0`)。
- **內嵌 Payload (bv41 LZ4)**：解壓後遍歷子項欄位：
  - `f1`: UTF-8 文本字串。
  - `f2`: 格式控制。`f1==1` 刪除線 (Strikethrough)，`f2==1` 底線 (Underline)，`f50==1` 斜體 (Italic)，`f60` / 字型名稱含 "Bold" 為粗體 (Bold)；`f3` 顏色 RGBA，`f30` 字型，`f40` 字號。
  - `f3`: 段落控制。`f3_3` 為列表類型（`"bullet"` 項目符號 或 `"numbered"` 編號列表）；`f4` 為對齊方式（`1` 左對齊、`2` 居中、`3` 右對齊）。

### 舊版 RTF 備用解析 (`rtf_to_text`)
對於早期或簡單文字，GoodNotes 使用 RTF 格式。[`rtf_to_text()`](../src/goodnotes_re/text.py) 使用特製正則表達式，優先以 Traditional Chinese (CP950) 進行編碼解碼，精準提取中文文本並去除 `\fonttbl` 與 RTF 控制字元。

---

## 4. 便條紙解析 (`Sticky Note`)

便條紙（Sticky Note）在 GoodNotes 中是黃色/彩色卡片，上方可供使用者貼上記錄或留言。

在 [`element.py`](../src/goodnotes_re/element.py) 的 `parse_sticky_notes()` 中：
- **卡片屬性**：提取 $(x, y)$ 座標、預設尺寸 (256x256)、背景顏色 `color_hex` (預設黃色 `#FAE778`) 以及作者 `author`。
- **折疊/展開狀態 (`is_open`)**：檢視 Tag 7 內是否有隱藏標誌。若折疊 (`is_folded=True`)，SVG 繪製時會將其渲染為右下角帶有折角的便條紙小圖示；若展開，則渲染為完整的半透明背景卡片。

---

## 5. 圖片貼圖與裁切矩陣 (`ImageElement`)

圖片貼圖 (Image Attachment) 儲存在 `attachments/<UUID>` 目錄中（JPEG 或 PNG）。

在 [`element.py`](../src/goodnotes_re/element.py) 的 `parse_image_elements()` 中：

### 1. 墓碑標誌 (Tombstone Detection)
當圖片在 GoodNotes 中被刪除或剪下移動到其他頁面時，舊頁面上會留下一筆 Record 作為墓碑（相同的 Record UUID 與 Attachment UUID），但其 **Field 3 被設為 1** (`f3 == 1`)。解析器會自動過濾 `f3 == 1` 的記錄，避免繪製已刪除的圖片。

### 2. 原始邊界與裁切 Crop 矩陣
圖片包含兩組尺寸資訊：
- **原始邊界框 (Original Bounding Box)**：$(orig_x, orig_y, orig_w, orig_h)$。
- **裁切邊界框 (Crop Bounding Box)**：$(cx, cy, crop_w, crop_h)$ 及旋轉角度 $\theta$ (`rotation_rad`)。

在匯出 SVG 時（[`export.py`](../src/goodnotes_re/export.py)）：
若檢測到圖片被裁切（`crop_w != orig_w`）：
利用 SVG 的 `<g transform="rotate(...)">` 與子 `<svg overflow="hidden">` 容器視窗，實作視窗遮罩（Clipping Window），準確還原 GoodNotes 內圖片的任意形狀裁切與旋轉效果。

---

在下一章 **[06 - PDF 底圖與 SVG 向量匯出](06-pdf-integration-and-svg-export.md)** 中，我們將詳細說明 PDF 背景尺寸解析、132 DPI 與 72 DPI 坐標轉換矩陣，以及 SVG 畫布的分層繪製邏輯。
