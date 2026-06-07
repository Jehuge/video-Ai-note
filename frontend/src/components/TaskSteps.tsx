import { useEffect, useState, useRef } from 'react'
import { FileVideo, Music, FileText, BookOpen, RotateCcw, Eye, Play } from 'lucide-react'
import { useTaskStore } from '../store/taskStore'
import { getTaskStatus, confirmStep, regenerateNote } from '../services/api'
import StepProgress, { StepStatus } from './StepProgress'
import ContentPreviewModal from './ContentPreviewModal'
import MarkdownContent from './MarkdownContent'
import toast from 'react-hot-toast'

interface TaskStepsProps {
  taskId: string
}

export default function TaskSteps({ taskId }: TaskStepsProps) {
  const { tasks, updateTask } = useTaskStore()
  const task = tasks.find((t) => t.id === taskId)
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
    if (!task) return

    const transcriptSegmentCount = transcript?.segments?.length || 0
    const isTranscribeCompleted = task.status === 'transcribed' || transcriptSegmentCount > 0

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
          : ['processing', 'transcribing', 'transcribed', 'summarizing', 'completed'].includes(task.status)
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
        description: '使用本地 faster-whisper 将音频转换为文字',
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
              <span>转写完成，共 {transcriptSegmentCount} 条片段</span>
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
          : isTranscribeCompleted || task.status === 'transcribing' || task.status === 'transcribed'
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

            await regenerateNote(taskId, noteStyle)
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
          <div className="mt-4 flex flex-col sm:flex-row gap-3">
            <div className="relative">
              <select
                value={noteStyle}
                onChange={(e) => setNoteStyle(e.target.value)}
                className="appearance-none block w-full sm:w-48 pl-4 pr-10 py-2.5 text-sm border border-slate-200 rounded-lg bg-slate-50 text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all cursor-pointer hover:bg-white hover:border-blue-300"
                onClick={(e) => e.stopPropagation()}
              >
                {noteStyles.map((style) => (
                  <option key={style.value} value={style.value}>
                    {style.label}
                  </option>
                ))}
              </select>
              <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-3 text-slate-500">
                <svg className="h-4 w-4 fill-current" viewBox="0 0 20 20">
                  <path d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" />
                </svg>
              </div>
            </div>

            <button
              onClick={(e) => {
                e.stopPropagation()
                // Start generation
                handleStepConfirm('summarize')
              }}
              className="flex-1 sm:flex-none px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-all shadow-sm shadow-blue-600/20 flex items-center justify-center gap-2"
            >
              <Play className="w-4 h-4 fill-current" />
              开始生成
            </button>
          </div>
        ),
        result: task.markdown && task.status === 'completed' ? (
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between text-sm text-emerald-600 p-3 bg-emerald-50 rounded-lg border border-emerald-100">
              <div className="flex items-center gap-2 font-medium">
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
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-white text-emerald-700 rounded-md border border-emerald-200 hover:bg-emerald-50 hover:border-emerald-300 transition-all shadow-sm"
                title="查看笔记"
              >
                <Eye className="w-3.5 h-3.5" />
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
          <div className="mt-4 pt-4 border-t border-slate-100 flex items-center gap-3" onClick={(e) => e.stopPropagation()}>
            <div className="relative">
              <select
                value={noteStyle}
                onChange={(e) => setNoteStyle(e.target.value)}
                className="appearance-none block w-full sm:w-40 pl-3 pr-8 py-2 text-xs border border-slate-200 rounded-lg bg-white text-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all cursor-pointer hover:border-blue-300 shadow-sm"
              >
                {noteStyles.map((style) => (
                  <option key={style.value} value={style.value}>
                    {style.label}
                  </option>
                ))}
              </select>
              <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-slate-400">
                <svg className="h-3 w-3 fill-current" viewBox="0 0 20 20">
                  <path d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" />
                </svg>
              </div>
            </div>

            <button
              onClick={async (e) => {
                e.stopPropagation()
                try {
                  setSteps((prev) =>
                    prev.map((step) =>
                      step.id === 'summarize' ? { ...step, status: 'processing' as StepStatus } : step
                    )
                  )

                  await regenerateNote(taskId, noteStyle)
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
              className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium bg-white text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50 hover:text-blue-600 hover:border-blue-200 hover:shadow-sm transition-all shadow-sm"
            >
              <RotateCcw className="w-3.5 h-3.5" />
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
            partialMarkdown: taskData.partial_markdown || currentTask?.partialMarkdown || '',
            progressMessage: taskData.progress_message || '',
            errorMessage: taskData.error_message || '',
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
    if (!task || (['completed', 'transcribed'].includes(task.status) && !autoProcess) || task.status === 'failed') {
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
            partialMarkdown: taskData.partial_markdown || currentTask?.partialMarkdown || '',
            progressMessage: taskData.progress_message || '',
            errorMessage: taskData.error_message || '',
          })

          if (taskData.transcript) {
            setTranscript(taskData.transcript)
          }

          updateStepsStatus(taskData.status, taskData)

          if (taskData.status === 'completed' || taskData.status === 'failed' || taskData.status === 'transcribed') {
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
        if (status === 'failed') {
          if (step.status === 'processing' || step.status === 'waiting_confirm') {
            return { ...step, status: 'failed' as StepStatus }
          }
          return step
        }

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
          } else if (status === 'transcribed') {
            return { ...step, status: 'completed' as StepStatus }
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

        if (status === 'transcribed' && step.id === 'summarize') {
          return { ...step, status: 'waiting_confirm' as StepStatus }
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

      await confirmStep(taskId, stepId, stepId === 'summarize' ? noteStyle : undefined)
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

  if (!task) {
    return (
      <div className="h-full flex items-center justify-center text-gray-400">
        <p>任务不存在</p>
      </div>
    )
  }

  const currentStepIndex = steps.findIndex((s) => s.status === 'processing' || s.status === 'waiting_confirm')

  return (
    <>
      <div className="h-full flex flex-col overflow-hidden bg-slate-50">
        {/* 统一滚动区域 */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-4xl mx-auto">
            {/* 任务头部信息 - 现在是流的一部分 */}
            <div className="mb-8 pl-1">
              <h2 className="text-2xl font-bold text-gray-900 break-words leading-tight mb-2" title={task.filename}>
                {task.filename}
              </h2>
              <p className="text-sm text-gray-500 font-medium opacity-80">任务 ID: {task.id.slice(0, 8)}...</p>
              {task.status === 'failed' && task.errorMessage && (
                <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {task.errorMessage}
                </div>
              )}
              {task.status === 'summarizing' && task.progressMessage && (
                <div className="mt-3 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-700">
                  {task.progressMessage}
                </div>
              )}
            </div>

            <h3 className="text-lg font-semibold text-gray-900 mb-6 px-1 flex items-center gap-2">
              <span className="w-1 h-6 bg-blue-600 rounded-full inline-block"></span>
              处理流程
            </h3>
            <StepProgress steps={steps} currentStep={currentStepIndex} />

            {task.status === 'summarizing' && (
              <div className="mt-6 rounded-2xl border border-blue-100 bg-white shadow-sm overflow-hidden">
                <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3">
                  <div>
                    <h4 className="text-sm font-semibold text-slate-900">实时生成内容</h4>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {task.progressMessage || '正在生成笔记'}
                    </p>
                  </div>
                  <div className="h-2 w-2 rounded-full bg-blue-500 animate-pulse" />
                </div>
                <div className="max-h-96 overflow-y-auto p-5">
                  {task.partialMarkdown ? (
                    <MarkdownContent markdown={task.partialMarkdown} />
                  ) : (
                    <div className="text-sm text-slate-400">正在等待模型返回第一段内容...</div>
                  )}
                </div>
              </div>
            )}

            {task.status === 'failed' && task.partialMarkdown && (
              <div className="mt-6 rounded-2xl border border-amber-100 bg-white shadow-sm overflow-hidden">
                <div className="border-b border-slate-100 px-5 py-3">
                  <h4 className="text-sm font-semibold text-slate-900">失败前已生成的内容</h4>
                  <p className="text-xs text-slate-500 mt-0.5">可以切换模型后重新生成，App 会复用已有转写。</p>
                </div>
                <div className="max-h-96 overflow-y-auto p-5">
                  <MarkdownContent markdown={task.partialMarkdown} />
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 内容预览弹窗 */}
      {previewContent && (
        <ContentPreviewModal
          type={previewContent.type}
          content={previewContent.content}
          title={previewContent.title}
          filename={task.filename}
          taskId={taskId}
          onClose={() => setPreviewContent(null)}
        />
      )}
    </>
  )
}
