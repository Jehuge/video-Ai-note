import { X, FileVideo, CheckCircle2 } from 'lucide-react'
import { useState } from 'react'

export interface FileLike {
  name: string
  size: number
  type: string
  lastModified: number
}

interface FileConfirmDialogProps {
  file: File | FileLike | null
  open: boolean
  onConfirm: (screenshot: boolean) => void
  onCancel: () => void
  title?: string
  confirmText?: string
}

export default function FileConfirmDialog({
  file,
  open,
  onConfirm,
  onCancel,
  title = "确认上传文件",
  confirmText = "确认上传"
}: FileConfirmDialogProps) {
  const [enableScreenshot, setEnableScreenshot] = useState(true)

  if (!open || !file) return null

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
        <div className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-xl font-semibold">{title}</h3>
            <button
              onClick={onCancel}
              className="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="space-y-4">
            <div className="flex items-start gap-4 p-4 bg-gray-50 rounded-lg">
              <FileVideo className="w-8 h-8 text-blue-500 flex-shrink-0 mt-1" />
              <div className="flex-1 min-w-0">
                <p className="font-medium text-gray-900 truncate">{file.name}</p>
                <div className="mt-2 space-y-1 text-sm text-gray-600">
                  <p>类型: {file.type || '未知'}</p>
                  <p>大小: {formatFileSize(file.size)}</p>
                  <p>修改时间: {new Date(file.lastModified).toLocaleString()}</p>
                </div>
              </div>
            </div>

            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h4 className="font-medium text-blue-900 mb-2">处理流程：</h4>
              <ol className="list-decimal list-inside space-y-1 text-sm text-blue-800">
                <li>上传文件到服务器</li>
                <li>提取音频（如果是视频文件）</li>
                <li>转写音频为文字</li>
                <li>使用 AI 生成结构化笔记</li>
              </ol>
            </div>

            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 mb-4">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={enableScreenshot}
                  onChange={(e) => setEnableScreenshot(e.target.checked)}
                  className="w-4 h-4 text-blue-600 rounded"
                />
                <span className="text-sm text-yellow-900">
                  启用自动截图（在笔记中插入视频关键帧截图）
                </span>
              </label>
            </div>

            <div className="flex gap-3">
              <button
                onClick={onCancel}
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
              >
                取消
              </button>
              <button
                onClick={() => onConfirm(enableScreenshot)}
                className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center justify-center gap-2"
              >
                <CheckCircle2 className="w-4 h-4" />
                {confirmText}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
