import { useState } from 'react'
import { toast } from 'react-hot-toast'
import { downloadBilibili } from '../services/api'

export default function VideoDownloader() {
  const [url, setUrl] = useState('')
  const [cookie, setCookie] = useState('')
  const [loading, setLoading] = useState(false)
  const [quality, setQuality] = useState('best')

  const handleDownload = async () => {
    if (!url) {
      toast.error('请输入哔哩哔哩视频链接')
      return
    }

    setLoading(true)
    try {
      const resp = await downloadBilibili(url, cookie, quality)
      // 期望后端返回 { download_url: string } 或 { message: string, requires_login: boolean }
      if (resp.data && resp.data.download_url) {
        // 打开下载链接
        window.open(resp.data.download_url, '_blank')
        toast.success('已打开下载链接，若为分段请等待后端合并完成')
      } else if (resp.data && resp.data.message) {
        toast.success(resp.data.message)
      } else {
        toast.success('请求已发送，检查后端任务列表以查看进度')
      }
    } catch (e: any) {
      console.error('download error', e)
      const msg = e?.response?.data?.message || e.message || '下载请求失败'
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="h-full p-6">
      <div className="max-w-3xl mx-auto bg-white rounded shadow p-6">
        <h2 className="text-lg font-medium mb-4">多平台视频下载（当前：哔哩哔哩）</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">视频链接</label>
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="例如 https://www.bilibili.com/video/BV1F7qDBeEGy/"
              className="w-full border rounded px-3 py-2"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">登录 Cookie（可选，用于获取高清/会员源）</label>
            <textarea
              value={cookie}
              onChange={(e) => setCookie(e.target.value)}
              placeholder="SESSDATA=xxx; buvid3=xxx; ..."
              className="w-full border rounded px-3 py-2 h-28"
            />
            <p className="text-xs text-gray-500 mt-1">只有在需要会员权限或更高清源时才需要粘贴 Cookie，请妥善保管。</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">期望清晰度</label>
            <select value={quality} onChange={(e) => setQuality(e.target.value)} className="border rounded px-3 py-2">
              <option value="best">最高画质（可能需要登录）</option>
              <option value="1080p">1080p</option>
              <option value="720p">720p</option>
              <option value="480p">480p</option>
            </select>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleDownload}
              disabled={loading}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-60"
            >
              {loading ? '处理中...' : '解析并下载'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}


