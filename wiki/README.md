# GoodNotes Document Format Wiki

歡迎來到 **GoodNotes Document Parser** 的技術 Wiki！

本 Wiki 旨在提供全面且極度詳細的技術文檔。讀者可透過閱讀本 Wiki，完全理解 `.goodnotes` 檔案的內部二進制結構、Protobuf Wire 格式解碼原理、Apple LZ4 壓縮串流、Troy Hanson TPL 記憶體映像、筆跡動態壓感 ribbon 構建算法、向量圖形與富文本提取、PDF 底圖繪製、幾何座標轉換矩陣、Python API、CLI 工具使用方式、單元測試以及打包發佈流程。

---

## 核心設計哲學 (Core Design Philosophy)

本專案遵循以下四大核心原則：

1. **Schema-Free 權威 Wire 解碼 (Authoritative Schema-Free Wire Decoding)**：
   本工具包**不依賴也不需要**固定的 Protobuf `.proto` 定義檔。我們實現了低階 Protobuf Wire 格式解碼器，能夠保留 raw bytes 與未知欄位（unknown fields），確保面對 GoodNotes 5 或 GoodNotes 6 未來更新的格式變更時不會丟失資料。

2. **嚴禁浮點數啟發式掃描 (Strict Prohibition of Heuristic Float Scanning)**：
   絕不從二進制流中盲目搜尋「看起來像浮點數」的 4-byte 組合。所有座標、顏色、寬度與尺寸，均嚴格透過 Protobuf 標籤（Tag Number）或 Troy Hanson TPL 型別描述符（Format String）精準解析。

3. **高忠實度向量重建 (High-Fidelity Vector Reconstruction)**：
   針對數位筆跡（Ink Strokes），除了解析控制點座標，更結合壓感（Pressure）計算兩側法向量平滑曲線，產生標準 SVG Path ribbon。對於被橡皮擦擦除切開的筆跡（v9 Mesh），採用**滑動視窗凸包算法（Sliding-Window Convex Hull）**，完美重現切開時的平頭銳利邊緣。

4. **標註與解析隔離 (Interpretation Isolation)**：
   像 `page`、`stroke`、`sticky_note` 等語意屬性僅為上層解釋（Interpretation），下層 `wire` 解碼層永不抹除或覆蓋原始 byte 結構。

---

## Wiki 目錄結構 (Table of Contents)

點擊下方連結即可跳轉至對應主題章節：

| 章節檔案 | 主題說明 | 關鍵內容 |
| :--- | :--- | :--- |
| **[01-architecture-overview.md](01-architecture-overview.md)** | **系統架構與資料流** | 模組職責分工、解析管道 (Pipeline)、GoodNotes 5 vs 6 檔案格式演進 |
| **[02-archive-and-wire-format.md](02-archive-and-wire-format.md)** | **ZIP 容器與 Protobuf Wire 解析** | ZIP 檔案結構、Varint 編碼規則、Length-Delimited 串流分幀解碼 |
| **[03-compression-and-tpl-binary.md](03-compression-and-tpl-binary.md)** | **Apple LZ4 壓縮與 TPL 記憶體映像** | `bv41`/`bv4$` 串流規約、Pure-Python LZ4 解壓、Troy Hanson TPL Format 語法與 RGBA Trailer 解析 |
| **[04-stroke-geometry-and-rendering.md](04-stroke-geometry-and-rendering.md)** | **筆跡幾何與向量 Ribbon 重建** | 控制點壓感、法向量平滑、Catmull-Rom 與 Bézier 曲線、v9 橡皮擦切口凸包演算法 |
| **[05-shapes-text-and-elements.md](05-shapes-text-and-elements.md)** | **圖形、文字與頁面元素** | 多邊形/矩形/橢圓形解析、箭頭端點 Marker、RTF/UTF-8 文字區塊、便條紙與圖片 Crop 裁切 |
| **[06-pdf-integration-and-svg-export.md](06-pdf-integration-and-svg-export.md)** | **PDF 底圖與 SVG 向量匯出** | PDF `/MediaBox` 解析、132 DPI 與 72 DPI 坐標轉換矩陣、SVG DOM 圖層堆疊邏輯 |
| **[07-cli-and-api-guide.md](07-cli-and-api-guide.md)** | **CLI 工具與 Python API 指南** | `gn-inspect`, `gn-dump`, `gn-diff`, `gn-export-json`, `gn-export-svg` 指令與程式庫調用 API |
| **[08-testing-building-publishing.md](08-testing-building-publishing.md)** | **開發、測試、打包與發佈** | `uv` 環境設置、Pytest 單元測試、受控逆向實驗協議 (Corpus Protocol)、PyPI 發佈流程 |
| **[09-current-re-findings.md](09-current-re-findings.md)** | **目前格式分析發現** | GN6 頁面排序、刪除事件、PDF 關聯、Type 35 文字、貼圖背景、圖片 Crop、Sticky Note parent-child 與目前限制 |

---

## 快速魔術標記速查表 (Quick Reference Cheat-Sheet)

在分析 `.goodnotes` 解開後的二進制檔案時，常會遇到以下 Magic Marker：

```
+------------------+-----------------------+-------------------------------------------------------+
| Magic / Sequence | 說明                  | 解析對應模組                                          |
+------------------+-----------------------+-------------------------------------------------------+
| 0x08 0x23        | schema.pb (Field 1=35)| wire.py / archive.py (Schema 版本標誌)                |
| 0x52 0x0a ...    | Length-delimited PB   | wire.py (decode_delimited_messages Varint 幀標頭)     |
| bv41             | Apple Framed LZ4 Compressed Block | compression.py (decode_apple_lz4 壓縮區塊)       |
| bv4-             | Apple LZ4 Stored Uncompressed Block | compression.py (未壓縮直通區塊)              |
| bv4$             | Apple LZ4 Stream End Marker | compression.py / stroke.py (串流結束，後接 Protobuf Trailer)|
| tpl\0            | Troy Hanson TPL Image Header | tpl.py (decode_tpl 筆跡點陣結構與描述符)       |
| {\rtf            | Rich Text Format      | text.py (rtf_to_text 解析打字機/便條紙文本)           |
| %PDF             | PDF Attachment        | pdf.py / page.py (PageDimensions / PyMuPDF 繪製底圖)  |
+------------------+-----------------------+-------------------------------------------------------+
```

---

## 快速調用範例

```python
from goodnotes_re import GoodNotesDocument

# 開啟 .goodnotes 文件
with GoodNotesDocument.open("samples/Teat.goodnotes") as doc:
    # 遍歷頁面
    for page in doc.pages():
        print(f"Page {page.index + 1}: {page.dimensions.width}x{page.dimensions.height} pt")
        print(f"  筆跡數量: {len(page.strokes)}, 圖形數量: {len(page.shapes)}")
        
        for stroke in page.strokes:
            print(f"    - Stroke {stroke.uuid}: color={stroke.color_hex}, alpha={stroke.alpha}, points={len(stroke.points)}")
```

## 目前格式分析狀態

目前專案已實際驗證 GN6 文件的頁面排序、刪除事件、PDF 背景關聯、Type 35 富文本、便條紙與圖片裁切等資料路徑。最新的驗證與已知限制整理於 **[09 - Current Format Analysis Findings](09-current-re-findings.md)**。

> Wiki 描述以目前 source code 為準；尚未被 corpus 驗證的欄位會標示為推測，不視為 GoodNotes 官方格式規格。

欲瞭解更多技術細節，請點選上方目錄導覽至具體章節！
