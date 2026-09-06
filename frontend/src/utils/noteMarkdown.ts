/**
 * 笔记 Markdown 预处理：
 * - 把后端生成的时间标记（*Content-[mm:ss] / *Screenshot-[mm:ss]）转成内联代码徽章
 * - 保留 LaTeX、图片等其他语法不动
 */
/**
 * 修复错乱的 $$ 配对：LLM 有时把 $$...$$ 当装饰用，块里装的是中文正文甚至标题/图片，
 * 导致后续所有公式块配对错位、大面积显示原始文本。
 * 策略：成对扫描，若"公式块"内容其实是正文（含中文，排除 \text{}），就摘掉定界符，
 * 内容按普通 Markdown 渲染（其中的 $...$ 内联公式仍可渲染）。
 */
function repairMathBlocks(md: string): string {
  if (!md.includes("$$")) return md
  let out = ""
  let i = 0
  while (i < md.length) {
    const open = md.indexOf("$$", i)
    if (open === -1) {
      out += md.slice(i)
      break
    }
    const close = md.indexOf("$$", open + 2)
    if (close === -1) {
      // 未闭合：视为普通文本，去掉这个悬挂定界符
      out += md.slice(i, open) + md.slice(open + 2)
      break
    }
    const content = md.slice(open + 2, close)
    if (content.trim() === "") {
      // 空的 $$...$$ 对：模型多余输出，丢弃定界符避免顶乱后续配对
      out += md.slice(i, open)
    } else if (isProseLike(content)) {
      // 正文块：丢弃定界符，保留内容
      out += md.slice(i, open) + content
    } else {
      // 正常公式块：原样保留
      out += md.slice(i, close + 2)
    }
    i = close + 2
  }
  return out
}

function isProseLike(content: string): boolean {
  const stripped = content
    .replace(/\\(?:text|mbox|mathrm)\s*\{[^{}]*\}/g, "")
    .replace(/\$[^$]*\$/g, "")
  return /[\u4e00-\u9fff]/.test(stripped)
}

export function preprocessNoteMarkdown(md: string): string {
  if (!md) return md
  return (
    repairMathBlocks(md)
      // 视觉模型/LLM 有时输出 \( \) 和 \[ \] 定界符，前端渲染器只认 $ / $$，统一转换
      .replace(/\\\(([\s\S]*?)\\\)/g, (_, t) => '$' + t + '$')
      .replace(/\\\[([\s\S]*?)\\\]/g, (_, t) => '$$' + t + '$$')
      // 斜体包裹形式：*Content-[00:53]*
      .replace(/\*Content-\[(\d+:\d{2}(?::\d{2})?)\]\*/g, '`⏱ $1`')
      .replace(/\*Screenshot-\[(\d+:\d{2}(?::\d{2})?)\]\*/g, '`📷 $1`')
      // 未被斜体包裹的裸标记
      .replace(/(^|[^*])\*Content-\[(\d+:\d{2}(?::\d{2})?)\]/g, '$1`⏱ $2`')
      .replace(/(^|[^*])\*Screenshot-\[(\d+:\d{2}(?::\d{2})?)\]/g, '$1`📷 $2`')
  )
}


/**
 * 把笔记 Markdown 按"块"切分（空行分界），用于渐进渲染。
 * $$ 公式块和 ``` 代码块内部的空行不会切断。
 */
const LF = String.fromCharCode(10)

export function splitNoteBlocks(md: string): string[] {
  if (!md) return []
  const lines = md.split('\n')
  const blocks: string[] = []
  let cur: string[] = []
  let inMath = false
  let inFence = false
  for (const line of lines) {
    const trimmed = line.trim()
    if (trimmed.startsWith('```')) inFence = !inFence
    if (!inFence) {
      const pairs = (line.match(/\$\$/g) || []).length
      if (pairs % 2 === 1) inMath = !inMath
    }
    if (trimmed === '' && !inMath && !inFence) {
      if (cur.length) {
        blocks.push(cur.join(LF))
        cur = []
      }
    } else {
      cur.push(line)
    }
  }
  if (cur.length) blocks.push(cur.join(LF))
  return blocks
}
