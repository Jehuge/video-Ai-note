import { useEffect, useState } from 'react'
import { ScrollArea } from './ui/ScrollArea'

interface Segment {
  start: number
  end: number
  text: string
}

interface TranscriptViewerProps {
  transcript?: {
    language?: string
    full_text?: string
    segments?: Segment[]
  }
}

export default function TranscriptViewer({ transcript }: TranscriptViewerProps) {
  const [activeSegment, setActiveSegment] = useState<number | null>(null)

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  if (!transcript?.segments?.length) {
    return (
      <div className="flex h-full items-center justify-center text-gray-400">
        暂无转写内容
      </div>
    )
  }

  return (
    <div className="flex h-full w-full flex-col rounded-md border bg-white shadow-sm overflow-hidden">
      <div className="p-4 border-b flex-shrink-0">
        <h2 className="text-lg font-medium">转写结果</h2>
        {transcript.language && (
          <p className="text-xs text-gray-500 mt-1">检测语言: {transcript.language}</p>
        )}
      </div>
      
      <div className="px-4 py-2 border-b grid grid-cols-[80px_1fr] gap-2 text-xs font-medium text-gray-500 flex-shrink-0">
        <div>时间</div>
        <div>内容</div>
      </div>
      
      <ScrollArea className="flex-1 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 300px)' }}>
        <div className="p-4 space-y-1">
          {transcript.segments.map((segment, index) => (
            <div
              key={index}
              className={`group grid grid-cols-[80px_1fr] gap-2 rounded-md p-2 transition-colors hover:bg-gray-50 ${
                activeSegment === index ? 'bg-gray-100' : ''
              }`}
              onClick={() => setActiveSegment(index)}
            >
              <div className="flex items-center gap-1 text-xs text-gray-500">
                <span>{formatTime(segment.start)}</span>
              </div>
              <div className="text-sm leading-relaxed text-gray-700">
                {segment.text}
              </div>
            </div>
          ))}
        </div>
      </ScrollArea>

      {transcript.segments.length > 0 && (
        <div className="px-4 py-3 border-t flex justify-between text-xs text-gray-500 flex-shrink-0">
          <span>共 {transcript.segments.length} 条片段</span>
          <span>
            总时长:{' '}
            {formatTime(
              transcript.segments[transcript.segments.length - 1]?.end || 0
            )}
          </span>
        </div>
      )}
    </div>
  )
}

