"""
自定义笔记风格 API 路由
"""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import note_styles
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


class StyleCreate(BaseModel):
    name: str
    prompt: str
    icon: Optional[str] = "📝"


class StyleUpdate(BaseModel):
    name: Optional[str] = None
    prompt: Optional[str] = None
    icon: Optional[str] = None


@router.get("/note/styles")
async def get_styles():
    """获取全部笔记风格（内置 + 自定义）"""
    try:
        return {"success": True, "data": note_styles.list_styles()}
    except Exception as e:
        logger.error(f"获取笔记风格失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/note/styles")
async def create_style(style: StyleCreate):
    try:
        created = note_styles.create_style(style.name, style.prompt, style.icon or "📝")
        return {"success": True, "data": created, "message": "风格已创建"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"创建笔记风格失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/note/styles/{style_id}")
async def update_style(style_id: str, style: StyleUpdate):
    try:
        updated = note_styles.update_style(style_id, style.name, style.prompt, style.icon)
        return {"success": True, "data": updated, "message": "风格已更新"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"更新笔记风格失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/note/styles/{style_id}")
async def delete_style(style_id: str):
    try:
        note_styles.delete_style(style_id)
        return {"success": True, "message": "风格已删除"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"删除笔记风格失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
