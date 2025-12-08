import { useState } from 'react'
import { Upload, Loader2 } from 'lucide-react'
import { uploadVideo } from '../services/api'
import { useTaskStore } from '../store/taskStore'
import toast from 'react-hot-toast'
import FileConfirmDialog from './FileConfirmDialog'

// 格式化文件大小
const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i]
}

export default function UploadForm() {
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [showConfirm, setShowConfirm] = useState(false)
  const { addTask } = useTaskStore()

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    // 检查文件类型（基于扩展名和 MIME 类型）
    const fileExtension = file.name.split('.').pop()?.toLowerCase()
    const allowedExtensions = ['mp4', 'avi', 'mov', 'mkv', 'webm', 'mp3', 'wav', 'm4a', 'flv', 'wmv']
    
    const isAllowedExtension = fileExtension && allowedExtensions.includes(fileExtension)
    const isAllowedMime = file.type.startsWith('video/') || file.type.startsWith('audio/')
    
    if (!isAllowedExtension && !isAllowedMime) {
      toast.error('不支持的文件类型，请上传视频或音频文件')
      e.target.value = ''
      return
    }

    // 检查文件大小（限制 500MB）
    if (file.size > 500 * 1024 * 1024) {
      toast.error('文件大小不能超过 500MB')
      e.target.value = ''
      return
    }

    // 显示确认对话框
    setSelectedFile(file)
    setShowConfirm(true)
    e.target.value = ''
  }

  const handleConfirmUpload = async (screenshot: boolean) => {
    if (!selectedFile) return

    // 获取当前选择的模型配置
    const selectedModelId = localStorage.getItem('selectedModel')
    const modelConfigs = localStorage.getItem('modelConfigs')
    
    let modelConfig = null
    if (selectedModelId && modelConfigs) {
      try {
        const configs = JSON.parse(modelConfigs)
        // 从 selectedModelId 中提取 provider 和 modelId
        // selectedModelId 格式: "provider-modelId"
        // 找到第一个 '-' 的位置，前面是 provider，后面是 modelId
        const firstDashIndex = selectedModelId.indexOf('-')
        if (firstDashIndex > 0) {
          const provider = selectedModelId.substring(0, firstDashIndex)
          const modelId = selectedModelId.substring(firstDashIndex + 1)
          const providerConfig = configs[provider]
          
          if (providerConfig) {
            // 使用从 selectedModelId 解析出来的 modelId
            // 这是用户实际选择的模型
            modelConfig = {
              provider,
              api_key: providerConfig.apiKey || '',
              base_url: providerConfig.baseUrl || '',
              model: modelId, // 使用从 selectedModelId 解析的 modelId
            }
            console.log('上传时使用的模型配置:', modelConfig)
          }
        }
      } catch (e) {
        console.error('解析模型配置失败:', e)
      }
    } else {
      console.warn('未选择模型或模型配置不存在')
    }

    setShowConfirm(false)
    setUploading(true)
    setUploadProgress(0)

    try {
      const response = await uploadVideo(
        selectedFile,
        screenshot,
        modelConfig,
        (progress) => {
          setUploadProgress(progress)
        }
      )

      if (response.data.code === 200) {
        const { task_id, filename } = response.data.data

        // 添加到任务列表
        addTask({
          id: task_id,
          filename,
          status: 'pending',
        })

        toast.success('文件上传成功！')
        setSelectedFile(null)
        setUploadProgress(0)
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

  const handleCancelUpload = () => {
    setShowConfirm(false)
    setSelectedFile(null)
  }

  return (
    <>
      <div>
        <label className="flex flex-col items-center justify-center w-full h-40 border-2 border-dashed border-gray-300 rounded-lg cursor-pointer hover:border-blue-400 hover:bg-blue-50/50 transition-all bg-white shadow-sm">
          {uploading ? (
            <div className="flex flex-col items-center w-full px-4">
              <Loader2 className="w-8 h-8 animate-spin text-blue-500 mb-2" />
              <span className="text-sm text-gray-600 mb-2">上传中...</span>
              {/* 进度条 */}
              <div className="w-full bg-gray-200 rounded-full h-2.5 mb-1">
                <div
                  className="bg-blue-500 h-2.5 rounded-full transition-all duration-300"
                  style={{ width: `${uploadProgress}%` }}
                ></div>
              </div>
              <span className="text-xs text-gray-500">
                {uploadProgress}% - {selectedFile ? formatFileSize(selectedFile.size) : ''}
              </span>
            </div>
          ) : (
            <div className="flex flex-col items-center">
              <Upload className="w-8 h-8 text-gray-400 mb-2" />
              <span className="text-sm text-gray-600">
                点击或拖拽文件到此处上传
              </span>
              <span className="text-xs text-gray-400 mt-1">
                支持 MP4, AVI, MOV, MKV, MP3, WAV 等格式（最大 500MB）
              </span>
            </div> 
          )}
          <input
            type="file"
            className="hidden"
            // 移除 accept 属性以避免某些系统下文件无法选择的问题，文件类型检查已在 onChange 中处理
            onChange={handleFileSelect}
            disabled={uploading}
          />
        </label>
      </div>

      <FileConfirmDialog
        file={selectedFile}
        open={showConfirm}
        onConfirm={handleConfirmUpload}
        onCancel={handleCancelUpload}
      />
    </>
  )
}
