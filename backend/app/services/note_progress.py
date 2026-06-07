import json
from pathlib import Path
from typing import Optional


def progress_file(output_dir: Path, task_id: str) -> Path:
    return output_dir / f"{task_id}_progress.json"


def write_note_progress(output_dir: Path, task_id: str, message: str, partial_markdown: str = "") -> None:
    path = progress_file(output_dir, task_id)
    payload = {
        "message": message,
        "partial_markdown": partial_markdown or "",
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_note_progress(output_dir: Path, task_id: str) -> Optional[dict]:
    path = progress_file(output_dir, task_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def clear_note_progress(output_dir: Path, task_id: str) -> None:
    path = progress_file(output_dir, task_id)
    if path.exists():
        path.unlink()
