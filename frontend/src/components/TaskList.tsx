import { useEffect, useState } from 'react'
import { FileVideo, Calendar, Trash2, Loader2, CheckCircle2, AlertCircle, Clock, Ban } from 'lucide-react'
import { useTaskStore } from '../store/taskStore'
import { getTasks, deleteTask } from '../services/api'
import { parseBiliTaskName } from '../utils/biliName'
import toast from 'react-hot-toast'

const statusIcons = {
  completed: <CheckCircle2 className="w-4 h-4 text-green-500" />,
  failed: <AlertCircle className="w-4 h-4 text-red-500" />,
  canceled: <Ban className="w-4 h-4 text-slate-400" />,
  pending: <Clock className="w-4 h-4 text-amber-500" />,
  processing: <Loader2 className="w-4 h-4 animate-spin text-blue-500" />,
  transcribing: <Loader2 className="w-4 h-4 animate-spin text-blue-500" />,
  transcribed: <CheckCircle2 className="w-4 h-4 text-emerald-500" />,
  summarizing: <Loader2 className="w-4 h-4 animate-spin text-blue-500" />,
}



export default function TaskList() {
  const { tasks, currentTaskId, setCurrentTask, loadTasks, removeTask } = useTaskStore()
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set())

  // 加载任务列表
  useEffect(() => {
    const loadTaskList = async (silent = false) => {
      try {
        const response = await getTasks()
        if (response.data.code === 200) {
          // 列表接口不返回 markdown 等大字段，合并时必须保留 store 里已有的值，
          // 否则轮询会把已生成笔记的内容冲掉，导致"笔记消失"
          const existingMap = new Map(useTaskStore.getState().tasks.map(t => [t.id, t]))
          const taskList = response.data.data.map((task: any) => {
            const prev = existingMap.get(task.task_id)
            return {
              id: task.task_id,
              filename: task.filename,
              status: task.status,
              errorMessage: task.error_message,
              source: task.source,
              sourceUrl: task.source_url,
              markdown: task.markdown ?? prev?.markdown ?? '',
              partialMarkdown: task.partial_markdown ?? prev?.partialMarkdown ?? '',
              progressMessage: task.progress_message ?? prev?.progressMessage ?? '',
              createdAt: task.created_at,
            }
          })
          loadTasks(taskList)
        }
      } catch (error: any) {
        if (!silent) {
          console.error('加载任务列表失败:', error)
          // 如果是连接错误，不显示错误（可能是后端未启动）
          if (error.code !== 'ECONNREFUSED' && error.code !== 'ERR_CONNECTION_TIMED_OUT') {
            console.warn('无法连接到后端服务，请确保后端已启动')
          }
        }
      }
    }

    loadTaskList()
    // 定时刷新 + 窗口聚焦时刷新，保证新建任务和进行中状态能自动出现
    const timer = setInterval(() => loadTaskList(true), 10000)
    const onFocus = () => loadTaskList(true)
    window.addEventListener('focus', onFocus)
    return () => {
      clearInterval(timer)
      window.removeEventListener('focus', onFocus)
    }
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
    <div className="flex flex-col h-full bg-gray-50/50">
      <div className="p-4 shrink-0 border-b border-gray-200">
        <h2 className="text-lg font-bold text-gray-900 px-1">我的任务</h2>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4">
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
            {tasks.map((task) => {
              const bili = parseBiliTaskName(task.filename || '')
              return (
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
                    <div className="flex items-start gap-2 mb-2">
                      <div className={`
                      p-1.5 rounded-lg shrink-0 mt-0.5
                      ${currentTaskId === task.id ? 'bg-blue-50 text-blue-600' : 'bg-gray-50 text-gray-500 group-hover:bg-blue-50 group-hover:text-blue-500'}
                    `}>
                        <FileVideo className="w-4 h-4" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <h3 className={`text-sm font-semibold transition-colors truncate ${currentTaskId === task.id ? 'text-blue-700' : 'text-gray-900 group-hover:text-blue-700'
                          }`}
                          title={bili.isBili ? bili.mainTitle : task.filename}
                        >
                          {bili.isBili ? bili.mainTitle : task.filename}
                        </h3>
                        {bili.isBili && bili.subTitle && (
                          <p className="text-xs text-gray-400 truncate mt-0.5" title={task.filename}>
                            {bili.subTitle}
                          </p>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      <div className={`
                      inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-medium border
                      ${task.status === 'completed' || task.status === 'transcribed' ? 'bg-green-50 text-green-700 border-green-100' :
                          task.status === 'failed' ? 'bg-red-50 text-red-700 border-red-100' :
                            task.status === 'canceled' ? 'bg-slate-100 text-slate-600 border-slate-200' :
                              'bg-blue-50 text-blue-700 border-blue-100'}
                    `}>
                        {statusIcons[task.status]}
                        <span>{
                          task.status === 'completed' ? '已完成' :
                            task.status === 'failed' ? '处理失败' :
                              task.status === 'canceled' ? '已停止' :
                                task.status === 'pending' ? '等待处理' :
                                  task.status === 'processing' ? '处理中...' :
                                    task.status === 'transcribing' ? '转写中...' :
                                      task.status === 'transcribed' ? '转写完成' :
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

                    {(task.status === 'failed' || task.status === 'canceled') && task.errorMessage && (
                      <p className="mt-2 text-xs text-red-600 line-clamp-2" title={task.errorMessage}>
                        {task.errorMessage}
                      </p>
                    )}
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
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
