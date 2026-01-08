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
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
            <h2 className="text-2xl font-bold mb-6 text-gray-900 dark:text-white">下载控制</h2>

            {/* 状态显示 */}
            <div className="mb-6 space-y-4">
                <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300">状态:</span>
                    <span className={`px-3 py-1 text-sm font-semibold rounded-full ${isRunning
                        ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                        : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
                        }`}>
                        {isRunning ? '下载中' : progress.status === 'stopped' ? '已停止' : '空闲'}
                    </span>
                </div>

                {isRunning && (
                    <>
                        {progress.current_video && (
                            <div>
                                <span className="text-sm font-medium text-gray-700 dark:text-gray-300 block mb-1">
                                    当前视频:
                                </span>
                                <span className="font-mono text-sm text-gray-900 dark:text-white">
                                    {progress.current_video}
                                </span>
                            </div>
                        )}

                        <div>
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                                    总体进度:
                                </span>
                                <span className="text-sm text-gray-600 dark:text-gray-400">
                                    {progress.completed} / {progress.total}
                                </span>
                            </div>
                            <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3 overflow-hidden">
                                <div
                                    className="bg-blue-600 h-3 rounded-full transition-all duration-500"
                                    style={{ width: `${progressPercent}%` }}
                                />
                            </div>
                            <div className="text-right text-xs text-gray-500 dark:text-gray-400 mt-1">
                                {progressPercent.toFixed(0)}%
                            </div>
                        </div>

                        {progress.progress > 0 && (
                            <div>
                                <div className="flex items-center justify-between mb-2">
                                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                                        当前视频进度:
                                    </span>
                                    <span className="text-sm text-gray-600 dark:text-gray-400">
                                        {progress.progress}%
                                    </span>
                                </div>
                                <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2 overflow-hidden">
                                    <div
                                        className="bg-green-500 h-2 rounded-full transition-all duration-300"
                                        style={{ width: `${progress.progress}%` }}
                                    />
                                </div>
                            </div>
                        )}
                    </>
                )}
            </div>

            {/* 控制按钮 */}
            <div className="flex gap-3">
                {!isRunning ? (
                    <button
                        onClick={handleStart}
                        disabled={loading}
                        className="flex-1 bg-green-600 hover:bg-green-700 text-white font-semibold 
                     py-3 px-6 rounded-lg transition duration-200 flex items-center justify-center gap-2
                     disabled:bg-gray-400 disabled:cursor-not-allowed"
                    >
                        {loading ? (
                            <>
                                <Loader2 className="w-5 h-5 animate-spin" />
                                启动中...
                            </>
                        ) : (
                            <>
                                <Play className="w-5 h-5" />
                                开始下载
                            </>
                        )}
                    </button>
                ) : (
                    <button
                        onClick={handleStop}
                        disabled={loading}
                        className="flex-1 bg-red-600 hover:bg-red-700 text-white font-semibold 
                     py-3 px-6 rounded-lg transition duration-200 flex items-center justify-center gap-2
                     disabled:bg-gray-400 disabled:cursor-not-allowed"
                    >
                        {loading ? (
                            <>
                                <Loader2 className="w-5 h-5 animate-spin" />
                                停止中...
                            </>
                        ) : (
                            <>
                                <Square className="w-5 h-5" />
                                停止下载
                            </>
                        )}
                    </button>
                )}
            </div>

            <p className="mt-4 text-sm text-gray-500 dark:text-gray-400">
                * 首次下载需要扫码登录B站账号
            </p>
        </div>
    )
}

export default BiliDownloadControl
