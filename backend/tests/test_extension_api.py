import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.routers import extension
from app.services import extension_bridge, web_video


class ExtensionApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.token = "test-bridge-token"

        self.patches = [
            mock.patch.object(extension, "get_app_data_dir", return_value=self.tmp_path),
            mock.patch.object(extension_bridge, "get_app_data_dir", return_value=self.tmp_path),
            mock.patch.object(extension_bridge, "get_bridge_token", return_value=self.token),
            mock.patch.object(extension, "get_bridge_token", return_value=self.token),
        ]
        for patcher in self.patches:
            patcher.start()

        app = FastAPI()
        app.include_router(extension.router)
        self.client = TestClient(
            app,
            client=("127.0.0.1", 50000),
            raise_server_exceptions=False,
        )

    def tearDown(self):
        for patcher in reversed(self.patches):
            patcher.stop()
        self.tmp.cleanup()

    def auth_headers(self):
        return {"X-AInote-Bridge-Token": self.token}

    def test_health_returns_bridge_status(self):
        response = self.client.get("/extension/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 200)
        self.assertEqual(payload["data"]["status"], "ok")
        self.assertEqual(payload["data"]["bridgeToken"], self.token)
        self.assertEqual(payload["data"]["tokenRequired"], True)

    def test_resolve_rejects_missing_or_wrong_token(self):
        body = {"pageUrl": "https://example.test/watch", "detectedStreams": []}

        missing = self.client.post("/extension/videos/resolve", json=body)
        wrong = self.client.post(
            "/extension/videos/resolve",
            json=body,
            headers={"X-AInote-Bridge-Token": "wrong"},
        )

        self.assertEqual(missing.status_code, 401)
        self.assertEqual(wrong.status_code, 401)

    def test_resolve_accepts_detected_hls_stream(self):
        body = {
            "pageUrl": "https://example.test/watch",
            "pageTitle": "Demo Page",
            "detectedStreams": [
                {
                    "url": "https://cdn.example.test/video.m3u8",
                    "mimeType": "application/vnd.apple.mpegurl",
                    "height": 720,
                }
            ],
        }

        with mock.patch.object(
            extension,
            "resolve_web_video",
            return_value={
                "pageUrl": body["pageUrl"],
                "pageTitle": body["pageTitle"],
                "candidates": [
                    {
                        "id": "stream-1",
                        "title": "Demo Page",
                        "sourceUrl": "https://cdn.example.test/video.m3u8",
                        "extractor": "browser-detected",
                        "formats": [{"formatId": "detected", "label": "720p", "protocol": "m3u8"}],
                    }
                ],
                "errors": [],
            },
        ):
            response = self.client.post(
                "/extension/videos/resolve",
                json=body,
                headers=self.auth_headers(),
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["candidates"][0]["formats"][0]["protocol"], "m3u8")

    def test_import_job_and_job_status_round_trip(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            upload_dir = tmp_path / "uploads"
            output_dir = tmp_path / "notes"
            upload_dir.mkdir()
            output_dir.mkdir()
            downloaded = tmp_path / "download.mp4"
            downloaded.write_bytes(b"video")

            with mock.patch.object(web_video, "UPLOAD_DIR", upload_dir), \
                    mock.patch.object(web_video, "NOTE_OUTPUT_DIR", output_dir), \
                    mock.patch.object(web_video, "_download_with_ytdlp", return_value=downloaded), \
                    mock.patch.object(web_video, "load_active_model_config", return_value={}), \
                    mock.patch.object(web_video, "create_task"):
                response = self.client.post(
                    "/extension/videos/import",
                    json={
                        "pageUrl": "https://example.test/watch",
                        "pageTitle": "Demo Video",
                        "candidateUrl": "https://cdn.example.test/video.mp4",
                        "formatId": "detected",
                        "autoRun": False,
                    },
                    headers=self.auth_headers(),
                )

                self.assertEqual(response.status_code, 200)
                job_id = response.json()["data"]["jobId"]

                job = web_video.job_manager.get(job_id)
                if job and job.status not in {"completed", "failed"}:
                    import time
                    deadline = time.time() + 2
                    while time.time() < deadline and job.status not in {"completed", "failed"}:
                        time.sleep(0.02)
                        job = web_video.job_manager.get(job_id)

                status_response = self.client.get(
                    f"/extension/jobs/{job_id}",
                    headers=self.auth_headers(),
                )

        self.assertEqual(status_response.status_code, 200)
        data = status_response.json()["data"]
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["progress"], 100)
        self.assertTrue(data["taskId"])
        self.assertEqual(data["pageUrl"], "https://example.test/watch")

    def test_job_status_syncs_to_canceled_when_app_task_is_deleted(self):
        job = web_video.job_manager.create("https://example.test/watch")
        web_video.job_manager.update(
            job.job_id,
            status="running_note",
            progress=96,
            message="Generating note",
            task_id="deleted-task",
        )

        with mock.patch.object(web_video, "get_task_by_id", return_value=None):
            response = self.client.get(
                f"/extension/jobs/{job.job_id}",
                headers=self.auth_headers(),
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["status"], "canceled")
        self.assertEqual(data["progress"], 100)
        self.assertEqual(data["message"], "Canceled in AInote")


if __name__ == "__main__":
    unittest.main()
