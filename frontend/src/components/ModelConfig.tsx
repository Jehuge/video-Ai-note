import { useState, useEffect, useRef } from 'react'
import { Save, Eye, EyeOff, Key, Brain, CheckCircle2, RefreshCw, Loader2, Info } from 'lucide-react'
import toast from 'react-hot-toast'
import { getModelList, testModelConnection, getProviders } from '../services/api'
import { migrateLegacyConfigs, saveModelConfigs, loadModelConfigs } from '../services/modelService'
import ModelSelectorPanel from './ModelSelectorPanel'

interface Provider {
  id: string
  name: string
  type: string
  logo: string
  base_url: string
}

interface ModelConfig {
  provider: string
  apiKey: string
  baseUrl?: string
  model: string  // 保留用于兼容，但主要使用 models
  models: string[]  // 多选的模型列表
}

interface ModelItem {
  id: string
  name: string
  provider: string
}

const PROVIDER_ICONS: Record<string, string> = {
  openai: '🤖',
  deepseek: '🔍',
  qwen: '💬',
  claude: '🧠',
  gemini: '✨',
  groq: '⚡',
  ollama: '🦙',
}

const PROVIDER_COLORS: Record<string, string> = {
  openai: 'bg-green-500',
  deepseek: 'bg-blue-500',
  qwen: 'bg-purple-500',
  claude: 'bg-orange-500',
  gemini: 'bg-yellow-500',
  groq: 'bg-indigo-500',
  ollama: 'bg-teal-500',
}

export default function ModelConfig() {
  const [providers, setProviders] = useState<Provider[]>([])
  const [selectedProvider, setSelectedProvider] = useState<string>('openai')
  const [configs, setConfigs] = useState<Record<string, ModelConfig>>({})
  // 当前 provider 下选择的 instance id（单一全局选中，用作 UI 编辑）
  const [selectedInstanceId, setSelectedInstanceId] = useState<string>('default')
  const [showApiKeys, setShowApiKeys] = useState<Record<string, boolean>>({})
  const [saving, setSaving] = useState(false)
  const [loadingModels, setLoadingModels] = useState(false)
  const [availableModels, setAvailableModels] = useState<ModelItem[]>([])
  const loadModelsRef = useRef<(() => Promise<void>) | null>(null)
  // 缓存已加载的模型列表，避免重复请求
  const modelsCacheRef = useRef<Record<string, { models: ModelItem[], timestamp: number }>>({})
  // 防止重复加载提供商列表
  const providersLoadedRef = useRef(false)

  // 加载提供商列表
  useEffect(() => {
    // 如果已经加载过，直接返回
    if (providersLoadedRef.current) {
      return
    }

    const loadProviders = async () => {
      providersLoadedRef.current = true
      // 迁移旧的 modelConfigs 到新 schema（如果需要）
      try {
        migrateLegacyConfigs()
      } catch (e) {
        console.warn('迁移模型配置时出错:', e)
      }
      try {
        const response = await getProviders()
        if (response.data.code === 200) {
          const providerList = response.data.data || []
          setProviders(providerList)
          
          // 初始化配置
          const initialConfigs: Record<string, ModelConfig> = {}
          providerList.forEach((p: Provider) => {
            // 使用 instances 新格式
            initialConfigs[p.id] = {
              provider: p.id,
              apiKey: '',
              baseUrl: p.base_url,
              model: '', // 兼容字段
              models: [],
              instances: [
                {
                  id: 'default',
                  name: '默认配置',
                  apiKey: '',
                  baseUrl: p.base_url,
                  models: [],
                  modelCapabilities: {},
                },
              ],
            }
          })
          
          // 从 localStorage 加载已保存的配置
          const savedConfigs = localStorage.getItem('modelConfigs')
          if (savedConfigs) {
            try {
              const parsed = JSON.parse(savedConfigs)
              // 合并已保存的配置（支持 instances 或旧格式）
              Object.keys(parsed).forEach((key) => {
                if (!initialConfigs[key]) return
                const cfg = parsed[key]
                if (cfg?.instances && Array.isArray(cfg.instances)) {
                  initialConfigs[key] = {
                    ...initialConfigs[key],
                    ...cfg,
                    instances: cfg.instances,
                  }
                } else {
                  // 兼容旧格式：转换为单个 instance
                  initialConfigs[key] = {
                    ...initialConfigs[key],
                    ...cfg,
                    instances: [
                      {
                        id: 'default',
                        name: '默认配置',
                        apiKey: cfg.apiKey || cfg.api_key || '',
                        baseUrl: cfg.baseUrl || cfg.base_url || initialConfigs[key].instances[0].baseUrl,
                        models: cfg.models || (cfg.model ? [cfg.model] : []),
                        modelCapabilities: cfg.modelCapabilities || {},
                      },
                    ],
                  }
                }
              })
            } catch (e) {
              console.error('加载配置失败:', e)
            }
          }
          
          setConfigs(initialConfigs)
        }
      } catch (error) {
        console.error('加载提供商列表失败:', error)
        // 如果加载失败，重置标记，允许重试
        providersLoadedRef.current = false
      }
    }
    loadProviders()
  }, [])

  // 当切换提供商时，从缓存加载模型列表（如果存在）
  // 不再自动刷新，需要用户手动点击"刷新列表"按钮
  useEffect(() => {
    const currentConfig = configs[selectedProvider]
    if (!currentConfig) {
      setAvailableModels([])
      return
    }
    
    const cacheKey = `${selectedProvider}-${currentConfig.apiKey || ''}-${currentConfig.baseUrl || ''}`
    const cached = modelsCacheRef.current[cacheKey]
    
    // 如果缓存存在且未过期（5分钟内），直接使用缓存
    if (cached && Date.now() - cached.timestamp < 5 * 60 * 1000) {
      setAvailableModels(cached.models)
    } else {
      // 如果没有缓存或缓存过期，清空列表，等待用户手动刷新
      setAvailableModels([])
    }
    // 只监听 selectedProvider 的变化
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProvider, configs])

  // 计算当前 provider 的 active instance（UI 编辑目标）
  const providerConfigRaw = configs[selectedProvider] || ({} as any)
  const providerInstances = (providerConfigRaw.instances && Array.isArray(providerConfigRaw.instances))
    ? providerConfigRaw.instances
    : [
        {
          id: 'default',
          name: '默认配置',
          apiKey: providerConfigRaw.apiKey || '',
          baseUrl: providerConfigRaw.baseUrl || providers.find(p => p.id === selectedProvider)?.base_url || '',
          models: providerConfigRaw.models || (providerConfigRaw.model ? [providerConfigRaw.model] : []),
          modelCapabilities: providerConfigRaw.modelCapabilities || {},
        },
      ]

  // 如果当前 selectedInstanceId 不在 instances 中，重置为第一个
  useEffect(() => {
    if (!providerInstances.find((ins: any) => ins.id === selectedInstanceId)) {
      setSelectedInstanceId(providerInstances[0]?.id || 'default')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProvider, configs])

  const currentInstance = providerInstances.find((ins: any) => ins.id === selectedInstanceId) || providerInstances[0]
  const currentConfig = {
    provider: selectedProvider,
    apiKey: currentInstance?.apiKey || '',
    baseUrl: currentInstance?.baseUrl || providers.find(p => p.id === selectedProvider)?.base_url || '',
    model: currentInstance?.models && currentInstance.models.length > 0 ? currentInstance.models[0] : '',
    models: currentInstance?.models || [],
  }

  const loadModels = async () => {
    // Ollama 不需要 API Key，其他提供商需要
    if (selectedProvider !== 'ollama' && !currentConfig.apiKey?.trim()) {
      toast.error('请先输入 API Key')
      setAvailableModels([])
      return
    }

    // 检查缓存
    const cacheKey = `${selectedProvider}-${currentConfig.apiKey || ''}-${currentConfig.baseUrl || ''}`
    const cached = modelsCacheRef.current[cacheKey]
    
    // 如果缓存存在且未过期（5分钟内），直接使用缓存
    if (cached && Date.now() - cached.timestamp < 5 * 60 * 1000) {
      setAvailableModels(cached.models)
      toast.success(`已加载缓存的模型列表（${cached.models.length} 个模型）`, { duration: 2000 })
      return
    }

    setLoadingModels(true)
    try {
    const response = await getModelList({
        provider: selectedProvider,
        api_key: currentConfig.apiKey || '',  // Ollama 可以为空
        base_url: currentConfig.baseUrl,
      })

      if (response.data.code === 200) {
        const models = response.data.data || []
        setAvailableModels(models)
        
        // 保存到缓存
        modelsCacheRef.current[cacheKey] = {
          models,
          timestamp: Date.now(),
        }
        
        // 同时保存到 localStorage 作为持久化缓存
        try {
          const cacheStorageKey = 'modelListCache'
          const allCache = JSON.parse(localStorage.getItem(cacheStorageKey) || '{}')
          allCache[cacheKey] = {
            models,
            timestamp: Date.now(),
          }
          localStorage.setItem(cacheStorageKey, JSON.stringify(allCache))
        } catch (e) {
          console.warn('保存模型列表缓存失败:', e)
        }
        
        toast.success(`已加载 ${models.length} 个模型`, { duration: 2000 })
        
        // 如果当前选择的模型不在列表中，但列表不为空，选择第一个
        if (models.length > 0) {
          const hasCurrentModel = models.find((m: ModelItem) => m.id === currentConfig.model)
          if (!hasCurrentModel && currentConfig.model) {
            // 如果之前选择的模型不在新列表中，保持原选择但显示提示
            console.warn(`之前选择的模型 ${currentConfig.model} 不在当前列表中`)
          }
        }
      } else {
        toast.error(response.data.msg || '获取模型列表失败')
        setAvailableModels([])
      }
    } catch (error: any) {
      console.error('获取模型列表失败:', error)
      toast.error(error.response?.data?.msg || '获取模型列表失败')
      setAvailableModels([])
    } finally {
      setLoadingModels(false)
    }
  }

  // 将 loadModels 保存到 ref，供 useEffect 使用
  // 注意：这里不包含 currentConfig.model，避免选择模型时触发刷新
  useEffect(() => {
    loadModelsRef.current = loadModels
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentConfig.apiKey, currentConfig.baseUrl, selectedProvider])

  const handleSave = async () => {
    setSaving(true)
    try {
      // 验证 API Key（Ollama 除外）
      if (selectedProvider !== 'ollama' && !currentConfig.apiKey.trim()) {
        toast.error('请输入 API Key')
        setSaving(false)
        return
      }

      // 验证模型（至少选择一个）
      if (!currentConfig.models || currentConfig.models.length === 0) {
        toast.error('请至少选择一个模型')
        setSaving(false)
        return
      }

      // 构建新的 configs，使用 instances 格式保存当前 provider 的 instance
      const updatedConfigs = {
        ...configs,
      } as any

      const providerCfg = updatedConfigs[selectedProvider] || {}
      const instances = providerCfg.instances && Array.isArray(providerCfg.instances) ? providerCfg.instances.slice() : []

      // 更新或插入当前 instance
      const existingIndex = instances.findIndex((ins: any) => ins.id === selectedInstanceId)
      const newInstance = {
        id: selectedInstanceId || 'default',
        name: currentInstance?.name || '默认配置',
        apiKey: currentConfig.apiKey || '',
        baseUrl: currentConfig.baseUrl || '',
        models: currentConfig.models || [],
        modelCapabilities: currentInstance?.modelCapabilities || {},
      }

      if (existingIndex >= 0) {
        instances[existingIndex] = newInstance
      } else {
        instances.push(newInstance)
      }

      updatedConfigs[selectedProvider] = {
        ...(providerCfg || {}),
        instances,
      }

      // 确保其他 providers 至少存在空结构
      providers.forEach((provider) => {
        if (!updatedConfigs[provider.id]) {
          updatedConfigs[provider.id] = {
            provider: provider.id,
            instances: [
              {
                id: 'default',
                name: '默认配置',
                apiKey: '',
                baseUrl: provider.base_url,
                models: [],
                modelCapabilities: {},
              },
            ],
          }
        }
      })

      // 使用共享的保存函数
      saveModelConfigs(updatedConfigs)
      setConfigs(updatedConfigs)
      
      // 显示保存的配置信息
      const selectedModelNames = currentConfig.models
        .map((modelId: string) => {
          const model = availableModels.find((m: ModelItem) => m.id === modelId)
          return model?.name || modelId
        })
        .join(', ')
      toast.success(`配置保存成功！已选择 ${currentConfig.models.length} 个模型：${selectedModelNames}`, { duration: 3000 })
      
      // 保存后重新加载模型列表，确保显示正确
      setTimeout(() => {
        loadModels()
      }, 500)
    } catch (error: any) {
      toast.error(error.message || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleConfigChange = (field: keyof ModelConfig, value: string) => {
    // 更新当前 instance 的字段（仅在内存中）
    setConfigs((prev) => {
      const copy = { ...(prev || {}) } as any
      const providerCfg = copy[selectedProvider] || {}
      const instances = providerCfg.instances && Array.isArray(providerCfg.instances) ? providerCfg.instances.slice() : [
        {
          id: 'default',
          name: '默认配置',
          apiKey: '',
          baseUrl: providers.find(p => p.id === selectedProvider)?.base_url || '',
          models: [],
          modelCapabilities: {},
        },
      ]

      const idx = instances.findIndex((ins: any) => ins.id === selectedInstanceId)
      const target = idx >= 0 ? { ...instances[idx] } : { ...instances[0] }
      // @ts-ignore
      target[field] = value
      if (idx >= 0) {
        instances[idx] = target
      } else {
        instances[0] = target
      }

      copy[selectedProvider] = {
        ...(providerCfg || {}),
        instances,
      }
      return copy
    })
  }
  
  // 处理模型多选
  const handleModelToggle = (modelId: string) => {
    const currentModels = currentConfig.models || []
    const isSelected = currentModels.includes(modelId)
    
    const updatedModels = isSelected
      ? currentModels.filter((id: string) => id !== modelId)
      : [...currentModels, modelId]

    // 更新当前 instance 的 models
    setConfigs((prev) => {
      const copy = { ...(prev || {}) } as any
      const providerCfg = copy[selectedProvider] || {}
      const instances = providerCfg.instances && Array.isArray(providerCfg.instances) ? providerCfg.instances.slice() : [
        {
          id: 'default',
          name: '默认配置',
          apiKey: '',
          baseUrl: providers.find(p => p.id === selectedProvider)?.base_url || '',
          models: [],
          modelCapabilities: {},
        },
      ]
      const idx = instances.findIndex((ins: any) => ins.id === selectedInstanceId)
      const target = idx >= 0 ? { ...instances[idx] } : { ...instances[0] }
      target.models = updatedModels
      if (idx >= 0) {
        instances[idx] = target
      } else {
        instances[0] = target
      }
      copy[selectedProvider] = {
        ...(providerCfg || {}),
        instances,
      }
      return copy
    })
  }

  const toggleApiKeyVisibility = (provider: string) => {
    setShowApiKeys((prev) => ({
      ...prev,
      [provider]: !prev[provider],
    }))
  }

  // 实例管理：添加/删除/重命名
  const addInstance = () => {
    const newId = `inst-${Date.now()}`
    const newInstance = {
      id: newId,
      name: '新实例',
      apiKey: '',
      baseUrl: providers.find(p => p.id === selectedProvider)?.base_url || '',
      models: [],
      modelCapabilities: {},
    }

    setConfigs((prev) => {
      const copy = { ...(prev || {}) } as any
      const providerCfg = copy[selectedProvider] || {}
      const instances = providerCfg.instances && Array.isArray(providerCfg.instances) ? providerCfg.instances.slice() : []
      instances.push(newInstance)
      copy[selectedProvider] = {
        ...(providerCfg || {}),
        instances,
      }
      return copy
    })
    setSelectedInstanceId(newId)
  }

  const removeInstance = (instanceId: string) => {
    if (!confirm('确认删除该实例？此操作不可撤销')) return
    setConfigs((prev) => {
      const copy = { ...(prev || {}) } as any
      const providerCfg = copy[selectedProvider] || {}
      let instances = providerCfg.instances && Array.isArray(providerCfg.instances) ? providerCfg.instances.slice() : []
      if (instances.length <= 1) {
        // 保持至少一个实例
        instances = [
          {
            id: 'default',
            name: '默认配置',
            apiKey: '',
            baseUrl: providers.find(p => p.id === selectedProvider)?.base_url || '',
            models: [],
            modelCapabilities: {},
          },
        ]
      } else {
        instances = instances.filter((ins: any) => ins.id !== instanceId)
      }
      copy[selectedProvider] = {
        ...(providerCfg || {}),
        instances,
      }
      return copy
    })
    // 切换选中到第一个实例
    setSelectedInstanceId('default')
  }

  const renameInstance = (instanceId: string, newName: string) => {
    setConfigs((prev) => {
      const copy = { ...(prev || {}) } as any
      const providerCfg = copy[selectedProvider] || {}
      const instances = providerCfg.instances && Array.isArray(providerCfg.instances) ? providerCfg.instances.slice() : []
      const idx = instances.findIndex((ins: any) => ins.id === instanceId)
      if (idx >= 0) {
        instances[idx] = { ...instances[idx], name: newName }
      }
      copy[selectedProvider] = {
        ...(providerCfg || {}),
        instances,
      }
      return copy
    })
  }

  const testConnection = async () => {
    // Ollama 不需要 API Key
    if (selectedProvider !== 'ollama' && !currentConfig.apiKey.trim()) {
      toast.error('请先输入 API Key')
      return
    }

    toast.loading('测试连接中...', { id: 'test-connection' })
    
    try {
      const response = await testModelConnection({
        provider: selectedProvider,
        api_key: currentConfig.apiKey || '',  // Ollama 可以为空
        base_url: currentConfig.baseUrl,
      })
      
      if (response.data.code === 200) {
        toast.success(response.data.msg || '连接成功', { id: 'test-connection' })
        // 连接成功后，加载模型列表
        setTimeout(() => {
          loadModels()
        }, 300)
      } else {
        toast.error(response.data.msg || '连接失败', { id: 'test-connection' })
      }
    } catch (error: any) {
      toast.error('连接失败: ' + (error.response?.data?.msg || error.message), { id: 'test-connection' })
    }
  }

  const currentProvider = providers.find(p => p.id === selectedProvider)
  const selectedModel = availableModels.find(m => m.id === currentConfig.model)

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="max-w-4xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">模型配置</h1>
          <p className="text-gray-600">配置 AI 模型的 API Key 和参数</p>
        </div>

        {/* 模型选择器 - 显示所有已配置的模型 */}
        <ModelSelectorPanel />

        {/* 提供商选择 */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">选择提供商</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {providers.map((provider) => {
              const providerConfig = configs[provider.id]
              const hasConfig = providerConfig && (provider.id === 'ollama' || providerConfig.apiKey?.trim())
              const hasModel = providerConfig?.model?.trim()
              
              return (
                <button
                  key={provider.id}
                  onClick={() => setSelectedProvider(provider.id)}
                  className={`flex flex-col items-center gap-2 px-4 py-3 rounded-lg border-2 transition-all relative ${
                    selectedProvider === provider.id
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div className={`w-12 h-12 ${PROVIDER_COLORS[provider.id] || 'bg-gray-500'} rounded-lg flex items-center justify-center text-2xl`}>
                    {PROVIDER_ICONS[provider.id] || '🤖'}
                  </div>
                  <div className="text-center">
                    <div className="text-sm font-medium text-gray-900">{provider.name}</div>
                    {hasConfig && (
                      <div className="text-xs text-green-600 mt-0.5">
                        {hasModel ? '已配置' : '未选择模型'}
                      </div>
                    )}
                  </div>
                  {selectedProvider === provider.id && (
                    <CheckCircle2 className="w-5 h-5 text-blue-500" />
                  )}
                  {hasModel && (
                    <div className="absolute top-1 right-1 w-2 h-2 bg-green-500 rounded-full"></div>
                  )}
                </button>
              )
            })}
          </div>
        </div>

        {/* 配置表单 */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-gray-900">
              {currentProvider?.name || '提供商'} 配置
            </h2>
            {selectedModel && (
              <div className="flex items-center gap-2 px-3 py-1.5 bg-green-50 border border-green-200 rounded-lg">
                <Info className="w-4 h-4 text-green-600" />
                <span className="text-sm text-green-700">
                  当前模型: <span className="font-medium">{selectedModel.name}</span>
                </span>
              </div>
            )}
          </div>

          {/* 实例选择与管理 */}
          <div className="flex items-center justify-between mb-4 gap-4">
            <div className="flex items-center gap-2">
              <label className="text-sm text-gray-700">实例</label>
              <select
                value={selectedInstanceId}
                onChange={(e) => setSelectedInstanceId(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-lg"
              >
                {(providerInstances || []).map((ins: any) => (
                  <option key={ins.id} value={ins.id}>
                    {ins.name || ins.id}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={addInstance}
                className="px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm"
              >
                新增实例
              </button>
              <button
                onClick={() => removeInstance(selectedInstanceId)}
                className="px-3 py-1.5 bg-red-50 text-red-700 rounded-lg hover:bg-red-100 text-sm"
              >
                删除实例
              </button>
            </div>
          </div>

          <div className="space-y-6">
            {/* API Key */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                <Key className="w-4 h-4 inline mr-1" />
                API Key
                {selectedProvider !== 'ollama' && <span className="text-red-500 ml-1">*</span>}
                {selectedProvider === 'ollama' && <span className="text-gray-400 ml-1 text-xs">(可选)</span>}
                {currentConfig.apiKey && (
                  <span className="ml-2 text-xs text-green-600">✓ 已配置</span>
                )}
              </label>
              <div className="relative">
                <input
                  type={showApiKeys[selectedProvider] ? 'text' : 'password'}
                  value={currentConfig.apiKey || ''}
                  onChange={(e) => handleConfigChange('apiKey', e.target.value)}
                  placeholder={selectedProvider === 'ollama' ? 'Ollama 本地服务不需要 API Key（可留空）' : `请输入 ${currentProvider?.name || '提供商'} API Key`}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 pr-10"
                />
                {selectedProvider !== 'ollama' && (
                  <button
                    type="button"
                    onClick={() => toggleApiKeyVisibility(selectedProvider)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700"
                    title={showApiKeys[selectedProvider] ? '隐藏 API Key' : '显示 API Key'}
                  >
                    {showApiKeys[selectedProvider] ? (
                      <EyeOff className="w-5 h-5" />
                    ) : (
                      <Eye className="w-5 h-5" />
                    )}
                  </button>
                )}
              </div>
              <p className="text-xs text-gray-500 mt-1">
                {selectedProvider === 'ollama' ? (
                  <>Ollama 是本地服务，不需要 API Key。确保 Ollama 服务正在运行（默认地址：<code className="bg-gray-100 px-1 rounded">http://127.0.0.1:11434</code>）</>
                ) : (
                  <>请前往对应提供商的官网获取 API Key</>
                )}
              </p>
            </div>

            {/* Base URL (可选) */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Base URL (可选)
              </label>
              <input
                type="text"
                value={currentConfig.baseUrl || ''}
                onChange={(e) => handleConfigChange('baseUrl', e.target.value)}
                placeholder={currentProvider?.base_url || ''}
                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
              <p className="text-xs text-gray-500 mt-1">
                默认值已自动填充，通常无需修改
              </p>
            </div>

            {/* 模型选择 - 多选 */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="block text-sm font-medium text-gray-700">
                  <Brain className="w-4 h-4 inline mr-1" />
                  选择模型（可多选）
                  {currentConfig.models && currentConfig.models.length > 0 && (
                    <span className="ml-2 text-xs text-green-600">
                      ✓ 已选择 {currentConfig.models.length} 个
                    </span>
                  )}
                </label>
                <button
                  onClick={loadModels}
                  disabled={loadingModels || (selectedProvider !== 'ollama' && !currentConfig.apiKey?.trim())}
                  className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 disabled:opacity-50 disabled:cursor-not-allowed px-2 py-1 rounded hover:bg-blue-50 transition-colors"
                  title={selectedProvider !== 'ollama' && !currentConfig.apiKey?.trim() ? '请先输入 API Key' : '刷新模型列表'}
                >
                  <RefreshCw className={`w-3 h-3 ${loadingModels ? 'animate-spin' : ''}`} />
                  {loadingModels ? '加载中...' : '刷新列表'}
                </button>
              </div>
              
              {loadingModels ? (
                <div className="flex items-center justify-center py-4 border border-gray-300 rounded-lg">
                  <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
                  <span className="ml-2 text-sm text-gray-600">正在加载模型列表...</span>
                </div>
              ) : availableModels.length > 0 ? (
                <div className="border border-gray-300 rounded-lg p-4 max-h-60 overflow-y-auto">
                  <div className="space-y-2">
                    {availableModels.map((model) => {
                      const isSelected = (currentConfig.models || []).includes(model.id)
                      return (
                        <label
                          key={model.id}
                          className={`flex items-center gap-3 p-2 rounded-lg cursor-pointer transition-colors ${
                            isSelected
                              ? 'bg-blue-50 border border-blue-200'
                              : 'hover:bg-gray-50 border border-transparent'
                          }`}
                          onClick={(e) => {
                            // 防止点击 label 时触发两次
                            e.preventDefault()
                            handleModelToggle(model.id)
                          }}
                        >
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={(e) => {
                              e.stopPropagation()
                              handleModelToggle(model.id)
                            }}
                            onClick={(e) => e.stopPropagation()}
                            className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500 cursor-pointer"
                          />
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium text-gray-900">{model.name}</div>
                            <div className="text-xs text-gray-500">{model.provider}</div>
                          </div>
                          {isSelected && (
                            <CheckCircle2 className="w-4 h-4 text-blue-600 shrink-0" />
                          )}
                        </label>
                      )
                    })}
                  </div>
                </div>
              ) : selectedProvider === 'ollama' ? (
                <div className="px-4 py-2.5 border border-blue-300 bg-blue-50 rounded-lg text-sm text-blue-800">
                  点击"刷新列表"或"测试连接"来加载模型列表
                </div>
              ) : currentConfig.apiKey ? (
                <div className="px-4 py-2.5 border border-yellow-300 bg-yellow-50 rounded-lg text-sm text-yellow-800">
                  点击"测试连接"或"刷新列表"来加载模型列表
                </div>
              ) : (
                <div className="px-4 py-2.5 border border-gray-300 bg-gray-50 rounded-lg text-sm text-gray-600">
                  请输入 API Key 后自动加载模型列表
                </div>
              )}
              <p className="text-xs text-gray-500 mt-1">
                可以多选模型，然后在顶部"选择当前使用的模型"中选择要使用的模型
              </p>
            </div>

            {/* 操作按钮 */}
            <div className="flex gap-3 pt-4 border-t border-gray-200">
              <button
                onClick={testConnection}
                disabled={selectedProvider !== 'ollama' && !currentConfig.apiKey?.trim()}
                className="flex-1 px-4 py-2.5 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <CheckCircle2 className="w-4 h-4" />
                测试连接
              </button>
              <button
                onClick={handleSave}
                disabled={saving || !currentConfig.models || currentConfig.models.length === 0}
                className="flex-1 px-4 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Save className="w-4 h-4" />
                {saving ? '保存中...' : '保存配置'}
              </button>
            </div>
          </div>
        </div>

        {/* 使用提示 */}
        <div className="mt-6 bg-blue-50 border border-blue-200 rounded-xl p-4">
          <h3 className="text-sm font-semibold text-blue-900 mb-2">💡 使用提示</h3>
          <ul className="text-sm text-blue-800 space-y-1">
            <li>• API Key 会保存在浏览器本地，不会上传到服务器</li>
            <li>• 配置保存后，可以在首页查看任务时使用已配置的模型</li>
            <li>• 建议先测试连接，确保 API Key 有效并自动加载模型列表</li>
            <li>• 不同模型的费用和效果不同，请根据需求选择</li>
            <li>• 支持多个厂商同时配置，可以随时切换使用</li>
            <li>• 已配置的提供商会显示绿色标记</li>
          </ul>
        </div>
      </div>
    </div>
  )
}
