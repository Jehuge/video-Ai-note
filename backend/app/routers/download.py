import asyncio
import base64
import json
import os
import shutil
import subprocess
import tempfile
import uuid
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

# 用于跟踪登录会话
_login_sessions: dict = {}


class DownloadRequest(BaseModel):
    url: str
    cookie: Optional[str] = ''
    quality: Optional[str] = 'best'


class StartLoginResponse(BaseModel):
    session_id: str
    qr_image_base64: str


@router.post("/download/bilibili/start_login", response_model=StartLoginResponse)
async def start_bilibili_login():
    """
    使用 Playwright 打开哔哩哔哩登录页面，截取二维码并返回 base64 图片以及 session_id。
    后续客户端应定期轮询 /download/bilibili/login_status?session_id=... 来检查是否登录成功。
    """
    try:
        from playwright.async_api import async_playwright
    except Exception as e:
        logger.error("Playwright 未安装: %s", e)
        raise HTTPException(status_code=500, detail="服务器未安装 playwright，请安装并运行 'playwright install' 后重试")

    session_id = uuid.uuid4().hex
    tmpdir = Path(tempfile.mkdtemp(prefix=f"bili_login_{session_id}_"))
    qr_path = tmpdir / "qr.png"
    storage_path = tmpdir / "storage_state.json"

    async def _login_task():
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=False)
                context = await browser.new_context()
                page = await context.new_page()
                await page.goto("https://passport.bilibili.com/login")

                # 等待二维码元素出现并截图
                try:
                    qr_el = await page.wait_for_selector("img.qrcode-img, img[data-type='qrcode']", timeout=15000)
                except Exception:
                    # 有时候页面需要点击“二维码登录”切换
                    try:
                        btn = await page.query_selector("a[href*='qrcode']")
                        if btn:
                            await btn.click()
                            qr_el = await page.wait_for_selector("img.qrcode-img, img[data-type='qrcode']", timeout=10000)
                        else:
                            qr_el = None
                    except Exception:
                        qr_el = None

                if qr_el:
                    await qr_el.screenshot(path=str(qr_path))
                else:
                    # fallback：截图整个页面
                    await page.screenshot(path=str(qr_path), full_page=False)

                # 轮询等待登录完成（检查是否存在登录用户的 cookie）
                logged_in = False
                for _ in range(180):  # 最多等待 ~180*1s = 3分钟
                    cookies = await context.cookies()
                    # 寻找 bilibili 的 sessdata 或 buvid3 等
                    if any(c.get("name", "").lower() in ("sessdata", "bili_jct", "buvid3") for c in cookies):
                        logged_in = True
                        await context.storage_state(path=str(storage_path))
                        break
                    await asyncio.sleep(1)

                # 关闭浏览器
                await browser.close()
                # 标记会话
                _login_sessions[session_id]["finished"] = logged_in
                if logged_in:
                    _login_sessions[session_id]["storage"] = str(storage_path)
                else:
                    _login_sessions[session_id]["storage"] = None
        except Exception as e:
            logger.exception("Playwright 登录任务失败: %s", e)
            _login_sessions[session_id]["error"] = str(e)

    # 保存会话元信息并启动后台任务
    _login_sessions[session_id] = {
        "tmpdir": str(tmpdir),
        "qr_path": str(qr_path),
        "storage": None,
        "finished": False,
        "error": None,
    }

    # 启动播放（后台任务）
    asyncio.create_task(_login_task())

    # 等待短暂时间让 qr.png 生成
    for _ in range(20):
        if qr_path.exists():
            break
        await asyncio.sleep(0.2)

    if not qr_path.exists():
        raise HTTPException(status_code=500, detail="无法生成二维码图片，请检查 Playwright 是否可用")

    b64 = base64.b64encode(qr_path.read_bytes()).decode("utf-8")
    return {"session_id": session_id, "qr_image_base64": b64}


@router.get("/download/bilibili/login_status")
async def bilibili_login_status(session_id: str):
    """
    查询登录状态，返回 { finished: bool, error: str|null }
    """
    sess = _login_sessions.get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="session_id 未找到")
    return {"finished": bool(sess.get("finished")), "error": sess.get("error")}


def _write_netscape_cookies(cookies, out_path: str):
    """
    将 Playwright storage_state 中的 cookies 写入 Netscape cookies.txt 格式，供 yt-dlp 使用 --cookies 参数。
    """
    lines = []
    for c in cookies:
        domain = c.get("domain", "")
        flag = "TRUE" if domain.startswith(".") else "FALSE"
        path = c.get("path", "/")
        secure = "TRUE" if c.get("secure", False) else "FALSE"
        expires = str(int(c.get("expires", 0))) if c.get("expires") else "0"
        name = c.get("name", "")
        value = c.get("value", "")
        lines.append("\t".join([domain, flag, path, secure, expires, name, value]))
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("# Netscape HTTP Cookie File\n")
        fh.write("\n".join(lines))


@router.post("/download/bilibili")
async def download_bilibili(req: DownloadRequest, background_tasks: BackgroundTasks):
    """
    最终下载接口。优先尝试使用提供的 cookie（或直接使用 yt-dlp），
    如果传入 session_id（来自登录流程），将使用 Playwright 保存下来的 storage_state 中的 cookie。
    """
    url = req.url
    cookie = (req.cookie or "").strip()
    quality = req.quality or "best"

    # 检查 yt-dlp
    try:
        subprocess.run(["yt-dlp", "--version"], capture_output=True, text=True, check=True)
    except Exception as e:
        logger.error("yt-dlp 未安装或不可用: %s", e)
        raise HTTPException(status_code=500, detail="服务器未安装 yt-dlp，请先安装 yt-dlp 后重试")

    # 如果 cookie 字符串看起来是 session_id（我们在 start_login 中返回），优先使用 storage_state
    storage_state_path = None
    if cookie and cookie.startswith("session:"):
        session_id = cookie.split("session:", 1)[1]
        sess = _login_sessions.get(session_id)
        if not sess:
            raise HTTPException(status_code=400, detail="无效的 session_id")
        if not sess.get("finished") or not sess.get("storage"):
            raise HTTPException(status_code=400, detail="会话尚未完成登录")
        storage_state_path = sess.get("storage")

    # 如果提供了 storage_state_path，读取 cookies 并写为 cookies.txt
    cookies_file = None
    if storage_state_path:
        try:
            with open(storage_state_path, "r", encoding="utf-8") as fh:
                st = json.load(fh)
            cookies = st.get("cookies", [])
            cookies_file = tempfile.mktemp(prefix="bili_cookies_", suffix=".txt")
            _write_netscape_cookies(cookies, cookies_file)
        except Exception as e:
            logger.exception("读取 storage_state 失败: %s", e)
            raise HTTPException(status_code=500, detail="读取登录会话的 cookie 失败")

    # 如果直接提供了 cookie 字符串（纯 Netscape 或 "name=val; ..."），使用 --add-header 或 --cookies
    cmd = ["yt-dlp", "-j", url]
    if cookies_file:
        cmd += ["--cookies", cookies_file]
    elif cookie:
        # 简单地将原始 Cookie 字符串作为请求头传入
        cmd += ["--add-header", f"Cookie: {cookie}"]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=120)
        info_json = json.loads(proc.stdout)
    except subprocess.CalledProcessError as e:
        logger.error("yt-dlp 获取信息失败: %s %s", e, e.stderr)
        raise HTTPException(status_code=500, detail=f"解析视频信息失败: {e.stderr[:200]}")
    except Exception as e:
        logger.exception("解析 yt-dlp 输出失败: %s", e)
        raise HTTPException(status_code=500, detail="解析视频信息失败")

    # 清理临时 cookies 文件（延迟清理）
    if cookies_file:
        background_tasks.add_task(lambda p: os.remove(p) if os.path.exists(p) else None, cookies_file)

    # 选择格式（与之前逻辑相同）
    formats = info_json.get("formats", []) or []
    selected = None
    if quality == "best":
        formats_with_height = [f for f in formats if f.get("height")]
        if formats_with_height:
            formats_with_height.sort(key=lambda x: (x.get("height") or 0, x.get("tbr") or 0), reverse=True)
            selected = formats_with_height[0]
    else:
        try:
            target_h = int(quality.replace("p", ""))
            cand = [f for f in formats if (f.get("height") or 0) == target_h]
            if cand:
                cand.sort(key=lambda x: x.get("tbr") or 0, reverse=True)
                selected = cand[0]
        except Exception:
            selected = None

    if not selected:
        if info_json.get("url"):
            return {"download_url": info_json.get("url"), "filename": info_json.get("title")}
        if formats:
            formats.sort(key=lambda x: (x.get("filesize") or 0, x.get("tbr") or 0), reverse=True)
            selected = formats[0]

    if not selected:
        raise HTTPException(status_code=500, detail="未能找到可下载的格式")

    download_url = selected.get("url")
    filename = info_json.get("title") or "video"
    ext = selected.get("ext")
    if ext:
        filename = f"{filename}.{ext}"

    return {"download_url": download_url, "filename": filename, "format_note": selected.get("format_note")}


