import sys
import unittest
from types import SimpleNamespace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import video_task_dao
from app.db.engine import Base
from app.routers import note
from app.services.note_progress import write_note_progress
from fastapi import BackgroundTasks
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class NoteStepTests(unittest.TestCase):
    def test_transition_task_status_claims_expected_state_once(self):
        engine = create_engine("sqlite://")
        testing_session = sessionmaker(bind=engine)
        Base.metadata.create_all(engine)

        with mock.patch.object(video_task_dao, "SessionLocal", testing_session):
            video_task_dao.create_task("task-claim", "video.mp4")
            self.assertTrue(
                video_task_dao.transition_task_status(
                    "task-claim",
                    {"pending"},
                    "extracting",
                )
            )
            self.assertFalse(
                video_task_dao.transition_task_status(
                    "task-claim",
                    {"pending"},
                    "extracting",
                )
            )
            self.assertEqual(video_task_dao.get_task_by_id("task-claim").status, "extracting")

        engine.dispose()

    def test_transcribe_step_marks_task_transcribed(self):
        status_updates = []

        class FakeNoteGenerator:
            def __init__(self, model_config=None):
                self.model_config = model_config

            def _extract_audio(self, video_path, task_id):
                raise AssertionError("transcribe should reuse extracted audio")

            def _transcribe_audio(self, audio_path, task_id):
                return object()

        with TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            (output_dir / "task-1_audio.wav").write_bytes(b"audio")
            with mock.patch.object(note, "NOTE_OUTPUT_DIR", output_dir), \
                    mock.patch.object(note, "NoteGenerator", FakeNoteGenerator), \
                    mock.patch.object(note, "update_task_status", side_effect=lambda task_id, status, markdown=None: status_updates.append(status)):
                note.run_note_task_step(
                    task_id="task-1",
                    video_path="video.mp4",
                    filename="video.mp4",
                    step="transcribe",
                )

        self.assertEqual(status_updates, ["transcribing", "transcribed"])

    def test_summarize_step_reuses_transcript_without_extracting_audio(self):
        status_updates = []

        class FakeNoteGenerator:
            def __init__(self, model_config=None):
                pass

            def _extract_audio(self, video_path, task_id):
                raise AssertionError("summarize should not extract audio")

            def _transcribe_audio(self, audio_path, task_id):
                return object()

            def _summarize_text(self, *args, **kwargs):
                return "# note"

        with TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            (output_dir / "task-summary_transcript.json").write_text("{}", encoding="utf-8")
            with mock.patch.object(note, "NOTE_OUTPUT_DIR", output_dir), \
                    mock.patch.object(note, "NoteGenerator", FakeNoteGenerator), \
                    mock.patch.object(note, "update_task_status", side_effect=lambda task_id, status, markdown=None: status_updates.append(status)):
                note.run_note_task_step(
                    task_id="task-summary",
                    video_path="video.mp4",
                    filename="video.mp4",
                    step="summarize",
                )

        self.assertEqual(status_updates, ["summarizing", "completed"])

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

    def test_get_task_returns_note_generation_progress(self):
        task = mock.Mock()
        task.task_id = "task-progress"
        task.filename = "video.mp4"
        task.status = "summarizing"
        task.error_message = None
        task.markdown = None
        task.source = "upload"
        task.source_url = None
        task.created_at = None
        task.updated_at = None

        with TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            write_note_progress(output_dir, "task-progress", "正在生成第 1/3 段摘要", "## partial")

            with mock.patch.object(note, "NOTE_OUTPUT_DIR", output_dir), \
                    mock.patch.object(note, "get_task_by_id", return_value=task):
                response = note.get_task("task-progress")

        self.assertEqual(response["code"], 200)
        self.assertEqual(response["data"]["progress_message"], "正在生成第 1/3 段摘要")
        self.assertEqual(response["data"]["partial_markdown"], "## partial")

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

    def test_confirm_step_does_not_enqueue_when_status_claim_fails(self):
        task = SimpleNamespace(
            task_id="task-confirm-raced",
            filename="video.mp4",
            status="pending",
            screenshot=0,
        )

        with TemporaryDirectory() as tmp:
            upload_dir = Path(tmp)
            (upload_dir / "task-confirm-raced.mp4").write_bytes(b"video")
            background_tasks = BackgroundTasks()

            with mock.patch.object(note, "UPLOAD_DIR", upload_dir), \
                    mock.patch.object(note, "get_task_by_id", return_value=task), \
                    mock.patch.object(note, "transition_task_status", return_value=False):
                response = note.confirm_step(
                    "task-confirm-raced",
                    note.ConfirmStepRequest(step="extract"),
                    background_tasks,
                )

        self.assertNotEqual(response["code"], 200)
        self.assertEqual(len(background_tasks.tasks), 0)

    def test_failed_task_retries_only_failed_stage(self):
        task = SimpleNamespace(
            task_id="task-failed",
            filename="video.mp4",
            status="failed",
            failed_step="summarize",
            screenshot=0,
            source="upload",
            source_url=None,
        )

        with TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "notes"
            upload_dir = Path(tmp) / "uploads"
            output_dir.mkdir()
            upload_dir.mkdir()
            (upload_dir / "task-failed.mp4").write_bytes(b"video")
            (output_dir / "task-failed_audio.wav").write_bytes(b"audio")
            (output_dir / "task-failed_transcript.json").write_text("{}", encoding="utf-8")
            background_tasks = BackgroundTasks()

            with mock.patch.object(note, "NOTE_OUTPUT_DIR", output_dir), \
                    mock.patch.object(note, "UPLOAD_DIR", upload_dir), \
                    mock.patch.object(note, "get_task_by_id", side_effect=[task, task]), \
                    mock.patch.object(note, "transition_task_status", return_value=True) as transition_status:
                response = note._retry_task_step(
                    "task-failed",
                    "summarize",
                    note.RetryStepRequest(step="summarize", noteStyle="simple"),
                    background_tasks,
                )

        self.assertEqual(response["code"], 200)
        self.assertEqual(response["data"]["task_id"], "task-failed")
        self.assertEqual(response["data"]["status"], "summarizing")
        transition_status.assert_called_once_with("task-failed", {"failed"}, "summarizing")
        self.assertEqual(len(background_tasks.tasks), 1)

    def test_completed_task_forks_before_rerunning_stage(self):
        task = SimpleNamespace(
            task_id="task-completed",
            filename="video.mp4",
            status="completed",
            failed_step=None,
            screenshot=1,
            source="upload",
            source_url="https://example.test/video",
        )
        branch = SimpleNamespace(
            task_id="task-branch",
            filename="video.mp4",
            status="summarizing",
            screenshot=1,
        )

        with TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "notes"
            upload_dir = Path(tmp) / "uploads"
            output_dir.mkdir()
            upload_dir.mkdir()
            (upload_dir / "task-completed.mp4").write_bytes(b"video")
            (output_dir / "task-completed_audio.wav").write_bytes(b"audio")
            (output_dir / "task-completed_transcript.json").write_text("{}", encoding="utf-8")
            background_tasks = BackgroundTasks()
            created = {}

            with mock.patch.object(note, "NOTE_OUTPUT_DIR", output_dir), \
                    mock.patch.object(note, "UPLOAD_DIR", upload_dir), \
                    mock.patch.object(note.uuid, "uuid4", return_value=UUID("11111111-1111-1111-1111-111111111111")), \
                    mock.patch.object(note, "get_task_by_id", side_effect=[task, branch]), \
                    mock.patch.object(note, "create_task", side_effect=lambda **kwargs: created.update(kwargs)):
                response = note._retry_task_step(
                    "task-completed",
                    "summarize",
                    note.RetryStepRequest(step="summarize", noteStyle="academic"),
                    background_tasks,
                )

            branch_id = "11111111-1111-1111-1111-111111111111"
            self.assertEqual(response["code"], 200)
            self.assertTrue(response["data"]["forked"])
            self.assertEqual(created["status"], "summarizing")
            self.assertEqual(response["data"]["status"], "summarizing")
            self.assertTrue((upload_dir / f"{branch_id}.mp4").exists())
            self.assertFalse((output_dir / f"{branch_id}_audio.wav").exists())
            self.assertTrue((output_dir / f"{branch_id}_transcript.json").exists())
            self.assertEqual(len(background_tasks.tasks), 1)

    def test_retry_does_not_mutate_outputs_when_status_claim_fails(self):
        task = SimpleNamespace(
            task_id="task-raced",
            filename="video.mp4",
            status="failed",
            failed_step="summarize",
        )

        with TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "notes"
            upload_dir = Path(tmp) / "uploads"
            output_dir.mkdir()
            upload_dir.mkdir()
            (upload_dir / "task-raced.mp4").write_bytes(b"video")
            markdown_file = output_dir / "task-raced_markdown.md"
            markdown_file.write_text("existing", encoding="utf-8")
            background_tasks = BackgroundTasks()

            with mock.patch.object(note, "NOTE_OUTPUT_DIR", output_dir), \
                    mock.patch.object(note, "UPLOAD_DIR", upload_dir), \
                    mock.patch.object(note, "get_task_by_id", return_value=task), \
                    mock.patch.object(note, "transition_task_status", return_value=False):
                response = note._retry_task_step(
                    "task-raced",
                    "summarize",
                    note.RetryStepRequest(step="summarize"),
                    background_tasks,
                )
                markdown_after_retry = markdown_file.read_text(encoding="utf-8")

        self.assertNotEqual(response["code"], 200)
        self.assertEqual(markdown_after_retry, "existing")
        self.assertEqual(len(background_tasks.tasks), 0)


if __name__ == "__main__":
    unittest.main()
