import { useTaskStore } from '../store/taskStore'
import TaskList from './TaskList'
import TaskSteps from './TaskSteps'
import ModelConfig from './ModelConfig'
import UploadZone from './UploadZone'
import BiliDownload from '../pages/BiliDownload'
import TranscriberSettings from './TranscriberSettings'

interface MainContentProps {
  activeMenu: 'home' | 'upload' | 'model' | 'settings' | 'bili'
}

export default function MainContent({ activeMenu }: MainContentProps) {
  const { currentTaskId } = useTaskStore()


  if (activeMenu === 'model') {
    return <ModelConfig />
  }

  if (activeMenu === 'bili') {
    return <BiliDownload />
  }


  if (activeMenu === 'settings') {
    return <TranscriberSettings />
  }

  // 首页：任务列表 + 步骤
  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* 主内容区：任务列表 + 步骤 */}
      <div className="flex-1 flex overflow-hidden">
        {/* 左侧：任务列表 */}
        <aside className="w-[30%] bg-white border-r border-gray-200 flex flex-col overflow-hidden shrink-0">
          <div className="p-4 border-b border-gray-200">
            <h2 className="text-base font-semibold text-gray-900">任务列表</h2>
          </div>
          <div className="flex-1 overflow-y-auto">
            <TaskList />
          </div>
        </aside>

        {/* 右侧：上传 + 步骤区域 */}
        <main className="flex-1 flex flex-col overflow-hidden bg-gray-50">
          {/* 顶部上传区域 */}
          <div className="p-6 pb-0 shrink-0">
            <UploadZone
              onUploadSuccess={(taskId) => {
                // 自动选中新任务
                useTaskStore.getState().setCurrentTask(taskId)
              }}
            />
          </div>

          <div className="flex-1 overflow-y-auto p-6">
            {currentTaskId ? (
              <TaskSteps taskId={currentTaskId} />
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-gray-400">
                <p>请选择一个任务查看详情，或上传新文件</p>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  )
}
