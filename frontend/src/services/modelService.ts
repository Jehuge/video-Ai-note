import { getModelList } from './api'

export interface InstanceConfig {
  id: string
  name?: string
  apiKey?: string
  baseUrl?: string
  models?: string[]
  modelCapabilities?: Record<string, any>
}

export type ProviderConfig = {
  // 新格式：使用 instances 数组
  instances?: InstanceConfig[]
  // 兼容旧格式：直接在 provider 根下保存 apiKey/baseUrl/models
  apiKey?: string
  baseUrl?: string
  model?: string
  models?: string[]
  modelCapabilities?: Record<string, any>
  [key: string]: any
}

export type ModelConfigs = Record<string, ProviderConfig>

// 读取本地配置（不做迁移）
export function loadModelConfigs(): ModelConfigs {
  try {
    const raw = localStorage.getItem('modelConfigs')
    if (!raw) return {}
    return JSON.parse(raw || '{}')
  } catch (e) {
    console.error('读取模型配置失败:', e)
    return {}
  }
}

export function saveModelConfigs(configs: ModelConfigs) {
  try {
    localStorage.setItem('modelConfigs', JSON.stringify(configs))
  } catch (e) {
    console.error('保存模型配置失败:', e)
  }
}

// 将旧格式（provider.apiKey / provider.baseUrl / provider.models 等）转换为新格式（provider.instances）但不写回 localStorage
export function convertLegacyConfigs(rawConfigs?: any): ModelConfigs {
  const configs = rawConfigs && typeof rawConfigs === 'object' ? { ...rawConfigs } : loadModelConfigs()

  Object.entries(configs).forEach(([providerId, cfg]) => {
    if (!cfg || typeof cfg !== 'object') return

    // 如果已经是新格式，跳过
    if (Array.isArray((cfg as any).instances)) return

    // 如果存在旧格式的关键字段，转换为 instances（仅返回转换结果，不写回）
    const legacyCfg = cfg as any
    if (legacyCfg.apiKey || legacyCfg.baseUrl || legacyCfg.models || legacyCfg.model) {
      const instances: InstanceConfig[] = [
        {
          id: 'default',
          name: '默认配置',
          apiKey: (legacyCfg.apiKey as string) || '',
          baseUrl: (legacyCfg.baseUrl as string) || '',
          models: (legacyCfg.models as string[]) || (legacyCfg.model ? [legacyCfg.model as string] : []),
          modelCapabilities: legacyCfg.modelCapabilities || {},
        },
      ]

      configs[providerId] = {
        ...cfg,
        instances,
      }
    }
  })

  return configs
}

// 判断给定 baseUrl 是否为本地/私有网络地址
function isLocalBaseUrl(baseUrl?: string | null): boolean {
  if (!baseUrl) return false
  try {
    const u = new URL(baseUrl.trim())
    const host = u.hostname
    if (host === 'localhost' || host === '127.0.0.1') return true
    // 私有 IP 段 10.*, 192.168.*, 172.16-31.*
    if (/^10\.\d+\.\d+\.\d+$/.test(host)) return true
    if (/^192\.168\.\d+\.\d+$/.test(host)) return true
    if (/^172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+$/.test(host)) return true
    return false
  } catch (e) {
    return false
  }
}

// 判断是否需要 API Key：如果 provider 是 ollama 或 baseUrl 是本地/私有地址，则不需要
export function needsApiKey(providerId: string, baseUrl?: string | null): boolean {
  if (!providerId) return true
  if (providerId === 'ollama') return false
  if (isLocalBaseUrl(baseUrl)) return false
  return true
}

// 从所有已保存的配置中列出可用模型（会调用后端 /models/list 接口）
export async function listModelsFromConfigs(): Promise<
  Array<{
    id: string
    name: string
    provider: string
    model: string
    instanceId?: string
    supportsVision?: boolean
  }>
> {
  // 1. 加载并标准化配置（强制转换为 instances 格式）
  const rawConfigs = loadModelConfigs()
  const configs = convertLegacyConfigs(rawConfigs)

  const results: Array<{
    id: string
    name: string
    provider: string
    model: string
    instanceId?: string
    supportsVision?: boolean
  }> = []

  for (const [providerId, cfg] of Object.entries(configs)) {
    const providerConfig = cfg as ProviderConfig

    // 经过 convertLegacyConfigs 处理后，应该都有 instances
    if (providerConfig.instances && Array.isArray(providerConfig.instances)) {
      for (const instance of providerConfig.instances) {
        const apiKey = (instance.apiKey || '').trim()
        const baseUrl = (instance.baseUrl || '').trim()

        // 如果需要 apiKey 且未提供，则跳过
        if (needsApiKey(providerId, baseUrl) && !apiKey) {
          continue
        }

        try {
          const resp = await getModelList({
            provider: providerId,
            api_key: apiKey,
            base_url: baseUrl,
          })

          if (resp?.data?.code === 200) {
            let models = resp.data.data || []

            // 严格过滤：只显示用户显式选中的模型
            // 如果 instance.models 是数组（哪怕为空），就严格按照它来过滤
            // 这意味着如果用户什么都没选，下拉框里就什么都不显示，而不是显示服务端返回的所有模型
            if (instance.models && Array.isArray(instance.models)) {
              models = models.filter((m: any) => instance.models!.includes(m.id))
            }

            models.forEach((m: any) => {
              results.push({
                id: `${providerId}-${instance.id}-${m.id}`,
                name: `${m.name} (${m.id})`,
                provider: providerId,
                model: m.id,
                instanceId: instance.id,
                supportsVision: m.supportsVision || m.capabilities?.supportsVision || false,
              })
            })
          }
        } catch (e) {
          console.error(`获取 ${providerId}/${instance.id} 模型失败:`, e)
        }
      }
    }
  }

  return results
}

