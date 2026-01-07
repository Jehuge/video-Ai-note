# -*- coding: utf-8 -*-
"""
Bilibili 登录模块
"""

import asyncio
import sys
from typing import Optional

from playwright.async_api import BrowserContext, Page
from tenacity import RetryError, retry, retry_if_result, stop_after_attempt, wait_fixed

from app.utils.bili_logger import logger
from app.utils.browser_util import convert_cookies


class BilibiliLogin:
    """B站登录类"""
    
    def __init__(
        self,
        browser_context: BrowserContext,
        context_page: Page,
    ):
        self.browser_context = browser_context
        self.context_page = context_page

    async def begin(self):
        """开始登录"""
        logger.info("开始登录 Bilibili...")
        await self.login_by_qrcode()

    @retry(
        stop=stop_after_attempt(600),
        wait=wait_fixed(1),
        retry=retry_if_result(lambda value: value is False)
    )
    async def check_login_state(self) -> bool:
        """
        检查登录状态
        重试装饰器会在返回False时重试600次，间隔1秒
        """
        current_cookie = await self.browser_context.cookies()
        _, cookie_dict = convert_cookies(current_cookie)
        
        if cookie_dict.get("SESSDATA", "") or cookie_dict.get("DedeUserID"):
            return True
        
        return False

    async def login_by_qrcode(self):
        """二维码登录"""
        logger.info("使用二维码登录 Bilibili...")

        # 点击登录按钮
        login_button_ele = self.context_page.locator(
            "xpath=//div[@class='right-entry__outside go-login-btn']//div"
)
        await login_button_ele.click()
        await asyncio.sleep(1)

        # 查找二维码
        qrcode_img_selector = "//div[@class='login-scan-box']//img"
        
        try:
            # 等待二维码元素出现
            elements = await self.context_page.wait_for_selector(
                selector=qrcode_img_selector,
                timeout=10000
            )
            
            # 显示二维码（在终端输出提示）
            logger.info("=" * 50)
            logger.info("请使用 Bilibili APP 扫描浏览器中的二维码登录")
            logger.info("=" * 50)
            
        except Exception as e:
            logger.error(f"未找到登录二维码: {e}")
            sys.exit()

        logger.info("等待扫码登录，最多等待10分钟...")
        try:
            await self.check_login_state()
        except RetryError:
            logger.error("二维码登录超时失败")
            sys.exit()

        wait_redirect_seconds = 5
        logger.info(f"登录成功! 等待 {wait_redirect_seconds} 秒后继续...")
        await asyncio.sleep(wait_redirect_seconds)
