import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import 'github-markdown-css/github-markdown.css'
import { Copy, Download, FileDown } from 'lucide-react'
import { useState, useRef } from 'react'
import toast from 'react-hot-toast'
import Zoom from 'react-medium-image-zoom'
import 'react-medium-image-zoom/dist/styles.css'
import jsPDF from 'jspdf'
import html2canvas from 'html2canvas'
import { exportPDF } from '../services/api'

interface EnhancedMarkdownViewerProps {
  markdown: string
  filename?: string
  taskId?: string
}

// 获取API基础URL
const getBaseURL = () => {
  const baseURL = import.meta.env.VITE_API_BASE_URL || '/api'
  return baseURL.replace(/\/$/, '')
}

export default function EnhancedMarkdownViewer({
  markdown,
  filename,
  taskId,
}: EnhancedMarkdownViewerProps) {
  const [copied, setCopied] = useState(false)
  const markdownRef = useRef<HTMLDivElement>(null)
  const baseURL = getBaseURL()

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
    // 如果提供了 taskId，优先使用后端 API 生成可复制文本的 PDF
    if (taskId) {
      try {
        toast.loading('正在生成PDF（可复制文本），请稍候...', { id: 'pdf-generating' })
        const response = await exportPDF(taskId)
        
        // 创建下载链接
        const blob = new Blob([response.data], { type: 'application/pdf' })
        const url = window.URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        const name = filename?.replace(/\.[^/.]+$/, '') || 'note'
        link.download = `${name}.pdf`
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        window.URL.revokeObjectURL(url)
        
        toast.dismiss('pdf-generating')
        toast.success('PDF文件已下载（文字可复制）')
        return
      } catch (error: any) {
        console.error('后端PDF生成失败，使用前端生成:', error)
        // 如果后端失败，fallback 到前端生成
        if (error.response?.status !== 404) {
          toast.dismiss('pdf-generating')
          toast.error('后端PDF生成失败，使用前端生成方式')
        }
      }
    }
    
    // 前端生成 PDF（图片模式，文字不可复制）
    if (!markdownRef.current) {
      toast.error('无法生成PDF，请稍后重试')
      return
    }

    try {
      if (!taskId) {
        toast.loading('正在生成PDF（图片模式），请稍候...', { id: 'pdf-generating' })
      }
      
      // 等待所有图片加载完成
      const images = markdownRef.current.querySelectorAll('img')
      const imagePromises = Array.from(images).map((img) => {
        if (img.complete && img.naturalHeight !== 0) {
          return Promise.resolve()
        }
        return new Promise((resolve) => {
          const timeout = setTimeout(() => {
            resolve(null) // 超时也继续
          }, 10000)
          
          img.onload = () => {
            clearTimeout(timeout)
            resolve(null)
          }
          img.onerror = () => {
            clearTimeout(timeout)
            resolve(null) // 即使加载失败也继续
          }
        })
      })
      await Promise.all(imagePromises)

      // 使用html2canvas将内容转换为canvas，改进配置以避免图片截断
      const canvas = await html2canvas(markdownRef.current, {
        scale: 2,
        useCORS: true,
        allowTaint: false,
        logging: false,
        backgroundColor: '#ffffff',
        width: markdownRef.current.scrollWidth,
        height: markdownRef.current.scrollHeight,
        windowWidth: markdownRef.current.scrollWidth,
        windowHeight: markdownRef.current.scrollHeight,
        onclone: (clonedDoc) => {
          // 确保克隆文档中的图片都已加载
          const clonedImages = clonedDoc.querySelectorAll('img')
          clonedImages.forEach((img: HTMLImageElement) => {
            if (!img.complete) {
              img.style.display = 'none'
            }
          })
        }
      })

      // 计算PDF尺寸
      const imgWidth = canvas.width
      const imgHeight = canvas.height
      const pdfWidth = 210 // A4宽度（mm）
      const pdfHeight = (imgHeight * pdfWidth) / imgWidth
      
      // 创建PDF
      const pdf = new jsPDF('p', 'mm', 'a4')
      const pageHeight = pdf.internal.pageSize.height
      const pageWidth = pdf.internal.pageSize.width
      const margin = 10 // 页边距（mm）
      const contentWidth = pageWidth - 2 * margin
      
      // 计算每页可以容纳的高度
      const contentHeightPerPage = pageHeight - 2 * margin
      const totalPages = Math.ceil(pdfHeight / contentHeightPerPage)
      
      let yPosition = -margin // 从顶部开始，减去 margin 因为 addImage 的 y 是相对于页面的
      
      // 添加第一页
      pdf.addImage(
        canvas.toDataURL('image/png', 0.95), 
        'PNG', 
        margin, 
        yPosition, 
        contentWidth, 
        pdfHeight
      )
      
      // 如果内容超过一页，添加更多页面
      for (let page = 1; page < totalPages; page++) {
        pdf.addPage()
        yPosition = -margin - (page * contentHeightPerPage)
        pdf.addImage(
          canvas.toDataURL('image/png', 0.95), 
          'PNG', 
          margin, 
          yPosition, 
          contentWidth, 
          pdfHeight
        )
      }

      // 下载PDF
      const name = filename?.replace(/\.[^/.]+$/, '') || 'note'
      pdf.save(`${name}.pdf`)
      
      toast.dismiss('pdf-generating')
      toast.success('PDF文件已下载（图片模式，文字不可复制）')
    } catch (error) {
      console.error('生成PDF失败:', error)
      toast.dismiss('pdf-generating')
      toast.error('生成PDF失败，请稍后重试')
    }
  }

  // 处理图片URL，确保使用正确的baseURL
  const processMarkdown = (md: string) => {
    // 由于markdown中的路径已经是 /api/note_results/screenshots/...
    // 而vite代理已经配置了 /api 代理，所以直接返回即可
    // 不需要再添加baseURL，避免重复
    return md
  }

  if (!markdown) {
    return (
      <div className="flex h-full items-center justify-center text-gray-400">
        暂无笔记内容
      </div>
    )
  }

  const processedMarkdown = processMarkdown(markdown)

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* 固定头部工具栏 */}
      <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4 bg-white shrink-0">
        <div>
          <h2 className="text-base font-semibold text-gray-900">笔记预览</h2>
          {filename && <p className="text-xs text-gray-500 mt-1">{filename}</p>}
        </div>
        <div className="flex gap-2">
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
            title="下载PDF文件（包含图片）"
          >
            <FileDown className="w-4 h-4" />
            PDF
          </button>
        </div>
      </div>
      
      {/* Markdown内容区域 - 内容自然高度，参与父容器滚动 */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        <div 
          ref={markdownRef}
          className="markdown-body prose prose-slate max-w-none px-6 py-6 pb-12" 
        >
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              // 处理图片，支持缩放
              img: ({ node, ...props }) => {
                let src = props.src || ''
                // 如果已经是完整URL（http/https/data），直接使用
                if (src.startsWith('http') || src.startsWith('data:')) {
                  // 已经是完整URL，不需要处理
                } else if (src.startsWith('/api/')) {
                  // 路径已经包含 /api/，vite代理会处理，直接使用
                  // 不需要再添加baseURL
                } else if (src.startsWith('/')) {
                  // 其他以 / 开头的路径，可能需要添加baseURL
                  // 但通常markdown中的路径已经是 /api/... 格式
                  src = src
                } else {
                  // 相对路径，添加baseURL
                  src = `${baseURL}/${src}`
                }
                
                // 使用 figure 标签包裹图片，避免在 p 标签内嵌套 div
                return (
                  <figure className="my-8 flex justify-center">
                    <Zoom>
                      <img
                        src={src}
                        alt={props.alt || ''}
                        className="max-w-full cursor-zoom-in rounded-lg object-cover shadow-md transition-all hover:shadow-lg"
                        style={{ maxHeight: '500px' }}
                        crossOrigin="anonymous"
                        onError={(e) => {
                          // 如果图片加载失败，尝试使用完整URL
                          const target = e.target as HTMLImageElement
                          const originalSrc = props.src || ''
                          console.warn('图片加载失败:', originalSrc, '当前src:', target.src)
                          // 如果原始路径是 /api/ 开头，说明路径是正确的，可能是服务器问题
                          // 不需要再次尝试修改URL
                        }}
                      />
                    </Zoom>
                  </figure>
                )
              },
              // 改进标题样式
              h1: ({ children, ...props }) => (
                <h1
                  className="text-gray-900 my-6 scroll-m-20 text-3xl font-extrabold tracking-tight"
                  {...props}
                >
                  {children}
                </h1>
              ),
              h2: ({ children, ...props }) => (
                <h2
                  className="text-gray-900 mt-10 mb-4 scroll-m-20 border-b border-gray-200 pb-2 text-2xl font-semibold tracking-tight first:mt-0"
                  {...props}
                >
                  {children}
                </h2>
              ),
              h3: ({ children, ...props }) => (
                <h3
                  className="text-gray-900 mt-8 mb-4 scroll-m-20 text-xl font-semibold tracking-tight"
                  {...props}
                >
                  {children}
                </h3>
              ),
              // 改进段落样式
              p: ({ children, ...props }) => {
                // 如果段落只包含一个图片，直接返回图片（不包裹在p中）
                if (
                  Array.isArray(children) &&
                  children.length === 1 &&
                  typeof children[0] === 'object' &&
                  children[0] !== null &&
                  'type' in children[0] &&
                  (children[0] as any).type === 'figure'
                ) {
                  return <>{children}</>
                }
                
                return (
                  <p className="leading-7 text-gray-700 [&:not(:first-child)]:mt-6" {...props}>
                    {children}
                  </p>
                )
              },
              // 改进列表样式
              ul: ({ children, ordered, ...props }) => (
                <ul className="my-6 ml-6 list-disc [&>li]:mt-2" {...props}>
                  {children}
                </ul>
              ),
              ol: ({ children, ordered, ...props }) => (
                <ol className="my-6 ml-6 list-decimal [&>li]:mt-2" {...props}>
                  {children}
                </ol>
              ),
              // 改进代码块样式
              code: ({ inline, className, children, ...props }) => {
                if (!inline) {
                  return (
                    <code
                      className="block bg-gray-100 rounded-lg p-4 my-4 overflow-x-auto text-sm"
                      {...props}
                    >
                      {children}
                    </code>
                  )
                }
                return (
                  <code
                    className="bg-gray-100 rounded px-1.5 py-0.5 font-mono text-sm"
                    {...props}
                  >
                    {children}
                  </code>
                )
              },
              // 改进引用样式
              blockquote: ({ children, ...props }) => (
                <blockquote
                  className="border-l-4 border-gray-300 pl-4 italic text-gray-600 my-6"
                  {...props}
                >
                  {children}
                </blockquote>
              ),
            }}
          >
            {processedMarkdown}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  )
}
