import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException, Body
from pydantic import BaseModel
from fastapi.responses import JSONResponse

from app.db.video_task_dao import create_task, get_task_by_id, get_all_tasks, update_task_status
from app.services.note import NoteGenerator
from app.utils.response import ResponseWrapper as R
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

NOTE_OUTPUT_DIR = Path(os.getenv("NOTE_OUTPUT_DIR", "note_results"))

# 支持的文件类型
ALLOWED_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.m4v', '.mp3', '.wav', '.m4a'}


def run_note_task_step(task_id: str, video_path: str, filename: str, step: str, screenshot: bool = False):
    """执行单个步骤"""
    try:
        generator = NoteGenerator()
        
        if step == "extract":
            # 提取音频
            audio_path = generator._extract_audio(video_path, task_id)
            update_task_status(task_id, "processing")
            logger.info(f"音频提取完成: {task_id}")
            
        elif step == "transcribe":
            # 转写音频
            update_task_status(task_id, "transcribing")
            transcript = generator._transcribe_audio(
                generator._extract_audio(video_path, task_id),
                task_id
            )
            # 转录完成后，状态改为 "transcribed" 表示等待下一步确认
            # 但为了兼容前端，我们保持 "transcribing" 状态，前端会通过检查 transcript 文件来判断是否完成
            logger.info(f"转写完成: {task_id}")
            
        elif step == "summarize":
            # 检查转录是否完成
            transcript_file = NOTE_OUTPUT_DIR / f"{task_id}_transcript.json"
            if not transcript_file.exists():
                logger.error(f"转录文件不存在: {task_id}")
                update_task_status(task_id, "failed")
                return
            
            # 如果启用了截图，删除缓存强制重新生成（确保包含截图标记）
            if screenshot:
                cache_file = NOTE_OUTPUT_DIR / f"{task_id}_markdown.md"
                if cache_file.exists():
                    cache_file.unlink()
                    logger.info(f"已删除缓存以重新生成带截图的笔记: {cache_file}")
            
            # 生成笔记
            update_task_status(task_id, "summarizing")
            audio_path = generator._extract_audio(video_path, task_id)
            transcript = generator._transcribe_audio(audio_path, task_id)
            # 如果启用了截图，禁用缓存确保重新生成
            markdown = generator._summarize_text(transcript, filename, task_id, screenshot, use_cache=not screenshot)
            
            # 后处理：插入截图
            if screenshot:
                markdown = generator._insert_screenshots(markdown, video_path, task_id)
            
            update_task_status(task_id, "completed", markdown)
            logger.info(f"笔记生成完成: {task_id}")
            
    except Exception as e:
        logger.error(f"步骤执行失败: {task_id}, step={step}, 错误: {e}", exc_info=True)
        update_task_status(task_id, "failed")


@router.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    screenshot: str = Form("false"),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """上传视频文件并开始生成笔记"""
    try:
        # 转换字符串为布尔值
        enable_screenshot = screenshot.lower() == "true"
        # 检查文件扩展名
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            return R.error(f"不支持的文件类型: {file_ext}，支持的类型: {', '.join(ALLOWED_EXTENSIONS)}")
        
        # 生成任务 ID
        task_id = str(uuid.uuid4())
        
        # 保存文件
        file_path = UPLOAD_DIR / f"{task_id}{file_ext}"
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # 创建任务记录（状态为 pending，等待用户确认第一步）
        create_task(task_id=task_id, filename=file.filename, screenshot=enable_screenshot)
        
        # 不自动启动，等待用户确认第一步
        
        logger.info(f"文件上传成功: {file.filename}, task_id={task_id}")
        
        return R.success({
            "task_id": task_id,
            "filename": file.filename
        })
        
    except Exception as e:
        logger.error(f"文件上传失败: {e}", exc_info=True)
        return R.error(f"上传失败: {str(e)}")


@router.get("/task/{task_id}")
def get_task(task_id: str):
    """获取任务状态和结果"""
    try:
        task = get_task_by_id(task_id)
        if not task:
            return R.error("任务不存在")
        
        result = {
            "task_id": task.task_id,
            "filename": task.filename,
            "status": task.status,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        }
        
        # 如果任务已完成或有 markdown，都返回 markdown
        if task.markdown:
            result["markdown"] = task.markdown
        
        # 尝试获取转写结果
        transcript_file = NOTE_OUTPUT_DIR / f"{task_id}_transcript.json"
        if transcript_file.exists():
            import json
            with open(transcript_file, 'r', encoding='utf-8') as f:
                transcript_data = json.load(f)
                result["transcript"] = transcript_data
        
        return R.success(result)
        
    except Exception as e:
        logger.error(f"获取任务失败: {e}", exc_info=True)
        return R.error(f"获取任务失败: {str(e)}")


@router.get("/tasks")
def list_tasks(limit: int = 50):
    """获取任务列表"""
    try:
        tasks = get_all_tasks(limit=limit)
        result = [
            {
                "task_id": task.task_id,
                "filename": task.filename,
                "status": task.status,
                "created_at": task.created_at.isoformat() if task.created_at else None,
            }
            for task in tasks
        ]
        return R.success(result)
    except Exception as e:
        logger.error(f"获取任务列表失败: {e}", exc_info=True)
        return R.error(f"获取任务列表失败: {str(e)}")


@router.post("/task/{task_id}/regenerate")
def regenerate_note(task_id: str, background_tasks: BackgroundTasks = BackgroundTasks()):
    """重新生成笔记"""
    try:
        # 检查任务是否存在
        task = get_task_by_id(task_id)
        if not task:
            return R.error("任务不存在")
        
        # 检查转录是否完成
        transcript_file = NOTE_OUTPUT_DIR / f"{task_id}_transcript.json"
        if not transcript_file.exists():
            return R.error("请先完成音频转写")
        
        # 获取文件路径
        file_ext = Path(task.filename).suffix.lower()
        file_path = UPLOAD_DIR / f"{task_id}{file_ext}"
        
        if not file_path.exists():
            return R.error("文件不存在")
        
        # 获取截图设置
        screenshot = bool(getattr(task, 'screenshot', 0))
        
        # 删除旧的笔记缓存，强制重新生成
        cache_file = NOTE_OUTPUT_DIR / f"{task_id}_markdown.md"
        if cache_file.exists():
            cache_file.unlink()
            logger.info(f"已删除旧笔记缓存: {cache_file}")
        
        # 更新状态为 summarizing
        update_task_status(task_id, "summarizing")
        
        # 在后台重新生成笔记
        background_tasks.add_task(
            run_note_task_step,
            task_id=task_id,
            video_path=str(file_path),
            filename=task.filename,
            step="summarize",
            screenshot=screenshot
        )
        
        logger.info(f"开始重新生成笔记: {task_id}")
        return R.success({"message": "正在重新生成笔记"})
        
    except Exception as e:
        logger.error(f"重新生成笔记失败: {e}", exc_info=True)
        return R.error(f"重新生成笔记失败: {str(e)}")


class ConfirmStepRequest(BaseModel):
    step: str

@router.post("/task/{task_id}/confirm_step")
def confirm_step(task_id: str, request: ConfirmStepRequest, background_tasks: BackgroundTasks = BackgroundTasks()):
    """确认步骤并执行"""
    try:
        # 检查任务状态
        task = get_task_by_id(task_id)
        if not task:
            return R.error("任务不存在")
        
        # 获取文件路径
        file_ext = Path(task.filename).suffix.lower()
        file_path = UPLOAD_DIR / f"{task_id}{file_ext}"
        
        if not file_path.exists():
            return R.error("文件不存在")
        
        # 获取截图设置（从数据库获取）
        screenshot = bool(getattr(task, 'screenshot', 0))
        
        # 根据步骤执行相应的任务
        step = request.step
        if step == "extract":
            if task.status != "pending":
                return R.error("当前步骤不可执行")
            background_tasks.add_task(
                run_note_task_step,
                task_id=task_id,
                video_path=str(file_path),
                filename=task.filename,
                step="extract",
                screenshot=screenshot
            )
        elif step == "transcribe":
            if task.status != "processing":
                return R.error("当前步骤不可执行")
            background_tasks.add_task(
                run_note_task_step,
                task_id=task_id,
                video_path=str(file_path),
                filename=task.filename,
                step="transcribe",
                screenshot=screenshot
            )
        elif step == "summarize":
            # 检查转录是否完成（通过检查转录文件是否存在）
            transcript_file = NOTE_OUTPUT_DIR / f"{task_id}_transcript.json"
            if task.status != "transcribing" and not transcript_file.exists():
                return R.error("请先完成音频转写")
            background_tasks.add_task(
                run_note_task_step,
                task_id=task_id,
                video_path=str(file_path),
                filename=task.filename,
                step="summarize",
                screenshot=screenshot
            )
        else:
            return R.error("未知的步骤")
        
        return R.success({"message": "步骤已确认，开始执行"})
        
    except Exception as e:
        logger.error(f"确认步骤失败: {e}", exc_info=True)
        return R.error(f"确认步骤失败: {str(e)}")


@router.delete("/task/{task_id}")
def delete_task(task_id: str):
    """删除任务（可选功能）"""
    # TODO: 实现删除功能
    return R.success("删除功能待实现")
