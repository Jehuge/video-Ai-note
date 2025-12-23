import { useState, useEffect } from 'react'
import { Brain, ChevronDown, AlertCircle, RefreshCw, Loader2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { migrateLegacyConfigs, listModelsFromConfigs } from '../services/modelService'

interface Model {
  id: string
  name: string
  provider: string
  model: string
  hasApiKey: boolean
}

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
  openai: 'bg-green-100 text-green-700',
  deepseek: 'bg-blue-100 text-blue-700',
  qwen: 'bg-purple-100 text-purple-700',
  claude: 'bg-orange-100 text-orange-700',
  gemini: 'bg-yellow-100 text-yellow-700',
  groq: 'bg-indigo-100 text-indigo-700',
  ollama: 'bg-teal-100 text-teal-700',
}

export default function ModelSelector() {
  const [selectedModel, setSelectedModel] = useState<string>('')
  const [models, setModels] = useState<Model[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [loading, setLoading] = useState(false)

  // 从 localStorage 加载模型配置并获取模型列表
  useEffect(() => {
    const init = async () => {
      try {
        migrateLegacyConfigs()
        const all = await listModelsFromConfigs()
        setModels(all.map((m: any) => ({
          id: m.id,
          name: m.name,
          provider: m.provider,
          model: m.model,
          hasApiKey: !!m.hasApiKey,
        })))
        // 选择默认
        const savedSelected = localStorage.getItem('selectedModel')
        if (savedSelected && all.find((x: any) => x.id === savedSelected)) {
          setSelectedModel(savedSelected)
        } else if (all.length > 0) {
          setSelectedModel(all[0].id)
          localStorage.setItem('selectedModel', all[0].id)
        }
      } catch (e) {
        console.warn('加载模型列表失败:', e)
      }
    }
    init()
  }, [])

  const loadModelsFromConfig = async () => {
    setLoading(true)
    try {
      await migrateLegacyConfigs()
      const all = await listModelsFromConfigs()
      setModels(all.map((m: any) => ({
        id: m.id,
        name: m.name,
        provider: m.provider,
        model: m.model,
        hasApiKey: !!m.hasApiKey,
      })))

      const savedSelected = localStorage.getItem('selectedModel')
      if (savedSelected && all.find((x: any) => x.id === savedSelected)) {
        setSelectedModel(savedSelected)
      } else if (all.length > 0) {
        setSelectedModel(all[0].id)
        localStorage.setItem('selectedModel', all[0].id)
      }
    } catch (error) {
      console.error('加载模型配置失败:', error)
      setModels([])
    } finally {
      setLoading(false)
    }
  }

  // 监听 storage 变化（只在其他窗口/标签页变化时触发）
  useEffect(() => {
    const handleStorageChange = (e: StorageEvent) => {
      // 只监听 modelConfigs 的变化
      if (e.key === 'modelConfigs') {
        loadModelsFromConfig()
      }
    }
    window.addEventListener('storage', handleStorageChange)

    return () => {
      window.removeEventListener('storage', handleStorageChange)
    }
  }, [])

  const currentModel = models.find(m => m.id === selectedModel)

  if (loading) {
    return (
      <div>
        <h2 className="text-sm font-semibold text-gray-700 mb-3 px-1">模型选择</h2>
        <div className="flex items-center justify-center py-4 bg-white border border-gray-300 rounded-lg">
          <Loader2 className="w-4 h-4 animate-spin text-blue-600" />
          <span className="ml-2 text-sm text-gray-600">加载模型列表...</span>
        </div>
      </div>
    )
  }

  if (models.length === 0) {
    return (
      <div>
        <h2 className="text-sm font-semibold text-gray-700 mb-3 px-1">模型选择</h2>
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <div className="flex items-start gap-2">
            <AlertCircle className="w-4 h-4 text-yellow-600 mt-0.5 shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-medium text-yellow-800 mb-1">未配置模型</p>
              <p className="text-xs text-yellow-700">
                请前往"模型配置"页面配置 API Key 和选择模型
              </p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-3 px-1">
        <h2 className="text-sm font-semibold text-gray-700">模型选择</h2>
        <button
          onClick={loadModelsFromConfig}
          disabled={loading}
          className="p-1.5 hover:bg-gray-100 rounded transition-colors"
          title="刷新模型列表"
        >
          <RefreshCw className={`w-3.5 h-3.5 text-gray-500 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>
      <div className="relative">
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="w-full flex items-center justify-between px-4 py-2.5 bg-white border border-gray-300 rounded-lg hover:border-blue-400 hover:bg-blue-50/50 transition-all text-left"
        >
          <div className="flex items-center gap-2 min-w-0">
            <Brain className="w-4 h-4 text-blue-600 shrink-0" />
            <span className="text-sm font-medium text-gray-900 truncate">
              {currentModel?.name || '请选择模型'}
            </span>
            {currentModel && (
              <span className={`text-xs px-2 py-0.5 rounded shrink-0 ${
                PROVIDER_COLORS[currentModel.provider] || 'bg-gray-100 text-gray-700'
              }`}>
                {PROVIDER_LABELS[currentModel.provider] || currentModel.provider}
              </span>
            )}
          </div>
          <ChevronDown className={`w-4 h-4 text-gray-500 transition-transform shrink-0 ${isOpen ? 'rotate-180' : ''}`} />
        </button>

        {isOpen && (
          <>
            <div
              className="fixed inset-0 z-10"
              onClick={() => setIsOpen(false)}
            />
            <div className="absolute z-20 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-y-auto">
              {models.map((model) => (
                <button
                  key={model.id}
                  onClick={() => {
                    setSelectedModel(model.id)
                    localStorage.setItem('selectedModel', model.id)
                    setIsOpen(false)
                    toast.success(`已选择: ${model.name}`)
                    // 触发自定义事件，通知其他组件模型已更改
                    window.dispatchEvent(new Event('modelChanged'))
                  }}
                  className={`w-full px-4 py-2.5 text-left hover:bg-blue-50 transition-colors border-b border-gray-100 last:border-b-0 ${
                    selectedModel === model.id
                      ? 'bg-blue-50 text-blue-700 font-medium'
                      : 'text-gray-700'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <Brain className="w-4 h-4" />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium truncate">{model.name}</div>
                      <div className="text-xs text-gray-500 mt-0.5">
                        {PROVIDER_LABELS[model.provider] || model.provider}
                      </div>
                    </div>
                    {selectedModel === model.id && (
                      <div className="w-2 h-2 bg-blue-600 rounded-full shrink-0"></div>
                    )}
                  </div>
                </button>
              ))}
            </div>
          </>
        )}
      </div>
      <p className="text-xs text-gray-500 mt-2 px-1">
        不同模型效果不同，建议自行测试
      </p>
    </div>
  )
}
