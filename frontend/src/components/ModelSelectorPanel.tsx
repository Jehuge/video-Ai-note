import { useState, useEffect } from 'react'
import { Brain, ChevronDown, CheckCircle2 } from 'lucide-react'
import ProviderIcon from './ProviderIcon'
import toast from 'react-hot-toast'

interface ModelOption {
  id: string
  name: string
  provider: string      // Instance ID
  providerType: string  // Provider Type (openai, etc.)
  providerName: string  // Instance Name
  modelId: string       // Actual model ID string
}

interface ProviderInstance {
  id: string
  name: string
  providerType: string
  apiKey: string
  baseUrl: string
  models: string[]
}

const PROVIDER_COLORS: Record<string, string> = {
  openai: 'bg-green-100 text-green-700 border-green-200',
  deepseek: 'bg-blue-100 text-blue-700 border-blue-200',
  qwen: 'bg-purple-100 text-purple-700 border-purple-200',
  claude: 'bg-orange-100 text-orange-700 border-orange-200',
  gemini: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  groq: 'bg-indigo-100 text-indigo-700 border-indigo-200',
  ollama: 'bg-teal-100 text-teal-700 border-teal-200',
  siliconflow: 'bg-indigo-100 text-indigo-700 border-indigo-200',
}

export default function ModelSelectorPanel() {
  const [selectedModel, setSelectedModel] = useState<string>('')
  const [availableModels, setAvailableModels] = useState<ModelOption[]>([])
  const [isOpen, setIsOpen] = useState(false)

  // 从 localStorage 加载所有已配置的模型
  const loadModels = () => {
    try {
      const savedConfigs = localStorage.getItem('modelConfigs')

      if (!savedConfigs) {
        setAvailableModels([])
        setSelectedModel('')
        return
      }

      const parsed = JSON.parse(savedConfigs)
      let instances: ProviderInstance[] = []

      // 兼容旧版配置（虽然 ModelConfig 会自动迁移，但为了安全起见这里也处理一下）
      if (Array.isArray(parsed)) {
        instances = parsed
      } else {
        // 如果是旧版对象格式，暂时忽略或尝试简单转换用于显示（实际迁移由 ModelConfig 负责）
        return
      }

      const modelList: ModelOption[] = []

      instances.forEach(instance => {
        // 检查是否有配置的模型
        if (instance.models && instance.models.length > 0) {
          // 检查是否有效 (Ollama 或 有 API Key)
          const hasApiKey = instance.providerType === 'ollama' || (instance.apiKey && instance.apiKey.trim().length > 0)

          if (hasApiKey) {
            instance.models.forEach(modelStr => {
              const trimmedId = modelStr.trim()
              if (!trimmedId) return

              // 构建显示名称
              let modelName = trimmedId
              // 简单处理名称，移除可能的重复前缀
              if (modelName.startsWith(instance.providerType + '-')) {
                modelName = modelName.substring(instance.providerType.length + 1)
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

              modelList.push({
                id: `${instance.id}:${trimmedId}`, // 组合ID: 实例ID:模型ID
                name: modelName,
                provider: instance.id,
                providerType: instance.providerType,
                providerName: instance.name,
                modelId: trimmedId
              })
            })
          }
        }
      })

      // 按实例名称排序，然后按模型名称排序
      modelList.sort((a, b) => {
        if (a.providerName !== b.providerName) {
          return a.providerName.localeCompare(b.providerName)
        }
        return a.name.localeCompare(b.name)
      })

      setAvailableModels(modelList)

      // 加载已选择的模型
      const savedSelected = localStorage.getItem('selectedModel')

      // 尝试匹配已保存的选择
      // savedSelected 可能是旧格式 (provider-model) 也可能是新格式 (instanceId:modelId)
      // 如果是旧格式，尝试在新列表中找到兼容的项

      let matchedModel = modelList.find(m => m.id === savedSelected)

      if (!matchedModel && savedSelected) {
        // 尝试模糊匹配 (比如旧格式是 ollama-llama3，新格式可能是 UUID:llama3)
        // 这只有在只有一个相同类型实例时才准确，但作为 fallback 够用了
        if (!savedSelected.includes(':')) {
          // 旧格式，尝试找拥有此 modelId 的模型
          // 先尝试匹配 provider-model 格式拆分
          const parts = savedSelected.split('-')
          const potentialProviderType = parts[0]
          const potentialModelName = parts.slice(1).join('-')

          // 尝试在列表中找
          matchedModel = modelList.find(m => m.providerType === potentialProviderType && m.modelId === potentialModelName)

          // 如果找不到，尝试直接匹配 modelId (比如 ollama 的情况)
          if (!matchedModel) {
            matchedModel = modelList.find(m => m.modelId === savedSelected)
          }
        }
      }

      if (matchedModel) {
        setSelectedModel(matchedModel.id)
        // 如果 ID 格式变了（旧->新），更新 storage
        if (matchedModel.id !== savedSelected) {
          localStorage.setItem('selectedModel', matchedModel.id)
        }
      } else if (modelList.length > 0) {
        // 如果没有保存的选择或找不到，选择第一个
        setSelectedModel(modelList[0].id)
        localStorage.setItem('selectedModel', modelList[0].id)
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

    // 监听 storage 变化
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'modelConfigs' || e.key === 'selectedModel') {
        loadModels()
      }
    }
    window.addEventListener('storage', handleStorageChange)

    // 监听自定义事件（用于同窗口组件通信）
    const handleModelChanged = () => {
      // 这里主要是重新读取 selectedModel，虽然我们通常自己通过 handleModelChange 更新
      // 但如果有其他组件修改了 selectedModel，这里可以同步
      const saved = localStorage.getItem('selectedModel')
      if (saved && saved !== selectedModel) {
        setSelectedModel(saved)
      }
      // 同时也刷新列表，因为可能是 config 变了触发的
      loadModels()
    }
    window.addEventListener('modelChanged', handleModelChanged)

    // 定期检查配置变化
    const interval = setInterval(loadModels, 2000)

    return () => {
      window.removeEventListener('storage', handleStorageChange)
      window.removeEventListener('modelChanged', handleModelChanged)
      clearInterval(interval)
    }
  }, [selectedModel])

  const currentModel = availableModels.find(m => m.id === selectedModel)

  const handleModelChange = (id: string) => {
    setSelectedModel(id)
    localStorage.setItem('selectedModel', id)
    setIsOpen(false)
    const model = availableModels.find(m => m.id === id)
    if (model) {
      toast.success(`已切换到: ${model.providerName} - ${model.name}`)
      // 触发自定义事件
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
            {currentModel ? (
              <ProviderIcon provider={currentModel.providerType} className="w-5 h-5 shrink-0" />
            ) : (
              <Brain className="w-5 h-5 text-blue-600 shrink-0" />
            )}
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
              <span className={`text-xs px-2.5 py-1 rounded border shrink-0 ${PROVIDER_COLORS[currentModel.providerType] || 'bg-gray-100 text-gray-700 border-gray-200'
                }`}>
                {currentModel.providerType}
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
                    <ProviderIcon provider={model.providerType} className="w-4 h-4" />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium truncate">{model.name}</div>
                      <div className="text-xs text-gray-500 mt-0.5">{model.providerName}</div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className={`text-xs px-2 py-0.5 rounded border ${PROVIDER_COLORS[model.providerType] || 'bg-gray-100 text-gray-700 border-gray-200'
                        }`}>
                        {model.providerType}
                      </span>
                      {selectedModel === model.id && (
                        <CheckCircle2 className="w-4 h-4 text-blue-600" />
                      )}
                    </div>
                  </div>
                </button>
              ))}
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
