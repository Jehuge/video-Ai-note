# -*- coding: utf-8 -*-
"""
Bilibili 视频下载器
"""

import asyncio
import os
import pathlib
from typing import Dict, List

import aiofiles
from playwright.async_api import async_playwright, BrowserContext, Page

from .client import BilibiliClient
from .login import BilibiliLogin
from .help import parse_video_info_from_url
from .exception import DataFetchError
from app.utils.bili_logger import logger
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
    
    def set_config(self, config: Dict):
        """设置配置（API模式）"""
        self.api_config = config
    
    def set_video_list(self, video_list: List[str]):
        """设置视频列表（API模式）"""
        self.video_list = video_list
    
    def set_task_manager(self, task_manager):
        """设置任务管理器"""
        self.task_manager = task_manager

    async def start(self):
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
        
        # 登录
        await self.login()
        
        # 下载视频
        await self.download_videos()
        
        # 关闭浏览器
        await self.cleanup()
        
        logger.info("=" * 60)
        logger.info("所有任务完成!")
        logger.info("=" * 60)
    
    async def cleanup(self):
        """清理资源"""
        if self.browser_context:
            await self.browser_context.close()
        if self.playwright:
            await self.playwright.stop()

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
        
        for idx, video_url in enumerate(video_list, 1):
            logger.info(f"\n[{idx}/{len(video_list)}] 处理: {video_url}")
            
            # 更新任务进度
            if self.task_manager:
                self.task_manager.update_progress(video_url, idx - 1, 0)
            
            try:
                # 更新数据库状态为下载中
                video_info = parse_video_info_from_url(video_url)
                bili_dao.update_bili_video_status(video_info.video_id, "running")

                result = await self.download_single_video(video_url)
                
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
                    self.task_manager.update_progress(video_url, idx, 100)
                
                # 下载间隔
                if idx < len(video_list):
                    logger.info(f"等待 {download_interval} 秒后继续...")
                    await asyncio.sleep(download_interval)
                    
            except Exception as e:
                logger.error(f"下载视频失败 {video_url}: {e}")
                # 更新数据库状态为失败
                try:
                    video_info = parse_video_info_from_url(video_url)
                    bili_dao.update_bili_video_status(video_info.video_id, "failed")
                except:
                    pass
                continue

    async def download_single_video(self, video_url: str):
        """下载单个视频"""
        # 解析视频ID
        video_info = parse_video_info_from_url(video_url)  
        bvid = video_info.video_id
        
        logger.info(f"获取视频信息: {bvid}")
        
        # 获取视频详情
        video_detail = await self.bili_client.get_video_info(bvid=bvid)
        video_view = video_detail.get("View", {})
        
        aid = video_view.get("aid")
        cid = video_view.get("cid")
        title = video_view.get("title", bvid)
        
        logger.info(f"视频标题: {title}")
        logger.info(f"aid={aid}, cid={cid}")
        
        # 获取播放URL
        video_quality = self.api_config.get('video_quality', 80) if self.api_config else 80
        logger.info(f"获取播放地址（清晰度: {video_quality}）...")
        play_url_result = await self.bili_client.get_video_play_url(
            aid=aid,
            cid=cid,
            qn=video_quality
        )
        
        if not play_url_result:
            logger.error("获取播放地址失败")
            return
        
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
            bvid=bvid,
            title=title,
            content=video_content
        )
        
        return {
            "bv_id": bvid,
            "title": title,
            "file_path": str(file_path),
            "file_size": len(video_content),
            "quality": video_quality
        }

    async def save_video(self, bvid: str, title: str, content: bytes):
        """保存视频到本地"""
        # 创建下载目录
        download_path = self.api_config.get('download_path', 'uploads') if self.api_config else 'uploads'
        download_dir = pathlib.Path(download_path)
        download_dir.mkdir(parents=True, exist_ok=True)
        
        # 清理文件名中的非法字符
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_', '(', ')'))
        safe_title = safe_title[:50]  # 限制文件名长度
        
        # 生成文件名
        filename = f"{safe_title}_{bvid}.mp4"
        filepath = download_dir / filename
        
        # 保存文件
        async with aiofiles.open(filepath, 'wb') as f:
            await f.write(content)
        
        logger.info(f"✅ 视频已保存: {filepath}")
        return filepath, filename
