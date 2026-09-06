import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    // Windows 下文件监听经常失效，改用轮询（300ms），根治"改了代码页面不更新"
    watch: {
      usePolling: true,
      interval: 300,
    },
    proxy: {
      '/api': {
        target: 'http://localhost:8483',
        changeOrigin: true,
        ws: true, // 启用 WebSocket 代理
      },
    },
  },
})

