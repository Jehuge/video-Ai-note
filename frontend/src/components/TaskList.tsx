import { useEffect, useState, useRef } from 'react'
import { Plus, UploadCloud, FileVideo, Calendar, Trash2, Loader2, CheckCircle2, AlertCircle, Clock, XCircle } from 'lucide-react'
import { useTaskStore } from '../store/taskStore'
import { getTasks, deleteTask, uploadVideo } from '../services/api'
import toast from 'react-hot-toast'
import FileConfirmDialog from './FileConfirmDialog'

const statusIcons = {
  completed: <CheckCircle2 className="w-4 h-4 text-green-500" />,
  failed: <AlertCircle className="w-4 h-4 text-red-500" />,
  pending: <Clock className="w-4 h-4 text-amber-500" />,
  processing: <Loader2 className="w-4 h-4 animate-spin text-blue-500" />,
  transcribing: <Loader2 className="w-4 h-4 animate-spin text-blue-500" />,
  summarizing: <Loader2 className="w-4 h-4 animate-spin text-blue-500" />,
}

const statusText = {
  pending: '等待中',
  processing: '处理中',
  transcribing: '转写中',
  summarizing: '生成中',
  completed: '已完成',
  failed: '失败',
}

export default function TaskList() {
  const { tasks, currentTaskId, setCurrentTask, loadTasks, removeTask, addTask } = useTaskStore()
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set())
  const tasksLoadedRef = useRef(false)

  // 上传相关状态
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [showConfirm, setShowConfirm] = useState(false)
  const [isDragOver, setIsDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // 加载任务列表
  useEffect(() => {
    // 防止重复加载
    if (tasksLoadedRef.current) {
      return
    }

    const loadTaskList = async () => {
      tasksLoadedRef.current = true
      try {
        const response = await getTasks()
        if (response.data.code === 200) {
          const taskList = response.data.data.map((task: any) => ({
            id: task.task_id,
            filename: task.filename,
            status: task.status,
            markdown: task.markdown,
            createdAt: task.created_at,
          }))
          loadTasks(taskList)
        }
      } catch (error: any) {
        console.error('加载任务列表失败:', error)
        // 如果是连接错误，不显示错误（可能是后端未启动）
        if (error.code !== 'ECONNREFUSED' && error.code !== 'ERR_CONNECTION_TIMED_OUT') {
          console.warn('无法连接到后端服务，请确保后端已启动')
        }
        // 加载失败时重置标记，允许重试
        tasksLoadedRef.current = false
      }
    }

    loadTaskList()
  }, [loadTasks])

  const handleDelete = async (taskId: string, e: React.MouseEvent) => {
    e.stopPropagation() // 阻止触发任务选择

    const task = tasks.find(t => t.id === taskId)
    const taskName = task?.filename || '任务'

    if (!window.confirm(`确定要删除 "${taskName}" 吗？\n\n删除后将无法恢复，包括：\n- 任务记录\n- 上传的文件\n- 生成的笔记和转写结果\n- 相关截图`)) {
      return
    }

    setDeletingIds((prev) => new Set(prev).add(taskId))

    try {
      const response = await deleteTask(taskId)
      if (response.data.code === 200) {
        removeTask(taskId)
        toast.success('任务删除成功')
      } else {
        toast.error(response.data.msg || '删除失败')
      }
    } catch (error: any) {
      console.error('删除任务失败:', error)
      toast.error(error.response?.data?.msg || '删除失败，请稍后重试')
    } finally {
      setDeletingIds((prev) => {
        const newSet = new Set(prev)
        newSet.delete(taskId)
        return newSet
      })
    }
  }

  // 处理文件选择
  const handleFile = (file: File) => {
    // 检查文件类型（基于扩展名和 MIME 类型）
    const fileExtension = file.name.split('.').pop()?.toLowerCase()
    const allowedExtensions = ['mp4', 'avi', 'mov', 'mkv', 'webm', 'mp3', 'wav', 'm4a', 'flv', 'wmv']

    const isAllowedExtension = fileExtension && allowedExtensions.includes(fileExtension)
    const isAllowedMime = file.type.startsWith('video/') || file.type.startsWith('audio/')

    if (!isAllowedExtension && !isAllowedMime) {
      toast.error('不支持的文件类型，请上传视频或音频文件')
      return
    }

    // 检查文件大小（限制 500MB）
    if (file.size > 500 * 1024 * 1024) {
      toast.error('文件大小不能超过 500MB')
      return
    }

    // 显示确认对话框
    setSelectedFile(file)
    setShowConfirm(true)
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      handleFile(file)
    }
    e.target.value = ''
  }

  // 拖拽处理
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) {
      handleFile(file)
    }
  }

  // 确认上传
  const handleConfirmUpload = async (screenshot: boolean, noteStyle: string) => {
    if (!selectedFile) return

    // 获取当前选择的模型配置
    const selectedModelId = localStorage.getItem('selectedModel')
    const modelConfigs = localStorage.getItem('modelConfigs')

    let modelConfig = null
    if (selectedModelId && modelConfigs) {
      try {
        const configs = JSON.parse(modelConfigs)
        // 从 selectedModelId 中提取 provider 和 modelId
        const firstDashIndex = selectedModelId.indexOf('-')
        if (firstDashIndex > 0) {
          const provider = selectedModelId.substring(0, firstDashIndex)
          const modelId = selectedModelId.substring(firstDashIndex + 1)
          const providerConfig = configs[provider]

          if (providerConfig) {
            modelConfig = {
              provider,
              api_key: providerConfig.apiKey || '',
              base_url: providerConfig.baseUrl || '',
              model: modelId,
            }
          }
        }
      } catch (e) {
        console.error('解析模型配置失败:', e)
      }
    }

    setShowConfirm(false)
    setUploading(true)
    setUploadProgress(0)

    try {
      const response = await uploadVideo(
        selectedFile,
        screenshot,
        modelConfig,
        noteStyle,
        (progress) => {
          setUploadProgress(progress)
        }
      )

      if (response.data.code === 200) {
        const { task_id, filename } = response.data.data

        // 添加到任务列表
        addTask({
          id: task_id,
          filename,
          status: 'pending',
          markdown: '',
          createdAt: new Date().toISOString()
        })

        // 自动选中新任务
        setCurrentTask(task_id)

        toast.success('文件上传成功！')
        setSelectedFile(null)
      } else {
        toast.error(response.data.msg || '上传失败')
      }
    } catch (error: any) {
      console.error('上传失败:', error)
      if (error.code === 'ECONNABORTED') {
        toast.error('上传超时，请检查网络连接或文件大小')
      } else {
        toast.error(error.response?.data?.msg || '上传失败，请稍后重试')
      }
    } finally {
      setUploading(false)
      setUploadProgress(0)
    }
  }

  const handleCancelUpload = () => {
    setShowConfirm(false)
    setSelectedFile(null)
  }

  // 触发文件选择
  const triggerFileUpload = () => {
    fileInputRef.current?.click()
  }

  return (
    <div className="flex flex-col h-full bg-gray-50/50">
      <div className="p-4 shrink-0">
        <h2 className="text-lg font-bold text-gray-900 mb-4 px-1">我的任务</h2>

        {/* 拖拽上传区域 */}
        <div
          onClick={triggerFileUpload}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`
            relative group cursor-pointer overflow-hidden rounded-xl border-2 border-dashed transition-all duration-300
            ${isDragOver
              ? 'border-blue-500 bg-blue-50 scale-[1.02]'
              : 'border-blue-200 bg-white hover:border-blue-400 hover:bg-blue-50/50 hover:shadow-md'
            }
            ${uploading ? 'pointer-events-none opacity-80' : ''}
          `}
        >
          <div className="p-6 flex flex-col items-center justify-center text-center">
            <div className={`
              p-3 rounded-full mb-3 transition-colors duration-300
              ${isDragOver ? 'bg-blue-100' : 'bg-blue-50 group-hover:bg-blue-100'}
            `}>
              {uploading ? (
                <Loader2 className="w-6 h-6 text-blue-600 animate-spin" />
              ) : (
                <UploadCloud className="w-6 h-6 text-blue-600" />
              )}
            </div>

            {uploading ? (
              <div className="w-full max-w-[140px]">
                <div className="text-sm font-medium text-blue-900 mb-1">正在上传...</div>
                <div className="text-xs text-blue-600 mb-2">{uploadProgress}%</div>
                <div className="h-1 bg-blue-100 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-500 transition-all duration-300"
                    style={{ width: `${uploadProgress}%` }}
                  />
                </div>
              </div>
            ) : (
              <>
                <h3 className="text-sm font-semibold text-gray-900 mb-1">
                  {isDragOver ? '释放文件以开始' : '点击或拖拽上传'}
                </h3>
                <p className="text-xs text-gray-500 px-2 leading-relaxed">
                  支持视频与音频文件<br />自动生成 AI 笔记
                </p>
              </>
            )}
          </div>

          <input
            type="file"
            ref={fileInputRef}
            className="hidden"
            onChange={handleFileSelect}
            disabled={uploading}
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 pb-4">
        {tasks.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-center border-2 border-dashed border-gray-100 rounded-xl bg-white/50">
            <div className="p-3 bg-gray-50 rounded-full mb-3">
              <FileVideo className="w-6 h-6 text-gray-300" />
            </div>
            <p className="text-sm font-medium text-gray-500">暂无任务</p>
            <p className="text-xs text-gray-400 mt-1">上传文件开始体验</p>
          </div>
        ) : (
          <div className="space-y-3">
            {tasks.map((task) => (
              <div
                key={task.id}
                className={`
                group relative p-4 rounded-xl transition-all duration-200 cursor-pointer border
                ${currentTaskId === task.id
                    ? 'bg-white border-blue-500 shadow-md ring-1 ring-blue-100'
                    : 'bg-white border-gray-100 hover:border-blue-200 hover:shadow-md'
                  }
              `}
                onClick={() => {
                  setCurrentTask(task.id)
                }}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2">
                      <div className={`
                      p-1.5 rounded-lg shrink-0
                      ${currentTaskId === task.id ? 'bg-blue-50 text-blue-600' : 'bg-gray-50 text-gray-500 group-hover:bg-blue-50 group-hover:text-blue-500'}
                    `}>
                        <FileVideo className="w-4 h-4" />
                      </div>
                      <h3 className={`text-sm font-semibold truncate transition-colors ${currentTaskId === task.id ? 'text-blue-700' : 'text-gray-900 group-hover:text-blue-700'
                        }`}
                        title={task.filename}
                      >
                        {task.filename}
                      </h3>
                    </div>

                    <div className="flex items-center gap-3">
                      <div className={`
                      inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-medium border
                      ${task.status === 'completed' ? 'bg-green-50 text-green-700 border-green-100' :
                          task.status === 'failed' ? 'bg-red-50 text-red-700 border-red-100' :
                            'bg-blue-50 text-blue-700 border-blue-100'}
                    `}>
                        {statusIcons[task.status]}
                        <span>{
                          task.status === 'completed' ? '已完成' :
                            task.status === 'failed' ? '处理失败' :
                              task.status === 'pending' ? '等待处理' :
                                task.status === 'processing' ? '处理中...' :
                                  task.status === 'transcribing' ? '转写中...' :
                                    task.status === 'summarizing' ? '生成中...' : task.status
                        }</span>
                      </div>

                      {task.createdAt && (
                        <div className="flex items-center gap-1 text-xs text-gray-400">
                          <Calendar className="w-3 h-3" />
                          <span>{new Date(task.createdAt).toLocaleDateString()}</span>
                        </div>
                      )}
                    </div>
                  </div>

                  <button
                    onClick={(e) => handleDelete(task.id, e)}
                    disabled={deletingIds.has(task.id)}
                    className="
                    opacity-0 group-hover:opacity-100 transition-all
                    p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg
                    disabled:opacity-0
                  "
                    title="删除任务"
                  >
                    {deletingIds.has(task.id) ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Trash2 className="w-4 h-4" />
                    )}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <FileConfirmDialog
        file={selectedFile}
        open={showConfirm}
        onConfirm={handleConfirmUpload}
        onCancel={handleCancelUpload}
      />
    </div>
  )
}
