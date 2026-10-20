"""Playwright 登录 blablalink，拿到 Cookie。

实测流程（2026-10-17）：
1. 打开首页 → 点右上角头像 → 弹层默认区服组「日本/韓國/北美/東南亞/全球」。
2. 填 #loginPwdForm_account / #loginPwdForm_password → 点「登入」。
3. 服务端返回 ret=2170 machine check err，弹腾讯拼图（drag_ele_global）。
4. 拖对后 localStorage["logined_account_cache_key"] 出现，解码可得
   openid / token / token_expire_time / channel_info.channelId。
5. 用最小 Cookie 调 CheckLogin，code=0 msg=ok。

滑块优先自动识别；识别失败时通过 on_captcha 回调把图交给网页，由用户拖。
"""
from __future__ import annotations

import asyncio
import base64
import json
import io
import random
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

import httpx

from ..nikke_api.auth import Credentials, build_cookie
from ..nikke_api.client import REGIONS
from .regions import selected_role

try:  # OpenCV 可选；没有就只走人工拖拽
    import cv2
    import numpy as np
except Exception:  # noqa: BLE001
    cv2 = None
    np = None

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0"
)
CHECK_LOGIN = "https://api.blablalink.com/api/user/CheckLogin"
LOGIN_CACHE_KEY = "logined_account_cache_key"


class LoginError(Exception):
    pass


class LoginTimeout(LoginError):
    pass


class LoginCancelled(LoginError):
    pass


@dataclass
class LoginResult:
    cookie: str
    openid: str
    token: str
    channel_id: str
    expire_at: int
    area_id: int
    area_label: str
    nickname: str
    uid: str
    role_name: str = ""


@dataclass
class CaptchaChallenge:
    """给网页人工拖拽用的验证码快照与图形位置。"""

    png: bytes
    width: int = 360
    height: int = 360
    piece: Optional[dict] = None
    hole: Optional[dict] = None
    slider: Optional[dict] = None


CaptchaHandler = Callable[[CaptchaChallenge], Awaitable[Optional[float]]]


def _i32(n: int) -> int:
    n &= 0xFFFFFFFF
    return n - 0x100000000 if n >= 0x80000000 else n


def _detect_puzzle(img, slider_cx: float | None = None):
    """返回 (左图形, 右图形, 调试图, 候选列表)。

    slider_cx 是滑块按钮中心 x。拼图块跟着滑块走，所以优先选离滑块最近的
    候选作为拼图块，再在它右侧找缺口；这能排除图片底部的小图标/装饰。
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.dilate(
        cv2.Canny(gray, 50, 150), np.ones((3, 3), np.uint8), iterations=1
    )
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    # 云层可能连上白色边框，再合入一组未模糊、未膨胀的弱边缘。
    raw_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    fine, _ = cv2.findContours(cv2.Canny(raw_gray, 30, 80), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = list(contours) + list(fine)
    # Pale polygon edges on textured backgrounds can be broken into short
    # segments. Close weak edges before looking for the matching pair.
    weak = cv2.morphologyEx(cv2.Canny(raw_gray, 20, 60), cv2.MORPH_CLOSE,
                           np.ones((3, 3), np.uint8))
    weak_contours, _ = cv2.findContours(weak, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours += list(weak_contours)
    h, w = gray.shape
    cands = []
    for c in contours:
        area = cv2.contourArea(c)
        if area < 250 or area > 5000:
            continue
        x, y, ww, hh = cv2.boundingRect(c)
        if ww < 28 or hh < 28 or ww > 80 or hh > 80:
            continue
        if not (0.55 <= ww / hh <= 1.8):
            continue
        if y < h * 0.18 or y > h * 0.78:
            continue
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.03 * peri, True)
        if not (3 <= len(approx) <= 8):
            continue
        cands.append(
            {
                "x": x,
                "y": y,
                "w": ww,
                "h": hh,
                "area": area,
                "cx": x + ww / 2,
                "cy": y + hh / 2,
                "vertices": len(approx),
            }
        )

    best = None
    for i in range(len(cands)):
        for j in range(i + 1, len(cands)):
            a, b = cands[i], cands[j]
            a, b = sorted((a, b), key=lambda c: c["cx"])
            if b["cx"] - a["cx"] < max(a["w"], b["w"]) or (slider_cx is not None and abs(a["cx"] - slider_cx) > 35):
                continue
            if abs(a["cy"] - b["cy"]) > 22:
                continue
            cost = abs(a["cy"] - b["cy"]) + 0.25 * (
                abs(a["w"] - b["w"]) + abs(a["h"] - b["h"])
            ) + (2 * abs(a["cx"] - slider_cx) if slider_cx is not None else 0)
            if best is None or cost < best[0]:
                best = (cost, a, b)
    dbg = img.copy()
    for c in cands:
        cv2.rectangle(dbg, (c["x"], c["y"]), (c["x"] + c["w"], c["y"] + c["h"]), (0, 0, 255), 1)
    if best:
        a, b = sorted([best[1], best[2]], key=lambda d: d["cx"])
        return a, b, dbg, cands
    return None, None, dbg, cands


def _detect_slider(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (95, 45, 120), (125, 255, 255))
    h, w = mask.shape
    mask[: int(h * 0.72), :] = 0
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    for c in contours:
        area = cv2.contourArea(c)
        if area < 400:
            continue
        x, y, ww, hh = cv2.boundingRect(c)
        if 25 <= ww <= 90 and 25 <= hh <= 70:
            if best is None or area > best["area"]:
                best = {
                    "cx": x + ww / 2,
                    "cy": y + hh / 2,
                    "area": area,
                    "w": ww,
                    "h": hh,
                }
    return best


def _analyze(img: bytes) -> tuple[CaptchaChallenge, Optional[tuple[float, float, float]]]:
    """返回验证码快照 + 自动拖拽参数 (dx, slider_x, slider_y)。"""
    if cv2 is None:
        from PIL import Image
        try:
            with Image.open(io.BytesIO(img)) as image:
                return CaptchaChallenge(png=img,width=image.width,height=image.height), None
        except OSError:
            return CaptchaChallenge(png=img), None
    arr = np.frombuffer(img, np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        return CaptchaChallenge(png=img), None

    height, width = bgr.shape[:2]
    # Detection thresholds are expressed at the provider's 360 CSS-pixel size.
    # Map results back to the actual screenshot; UI drag distance uses that
    # same coordinate system, never devicePixelRatio.
    scale = 360 / width
    analysis = cv2.resize(bgr, (360, max(1, round(height * scale)))) if width != 360 else bgr
    slider = _detect_slider(analysis)
    left, right, _, _ = _detect_puzzle(analysis, slider["cx"] if slider else None)
    def original(box):
        if box is None:
            return None
        return {key: value / scale if key in ('x', 'y', 'w', 'h', 'cx', 'cy') else value
                for key, value in box.items()}
    left, right, slider = original(left), original(right), original(slider)
    challenge = CaptchaChallenge(
        png=img,
        width=width,
        height=height,
        piece=left,
        hole=right,
        slider=slider,
    )
    if not left or not right or not slider:
        return challenge, None
    return challenge, (right["cx"] - left["cx"], slider["cx"], slider["cy"])


def _slider_from_image(img: bytes) -> Optional[tuple[float, float]]:
    if cv2 is None:
        return None
    arr = np.frombuffer(img, np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        return None
    slider = _detect_slider(bgr)
    if not slider:
        return None
    return slider["cx"], slider["cy"]


async def _human_drag(page, sx: float, sy: float, dx: float):
    await page.mouse.move(sx, sy)
    await asyncio.sleep(0.12)
    await page.mouse.down()
    steps = random.randint(28, 38)
    for i in range(1, steps + 1):
        t = i / steps
        ease = t * t * (3 - 2 * t)
        await page.mouse.move(
            sx + dx * ease + random.uniform(-0.6, 0.6),
            sy + random.uniform(-1.0, 1.0),
        )
        await asyncio.sleep(random.randint(8, 18) / 1000)
    await asyncio.sleep(random.randint(120, 260) / 1000)
    await page.mouse.up()


async def _find_captcha(ctx):
    for page in ctx.pages:
        for fr in page.frames:
            if "captcha" not in (fr.url or "").lower():
                continue
            try:
                el = await fr.frame_element()
                box = await el.bounding_box()
            except Exception:
                continue
            if box and box["width"] > 250 and box["height"] > 150:
                return page, el, box
    return None, None, None


def _captcha_image_ready(png: bytes) -> bool:
    """Reject blank/loading views without requiring successful puzzle detection."""
    from PIL import Image, ImageStat
    try:
        with Image.open(io.BytesIO(png)) as source:
            image = source.convert('RGB')
            w, h = image.size
            if w < 200 or h < 150:
                return False
            # A spinner or footer on an otherwise white panel is insufficient.
            image = image.crop((int(w*.08), int(h*.18), int(w*.92), int(h*.70)))
            tw, th = image.width//3, image.height//2
            textured = sum(max(ImageStat.Stat(image.crop((x*tw,y*th,(x+1)*tw,(y+1)*th))).stddev)>12
                           for y in range(2) for x in range(3))
            return textured >= 4
    except (OSError, ValueError):
        return False


async def _ready_captcha_shot(el):
    """Check image decode and visual content; return CSS-pixel screenshot only."""
    try:
        frame = await el.content_frame()
        if frame is None or not await frame.evaluate('''() => {
          const imgs=Array.from(document.images).filter(i=>i.getBoundingClientRect().width>20);
          return imgs.every(i=>i.complete && i.naturalWidth>0);
        }'''):
            return None
        shot = await el.screenshot(scale='css')
        return shot if _captcha_image_ready(shot) else None
    except Exception:
        return None


async def _read_storage(page) -> str:
    try:
        return await page.evaluate(
            f"() => localStorage.getItem('{LOGIN_CACHE_KEY}') || ''"
        )
    except Exception:
        return ""


def decode_storage(raw: str) -> dict:
    return json.loads(base64.b64decode(raw).decode("utf-8"))


async def _validate(cookie: str) -> bool:
    headers = {
        "cookie": cookie,
        "x-common-params": json.dumps(
            {
                "game_id": "29080",
                "area_id": "japan",
                "source": "pc_web",
                "intl_game_id": "29080",
                "language": "zh-TW",
                "env": "prod",
            },
            separators=(",", ":"),
        ),
        "x-language": "zh-TW",
        "user-agent": DEFAULT_UA,
    }
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(CHECK_LOGIN, headers=headers)
            d = r.json()
            return d.get("code") == 0 and d.get("msg") == "ok"
    except Exception:
        return False


async def _wait_official(ctx, page, deadline, on_captcha, ready):
    solved = False
    auto_fails = 0
    for _ in range(8):
        if time.monotonic() > deadline:
            raise LoginTimeout("登录超时")
        cap_page = None
        el = None
        box = None

        for _ in range(24):
            if time.monotonic() > deadline:
                raise LoginTimeout("登录超时")
            await page.wait_for_timeout(500)
            if await ready():
                solved = True
                break
            cap_page, el, box = await _find_captcha(ctx)
            if box:
                break
        if solved:
            break
        if not box:
            continue

        # iframe 初次出现时 y=-9999，等它进入视口
        if box["y"] < 0:
            await page.wait_for_timeout(1200)
            _, el, box = await _find_captcha(ctx)
            if not box or box["y"] < 0:
                continue

        shot = None
        while time.monotonic() < deadline:
            if await ready():
                return
            cap_page, el, box = await _find_captcha(ctx)
            if box and box['y'] >= 0:
                shot = await _ready_captcha_shot(el)
                if shot:
                    break
            await page.wait_for_timeout(250)
        if shot is None:
            raise LoginTimeout('验证码资源加载超时，请重新登录')
        challenge, auto = _analyze(shot)
        dx = None
        slider_x = 34.0
        slider_y = box["height"] * 0.815
        if auto and auto_fails < 2:
            dx, sx, sy = auto
            slider_x, slider_y = sx, sy
        elif on_captcha is not None:
            manual = await on_captcha(challenge)
            if manual is not None:
                dx = manual
                if challenge.slider:
                    slider_x = challenge.slider["cx"]
                    slider_y = challenge.slider["cy"]
        if dx is None:
            # 刷新拼图再试
            try:
                await cap_page.mouse.click(box["x"] + 18, box["y"] + box["height"] - 25)
            except Exception:
                pass
            await page.wait_for_timeout(1500)
            continue

        await _human_drag(
            cap_page,
            box["x"] + slider_x,
            box["y"] + slider_y,
            dx,
        )
        await page.wait_for_timeout(2500)
        if await ready():
            solved = True
            break

        auto_fails += 1
        try:
            await cap_page.mouse.click(box["x"] + 18, box["y"] + box["height"] - 25)
        except Exception:
            pass
        await page.wait_for_timeout(1200)

    if not solved:
        raise LoginError("官方验证未完成，请检查输入或重试")


async def login(
    account: str,
    password: str,
    *,
    area_id: int,
    headless: bool = True,
    channel: str = "auto",
    proxy: str = "",
    timeout: int = 180,
    on_captcha: Optional[CaptchaHandler] = None,
    on_code: Optional[Callable[[], Awaitable[str]]] = None,
) -> LoginResult:
    """登录并返回可用凭证。"""
    if area_id not in REGIONS:
        raise LoginError("请明确选择受支持的区服；港澳台服暂未支持")
    from playwright.async_api import async_playwright

    deadline = time.monotonic() + timeout
    async with async_playwright() as p:
        launch_kwargs = {"headless": headless}
        if proxy:
            launch_kwargs["proxy"] = {"server": proxy}
        browser = None
        errors = []
        for ch in ([channel] if channel != "auto" else [None, "msedge"]):
            try:
                kw = dict(launch_kwargs)
                if ch:
                    kw["channel"] = ch
                browser = await p.chromium.launch(**kw)
                break
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{ch or 'chromium'}: {exc}")
        if browser is None:
            raise LoginError("浏览器启动失败：" + " | ".join(errors))

        ctx = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="zh-TW",
            user_agent=DEFAULT_UA,
            timezone_id="Asia/Taipei",
        )
        page = await ctx.new_page()
        email_feedback = None
        try:
            await page.goto(
                "https://www.blablalink.com/",
                wait_until="domcontentloaded",
                timeout=60000,
            )
            await page.wait_for_timeout(5000)
            try:
                await page.locator("#onetrust-accept-btn-handler").click(timeout=3000)
            except Exception:
                pass
            await page.wait_for_timeout(800)

            await page.mouse.click(1283, 51)
            await page.wait_for_selector("#loginPwdForm_account", timeout=15000)
            if on_code is not None:
                from .email_flow import send_email_code, submit_email_code
                email_feedback = await send_email_code(page, ctx, account, deadline, on_captcha, _wait_official)
                account = password = ""
                code = await on_code()
                try:
                    if not code:
                        raise LoginCancelled("本次登录已取消")
                    await submit_email_code(page, code)
                finally:
                    code = ""
            else:
                await page.fill("#loginPwdForm_account", account)
                await page.fill("#loginPwdForm_password", password)
                await page.get_by_text("登入", exact=True).first.click()
                account = password = ""
                await page.fill("#loginPwdForm_password", "")

            async def authenticated():
                if email_feedback:
                    email_feedback.check()
                return await _read_storage(page)
            await _wait_official(ctx, page, deadline, on_captcha, authenticated)

            raw = await _read_storage(page)
            data = decode_storage(raw)
            openid = str(data.get("openid") or "")
            token = str(data.get("token") or "")
            channel_id = str((data.get("channel_info") or {}).get("channelId") or "131")
            expire_at = int(data.get("token_expire_time") or 0)
            if not openid or not token:
                raise LoginError("登录成功但未取到 openid/token")

            cookie = build_cookie(openid, token, channel_id)
            if not await _validate(cookie):
                raise LoginError("Cookie 校验失败，请重试")

            cred = Credentials(openid, token, channel_id, expire_at=expire_at)
            try:
                region, role = await selected_role(cred, area_id)
            except ValueError as exc:
                raise LoginError(str(exc)) from None

            return LoginResult(
                cookie=cookie,
                openid=openid,
                token=token,
                channel_id=channel_id,
                expire_at=expire_at,
                area_id=region.area_id,
                area_label=region.label,
                nickname=role.get("role_name") or data.get("user_name") or "",
                uid=str(role.get("role_id") or ""),
                role_name=role.get("role_name") or "",
            )
        finally:
            account = password = ""
            if email_feedback:
                email_feedback.close()
            try:
                await ctx.close()
            finally:
                await browser.close()
