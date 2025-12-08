import { useEffect, useState } from 'react'
import { CheckCircle2, XCircle, Loader2, Clock, Eye } from 'lucide-react'
import { useTaskStore } from '../store/taskStore'
import { getTasks } from '../services/api'
import TaskDetailPanel from './TaskDetailPanel'

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
  const { tasks, currentTaskId, setCurrentTask, loadTasks } = useTaskStore()
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null)

  // 加载任务列表
  useEffect(() => {
    const loadTaskList = async () => {
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
      }
    }

    loadTaskList()
  }, [loadTasks])

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h2 className="text-xl font-semibold mb-4">任务列表</h2>
      
      {tasks.length === 0 ? (
        <p className="text-gray-400 text-sm text-center py-8">暂无任务</p>
      ) : (
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {tasks.map((task) => (
            <div
              key={task.id}
              className={`p-3 rounded-lg transition-colors ${
                currentTaskId === task.id
                  ? 'bg-blue-50 border-2 border-blue-500'
                  : 'bg-gray-50 border-2 border-transparent'
              }`}
            >
              <div className="flex items-start justify-between">
                <div
                  className="flex-1 min-w-0 cursor-pointer"
                  onClick={() => setCurrentTask(task.id)}
                >
                  <p className="text-sm font-medium text-gray-900 truncate">
                    {task.filename}
                  </p>
                  <div className="flex items-center gap-2 mt-1">
                    {statusIcons[task.status]}
                    <span className="text-xs text-gray-500">
                      {statusText[task.status]}
                    </span>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedTaskId(task.id)}
                  className="ml-2 p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors"
                  title="查看详情"
                >
                  <Eye className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
      {selectedTaskId && (
        <TaskDetailPanel
          taskId={selectedTaskId}
          onClose={() => setSelectedTaskId(null)}
        />
      )}
    </div>
  )
}

