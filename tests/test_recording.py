from pathlib import Path
import tempfile
import unittest

from goodnotes_re.archive import GoodNotesDocument
from goodnotes_re.export import write_audio, write_recording_html, write_recording_video
from goodnotes_re.recording import Recording, RecordingStrokeTiming, parse_recordings_from_events


class RecordingTests(unittest.TestCase):
    def setUp(self):
        self.sample_file = Path(__file__).resolve().parent.parent / "samples" / "record.goodnotes"

    def test_recordings_parsing(self):
        if not self.sample_file.exists():
            self.skipTest("record.goodnotes sample not available")

        with GoodNotesDocument.open(self.sample_file) as doc:
            recordings = doc.recordings(include_deleted=False)
            self.assertEqual(len(recordings), 1)

            rec1 = recordings[0]
            self.assertEqual(rec1.id, "50646DE0-9555-42FC-B27D-9EF4E96BFE1A")
            self.assertEqual(rec1.audio_attachment_path, "attachments/C550091A-9A82-412E-8F10-5075404ACA74")
            self.assertAlmostEqual(rec1.duration, 10.0, places=1)
            self.assertEqual(len(rec1.stroke_timings), 12)
            self.assertFalse(rec1.is_deleted)

            # Check stroke timestamps are ascending
            timestamps = [t.timestamp for t in rec1.stroke_timings]
            self.assertEqual(timestamps, sorted(timestamps))
            self.assertGreater(timestamps[0], 0.0)

            # Check deleted recordings when requested
            all_recordings = doc.recordings(include_deleted=True)
            self.assertGreater(len(all_recordings), len(recordings))
            deleted = [r for r in all_recordings if r.is_deleted]
            self.assertTrue(len(deleted) >= 1)

    def test_read_and_export_audio(self):
        if not self.sample_file.exists():
            self.skipTest("record.goodnotes sample not available")

        with GoodNotesDocument.open(self.sample_file) as doc:
            recordings = doc.recordings()
            self.assertTrue(len(recordings) > 0)
            rec = recordings[0]

            audio_data = doc.read_audio(rec)
            self.assertTrue(len(audio_data) > 0)
            # Audio starts with MP4 ftyp box
            self.assertEqual(audio_data[4:8], b"ftyp")

            with tempfile.TemporaryDirectory() as tmpdir:
                out_file = Path(tmpdir) / "test_audio.m4a"
                res = write_audio(doc, out_file, recording_id=rec.id)
                self.assertTrue(res.exists())
                self.assertEqual(res.stat().st_size, len(audio_data))

                # Test sequential concatenated audio export
                out_concat = Path(tmpdir) / "test_concat.m4a"
                res_concat = write_audio(doc, out_concat, concat=True)
                self.assertTrue(res_concat.exists())
                self.assertGreaterEqual(res_concat.stat().st_size, len(audio_data))

    def test_export_recording_html(self):
        if not self.sample_file.exists():
            self.skipTest("record.goodnotes sample not available")

        with GoodNotesDocument.open(self.sample_file) as doc:
            with tempfile.TemporaryDirectory() as tmpdir:
                out_html = Path(tmpdir) / "player.html"
                res = write_recording_html(
                    doc,
                    out_html,
                    fill_shapes=True,
                    sticky_note_state="open",
                    textbox_state=True,
                    parse_all=True,
                )
                self.assertTrue(res.exists())
                content = res.read_text(encoding="utf-8")
                self.assertIn("<!DOCTYPE html>", content)
                self.assertIn("audioElement", content)
                self.assertIn("recordings", content)
                self.assertIn("data-stroke-id", content)

    def test_export_recording_video(self):
        if not self.sample_file.exists():
            self.skipTest("record.goodnotes sample not available")

        import shutil
        if not shutil.which("ffmpeg"):
            self.skipTest("ffmpeg not available")

        with GoodNotesDocument.open(self.sample_file) as doc:
            with tempfile.TemporaryDirectory() as tmpdir:
                out_mp4 = Path(tmpdir) / "video.mp4"
                # Export with 5 fps for fast test execution, sequential across all recordings
                res = write_recording_video(
                    doc,
                    out_mp4,
                    fps=5,
                    resolution_scale=1.0,
                    fill_shapes=True,
                    sticky_note_state="open",
                    textbox_state=True,
                    parse_all=True,
                )
                self.assertTrue(res.exists())
                self.assertGreater(res.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()

