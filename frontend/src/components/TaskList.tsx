import { useEffect, useState, useRef } from 'react'
import { CheckCircle2, XCircle, Loader2, Clock, Trash2 } from 'lucide-react'
import { useTaskStore } from '../store/taskStore'
import { getTasks, deleteTask } from '../services/api'
import toast from 'react-hot-toast'

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
  const { tasks, currentTaskId, setCurrentTask, loadTasks, removeTask } = useTaskStore()
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set())
  const tasksLoadedRef = useRef(false)

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

  return (
    <div className="p-4">
      {tasks.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-400 text-sm">暂无任务</p>
          <p className="text-xs text-gray-400 mt-2">上传文件后任务将显示在这里</p>
        </div>
      ) : (
        <div className="space-y-2">
          {tasks.map((task) => (
            <div
              key={task.id}
              className={`p-3 rounded-lg transition-all cursor-pointer border ${
                currentTaskId === task.id
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
  )
}
