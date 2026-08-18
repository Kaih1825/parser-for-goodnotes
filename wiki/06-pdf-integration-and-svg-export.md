<a id="english"></a>

# 06 - PDF Backgrounds and SVG Vector Export (PDF & SVG Integration)
[中文](#中文)

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

### In-Memory Streaming & Single-Page Rendering (`page_to_svg`)

To support high-throughput pipelines, WebAssembly (Pyodide) browser environments, and multi-page notebooks with over 100+ pages without disk I/O overhead, the engine exports [`page_to_svg()`](../src/goodnotes_re/export.py):

```python
from goodnotes_re import GoodNotesDocument, page_to_svg

with GoodNotesDocument.open("notebook.goodnotes") as doc:
    pages = doc.pages(parse_all=True)
    # Stream SVG directly in memory (zero disk I/O, O(1) per page)
    svg_content = page_to_svg(pages[0], doc, fill_shapes=True)
```

This avoids creating temporary directories or rewriting entire documents on every page access.

---

## 5. Multi-Page Vector PDF Compilation (`CairoSVG` + `PyMuPDF`)

GoodNotes notebooks can be compiled directly into multi-page PDF documents while preserving 100% of the SVG rendering logic:

1. **Vector Rendering (`CairoSVG`)**:
   - Each page is first rendered to SVG according to the document's vector geometries.
   - `cairosvg.svg2pdf(bytestring=svg_bytes)` converts each SVG into lossless vector PDF bytes (`svg_to_pdf_bytes`).
   - All SVG features—such as dashed stroke patterns (`stroke-dasharray`), sticky notes (folded/expanded states), rotated stickers, and arrowhead markers—are faithfully converted.
2. **Multi-Page Merging (`PyMuPDF`)**:
   - Each page's PDF stream is inserted in sequence into a unified PyMuPDF document (`fitz.open()`), producing a single multi-page `.pdf` file.
3. **Graceful Fallback**:
   - If CairoSVG or `libcairo` is unavailable on a minimal environment, the engine gracefully falls back to PyMuPDF's built-in vector converter without crashing.

---

## 6. Language-Aware CJK Font Fallback Stack

GoodNotes on Apple devices defaults text box font families to Western fonts (such as `Helvetica Neue`, `Courier New`, or `Avenir`). When exporting to SVG and CairoSVG PDF, Western fonts lack CJK glyphs.

The engine implements a **Language-Aware Font Stack** (`_format_font_family_stack`):

- **Script Detection**: Detects Chinese Hanzi (`0x4E00..0x9FFF`), Japanese Hiragana/Katakana (`0x3040..0x30FF`), or Korean Hangul (`0xAC00..0xD7AF`).
- **Prioritization**:
  - **Traditional / Simplified Chinese**: Puts `PingFang TC`, `PingFang SC`, `Heiti TC`, `Microsoft JhengHei`, `Microsoft YaHei` first.
  - **Japanese**: Puts `Hiragino Sans`, `Hiragino Kaku Gothic ProN`, `Yu Gothic`, `Meiryo`, `Noto Sans JP` first.
  - **Korean**: Puts `Apple SD Gothic Neo`, `Malgun Gothic`, `NanumGothic`, `Noto Sans KR` first.
  - **Latin / ASCII**: Preserves the original font family (e.g., `Helvetica Neue`) first.
- Prevents missing glyph tofu boxes (□) across all major platforms.

---

In the next chapter, **[07 - CLI Tools and Python API Guide](07-cli-and-api-guide#english)**, we will demonstrate the usage of each command-line instruction and provide calling examples for the Python library in detail.

---

<a id="中文"></a>

# 06 - PDF 底圖與 SVG 向量匯出 (PDF & SVG Integration)
[English](#english)

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

### 常見紙張尺寸參考表 (72 DPI Points)

- **A4 直向**: 595.28 x 841.89 pt
- **A4 橫向**: 841.89 x 595.28 pt
- **Letter 直向**: 612.00 x 792.00 pt
- **GoodNotes 預設範本**: 595.00 x 842.00 pt

---

## 2. 空間座標轉換矩陣 (132 DPI 轉 72 DPI Scale Factor)

在格式逆向過程中，最核心的發現之一是 **GoodNotes 內部幾何座標空間**：

- **GoodNotes 內部座標系統**：基於 **132 DPI** 的像素網格。
- **標準 PDF / SVG 畫布座標系統**：基於 **72 DPI** Points（1 Point = 1/72 Inch）。

因此，要將 GoodNotes 筆跡座標 $(x_{\text{gn}}, y_{\text{gn}})$ 完美貼合到底圖 PDF 上，必須套用縮放比例因子 $S$：

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

### 純記憶體高效串流與單頁渲染 (`page_to_svg`)

為支援高輸送量管線、WebAssembly (Pyodide) 瀏覽器前端環境，以及在處理超過 100+ 頁的大型筆記本時避免頻繁寫入實體/虛擬磁碟產生的 I/O 開銷，核心引擎提供了 [`page_to_svg()`](../src/goodnotes_re/export.py)：

```python
from goodnotes_re import GoodNotesDocument, page_to_svg

with GoodNotesDocument.open("notebook.goodnotes") as doc:
    pages = doc.pages(parse_all=True)
    # 純記憶體快速產生單頁 SVG 字串（零磁碟 I/O，單頁 O(1) 秒開）
    svg_content = page_to_svg(pages[0], doc, fill_shapes=True)
```

此機制大幅降低了重複建立暫存目錄的開銷，令多頁筆記與網頁端體驗更為敏捷。

---

## 5. 多頁向量 PDF 輸出整合 (`CairoSVG` + `PyMuPDF`)

GoodNotes 文件可直接編譯打包為高品質多頁 PDF：

1. **向量轉譯 (`CairoSVG`)**：
   - 每頁先透過完整的 GoodNotes 幾何渲染引擎生成 SVG。
   - 使用 `cairosvg.svg2pdf(bytestring=svg_bytes)` 直接將 SVG 轉為 PDF 二進位位元組（`pdf_bytes`）。
   - **完全保留所有向量細節**：包括虛線（`stroke-dasharray`）、便條紙折角與文字、箭頭 marker、貼紙旋轉遮罩等。
2. **多頁合併 (`PyMuPDF`)**：
   - 將各頁產生的 PDF 頁面依序插入 PyMuPDF 文件中合併輸出為單一 `.pdf` 檔案。
3. **容錯回退機制**：
   - 若極端環境未安裝 `libcairo`，程式會自動平滑降級為 PyMuPDF 內建引擎完成轉換，確保跨平台相容性。

---

## 6. 多語系 CJK 智慧字型回退機制 (Language-Aware Font Stack)

GoodNotes 在 iOS 上通常預設使用西文字體（如 `Helvetica Neue`），當使用者輸入中日韓文字時，若未妥善處理字型鏈，Cairo 轉 PDF 會因西文字型缺乏 CJK 字形而出現方塊缺字（豆腐塊 □）。

本庫實作了**語系感知字型調度**（`_format_font_family_stack`）：

- **字元語系自動偵測**：即時識別中文漢字 (`0x4E00..0x9FFF`)、日文平假名/片假名 (`0x3040..0x30FF`) 或韓文諺文 (`0xAC00..0xD7AF`)。
- **優先級自動調度**：
  - **繁體/簡體中文**：優先置入 `PingFang TC`, `PingFang SC`, `Heiti TC`, `微軟正黑體`, `微軟雅黑`。
  - **日文**：優先置入 `Hiragino Sans`, `Hiragino Kaku Gothic ProN`, `Yu Gothic`, `Meiryo`, `Noto Sans JP`。
  - **韓文**：優先置入 `Apple SD Gothic Neo`, `Malgun Gothic`, `NanumGothic`, `Noto Sans KR`。
  - **純英文數字**：優先保留原始指定字型（如 `Helvetica Neue`）。
- 確保在任何系統環境下均能輸出工整清晰的向量文字。

---

在下一章 **[07 - CLI 工具與 Python API 指南](07-cli-and-api-guide#中文)** 中，我們將詳細示範各命令列指令的使用方式與 Python 程式庫的調用範例。
