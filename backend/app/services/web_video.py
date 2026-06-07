import os
import re
import shutil
import subprocess
import tempfile
import threading
import uuid
import hashlib
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from app.db.video_task_dao import create_task, get_task_by_id, update_task_status
from app.services.model_settings import load_active_model_config
from app.services.note import NoteGenerator
from app.services.note_progress import read_note_progress
from app.utils.ffmpeg_helper import get_ffmpeg_path
from app.utils.logger import get_logger

logger = get_logger(__name__)

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))
NOTE_OUTPUT_DIR = Path(os.getenv("NOTE_OUTPUT_DIR", "note_results"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
NOTE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MEDIA_EXTENSIONS = {".mp4", ".m4v", ".mov", ".webm", ".mkv", ".flv", ".avi", ".mp3", ".m4a", ".wav", ".ts", ".aac"}
STREAM_EXTENSIONS = {".m3u8", ".mpd"}
FRAGMENT_EXTENSIONS = {".m4s", ".ts"}
DEFAULT_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
NOTE_STYLES = {"simple", "detailed", "academic", "creative"}
TERMINAL_JOB_STATUSES = {"completed", "failed", "canceled", "cancelled"}
TASK_STATUS_TO_JOB = {
    "pending": ("imported", 92, "Waiting in AInote"),
    "processing": ("running_note", 96, "Extracting audio"),
    "transcribing": ("running_note", 97, "Transcribing audio"),
    "transcribed": ("running_note", 98, "Waiting to summarize"),
    "summarizing": ("running_note", 99, "Generating note"),
}

YTDLP_DIAGNOSTIC_MARKERS = (
    "format(s)",
    "missing",
    "premium",
    "member",
    "login",
    "logged in",
    "fresh cookies",
    "requested format is not available",
    "only preview format is available",
    "unable to extract",
    "http error 403",
    "http error 412",
)
BILIBILI_BVID_PATTERN = re.compile(r"(BV[0-9A-Za-z]+)", re.IGNORECASE)
BILIBILI_MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52,
]


@dataclass
class WebVideoJob:
    job_id: str
    status: str = "queued"
    progress: int = 0
    message: str = ""
    error: Optional[str] = None
    task_id: Optional[str] = None
    filename: Optional[str] = None
    page_url: Optional[str] = None


@dataclass
class WebVideoJobManager:
    jobs: Dict[str, WebVideoJob] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def create(self, page_url: str) -> WebVideoJob:
        job = WebVideoJob(job_id=str(uuid.uuid4()), page_url=page_url)
        with self.lock:
            self.jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> Optional[WebVideoJob]:
        with self.lock:
            return self.jobs.get(job_id)

    def update(self, job_id: str, **updates) -> Optional[WebVideoJob]:
        with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                return None
            if job.status in {"canceled", "cancelled"} and updates.get("status") not in {None, job.status}:
                return job
            for key, value in updates.items():
                setattr(job, key, value)
            return job

    def find_by_task_id(self, task_id: str) -> List[WebVideoJob]:
        with self.lock:
            return [job for job in self.jobs.values() if job.task_id == task_id]


job_manager = WebVideoJobManager()


def _sanitize_ytdlp_message(message: Any) -> str:
    text = re.sub(r"\s+", " ", str(message or "")).strip()
    if not text:
        return ""
    text = re.sub(r"(?i)(SESSDATA|bili_jct|DedeUserID|sid_tt|sessionid|msToken|ttwid)=([^;\s&]+)", r"\1=<redacted>", text)
    text = re.sub(r"https?://[^\s]+", lambda match: match.group(0).split("?", 1)[0][:120], text)
    return text[:240]


def _is_useful_ytdlp_diagnostic(message: str) -> bool:
    lower = message.lower()
    return any(marker in lower for marker in YTDLP_DIAGNOSTIC_MARKERS)


def _append_unique_diagnostic(messages: List[str], message: Any, limit: int = 6) -> None:
    sanitized = _sanitize_ytdlp_message(message)
    if not sanitized or not _is_useful_ytdlp_diagnostic(sanitized):
        return
    if sanitized not in messages and len(messages) < limit:
        messages.append(sanitized)


class YtDlpDiagnosticLogger:
    def __init__(self, messages: List[str]):
        self.messages = messages

    def debug(self, message):
        _append_unique_diagnostic(self.messages, message)

    def warning(self, message):
        _append_unique_diagnostic(self.messages, message)

    def error(self, message):
        _append_unique_diagnostic(self.messages, message)


def _record_ytdlp_cookie_diagnostics(ydl: Any, diagnostics: Optional[Dict[str, Any]]) -> None:
    if diagnostics is None:
        return
    cookiejar = getattr(ydl, "cookiejar", None)
    getter = getattr(cookiejar, "get_cookies_for_url", None)
    if not getter:
        return

    def names_for(url: str) -> set:
        try:
            return {getattr(cookie, "name", "") for cookie in getter(url)}
        except Exception:
            return set()

    bilibili_names = names_for("https://api.bilibili.com/x/web-interface/nav")
    douyin_names = names_for("https://www.douyin.com/")
    diagnostics["bilibiliSessdata"] = bool("SESSDATA" in bilibili_names)
    diagnostics["douyinFresh"] = bool({"s_v_web_id", "msToken", "ttwid"} & douyin_names)


def cancel_jobs_for_task(task_id: str, message: str = "Canceled in AInote") -> List[WebVideoJob]:
    canceled = []
    for job in job_manager.find_by_task_id(task_id):
        if job.status not in TERMINAL_JOB_STATUSES or job.status in {"running_note", "imported"}:
            updated = job_manager.update(
                job.job_id,
                status="canceled",
                progress=100,
                message=message,
                error=None,
            )
            if updated:
                canceled.append(updated)
    return canceled


def sync_job_with_task(job_id: str) -> Optional[WebVideoJob]:
    job = job_manager.get(job_id)
    if not job or not job.task_id:
        return job

    if job.status in TERMINAL_JOB_STATUSES:
        return job

    task = get_task_by_id(job.task_id)
    if not task:
        return job_manager.update(
            job_id,
            status="canceled",
            progress=100,
            message="Canceled in AInote",
            error=None,
        )

    task_status = getattr(task, "status", "")
    if task_status == "failed":
        return job_manager.update(
            job_id,
            status="failed",
            progress=100,
            message="AInote task failed",
            error=getattr(task, "error_message", None) or "AInote task failed",
        )
    if task_status == "completed":
        return job_manager.update(job_id, status="completed", progress=100, message="Done", error=None)

    mapped = TASK_STATUS_TO_JOB.get(task_status)
    if mapped:
        status, progress, message = mapped
        if task_status == "summarizing":
            note_progress = read_note_progress(NOTE_OUTPUT_DIR, job.task_id)
            if note_progress and note_progress.get("message"):
                message = note_progress["message"]
        return job_manager.update(
            job_id,
            status=status,
            progress=max(job.progress, progress),
            message=message,
            error=None,
        )

    return job


def _safe_label(value: str, fallback: str = "web-video") -> str:
    value = value or fallback
    value = re.sub(r"[\\/:*?\"<>|]+", "_", value)
    value = re.sub(r"\s+", " ", value).strip()
    return (value[:80] or fallback).strip(". ")


def _stream_id(url: str) -> str:
    return "stream-" + uuid.uuid5(uuid.NAMESPACE_URL, url).hex[:16]


def _format_filesize(value: Optional[int]) -> Optional[int]:
    try:
        return int(value) if value else None
    except Exception:
        return None


def _stream_label(stream: Dict[str, Any], index: int) -> str:
    label = stream.get("label") or stream.get("quality")
    height = stream.get("height")
    if label:
        return str(label)
    if height:
        return f"{height}p"
    parsed = urlparse(stream.get("url", ""))
    suffix = Path(parsed.path).suffix.lower().lstrip(".")
    return suffix.upper() if suffix else f"Stream {index + 1}"


def _stream_suffix(url: str) -> str:
    parsed = urlparse(url)
    return Path(parsed.path).suffix.lower()


def _stream_mime(stream: Dict[str, Any]) -> str:
    return (stream.get("mimeType") or stream.get("mime") or stream.get("type") or "").lower()


def _is_manifest_stream(stream: Dict[str, Any]) -> bool:
    url = (stream.get("url") or "").strip()
    suffix = _stream_suffix(url)
    mime = _stream_mime(stream)
    return (
        suffix in STREAM_EXTENSIONS
        or "mpegurl" in mime
        or "application/x-mpegurl" in mime
        or "dash" in mime
        or "mpd" in mime
    )


def _is_fragment_stream(stream: Dict[str, Any]) -> bool:
    url = (stream.get("url") or "").strip()
    suffix = _stream_suffix(url)
    label = str(stream.get("label") or "").lower()
    return bool(
        stream.get("isFragment")
        or stream.get("segment")
        or (suffix == ".m4s")
        or (suffix == ".ts" and "segment" in label)
    )


def _stream_protocol(stream: Dict[str, Any]) -> str:
    suffix = _stream_suffix(stream.get("url") or "")
    if suffix == ".m3u8" or "mpegurl" in _stream_mime(stream):
        return "m3u8"
    if suffix == ".mpd" or "dash" in _stream_mime(stream) or "mpd" in _stream_mime(stream):
        return "dash"
    return "direct"


def _is_probable_media_url(url: str, mime: str = "") -> bool:
    if not url:
        return False
    suffix = _stream_suffix(url)
    lower_url = url.lower()
    lower_mime = (mime or "").lower()
    if suffix in MEDIA_EXTENSIONS or suffix in STREAM_EXTENSIONS:
        return True
    if any(token in lower_url for token in (
        "/aweme/v1/play",
        "/aweme/v1/playwm",
        "/aweme/v1/web/aweme/detail",
        "/video/tos/",
        "/tos-",
        "douyinvod.com",
        "douyinpic.com",
    )):
        return True
    return any(token in lower_mime for token in ("video", "audio", "mpegurl", "dash"))


def _normalize_detected_streams(streams: List[Dict[str, Any]], page_title: str = "") -> List[Dict[str, Any]]:
    normalized = []
    seen = set()
    for index, stream in enumerate(streams or []):
        url = (stream.get("url") or "").strip()
        if not url or url in seen:
            continue
        if url.startswith("blob:"):
            continue
        if _is_fragment_stream(stream) and not stream.get("isBilibiliPlayInfo") and not stream.get("isDouyinPageData"):
            continue
        seen.add(url)

        parsed = urlparse(url)
        suffix = _stream_suffix(url)
        mime = _stream_mime(stream)
        if not stream.get("isBilibiliPlayInfo") and not stream.get("isDouyinPageData") and not _is_probable_media_url(url, mime):
            continue

        ext = suffix.lstrip(".") if suffix else (stream.get("ext") or ("m3u8" if _is_manifest_stream(stream) else "mp4"))
        protocol = _stream_protocol(stream)

        label = _stream_label(stream, index)
        if stream.get("isBilibiliPlayInfo"):
            format_id = "bilibili-playinfo"
            extractor = "bilibili-playinfo"
        elif stream.get("isDouyinPageData"):
            format_id = "douyin-page-data"
            extractor = "douyin-page-data"
        else:
            format_id = "detected"
            extractor = "browser-detected"
        normalized.append({
            "id": _stream_id(url),
            "title": page_title or parsed.netloc or "Detected video",
            "sourceUrl": url,
            "extractor": extractor,
            "companionAudioUrl": stream.get("companionAudioUrl") or "",
            "formats": [{
                "formatId": format_id,
                "label": label,
                "height": stream.get("height"),
                "ext": ext,
                "filesize": _format_filesize(stream.get("filesize") or stream.get("size")),
                "protocol": protocol,
                "bandwidth": stream.get("bandwidth"),
                "codecs": stream.get("codecs"),
            }],
        })
    return normalized


def _format_label(fmt: Dict[str, Any]) -> str:
    height = fmt.get("height")
    ext = fmt.get("ext") or "media"
    note = fmt.get("format_note") or fmt.get("resolution") or fmt.get("format")
    if height:
        return f"{height}p {ext}"
    if note:
        return str(note)[:80]
    return str(fmt.get("format_id") or "best")


def _download_format_id(fmt: Dict[str, Any]) -> str:
    format_id = str(fmt.get("format_id") or "best")
    if fmt.get("vcodec") not in {None, "none"} and fmt.get("acodec") == "none":
        return f"{format_id}+ba/best"
    return format_id


def _normalize_page_url(url: str) -> str:
    parsed = urlparse(url or "")
    if not parsed.scheme or not parsed.netloc:
        return url
    host = parsed.netloc.lower()
    if host in {"v.douyin.com", "www.iesdouyin.com"}:
        return url
    if host.endswith("douyin.com") and parsed.path.startswith("/share/video/"):
        video_id = parsed.path.rstrip("/").split("/")[-1]
        if video_id:
            return f"https://www.douyin.com/video/{video_id}"
    if host in {"m.douyin.com", "www.douyin.com"} and parsed.path.startswith("/video/"):
        return urlunparse(("https", "www.douyin.com", parsed.path, "", parsed.query, ""))
    return url


def _safe_cookie_value(value: Any) -> str:
    return str(value or "").replace("\r", "").replace("\n", "")


def _cookie_expires_at(cookie: Dict[str, Any], default: str = "1893456000") -> str:
    value = cookie.get("expirationDate") or cookie.get("expires") or cookie.get("expiry")
    try:
        if value:
            return str(int(float(value)))
    except Exception:
        pass
    return default


def _write_cookie_file(cookie: str = "", cookie_details: Optional[List[Dict[str, Any]]] = None) -> Optional[str]:
    lines = ["# Netscape HTTP Cookie File"]
    seen = set()

    def add_line(domain: str, include_subdomains: bool, path: str, secure: bool, expires_at: str, name: str, value: str):
        domain = _safe_cookie_value(domain).strip()
        name = _safe_cookie_value(name).strip()
        value = _safe_cookie_value(value)
        path = _safe_cookie_value(path or "/") or "/"
        if not domain or not name:
            return
        key = (domain, path, name, value)
        if key in seen:
            return
        seen.add(key)
        lines.append(
            f"{domain}\t{'TRUE' if include_subdomains else 'FALSE'}\t{path}\t"
            f"{'TRUE' if secure else 'FALSE'}\t{expires_at}\t{name}\t{value}"
        )

    for item in cookie_details or []:
        domain = str(item.get("domain") or "").strip()
        if not domain:
            continue
        add_line(
            domain=domain,
            include_subdomains=domain.startswith("."),
            path=item.get("path") or "/",
            secure=bool(item.get("secure")),
            expires_at=_cookie_expires_at(item),
            name=item.get("name") or "",
            value=item.get("value") or "",
        )

    if cookie:
        domains = [
            ".bilibili.com",
            ".api.bilibili.com",
            ".passport.bilibili.com",
            ".t.bilibili.com",
            ".douyin.com",
            ".v.douyin.com",
            ".iesdouyin.com",
            ".snssdk.com",
        ]
        expires_at = "1893456000"  # 2030-01-01
        for item in cookie.split(";"):
            if "=" not in item:
                continue
            name, value = item.strip().split("=", 1)
            for domain in domains:
                add_line(domain, True, "/", False, expires_at, name, value)

    if len(lines) == 1:
        return None

    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".cookies.txt")
    with handle:
        handle.write("\n".join(lines))
        handle.write("\n")
    return handle.name


@contextmanager
def _temporary_cookiefile(cookie: str = "", cookie_details: Optional[List[Dict[str, Any]]] = None):
    cookie_file = _write_cookie_file(cookie or "", cookie_details=cookie_details)
    try:
        yield cookie_file
    finally:
        if cookie_file:
            try:
                Path(cookie_file).unlink(missing_ok=True)
            except Exception:
                pass


def _yt_dlp_options(headers: Optional[Dict[str, str]] = None, cookie: Optional[str] = None,
                    referer: Optional[str] = None, diagnostic_messages: Optional[List[str]] = None) -> Dict[str, Any]:
    http_headers = dict(DEFAULT_BROWSER_HEADERS)
    for key, value in (headers or {}).items():
        key_lower = key.lower()
        if key_lower in {"authorization", "cookie", "set-cookie"}:
            continue
        if value:
            http_headers[key] = value
    if referer and not any(key.lower() == "referer" for key in http_headers):
        http_headers["Referer"] = referer
    if cookie:
        http_headers["Cookie"] = cookie

    options: Dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        "ignore_no_formats_error": True,
        "socket_timeout": 15,
        "fragment_retries": 3,
        "retries": 3,
        "http_headers": http_headers,
    }
    if diagnostic_messages is not None:
        options["logger"] = YtDlpDiagnosticLogger(diagnostic_messages)
    impersonate_target = os.getenv("YTDLP_IMPERSONATE", "").strip()
    if impersonate_target:
        options["impersonate"] = impersonate_target

    try:
        ffmpeg_path = Path(get_ffmpeg_path())
        options["ffmpeg_location"] = str(ffmpeg_path.parent)
    except Exception:
        pass

    return options


def _candidate_key(candidate: Dict[str, Any]) -> str:
    formats = ",".join(sorted(str(fmt.get("formatId") or "") for fmt in candidate.get("formats") or []))
    return f"{candidate.get('extractor') or ''}|{candidate.get('sourceUrl') or ''}|{formats}"


def _dedupe_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped = []
    seen = set()
    for candidate in candidates:
        key = _candidate_key(candidate)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _candidate_max_height(candidate: Dict[str, Any]) -> int:
    heights = []
    for fmt in candidate.get("formats") or []:
        try:
            heights.append(int(fmt.get("height") or 0))
        except (TypeError, ValueError):
            heights.append(0)
    return max(heights or [0])


def _candidate_best_bandwidth(candidate: Dict[str, Any]) -> int:
    bandwidths = []
    for fmt in candidate.get("formats") or []:
        try:
            bandwidths.append(int(fmt.get("bandwidth") or 0))
        except (TypeError, ValueError):
            bandwidths.append(0)
    return max(bandwidths or [0])


def _candidate_priority(candidate: Dict[str, Any]) -> int:
    extractor = str(candidate.get("extractor") or "").lower()
    if extractor == "bilibili-api":
        return 40
    if "bilibili" in extractor or "playinfo" in extractor:
        return 30
    if "douyin" in extractor or "tiktok" in extractor:
        return 25
    if extractor in {"page-url", "selected-area"}:
        return 5
    return 10


def _sort_candidates_by_quality(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        candidates,
        key=lambda candidate: (
            _candidate_max_height(candidate),
            _candidate_priority(candidate),
            _candidate_best_bandwidth(candidate),
        ),
        reverse=True,
    )


def _bilibili_bvid_from_url(url: str) -> Optional[str]:
    try:
        parsed = urlparse(url or "")
    except Exception:
        return None
    if not parsed.netloc.lower().endswith("bilibili.com"):
        return None
    match = BILIBILI_BVID_PATTERN.search(parsed.path) or BILIBILI_BVID_PATTERN.search(parsed.query)
    return match.group(1) if match else None


def _bilibili_page_number_from_url(url: str) -> int:
    try:
        parsed = urlparse(url or "")
        values = parse_qs(parsed.query).get("p") or []
        page = int(values[0]) if values else 1
    except (TypeError, ValueError):
        page = 1
    return max(1, page)


def _bilibili_select_page(view: Dict[str, Any], page_number: int) -> Dict[str, Any]:
    pages = [page for page in view.get("pages") or [] if isinstance(page, dict)]
    if not pages:
        return {}
    for page in pages:
        try:
            if int(page.get("page") or 0) == page_number:
                return page
        except (TypeError, ValueError):
            continue
    index = page_number - 1
    if 0 <= index < len(pages):
        return pages[index]
    return pages[0]


def _bilibili_headers(headers: Optional[Dict[str, str]] = None, referer: str = "") -> Dict[str, str]:
    result = dict(DEFAULT_BROWSER_HEADERS)
    result["Accept"] = "application/json, text/plain, */*"
    result["Origin"] = "https://www.bilibili.com"
    result["Referer"] = referer or "https://www.bilibili.com/"
    for key, value in (headers or {}).items():
        if value and key.lower() not in {"cookie", "set-cookie", "authorization"}:
            result[key] = value
    return result


def _cookie_header_from_details(cookie: Optional[str], cookie_details: Optional[List[Dict[str, Any]]]) -> str:
    pairs: Dict[str, str] = {}
    for item in cookie_details or []:
        name = str(item.get("name") or "").strip()
        value = str(item.get("value") or "")
        if name:
            pairs[name] = value
    for item in (cookie or "").split(";"):
        if "=" not in item:
            continue
        name, value = item.strip().split("=", 1)
        if name:
            pairs[name] = value
    return "; ".join(f"{name}={value}" for name, value in pairs.items())


def _bilibili_wbi_key(nav_data: Dict[str, Any]) -> Optional[str]:
    wbi_img = ((nav_data.get("data") or {}).get("wbi_img") or {})
    lookup = "".join(
        str(wbi_img.get(key) or "").rsplit("/", 1)[-1].split(".", 1)[0]
        for key in ("img_url", "sub_url")
    )
    if len(lookup) <= max(BILIBILI_MIXIN_KEY_ENC_TAB):
        return None
    return "".join(lookup[index] for index in BILIBILI_MIXIN_KEY_ENC_TAB)[:32]


def _bilibili_sign_wbi(params: Dict[str, Any], mixin_key: str) -> Dict[str, Any]:
    signed = dict(params)
    signed["wts"] = round(time.time())
    filtered = {
        key: "".join(char for char in str(value) if char not in "!'()*")
        for key, value in sorted(signed.items())
    }
    query = urlencode(filtered)
    filtered["w_rid"] = hashlib.md5(f"{query}{mixin_key}".encode()).hexdigest()
    return filtered


def _bilibili_playinfo_formats(play_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    support_names = {
        item.get("quality"): item.get("new_description") or item.get("display_desc")
        for item in play_info.get("support_formats") or []
        if item.get("quality")
    }
    audios = [
        *(play_info.get("dash", {}).get("audio") or []),
        *(play_info.get("dash", {}).get("dolby", {}).get("audio") or []),
    ]
    flac_audio = play_info.get("dash", {}).get("flac", {}).get("audio")
    if flac_audio:
        audios.append(flac_audio)

    best_audio = sorted(
        [
            {
                "url": audio.get("baseUrl") or audio.get("base_url") or audio.get("url") or "",
                "bandwidth": int(audio.get("bandwidth") or 0),
                "mimeType": audio.get("mimeType") or audio.get("mime_type") or "audio/mp4",
                "codecs": audio.get("codecs") or "",
            }
            for audio in audios
        ],
        key=lambda item: item["bandwidth"],
        reverse=True,
    )
    companion_audio = best_audio[0] if best_audio else {}

    formats = []
    seen = set()
    for video in play_info.get("dash", {}).get("video") or []:
        url = video.get("baseUrl") or video.get("base_url") or video.get("url") or ""
        if not url or url in seen:
            continue
        seen.add(url)
        height = int(video.get("height") or 0) or None
        quality_id = video.get("id")
        description = support_names.get(quality_id)
        codecs = video.get("codecs") or ""
        base_label = description or (f"{height}p" if height else quality_id or "B站清晰度")
        label_parts = [str(base_label)]
        if height and not str(label_parts[0]).lower().startswith(str(height)):
            label_parts.append(f"{height}p")
        if codecs:
            label_parts.append(codecs)
        formats.append({
            "url": url,
            "format": " ".join(str(part) for part in label_parts if part),
            "height": height,
            "width": int(video.get("width") or 0) or None,
            "ext": "mp4",
            "filesize": _format_filesize(video.get("size")),
            "protocol": "bilibili-dash",
            "bandwidth": int(video.get("bandwidth") or 0) or None,
            "quality": quality_id,
            "codecs": codecs,
            "companionAudioUrl": companion_audio.get("url") or "",
            "companionAudioMimeType": companion_audio.get("mimeType") or "",
            "companionAudioCodecs": companion_audio.get("codecs") or "",
        })
    return sorted(formats, key=lambda item: (item.get("height") or 0, item.get("bandwidth") or 0), reverse=True)


def _merge_bilibili_playinfos(play_infos: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not play_infos:
        return {}

    merged = dict(play_infos[0])
    dash = dict(merged.get("dash") or {})
    seen_video_urls = set()
    seen_audio_urls = set()
    videos = []
    audios = []

    def add_unique(items: List[Dict[str, Any]], seen: set, target: List[Dict[str, Any]]) -> None:
        for item in items or []:
            url = item.get("baseUrl") or item.get("base_url") or item.get("url")
            if not url or url in seen:
                continue
            seen.add(url)
            target.append(item)

    for info in play_infos:
        info_dash = info.get("dash") or {}
        add_unique(info_dash.get("video") or [], seen_video_urls, videos)
        add_unique(info_dash.get("audio") or [], seen_audio_urls, audios)

    dash["video"] = videos
    dash["audio"] = audios
    merged["dash"] = dash
    accept_quality = []
    for info in play_infos:
        for quality in info.get("accept_quality") or []:
            if quality not in accept_quality:
                accept_quality.append(quality)
    if accept_quality:
        merged["accept_quality"] = accept_quality
    return merged


def _bilibili_api_candidates(page_url: str, page_title: str = "", headers: Optional[Dict[str, str]] = None,
                             cookie: Optional[str] = None, cookie_details: Optional[List[Dict[str, Any]]] = None,
                             diagnostics: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    bvid = _bilibili_bvid_from_url(page_url)
    if not bvid or "SESSDATA" not in _cookie_names(cookie, cookie_details):
        return []

    import requests

    session = requests.Session()
    request_headers = _bilibili_headers(headers, referer=page_url)
    cookie_header = _cookie_header_from_details(cookie, cookie_details)
    if cookie_header:
        request_headers["Cookie"] = cookie_header

    view_response = session.get(
        "https://api.bilibili.com/x/web-interface/view",
        params={"bvid": bvid},
        headers=request_headers,
        timeout=15,
    )
    view_response.raise_for_status()
    view_data = view_response.json()
    if view_data.get("code") not in {0, None}:
        raise RuntimeError(f"Bilibili view API failed: {view_data.get('code')} {view_data.get('message')}")
    view = view_data.get("data") or {}
    selected_page = _bilibili_select_page(view, _bilibili_page_number_from_url(page_url))
    cid = selected_page.get("cid") or view.get("cid")
    if not cid:
        return []

    nav_response = session.get(
        "https://api.bilibili.com/x/web-interface/nav",
        headers=request_headers,
        timeout=15,
    )
    nav_response.raise_for_status()
    nav_data = nav_response.json()
    mixin_key = _bilibili_wbi_key(nav_data)
    if diagnostics is not None:
        diagnostics["bilibiliApiLogin"] = nav_data.get("code") == 0 and bool((nav_data.get("data") or {}).get("isLogin"))
        if selected_page:
            diagnostics["bilibiliApiPage"] = selected_page.get("page")
            diagnostics["bilibiliApiCid"] = selected_page.get("cid")
    if not mixin_key:
        raise RuntimeError("Bilibili WBI key was not returned")

    playurl_endpoint = "https://api.bilibili.com/x/player/wbi/playurl"

    def request_playinfo(extra_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = _bilibili_sign_wbi({"bvid": bvid, "cid": cid, "fnval": 4048, "fourk": 1, **(extra_params or {})}, mixin_key)
        play_response = session.get(
            playurl_endpoint,
            params=params,
            headers=request_headers,
            timeout=15,
        )
        play_response.raise_for_status()
        play_data = play_response.json()
        if play_data.get("code") not in {0, None}:
            raise RuntimeError(f"Bilibili playurl API failed: {play_data.get('code')} {play_data.get('message')}")
        return play_data.get("data") or {}

    play_infos = [request_playinfo()]
    existing_qualities = {video.get("id") for video in (play_infos[0].get("dash", {}).get("video") or [])}
    for quality in play_infos[0].get("accept_quality") or []:
        if quality in existing_qualities:
            continue
        try:
            quality_play_info = request_playinfo({"qn": quality})
        except Exception as exc:
            logger.warning("Bilibili playurl qn=%s failed: %s", quality, exc)
            continue
        play_infos.append(quality_play_info)
        existing_qualities.update(video.get("id") for video in (quality_play_info.get("dash", {}).get("video") or []))

    play_info = _merge_bilibili_playinfos(play_infos)
    formats = _bilibili_playinfo_formats(play_info)
    if diagnostics is not None:
        diagnostics["bilibiliApiAcceptQuality"] = play_info.get("accept_quality") or []
        diagnostics["bilibiliApiFormatHeights"] = [fmt.get("height") for fmt in formats if fmt.get("height")]
    if not formats:
        return []

    return [{
        "id": f"bilibili-api-{bvid}",
        "title": view.get("title") or page_title or "Bilibili video",
        "sourceUrl": page_url,
        "extractor": "bilibili-api",
        "duration": view.get("duration"),
        "thumbnail": view.get("pic"),
        "formats": [
            {
                "formatId": f"bilibili-api-{fmt.get('quality') or fmt.get('height') or index}",
                "label": fmt.get("format") or _format_label(fmt),
                "height": fmt.get("height"),
                "ext": fmt.get("ext") or "mp4",
                "filesize": fmt.get("filesize"),
                "protocol": fmt.get("protocol"),
                "bandwidth": fmt.get("bandwidth"),
                "codecs": fmt.get("codecs"),
                "sourceUrl": fmt.get("url"),
                "companionAudioUrl": fmt.get("companionAudioUrl") or "",
                "companionAudioMimeType": fmt.get("companionAudioMimeType") or "",
                "companionAudioCodecs": fmt.get("companionAudioCodecs") or "",
            }
            for index, fmt in enumerate(formats, start=1)
        ],
    }]


def _cookie_names(cookie: Optional[str] = None, cookie_details: Optional[List[Dict[str, Any]]] = None) -> set:
    names = set()
    for item in cookie_details or []:
        name = str(item.get("name") or "").strip()
        if name:
            names.add(name)
    for item in (cookie or "").split(";"):
        if "=" not in item:
            continue
        name = item.strip().split("=", 1)[0].strip()
        if name:
            names.add(name)
    return names


def _candidate_diagnostics(candidates: List[Dict[str, Any]], errors: List[str],
                           cookie: Optional[str] = None,
                           cookie_details: Optional[List[Dict[str, Any]]] = None,
                           detected_streams: Optional[List[Dict[str, Any]]] = None,
                           yt_dlp_messages: Optional[List[str]] = None,
                           yt_dlp_cookies: Optional[Dict[str, Any]] = None,
                           bilibili_api: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cookie_names = _cookie_names(cookie, cookie_details)
    format_count = 0
    max_height = None
    extractors = []
    for candidate in candidates:
        extractor = candidate.get("extractor")
        if extractor and extractor not in extractors:
            extractors.append(extractor)
        for fmt in candidate.get("formats") or []:
            format_count += 1
            height = fmt.get("height")
            if isinstance(height, int):
                max_height = max(max_height or 0, height)

    stream_count = len(detected_streams or [])
    return {
        "candidateCount": len(candidates),
        "formatCount": format_count,
        "maxHeight": max_height,
        "extractors": extractors[:6],
        "detectedStreamCount": stream_count,
        "receivedCookies": {
            "bilibiliSessdata": "SESSDATA" in cookie_names,
            "bilibiliCsrf": "bili_jct" in cookie_names,
            "douyinFresh": bool({"s_v_web_id", "msToken", "ttwid"} & cookie_names),
            "douyinLogin": bool({"sid_tt", "sessionid", "uid_tt"} & cookie_names),
        },
        "ytDlpCookies": yt_dlp_cookies or {},
        "ytDlpMessages": list(yt_dlp_messages or [])[:6],
        "bilibiliApi": bilibili_api or {},
        "errorCount": len(errors),
    }


def _info_to_candidates(info: Dict[str, Any], page_title: str, source_url: str,
                        candidate_prefix: str = "yt", max_items: int = 8) -> List[Dict[str, Any]]:
    if not isinstance(info, dict):
        return []

    entries = info.get("entries")
    info_items = [item for item in entries if isinstance(item, dict)] if entries else [info]
    candidates = []

    for item_index, item in enumerate(info_items[:max_items]):
        formats = []
        for fmt in item.get("formats") or []:
            format_id = fmt.get("format_id")
            if not format_id:
                continue
            protocol = fmt.get("protocol") or ""
            if protocol == "mhtml":
                continue
            if fmt.get("vcodec") == "none":
                continue
            formats.append({
                "formatId": _download_format_id(fmt),
                "rawFormatId": str(format_id),
                "label": _format_label(fmt),
                "height": fmt.get("height"),
                "ext": fmt.get("ext"),
                "filesize": _format_filesize(fmt.get("filesize") or fmt.get("filesize_approx")),
                "protocol": protocol,
            })

        if formats:
            formats.sort(key=lambda f: (f.get("height") or 0, f.get("filesize") or 0), reverse=True)
        else:
            formats = [{
                "formatId": "best",
                "label": "Best available",
                "height": None,
                "ext": item.get("ext"),
                "filesize": _format_filesize(item.get("filesize")),
                "protocol": item.get("protocol"),
            }]

        resolved_source = (
            item.get("webpage_url")
            or item.get("original_url")
            or item.get("url")
            or source_url
        )
        candidates.append({
            "id": f"{candidate_prefix}-{item_index}",
            "title": item.get("title") or page_title or "Web video",
            "sourceUrl": resolved_source,
            "extractor": item.get("extractor") or "yt-dlp",
            "duration": item.get("duration"),
            "thumbnail": item.get("thumbnail"),
            "formats": formats,
        })

    return candidates


def _resolve_with_ytdlp(url: str, page_title: str = "", headers: Optional[Dict[str, str]] = None,
                       cookie: Optional[str] = None, cookie_details: Optional[List[Dict[str, Any]]] = None,
                       referer: Optional[str] = None,
                       candidate_prefix: str = "yt",
                       yt_dlp_messages: Optional[List[str]] = None,
                       yt_dlp_cookie_diagnostics: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    import yt_dlp

    url = _normalize_page_url(url)
    options = _yt_dlp_options(headers=headers, cookie=cookie, referer=referer, diagnostic_messages=yt_dlp_messages)
    with _temporary_cookiefile(cookie or "", cookie_details=cookie_details) as cookie_file:
        if cookie_file:
            options["cookiefile"] = cookie_file
        with yt_dlp.YoutubeDL(options) as ydl:
            _record_ytdlp_cookie_diagnostics(ydl, yt_dlp_cookie_diagnostics)
            info = ydl.extract_info(url, download=False)
    return _info_to_candidates(info, page_title=page_title, source_url=url, candidate_prefix=candidate_prefix)


def resolve_web_video(page_url: str, page_title: str = "", detected_streams: Optional[List[Dict[str, Any]]] = None,
                      headers: Optional[Dict[str, str]] = None, cookie: Optional[str] = None,
                      cookie_details: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    candidates = []
    errors = []
    yt_dlp_messages: List[str] = []
    yt_dlp_cookie_diagnostics: Dict[str, Any] = {}
    bilibili_api_diagnostics: Dict[str, Any] = {}

    if page_url:
        try:
            candidates.extend(_resolve_with_ytdlp(
                _normalize_page_url(page_url),
                page_title=page_title,
                headers=headers,
                cookie=cookie,
                cookie_details=cookie_details,
                candidate_prefix="yt",
                yt_dlp_messages=yt_dlp_messages,
                yt_dlp_cookie_diagnostics=yt_dlp_cookie_diagnostics,
            ))
        except Exception as exc:
            errors.append(f"page: {exc}")
            _append_unique_diagnostic(yt_dlp_messages, str(exc))

        try:
            candidates.extend(_bilibili_api_candidates(
                _normalize_page_url(page_url),
                page_title=page_title,
                headers=headers,
                cookie=cookie,
                cookie_details=cookie_details,
                diagnostics=bilibili_api_diagnostics,
            ))
        except Exception as exc:
            errors.append(f"bilibili-api: {exc}")
            _append_unique_diagnostic(yt_dlp_messages, str(exc))

    fallback_streams = []
    seen_stream_urls = set()
    for stream in detected_streams or []:
        url = (stream.get("url") or "").strip()
        if not url or url.startswith("blob:") or (
            _is_fragment_stream(stream) and not stream.get("isBilibiliPlayInfo") and not stream.get("isDouyinPageData")
        ):
            continue
        if url in seen_stream_urls:
            continue
        seen_stream_urls.add(url)

        if _is_manifest_stream(stream):
            try:
                stream_prefix = _stream_id(url)
                resolved = _resolve_with_ytdlp(
                    url,
                    page_title=page_title,
                    headers=headers,
                    cookie=cookie,
                    cookie_details=cookie_details,
                    referer=page_url,
                    candidate_prefix=stream_prefix,
                    yt_dlp_messages=yt_dlp_messages,
                    yt_dlp_cookie_diagnostics=yt_dlp_cookie_diagnostics,
                )
                if resolved:
                    candidates.extend(resolved)
                    continue
            except Exception as exc:
                errors.append(f"stream {url}: {exc}")
                _append_unique_diagnostic(yt_dlp_messages, str(exc))

        fallback_streams.append(stream)

    candidates.extend(_normalize_detected_streams(fallback_streams, page_title=page_title))
    candidates = _sort_candidates_by_quality(_dedupe_candidates(candidates))
    diagnostics = _candidate_diagnostics(
        candidates,
        errors,
        cookie=cookie,
        cookie_details=cookie_details,
        detected_streams=detected_streams,
        yt_dlp_messages=yt_dlp_messages,
        yt_dlp_cookies=yt_dlp_cookie_diagnostics,
        bilibili_api=bilibili_api_diagnostics,
    )

    return {
        "pageUrl": page_url,
        "pageTitle": page_title,
        "candidates": candidates,
        "errors": errors,
        "diagnostics": diagnostics,
    }


def start_import_job(payload: Dict[str, Any]) -> WebVideoJob:
    page_url = payload.get("pageUrl") or payload.get("page_url") or ""
    job = job_manager.create(page_url=page_url)
    thread = threading.Thread(target=_run_import_job, args=(job.job_id, payload), daemon=True)
    thread.start()
    return job


def _choose_download_url(payload: Dict[str, Any]) -> str:
    candidate_url = payload.get("candidateUrl") or payload.get("candidate_url")
    if candidate_url and not str(candidate_url).startswith("blob:"):
        return _normalize_page_url(str(candidate_url))
    candidate_id = payload.get("candidateId") or payload.get("candidate_id")
    for candidate in _normalize_detected_streams(payload.get("detectedStreams") or [], payload.get("pageTitle") or ""):
        if candidate["id"] == candidate_id:
            return candidate["sourceUrl"]
    return _normalize_page_url(payload.get("pageUrl") or payload.get("page_url") or "")


def _download_with_ytdlp(job_id: str, payload: Dict[str, Any]) -> Path:
    import yt_dlp

    url = _choose_download_url(payload)
    if not url:
        raise ValueError("No video URL was provided")

    job_prefix = f"web_{job_id}"
    outtmpl = str(UPLOAD_DIR / f"{job_prefix}.%(ext)s")
    format_id = payload.get("formatId") or payload.get("format_id") or "bv*+ba/best"
    if format_id in {"detected", "douyin-page-data"}:
        format_id = "best"
    cookie = payload.get("cookie") or payload.get("cookies")
    cookie_details = payload.get("cookieDetails") or payload.get("cookie_details") or []
    headers = payload.get("headers") or {}

    def progress_hook(status: Dict[str, Any]):
        if status.get("status") == "downloading":
            total = status.get("total_bytes") or status.get("total_bytes_estimate") or 0
            downloaded = status.get("downloaded_bytes") or 0
            progress = int(downloaded * 80 / total) if total else 10
            job_manager.update(job_id, status="downloading", progress=max(5, min(progress, 85)), message="Downloading video")
        elif status.get("status") == "finished":
            job_manager.update(job_id, status="downloading", progress=90, message="Finalizing media")

    options = _yt_dlp_options(headers=headers, cookie=cookie, referer=payload.get("pageUrl") or payload.get("page_url"))
    options.update({
        "outtmpl": outtmpl,
        "format": format_id,
        "merge_output_format": "mp4",
        "progress_hooks": [progress_hook],
        "restrictfilenames": False,
    })

    job_manager.update(job_id, status="downloading", progress=5, message="Resolving selected media")
    with _temporary_cookiefile(cookie or "", cookie_details=cookie_details) as cookie_file:
        if cookie_file:
            options["cookiefile"] = cookie_file
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([url])

    matches = sorted(UPLOAD_DIR.glob(f"{job_prefix}.*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not matches:
        raise FileNotFoundError("Download completed but no output file was found")
    return matches[0]


def _download_direct_url(url: str, target_path: Path, headers: Dict[str, str], job_id: str,
                         label: str = "Downloading media track") -> Path:
    import requests

    job_manager.update(job_id, status="downloading", progress=8, message=label)
    with requests.get(url, headers=headers, stream=True, timeout=30) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length") or 0)
        downloaded = 0
        with target_path.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 512):
                if not chunk:
                    continue
                handle.write(chunk)
                downloaded += len(chunk)
                if total:
                    progress = 8 + int(downloaded * 35 / total)
                    job_manager.update(
                        job_id,
                        status="downloading",
                        progress=max(8, min(progress, 45)),
                        message=label,
                    )
    return target_path


def _download_selected_direct_media(job_id: str, payload: Dict[str, Any], suffix: str = ".mp4") -> Path:
    url = _choose_download_url(payload)
    if not url:
        raise ValueError("No direct media URL was provided")

    headers = dict(DEFAULT_BROWSER_HEADERS)
    headers.update({k: v for k, v in (payload.get("headers") or {}).items() if v and k.lower() not in {"cookie", "set-cookie"}})
    if payload.get("cookies"):
        headers["Cookie"] = payload.get("cookies")
    if payload.get("pageUrl") or payload.get("page_url"):
        headers["Referer"] = payload.get("pageUrl") or payload.get("page_url")

    parsed_suffix = _stream_suffix(url)
    output_suffix = parsed_suffix if parsed_suffix in MEDIA_EXTENSIONS and parsed_suffix not in {".ts", ".aac"} else suffix
    output_path = UPLOAD_DIR / f"web_{job_id}{output_suffix}"
    return _download_direct_url(url, output_path, headers, job_id, "Downloading selected Douyin media")


def _merge_video_audio(video_path: Path, audio_path: Path, output_path: Path, job_id: str) -> Path:
    ffmpeg = get_ffmpeg_path()
    job_manager.update(job_id, status="downloading", progress=85, message="Merging video and audio")
    command = [
        ffmpeg,
        "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c", "copy",
        "-movflags", "+faststart",
        str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "ffmpeg merge failed").strip()[-1000:])
    return output_path


def _download_bilibili_playinfo(job_id: str, payload: Dict[str, Any]) -> Path:
    video_url = payload.get("candidateUrl") or payload.get("candidate_url")
    audio_url = ""
    candidate_id = payload.get("candidateId") or payload.get("candidate_id")
    format_id = payload.get("formatId") or payload.get("format_id")
    for candidate in _normalize_detected_streams(payload.get("detectedStreams") or [], payload.get("pageTitle") or ""):
        if candidate["id"] == candidate_id or candidate["sourceUrl"] == video_url:
            audio_url = candidate.get("companionAudioUrl") or ""
            break
    for candidate in (payload.get("resolvedCandidates") or payload.get("resolved_candidates") or []):
        if candidate.get("id") != candidate_id and candidate.get("sourceUrl") != video_url:
            continue
        for fmt in candidate.get("formats") or []:
            candidate_format_id = str(fmt.get("formatId") or "")
            if (
                format_id
                and candidate_format_id != str(format_id)
                and not (str(format_id) == "bilibili-api" and candidate_format_id.startswith("bilibili-api"))
            ):
                continue
            video_url = fmt.get("sourceUrl") or fmt.get("url") or video_url
            audio_url = fmt.get("companionAudioUrl") or audio_url
            break
    if not video_url:
        raise ValueError("No Bilibili video track URL was provided")
    if not audio_url:
        raise ValueError("No Bilibili audio track was found for the selected video quality")

    headers = dict(DEFAULT_BROWSER_HEADERS)
    headers.update({k: v for k, v in (payload.get("headers") or {}).items() if v and k.lower() not in {"cookie", "set-cookie"}})
    if payload.get("cookies"):
        headers["Cookie"] = payload.get("cookies")
    if payload.get("pageUrl") or payload.get("page_url"):
        headers["Referer"] = payload.get("pageUrl") or payload.get("page_url")

    job_prefix = f"web_{job_id}"
    video_path = UPLOAD_DIR / f"{job_prefix}.video.m4s"
    audio_path = UPLOAD_DIR / f"{job_prefix}.audio.m4s"
    output_path = UPLOAD_DIR / f"{job_prefix}.mp4"
    try:
        _download_direct_url(video_url, video_path, headers, job_id, "Downloading selected Bilibili video track")
        job_manager.update(job_id, status="downloading", progress=50, message="Downloading Bilibili audio track")
        _download_direct_url(audio_url, audio_path, headers, job_id, "Downloading Bilibili audio track")
        return _merge_video_audio(video_path, audio_path, output_path, job_id)
    finally:
        for path in (video_path, audio_path):
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass


def _task_filename(payload: Dict[str, Any], downloaded_path: Path) -> str:
    title = payload.get("pageTitle") or downloaded_path.stem or "web-video"
    suffix = downloaded_path.suffix.lower() or ".mp4"
    if suffix not in MEDIA_EXTENSIONS:
        suffix = ".mp4"
    return f"{_safe_label(title)}{suffix}"


def _write_model_config(task_id: str, model_config: Optional[dict]) -> None:
    if not model_config:
        return
    config_file = NOTE_OUTPUT_DIR / f"{task_id}_model_config.json"
    import json
    config_file.write_text(json.dumps(model_config, ensure_ascii=False, indent=2), encoding="utf-8")


def _payload_note_style(payload: Dict[str, Any], default: str = "simple") -> str:
    style = payload.get("noteStyle") or payload.get("note_style") or default
    return style if style in NOTE_STYLES else default


def _run_import_job(job_id: str, payload: Dict[str, Any]) -> None:
    downloaded_path: Optional[Path] = None
    try:
        format_id = str(payload.get("formatId") or payload.get("format_id") or "")
        if format_id == "bilibili-playinfo" or format_id.startswith("bilibili-api"):
            downloaded_path = _download_bilibili_playinfo(job_id, payload)
        elif format_id == "douyin-page-data":
            downloaded_path = _download_selected_direct_media(job_id, payload)
        else:
            downloaded_path = _download_with_ytdlp(job_id, payload)
        job_manager.update(job_id, status="imported", progress=92, message="Creating AInote task")

        task_id = str(uuid.uuid4())
        filename = _task_filename(payload, downloaded_path)
        target_path = UPLOAD_DIR / f"{task_id}{Path(filename).suffix.lower()}"
        shutil.move(str(downloaded_path), target_path)

        screenshot = bool(payload.get("screenshot", False))
        create_task(
            task_id=task_id,
            filename=filename,
            screenshot=screenshot,
            source="web",
            source_url=payload.get("pageUrl") or payload.get("page_url"),
        )

        model_config = load_active_model_config() or {}
        note_style = _payload_note_style(payload, model_config.get("note_style", "simple"))
        model_config["note_style"] = note_style
        _write_model_config(task_id, model_config)
        job_manager.update(job_id, task_id=task_id, filename=filename, progress=95)

        if payload.get("autoRun", payload.get("auto_run", True)):
            job_manager.update(job_id, status="running_note", progress=96, message="Generating note")
            NoteGenerator(model_config=model_config).generate(
                video_path=str(target_path),
                filename=filename,
                task_id=task_id,
                screenshot=screenshot,
                note_style=note_style,
            )

        job_manager.update(job_id, status="completed", progress=100, message="Done")
    except Exception as exc:
        logger.error(f"Web video import job failed: {exc}", exc_info=True)
        current = job_manager.get(job_id)
        if current and current.task_id:
            try:
                update_task_status(current.task_id, "failed", error_message=str(exc))
            except Exception:
                pass
        job_manager.update(job_id, status="failed", error=str(exc), message="Import failed")
        if downloaded_path and downloaded_path.exists():
            try:
                downloaded_path.unlink()
            except Exception:
                pass
