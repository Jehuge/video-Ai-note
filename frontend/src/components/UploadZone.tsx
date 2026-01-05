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
          relative group cursor-pointer overflow-hidden rounded-xl border-2 border-dashed transition-all duration-300
          ${isDragOver
                        ? 'border-blue-500 bg-blue-50 scale-[1.01]'
                        : 'border-blue-200 bg-white hover:border-blue-400 hover:bg-blue-50/50 hover:shadow-md'
                    }
          ${uploading ? 'pointer-events-none opacity-80' : ''}
        `}
            >
                <div className="p-8 flex flex-col items-center justify-center text-center">
                    <div className={`
            p-4 rounded-full mb-4 transition-colors duration-300
            ${isDragOver ? 'bg-blue-100' : 'bg-blue-50 group-hover:bg-blue-100'}
          `}>
                        {uploading ? (
                            <Loader2 className="w-8 h-8 text-blue-600 animate-spin" />
                        ) : (
                            <UploadCloud className="w-8 h-8 text-blue-600" />
                        )}
                    </div>

                    {uploading ? (
                        <div className="w-full max-w-[200px]">
                            <div className="text-sm font-medium text-blue-900 mb-1">正在上传...</div>
                            <div className="text-xs text-blue-600 mb-2">{uploadProgress}%</div>
                            <div className="h-1 bg-blue-100 rounded-full overflow-hidden">
                                <div
                                    className="h-full bg-blue-500 transition-all duration-300"
                                    style={{ width: `${uploadProgress}%` }}
                                />
                            </div>
                        </div>
                    ) : (
                        <>
                            <h3 className="text-lg font-semibold text-gray-900 mb-2">
                                {isDragOver ? '释放文件以开始' : '点击或拖拽上传'}
                            </h3>
                            <p className="text-sm text-gray-500">
                                支持 MP4, AVI, MP3, WAV 等视频/音频文件
                            </p>
                        </>
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
