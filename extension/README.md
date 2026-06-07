# AInote Video Bridge Extension

这是 Video Note AI / AInote 的 Chrome/Edge Manifest V3 插件。插件负责检测当前页面视频、手动选择视频框、选择清晰度和笔记模式，然后把任务发送给本机 AInote App。

## 开发加载

1. 启动 AInote 桌面 App 或后端服务，确认 `127.0.0.1:8483` 可访问。
2. 打开 `chrome://extensions` 或 `edge://extensions`。
3. 开启“开发者模式”。
4. 点击“加载已解压的扩展程序”，选择本 `extension/` 目录。
5. 打开视频页面，点击插件图标。

## 使用流程

1. 插件会自动扫描当前页面的 `<video>`、`<source>`、HLS、DASH、MP4、WebM 和媒体请求。
2. 如果页面有多个视频，可以点击“选视频”，在页面上手动点击目标视频框。
3. 点击解析后，插件会请求本机 App 返回真实候选视频和可用格式。
4. 选择视频候选、清晰度、是否带截图、是否发送站点 Cookie、笔记模式。站点 Cookie 默认开启，用于 B 站、抖音等需要登录态才能解析高画质或播放地址的网站。
5. 点击“生成视频笔记”，后续下载、转写和笔记生成都在 AInote App 里执行。

## 测试

```powershell
node extension\test-popup.js
node extension\test-content-picker.js
node extension\test-background.js
node --check extension\background.js
node --check extension\content.js
node --check extension\popup.js
```

## 范围

- 支持检测 DOM 视频地址、浏览器 performance media resources，以及 `.m3u8`、`.mpd`、`.mp4`、`.webm`、`.m4s`、`.ts`、抖音 `aweme/v1/play` 等网络媒体请求。
- 对 `blob:` 视频会回退到把当前页面 URL 发送给本机 App，由后端 `yt-dlp` 继续解析。
- “站点 Cookie”关闭时不会读取或发送当前站点 Cookie。
- 插件只请求 `127.0.0.1:8483` 或 `localhost:8483` 的本机 App。
- 不绕过 DRM、付费墙、验证码或站点访问规则。
