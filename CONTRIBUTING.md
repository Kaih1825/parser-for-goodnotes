# Contributing reverse-engineering findings

Never replace a parser discovery with an unverified theory. Add new observations to
`docs/knowledge-base.md`, cite the sample archive and member path, and add a test
capturing the raw wire structure. Keep schema interpretation separate from lossless
wire decoding so unknown data remains accessible.

For a changed sample, run `gn-diff old.goodnotes new.goodnotes` and commit the JSON
evidence or a concise summary. Do not add float-byte scanning: all numerical values
must arise from a protobuf fixed32/fixed64 field decoded according to the wire type.
