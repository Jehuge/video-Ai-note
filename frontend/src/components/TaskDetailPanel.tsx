import { useEffect, useState, useRef } from 'react'
import { X, FileVideo, Music, FileText, BookOpen } from 'lucide-react'
import { useTaskStore } from '../store/taskStore'
import { getTaskStatus, confirmStep, regenerateNote } from '../services/api'
import StepProgress, { StepStatus } from './StepProgress'
import TranscriptViewer from './TranscriptViewer'
import EnhancedMarkdownViewer from './EnhancedMarkdownViewer'
import toast from 'react-hot-toast'

interface TaskDetailPanelProps {
  taskId: string
  onClose: () => void
}

export default function TaskDetailPanel({ taskId, onClose }: TaskDetailPanelProps) {
  const { tasks, updateTask } = useTaskStore()
  const task = tasks.find((t) => t.id === taskId)
  const [steps, setSteps] = useState<any[]>([])
  const [autoProcess, setAutoProcess] = useState(false)
  const [transcript, setTranscript] = useState<any>(null)
  const [regenerateStyle, setRegenerateStyle] = useState<string>('')

  // 初始化步骤
  useEffect(() => {
    if (!task) return

    // 检查转录是否完成（通过 transcript 状态判断）
    const isTranscribeCompleted = transcript && transcript.segments && transcript.segments.length > 0

    const initialSteps = [
      {
        id: 'upload',
        name: '文件上传',
        description: '将文件上传到服务器',
        status: 'completed' as StepStatus,
        result: task.filename ? (
          <div className="flex items-center gap-2 text-sm">
            <FileVideo className="w-4 h-4 text-blue-500" />
            <span>{task.filename}</span>
          </div>
        ) : null,
      },
      {
        id: 'extract',
        name: '提取音频',
        description: '从视频文件中提取音频（如果是视频）',
        status: (task.status === 'pending'
          ? 'waiting_confirm'
          : ['processing', 'transcribing', 'summarizing', 'completed'].includes(task.status)
            ? 'completed'
            : 'pending') as StepStatus,
        canConfirm: task.status === 'pending',
        onConfirm: () => handleStepConfirm('extract'),
        result: task.status !== 'pending' ? (
          <div className="flex items-center gap-2 text-sm text-green-600">
            <Music className="w-4 h-4" />
            <span>音频提取完成</span>
          </div>
        ) : null,
      },
      {
        id: 'transcribe',
        name: '音频转写',
        description: '使用 AI 将音频转换为文字',
        status: (isTranscribeCompleted
          ? 'completed'
          : task.status === 'transcribing'
            ? 'processing'
            : task.status === 'processing'
              ? 'waiting_confirm'
              : 'pending') as StepStatus,
        canConfirm: task.status === 'processing',
        onConfirm: () => handleStepConfirm('transcribe'),
        result: isTranscribeCompleted ? (
          <div className="text-sm text-green-600">
            <FileText className="w-4 h-4 inline mr-2" />
            转写完成，共 {transcript.segments.length} 条片段
          </div>
        ) : null,
      },
      {
        id: 'summarize',
        name: '生成笔记',
        description: '使用 GPT 生成结构化笔记',
        status: (['summarizing', 'completed'].includes(task.status)
          ? task.status === 'summarizing'
            ? 'processing'
            : 'completed'
          : isTranscribeCompleted || task.status === 'transcribing'
            ? 'waiting_confirm'
            : 'pending') as StepStatus,
        canConfirm: isTranscribeCompleted, // 只有转录完成后才能生成笔记
        onConfirm: () => handleStepConfirm('summarize'),
      },
    ]

    setSteps(initialSteps)
  }, [task, transcript])

  // 使用 ref 来避免依赖问题
  const tasksRef = useRef(tasks)
  const updateTaskRef = useRef(updateTask)

  useEffect(() => {
    tasksRef.current = tasks
    updateTaskRef.current = updateTask
  }, [tasks, updateTask])

  const taskDetailLoadedRef = useRef<string | null>(null)

  // 初始加载任务详情
  useEffect(() => {
    if (!taskId) return

    // 防止重复加载同一个任务
    if (taskDetailLoadedRef.current === taskId) {
      return
    }

    const loadTaskDetail = async () => {
      taskDetailLoadedRef.current = taskId
      try {
        const response = await getTaskStatus(taskId)
        if (response.data.code === 200) {
          const taskData = response.data.data
          const currentTask = tasksRef.current.find((t) => t.id === taskId)
          updateTaskRef.current(taskId, {
            status: taskData.status,
            markdown: taskData.markdown || currentTask?.markdown || '',
          })

          // 更新转写结果
          if (taskData.transcript) {
            setTranscript(taskData.transcript)
          }

          // 更新步骤状态
          updateStepsStatus(taskData.status, taskData)
        }
      } catch (error) {
        console.error('加载任务详情失败:', error)
        // 加载失败时重置标记，允许重试
        if (taskDetailLoadedRef.current === taskId) {
          taskDetailLoadedRef.current = null
        }
      }
    }

    loadTaskDetail()
  }, [taskId])

  // 轮询任务状态
  useEffect(() => {
    if (!taskId) return

    const task = tasks.find((t) => t.id === taskId)
    // 如果任务已完成且不需要自动处理，直接返回，不启动轮询
    if (!task || (task.status === 'completed' && !autoProcess) || task.status === 'failed') {
      return
    }

    const interval = setInterval(async () => {
      try {
        const response = await getTaskStatus(taskId)
        if (response.data.code === 200) {
          const taskData = response.data.data
          const currentTask = tasksRef.current.find((t) => t.id === taskId)

          updateTaskRef.current(taskId, {
            status: taskData.status,
            markdown: taskData.markdown || currentTask?.markdown || '',
          })

          // 更新转写结果
          if (taskData.transcript) {
            setTranscript(taskData.transcript)
          }

          // 更新步骤状态
          updateStepsStatus(taskData.status, taskData)

          // 如果任务已完成或失败，停止轮询
          if (taskData.status === 'completed' || taskData.status === 'failed') {
            clearInterval(interval)
            setAutoProcess(false)
          }
        }
      } catch (error) {
        console.error('轮询失败:', error)
      }
    }, 2000)

    return () => clearInterval(interval)
  }, [taskId, autoProcess, task?.status])

  const updateStepsStatus = (status: string, taskData: any) => {
    setSteps((prev) =>
      prev.map((step) => {
        // 检查转录步骤：如果有 transcript 数据，即使状态是 transcribing，也标记为完成
        if (step.id === 'transcribe') {
          if (taskData.transcript && taskData.transcript.segments) {
            // 转录已完成
            return {
              ...step,
              status: 'completed' as StepStatus,
              result: (
                <div className="text-sm text-green-600">
                  <FileText className="w-4 h-4 inline mr-2" />
                  转写完成，共 {taskData.transcript.segments.length} 条片段
                </div>
              ),
            }
          } else if (status === 'transcribing') {
            // 正在转录中
            return { ...step, status: 'processing' as StepStatus }
          }
        }

        // 提取音频步骤
        if (status === 'processing' && step.id === 'extract') {
          return { ...step, status: 'processing' as StepStatus }
        }

        // 如果状态从 processing 变为其他状态，且提取已完成
        if (status !== 'pending' && step.id === 'extract' && step.status === 'processing') {
          return {
            ...step,
            status: 'completed' as StepStatus,
            result: (
              <div className="flex items-center gap-2 text-sm text-green-600">
                <Music className="w-4 h-4" />
                <span>音频提取完成</span>
              </div>
            ),
          }
        }

        // 生成笔记步骤
        if (status === 'summarizing' && step.id === 'summarize') {
          return { ...step, status: 'processing' as StepStatus }
        }

        // 所有步骤完成
        if (status === 'completed') {
          if (step.status === 'processing') {
            let result = null
            if (step.id === 'extract') {
              result = (
                <div className="flex items-center gap-2 text-sm text-green-600">
                  <Music className="w-4 h-4" />
                  <span>音频提取完成</span>
                </div>
              )
            } else if (step.id === 'transcribe' && taskData.transcript) {
              result = (
                <div className="text-sm text-green-600">
                  <FileText className="w-4 h-4 inline mr-2" />
                  转写完成，共 {taskData.transcript.segments?.length || 0} 条片段
                </div>
              )
            } else if (step.id === 'summarize' && taskData.markdown) {
              result = (
                <div className="text-sm text-green-600">
                  <BookOpen className="w-4 h-4 inline mr-2" />
                  笔记生成完成
                </div>
              )
            }
            return { ...step, status: 'completed' as StepStatus, result }
          }
        }
        return step
      })
    )
  }

  const handleStepConfirm = async (stepId: string) => {
    try {
      // 更新步骤状态为处理中
      setSteps((prev) =>
        prev.map((step) =>
          step.id === stepId ? { ...step, status: 'processing' as StepStatus } : step
        )
      )

      // 调用后端确认步骤（目前后端自动处理，这里主要是触发状态更新）
      await confirmStep(taskId, stepId)
      setAutoProcess(true)
    } catch (error) {
      console.error('确认步骤失败:', error)
      // 恢复状态
      setSteps((prev) =>
        prev.map((step) =>
          step.id === stepId ? { ...step, status: 'waiting_confirm' as StepStatus } : step
        )
      )
    }
  }

  if (!task) return null

  const currentStepIndex = steps.findIndex((s) => s.status === 'processing' || s.status === 'waiting_confirm')

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-7xl w-full max-h-[95vh] flex flex-col">
        <div className="p-6 border-b flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold">{task.filename}</h2>
            <p className="text-sm text-gray-500 mt-1">任务 ID: {task.id}</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-hidden flex">
          {/* 左侧：步骤和结果 */}
          <div className="w-1/2 border-r overflow-y-auto p-6">
            <h3 className="text-lg font-semibold mb-4">处理步骤</h3>
            <StepProgress steps={steps} currentStep={currentStepIndex} />
          </div>

          {/* 右侧：内容预览 */}
          <div className="w-1/2 overflow-y-auto p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">内容预览</h3>
              {task.status === 'completed' && task.markdown && (
                <div className="flex items-center gap-2">
                  <select
                    value={regenerateStyle}
                    onChange={(e) => setRegenerateStyle(e.target.value)}
                    className="text-sm border-gray-300 rounded-md shadow-sm focus:border-blue-300 focus:ring focus:ring-blue-200 focus:ring-opacity-50"
                  >
                    <option value="">保持当前风格</option>
                    <option value="simple">简洁模式</option>
                    <option value="detailed">详细模式</option>
                    <option value="academic">学术模式</option>
                    <option value="creative">创意模式</option>
                  </select>
                  <button
                    onClick={async () => {
                      try {
                        await regenerateNote(taskId, regenerateStyle || undefined)
                        toast.success('正在重新生成笔记...')
                        setAutoProcess(true)
                      } catch (error: any) {
                        toast.error(error.response?.data?.msg || '重新生成失败')
                      }
                    }}
                    className="px-3 py-1.5 text-sm bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors"
                  >
                    重新生成笔记
                  </button>
                </div>
              )}
            </div>

            <div className="h-full flex flex-col">
              {(() => {
                // 优先显示笔记（如果存在且已完成）
                if (task.markdown && (task.status === 'completed' || task.markdown.length > 0)) {
                  return <EnhancedMarkdownViewer markdown={task.markdown} filename={task.filename} taskId={taskId} />
                }

                // 其次显示转写结果（如果存在）
                if (transcript && transcript.segments && transcript.segments.length > 0) {
                  return <TranscriptViewer transcript={transcript} />
                }

                // 处理中显示加载
                if (task.status === 'processing' || task.status === 'transcribing' || task.status === 'summarizing') {
                  return (
                    <div className="flex h-full items-center justify-center text-gray-400">
                      <div className="text-center">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-2"></div>
                        <p>正在处理中...</p>
                      </div>
                    </div>
                  )
                }

                // 等待状态
                return (
                  <div className="flex h-full items-center justify-center text-gray-400">
                    <p>等待开始处理</p>
                  </div>
                )
              })()}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

