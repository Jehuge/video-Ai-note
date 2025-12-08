import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useTaskStore } from '../store/taskStore'
import 'github-markdown-css/github-markdown.css'

interface MarkdownViewerProps {
  markdown?: string
}

export default function MarkdownViewer({ markdown: propMarkdown }: MarkdownViewerProps = {}) {
  const { tasks, currentTaskId } = useTaskStore()
  
  const currentTask = tasks.find(t => t.id === currentTaskId)
  const markdown = propMarkdown || currentTask?.markdown || ''

  if (!currentTaskId) {
    return (
      <div className="bg-white rounded-lg shadow-md p-8">
        <div className="text-center text-gray-400">
          <p>请选择一个任务查看笔记</p>
        </div>
      </div>
    )
  }

  if (currentTask?.status === 'failed') {
    return (
      <div className="bg-white rounded-lg shadow-md p-8">
        <div className="text-center text-red-500">
          <p>任务处理失败，请重试</p>
        </div>
      </div>
    )
  }

  if (!markdown && currentTask?.status !== 'completed') {
    return (
      <div className="bg-white rounded-lg shadow-md p-8">
        <div className="text-center text-gray-400">
          <p>正在生成笔记，请稍候...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="mb-4">
        <h2 className="text-xl font-semibold">笔记预览</h2>
        {currentTask && (
          <p className="text-sm text-gray-500 mt-1">{currentTask.filename}</p>
        )}
      </div>
      
      <div className="markdown-body prose max-w-none">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {markdown}
        </ReactMarkdown>
      </div>
    </div>
  )
}

