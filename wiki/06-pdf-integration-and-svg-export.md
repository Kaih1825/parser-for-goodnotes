[中文](#中文)

<a id="english"></a>

# 06 - PDF Backgrounds and SVG Vector Export (PDF & SVG Integration)

This chapter explains how to parse GoodNotes' embedded PDF template backgrounds, the spatial coordinate transformation matrix between 132 DPI and 72 DPI, integration with PyMuPDF (fitz), and the complete details of rendering all strokes, shapes, and text into layered vector SVG image files.

---

## 1. Parsing PDF `/MediaBox` Dimensions and Orientation (`PageDimensions`)

The page dimensions of GoodNotes notebooks (such as A4, Letter, Landscape, Portrait) are determined by the embedded PDF templates or background files.

In [`src/goodnotes_re/page.py`](../src/goodnotes_re/page.py), `PageDimensions.from_pdf_mediabox()` reads the `/MediaBox` definition directly from the PDF binaries using regular expressions:

```python
@dataclass(frozen=True)
class PageDimensions:
    width: float = 612.0   # Default Letter width (72 DPI points)
    height: float = 792.0  # Default Letter height (72 DPI points)
    is_landscape: bool = False

    @classmethod
    def from_pdf_mediabox(cls, pdf_bytes: bytes) -> "PageDimensions":
        # Search for /MediaBox [ 0 0 width height ]
        m = re.search(b"/MediaBox\\s*\\[\\s*([\\d\\.]+)\\s+([\\d\\.]+)\\s+([\\d\\.]+)\\s+([\\d\\.]+)\\s*\\]", pdf_bytes)
        if m:
            w = float(m.group(3))
            h = float(m.group(4))
            return cls(width=w, height=h, is_landscape=w > h)
        return cls()
```

### Common Paper Size Reference (72 DPI Points)

- **A4 Portrait**: 595.28 x 841.89 pt
- **A4 Landscape**: 841.89 x 595.28 pt
- **Letter Portrait**: 612.00 x 792.00 pt
- **Standard GoodNotes Template**: 595.00 x 842.00 pt

---

## 2. Spatial Coordinate Transformation Matrix (132 DPI to 72 DPI Scale Factor)

During format analysis, one of the most critical discoveries was **GoodNotes' internal geometric coordinate space**:

- **GoodNotes Internal Coordinate System**: Based on a **132 DPI** pixel grid.
- **Standard PDF / SVG Canvas Coordinate System**: Based on **72 DPI** Points (1 Point = 1/72 Inch).

Therefore, to perfectly overlay GoodNotes stroke coordinates $(x_{\text{gn}}, y_{\text{gn}})$ onto the background PDF, a scaling factor $S$ must be applied:

$$S = \frac{72.0}{132.0} \approx 0.54545454...$$

$$\begin{bmatrix} x_{\text{svg}} \\ y_{\text{svg}} \end{bmatrix} = \begin{bmatrix} \frac{72}{132} & 0 \\ 0 & \frac{72}{132} \end{bmatrix} \begin{bmatrix} x_{\text{gn}} \\ y_{\text{gn}} \end{bmatrix}$$

In [`export.py`](../src/goodnotes_re/export.py), all Stroke control points, Shape coordinates, Text Box positions, and Image dimensions are multiplied by `dpi_scale = 72.0 / 132.0`. This makes the exported vector SVG **align 100% perfectly** with the original PDF exported by GoodNotes.

---

## 3. PyMuPDF Vector PDF Background Rendering (`pdf.py`)

When the `attachments/` in the `.goodnotes` file contains a background PDF file, [`src/goodnotes_re/pdf.py`](../src/goodnotes_re/pdf.py) uses the `fitz` (PyMuPDF) library to extract the vector graphics of that page:

```python
def render_pdf_page_to_svg(pdf_bytes: bytes, page_index: int, width: float, height: float) -> str | None:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    idx = min(page_index, len(doc) - 1)
    page = doc[idx]
    
    # Export as vector SVG
    svg_text = page.get_svg_image()
    
    # Extract the layer content inside the <svg> tag
    start = svg_text.find(">") + 1
    end = svg_text.rfind("</svg>")
    if start > 0 and end > start:
        inner_content = svg_text[start:end]
        return f'<g class="pdf-background">{inner_content}</g>'
    return None
```

If the background attachment is an image (JPEG / PNG), it is converted to a Base64 Data URI and seamlessly embedded using the SVG `<image>` tag.

---

## 4. SVG DOM Layering Architecture

To achieve visually correct overlay relationships (such as strokes drawn on the background, text positioned on the top layer), [`write_svg()`](../src/goodnotes_re/export.py) strictly writes the SVG DOM in the following layer order:

```
+-------------------------------------------------------------------+
| Top Layer: Text Boxes (<text> & Selection Bounds <rect>)          |  Layer 6
+-------------------------------------------------------------------+
| Layer 5: Image Attachments (<image> & Cropped <svg> Containers)   |  Layer 5
+-------------------------------------------------------------------+
| Layer 4: Ink Strokes (<path d="..." fill="color"/>)               |  Layer 4
+-------------------------------------------------------------------+
| Layer 3: Vector Shapes & Arrows (<ellipse>, <rect>, <marker>)     |  Layer 3
+-------------------------------------------------------------------+
| Layer 2: Sticky Notes Cards (<rect rx="8"> & Author Text)         |  Layer 2
+-------------------------------------------------------------------+
| Bottom Layer: PDF Background (<g class="pdf-background"> / Image) |  Layer 1
+-------------------------------------------------------------------+
```

### SVG Export Feature Option Controls

The `gn-export-svg` command-line tool provides various advanced rendering toggle switches:

- **`sticky_note_state` (`--sticky-note-state open|close`)**:
  - `open`: Force expands all sticky notes, drawing yellow translucent cards with their content.
  - `close`: Force collapses all sticky notes, drawing only a small sticky note icon in the top left corner.
- **`textbox_state` (`--textbox open|close`)**:
  - `open`: Draws sky blue (`#38BDF8`) bounding boxes around text boxes (restoring the GoodNotes IDE selection state).
- **`fill_shapes` (`--no-fill`)**:
  - Disables the translucent filling of vector shapes (`fill="none"`), drawing only the outlines.

---

In the next chapter, **[07 - CLI Tools and Python API Guide](07-cli-and-api-guide.md)**, we will demonstrate the usage of each command-line instruction and provide calling examples for the Python library in detail.

---

[English](#english)

<a id="中文"></a>

# 06 - PDF 底圖與 SVG 向量匯出 (PDF & SVG Integration)

本章節說明如何解析 GoodNotes 內嵌的 PDF 範本底圖、132 DPI 與 72 DPI 空間座標轉換矩陣、PyMuPDF (fitz) 整合，以及將所有筆跡、圖形與文字繪製為分層向量 SVG 圖檔的完整細節。

---

## 1. PDF `/MediaBox` 尺寸與方向解析 (`PageDimensions`)

GoodNotes 筆記的頁面尺寸（如 A4, Letter, 橫向 Landscape, 直向 Portrait）是由內嵌的 PDF 範本或背景檔案決定的。

在 [`src/goodnotes_re/page.py`](../src/goodnotes_re/page.py) 中，`PageDimensions.from_pdf_mediabox()` 透過正則表達式直接讀取 PDF 二進位檔中的 `/MediaBox` 定義：

```python
@dataclass(frozen=True)
class PageDimensions:
    width: float = 612.0   # 預設 Letter 寬度 (72 DPI points)
    height: float = 792.0  # 預設 Letter 高度 (72 DPI points)
    is_landscape: bool = False

    @classmethod
    def from_pdf_mediabox(cls, pdf_bytes: bytes) -> "PageDimensions":
        # 搜尋 /MediaBox [ 0 0 width height ]
        m = re.search(b"/MediaBox\\s*\\[\\s*([\\d\\.]+)\\s+([\\d\\.]+)\\s+([\\d\\.]+)\\s+([\\d\\.]+)\\s*\\]", pdf_bytes)
        if m:
            w = float(m.group(3))
            h = float(m.group(4))
            return cls(width=w, height=h, is_landscape=w > h)
        return cls()
```

### 常見紙張尺寸對照 (72 DPI Points)

- **A4 直向 (Portrait)**: 595.28 x 841.89 pt
- **A4 橫向 (Landscape)**: 841.89 x 595.28 pt
- **Letter 直向 (Portrait)**: 612.00 x 792.00 pt
- **Standard GoodNotes Template**: 595.00 x 842.00 pt

---

## 2. 空間座標轉換矩陣 (132 DPI to 72 DPI Scale Factor)

在格式分析過程中，最為關鍵的一項發現是 **GoodNotes 的內部幾何座標空間 (Coordinate Space)**：

- **GoodNotes 內部座標系統**：基於 **132 DPI** 像素網格。
- **標準 PDF / SVG 畫布座標系統**：基於 **72 DPI** Points（1 Point = 1/72 Inch）。

因此，要將 GoodNotes 的筆跡座標 $(x_{\text{gn}}, y_{\text{gn}})$ 完美的對疊在背景 PDF 上，必須套用縮放比例因子 $S$：

$$S = \frac{72.0}{132.0} \approx 0.54545454...$$

$$\begin{bmatrix} x_{\text{svg}} \\ y_{\text{svg}} \end{bmatrix} = \begin{bmatrix} \frac{72}{132} & 0 \\ 0 & \frac{72}{132} \end{bmatrix} \begin{bmatrix} x_{\text{gn}} \\ y_{\text{gn}} \end{bmatrix}$$

在 [`export.py`](../src/goodnotes_re/export.py) 中，所有 Stroke 控制點、Shape 座標、Text Box 位置與 Image 尺寸，均乘以 `dpi_scale = 72.0 / 132.0`。這使得導出的向量 SVG 與 GoodNotes 導出的原廠 PDF **達到 100% 完全重合**。

---

## 3. PyMuPDF 向量 PDF 底圖渲染 (`pdf.py`)

當 `.goodnotes` 檔案的 `attachments/` 中包含背景 PDF 檔案時，[`src/goodnotes_re/pdf.py`](../src/goodnotes_re/pdf.py) 利用 `fitz` (PyMuPDF) 庫提取該頁面的矢量圖形：

```python
def render_pdf_page_to_svg(pdf_bytes: bytes, page_index: int, width: float, height: float) -> str | None:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    idx = min(page_index, len(doc) - 1)
    page = doc[idx]
    
    # 導出為向量 SVG
    svg_text = page.get_svg_image()
    
    # 提取 <svg> 標籤內部的圖層內容
    start = svg_text.find(">") + 1
    end = svg_text.rfind("</svg>")
    if start > 0 and end > start:
        inner_content = svg_text[start:end]
        return f'<g class="pdf-background">{inner_content}</g>'
    return None
```

如果背景附件是圖片（JPEG / PNG），則轉換為 Base64 Data URI 並使用 SVG `<image>` 標籤無縫內嵌。

---

## 4. SVG DOM 分層繪製順序 (SVG Layering Architecture)

為了實現視覺上的正確覆蓋關係（如筆跡畫在背景上、文字位在最上層），[`write_svg()`](../src/goodnotes_re/export.py) 嚴格按照以下圖層順序寫入 SVG DOM：

```
+-------------------------------------------------------------------+
| Top Layer: Text Boxes (<text> & Selection Bounds <rect>)          |  Layer 6
+-------------------------------------------------------------------+
| Layer 5: Image Attachments (<image> & Cropped <svg> Containers)   |  Layer 5
+-------------------------------------------------------------------+
| Layer 4: Ink Strokes (<path d="..." fill="color"/>)               |  Layer 4
+-------------------------------------------------------------------+
| Layer 3: Vector Shapes & Arrows (<ellipse>, <rect>, <marker>)     |  Layer 3
+-------------------------------------------------------------------+
| Layer 2: Sticky Notes Cards (<rect rx="8"> & Author Text)         |  Layer 2
+-------------------------------------------------------------------+
| Bottom Layer: PDF Background (<g class="pdf-background"> / Image) |  Layer 1
+-------------------------------------------------------------------+
```

### SVG 導出功能選項控制

`gn-export-svg` 命令行工具提供多種高級繪製切換開關：

- **`sticky_note_state` (`--sticky-note-state open|close`)**：
  - `open`：強制展開所有便條紙，繪製黃色半透明卡片與內文。
  - `close`：強制折疊所有便條紙，僅在左上角繪製小巧的便條紙圖示。
- **`textbox_state` (`--textbox open|close`)**：
  - `open`：繪製天藍色 (`#38BDF8`) 的文字框外框選取邊界（還原 GoodNotes IDE 選取狀態）。
- **`fill_shapes` (`--no-fill`)**：
  - 關閉向量圖形的半透明填色 (`fill="none"`)，僅繪製外框。

---

在下一章 **[07 - CLI 工具與 Python API 指南](07-cli-and-api-guide.md)** 中，我們將詳細示範各命令列指令的使用方式與 Python 程式庫的調用範例。
