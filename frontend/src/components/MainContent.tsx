import { useTaskStore } from '../store/taskStore'
import UploadForm from './UploadForm'
import TaskList from './TaskList'
import TaskSteps from './TaskSteps'
import ModelConfig from './ModelConfig'
import UploadPage from './UploadPage'
import VideoDownloader from './VideoDownloader'

interface MainContentProps {
  activeMenu: 'home' | 'upload' | 'model' | 'settings'
}

export default function MainContent({ activeMenu }: MainContentProps) {
  const { currentTaskId } = useTaskStore()

  if (activeMenu === 'upload') {
    return <UploadPage />
  }

  if (activeMenu === 'model') {
    return <ModelConfig />
  }

  if (activeMenu === 'download') {
    return <VideoDownloader />
  }

  if (activeMenu === 'settings') {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <Settings className="w-16 h-16 text-gray-400 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-700 mb-2">设置</h2>
          <p className="text-sm text-gray-500">设置功能开发中...</p>
        </div>
      </div>
    )
  }

  // 首页：任务列表 + 步骤
  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* 主内容区：任务列表 + 步骤 */}
      <div className="flex-1 flex overflow-hidden">
        {/* 左侧：任务列表 */}
        <aside className="w-80 bg-white border-r border-gray-200 flex flex-col overflow-hidden shrink-0">
          <div className="p-4 border-b border-gray-200">
            <h2 className="text-base font-semibold text-gray-900">任务列表</h2>
          </div>
          <div className="flex-1 overflow-y-auto">
            <TaskList />
          </div>
        </aside>

        {/* 右侧：步骤区域 */}
        <main className="flex-1 overflow-hidden bg-gray-50">
          {currentTaskId ? (
            <TaskSteps taskId={currentTaskId} />
          ) : (
            <div className="h-full flex items-center justify-center p-8">
              <div className="text-center max-w-md">
                <div className="text-gray-400 text-6xl mb-4">📝</div>
                <h2 className="text-xl font-semibold text-gray-700 mb-2">选择一个任务查看详情</h2>
                <p className="text-sm text-gray-500">
                  在左侧任务列表中点击任务来查看处理步骤
                </p>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}

// 临时Settings图标组件
function Settings({ className }: { className: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  )
}
