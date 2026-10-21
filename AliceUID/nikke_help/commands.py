"""Render the role-aware guide, with an accessible copyable text fallback."""
from __future__ import annotations
from ..nikke_commands import command_prefix
from ..nikke_ai import query as ai_query, active as ai_active, description as ai_description

from gsuid_core.logger import logger
from gsuid_core.segment import MessageSegment
from gsuid_core.sv import SV
from ..nikke_message import send_with_forward

from .draw import build_help_context, draw_help, help_text

sv_help = SV('妮姬帮助', pm=6, priority=3)


@sv_help.on_command('帮助',
    to_ai=ai_description("""获取AliceUID妮姬插件的使用说明、命令与本人账号绑定步骤；只返回指南，不执行登录或管理操作。
    Args:
        text: 留空或“文字”。例“妮姬插件怎么用”“妮姬怎么查角色练度”。
    """), covers=['AliceUID帮助', '妮姬插件命令', 'NIKKE账号绑定说明'],
    aliases=['妮姬·插件怎么用', '妮姬·查看帮助'])
@ai_query(sv_help)
async def nikke_help(bot, ev):
    option = (ev.text or '').strip()
    if option not in ('', '文字', '文本'):
        await bot.send(f'发送 {command_prefix()}帮助 查看图片指南；发送 {command_prefix()}帮助 文字 获取可复制的指令。', at_sender=True)
        return
    from ..nikke_config.config import AliceUIDConfig
    mode = AliceUIDConfig.get_config('AliceUID_LoginMode').data
    context = build_help_context(getattr(ev, 'user_pm', 6), login_mode=mode)
    if option or ai_active():
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
