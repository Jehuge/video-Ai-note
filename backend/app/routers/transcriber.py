from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.transcriber_settings import (
    TRANSCRIBER_TYPES,
    load_transcriber_config,
    public_transcriber_config,
    save_transcriber_config,
    validate_transcriber_config,
)
from app.utils.response import ResponseWrapper as R

router = APIRouter()


class TranscriberConfigRequest(BaseModel):
    type: str = "fast-whisper"
    model_size: Optional[str] = None
    device: Optional[str] = None
    compute_type: Optional[str] = None


@router.get("/transcriber/types")
def get_transcriber_types():
    return R.success(list(TRANSCRIBER_TYPES.values()))


@router.get("/transcriber/config")
def get_transcriber_config():
    return R.success(public_transcriber_config(load_transcriber_config()))


@router.post("/transcriber/config")
def set_transcriber_config(config: TranscriberConfigRequest):
    saved = save_transcriber_config(config.model_dump(exclude_none=True))
    return R.success(public_transcriber_config(saved), msg="本地语音识别配置已保存")


@router.post("/transcriber/test")
def test_transcriber_config(config: TranscriberConfigRequest):
    payload = config.model_dump(exclude_none=True)
    error = validate_transcriber_config(payload)
    if error:
        return R.error(error)
    return R.success(public_transcriber_config(payload), msg="本地语音识别配置可用")
