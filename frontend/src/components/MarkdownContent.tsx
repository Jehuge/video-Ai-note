/**
 * 流式/内嵌 Markdown 渲染（任务详情页的实时生成预览）：
 *
 * 每秒轮询拿到的 partialMarkdown 都在变长，旧实现每 tick 用 markdown-it
 * 整篇重编译（几百个公式 ≈ 数百 ms × 每 tick），轮询期间 UI 直接冻结。
 *
 * 现在按空行切块（splitNoteBlocks，$$ 块和代码围栏内的空行不会切断），
 * 每块独立渲染并缓存（renderNoteBlock）：
 * - 前 n-1 块内容不变 → 命中缓存 + React.memo 跳过，DOM 不动；
 * - 只有尾部正在生长的块重新编译，每 tick 成本 O(1)。
 *
 * 块间垂直间距：块 div 无内边距，内部元素的外边距按 CSS 规则穿透 div
 * 相互折叠，与整篇渲染的间距视觉一致（见 index.css 的 .note-md-blocks）。
 */
import { memo, useDeferredValue, useMemo } from 'react'
import { renderNoteBlock } from '../utils/noteRenderer'
import { preprocessNoteMarkdown, splitNoteBlocks } from '../utils/noteMarkdown'

interface MarkdownContentProps {
  markdown: string
}

const Block = memo(function Block({ source }: { source: string }) {
  return (
    <div
      className="note-md-block"
      dangerouslySetInnerHTML={{ __html: renderNoteBlock(source) }}
    />
  )
})

export default function MarkdownContent({ markdown }: MarkdownContentProps) {
  // 流式场景更新频繁，deferred 让 React 可跳过中间态渲染，保持输入/滚动流畅
  const deferred = useDeferredValue(markdown || '')
  const blocks = useMemo(
    () => splitNoteBlocks(preprocessNoteMarkdown(deferred)),
    [deferred],
  )

  return (
    <div className="note-md note-md-blocks">
      {blocks.map((source, i) => (
        <Block key={i} source={source} />
      ))}
    </div>
  )
}
