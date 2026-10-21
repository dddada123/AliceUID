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
    if option:
        await bot.send(help_text(context), at_sender=True)
        return
    try:
        from .cache import cached_help
        image = await cached_help(context, draw_help)
    except Exception as exc:
        logger.warning(f'[AliceUID] 帮助图片渲染失败，回退文字 error_type={type(exc).__name__}')
        await bot.send(help_text(context), at_sender=True)
        return
    await send_with_forward(bot, ev, [MessageSegment.image(image), f'快速开始：{command_prefix()}登录 → 选择区服绑定 → {command_prefix()}信息。需要复制指令可发 {command_prefix()}帮助 文字。'],
                            config_key='AliceUID_HelpForward', title='AliceUID帮助')
