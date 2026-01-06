import { useState, useEffect, useRef } from 'react'
import { Save, Eye, EyeOff, Key, Brain, CheckCircle2, RefreshCw, Loader2, Plus, Trash2, Edit2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { getModelList, testModelConnection, getProviders } from '../services/api'
import ModelSelectorPanel from './ModelSelectorPanel'
import ProviderIcon from './ProviderIcon'
import { v4 as uuidv4 } from 'uuid'

interface ProviderType {
  id: string
  name: string
  type: string
  logo: string
  default_base_url: string
}

interface ProviderInstance {
  id: string          // 唯一实例ID (UUID)
  name: string        // 用户自定义名称
  providerType: string // 提供商类型 (openai, gemini, ollama, etc.)
  apiKey: string
  baseUrl: string
  models: string[]    // 多选的模型列表
  isActive?: boolean  // 是否为当前选中的配置
}

// 旧版配置接口，用于迁移
interface OldConfig {
  provider: string
  apiKey: string
  baseUrl?: string
  model: string
  models: string[]
}

interface ModelItem {
  id: string
  name: string
  provider: string      // 实例ID
  providerType?: string // 类型
}

export default function ModelConfig() {
  const [providerTypes, setProviderTypes] = useState<ProviderType[]>([])
  const [instances, setInstances] = useState<ProviderInstance[]>([])
  const [selectedInstanceId, setSelectedInstanceId] = useState<string | null>(null)
  const [showApiKeys, setShowApiKeys] = useState<Record<string, boolean>>({})
  const [saving, setSaving] = useState(false)
  const [loadingModels, setLoadingModels] = useState(false)
  const [availableModels, setAvailableModels] = useState<ModelItem[]>([])

  // 防止重复加载
  const initializedRef = useRef(false)
  // 缓存
  const modelsCacheRef = useRef<Record<string, { models: ModelItem[], timestamp: number }>>({})

  // 加载提供商类型和初始化配置
  useEffect(() => {
    if (initializedRef.current) return
    initializedRef.current = true

    const init = async () => {
      try {
        // 1. 获取支持的提供商类型
        const response = await getProviders()
        let types: ProviderType[] = []
        if (response.data.code === 200) {
          types = response.data.data || []
          setProviderTypes(types)
        }

        // 2. 加载并迁移配置
        const savedConfigs = localStorage.getItem('modelConfigs')
        let initialInstances: ProviderInstance[] = []

        if (savedConfigs) {
          try {
            const parsed = JSON.parse(savedConfigs)

            // 检查是新版还是旧版配置
            // 新版是数组，旧版是对象
            if (Array.isArray(parsed)) {
              initialInstances = parsed
            } else {
              // 迁移旧版配置
              console.log('检测到旧版配置，正在迁移...')
              Object.keys(parsed).forEach(key => {
                const oldConfig = parsed[key] as OldConfig
                // 只迁移有内容的配置
                if (key === 'ollama' || oldConfig.apiKey) {
                  const typeDef = types.find(t => t.id === key)
                  initialInstances.push({
                    id: uuidv4(),
                    name: typeDef?.name || key, // 使用默认名称
                    providerType: key,
                    apiKey: oldConfig.apiKey || '',
                    baseUrl: oldConfig.baseUrl || typeDef?.default_base_url || '',
                    models: oldConfig.models || (oldConfig.model ? [oldConfig.model] : [])
                  })
                }
              })
              // 如果迁移后为空，至少添加一个 OpenAI 默认模版
              if (initialInstances.length === 0) {
                const openaiType = types.find(t => t.id === 'openai')
                if (openaiType) {
                  initialInstances.push({
                    id: uuidv4(),
                    name: 'OpenAI',
                    providerType: 'openai',
                    apiKey: '',
                    baseUrl: openaiType.default_base_url,
                    models: []
                  })
                }
              }
              // 保存迁移后的配置
              localStorage.setItem('modelConfigs', JSON.stringify(initialInstances))
              toast.success('配置已自动升级到新版本')
            }
          } catch (e) {
            console.error('加载配置失败:', e)
          }
        } else {
          // 首次使用，添加一个默认 OpenAI 配置
          const openaiType = types.find(t => t.id === 'openai') || {
            id: 'openai', name: 'OpenAI', type: 'built-in', logo: 'OpenAI', default_base_url: 'https://api.openai.com/v1'
          }
          initialInstances.push({
            id: uuidv4(),
            name: 'OpenAI',
            providerType: 'openai',
            apiKey: '',
            baseUrl: openaiType.default_base_url,
            models: []
          })
        }

        setInstances(initialInstances)
        if (initialInstances.length > 0) {
          setSelectedInstanceId(initialInstances[0].id)
        }

      } catch (error) {
        console.error('初始化失败:', error)
        toast.error('初始化配置失败')
      }
    }
    init()
  }, [])

  const currentInstance = instances.find(i => i.id === selectedInstanceId)
  const currentProviderType = providerTypes.find(t => t.id === currentInstance?.providerType)

  // 当切换实例时，尝试加载缓存的模型列表
  useEffect(() => {
    if (!currentInstance) {
      setAvailableModels([])
      return
    }

    // 生成缓存 key：类型+API Key+Base URL
    const cacheKey = `${currentInstance.providerType}-${currentInstance.apiKey}-${currentInstance.baseUrl}`
    const cached = modelsCacheRef.current[cacheKey]

    // 如果缓存存在且未过期（5分钟），使用缓存
    if (cached && Date.now() - cached.timestamp < 5 * 60 * 1000) {
      setAvailableModels(cached.models)
    } else {
      setAvailableModels([]) // 清空，等待手动刷新或重新加载
    }
  }, [selectedInstanceId]) // 仅当 ID 变化时切换

  const handleAddInstance = (typeId: string) => {
    const typeDef = providerTypes.find(t => t.id === typeId)
    if (!typeDef) return

    const newInstance: ProviderInstance = {
      id: uuidv4(),
      name: `${typeDef.name} ${instances.filter(i => i.providerType === typeId).length + 1}`,
      providerType: typeId,
      apiKey: '',
      baseUrl: typeDef.default_base_url || '',
      models: []
    }

    const newInstances = [...instances, newInstance]
    setInstances(newInstances)
    setSelectedInstanceId(newInstance.id)
    // 自动保存
    localStorage.setItem('modelConfigs', JSON.stringify(newInstances))
    toast.success(`已添加 ${typeDef.name} 配置`)
  }

  const handleDeleteInstance = (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    if (instances.length <= 1) {
      toast.error("至少保留一个配置")
      return
    }
    if (!confirm("确定要删除这个配置吗？")) return

    const newInstances = instances.filter(i => i.id !== id)
    setInstances(newInstances)
    localStorage.setItem('modelConfigs', JSON.stringify(newInstances))

    if (selectedInstanceId === id) {
      setSelectedInstanceId(newInstances[0].id)
    }
    toast.success("配置已删除")
  }

  const handleUpdateInstance = (field: keyof ProviderInstance, value: any) => {
    if (!selectedInstanceId) return

    setInstances(prev => prev.map(inst => {
      if (inst.id === selectedInstanceId) {
        return { ...inst, [field]: value }
      }
      return inst
    }))
  }

  const handleSave = async () => {
    if (!currentInstance) return
    setSaving(true)
    try {
      // 验证
      if (currentInstance.providerType !== 'ollama' && !currentInstance.apiKey.trim()) {
        toast.error("请输入 API Key")
        setSaving(false)
        return
      }
      if (currentInstance.models.length === 0) {
        toast.error("请至少选择一个模型")
        setSaving(false)
        return
      }

      // 保存到 localStorage (整体保存)
      localStorage.setItem('modelConfigs', JSON.stringify(instances))

      toast.success(`保存成功！已选择 ${currentInstance.models.length} 个模型`)

      // 刷新模型列表显示（如果需要）
      loadModels()
    } catch (e: any) {
      toast.error(e.message || "保存失败")
    } finally {
      setSaving(false)
    }
  }

  const loadModels = async () => {
    if (!currentInstance) return

    if (currentInstance.providerType !== 'ollama' && !currentInstance.apiKey.trim()) {
      toast.error("请先输入 API Key")
      return
    }

    setLoadingModels(true)
    try {
      const response = await getModelList({
        provider: currentInstance.id, // 传递实例 ID
        provider_type: currentInstance.providerType, // 传递类型
        api_key: currentInstance.apiKey,
        base_url: currentInstance.baseUrl
      })

      if (response.data.code === 200) {
        const models = response.data.data || []
        setAvailableModels(models)

        const cacheKey = `${currentInstance.providerType}-${currentInstance.apiKey}-${currentInstance.baseUrl}`
        modelsCacheRef.current[cacheKey] = {
          models,
          timestamp: Date.now()
        }
        toast.success(`获取到 ${models.length} 个模型`)
      } else {
        toast.error(response.data.msg || "获取模型列表失败")
      }
    } catch (e: any) {
      console.error(e)
      toast.error("获取模型列表失败: " + (e.response?.data?.msg || e.message))
    } finally {
      setLoadingModels(false)
    }
  }

  const testConnection = async () => {
    if (!currentInstance) return
    if (currentInstance.providerType !== 'ollama' && !currentInstance.apiKey.trim()) {
      toast.error("请先输入 API Key")
      return
    }

    toast.loading("测试连接...", { id: 'test-conn' })
    try {
      const response = await testModelConnection({
        provider: currentInstance.id,
        provider_type: currentInstance.providerType,
        api_key: currentInstance.apiKey,
        base_url: currentInstance.baseUrl
      })
      if (response.data.code === 200) {
        toast.success("连接成功", { id: 'test-conn' })
        setTimeout(loadModels, 500)
      } else {
        toast.error(response.data.msg || "连接失败", { id: 'test-conn' })
      }
    } catch (e: any) {
      toast.error("连接失败: " + (e.response?.data?.msg || e.message), { id: 'test-conn' })
    }
  }

  const handleModelToggle = (modelId: string) => {
    if (!currentInstance) return
    const currentModels = currentInstance.models || []
    const isSelected = currentModels.includes(modelId)

    const newModels = isSelected
      ? currentModels.filter(id => id !== modelId)
      : [...currentModels, modelId]

    handleUpdateInstance('models', newModels)
  }

  return (
    <div className="h-full overflow-y-auto p-6 bg-gray-50/50">
      <div className="max-w-6xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">模型配置</h1>
          <p className="text-gray-600">配置多个 AI 模型厂商实例，按需切换</p>
        </div>

        {/* 模型选择器 - 显示所有已配置的模型 */}
        <ModelSelectorPanel />

        <div className="flex flex-col lg:flex-row gap-6 mt-6">

          {/* 左侧：实例列表 */}
          <div className="w-full lg:w-1/3 flex flex-col gap-4">
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden flex flex-col h-[600px]">
              <div className="p-4 border-b border-gray-100 bg-gray-50 flex justify-between items-center">
                <h3 className="font-semibold text-gray-700">已配置厂商</h3>
                <div className="group relative">
                  <button className="p-1 hover:bg-gray-200 rounded-full transition-colors">
                    <Plus className="w-5 h-5 text-blue-600" />
                  </button>
                  {/* 添加菜单 */}
                  <div className="absolute right-0 top-8 w-48 bg-white rounded-lg shadow-xl border border-gray-100 z-10 hidden group-hover:block hover:block">
                    <div className="p-2 grid gap-1">
                      {providerTypes.map(t => (
                        <button
                          key={t.id}
                          onClick={() => handleAddInstance(t.id)}
                          className="flex items-center gap-2 px-3 py-2 text-sm text-gray-700 hover:bg-blue-50 rounded-md w-full text-left"
                        >
                          <ProviderIcon provider={t.id} className="w-4 h-4" />
                          {t.name}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex-1 overflow-y-auto p-3 space-y-2">
                {instances.map(inst => (
                  <div
                    key={inst.id}
                    onClick={() => setSelectedInstanceId(inst.id)}
                    className={`flex items-center justify-between p-3 rounded-lg border cursor-pointer transition-all ${selectedInstanceId === inst.id
                      ? 'bg-blue-50 border-blue-500 shadow-sm'
                      : 'bg-white border-gray-200 hover:border-gray-300'
                      }`}
                  >
                    <div className="flex items-center gap-3 overflow-hidden">
                      <div className="w-10 h-10 rounded-lg flex items-center justify-center bg-white border border-gray-100 shrink-0">
                        <ProviderIcon provider={inst.providerType} className="w-6 h-6" />
                      </div>
                      <div className="min-w-0">
                        <div className="font-medium text-gray-900 truncate">{inst.name}</div>
                        <div className="text-xs text-gray-500 truncate flex items-center gap-1">
                          {providerTypes.find(t => t.id === inst.providerType)?.name}
                          {inst.models.length > 0 && <span className="text-green-600">• {inst.models.length} 模型</span>}
                        </div>
                      </div>
                    </div>
                    {selectedInstanceId === inst.id && (
                      <button
                        onClick={(e) => handleDeleteInstance(e, inst.id)}
                        className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-md transition-colors"
                        title="删除此配置"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                ))}

                {instances.length === 0 && (
                  <div className="text-center py-10 text-gray-400 text-sm">
                    还没有配置，点击右上角 + 添加
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* 右侧：配置详情 */}
          <div className="w-full lg:w-2/3">
            {currentInstance ? (
              <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 h-full">
                <div className="flex items-center gap-4 mb-6 pb-4 border-b border-gray-100">
                  <div className="w-12 h-12 rounded-xl bg-gray-50 flex items-center justify-center border border-gray-200">
                    <ProviderIcon provider={currentInstance.providerType} className="w-8 h-8" />
                  </div>
                  <div>
                    <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
                      {currentInstance.name}
                      <Edit2 className="w-4 h-4 text-gray-400 cursor-pointer hover:text-blue-500" onClick={() => {
                        const newName = prompt("修改名称", currentInstance.name)
                        if (newName) handleUpdateInstance('name', newName)
                      }} />
                    </h2>
                    <p className="text-sm text-gray-500">
                      类型: {currentProviderType?.name || currentInstance.providerType}
                    </p>
                  </div>
                </div>

                <div className="space-y-6">
                  {/* API Key */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      <Key className="w-4 h-4 inline mr-1" />
                      API Key
                      {currentInstance.providerType !== 'ollama' && <span className="text-red-500 ml-1">*</span>}
                    </label>
                    <div className="relative">
                      <input
                        type={showApiKeys[currentInstance.id] ? 'text' : 'password'}
                        value={currentInstance.apiKey}
                        onChange={(e) => handleUpdateInstance('apiKey', e.target.value)}
                        placeholder={currentInstance.providerType === 'ollama' ? '可选' : `请输入 ${currentProviderType?.name || 'API'} Key`}
                        className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 pr-10 font-mono text-sm"
                      />
                      <button
                        type="button"
                        onClick={() => setShowApiKeys(prev => ({ ...prev, [currentInstance.id]: !prev[currentInstance.id] }))}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700"
                      >
                        {showApiKeys[currentInstance.id] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>

                  {/* Base URL */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      API Base URL
                    </label>
                    <input
                      type="text"
                      value={currentInstance.baseUrl}
                      onChange={(e) => handleUpdateInstance('baseUrl', e.target.value)}
                      placeholder={currentProviderType?.default_base_url}
                      className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-sm"
                    />
                  </div>

                  {/* 模型选择 */}
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <label className="block text-sm font-medium text-gray-700">
                        <Brain className="w-4 h-4 inline mr-1" />
                        可用模型
                        {currentInstance.models.length > 0 && <span className="ml-2 text-xs text-green-600 bg-green-50 px-2 py-0.5 rounded-full">已选 {currentInstance.models.length}</span>}
                      </label>
                      <button
                        onClick={loadModels}
                        disabled={loadingModels || (currentInstance.providerType !== 'ollama' && !currentInstance.apiKey)}
                        className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 disabled:opacity-50 px-3 py-1.5 rounded-md hover:bg-blue-50 transition-colors bg-white border border-blue-100"
                      >
                        <RefreshCw className={`w-3.5 h-3.5 ${loadingModels ? 'animate-spin' : ''}`} />
                        {loadingModels ? '加载中...' : '刷新模型列表'}
                      </button>
                    </div>

                    {availableModels.length > 0 ? (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-60 overflow-y-auto p-1">
                        {availableModels.map(model => {
                          const isSelected = currentInstance.models.includes(model.id)
                          return (
                            <label
                              key={model.id}
                              className={`flex items-center gap-2 p-2.5 rounded-lg border cursor-pointer transition-all ${isSelected
                                ? 'bg-blue-50 border-blue-300 ring-1 ring-blue-300/50'
                                : 'bg-white border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                                }`}
                            >
                              <input
                                type="checkbox"
                                className="w-4 h-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
                                checked={isSelected}
                                onChange={() => handleModelToggle(model.id)}
                              />
                              <span className="text-sm text-gray-700 truncate select-none" title={model.id}>{model.name}</span>
                            </label>
                          )
                        })}
                      </div>
                    ) : (
                      <div className="flex flex-col items-center justify-center py-8 border-2 border-dashed border-gray-200 rounded-xl bg-gray-50/50 text-gray-400 text-sm">
                        <Brain className="w-8 h-8 mb-2 opacity-50" />
                        {loadingModels ? '正在加载模型...' : '点击"刷新模型列表"加载可用模型'}
                      </div>
                    )}
                  </div>

                  {/* 操作栏 */}
                  <div className="pt-6 border-t border-gray-100 flex gap-4">
                    <button
                      onClick={testConnection}
                      className="flex-1 px-4 py-2.5 bg-white text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors flex items-center justify-center gap-2 font-medium"
                    >
                      测试连接
                    </button>
                    <button
                      onClick={handleSave}
                      disabled={saving}
                      className="flex-1 px-4 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center justify-center gap-2 font-medium disabled:opacity-70 shadow-sm shadow-blue-200"
                    >
                      {saving ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin" />
                          保存中...
                        </>
                      ) : (
                        <>
                          <Save className="w-4 h-4" />
                          保存配置
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-gray-400 bg-white rounded-xl border border-gray-200 border-dashed">
                <div className="bg-gray-50 p-4 rounded-full mb-4">
                  <ProviderIcon provider="openai" className="w-8 h-8 opacity-50" />
                </div>
                <p>请选择左侧配置或添加新配置</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
