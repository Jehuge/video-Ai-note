import React, { useState } from 'react'
import { Play, Square, Loader2 } from 'lucide-react'
import { startDownload, stopDownload } from '../services/biliApi'
import { DownloadProgress } from '../hooks/useBiliWebSocket'
import toast from 'react-hot-toast'

interface BiliDownloadControlProps {
    progress: DownloadProgress
}

const BiliDownloadControl: React.FC<BiliDownloadControlProps> = ({ progress }) => {
    const [loading, setLoading] = useState(false)

    const handleStart = async () => {
        setLoading(true)
        try {
            const response = await startDownload()
            toast.success(response.message)
        } catch (error: any) {
            toast.error(error.response?.data?.detail || '启动下载失败')
        } finally {
            setLoading(false)
        }
    }

    const handleStop = async () => {
        setLoading(true)
        try {
            const response = await stopDownload()
            toast.success(response.message)
        } catch (error: any) {
            toast.error(error.response?.data?.detail || '停止下载失败')
        } finally {
            setLoading(false)
        }
    }

    const isRunning = progress.status === 'running'
    const progressPercent = progress.total > 0 ? (progress.completed / progress.total) * 100 : 0

    return (
        <div className="space-y-4">
            {/* 进度区域 */}
            {isRunning && (
                <div className="space-y-3">
                    {/* 当前视频 */}
                    {progress.current_video && (
                        <div className="flex items-center gap-2 text-sm">
                            <span className="text-gray-500 dark:text-gray-400">当前:</span>
                            <span className="font-mono text-gray-900 dark:text-white">
                                {progress.current_video}
                            </span>
                        </div>
                    )}

                    {/* 进度条 */}
                    <div>
                        <div className="flex items-center justify-between text-sm mb-1">
                            <span className="text-gray-600 dark:text-gray-400">
                                下载进度
                            </span>
                            <span className="font-medium text-gray-900 dark:text-white">
                                {progress.completed} / {progress.total}
                            </span>
                        </div>
                        <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5 overflow-hidden">
                            <div
                                className="bg-gradient-to-r from-blue-500 to-blue-600 h-2.5 rounded-full transition-all duration-500"
                                style={{ width: `${progressPercent}%` }}
                            />
                        </div>
                    </div>
                </div>
            )}

            {/* 控制按钮 */}
            <div className="flex items-center gap-3">
                {!isRunning ? (
                    <button
                        onClick={handleStart}
                        disabled={loading}
                        className="flex-1 bg-gradient-to-r from-green-500 to-green-600 hover:from-green-600 hover:to-green-700 
                     text-white font-semibold py-3 px-6 rounded-xl transition 
                     flex items-center justify-center gap-2 shadow-lg shadow-green-500/25
                     disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none"
                    >
                        {loading ? (
                            <Loader2 className="w-5 h-5 animate-spin" />
                        ) : (
                            <Play className="w-5 h-5" />
                        )}
                        {loading ? '启动中...' : '开始下载'}
                    </button>
                ) : (
                    <button
                        onClick={handleStop}
                        disabled={loading}
                        className="flex-1 bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 
                     text-white font-semibold py-3 px-6 rounded-xl transition
                     flex items-center justify-center gap-2 shadow-lg shadow-red-500/25
                     disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none"
                    >
                        {loading ? (
                            <Loader2 className="w-5 h-5 animate-spin" />
                        ) : (
                            <Square className="w-5 h-5" />
                        )}
                        {loading ? '停止中...' : '停止下载'}
                    </button>
                )}

                {/* 状态指示 */}
                <div className={`px-3 py-2 rounded-lg text-sm font-medium ${isRunning
                        ? 'bg-green-100 text-green-700 dark:bg-green-900/50 dark:text-green-300'
                        : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
                    }`}>
                    {isRunning ? '运行中' : '空闲'}
                </div>
            </div>
        </div>
    )
}

export default BiliDownloadControl
