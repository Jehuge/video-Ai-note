/**
 * 笔记渲染 Worker：markdown-it + KaTeX 编译在后台线程执行，
 * 整篇长笔记（数百公式）的编译耗时（数百 ms 到数秒）不再冻结 UI 线程。
 *
 * 协议：postMessage({ id, markdown }) → 回 { id, html }；id 用于匹配最新请求，
 * 主线程只采纳最后一次请求的结果，中途取消无副作用。
 */
import { renderNoteMarkdown } from '../utils/noteRenderer'

type RenderRequest = { id: number; markdown: string }
type RenderResponse = { id: number; html: string }

const ctx = self as unknown as {
  addEventListener: (type: 'message', cb: (e: MessageEvent<RenderRequest>) => void) => void
  postMessage: (msg: RenderResponse) => void
}

ctx.addEventListener('message', (e) => {
  const { id, markdown } = e.data
  const html = renderNoteMarkdown(markdown ?? '')
  ctx.postMessage({ id, html })
})
