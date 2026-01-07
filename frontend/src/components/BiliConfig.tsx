import React, { useState, useEffect } from 'react'
import { getBiliConfig, updateBiliConfig, BiliConfig } from '../services/biliApi'

const BiliConfigPanel: React.FC = () => {
    const [config, setConfig] = useState<BiliConfig>({
        video_quality: 80,
        download_path: 'uploads',
        download_interval: 2,
        headless: false,
    })
    const [loading, setLoading] = useState(false)
    const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

    useEffect(() => {
        loadConfig()
    }, [])

    const loadConfig = async () => {
        try {
            const response = await getBiliConfig()
            if (response.success) {
                setConfig(response.data)
            }
        } catch (error) {
            console.error('加载配置失败:', error)
        }
    }

    const handleSave = async () => {
        setLoading(true)
        setMessage(null)
        try {
            const response = await updateBiliConfig(config)
            if (response.success) {
                setMessage({ type: 'success', text: '配置保存成功!' })
                setTimeout(() => setMessage(null), 3000)
            }
        } catch (error: any) {
            setMessage({ type: 'error', text: error.response?.data?.detail || '保存失败' })
        } finally {
            setLoading(false)
        }
    }

    const qualityOptions = [
        { value: 16, label: '360p' },
        { value: 32, label: '480p' },
        { value: 64, label: '720p' },
        { value: 80, label: '1080p' },
        { value: 112, label: '1080p 高码率' },
        { value: 116, label: '1080p 60帧' },
        { value: 120, label: '4K' },
    ]

    return (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
            <h2 className="text-2xl font-bold mb-6 text-gray-900 dark:text-white">下载配置</h2>

            <div className="space-y-6">
                {/* 视频清晰度 */}
                <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        视频清晰度
                    </label>
                    <select
                        value={config.video_quality}
                        onChange={(e) => setConfig({ ...config, video_quality: Number(e.target.value) })}
                        className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg 
                     bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                     focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    >
                        {qualityOptions.map((option) => (
                            <option key={option.value} value={option.value}>
                                {option.label}
                            </option>
                        ))}
                    </select>
                    <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                        高清晰度可能需要 B站大会员权限
                    </p>
                </div>

                {/* 保存路径 */}
                <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        保存路径
                    </label>
                    <input
                        type="text"
                        value={config.download_path}
                        onChange={(e) => setConfig({ ...config, download_path: e.target.value })}
                        className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg 
                     bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                     focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        placeholder="uploads"
                    />
                    <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                        视频将保存到此目录
                    </p>
                </div>

                {/* 下载间隔 */}
                <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        下载间隔 (秒)
                    </label>
                    <input
                        type="number"
                        min="1"
                        max="60"
                        value={config.download_interval}
                        onChange={(e) => setConfig({ ...config, download_interval: Number(e.target.value) })}
                        className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg 
                     bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                     focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                    <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                        两个视频之间的等待时间
                    </p>
                </div>

                {/* 无头模式 */}
                <div className="flex items-center">
                    <input
                        type="checkbox"
                        id="headless"
                        checked={config.headless}
                        onChange={(e) => setConfig({ ...config, headless: e.target.checked })}
                        className="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded 
                     focus:ring-blue-500 dark:focus:ring-blue-600 
                     dark:ring-offset-gray-800 focus:ring-2 
                     dark:bg-gray-700 dark:border-gray-600"
                    />
                    <label htmlFor="headless" className="ml-2 text-sm font-medium text-gray-700 dark:text-gray-300">
                        无头模式 (后台运行,不显示浏览器窗口)
                    </label>
                </div>

                {/* 保存按钮 */}
                <button
                    onClick={handleSave}
                    disabled={loading}
                    className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold 
                   py-3 px-6 rounded-lg transition duration-200
                   disabled:bg-gray-400 disabled:cursor-not-allowed"
                >
                    {loading ? '保存中...' : '保存配置'}
                </button>

                {/* 消息提示 */}
                {message && (
                    <div
                        className={`p-4 rounded-lg ${message.type === 'success'
                                ? 'bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200'
                                : 'bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200'
                            }`}
                    >
                        {message.text}
                    </div>
                )}
            </div>
        </div>
    )
}

export default BiliConfigPanel
