# -*- coding: utf-8 -*-
"""
Bilibili API 客户端
"""

import json
from typing import Any, Dict, Optional, Tuple, Union
from urllib.parse import urlencode

import httpx
from playwright.async_api import BrowserContext, Page

from .exception import DataFetchError
from app.utils.bili_logger import logger
from .help import BilibiliSign
from app.utils.browser_util import convert_cookies


class BilibiliClient:
    """B站API客户端"""
    
    def __init__(
        self,
        timeout: int = 60,
        proxy: Optional[str] = None,
        headers: Dict[str, str] = None,
        playwright_page: Page = None,
        cookie_dict: Dict[str, str] = None,
    ):
        self.proxy = proxy
        self.timeout = timeout
        self.headers = headers or {}
        self._host = "https://api.bilibili.com"
        self.playwright_page = playwright_page
        self.cookie_dict = cookie_dict or {}

    async def request(self, method: str, url: str, **kwargs) -> Any:
        """发送HTTP请求"""
        async with httpx.AsyncClient(proxy=self.proxy) as client:
            response = await client.request(
                method, url, timeout=self.timeout, **kwargs
            )
        
        try:
            data: Dict = response.json()
        except json.JSONDecodeError:
            logger.error(f"JSON解码失败. status_code: {response.status_code}, response: {response.text}")
            raise DataFetchError(f"JSON解码失败: {response.text}")
        
        if data.get("code") != 0:
            raise DataFetchError(data.get("message", "未知错误"))
        
        return data.get("data", {})

    async def get_wbi_keys(self) -> Tuple[str, str]:
        """获取最新的 img_key 和 sub_key"""
        local_storage = await self.playwright_page.evaluate("() => window.localStorage")
        wbi_img_urls = local_storage.get("wbi_img_urls", "")
        
        if not wbi_img_urls:
            img_url_from_storage = local_storage.get("wbi_img_url")
            sub_url_from_storage = local_storage.get("wbi_sub_url")
            if img_url_from_storage and sub_url_from_storage:
                wbi_img_urls = f"{img_url_from_storage}-{sub_url_from_storage}"
        
        if wbi_img_urls and "-" in wbi_img_urls:
            img_url, sub_url = wbi_img_urls.split("-")
        else:
            resp = await self.request(method="GET", url=self._host + "/x/web-interface/nav")
            img_url: str = resp['wbi_img']['img_url']
            sub_url: str = resp['wbi_img']['sub_url']
        
        img_key = img_url.rsplit('/', 1)[1].split('.')[0]
        sub_key = sub_url.rsplit('/', 1)[1].split('.')[0]
        return img_key, sub_key

    async def pre_request_data(self, req_data: Dict) -> Dict:
        """为请求数据添加签名"""
        if not req_data:
            return {}
        
        img_key, sub_key = await self.get_wbi_keys()
        return BilibiliSign(img_key, sub_key).sign(req_data)

    async def get(self, uri: str, params: Dict = None, enable_params_sign: bool = True) -> Dict:
        """GET 请求"""
        final_uri = uri
        if enable_params_sign and params:
            params = await self.pre_request_data(params)
        
        if isinstance(params, dict):
            final_uri = f"{uri}?{urlencode(params)}"
        
        return await self.request(method="GET", url=f"{self._host}{final_uri}", headers=self.headers)

    async def pong(self) -> bool:
        """检查登录状态"""
        logger.info("检查B站登录状态...")
        try:
            check_login_uri = "/x/web-interface/nav"
            response = await self.get(check_login_uri, enable_params_sign=False)
            if response.get("isLogin"):
                logger.info("登录状态有效!")
                return True
        except Exception as e:
            logger.error(f"登录状态检查失败: {e}")
        
        return False

    async def update_cookies(self, browser_context: BrowserContext):
        """更新cookies"""
        cookie_str, cookie_dict = convert_cookies(await browser_context.cookies())
        self.headers["Cookie"] = cookie_str
        self.cookie_dict = cookie_dict

    async def get_video_info(
        self, 
        aid: Union[int, None] = None, 
        bvid: Union[str, None] = None
    ) -> Dict:
        """
        获取视频详情信息
        
        Args:
            aid: 视频aid
            bvid: 视频bvid (BV号)
        """
        if not aid and not bvid:
            raise ValueError("请至少提供 aid 或 bvid 其中一个参数")

        uri = "/x/web-interface/view/detail"
        params = dict()
        if aid:
            params.update({"aid": aid})
        else:
            params.update({"bvid": bvid})
        
        return await self.get(uri, params, enable_params_sign=False)

    async def get_video_play_url(self, aid: int, cid: int, qn: int = 80) -> Dict:
        """
        获取视频播放URL
        
        Args:
            aid: 视频aid
            cid: 视频cid
            qn: 清晰度 (16=360p, 32=480p, 64=720p, 80=1080p)
        """
        if not aid or not cid or aid <= 0 or cid <= 0:
            raise ValueError("aid 和 cid 必须存在且大于0")

        uri = "/x/player/wbi/playurl"
        params = {
            "avid": aid,
            "cid": cid,
            "qn": qn,
            "fourk": 1,
            "fnval": 1,
            "platform": "pc",
        }

        return await self.get(uri, params, enable_params_sign=True)

    async def get_video_media(self, url: str) -> Union[bytes, None]:
        """
        下载视频内容
        
        Args:
            url: 视频URL
        
        Returns:
            视频字节内容
        """
        async with httpx.AsyncClient(proxy=self.proxy, follow_redirects=True) as client:
            try:
                response = await client.request(
                    "GET", url, timeout=self.timeout, headers=self.headers
                )
                response.raise_for_status()
                if 200 <= response.status_code < 300:
                    return response.content
                
                logger.error(f"下载失败，状态码: {response.status_code}, URL: {url}")
                return None
            except httpx.HTTPError as exc:
                logger.error(f"下载视频出错: {exc}")
                return None
