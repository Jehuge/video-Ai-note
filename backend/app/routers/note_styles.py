from typing import List

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.note_style_settings import (
    load_note_style_settings,
    reset_builtin_note_styles,
    save_note_style_settings,
)
from app.utils.response import ResponseWrapper as R

router = APIRouter()


class NoteStyleItem(BaseModel):
    id: str
    name: str
    prompt: str
    built_in: bool = False
    enabled: bool = True


class NoteStyleSettingsRequest(BaseModel):
    version: int = 1
    default_style_id: str
    styles: List[NoteStyleItem]


@router.get("/note-styles")
def get_note_styles():
    return R.success(load_note_style_settings())


@router.put("/note-styles")
def update_note_styles(request: NoteStyleSettingsRequest):
    try:
        saved = save_note_style_settings(request.model_dump())
        return R.success(saved, msg="笔记模式设置已保存")
    except ValueError as exc:
        return R.error(str(exc), code=400)


@router.post("/note-styles/reset")
def reset_note_styles():
    return R.success(reset_builtin_note_styles(), msg="内置模式已恢复")
