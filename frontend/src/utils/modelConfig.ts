export interface ProviderInstance {
  id: string
  name: string
  providerType: string
  apiKey: string
  baseUrl: string
  models: string[]
}

export interface SelectedModelConfig {
  provider: string
  provider_type: string
  api_key: string
  base_url?: string
  model: string
  note_style?: string
}

export interface SelectedModelDisplay {
  modelName: string
  providerType: string
  providerName: string
}

interface LegacyProviderConfig {
  apiKey?: string
  baseUrl?: string
  model?: string
  models?: string[]
}

export function loadProviderInstances(): ProviderInstance[] {
  const savedConfigs = localStorage.getItem('modelConfigs')
  if (!savedConfigs) return []

  try {
    const parsed = JSON.parse(savedConfigs)
    if (Array.isArray(parsed)) {
      return parsed.filter((item) => item && item.id && item.providerType)
    }

    return Object.entries(parsed).map(([providerType, config]) => {
      const legacy = config as LegacyProviderConfig
      const models = legacy.models || (legacy.model ? [legacy.model] : [])
      return {
        id: providerType,
        name: providerType,
        providerType,
        apiKey: legacy.apiKey || '',
        baseUrl: legacy.baseUrl || '',
        models,
      }
    })
  } catch (error) {
    console.error('解析模型配置失败:', error)
    return []
  }
}

function splitSelectedModel(selectedModel: string) {
  if (selectedModel.includes(':')) {
    const separatorIndex = selectedModel.indexOf(':')
    return {
      providerId: selectedModel.substring(0, separatorIndex),
      modelId: selectedModel.substring(separatorIndex + 1),
      format: 'instance' as const,
    }
  }

  const separatorIndex = selectedModel.indexOf('-')
  if (separatorIndex > 0) {
    return {
      providerId: selectedModel.substring(0, separatorIndex),
      modelId: selectedModel.substring(separatorIndex + 1),
      format: 'legacy' as const,
    }
  }

  return null
}

export function getSelectedModelConfig(noteStyle: string = 'simple'): SelectedModelConfig | null {
  const selectedModel = localStorage.getItem('selectedModel')
  if (!selectedModel) return null

  const parsed = splitSelectedModel(selectedModel)
  if (!parsed || !parsed.modelId) return null

  const instances = loadProviderInstances()
  let instance = instances.find((item) => item.id === parsed.providerId)

  if (!instance && parsed.format === 'legacy') {
    instance = instances.find((item) =>
      item.providerType === parsed.providerId && item.models.includes(parsed.modelId)
    )
  }

  if (!instance) return null

  return {
    provider: instance.id,
    provider_type: instance.providerType,
    api_key: instance.apiKey || '',
    base_url: instance.baseUrl || '',
    model: parsed.modelId,
    note_style: noteStyle,
  }
}

export function getSelectedModelDisplay(): SelectedModelDisplay | null {
  const selectedModel = localStorage.getItem('selectedModel')
  if (!selectedModel) return null

  const parsed = splitSelectedModel(selectedModel)
  if (!parsed || !parsed.modelId) return null

  const instances = loadProviderInstances()
  let instance = instances.find((item) => item.id === parsed.providerId)

  if (!instance && parsed.format === 'legacy') {
    instance = instances.find((item) =>
      item.providerType === parsed.providerId && item.models.includes(parsed.modelId)
    )
  }

  const providerType = instance?.providerType || parsed.providerId
  let modelName = parsed.modelId
  if (modelName.startsWith(`${providerType}-`)) {
    modelName = modelName.substring(providerType.length + 1)
  }

  return {
    modelName,
    providerType,
    providerName: instance?.name || providerType,
  }
}
