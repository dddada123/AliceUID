"""Render the role-aware guide, with an accessible copyable text fallback."""
from __future__ import annotations
from ..nikke_commands import command_prefix

from gsuid_core.logger import logger
from gsuid_core.segment import MessageSegment
from gsuid_core.sv import SV
from ..nikke_message import send_with_forward

from .draw import build_help_context, draw_help, help_text

sv_help = SV('妮姬帮助', pm=6, priority=3)


@sv_help.on_command('帮助')
async def nikke_help(bot, ev):
    option = (ev.text or '').strip()
    if option not in ('', '文字', '文本'):
        await bot.send(f'发送 {command_prefix()}帮助 查看图片指南；发送 {command_prefix()}帮助 文字 获取可复制的指令。', at_sender=True)
        return
    from ..nikke_config.config import AliceUIDConfig
    mode = AliceUIDConfig.get_config('AliceUID_LoginMode').data
    context = build_help_context(getattr(ev, 'user_pm', 6), login_mode=mode)
    from ..nikke_user.models import AliceBind
    bind=await AliceBind.get_bind(ev.user_id,ev.bot_id) if getattr(ev,'user_id',None) and getattr(ev,'bot_id',None) else None
    if bind is not None:
        from ..nikke_api.client import REGIONS
        region=REGIONS.get(bind.area_id)
        context.update(commander_name=bind.nickname or '昵称未知',
                       commander_uid=bind.uid or '未知',
                       commander_region=region.label if region else '区服未知')
    if option:
        await bot.send(help_text(context), at_sender=True)
        return
    try:
        image = await draw_help(context)
    except Exception as exc:
        logger.warning(f'[AliceUID] 帮助图片渲染失败，回退文字 error_type={type(exc).__name__}')
        await bot.send(help_text(context), at_sender=True)
        return
    await send_with_forward(bot, ev, [MessageSegment.image(image), f'快速开始：{command_prefix()}登录 → 选择区服绑定 → {command_prefix()}信息。需要复制指令可发 {command_prefix()}帮助 文字。'],
                            config_key='AliceUID_HelpForward', title='AliceUID帮助')
