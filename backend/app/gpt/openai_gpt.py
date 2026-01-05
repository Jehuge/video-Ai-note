import os
from openai import OpenAI
from app.gpt.base import GPT
from app.models.transcriber_model import TranscriptResult
from app.utils.logger import get_logger

logger = get_logger(__name__)


class OpenAIGPT(GPT):
    """使用 OpenAI API 生成笔记"""
    
    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        """
        初始化 OpenAI GPT
        
        :param api_key: API 密钥
        :param base_url: API 基础 URL
        :param model: 模型名称
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.model = model or os.getenv("GPT_MODEL", "gpt-4o-mini")
        
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY 未设置")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        
        logger.info(f"初始化 OpenAI GPT: model={self.model}")
    
    def summarize(self, transcript: TranscriptResult, filename: str = "", screenshot: bool = False, note_style: str = "simple") -> str:
        """生成笔记"""
        logger.info(f"开始生成笔记... (screenshot={screenshot}, style={note_style})")
        
        # 构建提示词（传递 screenshot 和 style 参数）
        prompt = self._build_prompt(transcript, filename, screenshot, note_style)
        
        # 构建 system message
        system_content = "你是一个专业的笔记助手，擅长将视频转录内容整理成清晰、有条理且信息丰富的笔记。"
        if screenshot:
            system_content += "\n\n**重要**：当用户要求添加截图标记时，你必须在相关章节后插入 `*Screenshot-[mm:ss]` 格式的标记。这是强制要求，不能忽略。"
        
        # 调用 API
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
            )
            
            markdown = response.choices[0].message.content.strip()
            logger.info("笔记生成完成")
            
            # 如果启用了截图，检查是否包含截图标记
            if screenshot:
                import re
                pattern = r"\*Screenshot-\[(\d{2}):(\d{2})\]|\*Screenshot-(\d{2}):(\d{2})"
                matches = list(re.finditer(pattern, markdown))
                if matches:
                    logger.info(f"✓ 笔记中包含 {len(matches)} 个截图标记")
                else:
                    logger.warning("⚠ 警告：启用了截图功能，但生成的笔记中没有找到截图标记！")
            
            return markdown
            
        except Exception as e:
            logger.error(f"生成笔记失败: {e}")
            raise
    
    def _build_prompt(self, transcript: TranscriptResult, filename: str, screenshot: bool = False, note_style: str = "simple") -> str:
        """构建提示词"""
        # 构建分段文本
        segment_text = ""
        for seg in transcript.segments:
            mm = int(seg.start // 60)
            ss = int(seg.start % 60)
            segment_text += f"[{mm:02d}:{ss:02d}] {seg.text}\n"
        
        screenshot_instruction = ""
        if screenshot:
            screenshot_instruction = """

8. **截图占位符（强制要求）**：
   你**必须**在笔记中插入 2-5 个截图标记，用于从视频中提取关键画面（如：界面演示、代码片段、关键数据、人物出场等）。
   
   **格式与位置规则（严格执行）**：
   1. **格式**：必须严格使用 `*Screenshot-[mm:ss]` 格式（例如 `*Screenshot-[01:23]`）。
   2. **位置**：截图标记必须放在**章节内容的最后**（即该章节所有文字之后），并且前后必须有**空行**分隔。
   3. **时间戳**：使用该章节对应的视频开始时间。

   **正确结构示例**：
   ```markdown
   ### 章节标题
   - 核心内容点 1
   - 核心内容点 2
   
   *Screenshot-[05:30]
   
   ### 下一个章节
   ```
"""

        # 根据风格添加特定的提示词
        style_instruction = ""
        if note_style == "detailed":
            style_instruction = """
风格要求（详细模式）：
- **极其详尽**：不要遗漏任何细节，包括所有提到的例子、数据、参数和具体步骤。
- **深度解析**：对视频中的概念进行深入解释，不仅仅是表面记录。
- **结构丰富**：使用多级标题（##, ###, ####），详细的列表，以及引用块来组织内容。
- **完整性**：笔记应该可以替代观看视频，读者在阅读笔记后应能完全掌握视频内容。
"""
        elif note_style == "academic":
            style_instruction = """
风格要求（学术模式）：
- **专业严谨**：使用正式、学术的语言，避免口语化表达。
- **逻辑性强**：强调因果关系、论证过程和理论基础。
- **术语准确**：准确使用专业术语，并在首次出现时从视频内容中提取定义。
- **客观中立**：保持客观的记录视角，区分事实陈述和观点表达。
- **结构化**：建议使用"摘要"、"背景"、"核心论点"、"详细论证"、"结论"等标准学术结构。
"""
        elif note_style == "creative":
            style_instruction = """
风格要求（创意模式）：
- **生动活泼**：使用轻松、引人入胜的语言，可以适当使用emoji。
- **故事性**：尝试以讲故事的方式串联内容，使其更具可读性。
- **亮点突出**：特别强调视频中的"高光时刻"、"金句"或"有趣的点"。
- **启发性**：在总结中加入这就内容带来的启发或思考。
- **形式多样**：可以使用引用、加粗、斜体等多种格式增强视觉吸引力。
"""
        else:  # simple (默认)
            style_instruction = """
风格要求（简洁模式）：
- **精简扼要**：直击要点，去除所有冗余信息。
- **快速阅读**：适合快速浏览，使用短句和项目符号。
- **核心优先**：只保留最核心的概念、结论和关键步骤。
- **清晰明了**：结构简单清晰，避免过于复杂的层级。
"""
        
        prompt = f"""请根据以下视频转录内容生成结构化的 Markdown 笔记。

文件名称: {filename}

语言要求：
- 笔记必须使用 **中文** 撰写
- 专有名词、技术术语、品牌名称和人名应适当保留 **英文**

视频分段（格式：开始时间 - 内容）：
---
{segment_text}
---

你的任务：
根据上面的分段转录内容，生成结构化的笔记，遵循以下原则：

1. **完整信息**：记录尽可能多的相关细节，确保内容全面
2. **去除无关内容**：省略广告、填充词、问候语和不相关的言论
3. **保留关键细节**：保留重要事实、示例、结论和建议
4. **可读布局**：使用标题、列表等格式，保持段落简短
5. **数学公式**：视频中提及的数学公式必须保留，并以 LaTeX 语法形式呈现
6. 使用标题层级（##, ###）组织内容
7. 在主要章节后可以添加时间标记，格式：`*Content-[mm:ss]`{screenshot_instruction}
{style_instruction}

输出说明：
- 仅返回最终的 **Markdown 内容**
- **不要**将输出包裹在代码块中（例如：```markdown，```）

请在笔记末尾添加一个 **AI 总结**部分，简要总结整个视频的核心内容。

现在开始生成笔记："""
        
        return prompt

