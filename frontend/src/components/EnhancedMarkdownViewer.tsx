import { Copy, Download, FileDown, Loader2 } from 'lucide-react'
import { useRef, useState } from 'react'
import toast from 'react-hot-toast'
import { useNoteRender } from '../hooks/useNoteRender'
import { exportPDF } from '../services/api'
import { noteTitle } from '../utils/notePrint'

interface EnhancedMarkdownViewerProps {
  markdown: string
  filename?: string
  taskId?: string
  /** 头部模式：full=标题+导出按钮；actions=仅导出按钮（外层已有标题）；none=无头部 */
  headerMode?: 'full' | 'actions' | 'none'
  /** @deprecated 兼容旧用法，等价于 headerMode='none' */
  showHeader?: boolean
}

export default function EnhancedMarkdownViewer({
  markdown,
  filename,
  taskId,
  headerMode,
  showHeader,
}: EnhancedMarkdownViewerProps) {
  const mode: 'full' | 'actions' | 'none' =
    headerMode ?? (showHeader === false ? 'none' : 'full')
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(markdown)
      setCopied(true)
      toast.success('已复制到剪贴板')
      setTimeout(() => setCopied(false), 2000)
    } catch (e) {
      toast.error('复制失败')
    }
  }

  const handleDownloadMarkdown = async () => {
    try {
      toast.loading('正在处理图片，请稍候...', { id: 'markdown-processing' })
      
      const name = filename?.replace(/\.[^/.]+$/, '') || 'note'
      
      // 将 markdown 中的图片路径转换为 base64
      let processedMarkdown = markdown
      const imageRegex = /!\[\]\((.*?)\)/g
      const imageMatches = Array.from(markdown.matchAll(imageRegex))
      
      // 处理所有图片
      for (const match of imageMatches) {
        const imageUrl = match[1]
        
        // 如果已经是 base64，跳过
        if (imageUrl.startsWith('data:')) {
          continue
        }
        
        try {
          // 构建完整的图片 URL
          let fullImageUrl = imageUrl
          if (imageUrl.startsWith('/api/')) {
            // 已经是完整路径，使用 baseURL
            const apiBaseURL = import.meta.env.VITE_API_BASE_URL || ''
            if (apiBaseURL && !imageUrl.startsWith('http')) {
              fullImageUrl = `${apiBaseURL}${imageUrl}`
            } else if (!imageUrl.startsWith('http')) {
              // 使用当前页面的 origin
              fullImageUrl = `${window.location.origin}${imageUrl}`
            }
          } else if (imageUrl.startsWith('/')) {
            fullImageUrl = `${window.location.origin}${imageUrl}`
          }
          
          // 获取图片并转换为 base64
          const response = await fetch(fullImageUrl)
          if (response.ok) {
            const blob = await response.blob()
            const reader = new FileReader()
            const base64 = await new Promise<string>((resolve, reject) => {
              reader.onloadend = () => {
                if (typeof reader.result === 'string') {
                  resolve(reader.result)
                } else {
                  reject(new Error('Failed to convert image to base64'))
                }
              }
              reader.onerror = reject
              reader.readAsDataURL(blob)
            })
            
            // 替换 markdown 中的图片路径
            processedMarkdown = processedMarkdown.replace(match[0], `![](${base64})`)
          } else {
            console.warn(`Failed to fetch image: ${fullImageUrl}`)
          }
        } catch (error) {
          console.error(`Error processing image ${imageUrl}:`, error)
          // 如果图片处理失败，保留原路径
        }
      }
      
      const blob = new Blob([processedMarkdown], { type: 'text/markdown;charset=utf-8' })
      const link = document.createElement('a')
      link.href = URL.createObjectURL(blob)
      link.download = `${name}.md`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(link.href)
      
      toast.dismiss('markdown-processing')
      toast.success('Markdown文件已下载（图片已嵌入）')
    } catch (error) {
      console.error('下载 Markdown 失败:', error)
      toast.dismiss('markdown-processing')
      toast.error('下载失败，请稍后重试')
    }
  }

  const handleDownloadPDF = async () => {
    if (!taskId) {
      toast.error('当前笔记未绑定任务，无法导出 PDF')
      return
    }

    const toastId = 'pdf-generating'
    try {
      toast.loading('正在生成 PDF，请稍候...', { id: toastId })
      const response = await exportPDF(taskId)
      const contentType = response.data?.type || ''
      if (!contentType.includes('application/pdf')) {
        let message = '服务器没有返回 PDF 文件'
        if (response.data instanceof Blob) {
          try {
            const payload = JSON.parse(await response.data.text())
            message = payload?.msg || message
          } catch {
            // Keep the generic message when the response is not JSON.
          }
        }
        throw new Error(message)
      }

      const blob = response.data instanceof Blob
        ? response.data
        : new Blob([response.data], { type: 'application/pdf' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `${noteTitle(filename)}_note.pdf`
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
      toast.success('PDF 已下载', { id: toastId })
    } catch (error) {
      console.error('PDF 导出失败:', error)
      const message = error instanceof Error ? error.message : 'PDF 导出失败，请稍后重试'
      toast.error(message, { id: toastId })
    }
  }


  // ===== 渲染管线：markdown-it 在 Web Worker 中整篇编译（不阻塞 UI 线程），
  // 二次打开走主线程缓存即时显示。html === null 表示后台仍在编译，先出骨架 =====
  const renderedHtml = useNoteRender(markdown)
  const contentScrollRef = useRef<HTMLDivElement>(null)

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* 固定头部工具栏：full 显示标题，actions 只显示导出按钮 */}
      {mode !== 'none' && (
      <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4 bg-white shrink-0">
        {mode === 'full' && (
        <div>
          <h2 className="text-base font-semibold text-gray-900">笔记预览</h2>
          {filename && <p className="text-xs text-gray-500 mt-1">{filename}</p>}
        </div>
        )}
        <div className={`flex gap-2 ${mode === 'actions' ? 'w-full justify-end' : ''}`}>
          <button
            onClick={handleCopy}
            className="flex items-center gap-2 px-3 py-1.5 text-sm bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg transition-colors"
            title="复制内容"
          >
            <Copy className="w-4 h-4" />
            {copied ? '已复制' : '复制'}
          </button>
          <button
            onClick={handleDownloadMarkdown}
            className="flex items-center gap-2 px-3 py-1.5 text-sm bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg transition-colors"
            title="下载Markdown文件"
          >
            <Download className="w-4 h-4" />
            Markdown
          </button>
          <button
            onClick={handleDownloadPDF}
            className="flex items-center gap-2 px-3 py-1.5 text-sm bg-blue-600 text-white hover:bg-blue-700 rounded-lg transition-colors shadow-sm"
            title="导出 PDF（后端直接生成）"
          >
            <FileDown className="w-4 h-4" />
            PDF
          </button>
        </div>
      </div>
      )}
      
      {/* Markdown内容区域 - worker 编译完成后一次性注入的 HTML */}
      <div className="flex-1 min-h-0 overflow-y-auto" ref={contentScrollRef}>
        {renderedHtml === null ? (
          <div className="h-full flex flex-col items-center justify-center text-gray-400">
            <Loader2 className="w-6 h-6 animate-spin mb-3" />
            <p className="text-sm">正在渲染笔记…</p>
          </div>
        ) : (
          <div
            className="note-md w-full max-w-4xl mx-auto px-6 sm:px-10 py-6"
            dangerouslySetInnerHTML={{ __html: renderedHtml }}
          />
        )}
      </div>

    </div>
  )
}
