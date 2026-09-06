import { X } from 'lucide-react'
import TranscriptViewer from './TranscriptViewer'
import EnhancedMarkdownViewer from './EnhancedMarkdownViewer'

interface ContentPreviewModalProps {
  type: 'transcript' | 'markdown' | 'video'
  content: any
  title: string
  filename?: string
  taskId?: string
  onClose: () => void
}

export default function ContentPreviewModal({
  type,
  content,
  title,
  filename,
  taskId,
  onClose,
}: ContentPreviewModalProps) {
  // 弹窗外壳立即响应点击；长笔记由 EnhancedMarkdownViewer 在 Web Worker
  // 中后台编译（内部自带"正在渲染"加载态），不再阻塞 UI 线程

  return (
    <div 
      className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onClose()
        }
      }}
    >
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-6xl h-[90vh] flex flex-col overflow-hidden">
        {/* 头部 */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 shrink-0">
          <div>
            <h2 className="text-xl font-semibold text-gray-900">{title}</h2>
            {filename && <p className="text-sm text-gray-500 mt-1">{filename}</p>}
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            title="关闭"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* 内容区域 */}
        <div className="flex-1 min-h-0 overflow-hidden">
          {type === 'transcript' ? (
            <div className="h-full overflow-y-auto p-6">
              <TranscriptViewer transcript={content} />
            </div>
          ) : type === 'video' ? (
            <div className="h-full flex items-center justify-center bg-black p-6">
              <video
                src={content}
                controls
                className="max-w-full max-h-full"
                style={{ maxHeight: 'calc(90vh - 120px)' }}
              >
                您的浏览器不支持视频播放
              </video>
            </div>
          ) : (
            <div className="h-full overflow-hidden">
              {/* 弹窗已有标题，查看器只渲染导出按钮行，避免标题重复且保留导出功能 */}
              <EnhancedMarkdownViewer markdown={content} filename={filename} taskId={taskId} headerMode="actions" />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

