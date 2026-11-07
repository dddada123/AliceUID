"""Export bounded, sanitized plugin diagnostics to the requesting master."""
import asyncio
import re
from datetime import datetime

from gsuid_core.sv import SV
from gsuid_core.segment import MessageSegment
from ..nikke_commands import command_prefix
from ..nikke_user.service import is_master
from .store import export_markdown

sv_logs = SV('妮姬插件日志导出', pm=0, priority=3)
_busy = set()


@sv_logs.on_command('日志导出', block=True)
async def export_logs(bot, ev):
    if not is_master(ev.user_id):
        await bot.send('仅Bot主可以导出插件日志。')
        return
    text = ev.text.strip()
    if not re.fullmatch(r'[0-9]{1,4}', text) or not 1 <= int(text) <= 1440:
        await bot.send(f'用法：{command_prefix()}日志导出[分钟数]，范围1～1440。例如 {command_prefix()}日志导出10。')
        return
    owner = (str(ev.bot_id), str(ev.user_id))
    if owner in _busy:
        await bot.send('日志正在导出或发送，请稍候。')
        return
    _busy.add(owner)
    try:
        from gsuid_core import logger as core_logging
        history = tuple(core_logging.log_history.copy()) if hasattr(core_logging, 'log_history') else ()
        data = await asyncio.to_thread(export_markdown, int(text), history)
        if not is_master(ev.user_id):
            return
        filename = f'AliceUID_logs_{datetime.now():%Y%m%d_%H%M%S}_{int(text)}min.md'
        receipt = await bot.send(MessageSegment.file(data, filename))
        if receipt is False or receipt == []:
            await bot.send('日志文件已生成，但发送未确认。请检查接入端文件上传支持；未自动重发。')
    except asyncio.CancelledError:
        raise
    except Exception:
        await bot.send('日志导出或文件发送失败，请检查接入端文件上传和路径权限。')
    finally:
        _busy.discard(owner)
