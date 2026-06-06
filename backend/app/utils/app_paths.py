import os
import platform
from pathlib import Path


APP_NAME = "VideoNoteAI"


def get_app_data_dir() -> Path:
    """Return a user-writable app data directory for the current platform."""
    override = os.getenv("VIDEO_NOTE_DATA_DIR")
    if override:
        return Path(override).expanduser()

    system = platform.system().lower()
    home = Path.home()

    if system == "darwin":
        return home / "Library" / "Application Support" / APP_NAME

    if system == "windows":
        base = os.getenv("APPDATA")
        if base:
            return Path(base) / APP_NAME
        return home / "Documents" / "VideoNoteAI_Data"

    return home / ".local" / "share" / APP_NAME


def configure_app_environment() -> Path:
    """Set the filesystem env vars used by the FastAPI app and packaged app."""
    app_data_dir = get_app_data_dir()
    app_data_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "UPLOAD_DIR": app_data_dir / "uploads",
        "NOTE_OUTPUT_DIR": app_data_dir / "note_results",
        "STATIC_DIR": app_data_dir / "static",
        "FFMPEG_BIN_DIR": app_data_dir / "ffmpeg_bin",
        "HF_HOME": app_data_dir / "cache" / "huggingface",
        "PLAYWRIGHT_BROWSERS_PATH": app_data_dir / "ms-playwright",
    }

    for key, path in paths.items():
        os.environ.setdefault(key, str(path))
        Path(os.environ[key]).mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("DATABASE_URL", f"sqlite:///{app_data_dir / 'video_note.db'}")
    os.environ.setdefault("AINOTE_APP_DATA_DIR", str(app_data_dir))

    return app_data_dir
