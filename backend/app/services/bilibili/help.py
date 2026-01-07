# -*- coding: utf-8 -*-
"""
Bilibili 辅助函数
"""

import re
import urllib.parse
from hashlib import md5
from typing import Dict

from .models import VideoUrlInfo
from app.utils.time_util import get_unix_timestamp


class BilibiliSign:
    """WBI 签名类"""
    
    def __init__(self, img_key: str, sub_key: str):
        self.img_key = img_key
        self.sub_key = sub_key
        self.map_table = [
            46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
            33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
            61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
            36, 20, 34, 44, 52
        ]

    def get_salt(self) -> str:
        """获取加盐的密钥"""
        salt = ""
        mixin_key = self.img_key + self.sub_key
        for mt in self.map_table:
            salt += mixin_key[mt]
        return salt[:32]

    def sign(self, req_data: Dict) -> Dict:
        """
        为请求参数添加 WBI 签名
        """
        current_ts = get_unix_timestamp()
        req_data.update({"wts": current_ts})
        req_data = dict(sorted(req_data.items()))
        req_data = {
            k: ''.join(filter(lambda ch: ch not in "!'()*", str(v)))
            for k, v in req_data.items()
        }
        query = urllib.parse.urlencode(req_data)
        salt = self.get_salt()
        wbi_sign = md5((query + salt).encode()).hexdigest()
        req_data['w_rid'] = wbi_sign
        return req_data


def parse_video_info_from_url(url: str) -> VideoUrlInfo:
    """
    从 URL 中解析视频ID
    
    Args:
        url: B站视频链接或BV号
            - https://www.bilibili.com/video/BV1dwuKzmE26/
            - BV1d54y1g7db
    
    Returns:
        VideoUrlInfo: 包含视频ID的对象
    """
    # 如果输入已经是BV号，直接返回
    if url.startswith("BV"):
        return VideoUrlInfo(video_id=url)

    # 使用正则提取BV号
    bv_pattern = r'/video/(BV[a-zA-Z0-9]+)'
    match = re.search(bv_pattern, url)

    if match:
        video_id = match.group(1)
        return VideoUrlInfo(video_id=video_id)

    raise ValueError(f"无法从URL解析视频ID: {url}")
