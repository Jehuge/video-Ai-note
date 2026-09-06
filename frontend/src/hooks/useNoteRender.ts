/**
 * useNoteRender：整篇笔记的异步渲染 hook
 *
 * 渲染流程：
 * 1. 主线程 LRU 缓存命中（二次打开同一篇）→ 立即返回，零开销；
 * 2. 未命中 → 交给 Worker 在后台线程编译，期间 UI 完全不卡（可正常滚动/关闭弹窗）；
 * 3. Worker 不可用（极端环境）→ 降级为主线程同步渲染，至少保证功能正确。
 *
 * 只采纳最后一次请求的结果：markdown 快速变化时旧请求的结果直接丢弃。
 */
import { useEffect, useState } from 'react'
import { renderNoteMarkdown } from '../utils/noteRenderer'

// 主线程侧结果缓存：弹窗关闭再打开、Task 详情切换回来都直接命中
const resultCache = new Map<string, string>()
const RESULT_CACHE_MAX = 12

function cacheGet(key: string): string | undefined {
  const hit = resultCache.get(key)
  if (hit !== undefined) {
    resultCache.delete(key)
    resultCache.set(key, hit)
  }
  return hit
}

function cacheSet(key: string, html: string) {
  if (resultCache.size >= RESULT_CACHE_MAX) {
    const oldest = resultCache.keys().next().value
    if (oldest !== undefined) resultCache.delete(oldest)
  }
  resultCache.set(key, html)
}

// Worker 单例：首次使用时才创建（KaTeX 体积较大，放进 worker 分包不进主 bundle）
let worker: Worker | null = null
let workerBroken = false
let nextReqId = 1
const pending = new Map<number, (html: string) => void>()

function getWorker(): Worker | null {
  if (workerBroken) return null
  if (worker) return worker
  try {
    const w = new Worker(new URL('../workers/noteRender.worker.ts', import.meta.url), {
      type: 'module',
    })
    w.addEventListener('message', (e: MessageEvent<{ id: number; html: string }>) => {
      const resolve = pending.get(e.data.id)
      if (resolve) {
        pending.delete(e.data.id)
        resolve(e.data.html)
      }
    })
    w.addEventListener('error', () => {
      workerBroken = true
      pending.forEach((resolve) => resolve(''))
      pending.clear()
    })
    worker = w
    return w
  } catch {
    workerBroken = true
    return null
  }
}

function renderInWorker(markdown: string): Promise<string> {
  return new Promise((resolve) => {
    const w = getWorker()
    if (!w) {
      resolve('')
      return
    }
    const id = nextReqId++
    pending.set(id, resolve)
    w.postMessage({ id, markdown })
  })
}

export function useNoteRender(markdown: string): string | null {
  const [html, setHtml] = useState<string | null>(() => cacheGet(markdown) ?? null)

  useEffect(() => {
    const cached = cacheGet(markdown)
    if (cached !== undefined) {
      setHtml(cached)
      return
    }
    if (!markdown) {
      setHtml('')
      return
    }
    let cancelled = false
    setHtml(null)
    renderInWorker(markdown).then((workerHtml) => {
      if (cancelled) return
      const finalHtml = workerHtml || renderNoteMarkdown(markdown) // worker 失败降级同步渲染
      cacheSet(markdown, finalHtml)
      setHtml(finalHtml)
    })
    return () => {
      cancelled = true
    }
  }, [markdown])

  return html
}
