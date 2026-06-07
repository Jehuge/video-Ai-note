import sys
import unittest
from unittest import mock

from app.utils import ffmpeg_helper


class FfmpegHelperTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "Windows-only subprocess flags")
    def test_hidden_subprocess_kwargs_hide_windows_console(self):
        kwargs = ffmpeg_helper.hidden_subprocess_kwargs()

        self.assertEqual(kwargs["creationflags"], ffmpeg_helper.subprocess.CREATE_NO_WINDOW)
        self.assertTrue(kwargs["startupinfo"].dwFlags & ffmpeg_helper.subprocess.STARTF_USESHOWWINDOW)
        self.assertEqual(kwargs["startupinfo"].wShowWindow, 0)

    def test_check_ffmpeg_available_uses_hidden_subprocess_kwargs(self):
        with (
            mock.patch("app.utils.ffmpeg_helper.get_ffmpeg_path", return_value="ffmpeg"),
            mock.patch("app.utils.ffmpeg_helper.hidden_subprocess_kwargs", return_value={"creationflags": 123}),
            mock.patch("app.utils.ffmpeg_helper.subprocess.run") as run,
        ):
            run.return_value.returncode = 0

            self.assertTrue(ffmpeg_helper.check_ffmpeg_available())

        self.assertEqual(run.call_args.kwargs["creationflags"], 123)


if __name__ == "__main__":
    unittest.main()
