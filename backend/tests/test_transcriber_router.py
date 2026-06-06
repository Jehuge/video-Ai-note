import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.routers.transcriber import TranscriberConfigRequest, test_transcriber_config


class TranscriberRouterTests(unittest.TestCase):
    def test_test_config_accepts_local_faster_whisper_settings(self):
        response = test_transcriber_config(TranscriberConfigRequest(
            type="fast-whisper",
            model_size="base",
            device="cpu",
            compute_type="int8",
        ))

        self.assertEqual(response["code"], 200)
        self.assertEqual(response["data"]["type"], "fast-whisper")
        self.assertEqual(response["data"]["local_only"], True)

    def test_test_config_rejects_invalid_local_device(self):
        response = test_transcriber_config(TranscriberConfigRequest(
            type="fast-whisper",
            model_size="base",
            device="metal",
            compute_type="int8",
        ))

        self.assertNotEqual(response["code"], 200)


if __name__ == "__main__":
    unittest.main()
