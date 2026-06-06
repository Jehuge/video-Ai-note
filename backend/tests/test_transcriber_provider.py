import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.transcriber import transcriber_provider


class TranscriberProviderTests(unittest.TestCase):
    def test_remote_transcriber_env_is_ignored_for_local_whisper(self):
        with mock.patch.dict(os.environ, {
            "TRANSCRIBER_TYPE": "openai-whisper",
            "TRANSCRIBE_API_KEY": "local-key",
            "TRANSCRIBE_BASE_URL": "http://127.0.0.1:8766/v1",
            "TRANSCRIBE_MODEL": "whisper-1",
        }):
            with mock.patch.object(transcriber_provider, "load_transcriber_config", return_value={
                "type": "fast-whisper",
                "model_size": "base",
                "device": "cpu",
                "compute_type": "int8",
            }):
                with mock.patch.object(transcriber_provider, "FastWhisperTranscriber") as fake_local:
                    transcriber_provider.get_transcriber()

        fake_local.assert_called_once()
        kwargs = fake_local.call_args.kwargs
        self.assertEqual(kwargs["model_size"], "base")
        self.assertEqual(kwargs["device"], "cpu")

    def test_transcriber_can_be_built_from_local_app_config(self):
        with mock.patch.object(transcriber_provider, "FastWhisperTranscriber") as fake_local:
            transcriber_provider.get_transcriber(config={
                "type": "openai-whisper",
                "api_key": "settings-key",
                "base_url": "http://127.0.0.1:8767/v1",
                "model": "whisper-large-v3",
                "model_size": "small",
                "device": "auto",
                "compute_type": "float16",
            })

        kwargs = fake_local.call_args.kwargs
        self.assertEqual(kwargs["model_size"], "small")
        self.assertEqual(kwargs["device"], "auto")
        self.assertEqual(kwargs["compute_type"], "float16")


if __name__ == "__main__":
    unittest.main()
