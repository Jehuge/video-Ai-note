import React, { useState, useEffect } from 'react'
import { Trash2, X, Video } from 'lucide-react'
import { getBiliVideos, addBiliVideo, deleteBiliVideo, clearBiliVideos, BiliVideo } from '../services/biliApi'
import toast from 'react-hot-toast'

const BiliVideoList: React.FC = () => {
    const [videos, setVideos] = useState<BiliVideo[]>([])
    const [inputUrl, setInputUrl] = useState('')
    const [loading, setLoading] = useState(false)

    useEffect(() => {
        loadVideos()
    }, [])

    const loadVideos = async () => {
        try {
            const data = await getBiliVideos()
            setVideos(data)
        } catch (error) {
            console.error('加载视频列表失败:', error)
        }
    }

    const handleAdd = async () => {
        if (!inputUrl.trim()) {
            toast.error('请输入视频URL或BV号')
            return
        }

        setLoading(true)
        try {
            await addBiliVideo(inputUrl)
            toast.success('视频添加成功')
            setInputUrl('')
            await loadVideos()
        } catch (error: any) {
            toast.error(error.response?.data?.detail || '添加失败')
        } finally {
            setLoading(false)
        }
    }

    const handleDelete = async (id: number) => {
        try {
            await deleteBiliVideo(id)
            toast.success('视频已删除')
            await loadVideos()
        } catch (error) {
            toast.error('删除失败')
        }
    }

    const handleClear = async () => {
        if (!confirm('确定要清空所有视频吗?')) return

        try {
            await clearBiliVideos()
            toast.success('列表已清空')
            await loadVideos()
        } catch (error) {
            toast.error('清空失败')
        }
    }

    const getStatusBadge = (status: string) => {
        const badges = {
            pending: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
            downloaded: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
            failed: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
        }
        const labels = {
            pending: '待下载',
            downloaded: '已完成',
            failed: '失败',
        }
        return (
            <span className={`px-2 py-1 text-xs font-medium rounded-full ${badges[status as keyof typeof badges] || badges.pending}`}>
                {labels[status as keyof typeof labels] || status}
            </span>
        )
    }

    return (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
            <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white">视频列表</h2>
                {videos.length > 0 && (
                    <button
                        onClick={handleClear}
                        className="text-sm text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 
                     flex items-center gap-1"
                    >
                        <Trash2 className="w-4 h-4" />
                        清空列表
                    </button>
                )}
            </div>

            {/* 添加视频表单 */}
            <div className="flex gap-2 mb-6">
                <input
                    type="text"
                    value={inputUrl}
                    onChange={(e) => setInputUrl(e.target.value)}
                    onKeyPress={(e) => { if (e.key === 'Enter') handleAdd() }}
                    placeholder="输入B站视频URL或BV号 (如: BV1xx411c7mD)"
                    className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg 
                   bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                   focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <button
                    onClick={handleAdd}
                    disabled={loading}
                    className="bg-blue-600 hover:bg-blue-700 text-white font-semibold 
                   px-6 py-2 rounded-lg transition duration-200
                   disabled:bg-gray-400 disabled:cursor-not-allowed"
                >
                    {loading ? '添加中...' : '添加'}
                </button>
            </div>

            {/* 视频列表 */}
            {videos.length === 0 ? (
                <div className="text-center py-12 text-gray-500 dark:text-gray-400">
                    <Video className="w-12 h-12 mx-auto mb-3 opacity-50" />
                    <p>暂无视频,请添加视频到列表</p>
                </div>
            ) : (
                <div className="space-y-2 max-h-96 overflow-y-auto">
                    {videos.map((video) => (
                        <div
                            key={video.id}
                            className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-700 
                       rounded-lg hover:bg-gray-100 dark:hover:bg-gray-600 transition"
                        >
                            <div className="flex-1 min-w-0 mr-4">
                                <div className="flex items-center gap-2 mb-1">
                                    <span className="font-mono text-sm font-medium text-gray-900 dark:text-white">
                                        {video.bv_id}
                                    </span>
                                    {getStatusBadge(video.status)}
                                </div>
                                {video.title && (
                                    <p className="text-sm text-gray-600 dark:text-gray-300 truncate">
                                        {video.title}
                                    </p>
                                )}
                                {video.url && (
                                    <p className="text-xs text-gray-400 dark:text-gray-500 truncate">
                                        {video.url}
                                    </p>
                                )}
                            </div>
                            <button
                                onClick={() => handleDelete(video.id)}
                                className="flex-shrink-0 p-2 text-red-600 hover:text-red-700 
                         dark:text-red-400 dark:hover:text-red-300 
                         hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition"
                                title="删除"
                            >
                                <X className="w-4 h-4" />
                            </button>
                        </div>
                    ))}
                </div>
            )}

            <div className="mt-4 text-sm text-gray-500 dark:text-gray-400">
                共 {videos.length} 个视频
                {videos.filter(v => v.status === 'pending').length > 0 &&
                    ` • ${videos.filter(v => v.status === 'pending').length} 个待下载`}
            </div>
        </div>
    )
}

export default BiliVideoList
