"""Public guide query; permission checked before fetching and before delivery."""
from __future__ import annotations

from ..nikke_commands import command_prefix
from .service import get_guide
from .source import GuideUnavailable


def help_text():
    return (f'{command_prefix()}工会战阵容：获取固定作者本期联盟突袭攻略，无需绑定。\n'
        '默认合并转发三条：帖子原标题、組隊示例下的第一张阵容图、帖子正文完整长截图。\n'
        '长截图沿用转发JPG质量设置，默认95。战斗期缓存3天；休赛期长期保留最近一期。\n'
        '每次查询核对官方赛季，新一期开始清除旧攻略；新帖未发布提示稍后再试，失败冷却5分钟。')


class GuideCommands:
    def __init__(self, policy, *, service_factory=get_guide, sender=None, image_factory=None):
        self.policy, self.service_factory = policy, service_factory
        self.sender, self.image_factory = sender, image_factory

    async def allowed(self, ev):
        return (self.policy.user_allowed(getattr(ev, 'user_id', None))
                and await self.policy.query_allowed(getattr(ev, 'group_id', None)))

    async def handle(self, bot, ev):
        if not await self.allowed(ev):
            await bot.send('本群或当前用户未开放妮姬查询，请联系管理员。', at_sender=True)
            return
        if (getattr(ev, 'text', '') or '').strip():
            await bot.send(help_text(), at_sender=True)
            return
        try:
            result = await self.service_factory().get()
        except GuideUnavailable as exc:
            if await self.allowed(ev):
                await bot.send(str(exc), at_sender=True)
            return
        except Exception:
            if await self.allowed(ev):
                await bot.send('工会战攻略暂不可用，请稍后再试。', at_sender=True)
            return
        if not await self.allowed(ev):
            return
        image = self.image_factory
        sender = self.sender
        if image is None:
            from gsuid_core.segment import MessageSegment
            image = MessageSegment.image
        if sender is None:
            from ..nikke_message import send_with_forward
            sender = send_with_forward
        await sender(bot, ev, [result.title, image(result.team), image(result.screenshot)],
                     config_key='AliceUID_RaidGuideForward', at_sender=False)


_sv = None


def setup(policy=None):
    global _sv
    if _sv is not None:
        return _sv
    from gsuid_core.sv import SV
    from ..nikke_permissions.runtime import get_policy
    commands = GuideCommands(policy if policy is not None else get_policy())
    _sv = SV('妮姬工会战阵容攻略', pm=6, priority=3)

    @_sv.on_command(('工会战阵容', '公会战阵容'))
    async def raid_guide_command(bot, ev):
        await commands.handle(bot, ev)
    return _sv
