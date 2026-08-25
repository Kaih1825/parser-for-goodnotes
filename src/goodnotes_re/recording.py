"""Audio recording and timed handwriting synchronization model for GoodNotes."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from .wire import Message, try_decode_message


@dataclass(frozen=True)
class RecordingStrokeTiming:
    """A timestamped stroke linked to an audio recording session."""
    stroke_uuid: str
    timestamp: float  # Start time in seconds relative to recording start
    page_uuid: str

    def as_dict(self) -> dict[str, object]:
        return {
            "stroke_uuid": self.stroke_uuid,
            "timestamp": round(self.timestamp, 4),
            "page_uuid": self.page_uuid,
        }


@dataclass(frozen=True)
class Recording:
    """An audio recording session inside a GoodNotes document."""
    id: str
    audio_attachment_path: str
    duration: float  # Duration in seconds
    stroke_timings: tuple[RecordingStrokeTiming, ...] = field(default_factory=tuple)
    is_deleted: bool = False

    @property
    def page_uuids(self) -> tuple[str, ...]:
        """Unique page UUIDs involved in this recording."""
        seen = []
        for timing in self.stroke_timings:
            if timing.page_uuid and timing.page_uuid not in seen:
                seen.append(timing.page_uuid)
        return tuple(seen)

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "audio_attachment_path": self.audio_attachment_path,
            "duration": round(self.duration, 4),
            "stroke_count": len(self.stroke_timings),
            "page_uuids": list(self.page_uuids),
            "is_deleted": self.is_deleted,
            "stroke_timings": [t.as_dict() for t in self.stroke_timings],
        }


# GoodNotes Mach timestamp clock (31.25 kHz) to audio sample clock (22.05 kHz) ratio: 625 / 441
DEFAULT_CLOCK_RATIO = 625.0 / 441.0


def parse_mp4_duration(data: bytes) -> float | None:
    """Extract audio duration in seconds from MP4 / M4A container header."""
    import struct
    idx = 0
    while idx + 8 <= len(data):
        box_len, box_type = struct.unpack(">I4s", data[idx:idx+8])
        if box_len == 1:  # 64-bit length
            if idx + 16 > len(data):
                break
            box_len = struct.unpack(">Q", data[idx+8:idx+16])[0]
            box_header_size = 16
        else:
            box_header_size = 8
        if box_len == 0:
            box_len = len(data) - idx
        if box_len < box_header_size or idx + box_len > len(data):
            break

        if box_type in (b"moov", b"trak", b"mdia"):
            sub = parse_mp4_duration(data[idx+box_header_size:idx+box_len])
            if sub is not None:
                return sub
        elif box_type in (b"mvhd", b"mdhd"):
            payload = data[idx+box_header_size:idx+box_len]
            if len(payload) >= 20:
                version = payload[0]
                if version == 0:
                    timescale, duration = struct.unpack(">II", payload[12:20])
                elif version == 1 and len(payload) >= 32:
                    timescale, duration = struct.unpack(">IQ", payload[20:32])
                else:
                    timescale, duration = 0, 0
                if timescale > 0 and duration > 0:
                    return duration / timescale
        idx += box_len
    return None


def parse_recordings_from_events(
    events_records: Sequence[Message],
    attachment_map: dict[str, str] | None = None,
    audio_durations: dict[str, float] | None = None,
    include_deleted: bool = False,
) -> tuple[Recording, ...]:
    """Parse audio recordings and synchronized stroke timings from index.events.pb records.

    Field 160 represents a recording session:
      - Field 1: Recording session UUID
      - Field 2: Audio attachment UUID (matching attachments/<UUID> or index.attachments.pb)
      - Field 4: Duration in nanoseconds
      - Field 5: Repeated stroke sync entries (Inner f1 = stroke UUID, Inner f2.f1 = time ns, Inner f2.f2 = page UUID)

    Field 163 represents a recording deletion event:
      - Field 1: Deleted recording session UUID
    """
    deleted_ids: set[str] = set()
    raw_recordings: list[Recording] = []

    # First pass: collect deleted recording IDs
    for rec in events_records:
        for f in rec.by_number(163):
            if isinstance(f.value, bytes):
                msg = try_decode_message(f.value)
                if msg:
                    f1 = msg.by_number(1)
                    if f1 and isinstance(f1[0].value, bytes):
                        try:
                            deleted_ids.add(f1[0].value.decode("utf-8"))
                        except UnicodeDecodeError:
                            pass

    # Second pass: parse recording creation/update events (Field 160)
    for rec in events_records:
        for f in rec.by_number(160):
            if not isinstance(f.value, bytes):
                continue
            msg = try_decode_message(f.value)
            if not msg:
                continue

            rec_id = ""
            f1 = msg.by_number(1)
            if f1 and isinstance(f1[0].value, bytes):
                try:
                    rec_id = f1[0].value.decode("utf-8")
                except UnicodeDecodeError:
                    pass

            if not rec_id:
                continue

            is_deleted = rec_id in deleted_ids
            if is_deleted and not include_deleted:
                continue

            audio_id = ""
            f2 = msg.by_number(2)
            if f2 and isinstance(f2[0].value, bytes):
                try:
                    audio_id = f2[0].value.decode("utf-8")
                except UnicodeDecodeError:
                    pass

            # Resolve attachment path
            audio_path = f"attachments/{audio_id}" if audio_id else ""
            if attachment_map and audio_id in attachment_map:
                audio_path = attachment_map[audio_id]

            # Duration in seconds (field 4 is in nanoseconds in GoodNotes event clock)
            dur_ns = 0
            f4 = msg.by_number(4)
            if f4 and isinstance(f4[0].value, int):
                dur_ns = f4[0].value
            duration_sec = dur_ns / 1e9 if dur_ns > 0 else 0.0

            # Scale stroke timestamps to match real audio playback timeline
            time_scale = DEFAULT_CLOCK_RATIO
            if audio_durations:
                if audio_path in audio_durations and duration_sec > 0:
                    time_scale = audio_durations[audio_path] / duration_sec
                elif audio_id in audio_durations and duration_sec > 0:
                    time_scale = audio_durations[audio_id] / duration_sec

            final_duration = (duration_sec * time_scale) if duration_sec > 0 else 0.0

            # Parse stroke timings from field 5
            stroke_timings: list[RecordingStrokeTiming] = []
            f5 = msg.by_number(5)
            if f5 and isinstance(f5[0].value, bytes) and f5[0].value:
                m5 = try_decode_message(f5[0].value)
                if m5:
                    for item in m5.by_number(1):
                        if not isinstance(item.value, bytes):
                            continue
                        item_msg = try_decode_message(item.value)
                        if not item_msg:
                            continue
                        
                        s_uuid = ""
                        item_f1 = item_msg.by_number(1)
                        if item_f1 and isinstance(item_f1[0].value, bytes):
                            try:
                                s_uuid = item_f1[0].value.decode("utf-8")
                            except UnicodeDecodeError:
                                pass

                        t_ns = 0
                        page_uuid = ""
                        item_f2 = item_msg.by_number(2)
                        if item_f2 and isinstance(item_f2[0].value, bytes):
                            sub2 = try_decode_message(item_f2[0].value)
                            if sub2:
                                s2_f1 = sub2.by_number(1)
                                if s2_f1 and isinstance(s2_f1[0].value, int):
                                    t_ns = s2_f1[0].value
                                s2_f2 = sub2.by_number(2)
                                if s2_f2 and isinstance(s2_f2[0].value, bytes):
                                    try:
                                        page_uuid = s2_f2[0].value.decode("utf-8")
                                    except UnicodeDecodeError:
                                        pass

                        if s_uuid:
                            stroke_timings.append(
                                RecordingStrokeTiming(
                                    stroke_uuid=s_uuid,
                                    timestamp=(t_ns / 1e9) * time_scale,
                                    page_uuid=page_uuid,
                                )
                            )

            # Sort stroke timings chronologically
            stroke_timings.sort(key=lambda t: t.timestamp)

            raw_recordings.append(
                Recording(
                    id=rec_id,
                    audio_attachment_path=audio_path,
                    duration=final_duration,
                    stroke_timings=tuple(stroke_timings),
                    is_deleted=is_deleted,
                )
            )

    return tuple(raw_recordings)
