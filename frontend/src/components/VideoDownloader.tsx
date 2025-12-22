import { useState, useEffect, useRef } from 'react'
import { toast } from 'react-hot-toast'
import { downloadBilibili, startBilibiliLogin, getBilibiliLoginStatus, getBilibiliTaskStatus } from '../services/api'

export default function VideoDownloader() {
  const [url, setUrl] = useState('')
  const [cookie, setCookie] = useState('')
  const [loading, setLoading] = useState(false)
  const [quality, setQuality] = useState('best')
  const [qrBase64, setQrBase64] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [loginInProgress, setLoginInProgress] = useState(false)
  const [loginFinished, setLoginFinished] = useState(false)
  const [autoDownloadTriggered, setAutoDownloadTriggered] = useState(false)
  const pollRef = useRef<number | null>(null)
  const taskPollRef = useRef<number | null>(null)

  const handleDownload = async () => {
    if (!url) {
      toast.error('请输入哔哩哔哩视频链接')
      return
    }

    setLoading(true)
    try {
      // 如果使用扫码登录并已完成，则将 cookie 设为 session:<id>
      const cookieToSend = loginFinished && sessionId ? `session:${sessionId}` : cookie
      const resp = await downloadBilibili(url, cookieToSend, quality)
      // 如果返回直接 download_url，则打开；如果返回 task_id，则开始轮询任务状态
      if (resp.data && resp.data.download_url) {
        window.open(resp.data.download_url, '_blank')
        toast.success('已打开下载链接')
      } else if (resp.data && resp.data.task_id) {
        const taskId = resp.data.task_id
        toast.loading(`后台合并开始，任务 ${taskId} 已提交`)
        // 开始轮询任务状态
        taskPollRef.current = window.setInterval(async () => {
          try {
            const st = await getBilibiliTaskStatus(taskId)
            const data = st.data
            if (data) {
              const status = data.status
              const progress = data.progress || 0
              if (status === 'running') {
                toast.loading(`合并进行中：${progress}% (任务 ${taskId})`)
              } else if (status === 'completed') {
                if (taskPollRef.current) {
                  clearInterval(taskPollRef.current)
                  taskPollRef.current = null
                }
                toast.success(`合并完成，正在打开文件`)
                // 打开静态下载链接
                if (data.output) {
                  window.open(data.output, '_blank')
                } else {
                  toast.error('合并完成但未返回下载地址')
                }
              } else if (status === 'failed') {
                if (taskPollRef.current) {
                  clearInterval(taskPollRef.current)
                  taskPollRef.current = null
                }
                toast.error(`合并失败: ${data.error || '未知错误'}`)
              }
            }
          } catch (err) {
            console.error('task poll error', err)
          }
        }, 2000)
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

  // 启动扫码登录流程
  const handleStartLogin = async () => {
    try {
      setLoginInProgress(true)
      const resp = await startBilibiliLogin()
      const { session_id, qr_image_base64 } = resp.data
      setSessionId(session_id)
      setQrBase64(qr_image_base64)

      // 开始轮询登录状态
      pollRef.current = window.setInterval(async () => {
        try {
          const st = await getBilibiliLoginStatus(session_id)
          if (st.data && st.data.finished) {
            setLoginFinished(true)
            setLoginInProgress(false)
            // 自动填充 cookie 为 session:ID，方便直接下载
            setCookie(`session:${session_id}`)
            if (pollRef.current) {
              clearInterval(pollRef.current)
              pollRef.current = null
            }
            toast.success('登录成功，已自动使用该会话进行下载')
          }
        } catch (err) {
          console.error('login poll error', err)
        }
      }, 2000)
    } catch (err: any) {
      console.error('start login error', err)
      toast.error(err?.response?.data?.detail || '启动扫码登录失败')
      setLoginInProgress(false)
    }
  }

  useEffect(() => {
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current)
      }
      if (taskPollRef.current) {
        clearInterval(taskPollRef.current)
      }
    }
  }, [])

  // 当扫码登录成功且已有视频链接时，自动发起解析下载（只触发一次）
  useEffect(() => {
    if (loginFinished && sessionId && url && !autoDownloadTriggered) {
      setAutoDownloadTriggered(true)
      toast('检测到已登录，会在 1 秒后自动开始解析并下载', { icon: '🔔' })
      setTimeout(() => {
        handleDownload()
      }, 1000)
    }
  }, [loginFinished, sessionId, url, autoDownloadTriggered])

  return (
    <div className="h-full p-6">
      <div className="max-w-3xl mx-auto bg-white rounded shadow p-6">
        <h2 className="text-lg font-medium mb-4">多平台视频下载（当前：哔哩哔哩）</h2>
        <div className="space-y-4">
          <div>
            <button
              onClick={handleStartLogin}
              disabled={loginInProgress || loginFinished}
              className="px-3 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-60 mr-3"
            >
              {loginFinished ? '已登录' : loginInProgress ? '等待扫码...' : '扫码登录（B站）'}
            </button>
            {sessionId && (
              <span className="text-sm text-gray-500 ml-2">会话：{sessionId}</span>
            )}
          </div>

          {qrBase64 && !loginFinished && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">扫码登录二维码</label>
              <img src={`data:image/png;base64,${qrBase64}`} alt="bili-qr" className="w-48 h-48 border" />
              <p className="text-xs text-gray-500 mt-1">请使用哔哩哔哩 App 扫码，等待页面提示登录完成。</p>
            </div>
          )}

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


