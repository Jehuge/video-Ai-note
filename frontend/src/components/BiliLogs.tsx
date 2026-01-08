import React, { useState, useEffect } from 'react'
import { FileVideo, RefreshCw, PlayCircle } from 'lucide-react'
import { getBiliHistory, BiliDownloadHistory } from '../services/biliApi'
import ContentPreviewModal from './ContentPreviewModal'

const BiliHistoryPanel: React.FC = () => {
    const [history, setHistory] = useState<BiliDownloadHistory[]>([])
    const [loading, setLoading] = useState(false)
    const [previewVideo, setPreviewVideo] = useState<{ url: string, title: string } | null>(null)

    useEffect(() => {
        loadHistory()
    }, [])

    const loadHistory = async () => {
        setLoading(true)
        try {
            const data = await getBiliHistory(50)
            setHistory(data)
        } catch (error) {
            console.error('加载下载历史失败:', error)
        } finally {
            setLoading(false)
        }
    }

    const formatFileSize = (bytes: number) => {
        if (bytes < 1024) return bytes + ' B'
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
        return (bytes / 1024 / 1024).toFixed(1) + ' MB'
    }

    const handlePlay = (item: BiliDownloadHistory) => {
        // 假设文件保存在后端配置的 uploads 目录中
        // 提取文件名
        const filename = item.file_path.split(/[/\\]/).pop()
        if (filename) {
            // 构造访问 URL
            // 注意：这里假设后端已经将 uploads 目录映射到了 /api/uploads
            const videoUrl = `/api/uploads/${encodeURIComponent(filename)}`
            setPreviewVideo({
                url: videoUrl,
                title: item.title || item.bv_id
            })
        }
    }

    return (
        <>
            <div className="space-y-1">
                <div className="px-2 py-1 flex justify-end">
                    <button
                        onClick={loadHistory}
                        disabled={loading}
                        className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition rounded-md hover:bg-gray-100 dark:hover:bg-gray-800"
                        title="刷新列表"
                    >
                        <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
                    </button>
                </div>

                {history.length === 0 ? (
                    <div className="text-center py-12 text-gray-400">
                        <p className="text-xs">暂无历史记录</p>
                    </div>
                ) : (
                    history.map((item) => (
                        <div
                            key={item.id}
                            onClick={() => handlePlay(item)}
                            className="group flex flex-col p-3 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700/50 cursor-pointer transition-colors border border-transparent hover:border-gray-200 dark:hover:border-gray-700 relative"
                        >
                            <div className="flex items-start gap-3">
                                <div className="w-8 h-8 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center text-blue-600 dark:text-blue-400 shrink-0 group-hover:bg-blue-200 dark:group-hover:bg-blue-800 transition-colors">
                                    <FileVideo className="w-4 h-4 group-hover:hidden" />
                                    <PlayCircle className="w-5 h-5 hidden group-hover:block" />
                                </div>
                                <div className="min-w-0 flex-1">
                                    <h4 className="text-sm font-medium text-gray-900 dark:text-gray-100 leading-tight line-clamp-2 mb-1 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                                        {item.title || item.bv_id}
                                    </h4>
                                    <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                                        <span className="font-mono">{formatFileSize(item.file_size)}</span>
                                        <span>•</span>
                                        <span>{new Date(item.downloaded_at).toLocaleDateString()}</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    ))
                )}
            </div>

            {previewVideo && (
                <ContentPreviewModal
                    type="video"
                    content={previewVideo.url}
                    title={previewVideo.title}
                    onClose={() => setPreviewVideo(null)}
                />
            )}
        </>
    )
}

export default BiliHistoryPanel
