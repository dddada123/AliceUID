"""网页登录路由：/nikke/i/{token} + /nikke/api/*。"""
from __future__ import annotations
from ..nikke_commands import command_prefix

import asyncio
import base64
import html
import hashlib
import secrets
import math
import time
import re
from pathlib import Path
from typing import Optional

from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel

from gsuid_core.logger import logger
from gsuid_core.web_app import app

from ..nikke_api.auth import credentials_from_cookie
from ..nikke_api.client import NikkeClient, REGIONS
from ..nikke_config.config import ASSETS_PATH, AliceUIDConfig
from ..nikke_user.service import BindingPersistenceError, save_login
from ..nikke_user.models import AliceBind
from .regions import selected_role
from .browser import CaptchaChallenge, LoginError, login
from .session import sessions
from .expiry import expiry_notice
from ..nikke_permissions.runtime import get_policy
from .email_flow import cooldown, valid_email


def _owner_allowed(session):
    if get_policy().user_allowed(session.user_id):
        return True
    session.cancel()
    session.status = "failed"
    session.error = "当前用户无权使用AliceUID，请联系Bot主"
    return False


def _denied():
    return JSONResponse({"ok": False, "status": "denied", "msg": "当前用户无权使用AliceUID，请联系Bot主"}, status_code=403)

TEMPLATE = Path(__file__).parent.parent / "templates" / "login.html"
ASSET_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".svg", ".ico", ".css", ".js"}


def _binding_blocks(session, existing):
    """Replacement intent is set by the owner command, never a web payload."""
    if not session.replace_revision:
        return existing is not None
    return (existing is None or int(existing.area_id) != session.area_id or
            hashlib.sha256(existing.cookie_enc.encode()).hexdigest() != session.replace_revision)


def _replacement_kwargs(session):
    return {'replace_revision': session.replace_revision} if session.replace_revision else {}


class LoginPayload(BaseModel):
    token: str
    account: str
    password: str
    generation: Optional[int] = None


class TokenPayload(BaseModel):
    token: str


class EmailPayload(BaseModel):
    token: str
    account: str
    generation: Optional[int] = None


class CodePayload(BaseModel):
    token: str
    code: str
    generation: int


class ModePayload(BaseModel):
    token: str
    mode: str
    generation: Optional[int] = None


class CaptchaPayload(BaseModel):
    token: str
    dx: float
    challenge_id: str
    generation: Optional[int] = None


class CaptchaRefreshPayload(BaseModel):
    token: str
    challenge_id: str
    generation: int


class CookiePayload(BaseModel):
    token: str
    cookie: str


def _render(token: str, area_label: str, ttl: int) -> str:
    text = TEMPLATE.read_text(encoding="utf-8")
    mode = "cookie" if AliceUIDConfig.get_config("AliceUID_LoginMode").data == "cookie" else "browser"
    return text.replace("{{TOKEN}}", html.escape(token)).replace("{{REGION}}", html.escape(area_label)).replace("{{TTL}}", str(ttl // 60)).replace("{{MODE}}", mode).replace('{{COMMAND_PREFIX}}', command_prefix())


@app.get("/nikke/assets/{filename}")
async def nikke_asset(filename: str):
    if Path(filename).name != filename or ".." in filename:
        return JSONResponse({"ok": False}, status_code=404)
    path = ASSETS_PATH / filename
    if path.suffix.lower() not in ASSET_SUFFIXES or not path.is_file():
        return JSONResponse({"ok": False}, status_code=404)
    return FileResponse(path)


@app.get("/nikke/i/{token}", response_class=HTMLResponse)
async def nikke_login_page(token: str):
    session = sessions.get(token)
    if session and not _owner_allowed(session):
        return _denied()
    if not session:
        return HTMLResponse(
            "<html><body style='font-family:sans-serif;padding:40px'>"
            f"<h2>链接已失效</h2><p>请回到聊天窗口，重新发送「{command_prefix()} 登录」。</p>"
            "</body></html>",
            status_code=410,
        )
    return HTMLResponse(_render(token, REGIONS[session.area_id].label, session.ttl), headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})


@app.post("/nikke/api/login")
async def nikke_api_login(payload: LoginPayload):
    session = sessions.get(payload.token)
    if session and not _owner_allowed(session):
        return _denied()
    if AliceUIDConfig.get_config("AliceUID_LoginMode").data == "cookie":
        return JSONResponse({"ok": False, "msg": f"当前仅允许 Cookie 导入；请私聊 Bot 使用 {command_prefix()}导入cookie 区服 Cookie"}, status_code=403)
    if not session:
        return JSONResponse({"ok": False, "msg": "登录会话已失效"}, status_code=410)
    if session.area_id not in REGIONS:
        return JSONResponse({"ok": False, "msg": "请重新选择区服获取链接"})
    initial_generation = session.generation
    existing = await AliceBind.get_bind(session.user_id, session.bot_id)
    if not _owner_allowed(session):
        return _denied()
    if _binding_blocks(session, existing):
        return JSONResponse({"ok": False, "msg": "已有绑定或原绑定已变化，请回聊天获取正确登录链接；不会自动覆盖"})
    if sessions.get(payload.token) is not session or session.generation != initial_generation:
        return JSONResponse({"ok": False, "msg": "登录状态已更新"})
    if session.status not in ("created", "failed"):
        return JSONResponse({"ok": False, "msg": "这个链接已经用过了"})
    if not payload.account.strip() or not payload.password:
        return JSONResponse({"ok": False, "msg": "账号或密码为空"})

    if payload.generation is not None and payload.generation != session.generation:
        return JSONResponse({"ok": False, "msg": "登录方式已更新，请刷新状态"})
    session.cancel()
    session.mode = "password"
    session.status = "logging_in"
    session.operation_started_at = session.heartbeat_at = time.time()
    session.error = ""
    session.task = asyncio.create_task(_run_login(session.token, payload.account.strip(), payload.password, generation=session.generation))
    payload.password = ""
    return JSONResponse({"ok": True, "generation": session.generation})


@app.post("/nikke/api/mode")
async def nikke_api_mode(payload: ModePayload):
    session = sessions.get(payload.token)
    if session and not _owner_allowed(session):
        return _denied()
    if not session:
        return JSONResponse({"ok": False, "msg": "登录会话已失效"}, status_code=410)
    if payload.mode not in ("email", "password", "cancel"):
        return JSONResponse({"ok": False, "msg": "登录方式无效"})
    if payload.generation is not None and payload.generation != session.generation:
        return JSONResponse({"ok": False, "msg": "登录方式已更新", "generation": session.generation})
    if session.status == "success":
        return JSONResponse({"ok": False, "msg": "已完成绑定"})
    session.cancel()
    if payload.mode != "cancel":
        session.mode = payload.mode
    session.status = "created"
    session.operation_started_at = 0
    session.error = ""
    session.code_deadline = 0
    return JSONResponse({"ok": True, "generation": session.generation, "mode": session.mode})


@app.post("/nikke/api/email/send")
async def nikke_api_email_send(payload: EmailPayload):
    session = sessions.get(payload.token)
    if session and not _owner_allowed(session):
        return _denied()
    if AliceUIDConfig.get_config("AliceUID_LoginMode").data == "cookie":
        return JSONResponse({"ok": False, "msg": "当前仅允许 Cookie 导入"}, status_code=403)
    if not session:
        return JSONResponse({"ok": False, "msg": "登录会话已失效"}, status_code=410)
    if session.area_id not in REGIONS or session.status not in ("created", "failed", "awaiting_code"):
        return JSONResponse({"ok": False, "msg": "登录正在处理或已完成"})
    if payload.generation is not None and payload.generation != session.generation:
        return JSONResponse({"ok": False, "msg": "登录方式已更新"})
    account = payload.account.strip()
    if not valid_email(account):
        return JSONResponse({"ok": False, "msg": "请输入有效邮箱（最多64字符）"})
    initial_generation = session.generation
    existing = await AliceBind.get_bind(session.user_id, session.bot_id)
    if not _owner_allowed(session):
        return _denied()
    if _binding_blocks(session, existing):
        return JSONResponse({"ok": False, "msg": "已有绑定或原绑定已变化，请回聊天获取正确登录链接；不会自动覆盖"})
    if sessions.get(payload.token) is not session or session.generation != initial_generation:
        return JSONResponse({"ok": False, "msg": "登录状态已更新"})
    # Recheck after database await so simultaneous sends cannot launch two tasks.
    if sessions.get(payload.token) is not session or session.status not in ("created", "failed", "awaiting_code"):
        return JSONResponse({"ok": False, "msg": "登录状态已更新"})
    retry = cooldown.reserve(session.user_id, session.bot_id, account)
    if retry:
        session.resend_at = max(session.resend_at, time.time() + retry)
        return JSONResponse({"ok": False, "msg": f"发送冷却中，请等待 {retry} 秒", "retry_after": retry})
    session.cancel()
    session.mode = "email"
    session.status = "sending_code"
    session.operation_started_at = session.heartbeat_at = time.time()
    session.resend_at = time.time() + cooldown.seconds
    session.code_deadline = 0
    session.error = ""
    session.task = asyncio.create_task(_run_login(session.token, account, "", mode="email", generation=session.generation))
    return JSONResponse({"ok": True, "generation": session.generation, "retry_after": cooldown.seconds})


@app.post("/nikke/api/email/verify")
async def nikke_api_email_verify(payload: CodePayload):
    try:
        session = sessions.get(payload.token)
        if session and not _owner_allowed(session):
            return _denied()
        if AliceUIDConfig.get_config("AliceUID_LoginMode").data == "cookie":
            return JSONResponse({"ok": False, "msg": "当前仅允许 Cookie 导入"}, status_code=403)
        if not session or session.status != "awaiting_code" or payload.generation != session.generation:
            return JSONResponse({"ok": False, "msg": "当前验证码已失效，请重新发送"})
        if time.time() >= session.code_deadline:
            session.cancel()
            session.status = "failed"
            session.error = "验证码已过期，请显式重新发送"
            return JSONResponse({"ok": False, "msg": session.error})
        if not re.fullmatch(r"[0-9]{5}", payload.code.strip()):
            return JSONResponse({"ok": False, "msg": "请输入5位邮箱验证码"})
        session.email_code = payload.code.strip()
        session.heartbeat_at = time.time()
        session.status = "logging_in"
        session.code_event.set()
        return JSONResponse({"ok": True})
    finally:
        payload.code = ""


async def _run_login(token: str, account: str, password: str, *, mode="password", generation=None):
    session = sessions.get(token)
    if session and not _owner_allowed(session):
        return
    if not session:
        return
    generation = session.generation if generation is None else generation
    if generation != session.generation:
        return
    mailbox_digest = cooldown.mailbox_key(account) if mode == "email" else ""
    def current():
        return sessions.get(token) is session and session.generation == generation and _owner_allowed(session)

    async def watchdog():
        while current():
            await asyncio.sleep(5)
            if not current():
                return
            if session.status == "awaiting_code" and time.time() < session.code_deadline:
                # Mobile mail apps can freeze this page's JS. The existing code
                # deadline and 330s/360s operation limits still bound this wait.
                continue
            if time.time() - session.heartbeat_at > 35:
                session.cancel()
                session.status = "failed"
                session.error = "页面已关闭或连接中断，本次登录已停止；请重新操作"
                return

    async def on_captcha(challenge: CaptchaChallenge) -> Optional[float]:
        if not current():
            raise asyncio.CancelledError()
        previous = session.status
        session.captcha_id = secrets.token_urlsafe(12)
        session.captcha_png = challenge.png
        session.captcha_piece = challenge.piece
        session.captcha_hole = challenge.hole
        session.captcha_slider = challenge.slider
        session.captcha_size = {"width": challenge.width, "height": challenge.height}
        session.captcha_dx = None
        session.captcha_event.clear()
        session.status = "captcha"
        try:
            await asyncio.wait_for(session.captcha_event.wait(), timeout=120)
        except asyncio.TimeoutError:
            session.captcha_png = None
            session.captcha_id = ''
            session.status = previous
            return None
        if not current():
            raise asyncio.CancelledError()
        session.status = previous
        return session.captcha_dx

    async def on_code():
        if not current():
            raise asyncio.CancelledError()
        session.resend_at = cooldown.confirm(session.user_id, session.bot_id, mailbox_digest)
        session.email_code = ""
        session.code_event.clear()
        # Local waiting limit, deliberately shorter than the total 360s operation.
        session.code_deadline = min(time.time() + 240, session.operation_started_at + 330)
        session.status = "awaiting_code"
        try:
            await asyncio.wait_for(session.code_event.wait(), max(0, session.code_deadline - time.time()))
        except asyncio.TimeoutError:
            raise LoginError("验证码已过期，请显式重新发送") from None
        if not current():
            raise asyncio.CancelledError()
        code, session.email_code = session.email_code, ""
        session.status = "logging_in"
        return code

    monitor = asyncio.create_task(watchdog())
    try:
        kwargs = dict(
            headless=bool(AliceUIDConfig.get_config("AliceUID_Headless").data),
            channel=str(AliceUIDConfig.get_config("AliceUID_BrowserChannel").data or "auto"),
            proxy=str(AliceUIDConfig.get_config("AliceUID_Proxy").data or ""),
            timeout=330 if mode == "email" else 180,
            on_captcha=on_captcha, area_id=session.area_id,
        )
        if mode == "email":
            kwargs["on_code"] = on_code
        operation = login(account, password, **kwargs)
        account = password = ""
        result = await asyncio.wait_for(operation, timeout=330 if mode == "email" else 180)
        if not current():
            return
        if result.area_id != session.area_id:
            raise LoginError("返回区服与所选区服不一致，已停止绑定")
        existing = await AliceBind.get_bind(session.user_id, session.bot_id)
        if _binding_blocks(session, existing):
            raise LoginError("已有绑定，已停止覆盖；换号请先解绑")
        if session.replace_revision and str(result.openid) != str(existing.intl_open_id):
            raise LoginError("重新登录须使用原账号；原Cookie未替换")
        await save_login(
            session.user_id, session.bot_id, session.group_id,
            openid=result.openid, area_id=result.area_id,
            game_id="29080" if result.area_id != 91 else "29157",
            cookie=result.cookie, nickname=result.nickname, uid=result.uid,
            expire_at=result.expire_at, still_current=current,
            **_replacement_kwargs(session),
        )
        if not current():
            return
        session.nickname = result.nickname
        session.cookie_expire = result.expire_at
        session.uid = result.uid
        session.area_label = result.area_label
        session.success_at = time.time()
        session.status = "success"
        logger.info(f"[AliceUID] 登录成功 user={session.user_id} area={result.area_id}")
    except asyncio.CancelledError:
        pass
    except BindingPersistenceError:
        if current():
            session.status = "failed"
            session.error = f"绑定保存未确认，请回聊天发送 {command_prefix()}我的账号 检查后重试。"
            logger.warning(f"[AliceUID] 绑定保存未确认 user={session.user_id}")
    except (LoginError, asyncio.TimeoutError) as exc:
        if current():
            session.status = "failed"
            # Only our own constant UI errors are allowed; never expose SDK payloads.
            session.error = str(exc)[:200] if isinstance(exc, LoginError) else "登录超时，请重新操作"
            logger.warning(f"[AliceUID] 登录失败 user={session.user_id}")
    except Exception:
        if current():
            session.status = "failed"
            session.error = "登录异常，请稍后重试"
            logger.warning(f"[AliceUID] 登录异常 user={session.user_id}（详情已省略以保护凭证）")
    finally:
        account = password = ""
        monitor.cancel()
        await asyncio.gather(monitor, return_exceptions=True)
        if current():
            session.email_code = ""
            session.captcha_png = None
            session.captcha_piece = session.captcha_hole = session.captcha_size = session.captcha_slider = None
            session.captcha_dx = None
            session.captcha_id = ""
            session.task = None


@app.post("/nikke/api/status")
async def nikke_api_status(payload: TokenPayload):
    session = sessions.get(payload.token)
    if session and not _owner_allowed(session):
        return _denied()
    if not session:
        return JSONResponse({"status": "expired", "error": "登录会话已失效"})
    session.heartbeat_at = time.time()
    data = {
        "generation": session.generation,
        "mode": session.mode,
        "retry_after": max(0, math.ceil(session.resend_at - time.time())),
        "code_expires_in": max(0, math.ceil(session.code_deadline - time.time())),
        "status": session.status,
        "error": session.error,
        "nickname": session.nickname,
        "uid": session.uid,
        "area": session.area_label,
        "relogin": bool(session.replace_revision),
        "expiry_hint": expiry_notice(session.cookie_expire) if session.status == 'success' else '',
    }
    if session.status == 'success' and session.replace_revision:
        from ..nikke_community.runtime import login_recovery_notice
        data['expiry_hint'] += '\n' + await login_recovery_notice(session.user_id,session.bot_id)
    if session.status == "captcha" and session.captcha_png:
        data["captcha"] = base64.b64encode(session.captcha_png).decode("ascii")
        data["captcha_piece"] = session.captcha_piece
        data["captcha_hole"] = session.captcha_hole
        data["captcha_slider"] = session.captcha_slider
        data["captcha_size"] = session.captcha_size
        data["challenge_id"] = session.captcha_id
    return JSONResponse(data)


@app.post("/nikke/api/captcha")
async def nikke_api_captcha(payload: CaptchaPayload):
    session = sessions.get(payload.token)
    if session and not _owner_allowed(session):
        return _denied()
    if not session or session.status != "captcha":
        return JSONResponse({"ok": False, "msg": "当前不需要验证码"})
    if (payload.generation is not None and payload.generation != session.generation) or payload.challenge_id != session.captcha_id or not session.captcha_png:
        return JSONResponse({"ok": False, "msg": "验证码已更新，请使用当前图片"})
    if not math.isfinite(payload.dx) or not 0 <= payload.dx <= 300:
        return JSONResponse({"ok": False, "msg": "验证码位移无效"})
    session.captcha_dx = payload.dx
    session.status = "logging_in"
    session.captcha_png = None
    session.captcha_piece = None
    session.captcha_hole = None
    session.captcha_size = None
    session.captcha_slider = None
    session.captcha_event.set()
    return JSONResponse({"ok": True})


@app.post('/nikke/api/captcha/refresh')
async def nikke_api_captcha_refresh(payload: CaptchaRefreshPayload):
    session = sessions.get(payload.token)
    if session and not _owner_allowed(session):
        return _denied()
    if (not session or session.status != 'captcha' or
            payload.generation != session.generation or
            payload.challenge_id != session.captcha_id or not session.captcha_png):
        return JSONResponse({'ok':False,'msg':'验证码已更新，请等待当前图片'})
    session.captcha_dx = None
    session.captcha_png = None
    session.captcha_piece = session.captcha_hole = session.captcha_size = session.captcha_slider = None
    session.captcha_id = ''
    session.status = 'logging_in'
    session.captcha_event.set()
    return JSONResponse({'ok':True,'msg':'正在刷新验证码'})


@app.post("/nikke/api/cookie")
async def nikke_api_cookie(payload: CookiePayload):
    """Cookie 兜底沿用链接所选区服，不自动覆盖已有绑定。"""
    session = sessions.get(payload.token)
    if session and not _owner_allowed(session):
        return _denied()
    if not session:
        return JSONResponse({"ok": False, "msg": "登录会话已失效"}, status_code=410)
    if session.status not in ("created", "failed") or session.area_id not in REGIONS:
        return JSONResponse({"ok": False, "msg": "链接正在使用或已完成，请重新选择区服获取链接"})
    initial_generation = session.generation
    existing = await AliceBind.get_bind(session.user_id, session.bot_id)
    if not _owner_allowed(session):
        return _denied()
    if _binding_blocks(session, existing):
        return JSONResponse({"ok": False, "msg": "已有绑定或原绑定已变化，请回聊天获取正确登录链接；不会自动覆盖"})
    if sessions.get(payload.token) is not session or session.generation != initial_generation:
        return JSONResponse({"ok": False, "msg": "登录状态已更新"})
    cred = credentials_from_cookie(payload.cookie, 0)
    if cred is None:
        return JSONResponse({"ok": False, "msg": "Cookie 里缺少 game_openid / game_token"})
    session.cancel()
    generation = session.generation
    def current():
        return sessions.get(payload.token) is session and session.generation == generation and _owner_allowed(session)
    session.status = "logging_in"
    session.operation_started_at = time.time()
    try:
        async with NikkeClient(cred, REGIONS[session.area_id]) as client:
            if not await client.check_login():
                raise ValueError("Cookie 无效或已过期")
        if not current():
            return _denied() if not get_policy().user_allowed(session.user_id) else JSONResponse({"ok": False, "msg": "登录操作已取消"})
        region, role = await selected_role(cred, session.area_id)
        if not current():
            return JSONResponse({"ok": False, "msg": "登录操作已取消"})
        existing = await AliceBind.get_bind(session.user_id, session.bot_id)
        if _binding_blocks(session, existing):
            raise ValueError("已有绑定，已停止覆盖")
        if session.replace_revision and str(cred.openid) != str(existing.intl_open_id):
            raise ValueError("重新登录须使用原账号；原Cookie未替换")
        await save_login(session.user_id, session.bot_id, session.group_id,
                         openid=cred.openid, area_id=region.area_id, game_id=region.game_id,
                         cookie=cred.cookie, nickname=role.get("role_name") or "",
                         uid=str(role.get("role_id") or ""), expire_at=0,
                          still_current=current, **_replacement_kwargs(session))
        if not current():
            return JSONResponse({"ok": False, "msg": "登录操作已取消"})
        session.nickname = role.get("role_name") or ""
        session.uid = str(role.get("role_id") or "")
        session.area_label = region.label
        session.success_at = time.time()
        session.status = "success"
        session.error = ""
        return JSONResponse({"ok": True})
    except BindingPersistenceError:
        if not current():
            return JSONResponse({"ok": False, "msg": "登录操作已取消"})
        session.error = f'绑定保存未确认，请回聊天发送 {command_prefix()}我的账号 检查后重试。'
        logger.warning('[AliceUID] Cookie绑定保存未确认（未记录凭据）')
    except ValueError as exc:
        if not current():
            return JSONResponse({"ok": False, "msg": "登录操作已取消"})
        session.error = str(exc)
    except Exception:
        if not current():
            return JSONResponse({"ok": False, "msg": "登录操作已取消"})
        session.error = "Cookie 校验失败，请稍后重试"
        logger.warning("[AliceUID] Cookie 导入失败（详情已省略以保护凭证）")
    session.status = "failed"
    return JSONResponse({"ok": False, "msg": session.error})
