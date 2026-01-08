import { useEffect, useRef, useState, useCallback } from 'react'

export interface BiliLogMessage {
    type: 'log' | 'progress' | 'status' | 'connected'
    timestamp: string
    level?: 'info' | 'success' | 'warning' | 'error'
    message?: string
    status?: string
    data?: {
        status: string
        current_video: string | null
        total: number
        completed: number
        progress: number
    }
}

export interface DownloadProgress {
    status: 'idle' | 'running' | 'paused' | 'stopped'
    current_video: string | null
    total: number
    completed: number
    progress: number
}

interface UseBiliWebSocketReturn {
    isConnected: boolean
    logs: BiliLogMessage[]
    progress: DownloadProgress
    clearLogs: () => void
}

const WS_RECONNECT_DELAY = 3000
const WS_HEARTBEAT_INTERVAL = 30000

export function useBiliWebSocket(): UseBiliWebSocketReturn {
    const [isConnected, setIsConnected] = useState(false)
    const [logs, setLogs] = useState<BiliLogMessage[]>([])
    const [progress, setProgress] = useState<DownloadProgress>({
        status: 'idle',
        current_video: null,
        total: 0,
        completed: 0,
        progress: 0,
    })

    const wsRef = useRef<WebSocket | null>(null)
    const heartbeatRef = useRef<NodeJS.Timeout | null>(null)
    const reconnectRef = useRef<NodeJS.Timeout | null>(null)

    const clearLogs = useCallback(() => {
        setLogs([])
    }, [])

    const connect = useCallback(() => {
        // 清理现有连接
        if (wsRef.current) {
            wsRef.current.close()
        }

        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
        const wsHost = window.location.host
        const wsUrl = `${wsProtocol}//${wsHost}/api/ws/bili/logs`

        console.log('[WS] 正在连接:', wsUrl)
        const ws = new WebSocket(wsUrl)
        wsRef.current = ws

        ws.onopen = () => {
            console.log('[WS] 连接成功')
            setIsConnected(true)

            // 启动心跳
            heartbeatRef.current = setInterval(() => {
                if (ws.readyState === WebSocket.OPEN) {
                    ws.send('ping')
                }
            }, WS_HEARTBEAT_INTERVAL)
        }

        ws.onmessage = (event) => {
            // 忽略 pong 响应
            if (event.data === 'pong') return

            try {
                const message: BiliLogMessage = JSON.parse(event.data)

                switch (message.type) {
                    case 'log':
                        setLogs((prev) => [...prev.slice(-99), message]) // 保留最近100条
                        break
                    case 'progress':
                        if (message.data) {
                            setProgress({
                                status: message.data.status as DownloadProgress['status'],
                                current_video: message.data.current_video,
                                total: message.data.total,
                                completed: message.data.completed,
                                progress: message.data.progress,
                            })
                        }
                        break
                    case 'status':
                        if (message.status) {
                            setProgress((prev) => ({
                                ...prev,
                                status: message.status as DownloadProgress['status'],
                            }))
                        }
                        // 状态变更也作为日志
                        if (message.message) {
                            setLogs((prev) => [...prev.slice(-99), {
                                type: 'log',
                                timestamp: message.timestamp,
                                level: 'info',
                                message: message.message,
                            }])
                        }
                        break
                    case 'connected':
                        console.log('[WS]', message.message)
                        break
                }
            } catch (e) {
                console.error('[WS] 解析消息失败:', e)
            }
        }

        ws.onerror = (error) => {
            console.error('[WS] 错误:', error)
        }

        ws.onclose = () => {
            console.log('[WS] 连接关闭')
            setIsConnected(false)

            // 清理心跳
            if (heartbeatRef.current) {
                clearInterval(heartbeatRef.current)
                heartbeatRef.current = null
            }

            // 尝试重连
            reconnectRef.current = setTimeout(() => {
                console.log('[WS] 尝试重连...')
                connect()
            }, WS_RECONNECT_DELAY)
        }
    }, [])

    useEffect(() => {
        connect()

        return () => {
            // 清理
            if (heartbeatRef.current) {
                clearInterval(heartbeatRef.current)
            }
            if (reconnectRef.current) {
                clearTimeout(reconnectRef.current)
            }
            if (wsRef.current) {
                wsRef.current.close()
            }
        }
    }, [connect])

    return { isConnected, logs, progress, clearLogs }
}
