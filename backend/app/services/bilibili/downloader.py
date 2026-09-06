# -*- coding: utf-8 -*-
"""
Bilibili 视频下载器
"""

import asyncio
import os
import pathlib
import subprocess
import sys
import threading
from typing import Dict, List

import aiofiles
from playwright.async_api import async_playwright, BrowserContext, Page

from .client import BilibiliClient
from .login import BilibiliLogin
from .help import parse_video_info_from_url
from .exception import DataFetchError
from app.utils.bili_logger import logger
from app.utils.ffmpeg_helper import get_ffmpeg_path, hidden_subprocess_kwargs
from app.db import bili_dao


class BilibiliDownloader:
    """B站视频下载器"""
    
    def __init__(self):
        self.index_url = "https://www.bilibili.com"
        self.user_data_dir = "bilibili_user_data"  # 默认值
        self.browser_context: BrowserContext = None
        self.context_page: Page = None
        self.bili_client: BilibiliClient = None
        self.playwright = None
        
        # API模式的配置
        self.api_config: Dict = None
        self.video_list: List[str] = None
        self.task_manager = None
        self._stop_requested = threading.Event()
        self._worker_loop: asyncio.AbstractEventLoop = None

    def set_config(self, config: Dict):
        """设置配置（API模式）"""
        self.api_config = config
    
    def set_video_list(self, video_list: List[str]):
        """设置视频列表（API模式）"""
        self.video_list = video_list
    
    def set_task_manager(self, task_manager):
        """设置任务管理器"""
        self.task_manager = task_manager

    def request_stop(self):
        """请求停止下载（线程安全）"""
        self._stop_requested.set()

    async def start(self):
        """启动下载器"""
        # PDF export no longer needs a browser. Install/check Chromium only
        # when the user actually starts the legacy Bilibili workflow.
        await self._ensure_chromium_available()
        if sys.platform == "win32":
            # uvicorn reload 模式在 Windows 上强制切换到 SelectorEventLoop，
            # 该循环不支持子进程，Playwright 启动 driver 会抛 NotImplementedError。
            # 因此在独立线程中用支持子进程的 ProactorEventLoop 运行下载流程。
            await asyncio.get_running_loop().run_in_executor(
                None, self._start_with_proactor
            )
        else:
            await self._start_impl()

    async def _ensure_chromium_available(self):
        """Ensure Playwright's browser exists without blocking app startup."""
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                await browser.close()
            return
        except Exception as first_error:
            logger.warning("Playwright Chromium 不可用，尝试按需安装: %s", first_error)

        from playwright._impl._driver import compute_driver_executable, get_driver_env

        driver_executable, driver_cli = compute_driver_executable()
        kwargs = hidden_subprocess_kwargs()
        result = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: subprocess.run(
                [driver_executable, driver_cli, "install", "chromium"],
                capture_output=True,
                text=True,
                check=False,
                env=get_driver_env(),
                timeout=600,
                **kwargs,
            ),
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip().splitlines()[-1:]
            raise RuntimeError(
                f"Playwright Chromium 安装失败{': ' + detail[0] if detail else ''}"
            )
        logger.info("Playwright Chromium 按需安装完成")

    def _start_with_proactor(self):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        self._worker_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._worker_loop)
        try:
            self._worker_loop.run_until_complete(self._start_impl())
        finally:
            asyncio.set_event_loop(None)
            self._worker_loop.close()
            self._worker_loop = None

    async def _start_impl(self):
        """启动下载器"""
        logger.info("=" * 60)
        logger.info("Bilibili 视频下载器启动")
        logger.info("=" * 60)
        
        # 启动浏览器
        self.playwright = await async_playwright().start()
        chromium = self.playwright.chromium
        
        # 获取配置
        headless = self.api_config.get('headless', False) if self.api_config else False
        
        # 创建浏览器上下文
        self.browser_context = await chromium.launch_persistent_context(
            user_data_dir=self.user_data_dir,
            headless=headless,
            viewport={"width": 1920, "height": 1080},
        )
        
        self.context_page = await self.browser_context.new_page()
        await self.context_page.goto(self.index_url)
        
        # 创建客户端
        timeout = self.api_config.get('request_timeout', 60) if self.api_config else 60
        self.bili_client = BilibiliClient(
            timeout=timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Referer": "https://www.bilibili.com",
            },
            playwright_page=self.context_page,
        )

        try:
            # 登录
            await self.login()

            # 下载视频
            await self.download_videos()
        finally:
            # 关闭浏览器
            await self._cleanup_impl()

        logger.info("=" * 60)
        logger.info("所有任务完成!")
        logger.info("=" * 60)

    async def cleanup(self):
        """清理资源（支持从其他线程/事件循环调用）"""
        worker_loop = self._worker_loop
        if worker_loop and worker_loop.is_running():
            fut = asyncio.run_coroutine_threadsafe(self._cleanup_impl(), worker_loop)
            await asyncio.wrap_future(fut)
        else:
            await self._cleanup_impl()

    async def _cleanup_impl(self):
        """清理资源"""
        if self.browser_context:
            await self.browser_context.close()
            self.browser_context = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None

    async def login(self):
        """登录B站"""
        # 更新cookies
        await self.bili_client.update_cookies(self.browser_context)
        
        # 检查登录状态
        if await self.bili_client.pong():
            logger.info("使用已保存的登录状态")
            return
        
        # 需要登录
        login_obj = BilibiliLogin(
            browser_context=self.browser_context,
            context_page=self.context_page,
        )
        
        await login_obj.begin()
        await self.bili_client.update_cookies(self.browser_context)

    async def download_videos(self):
        """下载视频列表"""
        # 使用API传入的视频列表
        video_list = self.video_list if self.video_list else []

        if not video_list:
            logger.warning("视频列表为空")
            return

        # 获取下载间隔配置
        download_interval = self.api_config.get('download_interval', 2) if self.api_config else 2

        logger.info(f"开始下载 {len(video_list)} 个视频...")

        for idx, queue_id in enumerate(video_list, 1):
            if self._stop_requested.is_set():
                logger.info("收到停止请求，终止剩余下载")
                break

            logger.info(f"\n[{idx}/{len(video_list)}] 处理: {queue_id}")

            # 更新任务进度
            if self.task_manager:
                await self.task_manager.update_progress(queue_id, idx - 1, 0)

            try:
                # 更新数据库状态为下载中
                bili_dao.update_bili_video_status(queue_id, "running")

                result = await self.download_single_video(queue_id)

                if result:
                    # 更新数据库状态为已完成
                    bili_dao.update_bili_video_status(
                        result["bv_id"],
                        "downloaded",
                        title=result["title"]
                    )

                    # 添加下载历史
                    bili_dao.add_bili_download_history(
                        bv_id=result["bv_id"],
                        title=result["title"],
                        file_path=result["file_path"],
                        file_size=result["file_size"],
                        quality=result["quality"]
                    )

                # 更新完成进度
                if self.task_manager:
                    await self.task_manager.update_progress(queue_id, idx, 100)

                # 下载间隔
                if idx < len(video_list):
                    logger.info(f"等待 {download_interval} 秒后继续...")
                    await asyncio.sleep(download_interval)

            except Exception as e:
                logger.error(f"下载视频失败 {queue_id}: {e}")
                # 更新数据库状态为失败
                try:
                    bili_dao.update_bili_video_status(queue_id, "failed")
                except:
                    pass
                continue

    async def download_single_video(self, video_url: str):
        """下载单个视频（支持分P：队列条目为 BV号 或 BV号_pN）"""
        video_info = parse_video_info_from_url(video_url)
        bvid = video_info.video_id
        page = video_info.page

        logger.info(f"获取视频信息: {bvid} (P{page})")

        # 获取视频详情
        video_detail = await self.bili_client.get_video_info(bvid=bvid)
        video_view = video_detail.get("View", {})

        aid = video_view.get("aid")
        title = video_view.get("title", bvid)
        pages = video_view.get("pages") or []

        # 多P视频按分P定位cid
        if pages and (page > 1 or len(pages) > 1):
            page_info = next((pg for pg in pages if pg.get("page") == page), None)
            if page_info is None:
                raise DataFetchError(
                    f"视频 {bvid} 不存在第 {page} 个分P（共 {len(pages)} 个分P）"
                )
            cid = page_info.get("cid")
            part_name = page_info.get("part") or ""
            title = f"{title} P{page} {part_name}".strip()
            logger.info(f"分P标题: {part_name}")
        else:
            cid = video_view.get("cid")

        if not aid or not cid:
            logger.error(f"获取视频信息失败: aid={aid}, cid={cid}")
            return

        logger.info(f"视频标题: {title}")
        logger.info(f"aid={aid}, cid={cid}")

        # 获取播放URL
        video_quality = self.api_config.get('video_quality', 80) if self.api_config else 80
        logger.info(f"获取播放地址（期望清晰度: {video_quality}）...")
        play_url_result = await self.bili_client.get_video_play_url(
            aid=aid,
            cid=cid,
            qn=video_quality
        )

        if not play_url_result:
            logger.error("获取播放地址失败")
            return

        # DASH 格式（现代默认）：视频流+音频流分离，下载后用 ffmpeg 合并
        dash = play_url_result.get("dash")
        if dash:
            return await self._download_dash(dash, video_url, title, video_quality)

        # 旧版 durl 格式兜底
        durl_list = play_url_result.get("durl", [])
        if not durl_list:
            logger.error("未找到可用的播放地址")
            return

        # 选择最大尺寸的视频
        max_size = -1
        video_url = ""
        for durl in durl_list:
            size = durl.get("size", 0)
            if size > max_size:
                max_size = size
                video_url = durl.get("url")

        if not video_url:
            logger.error("未找到视频URL")
            return

        logger.info(f"视频大小: {max_size / 1024 / 1024:.2f} MB")

        # 下载视频
        logger.info("开始下载视频...")
        video_content = await self.bili_client.get_video_media(video_url)

        if not video_content:
            logger.error("下载视频内容失败")
            return

        # 保存视频
        file_path, filename = await self.save_video(
            bvid=video_url,
            title=title,
            content=video_content
        )

        return {
            "bv_id": video_url,
            "title": title,
            "file_path": str(file_path),
            "file_size": len(video_content),
            "quality": video_quality
        }

    # ==================== DASH 下载 ====================

    QUALITY_NAMES = {
        16: "360p", 32: "480p", 64: "720p", 74: "720p60", 80: "1080p",
        112: "1080p+", 116: "1080p60", 120: "4K", 125: "HDR", 126: "杜比视界", 127: "8K",
    }

    def _pick_dash_video(self, dash: Dict, requested_qn: int):
        """从 DASH 视频流中选出目标清晰度：优先选不高于期望清晰度的最高档，没有则选最高可用档"""
        by_qn = {}
        for stream in dash.get("video") or []:
            qn = stream.get("id")
            if qn is None:
                continue
            # 同一清晰度可能有多条不同编码的流，取带宽最高的
            if qn not in by_qn or stream.get("bandwidth", 0) > by_qn[qn].get("bandwidth", 0):
                by_qn[qn] = stream

        if not by_qn:
            return None, None

        available = sorted(by_qn.keys(), reverse=True)
        # 不高于期望清晰度的最高档；如果所有可用档位都高于期望，取最低档
        chosen = next((qn for qn in available if qn <= requested_qn), None)
        if chosen is None:
            chosen = available[-1]
        return by_qn[chosen], chosen

    def _pick_dash_audio(self, dash: Dict):
        """选带宽最高的音频流"""
        audios = dash.get("audio") or []
        if not audios:
            return None
        return max(audios, key=lambda a: a.get("bandwidth", 0))

    def _get_download_dir(self) -> pathlib.Path:
        download_path = self.api_config.get('download_path', 'uploads') if self.api_config else 'uploads'
        download_dir = pathlib.Path(download_path)
        if not download_dir.is_absolute():
            # 相对路径统一落到应用数据目录的 uploads（UPLOAD_DIR），
            # 前端通过 /api/uploads/<文件名> 访问这些文件
            download_dir = pathlib.Path(os.getenv("UPLOAD_DIR", download_path))
        download_dir.mkdir(parents=True, exist_ok=True)
        return download_dir

    @staticmethod
    def _safe_title(title: str) -> str:
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_', '(', ')'))
        # 保留尾部：多P视频的 "P167 分P名" 在标题末尾，截头部不会丢关键信息
        return safe_title[-50:] if len(safe_title) > 50 else safe_title

    async def _download_dash(self, dash: Dict, queue_id: str, title: str, requested_qn: int):
        """下载 DASH 视频流+音频流并用 ffmpeg 合并"""
        video_stream, chosen_qn = self._pick_dash_video(dash, requested_qn)
        if not video_stream:
            logger.error("DASH 响应中没有可用的视频流")
            return None

        if chosen_qn != requested_qn:
            qn_name = self.QUALITY_NAMES.get(chosen_qn, str(chosen_qn))
            logger.warning(f"期望清晰度 {requested_qn} 不可用，自动使用最高可用清晰度: {qn_name}")
        else:
            logger.info(f"清晰度: {self.QUALITY_NAMES.get(chosen_qn, str(chosen_qn))}")

        audio_stream = self._pick_dash_audio(dash)
        download_dir = self._get_download_dir()
        video_tmp = download_dir / f".{queue_id}.video.m4s"
        audio_tmp = download_dir / f".{queue_id}.audio.m4s"

        try:
            video_url = video_stream.get("baseUrl") or video_stream.get("base_url")
            logger.info("开始下载视频流...")
            if not await self.bili_client.download_media_to_file(video_url, video_tmp):
                logger.error("下载视频流失败")
                return None

            if audio_stream:
                logger.info("开始下载音频流...")
                audio_url = audio_stream.get("baseUrl") or audio_stream.get("base_url")
                if not await self.bili_client.download_media_to_file(audio_url, audio_tmp):
                    logger.error("下载音频流失败")
                    return None

            # 生成输出文件名：队列ID（含分P号）放最前，系列名再长也不会截掉 P 号
            filename = f"{queue_id}_{self._safe_title(title)}.mp4"
            output_path = download_dir / filename

            logger.info("合并视频与音频...")
            if not self._merge_av(video_tmp, audio_tmp, output_path):
                logger.error("合并失败")
                return None

            logger.info(f"✅ 视频已保存: {output_path}")
            return {
                "bv_id": queue_id,
                "title": title,
                "file_path": str(output_path),
                "file_size": output_path.stat().st_size,
                "quality": chosen_qn
            }
        finally:
            for tmp in (video_tmp, audio_tmp):
                try:
                    if tmp.exists():
                        tmp.unlink()
                except OSError:
                    pass

    @staticmethod
    def _merge_av(video_path: pathlib.Path, audio_path: pathlib.Path, output_path: pathlib.Path) -> bool:
        """用 ffmpeg 将视频流和音频流无损合并为 mp4"""
        cmd = [
            get_ffmpeg_path(), "-y",
            "-i", str(video_path),
        ]
        if audio_path.exists():
            cmd += ["-i", str(audio_path)]
        cmd += ["-c", "copy", "-movflags", "+faststart", str(output_path)]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
                **hidden_subprocess_kwargs(),
            )
            if result.returncode != 0:
                logger.error(f"ffmpeg 合并失败: {(result.stderr or '')[-500:]}")
                return False
            return True
        except Exception as e:
            logger.error(f"ffmpeg 合并出错: {e}")
            return False

    async def save_video(self, bvid: str, title: str, content: bytes):
        """保存视频到本地"""
        download_dir = self._get_download_dir()

        # 生成文件名：队列ID（含分P号）放最前
        filename = f"{bvid}_{self._safe_title(title)}.mp4"
        filepath = download_dir / filename

        # 保存文件
        async with aiofiles.open(filepath, 'wb') as f:
            await f.write(content)

        logger.info(f"✅ 视频已保存: {filepath}")
        return filepath, filename
