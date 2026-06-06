import secrets
from pathlib import Path

from fastapi import Header, HTTPException, Request

from app.utils.app_paths import get_app_data_dir


def _token_path() -> Path:
    path = get_app_data_dir() / "bridge_token.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_bridge_token() -> str:
    path = _token_path()
    if path.exists():
        token = path.read_text(encoding="utf-8").strip()
        if token:
            return token

    token = secrets.token_urlsafe(32)
    path.write_text(token, encoding="utf-8")
    return token


def _is_loopback(request: Request) -> bool:
    client_host = request.client.host if request.client else ""
    return client_host in {"127.0.0.1", "::1", "localhost"}


async def verify_bridge_token(
    request: Request,
    x_ainote_bridge_token: str = Header(default=""),
) -> None:
    if not _is_loopback(request):
        raise HTTPException(status_code=403, detail="Extension bridge only accepts local requests")

    expected = get_bridge_token()
    if x_ainote_bridge_token != expected:
        raise HTTPException(status_code=401, detail="Invalid AInote bridge token")
