import { useState } from 'react'
import Sidebar from './components/Sidebar'
import MainContent from './components/MainContent'
import CurrentModelDisplay from './components/CurrentModelDisplay'
import { Toaster } from 'react-hot-toast'

type MenuItem = 'home' | 'upload' | 'model' | 'settings'

function App() {
  const [activeMenu, setActiveMenu] = useState<MenuItem>('home')

  return (
    <div className="h-screen flex flex-col bg-gray-50 overflow-hidden">
      {/* 顶部导航栏 */}
      <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6 shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-10 h-10 bg-blue-600 rounded-lg">
            <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <div>
            <h1 className="text-lg font-bold text-gray-900">Video AI Note</h1>
            <p className="text-xs text-gray-500">智能视频笔记生成工具</p>
          </div>
        </div>
        {/* 右侧：当前模型显示 */}
        <div className="flex items-center">
          <CurrentModelDisplay />
        </div>
      </header>

      {/* 主内容区 */}
      <div className="flex-1 flex overflow-hidden">
        {/* 左侧：菜单栏 */}
        <Sidebar activeMenu={activeMenu} onMenuChange={setActiveMenu} />

        {/* 右侧：功能配置和操作区 */}
        <main className="flex-1 overflow-hidden bg-gray-50">
          <MainContent activeMenu={activeMenu} />
        </main>
      </div>
      <Toaster position="top-right" />
    </div>
  )
}

export default App
