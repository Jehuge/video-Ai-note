import { Check, Loader2, Plus, RotateCcw, Save, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import toast from 'react-hot-toast'
import { resetNoteStyleSettings, saveNoteStyleSettings } from '../services/api'
import { useNoteStyles } from '../hooks/useNoteStyles'
import { NoteStyleDefinition, NoteStyleSettings as NoteStyleSettingsData } from '../utils/noteStyles'

export default function NoteStyleSettings() {
  const { settings: sharedSettings, loaded, replaceSettings } = useNoteStyles()
  const [settings, setSettings] = useState<NoteStyleSettingsData | null>(null)
  const [selectedId, setSelectedId] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!loaded || settings) return
    setSettings(sharedSettings)
    setSelectedId(sharedSettings.default_style_id)
  }, [loaded, sharedSettings, settings])

  const selected = useMemo(
    () => settings?.styles.find((style) => style.id === selectedId) || null,
    [settings, selectedId]
  )

  const updateSelected = (updates: Partial<NoteStyleDefinition>) => {
    if (!settings || !selected) return
    setSettings({
      ...settings,
      styles: settings.styles.map((style) => style.id === selected.id ? { ...style, ...updates } : style),
    })
  }

  const addStyle = () => {
    if (!settings) return
    const id = `custom-${crypto.randomUUID()}`
    const style: NoteStyleDefinition = {
      id,
      name: '自定义模式',
      prompt: '',
      built_in: false,
      enabled: true,
    }
    setSettings({ ...settings, styles: [...settings.styles, style] })
    setSelectedId(id)
  }

  const deleteSelected = () => {
    if (!settings || !selected || selected.built_in) return
    if (!window.confirm(`删除“${selected.name}”？`)) return
    const remainingStyles = settings.styles.filter((style) => style.id !== selected.id)
    let remaining = remainingStyles
    let enabled = remaining.filter((style) => style.enabled)
    if (!enabled.length) {
      remaining = remaining.map((style) => style.id === 'simple' ? { ...style, enabled: true } : style)
      enabled = remaining.filter((style) => style.enabled)
    }
    const defaultStyleId = settings.default_style_id === selected.id
      ? enabled[0]?.id || 'simple'
      : settings.default_style_id
    setSettings({ ...settings, default_style_id: defaultStyleId, styles: remaining })
    setSelectedId(defaultStyleId)
  }

  const toggleEnabled = () => {
    if (!settings || !selected) return
    if (selected.enabled && settings.default_style_id === selected.id) {
      toast.error('请先设置另一个默认模式')
      return
    }
    updateSelected({ enabled: !selected.enabled })
  }

  const setAsDefault = () => {
    if (!settings || !selected) return
    if (!selected.enabled) {
      toast.error('停用的模式不能设为默认')
      return
    }
    setSettings({ ...settings, default_style_id: selected.id })
  }

  const handleSave = async () => {
    if (!settings) return
    setSaving(true)
    try {
      const response = await saveNoteStyleSettings(settings)
      if (response.data.code !== 200) {
        throw new Error(response.data.msg || '保存失败')
      }
      const next = response.data.data as NoteStyleSettingsData
      setSettings(next)
      replaceSettings(next)
      toast.success('笔记模式设置已保存')
    } catch (error: any) {
      toast.error(error.response?.data?.msg || error.message || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleReset = async () => {
    if (!window.confirm('恢复四个内置模式的名称和提示词？自定义模式会保留。')) return
    try {
      const response = await resetNoteStyleSettings()
      if (response.data.code !== 200) {
        throw new Error(response.data.msg || '恢复失败')
      }
      const next = response.data.data as NoteStyleSettingsData
      setSettings(next)
      setSelectedId(next.default_style_id)
      replaceSettings(next)
      toast.success('内置模式已恢复')
    } catch (error: any) {
      toast.error(error.response?.data?.msg || error.message || '恢复失败')
    }
  }

  if (!loaded || !settings) {
    return (
      <div className="h-full flex items-center justify-center text-slate-500">
        <Loader2 className="w-5 h-5 animate-spin mr-2" />
        加载设置中...
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="max-w-6xl mx-auto">
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">笔记模式</h1>
            <p className="text-sm text-slate-500 mt-1">设置默认模式，以及生成笔记时附加给模型的写作要求。</p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={handleReset}
              className="p-2.5 border border-slate-300 text-slate-600 bg-white rounded-lg hover:bg-slate-50"
              title="恢复内置模式"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-4 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-60 flex items-center gap-2 font-medium"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              保存设置
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-[280px_minmax(0,1fr)] border border-slate-200 rounded-lg bg-white overflow-hidden min-h-[520px]">
          <aside className="border-b md:border-b-0 md:border-r border-slate-200 bg-slate-50">
            <div className="h-14 px-4 flex items-center justify-between border-b border-slate-200">
              <span className="text-sm font-semibold text-slate-800">模式列表</span>
              <button
                onClick={addStyle}
                className="p-2 text-blue-600 hover:bg-blue-50 rounded-md"
                title="新增模式"
              >
                <Plus className="w-4 h-4" />
              </button>
            </div>
            <div className="max-h-72 md:max-h-none overflow-y-auto">
              {settings.styles.map((style) => (
                <button
                  key={style.id}
                  onClick={() => setSelectedId(style.id)}
                  className={`w-full px-4 py-3 text-left border-b border-slate-200 transition-colors ${
                    selectedId === style.id ? 'bg-white text-blue-700' : 'text-slate-700 hover:bg-white/70'
                  }`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-sm font-medium truncate flex-1">{style.name}</span>
                    {settings.default_style_id === style.id && <Check className="w-4 h-4 text-emerald-600 shrink-0" />}
                  </div>
                  <div className="mt-1 text-xs text-slate-400">
                    {!style.enabled ? '已停用' : style.built_in ? '内置模式' : '自定义模式'}
                  </div>
                </button>
              ))}
            </div>
          </aside>

          {selected && (
            <section className="p-5 md:p-6 min-w-0">
              <div className="flex items-center justify-between gap-3 mb-6">
                <div className="min-w-0">
                  <div className="text-xs text-slate-400 truncate">{selected.id}</div>
                  <div className="text-sm text-slate-600 mt-1">
                    {selected.built_in ? '内置模式' : '自定义模式'}
                  </div>
                </div>
                {!selected.built_in && (
                  <button
                    onClick={deleteSelected}
                    className="p-2 text-red-600 hover:bg-red-50 rounded-md"
                    title="删除模式"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>

              <div className="space-y-5">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">模式名称</label>
                  <input
                    value={selected.name}
                    onChange={(event) => updateSelected({ name: event.target.value })}
                    maxLength={60}
                    className="w-full px-3 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">模式提示词</label>
                  <textarea
                    value={selected.prompt}
                    onChange={(event) => updateSelected({ prompt: event.target.value })}
                    rows={12}
                    maxLength={12000}
                    className="w-full min-h-64 resize-y px-3 py-2.5 border border-slate-300 rounded-lg font-mono text-sm leading-6 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
                    placeholder="输入该模式需要模型遵循的内容取舍、组织方式和表达要求"
                  />
                  <div className="mt-1 text-right text-xs text-slate-400">{selected.prompt.length} / 12000</div>
                </div>

                <div className="pt-4 border-t border-slate-100 flex flex-wrap items-center gap-3">
                  <label className="inline-flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={selected.enabled}
                      onChange={toggleEnabled}
                      className="w-4 h-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                    />
                    启用模式
                  </label>
                  {settings.default_style_id === selected.id ? (
                    <span className="text-sm font-medium text-emerald-700">当前默认模式</span>
                  ) : (
                    <button
                      onClick={setAsDefault}
                      disabled={!selected.enabled}
                      className="px-3 py-1.5 text-sm border border-slate-300 rounded-md text-slate-700 hover:border-blue-300 hover:text-blue-700 disabled:opacity-50"
                    >
                      设为默认
                    </button>
                  )}
                </div>
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  )
}
