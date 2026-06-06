import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.routers import note


class NoteStepTests(unittest.TestCase):
    def test_transcribe_step_marks_task_transcribed(self):
        status_updates = []

        class FakeNoteGenerator:
            def __init__(self, model_config=None):
                self.model_config = model_config

            def _extract_audio(self, video_path, task_id):
                return f"{task_id}.wav"

            def _transcribe_audio(self, audio_path, task_id):
                return object()

        with TemporaryDirectory() as tmp:
            with mock.patch.object(note, "NOTE_OUTPUT_DIR", Path(tmp)), \
                    mock.patch.object(note, "NoteGenerator", FakeNoteGenerator), \
                    mock.patch.object(note, "update_task_status", side_effect=lambda task_id, status, markdown=None: status_updates.append(status)):
                note.run_note_task_step(
                    task_id="task-1",
                    video_path="video.mp4",
                    filename="video.mp4",
                    step="transcribe",
                )

        self.assertEqual(status_updates, ["transcribing", "transcribed"])

    def test_failed_step_records_error_message(self):
        updates = []

        class FailingNoteGenerator:
            def __init__(self, model_config=None):
                pass

            def _extract_audio(self, video_path, task_id):
                raise RuntimeError("ffmpeg failed")

        with TemporaryDirectory() as tmp:
            with mock.patch.object(note, "NOTE_OUTPUT_DIR", Path(tmp)), \
                    mock.patch.object(note, "NoteGenerator", FailingNoteGenerator), \
                    mock.patch.object(note, "update_task_status", side_effect=lambda *args, **kwargs: updates.append((args, kwargs))):
                note.run_note_task_step(
                    task_id="task-2",
                    video_path="video.mp4",
                    filename="video.mp4",
                    step="extract",
                )

        self.assertEqual(updates[-1][0][:2], ("task-2", "failed"))
        self.assertEqual(updates[-1][1]["error_message"], "ffmpeg failed")

    def test_empty_transcript_fails_instead_of_summarizing_empty_note(self):
        from app.models.transcriber_model import TranscriptResult
        from app.services.note import NoteGenerator

        class EmptyTranscriber:
            def transcript(self, audio_path):
                return TranscriptResult(language="en", full_text="", segments=[])

        generator = NoteGenerator(model_config={})
        generator.transcriber = EmptyTranscriber()

        with TemporaryDirectory() as tmp:
            with mock.patch.object(note, "NOTE_OUTPUT_DIR", Path(tmp)), \
                    mock.patch("app.services.note.NOTE_OUTPUT_DIR", Path(tmp)):
                with self.assertRaisesRegex(RuntimeError, "没有识别到有效语音"):
                    generator._transcribe_audio("empty.wav", "task-empty")


if __name__ == "__main__":
    unittest.main()
