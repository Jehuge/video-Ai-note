import os
import re
from typing import Callable, Iterable, List, Optional, Sequence

from openai import APIConnectionError, APIStatusError, APITimeoutError

from app.gpt.base import GPT
from app.models.transcriber_model import TranscriptResult
from app.services.openai_client import create_openai_client
from app.utils.logger import get_logger

logger = get_logger(__name__)

MAX_DIRECT_PROMPT_CHARS = 24000
CHUNK_TARGET_CHARS = 12000
MERGE_TARGET_CHARS = 18000
ProgressCallback = Callable[[str, str], None]


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
        progress_callback: Optional[ProgressCallback] = None,
    ) -> str:
        logger.info(f"Start note generation (screenshot={screenshot}, style={note_style})")

        prompt = self._build_prompt(transcript, filename, screenshot, note_style)
        system_content = (
            "You are a professional video-note assistant. Write clear, well-structured, "
            "information-rich Chinese Markdown notes from video transcripts."
        )
        if screenshot:
            system_content += (
                "\n\nWhen screenshot markers are requested, insert useful markers in the exact "
                "format `*Screenshot-[mm:ss]` near the relevant content."
            )

        try:
            if len(prompt) > MAX_DIRECT_PROMPT_CHARS and transcript.segments:
                logger.info(
                    "Transcript prompt is long (%s chars, %s segments); using chunked note generation",
                    len(prompt),
                    len(transcript.segments),
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
                markdown = self._complete_markdown(
                    system_content,
                    prompt,
                    temperature=0.7,
                    progress_callback=progress_callback,
                    progress_message="正在生成笔记",
                )

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

    def _complete_markdown(
        self,
        system_content: str,
        prompt: str,
        temperature: float = 0.7,
        progress_callback: Optional[ProgressCallback] = None,
        progress_message: str = "正在生成笔记",
    ) -> str:
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
        for event in response:
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

        return f"""Create the final Chinese Markdown note for the whole video from these intermediate summaries.
File: {filename}

Requirements:
- Keep the output in Chinese Markdown.
- Merge duplicate points and keep the original order of the video.
- Preserve important timestamps as `*Content-[mm:ss]` when useful.
- Preserve formulas, names, products, parameters, examples, and concrete steps.
- End with a section named `AI 总结`.
- Return only the final Markdown content.{screenshot_instruction}
- {style_instruction}

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
{screenshot_instruction}
{style_instruction}

Output:
- Return only final Markdown content.
- Do not wrap the output in a code block.
- End with a section named `AI 总结`.

Start generating the note now:"""
