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
  onProgress?: (progress: number) => void
) => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('screenshot', screenshot.toString())
  
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
  return await api.post(`/task/${taskId}/regenerate`)
}

