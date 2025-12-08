import json
import os
import re
import subprocess
from pathlib import Path
from typing import Optional, List, Tuple

from app.db.video_task_dao import update_task_status
from app.gpt.openai_gpt import OpenAIGPT
from app.models.notes_model import NoteResult
from app.transcriber.transcriber_provider import get_transcriber
from app.utils.logger import get_logger
from app.utils.video_helper import generate_screenshot
from app.utils.ffmpeg_helper import get_ffmpeg_path

logger = get_logger(__name__)

NOTE_OUTPUT_DIR = Path(os.getenv("NOTE_OUTPUT_DIR", "note_results"))
NOTE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 截图输出目录 - 放在 note_results 目录下
IMAGE_OUTPUT_DIR = NOTE_OUTPUT_DIR / "screenshots"
IMAGE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
# 使用相对路径，因为截图和笔记在同一目录下
IMAGE_BASE_URL = os.getenv("IMAGE_BASE_URL", "/api/note_results/screenshots")


class NoteGenerator:
    """笔记生成器"""
    
    def __init__(self, model_config: dict = None):
        self.transcriber = get_transcriber()
        self.gpt = None  # 延迟初始化，避免启动时就需要 API key
        self.model_config = model_config  # 保存模型配置
        logger.info("NoteGenerator 初始化完成")
    
    def _get_gpt(self):
        """延迟初始化 GPT 实例"""
        if self.gpt is None:
            if self.model_config:
                # 使用提供的模型配置
                provider = self.model_config.get('provider', 'openai')
                api_key = self.model_config.get('api_key', '')
                base_url = self.model_config.get('base_url', '')
                model = self.model_config.get('model', '')
                
                logger.info(f"使用模型配置: provider={provider}, model={model}, base_url={base_url}")
                
                # 根据提供商创建对应的 GPT 实例
                if provider == 'ollama':
                    # Ollama 使用 OpenAI 兼容接口
                    # 确保 base_url 正确
                    if not base_url or base_url.strip() == '':
                        base_url = 'http://127.0.0.1:11434/v1'
                    elif not base_url.endswith('/v1'):
                        # 如果 base_url 不包含 /v1，添加它
                        base_url = base_url.rstrip('/') + '/v1'
                    
                    logger.info(f"初始化 Ollama GPT: base_url={base_url}, model={model}")
                    self.gpt = OpenAIGPT(
                        api_key=api_key or 'ollama',  # Ollama 不需要真实的 API key
                        base_url=base_url,
                        model=model
                    )
                else:
                    # 其他提供商使用 OpenAI 兼容接口
                    logger.info(f"初始化 {provider} GPT: model={model}")
                    self.gpt = OpenAIGPT(
                        api_key=api_key,
                        base_url=base_url,
                        model=model
                    )
            else:
                # 使用默认配置
                logger.warning("未提供模型配置，使用默认配置")
                self.gpt = OpenAIGPT()
        return self.gpt
    
    def generate(
        self,
        video_path: str,
        filename: str,
        task_id: str,
        screenshot: bool = False
    ) -> Optional[NoteResult]:
        """
        生成笔记的主流程
        
        :param video_path: 视频文件路径
        :param filename: 原始文件名
        :param task_id: 任务 ID
        :return: NoteResult 对象
        """
        try:
            logger.info(f"开始生成笔记 (task_id={task_id})")
            update_task_status(task_id, "processing")
            
            # 1. 提取音频
            audio_path = self._extract_audio(video_path, task_id)
            
            # 2. 转写音频
            update_task_status(task_id, "transcribing")
            transcript = self._transcribe_audio(audio_path, task_id)
            
            # 3. GPT 生成笔记
            update_task_status(task_id, "summarizing")
            markdown = self._summarize_text(transcript, filename, task_id, screenshot)
            
            # 清理 AI 输出中的思考过程标签（redacted_reasoning）
            import re
            markdown = re.sub(r'<think>.*?</think>', '', markdown, flags=re.DOTALL | re.IGNORECASE)
            markdown = re.sub(r'<think>[\s\S]*?</think>', '', markdown, flags=re.IGNORECASE)
            # 清理多余的空白行
            markdown = re.sub(r'\n\s*\n\s*\n', '\n\n', markdown)
            
            # 4. 后处理：插入截图
            if screenshot:
                markdown = self._insert_screenshots(markdown, video_path)
            
            # 5. 保存结果
            update_task_status(task_id, "completed", markdown)
            
            logger.info(f"笔记生成成功 (task_id={task_id})")
            return NoteResult(
                markdown=markdown,
                transcript=transcript,
                filename=filename
            )
            
        except Exception as exc:
            logger.error(f"生成笔记失败 (task_id={task_id}): {exc}", exc_info=True)
            update_task_status(task_id, "failed")
            raise
    
    def _extract_audio(self, video_path: str, task_id: str) -> str:
        """从视频中提取音频"""
        logger.info(f"提取音频: {video_path}")
        
        audio_path = NOTE_OUTPUT_DIR / f"{task_id}_audio.wav"
        
        try:
            # 使用 ffmpeg 命令提取音频
            ffmpeg_path = get_ffmpeg_path()
            command = [
                ffmpeg_path,
                "-i", str(video_path),
                "-acodec", "pcm_s16le",
                "-ac", "1",
                "-ar", "16000",
                "-y",  # 覆盖已存在文件
                str(audio_path)
            ]
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True
            )
            
            logger.info(f"音频提取完成: {audio_path}")
            return str(audio_path)
            
        except subprocess.CalledProcessError as e:
            logger.error(f"音频提取失败: {e.stderr}")
            raise Exception(f"音频提取失败: {e.stderr}")
        except Exception as e:
            logger.error(f"音频提取失败: {e}")
            raise
    
    def _transcribe_audio(self, audio_path: str, task_id: str):
        """转录音频"""
        logger.info(f"开始转录: {audio_path}")
        
        # 检查缓存
        cache_file = NOTE_OUTPUT_DIR / f"{task_id}_transcript.json"
        if cache_file.exists():
            logger.info(f"使用缓存: {cache_file}")
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                from app.models.transcriber_model import TranscriptResult, TranscriptSegment
                segments = [TranscriptSegment(**seg) for seg in data['segments']]
                return TranscriptResult(
                    language=data['language'],
                    full_text=data['full_text'],
                    segments=segments
                )
        
        # 执行转录
        transcript = self.transcriber.transcript(audio_path)
        
        # 保存缓存
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump({
                'language': transcript.language,
                'full_text': transcript.full_text,
                'segments': [
                    {
                        'start': seg.start,
                        'end': seg.end,
                        'text': seg.text
                    }
                    for seg in transcript.segments
                ]
            }, f, ensure_ascii=False, indent=2)
        
        logger.info("转录完成")
        return transcript
    
    def _summarize_text(self, transcript, filename: str, task_id: str, screenshot: bool = False, use_cache: bool = True) -> str:
        """使用 GPT 生成笔记"""
        logger.info(f"开始生成笔记... (screenshot={screenshot}, use_cache={use_cache})")
        
        # 检查缓存（如果允许使用缓存）
        cache_file = NOTE_OUTPUT_DIR / f"{task_id}_markdown.md"
        if use_cache and cache_file.exists():
            # 如果启用了截图但缓存中没有截图标记，强制重新生成
            if screenshot:
                cached_content = cache_file.read_text(encoding='utf-8')
                import re
                pattern = r"\*Screenshot-\[(\d{2}):(\d{2})\]|\*Screenshot-(\d{2}):(\d{2})"
                if not re.search(pattern, cached_content):
                    logger.info(f"缓存中没有截图标记，强制重新生成 (screenshot={screenshot})")
                    cache_file.unlink()
                else:
                    logger.info(f"使用缓存: {cache_file}")
                    return cached_content
            else:
                logger.info(f"使用缓存: {cache_file}")
                return cache_file.read_text(encoding='utf-8')
        
        # 调用 GPT（延迟初始化）
        gpt = self._get_gpt()
        markdown = gpt.summarize(transcript, filename, screenshot)
        
        # 清理 AI 输出中的思考过程标签（redacted_reasoning）
        # 删除所有 <think>...</think> 标签及其内容
        import re
        markdown = re.sub(r'<think>.*?</think>', '', markdown, flags=re.DOTALL | re.IGNORECASE)
        # 也处理可能的多行格式
        markdown = re.sub(r'<think>[\s\S]*?</think>', '', markdown, flags=re.IGNORECASE)
        # 清理多余的空白行
        markdown = re.sub(r'\n\s*\n\s*\n', '\n\n', markdown)
        
        # 保存缓存
        cache_file.write_text(markdown, encoding='utf-8')
        
        logger.info("笔记生成完成")
        return markdown
    
    def _insert_screenshots(self, markdown: str, video_path: str, task_id: str = None) -> str:
        """
        扫描 Markdown 文本中所有 Screenshot 标记，并替换为实际生成的截图链接
        
        :param markdown: 含有 *Screenshot-[mm:ss] 标记的 Markdown 文本
        :param video_path: 本地视频文件路径
        :param task_id: 任务 ID，用于更新缓存文件
        :return: 替换后的 Markdown 字符串
        """
        # 先修复旧的图片路径（如果存在），并清理格式问题
        # 修复所有旧的图片路径
        markdown = re.sub(
            r'!\[\]\(/static/screenshots/([^)]+)\)',
            lambda m: f"![]({IMAGE_BASE_URL.rstrip('/')}/{m.group(1)})",
            markdown
        )
        
        matches = self._extract_screenshot_timestamps(markdown)
        if not matches:
            logger.info("未找到截图标记")
            # 清理可能存在的格式问题（图片后的 * 符号）
            markdown = re.sub(r'!\[\]\([^)]+\)\*', lambda m: m.group(0).rstrip('*'), markdown)
            return markdown
        
        logger.info(f"找到 {len(matches)} 个截图标记，开始生成截图...")
        
        for idx, (marker, timestamp) in enumerate(matches):
            try:
                img_path = generate_screenshot(str(video_path), str(IMAGE_OUTPUT_DIR), timestamp, idx)
                filename = Path(img_path).name
                # 直接生成正确的 URL（截图在 note_results/screenshots 目录下）
                img_url = f"{IMAGE_BASE_URL.rstrip('/')}/{filename}"
                
                # 智能替换：在标记所在位置插入图片，保持原有结构
                # 处理带 * 的标记
                marker_with_star = f"{marker}*"
                if marker_with_star in markdown:
                    # 替换带 * 的标记，在标记位置插入图片
                    markdown = markdown.replace(marker_with_star, f"\n\n![]({img_url})\n\n", 1)
                else:
                    # 替换标记：找到标记所在位置，在该位置插入图片
                    # 如果标记在单独一行，直接替换该行
                    # 如果标记在行尾，在该行后插入图片
                    lines = markdown.split('\n')
                    new_lines = []
                    replaced = False
                    
                    for i, line in enumerate(lines):
                        if not replaced and marker in line:
                            # 找到包含标记的行
                            cleaned_line = line.replace(marker, '').strip()
                            
                            if cleaned_line:
                                # 行中还有其他内容：保留内容，在下一行插入图片
                                new_lines.append(cleaned_line)
                                new_lines.append('')  # 空行
                                new_lines.append(f"![]({img_url})")
                            else:
                                # 这行只有标记：直接替换为图片
                                new_lines.append(f"![]({img_url})")
                            
                            # 检查下一行是否是空行或新章节，如果不是则添加空行
                            if i + 1 < len(lines):
                                next_line = lines[i + 1].strip()
                                if next_line and not next_line.startswith('#'):
                                    new_lines.append('')  # 添加空行分隔
                            else:
                                new_lines.append('')  # 文件末尾也添加空行
                            
                            replaced = True
                        else:
                            new_lines.append(line)
                    
                    if not replaced:
                        # 如果没找到，使用简单替换
                        markdown = markdown.replace(marker, f"\n\n![]({img_url})\n\n", 1)
                    else:
                        markdown = '\n'.join(new_lines)
                
                logger.info(f"截图已插入: {img_url} (时间戳: {timestamp}秒)")
            except Exception as exc:
                logger.error(f"生成截图失败 (timestamp={timestamp}): {exc}")
                # 失败时保留原标记
                continue
        
        # 清理多余的换行和格式问题
        markdown = re.sub(r'\n{4,}', '\n\n\n', markdown)  # 将4个以上连续换行替换为3个（保留章节间的分隔）
        markdown = re.sub(r'!\[\]\([^)]+\)\*', lambda m: m.group(0).rstrip('*'), markdown)  # 清理图片后的 * 符号
        
        # 最后修复所有图片路径（确保都是新路径，包括刚生成的）
        # 这是关键步骤：修复所有可能的旧路径格式
        def fix_all_image_paths(text):
            """修复所有图片路径，确保都使用新路径"""
            # 1. 修复 /static/screenshots/ 路径
            text = re.sub(
                r'!\[\]\(/static/screenshots/([^)]+)\)',
                lambda m: f"![]({IMAGE_BASE_URL.rstrip('/')}/{m.group(1)})",
                text
            )
            # 2. 修复任何包含 screenshots 但路径不对的图片
            def fix_path(match):
                full_path = match.group(1)
                filename = Path(full_path).name
                # 如果路径不是新路径，统一修复
                if '/static/screenshots/' in full_path or not full_path.startswith('/api/note_results/screenshots/'):
                    return f"![]({IMAGE_BASE_URL.rstrip('/')}/{filename})"
                return match.group(0)  # 已经是正确路径，不修改
            
            text = re.sub(
                r'!\[\]\((.*?screenshots.*?/([^/)]+))\)',
                fix_path,
                text
            )
            return text
        
        markdown = fix_all_image_paths(markdown)
        
        # 最终检查：确保所有图片路径都是正确的
        logger.info(f"最终图片路径检查: IMAGE_BASE_URL={IMAGE_BASE_URL}")
        old_paths = re.findall(r'!\[\]\(/static/screenshots/[^)]+\)', markdown)
        if old_paths:
            logger.warning(f"发现 {len(old_paths)} 个旧路径，正在强制修复...")
            # 强制修复所有旧路径
            markdown = re.sub(
                r'!\[\]\(/static/screenshots/([^)]+)\)',
                lambda m: f"![]({IMAGE_BASE_URL.rstrip('/')}/{m.group(1)})",
                markdown
            )
            # 再次检查
            remaining = len(re.findall(r'!\[\]\(/static/screenshots/[^)]+\)', markdown))
            if remaining == 0:
                logger.info("✓ 所有旧路径已修复")
            else:
                logger.error(f"⚠ 仍有 {remaining} 个旧路径未修复！")
        
        # 如果提供了 task_id，更新缓存文件
        if task_id:
            cache_file = NOTE_OUTPUT_DIR / f"{task_id}_markdown.md"
            cache_file.write_text(markdown, encoding='utf-8')
            logger.info(f"已更新缓存文件: {cache_file}")
        
        return markdown
    
    @staticmethod
    def _extract_screenshot_timestamps(markdown: str) -> List[Tuple[str, int]]:
        """
        从 Markdown 文本中提取所有 '*Screenshot-[mm:ss]' 或 '*Screenshot-mm:ss' 标记
        
        :param markdown: 原始 Markdown 文本
        :return: 标记与对应时间戳秒数的列表 [(标记文本, 时间戳秒数), ...]
        """
        # 匹配 *Screenshot-[mm:ss] 或 *Screenshot-mm:ss 格式
        pattern = r"\*Screenshot-\[(\d{2}):(\d{2})\]|\*Screenshot-(\d{2}):(\d{2})"
        results: List[Tuple[str, int]] = []
        for match in re.finditer(pattern, markdown):
            # group(1) 和 group(2) 是 [mm:ss] 格式，group(3) 和 group(4) 是 mm:ss 格式
            mm = match.group(1) or match.group(3)
            ss = match.group(2) or match.group(4)
            if mm and ss:
                total_seconds = int(mm) * 60 + int(ss)
                results.append((match.group(0), total_seconds))
        return results

