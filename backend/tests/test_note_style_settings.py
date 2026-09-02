import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import note_style_settings


class NoteStyleSettingsTests(unittest.TestCase):
    def test_custom_style_round_trip_and_snapshot_is_stable(self):
        with TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / "note_style_settings.json"
            with mock.patch.object(note_style_settings, "_settings_path", return_value=settings_path):
                settings = note_style_settings.default_note_style_settings()
                settings["default_style_id"] = "custom-tutorial"
                settings["styles"].append({
                    "id": "custom-tutorial",
                    "name": "教程模式",
                    "prompt": "保留每条命令、参数和排错步骤。",
                    "built_in": False,
                    "enabled": True,
                })
                saved = note_style_settings.save_note_style_settings(settings)
                loaded = note_style_settings.load_note_style_settings()
                snapshot = note_style_settings.apply_note_style_snapshot({}, "custom-tutorial")

                self.assertEqual(loaded, saved)
                self.assertEqual(snapshot["note_style_name"], "教程模式")
                self.assertEqual(snapshot["note_style_prompt"], "保留每条命令、参数和排错步骤。")

                loaded["styles"][-1]["prompt"] = "新的提示词"
                note_style_settings.save_note_style_settings(loaded)
                preserved = note_style_settings.apply_note_style_snapshot(snapshot)
                refreshed = note_style_settings.apply_note_style_snapshot(snapshot, "custom-tutorial")
                self.assertEqual(preserved["note_style_prompt"], "保留每条命令、参数和排错步骤。")
                self.assertEqual(refreshed["note_style_prompt"], "新的提示词")

    def test_invalid_default_and_missing_builtin_are_rejected(self):
        settings = note_style_settings.default_note_style_settings()
        settings["default_style_id"] = "missing"
        with self.assertRaisesRegex(ValueError, "默认模式"):
            note_style_settings.validate_note_style_settings(settings)

        settings = note_style_settings.default_note_style_settings()
        settings["styles"] = [item for item in settings["styles"] if item["id"] != "simple"]
        settings["default_style_id"] = "detailed"
        with self.assertRaisesRegex(ValueError, "内置模式不能删除"):
            note_style_settings.validate_note_style_settings(settings)

    def test_reset_restores_builtins_and_preserves_custom_styles(self):
        with TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / "note_style_settings.json"
            with mock.patch.object(note_style_settings, "_settings_path", return_value=settings_path):
                settings = note_style_settings.default_note_style_settings()
                settings["default_style_id"] = "detailed"
                settings["styles"][0]["prompt"] = "被修改的提示词"
                settings["styles"].append({
                    "id": "custom-review",
                    "name": "复盘模式",
                    "prompt": "提取决策和后续行动。",
                    "built_in": False,
                    "enabled": True,
                })
                note_style_settings.save_note_style_settings(settings)

                reset = note_style_settings.reset_builtin_note_styles()

                simple = next(item for item in reset["styles"] if item["id"] == "simple")
                self.assertNotEqual(simple["prompt"], "被修改的提示词")
                self.assertEqual(reset["default_style_id"], "detailed")
                self.assertTrue(any(item["id"] == "custom-review" for item in reset["styles"]))


if __name__ == "__main__":
    unittest.main()
