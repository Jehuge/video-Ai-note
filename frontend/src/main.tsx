import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
// KaTeX 基础样式表：公式的上标/根号/分数线全靠它排版，必须在 index.css 之前引入，
// 让 .note-md 里的自定义规则能覆盖它
import 'katex/dist/katex.min.css'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)

