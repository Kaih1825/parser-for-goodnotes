# 09 - 目前格式分析發現 (Current Format Analysis Findings)

本章記錄目前已由專案 source code 與測試 corpus 實際落地的 GoodNotes 格式觀察。這不是 GoodNotes 官方格式規格；未經多份 corpus 驗證的欄位只應視為目前的 binary format analysis hypothesis。

---

## 1. GN6 頁面排序不是單純 `index.notes.pb` 順序

`index.notes.pb` 可以提供頁面清單，但 GoodNotes 在重新排序頁面後，排序資訊會出現在 `index.events.pb` 的 page-order 事件中。

目前 `archive.py` 的 `GoodNotesDocument._page_order_keys()` 會：

1. 讀取 `index.events.pb`。
2. 尋找 page UUID 與 order-key 欄位。
3. 使用事件 timestamp 選取同一頁最新的排序資訊。
4. 將 order key 套回 `index.notes.pb` 的頁面清單。
5. 對沒有 order event 的頁面保留原始位置。

這避免了只按照 `index.notes.pb` 排序而無法反映 GoodNotes 重新排列頁面的問題。

> **Confidence:** High（已反映於現有 parser 實作與 page-order corpus）。

---

## 2. 已刪除頁面可由 Event Record 排除

`index.events.pb` 的特定事件 Record（目前實作使用 Field 56）包含被刪除頁面的 UUID。`pages(parse_all=False)` 會先建立 inactive page set，再從正常頁面清單排除這些頁面。

`parse_all=True` 則保留解析所有可找到的 page records，適合 binary format analysis 與 corpus 比對。

> **Confidence:** High（已有 parser 與測試邏輯）。

---

## 3. 頁面與 PDF / image attachment 的關聯需要跨多個 index

頁面背景不是單純由 `notes/<UUID>` 推導。現行 parser 會結合：

- `index.attachments.pb`
- `index.events.pb`
- page/template UUID
- attachment UUID
- PDF page index

再建立 `Page.background_attachment_path` 與 `Page.pdf_page_index`。

因此，解析背景時不應只掃描 page record 裡的 UUID，也不應假設一頁永遠對應 attachment 的第一頁。

> **Confidence:** High（目前 parser 已處理多層 mapping，且 archive tests 驗證不同頁面可指向不同 PDF attachment）。

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

Type 35 records 可包含經 Apple LZ4 (`bv41`) 壓縮的富文本 payload。`text.py` 目前已解析：

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

## 6. Sticker / text background 需要區分「文字本身」與「貼圖背景」

SVG exporter 現在不會對所有文字框強制加入背景。只有在 parsed text box 與 image attachment 高度重疊，且 text payload 本身提供 `background_color_hex` / `background_alpha` 時，才繪製不透明或半透明的文字背景。

這個判斷是為了避免一般文字框被錯誤加上白底，同時保留 GoodNotes 貼圖內文字的背景遮罩效果。

> **Confidence:** Medium-High（已由 sticker corpus 驗證；overlap threshold 仍屬 renderer policy，而非檔案格式欄位）。

---

## 7. 圖片 attachment 同時保存原始框與 crop 資訊

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

## 9. 便條紙有獨立的 parent-child 關係

Sticky Note 本身可作為 parent。其子 shape、stroke 與 text element 可以透過 UUID 關係掛在便條紙座標系下。

SVG export 時，子元素會加上 sticky note 的 `(x, y)` offset；折疊便條紙的子元素則不應被正常展開繪製。

因此不能把 sticky note 內容當作一般 page-level coordinates 處理。

> **Confidence:** High for current sticker/sticky-note corpus。

---

## 10. Wire decoder 的定位：解析格式，而不是猜資料

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

以下項目仍應視為持續格式分析，而不是穩定格式規格：

- 所有 GoodNotes 版本的完整 field schema。
- 所有 stroke TPL format string 的完整集合。
- 所有 shape type code 與 marker code。
- 所有 page event type 的完整 enum。
- 所有 image crop / transform 欄位在不同版本中的語意。
- 未知 protobuf fields 的官方語意。

新增 corpus 時，應優先使用 `gn-diff` 比較「單一操作前 / 操作後」的 `.goodnotes`，再將觀察寫入 `docs/knowledge-base.md` 與本章，並標示 confidence。

---

## 12. 驗證方式

推薦使用受控操作建立 corpus：

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
加入 parser + regression test
   ↓
更新 Wiki
```

這比直接在大型二進制檔案中搜尋 float、UUID 或固定 byte pattern 更可靠。
