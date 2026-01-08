import React, { useState } from 'react'
import { Settings, Download, RefreshCw, Trash2, Link as LinkIcon, Play, Square, Loader2, CheckCircle2 } from 'lucide-react'
import { useBiliWebSocket } from '../hooks/useBiliWebSocket'
import { addBiliVideo, startDownload, stopDownload, getBiliVideos, BiliVideo } from '../services/biliApi'
import BiliHistoryPanel from '../components/BiliLogs'
import BiliRealtimeLogs from '../components/BiliRealtimeLogs'
import BiliConfigPanel from '../components/BiliConfigPanel'
import toast from 'react-hot-toast'

// 简化版视频卡片组件
const VideoQueueItem = ({ video, onDelete }: { video: BiliVideo, onDelete: (id: number) => void }) => (
    <div className="flex items-center justify-between p-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-100 dark:border-gray-700 shadow-sm hover:shadow-md transition-shadow">
        <div className="flex items-center gap-3 overflow-hidden">
            <div className={`w-2 h-2 rounded-full shrink-0 ${video.status === 'running' ? 'bg-blue-500 animate-pulse' :
                video.status === 'downloaded' ? 'bg-green-500' :
                    video.status === 'failed' ? 'bg-red-500' : 'bg-gray-300'
                }`} />
            <div className="min-w-0">
                <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{video.title || video.bv_id}</p>
                <p className="text-xs text-gray-400 truncate">{video.url}</p>
            </div>
        </div>
        <div className="flex items-center gap-2">
            <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-700 text-gray-500">
                {video.status === 'pending' ? '等待中' :
                    video.status === 'running' ? '下载中' :
                        video.status === 'downloaded' ? '已完成' : '失败'}
            </span>
            {video.status !== 'running' && (
                <button
                    onClick={() => onDelete(video.id)}
                    className="p-1 hover:bg-red-50 text-gray-400 hover:text-red-500 rounded transition"
                >
                    <Trash2 className="w-4 h-4" />
                </button>
            )}
        </div>
    </div>
)

const BiliDownload: React.FC = () => {
    const { isConnected, logs, progress, clearLogs } = useBiliWebSocket()
    const [inputUrl, setInputUrl] = useState('')
    const [videos, setVideos] = useState<BiliVideo[]>([])
    const [showConfig, setShowConfig] = useState(false)
    const [isLoading, setIsLoading] = useState(false)

    // 加载视频列表
    const loadVideos = async () => {
        try {
            const data = await getBiliVideos()
            setVideos(data)
        } catch (error) {
            console.error('加载视频失败', error)
        }
    }

    // 初始加载及定时刷新
    React.useEffect(() => {
        loadVideos()
        const timer = setInterval(loadVideos, 3000)
        return () => clearInterval(timer)
    }, [])

    const handleAddVideo = async () => {
        if (!inputUrl.trim()) return
        setIsLoading(true)
        try {
            await addBiliVideo(inputUrl)
            setInputUrl('')
            toast.success('已添加到队列')
            loadVideos()
        } catch (error: any) {
            toast.error(error.response?.data?.detail || '添加失败')
        } finally {
            setIsLoading(false)
        }
    }

    const handleStartDownload = async () => {
        try {
            await startDownload()
            toast.success('开始下载任务')
        } catch (error) {
            toast.error('启动失败')
        }
    }

    const handleStopDownload = async () => {
        try {
            await stopDownload()
            toast.error('已停止下载')
        } catch (error) {
            toast.error('停止失败')
        }
    }

    const pendingVideos = videos.filter(v => v.status === 'pending' || v.status === 'running')
    // const completedVideosCount = videos.filter(v => v.status === 'downloaded').length
    const isRunning = progress.status === 'running'
    const progressPercent = progress.total > 0 ? Math.round((progress.completed / progress.total) * 100) : 0

    return (
        <div className="h-full flex overflow-hidden bg-gray-50 dark:bg-gray-900">
            {/* 左侧侧边栏 - 历史记录 (模仿 TaskList) */}
            <aside className="w-80 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex flex-col z-10">
                <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
                    <h2 className="font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                        <CheckCircle2 className="w-5 h-5 text-green-500" />
                        已完成
                    </h2>
                    <span className="text-xs text-gray-500 bg-gray-100 dark:bg-gray-700 px-2 py-0.5 rounded-full">
                        历史记录
                    </span>
                </div>
                <div className="flex-1 overflow-y-auto p-2">
                    <BiliHistoryPanel />
                </div>
            </aside>

            {/* 右侧主区域 */}
            <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
                {/* 顶部操作区 (模仿 UploadZone) */}
                <div className="p-8 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 shadow-sm shrink-0">
                    <div className="max-w-3xl mx-auto w-full">
                        <div className="flex items-center justify-between mb-6">
                            <div>
                                <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
                                    <Download className="w-8 h-8 text-blue-600" />
                                    B站视频下载
                                </h1>
                                <p className="text-gray-500 dark:text-gray-400 mt-1">
                                    输入视频链接或 BV 号，支持批量排队下载
                                </p>
                            </div>
                            <button
                                onClick={() => setShowConfig(!showConfig)}
                                className={`p-2 rounded-lg transition-colors ${showConfig
                                    ? 'bg-blue-100 text-blue-600 dark:bg-blue-900 dark:text-blue-300'
                                    : 'hover:bg-gray-100 text-gray-500 dark:hover:bg-gray-700'
                                    }`}
                                title="下载设置"
                            >
                                <Settings className="w-6 h-6" />
                            </button>
                        </div>

                        {/* 配置面板 - 可折叠 */}
                        {showConfig && (
                            <div className="mb-6 bg-gray-50 dark:bg-gray-700/50 rounded-xl p-4 border border-gray-200 dark:border-gray-600 animate-in slide-in-from-top-2">
                                <BiliConfigPanel compact />
                            </div>
                        )}

                        {/* 输入框区域 */}
                        <div className="relative group">
                            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                                <LinkIcon className="h-5 w-5 text-gray-400 group-focus-within:text-blue-500 transition-colors" />
                            </div>
                            <input
                                type="text"
                                className="block w-full pl-11 pr-32 py-4 bg-gray-50 dark:bg-gray-900 border-2 border-gray-200 dark:border-gray-700 rounded-2xl 
                                         text-gray-900 dark:text-white placeholder-gray-400 
                                         focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10 focus:bg-white dark:focus:bg-gray-800
                                          transition-all duration-200 text-lg"
                                placeholder="粘贴 Bilibili 视频链接 (https://b23.tv/...)"
                                value={inputUrl}
                                onChange={(e) => setInputUrl(e.target.value)}
                                onKeyDown={(e) => e.key === 'Enter' && handleAddVideo()}
                            />
                            <div className="absolute inset-y-2 right-2 flex gap-2">
                                <button
                                    onClick={handleAddVideo}
                                    disabled={isLoading || !inputUrl}
                                    className="px-4 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-medium shadow-lg shadow-blue-500/20 
                                             disabled:opacity-50 disabled:shadow-none disabled:cursor-not-allowed transition-all flex items-center gap-2"
                                >
                                    {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : '添加'}
                                </button>
                            </div>
                        </div>

                        {/* 状态控制栏 */}
                        {pendingVideos.length > 0 && (
                            <div className="mt-6 flex items-center gap-4 bg-blue-50 dark:bg-blue-900/20 p-4 rounded-xl border border-blue-100 dark:border-blue-800">
                                <div className="flex-1">
                                    <div className="flex items-center gap-2 mb-1">
                                        <span className="font-semibold text-blue-900 dark:text-blue-100">
                                            {isRunning ? '正在下载...' : '准备就绪'}
                                        </span>
                                        <span className="text-sm text-blue-600 dark:text-blue-300">
                                            ({progress.completed}/{progress.total} 已完成)
                                        </span>
                                    </div>
                                    {isRunning && (
                                        <div className="h-2 bg-blue-200 dark:bg-blue-800 rounded-full overflow-hidden">
                                            <div
                                                className="h-full bg-blue-600 rounded-full transition-all duration-500 ease-out"
                                                style={{ width: `${progressPercent}%` }}
                                            />
                                        </div>
                                    )}
                                </div>
                                <div>
                                    {!isRunning ? (
                                        <button
                                            onClick={handleStartDownload}
                                            className="flex items-center gap-2 px-6 py-2.5 bg-green-500 hover:bg-green-600 text-white rounded-lg font-semibold shadow-lg shadow-green-500/20 transition-all active:scale-95"
                                        >
                                            <Play className="w-4 h-4" fill="currentColor" />
                                            开始全部
                                        </button>
                                    ) : (
                                        <button
                                            onClick={handleStopDownload}
                                            className="flex items-center gap-2 px-6 py-2.5 bg-red-500 hover:bg-red-600 text-white rounded-lg font-semibold shadow-lg shadow-red-500/20 transition-all active:scale-95"
                                        >
                                            <Square className="w-4 h-4" fill="currentColor" />
                                            停止
                                        </button>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* 下方内容区：两栏 (左：队列，右：日志) */}
                <div className="flex-1 overflow-hidden">
                    <div className="h-full flex flex-col md:flex-row max-w-7xl mx-auto">
                        {/* 待下载/下载中队列 */}
                        <div className="flex-1 overflow-y-auto p-6 border-r border-gray-100 dark:border-gray-800">
                            <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-4 flex items-center justify-between">
                                下载队列
                                {pendingVideos.length > 0 && <span className="bg-gray-100 px-2 py-0.5 rounded-full text-xs">{pendingVideos.length}</span>}
                            </h3>
                            {pendingVideos.length === 0 ? (
                                <div className="text-center py-20 text-gray-400 dark:text-gray-600 border-2 border-dashed border-gray-100 dark:border-gray-800 rounded-2xl">
                                    <div className="mx-auto w-16 h-16 bg-gray-50 dark:bg-gray-800 rounded-full flex items-center justify-center mb-4">
                                        <LinkIcon className="w-8 h-8 text-gray-300" />
                                    </div>
                                    <p>暂无任务</p>
                                    <p className="text-sm mt-1">在上方添加视频链接开始下载</p>
                                </div>
                            ) : (
                                <div className="space-y-3">
                                    {pendingVideos.map(video => (
                                        <VideoQueueItem
                                            key={video.id}
                                            video={video}
                                            onDelete={(id) => {
                                                // 实际项目中这里应调用 deleteBiliVideo API
                                                console.log('delete', id)
                                            }}
                                        />
                                    ))}
                                </div>
                            )}
                        </div>

                        {/* 实时日志 */}
                        <div className="w-full md:w-96 flex flex-col bg-gray-900 dark:bg-black border-l border-gray-800">
                            <div className="p-3 border-b border-gray-800 flex items-center justify-between bg-gray-900/50 backdrop-blur">
                                <span className="text-xs font-mono text-gray-400 flex items-center gap-2">
                                    <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}></span>
                                    CONSOLE_OUTPUT
                                </span>
                                <button onClick={clearLogs} className="text-xs text-gray-600 hover:text-gray-300 uppercase">Clear</button>
                            </div>
                            <div className="flex-1 overflow-hidden relative">
                                <div className="absolute inset-0">
                                    <BiliRealtimeLogs logs={logs} isConnected={isConnected} onClear={clearLogs} />
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </main>
        </div >
    )
}

export default BiliDownload
