import axios from 'axios'

// 使用相对路径，通过 Vite 代理访问后端
// 开发环境：通过 vite.config.ts 中的 proxy 配置代理到 http://localhost:8483
// 生产环境：可以设置 VITE_API_BASE_URL 环境变量
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000, // 增加超时时间，因为文件上传和转写可能需要较长时间
})

// 上传视频文件
export const uploadVideo = async (
  file: File,
  screenshot: boolean = false,
  modelConfig: {
    provider: string
    api_key: string
    base_url?: string
    model: string
  } | null = null,
  onProgress?: (progress: number) => void
) => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('screenshot', screenshot.toString())
  
  // 如果提供了模型配置，添加到请求中
  if (modelConfig) {
    formData.append('model_config', JSON.stringify(modelConfig))
  }
  
  const response = await api.post('/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    timeout: 300000, // 5分钟超时，适合大文件上传
    onUploadProgress: (progressEvent) => {
      if (progressEvent.total && onProgress) {
        const percentCompleted = Math.round(
          (progressEvent.loaded * 100) / progressEvent.total
        )
        onProgress(percentCompleted)
      }
    },
  })
  
  return response
}

// 获取任务状态
export const getTaskStatus = async (taskId: string) => {
  return await api.get(`/task/${taskId}`)
}

// 获取任务列表
export const getTasks = async (limit: number = 50) => {
  return await api.get(`/tasks?limit=${limit}`)
}

// 确认步骤
export const confirmStep = async (taskId: string, step: string) => {
  return await api.post(`/task/${taskId}/confirm_step`, { step })
}

// 重新生成笔记
export const regenerateNote = async (taskId: string) => {
  // 获取当前选择的模型配置
  const selectedModelId = localStorage.getItem('selectedModel')
  const modelConfigs = localStorage.getItem('modelConfigs')
  
  let modelConfig = null
  if (selectedModelId && modelConfigs) {
    try {
      const configs = JSON.parse(modelConfigs)
      // 支持两种 id 格式：provider-model 或 provider-instance-model（model 本身可能包含 -）
      const parts = selectedModelId.split('-')
      if (parts.length >= 2) {
        const provider = parts[0]
        let instanceId: string | null = null
        let modelId = ''
        if (parts.length >= 3) {
          instanceId = parts[1]
          modelId = parts.slice(2).join('-')
        } else {
          modelId = parts.slice(1).join('-')
        }

        const providerConfig = configs[provider]
        if (providerConfig) {
          let apiKey = ''
          let baseUrl = ''
          // 如果存在 instanceId，优先使用 instance 的 apiKey / baseUrl
          if (instanceId && providerConfig.instances && Array.isArray(providerConfig.instances)) {
            const ins = providerConfig.instances.find((x: any) => x.id === instanceId)
            if (ins) {
              apiKey = ins.apiKey || ins.api_key || ''
              baseUrl = ins.baseUrl || ins.base_url || ''
            }
          }

          // fallback 到 provider 顶层字段
          apiKey = apiKey || providerConfig.apiKey || providerConfig.api_key || ''
          baseUrl = baseUrl || providerConfig.baseUrl || providerConfig.base_url || ''

          modelConfig = {
            provider,
            api_key: apiKey,
            base_url: baseUrl,
            model: modelId,
          }
          console.log('重新生成时使用的模型配置:', modelConfig)
        }
      }
    } catch (e) {
      console.error('解析模型配置失败:', e)
    }
  }
  
  // 将模型配置作为请求体传递（使用驼峰命名）
  return await api.post(`/task/${taskId}/regenerate`, {
    modelConfig: modelConfig
  })
}

// 获取模型列表
export const getModelList = async (config: {
  provider: string
  api_key: string
  base_url?: string
}) => {
  return await api.post('/models/list', config)
}

// 测试模型连接
export const testModelConnection = async (config: {
  provider: string
  api_key: string
  base_url?: string
}) => {
  return await api.post('/models/test', config)
}

// 获取提供商列表
export const getProviders = async () => {
  return await api.get('/providers')
}

// 删除任务
export const deleteTask = async (taskId: string) => {
  return await api.delete(`/task/${taskId}`)
}

// 导出 PDF（可复制文本）
export const exportPDF = async (taskId: string) => {
  const response = await api.get(`/task/${taskId}/export_pdf`, {
    responseType: 'blob',
  })
  return response
}

