import os
import re
import tempfile
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException, Body, Request
from pydantic import BaseModel
from fastapi.responses import JSONResponse, Response

from app.db.video_task_dao import create_task, get_task_by_id, get_all_tasks, is_task_canceled, update_task_status, delete_task_by_id
from app.services.note import NoteGenerator, IMAGE_OUTPUT_DIR, IMAGE_BASE_URL
from app.services.vision import describe_frame
from app.services.model_settings import load_active_model_config
from app.services.note_progress import clear_note_progress, read_note_progress
from app.services.note_format import normalize_note_markdown
from app.services.web_video import cancel_jobs_for_task
from app.utils.response import ResponseWrapper as R
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

NOTE_OUTPUT_DIR = Path(os.getenv("NOTE_OUTPUT_DIR", "note_results"))

# 支持的文件类型
ALLOWED_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.m4v', '.mp3', '.wav', '.m4a'}


def _merge_model_config_with_active(task_config: Optional[dict] = None) -> Optional[dict]:
    if task_config and task_config.get("_explicit_current_model"):
        return task_config
    active_config = load_active_model_config() or {}
    if active_config:
        merged = dict(active_config)
        if task_config and task_config.get("note_style"):
            merged["note_style"] = task_config.get("note_style")
        return merged
    return task_config


def _write_task_model_config(task_id: str, model_config: Optional[dict]) -> None:
    if not model_config:
        return
    config_file = NOTE_OUTPUT_DIR / f"{task_id}_model_config.json"
    import json
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(model_config, f, ensure_ascii=False, indent=2)


def run_note_task_step(task_id: str, video_path: str, filename: str, step: str, screenshot: bool = False):
    """执行单个步骤"""
    if is_task_canceled(task_id):
        logger.info(f"任务已手动停止，跳过步骤执行: {task_id}, step={step}")
        return
    try:
        # 尝试读取模型配置
        model_config = None
        config_file = NOTE_OUTPUT_DIR / f"{task_id}_model_config.json"
        if config_file.exists():
            try:
                import json
                with open(config_file, "r", encoding="utf-8") as f:
                    model_config = json.load(f)
                model_config = _merge_model_config_with_active(model_config)
                _write_task_model_config(task_id, model_config)
                logger.info(
                    "加载模型配置: "
                    f"provider={model_config.get('provider')}, "
                    f"type={model_config.get('provider_type')}, "
                    f"model={model_config.get('model')}, "
                    f"style={model_config.get('note_style')}"
                )
            except Exception as e:
                logger.warning(f"读取模型配置失败: {e}, 将使用默认配置")
        
        # 从配置中获取 style
        if model_config is None:
            model_config = _merge_model_config_with_active(None)
            _write_task_model_config(task_id, model_config)

        note_style = "simple"
        if model_config and "note_style" in model_config:
            note_style = model_config["note_style"]
            
        generator = NoteGenerator(model_config=model_config)
        
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
            update_task_status(task_id, "transcribed")
            # 重新转写场景：此前已生成过笔记时，恢复 completed 状态，
            # 避免笔记查看/导出入口因状态回退而消失（markdown 仍在）
            try:
                task_row = get_task_by_id(task_id)
            except Exception as exc:
                # This is only a post-transcription status repair. A transient
                # lookup failure must not turn an otherwise successful step
                # into a failed task.
                logger.warning(f"转写后检查任务状态失败，保留 transcribed 状态: {exc}")
                task_row = None
            if task_row and task_row.markdown:
                update_task_status(task_id, "completed")
            logger.info(f"转写完成: {task_id}")
            
        elif step == "summarize":
            # 检查转录是否完成
            transcript_file = NOTE_OUTPUT_DIR / f"{task_id}_transcript.json"
            if not transcript_file.exists():
                logger.error(f"转录文件不存在: {task_id}")
                update_task_status(task_id, "failed", error_message="转录文件不存在，请先重新执行音频转写")
                return
            
            # 如果启用了截图，删除缓存强制重新生成（确保包含截图标记）
            if screenshot:
                cache_file = NOTE_OUTPUT_DIR / f"{task_id}_markdown.md"
                if cache_file.exists():
                    cache_file.unlink()
                    logger.info(f"已删除缓存以重新生成带截图的笔记: {cache_file}")
            
            # 生成笔记
            if is_task_canceled(task_id):
                logger.info(f"任务已手动停止，跳过生成: {task_id}")
                return
            update_task_status(task_id, "summarizing")
            audio_path = generator._extract_audio(video_path, task_id)
            transcript = generator._transcribe_audio(audio_path, task_id)

            # 看题模式：采集每一页完整板书（自动去重/翻页检测）并视觉转录
            board_pages_meta = None
            if screenshot:
                try:
                    from app.services.board_capture import capture_board_pages
                    from pathlib import Path as _Path
                    pages = capture_board_pages(video_path, out_dir=str(IMAGE_OUTPUT_DIR))
                    board_pages_meta = []
                    for pg in pages:
                        text = ""
                        try:
                            text = describe_frame(pg.image_path, model_config) or ""
                        except Exception as ve:
                            logger.warning(f"板书识别失败（第{pg.index + 1}页，跳过）: {ve}")
                        board_pages_meta.append({
                            "index": pg.index,
                            "start": pg.start,
                            "end": pg.end,
                            "image_url": f"{IMAGE_BASE_URL.rstrip('/')}/{_Path(pg.image_path).name}",
                            "text": text,
                        })
                    logger.info(f"板书采集完成: {len(board_pages_meta)} 页")
                except Exception as be:
                    logger.error(f"板书采集失败，退回普通模式: {be}", exc_info=True)
                    board_pages_meta = None

            # 如果启用了截图，禁用缓存确保重新生成
            markdown = generator._summarize_text(transcript, filename, task_id, screenshot, use_cache=not screenshot, note_style=note_style, board_pages=board_pages_meta)

            # 看题模式：把 [[BOARD_PAGE i]] 占位替换为截图+板书内容；未被引用的页追加到文末
            if board_pages_meta:
                import re as _re
                referenced = set()

                def _board_quote(text: str) -> str:
                    """把板书内容排成引用块，多行时每行都要有 > 前缀"""
                    nl = chr(10)
                    lines = (text or "").splitlines() or [""]
                    quoted = nl.join("> " + line if line.strip() else ">" for line in lines)
                    return "> 📋 **板书内容**" + nl + quoted + nl

                def _replace_marker(m):
                    idx = int(m.group(1))
                    referenced.add(idx)
                    page = next((p for p in board_pages_meta if p["index"] == idx), None)
                    if not page:
                        return ""
                    nl = chr(10)
                    block = nl + nl + "![](" + page["image_url"] + ")" + nl
                    if page.get("text"):
                        block += nl + _board_quote(page["text"]) + nl
                    return block
                markdown = _re.sub(r"\[\[BOARD_PAGE (\d+)\]\]", _replace_marker, markdown)
                missing = [p for p in board_pages_meta if p["index"] not in referenced]
                if missing:
                    nl = chr(10)
                    extra = [nl * 2 + "## 附：其余板书页" + nl]
                    for p in missing:
                        start_s = int(p["start"])
                        extra.append(nl * 2 + f"### [{start_s // 60}:{start_s % 60:02d}] 第{p['index'] + 1}页" + nl)
                        extra.append(nl * 2 + "![](" + p["image_url"] + ")" + nl)
                        if p.get("text"):
                            extra.append(nl + _board_quote(p["text"]) + nl)
                    markdown = markdown + "".join(extra)
            
            markdown = normalize_note_markdown(markdown)
            
            # 后处理：插入截图
            if screenshot:
                markdown = generator._insert_screenshots(markdown, video_path, task_id)
                markdown = normalize_note_markdown(markdown)
                (NOTE_OUTPUT_DIR / f"{task_id}_markdown.md").write_text(markdown, encoding="utf-8")

            # 用户在生成期间点了停止：丢弃结果，保持 canceled 状态
            if is_task_canceled(task_id):
                logger.info(f"任务已手动停止，丢弃已生成内容: {task_id}")
                return

            update_task_status(task_id, "completed", markdown)
            logger.info(f"笔记生成完成: {task_id}")

    except Exception as e:
        # 手动停止的场景下状态已是 canceled，不要再覆盖为 failed
        if is_task_canceled(task_id):
            logger.info(f"任务已手动停止: {task_id}, step={step}")
            return
        logger.error(f"步骤执行失败: {task_id}, step={step}, 错误: {e}", exc_info=True)
        update_task_status(task_id, "failed", error_message=str(e))


@router.post("/upload")
async def upload_video(
    request: Request,
    file: Optional[UploadFile] = File(None),
    screenshot: str = Form("false"),
    note_style: str = Form("simple"),
    existing_file_path: Optional[str] = Form(None),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """上传视频文件并开始生成笔记"""
    try:
        # 转换字符串为布尔值
        enable_screenshot = screenshot.lower() == "true"
        
        # 从表单数据中获取模型配置（可选）
        model_config_dict = None
        form_data = await request.form()
        if "model_config" in form_data:
            model_config_str = form_data.get("model_config")
            if model_config_str and model_config_str.strip():
                try:
                    import json
                    model_config_dict = json.loads(model_config_str)
                    logger.info(f"收到模型配置: provider={model_config_dict.get('provider')}, model={model_config_dict.get('model')}")
                except Exception as e:
                    logger.warning(f"解析模型配置失败: {e}, 将使用默认配置")
        
        # 将 note_style 合并到 model_config 中
        if model_config_dict is None:
            model_config_dict = {}
        model_config_dict["note_style"] = note_style
        
        # 检查参数
        if not file and not existing_file_path:
            return R.error("请上传文件或选择已有文件")
            
        # 确定文件名和源路径
        source_path = None
        filename = ""
        
        if existing_file_path:
            # 验证已有文件
            source_path = Path(existing_file_path)
            if not source_path.exists():
                return R.error("选择的文件不存在")
            filename = source_path.name
        else:
            filename = file.filename

        # 检查文件扩展名
        file_ext = Path(filename).suffix.lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            return R.error(f"不支持的文件类型: {file_ext}，支持的类型: {', '.join(ALLOWED_EXTENSIONS)}")
        
        # 生成任务 ID
        task_id = str(uuid.uuid4())
        
        # 保存文件
        target_path = UPLOAD_DIR / f"{task_id}{file_ext}"
        
        if existing_file_path:
            # 如果是已有文件，直接复制或创建软链接
            # 这里为了简单和安全，我们复制文件
            import shutil
            shutil.copy2(source_path, target_path)
            logger.info(f"已复制文件: {source_path} -> {target_path}")
        else:
            # 上传文件
            with open(target_path, "wb") as f:
                content = await file.read()
                f.write(content)
        
        # 创建任务记录（状态为 pending，等待用户确认第一步）
        # 将模型配置保存到任务记录中（如果数据库支持）
        create_task(task_id=task_id, filename=filename, screenshot=enable_screenshot)
        
        # 将模型配置保存到文件系统，供后续步骤使用
        if model_config_dict:
            config_file = NOTE_OUTPUT_DIR / f"{task_id}_model_config.json"
            with open(config_file, "w", encoding="utf-8") as f:
                import json
                json.dump(model_config_dict, f, ensure_ascii=False, indent=2)
            logger.info(f"已保存模型配置到: {config_file}")
        
        # 不自动启动，等待用户确认第一步
        
        logger.info(f"任务创建成功: {filename}, task_id={task_id}")
        
        return R.success({
            "task_id": task_id,
            "filename": filename
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
            "error_message": getattr(task, "error_message", None),
            "source": getattr(task, "source", "upload"),
            "source_url": getattr(task, "source_url", None),
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        }
        
        # Normalize on read as well as during generation so notes created by an
        # older build cannot bypass the Markdown structure rules when previewed
        # or sent to the HTML/CSS PDF print page.
        if task.markdown:
            result["markdown"] = normalize_note_markdown(task.markdown)

        progress = read_note_progress(NOTE_OUTPUT_DIR, task_id)
        if progress:
            result["progress_message"] = progress.get("message")
            result["partial_markdown"] = progress.get("partial_markdown") or ""
        
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
                "error_message": getattr(task, "error_message", None),
                "source": getattr(task, "source", "upload"),
                "source_url": getattr(task, "source_url", None),
                "created_at": task.created_at.isoformat() if task.created_at else None,
            }
            for task in tasks
        ]
        return R.success(result)
    except Exception as e:
        logger.error(f"获取任务列表失败: {e}", exc_info=True)
        return R.error(f"获取任务列表失败: {str(e)}")


class RegenerateRequest(BaseModel):
    modelConfig: Optional[dict] = None  # 使用驼峰命名，避免与 Pydantic 的 model_config 冲突
    noteStyle: Optional[str] = None
    screenshot: Optional[bool] = None  # 看题模式：开启后抽取视频帧并调用视觉模型转录板书

@router.post("/task/{task_id}/retranscribe")
def retranscribe(
    task_id: str,
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """重新转写音频（使用当前设置的转写引擎重新识别）"""
    try:
        task = get_task_by_id(task_id)
        if not task:
            return R.error("任务不存在")

        transcript_file = NOTE_OUTPUT_DIR / f"{task_id}_transcript.json"
        if not transcript_file.exists():
            return R.error("该任务还没有转写结果")

        file_ext = Path(task.filename).suffix.lower()
        file_path = UPLOAD_DIR / f"{task_id}{file_ext}"
        if not file_path.exists():
            return R.error("源文件不存在，无法重新转写")

        # 删除转写缓存，强制引擎真正重新识别（否则会直接读旧结果）
        transcript_file = NOTE_OUTPUT_DIR / f"{task_id}_transcript.json"
        if transcript_file.exists():
            transcript_file.unlink()
            logger.info(f"已删除转写缓存，强制重新识别: {task_id}")

        update_task_status(task_id, "transcribing")
        background_tasks.add_task(
            run_note_task_step,
            task_id=task_id,
            video_path=str(file_path),
            filename=task.filename,
            step="transcribe",
            screenshot=bool(getattr(task, 'screenshot', 0))
        )
        logger.info(f"已触发重新转写: {task_id}")
        return R.success(msg="已开始重新转写")
    except Exception as e:
        logger.error(f"重新转写失败: {task_id}, 错误: {e}", exc_info=True)
        return R.error(f"重新转写失败: {e}")


@router.post("/task/{task_id}/regenerate")
def regenerate_note(
    task_id: str, 
    request: RegenerateRequest = Body(None),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
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
        
        # 获取截图设置（请求可覆盖：看题模式）
        screenshot = bool(getattr(task, 'screenshot', 0))
        if request and request.screenshot is not None:
            screenshot = request.screenshot
        
        # 获取模型配置（如果提供）
        model_config_dict = None
        if request and request.modelConfig:
            model_config_dict = dict(request.modelConfig)
            model_config_dict["_explicit_current_model"] = True
            logger.info(f"重新生成时收到模型配置: provider={model_config_dict.get('provider')}, model={model_config_dict.get('model')}")
        
        # 如果没有提供模型配置，尝试从文件读取（兼容旧任务）
        if not model_config_dict:
            config_file = NOTE_OUTPUT_DIR / f"{task_id}_model_config.json"
            if config_file.exists():
                try:
                    import json
                    with open(config_file, "r", encoding="utf-8") as f:
                        model_config_dict = json.load(f)
                    logger.info(
                        "从文件加载模型配置: "
                        f"provider={model_config_dict.get('provider')}, "
                        f"type={model_config_dict.get('provider_type')}, "
                        f"model={model_config_dict.get('model')}, "
                        f"style={model_config_dict.get('note_style')}"
                    )
                except Exception as e:
                    logger.warning(f"读取模型配置失败: {e}")
        
        # 更新 note_style
        if request and request.noteStyle:
            if model_config_dict is None:
                model_config_dict = {}
            model_config_dict["note_style"] = request.noteStyle
        
        # 保存或更新模型配置到文件
        if model_config_dict:
            config_file = NOTE_OUTPUT_DIR / f"{task_id}_model_config.json"
            with open(config_file, "w", encoding="utf-8") as f:
                import json
                json.dump(model_config_dict, f, ensure_ascii=False, indent=2)
            logger.info(f"已保存模型配置到: {config_file}")
        
        # 删除旧的笔记缓存，强制重新生成
        cache_file = NOTE_OUTPUT_DIR / f"{task_id}_markdown.md"
        if cache_file.exists():
            cache_file.unlink()
            logger.info(f"已删除旧笔记缓存: {cache_file}")
        
        # 更新状态为 summarizing
        update_task_status(task_id, "summarizing")
        
        # 在后台重新生成笔记（模型配置会在 run_note_task_step 中读取）
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
    modelConfig: Optional[dict] = None
    noteStyle: Optional[str] = None
    screenshot: Optional[bool] = None  # 看题模式覆盖（不传则沿用任务创建时的设置）

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
        if request.modelConfig:
            model_config = dict(request.modelConfig)
            model_config["_explicit_current_model"] = True
            if request.noteStyle:
                model_config["note_style"] = request.noteStyle
            _write_task_model_config(task_id, model_config)
        
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
            if task.status not in {"transcribing", "transcribed"} and not transcript_file.exists():
                return R.error("请先完成音频转写")
            if request.screenshot is not None:
                screenshot = request.screenshot
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


@router.get("/task/{task_id}/export_pdf")
def export_pdf(task_id: str):
    """使用 ReportLab 直接导出可复制文本的 PDF。"""
    from app.services.pdf_export import render_note_pdf

    task = get_task_by_id(task_id)
    if not task:
        return R.error("任务不存在")
    if not task.markdown:
        return R.error("笔记内容不存在")

    try:
        title = Path(task.filename).stem.strip() or "笔记"
        with tempfile.TemporaryDirectory(prefix="video-note-pdf-") as temp_dir:
            pdf_path = Path(temp_dir) / "note.pdf"
            render_note_pdf(task.markdown, title, pdf_path, NOTE_OUTPUT_DIR)
            pdf_data = pdf_path.read_bytes()
        safe_name = re.sub(r"[\\/:*?\"<>|]+", "_", title).strip() or "note"
        download_name = f"{safe_name}_note.pdf"
        return Response(
            content=pdf_data,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename*=utf-8''{quote(download_name)}"
            },
        )
    except Exception as exc:
        logger.error(f"导出 PDF 失败: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content=R.error("导出 PDF 失败，请查看后端日志后重试"),
        )

@router.post("/task/{task_id}/cancel")
def cancel_task(task_id: str):
    """手动停止正在处理的任务

    只修改数据库状态为 canceled，由后台线程在取消检查点自行中断：
    - 流式生成循环（每 50 个事件检查一次）
    - 长文分块循环（每段开始前）
    - 各步骤的进入/收尾守卫
    进度文件保留，前端可继续展示已生成的部分内容。
    """
    try:
        task = get_task_by_id(task_id)
        if not task:
            return R.error("任务不存在")

        if task.status in ("completed", "failed", "canceled"):
            return R.success(None, msg="任务已结束，无需停止")

        update_task_status(task_id, "canceled", error_message="已手动停止生成")
        cancel_jobs_for_task(task_id)
        logger.info(f"任务已手动停止: {task_id}, 原状态: {task.status}")
        return R.success(None, msg="任务已停止")
    except Exception as e:
        logger.error(f"停止任务失败: {task_id}, {e}", exc_info=True)
        return R.error(f"停止任务失败: {str(e)}")


@router.delete("/task/{task_id}")
def delete_task(task_id: str):
    """删除任务"""
    try:
        import shutil
        
        # 检查任务是否存在
        task = get_task_by_id(task_id)
        if not task:
            return R.error("任务不存在")
        
        # 删除数据库记录
        cancel_jobs_for_task(task_id)
        delete_task_by_id(task_id)
        
        # 删除相关文件
        try:
            # 删除上传的文件
            upload_file = UPLOAD_DIR / f"{task_id}.mp4"
            if upload_file.exists():
                upload_file.unlink()
            
            # 删除输出文件
            audio_file = NOTE_OUTPUT_DIR / f"{task_id}_audio.wav"
            if audio_file.exists():
                audio_file.unlink()
            
            markdown_file = NOTE_OUTPUT_DIR / f"{task_id}_markdown.md"
            if markdown_file.exists():
                markdown_file.unlink()

            # 兼容清理由旧版持久化导出流程留下的公开 PDF。
            export_file = NOTE_OUTPUT_DIR / f"{task_id}_export.pdf"
            if export_file.exists():
                export_file.unlink()
            
            transcript_file = NOTE_OUTPUT_DIR / f"{task_id}_transcript.json"
            if transcript_file.exists():
                transcript_file.unlink()
            
            # 删除截图目录
            screenshot_dir = NOTE_OUTPUT_DIR / "screenshots"
            if screenshot_dir.exists():
                # 删除该任务相关的截图
                for screenshot_file in screenshot_dir.glob(f"{task_id}_*.jpg"):
                    screenshot_file.unlink()
            
            # 删除静态文件目录中的截图（如果存在）
            # 注意：STATIC_DIR 可能未定义，这里只删除 NOTE_OUTPUT_DIR 中的截图
                    
        except Exception as e:
            logger.warning(f"删除任务文件失败（任务记录已删除）: {e}")
        
        logger.info(f"任务 {task_id} 已删除")
        return R.success(None, msg="任务删除成功")
        
    except Exception as e:
        logger.error(f"删除任务失败: {e}", exc_info=True)
        return R.error(f"删除任务失败: {str(e)}")
