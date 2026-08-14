[中文](#中文)

<a id="english"></a>

# 07 - CLI & Python API Guide

This chapter provides instructions for using the **Document Parser for GoodNotes** command-line interface (CLI) tools and the Python API library.

---

## 1. CLI Tool Suite

After installation, the package provides 5 global command-line tools (which can also be invoked via `python3 -m goodnotes_re.cli`):

```
                                ┌── gn-inspect (Inspect ZIP file directory and SHA256)
                                ├── gn-dump (Lossless dump to JSON)
python3 -m goodnotes_re.cli ───┼── gn-diff (Compare differences between two .goodnotes members)
                                ├── gn-export-json (Export full structure as JSON)
                                └── gn-export-svg (Export vector SVG pages)
```

---

### 1.1 `gn-inspect` - Inspect Inventory and SHA256 Checksums

Used to quickly inspect which Protobuf members and media attachments are included inside a `.goodnotes` file, listing sizes and the first 12 characters of their SHA256 checksums.

```sh
gn-inspect samples/Teat.goodnotes
```

**Example Output:**
```text
protobuf      2 byte  schema.pb  sha256:0a2e38c119d4
protobuf     148 byte  index.notes.pb  sha256:5b839f201d4a
protobuf      84 byte  index.attachments.pb  sha256:19e48102fa9c
protobuf   12840 byte  notes/31BE4069-02E5-4C5D-BFF9-2A8DCBC744E9  sha256:e3b0c44298fc
asset    1082491 byte  attachments/31BE4069-02E5-4C5D-BFF9-2A8DCBC744E9  sha256:8f3c7a...
```

---

### 1.2 `gn-dump` - Lossless Conversion of Single Protobuf Member to JSON

Decodes any `.pb` or `notes/<UUID>` field inside a `.goodnotes` file, outputting lossless JSON containing Tag numbers, Wire Types, Offsets, and Base64 data.

```sh
gn-dump samples/Teat.goodnotes index.notes.pb
```

---

### 1.3 `gn-diff` - Compare Differences Between Two `.goodnotes` Files

When conducting format analysis controlled experiments, compares two files with only a single modification (such as `before.goodnotes` before an operation and `after.goodnotes` after an operation).

```sh
gn-diff before.goodnotes after.goodnotes
```

**Example Output:**
```text
CHANGED  index.notes.pb
ADDED    attachments/7F129B44-55C1-4D30-8812-4E1B88944E1B
CHANGED  notes/31BE4069-02E5-4C5D-BFF9-2A8DCBC744E9
```

---

### 1.4 `gn-export-json` - Export Full JSON Structure

Exports all pages, ink strokes, pressure data, RGBA colors, shapes, typewriter text, and raw wire data of the entire notebook into a single JSON file.

```sh
gn-export-json samples/Teat.goodnotes -o document.json
```

---

### 1.5 `gn-export-svg` - Export High-Fidelity SVG Vector Pages

Renders each page of the entire notebook as independent, high-resolution SVG vector graphics.

```sh
gn-export-svg samples/Teat.goodnotes -o pages-svg/
```

#### Advanced Parameters:
- `-s, --sticky-note-state {open,close,auto}`: Controls sticky note state (`open` expands the card, `close` collapses the icon).
- `-b, --textbox {open,close}`: Controls whether to draw the blue text selection bounding box (`open` displays the border).
- `--no-fill`: Disables filling for vector shapes.

```sh
# Example: Generate SVGs displaying text bounding boxes and expanded sticky notes
gn-export-svg samples/Teat.goodnotes -o output_svgs/ -b open -s open
```

---

## 2. Python API Guide

The core API is encapsulated in the `GoodNotesDocument` class.

### 2.1 Opening and Reading Documents

```python
from goodnotes_re import GoodNotesDocument

with GoodNotesDocument.open("samples/Teat.goodnotes") as doc:
    # Get internal file inventory
    members = doc.inventory()
    for m in members:
        print(m.path, m.size, m.sha256)
        
    # Read member bytes directly
    raw_data = doc.read("schema.pb")
```

---

### 2.2 Iterating Over Pages, Strokes, and Pressure Points

```python
with GoodNotesDocument.open("samples/Teat.goodnotes") as doc:
    pages = doc.pages()
    for page in pages:
        print(f"=== Page {page.index + 1} (UUID: {page.uuid}) ===")
        print(f"Dimensions: {page.dimensions.width} x {page.dimensions.height} pt, Landscape: {page.dimensions.is_landscape}")
        
        # Iterate over strokes
        for stroke in page.strokes:
            print(f"Stroke UUID: {stroke.uuid}")
            print(f"  Color: {stroke.color_hex}, Alpha: {stroke.alpha}")
            print(f"  Width: {stroke.width}, Highlighter: {stroke.is_highlighter}")
            print(f"  Control points count: {len(stroke.points)}")
            
            # Read specific control points (x, y, pressure)
            for pt in stroke.points[:3]:
                print(f"    Point: ({pt.x:.2f}, {pt.y:.2f}), pressure={pt.pressure:.2f}")
```

---

### 2.3 Reading Shapes and Typewriter Text Elements

```python
with GoodNotesDocument.open("samples/Teat.goodnotes") as doc:
    for page in doc.pages():
        # Read vector shapes
        for shape in page.shapes:
            print(f"Shape type: {shape.shape_type}, Color: {shape.color_hex}")
            print(f"  Vertices count: {len(shape.points)}")
            if shape.start_arrow or shape.end_arrow:
                print(f"  With arrow Marker: start={shape.start_arrow}, end={shape.end_arrow}")
                
        # Read typewriter rich text elements
        for te in page.text_elements:
            print(f"Text block [{te.x}, {te.y}]: {te.text}")
            print(f"  Font: {te.font_family}, Size: {te.font_size}, Bold: {te.is_bold}")
```

---

### 2.4 Directly Invoking the Vector SVG Exporter

```python
from pathlib import Path
from goodnotes_re import GoodNotesDocument
from goodnotes_re.export import write_svg

with GoodNotesDocument.open("samples/Teat.goodnotes") as doc:
    svg_paths = write_svg(
        document=doc,
        directory="output_svgs",
        fill_shapes=True,
        sticky_note_state="open",
        textbox_state="close"
    )
    print("Generated SVG files:", svg_paths)
```

---

In the next chapter, **[08 - Testing, Building, and Publishing](08-testing-building-publishing.md)**, we will explain how to set up the development environment, execute unit tests, maintain controlled format analysis experiment protocols, and package for publishing to PyPI.

---

[English](#english)

<a id="中文"></a>

# 07 - CLI 工具與 Python API 指南 (CLI & API Guide)

本章節提供 **Document Parser for GoodNotes** 的命令行 CLI 工具說明與 Python API 程式庫調用指南。

---

## 1. CLI 工具套件 (CLI Tool Suite)

套件安裝後會提供 5 個全域命令列工具（亦可透過 `python3 -m goodnotes_re.cli` 調用）：

```
                                ┌── gn-inspect (檢視 ZIP 檔案目錄與 SHA256)
                                ├── gn-dump (無損 dump 成 JSON)
python3 -m goodnotes_re.cli ───┼── gn-diff (比較兩個 .goodnotes 成員差異)
                                ├── gn-export-json (匯出完整結構為 JSON)
                                └── gn-export-svg (匯出向量 SVG 頁面)
```

---

### 1.1 `gn-inspect` - 檢視清單與 SHA256 校驗碼

用於快速檢視 `.goodnotes` 檔案內部包含哪些 Protobuf 成員與媒體附件，並列出大小與 SHA256 前 12 碼。

```sh
gn-inspect samples/Teat.goodnotes
```

**輸出範例：**
```text
protobuf      2 byte  schema.pb  sha256:0a2e38c119d4
protobuf     148 byte  index.notes.pb  sha256:5b839f201d4a
protobuf      84 byte  index.attachments.pb  sha256:19e48102fa9c
protobuf   12840 byte  notes/31BE4069-02E5-4C5D-BFF9-2A8DCBC744E9  sha256:e3b0c44298fc
asset    1082491 byte  attachments/31BE4069-02E5-4C5D-BFF9-2A8DCBC744E9  sha256:8f3c7a...
```

---

### 1.2 `gn-dump` - 無損轉換單一 Protobuf 成員為 JSON

將 `.goodnotes` 檔案內部的任意 `.pb` 或 `notes/<UUID>` 欄位解碼，輸出帶有 Tag 號碼、Wire Type、Offset 與 Base64 的無損 JSON。

```sh
gn-dump samples/Teat.goodnotes index.notes.pb
```

---

### 1.3 `gn-diff` - 比較兩個 `.goodnotes` 檔案差異

在進行格式分析控制實驗 (Controlled Experiments) 時，比較兩個僅有一處修改的檔案（如操作前 `before.goodnotes` 與操作後 `after.goodnotes`）。

```sh
gn-diff before.goodnotes after.goodnotes
```

**輸出範例：**
```text
CHANGED  index.notes.pb
ADDED    attachments/7F129B44-55C1-4D30-8812-4E1B88944E1B
CHANGED  notes/31BE4069-02E5-4C5D-BFF9-2A8DCBC744E9
```

---

### 1.4 `gn-export-json` - 匯出完整 JSON 結構

將整本筆記的所有頁面、筆跡點陣、壓感、RGBA 顏色、圖形、打字機文本與 raw wire 數據導出為單一 JSON 檔案。

```sh
gn-export-json samples/Teat.goodnotes -o document.json
```

---

### 1.5 `gn-export-svg` - 匯出高忠實度 SVG 向量頁面

將整本筆記的每一頁渲染為獨立的高解析度 SVG 向量圖形。

```sh
gn-export-svg samples/Teat.goodnotes -o pages-svg/
```

#### 高級參數：
- `-s, --sticky-note-state {open,close,auto}`：控制便條紙狀態 (`open` 展開卡片, `close` 折疊圖示)。
- `-b, --textbox {open,close}`：控制是否繪製藍色文字選取框 (`open` 顯示外框)。
- `--no-fill`：關閉向量圖形填色。

```sh
# 範例：繪製顯示文字選取框且展開便條紙的 SVG
gn-export-svg samples/Teat.goodnotes -o output_svgs/ -b open -s open
```

---

## 2. Python 程式庫 API 指南 (Python API Guide)

核心 API 封裝於 `GoodNotesDocument` 類別中。

### 2.1 開啟與讀取文件

```python
from goodnotes_re import GoodNotesDocument

with GoodNotesDocument.open("samples/Teat.goodnotes") as doc:
    # 取得內部檔案列表
    members = doc.inventory()
    for m in members:
        print(m.path, m.size, m.sha256)
        
    # 直接讀取成員 bytes
    raw_data = doc.read("schema.pb")
```

---

### 2.2 遍歷頁面、筆跡與壓感點

```python
with GoodNotesDocument.open("samples/Teat.goodnotes") as doc:
    pages = doc.pages()
    for page in pages:
        print(f"=== 頁面 {page.index + 1} (UUID: {page.uuid}) ===")
        print(f"尺寸: {page.dimensions.width} x {page.dimensions.height} pt, 橫向: {page.dimensions.is_landscape}")
        
        # 遍歷筆跡 (Strokes)
        for stroke in page.strokes:
            print(f"筆跡 UUID: {stroke.uuid}")
            print(f"  顏色: {stroke.color_hex}, 透明度 Alpha: {stroke.alpha}")
            print(f"  筆寬: {stroke.width}, 螢光筆: {stroke.is_highlighter}")
            print(f"  控制點數量: {len(stroke.points)}")
            
            # 讀取具體控制點 (x, y, pressure)
            for pt in stroke.points[:3]:
                print(f"    Point: ({pt.x:.2f}, {pt.y:.2f}), pressure={pt.pressure:.2f}")
```

---

### 2.3 讀取圖形 (Shapes) 與打字機文字 (Text Elements)

```python
with GoodNotesDocument.open("samples/Teat.goodnotes") as doc:
    for page in doc.pages():
        # 讀取向量圖形
        for shape in page.shapes:
            print(f"圖形類型: {shape.shape_type}, 顏色: {shape.color_hex}")
            print(f"  頂點數量: {len(shape.points)}")
            if shape.start_arrow or shape.end_arrow:
                print(f"  帶有箭頭 Marker: start={shape.start_arrow}, end={shape.end_arrow}")
                
        # 讀取打字機富文本框
        for te in page.text_elements:
            print(f"文字區塊 [{te.x}, {te.y}]: {te.text}")
            print(f"  字型: {te.font_family}, 字號: {te.font_size}, 粗體: {te.is_bold}")
```

---

### 2.4 直接調用向量 SVG 匯出器

```python
from pathlib import Path
from goodnotes_re import GoodNotesDocument
from goodnotes_re.export import write_svg

with GoodNotesDocument.open("samples/Teat.goodnotes") as doc:
    svg_paths = write_svg(
        document=doc,
        directory="output_svgs",
        fill_shapes=True,
        sticky_note_state="open",
        textbox_state="close"
    )
    print("生成的 SVG 檔案列表:", svg_paths)
```

---

在下一章 **[08 - 開發、測試、打包與發佈](08-testing-building-publishing.md)** 中，我們將說明如何設置開發環境、執行單元測試、維護受控格式分析實驗協議以及打包發佈至 PyPI。
