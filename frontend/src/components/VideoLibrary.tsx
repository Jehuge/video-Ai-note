import { useState, useEffect } from 'react'
import { FileVideo, Clock, Database, Loader2, Search, Play, PencilLine } from 'lucide-react'
import { getVideoFiles, createTaskFromFile } from '../services/api'
import { useTaskStore } from '../store/taskStore'
import toast from 'react-hot-toast'
import FileConfirmDialog from './FileConfirmDialog'
import ContentPreviewModal from './ContentPreviewModal'
import { getSelectedModelConfig } from '../utils/modelConfig'

interface VideoFile {
    filename: string
    path: string
    size: number
    modified_at: string
    source: 'upload' | 'bilibili'
    metadata?: {
        title?: string
        bv_id?: string
        quality?: number
    }
}

// 多P视频解析：文件名/BV号形如 BVxxxx_pN，标题形如 "系列标题 Pn 分P名"
function parseMultiPart(file: VideoFile) {
    const bv = file.metadata?.bv_id || ''
    const m = bv.match(/_p(\d+)$/)
    if (!m) return null
    const t = file.metadata?.title || ''
    const tm = t.match(/^(.*?)\s+P\d+\s+(.*)$/)
    return {
        pageNo: m[1],
        series: tm ? tm[1] : t,
        label: tm ? `P${m[1]} · ${tm[2]}` : `P${m[1]}`,
    }
}

interface VideoLibraryProps {
    onTaskCreated: (taskId: string) => void
}

export default function VideoLibrary({ onTaskCreated }: VideoLibraryProps) {
    const { addTask } = useTaskStore()
    const [loading, setLoading] = useState(true)
    const [files, setFiles] = useState<VideoFile[]>([])
    const [selectedFile, setSelectedFile] = useState<VideoFile | null>(null)
    const [showConfirm, setShowConfirm] = useState(false)
    const [searchTerm, setSearchTerm] = useState('')
    const [previewFile, setPreviewFile] = useState<VideoFile | null>(null)

    useEffect(() => {
        loadFiles()
    }, [])

    const loadFiles = async () => {
        setLoading(true)
        try {
            // @ts-ignore
            const res = await getVideoFiles()
            if (res.data.success) {
                setFiles(res.data.data)
            }
        } catch (error) {
            console.error('加载视频文件失败:', error)
            toast.error('无法加载媒体库')
        } finally {
            setLoading(false)
        }
    }

    const handleSelect = (file: VideoFile) => {
        setSelectedFile(file)
        setShowConfirm(true)
    }

    const handleConfirm = async (screenshot: boolean) => {
        if (!selectedFile) return

        // 此处逻辑复用 UploadZone 的逻辑，但不涉及文件上传
        const noteStyle = 'simple'

        const modelConfig = getSelectedModelConfig(noteStyle)

        const toastId = toast.loading('正在创建任务...')
        setShowConfirm(false)

        try {
            // @ts-ignore
            const response = await createTaskFromFile(
                selectedFile.path,
                screenshot,
                modelConfig,
                noteStyle
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

                toast.success('任务创建成功', { id: toastId })
                if (onTaskCreated) onTaskCreated(task_id)
            } else {
                toast.error(response.data.msg || '创建失败', { id: toastId })
            }
        } catch (error: any) {
            console.error('创建任务失败:', error)
            toast.error(error.response?.data?.msg || '创建失败', { id: toastId })
        }
    }

    // 格式化文件大小
    const formatSize = (bytes: number) => {
        if (bytes === 0) return '0 B'
        const k = 1024
        const sizes = ['B', 'KB', 'MB', 'GB']
        const i = Math.floor(Math.log(bytes) / Math.log(k))
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
    }

    // 格式化时间
    const formatTime = (isoString: string) => {
        return new Date(isoString).toLocaleString()
    }

    const filteredFiles = files.filter(f => {
        const term = searchTerm.toLowerCase()
        return f.filename.toLowerCase().includes(term) ||
            f.metadata?.title?.toLowerCase().includes(term) ||
            f.metadata?.bv_id?.toLowerCase().includes(term)
    })

    return (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden flex flex-col max-h-[500px] min-w-0">
            {/* Header */}
            <div className="p-4 border-b border-gray-100 flex items-center justify-between gap-4 bg-gray-50/50">
                <h3 className="font-semibold text-gray-800 flex items-center gap-2 shrink-0">
                    <Database className="w-4 h-4 text-blue-500" />
                    B站下载媒体库
                </h3>
                <div className="relative w-full max-w-64">
                    <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                    <input
                        type="text"
                        placeholder="搜索标题、文件名或BV号..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        className="w-full pl-9 pr-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                    />
                </div>
            </div>

            {/* List */}
            <div className="flex-1 overflow-y-auto overflow-x-hidden p-2">
                {loading ? (
                    <div className="flex flex-col items-center justify-center py-12 text-gray-400">
                        <Loader2 className="w-8 h-8 animate-spin mb-2" />
                        <p className="text-sm">加载媒体库...</p>
                    </div>
                ) : files.length === 0 ? (
                    <div className="text-center py-12 text-gray-400">
                        <Database className="w-12 h-12 mx-auto mb-3 opacity-20" />
                        <p>暂无已下载的视频</p>
                        <p className="text-xs mt-1">请先去 B站下载 页面下载视频</p>
                    </div>
                ) : filteredFiles.length === 0 ? (
                    <div className="text-center py-12 text-gray-400">
                        <p>未找到匹配的视频</p>
                    </div>
                ) : (
                    <div className="grid gap-2">
                        {filteredFiles.map((file) => {
                            const part = parseMultiPart(file)
                            const displayTitle = part ? part.label : (file.metadata?.title || file.filename)
                            const subTitle = part ? part.series : (file.metadata?.title || null)
                            return (
                                <div
                                    key={file.filename}
                                    className="group flex items-center gap-3 p-3 rounded-lg border border-transparent hover:border-blue-100 hover:bg-blue-50/50 cursor-pointer transition-all min-w-0"
                                    onClick={() => handleSelect(file)}
                                >
                                    <div className="w-10 h-10 rounded-lg bg-blue-100/50 text-blue-600 flex items-center justify-center flex-shrink-0 group-hover:bg-blue-200/50 transition-colors">
                                        <FileVideo className="w-5 h-5" />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-0.5 min-w-0">
                                            <h4 className="font-medium text-gray-900 line-clamp-1 break-all" title={file.metadata?.title || file.filename}>
                                                {displayTitle}
                                            </h4>
                                            {file.source === 'bilibili' && (
                                                <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-pink-100 text-pink-600 shrink-0">
                                                    Bilibili
                                                </span>
                                            )}
                                        </div>
                                        {subTitle && (
                                            <p className="text-xs text-gray-400 line-clamp-1 break-all mb-0.5" title={subTitle}>{subTitle}</p>
                                        )}
                                        <div className="flex items-center gap-3 text-xs text-gray-500">
                                            <span className="flex items-center gap-1 shrink-0">
                                                <Database className="w-3 h-3" />
                                                {formatSize(file.size)}
                                            </span>
                                            <span className="flex items-center gap-1 shrink-0">
                                                <Clock className="w-3 h-3" />
                                                {formatTime(file.modified_at)}
                                            </span>
                                            {file.metadata?.bv_id && (
                                                <span className="font-mono bg-gray-100 px-1 rounded truncate">
                                                    {file.metadata.bv_id}
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2 shrink-0">
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation()
                                                setPreviewFile(file)
                                            }}
                                            title="播放视频"
                                            className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-600 text-xs font-medium rounded-md transition-colors flex items-center gap-1"
                                        >
                                            <Play className="w-3.5 h-3.5" fill="currentColor" />
                                            播放
                                        </button>
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation()
                                                handleSelect(file)
                                            }}
                                            className="opacity-60 group-hover:opacity-100 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium rounded-md shadow-sm transition-all flex items-center gap-1"
                                        >
                                            <PencilLine className="w-3.5 h-3.5" />
                                            创建笔记
                                        </button>
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                )}
            </div>

            {/* 视频预览 */}
            {previewFile && (
                <ContentPreviewModal
                    type="video"
                    content={`/api/uploads/${encodeURIComponent(previewFile.filename)}`}
                    title={previewFile.metadata?.title || previewFile.filename}
                    onClose={() => setPreviewFile(null)}
                />
            )}

            {/* Confirm Dialog - reuse logic via wrapper or simply pass mock file object */}
            {/* Since FileConfirmDialog expects a File object, we might need a modified version or adapt the props. 
                Let's check FileConfirmDialog first. It likely just displays name/size. 
                Wait, FileConfirmDialog takes 'file: File | null'. We don't have a File object, just metadata.
                We should verify FileConfirmDialog implementation. */}

            {selectedFile && (
                <FileConfirmDialog
                    // @ts-ignore - Create a mock file object structure that satisfies the dialog's display needs
                    file={{
                        name: selectedFile.metadata?.title ? `${selectedFile.metadata.title} (${selectedFile.filename})` : selectedFile.filename,
                        size: selectedFile.size,
                        type: 'video/mp4' // Mock
                    }}
                    open={showConfirm}
                    onConfirm={handleConfirm}
                    onCancel={() => {
                        setShowConfirm(false)
                        setSelectedFile(null)
                    }}
                    title="确认创建任务"
                    confirmText="开始生成笔记"
                />
            )}
        </div>
    )
}
