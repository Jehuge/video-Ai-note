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


def _chunk(content):
    return mock.Mock(choices=[mock.Mock(delta=mock.Mock(content=content))])


if __name__ == "__main__":
    unittest.main()
