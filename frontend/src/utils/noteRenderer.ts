/**
 * 笔记渲染引擎：markdown-it 管线
 *
 * 为什么不用 react-markdown：react-markdown 会把整篇笔记展开成 React 虚拟节点
 * （600 个 KaTeX 公式 ≈ 6 万+ DOM 节点），初次渲染需要 React 逐个创建，长笔记直接卡死。
 * 这里改为 markdown-it 直接编译成 HTML 字符串，浏览器原生解析一次成型，
 * 快一个数量级，且结果可缓存（同一篇笔记二次打开零开销）。
 *
 * 能力：GFM 表格/删除线/任务列表、$/$$ 数学公式（KaTeX）、自动链接。
 * 安全：markdown-it 默认转义内嵌 HTML（html: false），无 XSS 注入面。
 *
 * 性能设计（流式/长笔记不卡顿的关键）：
 * - 块级缓存 renderNoteBlock：流式生成时每秒轮询一次，只有最后一块内容在变，
 *   前面所有块命中缓存后编译成本为 O(1)，不再整篇重编译。
 * - KaTeX output:'html'：默认会同时输出 MathML（供复制/读屏），节点数近乎翻倍；
 *   长笔记场景视觉优先，关闭 MathML 把公式 DOM 砍掉约一半。
 */
import MarkdownIt from 'markdown-it'
import texmath from 'markdown-it-texmath'
import katex from 'katex'
import { preprocessNoteMarkdown } from './noteMarkdown'

const md = new MarkdownIt({
  html: false, // 转义原始 HTML，防注入
  linkify: true,
  breaks: false,
})

md.use(texmath, {
  engine: katex,
  delimiters: 'dollars',
  katexOptions: { throwOnError: false, strict: false, output: 'html' },
})

// 图片：懒加载 + 异步解码 + 圆角（样式由 .note-md img 提供）
const defaultImage =
  md.renderer.rules.image ||
  ((tokens, idx, options, _env, self) => self.renderToken(tokens, idx, options))

md.renderer.rules.image = (tokens, idx, options, _env, self) => {
  const token = tokens[idx]
  token.attrSet('loading', 'lazy')
  token.attrSet('decoding', 'async')
  return defaultImage(tokens, idx, options, _env, self)
}

/** LRU 缓存工具：命中返回值并刷新热度，未命中返回 undefined */
function lruGet<T>(map: Map<string, T>, key: string): T | undefined {
  const hit = map.get(key)
  if (hit !== undefined) {
    // 触碰一次保持 LRU 顺序
    map.delete(key)
    map.set(key, hit)
  }
  return hit
}

function lruSet<T>(map: Map<string, T>, key: string, value: T, max: number) {
  if (map.size >= max) {
    const oldest = map.keys().next().value
    if (oldest !== undefined) map.delete(oldest)
  }
  map.set(key, value)
}

// 同一篇笔记的渲染结果缓存（字符串），重复打开预览零开销
const fullCache = new Map<string, string>()
const FULL_CACHE_MAX = 12

// 块级缓存：块源码 → HTML。流式场景每 tick 只有尾部块未命中
const blockCache = new Map<string, string>()
const BLOCK_CACHE_MAX = 4000

/** 渲染单个块（带缓存）。块内容不变则零成本 */
export function renderNoteBlock(blockSource: string): string {
  const cached = lruGet(blockCache, blockSource)
  if (cached !== undefined) return cached
  const html = md.render(preprocessNoteMarkdown(blockSource))
  lruSet(blockCache, blockSource, html, BLOCK_CACHE_MAX)
  return html
}

export function renderNoteMarkdown(markdown: string): string {
  if (!markdown) return ''
  const hit = lruGet(fullCache, markdown)
  if (hit !== undefined) return hit

  const html = md.render(preprocessNoteMarkdown(markdown))

  lruSet(fullCache, markdown, html, FULL_CACHE_MAX)
  return html
}
