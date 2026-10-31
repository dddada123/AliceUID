"""Explicitly typed UID registration. This module never loads private clients."""
from __future__ import annotations
from ..nikke_commands import command_prefix

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import SV

from .store import format_summary, get_uid_store

sv_uid = SV("妮姬UID登记", pm=6, priority=3)

USAGE = (
    "UID登记用法：\n"
    f"{command_prefix()}绑定UID 社区 <社区标识>\n"
    f"{command_prefix()}绑定UID 游戏 日服 <游戏UID>\n"
    "游戏区服可选：日服 / 北美服 / 韩服 / 国际服 / 东南亚服\n"
    f"{command_prefix()}绑定UID 分享 <官网分享URL或Base64完整标识>\n"
    "官网分享URL须为HTTPS的 blablalink.com 或 www.blablalink.com，"
    "来自 /shiftyspad 或 /user 页面。\n"
    f"{command_prefix()}我的UID：查看自己的登记\n"
    f"{command_prefix()}解绑UID：清除自己的UID登记\n"
    "必须明确类型，不会按位数猜测；多个类型可分别登记并保留。\n"
    "仅登记标识，未验证账号归属，不等于登录或匿名查询权限。"
    f"本人练度查询仍需 {command_prefix()}登录日服 等区服命令。"
)


def _failure(stage: str, exc: Exception) -> str:
    # Never include raw input, URL, model contents or exception messages in logs.
    logger.error(f"[AliceUID] UID登记失败 stage={stage} error_type={type(exc).__name__}")
    return "UID登记操作失败，请稍后重试并请管理员检查日志。"


@sv_uid.on_command(("绑定UID", "绑定uid"), block=True)
async def nikke_bind_uid_cmd(bot: Bot, ev: Event):
    text = (ev.text or "").strip()
    if not text:
        await bot.send(USAGE, at_sender=True)
        return
    parts = text.split()
    if len(text) > 4200:
        await bot.send("UID登记内容过长，请检查输入。", at_sender=True)
        return
    try:
        # Owner always comes from the sender, regardless of mentions or text.
        user_id, bot_id = ev.user_id, ev.bot_id
        if parts[0] == "社区" and len(parts) == 2:
            record = get_uid_store().bind_community(user_id, bot_id, parts[1])
        elif parts[0] == "游戏" and len(parts) == 3:
            record = get_uid_store().bind_game(user_id, bot_id, parts[1], parts[2])
        elif parts[0] == "分享" and len(parts) == 2:
            record = get_uid_store().bind_share(user_id, bot_id, parts[1])
        else:
            await bot.send("请按明确类型登记。\n" + USAGE, at_sender=True)
            return
    except ValueError as exc:
        await bot.send(str(exc), at_sender=True)
        return
    except Exception as exc:  # noqa: BLE001
        await bot.send(_failure("bind", exc), at_sender=True)
        return
    await bot.send("UID登记已保存。\n" + format_summary(record), at_sender=True)


@sv_uid.on_command(("我的UID", "我的uid"), block=True)
async def nikke_my_uid_cmd(bot: Bot, ev: Event):
    if (ev.text or "").strip():
        await bot.send(f"直接发送 {command_prefix()}我的UID 即可查看自己的登记，无需附加UID。", at_sender=True)
        return
    try:
        record = get_uid_store().get(ev.user_id, ev.bot_id)
    except Exception as exc:  # noqa: BLE001
        await bot.send(_failure("get", exc), at_sender=True)
        return
    await bot.send(format_summary(record), at_sender=True)


@sv_uid.on_command(("解绑UID", "解绑uid"), block=True)
async def nikke_clear_uid_cmd(bot: Bot, ev: Event):
    if (ev.text or "").strip():
        await bot.send(f"直接发送 {command_prefix()}解绑UID 即可清除自己的登记，无需附加UID。", at_sender=True)
        return
    try:
        removed = get_uid_store().clear(ev.user_id, ev.bot_id)
    except Exception as exc:  # noqa: BLE001
        await bot.send(_failure("clear", exc), at_sender=True)
        return
    text = "已清除你的UID登记。" if removed else "你还没有登记UID。"
    await bot.send(text + f"账号登录请使用 {command_prefix()}登录日服 等区服命令；退出登录请使用 {command_prefix()}解绑。", at_sender=True)
