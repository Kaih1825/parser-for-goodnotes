# Controlled binary-format corpus protocol

Semantic parsing is accepted only when one controlled operation changes between two
otherwise identical documents. For every case, retain both the exported `.goodnotes`
source and its GoodNotes PDF export. Use a new document for each feature family.

## Naming

`<generation>-<family>-<case>-before.goodnotes` and
`<generation>-<family>-<case>-after.goodnotes`, plus the matching `after.pdf`.
`generation` is `gn5` or `gn6`. Record the exact application version and platform in
`manifest.json` next to each pair.

## Required cases

| Family | Minimal controlled operations |
| --- | --- |
| Ink | Dot; short/long straight stroke; short/long curve; rapid scribble; ballpoint, fountain pen, brush, highlighter; three colours; three widths. |
| Editing | Erase part and all of one stroke; lasso move; lasso duplicate/paste; undo and redo each operation. |
| Page | Empty; A4 portrait; A4 landscape; Letter portrait; Letter landscape; PDF background; multi-page order. |
| Objects | One raster image; one text box; one line; one circle; one recognised shape; folded and unfolded sticky note. |

## Capture procedure

1. Export `before.goodnotes` before the one operation.
2. Apply precisely one operation; do not modify another object.
3. Export `after.goodnotes` and `after.pdf` immediately.
4. Store expected object count, page number, colour/width, and a visual description in
   `manifest.json`.
5. Run `gn-diff` and commit the member-level difference with the raw samples.

## Acceptance rules

An asserted field mapping needs two independent controlled examples. Ink geometry
requires SVG-to-PDF raster comparison after applying documented coordinate transforms,
with no missing or extra paths. Erasure, lasso movement, and duplication additionally
require proving object identity across before/after pairs. The parser must represent
unresolved bytes as unknown fields rather than silently discard them.
