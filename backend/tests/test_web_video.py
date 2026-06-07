import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import web_video
from app.routers.extension import ImportRequest


class WebVideoServiceTests(unittest.TestCase):
    def test_resolve_falls_back_to_detected_stream_when_ytdlp_fails(self):
        class FakeYoutubeDL:
            def __init__(self, _options):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def extract_info(self, *_args, **_kwargs):
                raise RuntimeError("unsupported site")

        with mock.patch.dict(sys.modules, {"yt_dlp": types.SimpleNamespace(YoutubeDL=FakeYoutubeDL)}):
            result = web_video.resolve_web_video(
                page_url="https://example.test/watch",
                page_title="Demo",
                detected_streams=[
                    {"url": "https://cdn.example.test/video.m3u8", "mimeType": "application/vnd.apple.mpegurl"},
                    {"url": "https://cdn.example.test/video.m3u8", "mimeType": "application/vnd.apple.mpegurl"},
                    {"url": "https://cdn.example.test/asset.css", "mimeType": "text/css"},
                ],
            )

        self.assertEqual(result["errors"], [
            "page: unsupported site",
            "stream https://cdn.example.test/video.m3u8: unsupported site",
        ])
        self.assertEqual(len(result["candidates"]), 1)
        candidate = result["candidates"][0]
        self.assertEqual(candidate["extractor"], "browser-detected")
        self.assertEqual(candidate["formats"][0]["protocol"], "m3u8")

    def test_resolve_sorts_ytdlp_formats_by_quality(self):
        class FakeYoutubeDL:
            def __init__(self, _options):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def extract_info(self, *_args, **_kwargs):
                return {
                    "title": "Resolved",
                    "webpage_url": "https://video.example.test/watch",
                    "extractor": "generic",
                    "formats": [
                        {"format_id": "360", "height": 360, "ext": "mp4", "filesize": 100},
                        {"format_id": "1080", "height": 1080, "ext": "mp4", "filesize": 300},
                        {"format_id": "storyboard", "protocol": "mhtml"},
                    ],
                }

        with mock.patch.dict(sys.modules, {"yt_dlp": types.SimpleNamespace(YoutubeDL=FakeYoutubeDL)}):
            result = web_video.resolve_web_video(page_url="https://video.example.test/watch")

        formats = result["candidates"][0]["formats"]
        self.assertEqual([fmt["formatId"] for fmt in formats], ["1080", "360"])

    def test_resolve_video_only_formats_request_best_audio(self):
        class FakeYoutubeDL:
            def __init__(self, _options):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def extract_info(self, *_args, **_kwargs):
                return {
                    "title": "Resolved",
                    "formats": [
                        {"format_id": "720", "height": 720, "ext": "mp4", "vcodec": "avc1", "acodec": "none"},
                        {"format_id": "audio", "ext": "m4a", "vcodec": "none", "acodec": "mp4a"},
                    ],
                }

        with mock.patch.dict(sys.modules, {"yt_dlp": types.SimpleNamespace(YoutubeDL=FakeYoutubeDL)}):
            result = web_video.resolve_web_video(page_url="https://video.example.test/watch")

        formats = result["candidates"][0]["formats"]
        self.assertEqual(formats[0]["formatId"], "720+ba/best")
        self.assertEqual(formats[0]["rawFormatId"], "720")

    def test_resolve_expands_detected_hls_manifest_formats(self):
        calls = []

        class FakeYoutubeDL:
            def __init__(self, options):
                self.options = options

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def extract_info(self, url, **_kwargs):
                calls.append((url, self.options))
                if url == "https://page.example.test/watch":
                    raise RuntimeError("unsupported page")
                return {
                    "title": "Manifest video",
                    "webpage_url": url,
                    "extractor": "generic",
                    "formats": [
                        {"format_id": "hls-360", "height": 360, "ext": "mp4", "protocol": "m3u8_native"},
                        {"format_id": "hls-1080", "height": 1080, "ext": "mp4", "protocol": "m3u8_native"},
                    ],
                }

        with mock.patch.dict(sys.modules, {"yt_dlp": types.SimpleNamespace(YoutubeDL=FakeYoutubeDL)}):
            result = web_video.resolve_web_video(
                page_url="https://page.example.test/watch",
                page_title="Page",
                detected_streams=[
                    {
                        "url": "https://cdn.example.test/master.m3u8",
                        "mimeType": "application/vnd.apple.mpegurl",
                    }
                ],
            )

        self.assertEqual([fmt["formatId"] for fmt in result["candidates"][0]["formats"]], ["hls-1080", "hls-360"])
        self.assertTrue(result["candidates"][0]["id"].startswith("stream-"))
        self.assertIn(("https://cdn.example.test/master.m3u8", mock.ANY), calls)
        manifest_options = calls[-1][1]
        self.assertEqual(manifest_options["http_headers"]["Referer"], "https://page.example.test/watch")
        self.assertIn("User-Agent", manifest_options["http_headers"])

    def test_resolve_filters_media_fragments_from_detected_streams(self):
        class FakeYoutubeDL:
            def __init__(self, _options):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def extract_info(self, *_args, **_kwargs):
                raise RuntimeError("unsupported site")

        with mock.patch.dict(sys.modules, {"yt_dlp": types.SimpleNamespace(YoutubeDL=FakeYoutubeDL)}):
            result = web_video.resolve_web_video(
                page_url="https://example.test/watch",
                detected_streams=[
                    {"url": "https://cdn.example.test/chunk-1.m4s", "mimeType": "video/iso.segment"},
                    {"url": "https://cdn.example.test/seg-1.ts", "label": "HLS media segment"},
                    {"url": "https://cdn.example.test/video.mp4", "mimeType": "video/mp4"},
                ],
            )

        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(result["candidates"][0]["sourceUrl"], "https://cdn.example.test/video.mp4")

    def test_resolve_preserves_extensionless_douyin_media_urls(self):
        class FakeYoutubeDL:
            def __init__(self, _options):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def extract_info(self, *_args, **_kwargs):
                raise RuntimeError("unsupported site")

        with mock.patch.dict(sys.modules, {"yt_dlp": types.SimpleNamespace(YoutubeDL=FakeYoutubeDL)}):
            result = web_video.resolve_web_video(
                page_url="https://www.douyin.com/video/123456",
                page_title="Douyin",
                detected_streams=[
                    {"url": "https://www.douyin.com/aweme/v1/play/?video_id=abc", "label": "Media stream"},
                    {"url": "https://v3-dy-o.douyinvod.com/tos-cn-ve-15/abc/video", "label": "Media stream"},
                    {"url": "https://static.example.test/app.js", "label": "Script"},
                ],
            )

        self.assertEqual(
            [candidate["sourceUrl"] for candidate in result["candidates"]],
            [
                "https://www.douyin.com/aweme/v1/play/?video_id=abc",
                "https://v3-dy-o.douyinvod.com/tos-cn-ve-15/abc/video",
            ],
        )

    def test_choose_download_url_prefers_candidate_url(self):
        url = web_video._choose_download_url({
            "pageUrl": "https://example.test/page",
            "candidateUrl": "https://cdn.example.test/video.m3u8",
        })

        self.assertEqual(url, "https://cdn.example.test/video.m3u8")

    def test_ytdlp_options_set_network_timeouts(self):
        options = web_video._yt_dlp_options()

        self.assertEqual(options["socket_timeout"], 15)
        self.assertEqual(options["retries"], 3)
        self.assertEqual(options["fragment_retries"], 3)
        self.assertIn("User-Agent", options["http_headers"])

    def test_ytdlp_options_use_referer_and_cookie(self):
        options = web_video._yt_dlp_options(
            headers={"Accept-Language": "zh-CN", "Cookie": "ignored=1"},
            cookie="SESSDATA=demo",
            referer="https://example.test/watch",
        )

        self.assertEqual(options["http_headers"]["Referer"], "https://example.test/watch")
        self.assertEqual(options["http_headers"]["Cookie"], "SESSDATA=demo")
        self.assertEqual(options["http_headers"]["Accept-Language"], "zh-CN")
        self.assertNotEqual(options["http_headers"]["Cookie"], "ignored=1")
        self.assertNotIn("cookiefile", options)

    def test_ytdlp_options_do_not_force_bilibili_legacy_flv(self):
        options = web_video._yt_dlp_options()

        bilibili_args = (options.get("extractor_args") or {}).get("bilibili") or {}
        self.assertNotIn("prefer_multi_flv", bilibili_args)

    def test_ytdlp_options_allow_optional_browser_impersonation(self):
        with mock.patch.dict("os.environ", {"YTDLP_IMPERSONATE": "chrome"}, clear=False):
            options = web_video._yt_dlp_options()

        self.assertEqual(options["impersonate"], "chrome")

    def test_temporary_cookiefile_writes_browser_cookie_for_supported_sites(self):
        with web_video._temporary_cookiefile("SESSDATA=demo; msToken=abc") as cookie_file:
            path = Path(cookie_file)
            content = path.read_text(encoding="utf-8")

            self.assertTrue(path.exists())
            self.assertIn(".bilibili.com\tTRUE\t/\tFALSE\t1893456000\tSESSDATA\tdemo", content)
            self.assertIn(".passport.bilibili.com\tTRUE\t/\tFALSE\t1893456000\tSESSDATA\tdemo", content)
            self.assertIn(".douyin.com\tTRUE\t/\tFALSE\t1893456000\tmsToken\tabc", content)
            self.assertIn(".v.douyin.com\tTRUE\t/\tFALSE\t1893456000\tmsToken\tabc", content)
            self.assertIn(".snssdk.com\tTRUE\t/\tFALSE\t1893456000\tmsToken\tabc", content)

        self.assertFalse(path.exists())

    def test_temporary_cookiefile_preserves_structured_cookie_metadata(self):
        with web_video._temporary_cookiefile(
            "",
            cookie_details=[
                {
                    "name": "SESSDATA",
                    "value": "demo",
                    "domain": ".bilibili.com",
                    "path": "/",
                    "secure": True,
                    "expirationDate": 1924992000,
                },
                {
                    "name": "s_v_web_id",
                    "value": "fresh",
                    "domain": ".douyin.com",
                    "path": "/",
                    "secure": True,
                    "expirationDate": 1924992000,
                },
            ],
        ) as cookie_file:
            path = Path(cookie_file)
            content = path.read_text(encoding="utf-8")

            self.assertIn(".bilibili.com\tTRUE\t/\tTRUE\t1924992000\tSESSDATA\tdemo", content)
            self.assertIn(".douyin.com\tTRUE\t/\tTRUE\t1924992000\ts_v_web_id\tfresh", content)

        self.assertFalse(path.exists())

    def test_resolve_passes_cookiefile_to_ytdlp_and_removes_it(self):
        seen = {}

        class FakeYoutubeDL:
            def __init__(self, options):
                seen["cookiefile"] = options.get("cookiefile")
                seen["cookiefile_exists"] = Path(seen["cookiefile"]).exists()
                seen["cookiefile_content"] = Path(seen["cookiefile"]).read_text(encoding="utf-8")

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def extract_info(self, url, **_kwargs):
                seen["url"] = url
                return {
                    "title": "Resolved",
                    "webpage_url": url,
                    "formats": [{"format_id": "1080", "height": 1080, "ext": "mp4"}],
                }

        with mock.patch.dict(sys.modules, {"yt_dlp": types.SimpleNamespace(YoutubeDL=FakeYoutubeDL)}):
            result = web_video.resolve_web_video(
                page_url="https://m.douyin.com/video/123456",
                cookie="SESSDATA=demo; msToken=abc",
                cookie_details=[{
                    "name": "s_v_web_id",
                    "value": "fresh",
                    "domain": ".douyin.com",
                    "path": "/",
                    "secure": True,
                    "expirationDate": 1924992000,
                }],
            )

        self.assertEqual(seen["url"], "https://www.douyin.com/video/123456")
        self.assertTrue(seen["cookiefile_exists"])
        self.assertIn(".douyin.com\tTRUE\t/\tTRUE\t1924992000\ts_v_web_id\tfresh", seen["cookiefile_content"])
        self.assertFalse(Path(seen["cookiefile"]).exists())
        self.assertEqual(result["candidates"][0]["formats"][0]["formatId"], "1080")

    def test_resolve_returns_non_sensitive_diagnostics(self):
        class FakeYoutubeDL:
            def __init__(self, _options):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def extract_info(self, url, **_kwargs):
                return {
                    "title": "Resolved",
                    "webpage_url": url,
                    "extractor": "BiliBili",
                    "formats": [
                        {"format_id": "64", "height": 480, "ext": "mp4"},
                        {"format_id": "80", "height": 1080, "ext": "mp4"},
                    ],
                }

        with mock.patch.dict(sys.modules, {"yt_dlp": types.SimpleNamespace(YoutubeDL=FakeYoutubeDL)}):
            result = web_video.resolve_web_video(
                page_url="https://www.bilibili.com/video/BV1demo/",
                cookie="SESSDATA=secret; bili_jct=csrf; s_v_web_id=fresh",
                detected_streams=[{"url": "https://cdn.example.test/video.m3u8"}],
            )

        diagnostics = result["diagnostics"]
        self.assertEqual(diagnostics["candidateCount"], 2)
        self.assertEqual(diagnostics["formatCount"], 4)
        self.assertEqual(diagnostics["maxHeight"], 1080)
        self.assertEqual(diagnostics["extractors"][0], "BiliBili")
        self.assertTrue(diagnostics["receivedCookies"]["bilibiliSessdata"])
        self.assertTrue(diagnostics["receivedCookies"]["bilibiliCsrf"])
        self.assertTrue(diagnostics["receivedCookies"]["douyinFresh"])
        self.assertNotIn("secret", str(diagnostics))

    def test_download_passes_cookiefile_to_ytdlp_and_removes_it(self):
        with TemporaryDirectory() as tmp:
            upload_dir = Path(tmp)
            seen = {}

            class FakeYoutubeDL:
                def __init__(self, options):
                    seen["cookiefile"] = options.get("cookiefile")
                    seen["format"] = options.get("format")
                    seen["cookiefile_exists"] = Path(seen["cookiefile"]).exists()
                    seen["cookiefile_content"] = Path(seen["cookiefile"]).read_text(encoding="utf-8")

                def __enter__(self):
                    return self

                def __exit__(self, *_args):
                    return False

                def download(self, urls):
                    seen["urls"] = urls
                    (upload_dir / "web_job-1.mp4").write_bytes(b"video")

            with mock.patch.object(web_video, "UPLOAD_DIR", upload_dir), \
                    mock.patch.dict(sys.modules, {"yt_dlp": types.SimpleNamespace(YoutubeDL=FakeYoutubeDL)}):
                path = web_video._download_with_ytdlp("job-1", {
                    "pageUrl": "https://www.bilibili.com/video/BV1demo/",
                    "candidateUrl": "https://www.bilibili.com/video/BV1demo/",
                    "formatId": "116+ba/best",
                    "cookies": "SESSDATA=demo",
                    "cookieDetails": [{
                        "name": "SESSDATA",
                        "value": "demo",
                        "domain": ".bilibili.com",
                        "path": "/",
                        "secure": True,
                        "expirationDate": 1924992000,
                    }],
                })

            self.assertEqual(path.name, "web_job-1.mp4")
            self.assertEqual(seen["urls"], ["https://www.bilibili.com/video/BV1demo/"])
            self.assertEqual(seen["format"], "116+ba/best")
            self.assertTrue(seen["cookiefile_exists"])
            self.assertIn(".bilibili.com\tTRUE\t/\tTRUE\t1924992000\tSESSDATA\tdemo", seen["cookiefile_content"])
            self.assertFalse(Path(seen["cookiefile"]).exists())

    def test_normalize_douyin_share_url(self):
        self.assertEqual(
            web_video._normalize_page_url("https://www.douyin.com/share/video/123456/?foo=bar"),
            "https://www.douyin.com/video/123456",
        )

    def test_import_request_preserves_candidate_url(self):
        payload = ImportRequest(
            pageUrl="https://example.test/watch",
            candidateId="page-url",
            candidateUrl="https://cdn.example.test/video.m3u8",
            formatId="detected",
        )

        self.assertEqual(payload.model_dump()["candidateUrl"], "https://cdn.example.test/video.m3u8")

    def test_run_import_job_creates_task_and_skips_note_when_auto_run_false(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            upload_dir = tmp_path / "uploads"
            output_dir = tmp_path / "notes"
            upload_dir.mkdir()
            output_dir.mkdir()
            downloaded = tmp_path / "download.mp4"
            downloaded.write_bytes(b"video")

            created = {}

            def fake_create_task(**kwargs):
                created.update(kwargs)

            class FakeNoteGenerator:
                def __init__(self, *_args, **_kwargs):
                    raise AssertionError("Note generation should not run when autoRun is false")

            with mock.patch.object(web_video, "UPLOAD_DIR", upload_dir), \
                    mock.patch.object(web_video, "NOTE_OUTPUT_DIR", output_dir), \
                    mock.patch.object(web_video, "_download_with_ytdlp", return_value=downloaded), \
                    mock.patch.object(web_video, "load_active_model_config", return_value={"model": "demo", "note_style": "simple"}), \
                    mock.patch.object(web_video, "create_task", side_effect=fake_create_task), \
                    mock.patch.object(web_video, "NoteGenerator", FakeNoteGenerator):
                job = web_video.job_manager.create("https://example.test/watch")
                web_video._run_import_job(job.job_id, {
                    "pageUrl": "https://example.test/watch",
                    "pageTitle": "Unsafe:/Title",
                    "autoRun": False,
                })

            updated = web_video.job_manager.get(job.job_id)
            self.assertEqual(updated.status, "completed")
            self.assertTrue(updated.task_id)
            self.assertEqual(created["source"], "web")
            self.assertEqual(created["source_url"], "https://example.test/watch")
            self.assertTrue((output_dir / f"{updated.task_id}_model_config.json").exists())
            self.assertTrue(list(upload_dir.glob(f"{updated.task_id}.mp4")))

    def test_run_import_job_uses_plugin_note_style(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            upload_dir = tmp_path / "uploads"
            output_dir = tmp_path / "notes"
            upload_dir.mkdir()
            output_dir.mkdir()
            downloaded = tmp_path / "download.mp4"
            downloaded.write_bytes(b"video")

            generated = {}

            class FakeNoteGenerator:
                def __init__(self, model_config=None):
                    generated["model_config"] = model_config

                def generate(self, **kwargs):
                    generated.update(kwargs)

            with mock.patch.object(web_video, "UPLOAD_DIR", upload_dir), \
                    mock.patch.object(web_video, "NOTE_OUTPUT_DIR", output_dir), \
                    mock.patch.object(web_video, "_download_with_ytdlp", return_value=downloaded), \
                    mock.patch.object(web_video, "load_active_model_config", return_value={"model": "demo", "note_style": "simple"}), \
                    mock.patch.object(web_video, "create_task"), \
                    mock.patch.object(web_video, "NoteGenerator", FakeNoteGenerator):
                job = web_video.job_manager.create("https://example.test/watch")
                web_video._run_import_job(job.job_id, {
                    "pageUrl": "https://example.test/watch",
                    "pageTitle": "Style Demo",
                    "noteStyle": "creative",
                    "autoRun": True,
                })

            updated = web_video.job_manager.get(job.job_id)
            config_file = output_dir / f"{updated.task_id}_model_config.json"
            self.assertEqual(generated["note_style"], "creative")
            self.assertEqual(generated["model_config"]["note_style"], "creative")
            self.assertIn('"note_style": "creative"', config_file.read_text(encoding="utf-8"))

    def test_run_import_job_marks_failed_on_download_error(self):
        with mock.patch.object(web_video, "_download_with_ytdlp", side_effect=RuntimeError("boom")):
            job = web_video.job_manager.create("https://example.test/watch")
            web_video._run_import_job(job.job_id, {"pageUrl": "https://example.test/watch"})

        updated = web_video.job_manager.get(job.job_id)
        self.assertEqual(updated.status, "failed")
        self.assertEqual(updated.error, "boom")

    def test_canceled_job_is_not_overwritten_by_late_updates(self):
        job = web_video.job_manager.create("https://example.test/watch")

        web_video.job_manager.update(job.job_id, status="canceled", progress=100, message="Canceled in AInote")
        web_video.job_manager.update(job.job_id, status="completed", progress=100, message="Done")

        updated = web_video.job_manager.get(job.job_id)
        self.assertEqual(updated.status, "canceled")
        self.assertEqual(updated.message, "Canceled in AInote")

    def test_job_status_uses_note_progress_message_while_summarizing(self):
        job = web_video.job_manager.create("https://example.test/watch")
        web_video.job_manager.update(
            job.job_id,
            status="running_note",
            progress=96,
            message="Generating note",
            task_id="task-progress",
        )

        task = mock.Mock()
        task.status = "summarizing"

        with TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            (output_dir / "task-progress_progress.json").write_text(
                '{"message":"正在生成第 2/4 段摘要","partial_markdown":"## partial"}',
                encoding="utf-8",
            )
            with mock.patch.object(web_video, "NOTE_OUTPUT_DIR", output_dir), \
                    mock.patch.object(web_video, "get_task_by_id", return_value=task):
                updated = web_video.sync_job_with_task(job.job_id)

        self.assertEqual(updated.status, "running_note")
        self.assertEqual(updated.message, "正在生成第 2/4 段摘要")


if __name__ == "__main__":
    unittest.main()
