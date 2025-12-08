import UploadForm from './UploadForm'

export default function UploadPage() {
  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="max-w-4xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">上传视频/音频</h1>
          <p className="text-gray-600">上传视频或音频文件，系统将自动处理并生成笔记</p>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <UploadForm />
        </div>

        {/* 使用提示 */}
        <div className="mt-6 bg-blue-50 border border-blue-200 rounded-xl p-4">
          <h3 className="text-sm font-semibold text-blue-900 mb-2">💡 使用提示</h3>
          <ul className="text-sm text-blue-800 space-y-1">
            <li>• 支持 MP4, AVI, MOV, MKV, MP3, WAV 等格式</li>
            <li>• 文件大小限制：最大 500MB</li>
            <li>• 上传后系统会自动处理：提取音频 → 转写文字 → 生成笔记</li>
            <li>• 处理完成后可以在首页查看任务列表和笔记预览</li>
            <li>• 可以选择是否生成截图标记（仅视频文件）</li>
          </ul>
        </div>
      </div>
    </div>
  )
}

