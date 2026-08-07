"""GoodNotes ZIP container access and evidence-preserving export."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import zipfile

from .page import Page, parse_page_from_records
from .wire import DecodeError, Message, decode_delimited_messages, decode_message
from .text import TextFragment, extract_text


@dataclass(frozen=True)
class ArchiveMember:
    path: str
    size: int
    sha256: str
    is_protobuf: bool


@dataclass
class GoodNotesDocument:
    path: Path
    _archive: zipfile.ZipFile

    @classmethod
    def open(cls, path: str | Path) -> "GoodNotesDocument":
        archive_path = Path(path)
        return cls(archive_path, zipfile.ZipFile(archive_path))

    def close(self) -> None:
        self._archive.close()

    def __enter__(self) -> "GoodNotesDocument":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def member_names(self) -> tuple[str, ...]:
        return tuple(info.filename for info in self._archive.infolist() if not info.is_dir())

    def read(self, member: str) -> bytes:
        return self._archive.read(member)

    def decode(self, member: str) -> Message:
        data = self.read(member)
        try:
            return decode_message(data)
        except DecodeError as direct_error:
            try:
                records = decode_delimited_messages(data)
            except DecodeError:
                raise direct_error
            return Message(tuple(field for record in records for field in record.fields), data)

    def decode_records(self, member: str) -> tuple[Message, ...]:
        """Return the explicit delimited records, or one unframed message."""
        data = self.read(member)
        try:
            return (decode_message(data),)
        except DecodeError as direct_error:
            try:
                return decode_delimited_messages(data)
            except DecodeError:
                raise direct_error

    def inventory(self) -> tuple[ArchiveMember, ...]:
        return tuple(
            ArchiveMember(info.filename, info.file_size, hashlib.sha256(self.read(info.filename)).hexdigest(), info.filename.endswith(".pb"))
            for info in self._archive.infolist()
            if not info.is_dir()
        )

    def pages(self) -> tuple[Page, ...]:
        """Extract and parse all document pages, preserving page order and attachments."""
        page_entries: list[tuple[str, str]] = []
        if "index.notes.pb" in self.member_names():
            try:
                records = self.decode_records("index.notes.pb")
                for rec in records:
                    p_uuid = ""
                    p_path = ""
                    for f in rec.fields:
                        if isinstance(f.value, bytes):
                            try:
                                val_str = f.value.decode("utf-8")
                                if val_str.startswith("notes/"):
                                    p_path = val_str
                                elif len(val_str) == 36 and "-" in val_str:
                                    p_uuid = val_str
                            except UnicodeDecodeError:
                                pass
                    if p_path and p_path in self.member_names():
                        page_entries.append((p_uuid or p_path.replace("notes/", ""), p_path))
            except (DecodeError, ValueError):
                pass

        if not page_entries:
            note_members = sorted(m for m in self.member_names() if m.startswith("notes/"))
            for m in note_members:
                page_entries.append((m.replace("notes/", ""), m))

        # Build attachment maps
        att_map: dict[str, str] = {}
        if "index.attachments.pb" in self.member_names():
            try:
                for rec in self.decode_records("index.attachments.pb"):
                    att_id = ""
                    att_path = ""
                    for f in rec.fields:
                        if isinstance(f.value, bytes):
                            try:
                                s = f.value.decode("utf-8")
                                if s.startswith("attachments/"):
                                    att_path = s
                                elif len(s) == 36 and "-" in s:
                                    att_id = s
                            except UnicodeDecodeError:
                                pass
                    if att_id and att_path:
                        att_map[att_id] = att_path
            except (DecodeError, ValueError):
                pass

        # Match page to attachment PDF
        attachment_by_page: dict[str, str] = {}
        if "index.events.pb" in self.member_names():
            try:
                for rec in self.decode_records("index.events.pb"):
                    p_uuid = ""
                    att_id = ""
                    for f in rec.fields:
                        if isinstance(f.value, bytes):
                            try:
                                s = f.value.decode("utf-8")
                                if len(s) == 36 and "-" in s:
                                    if s in att_map:
                                        att_id = s
                                    else:
                                        p_uuid = s
                            except UnicodeDecodeError:
                                pass
                    if p_uuid and att_id and att_id in att_map:
                        attachment_by_page[p_uuid] = att_map[att_id]
            except (DecodeError, ValueError):
                pass

        pages_list: list[Page] = []
        for idx, (p_uuid, member_path) in enumerate(page_entries):
            try:
                records = self.decode_records(member_path)
            except (DecodeError, ValueError):
                continue

            att_path = attachment_by_page.get(p_uuid)
            pdf_bytes = None
            if not att_path:
                # Find main PDF attachment (prefer larger multi-page PDFs over 1KB templates)
                pdf_atts = sorted(
                    [m for m in self.member_names() if m.startswith("attachments/") and self.read(m).startswith(b"%PDF")],
                    key=lambda m: self._archive.getinfo(m).file_size,
                    reverse=True,
                )
                if pdf_atts:
                    att_path = pdf_atts[min(idx, len(pdf_atts) - 1)]

            if att_path and att_path in self.member_names():
                bdata = self.read(att_path)
                if bdata.startswith(b"%PDF"):
                    pdf_bytes = bdata

            page_obj = parse_page_from_records(
                page_index=idx,
                page_uuid=p_uuid,
                member_path=member_path,
                records=records,
                pdf_attachment_bytes=pdf_bytes,
                attachment_path=att_path,
            )
            pages_list.append(page_obj)

        return tuple(pages_list)

    def as_json(self) -> dict[str, object]:
        protobuf: dict[str, object] = {}
        for member in self.member_names():
            if member.endswith(".pb") or member.startswith(("notes/", "search/")):
                try:
                    protobuf[member] = self.decode(member).as_json()
                except ValueError as error:
                    protobuf[member] = {"decode_error": str(error)}
        return {
            "source": self.path.name,
            "members": [member.__dict__ if hasattr(member, "__dict__") else {"path": member.path, "size": member.size, "sha256": member.sha256, "is_protobuf": member.is_protobuf} for member in self.inventory()],
            "pages": [p.as_dict() for p in self.pages()],
            "protobuf": protobuf,
        }

    def text_fragments(self) -> tuple[TextFragment, ...]:
        """Extract text/RTF stored in note protobuf records with source locations."""
        fragments: list[TextFragment] = []
        for member in self.member_names():
            if not member.startswith("notes/"):
                continue
            try:
                for record_index, record in enumerate(self.decode_records(member)):
                    for fragment in extract_text(record, f"{member}.record[{record_index}]"):
                        fragments.append(fragment)
            except DecodeError:
                continue
        return tuple(fragments)
