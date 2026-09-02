import { FileText, Mic } from 'lucide-react'
import { useState } from 'react'
import NoteStyleSettings from './NoteStyleSettings'
import TranscriberSettings from './TranscriberSettings'

type SettingsTab = 'note-styles' | 'transcriber'

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<SettingsTab>('note-styles')

  return (
    <div className="h-full flex flex-col overflow-hidden bg-slate-50">
      <div className="shrink-0 border-b border-slate-200 bg-white px-6">
        <div className="max-w-6xl mx-auto flex gap-1 py-2">
          <button
            onClick={() => setActiveTab('note-styles')}
            className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'note-styles'
                ? 'border-blue-600 text-blue-700'
                : 'border-transparent text-slate-600 hover:text-slate-900'
            }`}
          >
            <FileText className="w-4 h-4" />
            笔记模式
          </button>
          <button
            onClick={() => setActiveTab('transcriber')}
            className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'transcriber'
                ? 'border-blue-600 text-blue-700'
                : 'border-transparent text-slate-600 hover:text-slate-900'
            }`}
          >
            <Mic className="w-4 h-4" />
            语音识别
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-hidden">
        {activeTab === 'note-styles' ? <NoteStyleSettings /> : <TranscriberSettings />}
      </div>
    </div>
  )
}
