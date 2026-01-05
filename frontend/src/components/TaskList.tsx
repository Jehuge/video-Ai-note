import { useEffect, useState, useRef } from 'react'
import { CheckCircle2, XCircle, Loader2, Clock, Trash2 } from 'lucide-react'
import { useTaskStore } from '../store/taskStore'
import { getTasks, deleteTask, uploadVideo } from '../services/api'
import toast from 'react-hot-toast'
import FileConfirmDialog from './FileConfirmDialog'
import { Plus } from 'lucide-react'

const statusIcons = {
  completed: <CheckCircle2 className="w-4 h-4 text-green-500" />,
  failed: <XCircle className="w-4 h-4 text-red-500" />,
  pending: <Clock className="w-4 h-4 text-gray-400" />,
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
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    // 检查文件类型（基于扩展名和 MIME 类型）
    const fileExtension = file.name.split('.').pop()?.toLowerCase()
    const allowedExtensions = ['mp4', 'avi', 'mov', 'mkv', 'webm', 'mp3', 'wav', 'm4a', 'flv', 'wmv']

    const isAllowedExtension = fileExtension && allowedExtensions.includes(fileExtension)
    const isAllowedMime = file.type.startsWith('video/') || file.type.startsWith('audio/')

    if (!isAllowedExtension && !isAllowedMime) {
      toast.error('不支持的文件类型，请上传视频或音频文件')
      e.target.value = ''
      return
    }

    // 检查文件大小（限制 500MB）
    if (file.size > 500 * 1024 * 1024) {
      toast.error('文件大小不能超过 500MB')
      e.target.value = ''
      return
    }

    // 显示确认对话框
    setSelectedFile(file)
    setShowConfirm(true)
    e.target.value = ''
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
    <div className="flex flex-col h-full">
      <div className="p-4 border-b border-gray-200 flex items-center justify-between shrink-0">
        <h2 className="text-base font-semibold text-gray-900">任务列表</h2>
        <button
          onClick={triggerFileUpload}
          disabled={uploading}
          className="p-1.5 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          title="新建任务"
        >
          {uploading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Plus className="w-5 h-5" />}
        </button>
        <input
          type="file"
          ref={fileInputRef}
          className="hidden"
          onChange={handleFileSelect}
          disabled={uploading}
        />
      </div>

      {uploading && (
        <div className="p-4 border-b border-gray-100 bg-blue-50">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-medium text-blue-700">正在上传...</span>
            <span className="text-xs text-blue-700">{uploadProgress}%</span>
          </div>
          <div className="w-full bg-blue-200 rounded-full h-1.5">
            <div
              className="bg-blue-600 h-1.5 rounded-full transition-all duration-300"
              style={{ width: `${uploadProgress}%` }}
            ></div>
          </div>
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-4">
        {tasks.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-400 text-sm">暂无任务</p>
            <p className="text-xs text-gray-400 mt-2">点击顶部 "+" 号上传文件</p>
          </div>
        ) : (
          <div className="space-y-2">
            {tasks.map((task) => (
              <div
                key={task.id}
                className={`p-3 rounded-lg transition-all cursor-pointer border ${currentTaskId === task.id
                    ? 'bg-blue-50 border-blue-500 shadow-sm'
                    : 'bg-white border-gray-200 hover:border-gray-300 hover:shadow-sm'
                  }`}
                onClick={() => {
                  setCurrentTask(task.id)
                }}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate mb-1.5">
                      {task.filename}
                    </p>
                    <div className="flex items-center gap-2">
                      {statusIcons[task.status]}
                      <span className="text-xs text-gray-500">
                        {statusText[task.status]}
                      </span>
                    </div>
                  </div>
                  <button
                    onClick={(e) => handleDelete(task.id, e)}
                    disabled={deletingIds.has(task.id)}
                    className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors shrink-0 disabled:opacity-50 disabled:cursor-not-allowed"
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
