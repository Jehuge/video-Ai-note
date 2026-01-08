import React from 'react'
import BiliConfig from '../components/BiliConfig'
import BiliVideoList from '../components/BiliVideoList'
import BiliDownloadControl from '../components/BiliDownloadControl'
import BiliHistoryPanel from '../components/BiliLogs'
import BiliRealtimeLogs from '../components/BiliRealtimeLogs'
import { useBiliWebSocket } from '../hooks/useBiliWebSocket'

const BiliDownload: React.FC = () => {
    const { isConnected, logs, progress, clearLogs } = useBiliWebSocket()

    return (
        <div className="h-full overflow-y-auto bg-gray-50 dark:bg-gray-900 p-6">
            <div className="max-w-7xl mx-auto pb-6">
                {/* 页面标题 */}
                <div className="mb-8">
                    <h1 className="text-4xl font-bold text-gray-900 dark:text-white mb-2">
                        B站视频下载
                    </h1>
                    <p className="text-gray-600 dark:text-gray-400">
                        批量下载B站视频,下载完成自动显示在列表中
                    </p>
                </div>

                {/* 主要布局 */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* 左侧列 */}
                    <div className="space-y-6">
                        <BiliConfig />
                        <BiliDownloadControl progress={progress} />
                    </div>

                    {/* 右侧列 */}
                    <div className="space-y-6">
                        <BiliVideoList />
                    </div>
                </div>

                {/* 实时日志 */}
                <div className="mt-6">
                    <BiliRealtimeLogs
                        logs={logs}
                        isConnected={isConnected}
                        onClear={clearLogs}
                    />
                </div>

                {/* 下载历史 */}
                <div className="mt-6">
                    <BiliHistoryPanel />
                </div>
            </div>
        </div>
    )
}

export default BiliDownload
