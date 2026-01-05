import { useEffect, useState, useRef } from 'react'
import { FileVideo, Music, FileText, BookOpen, RotateCcw, Eye } from 'lucide-react'
import { useTaskStore } from '../store/taskStore'
import { getTaskStatus, confirmStep, regenerateNote } from '../services/api'
import StepProgress, { StepStatus } from './StepProgress'
import ContentPreviewModal from './ContentPreviewModal'
import toast from 'react-hot-toast'
import UploadZone from './UploadZone'

interface TaskStepsProps {
  taskId?: string | null
}

export default function TaskSteps({ taskId }: TaskStepsProps) {
  const { tasks, updateTask } = useTaskStore()
  const task = taskId ? tasks.find((t) => t.id === taskId) : null
  const [steps, setSteps] = useState<any[]>([])
  const [autoProcess, setAutoProcess] = useState(false)
  const [transcript, setTranscript] = useState<any>(null)
  const [previewContent, setPreviewContent] = useState<{
    type: 'transcript' | 'markdown' | 'video'
    content: any
    title: string
  } | null>(null)
  const [noteStyle, setNoteStyle] = useState('simple')

  const noteStyles = [
    { value: 'simple', label: '简洁模式 (默认)' },
    { value: 'detailed', label: '详细模式' },
    { value: 'academic', label: '学术模式' },
    { value: 'creative', label: '创意模式' },
  ]

  // 初始化步骤
  useEffect(() => {
    // 如果没有任务，显示初始状态（等待上传）
    if (!task) {
      const initialSteps = [
        {
          id: 'upload',
          name: '文件上传',
          description: '将文件上传到服务器',
          status: 'waiting_confirm' as StepStatus,
          customControl: (
            <div className="mt-4">
              <UploadZone onUploadSuccess={(newTaskId) => {
                useTaskStore.getState().setCurrentTask(newTaskId)
              }} />
            </div>
          )
        },
        {
          id: 'extract',
          name: '提取音频',
          description: '从视频文件中提取音频（如果是视频）',
          status: 'pending' as StepStatus,
        },
        {
          id: 'transcribe',
          name: '音频转写',
          description: '使用 AI 将音频转换为文字',
          status: 'pending' as StepStatus,
        },
        {
          id: 'summarize',
          name: '生成笔记',
          description: '使用 GPT 生成结构化笔记',
          status: 'pending' as StepStatus,
        }
      ]
      setSteps(initialSteps)
      return
    }

    const isTranscribeCompleted = transcript && transcript.segments && transcript.segments.length > 0

    const initialSteps = [
      {
        id: 'upload',
        name: '文件上传',
        description: '将文件上传到服务器',
        status: 'completed' as StepStatus,
        result: task.filename ? (
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2 flex-1 min-w-0">
              <FileVideo className="w-4 h-4 text-blue-500 shrink-0" />
              <span className="truncate" title={task.filename}>{task.filename}</span>
            </div>
            <button
              onClick={() => {
                const fileExt = task.filename.split('.').pop()?.toLowerCase()
                const videoUrl = `/api/uploads/${taskId}.${fileExt}`
                setPreviewContent({
                  type: 'video',
                  content: videoUrl,
                  title: '视频预览',
                })
              }}
              className="flex items-center gap-1 px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200 transition-colors shrink-0"
            >
              <Eye className="w-3 h-3" />
              查看
            </button>
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
          <div className="flex items-center justify-between text-sm text-green-600">
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4" />
              <span>转写完成，共 {transcript.segments.length} 条片段</span>
            </div>
            <button
              onClick={() => {
                if (transcript) {
                  setPreviewContent({
                    type: 'transcript',
                    content: transcript,
                    title: '音频转写内容',
                  })
                }
              }}
              className="flex items-center gap-1 px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200 transition-colors"
            >
              <Eye className="w-3 h-3" />
              查看
            </button>
          </div>
        ) : null,
        onClick: isTranscribeCompleted ? () => {
          if (transcript) {
            setPreviewContent({
              type: 'transcript',
              content: transcript,
              title: '音频转写内容',
            })
          }
        } : undefined,
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
        canConfirm: isTranscribeCompleted,
        onConfirm: async () => {
          try {
            setSteps((prev) =>
              prev.map((step) =>
                step.id === 'summarize' ? { ...step, status: 'processing' as StepStatus } : step
              )
            )

            await regenerateNote(taskId!, noteStyle)
            setAutoProcess(true)
          } catch (error: any) {
            console.error('开始生成笔记失败:', error)
            toast.error(error.response?.data?.msg || '开始生成失败')
            setSteps((prev) =>
              prev.map((step) =>
                step.id === 'summarize' ? { ...step, status: 'waiting_confirm' as StepStatus } : step
              )
            )
          }
        },
        customControl: (
          <div className="mt-3 flex items-center gap-3">
            <select
              value={noteStyle}
              onChange={(e) => setNoteStyle(e.target.value)}
              className="block w-40 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2 border"
              onClick={(e) => e.stopPropagation()}
            >
              {noteStyles.map((style) => (
                <option key={style.value} value={style.value}>
                  {style.label}
                </option>
              ))}
            </select>
          </div>
        ),
        result: task.markdown && task.status === 'completed' ? (
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between text-sm text-green-600">
              <div className="flex items-center gap-2">
                <BookOpen className="w-4 h-4" />
                <span>笔记生成完成</span>
              </div>
              <button
                onClick={() => {
                  if (task.markdown) {
                    setPreviewContent({
                      type: 'markdown',
                      content: task.markdown,
                      title: '笔记预览',
                    })
                  }
                }}
                className="flex items-center gap-1 px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200 transition-colors"
                title="查看笔记"
              >
                <Eye className="w-3 h-3" />
                查看
              </button>
            </div>
          </div>
        ) : null,
        onClick: task.markdown && task.status === 'completed' ? () => {
          if (task.markdown) {
            setPreviewContent({
              type: 'markdown',
              content: task.markdown,
              title: '笔记预览',
            })
          }
        } : undefined,
        completedControl: (
          <div className="mt-3 pt-3 border-t border-gray-100 flex items-center gap-3" onClick={(e) => e.stopPropagation()}>
            <select
              value={noteStyle}
              onChange={(e) => setNoteStyle(e.target.value)}
              className="block w-40 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-xs p-1.5 border"
            >
              {noteStyles.map((style) => (
                <option key={style.value} value={style.value}>
                  {style.label}
                </option>
              ))}
            </select>
            <button
              onClick={async (e) => {
                e.stopPropagation()
                try {
                  setSteps((prev) =>
                    prev.map((step) =>
                      step.id === 'summarize' ? { ...step, status: 'processing' as StepStatus } : step
                    )
                  )

                  await regenerateNote(taskId!, noteStyle)
                  toast.success('正在重新生成笔记...')
                  setAutoProcess(true)
                } catch (error: any) {
                  toast.error(error.response?.data?.msg || '重新生成失败')
                  if (task.status === 'completed') {
                    setSteps((prev) =>
                      prev.map((step) =>
                        step.id === 'summarize' ? { ...step, status: 'completed' as StepStatus } : step
                      )
                    )
                  }
                }
              }}
              className="flex items-center gap-1 px-3 py-1.5 text-xs bg-blue-50 text-blue-600 border border-blue-200 rounded hover:bg-blue-100 transition-colors"
            >
              <RotateCcw className="w-3 h-3" />
              重新生成
            </button>
          </div>
        )
      },
    ]

    setSteps(initialSteps)
  }, [task, transcript, noteStyle])

  const tasksRef = useRef(tasks)
  const updateTaskRef = useRef(updateTask)

  useEffect(() => {
    tasksRef.current = tasks
    updateTaskRef.current = updateTask
  }, [tasks, updateTask])

  const taskDetailLoadedRef = useRef<string | null>(null)

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

          if (taskData.transcript) {
            setTranscript(taskData.transcript)
          }

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

  useEffect(() => {
    if (!taskId) return

    const task = tasks.find((t) => t.id === taskId)
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

          if (taskData.transcript) {
            setTranscript(taskData.transcript)
          }

          updateStepsStatus(taskData.status, taskData)

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
        if (step.id === 'transcribe') {
          if (taskData.transcript && taskData.transcript.segments) {
            return {
              ...step,
              status: 'completed' as StepStatus,
              result: (
                <div className="flex items-center justify-between text-sm text-green-600">
                  <div className="flex items-center gap-2">
                    <FileText className="w-4 h-4" />
                    <span>转写完成，共 {taskData.transcript.segments.length} 条片段</span>
                  </div>
                  <button
                    onClick={() => {
                      if (taskData.transcript) {
                        setPreviewContent({
                          type: 'transcript',
                          content: taskData.transcript,
                          title: '音频转写内容',
                        })
                      }
                    }}
                    className="flex items-center gap-1 px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200 transition-colors"
                  >
                    <Eye className="w-3 h-3" />
                    查看
                  </button>
                </div>
              ),
              onClick: () => {
                if (taskData.transcript) {
                  setPreviewContent({
                    type: 'transcript',
                    content: taskData.transcript,
                    title: '音频转写内容',
                  })
                }
              },
            }
          } else if (status === 'transcribing') {
            return { ...step, status: 'processing' as StepStatus }
          }
        }

        if (status === 'processing' && step.id === 'extract') {
          return { ...step, status: 'processing' as StepStatus }
        }

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

        if (status === 'summarizing' && step.id === 'summarize') {
          return { ...step, status: 'processing' as StepStatus }
        }

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
                <div className="flex items-center justify-between text-sm text-green-600">
                  <div className="flex items-center gap-2">
                    <FileText className="w-4 h-4" />
                    <span>转写完成，共 {taskData.transcript.segments?.length || 0} 条片段</span>
                  </div>
                  <button
                    onClick={() => {
                      if (taskData.transcript) {
                        setPreviewContent({
                          type: 'transcript',
                          content: taskData.transcript,
                          title: '音频转写内容',
                        })
                      }
                    }}
                    className="flex items-center gap-1 px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200 transition-colors"
                  >
                    <Eye className="w-3 h-3" />
                    查看
                  </button>
                </div>
              )
            } else if (step.id === 'summarize' && taskData.markdown) {
              result = (
                <div className="flex items-center justify-between text-sm text-green-600">
                  <div className="flex items-center gap-2">
                    <BookOpen className="w-4 h-4" />
                    <span>笔记生成完成</span>
                  </div>
                  <button
                    onClick={() => {
                      if (taskData.markdown) {
                        setPreviewContent({
                          type: 'markdown',
                          content: taskData.markdown,
                          title: '笔记预览',
                        })
                      }
                    }}
                    className="flex items-center gap-1 px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200 transition-colors"
                  >
                    <Eye className="w-3 h-3" />
                    查看
                  </button>
                </div>
              )
            }
            return {
              ...step,
              status: 'completed' as StepStatus,
              result,
              onClick: step.id === 'transcribe' && taskData.transcript ? () => {
                setPreviewContent({
                  type: 'transcript',
                  content: taskData.transcript,
                  title: '音频转写内容',
                })
              } : step.id === 'summarize' && taskData.markdown ? () => {
                setPreviewContent({
                  type: 'markdown',
                  content: taskData.markdown,
                  title: '笔记预览',
                })
              } : undefined,
            }
          }
        }
        return step
      })
    )
  }

  const handleStepConfirm = async (stepId: string) => {
    try {
      setSteps((prev) =>
        prev.map((step) =>
          step.id === stepId ? { ...step, status: 'processing' as StepStatus } : step
        )
      )

      await confirmStep(taskId!, stepId)
      setAutoProcess(true)
    } catch (error) {
      console.error('确认步骤失败:', error)
      setSteps((prev) =>
        prev.map((step) =>
          step.id === stepId ? { ...step, status: 'waiting_confirm' as StepStatus } : step
        )
      )
    }
  }

  if (!task && taskId) {
    return (
      <div className="h-full flex items-center justify-center text-gray-400">
        <p>任务不存在</p>
      </div>
    )
  }

  const currentStepIndex = steps.findIndex((s) => s.status === 'processing' || s.status === 'waiting_confirm')

  return (
    <>
      <div className="h-full flex flex-col overflow-hidden">
        {/* 固定头部 */}
        <div className="bg-white border-b border-gray-200 px-6 py-4 shrink-0">
          <div className="flex items-center justify-between">
            <div className="flex-1 min-w-0">
              <h2 className="text-xl font-semibold text-gray-900 truncate" title={task?.filename || '新建任务'}>{task?.filename || '新建任务'}</h2>
              {task && <p className="text-sm text-gray-500 mt-1">任务 ID: {task.id.slice(0, 8)}...</p>}
            </div>
            {task?.status === 'completed' && task.markdown && (
              // 顶部重新生成按钮已移动到生成笔记步骤中
              null
            )}
          </div>
        </div>

        {/* 步骤区域 */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-4xl mx-auto">
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-6">处理步骤</h3>
              <StepProgress steps={steps} currentStep={currentStepIndex} />
            </div>
          </div>
        </div>
      </div>

      {/* 内容预览弹窗 */}
      {previewContent && (
        <ContentPreviewModal
          type={previewContent.type}
          content={previewContent.content}
          title={previewContent.title}
          filename={task?.filename || ''}
          taskId={taskId || ''}
          onClose={() => setPreviewContent(null)}
        />
      )}
    </>
  )
}
