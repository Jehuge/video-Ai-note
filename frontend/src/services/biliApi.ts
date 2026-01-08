import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

const api = axios.create({
    baseURL: API_BASE_URL,
    timeout: 120000, // B站下载可能需要较长时间
})

// ==================== 配置管理 ====================

export interface BiliConfig {
    video_quality: number
    download_path: string
    download_interval: number
    headless: boolean
}

export const getBiliConfig = async () => {
    const response = await api.get('/bili/config')
    return response.data
}

export const updateBiliConfig = async (config: Partial<BiliConfig>) => {
    const response = await api.post('/bili/config', config)
    return response.data
}

// ==================== 视频管理 ====================

export interface BiliVideo {
    id: number
    bv_id: string
    url: string
    title?: string
    status: 'pending' | 'running' | 'downloaded' | 'failed'
    created_at?: string
}

export const getBiliVideos = async (): Promise<BiliVideo[]> => {
    const response = await api.get(`/bili/videos?_t=${Date.now()}`)
    return response.data.data || []
}

export const addBiliVideo = async (url: string) => {
    const response = await api.post('/bili/videos', { url })
    return response.data
}

export const deleteBiliVideo = async (videoId: number) => {
    const response = await api.delete(`/bili/videos/${videoId}`)
    return response.data
}

export const clearBiliVideos = async () => {
    const response = await api.delete('/bili/videos')
    return response.data
}

// ==================== 下载控制 ====================

export interface DownloadStatus {
    status: 'idle' | 'running' | 'paused' | 'stopped'
    task_id: string | null
    current_video: string | null
    total: number
    completed: number
    progress: number
}

export const startDownload = async (videoIds?: number[]) => {
    const response = await api.post('/bili/download/start', {
        video_ids: videoIds,
    })
    return response.data
}

export const stopDownload = async () => {
    const response = await api.post('/bili/download/stop')
    return response.data
}

export const getDownloadStatus = async (): Promise<DownloadStatus> => {
    const response = await api.get(`/bili/download/status?_t=${Date.now()}`)
    return response.data.data
}

// ==================== 下载历史 ====================

export interface BiliDownloadHistory {
    id: number
    bv_id: string
    title: string
    file_path: string
    file_size: number
    quality: number
    downloaded_at: string
}

export const getBiliHistory = async (limit: number = 50): Promise<BiliDownloadHistory[]> => {
    const response = await api.get(`/bili/history?limit=${limit}&_t=${Date.now()}`)
    return response.data.data || []
}
