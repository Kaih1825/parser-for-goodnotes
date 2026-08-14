[中文](#中文)

<a id="english"></a>

# 09 - Current Format Analysis Findings

This chapter documents the observations of the GoodNotes format currently implemented via the project's source code and tested against the corpus. This is not an official GoodNotes format specification; fields not verified across multiple corpora should only be considered as the current binary format analysis hypothesis.

---

## 1. GN6 Page Order is Not Just the `index.notes.pb` Sequence

`index.notes.pb` can provide a list of pages, but when GoodNotes reorders pages, the sorting information appears in the page-order events of `index.events.pb`.

Currently, `GoodNotesDocument._page_order_keys()` in `archive.py` will:

1. Read `index.events.pb`.
2. Look for the page UUID and order-key fields.
3. Select the latest sorting information for the same page using the event timestamp.
4. Apply the order key back to the page list in `index.notes.pb`.
5. Retain the original position for pages without an order event.

This prevents the issue where sorting solely by `index.notes.pb` fails to reflect the pages reordered by GoodNotes.

> **Confidence:** High (Reflected in current document parser implementation and page-order corpus).

---

## 2. Deleted Pages Can Be Excluded via Event Record

Specific event Records in `index.events.pb` (currently implemented using Field 56) contain the UUIDs of deleted pages. `pages(parse_all=False)` will first create an inactive page set, then exclude these pages from the normal page list.

`parse_all=True` retains parsing for all discoverable page records, suitable for binary format analysis and corpus comparison.

> **Confidence:** High (Parser and test logic already exist).

---

## 3. Association Between Pages and PDF / Image Attachments Requires Spanning Multiple Indices

The page background is not derived solely from `notes/<UUID>`. The current document parser combines:

- `index.attachments.pb`
- `index.events.pb`
- page/template UUID
- attachment UUID
- PDF page index

To construct `Page.background_attachment_path` and `Page.pdf_page_index`.

Therefore, when parsing backgrounds, one should not just scan the UUID in the page record, nor should one assume a page always corresponds to the first page of an attachment.

> **Confidence:** High (Current parser already handles multi-layer mapping, and archive tests verify that different pages can point to different PDF attachments).

---

## 4. PDF `/MediaBox` is a Crucial Source for Page Dimensions

When a page has a PDF attachment, `PageDimensions.from_pdf_mediabox()` retrieves the actual page size from the PDF `/MediaBox` instead of fixing it to default A4 / Letter values.

Currently, SVG export uses a ratio from GoodNotes coordinates to PDF/SVG points of:

```text
72 / 132
```

This conversion must remain consistent, otherwise, backgrounds, strokes, shapes, and texts will suffer from scaling or positional offsets.

> **Confidence:** High (Covered by PDF module and page/export tests).

---

## 5. Type 35 is Currently the Key Entry Point for Text and Partial Page Element Parsing

Type 35 records can contain rich text payloads compressed with Apple LZ4 (`bv41`). `text.py` currently parses:

- UTF-8 text
- font family
- font size
- RGBA text color and alpha
- bold / italic / underline / strikethrough
- bullet / numbered list
- left / center / right alignment
- text box position / size

The legacy format still retains the RTF fallback parser, so not all text should be assumed to be a Type 35 payload.

> **Confidence:** High for currently supported corpus; field semantics remain corpus-dependent.

---

## 6. Sticker / Text Background Requires Differentiating "Text Itself" and "Sticker Background"

The SVG exporter does not forcefully apply a background to all text boxes now. Only when the parsed text box highly overlaps with the image attachment, and the text payload itself provides `background_color_hex` / `background_alpha`, will an opaque or translucent text background be drawn.

This determination aims to prevent ordinary text boxes from incorrectly receiving a white background while preserving the background mask effect for text inside GoodNotes stickers.

> **Confidence:** Medium-High (Verified by sticker corpus; the overlap threshold is still a renderer policy, not a file format field).

---

## 7. Image Attachments Store Both Original Box and Crop Information

`ImageElement` currently retains:

- original position / size
- crop center
- crop width / height
- rotation
- attachment UUID

Hence, the SVG exporter can use nested `<svg overflow="hidden">` along with transforms to restore cropped images, rather than directly stretching the attachment as a regular `<image>`.

An image record with Field 3 == 1 will be treated as a tombstone / inactive record and excluded.

> **Confidence:** High for current corpus.

---

## 8. Shape and Stroke UUIDs Might Overlap; Exporter Will Prevent Redundant Drawing

`page.py` creates both shapes and strokes. During export, `export.py` cross-checks using UUIDs to prevent the same element from being drawn twice as both a shape and a stroke.

This indicates that UUIDs are not just metadata, but also participate in element classification and rendering de-duplication.

---

## 9. Sticky Notes Have Independent Parent-Child Relationships

A Sticky Note itself can act as a parent. Its child shapes, strokes, and text elements can be hooked under the sticky note's coordinate system via UUID relationships.

During SVG export, child elements will have the sticky note's `(x, y)` offset added; child elements of collapsed sticky notes should not be rendered normally as expanded.

Therefore, the content of a sticky note cannot be treated as general page-level coordinates.

> **Confidence:** High for current sticker/sticky-note corpus.

---

## 10. Positioning the Wire Decoder: Parsing Format, Not Guessing Data

`wire.py` is the lowest level of the entire toolkit. It directly parses:

- Varint
- Fixed64
- Length-delimited
- Start/End Group
- Fixed32

A `Field` concurrently holds the field number, wire type, raw value, and raw bytes. Length-delimited data can attempt to recursively parse into a nested `Message`, but the raw bytes won't be discarded just because parsing fails.

This is the core reason the project prohibits heuristic float scanning: only by knowing the boundaries of wire fields first, then interpreting the data based on observed field schemas / nested messages, can we avoid mistaking random bytes for coordinates.

---

## 11. Parts Yet to Be Fully Defined

The following items should still be viewed as ongoing format analysis, rather than a stable format specification:

- Complete field schemas across all GoodNotes versions.
- The exhaustive set of all stroke TPL format strings.
- All shape type codes and marker codes.
- Complete enums for all page event types.
- The semantics of all image crop / transform fields across different versions.
- Official semantics of unknown protobuf fields.

When introducing a new corpus, priority should be given to using `gn-diff` to compare the `.goodnotes` "before / after a single operation", then recording observations in `docs/knowledge-base.md` and this chapter, and labeling the confidence.

---

## 12. Verification Method

It is recommended to build the corpus using controlled operations:

```text
Original Document
   ↓
Perform a single GoodNotes operation
   ↓
Save As new .goodnotes
   ↓
gn-diff before.goodnotes after.goodnotes
   ↓
Locate changed members
   ↓
gn-dump / wire decoder
   ↓
Confirm field / event / payload
   ↓
Add to document parser + regression test
   ↓
Update Wiki
```

This is much more reliable than directly searching for floats, UUIDs, or fixed byte patterns in large binary files.


---

[English](#english)

<a id="中文"></a>

# 09 - 目前格式分析發現 (Current Format Analysis Findings)

本章記錄目前已由專案原始碼 (source code) 與測試語料庫 (corpus) 實際落地的 GoodNotes 格式觀察。這不是 GoodNotes 官方格式規格；未經多份語料庫驗證的欄位只應視為目前的二進位格式分析假說 (binary format analysis hypothesis)。

---

## 1. GN6 頁面排序不是單純 `index.notes.pb` 順序

`index.notes.pb` 可以提供頁面清單，但 GoodNotes 在重新排序頁面後，排序資訊會出現在 `index.events.pb` 的 page-order 事件中。

目前 `archive.py` 的 `GoodNotesDocument._page_order_keys()` 會：

1. 讀取 `index.events.pb`。
2. 尋找 page UUID 與 order-key 欄位。
3. 使用事件時間戳記 (timestamp) 選取同一頁最新的排序資訊。
4. 將 order key 套回 `index.notes.pb` 的頁面清單。
5. 對沒有 order event 的頁面保留原始位置。

這避免了只按照 `index.notes.pb` 排序而無法反映 GoodNotes 重新排列頁面的問題。

> **Confidence:** High（已反映於現有文件解析器 (parser) 實作與 page-order 語料庫）。

---

## 2. 已刪除頁面可由 Event Record 排除

`index.events.pb` 的特定事件 Record（目前實作使用 Field 56）包含被刪除頁面的 UUID。`pages(parse_all=False)` 會先建立 inactive page set，再從正常頁面清單排除這些頁面。

`parse_all=True` 則保留解析所有可找到的 page records，適合二進位格式分析 (binary format analysis) 與語料庫比對。

> **Confidence:** High（已有文件解析器與測試邏輯）。

---

## 3. 頁面與 PDF / 圖片附件 (image attachment) 的關聯需要跨多個 index

頁面背景不是單純由 `notes/<UUID>` 推導。現行文件解析器會結合：

- `index.attachments.pb`
- `index.events.pb`
- page/template UUID
- attachment UUID
- PDF page index

再建立 `Page.background_attachment_path` 與 `Page.pdf_page_index`。

因此，解析背景時不應只掃描 page record 裡的 UUID，也不應假設一頁永遠對應 attachment 的第一頁。

> **Confidence:** High（目前文件解析器已處理多層對應，且 archive tests 驗證不同頁面可指向不同 PDF attachment）。

---

## 4. PDF `/MediaBox` 是頁面尺寸的重要來源

當頁面具有 PDF attachment 時，`PageDimensions.from_pdf_mediabox()` 會從 PDF `/MediaBox` 取得實際頁面尺寸，而不是固定使用 A4 / Letter 預設值。

目前 SVG export 使用 GoodNotes 座標到 PDF/SVG point 的比例：

```text
72 / 132
```

這個轉換必須保持一致，否則背景與筆跡、圖形、文字會產生比例或位置偏移。

> **Confidence:** High（有 PDF module 與 page/export tests）。

---

## 5. Type 35 是目前文字與部分頁面元素解析的重要入口

Type 35 records 可包含經 Apple LZ4 (`bv41`) 壓縮的富文本 (rich text) payload。`text.py` 目前已解析：

- UTF-8 文字
- font family
- font size
- RGBA 文字顏色與 alpha
- bold / italic / underline / strikethrough
- bullet / numbered list
- left / center / right alignment
- text box position / size

舊格式仍保留 RTF fallback parser，因此不能把所有文字都假設成 Type 35 payload。

> **Confidence:** High for currently supported corpus; field semantics remain corpus-dependent。

---

## 6. 貼紙 (Sticker) / 文字背景需要區分「文字本身」與「貼圖背景」

SVG exporter 現在不會對所有文字框強制加入背景。只有在 parsed text box 與 image attachment 高度重疊，且 text payload 本身提供 `background_color_hex` / `background_alpha` 時，才繪製不透明或半透明的文字背景。

這個判斷是為了避免一般文字框被錯誤加上白底，同時保留 GoodNotes 貼圖內文字的背景遮罩效果。

> **Confidence:** Medium-High（已由 sticker corpus 驗證；overlap threshold 仍屬 renderer policy，而非檔案格式欄位）。

---

## 7. 圖片 attachment 同時保存原始框與裁切 (crop) 資訊

`ImageElement` 目前保留：

- original position / size
- crop center
- crop width / height
- rotation
- attachment UUID

因此 SVG exporter 可以使用 nested `<svg overflow="hidden">` 加上 transform，還原裁切後的圖片，而不是直接把 attachment 當成普通 `<image>` 拉伸。

Field 3 == 1 的 image record 會被視為 tombstone / inactive record 並排除。

> **Confidence:** High for current corpus。

---

## 8. Shape 與 Stroke UUID 可能重疊，exporter 會避免重複繪製

`page.py` 會同時建立 shapes 與 strokes。`export.py` 在輸出時會以 UUID 交叉比對，避免同一個元素同時以 shape 與 stroke 被繪製兩次。

這代表 UUID 不只是 metadata，也參與 element classification 與 rendering de-duplication。

---

## 9. 便條紙 (Sticky Note) 有獨立的 parent-child 關係

便條紙本身可作為 parent。其子 shape、stroke 與 text element 可以透過 UUID 關係掛在便條紙座標系下。

SVG export 時，子元素會加上便條紙的 `(x, y)` offset；折疊便條紙的子元素則不應被正常展開繪製。

因此不能把便條紙內容當作一般 page-level coordinates 處理。

> **Confidence:** High for current sticker/sticky-note corpus。

---

## 10. Wire decoder 的定位：解析格式，而不是猜測資料

`wire.py` 是整個 toolkit 的最低層。它直接解析：

- Varint
- Fixed64
- Length-delimited
- Start/End Group
- Fixed32

`Field` 同時保存 field number、wire type、raw value 與原始 bytes。Length-delimited data 可嘗試遞迴解析成 nested `Message`，但不會因為無法解析就丟棄原始 bytes。

這也是本專案禁止 heuristic float scanning 的核心原因：只有先知道 wire field 的邊界，再根據已觀察到的 field schema / nested message 解釋資料，才能避免把隨機 bytes 誤認成座標。

---

## 11. 目前尚未完全定義的部分

以下項目仍應視為持續格式分析 (format analysis)，而不是穩定格式規格：

- 所有 GoodNotes 版本的完整 field schema。
- 所有 stroke TPL format string 的完整集合。
- 所有 shape type code 與 marker code。
- 所有 page event type 的完整 enum。
- 所有 image crop / transform 欄位在不同版本中的語意。
- 未知 protobuf fields 的官方語意。

新增語料庫時，應優先使用 `gn-diff` 比較「單一操作前 / 操作後」的 `.goodnotes`，再將觀察寫入 `docs/knowledge-base.md` 與本章，並標示 confidence。

---

## 12. 驗證方式

推薦使用受控操作建立語料庫：

```text
原始文件
   ↓
只執行一個 GoodNotes 操作
   ↓
另存新 .goodnotes
   ↓
gn-diff before.goodnotes after.goodnotes
   ↓
定位 changed members
   ↓
gn-dump / wire decoder
   ↓
確認 field / event / payload
   ↓
加入文件解析器 + regression test
   ↓
更新 Wiki
```

這比直接在大型二進位檔案中搜尋 float、UUID 或固定 byte pattern 更可靠。

---

