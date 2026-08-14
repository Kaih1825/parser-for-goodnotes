[中文](#中文)

<a id="english"></a>

# 08 - Testing, Building & Publishing

This section introduces the standard procedures for the **Document Parser for GoodNotes** development environment setup, unit testing, Controlled Corpus Protocol for format analysis, wheel packaging, and publishing to PyPI.

---

## 1. Environment Setup

The project recommends using the modern Python package manager [`uv`](https://github.com/astral-sh/uv) for dependency synchronization and environment isolation.

### Option A: Using `uv` (Recommended)

```sh
# 1. Clone the repository
git clone https://github.com/your-org/goodnotes-document-parser.git
cd goodnotes-document-parser

# 2. Automatically create virtual environment and install all dependencies (including PyMuPDF, pytest, mypy)
uv sync
```

### Option B: Using standard `pip`

```sh
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in Editable Mode
pip install -e ".[dev]"
```

---

## 2. Testing & Type Checking

The project adopts `pytest` as the testing framework and uses `mypy` for strict static type checking (`strict = true`).

### Running the Unit Test Suite

```sh
# Run tests using uv
uv run pytest

# Or invoke pytest directly
pytest -v
```

The tests cover a full suite of 10 core testing modules:
- `tests/test_wire.py`: Protobuf Varint and Wire decoding tests.
- `tests/test_archive.py`: ZIP Inventory and record reading tests.
- `tests/test_compression.py`: Apple LZ4 (`bv41`/`bv4$`) decompression algorithm tests.
- `tests/test_tpl.py`: Troy Hanson TPL binary format and Format String parsing tests.
- `tests/test_stroke.py`: Normal vector smoothing, Catmull-Rom stroke Ribbon, and RGBA Trailer tests.
- `tests/test_shape.py`: Rectangle, ellipse, polygon, and Type 31/35 shape tests.
- `tests/test_text.py`: Rich text/RTF decoding tests.
- `tests/test_page.py`: PDF MediaBox dimensions and layer parsing tests.
- `tests/test_export.py`: JSON and SVG high-fidelity export tests.
- `tests/test_cli.py`: CLI tool command-line integration tests.

### Running Mypy Static Type Checking

```sh
uv run mypy src/goodnotes_parser
```

---

## 3. Controlled Corpus Protocol

To ensure the correctness of semantic parsing and avoid introducing unverified assumptions, this project establishes and strictly follows a controlled experimental protocol:

### 1. Principles & Naming
Semantic parsing is only accepted when there is exactly one controlled operation difference between two otherwise identical documents. Every case should preserve the exported `.goodnotes` source file and the GoodNotes PDF export. Each feature family should use a new document.

- **File Naming**: `<generation>-<family>-<case>-before.goodnotes` and `<generation>-<family>-<case>-after.goodnotes`, along with the corresponding `after.pdf`. (`generation` is `gn5` or `gn6`)
- **Environment Record**: Record the exact application version and platform in a `manifest.json` next to each set of files.

### 2. Required Cases

| Family | Minimal controlled operations |
| :--- | :--- |
| **Ink** | Dot, short/long straight line, short/long curve, quick scribble; ballpoint pen, fountain pen, brush pen, highlighter; three colors; three widths. |
| **Editing** | Erasing partial and full strokes; lasso move; lasso copy/paste; test undo and redo for every operation. |
| **Page** | Blank; A4 Portrait; A4 Landscape; Letter Portrait; Letter Landscape; PDF background; multi-page order. |
| **Objects** | An image bitmap; a text box; a line; a circle; a recognized shape; a folded and unfolded sticky note. |

### 3. Capture Procedure

1. Export `before.goodnotes` before executing a single operation.
2. Perform **exactly one specific controlled operation** (e.g., drawing a single dot, drawing a slanted curve, erasing part of a stroke, lasso moving an image). Do not modify other objects.
3. Immediately export `after.goodnotes` and `after.pdf`.
4. Record the expected object count, page number, color/width, and a visual description in `manifest.json`.
5. Run the `gn-diff` tool to compare file member differences:
   ```sh
   gn-diff before.goodnotes after.goodnotes
   ```
   Submit the member-level differences along with the original samples.

### 4. Acceptance Rules

- Any field mapping assertion must have **two independent controlled examples**.
- Stroke geometry must match the exported SVG against the original PDF in vector overlap after applying the documented coordinate transformation (multiplying by $72.0/132.0$), without any missing or extra paths.
- Erasing, lasso moving, and copying must also prove object UUID identification consistency between before/after.
- The parser must represent unparsed bytes as unknown fields instead of silently dropping them.

---

## 4. Packaging & Building

The project is built using `pyproject.toml` and `setuptools` / `hatchling` to generate standard Python Source Distributions (`.tar.gz`) and Wheels (`.whl`).

### `pyproject.toml` Configuration

```toml
[build-system]
requires = ["setuptools"]
build-backend = "setuptools.build_meta"

[project]
name = "goodnotes-document-parser"
version = "0.1.0"
description = "A typed, schema-free protobuf inspector and exporter for GoodNotes documents."
requires-python = ">=3.9"
dependencies = [
    "PyMuPDF>=1.23.0",
]

[project.scripts]
gn-inspect = "goodnotes_parser.cli:inspect_main"
gn-dump = "goodnotes_parser.cli:dump_main"
gn-diff = "goodnotes_parser.cli:diff_main"
gn-export-json = "goodnotes_parser.cli:export_json_main"
gn-export-svg = "goodnotes_parser.cli:export_svg_main"
```

### Build Artifacts

```sh
# Install build tools
uv pip install build

# Execute build
python3 -m build
```

After execution, the built files will be generated in the `dist/` directory:
- `dist/goodnotes_document_parser-0.1.0-py3-none-any.whl`
- `dist/goodnotes_document_parser-0.1.0.tar.gz`

---

## 5. Publishing to PyPI

### Step 1: Validate Package Content

Before publishing, use `twine` to check if the package description and format comply with the standards:

```sh
uv pip install twine
twine check dist/*
```

### Step 2: Test Publishing to TestPyPI

It is recommended to publish to TestPyPI first to verify the installation:

```sh
twine upload --repository testpypi dist/*
```

Verify installation:
```sh
pip install --index-url https://test.pypi.org/simple/ goodnotes-document-parser
```

### Step 3: Official Release to PyPI

```sh
twine upload dist/*
```

Upon successful publishing, Python developers worldwide can easily install and use the package via `pip install goodnotes-document-parser`!

---

Congratulations, you have completed reading the comprehensive Wiki for the **Document Parser for GoodNotes**! If you have any questions or discover new binary formats, feel free to submit an Issue or PR to contribute to the repository.

---

[English](#english)

<a id="中文"></a>

# 08 - 開發、測試、打包與發佈 (Testing, Building & Publishing)

本章節介紹 **Document Parser for GoodNotes** 的開發環境配置、單元測試、受控格式分析實驗協議 (Controlled Corpus Protocol)、wheel 套件打包以及發佈至 PyPI 的標準流程。

---

## 1. 開發環境配置 (Environment Setup)

專案推薦使用現代 Python 套件管理器 [`uv`](https://github.com/astral-sh/uv) 進行依賴同步與環境隔離。

### 方式 A：使用 `uv` (推薦)

```sh
# 1. 複製專案庫
git clone https://github.com/your-org/goodnotes-document-parser.git
cd goodnotes-document-parser

# 2. 自動建立虛擬環境並安裝所有依賴 (包含 PyMuPDF, pytest, mypy)
uv sync
```

### 方式 B：使用標準 `pip`

```sh
# 建立虛擬環境
python3 -m venv .venv
source .venv/bin/activate

# 以可編輯模式 (Editable Mode) 安裝
pip install -e ".[dev]"
```

---

## 2. 單元測試與型別檢查 (Testing & Type Checking)

專案採用 `pytest` 作為測試框架，並使用 `mypy` 進行嚴格靜態型別檢查 (`strict = true`)。

### 執行單元測試套件

```sh
# 使用 uv 執行測試
uv run pytest

# 或直接調用 pytest
pytest -v
```

測試涵蓋全套 10 個核心測試模組：
- `tests/test_wire.py`: Protobuf Varint 與 Wire 解碼測試。
- `tests/test_archive.py`: ZIP Inventory 與記錄讀取測試。
- `tests/test_compression.py`: Apple LZ4 (`bv41`/`bv4$`) 解壓演算法測試。
- `tests/test_tpl.py`: Troy Hanson TPL 二進制格式與 Format String 解析測試。
- `tests/test_stroke.py`: 法向量平滑、Catmull-Rom 筆跡 Ribbon 與 RGBA Trailer 測試。
- `tests/test_shape.py`: 矩形、橢圓、多邊形、Type 31/35 圖形測試。
- `tests/test_text.py`: 富文本/RTF 解碼測試。
- `tests/test_page.py`: PDF MediaBox 尺寸與圖層解析測試。
- `tests/test_export.py`: JSON 與 SVG 高忠實度導出測試。
- `tests/test_cli.py`: CLI 工具命令列整合測試。

### 執行 Mypy 靜態型別檢查

```sh
uv run mypy src/goodnotes_parser
```

---

## 3. 受控格式分析實驗協議 (Controlled Corpus Protocol)

為確保語意解析的正確性、避免引入未經證實的猜測，本專案訂立並嚴格遵循受控實驗協議：

### 1. 核心原則與命名規範 (Principles & Naming)
只有在兩份其他條件完全相同的文件之間，僅有一個受控操作發生變化時，才接受語意解析。每個案例都應保留匯出的 `.goodnotes` 原始檔與 GoodNotes PDF 匯出檔。每個功能類別都應使用新的文件。

- **檔案命名**：`<generation>-<family>-<case>-before.goodnotes` 與 `<generation>-<family>-<case>-after.goodnotes`，以及對應的 `after.pdf`。（`generation` 為 `gn5` 或 `gn6`）
- **環境紀錄**：在每組檔案旁的 `manifest.json` 記錄確切的應用程式版本與平台。

### 2. 必要測試案例 (Required Cases)

| 類別 (Family) | 最小受控操作 (Minimal controlled operations) |
| :--- | :--- |
| **筆跡 (Ink)** | 點、短／長直線、短／長曲線、快速塗寫；原子筆、鋼筆、筆刷、螢光筆；三種顏色；三種寬度。 |
| **編輯 (Editing)** | 擦除部分與全部筆跡；套索移動；套索複製／貼上；每個操作都測試復原與重做。 |
| **頁面 (Page)** | 空白；A4 直向；A4 橫向；Letter 直向；Letter 橫向；PDF 背景；多頁順序。 |
| **物件 (Objects)** | 一張點陣圖；一個文字框；一條線；一個圓；一個辨識形狀；摺疊與展開的便條紙。 |

### 3. 實驗擷取流程 (Capture Procedure)

1. 在執行單一操作前匯出 `before.goodnotes`。
2. 只執行**一個特定受控操作**（例如：畫一個單點 Dot、畫一條傾斜曲線、擦除某筆劃的一部分、套索移動某圖片），切勿修改其他物件。
3. 立即匯出 `after.goodnotes` 與 `after.pdf`。
4. 在 `manifest.json` 記錄預期物件數量、頁碼、顏色／寬度與視覺描述。
5. 執行 `gn-diff` 工具比對檔案成員差異：
   ```sh
   gn-diff before.goodnotes after.goodnotes
   ```
   並將成員層級差異與原始樣本一併提交。

### 4. 驗收規則 (Acceptance Rules)

- 任何欄位映射斷言必須擁有**兩個獨立受控範例**。
- 筆跡幾何必須在套用已記錄的座標轉換（乘以 $72.0/132.0$）後將導出的 SVG 與原廠 PDF 進行向量重合比較，不得有遺失或多出的 path。
- 擦除、套索移動與複製還必須證明 before/after 之間的物件 UUID 識別一致。
- 解析器必須將尚未解析的位元組表示為未知欄位，而不是靜默丟棄。

---

## 4. 專案打包 (Packaging & Building)

專案基於 `pyproject.toml` 與 `setuptools` / `hatchling` 建置標準 Python Source Distribution (`.tar.gz`) 與 Wheel (`.whl`)。

### `pyproject.toml` 組態說明

```toml
[build-system]
requires = ["setuptools"]
build-backend = "setuptools.build_meta"

[project]
name = "goodnotes-document-parser"
version = "0.1.0"
description = "A typed, schema-free protobuf inspector and exporter for GoodNotes documents."
requires-python = ">=3.9"
dependencies = [
    "PyMuPDF>=1.23.0",
]

[project.scripts]
gn-inspect = "goodnotes_parser.cli:inspect_main"
gn-dump = "goodnotes_parser.cli:dump_main"
gn-diff = "goodnotes_parser.cli:diff_main"
gn-export-json = "goodnotes_parser.cli:export_json_main"
gn-export-svg = "goodnotes_parser.cli:export_svg_main"
```

### 建置構建包 (Build Artifacts)

```sh
# 安裝 build 工具
uv pip install build

# 執行建置
python3 -m build
```

執行後會在 `dist/` 目錄下生成打包好的檔案：
- `dist/goodnotes_document_parser-0.1.0-py3-none-any.whl`
- `dist/goodnotes_document_parser-0.1.0.tar.gz`

---

## 5. 發佈至 PyPI (Publishing to PyPI)

### 步驟 1：驗證包內容

在發佈前，使用 `twine` 檢查套件描述與格式是否合規：

```sh
uv pip install twine
twine check dist/*
```

### 步驟 2：測試發佈至 TestPyPI

建議先發佈至 TestPyPI 驗證安裝：

```sh
twine upload --repository testpypi dist/*
```

驗證安裝：
```sh
pip install --index-url https://test.pypi.org/simple/ goodnotes-document-parser
```

### 步驟 3：正式發佈至 PyPI

```sh
twine upload dist/*
```

發佈成功後，全球 Python 開發者即可透過 `pip install goodnotes-document-parser` 輕鬆安裝使用！

---

至此，您已完成了 **Document Parser for GoodNotes** 的完整 Wiki 閱讀！如有任何問題或發現新的二進位特徵，歡迎提交 Issue 或 PR 貢獻至專案庫。
