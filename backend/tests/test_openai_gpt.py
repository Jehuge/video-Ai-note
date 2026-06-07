import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.gpt.openai_gpt import OpenAIGPT
from app.models.transcriber_model import TranscriptResult, TranscriptSegment


class OpenAIGPTTests(unittest.TestCase):
    def test_client_disables_retries_for_note_generation(self):
        with mock.patch("app.gpt.openai_gpt.create_openai_client", return_value=mock.Mock()) as create_client:
            OpenAIGPT(api_key="sk-test", base_url="https://example.test/v1", model="demo")

        create_client.assert_called_once_with(
            api_key="sk-test",
            base_url="https://example.test/v1",
            timeout=600.0,
            max_retries=0,
        )

    def test_summarize_reads_streaming_chunks(self):
        fake_client = mock.Mock()
        fake_client.chat.completions.create.return_value = [
            _chunk("## Note\n"),
            _chunk("- item"),
        ]

        with mock.patch("app.gpt.openai_gpt.create_openai_client", return_value=fake_client):
            gpt = OpenAIGPT(api_key="sk-test", base_url="https://example.test/v1", model="demo")

        transcript = TranscriptResult(
            language="zh",
            full_text="hello",
            segments=[TranscriptSegment(start=0, end=1, text="hello")],
        )

        markdown = gpt.summarize(transcript, filename="demo.mp4")

        self.assertEqual(markdown, "## Note\n- item")
        self.assertTrue(fake_client.chat.completions.create.call_args.kwargs["stream"])

    def test_streaming_progress_callback_receives_partial_markdown(self):
        fake_client = mock.Mock()
        fake_client.chat.completions.create.return_value = [
            _chunk("a" * 250),
            _chunk("b" * 250),
        ]

        with mock.patch("app.gpt.openai_gpt.create_openai_client", return_value=fake_client):
            gpt = OpenAIGPT(api_key="sk-test", base_url="https://example.test/v1", model="demo")

        events = []
        transcript = TranscriptResult(
            language="zh",
            full_text="hello",
            segments=[TranscriptSegment(start=0, end=1, text="hello")],
        )

        markdown = gpt.summarize(
            transcript,
            filename="demo.mp4",
            progress_callback=lambda message, partial: events.append((message, partial)),
        )

        self.assertEqual(markdown, "a" * 250 + "b" * 250)
        self.assertTrue(events)
        self.assertEqual(events[-1][0], "正在生成笔记")
        self.assertEqual(events[-1][1], markdown)

    def test_long_transcript_uses_chunked_generation_and_final_merge(self):
        fake_client = mock.Mock()
        fake_client.chat.completions.create.side_effect = [
            [_chunk("chunk one")],
            [_chunk("chunk two")],
            [_chunk("chunk three")],
            [_chunk("# Final note")],
        ]

        with mock.patch("app.gpt.openai_gpt.create_openai_client", return_value=fake_client):
            gpt = OpenAIGPT(api_key="sk-test", base_url="https://example.test/v1", model="demo")

        segments = [
            TranscriptSegment(start=i * 2, end=i * 2 + 1, text="x" * 500)
            for i in range(60)
        ]
        transcript = TranscriptResult(language="zh", full_text=" ".join(seg.text for seg in segments), segments=segments)
        events = []

        markdown = gpt.summarize(
            transcript,
            filename="long.mp4",
            progress_callback=lambda message, partial: events.append((message, partial)),
        )

        self.assertEqual(markdown, "# Final note")
        self.assertEqual(fake_client.chat.completions.create.call_count, 4)
        self.assertTrue(any("正在生成第 1/3 段摘要" in message for message, _ in events))
        self.assertTrue(any(message == "正在合并全片笔记" for message, _ in events))


def _chunk(content):
    return mock.Mock(choices=[mock.Mock(delta=mock.Mock(content=content))])


if __name__ == "__main__":
    unittest.main()
