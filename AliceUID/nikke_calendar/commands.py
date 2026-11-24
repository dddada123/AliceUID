"""nk日历: public screenshot query, guarded before opening any browser."""
from __future__ import annotations
from ..nikke_commands import command_prefix

from .service import CalendarUnavailable, get_calendar

HELP = (f'命令：{command_prefix()}日历\n'
        '基于官网公开日程数据与官方 Banner/头像资源渲染当前活动日历，无需绑定账号。\n'
        f'{command_prefix()}日历 帮助：查看说明。暂不支持历史月份、指定日期或区服参数。\n'
        '不会按绑定区服筛选，Raid仅为活动日程，不含阵容或分数。\n'
        '图片缓存30分钟；官网异常时可能发送标明生成时间的旧图，失败后至少冷却5分钟。')


class CalendarCommands:
    def __init__(self, policy, *, service_factory=get_calendar, image_factory=None):
        self.policy = policy
        self.service_factory = service_factory
        self.image_factory = image_factory

    async def handle(self, bot, ev):
        try:
            from ..nikke_message.persona import send_reply
        except ImportError:
            async def send_reply(b, e, p, *, at_sender=True, newline=False, sep=None):
                return await b.send(p, at_sender=at_sender)
        if not await self.policy.query_allowed(getattr(ev, 'group_id', None)):
            await send_reply(bot, ev, '本群未开放妮姬查询，请联系群管理员或 Bot 主。', at_sender=True)
            return
        argument = (getattr(ev, 'text', '') or '').strip()
        if argument:
            await send_reply(bot, ev, HELP, at_sender=True)
            return
        try:
            result = await self.service_factory().get()
        except CalendarUnavailable as exc:
            await send_reply(bot, ev, str(exc), at_sender=True)
            return
        except Exception:
            await send_reply(bot, ev, '官网日历截图暂不可用，请稍后重试。', at_sender=True)
            return
        # The caption always includes source and actual capture time, including cache hits.
        image_factory = self.image_factory
        if image_factory is None:
            from gsuid_core.segment import MessageSegment
            image_factory = MessageSegment.image
        # Both are already ready: keep provenance/stale warning with its image.
        await send_reply(bot, ev, [image_factory(result.png), result.caption()], at_sender=True, newline=True)


_sv = None


def setup(policy=None):
    """Explicit, idempotent registration; root integration calls setup() once."""
    global _sv
    if _sv is not None:
        return _sv
    from gsuid_core.sv import SV
    from ..nikke_permissions.runtime import get_policy

    commands = CalendarCommands(policy if policy is not None else get_policy())
    _sv = SV('妮姬活动日历', pm=6, priority=3)

    @_sv.on_command('日历')
    async def calendar_command(bot, ev):
        await commands.handle(bot, ev)

    return _sv
