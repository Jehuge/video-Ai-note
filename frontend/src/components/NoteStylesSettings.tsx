import { useEffect, useState } from 'react'
import { Palette, Plus, Pencil, Trash2, Loader2, X, Sparkles, Lock } from 'lucide-react'
import { getNoteStyles, createNoteStyle, updateNoteStyle, deleteNoteStyle, NoteStyle } from '../services/api'
import toast from 'react-hot-toast'

const PROMPT_HINT = `这段提示词会作为"风格指令"注入笔记生成流程，和视频转写内容一起发给模型。
可以描述：结构（如何分章节）、语言风格（口语化/严谨/考纲导向）、重点（公式推导、例题步骤、易错点）、输出格式（表格、符号规范）等。
用中文或英文都可以。`

export default function NoteStylesSettings() {
    const [styles, setStyles] = useState<NoteStyle[]>([])
    const [loading, setLoading] = useState(true)
    const [editing, setEditing] = useState<NoteStyle | null>(null) // 编辑中的风格
    const [creating, setCreating] = useState(false)
    const [saving, setSaving] = useState(false)
    const [form, setForm] = useState({ name: '', icon: '📝', prompt: '' })

    const loadStyles = async () => {
        setLoading(true)
        try {
            setStyles(await getNoteStyles())
        } catch {
            toast.error('加载笔记风格失败')
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        loadStyles()
    }, [])

    const openCreate = () => {
        setForm({ name: '', icon: '📝', prompt: '' })
        setEditing(null)
        setCreating(true)
    }

    const openEdit = (s: NoteStyle) => {
        setForm({ name: s.name, icon: s.icon, prompt: s.prompt })
        setEditing(s)
        setCreating(true)
    }

    const handleSave = async () => {
        if (!form.name.trim() || !form.prompt.trim()) {
            toast.error('名称和提示词不能为空')
            return
        }
        setSaving(true)
        try {
            if (editing) {
                await updateNoteStyle(editing.id, { name: form.name, prompt: form.prompt, icon: form.icon })
                toast.success('风格已更新')
            } else {
                await createNoteStyle(form.name, form.prompt, form.icon)
                toast.success('风格已创建')
            }
            setCreating(false)
            setEditing(null)
            loadStyles()
        } catch (error: any) {
            toast.error(error.response?.data?.detail || '保存失败')
        } finally {
            setSaving(false)
        }
    }

    const handleDelete = async (s: NoteStyle) => {
        if (!window.confirm(`确定删除风格「${s.name}」吗？`)) return
        try {
            await deleteNoteStyle(s.id)
            toast.success('已删除')
            loadStyles()
        } catch (error: any) {
            toast.error(error.response?.data?.detail || '删除失败')
        }
    }

    return (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 mb-6">
            <div className="flex items-center justify-between mb-1">
                <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                    <Palette className="w-4 h-4 text-violet-500" />
                    笔记风格
                </h3>
                <button
                    onClick={openCreate}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium bg-violet-600 hover:bg-violet-700 text-white rounded-lg transition-colors shadow-sm"
                >
                    <Plus className="w-4 h-4" />
                    新建风格
                </button>
            </div>
            <p className="text-xs text-gray-500 mb-4">
                自定义笔记风格的提示词模板。生成笔记时在任务页选择对应风格即可生效，内置风格不可修改。
            </p>

            {loading ? (
                <div className="flex items-center justify-center py-8 text-gray-400">
                    <Loader2 className="w-5 h-5 animate-spin" />
                </div>
            ) : (
                <div className="grid gap-2">
                    {styles.map((s) => (
                        <div
                            key={s.id}
                            className="group flex items-center gap-3 p-3 rounded-lg border border-gray-100 hover:border-violet-200 hover:bg-violet-50/40 transition-all"
                        >
                            <span className="text-xl shrink-0 w-8 text-center">{s.icon}</span>
                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                    <h4 className="text-sm font-medium text-gray-900">{s.name}</h4>
                                    {s.builtin ? (
                                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] bg-gray-100 text-gray-500">
                                            <Lock className="w-2.5 h-2.5" />
                                            内置
                                        </span>
                                    ) : (
                                        <span className="px-1.5 py-0.5 rounded text-[10px] bg-violet-100 text-violet-600">自定义</span>
                                    )}
                                </div>
                                <p className="text-xs text-gray-400 line-clamp-1 mt-0.5" title={s.prompt}>
                                    {s.prompt || '—'}
                                </p>
                            </div>
                            {!s.builtin && (
                                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                                    <button
                                        onClick={() => openEdit(s)}
                                        className="p-1.5 text-gray-400 hover:text-violet-600 hover:bg-violet-100 rounded-md"
                                        title="编辑"
                                    >
                                        <Pencil className="w-4 h-4" />
                                    </button>
                                    <button
                                        onClick={() => handleDelete(s)}
                                        className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-md"
                                        title="删除"
                                    >
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}

            {/* 新建/编辑弹窗 */}
            {creating && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
                    <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setCreating(false)} />
                    <div className="relative bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[85vh] flex flex-col">
                        <div className="flex items-center justify-between p-5 border-b border-gray-100">
                            <h4 className="font-semibold text-gray-900 flex items-center gap-2">
                                <Sparkles className="w-4 h-4 text-violet-500" />
                                {editing ? '编辑风格' : '新建笔记风格'}
                            </h4>
                            <button onClick={() => setCreating(false)} className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-md">
                                <X className="w-4 h-4" />
                            </button>
                        </div>
                        <div className="p-5 space-y-4 overflow-y-auto">
                            <div className="flex gap-3">
                                <div>
                                    <label className="block text-xs font-medium text-gray-500 mb-1">图标</label>
                                    <input
                                        value={form.icon}
                                        onChange={(e) => setForm({ ...form, icon: e.target.value })}
                                        maxLength={4}
                                        className="w-16 px-3 py-2 text-center text-lg border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500"
                                    />
                                </div>
                                <div className="flex-1">
                                    <label className="block text-xs font-medium text-gray-500 mb-1">风格名称 *</label>
                                    <input
                                        value={form.name}
                                        onChange={(e) => setForm({ ...form, name: e.target.value })}
                                        placeholder="例如：考研数学重点提炼"
                                        maxLength={30}
                                        className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500"
                                    />
                                </div>
                            </div>
                            <div>
                                <label className="block text-xs font-medium text-gray-500 mb-1">提示词模板 *</label>
                                <textarea
                                    value={form.prompt}
                                    onChange={(e) => setForm({ ...form, prompt: e.target.value })}
                                    rows={10}
                                    placeholder={'例如：\n- 以考纲知识点为主线组织笔记，每个知识点给出：定义、公式、典型例题、易错点\n- 公式用 LaTeX 展示并保留推导过程\n- 语言精炼，适合考前复习快速过一遍'}
                                    className="w-full px-3 py-2 text-sm font-mono border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 leading-relaxed"
                                />
                                <p className="text-xs text-gray-400 mt-1.5 leading-relaxed">{PROMPT_HINT}</p>
                            </div>
                        </div>
                        <div className="flex items-center justify-end gap-2 p-4 border-t border-gray-100">
                            <button onClick={() => setCreating(false)} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors">
                                取消
                            </button>
                            <button
                                onClick={handleSave}
                                disabled={saving}
                                className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium bg-violet-600 hover:bg-violet-700 text-white rounded-lg transition-colors disabled:opacity-50"
                            >
                                {saving && <Loader2 className="w-4 h-4 animate-spin" />}
                                {editing ? '保存修改' : '创建风格'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
