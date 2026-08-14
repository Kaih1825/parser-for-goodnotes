[中文](#中文)

# Contributing to Document Parser for GoodNotes

Thank you for your interest in contributing! This project is built on careful, evidence-based binary format analysis. Please read this guide before submitting a pull request.

---

## Principles

- **Never replace a parser discovery with an unverified theory.** Every field interpretation must be backed by observable wire data.
- **Add new observations to `wiki/09-current-re-findings.md`**, citing the sample archive member path and the specific protobuf field numbers.
- **Add a test** capturing the raw wire structure of any new finding.
- **Keep schema interpretation separate from lossless wire decoding** so unknown fields remain accessible to future analysis.
- **No float-byte scanning.** All numerical values must arise from a protobuf `fixed32`/`fixed64` field decoded according to its wire type.

---

## Development Setup

```sh
# Clone the repository
git clone https://github.com/Kaih1825/document-parser-for-goodnotes.git
cd document-parser-for-goodnotes

# Install dependencies with uv (recommended)
uv sync

# Run the test suite
uv run pytest

# Run type checking
uv run mypy src/goodnotes_re
```

> **Note on sample files:** `samples/` is listed in `.gitignore` and is never committed. Tests that depend on sample files use `skipTest()` when the file is absent, so the suite still passes without them.

---

## Submitting a Pull Request

1. **Fork** the repository and create a feature branch: `git checkout -b feat/my-finding`
2. Make your changes in `src/goodnotes_re/` and add or update tests in `tests/`.
3. If you discovered a new wire-format field, document it in `wiki/09-current-re-findings.md`.
4. If you changed parsing behavior against an existing sample, run `gn-diff old.goodnotes new.goodnotes` and include the JSON diff summary or a concise description in your PR description.
5. Ensure tests pass: `uv run pytest`
6. Ensure type checks pass: `uv run mypy src/goodnotes_re`
7. Open a pull request against `main` with a clear description of what was found and how it was verified.

---

## Reporting Issues

Use the GitHub Issue templates:

- **Bug Report** — for parsing errors, incorrect SVG output, or crashes.
- **Feature Request / Format Finding** — for proposing new functionality or sharing a format-analysis discovery.

> **Privacy reminder:** Do not attach `.goodnotes` files containing personal data. Use a minimal synthetic sample whenever possible.

---

## Code Style

- Code is fully typed. Avoid `Any` unless absolutely necessary.
- Follow existing module conventions (see `stroke.py`, `wire.py` for style reference).
- Keep functions focused and add docstrings for non-obvious logic.

---

[English](#english)

# Document Parser for GoodNotes 貢獻指南

感謝你有興趣參與貢獻！本專案建立在謹慎且以證據為基礎的二進位格式分析之上。提交 Pull Request 前請先閱讀本指南。

## 原則

- **不要以未驗證的理論取代解析器發現。** 每個欄位解讀都必須有可觀察的 wire data 支持。
- **將新觀察結果加入 `wiki/09-current-re-findings.md`**，並標註樣本封存成員路徑與具體 protobuf 欄位編號。
- **為新的發現新增測試**，記錄原始 wire 結構。
- **將 schema 解讀與無損 wire decoding 分離**，讓未知欄位仍可供後續分析使用。
- **不得進行浮點位元組掃描。** 所有數值都必須來自依照 wire type 解碼的 protobuf `fixed32`／`fixed64` 欄位。

## 開發環境

```sh
git clone https://github.com/Kaih1825/document-parser-for-goodnotes.git
cd document-parser-for-goodnotes
uv sync
uv run pytest
uv run mypy src/goodnotes_re
```

> **樣本檔案注意事項：** `samples/` 已列於 `.gitignore`，永遠不會提交。依賴樣本檔案的測試在檔案不存在時會使用 `skipTest()`，因此沒有樣本時測試套件仍可執行。

## 提交 Pull Request

1. Fork 儲存庫並建立功能分支：`git checkout -b feat/my-finding`
2. 在 `src/goodnotes_re/` 修改程式，並在 `tests/` 新增或更新測試。
3. 如果發現新的 wire-format 欄位，請記錄在 `wiki/09-current-re-findings.md`。
4. 如果針對既有樣本改變解析行為，執行 `gn-diff old.goodnotes new.goodnotes`，並在 PR 描述中提供 JSON 差異摘要或簡潔說明。
5. 確認測試通過：`uv run pytest`
6. 確認型別檢查通過：`uv run mypy src/goodnotes_re`
7. 向 `main` 開啟 Pull Request，清楚說明修改內容及驗證方式。

## 回報問題

請使用 GitHub Issue 範本：

- **Bug Report** — 回報解析錯誤、SVG 輸出不正確或程式崩潰。
- **Feature Request / Format Finding** — 提議新功能或分享新的格式分析發現。

> **隱私提醒：** 不要附加包含個人資料的 `.goodnotes` 檔案。請盡可能使用最小化的合成樣本。

## 程式碼風格

- 程式碼必須完整型別化。除非絕對必要，否則避免使用 `Any`。
- 遵循既有模組慣例（可參考 `stroke.py`、`wire.py`）。
- 保持函式職責單一，非顯而易見的邏輯應加入 docstring。
