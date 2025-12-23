import { useState, useEffect } from 'react'
import { Brain, ChevronDown, CheckCircle2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { listModelsFromConfigs } from '../services/modelService'

interface ModelOption {
  id: string
  name: string
  provider: string
  providerName: string
  modelId: string
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
  openai: 'bg-green-100 text-green-700 border-green-200',
  deepseek: 'bg-blue-100 text-blue-700 border-blue-200',
  qwen: 'bg-purple-100 text-purple-700 border-purple-200',
  claude: 'bg-orange-100 text-orange-700 border-orange-200',
  gemini: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  groq: 'bg-indigo-100 text-indigo-700 border-indigo-200',
  ollama: 'bg-teal-100 text-teal-700 border-teal-200',
}

export default function ModelSelectorPanel() {
  const [selectedModel, setSelectedModel] = useState<string>('')
  const [availableModels, setAvailableModels] = useState<ModelOption[]>([])
  const [isOpen, setIsOpen] = useState(false)

  // 从 localStorage 加载所有已配置的模型
  const loadModels = async () => {
    try {
      // 使用统一的服务获取模型列表 (已包含 migration, instance 遍历, 和 filtering)
      const allModels = await listModelsFromConfigs()

      const modelList: ModelOption[] = allModels.map((m: any) => {
        let modelName = m.name
        // 尝试从 name 中移除 id 部分 "Name (ID)" -> "Name"
        if (modelName.endsWith(`(${m.model})`)) {
          modelName = modelName.slice(0, -(m.model.length + 2)).trim()
        } else if (modelName === m.model) {
          // 如果 name 和 model 一样，尝试美化
          // 处理特殊格式的模型名称（如 hf.co/unsloth/Qwen3-4B-GGUF:Q6_K_XL）
          if (modelName.includes('/')) {
            const parts = modelName.split('/')
            modelName = parts[parts.length - 1]
          }
          // 处理量化格式（如 :Q6_K_XL），保留量化信息
          if (modelName.includes(':')) {
            const colonIndex = modelName.lastIndexOf(':')
            if (colonIndex > 0) {
              const baseName = modelName.substring(0, colonIndex)
              const quantInfo = modelName.substring(colonIndex + 1)
              modelName = `${baseName} (${quantInfo})`
            }
          }
        }

        return {
          id: m.id,
          name: modelName || m.model, // Display name
          provider: m.provider,
          providerName: PROVIDER_LABELS[m.provider] || m.provider,
          modelId: m.model
        }
      })

      // 按提供商名称排序，然后按模型名称排序
      modelList.sort((a, b) => {
        if (a.providerName !== b.providerName) {
          return a.providerName.localeCompare(b.providerName)
        }
        return a.name.localeCompare(b.name)
      })

      setAvailableModels(modelList)

      // 加载已选择的模型
      const savedSelected = localStorage.getItem('selectedModel')

      if (savedSelected && modelList.find(m => m.id === savedSelected)) {
        setSelectedModel(savedSelected)
      } else if (modelList.length > 0) {
        // 如果没有保存的选择，选择第一个
        setSelectedModel(modelList[0].id)
        localStorage.setItem('selectedModel', modelList[0].id)
        // 触发自定义事件，通知其他组件模型已更改
        window.dispatchEvent(new Event('modelChanged'))
      } else {
        setSelectedModel('')
      }
    } catch (error) {
      console.error('加载模型列表失败:', error)
      setAvailableModels([])
      setSelectedModel('')
    }
  }

  useEffect(() => {
    loadModels()


    // 监听 storage 变化 (跨标签页同步)
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'modelConfigs' || e.key === 'selectedModel') {
        loadModels()
      }
    }
    window.addEventListener('storage', handleStorageChange)

    // 监听配置保存事件 (同窗口同步)
    const handleConfigUpdate = () => {
      loadModels()
    }
    window.addEventListener('modelConfigsUpdated', handleConfigUpdate)

    // 监听模型切换事件 (同窗口同步)
    const handleModelChange = () => {
      // 主要是重新高亮选中项，这里 loadModels 也会读取 selectedModel
      loadModels()
    }
    window.addEventListener('modelChanged', handleModelChange)

    return () => {
      window.removeEventListener('storage', handleStorageChange)
      window.removeEventListener('modelConfigsUpdated', handleConfigUpdate)
      window.removeEventListener('modelChanged', handleModelChange)
    }
  }, [])

  const currentModel = availableModels.find(m => m.id === selectedModel)

  const handleModelChange = (modelId: string) => {
    setSelectedModel(modelId)
    localStorage.setItem('selectedModel', modelId)
    setIsOpen(false)
    const model = availableModels.find(m => m.id === modelId)
    if (model) {
      toast.success(`已切换到: ${model.providerName} - ${model.name}`)
      // 触发自定义事件，通知其他组件模型已更改
      window.dispatchEvent(new Event('modelChanged'))
    }
  }

  if (availableModels.length === 0) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 mb-6">
        <div className="flex items-start gap-3">
          <Brain className="w-5 h-5 text-yellow-600 mt-0.5 shrink-0" />
          <div className="flex-1">
            <h3 className="text-sm font-semibold text-yellow-900 mb-1">未配置模型</h3>
            <p className="text-xs text-yellow-800">
              请先在下方配置至少一个提供商的 API Key 和模型，然后才能在此处选择使用。
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">选择当前使用的模型</h2>
      <div className="relative">
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 border border-gray-300 rounded-lg hover:border-blue-400 hover:bg-blue-50/50 transition-all text-left"
        >
          <div className="flex items-center gap-3 min-w-0">
            <Brain className="w-5 h-5 text-blue-600 shrink-0" />
            <div className="flex-1 min-w-0">
              {currentModel ? (
                <>
                  <div className="text-sm font-medium text-gray-900 truncate">
                    {currentModel.name}
                  </div>
                  <div className="text-xs text-gray-500 mt-0.5">
                    {currentModel.providerName}
                  </div>
                </>
              ) : (
                <div className="text-sm text-gray-500">请选择模型</div>
              )}
            </div>
            {currentModel && (
              <span className={`text-xs px-2.5 py-1 rounded border shrink-0 ${PROVIDER_COLORS[currentModel.provider] || 'bg-gray-100 text-gray-700 border-gray-200'
                }`}>
                {currentModel.providerName}
              </span>
            )}
          </div>
          <ChevronDown className={`w-4 h-4 text-gray-500 transition-transform shrink-0 ml-2 ${isOpen ? 'rotate-180' : ''}`} />
        </button>

        {isOpen && (
          <>
            <div
              className="fixed inset-0 z-10"
              onClick={() => setIsOpen(false)}
            />
            <div className="absolute z-20 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-y-auto">
              {availableModels.length === 0 ? (
                <div className="px-4 py-3 text-sm text-gray-500 text-center">
                  暂无可用模型
                </div>
              ) : (
                <>
                  <div className="px-4 py-2 bg-gray-50 border-b border-gray-200 text-xs font-medium text-gray-700 sticky top-0">
                    共 {availableModels.length} 个可用模型
                  </div>
                  {availableModels.map((model) => (
                    <button
                      key={model.id}
                      onClick={() => handleModelChange(model.id)}
                      className={`w-full px-4 py-3 text-left hover:bg-blue-50 transition-colors border-b border-gray-100 last:border-b-0 ${selectedModel === model.id
                        ? 'bg-blue-50 text-blue-700 font-medium'
                        : 'text-gray-700'
                        }`}
                    >
                      <div className="flex items-center gap-3">
                        <Brain className="w-4 h-4" />
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium truncate">{model.name}</div>
                          <div className="text-xs text-gray-500 mt-0.5">{model.providerName}</div>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <span className={`text-xs px-2 py-0.5 rounded border ${PROVIDER_COLORS[model.provider] || 'bg-gray-100 text-gray-700 border-gray-200'
                            }`}>
                            {model.providerName}
                          </span>
                          {selectedModel === model.id && (
                            <CheckCircle2 className="w-4 h-4 text-blue-600" />
                          )}
                        </div>
                      </div>
                    </button>
                  ))}
                </>
              )}
            </div>
          </>
        )}
      </div>
      <p className="text-xs text-gray-500 mt-2">
        当前选择的模型将用于生成笔记。共 {availableModels.length} 个可用模型，可以在下方配置更多模型。
      </p>
    </div>
  )
}
