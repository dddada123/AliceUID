"""账号相关命令：登录、解绑、导入 Cookie、查看绑定。"""
from __future__ import annotations
from ..nikke_commands import command_prefix

import asyncio
import hashlib
from functools import wraps
from io import BytesIO

from gsuid_core.bot import Bot
from gsuid_core.config import core_config
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.segment import MessageSegment
from gsuid_core.sv import SV

from ..nikke_api.auth import credentials_from_cookie
from ..nikke_api.client import NikkeClient, REGIONS
from ..nikke_config.config import AliceUIDConfig
from ..nikke_user.models import AliceBind
from ..nikke_user.service import BindingPersistenceError, bind_summary, is_master, save_login, set_public
from .session import sessions
from .expiry import expiry_notice
from .regions import REGION_ALIASES, REGION_HELP, selected_role

sv_account = SV("妮姬账号", pm=6, priority=4)
sv_account_admin = SV("妮姬账号管理", pm=0, priority=4)


def account_errors(func):
    @wraps(func)
    async def guarded(bot, ev):
        try:
            return await func(bot, ev)
        except Exception as exc:
            logger.error(f"[AliceUID] 账号命令失败 command={func.__name__} error_type={type(exc).__name__}")
            await bot.send("账号操作失败，未确认完成，请稍后重试并请管理员检查日志。", at_sender=True)
    return guarded


def get_base_url() -> str:
    login_url = str(AliceUIDConfig.get_config("AliceUID_LoginUrl").data or "").strip()
    if login_url:
        if not login_url.startswith(("http://", "https://")):
            login_url = f"https://{login_url}"
        return login_url.rstrip("/")
    host = str(core_config.get_config("HOST") or "127.0.0.1")
    port = str(core_config.get_config("PORT") or "8765")
    if host in ("0.0.0.0", "::", "localhost"):
        host = "127.0.0.1"
    return f"http://{host}:{port}"


def _make_qr_png(url: str) -> bytes | None:
    try:
        import qrcode

        img = qrcode.make(url)
        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[AliceUID] 生成二维码失败 error_type={type(exc).__name__}")
        return None


@sv_account.on_command(("登录", "登陆", "绑定账号"))
@account_errors
async def nikke_login_cmd(bot: Bot, ev: Event):
    area_id = REGION_ALIASES.get((ev.text or "").strip())
    if area_id is None:
        await bot.send(REGION_HELP, at_sender=True)
        return
    bind = await AliceBind.get_bind(ev.user_id, ev.bot_id)
    if bind:
        await bot.send(
            f"你已经绑定过「{bind.nickname or '未知'}」。\n更新Cookie请发 {command_prefix()}重新登录；如需换号，先发 {command_prefix()} 解绑。",
            at_sender=True,
        )
        return

    if AliceUIDConfig.get_config("AliceUID_LoginMode").data == "cookie":
        await bot.send(f"当前仅允许 Cookie 导入，请私聊 Bot：\n{command_prefix()}导入cookie {REGIONS[area_id].label} game_openid=...; game_token=...; ...\n不要将 Cookie 发到群里。", at_sender=True)
        return
    active = sessions.active(ev.user_id, ev.bot_id)
    if active is not None:
        url = f"{get_base_url()}/nikke/i/{active.token}"
        await _send_login_link(bot,
            f"已有「{REGIONS[active.area_id].label}」登录正在处理，请继续原链接完成验证：\n{url}\n"
            "本次未更换区服；完成或超时后再重新选择。",
            url, ev=ev,
        )
        return
    ttl = int(AliceUIDConfig.get_config("AliceUID_LoginTTL").data or 600)
    session = sessions.create(ev.user_id, ev.bot_id, ev.group_id, area_id=area_id, ttl=ttl)
    url = f"{get_base_url()}/nikke/i/{session.token}"
    text = (
        f"NIKKE 账号绑定 · {REGIONS[area_id].label}\n"
        f"请在 {ttl // 60} 分钟内打开下面的链接，输入 blablalink 账号密码：\n"
        f"{url}\n\n"
        "绑定仅使用所选区服，查不到角色会失败，不会自动换区。\n"
        "登录成功后会加密保存 Cookie；请勿在聊天中发送密码。\n"
        "链接仅供本人绑定，请勿转发；群成员请各自获取自己的链接。\n"
        "如果页面出现拼图，按提示拖动即可。\n" + expiry_notice()
    )

    await _send_login_link(bot, text, url, ev=ev)
    asyncio.create_task(_notify_login(bot, ev, session.token))


@sv_account.on_fullmatch(("重新登录", "重新登陆"))
@account_errors
async def nikke_relogin_cmd(bot: Bot, ev: Event):
    bind = await AliceBind.get_bind(ev.user_id, ev.bot_id)
    if bind is None:
        await bot.send(f"还没有绑定账号，请先发送 {command_prefix()}登录 选择区服。", at_sender=True)
        return
    if bind.area_id not in REGIONS:
        await bot.send("原绑定区服暂不支持网页登录，请联系Bot主检查绑定。", at_sender=True)
        return
    active = sessions.active(ev.user_id, ev.bot_id)
    if active is not None:
        url = f"{get_base_url()}/nikke/i/{active.token}"
        await _send_login_link(bot, f"已有登录正在处理，请继续原链接：\n{url}", url, ev=ev)
        return
    ttl = int(AliceUIDConfig.get_config("AliceUID_LoginTTL").data or 600)
    session = sessions.create(ev.user_id, ev.bot_id, ev.group_id, area_id=bind.area_id, ttl=ttl)
    session.replace_revision = hashlib.sha256(bind.cookie_enc.encode()).hexdigest()
    url = f"{get_base_url()}/nikke/i/{session.token}"
    method = "导入新Cookie" if AliceUIDConfig.get_config("AliceUID_LoginMode").data == "cookie" else "登录原blablalink账号"
    text = (f"NIKKE 重新登录 · {REGIONS[bind.area_id].label}\n请在{ttl // 60}分钟内打开链接，{method}：\n{url}\n"
            "仅更新本人同账号同区服的Cookie；失败保留原绑定。链接仅供本人使用，请勿转发。\n"
            "更新后自动社区授权需重新开启，每日预算不会重置。\n" + expiry_notice(bind.cookie_expire))
    await _send_login_link(bot, text, url, ev=ev)
    asyncio.create_task(_notify_login(bot, ev, session.token))


async def _send_login_link(bot, text, url, *, ev=None):
    from ..nikke_message import send_with_forward
    qr_enabled = bool(AliceUIDConfig.get_config("AliceUID_LoginQRCode").data)
    qr_png = _make_qr_png(url) if qr_enabled else None
    content = [MessageSegment.text(text)]
    if qr_png:
        content.append(MessageSegment.image(qr_png))
    return await send_with_forward(bot, ev, content if qr_png else text,
                                   config_key='AliceUID_LoginForward')

async def _notify_login(bot: Bot, ev: Event, token: str):
    """后台等结果，成功/失败都回一条消息。"""
    while True:
        await asyncio.sleep(2)
        session = sessions.get(token)
        if not session:
            return
        if session.status == "success":
            await bot.send(
                f"{'重新登录' if session.replace_revision else '绑定'}成功：{session.nickname or '未知'}（{session.area_label}）\n"
                f"回到聊天窗口发送 {command_prefix()}我的账号 查看绑定。\n" + expiry_notice(session.cookie_expire),
                at_sender=True,
            )
            return
        if session.status == "failed":
            await bot.send(f"绑定失败：{session.error or '未知错误'}", at_sender=True)
            return


@sv_account.on_fullmatch(("解绑", "删除绑定"))
@account_errors
async def nikke_unbind_cmd(bot: Bot, ev: Event):
    try:
        bind = await AliceBind.get_bind(ev.user_id, ev.bot_id)
        if not bind:
            await bot.send(f"你还没有绑定登录账号。如只登记了UID，请发送 {command_prefix()}解绑UID 清除登记。", at_sender=True)
            return
        result = await AliceBind.delete_bind(ev.user_id, ev.bot_id)
        if result != 0:
            raise RuntimeError("绑定删除返回失败")
    except Exception as exc:  # noqa: BLE001
        # Exception messages / model repr may contain cookies. Log the stage
        # and exception type only, never account data or database parameters.
        logger.error(f"[AliceUID] 解绑失败 stage=delete_bind error_type={type(exc).__name__}")
        await bot.send("解绑失败，本地绑定删除未确认，请稍后重试并请管理员检查日志。", at_sender=True)
        return
    sessions.clear_owner(ev.user_id, ev.bot_id)
    cache_notice = ''
    try:
        from ..nikke_character.service import character_queries
        from ..nikke_character.cache import panel_identity
        character_queries.invalidate(bind)
        panel_store = character_queries.store()
        if panel_store is not None:
            panel_store.purge(panel_identity(bind))
        from ..nikke_roster.service import revoke_cached_binding
        revoke_cached_binding(bind, ev.user_id, ev.bot_id)
    except Exception as exc:
        logger.error(f'[AliceUID] 登录绑定已解除但卡片缓存清理未确认 error_type={type(exc).__name__}')
        cache_notice = '\n登录绑定已解除；卡片缓存清理未确认，请管理员检查日志。'
    # Solo results must also be erased if another card cache cleanup failed.
    try:
        from ..nikke_solo.cache import invalidate_binding
        invalidate_binding(bind)
    except Exception as exc:
        logger.error(f'[AliceUID] 登录绑定已解除但突袭缓存清理未确认 error_type={type(exc).__name__}')
        cache_notice += '\n登录绑定已解除；个人突袭缓存清理未确认，请管理员检查日志。'
    await bot.send(f"已解绑「{bind.nickname or '未知'}」，本地 Cookie 已删除。" + cache_notice, at_sender=True)


@sv_account.on_fullmatch(("我的账号", "账号信息"))
@account_errors
async def nikke_account_cmd(bot: Bot, ev: Event):
    bind = await AliceBind.get_bind(ev.user_id, ev.bot_id)
    if not bind:
        await bot.send(f"还没有绑定登录账号。UID登记请发送 {command_prefix()}我的UID 查看；本人练度查询需先发送 {command_prefix()}登录 选择区服。", at_sender=True)
        return
    await bot.send(bind_summary(bind), at_sender=True)


@sv_account.on_command(("导入cookie", "导入Cookie", "绑定cookie"))
@account_errors
async def nikke_cookie_cmd(bot: Bot, ev: Event):
    """高级用法：直接粘贴 Cookie。仅私聊，避免在群里泄露。"""
    if ev.group_id:
        await bot.send("Cookie 含账号凭证，请私聊我发送。", at_sender=True)
        return
    if await AliceBind.get_bind(ev.user_id, ev.bot_id):
        await bot.send(f"已有绑定，请先 {command_prefix()}解绑；不会自动覆盖。", at_sender=True)
        return
    area_text, _, cookie = (ev.text or "").strip().partition(" ")
    area_id = REGION_ALIASES.get(area_text)
    if area_id is None:
        await bot.send(f"请显式选择区服，例如：{command_prefix()}导入cookie 日服 game_openid=...; game_token=...; ...\n" + REGION_HELP, at_sender=True)
        return
    if "game_token=" not in cookie:
        await bot.send(f"用法：{command_prefix()}导入cookie 日服 game_openid=...; game_token=...; ...", at_sender=True)
        return
    cred = credentials_from_cookie(cookie, 0)
    if cred is None:
        await bot.send("Cookie 里缺少 game_openid / game_token。", at_sender=True)
        return

    try:
        async with NikkeClient(cred, REGIONS[area_id]) as client:
            if not await client.check_login():
                await bot.send("Cookie 无效或已过期。", at_sender=True)
                return
        region, role = await selected_role(cred, area_id)
        if await AliceBind.get_bind(ev.user_id, ev.bot_id):
            await bot.send("已有绑定，已停止覆盖；换号请先解绑。", at_sender=True)
            return
        await save_login(
            ev.user_id,
            ev.bot_id,
            ev.group_id,
            openid=cred.openid,
            area_id=region.area_id,
            game_id=cred.game_id,
            cookie=cred.cookie,
            nickname=role.get("role_name") or "",
            uid=str(role.get("role_id") or ""),
            expire_at=0,
        )
        await bot.send(
            f"绑定成功：{role.get('role_name') or '未知'}（{region.label}）\n"
            "提醒：这条消息里的 Cookie 请自行撤回。",
            at_sender=True,
        )
    except BindingPersistenceError:
        await bot.send(f"绑定保存未确认，请发送 {command_prefix()}我的账号 检查后重试。", at_sender=True)
    except ValueError as exc:
        await bot.send(str(exc), at_sender=True)
    except Exception:  # noqa: BLE001
        logger.warning("[AliceUID] 导入 Cookie 失败（详情已省略以保护凭证）")
        await bot.send("Cookie 校验失败，请重新从浏览器复制。", at_sender=True)


@sv_account.on_fullmatch(("公开", "公开账号"))
@account_errors
async def nikke_public_cmd(bot: Bot, ev: Event):
    if not await set_public(ev.user_id, ev.bot_id, True):
        await bot.send("还没有绑定账号。", at_sender=True)
        return
    await bot.send("已开启账号公开标记。当前版本未提供群排行命令。", at_sender=True)


@sv_account.on_fullmatch(("隐藏", "隐藏账号"))
@account_errors
async def nikke_private_cmd(bot: Bot, ev: Event):
    if not await set_public(ev.user_id, ev.bot_id, False):
        await bot.send("还没有绑定账号。", at_sender=True)
        return
    await bot.send("已关闭账号公开标记。", at_sender=True)


@sv_account_admin.on_fullmatch(("账号列表", "绑定列表"))
@account_errors
async def nikke_list_cmd(bot: Bot, ev: Event):
    if getattr(ev, "user_pm", None) != 0 and not is_master(ev.user_id):
        await bot.send("这个命令只有 Bot 主可以使用。", at_sender=True)
        return
    binds = await AliceBind.get_all_binds()
    if not binds:
        await bot.send("还没有任何绑定。", at_sender=True)
        return
    lines = ["当前绑定："]
    for b in binds[:30]:
        lines.append(
            f"{'★' if b.is_master else '·'} {b.user_id}  {b.nickname or '未知'}  "
            f"{b.area_id}  {'公开' if b.is_public else '私密'}"
        )
    if len(binds) > 30:
        lines.append(f"... 共 {len(binds)} 条")
    await bot.send("\n".join(lines), at_sender=True)
