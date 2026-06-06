import { useState, useEffect } from 'react'
import { Brain } from 'lucide-react'
import ProviderIcon from './ProviderIcon'
import { getSelectedModelDisplay } from '../utils/modelConfig'

const PROVIDER_LABELS: Record<string, string> = {
  openai: 'OpenAI',
  deepseek: 'DeepSeek',
  qwen: 'Qwen',
  claude: 'Claude',
  gemini: 'Gemini',
  groq: 'Groq',
  ollama: 'Ollama',
}

const PROVIDER_COLORS: Record<string, string> = {
  openai: 'bg-green-100 text-green-700 border-green-200',
  deepseek: 'bg-blue-100 text-blue-700 border-blue-200',
  qwen: 'bg-purple-100 text-purple-700 border-purple-200',
  claude: 'bg-orange-100 text-orange-700 border-orange-200',
  gemini: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  groq: 'bg-indigo-100 text-indigo-700 border-indigo-200',
  ollama: 'bg-teal-100 text-teal-700 border-teal-200',
}

export default function CurrentModelDisplay() {
  const [currentModel, setCurrentModel] = useState<{
    name: string
    provider: string
    providerName: string
  } | null>(null)

  useEffect(() => {
    const loadCurrentModel = () => {
      try {
        const selected = getSelectedModelDisplay()
        if (!selected) {
          setCurrentModel(null)
          return
        }

        setCurrentModel({
          name: selected.modelName,
          provider: selected.providerType,
          providerName: selected.providerName || PROVIDER_LABELS[selected.providerType] || selected.providerType,
        })
      } catch (error) {
        console.error('加载当前模型失败:', error)
        setCurrentModel(null)
      }
    }

    loadCurrentModel()

    // 监听 storage 变化（同窗口内的变化不会触发 storage 事件，所以需要自定义事件）
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'selectedModel') {
        loadCurrentModel()
      }
    }
    window.addEventListener('storage', handleStorageChange)

    // 监听自定义事件（用于同窗口内的变化）
    const handleCustomStorageChange = () => {
      loadCurrentModel()
    }
    window.addEventListener('modelChanged', handleCustomStorageChange)

    // 定期检查配置变化（作为备用方案）
    const interval = setInterval(loadCurrentModel, 1000)

    return () => {
      window.removeEventListener('storage', handleStorageChange)
      window.removeEventListener('modelChanged', handleCustomStorageChange)
      clearInterval(interval)
    }
  }, [])

  if (!currentModel) {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-400">
        <Brain className="w-4 h-4" />
        <span>当前模型: 未选择</span>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-2 text-sm">
      <ProviderIcon provider={currentModel.provider} className="w-4 h-4" />
      <span className="text-gray-600">当前模型:</span>
      <span className="font-medium text-gray-900">{currentModel.name}</span>
      <span className="text-gray-500">{currentModel.providerName}</span>
    </div>
  )
}

