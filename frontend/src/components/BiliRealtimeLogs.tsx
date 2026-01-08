import React, { useRef, useEffect } from 'react'
import { Terminal, Trash2, Wifi, WifiOff } from 'lucide-react'
import { BiliLogMessage } from '../hooks/useBiliWebSocket'

interface BiliRealtimeLogsProps {
    logs: BiliLogMessage[]
    isConnected: boolean
    onClear: () => void
}

const BiliRealtimeLogs: React.FC<BiliRealtimeLogsProps> = ({ logs, isConnected, onClear }) => {
    const logsEndRef = useRef<HTMLDivElement>(null)

    // 自动滚动到底部
    useEffect(() => {
        logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [logs])

    const getLevelColor = (level?: string) => {
        switch (level) {
            case 'success':
                return 'text-green-400'
            case 'warning':
                return 'text-yellow-400'
            case 'error':
                return 'text-red-400'
            default:
                return 'text-gray-300'
        }
    }

    const getLevelBadge = (level?: string) => {
        switch (level) {
            case 'success':
                return 'bg-green-500/20 text-green-400'
            case 'warning':
                return 'bg-yellow-500/20 text-yellow-400'
            case 'error':
                return 'bg-red-500/20 text-red-400'
            default:
                return 'bg-blue-500/20 text-blue-400'
        }
    }

    const formatTime = (timestamp: string) => {
        const date = new Date(timestamp)
        return date.toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
        })
    }

    return (
        <div className="bg-gray-900 rounded-lg shadow-lg overflow-hidden">
            {/* 标题栏 */}
            <div className="flex items-center justify-between px-4 py-3 bg-gray-800 border-b border-gray-700">
                <div className="flex items-center gap-2">
                    <Terminal className="w-5 h-5 text-green-400" />
                    <h3 className="font-semibold text-white">实时日志</h3>
                    {isConnected ? (
                        <span className="flex items-center gap-1 px-2 py-0.5 text-xs bg-green-500/20 text-green-400 rounded-full">
                            <Wifi className="w-3 h-3" />
                            已连接
                        </span>
                    ) : (
                        <span className="flex items-center gap-1 px-2 py-0.5 text-xs bg-red-500/20 text-red-400 rounded-full">
                            <WifiOff className="w-3 h-3" />
                            断开
                        </span>
                    )}
                </div>
                <button
                    onClick={onClear}
                    className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded transition"
                    title="清空日志"
                >
                    <Trash2 className="w-4 h-4" />
                </button>
            </div>

            {/* 日志内容 */}
            <div className="h-64 overflow-y-auto p-4 font-mono text-sm">
                {logs.length === 0 ? (
                    <div className="text-gray-500 text-center py-8">
                        等待日志输出...
                    </div>
                ) : (
                    <div className="space-y-1">
                        {logs.map((log, index) => (
                            <div key={index} className="flex items-start gap-2">
                                <span className="text-gray-500 text-xs flex-shrink-0">
                                    {formatTime(log.timestamp)}
                                </span>
                                <span className={`px-1.5 py-0.5 text-xs rounded uppercase flex-shrink-0 ${getLevelBadge(log.level)}`}>
                                    {log.level || 'info'}
                                </span>
                                <span className={getLevelColor(log.level)}>
                                    {log.message}
                                </span>
                            </div>
                        ))}
                        <div ref={logsEndRef} />
                    </div>
                )}
            </div>
        </div>
    )
}

export default BiliRealtimeLogs
