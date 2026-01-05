import { useState, useRef } from 'react'
import { UploadCloud, Loader2 } from 'lucide-react'
import { useTaskStore } from '../store/taskStore'
import { uploadVideo } from '../services/api'
import toast from 'react-hot-toast'
import FileConfirmDialog from './FileConfirmDialog'

interface UploadZoneProps {
    onUploadSuccess?: (taskId: string) => void
}

export default function UploadZone({ onUploadSuccess }: UploadZoneProps) {
    const { addTask } = useTaskStore()

    const [uploading, setUploading] = useState(false)
    const [uploadProgress, setUploadProgress] = useState(0)
    const [selectedFile, setSelectedFile] = useState<File | null>(null)
    const [showConfirm, setShowConfirm] = useState(false)
    const [isDragOver, setIsDragOver] = useState(false)
    const fileInputRef = useRef<HTMLInputElement>(null)

    const handleFile = (file: File) => {
        // 检查文件类型
        const fileExtension = file.name.split('.').pop()?.toLowerCase()
        const allowedExtensions = ['mp4', 'avi', 'mov', 'mkv', 'webm', 'mp3', 'wav', 'm4a', 'flv', 'wmv']
        const isAllowedExtension = fileExtension && allowedExtensions.includes(fileExtension)
        const isAllowedMime = file.type.startsWith('video/') || file.type.startsWith('audio/')

        if (!isAllowedExtension && !isAllowedMime) {
            toast.error('不支持的文件类型，请上传视频或音频文件')
            return
        }

        if (file.size > 500 * 1024 * 1024) {
            toast.error('文件大小不能超过 500MB')
            return
        }

        setSelectedFile(file)
        setShowConfirm(true)
    }

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (file) handleFile(file)
        e.target.value = ''
    }

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault()
        setIsDragOver(true)
    }

    const handleDragLeave = (e: React.DragEvent) => {
        e.preventDefault()
        setIsDragOver(false)
    }

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault()
        setIsDragOver(false)
        const file = e.dataTransfer.files[0]
        if (file) handleFile(file)
    }

    const handleConfirmUpload = async (screenshot: boolean) => {
        const noteStyle = 'simple'
        if (!selectedFile) return

        // 获取模型配置 logic
        const selectedModelId = localStorage.getItem('selectedModel')
        const modelConfigs = localStorage.getItem('modelConfigs')
        let modelConfig = null

        if (selectedModelId && modelConfigs) {
            try {
                const configs = JSON.parse(modelConfigs)
                const firstDashIndex = selectedModelId.indexOf('-')
                if (firstDashIndex > 0) {
                    const provider = selectedModelId.substring(0, firstDashIndex)
                    const modelId = selectedModelId.substring(firstDashIndex + 1)
                    const providerConfig = configs[provider]
                    if (providerConfig) {
                        modelConfig = {
                            provider,
                            api_key: providerConfig.apiKey || '',
                            base_url: providerConfig.baseUrl || '',
                            model: modelId,
                        }
                    }
                }
            } catch (e) {
                console.error('解析模型配置失败:', e)
            }
        }

        setShowConfirm(false)
        setUploading(true)
        setUploadProgress(0)

        try {
            const response = await uploadVideo(
                selectedFile,
                screenshot,
                modelConfig,
                noteStyle,
                (progress) => setUploadProgress(progress)
            )

            if (response.data.code === 200) {
                const { task_id, filename } = response.data.data
                addTask({
                    id: task_id,
                    filename,
                    status: 'pending',
                    markdown: '',
                    createdAt: new Date().toISOString()
                })

                toast.success('上传成功')
                if (onUploadSuccess) onUploadSuccess(task_id)
                setSelectedFile(null)
            } else {
                toast.error(response.data.msg || '上传失败')
            }
        } catch (error: any) {
            console.error('上传失败:', error)
            if (error.code === 'ECONNABORTED') {
                toast.error('上传超时，请检查网络连接或文件大小')
            } else {
                toast.error(error.response?.data?.msg || '上传失败，请稍后重试')
            }
        } finally {
            setUploading(false)
            setUploadProgress(0)
        }
    }

    const triggerFileUpload = () => {
        fileInputRef.current?.click()
    }

    return (
        <>
            <div
                onClick={triggerFileUpload}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={`
          relative group cursor-pointer overflow-hidden rounded-2xl border-2 border-dashed transition-all duration-300 ease-out
          ${isDragOver
                        ? 'border-blue-500 bg-blue-50/50 scale-[1.01] shadow-xl ring-4 ring-blue-500/10'
                        : 'border-slate-200 bg-white hover:border-blue-400 hover:bg-slate-50 hover:shadow-lg hover:-translate-y-0.5'
                    }
          ${uploading ? 'pointer-events-none opacity-80' : ''}
        `}
            >
                <div className="p-5 flex items-center gap-5">
                    <div className={`
            flex-shrink-0 w-12 h-12 rounded-full flex items-center justify-center transition-all duration-300 transform group-hover:scale-110
            ${isDragOver ? 'bg-blue-100 rotate-12' : 'bg-slate-50 group-hover:bg-blue-50 text-slate-400 group-hover:text-blue-500'}
          `}>
                        {uploading ? (
                            <Loader2 className="w-6 h-6 animate-spin" />
                        ) : (
                            <UploadCloud className="w-6 h-6" />
                        )}
                    </div>

                    <div className="flex-1 min-w-0 text-left">
                        {uploading ? (
                            <div className="w-full pr-4">
                                <div className="flex items-center justify-between mb-1.5">
                                    <div className="text-sm font-semibold text-slate-900">正在上传... {uploadProgress}%</div>
                                </div>
                                <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden w-full max-w-md ring-1 ring-slate-900/5">
                                    <div
                                        className="h-full bg-blue-500 transition-all duration-300 ease-out rounded-full"
                                        style={{ width: `${uploadProgress}%` }}
                                    />
                                </div>
                            </div>
                        ) : (
                            <div>
                                <h3 className="text-base font-bold text-slate-900 group-hover:text-blue-600 transition-colors">
                                    {isDragOver ? '释放文件以开始' : '点击或拖拽上传视频'}
                                </h3>
                                <p className="text-xs text-slate-500 mt-0.5">
                                    支持 MP4, AVI, MP3 等 • 最大 500MB
                                </p>
                            </div>
                        )}
                    </div>

                    {!uploading && (
                        <div className="hidden sm:block">
                            <span className="px-3 py-1.5 rounded-lg bg-slate-50 text-xs font-medium text-slate-600 border border-slate-200 group-hover:border-blue-200 group-hover:text-blue-600 transition-colors">
                                选择文件
                            </span>
                        </div>
                    )}
                </div>

                <input
                    type="file"
                    ref={fileInputRef}
                    className="hidden"
                    onChange={handleFileSelect}
                    disabled={uploading}
                />
            </div>

            <FileConfirmDialog
                file={selectedFile}
                open={showConfirm}
                onConfirm={handleConfirmUpload}
                onCancel={() => {
                    setShowConfirm(false)
                    setSelectedFile(null)
                }}
            />
        </>
    )
}
