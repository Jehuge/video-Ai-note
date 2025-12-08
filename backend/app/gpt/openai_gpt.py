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
    
    def summarize(self, transcript: TranscriptResult, filename: str = "", screenshot: bool = False) -> str:
        """生成笔记"""
        logger.info(f"开始生成笔记... (screenshot={screenshot})")
        
        # 构建提示词（传递 screenshot 参数）
        prompt = self._build_prompt(transcript, filename, screenshot)
        
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
    
    def _build_prompt(self, transcript: TranscriptResult, filename: str, screenshot: bool = False) -> str:
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
   
   ⚠️ **这是强制要求，不能忽略！** ⚠️
   
   你**必须**在笔记中插入至少 2-5 个截图标记。截图标记应该插入在以下类型的章节后面：
   - **视觉演示**：展示界面、效果、结果、画面内容
   - **代码演示**：显示代码、配置、参数设置
   - **UI 交互**：操作步骤、界面变化、点击操作
   - **对比效果**：前后对比、不同参数的效果
   - **关键操作**：重要步骤、关键设置、重要时刻
   - **人物介绍**：嘉宾出场、重要人物介绍
   - **场景切换**：重要场景、关键转折点
   
   **截图标记格式（严格遵循）**：
   ```
   *Screenshot-[mm:ss]
   ```
   - 格式必须完全一致：`*Screenshot-[mm:ss]`（注意：星号开头，方括号是必需的）
   - 时间戳格式：mm:ss（两位分钟:两位秒，例如 01:23 表示 1分23秒）
   - 时间戳应该对应该章节在视频中的开始时间
   
   **插入位置（非常重要）**：
   
   ⚠️ **位置规则**：
   - 截图标记必须插入在**章节的所有内容之后**，紧跟在章节的最后一行内容后面
   - 格式结构：**章节标题 → 章节内容（列表/段落）→ 空行 → 截图标记 → 空行 → 下一个章节**
   
   - **错误示例 1**（不要这样做 - 在标题后）：
     ```
     ### 节目开场
     *Screenshot-[00:30]  ← ❌ 错误：在标题后，内容前
     - 韩立表达了参加...
     ```
   
   - **错误示例 2**（不要这样做 - 在内容中间）：
     ```
     ### 节目开场
     - 韩立表达了参加...
     *Screenshot-[00:30]  ← ❌ 错误：在内容中间
     - 继续其他内容...
     ```
   
   - **正确示例**（必须这样做）：
     ```
     ### 节目开场
     - 韩立表达了参加由何欢宗举办的相亲节目的兴奋之情，并希望能获得新的理解与体验。
     - 节目气氛轻松，观众反应热烈。
     
     *Screenshot-[00:30]
     
     ### 嘉宾介绍
     - 三号女嘉宾与韩立的互动，提到彼此的旧识与关系。
     - 韩立提到自己与女嘉宾的过去，带有幽默的调侃。
     
     *Screenshot-[02:15]
     
     ### 个人故事
     ```
   
   - **关键规则**：
     1. 截图标记必须在章节的**所有内容都写完后**才插入
     2. 截图标记前必须有**一个空行**（与内容分隔）
     3. 截图标记后必须有**一个空行**（与下一个章节分隔）
     4. 截图标记**不能**在章节标题后、内容中间或内容开头
     5. 每个需要截图的章节，标记都必须在**该章节内容的最后**
   
   **数量要求**：
   - **至少插入 2-5 个截图标记**
   - 根据视频长度和内容复杂度，适当增加标记数量
   - 不要只添加一个标记，要为多个重要章节都添加标记
   
   **时间戳选择**：
   - 查看上面的视频分段，选择每个重要章节对应的开始时间
   - 例如：如果"节目介绍"章节在 [00:30] 开始，就在该章节后添加 `*Screenshot-[00:30]`
   - 确保时间戳与章节内容对应
   
   **重要提醒**：
   - 这是**强制要求**，不是可选项
   - 如果视频内容涉及任何视觉元素（人物、界面、场景等），都必须添加截图标记
   - 不要忘记添加截图标记，这是生成笔记的必需步骤
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

输出说明：
- 仅返回最终的 **Markdown 内容**
- **不要**将输出包裹在代码块中（例如：```markdown，```）

请在笔记末尾添加一个 **AI 总结**部分，简要总结整个视频的核心内容。

现在开始生成笔记："""
        
        return prompt

