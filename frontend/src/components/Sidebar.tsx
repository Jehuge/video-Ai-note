import { useState } from 'react'
import { Home, Settings, Bot, Upload, Download, ChevronLeft, ChevronRight } from 'lucide-react'

interface SidebarProps {
  activeMenu: 'home' | 'upload' | 'model' | 'settings' | 'download'
  onMenuChange: (menu: 'home' | 'upload' | 'model' | 'settings' | 'download') => void
}

export default function Sidebar({ activeMenu, onMenuChange }: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false)

  const menuItems = [
    {
      id: 'home' as const,
      name: '首页',
      icon: <Home className="w-5 h-5" />,
    },
    {
      id: 'upload' as const,
      name: '上传',
      icon: <Upload className="w-5 h-5" />,
    },
    {
      id: 'model' as const,
      name: '模型配置',
      icon: <Bot className="w-5 h-5" />,
    },
    {
      id: 'download' as const,
      name: '下载',
      icon: <Download className="w-5 h-5" />,
    },
    {
      id: 'settings' as const,
      name: '设置',
      icon: <Settings className="w-5 h-5" />,
    },
  ]

  return (
    <aside className={`${collapsed ? 'w-16' : 'w-34'} bg-white border-r border-gray-200 flex flex-col overflow-hidden shrink-0 transition-all duration-300`}>
      {/* 收缩按钮 */}
      <div className="p-2 border-b border-gray-200 flex justify-end">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-1.5 rounded hover:bg-gray-100 transition-colors"
          title={collapsed ? '展开菜单' : '收缩菜单'}
        >
          {collapsed ? (
            <ChevronRight className="w-4 h-4 text-gray-600" />
          ) : (
            <ChevronLeft className="w-4 h-4 text-gray-600" />
          )}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        <div className="space-y-1">
          {menuItems.map((item) => (
            <button
              key={item.id}
              onClick={() => onMenuChange(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-3 rounded-lg transition-colors ${
                activeMenu === item.id
                  ? 'bg-blue-50 text-blue-700 font-medium'
                  : 'text-gray-700 hover:bg-gray-50'
              }`}
              title={collapsed ? item.name : undefined}
            >
              {item.icon}
              {!collapsed && <span className="text-sm">{item.name}</span>}
            </button>
          ))}
        </div>
      </div>
    </aside>
  )
}
