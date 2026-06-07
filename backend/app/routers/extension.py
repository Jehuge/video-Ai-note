from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.services.extension_bridge import get_bridge_token, verify_bridge_token
from app.services.web_video import job_manager, resolve_web_video, start_import_job, sync_job_with_task
from app.utils.app_paths import get_app_data_dir
from app.utils.response import ResponseWrapper as R

router = APIRouter()


class DetectedStream(BaseModel):
    url: str
    mimeType: Optional[str] = None
    type: Optional[str] = None
    label: Optional[str] = None
    quality: Optional[str] = None
    height: Optional[int] = None
    width: Optional[int] = None
    filesize: Optional[int] = None
    source: Optional[str] = None
    isFragment: Optional[bool] = False
    isBlob: Optional[bool] = False
    companionAudioUrl: Optional[str] = None
    companionAudioMimeType: Optional[str] = None
    companionAudioCodecs: Optional[str] = None
    bandwidth: Optional[int] = None
    codecs: Optional[str] = None
    isBilibiliPlayInfo: Optional[bool] = False
    isDouyinPageData: Optional[bool] = False


class BrowserCookie(BaseModel):
    name: str
    value: str
    domain: Optional[str] = None
    path: Optional[str] = "/"
    secure: Optional[bool] = False
    expirationDate: Optional[float] = None
    session: Optional[bool] = None


class ResolveRequest(BaseModel):
    pageUrl: str
    pageTitle: Optional[str] = ""
    detectedStreams: List[DetectedStream] = Field(default_factory=list)
    headers: Dict[str, str] = Field(default_factory=dict)
    cookies: Optional[str] = None
    cookieDetails: List[BrowserCookie] = Field(default_factory=list)


class ImportRequest(ResolveRequest):
    candidateId: Optional[str] = None
    candidateUrl: Optional[str] = None
    formatId: Optional[str] = None
    noteStyle: Optional[str] = "simple"
    autoRun: bool = True
    screenshot: bool = False


@router.get("/extension/health")
async def extension_health(request: Request):
    return R.success({
        "app": "VideoNoteAI",
        "version": "1.1.0",
        "status": "ok",
        "host": request.client.host if request.client else None,
        "bridgeToken": get_bridge_token(),
        "tokenRequired": True,
        "dataDir": str(get_app_data_dir()),
    })


@router.post("/extension/videos/resolve")
async def resolve_videos(payload: ResolveRequest, _: None = Depends(verify_bridge_token)):
    result = await _to_thread(
        resolve_web_video,
        page_url=payload.pageUrl,
        page_title=payload.pageTitle or "",
        detected_streams=[item.model_dump() for item in payload.detectedStreams],
        headers=payload.headers,
        cookie=payload.cookies,
        cookie_details=[item.model_dump() for item in payload.cookieDetails],
    )
    return R.success(result)


@router.post("/extension/videos/import")
async def import_video(payload: ImportRequest, _: None = Depends(verify_bridge_token)):
    job = start_import_job(payload.model_dump())
    return R.success({
        "jobId": job.job_id,
        "status": job.status,
        "progress": job.progress,
    })


@router.get("/extension/jobs/{job_id}")
async def get_job(job_id: str, _: None = Depends(verify_bridge_token)):
    job = sync_job_with_task(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return R.success({
        "jobId": job.job_id,
        "status": job.status,
        "progress": job.progress,
        "message": job.message,
        "error": job.error,
        "taskId": job.task_id,
        "filename": job.filename,
        "pageUrl": job.page_url,
    })


async def _to_thread(func, *args, **kwargs):
    import asyncio
    return await asyncio.to_thread(func, *args, **kwargs)
