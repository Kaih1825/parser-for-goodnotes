# GoodNotes Reverse Engineering Toolkit — CLI 使用指南

`GoodNotes Reverse Engineering Toolkit` 提供了一套完整的命令列工具（CLI），用於檢視、解碼、比對以及匯出 GoodNotes 5 與 GoodNotes 6 的 `.goodnotes` 文件檔案。

本工具能直接解碼未公開的 Protobuf wire 格式、解壓縮 Apple LZ4 (bv41) 與 Troy Hanson TPL 筆劃資料，並可將 GoodNotes 筆跡與頁面結構無損轉換為 JSON 或高品質向量 SVG。

---

## 目錄

- [安裝與環境設定](#安裝與環境設定)
- [CLI 命令總覽](#cli-命令總覽)
- [詳細命令說明](#詳細命令說明)
  - [1. gn-inspect（檔案清單檢視）](#1-gn-inspect檔案清單檢視)
  - [2. gn-dump（Protobuf 轉 JSON）](#2-gn-dumpprotobuf-轉-json)
  - [3. gn-diff（檔案差異比對）](#3-gn-diff檔案差異比對)
  - [4. gn-export-json（完整結構匯出為 JSON）](#4-gn-export-json完整結構匯出為-json)
  - [5. gn-export-svg（頁面匯出為向量 SVG）](#5-gn-export-svg頁面匯出為向量-svg)
- [通用模組調用方式](#通用模組調用方式)
- [批次匯出範例](#批次匯出範例)

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

安裝完成後，系統將註冊以下 5 個獨立 CLI 命令：
- `gn-inspect`
- `gn-dump`
- `gn-diff`
- `gn-export-json`
- `gn-export-svg`

---

## CLI 命令總覽

| 命令 | 說明 | 主要用途 |
| :--- | :--- | :--- |
| `gn-inspect` | 列出 `.goodnotes` 壓縮檔內所有成員檔案與 SHA-256 雜湊值 | 快速了解文件結構與內部資源 |
| `gn-dump` | 無損印出指定 Protobuf 成員的 JSON 解碼樹 | 逆向工程分析特定 `.pb` 檔案 |
| `gn-diff` | 比對兩個 `.goodnotes` 檔案內部成員的增刪與修改狀態 | 分析編輯操作（如新增筆跡、黏貼貼紙）前後的變化 |
| `gn-export-json` | 匯出整份文件的頁面、筆跡點位、顏色、文字與元資料為單一 JSON | 程式化資料處理或第三方格式轉換 |
| `gn-export-svg` | 將文件頁面匯出為高品質向量 SVG 圖檔（含 PDF 背景、筆跡、便條紙等） | 視覺化檢視與高品質列印 / 網頁呈現 |

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
- `-s`, `--sticky-note-state`：控制便條紙（Sticky Notes）展開狀態：
  - `open`：強制展開所有便條紙，顯示內容。
  - `close`：強制收合所有便條紙，僅顯示圖示。
  - `auto`：（預設）依照 GoodNotes 檔案內原始儲存狀態顯示。
- `-b`, `--textbox`：控制文字方塊外框線：
  - `close`：（預設）隱藏文字方塊外框線。
  - `open`：顯示文字方塊外框輔助線。
- `--no-fill`：停用向量封閉圖形的自動填色功能（預設會填色）。

#### 使用範例

##### 基本匯出
```bash
gn-export-svg sample.goodnotes -o output_svgs/
```

##### 強制展開便條紙並顯示文字框線
```bash
gn-export-svg sample.goodnotes -o output_svgs/ -s open -b open
```

##### 不填滿封閉幾何圖形
```bash
gn-export-svg sample.goodnotes -o output_svgs/ --no-fill
```

---

## 通用模組調用方式

若未將命令註冊至系統 PATH，或習慣使用 Python 模組直接執行，可透過 `python -m goodnotes_re.cli` 來調用：

```bash
# 使用 uv
uv run python -m goodnotes_re.cli export-svg sample.goodnotes -o output_svgs/

# 設定 PYTHONPATH 執行
PYTHONPATH=src python3 -m goodnotes_re.cli inspect sample.goodnotes
PYTHONPATH=src python3 -m goodnotes_re.cli dump sample.goodnotes index.notes.pb
PYTHONPATH=src python3 -m goodnotes_re.cli diff before.goodnotes after.goodnotes
PYTHONPATH=src python3 -m goodnotes_re.cli export-json sample.goodnotes -o doc.json
PYTHONPATH=src python3 -m goodnotes_re.cli export-svg sample.goodnotes -o output_svgs/
```

---

## 批次匯出範例

可建立 Shell 腳本批次將多個 `.goodnotes` 檔案自動轉為 SVG：

```bash
#!/bin/bash
# 批次轉檔腳本範例 batch_export.sh

INPUT_DIR="./samples"
OUTPUT_DIR="./output_svgs"

mkdir -p "$OUTPUT_DIR"

for file in "$INPUT_DIR"/*.goodnotes; do
    if [ -f "$file" ]; then
        echo "正在處理: $file"
        uv run gn-export-svg "$file" -o "$OUTPUT_DIR/$(basename "$file" .goodnotes)" -b close
    fi
done

echo "批次轉換完成！結果儲存於 $OUTPUT_DIR"
```
