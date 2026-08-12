# Contributing to GoodNotes Reverse Engineering Toolkit

Thank you for your interest in contributing! This project is built on careful, evidence-based reverse engineering. Please read this guide before submitting a pull request.

---

## Principles

- **Never replace a parser discovery with an unverified theory.** Every field interpretation must be backed by observable wire data.
- **Add new observations to `docs/knowledge-base.md`**, citing the sample archive member path and the specific protobuf field numbers.
- **Add a test** capturing the raw wire structure of any new finding.
- **Keep schema interpretation separate from lossless wire decoding** so unknown fields remain accessible to future analysis.
- **No float-byte scanning.** All numerical values must arise from a protobuf `fixed32`/`fixed64` field decoded according to its wire type.

---

## Development Setup

```sh
# Clone the repository
git clone https://github.com/<your-org>/goodnotes-reverse-engineering-toolkit.git
cd goodnotes-reverse-engineering-toolkit

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
3. If you discovered a new wire-format field, document it in `docs/knowledge-base.md`.
4. If you changed parsing behavior against an existing sample, run `gn-diff old.goodnotes new.goodnotes` and include the JSON diff summary or a concise description in your PR description.
5. Ensure tests pass: `uv run pytest`
6. Ensure type checks pass: `uv run mypy src/goodnotes_re`
7. Open a pull request against `main` with a clear description of what was found and how it was verified.

---

## Reporting Issues

Use the GitHub Issue templates:

- **Bug Report** — for parsing errors, incorrect SVG output, or crashes.
- **Feature Request / Finding** — for proposing new functionality or sharing a reverse-engineering discovery.

> **Privacy reminder:** Do not attach `.goodnotes` files containing personal data. Use a minimal synthetic sample whenever possible.

---

## Code Style

- Code is fully typed. Avoid `Any` unless absolutely necessary.
- Follow existing module conventions (see `stroke.py`, `wire.py` for style reference).
- Keep functions focused and add docstrings for non-obvious logic.
