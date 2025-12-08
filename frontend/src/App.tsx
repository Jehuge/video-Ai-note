import { useTaskStore } from './store/taskStore'
import UploadForm from './components/UploadForm'
import TaskList from './components/TaskList'
import { Toaster } from 'react-hot-toast'

function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold text-center mb-8">Video AI Note</h1>
        
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 左侧：上传和任务列表 */}
          <div className="lg:col-span-1 space-y-4">
            <UploadForm />
            <TaskList />
          </div>

          {/* 右侧：提示信息 */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-lg shadow-md p-8">
              <div className="text-center text-gray-400">
                <p className="text-lg mb-2">选择一个任务查看详情</p>
                <p className="text-sm">点击任务列表中的"查看详情"按钮</p>
              </div>
            </div>
          </div>
        </div>
      </div>
      <Toaster position="top-right" />
    </div>
  )
}

export default App

