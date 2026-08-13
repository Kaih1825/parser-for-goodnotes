# Binary format knowledge base

## Evidence baseline (2026-08-04)

| Finding | Evidence |
| --- | --- |
| A `.goodnotes` file is a ZIP archive. | `Teat.goodnotes`, `ooo.goodnotes`, and `國際情勢.goodnotes` all open as ZIP archives. |
| `schema.pb` is protobuf field 1, varint value 35 in all current samples. | Archive member `schema.pb` contains bytes `08 23`. |
| Archive indexes and `notes/<UUID>` members are streams of varint-length-prefixed protobuf records. | `index.notes.pb` starts `52 0a...`: `0x52` is the 82-byte record length, followed by protobuf field 1. A Teat note starts `6c 0a...`: a 108-byte record. |
| `index.events.pb` contains high-numbered protobuf fields. | `Teat.goodnotes:index.events.pb` starts with wire key bytes `b1 02` (field 38, fixed). |
| Notes live in `notes/<UUID>` and corresponding content is indexed. | All supplied archives. |
| Typed text & sticky note content stored as RTF / UTF-8 length-delimited payload. | `國際情勢.goodnotes` and `Teat.goodnotes` contain RTF headers and Traditional-Chinese/UTF-8 byte fragments in note records. |
| `bv41` is an Apple framed LZ4 stream. | Every discovered payload has `bv41`, little-endian sizes, and a terminating `bv4$`. |
| TPL binary format (`tpl\0`) with embedded type descriptors defines stroke geometry. | Decompressed LZ4 streams start with `tpl\0` and format strings like `vuA(v)A(S(uu))A(S(uuuu))vA(f)` and `vuA(v)A(S(uuuuu))...`. Troy Hanson TPL binary decoding extracts coordinates without heuristic float scanning. |
| Protobuf trailer following `bv4$` contains RGBA stroke color and opacity. | Direct protobuf wire decoding of bytes after `bv4$` reveals tag `0x22` (field 4) containing nested FIXED32 fields for Red, Green, Blue, Alpha (e.g. `alpha=0.50` for highlighters). |
| Coordinate space & PDF MediaBox resolution. | GoodNotes stroke coordinates are in 132 DPI space. Scaling by `72.0 / 132.0` aligns strokes with PDF background `/MediaBox` dimensions (A4, Letter, landscape). |
| Page records also carry non-stroke element metadata. | Teat page 2 contains a record with `field 4` set to attachment UUID `31BE4069-02E5-4C5D-BFF9-2A8DCBC744E9`, which points at the 1.08 MB JPEG attachment in `attachments/31BE4069-02E5-4C5D-BFF9-2A8DCBC744E9`. |
| Page record summaries are useful for format analysis. | Each decoded page record is now summarized as a typed `PageElement` with `kind`, `type_code`, `attachment_uuid`, related UUIDs, and field numbers while preserving the raw protobuf tree separately. |
| Shape geometry lives in nested protobuf inside `field 9`. | Teat records `7`, `21`, `23`, and `39` contain `field 9` messages with child field `1` or `2`, which then contain repeated submessages of FIXED32 x/y pairs. These decode to explicit line/shape geometry without float scanning. |

## Interpretation policy

The wire decoder is authoritative. Labels such as `page` and `stroke` are
interpretations and must not overwrite raw fields. All stroke coordinates are
decoded strictly through Troy Hanson TPL format descriptors embedded in the LZ4 stream,
and stroke colors are extracted from the protobuf trailer following `bv4$`.
Heuristic float scanning is strictly prohibited.

## Validation boundary

Every page in `Teat.goodnotes`, `ooo.goodnotes`, and `國際情勢.goodnotes` exports to valid JSON and SVG vector pages matching page dimensions, orientations, stroke ribbons, single dot points, highlighter opacity, and text/sticky note contents.
