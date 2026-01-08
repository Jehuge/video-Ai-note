import React, { useState, useEffect } from 'react'
import { Check, Loader2 } from 'lucide-react'
import { getBiliConfig, updateBiliConfig, BiliConfig } from '../services/biliApi'
import toast from 'react-hot-toast'

interface BiliConfigPanelProps {
    compact?: boolean
}

const BiliConfigPanel: React.FC<BiliConfigPanelProps> = ({ compact = false }) => {
    const [config, setConfig] = useState<BiliConfig>({
        video_quality: 80,
        download_path: 'uploads',
        download_interval: 2,
        headless: false,
    })
    const [loading, setLoading] = useState(false)
    const [saved, setSaved] = useState(false)

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
        try {
            const response = await updateBiliConfig(config)
            if (response.success) {
                setSaved(true)
                toast.success('配置已保存')
                setTimeout(() => setSaved(false), 2000)
            }
        } catch (error: any) {
            toast.error(error.response?.data?.detail || '保存失败')
        } finally {
            setLoading(false)
        }
    }

    const qualityOptions = [
        { value: 16, label: '360p' },
        { value: 32, label: '480p' },
        { value: 64, label: '720p' },
        { value: 80, label: '1080p' },
        { value: 112, label: '1080p+' },
        { value: 120, label: '4K' },
    ]

    return (
        <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <div>
                    <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                        清晰度
                    </label>
                    <select
                        value={config.video_quality}
                        onChange={(e) => setConfig({ ...config, video_quality: Number(e.target.value) })}
                        className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg 
                         bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    >
                        {qualityOptions.map((opt) => (
                            <option key={opt.value} value={opt.value}>{opt.label}</option>
                        ))}
                    </select>
                </div>

                <div>
                    <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                        下载间隔 (秒)
                    </label>
                    <input
                        type="number"
                        min="1"
                        max="60"
                        value={config.download_interval}
                        onChange={(e) => setConfig({ ...config, download_interval: Number(e.target.value) })}
                        className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg 
                         bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    />
                </div>

                <div className="md:col-span-2">
                    <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                        保存路径
                    </label>
                    <input
                        type="text"
                        value={config.download_path}
                        onChange={(e) => setConfig({ ...config, download_path: e.target.value })}
                        className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg 
                         bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                        placeholder="uploads"
                    />
                </div>
            </div>

            <div className="flex items-center justify-between">
                <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 cursor-pointer">
                    <input
                        type="checkbox"
                        checked={config.headless}
                        onChange={(e) => setConfig({ ...config, headless: e.target.checked })}
                        className="w-4 h-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
                    />
                    后台静默下载
                </label>

                <button
                    onClick={handleSave}
                    disabled={loading}
                    className={`px-4 py-1.5 text-sm font-medium rounded-lg transition flex items-center gap-2
                     ${saved
                            ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
                            : 'bg-blue-600 hover:bg-blue-700 text-white'
                        } disabled:opacity-50`}
                >
                    {loading ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                    ) : saved ? (
                        <Check className="w-3 h-3" />
                    ) : null}
                    {saved ? '已保存' : '保存配置'}
                </button>
            </div>
        </div>
    )
}

export default BiliConfigPanel
