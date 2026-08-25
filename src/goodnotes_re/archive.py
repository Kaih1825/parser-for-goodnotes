"""GoodNotes ZIP container access and evidence-preserving export."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import zipfile

from .page import Page, parse_page_from_records
from .recording import Recording, parse_mp4_duration, parse_recordings_from_events
from .wire import DecodeError, Message, decode_delimited_messages, decode_message, try_decode_message
from .text import TextFragment, extract_text


# NOTE: GoodNotes appends a per-revision version suffix as the final
# character of a page UUID. The *same* logical page therefore shows up
# with different trailing characters in index.events.pb vs.
# index.notes.pb (e.g. "...907A" in events, "...907B" in notes). Compare
# using the UUID minus its trailing version character instead of exact
# string equality.
def _uuid_key(u: str) -> str:
    return u[:32] if len(u) >= 32 else u



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
    def open(cls, path: str | Path | bytes | io.BytesIO) -> "GoodNotesDocument":
        if isinstance(path, bytes):
            import io
            return cls(Path("memory.goodnotes"), zipfile.ZipFile(io.BytesIO(path)))
        if hasattr(path, "read") and hasattr(path, "seek"):
            return cls(Path(getattr(path, "name", "memory.goodnotes")), zipfile.ZipFile(path))  # type: ignore
        archive_path = Path(path)
        return cls(archive_path, zipfile.ZipFile(archive_path))

    @classmethod
    def from_bytes(cls, data: bytes, filename: str = "memory.goodnotes") -> "GoodNotesDocument":
        import io
        return cls(Path(filename), zipfile.ZipFile(io.BytesIO(data)))

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
            msg = decode_message(data)
            if msg.by_number(7):
                recs = []
                for f in msg.by_number(7):
                    if isinstance(f.value, bytes):
                        nested = try_decode_message(f.value)
                        if nested:
                            recs.append(nested)
                if recs:
                    return tuple(recs)
            return (msg,)
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

    def _page_order_keys(self) -> dict[str, tuple[int, str]]:
        """Return {uuid_key: (timestamp, order_key)} - the current sort
        position of each page, sourced from index.events.pb.

        Each page gets a short, lexicographically-sortable "order key"
        string when it's created (event field 54, order key nested at
        field 4). Dragging a page to a new spot in GoodNotes does NOT
        touch index.notes.pb - it only appends a "page order changed"
        event (field 55, order key nested at field 3) carrying a fresh
        key for that page, chosen to sort between its new neighbours.
        The page listing order is therefore: sort all pages by their
        *latest* known order key (reorder event if present, otherwise
        the key from page creation).
        """
        order_keys: dict[str, tuple[int, str]] = {}
        if "index.events.pb" not in self.member_names():
            return order_keys

        def _record_order_key(msg: Message, page_field_no: int, key_field_no: int) -> None:
            page_field = msg.by_number(page_field_no)
            key_field = msg.by_number(key_field_no)
            if not (page_field and key_field and isinstance(page_field[0].value, bytes) and isinstance(key_field[0].value, bytes)):
                return
            page_uuid = page_field[0].value.decode("utf-8", errors="ignore")
            if not (len(page_uuid) == 36 and "-" in page_uuid):
                return
            wrapper = try_decode_message(key_field[0].value)
            if not wrapper:
                return
            key_str_field = wrapper.by_number(1)
            if not (key_str_field and isinstance(key_str_field[0].value, bytes)):
                return
            try:
                order_key = key_str_field[0].value.decode("utf-8")
            except UnicodeDecodeError:
                return
            ts_field = msg.by_number(14)
            ts = ts_field[0].value if ts_field and isinstance(ts_field[0].value, int) else 0
            uuid_key = _uuid_key(page_uuid)
            prior = order_keys.get(uuid_key)
            # >= so that, among same-timestamp events, the one that
            # appears later in the log (the more recent edit) wins.
            if prior is None or ts >= prior[0]:
                order_keys[uuid_key] = (ts, order_key)

        try:
            records = self.decode_records("index.events.pb")
        except (DecodeError, ValueError):
            return order_keys

        for rec in records:
            # Field 54 = page created; order key nested at field 4.
            for f in rec.by_number(54):
                if isinstance(f.value, bytes):
                    msg = try_decode_message(f.value)
                    if msg:
                        _record_order_key(msg, page_field_no=2, key_field_no=4)
            # Field 55 = page order changed (dragged to a new spot);
            # order key nested at field 3.
            for f in rec.by_number(55):
                if isinstance(f.value, bytes):
                    msg = try_decode_message(f.value)
                    if msg:
                        _record_order_key(msg, page_field_no=2, key_field_no=3)

        return order_keys

    def pages(self,parse_all:bool = False) -> tuple[Page, ...]:
        """Extract and parse all document pages, preserving page order and attachments."""
        page_entries: list[tuple[str, str]] = []

        # Field 56 in index.events.pb is the "PageDeleted" event; its nested
        # field 2 holds the target page UUID *as recorded at deletion time*,
        # which will not match the notes-index UUID via exact string
        # equality, hence the _uuid_key() comparison below.
        inactive_page_ids = set()
        if "index.events.pb" in self.member_names() and not parse_all:
            try:
                records = self.decode_records("index.events.pb")
                for rec in records:
                    # Field 56 = PageDeleted event; its nested field 2 is the
                    # deleted page's UUID.
                    field_data = rec.by_number(56)
                    for data in field_data:
                        nested_msg = try_decode_message(data.value)
                        if nested_msg:
                            f2 = nested_msg.by_number(2)
                            if f2 and isinstance(f2[0].value, bytes):
                                target_value = f2[0].value.decode("utf-8", errors="ignore")
                                if len(target_value) == 36 and "-" in target_value:
                                    inactive_page_ids.add(_uuid_key(target_value))
            except (DecodeError, ValueError):
                pass

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
                    if p_path and p_path in self.member_names() and _uuid_key(p_uuid) not in inactive_page_ids:
                        page_entries.append((p_uuid or p_path.replace("notes/", ""), p_path))
            except (DecodeError, ValueError):
                pass

        if not page_entries:
            note_members = sorted(m for m in self.member_names() if m.startswith("notes/"))
            for m in note_members:
                page_entries.append((m.replace("notes/", ""), m))

        # index.notes.pb records the page *listing*, but GoodNotes does NOT
        # rewrite it when the user drags a page to a new position - only
        # index.events.pb gets a new "page order changed" event. Without
        # this step, page_entries always reflects the order pages were
        # originally created in, never a later reorder.
        order_keys = self._page_order_keys()
        if order_keys:
            original_pos = {p_uuid: i for i, (p_uuid, _) in enumerate(page_entries)}

            def _order_sort_key(entry: tuple[str, str]) -> tuple:
                p_uuid, _ = entry
                found = order_keys.get(_uuid_key(p_uuid))
                if found is not None:
                    return (0, found[1], 0)
                # No order key on record (shouldn't normally happen): keep
                # it in its original relative position, after any pages
                # that do have a known key.
                return (1, "", original_pos[p_uuid])

            page_entries.sort(key=_order_sort_key)

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

        # Match page to attachment PDF/image via index.events.pb
        # attachment_by_page: dict[str, str] = {}
        # if "index.events.pb" in self.member_names():
        #     try:
        #         template_to_att: dict[str, str] = {}
        #         page_to_template: dict[str, str] = {}
        #         direct_page_to_att: dict[str, str] = {}

        #         for rec in self.decode_records("index.events.pb"):
        #             # 1. Field 2 (Template node creation): maps tmpl_uuid -> att_uuid
        #             f2 = rec.by_number(2)
        #             if f2 and isinstance(f2[0].value, bytes):
        #                 msg = try_decode_message(f2[0].value)
        #                 if msg:
        #                     tmpl_uuid = ""
        #                     att_uuid = ""
        #                     for mf in msg.fields:
        #                         if mf.number == 2 and isinstance(mf.value, bytes):
        #                             tmpl_uuid = mf.value.decode("utf-8", errors="ignore")
        #                         elif mf.number == 4 and isinstance(mf.value, bytes):
        #                             att_uuid = mf.value.decode("utf-8", errors="ignore")
        #                     if tmpl_uuid and att_uuid:
        #                         template_to_att[tmpl_uuid] = att_uuid

        #             # 2. Field 54 (Page node creation): maps page_node_uuid -> tmpl_uuid
        #             f54 = rec.by_number(54)
        #             if f54 and isinstance(f54[0].value, bytes):
        #                 msg = try_decode_message(f54[0].value)
        #                 if msg:
        #                     page_node_uuid = ""
        #                     tmpl_uuid = ""
        #                     for mf in msg.fields:
        #                         if mf.number == 2 and isinstance(mf.value, bytes):
        #                             page_node_uuid = mf.value.decode("utf-8", errors="ignore")
        #                         elif mf.number == 3 and isinstance(mf.value, bytes):
        #                             sub = try_decode_message(mf.value)
        #                             if sub and sub.by_number(1) and isinstance(sub.by_number(1)[0].value, bytes):
        #                                 tmpl_uuid = sub.by_number(1)[0].value.decode("utf-8", errors="ignore")
        #                     if page_node_uuid and tmpl_uuid:
        #                         page_to_template[page_node_uuid] = tmpl_uuid

        #             # 3. Direct scanning across record fields as fallback
        #             p_uuid = ""
        #             att_id = ""
        #             for f in rec.fields:
        #                 if isinstance(f.value, bytes):
        #                     try:
        #                         s = f.value.decode("utf-8")
        #                         if len(s) == 36 and "-" in s:
        #                             if s in att_map:
        #                                 att_id = s
        #                             else:
        #                                 p_uuid = s
        #                     except UnicodeDecodeError:
        #                         pass
        #             if p_uuid and att_id and att_id in att_map:
        #                 direct_page_to_att[p_uuid] = att_map[att_id]

        #         for p_uuid, member_path in page_entries:
        #             matched_path = None
        #             for p_node_uuid, tmpl_uuid in page_to_template.items():
        #                 if p_uuid == p_node_uuid or (len(p_uuid) >= 32 and p_uuid[:32] == p_node_uuid[:32]):
        #                     att_uuid = template_to_att.get(tmpl_uuid)
        #                     if att_uuid and att_uuid in att_map:
        #                         matched_path = att_map[att_uuid]
        #                         break

        #             if not matched_path:
        #                 for p_cand, a_path in direct_page_to_att.items():
        #                     if p_uuid == p_cand or (len(p_uuid) >= 32 and p_uuid[:32] == p_cand[:32]):
        #                         matched_path = a_path
        #                         break

        #             if matched_path:
        #                 attachment_by_page[p_uuid] = matched_path
        #     except (DecodeError, ValueError):
        #         pass

        # Match page to attachment PDF/image via index.events.pb
        attachment_by_page: dict[str, str] = {}
        pdf_page_index_by_page: dict[str, int] = {}
        if "index.events.pb" in self.member_names():
            try:
                template_to_att: dict[str, str] = {}
                template_to_pdf_page: dict[str, int] = {}
                page_to_template: dict[str, str] = {}
                direct_page_to_att: dict[str, str] = {}

                for rec in self.decode_records("index.events.pb"):
                    # 1. Field 2 (Template node creation): maps tmpl_uuid -> att_uuid & pdf_page_index
                    f2 = rec.by_number(2)
                    if f2 and isinstance(f2[0].value, bytes):
                        msg = try_decode_message(f2[0].value)
                        if msg:
                            tmpl_uuid = ""
                            att_uuid = ""
                            pdf_page_idx = 1
                            for mf in msg.fields:
                                if mf.number == 2 and isinstance(mf.value, bytes):
                                    tmpl_uuid = mf.value.decode("utf-8", errors="ignore")
                                elif mf.number == 4 and isinstance(mf.value, bytes):
                                    att_uuid = mf.value.decode("utf-8", errors="ignore")
                                elif mf.number == 5 and isinstance(mf.value, int):
                                    pdf_page_idx = mf.value
                            if tmpl_uuid and att_uuid:
                                template_to_att[tmpl_uuid] = att_uuid
                                template_to_pdf_page[tmpl_uuid] = pdf_page_idx

                    # 2. Field 54 (Page node creation): maps page_node_uuid -> tmpl_uuid
                    # Page/template creation has appeared under different event field numbers.
                    for page_field_number in (54, 3):
                        f_page = rec.by_number(page_field_number)
                        if not f_page or not isinstance(f_page[0].value, bytes):
                            continue
                        msg = try_decode_message(f_page[0].value)
                        if not msg:
                            continue
                        page_node_uuid = ""
                        tmpl_uuid = ""
                        for mf in msg.fields:
                            if mf.number == 2 and isinstance(mf.value, bytes):
                                page_node_uuid = mf.value.decode("utf-8", errors="ignore")
                            elif mf.number == 3 and isinstance(mf.value, bytes):
                                sub = try_decode_message(mf.value)
                                if sub and sub.by_number(1) and isinstance(sub.by_number(1)[0].value, bytes):
                                    tmpl_uuid = sub.by_number(1)[0].value.decode("utf-8", errors="ignore")
                        if page_node_uuid and tmpl_uuid:
                            page_to_template[page_node_uuid] = tmpl_uuid

                    # 3. Direct scanning across record fields as fallback
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
                        direct_page_to_att[p_uuid] = att_map[att_id]

                for p_uuid, member_path in page_entries:
                    matched_path = None
                    matched_pdf_page = 1
                    p_key = _uuid_key(p_uuid)

                    # Prefer directly matched attachments
                    for p_cand, a_path in direct_page_to_att.items():
                        if _uuid_key(p_cand) == p_key:
                            matched_path = a_path
                            matched_pdf_page = 1
                            break

                    # If no directly matched attachment, fall back to default template
                    if not matched_path:
                        for p_node_uuid, tmpl_uuid in page_to_template.items():
                            if _uuid_key(p_node_uuid) == p_key:
                                att_uuid = template_to_att.get(tmpl_uuid)
                                if att_uuid and att_uuid in att_map:
                                    matched_path = att_map[att_uuid]
                                    matched_pdf_page = template_to_pdf_page.get(tmpl_uuid, 1)
                                    break

                    if matched_path:
                        attachment_by_page[p_uuid] = matched_path
                        pdf_page_index_by_page[p_uuid] = matched_pdf_page
            except (DecodeError, ValueError):
                pass
        pages_list: list[Page] = []
        for idx, (p_uuid, member_path) in enumerate(page_entries):
            try:
                records = self.decode_records(member_path)
            except (DecodeError, ValueError):
                continue

            att_path = attachment_by_page.get(p_uuid)
            pdf_page_idx = pdf_page_index_by_page.get(p_uuid, 1)
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
                    pdf_page_idx = idx + 1

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
                pdf_page_index=pdf_page_idx,
            )
            pages_list.append(page_obj)

        return tuple(pages_list)

    def recordings(self, include_deleted: bool = False) -> tuple[Recording, ...]:
        """Extract audio recordings and synchronized stroke timings from document events."""
        if "index.events.pb" not in self.member_names():
            return ()
        try:
            records = self.decode_records("index.events.pb")
        except (DecodeError, ValueError):
            return ()

        # Build attachment map
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

        # Probe durations from audio attachments directly
        audio_durations: dict[str, float] = {}
        for member in self.member_names():
            if member.startswith("attachments/"):
                try:
                    data = self.read(member)
                    dur = parse_mp4_duration(data)
                    if dur is not None:
                        audio_durations[member] = dur
                        audio_durations[member.replace("attachments/", "")] = dur
                except Exception:
                    pass

        return parse_recordings_from_events(
            records,
            attachment_map=att_map,
            audio_durations=audio_durations,
            include_deleted=include_deleted,
        )

    def read_audio(self, recording: Recording | str) -> bytes:
        """Read the raw audio bytes for a recording or attachment member path."""
        path = recording.audio_attachment_path if isinstance(recording, Recording) else recording
        if path not in self.member_names():
            if f"attachments/{path}" in self.member_names():
                path = f"attachments/{path}"
            else:
                raise FileNotFoundError(f"Audio attachment '{path}' not found in document")
        return self.read(path)

    def export_audio(self, recording: Recording | str, output_path: str | Path) -> Path:
        """Export audio track of a recording to a file."""
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        data = self.read_audio(recording)
        out.write_bytes(data)
        return out

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
            "recordings": [r.as_dict() for r in self.recordings()],
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