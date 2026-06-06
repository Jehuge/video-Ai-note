import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import transcriber_settings


class TranscriberSettingsTests(unittest.TestCase):
    def test_save_and_load_keeps_local_faster_whisper_only(self):
        with TemporaryDirectory() as tmp:
            with mock.patch.object(transcriber_settings, "get_app_data_dir", return_value=Path(tmp)):
                saved = transcriber_settings.save_transcriber_config({
                    "type": "openai-whisper",
                    "api_key": "sk-should-not-be-used",
                    "base_url": "http://127.0.0.1:8766/v1",
                    "model": "whisper-1",
                    "model_size": "small",
                    "device": "cpu",
                    "compute_type": "int8",
                })
                loaded = transcriber_settings.load_transcriber_config()
                public = transcriber_settings.public_transcriber_config(saved)

        self.assertEqual(saved["type"], "fast-whisper")
        self.assertEqual(loaded["type"], "fast-whisper")
        self.assertEqual(loaded["model_size"], "small")
        self.assertNotIn("api_key", loaded)
        self.assertEqual(public["has_api_key"], False)
        self.assertEqual(public["local_only"], True)

    def test_invalid_device_falls_back_to_default(self):
        normalized = transcriber_settings.normalize_transcriber_config({
            "device": "bad-device",
            "model_size": "base",
            "compute_type": "int8",
        })

        self.assertEqual(normalized["device"], "cpu")


if __name__ == "__main__":
    unittest.main()
