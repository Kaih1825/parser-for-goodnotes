---
name: Bug Report
about: Report a parsing error, incorrect output, or unexpected crash
title: "[Bug] "
labels: bug
assignees: ""
---

## Description

A clear and concise description of the bug.

## To Reproduce

Steps to reproduce the behavior:

1. Run `gn-export-svg sample.goodnotes -o out/`
2. Observe error / incorrect SVG output

## Expected Behavior

What you expected to happen.

## Actual Behavior

What actually happened. Include the full error traceback if applicable.

## Sample File

> **Do not attach files containing personal data.**
> If you can reproduce the issue with a minimal synthetic file, please include it.

- Provide a minimal `.goodnotes` file that demonstrates the issue, **or**
- Describe the archive structure (member names, sizes) that triggers the bug

## Environment

- OS: (e.g. macOS 14, Ubuntu 22.04)
- Python version: `python --version`
- Package version: `pip show goodnotes-reverse-engineering-toolkit`

## Additional Context

Any other context about the problem (e.g. GoodNotes version that created the file, pen tool used).
