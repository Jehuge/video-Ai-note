import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import 'github-markdown-css/github-markdown.css'
import { ScrollArea } from './ui/ScrollArea'
import { Copy, Download } from 'lucide-react'
import { useState } from 'react'
import toast from 'react-hot-toast'

interface EnhancedMarkdownViewerProps {
  markdown: string
  filename?: string
}

export default function EnhancedMarkdownViewer({
  markdown,
  filename,
}: EnhancedMarkdownViewerProps) {
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

  const handleDownload = () => {
    const name = filename?.replace(/\.[^/.]+$/, '') || 'note'
    const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `${name}.md`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(link.href)
  }

  if (!markdown) {
    return (
      <div className="flex h-full items-center justify-center text-gray-400">
        暂无笔记内容
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col bg-white rounded-lg border shadow-sm">
      <div className="flex items-center justify-between border-b p-4">
        <div>
          <h2 className="text-lg font-semibold">笔记预览</h2>
          {filename && <p className="text-sm text-gray-500 mt-1">{filename}</p>}
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleCopy}
            className="flex items-center gap-2 px-3 py-1.5 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
          >
            <Copy className="w-4 h-4" />
            {copied ? '已复制' : '复制'}
          </button>
          <button
            onClick={handleDownload}
            className="flex items-center gap-2 px-3 py-1.5 text-sm bg-blue-600 text-white hover:bg-blue-700 rounded-lg transition-colors"
          >
            <Download className="w-4 h-4" />
            下载
          </button>
        </div>
      </div>
      
      <ScrollArea className="flex-1" style={{ maxHeight: 'calc(100vh - 300px)' }}>
        <div className="markdown-body prose max-w-none p-6" style={{ minHeight: '100%' }}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{markdown}</ReactMarkdown>
        </div>
      </ScrollArea>
    </div>
  )
}

