import React, { useState, useEffect } from 'react'
import { History, RefreshCw } from 'lucide-react'
import { getBiliHistory, BiliDownloadHistory } from '../services/biliApi'

const BiliHistoryPanel: React.FC = () => {
    const [history, setHistory] = useState<BiliDownloadHistory[]>([])
    const [loading, setLoading] = useState(false)

    useEffect(() => {
        loadHistory()
        // 每10秒自动刷新历史
        const interval = setInterval(loadHistory, 10000)
        return () => clearInterval(interval)
    }, [])

    const loadHistory = async () => {
        try {
            const data = await getBiliHistory(20)
            setHistory(data)
        } catch (error) {
            console.error('加载下载历史失败:', error)
        }
    }

    const handleRefresh = async () => {
        setLoading(true)
        await loadHistory()
        setLoading(false)
    }

    const formatFileSize = (bytes: number) => {
        if (bytes < 1024) return bytes + ' B'
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
        return (bytes / 1024 / 1024).toFixed(1) + ' MB'
    }

    const formatDate = (dateStr: string) => {
        const date = new Date(dateStr)
        return date.toLocaleString('zh-CN', {
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        })
    }

    return (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                    <History className="w-6 h-6 text-gray-700 dark:text-gray-300" />
                    <h2 className="text-2xl font-bold text-gray-900 dark:text-white">下载历史</h2>
                </div>
                <button
                    onClick={handleRefresh}
                    disabled={loading}
                    className="p-2 text-gray-600 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300 
                   hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition"
                    title="刷新"
                >
                    <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
                </button>
            </div>

            {history.length === 0 ? (
                <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                    <History className="w-12 h-12 mx-auto mb-3 opacity-50" />
                    <p>暂无下载记录</p>
                </div>
            ) : (
                <div className="space-y-2 max-h-80 overflow-y-auto">
                    {history.map((item) => (
                        <div
                            key={item.id}
                            className="p-3 bg-gray-50 dark:bg-gray-700 rounded-lg"
                        >
                            <div className="flex items-start justify-between">
                                <div className="flex-1 min-w-0">
                                    <p className="font-medium text-gray-900 dark:text-white truncate">
                                        {item.title || item.bv_id}
                                    </p>
                                    <div className="flex items-center gap-3 mt-1 text-xs text-gray-500 dark:text-gray-400">
                                        <span className="font-mono">{item.bv_id}</span>
                                        <span>•</span>
                                        <span>{formatFileSize(item.file_size)}</span>
                                        <span>•</span>
                                        <span>{formatDate(item.downloaded_at)}</span>
                                    </div>
                                </div>
                                <span className="ml-2 px-2 py-1 text-xs font-medium rounded bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200 flex-shrink-0">
                                    已完成
                                </span>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            <div className="mt-4 text-sm text-gray-500 dark:text-gray-400">
                共 {history.length} 条记录
            </div>
        </div>
    )
}

export default BiliHistoryPanel
