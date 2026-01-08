import React, { useRef, useEffect } from 'react'
import { BiliLogMessage } from '../hooks/useBiliWebSocket'

interface BiliRealtimeLogsProps {
    logs: BiliLogMessage[]
    isConnected: boolean
    onClear: () => void
}

const BiliRealtimeLogs: React.FC<BiliRealtimeLogsProps> = ({ logs }) => {
    const logsEndRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [logs])

    const getLevelColor = (level?: string) => {
        const colors: Record<string, string> = {
            success: 'text-emerald-400',
            warning: 'text-amber-400',
            error: 'text-red-400',
            info: 'text-blue-300',
        }
        return colors[level || 'info'] || 'text-gray-400'
    }

    return (
        <div className="h-full overflow-y-auto p-4 font-mono text-xs leading-5 bg-transparent scrollbar-thin scrollbar-thumb-gray-700">
            {logs.length === 0 ? (
                <div className="text-gray-700 opacity-50 mt-10 text-center select-none font-sans">
                    Waiting for logs...
                </div>
            ) : (
                <>
                    {logs.map((log, index) => (
                        <div key={index} className="mb-1 break-all">
                            <span className="text-gray-600 mr-2 select-none">
                                {new Date(log.timestamp).toLocaleTimeString([], { hour12: false })}
                            </span>
                            <span className={getLevelColor(log.level)}>
                                {log.message}
                            </span>
                        </div>
                    ))}
                    <div ref={logsEndRef} />
                </>
            )}
        </div>
    )
}

export default BiliRealtimeLogs
