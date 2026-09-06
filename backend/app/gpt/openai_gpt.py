import os
import re
from typing import Callable, Iterable, List, Optional, Sequence

from openai import APIConnectionError, APIStatusError, APITimeoutError

from app.gpt.base import GPT
from app.models.transcriber_model import TranscriptResult
from app.services.openai_client import create_openai_client
from app.services.note_format import MARKDOWN_FORMAT_RULES
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Keep direct generation as the default for long-context models. A 256k-token
# model can normally handle prompts far above 24k characters, so chunking is a
# fallback instead of the first path.
MAX_DIRECT_PROMPT_CHARS = int(os.getenv("NOTE_DIRECT_PROMPT_CHARS", "180000"))
CHUNK_TARGET_CHARS = 12000
MERGE_TARGET_CHARS = 18000
NOTE_GENERATION_MODE = os.getenv("NOTE_GENERATION_MODE", "auto").strip().lower()
ProgressCallback = Callable[[str, str], None]


class TaskCancelledError(RuntimeError):
    """用户手动停止任务时抛出，用于中断流式生成循环"""


class OpenAIGPT(GPT):
    """Generate video notes through an OpenAI-compatible chat API."""

    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.model = model or os.getenv("GPT_MODEL", "gpt-4o-mini")

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not configured")

        # 由调用方注入（返回 True 表示任务已被手动停止），
        # 在流式循环与分块循环中周期性检查，及时中断生成
        self.cancel_check: Optional[Callable[[], bool]] = None

        self.client = create_openai_client(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=600.0,
            max_retries=0,
        )

        logger.info(f"Initialized OpenAI-compatible GPT: model={self.model}")

    def _raise_if_canceled(self) -> None:
        check = self.cancel_check
        if check is not None and check():
            logger.info("Task canceled by user; aborting note generation")
            raise TaskCancelledError("已手动停止生成")

    def summarize(
        self,
        transcript: TranscriptResult,
        filename: str = "",
        screenshot: bool = False,
        note_style: str = "simple",
        progress_callback: Optional[ProgressCallback] = None,
        board_pages: Optional[List[dict]] = None,
    ) -> str:
        logger.info(f"Start note generation (screenshot={screenshot}, style={note_style}, board_pages={len(board_pages) if board_pages else 0})")

        if board_pages:
            # 板书时间线模式：逐页完整记录 + 按视频时间线梳理 + 结尾总结
            prompt = self._build_board_prompt(transcript, filename, note_style, board_pages)
            system_content = (
                "You are a professional video-note assistant specialized in lecture board capture. "
                "Write clear, well-structured Chinese Markdown notes organized strictly by the video timeline.\n\n"
                f"{MARKDOWN_FORMAT_RULES}"
            )
            try:
                markdown = self._complete_markdown(
                    system_content,
                    prompt,
                    temperature=0.5,
                    progress_callback=progress_callback,
                    progress_message="正在按板书时间线生成笔记",
                )
            except Exception as exc:
                if self._is_context_limit_error(exc):
                    logger.info("Board-mode prompt hit context limit; falling back to chunked without board pages")
                    prompt = self._build_prompt(transcript, filename, False, note_style)
                    markdown = self._summarize_long_transcript(
                        transcript=transcript,
                        filename=filename,
                        screenshot=False,
                        note_style=note_style,
                        system_content=system_content,
                        progress_callback=progress_callback,
                    )
                else:
                    raise
            logger.info("Board-mode note generation completed")
            return markdown

        prompt = self._build_prompt(transcript, filename, screenshot, note_style)
        system_content = (
            "You are a professional video-note assistant. Write clear, well-structured, "
            "information-rich Chinese Markdown notes from video transcripts.\n\n"
            f"{MARKDOWN_FORMAT_RULES}"
        )
        if screenshot:
            system_content += (
                "\n\nWhen screenshot markers are requested, insert useful markers in the exact "
                "format `*Screenshot-[mm:ss]` near the relevant content."
            )

        try:
            mode = self._generation_mode()
            should_chunk_first = (
                transcript.segments
                and (
                    mode == "chunk"
                    or (mode == "auto" and len(prompt) > MAX_DIRECT_PROMPT_CHARS)
                )
            )

            if should_chunk_first:
                logger.info(
                    "Transcript prompt is long (%s chars, %s segments, mode=%s); using chunked note generation",
                    len(prompt),
                    len(transcript.segments),
                    mode,
                )
                markdown = self._summarize_long_transcript(
                    transcript=transcript,
                    filename=filename,
                    screenshot=screenshot,
                    note_style=note_style,
                    system_content=system_content,
                    progress_callback=progress_callback,
                )
            else:
                try:
                    markdown = self._complete_markdown(
                        system_content,
                        prompt,
                        temperature=0.7,
                        progress_callback=progress_callback,
                        progress_message="正在生成笔记",
                    )
                except Exception as exc:
                    if mode == "auto" and transcript.segments and self._is_context_limit_error(exc):
                        logger.info(
                            "Direct note generation hit a context limit (%s chars); retrying with chunked generation",
                            len(prompt),
                        )
                        markdown = self._summarize_long_transcript(
                            transcript=transcript,
                            filename=filename,
                            screenshot=screenshot,
                            note_style=note_style,
                            system_content=system_content,
                            progress_callback=progress_callback,
                        )
                    else:
                        raise

            logger.info("Note generation completed")

            if screenshot:
                pattern = r"\*Screenshot-\[(\d+):(\d{2})\]|\*Screenshot-(\d+):(\d{2})"
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

    def _complete_markdown(
        self,
        system_content: str,
        prompt: str,
        temperature: float = 0.7,
        progress_callback: Optional[ProgressCallback] = None,
        progress_message: str = "正在生成笔记",
    ) -> str:
        self._raise_if_canceled()
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            stream=True,
        )

        markdown = self._read_streaming_markdown(
            response,
            progress_callback=progress_callback,
            progress_message=progress_message,
        ).strip()
        if not markdown:
            raise RuntimeError("AI did not return note content. Please check whether this model supports chat streaming.")
        return markdown

    def _read_streaming_markdown(
        self,
        response: Iterable,
        progress_callback: Optional[ProgressCallback] = None,
        progress_message: str = "正在生成笔记",
    ) -> str:
        chunks = []
        last_emit_len = 0
        event_count = 0
        for event in response:
            event_count += 1
            if event_count % 50 == 0:
                # 周期性检查取消标记，避免手动停止后仍继续生成
                self._raise_if_canceled()
            if not getattr(event, "choices", None):
                continue
            delta = event.choices[0].delta
            content = getattr(delta, "content", None)
            if content:
                chunks.append(content)
                current = "".join(chunks)
                if progress_callback and len(current) - last_emit_len >= 400:
                    progress_callback(progress_message, current)
                    last_emit_len = len(current)
        if progress_callback and chunks:
            progress_callback(progress_message, "".join(chunks))
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

        if self._is_context_limit_error(exc):
            return (
                "AI model context window is too small for this transcript. "
                "Use a long-context model, or set NOTE_GENERATION_MODE=auto/chunk to allow segmented note generation."
            )

        if isinstance(exc, APIStatusError):
            if exc.status_code in {429, 500, 502, 503, 504}:
                return (
                    f"AI provider is temporarily unavailable (HTTP {exc.status_code}). "
                    "This is usually provider overload, an unstable relay channel, or a model that is not currently available. "
                    "AInote did not receive a finished note. Try another model/provider or regenerate later. "
                    f"Details: {message}"
                )
            return f"AI provider returned HTTP {exc.status_code}: {message}"

        return f"AI note generation failed: {message or type(exc).__name__}"

    def _generation_mode(self) -> str:
        if NOTE_GENERATION_MODE in {"auto", "direct", "chunk"}:
            return NOTE_GENERATION_MODE
        logger.warning("Invalid NOTE_GENERATION_MODE=%s; falling back to auto", NOTE_GENERATION_MODE)
        return "auto"

    def _is_context_limit_error(self, exc: Exception) -> bool:
        message = str(exc).lower()
        status_code = getattr(exc, "status_code", None)
        if isinstance(exc, APIStatusError) and status_code == 413:
            return True
        if status_code not in {None, 400, 413}:
            return False
        context_markers = (
            "context_length_exceeded",
            "maximum context length",
            "context window",
            "too many tokens",
            "input is too long",
            "prompt is too long",
            "request too large",
            "reduce the length",
        )
        return any(marker in message for marker in context_markers)

    def _summarize_long_transcript(
        self,
        transcript: TranscriptResult,
        filename: str,
        screenshot: bool,
        note_style: str,
        system_content: str,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> str:
        chunks = self._chunk_segments(transcript.segments, CHUNK_TARGET_CHARS)
        chunk_summaries: List[str] = []
        if progress_callback:
            progress_callback(f"正在拆分长视频：共 {len(chunks)} 段", "")

        for index, chunk in enumerate(chunks, start=1):
            self._raise_if_canceled()
            message = f"正在生成第 {index}/{len(chunks)} 段摘要"
            logger.info("Generating intermediate note chunk %s/%s (%s segments)", index, len(chunks), len(chunk))
            chunk_prompt = self._build_chunk_prompt(chunk, filename, index, len(chunks), screenshot)
            chunk_summary = self._complete_markdown(
                system_content,
                chunk_prompt,
                temperature=0.35,
                progress_callback=self._chunk_progress_callback(
                    progress_callback,
                    chunk_summaries,
                    index,
                    len(chunks),
                ),
                progress_message=message,
            )
            chunk_summaries.append(f"## 第 {index}/{len(chunks)} 段摘要\n\n{chunk_summary}")
            if progress_callback:
                progress_callback(f"已完成第 {index}/{len(chunks)} 段摘要", "\n\n".join(chunk_summaries))

        merged_summaries = self._compress_summaries_if_needed(chunk_summaries, system_content, progress_callback)
        final_prompt = self._build_final_prompt(merged_summaries, filename, screenshot, note_style)
        return self._complete_markdown(
            system_content,
            final_prompt,
            temperature=0.55,
            progress_callback=progress_callback,
            progress_message="正在合并全片笔记",
        )

    def _chunk_progress_callback(
        self,
        progress_callback: Optional[ProgressCallback],
        completed_summaries: Sequence[str],
        index: int,
        total: int,
    ) -> Optional[ProgressCallback]:
        if not progress_callback:
            return None

        def callback(message: str, partial: str) -> None:
            sections = list(completed_summaries)
            if partial:
                sections.append(f"## 正在生成第 {index}/{total} 段摘要\n\n{partial}")
            progress_callback(message, "\n\n".join(sections))

        return callback

    def _compress_summaries_if_needed(
        self,
        summaries: List[str],
        system_content: str,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> List[str]:
        current = summaries
        while len("\n\n".join(current)) > MAX_DIRECT_PROMPT_CHARS and len(current) > 1:
            grouped = self._chunk_text_blocks(current, MERGE_TARGET_CHARS)
            if progress_callback:
                progress_callback(f"中间摘要过长，正在压缩为 {len(grouped)} 组", "\n\n".join(current))
            next_round: List[str] = []
            for index, group in enumerate(grouped, start=1):
                prompt = (
                    "The following are intermediate Chinese video-note summaries from a long video.\n"
                    "Compress them into a denser Chinese outline while preserving timestamps, facts, examples, "
                    "names, parameters, and decisions. Do not add a final conclusion yet.\n\n"
                    f"{MARKDOWN_FORMAT_RULES}\n\n"
                    f"Group {index}/{len(grouped)}:\n---\n{chr(10).join(group)}\n---"
                )
                next_round.append(
                    self._complete_markdown(
                        system_content,
                        prompt,
                        temperature=0.25,
                        progress_callback=progress_callback,
                        progress_message=f"正在压缩中间摘要 {index}/{len(grouped)}",
                    )
                )
            current = next_round
        return current

    def _chunk_segments(self, segments: Sequence, target_chars: int) -> List[List]:
        chunks: List[List] = []
        current: List = []
        current_len = 0

        for segment in segments:
            formatted_len = len(self._format_segment(segment))
            if current and current_len + formatted_len > target_chars:
                chunks.append(current)
                current = []
                current_len = 0
            current.append(segment)
            current_len += formatted_len

        if current:
            chunks.append(current)
        return chunks or [list(segments)]

    def _chunk_text_blocks(self, blocks: Sequence[str], target_chars: int) -> List[List[str]]:
        groups: List[List[str]] = []
        current: List[str] = []
        current_len = 0

        for block in blocks:
            block_len = len(block)
            if current and current_len + block_len > target_chars:
                groups.append(current)
                current = []
                current_len = 0
            current.append(block)
            current_len += block_len

        if current:
            groups.append(current)
        return groups

    def _format_segment(self, segment) -> str:
        mm = int(segment.start // 60)
        ss = int(segment.start % 60)
        return f"[{mm:02d}:{ss:02d}] {segment.text}\n"

    def _format_segments(self, segments: Sequence) -> str:
        return "".join(self._format_segment(segment) for segment in segments)

    def _build_board_prompt(
        self,
        transcript: TranscriptResult,
        filename: str,
        note_style: str,
        board_pages: List[dict],
    ) -> str:
        """板书时间线模式提示词：逐页完整记录 + 按时间线梳理 + 结尾总结"""
        from app.services.note_styles import get_style_prompt

        style_instruction = {
            "detailed": "- 详细展开每页的讲解内容，保留例题与推导。",
            "academic": "- 语言严谨，强调定义、定理与论证链条。",
            "creative": "- 表达生动但忠于板书与讲解事实。",
        }.get(note_style)
        if not style_instruction:
            custom = get_style_prompt(note_style)
            style_instruction = ("- 遵循用户自定义风格要求：" + custom) if custom else "- 简洁凝练，突出重点。"

        timeline_lines = []
        for pg in board_pages:
            start_s = int(pg.get("start", 0))
            end_s = int(pg.get("end", 0))
            text = (pg.get("text") or "").strip() or "（板书内容待参考截图）"
            timeline_lines.append(
                f"[[BOARD_PAGE {pg['index']}]] {start_s // 60}:{start_s % 60:02d}-{end_s // 60}:{end_s % 60:02d}"
                f"{chr(10)}板书内容：{text}"
            )

        return f"""根据以下视频转写与板书时间线，生成一篇以视频时间线为主轴的高质量中文 Markdown 学习笔记。

文件名: {filename}

板书时间线（每页一段，[[BOARD_PAGE i]] 是该页截图的占位标记，必须原样保留在对应小节开头）：
---
{chr(10).join(timeline_lines)}
---

组织规则（必须严格遵守）：
1. 以视频时间线为主线：按板书页顺序逐页梳理，每页一个小节，标题格式为 `### [起止时间] 第N页：<本页主题>`。
2. 每个小节的第一行必须是该页的 `[[BOARD_PAGE i]]` 占位标记（单独一行，系统会在此插入完整板书截图与转录文字）。
3. 板书里出现的题目必须原样完整保留（题干、条件、问法一个都不能省），公式用 LaTeX。
4. 板书之后写本页对应的讲解要点：老师口头讲解的逻辑、推导步骤、例题解题过程（从转写中提炼），以及易错点。
5. 口语、废话、重复内容过滤掉；老师课堂上的口误、自我纠正、反复尝试（如"等等，不对，让我重新整理"）不要写进笔记，只保留最终正确的结论与推导。
6. 转写中的同音字错误用上下文修正（特别是数学术语），但不许改变原意、不许编造。
7. 排版密度：短公式优先行内展示；连续多步推导合并为一个 aligned 公式块，每行一步；每个自然段不超过 4 行，段落之间只留一个空行。
8. 不要在笔记里暴露任何推理过程用语（如"等等""不对""实际上题目可能是"），直接呈现最终整理好的内容。
 9. 全部板书页都要覆盖，一页都不能漏。
10. 最后必须有「## AI 总结」章节：本节课方法清单、典型例题套路、易错点汇总、考点提示。
{style_instruction}

{MARKDOWN_FORMAT_RULES}

视频转写内容：
---
{self._format_segments(transcript.segments)}
---

现在开始生成笔记，只输出 Markdown 正文："""

    def _build_chunk_prompt(
        self,
        segments: Sequence,
        filename: str,
        index: int,
        total: int,
        screenshot: bool,
    ) -> str:
        screenshot_instruction = ""
        if screenshot:
            screenshot_instruction = (
                "\nIf a visual frame is important, keep a candidate marker in the exact format "
                "`*Screenshot-[mm:ss]` using the original video timestamp."
            )

        return f"""This is part {index}/{total} of a long video transcript.
Write an intermediate Chinese Markdown outline for this part only.
Preserve exact timestamps, key facts, examples, tool names, parameters, steps, conclusions, and warnings.
Do not invent information. Do not write the final whole-video summary yet.{screenshot_instruction}

{MARKDOWN_FORMAT_RULES}

File: {filename}

Segments:
---
{self._format_segments(segments)}
---"""

    def _build_final_prompt(
        self,
        summaries: Sequence[str],
        filename: str,
        screenshot: bool,
        note_style: str,
    ) -> str:
        screenshot_instruction = ""
        if screenshot:
            screenshot_instruction = (
                "\nKeep or add a small number of useful screenshot markers in the exact format "
                "`*Screenshot-[mm:ss]`, placed near the relevant section."
            )

        style_instruction = {
            "detailed": "Use detailed mode: preserve examples, data, parameters, concrete steps, and enough detail to replace rewatching.",
            "academic": "Use academic mode: formal, objective, structured around background, arguments, evidence, and conclusions.",
            "creative": "Use creative mode: readable and vivid, but factual, with highlights and takeaways.",
        }.get(
            note_style,
            "Use concise mode: direct key points, short paragraphs, and only the most important concepts and steps.",
        )
        # 自定义风格优先：用户在设置里配置的提示词模板
        custom_instruction = None
        try:
            from app.services import note_styles
            custom_instruction = note_styles.get_style_prompt(note_style)
        except Exception:
            pass
        if custom_instruction:
            style_instruction = custom_instruction

        return f"""Create the final Chinese Markdown note for the whole video from these intermediate summaries.
File: {filename}

Requirements:
- Keep the output in Chinese Markdown.
- Merge duplicate points and keep the original order of the video.
- Preserve important timestamps as `*Content-[mm:ss]` when useful.
- Preserve formulas, names, products, parameters, examples, and concrete steps.
- Math formatting (critical): display math must be a `$$` block that contains ONLY the formula, never Chinese prose, headings, or images. Inline math uses `$...$`.
- ASR error correction (critical): the intermediate summaries come from speech recognition and may contain homophone errors and misheard technical terms. Use context to fix them; never change the actual meaning or invent content.
- End with a section named `AI 总结`.
- Return only the final Markdown content.{screenshot_instruction}
- {style_instruction}

{MARKDOWN_FORMAT_RULES}

Intermediate summaries:
---
{chr(10).join(summaries)}
---"""

    def _build_prompt(
        self,
        transcript: TranscriptResult,
        filename: str,
        screenshot: bool = False,
        note_style: str = "simple",
    ) -> str:
        segment_text = self._format_segments(transcript.segments)

        screenshot_instruction = ""
        if screenshot:
            screenshot_instruction = """

8. Screenshot placeholders:
   Insert a few useful screenshot markers, recommended at least 3, for key visual moments.
   The exact format must be `*Screenshot-[mm:ss]`, for example `*Screenshot-[01:23]`.
   Put the marker near the related section and separate it from normal text with blank lines."""

        style_instruction = {
            "detailed": """
Style: detailed mode.
- Keep examples, data, parameters, and concrete steps from the video.
- Explain key concepts deeply enough that the note can replace rewatching.
- Use clear headings and lists.""",
            "academic": """
Style: academic mode.
- Use formal, objective language.
- Emphasize causality, argumentation, evidence, and terminology.
- Organize content as background, core points, evidence, and conclusion.""",
            "creative": """
Style: creative mode.
- Make the note readable and vivid without losing facts.
- Highlight key moments, insights, and takeaways.
- Use expressive but still structured headings.""",
        }.get(
            note_style,
            """
Style: concise mode.
- Focus on key points and remove redundant filler.
- Use short paragraphs and bullets.
- Keep core concepts, conclusions, and steps.""",
        )
        # 自定义风格优先：用户在设置里配置的提示词模板
        try:
            from app.services import note_styles
            custom_instruction = note_styles.get_style_prompt(note_style)
            if custom_instruction:
                style_instruction = "\nStyle: custom mode defined by the user.\n" + custom_instruction
        except Exception:
            pass

        return f"""Generate a structured Chinese Markdown note from the following video transcript.
File name: {filename}

Language:
- The note must be written in Chinese.
- Keep proper nouns, technical terms, brand names, and names in English when appropriate.

Transcript segments:
---
{segment_text}
---

Tasks:
1. Record relevant details as completely as possible.
2. Remove ads, fillers, greetings, and irrelevant content.
3. Preserve important facts, examples, conclusions, and suggestions.
4. Use Markdown headings and lists with concise paragraphs.
5. Preserve formulas and render them with LaTeX when present.
6. Add useful time markers as `*Content-[mm:ss]` when helpful.
7. Math formatting (critical): display math must be a `$$` block that contains ONLY the formula, never Chinese prose, headings, or images. Inline math uses `$...$`.
8. ASR error correction (critical): the transcript comes from speech recognition and contains homophone errors and misheard technical terms (especially math/physics terminology). Use context to fix them in the note (e.g. wrong characters in terms, formula names). Never change the actual meaning or invent content that is not supported by the transcript.
9. Content hygiene: the teacher may mis-speak and self-correct on the fly. Do NOT include the corrections or hesitation ("wait, no, let me redo this") — only the final correct version. For multi-step derivations, use one compact `$$\\begin{{aligned}} ... \\\\ ... \\\\end{{aligned}}$$` block with one step per row. Do not emit a series of one-line display-math blocks.
{screenshot_instruction}
{style_instruction}

{MARKDOWN_FORMAT_RULES}

Output:
- Return only final Markdown content.
- Do not wrap the output in a code block.
- End with a section named `AI 总结`.

Start generating the note now:"""
