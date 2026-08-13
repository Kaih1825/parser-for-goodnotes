# 08 - 開發、測試、打包與發佈 (Testing, Building & Publishing)

本章節介紹 **GoodNotes Reverse Engineering Toolkit** 的開發環境配置、單元測試、受控逆向工程實驗協議 (Controlled Corpus Protocol)、wheel 套件打包以及發佈至 PyPI 的標準流程。

---

## 1. 開發環境配置 (Environment Setup)

專案推薦使用現代 Python 套件管理器 [`uv`](https://github.com/astral-sh/uv) 進行依賴同步與環境隔離。

### 方式 A：使用 `uv` (推薦)

```sh
# 1. 複製專案庫
git clone https://github.com/your-org/goodnotes-reverse-engineering-toolkit.git
cd goodnotes-reverse-engineering-toolkit

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
uv run mypy src/goodnotes_re
```

---

## 3. 受控逆向工程實驗協議 (Controlled Corpus Protocol)

為確保語意解析的正確性、避免引入未經證實的猜測，本專案嚴格遵循 [`docs/corpus-protocol.md`](../docs/corpus-protocol.md) 訂定的受控實驗協議：

### 實驗捕獲步驟 (Capture Procedure)

1. **極簡單一控制變因 (Minimal Controlled Operation)**：在 GoodNotes 中僅執行**一個特定操作**（例如：畫一個單點 Dot、畫一條傾斜曲線、擦除某筆劃的一部分、套索移動某圖片）。
2. **前後對照備份**：
   - 操作前匯出 `<generation>-<family>-<case>-before.goodnotes`。
   - 操作後立即匯出 `<generation>-<family>-<case>-after.goodnotes` 以及對應的原廠 `after.pdf`。
3. **執行 `gn-diff` 驗證**：
   ```sh
   gn-diff before.goodnotes after.goodnotes
   ```
4. **驗收標準 (Acceptance Rules)**：
   - 任何欄位映射斷言必須擁有**兩個獨立受控範例**。
   - 筆跡幾何必須將導出的 SVG 座標乘以 $72.0/132.0$ 後，與原廠 PDF 進行向量重合比對。
   - 擦除、套索移動與複製，必須能證明物件 UUID 的跨檔案承襲性。

---

## 4. 專案打包 (Packaging & Building)

專案基於 `pyproject.toml` 與 `setuptools` / `hatchling` 建置標準 Python Source Distribution (`.tar.gz`) 與 Wheel (`.whl`)。

### `pyproject.toml` 組態說明

```toml
[build-system]
requires = ["setuptools"]
build-backend = "setuptools.build_meta"

[project]
name = "goodnotes-reverse-engineering-toolkit"
version = "0.1.0"
description = "A typed, schema-free protobuf inspector and exporter for GoodNotes documents."
requires-python = ">=3.9"
dependencies = [
    "PyMuPDF>=1.23.0",
]

[project.scripts]
gn-inspect = "goodnotes_re.cli:inspect_main"
gn-dump = "goodnotes_re.cli:dump_main"
gn-diff = "goodnotes_re.cli:diff_main"
gn-export-json = "goodnotes_re.cli:export_json_main"
gn-export-svg = "goodnotes_re.cli:export_svg_main"
```

### 建置構建包 (Build Artifacts)

```sh
# 安裝 build 工具
uv pip install build

# 執行建置
python3 -m build
```

執行後會在 `dist/` 目錄下生成打包好的檔案：
- `dist/goodnotes_reverse_engineering_toolkit-0.1.0-py3-none-any.whl`
- `dist/goodnotes_reverse_engineering_toolkit-0.1.0.tar.gz`

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
pip install --index-url https://test.pypi.org/simple/ goodnotes-reverse-engineering-toolkit
```

### 步驟 3：正式發佈至 PyPI

```sh
twine upload dist/*
```

發佈成功後，全球 Python 開發者即可透過 `pip install goodnotes-reverse-engineering-toolkit` 輕鬆安裝使用！

---

至此，您已完成了 **GoodNotes Reverse Engineering Toolkit** 的完整 Wiki 閱讀！如有任何問題或發現新的二進位特徵，歡迎提交 Issue 或 PR 貢獻至專案庫。
