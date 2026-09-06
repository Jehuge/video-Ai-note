import { useEffect, useState } from 'react'
import { Cpu, Gauge, Loader2, Save, SlidersHorizontal, Zap, Sparkles } from 'lucide-react'
import toast from 'react-hot-toast'
import { getTranscriberConfig, saveTranscriberConfig, testTranscriberConfig } from '../services/api'

interface TranscriberConfig {
  type: string
  engine: string
  model_size: string
  device: string
  compute_type: string
  hotwords?: string
}

const DEFAULT_CONFIG: TranscriberConfig = {
  type: 'fast-whisper',
  engine: 'fast-whisper',
  model_size: 'base',
  device: 'cpu',
  compute_type: 'int8',
  hotwords: '',
}

const ENGINES = [
  {
    value: 'funasr',
    name: 'FunASR（推荐）',
    desc: '阿里 Paraformer 中文模型，中文课视频识别更准、CPU 上速度远快于 Whisper；支持热词，模型从国内 ModelScope 下载',
    tag: '中文课程优化',
  },
  {
    value: 'fast-whisper',
    name: 'faster-whisper',
    desc: 'OpenAI Whisper 本地版，多语言通用；模型从 HuggingFace 下载（国内网络可能失败）',
    tag: '多语言',
  },
]

const MODEL_SIZES = ['tiny', 'base', 'small', 'medium', 'large-v3']
const DEVICES = [
  { value: 'cpu', label: 'CPU' },
  { value: 'cuda', label: 'CUDA' },
  { value: 'auto', label: 'Auto' },
]
const COMPUTE_TYPES = ['int8', 'float16', 'float32']

export default function TranscriberSettings({ embedded = false }: { embedded?: boolean }) {
  const [config, setConfig] = useState<TranscriberConfig>(DEFAULT_CONFIG)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)

  useEffect(() => {
    const load = async () => {
      try {
        const response = await getTranscriberConfig()
        if (response.data.code === 200 && response.data.data) {
          setConfig({ ...DEFAULT_CONFIG, ...response.data.data, type: 'fast-whisper' })
        }
      } catch (error) {
        console.error('Failed to load local speech config:', error)
        toast.error('加载本地识别配置失败')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const update = (field: keyof TranscriberConfig, value: string) => {
    setConfig((prev) => ({ ...prev, [field]: value }))
  }

  const payload = () => ({
    type: 'fast-whisper',
    engine: config.engine,
    model_size: config.model_size,
    device: config.device,
    compute_type: config.compute_type,
    hotwords: config.hotwords || '',
  })

  const handleSave = async () => {
    setSaving(true)
    try {
      const response = await saveTranscriberConfig(payload())
      if (response.data.code === 200) {
        setConfig({ ...DEFAULT_CONFIG, ...response.data.data, type: 'fast-whisper' })
        toast.success('本地识别配置已保存')
      } else {
        toast.error(response.data.msg || '保存失败')
      }
    } catch (error: any) {
      toast.error(error.response?.data?.msg || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
    setTesting(true)
    try {
      const response = await testTranscriberConfig(payload())
      if (response.data.code === 200) {
        toast.success('本地识别配置可用')
      } else {
        toast.error(response.data.msg || '配置不可用')
      }
    } catch (error: any) {
      toast.error(error.response?.data?.msg || '配置不可用')
    } finally {
      setTesting(false)
    }
  }

  if (loading) {
    return (
      <div className={`flex items-center justify-center text-slate-500 ${embedded ? 'py-8' : 'h-full'}`}>
        <Loader2 className="w-5 h-5 animate-spin mr-2" />
        加载设置中...
      </div>
    )
  }

  return (
    <div className={embedded ? '' : 'h-full overflow-y-auto bg-slate-50 p-6'}>
      <div className={embedded ? '' : 'max-w-4xl mx-auto'}>
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-slate-900">本地语音识别</h1>
          <p className="text-sm text-slate-500 mt-1">
            音频转文字在本机完成，不需要语音识别 API Key；笔记生成的 LLM 厂商在“模型配置”中设置。
          </p>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg shadow-sm p-6 space-y-6">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              <Zap className="w-4 h-4 inline mr-1" />
              转写引擎
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {ENGINES.map((item) => (
                <button
                  key={item.value}
                  onClick={() => update('engine', item.value)}
                  className={`text-left p-3 rounded-lg border transition-colors ${
                    config.engine === item.value
                      ? 'border-blue-500 bg-blue-50/60 ring-1 ring-blue-200'
                      : 'border-slate-200 bg-white hover:border-blue-200'
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-semibold text-slate-800">{item.name}</span>
                    {item.value === 'funasr' && (
                      <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-100 text-emerald-700">
                        <Sparkles className="w-2.5 h-2.5" />
                        {item.tag}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-500 leading-relaxed">{item.desc}</p>
                </button>
              ))}
            </div>
          </div>

          {config.engine === 'funasr' && (
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                <Sparkles className="w-4 h-4 inline mr-1" />
                识别热词（空格分隔，可选）
              </label>
              <input
                value={config.hotwords || ''}
                onChange={(e) => update('hotwords', e.target.value)}
                placeholder="例如：洛伦兹力 圆锥曲线 傅里叶变换 楞次定律"
                className="w-full px-3 py-2 border border-slate-300 rounded-lg bg-white text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
              <p className="text-xs text-slate-400 mt-1.5">
                把课程里的专有名词加入热词，可明显提升这些词的识别准确率（对数学、物理课尤其有效）。未填写时使用内置理科热词表。
              </p>
            </div>
          )}

          {config.engine === 'fast-whisper' && (
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              <Cpu className="w-4 h-4 inline mr-1" />
              模型大小
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
              {MODEL_SIZES.map((item) => (
                <button
                  key={item}
                  onClick={() => update('model_size', item)}
                  className={`px-3 py-2 rounded-lg border text-sm font-medium transition-colors ${
                    config.model_size === item
                      ? 'border-blue-500 bg-blue-50 text-blue-700'
                      : 'border-slate-200 bg-white text-slate-700 hover:border-blue-200'
                  }`}
                >
                  {item}
                </button>
              ))}
            </div>
          </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                <Gauge className="w-4 h-4 inline mr-1" />
                运行设备
              </label>
              <select
                value={config.device}
                onChange={(e) => update('device', e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg bg-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                {DEVICES.map((item) => (
                  <option key={item.value} value={item.value}>{item.label}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                <SlidersHorizontal className="w-4 h-4 inline mr-1" />
                计算精度
              </label>
              <select
                value={config.compute_type}
                onChange={(e) => update('compute_type', e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg bg-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                {COMPUTE_TYPES.map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="pt-4 border-t border-slate-100 flex flex-col sm:flex-row gap-3">
            <button
              onClick={handleTest}
              disabled={testing}
              className="px-4 py-2.5 bg-white text-slate-700 border border-slate-300 rounded-lg hover:bg-slate-50 transition-colors flex items-center justify-center gap-2 font-medium disabled:opacity-70"
            >
              {testing && <Loader2 className="w-4 h-4 animate-spin" />}
              检查配置
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-4 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center justify-center gap-2 font-medium disabled:opacity-70"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              保存本地识别配置
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
