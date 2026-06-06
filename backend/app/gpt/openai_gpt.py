import os
import re
from typing import Iterable

from openai import APIConnectionError, APIStatusError, APITimeoutError

from app.gpt.base import GPT
from app.models.transcriber_model import TranscriptResult
from app.services.openai_client import create_openai_client
from app.utils.logger import get_logger

logger = get_logger(__name__)


class OpenAIGPT(GPT):
    """Generate video notes through an OpenAI-compatible chat API."""

    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.model = model or os.getenv("GPT_MODEL", "gpt-4o-mini")

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not configured")

        self.client = create_openai_client(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=600.0,
            max_retries=0,
        )

        logger.info(f"Initialized OpenAI-compatible GPT: model={self.model}")

    def summarize(
        self,
        transcript: TranscriptResult,
        filename: str = "",
        screenshot: bool = False,
        note_style: str = "simple",
    ) -> str:
        logger.info(f"Start note generation (screenshot={screenshot}, style={note_style})")

        prompt = self._build_prompt(transcript, filename, screenshot, note_style)
        system_content = (
            "你是一个专业的视频笔记助手，擅长把视频转写内容整理成清晰、有条理、信息丰富的中文 Markdown 笔记。"
        )
        if screenshot:
            system_content += (
                "\n\n重要：当用户要求添加截图标记时，必须在相关章节后插入 "
                "`*Screenshot-[mm:ss]` 格式的标记，不能忽略。"
            )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                stream=True,
            )

            markdown = self._read_streaming_markdown(response).strip()
            if not markdown:
                raise RuntimeError("AI did not return note content. Please check whether this model supports chat streaming.")

            logger.info("Note generation completed")

            if screenshot:
                pattern = r"\*Screenshot-\[(\d{2}):(\d{2})\]|\*Screenshot-(\d{2}):(\d{2})"
                matches = list(re.finditer(pattern, markdown))
                if matches:
                    logger.info(f"Generated note contains {len(matches)} screenshot markers")
                else:
                    logger.warning("Screenshot was enabled, but no screenshot markers were found in the note")

            return markdown
        except Exception as exc:
            friendly_error = self._friendly_error(exc)
            logger.error(f"Note generation failed: {friendly_error}", exc_info=True)
            raise RuntimeError(friendly_error) from exc

    def _read_streaming_markdown(self, response: Iterable) -> str:
        chunks = []
        for event in response:
            if not getattr(event, "choices", None):
                continue
            delta = event.choices[0].delta
            content = getattr(delta, "content", None)
            if content:
                chunks.append(content)
        return "".join(chunks)

    def _friendly_error(self, exc: Exception) -> str:
        message = str(exc).strip()
        cause = getattr(exc, "__cause__", None)
        cause_message = str(cause).strip() if cause else ""
        combined = " ".join(part for part in [message, cause_message] if part)
        lower_message = combined.lower()

        if isinstance(exc, APITimeoutError) or "timeout" in lower_message:
            return "AI note generation timed out. Try simple mode, a faster model, or regenerate later."

        if isinstance(exc, APIConnectionError) or "server disconnected without sending a response" in lower_message:
            return (
                "AI provider disconnected before returning the note. "
                "The provider dashboard may still show token usage, but AInote did not receive a complete result. "
                "Please regenerate with simple mode or use a more stable model/provider."
            )

        if isinstance(exc, APIStatusError):
            return f"AI provider returned HTTP {exc.status_code}: {message}"

        return f"AI note generation failed: {message or type(exc).__name__}"

    def _build_prompt(
        self,
        transcript: TranscriptResult,
        filename: str,
        screenshot: bool = False,
        note_style: str = "simple",
    ) -> str:
        segment_text = ""
        for segment in transcript.segments:
            mm = int(segment.start // 60)
            ss = int(segment.start % 60)
            segment_text += f"[{mm:02d}:{ss:02d}] {segment.text}\n"

        screenshot_instruction = ""
        if screenshot:
            screenshot_instruction = """

8. 截图占位符：
   必须在笔记中插入适量截图标记，建议至少 3 个，用于从视频中提取关键画面。
   格式必须是 `*Screenshot-[mm:ss]`，例如 `*Screenshot-[01:23]`。
   截图标记应放在对应章节内容之后，并与正文空行分隔。
"""

        style_instruction = {
            "detailed": """
风格要求：详细模式
- 尽量保留视频中的例子、数据、参数和具体步骤。
- 对关键概念做深入解释，让笔记可以替代重新观看视频。
- 使用多级标题和清晰列表组织内容。
""",
            "academic": """
风格要求：学术模式
- 使用正式、严谨、客观的语言。
- 强调因果关系、论证过程和理论依据。
- 准确保留专业术语，并组织为摘要、背景、核心论点、论证和结论等结构。
""",
            "creative": """
风格要求：创意模式
- 语言可以更生动，但不能丢失事实。
- 突出高光时刻、关键观点和启发。
- 可以使用更有可读性的标题和表达方式。
""",
        }.get(
            note_style,
            """
风格要求：简洁模式
- 直击要点，去除冗余信息。
- 使用短句和项目符号，便于快速浏览。
- 保留核心概念、结论和关键步骤。
""",
        )

        return f"""请根据以下视频转写内容生成结构化的 Markdown 笔记。

文件名称: {filename}

语言要求：
- 笔记必须使用中文撰写。
- 专有名词、技术术语、品牌名和人名可以保留英文。

视频分段：
---
{segment_text}
---

任务：
1. 尽可能完整地记录相关细节，保证内容全面。
2. 省略广告、填充词、问候语和无关内容。
3. 保留重要事实、示例、结论和建议。
4. 使用标题、列表等 Markdown 格式，保持段落简短。
5. 视频中提到的数学公式必须保留，并用 LaTeX 语法呈现。
6. 可以在主要章节后添加时间标记，格式为 `*Content-[mm:ss]`。
{screenshot_instruction}
{style_instruction}

输出说明：
- 只返回最终 Markdown 内容。
- 不要把输出包裹在代码块中。
- 在笔记末尾添加一个“AI 总结”部分，概括整个视频的核心内容。

现在开始生成笔记："""
