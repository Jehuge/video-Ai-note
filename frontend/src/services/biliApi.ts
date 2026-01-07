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
    status: 'pending' | 'downloaded' | 'failed'
    created_at?: string
}

export const getBiliVideos = async (): Promise<BiliVideo[]> => {
    const response = await api.get('/bili/videos')
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
    const response = await api.get('/bili/download/status')
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
    const response = await api.get(`/bili/history?limit=${limit}`)
    return response.data.data || []
}

// ==================== WebSocket ====================

export interface BiliLogMessage {
    type: 'log'
    timestamp: string
    level: 'info' | 'success' | 'warning' | 'error'
    message: string
}

export const createBiliWebSocket = (
    onMessage: (message: BiliLogMessage) => void,
    onError?: (error: Event) => void
) => {
    // 使用当前host,通过 Vite 代理到后端
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsHost = window.location.host // localhost:5173
    const wsUrl = `${wsProtocol}//${wsHost}/api/ws/bili/logs`

    console.log('正在连接 WebSocket:', wsUrl)
    const ws = new WebSocket(wsUrl)

    ws.onmessage = (event) => {
        try {
            const message: BiliLogMessage = JSON.parse(event.data)
            onMessage(message)
        } catch (e) {
            console.error('解析 WebSocket 消息失败:', e)
        }
    }

    ws.onerror = (error) => {
        console.error('WebSocket 错误:', error)
        if (onError) {
            onError(error)
        }
    }

    ws.onopen = () => {
        console.log('WebSocket 连接已建立')
        // 发送心跳
        const heartbeat = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send('ping')
            } else {
                clearInterval(heartbeat)
            }
        }, 30000)
    }

    ws.onclose = () => {
        console.log('WebSocket 连接已关闭')
    }

    return ws
}
