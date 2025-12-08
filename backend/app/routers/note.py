import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException, Body, Request
from pydantic import BaseModel
from fastapi.responses import JSONResponse

from app.db.video_task_dao import create_task, get_task_by_id, get_all_tasks, update_task_status, delete_task_by_id
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
        # 尝试读取模型配置
        model_config = None
        config_file = NOTE_OUTPUT_DIR / f"{task_id}_model_config.json"
        if config_file.exists():
            try:
                import json
                with open(config_file, "r", encoding="utf-8") as f:
                    model_config = json.load(f)
                logger.info(f"加载模型配置: {model_config}")
            except Exception as e:
                logger.warning(f"读取模型配置失败: {e}, 将使用默认配置")
        
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
            
            # 清理 AI 输出中的思考过程标签（redacted_reasoning）
            import re
            markdown = re.sub(r'<think>.*?</think>', '', markdown, flags=re.DOTALL | re.IGNORECASE)
            markdown = re.sub(r'<think>[\s\S]*?</think>', '', markdown, flags=re.IGNORECASE)
            # 清理多余的空白行
            markdown = re.sub(r'\n\s*\n\s*\n', '\n\n', markdown)
            
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
    request: Request,
    file: UploadFile = File(...),
    screenshot: str = Form("false"),
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
        # 将模型配置保存到任务记录中（如果数据库支持）
        create_task(task_id=task_id, filename=file.filename, screenshot=enable_screenshot)
        
        # 将模型配置保存到文件系统，供后续步骤使用
        if model_config_dict:
            config_file = NOTE_OUTPUT_DIR / f"{task_id}_model_config.json"
            with open(config_file, "w", encoding="utf-8") as f:
                import json
                json.dump(model_config_dict, f, ensure_ascii=False, indent=2)
            logger.info(f"已保存模型配置到: {config_file}")
        
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


class RegenerateRequest(BaseModel):
    modelConfig: Optional[dict] = None  # 使用驼峰命名，避免与 Pydantic 的 model_config 冲突

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
        
        # 获取截图设置
        screenshot = bool(getattr(task, 'screenshot', 0))
        
        # 获取模型配置（如果提供）
        model_config_dict = None
        if request and request.modelConfig:
            model_config_dict = request.modelConfig
            logger.info(f"重新生成时收到模型配置: provider={model_config_dict.get('provider')}, model={model_config_dict.get('model')}")
        
        # 如果没有提供模型配置，尝试从文件读取（兼容旧任务）
        if not model_config_dict:
            config_file = NOTE_OUTPUT_DIR / f"{task_id}_model_config.json"
            if config_file.exists():
                try:
                    import json
                    with open(config_file, "r", encoding="utf-8") as f:
                        model_config_dict = json.load(f)
                    logger.info(f"从文件加载模型配置: {model_config_dict}")
                except Exception as e:
                    logger.warning(f"读取模型配置失败: {e}")
        
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


@router.get("/task/{task_id}/export_pdf")
def export_pdf(task_id: str):
    """导出笔记为 PDF（可复制文本）- 使用 reportlab"""
    try:
        from fastapi.responses import FileResponse
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
        from reportlab.lib.enums import TA_LEFT, TA_CENTER
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        import re
        import base64
        from io import BytesIO
        import os
        
        # 检查任务是否存在
        task = get_task_by_id(task_id)
        if not task:
            return R.error("任务不存在")
        
        if not task.markdown:
            return R.error("笔记内容不存在")
        
        # 注册中文字体（使用系统字体或默认字体）
        try:
            # 尝试注册系统中文字体（macOS 优先）
            font_paths = [
                '/System/Library/Fonts/STHeiti Medium.ttc',  # macOS 黑体 Medium
                '/System/Library/Fonts/STHeiti Light.ttc',  # macOS 黑体 Light
                '/System/Library/Fonts/Supplemental/Songti.ttc',  # macOS 宋体
                '/System/Library/Fonts/PingFang.ttc',  # macOS 苹方
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',  # Linux
                'C:/Windows/Fonts/simsun.ttc',  # Windows 宋体
                'C:/Windows/Fonts/simhei.ttf',  # Windows 黑体
            ]
            
            chinese_font_name = 'ChineseFont'
            font_registered = False
            
            for font_path in font_paths:
                if os.path.exists(font_path):
                    try:
                        # 对于 .ttc 文件，需要指定字体索引（通常是 0）
                        if font_path.endswith('.ttc'):
                            # TTC 文件可能包含多个字体，尝试索引 0
                            pdfmetrics.registerFont(TTFont(chinese_font_name, font_path, subfontIndex=0))
                        else:
                            pdfmetrics.registerFont(TTFont(chinese_font_name, font_path))
                        font_registered = True
                        logger.info(f"成功注册中文字体: {font_path}")
                        break
                    except Exception as e:
                        logger.warning(f"注册字体失败 {font_path}: {e}")
                        # 如果 subfontIndex 失败，尝试不使用索引
                        try:
                            pdfmetrics.registerFont(TTFont(chinese_font_name, font_path))
                            font_registered = True
                            logger.info(f"成功注册中文字体（无索引）: {font_path}")
                            break
                        except Exception as e2:
                            logger.warning(f"注册字体失败（无索引） {font_path}: {e2}")
                            continue
            
            # 如果没有找到系统字体，使用 reportlab 的默认字体（可能不支持中文）
            if not font_registered:
                logger.warning("未找到中文字体，使用默认字体（可能不支持中文）")
                chinese_font_name = 'Helvetica'
        except Exception as e:
            logger.warning(f"字体注册失败: {e}，使用默认字体")
            chinese_font_name = 'Helvetica'
        
        # 创建 PDF
        pdf_path = NOTE_OUTPUT_DIR / f"{task_id}_export.pdf"
        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        # 创建样式（使用中文字体）
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontName=chinese_font_name,
            fontSize=18,
            textColor='#333333',
            spaceAfter=12,
        )
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontName=chinese_font_name,
            fontSize=14,
            textColor='#333333',
            spaceAfter=8,
            spaceBefore=12,
        )
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontName=chinese_font_name,
            fontSize=11,
            textColor='#333333',
            leading=16,
            spaceAfter=6,
        )
        
        # 构建内容
        story = []
        
        # 解析 markdown 内容
        lines = task.markdown.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            if not stripped:
                story.append(Spacer(1, 6))
                i += 1
                continue
            
            # 处理标题
            if stripped.startswith('###'):
                text = stripped[3:].strip()
                if text:
                    story.append(Paragraph(text, heading_style))
            elif stripped.startswith('##'):
                text = stripped[2:].strip()
                if text:
                    story.append(Paragraph(text, title_style))
            elif stripped.startswith('#'):
                text = stripped[1:].strip()
                if text:
                    story.append(Paragraph(text, title_style))
            # 处理图片
            elif '![](' in stripped:
                match = re.search(r'!\[\]\(([^)]+)\)', stripped)
                if match:
                    img_path = match.group(1)
                    try:
                        from PIL import Image as PILImage
                        
                        # 计算可用页面大小（A4 减去边距）
                        available_width = A4[0] - 4*cm  # 左右各 2cm
                        available_height = A4[1] - 4*cm  # 上下各 2cm
                        max_width = available_width
                        max_height = available_height * 0.6  # 图片最多占页面高度的 60%
                        
                        img_obj = None
                        # 处理 base64 图片
                        if img_path.startswith('data:'):
                            # 提取 base64 数据
                            parts = img_path.split(',', 1)
                            if len(parts) == 2:
                                base64_data = parts[1]
                                img_data = base64.b64decode(base64_data)
                                img_obj = PILImage.open(BytesIO(img_data))
                        # 处理本地文件路径
                        elif '/api/note_results/screenshots/' in img_path or '/screenshots/' in img_path:
                            filename = img_path.split('/')[-1]
                            local_path = NOTE_OUTPUT_DIR / "screenshots" / filename
                            if local_path.exists():
                                img_obj = PILImage.open(str(local_path))
                        
                        if img_obj:
                            # 获取原始尺寸
                            orig_width, orig_height = img_obj.size
                            
                            # 计算缩放比例，确保图片适应页面
                            width_ratio = max_width / orig_width
                            height_ratio = max_height / orig_height
                            ratio = min(width_ratio, height_ratio, 1.0)  # 不超过原始大小
                            
                            # 计算新尺寸
                            new_width = orig_width * ratio
                            new_height = orig_height * ratio
                            
                            # 创建临时文件保存调整后的图片
                            temp_buffer = BytesIO()
                            img_obj.save(temp_buffer, format='JPEG', quality=85)
                            temp_buffer.seek(0)
                            
                            # 添加到 PDF
                            img = Image(temp_buffer, width=new_width, height=new_height)
                            story.append(Spacer(1, 6))
                            story.append(img)
                            story.append(Spacer(1, 6))
                    except Exception as e:
                        logger.warning(f"无法加载图片 {img_path}: {e}")
            # 处理列表项
            elif stripped.startswith('-') or stripped.startswith('*'):
                text = stripped[1:].strip()
                if text:
                    # 转义 HTML 特殊字符
                    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    story.append(Paragraph(f"• {text}", normal_style))
            # 处理普通文本
            else:
                # 转义 HTML 特殊字符
                text = stripped.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                if text:
                    story.append(Paragraph(text, normal_style))
            
            i += 1
        
        # 生成 PDF
        doc.build(story)
        
        return FileResponse(
            pdf_path,
            media_type='application/pdf',
            filename=f"{task.filename.replace('.', '_')}_note.pdf"
        )
        
    except ImportError as e:
        logger.error(f"PDF 导出依赖未安装: {e}")
        return R.error("PDF 导出功能需要安装 reportlab 库。请运行: pip install reportlab")
    except Exception as e:
        logger.error(f"导出 PDF 失败: {e}", exc_info=True)
        return R.error(f"导出 PDF 失败: {str(e)}")


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
